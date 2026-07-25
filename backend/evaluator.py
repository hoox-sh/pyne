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
        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """
        Capture the value being plotted.
        Arguments expected: series, title, color, linewidth, style, trackprice, etc.
        For now, we just grab the first argument (series/value).
        """
        if not args:
            return None

        value = args[0]

        # Unwrap PineSeries if necessary
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes)):
            current = getattr(value, "current", None)
            if current is not None or hasattr(value, "history"):
                value = current

        # Bar-by-bar runtime: TA helpers often return full series lists;
        # plot the current (last) bar value to match Pine semantics.
        if isinstance(value, list):
            value = value[-1] if value else None

        self.plot_outputs.append({"type": "plot", "value": value})
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
