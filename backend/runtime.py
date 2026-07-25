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
    """Timeframe information namespace for Pine Script builtins."""

    period: str = "D"  # e.g., "1D", "1H", "5"
    multiplier: int = 1
    isintraday: bool = False
    is_daily: bool = False
    is_weekly: bool = False
    is_monthly: bool = False
    is_seconds: bool = False
    current: str = "D"

    # November 2024: Main period from chart's main context
    main_period: str = "D"


class Barstate:
    """Bar state information namespace for Pine Script builtins."""

    islast: bool = False
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

        # Context initialization
        context = {
            "open": open_series,
            "high": high_series,
            "low": low_series,
            "close": close_series,
            # Symbol info namespace (November 2025: syminfo.isin, July 2025: syminfo.current_contract)
            "syminfo": self._syminfo,
            "timeframe": Timeframe(),
            "barstate": Barstate(),
            "chart": Chart(),
            # Per-bar counters updated in the loop below
            "bar_index": 0,
            "time": 0,
        }

        evaluator = CustomEvaluator(context=context, data_feed=data_feed, data_provider=data_provider)
        evaluator.reset_var_declarations()

        results = []
        all_events: list[dict] = []

        # Generate stable script_id from source hash
        script_id = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16]

        for bar_index, bar in enumerate(ohlcv_data):
            # Update series state
            open_series.update(bar.get("open"))
            high_series.update(bar.get("high"))
            low_series.update(bar.get("low"))
            close_series.update(bar.get("close"))

            # Update per-bar counters
            context["bar_index"] = bar_index
            context["time"] = bar.get("time", 0)

            # Update bid/ask if available (February 2025)
            if "bid" in bar:
                self._bid = bar["bid"]
            if "ask" in bar:
                self._ask = bar["ask"]

            # Reset plot capture and event buffer for this bar
            evaluator.reset_plots()
            evaluator.reset_events()

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

            # Collect events from this bar (convert to dicts for serialization)
            bar_events = evaluator._strategy_state.drain_events()
            for ev in bar_events:
                ev_dict = ev.to_dict()
                ev_dict["script_id"] = script_id
                ev_dict["run_id"] = self._run_id
                all_events.append(ev_dict)

            # Collect outputs from this bar
            # For simplicity, we assume one plot() call for now and return that value.
            # If there are multiple plots, we'd need a more structured response.
            bar_result = {}
            for i, plot in enumerate(evaluator.plot_outputs):
                bar_result[f"plot_{i}"] = plot["value"]

            results.append(bar_result)

        # Post-process results into structure expected by frontend
        # Front end expects: array of values for the overlay series.
        # Let's simplify and just return the first plot series found.

        final_series = []
        if results and "plot_0" in results[0]:
            final_series = [r.get("plot_0") for r in results]

        return {
            "plots": final_series,
            "events": all_events,
            "count": len(results),
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "interpret",
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

        # Primary plot series (first numeric plot) as list for frontend compatibility
        final_series: list = []
        numeric = {k: v for k, v in series_map.items() if hasattr(v, "tolist")}
        if numeric:
            first = next(iter(numeric.values()))
            final_series = [None if (isinstance(x, float) and x != x) else float(x) for x in first]

        script_id = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:16]
        return {
            "plots": final_series,
            "series": {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in series_map.items()},
            "drawings": drawings,
            "events": [],
            "count": len(ohlcv_data),
            "script_id": script_id,
            "run_id": self._run_id,
            "mode": "compile",
            "object_mode": compiled.object_mode,
            "generated_code": compiled.generated_code,
        }
