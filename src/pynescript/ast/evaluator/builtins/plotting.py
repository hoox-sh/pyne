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

"""Plotting builtins with real side effects (PlotRegistry).

All plot*/hline/bgcolor/barcolor/fill calls register a :class:`Plot` so
backends, tests, and parity tools can inspect visual outputs without a UI.
``plot()`` returns the Plot id (needed by ``fill(plot1, plot2)``).

Bar-mode (Runtime) reuses Plot objects by call-site index so N bars do not
allocate N×M Plot instances / string conversions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import ClassVar

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler

# Hot-path constants (avoid attribute lookups + str() on defaults every bar)
_LS_SOLID = "linestyle_solid"
_EMPTY = ""
_AUTO = "auto"
_MISSING: Any = object()


@dataclass(slots=True)
class Plot:
    """Plot / visual object captured during evaluation.

    ``slots=True`` keeps per-object footprint small; bar-mode reuses instances
    so the registry stays O(plots) rather than O(bars × plots).
    """

    kind: str = "plot"  # plot, hline, bgcolor, barcolor, fill, plotshape, …
    series: Any = None
    title: str = _EMPTY
    color: Any = None
    style: str = _EMPTY
    linewidth: int = 1
    linestyle: str = _LS_SOLID
    text: str = _EMPTY
    text_size: int | str = _AUTO
    text_formatting: str = _EMPTY
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
    char: str = _EMPTY
    location: str = _EMPTY
    offset: int = 0
    # Only allocated when a plot kind needs extra keys (e.g. plotcandle)
    meta: dict[str, Any] | None = None
    deleted: bool = False


class PlotStyle:
    """Plot style / linestyle constants."""

    LINESTYLE_SOLID = _LS_SOLID
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


def _kw(
    args: list[Any],
    kwargs: dict[str, Any] | None,
    name: str,
    index: int | None = None,
    default: Any = None,
) -> Any:
    """Resolve keyword-or-positional arg without allocating empty dicts."""
    if kwargs is not None:
        v = kwargs.get(name, _MISSING)
        if v is not _MISSING and v is not None:
            return v
    if index is not None and len(args) > index:
        return args[index]
    return default


def _as_str(v: Any, default: str = _EMPTY) -> str:
    if v is None:
        return default
    if isinstance(v, str):
        return v
    return str(v)


def _as_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _fill_plot(
    p: Plot,
    *,
    kind: str = "plot",
    series: Any = None,
    title: str = _EMPTY,
    color: Any = None,
    style: str = _EMPTY,
    linewidth: int = 1,
    linestyle: str = _LS_SOLID,
    text: str = _EMPTY,
    text_size: int | str = _AUTO,
    text_formatting: str = _EMPTY,
    force_overlay: bool = False,
    price: Any = None,
    plot1: Any = None,
    plot2: Any = None,
    open: Any = None,
    high: Any = None,
    low: Any = None,
    close: Any = None,
    char: str = _EMPTY,
    location: str = _EMPTY,
    offset: int = 0,
    meta: dict[str, Any] | None = None,
) -> Plot:
    """Write all fields (full defaults) so bar-mode reuse cannot leak stale state."""
    p.kind = kind
    p.series = series
    p.title = title
    p.color = color
    p.style = style
    p.linewidth = linewidth
    p.linestyle = linestyle
    p.text = text
    p.text_size = text_size
    p.text_formatting = text_formatting
    p.force_overlay = force_overlay
    p.price = price
    p.plot1 = plot1
    p.plot2 = plot2
    p.open = open
    p.high = high
    p.low = low
    p.close = close
    p.char = char
    p.location = location
    p.offset = offset
    p.meta = meta
    p.deleted = False
    return p


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

    def _plot_upsert(self, **fields: Any) -> Plot:
        """Create or reuse a Plot for this call site.

        In bar mode (Runtime), ``_plot_call_i`` indexes into PlotRegistry so
        each call site keeps a stable handle across bars — O(plots) storage
        and no per-bar dataclass allocation after the first bar.
        """
        if getattr(self, "_pine_bar_mode", False):
            # _plot_call_i is always an int in Runtime; avoid int() / or 0 each plot
            i = getattr(self, "_plot_call_i", 0)
            if i is None:
                i = 0
            self._plot_call_i = i + 1  # type: ignore[attr-defined]
            plots = PlotRegistry.plots
            if i < len(plots):
                return _fill_plot(plots[i], **fields)
            p = _fill_plot(Plot(), **fields)
            plots.append(p)
            return p
        return PlotRegistry.add(_fill_plot(Plot(), **fields))

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        """plot(series, title, color, …) → plot id (Plot object)."""
        # Fast path: plot(series) / plot(series, title, color, …) with no kwargs
        if not kwargs:
            series = args[0] if args else None
            n = len(args)
            title = _as_str(args[1], _EMPTY) if n > 1 else _EMPTY
            color = args[2] if n > 2 else None
            style = _as_str(args[4], _EMPTY) if n > 4 else _EMPTY
            linewidth = _as_int(args[5], 1) if n > 5 else 1
            return self._plot_upsert(
                kind="plot",
                series=series,
                title=title,
                color=color,
                style=style,
                linewidth=linewidth,
            )

        return self._plot_upsert(
            kind="plot",
            series=_kw(args, kwargs, "series", 0),
            title=_as_str(_kw(args, kwargs, "title", 1, _EMPTY), _EMPTY),
            color=_kw(args, kwargs, "color", 2),
            style=_as_str(_kw(args, kwargs, "style", 4, _EMPTY), _EMPTY),
            linewidth=_as_int(_kw(args, kwargs, "linewidth", 5, 1), 1),
            linestyle=_as_str(_kw(args, kwargs, "linestyle", None, _LS_SOLID), _LS_SOLID),
            text=_as_str(_kw(args, kwargs, "text", 12, _EMPTY), _EMPTY),
            text_size=_kw(args, kwargs, "text_size", 15, _AUTO),
            text_formatting=_as_str(_kw(args, kwargs, "text_formatting", None, _EMPTY), _EMPTY),
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )

    def _builtin_plotarrow(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="plotarrow",
            series=_kw(args, kwargs, "series", 0),
            title=_as_str(_kw(args, kwargs, "title", 1, "arrow"), "arrow"),
            color=_kw(args, kwargs, "color", 2),
            style="arrow",
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )

    def _builtin_plotbar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="plotbar",
            open=_kw(args, kwargs, "open", 0),
            high=_kw(args, kwargs, "high", 1),
            low=_kw(args, kwargs, "low", 2),
            close=_kw(args, kwargs, "close", 3),
            title=_as_str(_kw(args, kwargs, "title", 4, "bars"), "bars"),
            color=_kw(args, kwargs, "color", 5),
            style="bars",
        )

    def _builtin_plotcandle(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        wick = _kw(args, kwargs, "wickcolor", None)
        border = _kw(args, kwargs, "bordercolor", None)
        meta = None
        if wick is not None or border is not None:
            meta = {"wickcolor": wick, "bordercolor": border}
        return self._plot_upsert(
            kind="plotcandle",
            open=_kw(args, kwargs, "open", 0),
            high=_kw(args, kwargs, "high", 1),
            low=_kw(args, kwargs, "low", 2),
            close=_kw(args, kwargs, "close", 3),
            title=_as_str(_kw(args, kwargs, "title", 4, "candles"), "candles"),
            color=_kw(args, kwargs, "color", 5),
            style="candles",
            meta=meta,
        )

    def _builtin_plotchar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="plotchar",
            series=_kw(args, kwargs, "series", 0),
            title=_as_str(_kw(args, kwargs, "title", 1, "char"), "char"),
            char=_as_str(_kw(args, kwargs, "char", 2, _EMPTY), _EMPTY),
            location=_as_str(_kw(args, kwargs, "location", 3, _EMPTY), _EMPTY),
            color=_kw(args, kwargs, "color", 4),
            offset=_as_int(_kw(args, kwargs, "offset", 5, 0), 0),
            style="char",
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )

    def _builtin_plotshape(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="plotshape",
            series=_kw(args, kwargs, "series", 0),
            title=_as_str(_kw(args, kwargs, "title", 1, "shape"), "shape"),
            style=_as_str(_kw(args, kwargs, "style", 2, "shape"), "shape"),
            location=_as_str(_kw(args, kwargs, "location", 3, _EMPTY), _EMPTY),
            color=_kw(args, kwargs, "color", 4),
            offset=_as_int(_kw(args, kwargs, "offset", 5, 0), 0),
            text=_as_str(_kw(args, kwargs, "text", None, _EMPTY), _EMPTY),
            text_size=_kw(args, kwargs, "size", None, _AUTO),
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
        )

    def _builtin_fill(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="fill",
            plot1=_kw(args, kwargs, "plot1", 0),
            plot2=_kw(args, kwargs, "plot2", 1),
            color=_kw(args, kwargs, "color", 2),
            title=_as_str(_kw(args, kwargs, "title", 3, "fill"), "fill"),
            style="fill",
        )

    def _builtin_bgcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="bgcolor",
            color=_kw(args, kwargs, "color", 0),
            title=_as_str(_kw(args, kwargs, "title", 1, "bgcolor"), "bgcolor"),
            offset=_as_int(_kw(args, kwargs, "offset", None, 0), 0),
            force_overlay=bool(_kw(args, kwargs, "force_overlay", None, False)),
            style="bgcolor",
        )

    def _builtin_barcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        return self._plot_upsert(
            kind="barcolor",
            color=_kw(args, kwargs, "color", 0),
            title=_as_str(_kw(args, kwargs, "title", None, "barcolor"), "barcolor"),
            offset=_as_int(_kw(args, kwargs, "offset", 1, 0), 0),
            style="barcolor",
        )

    def _builtin_hline(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Plot:
        price = _kw(args, kwargs, "price", 0, 0.0)
        return self._plot_upsert(
            kind="hline",
            price=price,
            series=price,
            title=_as_str(_kw(args, kwargs, "title", 1, "hline"), "hline"),
            color=_kw(args, kwargs, "color", 2),
            linestyle=_as_str(_kw(args, kwargs, "linestyle", 3, _LS_SOLID), _LS_SOLID),
            linewidth=_as_int(_kw(args, kwargs, "linewidth", 4, 1), 1),
            style="hline",
        )

    def _builtin_plot_linestyle_solid(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return PlotStyle.LINESTYLE_SOLID

    def _builtin_plot_linestyle_dashed(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return PlotStyle.LINESTYLE_DASHED

    def _builtin_plot_linestyle_dotted(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        return PlotStyle.LINESTYLE_DOTTED
