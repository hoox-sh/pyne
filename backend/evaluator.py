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

from typing import Any

from pynescript.ast.evaluator import NodeLiteralEvaluator


class CustomEvaluator(NodeLiteralEvaluator):
    """
    Evaluator that captures plot commands.
    Supports optional data_feed / data_provider for request.* integration.
    """

    def __init__(self, context=None, data_feed=None, data_provider=None):
        super().__init__(context, data_feed=data_feed, data_provider=data_provider)
        self.plot_outputs = []
        # Bar-by-bar mode: TA helpers return current scalar instead of full series
        self._pine_bar_mode = True
        # O(1)/O(period) call-site TA for sma/ema/rma/rsi (disable via PYNE_TA_INCREMENTAL=0)
        self._pine_ta_incremental = True
        # OHLCV history lists for ta helpers that read high/low/close by name
        self.current_series: dict[str, list] = {}
        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """Capture plot value + title/color for multi-series AXIS response."""
        kwargs = kwargs or {}
        if not args and "series" not in kwargs:
            return None

        value = kwargs.get("series", args[0] if args else None)
        title = kwargs.get("title", args[1] if len(args) > 1 else "")
        color = kwargs.get("color", args[2] if len(args) > 2 else None)
        linewidth = kwargs.get("linewidth", args[5] if len(args) > 5 else 1)

        # Unwrap PineSeries if necessary
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes)):
            current = getattr(value, "current", None)
            if current is not None or hasattr(value, "history"):
                value = current

        # Bar-by-bar runtime: TA helpers often return full series lists;
        # plot the current (last) bar value to match Pine semantics.
        if isinstance(value, list):
            value = value[-1] if value else None

        self.plot_outputs.append(
            {
                "type": "plot",
                "value": value,
                "title": str(title or "") or None,
                "color": color,
                "linewidth": int(linewidth or 1),
            }
        )
        # Still register on PlotRegistry for parity/backends that inspect it
        try:
            return super()._builtin_plot(args, kwargs)
        except Exception:
            return None

    def reset_plots(self):
        self.plot_outputs = []

    def reset_var_declarations(self):
        """Reset var declarations set for per-run (from plan branch var support)."""
        self._var_declarations = set()

    def reset_events(self):
        """Reset per-bar events (from strategy events integration)."""
        # Events are typically drained from strategy state in the integrated flow
        if hasattr(self, "_strategy_state"):
            self._strategy_state._events = []  # type: ignore[attr-defined]
