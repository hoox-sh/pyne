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

import math
import random

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .timeframe import _chart_period
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
_OHLCV_SERIES_KEYS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "hl2",
    "hlc3",
    "ohlc4",
)
_CHART_PLACEHOLDERS = frozenset({"", "CHART", "SYMBOL", "TICKER", "NONE", "NA", "UNKNOWN"})
_FUNDAMENTAL_TOKENS = ("DIVIDEND", "FACTSET", "EARNINGS", "ESD_")


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
    """
    Request/data fetching functions for multi-timeframe and fundamental data.
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
        """True for pre-eval values that look like simple chart OHLCV samples."""
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

        Standard TV formulas:
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
        - **Same-symbol + simple OHLCV** (string name or chart OHLCV sample) →
          chart passthrough / provider series.
        - **Same-symbol Heikin-Ashi** (``ticker.heikinashi``) → transform chart
          OHLCV to HA (do not return raw chart candles or all-``na``).
        - **Same-symbol + complex pre-eval** (UDF / ta) on a **different** TF →
          ``na`` without real HTF re-eval (do not invent HTF structure).
        - **Same-symbol + same TF** pre-eval → chart eval is correct; allow.
        """
        ticker_arg = args[0] if len(args) > 0 else "AAPL"
        is_ha = bool(getattr(ticker_arg, "heikinashi_applied", False))
        symbol = self._resolve_symbol(ticker_arg)
        timeframe = args[1] if len(args) > 1 else "D"
        expression = args[2] if len(args) > REQUEST_SECURITY_MIN_ARGS else "close"

        if isinstance(timeframe, list):
            timeframe = timeframe[-1] if timeframe else "D"

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
        na = float("nan")

        # Heikin-Ashi transform for chart (same-symbol) security requests.
        if is_ha and chart_sym:
            ha = self._heikinashi_current_ohlc()
            if ha is not None:
                ha_o, ha_h, ha_l, ha_c = ha
                if isinstance(expression, str):
                    key = expression.strip().lower()
                    return {
                        "open": ha_o,
                        "o": ha_o,
                        "high": ha_h,
                        "h": ha_h,
                        "low": ha_l,
                        "l": ha_l,
                        "close": ha_c,
                        "c": ha_c,
                    }.get(key, na)
                if isinstance(expression, list):
                    if len(expression) == 1 and (
                        expression[0] is None
                        or isinstance(expression[0], (int, float, bool))
                    ):
                        return self._remap_preeval_ohlcv_to_ha(expression[0], ha)
                    return self._remap_preeval_ohlcv_to_ha(expression, ha)
                if isinstance(expression, tuple):
                    return self._remap_preeval_ohlcv_to_ha(expression, ha)
                return self._remap_preeval_ohlcv_to_ha(
                    self._unwrap_preeval_scalar(expression), ha
                )

        if isinstance(expression, list):
            if len(expression) == 1 and (
                expression[0] is None or isinstance(expression[0], (int, float, bool))
            ):
                expression = expression[0]
            elif chart_sym:
                if self._allow_same_symbol_preeval(expression, timeframe):
                    return expression
                return na
            else:
                return na
        if isinstance(expression, tuple):
            if chart_sym and self._allow_same_symbol_preeval(expression, timeframe):
                return expression
            return na

        if not isinstance(expression, str):
            if chart_sym and self._allow_same_symbol_preeval(expression, timeframe):
                # Bare `close` / PineSeries → current scalar for plot/assign paths.
                return self._unwrap_preeval_scalar(expression)
            # Foreign + chart-evaluated UDF/expr, or same-symbol complex HTF → na
            return na

        symbol_str = str(symbol)

        # Try real data provider (historical or live) via shared helpers
        closes = self._ohlcv_closes(symbol, str(timeframe), limit=REQUEST_OHLCV_LIMIT)
        if closes:
            return self._get_expression_prices(str(expression), closes)
        last = self._ticker_last(symbol)
        if last is not None:
            return self._get_expression_prices(str(expression), [float(last)] * REQUEST_OHLCV_LIMIT)

        # Fundamental / non-equity prefixes — never invent OHLCV.
        if any(tok in symbol_str for tok in _FUNDAMENTAL_TOKENS):
            return na

        # Foreign under a host chart with no multi-symbol feed hit → na.
        # Aligns interpret with compile foreign-na (no mock UPVOL/MSFT prices).
        if not chart_sym and self._host_has_chart_identity():
            return na

        # Fallback mock data for bare string series names only (legacy demos /
        # standalone evaluator without a wired chart identity).
        base_prices = {
            "AAPL": [100.0, 101.5, 102.0, 103.5, 105.0],
            "GOOGL": [1000.0, 1015.5, 1020.0, 1035.5, 1050.0],
            "BTC/USD": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
            "BTC/USDT": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
        }

        prices = base_prices.get(symbol_str, [100.0, 101.0, 102.0, 101.5, 103.0])
        return self._get_expression_prices(expression, prices)

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
        # TV: expression may be a tuple/list of series → return a tuple of arrays
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
