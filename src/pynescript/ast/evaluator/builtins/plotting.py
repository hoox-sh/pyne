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

"""Plotting builtins with real side effects (PlotRegistry).

All plot*/hline/bgcolor/barcolor/fill calls register a :class:`Plot` so
backends, tests, and parity tools can inspect visual outputs without a UI.
``plot()`` returns the Plot id (needed by ``fill(plot1, plot2)``).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


@dataclass
class Plot:
    """Plot / visual object captured during evaluation."""

    kind: str = "plot"  # plot, hline, bgcolor, barcolor, fill, plotshape, …
    series: Any = None
    title: str = ""
    color: Any = None
    style: str = ""
    linewidth: int = 1
    linestyle: str = "linestyle_solid"
    text: str = ""
    text_size: int | str = "auto"
    text_formatting: str = ""
    force_overlay: bool = False
    # hline
    price: Any = None
    # fill
    plot1: Any = None
    plot2: Any = None
    # OHLC plots
    open: Any = None
    high: Any = None
    low: Any = None
    close: Any = None
    # char/shape
    char: str = ""
    location: str = ""
    offset: int = 0
    meta: dict[str, Any] = field(default_factory=dict)
    deleted: bool = False


class PlotStyle:
    """Plot style / linestyle constants."""

    LINESTYLE_SOLID = "linestyle_solid"
    LINESTYLE_DASHED = "linestyle_dashed"
    LINESTYLE_DOTTED = "linestyle_dotted"


class PlotRegistry:
    """Registry for plot objects created during script evaluation."""

    plots: ClassVar[list[Plot]] = []

    @classmethod
    def reset(cls) -> None:
        cls.plots = []

    @classmethod
    def add(cls, plot: Plot) -> Plot:
        cls.plots.append(plot)
        return plot

    @classmethod
    def active(cls) -> list[Plot]:
        return [p for p in cls.plots if not p.deleted]


def _kw(args: list[Any], kwargs: dict[str, Any] | None, name: str, index: int | None = None, default: Any = None) -> Any:
    kw = kwargs or {}
    if name in kw and kw[name] is not None:
        return kw[name]
    if index is not None and len(args) > index:
        return args[index]
    return default


class PlottingFunctionsMixin(BuiltinDispatchMixin):
    """Plotting functions with registry side effects for non-UI evaluation."""

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
            "plot.linestyle_solid": self._builtin_plot_linestyle_solid,
            "plot.linestyle_dashed": self._builtin_plot_linestyle_dashed,
            "plot.linestyle_dotted": self._builtin_plot_linestyle_dotted,
        }

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        """plot(series, title, color, …) → plot id (Plot object)."""
        p = Plot(
            kind="plot",
            series=_kw(args, kwargs, "series", 0),
            title=str(_kw(args, kwargs, "title", 1, "") or ""),
            color=_kw(args, kwargs, "color", 2),
            style=str(_kw(args, kwargs, "style", 4, "") or ""),
            linewidth=int(_kw(args, kwargs, "linewidth", 5, 1) or 1),
            linestyle=str(_kw(args, kwargs, "linestyle", None, PlotStyle.LINESTYLE_SOLID) or PlotStyle.LINESTYLE_SOLID),
            text=str(_kw(args, kwargs, "text", 12, "") or ""),
            text_size=_kw(args, kwargs, "text_size", 15, "auto"),
            text_formatting=str(_kw(args, kwargs, "text_formatting", None, "") or ""),
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )
        return PlotRegistry.add(p)

    def _builtin_plotarrow(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="plotarrow",
            series=_kw(args, kwargs, "series", 0),
            title=str(_kw(args, kwargs, "title", 1, "arrow") or "arrow"),
            color=_kw(args, kwargs, "color", 2),
            style="arrow",
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )
        return PlotRegistry.add(p)

    def _builtin_plotbar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="plotbar",
            open=_kw(args, kwargs, "open", 0),
            high=_kw(args, kwargs, "high", 1),
            low=_kw(args, kwargs, "low", 2),
            close=_kw(args, kwargs, "close", 3),
            title=str(_kw(args, kwargs, "title", 4, "bars") or "bars"),
            color=_kw(args, kwargs, "color", 5),
            style="bars",
        )
        return PlotRegistry.add(p)

    def _builtin_plotcandle(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="plotcandle",
            open=_kw(args, kwargs, "open", 0),
            high=_kw(args, kwargs, "high", 1),
            low=_kw(args, kwargs, "low", 2),
            close=_kw(args, kwargs, "close", 3),
            title=str(_kw(args, kwargs, "title", 4, "candles") or "candles"),
            color=_kw(args, kwargs, "color", 5),
            style="candles",
            meta={
                "wickcolor": _kw(args, kwargs, "wickcolor", None),
                "bordercolor": _kw(args, kwargs, "bordercolor", None),
            },
        )
        return PlotRegistry.add(p)

    def _builtin_plotchar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="plotchar",
            series=_kw(args, kwargs, "series", 0),
            title=str(_kw(args, kwargs, "title", 1, "char") or "char"),
            char=str(_kw(args, kwargs, "char", 2, "") or ""),
            location=str(_kw(args, kwargs, "location", 3, "") or ""),
            color=_kw(args, kwargs, "color", 4),
            offset=int(_kw(args, kwargs, "offset", 5, 0) or 0),
            style="char",
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )
        return PlotRegistry.add(p)

    def _builtin_plotshape(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="plotshape",
            series=_kw(args, kwargs, "series", 0),
            title=str(_kw(args, kwargs, "title", 1, "shape") or "shape"),
            style=str(_kw(args, kwargs, "style", 2, "shape") or "shape"),
            location=str(_kw(args, kwargs, "location", 3, "") or ""),
            color=_kw(args, kwargs, "color", 4),
            offset=int(_kw(args, kwargs, "offset", 5, 0) or 0),
            text=str(_kw(args, kwargs, "text", None, "") or ""),
            text_size=_kw(args, kwargs, "size", None, "auto"),
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )
        return PlotRegistry.add(p)

    def _builtin_fill(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="fill",
            plot1=_kw(args, kwargs, "plot1", 0),
            plot2=_kw(args, kwargs, "plot2", 1),
            color=_kw(args, kwargs, "color", 2),
            title=str(_kw(args, kwargs, "title", 3, "fill") or "fill"),
            style="fill",
        )
        return PlotRegistry.add(p)

    def _builtin_bgcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="bgcolor",
            color=_kw(args, kwargs, "color", 0),
            title=str(_kw(args, kwargs, "title", 1, "bgcolor") or "bgcolor"),
            offset=int(_kw(args, kwargs, "offset", None, 0) or 0),
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
            style="bgcolor",
        )
        return PlotRegistry.add(p)

    def _builtin_barcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        p = Plot(
            kind="barcolor",
            color=_kw(args, kwargs, "color", 0),
            title=str(_kw(args, kwargs, "title", None, "barcolor") or "barcolor"),
            offset=int(_kw(args, kwargs, "offset", 1, 0) or 0),
            style="barcolor",
        )
        return PlotRegistry.add(p)

    def _builtin_hline(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        price = _kw(args, kwargs, "price", 0, 0.0)
        p = Plot(
            kind="hline",
            price=price,
            series=price,
            title=str(_kw(args, kwargs, "title", 1, "hline") or "hline"),
            color=_kw(args, kwargs, "color", 2),
            linestyle=str(_kw(args, kwargs, "linestyle", 3, PlotStyle.LINESTYLE_SOLID) or PlotStyle.LINESTYLE_SOLID),
            linewidth=int(_kw(args, kwargs, "linewidth", 4, 1) or 1),
            style="hline",
        )
        return PlotRegistry.add(p)

    def _builtin_plot_linestyle_solid(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return PlotStyle.LINESTYLE_SOLID

    def _builtin_plot_linestyle_dashed(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return PlotStyle.LINESTYLE_DASHED

    def _builtin_plot_linestyle_dotted(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return PlotStyle.LINESTYLE_DOTTED
