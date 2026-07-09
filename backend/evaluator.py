# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from typing import Any

from pynescript.ast.evaluator import NodeLiteralEvaluator


class CustomEvaluator(NodeLiteralEvaluator):
    """
    Evaluator that captures plot commands.
    """

    def __init__(self, context=None):
        super().__init__(context)
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
        if hasattr(value, "current"):
            value = value.current

        self.plot_outputs.append({"type": "plot", "value": value})
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
