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

from __future__ import annotations

import hashlib
import math
import os
import re
import time
import uuid

from typing import Any

from pynescript.ast.helper import parse
from pynescript.util.time_parts import apply_utc_parts_to_context

from .evaluator import CustomEvaluator
from .series import PineSeries

# Crude scan: skip calendar field fill when script never names them
_CAL_NAME_RE = re.compile(
    r"\b(year|month|dayofmonth|hour|minute|second|dayofweek)\b",
)
# fill() needs plot() to return Plot handles (PlotRegistry).
_FILL_CALL_RE = re.compile(r"\bfill\s*\(")
# Derived built-in series — skip update/append when script never names them.
_HL2_RE = re.compile(r"\bhl2\b")
_HLC3_RE = re.compile(r"\bhlc3\b")
_OHLC4_RE = re.compile(r"\bohlc4\b")

# Parse tree cache (source sha256 → AST). Bounded to avoid unbounded growth.
_PARSE_CACHE: dict[str, Any] = {}
_PARSE_CACHE_MAX = 64

# Host-side compile cache (raw source sha256 → CompiledScript). Avoids re-running
# corpus sanitize + engine cache lookup on every mode=compile warm re-eval.
# Engine still has its own LRU; this is a thin SoT host short-circuit.
_HOST_COMPILE_CACHE: dict[str, Any] = {}
_HOST_COMPILE_CACHE_MAX = 64

# Cached numba availability for mode=auto prefilter (None = not probed yet).
_HAS_NUMBA: bool | None = None


def _json_safe_number(x: Any) -> float | None:
    """Map NaN/±Inf (and numpy scalars) to ``None`` for strict JSON / browsers."""
    if x is None:
        return None
    try:
        # numpy scalar → python
        if hasattr(x, "item") and not isinstance(x, (bytes, str, dict, list)):
            x = x.item()
    except Exception:  # noqa: BLE001
        pass
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        fx = float(x)
        if math.isnan(fx) or math.isinf(fx):
            return None
        return fx
    return None


def _series_values_jsonable(values: Any) -> list[Any]:
    """Convert a plot series (list / numpy) to JSON-safe list of floats|null.

    Hot path for ``mode=compile`` host wrap: numpy float64 arrays from
    ``CompiledScript.run``. Prefer C-level ``tolist()`` then sparse None fix
    for non-finite samples (warm-up ``na``) — much faster than per-element
    ``math.isnan`` / ``math.isinf`` in pure Python.
    """
    if values is None:
        return []
    try:
        import numpy as np  # noqa: PLC0415

        if isinstance(values, np.ndarray):
            kind = values.dtype.kind
            if kind in "f":
                arr = np.asarray(values, dtype=np.float64).ravel()
                n = int(arr.size)
                if n == 0:
                    return []
                finite = np.isfinite(arr)
                if bool(finite.all()):
                    return arr.tolist()
                # tolist keeps nan/inf as float; patch only non-finite slots
                out: list[Any] = arr.tolist()
                # Sparse bad indices (warm-up head) vs dense: both beat pure-Python loop
                bad = np.flatnonzero(~finite)
                for i in bad:
                    out[int(i)] = None
                return out
            if kind in "iu":
                # Integers are always finite → direct list of floats for JSON
                return np.asarray(values, dtype=np.float64).ravel().tolist()
            if kind == "b":
                return [bool(x) for x in values.ravel()]
            # object / other: fall through via tolist
            values = values.tolist()
    except Exception:
        pass
    if hasattr(values, "tolist") and not isinstance(values, (list, tuple)):
        try:
            values = values.tolist()
        except Exception:
            return []
    if not isinstance(values, (list, tuple)):
        return []
    out_list: list[Any] = []
    append = out_list.append
    for x in values:
        if x is None:
            append(None)
        elif isinstance(x, bool):
            append(x)
        elif isinstance(x, (int, float)):
            fx = float(x)
            if math.isnan(fx) or math.isinf(fx):
                append(None)
            else:
                append(fx)
        elif hasattr(x, "item") and not isinstance(x, (str, bytes)):
            append(_json_safe_number(x))
        else:
            # Keep non-numeric as-is only if already JSON-friendly
            append(x if isinstance(x, (str, dict, list)) else None)
    return out_list


# Pack cache for warm re-runs of the same bar list (bench / re-eval).
# Keyed by id(list); entry stores (list identity, cheap fingerprint, packed).
# Fingerprint = (n, first.time, last.time, first.close, last.close) so in-place
# mutation of ends invalidates; full middle edits still rare for this host path.
_OHLCV_PACK_CACHE: dict[int, tuple[Any, tuple, tuple[Any, Any, Any, Any, Any]]] = {}
_OHLCV_PACK_CACHE_MAX = 8


def _ohlcv_pack_fingerprint(ohlcv_data: list[dict]) -> tuple:
    n = len(ohlcv_data)
    if n == 0:
        return (0,)
    first = ohlcv_data[0]
    last = ohlcv_data[-1]
    return (
        n,
        first.get("time"),
        last.get("time"),
        first.get("close"),
        last.get("close"),
    )


def _ohlcv_dicts_to_arrays(ohlcv_data: list[dict]) -> tuple[Any, Any, Any, Any, Any]:
    """Pack OHLCV dict rows into float64 numpy arrays (single pass).

    Uses list accumulation + one ``asarray`` per column (faster than pre-allocated
    per-element store into numpy buffers). Caches by list identity + fingerprint
    for warm re-runs (bench / re-eval same bars).
    """
    import numpy as np  # noqa: PLC0415

    oid = id(ohlcv_data)
    fp = _ohlcv_pack_fingerprint(ohlcv_data)
    hit = _OHLCV_PACK_CACHE.get(oid)
    if hit is not None and hit[0] is ohlcv_data and hit[1] == fp:
        return hit[2]

    n = len(ohlcv_data)
    if n == 0:
        z = np.empty(0, dtype=np.float64)
        return (z, z, z, z, z)

    # Single-pass Python lists, then one asarray/column (faster than empty+assign
    # or per-cell float()). Prefer direct keys when present (API/bench contract).
    o_l: list[Any] = []
    h_l: list[Any] = []
    l_l: list[Any] = []
    c_l: list[Any] = []
    v_l: list[Any] = []
    oa, ha, la, ca, va = o_l.append, h_l.append, l_l.append, c_l.append, v_l.append
    for b in ohlcv_data:
        # Hot path: required OHLC keys (KeyError → safe defaults)
        try:
            o = b["open"]
            h = b["high"]
            l = b["low"]
            c = b["close"]
        except KeyError:
            o = b.get("open", 0.0)
            h = b.get("high", 0.0)
            l = b.get("low", 0.0)
            c = b.get("close", 0.0)
        oa(0.0 if o is None else o)
        ha(0.0 if h is None else h)
        la(0.0 if l is None else l)
        ca(0.0 if c is None else c)
        vol = b.get("volume", 1.0)
        va(1.0 if vol is None else vol)

    packed = (
        np.asarray(o_l, dtype=np.float64),
        np.asarray(h_l, dtype=np.float64),
        np.asarray(l_l, dtype=np.float64),
        np.asarray(c_l, dtype=np.float64),
        np.asarray(v_l, dtype=np.float64),
    )
    if len(_OHLCV_PACK_CACHE) >= _OHLCV_PACK_CACHE_MAX:
        try:
            _OHLCV_PACK_CACHE.pop(next(iter(_OHLCV_PACK_CACHE)))
        except StopIteration:
            pass
    _OHLCV_PACK_CACHE[oid] = (ohlcv_data, fp, packed)
    return packed


def _parse_script(source_code: str) -> Any:
    key = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
    tree = _PARSE_CACHE.get(key)
    if tree is not None:
        return tree
    tree = parse(source_code, mode="exec")
    if len(_PARSE_CACHE) >= _PARSE_CACHE_MAX:
        # Drop oldest insertion (CPython 3.7+ dict order)
        try:
            _PARSE_CACHE.pop(next(iter(_PARSE_CACHE)))
        except StopIteration:
            pass
    _PARSE_CACHE[key] = tree
    return tree


class Syminfo:
    """Symbol information namespace for Pine Script builtins.

    Contains information about the current symbol like ticker, currency, etc.
    Added in Pine Script v5, with isin and current_contract added in 2025.
    """

    # Basic symbol info (existing)
    tickerid: str = "AAPL"
    currency: str = "USD"
    type: str = "stock"
    session: str = "regular"
    tick_size: float = 0.01
    pointvalue: float = 1.0
    mintick: float = 0.01
    description: str = "Apple Inc."
    strategy_type: str = "long"
    prefix: str = "NASDAQ"
    name: str = "AAPL"

    # November 2025: ISIN (International Securities Identification Number)
    isin: str = ""  # 12-character ISIN code, empty string if not available

    # July 2025: Current contract for continuous futures
    current_contract: str | None = None  # Ticker ID of underlying contract for continuous futures

    # November 2024: Minimum contract size
    mincontract: int = 1


class Chartinfo:
    """Chart information namespace for Pine Script builtins."""

    type: str = "candle"
    aggtype: str = "Standard"
    time: int = 0
    status: str = "regular"


class Timeframe:
    """Timeframe information namespace for Pine Script builtins.

    Attribute names match TradingView Pine: ``isdaily`` / ``ismonthly`` /
    ``isdwm`` (not ``is_daily``). Defaults assume a daily chart.
    """

    period: str = "D"  # e.g., "1D", "1H", "5"
    multiplier: int = 1
    isintraday: bool = False
    isdaily: bool = True
    isweekly: bool = False
    ismonthly: bool = False
    isseconds: bool = False
    isinseconds: bool = False
    isminutes: bool = False
    ishours: bool = False
    isdwm: bool = True
    current: str = "D"

    # November 2024: Main period from chart's main context
    main_period: str = "D"

    # Back-compat aliases
    is_daily: bool = True
    is_weekly: bool = False
    is_monthly: bool = False
    is_seconds: bool = False


class Barstate:
    """Bar state information namespace for Pine Script builtins."""

    isfirst: bool = False
    islast: bool = False
    isnew: bool = True
    ishistory: bool = True
    isconfirmed: bool = True
    islastconfirmedhistory: bool = False
    isrealtime: bool = False
    iscomposite: bool = False


class Chart:
    """Chart namespace for Pine Script builtins.

    Pine uses ununderscored names (``is_heikinashi``); keep snake_case aliases
    for older hosts and bind both on instances.
    """

    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    resolution: str = "D"

    # Chart display mode (Python-style + Pine-style aliases)
    is_heikin_ashi: bool = False
    is_heikinashi: bool = False
    is_kagi: bool = False
    is_line_break: bool = False
    is_linebreak: bool = False
    is_point_figure: bool = False
    is_pointfigure: bool = False
    is_pnf: bool = False  # TV name for point-and-figure
    is_renko: bool = False
    is_range: bool = False
    is_standard: bool = True
    # Viewport (host may override; Runtime seeds from bar range)
    left_visible_bar_time: int | float = 0
    right_visible_bar_time: int | float = 0


class Runtime:
    def __init__(self, symbol: str = "AAPL", run_id: str | None = None):
        """
        Initialize the runtime with optional symbol configuration.

        Args:
            symbol: The symbol to use for the runtime (default: "AAPL")
            run_id: Optional unique run identifier. Generated if not provided.
        """
        self.symbol = symbol
        self._run_id = run_id or uuid.uuid4().hex[:16]
        self._syminfo = Syminfo()
        self._syminfo.tickerid = symbol
        self._syminfo.name = symbol
        self._syminfo.prefix = self._extract_prefix(symbol)

        # February 2025: bid/ask variables (only available on 1T timeframe)
        self._bid: float | None = None
        self._ask: float | None = None

        # November 2024: main ticker reference
        self._main_tickerid: str = symbol

    def _extract_prefix(self, symbol: str) -> str:
        """Extract prefix from symbol (e.g., 'NASDAQ' from 'NASDAQ:AAPL')."""
        if ":" in symbol:
            return symbol.split(":", maxsplit=1)[0]
        return ""

    def _make_chart(self, ohlcv_data: list | None = None) -> Chart:
        """Build a Chart host object seeded with viewport times from bars."""
        chart = Chart()
        if ohlcv_data:
            first_t = ohlcv_data[0].get("time", 0) or 0
            last_t = ohlcv_data[-1].get("time", 0) or 0
            chart.left_visible_bar_time = first_t
            chart.right_visible_bar_time = last_t
        return chart

    def configure_footprint(self, footprint_data: dict) -> None:
        """Configure syminfo based on footprint data.

        Args:
            footprint_data: Dictionary containing footprint configuration
        """
        if "isin" in footprint_data:
            self._syminfo.isin = footprint_data["isin"]
        if "current_contract" in footprint_data:
            self._syminfo.current_contract = footprint_data["current_contract"]

    def update_bid_ask(self, bid: float | None, ask: float | None) -> None:
        """Update bid/ask prices (February 2025 feature).

        Args:
            bid: Bid price (highest buy order)
            ask: Ask price (lowest sell order)
        """
        self._bid = bid
        self._ask = ask

    def run(
        self,
        source_code: str,
        ohlcv_data: list[dict],
        data_feed=None,
        data_provider=None,
        mode: str | None = None,
        inputs: dict | None = None,
    ):
        """
        Execute the script over the provided OHLCV data.

        Args:
            source_code: Pine Script source to run.
            ohlcv_data: List of dicts with 'open', 'high', 'low', 'close', 'time'.
            data_feed: Optional realtime DataFeed for request.* live data.
            data_provider: Optional historical provider for request.* .
            mode:
                ``"interpret"`` — AST walker.
                ``"compile"`` — Numba/object bar loop (supported subset).
                ``"auto"`` — try compile; on any failure fall back to interpret.
                Default: ``PYNE_RUNTIME_MODE`` env, else ``"interpret"`` (tests/API
                callers that omit mode: Pro API schema defaults to ``auto``).
            inputs: Optional Pine ``input.*`` overrides keyed by title.

        Returns:
            dict with 'series': list of plotted values for each bar.
        """
        import os

        if mode is None or mode == "":
            mode = os.environ.get("PYNE_RUNTIME_MODE", "interpret")
        mode_norm = (mode or "interpret").strip().lower()
        if mode_norm == "compile":
            return self._run_compiled(source_code, ohlcv_data)
        if mode_norm == "auto":
            return self._run_auto(
                source_code,
                ohlcv_data,
                data_feed=data_feed,
                data_provider=data_provider,
                inputs=inputs,
            )
        if mode_norm not in ("interpret",):
            return {"error": f"Unknown mode: {mode!r} (use interpret|compile|auto)"}

        # Wire request.* sources: chart bars as historical provider when unset
        try:
            from pynescript.util.data import resolve_request_sources

            data_feed, data_provider = resolve_request_sources(
                data_feed=data_feed,
                data_provider=data_provider,
                chart_bars=ohlcv_data,
                symbol=getattr(self, "symbol", "CHART") or "CHART",
            )
        except Exception:
            # Non-fatal: request.* falls back to built-in mocks
            pass

        # Parse once (cached by source hash for multi-run hosts)
        try:
            tree = _parse_script(source_code)
        except Exception as e:
            return {"error": f"Parse Error: {e!s}"}

        # Initialize Series
        open_series = PineSeries()
        high_series = PineSeries()
        low_series = PineSeries()
        close_series = PineSeries()
        volume_series = PineSeries()
        hl2_series = PineSeries()
        hlc3_series = PineSeries()
        ohlc4_series = PineSeries()
        tr_series = PineSeries()  # true range (built-in series in Pine)

        # Context initialization (daily chart defaults)
        tf = Timeframe()
        barstate = Barstate()
        context = {
            "open": open_series,
            "high": high_series,
            "low": low_series,
            "close": close_series,
            "volume": volume_series,
            "hl2": hl2_series,
            "hlc3": hlc3_series,
            "ohlc4": ohlc4_series,
            "tr": tr_series,
            # Symbol info namespace (November 2025: syminfo.isin, July 2025: syminfo.current_contract)
            "syminfo": self._syminfo,
            "timeframe": tf,
            "barstate": barstate,
            "chart": self._make_chart(ohlcv_data),
            "timeframe.period": tf.period,
            "timeframe.main_period": tf.main_period,
            "timeframe.multiplier": tf.multiplier,
            "timeframe.isintraday": tf.isintraday,
            "timeframe.isdaily": tf.isdaily,
            "timeframe.isweekly": tf.isweekly,
            "timeframe.ismonthly": tf.ismonthly,
            "timeframe.isseconds": tf.isseconds,
            "timeframe.isinseconds": tf.isinseconds,
            "timeframe.isdwm": tf.isdwm,
            # Per-bar counters updated in the loop below
            "bar_index": 0,
            "time": 0,
            "time_close": 0,
            "last_bar_index": max(0, len(ohlcv_data) - 1),
            "last_bar_time": ohlcv_data[-1].get("time", 0) if ohlcv_data else 0,
        }

        evaluator = CustomEvaluator(context=context, data_feed=data_feed, data_provider=data_provider)
        evaluator.reset_var_declarations()
        # Host UI overrides for input.* (keyed by title)
        if inputs and isinstance(inputs, dict):
            try:
                evaluator._input_overrides = dict(inputs)  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            evaluator._input_declarations = []  # type: ignore[attr-defined]
        except Exception:
            pass

        # fill() needs plot() → Plot handles; skip PlotRegistry otherwise (big host win).
        evaluator._pine_need_plot_ids = bool(_FILL_CALL_RE.search(source_code))  # type: ignore[attr-defined]

        # Append-only chronological OHLCV lists for ta.* helpers (oldest → newest).
        # Avoid rebuilding via list(reversed(PineSeries.history)) every bar.
        _series_lists: dict[str, list] = {
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "hl2": [],
            "hlc3": [],
            "ohlc4": [],
            "tr": [],
        }
        evaluator.current_series = _series_lists

        # Fresh drawing registries so leftover labels/lines from prior runs
        # (or tests) do not leak into this response.
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            DrawingRegistry.reset()
        except Exception:
            pass

        all_events: list[dict] = []
        all_events_append = all_events.append

        # Generate stable script_id from source hash
        script_id = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16]
        run_id = self._run_id

        n_bars = len(ohlcv_data)
        last_bar_i = n_bars - 1
        # Pre-extract columns once (single pass — avoid 6× bar walks)
        col_open: list[Any] = []
        col_high: list[Any] = []
        col_low: list[Any] = []
        col_close: list[Any] = []
        col_vol: list[Any] = []
        col_time: list[Any] = []
        _ao, _ah, _al, _ac, _av, _at = (
            col_open.append,
            col_high.append,
            col_low.append,
            col_close.append,
            col_vol.append,
            col_time.append,
        )
        has_bid_ask = False
        for b in ohlcv_data:
            _ao(b.get("open"))
            _ah(b.get("high"))
            _al(b.get("low"))
            _ac(b.get("close"))
            _av(b.get("volume", 0.0))
            _at(b.get("time", 0) or 0)
            if not has_bid_ask and (("bid" in b) or ("ask" in b)):
                has_bid_ask = True
        need_calendar = bool(_CAL_NAME_RE.search(source_code))
        need_hl2 = bool(_HL2_RE.search(source_code))
        need_hlc3 = bool(_HLC3_RE.search(source_code))
        need_ohlc4 = bool(_OHLC4_RE.search(source_code))

        # Pre-bind hot locals (series lists, methods, strategy buffers)
        sl_open = _series_lists["open"]
        sl_high = _series_lists["high"]
        sl_low = _series_lists["low"]
        sl_close = _series_lists["close"]
        sl_vol = _series_lists["volume"]
        sl_hl2 = _series_lists["hl2"]
        sl_hlc3 = _series_lists["hlc3"]
        sl_ohlc4 = _series_lists["ohlc4"]
        sl_tr = _series_lists["tr"]
        # Keep a tuple of list refs for in-place series-cap trim (no rebind).
        # Only include lists that are actually appended each bar.
        _series_list_refs_list = [sl_open, sl_high, sl_low, sl_close, sl_vol, sl_tr]
        if need_hl2:
            _series_list_refs_list.append(sl_hl2)
        if need_hlc3:
            _series_list_refs_list.append(sl_hlc3)
        if need_ohlc4:
            _series_list_refs_list.append(sl_ohlc4)
        _series_list_refs = tuple(_series_list_refs_list)
        series_cap = int(getattr(evaluator, "_SERIES_MAX", 256) or 256)
        series_cap_limit = series_cap + 64

        open_update = open_series.update
        high_update = high_series.update
        low_update = low_series.update
        close_update = close_series.update
        volume_update = volume_series.update
        hl2_update = hl2_series.update
        hlc3_update = hlc3_series.update
        ohlc4_update = ohlc4_series.update
        tr_update = tr_series.update

        # Static barstate flags for historical bar-by-bar host (do not change mid-run)
        barstate.isnew = True
        barstate.ishistory = True
        barstate.isconfirmed = True
        barstate.isrealtime = False

        visit = evaluator.visit
        reset_plots = evaluator.reset_plots
        finish_bar_plots = evaluator.finish_bar_plots
        strategy_state = evaluator._strategy_state
        pending_orders = strategy_state.pending_orders
        strategy_events = strategy_state._events
        process_pending = getattr(evaluator, "process_pending_orders", None)
        set_defs_locked = True  # first bar unlocks defs; then permanently locked

        prev_close_f: float | None = None

        for bar_index in range(n_bars):
            o = col_open[bar_index]
            h = col_high[bar_index]
            l = col_low[bar_index]
            c = col_close[bar_index]
            v = col_vol[bar_index]

            # One float cast path for derived series + true range
            try:
                of = float(o)
                hf = float(h)
                lf = float(l)
                cf = float(c)
                hl2_val: float | None = (hf + lf) * 0.5 if need_hl2 else None
                hlc3_val = (hf + lf + cf) / 3.0 if need_hlc3 else None
                ohlc4_val = (of + hf + lf + cf) * 0.25 if need_ohlc4 else None
                if prev_close_f is None:
                    tr_val: float | None = hf - lf
                else:
                    tr_val = max(hf - lf, abs(hf - prev_close_f), abs(lf - prev_close_f))
                prev_close_f = cf
            except (TypeError, ValueError):
                hl2_val = None
                hlc3_val = None
                ohlc4_val = None
                tr_val = None
                try:
                    prev_close_f = float(c)
                except (TypeError, ValueError):
                    prev_close_f = None

            open_update(o)
            high_update(h)
            low_update(l)
            close_update(c)
            volume_update(v)
            if need_hl2:
                hl2_update(hl2_val)
                sl_hl2.append(hl2_val)
            if need_hlc3:
                hlc3_update(hlc3_val)
                sl_hlc3.append(hlc3_val)
            if need_ohlc4:
                ohlc4_update(ohlc4_val)
                sl_ohlc4.append(ohlc4_val)
            tr_update(tr_val)

            # Append-only chronological lists for ta.* (shared with evaluator.current_series).
            # Cap in-place (del prefix) so pre-bound list refs stay valid.
            sl_open.append(o)
            sl_high.append(h)
            sl_low.append(l)
            sl_close.append(c)
            sl_vol.append(v)
            sl_tr.append(tr_val)
            n_hist = len(sl_close)
            if n_hist > series_cap_limit:
                drop = n_hist - series_cap
                for _lst in _series_list_refs:
                    del _lst[:drop]

            # Per-bar counters / time
            bar_time = col_time[bar_index]
            if bar_index < last_bar_i:
                time_close = col_time[bar_index + 1] or bar_time
            else:
                time_close = int(bar_time) + 86_400_000
            context["bar_index"] = bar_index
            context["time"] = bar_time
            context["time_close"] = time_close
            if need_calendar:
                apply_utc_parts_to_context(context, bar_time)

            is_last = bar_index == last_bar_i
            barstate.isfirst = bar_index == 0
            barstate.islast = is_last
            barstate.islastconfirmedhistory = is_last

            if has_bid_ask:
                bar = ohlcv_data[bar_index]
                if "bid" in bar:
                    self._bid = bar["bid"]
                if "ask" in bar:
                    self._ask = bar["ask"]

            # Reset per-bar plot index; clear strategy event buffer without extra list alloc
            reset_plots()
            if strategy_events:
                strategy_events.clear()
            # Bar-mode call-site indices (crossover + incremental ta.* + plot reuse)
            evaluator._cross_call_i = 0  # type: ignore[attr-defined]
            evaluator._ta_call_i = 0  # type: ignore[attr-defined]
            evaluator._plot_call_i = 0  # type: ignore[attr-defined]

            # Broker sim: only when there are pending limit/stop orders
            if process_pending is not None and pending_orders:
                try:
                    process_pending(open_=o, high=h, low=l, close=c)
                except Exception as e:
                    return {"error": f"Order fill error at bar {bar_time}: {e!s}"}

            try:
                visit(tree)
            except Exception as e:
                return {"error": f"Runtime Error at bar {bar_time}: {e!s}"}

            # Pad short plot columns for call sites not hit this bar
            finish_bar_plots()

            # Lock function/type/import registration after first bar (O(bars²) guard)
            if set_defs_locked:
                evaluator._pine_defs_locked = True  # type: ignore[attr-defined]
                # Keep assigning True is cheap; skip after first for micro-gain
                set_defs_locked = False

            # Strategy events (empty for pure indicators — skip drain alloc)
            if strategy_events:
                for ev in strategy_state.drain_events():
                    ev_dict = ev.to_dict()
                    ev_dict["script_id"] = script_id
                    ev_dict["run_id"] = run_id
                    all_events_append(ev_dict)

        # Build multi-series map from columnar plot capture (value cols + once-only meta)
        series_map: dict[str, list[Any]] = {}
        plot_meta: dict[str, dict[str, Any]] = {}
        value_cols: list[list[Any]] = getattr(evaluator, "_plot_value_cols", None) or []
        meta_list: list[dict[str, Any]] = getattr(evaluator, "_plot_meta_list", None) or []
        n_result_bars = n_bars
        if value_cols:
            n_result_bars = len(value_cols[0])

        def _color_str(c: Any) -> str | None:
            if c is None:
                return None
            t = type(c)
            if t is str:
                return c if c else None
            if t is int:
                return f"#{c & 0xFFFFFF:06X}"
            to_rgba = getattr(c, "to_rgba", None)
            if callable(to_rgba):
                try:
                    return str(to_rgba())
                except Exception:
                    pass
            to_hex = getattr(c, "to_hex", None)
            if callable(to_hex):
                try:
                    return str(to_hex())
                except Exception:
                    pass
            s = str(c)
            return s if s else None

        def _json_plot_value(v: Any, kind: str) -> Any:
            """JSON-safe series cell for plot / bgcolor / plotshape kinds."""
            if v is None:
                return None
            t = type(v)
            if kind == "bgcolor":
                # Capture already serializes colors to str | None
                if t is str:
                    return v if v else None
                return _color_str(v)
            if kind in ("plotshape", "plotchar", "plotarrow"):
                if t is bool:
                    return v
                if t is int or t is float:
                    try:
                        fv = float(v)
                        if fv != fv:  # NaN
                            return False
                        return fv != 0.0
                    except (TypeError, ValueError):
                        return bool(v)
                return bool(v)
            # line / hline numeric (or pass through strings already serialized)
            if t is float or t is int or t is str or t is bool:
                return v
            return _color_str(v) if hasattr(v, "to_rgba") or hasattr(v, "to_hex") else v

        max_plots = len(value_cols)
        for pi in range(max_plots):
            m0 = meta_list[pi] if pi < len(meta_list) else {}
            title = str(m0.get("title") or "") or f"plot_{pi}"
            color = m0.get("color")
            if color is not None and type(color) is not str:
                color = _color_str(color)
            elif color == "":
                color = None
            linewidth = int(m0.get("linewidth") or 1)
            kind = str(m0.get("kind") or m0.get("type") or "plot")
            style = m0.get("style")
            if style is not None:
                style = str(style) if style != "" else None
            linestyle = m0.get("linestyle")
            if linestyle is not None:
                linestyle = str(linestyle)
            location = m0.get("location")
            if location is not None:
                location = str(location) if location != "" else None
            text = m0.get("text")
            if text is not None:
                text = str(text) if text != "" else None
            char = m0.get("char")
            if char is not None:
                char = str(char) if char != "" else None

            base = title
            suffix = 2
            while title in series_map:
                title = f"{base}_{suffix}"
                suffix += 1
            raw_col = value_cols[pi]
            # Fast path: pure numeric plot columns need no per-cell work
            if kind in ("plot", "hline") and raw_col and all(
                type(v) is float or type(v) is int or v is None for v in raw_col
            ):
                values = list(raw_col)
            else:
                values = [_json_plot_value(v, kind) for v in raw_col]
            # hline: constant price — fill gaps with last known price so AXIS
            # can render a full-width level (or read price from meta).
            if kind == "hline":
                fill = None
                for v in values:
                    if v is not None:
                        fill = v
                        break
                if fill is not None:
                    values = [fill if v is None else v for v in values]
            series_map[title] = values
            meta_entry: dict[str, Any] = {
                "title": title,
                "color": color,
                "linewidth": linewidth,
                "index": pi,
                "kind": kind,
            }
            if style is not None:
                meta_entry["style"] = style
            if linestyle is not None:
                meta_entry["linestyle"] = linestyle
            if location is not None:
                meta_entry["location"] = location
            if text is not None:
                meta_entry["text"] = text
            if char is not None:
                meta_entry["char"] = char
            if kind == "hline":
                price_val = next((v for v in values if v is not None), None)
                if price_val is not None:
                    try:
                        meta_entry["price"] = float(price_val)
                    except (TypeError, ValueError):
                        meta_entry["price"] = price_val
            plot_meta[title] = meta_entry

        # Primary plots list = first plot series (backward compatible)
        final_series: list[Any] = []
        if max_plots > 0:
            final_series = list(value_cols[0])
        elif series_map:
            final_series = next(iter(series_map.values()))

        # Serialize Pine drawing objects (line/label/box) for AXIS overlay.
        # Fast path: skip bar_times materialization + export when registry empty
        # (most indicator scripts never call line/label/box/table/polyline).
        drawings: list[dict] = []
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            if not DrawingRegistry.is_empty():
                bar_times = [int(t or 0) for t in col_time]
                drawings = DrawingRegistry.export_for_api(bar_times)
        except Exception:
            drawings = []

        # Script declaration → AXIS pane routing (indicator default overlay=false)
        decl = getattr(evaluator, "_script_declaration", None)
        overlay = True
        script_name = "plot"
        script_type = "indicator"
        if decl is not None:
            script_type = str(getattr(decl, "script_type", "indicator") or "indicator")
            title = str(getattr(decl, "title", "") or "").strip()
            if title:
                script_name = title
            if hasattr(decl, "overlay"):
                overlay = bool(decl.overlay)
            else:
                kw = getattr(decl, "kwargs", None) or {}
                if "overlay" in kw:
                    overlay = bool(kw["overlay"])
                else:
                    overlay = script_type == "strategy"

        # Export input.* declarations for AXIS Script Settings (dedupe by title)
        input_defs: list[dict[str, Any]] = []
        try:
            decls = list(getattr(evaluator, "_input_declarations", None) or [])
            seen_titles: set[str] = set()
            for d in decls:
                if not isinstance(d, dict):
                    continue
                t = str(d.get("title") or "")
                if t and t in seen_titles:
                    continue
                if t:
                    seen_titles.add(t)
                # JSON-safe copy
                safe: dict[str, Any] = {}
                for k, v in d.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        safe[k] = v
                    elif isinstance(v, (list, tuple)):
                        safe[k] = [str(x) if not isinstance(x, (str, int, float, bool, type(None))) else x for x in v]
                    else:
                        safe[k] = str(v)
                input_defs.append(safe)
        except Exception:
            input_defs = []

        return {
            "plots": final_series,
            "series": series_map,
            "plot_meta": plot_meta,
            "events": all_events,
            "drawings": drawings,
            "inputs": input_defs,
            "count": n_result_bars,
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "interpret",
            "overlay": overlay,
            "script_name": script_name,
            "script_type": script_type,
            "meta": {
                "overlay": overlay,
                "script_name": script_name,
                "script_type": script_type,
                "inputs": input_defs,
            },
        }

    @staticmethod
    def _compile_eligible(source_code: str) -> tuple[bool, str]:
        """Cheap prefilter before attempting compile (auto mode).

        Returns ``(eligible, reason_if_not)``.
        """
        global _HAS_NUMBA
        if _HAS_NUMBA is False:
            return False, "numba not installed"
        if _HAS_NUMBA is None:
            try:
                from pynescript.compiler.engine import has_numba

                _HAS_NUMBA = bool(has_numba())
            except ImportError:
                _HAS_NUMBA = False
                return False, "compiler package unavailable"
            if not _HAS_NUMBA:
                return False, "numba not installed"
        src = source_code or ""
        # Import / request.* often need interpreter library + data plumbing
        if re.search(r"(?m)^\s*import\s+\S+", src):
            return False, "import statements not supported in compile path"
        if "request." in src:
            return False, "request.* not supported in compile path"
        return True, ""

    def _run_auto(
        self,
        source_code: str,
        ohlcv_data: list[dict],
        data_feed=None,
        data_provider=None,
        inputs: dict | None = None,
    ) -> dict:
        """Try compile; fall back to interpret on eligibility fail or any error."""
        eligible, reason = self._compile_eligible(source_code)
        compile_err: str | None = reason or None
        if eligible:
            compiled_result = self._run_compiled(source_code, ohlcv_data)
            if "error" not in compiled_result:
                compiled_result["mode"] = "compile"
                compiled_result["auto_backend"] = "compile"
                return compiled_result
            compile_err = str(compiled_result.get("error") or "compile failed")

        # Interpret fallback (full host semantics)
        result = self.run(
            source_code,
            ohlcv_data,
            data_feed=data_feed,
            data_provider=data_provider,
            mode="interpret",
            inputs=inputs,
        )
        if isinstance(result, dict):
            result["mode"] = result.get("mode") or "interpret"
            result["auto_backend"] = "interpret"
            if compile_err:
                result["compile_fallback_reason"] = compile_err
        return result

    def _run_compiled(self, source_code: str, ohlcv_data: list[dict]) -> dict:
        """Execute via Numba-compiled bar loop (supported subset of Pine)."""
        try:
            from pynescript.compiler.engine import compile_script
            from pynescript.compiler.engine import has_numba
        except ImportError as e:
            return {"error": f"Compile mode unavailable: {e!s}"}

        if not has_numba():
            return {"error": "Compile mode requires numba (pip install numba)"}

        if not ohlcv_data:
            return {"plots": [], "events": [], "count": 0, "mode": "compile", "series": {}}

        # Host short-circuit: raw-source hash → CompiledScript (skips sanitize on hit).
        cache_key = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        script_id = cache_key[:16]
        compiled = _HOST_COMPILE_CACHE.get(cache_key)
        was_cached = compiled is not None

        t_compile0 = time.perf_counter()
        if compiled is None:
            try:
                compiled = compile_script(source_code)
            except Exception as e:
                return {"error": f"Compile Error: {e!s}"}
            if len(_HOST_COMPILE_CACHE) >= _HOST_COMPILE_CACHE_MAX:
                try:
                    _HOST_COMPILE_CACHE.pop(next(iter(_HOST_COMPILE_CACHE)))
                except StopIteration:
                    pass
            _HOST_COMPILE_CACHE[cache_key] = compiled
        compile_ms = (time.perf_counter() - t_compile0) * 1000.0

        # Single-pass float64 packing (avoids 5 list comps + re-asarray in engine)
        opens, highs, lows, closes, volumes = _ohlcv_dicts_to_arrays(ohlcv_data)

        t_run0 = time.perf_counter()
        try:
            series_map = compiled.run(opens, highs, lows, closes, volumes)
        except Exception as e:
            return {"error": f"Compiled Runtime Error: {e!s}"}
        run_ms = (time.perf_counter() - t_run0) * 1000.0

        drawings: list[Any] = []
        events: list[Any] = []
        json_series: dict[str, list[Any]] = {}
        if isinstance(series_map, dict):
            # Pop internal keys once (avoid per-key isinstance re-checks)
            drawings = series_map.pop("__drawings", []) or []
            events = series_map.pop("__events", []) or []
            series_map.pop("__position_size", None)
            series_map.pop("__netprofit", None)
            series_map.pop("__equity", None)

            # JSON-safe series map (numpy NaN → null). Dominant host wrap cost after pack.
            _to_json = _series_values_jsonable
            for k, v in series_map.items():
                ks = k if isinstance(k, str) else str(k)
                if ks.startswith("__"):
                    continue
                json_series[ks] = _to_json(v)

        # Primary plot series (first numeric plot) as list for frontend compatibility
        final_series: list = next(iter(json_series.values()), []) if json_series else []

        # Stamp script/run ids on strategy events (skip when empty — pure indicators)
        if events:
            rid = self._run_id
            for ev in events:
                if isinstance(ev, dict):
                    ev.setdefault("script_id", script_id)
                    ev.setdefault("run_id", rid)

        # Do NOT return generated_code by default — large scripts + cold Numba make
        # JSON responses multi-MB and can trip AXIS/gunicorn timeouts. Opt-in via
        # PYNESCRIPT_RETURN_GENERATED_CODE=1 for debugging.
        out: dict[str, Any] = {
            "plots": final_series,
            "series": json_series,
            "drawings": drawings if isinstance(drawings, list) else list(drawings or []),
            "events": events if isinstance(events, list) else list(events or []),
            "count": len(ohlcv_data),
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "compile",
            "object_mode": compiled.object_mode,
            "compile_ms": round(compile_ms, 2),
            "run_ms": round(run_ms, 2),
            "compile_cached": was_cached,
        }
        if os.environ.get("PYNESCRIPT_RETURN_GENERATED_CODE", "").strip() in {"1", "true", "yes"}:
            out["generated_code"] = compiled.generated_code
        return out
