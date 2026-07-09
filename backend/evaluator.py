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
