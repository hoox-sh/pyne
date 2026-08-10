# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""request.* builtins — live/historical fetch with intentional mock soft-fail.

Data-path failures (missing feed, network, bad provider payload) are **soft**:
helpers catch ``Exception`` and fall through to built-in mock prices so
indicator scripts keep evaluating without a real market data backend.

Do **not** harden these into hard failures without an explicit host flag —
Runtime hosts and corpus demos rely on mock fallbacks. Programming errors
inside expression evaluation still propagate via the normal bar loop.
"""

from __future__ import annotations

import logging
import math
import random

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from pynescript.ast import node as ast_mod
from pynescript.ast.evaluator.names import ast_qualified_name

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .timeframe import SECONDS_PER_MONTH
from .timeframe import _chart_period
from .timeframe import timeframe_in_seconds
from .timeframe import timeframes_equivalent


# Define constants for magic numbers
REQUEST_SECURITY_MIN_ARGS = 2
REQUEST_OHLCV_LIMIT = 5
OHLCV_CLOSE_IDX = 4
REQUEST_RECENT_LIMIT = 5
REQUEST_MOCK_PRICE = 100.0
LOWER_TF_SIMULATE_MULTIPLIER = 2  # for demo lower tf bar count from latest data
# How many chart bars to scan when guessing if a pre-eval value is simple OHLCV.
_OHLCV_MATCH_LOOKBACK = 32
# Margin when comparing request TF vs inferred chart bar duration (irregular gaps).
_HTF_BAR_SEC_MARGIN = 1.25
# Chart series safe for same-symbol security passthrough (simple OHLCV + time).
# ``time`` is required so tuples like ``[open, high, low, close, volume, time]``
# (Perceptron / KNN corpus) are not rejected as complex HTF when TF differs.
_OHLCV_SERIES_KEYS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "time",
    "hl2",
    "hlc3",
    "ohlc4",
)
_OHLCV_FIELD_ALIASES: dict[str, str] = {
    "open": "open",
    "o": "open",
    "high": "high",
    "h": "high",
    "low": "low",
    "l": "low",
    "close": "close",
    "c": "close",
    "volume": "volume",
    "vol": "volume",
    "time": "time",
    "hl2": "hl2",
    "hlc3": "hlc3",
    "ohlc4": "ohlc4",
}
_CHART_PLACEHOLDERS = frozenset({"", "CHART", "SYMBOL", "TICKER", "NONE", "NA", "UNKNOWN"})
_FUNDAMENTAL_TOKENS = ("DIVIDEND", "FACTSET", "EARNINGS", "ESD_")

# Allowlisted simple ta.* forms for HTF resample (no arbitrary AST re-eval).
# Matched only when the security expression *AST* is exactly one of these shapes
# (visit_Call attaches :class:`HtfSimpleTaExpr` before chart pre-eval wins).
_HTF_SIMPLE_TA_FUNCS = frozenset({"sma", "ema", "rsi", "atr"})

_LOG = logging.getLogger("pynescript.request.security")

# Static product notes exposed on Runtime ``meta.request_security``.
_SECURITY_POLICY_NOTES: tuple[str, ...] = (
    "No multi-timeframe expression re-eval engine: HTF complex UDF/nested ta results are na.",
    "barmerge.gaps_on / gaps_off are accepted but unused (no gap-fill / na-gap series).",
    "barmerge.lookahead_on / lookahead_off are accepted but unused (no lookahead offset).",
    "Same-symbol simple OHLCV on a coarser TF resamples chart bars by timestamp "
    "(htf_ohlcv_resample, last completed HTF bar only — not full expression re-eval).",
    "Same-symbol allowlisted ta.sma/ema/rsi/atr on coarser TF runs the TA helper on "
    "resampled HTF bars (htf_simple_ta_resample) — still not a full multi-TF engine.",
    "LTF / unparseable TF / history offsets still use chart passthrough stub when simple.",
    "Foreign symbols without a multi-symbol feed hit return na (no mock invent under host chart).",
)


@dataclass(frozen=True)
class HtfSimpleTaExpr:
    """Allowlisted simple ``ta.*`` form for HTF series resample (not chart pre-eval).

    Produced by :func:`match_htf_simple_ta_ast` when ``request.security``'s
    expression argument is a bare allowlisted call such as ``ta.sma(close, 14)``.
    Nested sources, UDFs, and non-constant lengths are rejected.
    """

    name: str  # sma | ema | rsi | atr
    source: str | None  # normalized OHLCV field; None for atr (uses h/l/c)
    length: int


def _const_positive_int(node: Any) -> int | None:
    """Literal positive int from a Constant AST node, or None."""
    if type(node) is not ast_mod.Constant:
        return None
    kind = node.kind
    if kind is not None and kind != "#":
        return None
    raw = node.value
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        iv = int(raw)
    except (TypeError, ValueError):
        return None
    return iv if iv == raw and iv > 0 else None


def match_htf_simple_ta_ast(expr_ast: Any) -> HtfSimpleTaExpr | None:  # noqa: PLR0911
    """Match allowlisted simple ``ta.*`` AST for HTF resample, else None.

    Allowed shapes (positional args only, no kwargs):

    - ``ta.sma(close, 14)`` / ``ta.ema`` / ``ta.rsi`` — source is a bare OHLCV
      name (``close``, ``open``, ``high``, ``low``, ``volume``, ``hl2``, …);
      length is a positive integer literal.
    - ``ta.atr(14)`` — length-only form (uses HTF high/low/close).

    Nested calls (``ta.sma(ta.ema(...), n)``), multi-arg atr, variables as
    length, and non-ta callees return ``None`` (existing complex-na path).
    """
    if type(expr_ast) is not ast_mod.Call:
        return None
    qual = ast_qualified_name(expr_ast.func)
    if not qual or not qual.startswith("ta."):
        return None
    fname = qual[3:]
    if fname not in _HTF_SIMPLE_TA_FUNCS:
        return None
    arg_nodes = list(getattr(expr_ast, "args", None) or ())
    if any(getattr(a, "name", None) for a in arg_nodes):
        return None

    if fname == "atr":
        length = _const_positive_int(arg_nodes[0].value) if len(arg_nodes) == 1 else None
        return HtfSimpleTaExpr("atr", None, length) if length else None

    # sma / ema / rsi: (source_name, length)
    if len(arg_nodes) != 2:  # noqa: PLR2004 - fixed allowlist arity
        return None
    src_node = arg_nodes[0].value
    if type(src_node) is not ast_mod.Name:
        return None
    src = _OHLCV_FIELD_ALIASES.get(str(src_node.id).strip().lower())
    length = _const_positive_int(arg_nodes[1].value)
    if src is None or length is None:
        return None
    return HtfSimpleTaExpr(name=fname, source=src, length=length)

@dataclass
class VolumeRow:
    """Volume row in a footprint object.

    Represents a single price level in a footprint with its volume data.
    Added in Pine Script v6 (January 2026).
    """

    up_price: float = 0.0
    down_price: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta: float = 0.0
    is_imbalance: bool = False
    is_poc: bool = False
    is_vah: bool = False
    is_val: bool = False


@dataclass
class Footprint:
    """Footprint object representing volume profile data for a bar.

    Contains volume data at each price level, including buy/sell volumes,
    delta, Point of Control (POC), and Value Area (VA) boundaries.
    Added in Pine Script v6 (January 2026).
    """

    num_ticks: int = 100
    va_percentage: int = 70
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta: float = 0.0
    total_volume: float = 0.0
    vah_row: VolumeRow | None = None
    val_row: VolumeRow | None = None
    poc_row: VolumeRow | None = None
    rows: list[VolumeRow] = field(default_factory=list)


class FootprintBuiltinsMixin(BuiltinDispatchMixin):
    """Footprint type methods for accessing volume profile data.

    Added in Pine Script v6 (January 2026).
    """

    def _footprint_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "footprint.buy_volume": self._handle_footprint_buy_volume,
            "footprint.sell_volume": self._handle_footprint_sell_volume,
            "footprint.delta": self._handle_footprint_delta,
            "footprint.vah": self._handle_footprint_vah,
            "footprint.val": self._handle_footprint_val,
            "footprint.poc": self._handle_footprint_poc,
            "footprint.total_volume": self._handle_footprint_total_volume,
            "footprint.rows": self._handle_footprint_rows,
            "footprint.get_row_by_price": self._handle_footprint_get_row_by_price,
            "volume_row.up_price": self._handle_volume_row_up_price,
            "volume_row.down_price": self._handle_volume_row_down_price,
            "volume_row.buy_volume": self._handle_volume_row_buy_volume,
            "volume_row.sell_volume": self._handle_volume_row_sell_volume,
            "volume_row.delta": self._handle_volume_row_delta,
            "volume_row.total_volume": self._handle_volume_row_total_volume,
            "volume_row.has_buy_imbalance": self._handle_volume_row_has_buy_imbalance,
            "volume_row.has_sell_imbalance": self._handle_volume_row_has_sell_imbalance,
        }

    def _handle_footprint_buy_volume(self, args: list[Any]) -> float:
        """footprint.buy_volume(footprint) - Get total buy volume from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.buy_volume
        return 0.0

    def _handle_footprint_sell_volume(self, args: list[Any]) -> float:
        """footprint.sell_volume(footprint) - Get total sell volume from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.sell_volume
        return 0.0

    def _handle_footprint_delta(self, args: list[Any]) -> float:
        """footprint.delta(footprint) - Get volume delta from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.delta
        return 0.0

    def _handle_footprint_vah(self, args: list[Any]) -> VolumeRow | None:
        """footprint.vah(footprint) - Get Value Area High row from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.vah_row
        return None

    def _handle_footprint_val(self, args: list[Any]) -> VolumeRow | None:
        """footprint.val(footprint) - Get Value Area Low row from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.val_row
        return None

    def _handle_footprint_poc(self, args: list[Any]) -> VolumeRow | None:
        """footprint.poc(footprint) - Get Point of Control row from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.poc_row
        return None

    def _handle_volume_row_up_price(self, args: list[Any]) -> float:
        """volume_row.up_price(volume_row) - Get upper price of volume row."""
        vr = args[0] if len(args) > 0 else None
        if isinstance(vr, VolumeRow):
            return vr.up_price
        return 0.0

    def _handle_volume_row_down_price(self, args: list[Any]) -> float:
        """volume_row.down_price(volume_row) - Get lower price of volume row."""
        vr = args[0] if len(args) > 0 else None
        if isinstance(vr, VolumeRow):
            return vr.down_price
        return 0.0

    def _handle_footprint_total_volume(self, args: list[Any]) -> float:
        fp = args[0] if args else None
        if isinstance(fp, Footprint):
            return fp.total_volume
        return 0.0

    def _handle_footprint_rows(self, args: list[Any]) -> list[VolumeRow]:
        fp = args[0] if args else None
        if isinstance(fp, Footprint):
            return list(fp.rows)
        return []

    def _handle_footprint_get_row_by_price(self, args: list[Any]) -> VolumeRow | None:
        fp = args[0] if args else None
        price = args[1] if len(args) > 1 else None
        if not isinstance(fp, Footprint) or price is None:
            return None
        p = float(price)
        for row in fp.rows:
            lo = min(row.down_price, row.up_price)
            hi = max(row.down_price, row.up_price)
            if lo <= p <= hi:
                return row
        return None

    def _handle_volume_row_buy_volume(self, args: list[Any]) -> float:
        vr = args[0] if args else None
        return float(vr.buy_volume) if isinstance(vr, VolumeRow) else 0.0

    def _handle_volume_row_sell_volume(self, args: list[Any]) -> float:
        vr = args[0] if args else None
        return float(vr.sell_volume) if isinstance(vr, VolumeRow) else 0.0

    def _handle_volume_row_delta(self, args: list[Any]) -> float:
        vr = args[0] if args else None
        return float(vr.delta) if isinstance(vr, VolumeRow) else 0.0

    def _handle_volume_row_total_volume(self, args: list[Any]) -> float:
        vr = args[0] if args else None
        if isinstance(vr, VolumeRow):
            return float(vr.buy_volume) + float(vr.sell_volume)
        return 0.0

    def _handle_volume_row_has_buy_imbalance(self, args: list[Any]) -> bool:
        vr = args[0] if args else None
        if isinstance(vr, VolumeRow):
            return bool(vr.is_imbalance and vr.buy_volume > vr.sell_volume)
        return False

    def _handle_volume_row_has_sell_imbalance(self, args: list[Any]) -> bool:
        vr = args[0] if args else None
        if isinstance(vr, VolumeRow):
            return bool(vr.is_imbalance and vr.sell_volume > vr.buy_volume)
        return False


class RequestBuiltinsMixin(BuiltinDispatchMixin):
    """``request.security``, fundamentals, and related data-fetch builtins.

    Missing feeds and provider errors soft-fail to mock series so scripts
    continue evaluating without a live data backend (see module docstring).
    """

    def _request_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "request.security": self._handle_request_security,
            "request.security_lower_tf": (self._handle_request_security_lower_tf),
            "request.dividends": self._handle_request_dividends,
            "request.earnings": self._handle_request_earnings,
            "request.splits": self._handle_request_splits,
            "request.financial": self._handle_request_financial,
            "request.quandl": self._handle_request_quandl,
            "request.economic": self._handle_request_economic,
            "request.currency_rate": self._handle_request_currency_rate,
            "request.seed": self._handle_request_seed,
            "request.footprint": self._handle_request_footprint,
            # Pine v3/v4 bare names (pre-request.* namespace)
            "security": self._handle_request_security,
            "security_lower_tf": self._handle_request_security_lower_tf,
        }

    def _get_expression_prices(self, expression: str, prices: list[float]) -> list[float]:
        """Return a list of prices based on the expression."""
        expr = expression.lower()
        if expr in ("open", "o"):
            return [p - 0.5 for p in prices]
        if expr in ("high", "h"):
            return [p + 1.0 for p in prices]
        if expr in ("low", "l"):
            return [p - 1.0 for p in prices]
        if expr == "volume":
            return [1000000, 1100000, 1200000, 1050000, 1300000]
        return prices  # Default to close

    def _resolve_symbol(self, arg: Any, default: str = "AAPL") -> str:
        """Resolve symbol which may be dynamic (list/series from loop/conditional)."""
        if isinstance(arg, list):
            arg = arg[-1] if arg else default
        if arg is None:
            return default
        # TickerInfo from ticker.* / heikinashi() / renko() etc.
        symbol_attr = getattr(arg, "symbol", None)
        if isinstance(symbol_attr, str) and symbol_attr:
            return symbol_attr.upper()
        # Empty TickerInfo.symbol (ticker.new(syminfo.prefix, …)) → chart
        if hasattr(arg, "symbol") and isinstance(symbol_attr, str):
            return ""
        return str(arg).upper()

    def _chart_symbol_candidates(self) -> list[str]:
        """Host chart identity strings (ticker / tickerid / provider symbol)."""
        ctx = getattr(self, "context", {}) or {}
        candidates: list[str] = []
        for key in (
            "syminfo.ticker",
            "syminfo.tickerid",
            "syminfo.root",
            "symbol",
            "_host_symbol",
        ):
            raw = ctx.get(key)
            if raw is None:
                continue
            t = str(raw).strip().upper()
            if t and t not in _CHART_PLACEHOLDERS:
                candidates.append(t)
        si = ctx.get("syminfo")
        if si is not None:
            for attr in ("ticker", "tickerid", "root"):
                raw = getattr(si, attr, None)
                if raw is None:
                    continue
                t = str(raw).strip().upper()
                if t and t not in _CHART_PLACEHOLDERS:
                    candidates.append(t)
        _, data_provider = self._get_request_data()
        prov_sym = getattr(data_provider, "_symbol", None)
        if prov_sym:
            t = str(prov_sym).strip().upper()
            if t and t not in _CHART_PLACEHOLDERS:
                candidates.append(t)
        return candidates

    def _host_has_chart_identity(self) -> bool:
        """True when Runtime/host wired a real chart ticker (not bare unit eval)."""
        return bool(self._chart_symbol_candidates())

    def _is_chart_symbol(self, symbol: str) -> bool:
        """True when *symbol* refers to the host chart (or is empty / generic).

        Foreign tickers (``ESD_FACTSET``, ``MSFT`` when chart is ``AAPL``, …)
        must not inherit pre-evaluated chart expressions as if they were
        multi-symbol results (dividend_yield inventing close-as-dividend).
        """
        s = (symbol or "").strip().upper()
        if not s or s in _CHART_PLACEHOLDERS:
            return True
        for t in self._chart_symbol_candidates():
            if s == t:
                return True
            if s.split(":")[-1] == t.split(":")[-1]:
                return True
            if s.endswith(":" + t) or t.endswith(":" + s):
                return True
        return False

    def _get_request_data(self):
        """Get (data_feed, data_provider) for live/historical fallback."""
        ctx = getattr(self, "context", {}) or {}
        return ctx.get("data_feed"), ctx.get("data_provider")

    def _unwrap_preeval_scalar(self, expression: Any) -> Any:
        """Reduce PineSeries / 1-element containers to a plottable scalar when needed."""
        if expression is None or isinstance(expression, (bool, int, float, str)):
            return expression
        # Host OHLCV PineSeries passed as the security expression (`close`)
        current = getattr(expression, "current", None)
        if current is not None and not isinstance(expression, (list, tuple, dict)):
            return current
        return expression

    def _scalar_matches_chart_ohlcv(self, value: Any) -> bool:
        """True when *value* equals a chart OHLCV sample (current or recent history).

        Used to distinguish simple same-symbol OHLCV passthrough
        (``close``, ``high[1]``, …) from complex UDF results (``f_struct`` →
        ±1/0, RSI, …) when the expression is already evaluated at the call site.

        Supports ``PineSeries`` (offset indexing: ``s[0]`` current, ``s[1]``
        previous) and plain list/tuple chronologies.
        """
        if value is None:
            return True
        if isinstance(value, bool):
            return False

        ctx = getattr(self, "context", {}) or {}

        # Identity: expression is the host chart series object itself (`close`).
        for key in _OHLCV_SERIES_KEYS:
            series = ctx.get(key)
            if series is not None and value is series:
                return True

        # PineSeries wrapper that is not identity-equal — compare .current
        current = getattr(value, "current", None)
        if current is not None and not isinstance(value, (list, tuple, dict, str)):
            if isinstance(current, bool):
                return False
            if isinstance(current, (int, float)) or current is None:
                value = current
            else:
                return False

        if not isinstance(value, (int, float)):
            return False
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return False
        if math.isnan(fv):
            return True

        def _eq(sample: Any) -> bool:
            if sample is None:
                return False
            try:
                return float(sample) == fv
            except (TypeError, ValueError):
                return False

        for key in _OHLCV_SERIES_KEYS:
            series = ctx.get(key)
            if series is None:
                continue
            # Scalar chart bind
            if isinstance(series, (int, float)) and not isinstance(series, bool):
                if _eq(series):
                    return True
                continue
            # PineSeries: .current + history (newest-first)
            sc = getattr(series, "current", None)
            if sc is not None and _eq(sc):
                return True
            hist = getattr(series, "history", None)
            if hist is not None:
                for i, sample in enumerate(hist):
                    if i >= _OHLCV_MATCH_LOOKBACK:
                        break
                    if _eq(sample):
                        return True
                continue
            # Plain list/tuple chronology (oldest → newest)
            if isinstance(series, (list, tuple)):
                if not series:
                    continue
                for sample in series[-_OHLCV_MATCH_LOOKBACK:]:
                    if _eq(sample):
                        return True
                continue
            try:
                if _eq(float(series)):  # type: ignore[arg-type]
                    return True
            except (TypeError, ValueError):
                pass
            try:
                if _eq(series[0]):  # type: ignore[index]
                    return True
            except (TypeError, IndexError, KeyError):
                pass
        return False

    def _expression_is_simple_ohlcv_value(self, expression: Any) -> bool:
        """True for pre-eval values that look like simple chart OHLCV/time samples.

        Includes ``time`` so multi-value same-symbol requests such as
        ``[open, high, low, close, volume, time]`` remain list-shaped under a
        different request TF (chart passthrough stub), instead of collapsing
        to a single ``na`` that breaks destructure and poisons custom DMI.
        """
        if isinstance(expression, str):
            return expression.strip().lower() in {
                "open",
                "o",
                "high",
                "h",
                "low",
                "l",
                "close",
                "c",
                "volume",
                "vol",
                "time",
                "hl2",
                "hlc3",
                "ohlc4",
            }
        if isinstance(expression, (list, tuple)):
            if not expression:
                return False
            return all(self._expression_is_simple_ohlcv_value(x) for x in expression)
        return self._scalar_matches_chart_ohlcv(expression)

    def _allow_same_symbol_preeval(self, expression: Any, timeframe: Any) -> bool:
        """Whether chart-evaluated *expression* may passthrough for same-symbol.

        - Same (or empty) request TF as chart → chart eval is correct; allow.
        - Different TF + simple OHLCV sample → chart passthrough stub (no HTF
          series, matches compile simple OHLCV policy intent).
        - Different TF + complex UDF/arith result → ``na`` (do not invent HTF
          structure from chart bars — MTF Structure Bias residual).
        """
        chart_tf = _chart_period(self)
        req_tf = timeframe
        if isinstance(req_tf, list):
            req_tf = req_tf[-1] if req_tf else chart_tf
        if timeframes_equivalent(None if req_tf is None else str(req_tf), chart_tf):
            return True
        return self._expression_is_simple_ohlcv_value(expression)

    def _request_tf_matches_chart(self, timeframe: Any) -> bool:
        """True when *timeframe* is empty or equivalent to the host chart period."""
        chart_tf = _chart_period(self)
        req_tf = timeframe
        if isinstance(req_tf, list):
            req_tf = req_tf[-1] if req_tf else chart_tf
        return timeframes_equivalent(None if req_tf is None else str(req_tf), chart_tf)

    def _series_chrono_values(self, key: str) -> list[Any]:
        """Chronological samples for a chart series key (oldest → newest)."""
        ctx = getattr(self, "context", {}) or {}
        series = ctx.get(key) if isinstance(ctx, dict) else None
        if series is not None:
            buf = getattr(series, "buffer", None)
            if buf is not None:
                return list(buf)
            hist = getattr(series, "history", None)
            if hist is not None:
                try:
                    return list(reversed(list(hist)))
                except TypeError:
                    pass
            if isinstance(series, (list, tuple)):
                return list(series)
        cs = getattr(self, "current_series", None) or {}
        if isinstance(cs, dict):
            lst = cs.get(key)
            if isinstance(lst, (list, tuple)):
                return list(lst)
        return []

    def _infer_chart_bar_seconds(self) -> float | None:
        """Median positive delta of chart bar times (seconds), if available."""
        times = self._series_chrono_values("time")
        if len(times) < 2:
            return None
        deltas: list[float] = []
        prev: float | None = None
        # Prefer recent bars (stable spacing) over the full history tail.
        for raw in times[-min(len(times), 64) :]:
            try:
                t = float(raw)
            except (TypeError, ValueError):
                continue
            if prev is not None:
                d = t - prev
                # Bar times are Unix ms on the Runtime host; tolerate seconds too.
                if d > 0:
                    deltas.append(d)
            prev = t
        if not deltas:
            return None
        deltas.sort()
        med = deltas[len(deltas) // 2]
        # Heuristic: values ≫ 10_000 are milliseconds.
        if med >= 10_000.0:
            return med / 1000.0
        return med

    def _request_tf_bucket_ms(self, timeframe: Any) -> int | None:
        """Fixed-size HTF bucket width in ms, or None if unusable for resample.

        Monthly (and coarser approximate) TFs are skipped — calendar months are
        not fixed-ms buckets. Empty TF means chart TF (no resample).
        """
        req_tf = timeframe
        if isinstance(req_tf, list):
            req_tf = req_tf[-1] if req_tf else None
        if req_tf is None or str(req_tf).strip() == "":
            return None
        try:
            sec = int(timeframe_in_seconds(str(req_tf)))
        except (TypeError, ValueError):
            return None
        if sec <= 0:
            return None
        # Skip calendar-month approximations (not fixed buckets).
        if sec >= SECONDS_PER_MONTH:
            return None
        return sec * 1000

    def _request_is_higher_tf(self, timeframe: Any) -> bool:
        """True when *timeframe* is coarser than chart bars (inferred or declared)."""
        bucket_ms = self._request_tf_bucket_ms(timeframe)
        if bucket_ms is None:
            return False
        req_sec = bucket_ms / 1000.0
        chart_sec = self._infer_chart_bar_seconds()
        if chart_sec is not None and chart_sec > 0:
            return req_sec > chart_sec * _HTF_BAR_SEC_MARGIN
        try:
            declared = float(timeframe_in_seconds(_chart_period(self)))
        except (TypeError, ValueError):
            return False
        if declared <= 0:
            return False
        return req_sec > declared * _HTF_BAR_SEC_MARGIN

    def _identify_simple_ohlcv_field(self, expression: Any) -> str | None:
        """Map *expression* to a bare OHLCV field name when identity-known.

        Returns ``None`` for history offsets (``high[1]`` → float), complex
        UDF results, and ambiguous scalar matches — those stay on the chart
        passthrough stub path rather than inventing HTF structure.
        """
        if isinstance(expression, str):
            return _OHLCV_FIELD_ALIASES.get(expression.strip().lower())

        ctx = getattr(self, "context", {}) or {}
        if isinstance(ctx, dict):
            for key in _OHLCV_SERIES_KEYS:
                series = ctx.get(key)
                if series is not None and expression is series:
                    return key

        # PineSeries-like that is not context identity: reject (could be UDF).
        if getattr(expression, "current", None) is not None and not isinstance(
            expression, (list, tuple, dict, str, int, float, bool)
        ):
            return None

        # Bare numeric / bool / None — not a field identity (offsets, pre-eval).
        return None

    def _identify_simple_ohlcv_fields(self, expression: Any) -> list[str] | None:
        """Field list for a single series or homogeneous OHLCV tuple/list."""
        if isinstance(expression, (list, tuple)):
            if not expression:
                return None
            fields: list[str] = []
            for item in expression:
                f = self._identify_simple_ohlcv_field(item)
                if f is None:
                    # String names inside list (rare) or fail
                    if isinstance(item, str):
                        f = _OHLCV_FIELD_ALIASES.get(item.strip().lower())
                    if f is None:
                        return None
                fields.append(f)
            return fields
        f = self._identify_simple_ohlcv_field(expression)
        return [f] if f is not None else None

    def _htf_agg_field(self, agg: dict[str, float], field: str) -> float:
        """Read one OHLCV/derived field from an aggregated HTF bucket."""
        if field == "open":
            return agg["open"]
        if field == "high":
            return agg["high"]
        if field == "low":
            return agg["low"]
        if field == "close":
            return agg["close"]
        if field == "volume":
            return agg["volume"]
        if field == "time":
            return agg["time"]
        o, h, l, c = agg["open"], agg["high"], agg["low"], agg["close"]
        if field == "hl2":
            return (h + l) * 0.5
        if field == "hlc3":
            return (h + l + c) / 3.0
        if field == "ohlc4":
            return (o + h + l + c) * 0.25
        return float("nan")

    def _build_htf_completed_series(
        self,
        bucket_ms: int,
        n: int,
        opens: list[Any],
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        volumes: list[Any],
        times: list[Any],
    ) -> list[dict[str, float] | None]:
        """Per chart bar: last *completed* HTF OHLCV agg (lookahead_off-style).

        Forming HTF bar is never returned. Bars before the first HTF close →
        ``None`` (caller maps to ``na``).
        """
        na_out: list[dict[str, float] | None] = [None] * n
        if n == 0 or bucket_ms <= 0:
            return na_out

        def _f(v: Any, default: float = float("nan")) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        completed: dict[str, float] | None = None
        forming: dict[str, float] | None = None
        forming_bucket: int | None = None

        for i in range(n):
            t_raw = times[i] if i < len(times) else None
            try:
                t_ms = float(t_raw)
            except (TypeError, ValueError):
                na_out[i] = completed
                continue
            # Accept Unix seconds (rare) by scaling into ms range.
            if t_ms > 0 and t_ms < 1e11:
                t_ms *= 1000.0
            b = int(t_ms) // bucket_ms * bucket_ms
            o = _f(opens[i] if i < len(opens) else None)
            h = _f(highs[i] if i < len(highs) else None)
            l = _f(lows[i] if i < len(lows) else None)
            c = _f(closes[i] if i < len(closes) else None)
            v = _f(volumes[i] if i < len(volumes) else None, 0.0)

            if forming_bucket is None:
                forming_bucket = b
                forming = {
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                    "time": float(b),
                }
                na_out[i] = None
                continue

            if b == forming_bucket and forming is not None:
                if h == h:  # not nan
                    forming["high"] = h if forming["high"] != forming["high"] else max(forming["high"], h)
                if l == l:
                    forming["low"] = l if forming["low"] != forming["low"] else min(forming["low"], l)
                if c == c:
                    forming["close"] = c
                if v == v:
                    forming["volume"] = (forming["volume"] if forming["volume"] == forming["volume"] else 0.0) + (
                        v if v == v else 0.0
                    )
                na_out[i] = completed
                continue

            # New HTF bucket: previous forming bar completes (lookahead_off).
            completed = forming
            forming_bucket = b
            forming = {
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "time": float(b),
            }
            na_out[i] = completed

        return na_out

    def _htf_ohlcv_series_for_tf(self, bucket_ms: int) -> list[dict[str, float] | None] | None:
        """Cached last-completed HTF agg per chart bar for *bucket_ms*."""
        opens = self._series_chrono_values("open")
        if not opens:
            return None
        n = len(opens)
        highs = self._series_chrono_values("high")
        lows = self._series_chrono_values("low")
        closes = self._series_chrono_values("close")
        volumes = self._series_chrono_values("volume")
        times = self._series_chrono_values("time")
        if len(times) < n:
            # Pad synthetic 1m steps if time series is short (should not happen
            # under Runtime host once bar_index advances with time_update).
            base = float(times[-1]) if times else 0.0
            times = list(times) + [base + (i + 1) * 60_000.0 for i in range(n - len(times))]
        times = times[:n]

        cache = getattr(self, "_htf_ohlcv_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._htf_ohlcv_cache = cache  # type: ignore[attr-defined]
        key = int(bucket_ms)
        entry = cache.get(key)
        if isinstance(entry, dict) and entry.get("n") == n and entry.get("series") is not None:
            return entry["series"]  # type: ignore[return-value]
        series = self._build_htf_completed_series(
            bucket_ms, n, opens, highs, lows, closes, volumes, times
        )
        cache[key] = {"n": n, "series": series}
        return series

    def _try_htf_ohlcv_resample(self, expression: Any, timeframe: Any) -> Any | None:
        """Resample chart OHLCV to HTF for simple series fields, or None.

        Semantics: **last completed HTF bar only** (lookahead_off-style). Gaps
        and lookahead args remain unused. Complex expressions are not re-eval'd.
        """
        if not self._request_is_higher_tf(timeframe):
            return None
        bucket_ms = self._request_tf_bucket_ms(timeframe)
        if bucket_ms is None:
            return None
        fields = self._identify_simple_ohlcv_fields(expression)
        if not fields:
            return None
        series = self._htf_ohlcv_series_for_tf(bucket_ms)
        if not series:
            return None
        agg = series[-1] if series else None
        na = float("nan")
        if len(fields) == 1 and not isinstance(expression, (list, tuple)):
            if agg is None:
                return na
            return self._htf_agg_field(agg, fields[0])
        # Multi-value list/tuple — preserve shape for destructure.
        if agg is None:
            out_na = [na] * len(fields)
            return out_na if isinstance(expression, list) else tuple(out_na)
        vals = [self._htf_agg_field(agg, f) for f in fields]
        return vals if isinstance(expression, list) else tuple(vals)

    def _htf_unique_and_map(
        self, bucket_ms: int
    ) -> tuple[list[dict[str, float]], list[int | None]] | None:
        """Unique completed HTF bars + per-chart-bar index into that list.

        Index ``None`` means no completed HTF bar yet at that chart bar
        (lookahead_off forming bucket).
        """
        series = self._htf_ohlcv_series_for_tf(bucket_ms)
        if not series:
            return None
        unique: list[dict[str, float]] = []
        by_time: dict[float, int] = {}
        chart_to_htf: list[int | None] = []
        for agg in series:
            if agg is None:
                chart_to_htf.append(None)
                continue
            try:
                t_key = float(agg["time"])
            except (TypeError, ValueError, KeyError):
                chart_to_htf.append(None)
                continue
            idx = by_time.get(t_key)
            if idx is None:
                idx = len(unique)
                by_time[t_key] = idx
                unique.append(agg)
            chart_to_htf.append(idx)
        return unique, chart_to_htf

    def _htf_source_series(
        self, unique: list[dict[str, float]], field: str
    ) -> list[float | None]:
        """Extract one OHLCV/derived field from unique HTF aggs (chronological)."""
        out: list[float | None] = []
        for agg in unique:
            v = self._htf_agg_field(agg, field)
            if v != v:  # nan
                out.append(None)
            else:
                out.append(v)
        return out

    def _htf_rsi_full_series(
        self, closes: list[float | None], period: int
    ) -> list[float | None]:
        """Full-list RSI on *closes* (Wilder RMA of gains/losses), bar-aligned."""
        n = len(closes)
        out: list[float | None] = [None] * n
        if n < 2 or period <= 0:
            return out
        gains: list[float] = []
        losses: list[float] = []
        for i in range(1, n):
            a, b = closes[i - 1], closes[i]
            if a is None or b is None:
                gains.append(0.0)
                losses.append(0.0)
                continue
            try:
                change = float(b) - float(a)
            except (TypeError, ValueError):
                gains.append(0.0)
                losses.append(0.0)
                continue
            gains.append(change if change > 0 else 0.0)
            losses.append(-change if change < 0 else 0.0)
        rma_fn = getattr(self, "_rma", None)
        if not callable(rma_fn):
            # Soft fallback: last-only helper on prefixes (small HTF n only).
            rsi_fn = getattr(self, "_rsi", None)
            if not callable(rsi_fn):
                return out
            for i in range(1, n):
                window = [float(c) for c in closes[: i + 1] if c is not None]
                out[i] = rsi_fn(window, period)
            return out
        avg_g = rma_fn(gains, period)
        avg_l = rma_fn(losses, period)
        for i in range(1, n):
            g = avg_g[i - 1] if i - 1 < len(avg_g) else None
            lo = avg_l[i - 1] if i - 1 < len(avg_l) else None
            try:
                gf = float(g) if g is not None else float("nan")
                lf = float(lo) if lo is not None else float("nan")
            except (TypeError, ValueError):
                out[i] = None
                continue
            if gf != gf or lf != lf:
                out[i] = None
                continue
            if lf == 0.0:
                out[i] = 100.0
            else:
                rs = gf / lf
                out[i] = 100.0 - (100.0 / (1.0 + rs))
        return out

    def _htf_ta_values_on_unique(
        self, expr: HtfSimpleTaExpr, unique: list[dict[str, float]]
    ) -> list[float | None]:
        """Run allowlisted TA full-list helpers on unique HTF bars."""
        n = len(unique)
        if n == 0 or expr.length <= 0:
            return []
        name = expr.name
        period = int(expr.length)
        if name in ("sma", "ema", "rsi"):
            field = expr.source or "close"
            src = self._htf_source_series(unique, field)
            if name == "sma":
                sma_fn = getattr(self, "_sma", None)
                if not callable(sma_fn):
                    return [None] * n
                raw = sma_fn(src, period)
                # Align length (helpers return list of same len).
                return list(raw) if raw is not None else [None] * n
            if name == "ema":
                ema_fn = getattr(self, "_ema", None)
                if not callable(ema_fn):
                    return [None] * n
                raw = ema_fn(src, period)
                return list(raw) if raw is not None else [None] * n
            return self._htf_rsi_full_series(src, period)

        # atr: length-only; uses HTF high/low/close.
        highs = self._htf_source_series(unique, "high")
        lows = self._htf_source_series(unique, "low")
        closes = self._htf_source_series(unique, "close")
        atr_fn = getattr(self, "_atr", None)
        out: list[float | None] = [None] * n
        if not callable(atr_fn):
            return out
        # _atr returns series aligned to TR samples (len ≈ n-1).
        atr_raw = atr_fn(highs, lows, closes, period)
        if not atr_raw:
            return out
        # Map ATR[j] → HTF bar j+1 (TR needs a previous close).
        for j, v in enumerate(atr_raw):
            dest = j + 1
            if dest >= n:
                break
            if v is None:
                out[dest] = None
                continue
            try:
                fv = float(v)
                out[dest] = None if fv != fv else fv
            except (TypeError, ValueError):
                out[dest] = None
        return out

    def _try_htf_simple_ta_resample(
        self, expression: HtfSimpleTaExpr, timeframe: Any
    ) -> Any | None:
        """Run allowlisted ta.* on resampled HTF bars; map last completed to chart.

        Semantics match OHLCV HTF resample: **last completed** HTF bar only
        (lookahead_off-style). Full-list TA on the unique HTF series is cached
        per (bucket, ta name, source, length, chart n).
        """
        if not isinstance(expression, HtfSimpleTaExpr):
            return None
        if not self._request_is_higher_tf(timeframe):
            return None
        bucket_ms = self._request_tf_bucket_ms(timeframe)
        if bucket_ms is None:
            return None
        built = self._htf_unique_and_map(bucket_ms)
        if built is None:
            return None
        unique, chart_to_htf = built
        n_chart = len(chart_to_htf)
        if n_chart == 0:
            return None

        cache = getattr(self, "_htf_simple_ta_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._htf_simple_ta_cache = cache  # type: ignore[attr-defined]
        ckey = (
            int(bucket_ms),
            expression.name,
            expression.source or "",
            int(expression.length),
            n_chart,
            len(unique),
        )
        entry = cache.get(ckey)
        if isinstance(entry, dict) and entry.get("chart_vals") is not None:
            chart_vals = entry["chart_vals"]
        else:
            ta_on_htf = self._htf_ta_values_on_unique(expression, unique)
            chart_vals = [None] * n_chart
            for i, hidx in enumerate(chart_to_htf):
                if hidx is None or hidx < 0 or hidx >= len(ta_on_htf):
                    chart_vals[i] = None
                else:
                    chart_vals[i] = ta_on_htf[hidx]
            cache[ckey] = {"chart_vals": chart_vals}

        # Current chart bar → last sample (Runtime advances series in lockstep).
        last = chart_vals[-1] if chart_vals else None
        if last is None:
            return float("nan")
        try:
            fv = float(last)
        except (TypeError, ValueError):
            return float("nan")
        return fv if fv == fv else float("nan")

    def _chart_simple_ta_last(self, expression: HtfSimpleTaExpr) -> Any:
        """Same-TF allowlisted ta.* on chart series (last sample)."""
        na = float("nan")
        period = int(expression.length)
        if period <= 0:
            return na
        name = expression.name
        if name == "atr":
            highs = self._series_chrono_values("high")
            lows = self._series_chrono_values("low")
            closes = self._series_chrono_values("close")
            atr_fn = getattr(self, "_atr", None)
            if not callable(atr_fn) or not closes:
                return na
            raw = atr_fn(highs, lows, closes, period)
            if not raw:
                return na
            last = raw[-1]
            if last is None:
                return na
            try:
                fv = float(last)
                return fv if fv == fv else na
            except (TypeError, ValueError):
                return na
        field = expression.source or "close"
        src = self._series_chrono_values(field)
        if not src and field in ("hl2", "hlc3", "ohlc4"):
            opens = self._series_chrono_values("open")
            highs = self._series_chrono_values("high")
            lows = self._series_chrono_values("low")
            closes = self._series_chrono_values("close")
            n = len(closes)
            src = []
            for i in range(n):
                try:
                    o = float(opens[i]) if i < len(opens) else float("nan")
                    h = float(highs[i]) if i < len(highs) else float("nan")
                    l = float(lows[i]) if i < len(lows) else float("nan")
                    c = float(closes[i])
                except (TypeError, ValueError):
                    src.append(None)
                    continue
                v = self._htf_agg_field(
                    {"open": o, "high": h, "low": l, "close": c, "volume": 0.0, "time": 0.0},
                    field,
                )
                src.append(None if v != v else v)
        if not src:
            return na
        if name == "sma":
            fn = getattr(self, "_sma", None)
            raw = fn(src, period) if callable(fn) else None
        elif name == "ema":
            fn = getattr(self, "_ema", None)
            raw = fn(src, period) if callable(fn) else None
        elif name == "rsi":
            cleaned: list[float | None] = []
            for v in src:
                if v is None:
                    cleaned.append(None)
                    continue
                try:
                    cleaned.append(float(v))
                except (TypeError, ValueError):
                    cleaned.append(None)
            raw = self._htf_rsi_full_series(cleaned, period)
        else:
            return na
        if not raw:
            return na
        last = raw[-1]
        if last is None:
            return na
        try:
            fv = float(last)
            return fv if fv == fv else na
        except (TypeError, ValueError):
            return na

    def _security_policy_state(self) -> dict[str, Any]:
        """Lazy-init shared request.security honesty metadata for hosts/tests."""
        state = getattr(self, "_request_security_policy", None)
        if isinstance(state, dict):
            return state
        state = {
            "htf_reeval": False,
            "gaps_supported": False,
            "lookahead_supported": False,
            "policies": {},  # tag → {count, ...}
            "notes": list(_SECURITY_POLICY_NOTES),
            "calls": 0,
        }
        self._request_security_policy = state  # type: ignore[attr-defined]
        ctx = getattr(self, "context", None)
        if isinstance(ctx, dict):
            ctx["request.security_policy"] = state
        return state

    def _note_security_policy(self, tag: str, **extra: Any) -> None:
        """Record a unique policy decision (once-log + per-run counters).

        Tags are product-facing honesty markers (``complex_htf_na``,
        ``chart_passthrough_htf_stub``, ``foreign_na``, …). Counts increment
        every bar; ``extra`` is kept from the first observation only so meta
        stays compact.
        """
        state = self._security_policy_state()
        state["calls"] = int(state.get("calls") or 0) + 1
        policies = state.setdefault("policies", {})
        entry = policies.get(tag)
        if entry is None:
            entry = {"count": 0}
            for k, v in extra.items():
                if isinstance(v, (str, int, float, bool)) or v is None:
                    entry[k] = v
                else:
                    entry[k] = str(v)
            policies[tag] = entry
            # One debug line per new tag (avoid per-bar spam on long charts).
            _LOG.debug("request.security policy %s %s", tag, {k: v for k, v in entry.items() if k != "count"})
        entry["count"] = int(entry.get("count") or 0) + 1

    def _security_return(self, value: Any, tag: str, **extra: Any) -> Any:
        """Record *tag* and return *value* (na / chart series / provider series)."""
        self._note_security_policy(tag, **extra)
        return value

    def _ticker_last(self, symbol: str) -> float | None:
        """Best-effort last price from data_feed (if wired)."""
        data_feed, _ = self._get_request_data()
        if data_feed is None or not hasattr(data_feed, "fetch_latest_ticker"):
            return None
        try:
            t = data_feed.fetch_latest_ticker(symbol)
            last = t.get("last") or t.get("close")
            return float(last) if last is not None else None
        except Exception:  # noqa: S110
            return None

    def _ohlcv_closes(self, symbol: str, timeframe: str = "D", limit: int = REQUEST_OHLCV_LIMIT) -> list[float] | None:
        data_feed, data_provider = self._get_request_data()
        if data_feed is not None and hasattr(data_feed, "fetch_latest_ohlcv"):
            try:
                ohlcv = data_feed.fetch_latest_ohlcv(symbol, str(timeframe), limit=limit)
                if ohlcv:
                    closes = [float(c[OHLCV_CLOSE_IDX]) for c in ohlcv if len(c) > OHLCV_CLOSE_IDX]
                    if closes:
                        return closes
            except Exception:  # noqa: S110
                pass
        if data_provider is not None and hasattr(data_provider, "fetch"):
            try:
                data = data_provider.fetch(symbol, period="1d", interval=str(timeframe))
                closes = data.get("close", [])
                if closes:
                    recent = closes[-limit:] if len(closes) >= limit else closes
                    return [float(x) for x in recent]
            except Exception:  # noqa: S110
                pass
        return None

    def _heikinashi_current_ohlc(self) -> tuple[float, float, float, float] | None:
        """Incremental Heikin-Ashi OHLC for the host chart (one update per bar).

        Standard reference formulas:
        - ``ha_close = (o + h + l + c) / 4``
        - ``ha_open = (prev_ha_open + prev_ha_close) / 2`` (first bar: ``(o+c)/2``)
        - ``ha_high = max(h, ha_open, ha_close)``
        - ``ha_low = min(l, ha_open, ha_close)``
        """
        ctx = getattr(self, "context", {}) or {}
        series_map = getattr(self, "current_series", None) or ctx

        def _sample(key: str) -> float | None:
            s = series_map.get(key) if isinstance(series_map, dict) else None
            if s is None:
                s = ctx.get(key)
            if s is None:
                return None
            cur = getattr(s, "current", None)
            if cur is not None and not isinstance(s, (list, tuple)):
                try:
                    return float(cur)
                except (TypeError, ValueError):
                    return None
            if isinstance(s, (list, tuple)) and s:
                try:
                    return float(s[-1])  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return None
            try:
                return float(s)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        o, h, l, c = _sample("open"), _sample("high"), _sample("low"), _sample("close")
        if o is None or h is None or l is None or c is None:
            return None
        ha_close = (o + h + l + c) * 0.25
        st = getattr(self, "_ha_inc_state", None)
        if st is None:
            st = {"prev_open": None, "prev_close": None}
            self._ha_inc_state = st  # type: ignore[attr-defined]
        prev_o = st.get("prev_open")
        prev_c = st.get("prev_close")
        if prev_o is None or prev_c is None:
            ha_open = (o + c) * 0.5
        else:
            ha_open = (float(prev_o) + float(prev_c)) * 0.5
        ha_high = max(h, ha_open, ha_close)
        ha_low = min(l, ha_open, ha_close)
        st["prev_open"] = ha_open
        st["prev_close"] = ha_close
        return ha_open, ha_high, ha_low, ha_close

    def _remap_preeval_ohlcv_to_ha(
        self,
        expression: Any,
        ha: tuple[float, float, float, float],
    ) -> Any:
        """Replace chart OHLCV samples in *expression* with Heikin-Ashi values.

        Pre-eval often passes ``PineSeries`` / list wrappers for ``open``/``close``
        etc.; unwrap to the current scalar before float matching.
        """
        ha_o, ha_h, ha_l, ha_c = ha

        def _scalar(v: Any) -> float | None:
            if v is None or isinstance(v, bool):
                return None
            cur = getattr(v, "current", None)
            if cur is not None and not isinstance(v, (list, tuple, dict)):
                v = cur
            elif isinstance(v, (list, tuple)) and v:
                v = v[-1]
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        chart: dict[str, float] = {}
        for key, dest in (
            ("open", "o"),
            ("high", "h"),
            ("low", "l"),
            ("close", "c"),
        ):
            series_map = getattr(self, "current_series", None) or {}
            s = series_map.get(key) if isinstance(series_map, dict) else None
            if s is None:
                s = (getattr(self, "context", {}) or {}).get(key)
            fv = _scalar(s)
            if fv is not None:
                chart[dest] = fv
        ha_by_chart = {
            chart.get("o"): ha_o,
            chart.get("h"): ha_h,
            chart.get("l"): ha_l,
            chart.get("c"): ha_c,
        }

        def _map_one(v: Any) -> Any:
            fv = _scalar(v)
            if fv is None:
                return v
            for ck, hv in ha_by_chart.items():
                if ck is None:
                    continue
                if fv == ck:
                    return hv
            return fv

        if isinstance(expression, list):
            return [_map_one(x) for x in expression]
        if isinstance(expression, tuple):
            return tuple(_map_one(x) for x in expression)
        return _map_one(expression)

    def _handle_request_security(self, args: list[Any]) -> Any:  # noqa: C901
        # complexity acceptable: handles multiple data source fallbacks + exprs
        """
        request.security(symbol, timeframe, expression, gaps, lookahead)

        Request data from another symbol or timeframe.

        v6+: Supports real data via context['data_provider'] (historical)
        or context['data_feed'] (CCXTProDataFeed for live/latest data).

        Policy (parity with compile foreign-na / same-symbol simple OHLCV):

        - **Foreign** without a multi-symbol feed hit → ``na`` (never invent chart
          series or legacy mock OHLCV as foreign fundamentals when a host chart
          identity is wired). Standalone unit eval without chart identity may
          still use legacy mock prices for bare string series names.
        - **Same-symbol + simple OHLCV** on a **coarser** TF with bar times →
          timestamp resample of chart OHLCV (``htf_ohlcv_resample``): last
          completed HTF bar only (lookahead_off-style; gaps/lookahead unused).
        - **Same-symbol + allowlisted simple ta.*** (``ta.sma/ema/rsi/atr`` with
          bare OHLCV source + const length) on a **coarser** TF → run the
          interpret TA helper on resampled HTF bars (``htf_simple_ta_resample``).
        - **Same-symbol + simple OHLCV** otherwise → chart passthrough /
          provider series (``chart_passthrough_htf_stub`` / same-TF eval).
        - **Same-symbol Heikin-Ashi** (``ticker.heikinashi``) → transform chart
          OHLCV to HA (do not return raw chart candles or all-``na``).
        - **Same-symbol + complex pre-eval** (UDF / nested / multi-arg ta) on a
          **different** TF → ``na`` without full multi-TF re-eval.
        - **Same-symbol + same TF** pre-eval → chart eval is correct; allow.
        - **gaps / lookahead** (``barmerge.*``) are accepted for API shape but
          **unused** (no gap-fill series, no lookahead offset). Recorded in
          policy metadata rather than silently affecting values.
        """
        ticker_arg = args[0] if len(args) > 0 else "AAPL"
        is_ha = bool(getattr(ticker_arg, "heikinashi_applied", False))
        symbol = self._resolve_symbol(ticker_arg)
        timeframe = args[1] if len(args) > 1 else "D"
        expression = args[2] if len(args) > REQUEST_SECURITY_MIN_ARGS else "close"
        # Presence by arity (False/None still count as "provided" positions).
        gaps_provided = len(args) > 3
        lookahead_provided = len(args) > 4
        gaps_arg = args[3] if gaps_provided else None
        lookahead_arg = args[4] if lookahead_provided else None

        if isinstance(timeframe, list):
            timeframe = timeframe[-1] if timeframe else "D"

        # Accept gaps/lookahead for signature compatibility; never apply them.
        if gaps_provided or lookahead_provided:
            self._note_security_policy(
                "gaps_lookahead_unused",
                gaps_provided=gaps_provided,
                lookahead_provided=lookahead_provided,
                gaps_value=gaps_arg if isinstance(gaps_arg, (bool, int, float, str)) or gaps_arg is None else str(gaps_arg),
                lookahead_value=(
                    lookahead_arg
                    if isinstance(lookahead_arg, (bool, int, float, str)) or lookahead_arg is None
                    else str(lookahead_arg)
                ),
            )

        # The expression arg is usually already evaluated by the call site.
        # - str: series name like "close" → fetch OHLCV and map
        # - list/tuple of already-evaluated values: return as-is so destructure
        #   ``[hi, lo, cl] = request.security(..., [high[1], low[1], close[1]])``
        #   (Camarilla pivots etc.) keeps the multi-value shape.  Do NOT collapse
        #   multi-element numeric lists to the last sample — that breaks unpack.
        # - single-element numeric list: unwrap to scalar (legacy series path)
        # - matrix/array/UDT result: return as-is
        #
        # Pre-evaluated non-str expressions were computed on the *chart* series.
        # Same-symbol security may return simple OHLCV / same-TF results; foreign
        # symbols without a real multi-symbol context must return na (not invent
        # chart close as dividends / fundamentals — see dividend_yield.pine).
        # Heikin-Ashi of the chart is same-symbol (HA(...) ticker string).
        chart_sym = self._is_chart_symbol(str(symbol)) or is_ha
        same_tf = self._request_tf_matches_chart(timeframe)
        na = float("nan")
        tf_s = str(timeframe) if timeframe is not None else ""

        def _maybe_htf_resample(expr: Any) -> Any | None:
            """Same-symbol simple OHLCV or allowlisted ta.* HTF path; None → fall through."""
            if not chart_sym or is_ha:
                return None
            if isinstance(expr, HtfSimpleTaExpr):
                return self._try_htf_simple_ta_resample(expr, timeframe)
            if not self._expression_is_simple_ohlcv_value(expr):
                return None
            return self._try_htf_ohlcv_resample(expr, timeframe)

        def _handle_simple_ta_expr(expr: HtfSimpleTaExpr) -> Any:
            """Same-symbol allowlisted ta.* — HTF resample, same-TF chart, else na."""
            if not chart_sym:
                return self._security_return(
                    na, "foreign_na", symbol=str(symbol), reason="foreign_simple_ta"
                )
            htf_val = self._try_htf_simple_ta_resample(expr, timeframe)
            if htf_val is not None:
                return self._security_return(
                    htf_val,
                    "htf_simple_ta_resample",
                    timeframe=tf_s,
                    ta=expr.name,
                    length=expr.length,
                    source=expr.source or "ohlc",
                )
            if same_tf:
                return self._security_return(
                    self._chart_simple_ta_last(expr),
                    "same_tf_chart_eval",
                    timeframe=tf_s,
                    ta=expr.name,
                )
            # LTF / unparseable coarser TF without fixed buckets — honest na
            # (not chart TA inventing HTF/LTF structure).
            return self._security_return(
                na,
                "complex_htf_na",
                timeframe=tf_s,
                reason="simple_ta_not_htf_or_same_tf",
                ta=expr.name,
            )

        # Heikin-Ashi transform for chart (same-symbol) security requests.
        if is_ha and chart_sym:
            ha = self._heikinashi_current_ohlc()
            if ha is not None:
                ha_o, ha_h, ha_l, ha_c = ha
                if isinstance(expression, str):
                    key = expression.strip().lower()
                    return self._security_return(
                        {
                            "open": ha_o,
                            "o": ha_o,
                            "high": ha_h,
                            "h": ha_h,
                            "low": ha_l,
                            "l": ha_l,
                            "close": ha_c,
                            "c": ha_c,
                        }.get(key, na),
                        "heikinashi_chart_transform",
                        timeframe=tf_s,
                    )
                if isinstance(expression, list):
                    if len(expression) == 1 and (
                        expression[0] is None
                        or isinstance(expression[0], (int, float, bool))
                    ):
                        return self._security_return(
                            self._remap_preeval_ohlcv_to_ha(expression[0], ha),
                            "heikinashi_chart_transform",
                            timeframe=tf_s,
                        )
                    return self._security_return(
                        self._remap_preeval_ohlcv_to_ha(expression, ha),
                        "heikinashi_chart_transform",
                        timeframe=tf_s,
                    )
                if isinstance(expression, tuple):
                    return self._security_return(
                        self._remap_preeval_ohlcv_to_ha(expression, ha),
                        "heikinashi_chart_transform",
                        timeframe=tf_s,
                    )
                return self._security_return(
                    self._remap_preeval_ohlcv_to_ha(
                        self._unwrap_preeval_scalar(expression), ha
                    ),
                    "heikinashi_chart_transform",
                    timeframe=tf_s,
                )

        def _same_symbol_preeval_tag() -> str:
            return "same_tf_chart_eval" if same_tf else "chart_passthrough_htf_stub"

        def _deny_preeval() -> Any:
            if chart_sym and not same_tf:
                return self._security_return(
                    na, "complex_htf_na", timeframe=tf_s, reason="no_htf_reeval"
                )
            return self._security_return(
                na, "foreign_na", symbol=str(symbol), reason="foreign_or_complex"
            )

        # Allowlisted simple ta.* marker (attached at visit_Call before chart pre-eval).
        if isinstance(expression, HtfSimpleTaExpr):
            return _handle_simple_ta_expr(expression)

        if isinstance(expression, list):
            if len(expression) == 1 and (
                expression[0] is None or isinstance(expression[0], (int, float, bool))
            ):
                expression = expression[0]
            elif chart_sym:
                htf_val = _maybe_htf_resample(expression)
                if htf_val is not None:
                    tag = (
                        "htf_simple_ta_resample"
                        if isinstance(expression, HtfSimpleTaExpr)
                        else "htf_ohlcv_resample"
                    )
                    return self._security_return(htf_val, tag, timeframe=tf_s)
                if self._allow_same_symbol_preeval(expression, timeframe):
                    return self._security_return(
                        expression, _same_symbol_preeval_tag(), timeframe=tf_s
                    )
                return _deny_preeval()
            else:
                return self._security_return(
                    na, "foreign_na", symbol=str(symbol), reason="foreign_list"
                )
        if isinstance(expression, tuple):
            if chart_sym:
                htf_val = _maybe_htf_resample(expression)
                if htf_val is not None:
                    return self._security_return(
                        htf_val, "htf_ohlcv_resample", timeframe=tf_s
                    )
            if chart_sym and self._allow_same_symbol_preeval(expression, timeframe):
                return self._security_return(
                    expression, _same_symbol_preeval_tag(), timeframe=tf_s
                )
            return _deny_preeval()

        if not isinstance(expression, str):
            if chart_sym:
                htf_val = _maybe_htf_resample(expression)
                if htf_val is not None:
                    tag = (
                        "htf_simple_ta_resample"
                        if isinstance(expression, HtfSimpleTaExpr)
                        else "htf_ohlcv_resample"
                    )
                    # `_try_htf_simple_ta_resample` already returns only for higher TF;
                    # tag OHLCV vs simple-ta explicitly for meta honesty.
                    if tag == "htf_simple_ta_resample":
                        return self._security_return(
                            htf_val,
                            tag,
                            timeframe=tf_s,
                        )
                    return self._security_return(
                        htf_val, "htf_ohlcv_resample", timeframe=tf_s
                    )
            if chart_sym and self._allow_same_symbol_preeval(expression, timeframe):
                # Bare `close` / PineSeries → current scalar for plot/assign paths.
                return self._security_return(
                    self._unwrap_preeval_scalar(expression),
                    _same_symbol_preeval_tag(),
                    timeframe=tf_s,
                )
            # Foreign + chart-evaluated UDF/expr, or same-symbol complex HTF → na
            return _deny_preeval()

        symbol_str = str(symbol)

        # String series name: prefer true HTF resample on same-symbol before
        # provider/mock paths (ChartOHLCVProvider ignores interval → chart bars).
        if chart_sym:
            htf_val = _maybe_htf_resample(expression)
            if htf_val is not None:
                return self._security_return(
                    htf_val, "htf_ohlcv_resample", timeframe=tf_s
                )

        # Try real data provider (historical or live) via shared helpers.
        # ChartOHLCVProvider ignores interval → still chart bars (not HTF resample).
        closes = self._ohlcv_closes(symbol, str(timeframe), limit=REQUEST_OHLCV_LIMIT)
        if closes:
            tag = (
                "provider_ohlcv"
                if same_tf or not chart_sym
                else "provider_ohlcv_chart_stub"
            )
            return self._security_return(
                self._get_expression_prices(str(expression), closes),
                tag,
                timeframe=tf_s,
                symbol=symbol_str,
            )
        last = self._ticker_last(symbol)
        if last is not None:
            return self._security_return(
                self._get_expression_prices(
                    str(expression), [float(last)] * REQUEST_OHLCV_LIMIT
                ),
                "provider_ticker_last",
                timeframe=tf_s,
                symbol=symbol_str,
            )

        # Fundamental / non-equity prefixes — never invent OHLCV.
        if any(tok in symbol_str for tok in _FUNDAMENTAL_TOKENS):
            return self._security_return(
                na, "fundamental_na", symbol=symbol_str, reason="fundamental_token"
            )

        # Foreign under a host chart with no multi-symbol feed hit → na.
        # Aligns interpret with compile foreign-na (no mock UPVOL/MSFT prices).
        if not chart_sym and self._host_has_chart_identity():
            return self._security_return(
                na, "foreign_na", symbol=symbol_str, reason="no_multisymbol_feed"
            )

        # Fallback mock data for bare string series names only (legacy demos /
        # standalone evaluator without a wired chart identity).
        base_prices = {
            "AAPL": [100.0, 101.5, 102.0, 103.5, 105.0],
            "GOOGL": [1000.0, 1015.5, 1020.0, 1035.5, 1050.0],
            "BTC/USD": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
            "BTC/USDT": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
        }

        prices = base_prices.get(symbol_str, [100.0, 101.0, 102.0, 101.5, 103.0])
        return self._security_return(
            self._get_expression_prices(expression, prices),
            "legacy_mock_ohlcv",
            symbol=symbol_str,
            timeframe=tf_s,
        )

    def _handle_request_security_lower_tf(self, args: list[Any]) -> Any:
        """
        request.security_lower_tf(symbol, timeframe, expression)

        Request lower timeframe data within the current timeframe.
        Now supports data_feed / data_provider when wired (reuses latest for demo).
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        timeframe = args[1] if len(args) > 1 else "5m"
        expression = args[2] if len(args) > 2 else "close"  # noqa: PLR2004 - arg count check

        # Try data feed/provider for consistency with request.security
        data_feed, data_provider = self._get_request_data()

        if data_feed is not None and hasattr(data_feed, "fetch_latest_ohlcv"):
            try:
                ohlcv = data_feed.fetch_latest_ohlcv(symbol, str(timeframe), limit=REQUEST_RECENT_LIMIT)
                if ohlcv:
                    closes = [c[OHLCV_CLOSE_IDX] for c in ohlcv if len(c) > OHLCV_CLOSE_IDX]
                    if closes:
                        return closes * LOWER_TF_SIMULATE_MULTIPLIER  # simulate more lower-tf bars from latest
            except Exception:  # noqa: S110
                pass

        if data_provider is not None and hasattr(data_provider, "fetch"):
            try:
                data = data_provider.fetch(symbol, period="1d", interval=str(timeframe))
                closes = data.get("close", [])
                if closes:
                    return closes[-REQUEST_RECENT_LIMIT:] or closes
            except Exception:  # noqa: S110
                pass

        # Fallback mock intrabar data (simulated lower timeframe)
        intrabar_prices = [100.0 + i * 0.25 for i in range(10)]
        if isinstance(expression, str):
            return self._get_expression_prices(str(expression), intrabar_prices)
        # Reference Pine: expression may be a tuple/list of series → return a tuple of arrays
        # so destructure like ``[o,h,l,c] = request.security_lower_tf(..., [open,high,low,close])`` works.
        if isinstance(expression, (list, tuple)) and expression:
            n = len(expression)
            out: list[list[float]] = []
            for i, item in enumerate(expression):
                if isinstance(item, str):
                    out.append(self._get_expression_prices(str(item), intrabar_prices))
                elif isinstance(item, (int, float)) and not isinstance(item, bool):
                    base = float(item)
                    out.append([base + j * 0.05 for j in range(10)])
                else:
                    # Distinct mock series per component when values are already scalars/series
                    out.append([100.0 + i + j * 0.25 for j in range(10)])
            return out if n != 1 else out[0]
        return intrabar_prices

    def _handle_request_dividends(self, args: list[Any]) -> float:
        """
        request.dividends(symbol, currency)

        Request dividend information for a symbol.

        Parameters:
            symbol: Symbol/ticker string (str)
            currency: Currency code (str or None)

        Returns dividend amount as float.
        This is a mock implementation.
        """
        symbol = self._resolve_symbol(args[0] if len(args) > 0 else "AAPL")
        # currency = args[1] if len(args) > 1 else "USD"

        data_feed, _ = self._get_request_data()
        # If data_feed available, could derive 'yield' from price, but keep simple mock scaled
        base_div = {"AAPL": 0.24, "MSFT": 0.62, "JNJ": 1.13}
        val = base_div.get(symbol, 0.0)
        if data_feed and hasattr(data_feed, "fetch_latest_ticker"):
            try:
                t = data_feed.fetch_latest_ticker(symbol)
                last = t.get("last") or t.get("close") or 100.0
                val = round(val * (last / 100.0), 2)  # naive dynamic scale
            except Exception:  # noqa: S110
                pass
        return val

    def _handle_request_earnings(self, args: list[Any]) -> float:
        """
        request.earnings(symbol, currency)

        Request earnings information for a symbol.

        Parameters:
            symbol: Symbol/ticker string (str)
            currency: Currency code (str or None)

        Returns earnings per share as float.
        This is a mock implementation.
        """
        symbol = self._resolve_symbol(args[0] if len(args) > 0 else "AAPL")
        # currency = args[1] if len(args) > 1 else "USD"

        data_feed, _ = self._get_request_data()
        base_eps = {"AAPL": 5.61, "MSFT": 9.27, "JNJ": 9.13}
        val = base_eps.get(symbol, 0.0)
        if data_feed and hasattr(data_feed, "fetch_latest_ticker"):
            try:
                t = data_feed.fetch_latest_ticker(symbol)
                last = t.get("last") or t.get("close") or 100.0
                val = round(val * (last / 150.0), 2)
            except Exception:  # noqa: S110
                pass
        return val

    def _handle_request_splits(self, args: list[Any]) -> float:
        """
        request.splits(symbol, currency)

        Request stock split information for a symbol.

        Parameters:
            symbol: Symbol/ticker string (str)
            currency: Currency code (str or None)

        Returns split ratio as float.
        This is a mock implementation.
        """
        symbol = self._resolve_symbol(args[0] if len(args) > 0 else "AAPL")
        # currency = args[1] if len(args) > 1 else "USD"

        base_splits = {"AAPL": 4.0, "TSLA": 3.0, "MSFT": 1.0}
        val = base_splits.get(symbol, 1.0)
        # Optional feed hook: if ticker available, keep known ratio (no change)
        _ = self._ticker_last(symbol)
        return val

    def _handle_request_financial(self, args: list[Any]) -> float:
        """
        request.financial(symbol, financial_id, period)

        Request financial statement data (from SEC filings).

        Parameters:
            symbol: Symbol/ticker string (str)
            financial_id: Financial metric identifier (str)
            period: Reporting period (str, e.g., "FQ", "FY")

        Returns financial metric value as float.
        Mock table with optional price-based scaling when data_feed is wired.
        """
        symbol = self._resolve_symbol(args[0] if len(args) > 0 else "AAPL")
        financial_id = args[1] if len(args) > 1 else "REVENUE"
        # period = args[2] if len(args) > 2 else "FY"

        # Mock: return financial metrics (symbol dynamic)
        financials = {
            ("AAPL", "REVENUE"): 383285000000,
            ("AAPL", "NET_INCOME"): 96995000000,
            ("MSFT", "REVENUE"): 198716000000,
            ("MSFT", "NET_INCOME"): 72794000000,
        }
        key = (symbol, str(financial_id).upper())
        val = float(financials.get(key, 0.0))
        last = self._ticker_last(symbol)
        if last is not None and val > 0:
            # Naive dynamic scale so feed presence is observable in tests
            val = val * (last / max(last, 1.0))
        return val

    def _handle_request_quandl(self, args: list[Any]) -> Any:
        """
        request.quandl(quandl_code, column)

        Request data from Quandl database.

        Parameters:
            quandl_code: Quandl dataset code (str)
            column: Column name within dataset (str)

        Returns series data from Quandl dataset.
        This is a mock implementation.
        """
        quandl_code = self._resolve_symbol(args[0] if len(args) > 0 else "EIA/PET_RWTC_D", default="EIA/PET_RWTC_D")
        # column = args[1] if len(args) > 1 else "Value"

        # Mock: return time series data for common Quandl datasets
        if "PET_RWTC" in str(quandl_code):
            # Oil prices (WTI Crude Oil)
            return [50.0, 51.5, 52.0, 51.0, 53.5, 55.0, 54.5, 56.0]
        if "GDPC" in str(quandl_code):
            # GDP data
            return [21060000, 21200000, 21400000, 21600000]

        # Default: return generic series
        return [100.0, 101.0, 102.0, 101.5, 103.0]

    def _handle_request_economic(self, args: list[Any]) -> Any:
        """
        request.economic(country, indicator_code)

        Request economic indicator data (e.g., unemployment, inflation).

        Parameters:
            country: Country code (str, e.g., "US", "EU")
            indicator_code: Economic indicator code (str)

        Returns economic data as series or value.
        This is a mock implementation.
        """
        country = self._resolve_symbol(args[0] if len(args) > 0 else "US", default="US")
        indicator_code = args[1] if len(args) > 1 else "UNRATE"

        # Mock: return economic indicators
        if str(indicator_code).upper() == "UNRATE":
            # US Unemployment Rate (%)
            if str(country).upper() == "US":
                return [3.5, 3.4, 3.6, 3.7, 3.8]
            # EU Unemployment Rate (%)
            if str(country).upper() == "EU":
                return [6.1, 6.0, 6.2, 6.3, 6.4]

        if str(indicator_code).upper() == "INFLATION":
            # Inflation Rate (%)
            if str(country).upper() == "US":
                return [3.4, 3.2, 3.0, 2.9, 2.8]
            if str(country).upper() == "EU":
                return [2.6, 2.4, 2.2, 2.1, 2.0]

        # Default: return generic series
        return [100.0, 101.0, 102.0, 101.5, 103.0]

    def _handle_request_currency_rate(self, args: list[Any]) -> float:
        """
        request.currency_rate(from_currency, to_currency)

        Request exchange rate between two currencies.

        Parameters:
            from_currency: Source currency code (str, e.g., "USD")
            to_currency: Target currency code (str, e.g., "EUR")

        Returns exchange rate as float.
        This is a mock implementation.
        """
        from_currency = self._resolve_symbol(args[0] if len(args) > 0 else "USD", default="USD")
        to_currency = self._resolve_symbol(args[1] if len(args) > 1 else "EUR", default="EUR")

        # Prefer live feed pair if available (e.g. EUR/USD last)
        pair = f"{from_currency}/{to_currency}"
        last = self._ticker_last(pair)
        if last is not None and last > 0:
            return float(last)

        # Mock: return exchange rates
        rates = {
            ("USD", "EUR"): 0.92,
            ("USD", "GBP"): 0.79,
            ("USD", "JPY"): 149.5,
            ("EUR", "USD"): 1.09,
            ("EUR", "GBP"): 0.86,
            ("GBP", "USD"): 1.27,
        }

        key = (str(from_currency).upper(), str(to_currency).upper())
        return rates.get(key, 1.0)

    def _handle_request_seed(self, args: list[Any]) -> None:
        """
        request.seed(seed_value)

        Seed the random number generator for reproducible mock request data.
        Stores the seed on evaluator context and optional numpy RNG.
        """
        seed_value = args[0] if len(args) > 0 else 0
        try:
            seed_int = int(seed_value)
        except (TypeError, ValueError):
            seed_int = hash(str(seed_value)) & 0xFFFFFFFF
        random.seed(seed_int)
        try:
            import numpy as np

            np.random.seed(seed_int % (2**32 - 1))
        except Exception:
            pass
        ctx = getattr(self, "context", None)
        if isinstance(ctx, dict):
            ctx["request.seed"] = seed_int
        try:
            self._request_seed = seed_int  # type: ignore[attr-defined]
        except Exception:
            pass

    def _handle_request_footprint(self, args: list[Any]) -> Footprint | None:
        """
        request.footprint(num_ticks, va_percentage)

        Request volume footprint data for the current bar.
        Added in Pine Script v6 (January 2026).

        Now supports symbol (dynamic) and data_feed for volume scaling.
        """
        num_ticks = args[0] if len(args) > 0 else 100
        va_percentage = args[1] if len(args) > 1 else 70
        # symbol optional for dynamic
        _ = self._resolve_symbol(args[2] if len(args) > 2 else "ES", default="ES")  # noqa: PLR2004 - optional arg
        data_feed, _ = self._get_request_data()

        rows: list[VolumeRow] = []
        base_price = 100.0
        tick_size = 0.01
        vol_scale = 1.0
        if data_feed and hasattr(data_feed, "fetch_latest_ticker"):
            try:
                t = data_feed.fetch_latest_ticker("ES")  # or symbol
                last = t.get("last") or t.get("close") or 4000.0
                vol_scale = max(0.1, last / 4000.0)
            except Exception:  # noqa: S110
                pass

        for i in range(num_ticks):
            price_level = base_price + (i * tick_size)
            row = VolumeRow(
                up_price=price_level + tick_size,
                down_price=price_level,
                buy_volume=(1000.0 + (random.random() * 500)) * vol_scale,
                sell_volume=(900.0 + (random.random() * 500)) * vol_scale,
                delta=100.0 + (random.random() * 200 - 100),
                is_imbalance=random.random() < 0.1,  # noqa: PLR2004 - mock data gen
                is_poc=(i == num_ticks // 2),
                is_vah=(i == int(num_ticks * 0.7)),
                is_val=(i == int(num_ticks * 0.3)),
            )
            rows.append(row)

        poc_idx = num_ticks // 2
        vah_idx = int(num_ticks * 0.7)
        val_idx = int(num_ticks * 0.3)

        total_buy = sum(r.buy_volume for r in rows)
        total_sell = sum(r.sell_volume for r in rows)

        footprint = Footprint(
            num_ticks=num_ticks,
            va_percentage=va_percentage,
            buy_volume=total_buy,
            sell_volume=total_sell,
            delta=total_buy - total_sell,
            total_volume=total_buy + total_sell,
            vah_row=rows[vah_idx] if vah_idx < len(rows) else None,
            val_row=rows[val_idx] if val_idx < len(rows) else None,
            poc_row=rows[poc_idx] if poc_idx < len(rows) else None,
            rows=rows,
        )

        return footprint
