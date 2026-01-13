# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class PlottingFunctionsMixin(BuiltinDispatchMixin):
    """Plotting function stubs for Pine Script compatibility."""

    def _plotting_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "plot": self._builtin_plot,
            "plotarrow": self._builtin_plotarrow,
            "plotbar": self._builtin_plotbar,
            "plotcandle": self._builtin_plotcandle,
            "plotchar": self._builtin_plotchar,
            "plotshape": self._builtin_plotshape,
            "fill": self._builtin_fill,
            "bgcolor": self._builtin_bgcolor,
            "barcolor": self._builtin_barcolor,
            "hline": self._builtin_hline,
        }

    def _builtin_plot(self, _args: list[Any]) -> None:
        """Stub: plot(series, title, color, linewidth, style, trackprice)."""
        # In Pine Script, plot() returns None and has side effects on the chart
        # This is a stub that accepts the arguments but does nothing
        return None

    def _builtin_plotarrow(self, _args: list[Any]) -> None:
        """Stub: plotarrow(series, title, colorup, colordown, offset,
        minHeight, maxHeight)."""
        return None

    def _builtin_plotbar(self, _args: list[Any]) -> None:
        """Stub: plotbar(open, high, low, close, title, color,
        editable, show_last)."""
        return None

    def _builtin_plotcandle(self, _args: list[Any]) -> None:
        """Stub: plotcandle(open, high, low, close, title, color,
        editable, show_last, wickcolor, bordercolor)."""
        return None

    def _builtin_plotchar(self, _args: list[Any]) -> None:
        """Stub: plotchar(series, title, char, location, color, offset,
        size, editable, show_last)."""
        return None

    def _builtin_plotshape(self, _args: list[Any]) -> None:
        """Stub: plotshape(series, title, style, location, color,
        offset, text, editable, show_last)."""
        return None

    def _builtin_fill(self, _args: list[Any]) -> None:
        """Stub: fill(plot1, plot2, color, title, editable, show_last)."""
        return None

    def _builtin_bgcolor(self, _args: list[Any]) -> None:
        """Stub: bgcolor(color, title, editable, show_last)."""
        return None

    def _builtin_barcolor(self, _args: list[Any]) -> None:
        """Stub: barcolor(color, offset, editable, show_last)."""
        return None

    def _builtin_hline(self, _args: list[Any]) -> None:
        """Stub: hline(price, title, color, linestyle, linewidth)."""
        return None
