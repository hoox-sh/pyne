# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class PlotStyle:
    """Plot style constants for Pine Script.

    September 2025: Added linestyle parameter to plot().
    """

    # Line styles (September 2025 feature)
    LINESTYLE_SOLID = "linestyle_solid"
    LINESTYLE_DASHED = "linestyle_dashed"
    LINESTYLE_DOTTED = "linestyle_dotted"

    # Plot styles
    STYLE_LINE = "plot_style_line"
    STYLE_LINE_BRK = "plot_style_line_brk"
    STYLE_STEPDOWN = "plot_style_stePDown"
    STYLE_STEPLEFT = "plot_style_stepleft"
    STYLE_STEPRIGHT = "plot_style_stepright"
    STYLE_HISTOGRAM = "plot_style_histogram"
    STYLE_CROSS = "plot_style_cross"
    STYLE_STAIR = "plot_style_stair"
    STYLE_CIRCLES = "plot_style_circles"
    STYLE_PLOLINE = "plot_style_colL"
    STYLE_BARS = "plot_style_stair"


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
            # September 2025: Plot linestyle constants
            "plot.linestyle_solid": self._builtin_plot_linestyle_solid,
            "plot.linestyle_dashed": self._builtin_plot_linestyle_dashed,
            "plot.linestyle_dotted": self._builtin_plot_linestyle_dotted,
        }

    def _builtin_plot(self, args: list[Any]) -> None:
        """Plot a series on the chart.

        plot(series, title, color, opacity, style, linewidth, trackprice,
             crossing_disabled, display, force_overlay, format, format_num, text, text_wrap,
             text_color, text_size, text_align, text_halign, text_valign, linestyle)

        Added September 2025: linestyle parameter for dashed/dotted lines.
        Added November 2024: text_formatting parameter.

        Parameters:
            series: Value to plot
            title: Plot title
            color: Plot color
            opacity: Opacity (0-100)
            style: Plot style (line, histogram, etc.)
            linewidth: Line width (1-4)
            trackprice: Track price level
            crossing_disabled: Disable crossing markers
            display: Display settings
            force_overlay: Plot in main chart pane
            format: Number format
            format_num: Format precision
            text: Display text
            text_wrap: Text wrap setting
            text_color: Text color
            text_size: Text size
            text_align: Text alignment
            text_halign: Horizontal alignment
            text_valign: Vertical alignment
            linestyle: Line style (September 2025: plot.linestyle_solid, dashed, dotted)
        """
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

    # September 2025: Plot linestyle constants
    def _builtin_plot_linestyle_solid(self, _args: list[Any]) -> str:
        """plot.linestyle_solid - Solid line style constant."""
        return PlotStyle.LINESTYLE_SOLID

    def _builtin_plot_linestyle_dashed(self, _args: list[Any]) -> str:
        """plot.linestyle_dashed - Dashed line style constant."""
        return PlotStyle.LINESTYLE_DASHED

    def _builtin_plot_linestyle_dotted(self, _args: list[Any]) -> str:
        """plot.linestyle_dotted - Dotted line style constant."""
        return PlotStyle.LINESTYLE_DOTTED
