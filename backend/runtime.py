# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from __future__ import annotations

import hashlib
import uuid

from datetime import datetime
from datetime import timezone

from pynescript.ast.helper import parse

from .evaluator import CustomEvaluator
from .series import PineSeries


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
    """Chart namespace for Pine Script builtins."""

    fg_color: str = "#000000"
    bg_color: str = "#FFFFFF"
    resolution: str = "D"

    # Chart display mode
    is_heikin_ashi: bool = False
    is_kagi: bool = False
    is_line_break: bool = False
    is_point_figure: bool = False
    is_renko: bool = False
    is_range: bool = False


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
        mode: str = "interpret",
    ):
        """
        Execute the script over the provided OHLCV data.

        Args:
            source_code: Pine Script source to run.
            ohlcv_data: List of dicts with 'open', 'high', 'low', 'close', 'time'.
            data_feed: Optional realtime DataFeed for request.* live data.
            data_provider: Optional historical provider for request.* .
            mode: ``"interpret"`` (default AST walker) or ``"compile"`` (Numba
                bar-loop for a supported subset: ta.sma/ema/rsi, plots, math).

        Returns:
            dict with 'series': list of plotted values for each bar.
        """
        if mode == "compile":
            return self._run_compiled(source_code, ohlcv_data)

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

        # Parse once
        try:
            tree = parse(source_code, mode="exec")
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
            "chart": Chart(),
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

        # Fresh drawing registries so leftover labels/lines from prior runs
        # (or tests) do not leak into this response.
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            DrawingRegistry.reset()
        except Exception:
            pass

        results = []
        all_events: list[dict] = []

        # Generate stable script_id from source hash
        script_id = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16]

        n_bars = len(ohlcv_data)
        for bar_index, bar in enumerate(ohlcv_data):
            # Update series state
            o = bar.get("open")
            h = bar.get("high")
            l = bar.get("low")
            c = bar.get("close")
            v = bar.get("volume", 0.0)
            open_series.update(o)
            high_series.update(h)
            low_series.update(l)
            close_series.update(c)
            volume_series.update(v)
            try:
                hl2_series.update((float(h) + float(l)) / 2.0)
                hlc3_series.update((float(h) + float(l) + float(c)) / 3.0)
                ohlc4_series.update((float(o) + float(h) + float(l) + float(c)) / 4.0)
            except (TypeError, ValueError):
                hl2_series.update(None)
                hlc3_series.update(None)
                ohlc4_series.update(None)
            # True range: max(h-l, |h-prev_c|, |l-prev_c|)
            try:
                if bar_index == 0 or close_series[1] is None:
                    tr_val = float(h) - float(l) if h is not None and l is not None else None
                else:
                    prev_c = float(close_series[1])
                    tr_val = max(
                        float(h) - float(l),
                        abs(float(h) - prev_c),
                        abs(float(l) - prev_c),
                    )
            except (TypeError, ValueError):
                tr_val = None
            tr_series.update(tr_val)

            # Update per-bar counters and time components
            bar_time = bar.get("time", 0) or 0
            if bar_index + 1 < n_bars:
                time_close = ohlcv_data[bar_index + 1].get("time", bar_time) or bar_time
            else:
                time_close = int(bar_time) + 86_400_000
            context["bar_index"] = bar_index
            context["time"] = bar_time
            context["time_close"] = time_close
            try:
                dt = datetime.fromtimestamp(int(bar_time) / 1000, tz=timezone.utc)
                context["year"] = dt.year
                context["month"] = dt.month
                context["dayofmonth"] = dt.day
                context["hour"] = dt.hour
                context["minute"] = dt.minute
                context["second"] = dt.second
                context["dayofweek"] = ((dt.weekday() + 1) % 7) + 1
            except (ValueError, OSError, OverflowError):
                pass

            barstate.isfirst = bar_index == 0
            barstate.islast = bar_index == n_bars - 1
            barstate.isnew = True
            barstate.ishistory = True
            barstate.isconfirmed = True
            barstate.islastconfirmedhistory = barstate.islast
            barstate.isrealtime = False

            # Update bid/ask if available (February 2025)
            if "bid" in bar:
                self._bid = bar["bid"]
            if "ask" in bar:
                self._ask = bar["ask"]
            # Keep ta helpers' current_series in sync (high/low/close history)
            def _hist(series_obj):
                try:
                    return list(reversed(series_obj.history))
                except Exception:
                    return []

            evaluator.current_series = {
                "open": _hist(open_series),
                "high": _hist(high_series),
                "low": _hist(low_series),
                "close": _hist(close_series),
                "volume": _hist(volume_series),
                "hl2": _hist(hl2_series),
                "hlc3": _hist(hlc3_series),
                "ohlc4": _hist(ohlc4_series),
                "tr": _hist(tr_series),
            }

            # Reset plot capture and event buffer for this bar
            evaluator.reset_plots()
            evaluator.reset_events()
            # Bar-mode ta.crossover/crossunder call-index (stateful prev pair)
            evaluator._cross_call_i = 0  # type: ignore[attr-defined]

            # Fill pending strategy.order limit/stop against this bar's OHLC
            # before script re-evaluation (broker sim step).
            try:
                if hasattr(evaluator, "process_pending_orders"):
                    evaluator.process_pending_orders(
                        open_=bar.get("open"),
                        high=bar.get("high"),
                        low=bar.get("low"),
                        close=bar.get("close"),
                    )
            except Exception as e:
                return {"error": f"Order fill error at bar {bar.get('time')}: {e!s}"}

            # Execute script
            try:
                evaluator.visit(tree)
            except Exception as e:
                # In a real engine we might handle runtime errors more gracefully
                # e.g. propagate 'na' or halt
                return {"error": f"Runtime Error at bar {bar.get('time')}: {e!s}"}

            # After the first bar, lock function/type/import registration.
            # Re-visiting Console-scale method tables every bar used to append
            # multi-dispatch overloads (O(bars²)) and time out the PWA (30s).
            evaluator._pine_defs_locked = True  # type: ignore[attr-defined]

            # Collect events from this bar (convert to dicts for serialization)
            bar_events = evaluator._strategy_state.drain_events()
            for ev in bar_events:
                ev_dict = ev.to_dict()
                ev_dict["script_id"] = script_id
                ev_dict["run_id"] = self._run_id
                all_events.append(ev_dict)

            # Collect every plot() on this bar (value + title + color)
            bar_result: dict[str, Any] = {"_plots": list(evaluator.plot_outputs)}
            for i, plot in enumerate(evaluator.plot_outputs):
                bar_result[f"plot_{i}"] = plot.get("value")
            results.append(bar_result)

        # Build multi-series map for AXIS (all plot() calls, not just first)
        series_map: dict[str, list[Any]] = {}
        plot_meta: dict[str, dict[str, Any]] = {}
        n_bars = len(results)

        def _color_str(c: Any) -> str | None:
            if c is None:
                return None
            if isinstance(c, str) and c:
                return c
            if isinstance(c, int):
                return f"#{c & 0xFFFFFF:06X}"
            return str(c)

        # Discover max plot count / stable keys from first non-empty bar
        max_plots = 0
        for br in results:
            max_plots = max(max_plots, len(br.get("_plots") or []))

        for pi in range(max_plots):
            # Prefer title from first bar that defines this plot index
            title = f"plot_{pi}"
            color = None
            linewidth = 1
            for br in results:
                plots = br.get("_plots") or []
                if pi < len(plots):
                    t = plots[pi].get("title")
                    if t:
                        title = str(t)
                    if plots[pi].get("color") is not None:
                        color = _color_str(plots[pi].get("color"))
                    if plots[pi].get("linewidth"):
                        linewidth = int(plots[pi]["linewidth"] or 1)
                    break
            # Disambiguate duplicate titles
            base = title
            suffix = 2
            while title in series_map:
                title = f"{base}_{suffix}"
                suffix += 1
            values: list[Any] = []
            for br in results:
                plots = br.get("_plots") or []
                if pi < len(plots):
                    values.append(plots[pi].get("value"))
                else:
                    values.append(None)
            series_map[title] = values
            plot_meta[title] = {
                "title": title,
                "color": color,
                "linewidth": linewidth,
                "index": pi,
            }

        # Primary plots list = first plot series (backward compatible)
        final_series: list[Any] = []
        if results and "plot_0" in results[0]:
            final_series = [r.get("plot_0") for r in results]
        elif series_map:
            final_series = next(iter(series_map.values()))

        # Serialize Pine drawing objects (line/label/box) for AXIS overlay
        drawings: list[dict] = []
        try:
            from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

            bar_times = [int(b.get("time", 0) or 0) for b in ohlcv_data]
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

        return {
            "plots": final_series,
            "series": series_map,
            "plot_meta": plot_meta,
            "events": all_events,
            "drawings": drawings,
            "count": len(results),
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
            },
        }

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

        try:
            compiled = compile_script(source_code)
        except Exception as e:
            return {"error": f"Compile Error: {e!s}"}

        opens = [float(b.get("open", 0.0)) for b in ohlcv_data]
        highs = [float(b.get("high", 0.0)) for b in ohlcv_data]
        lows = [float(b.get("low", 0.0)) for b in ohlcv_data]
        closes = [float(b.get("close", 0.0)) for b in ohlcv_data]
        volumes = [float(b.get("volume", 1.0)) for b in ohlcv_data]

        try:
            series_map = compiled.run(opens, highs, lows, closes, volumes)
        except Exception as e:
            return {"error": f"Compiled Runtime Error: {e!s}"}

        drawings = series_map.pop("__drawings", []) if isinstance(series_map, dict) else []
        events = series_map.pop("__events", []) if isinstance(series_map, dict) else []
        # Drop internal compile metrics from series map (keep plots)
        for meta_key in ("__position_size", "__netprofit", "__equity"):
            if isinstance(series_map, dict):
                series_map.pop(meta_key, None)

        # Primary plot series (first numeric plot) as list for frontend compatibility
        final_series: list = []
        numeric = {k: v for k, v in series_map.items() if hasattr(v, "tolist")}
        if numeric:
            first = next(iter(numeric.values()))
            final_series = [None if (isinstance(x, float) and x != x) else float(x) for x in first]

        script_id = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16]
        # Stamp script/run ids on strategy events
        if isinstance(events, list):
            for ev in events:
                if isinstance(ev, dict):
                    ev.setdefault("script_id", script_id)
                    ev.setdefault("run_id", self._run_id)

        return {
            "plots": final_series,
            "series": {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in series_map.items()},
            "drawings": drawings,
            "events": events if isinstance(events, list) else [],
            "count": len(ohlcv_data),
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "compile",
            "object_mode": compiled.object_mode,
            "generated_code": compiled.generated_code,
        }
