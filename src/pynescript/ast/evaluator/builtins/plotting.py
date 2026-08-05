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

Also exports :func:`materialize_visual_series_from_drawings` so compile-mode
``__drawings`` events (bgcolor / plotshape / plotchar / plotarrow) can be
lifted into titled series keys matching interpret packaging (parity helper;
wire from Runtime / engine when dual-mode packing is enabled).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from typing import ClassVar
from typing import Iterable
from typing import Mapping
from typing import MutableMapping
from typing import Sequence

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler

# Hot-path constants (avoid attribute lookups + str() on defaults every bar)
_LS_SOLID = "linestyle_solid"
_EMPTY = ""
_AUTO = "auto"
_MISSING: Any = object()

# Default series titles when the Pine call omits ``title=`` (interpret + compile).
DEFAULT_VISUAL_TITLES: dict[str, str] = {
    "plot": "plot",
    "hline": "hline",
    "bgcolor": "bgcolor",
    "barcolor": "barcolor",
    "fill": "fill",
    "plotshape": "shape",
    "plotchar": "char",
    "plotarrow": "arrow",
    "plotbar": "bars",
    "plotcandle": "candles",
}

# Compile ``__drawings`` kinds that interpret exports as series + plot_meta.
_VISUAL_SERIES_KINDS: frozenset[str] = frozenset(
    {"bgcolor", "plotshape", "plotchar", "plotarrow"}
)


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


def uniquify_series_title(title: str, used: MutableMapping[str, Any] | set[str] | None = None) -> str:
    """Return a series key unused in *used* (``title``, ``title_2``, …).

    Matches Runtime interpret packaging and compile ``_unique_plot_title``.
    """
    base = (title or _EMPTY).strip() or "plot"
    used_set: set[str]
    if used is None:
        used_set = set()
    elif isinstance(used, set):
        used_set = used
    else:
        used_set = set(used.keys()) if hasattr(used, "keys") else set(used)  # type: ignore[arg-type]
    if base not in used_set:
        return base
    suffix = 2
    while f"{base}_{suffix}" in used_set:
        suffix += 1
    return f"{base}_{suffix}"


def _visual_default_title(kind: str) -> str:
    return DEFAULT_VISUAL_TITLES.get(kind, kind or "plot")


def _json_safe_visual_value(kind: str, event: Mapping[str, Any]) -> Any:
    """Extract one series cell from a compile drawing event (interpret semantics)."""
    if kind == "bgcolor":
        color = event.get("color")
        if color is None:
            return None
        if isinstance(color, str):
            s = color.strip()
            return s if s else None
        # int 0xRRGGBB / objects → string when possible
        if isinstance(color, int):
            if color > 0xFFFFFF:
                r = (color >> 16) & 0xFF
                g = (color >> 8) & 0xFF
                b = color & 0xFF
                return f"#{r:02X}{g:02X}{b:02X}"
            return f"#{color & 0xFFFFFF:06X}"
        s = str(color).strip()
        return s if s else None

    # plotshape / plotchar / plotarrow — series condition / value.
    # Interpret exports True when the marker shows and None (na) when not —
    # never a hard False (avoids type/na MISMATCH vs compile materialize).
    raw = event.get("series", event.get("value"))
    if raw is None:
        return None
    if kind in ("plotshape", "plotchar"):
        if isinstance(raw, bool):
            return True if raw else None
        if isinstance(raw, (int, float)):
            try:
                fv = float(raw)
                if fv != fv:  # NaN
                    return None
                return True if fv != 0.0 else None
            except (TypeError, ValueError):
                return True if raw else None
        return True if raw else None
    # plotarrow — keep numeric delta when possible
    if isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (int, float)):
        try:
            fv = float(raw)
            return None if fv != fv else fv
        except (TypeError, ValueError):
            return None
    try:
        fv = float(raw)
        return None if fv != fv else fv
    except (TypeError, ValueError):
        return None


def materialize_visual_series_from_drawings(
    drawings: Sequence[Any] | None,
    n_bars: int,
    *,
    existing_keys: Iterable[str] | None = None,
) -> tuple[dict[str, list[Any]], dict[str, dict[str, Any]]]:
    """Lift compile ``__drawings`` bgcolor/plotshape/plotchar/plotarrow into series.

    Interpret Runtime packaging already exports these as titled series keys.
    Compile historically only appends per-bar events on ``__drawings``. This
    helper reconstructs the missing series map so both modes share keys (and
    bgcolor color / shape bool values) without harness ignore flags.

    Call-site order is taken from the first bar that emits visual events (usually
    bar 0). Titles use event ``title`` when present; otherwise kind defaults
    (``bgcolor``, ``shape``, ``char``, ``arrow``) with ``_2`` uniquify against
    *existing_keys* and earlier sites.

    Notes
    -----
    - Compile emit currently **drops** ``title=`` on bgcolor events (only color
      is stored). Titled bgcolors therefore uniquify as ``bgcolor`` /
      ``bgcolor_2`` until compiler ``_emit_drawing`` includes title (Agent 03).
    - Already-present series keys in *existing_keys* are not overwritten.
    """
    series_map: dict[str, list[Any]] = {}
    plot_meta: dict[str, dict[str, Any]] = {}
    if not drawings or n_bars <= 0:
        return series_map, plot_meta

    by_bar: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in drawings:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or item.get("type") or "")
        if kind not in _VISUAL_SERIES_KINDS:
            continue
        try:
            bar = int(item.get("bar", 0) or 0)
        except (TypeError, ValueError):
            bar = 0
        if bar < 0 or bar >= n_bars:
            # Still record for discovery if out of range? skip fill
            if 0 <= bar:
                by_bar[bar].append(item)
            continue
        by_bar[bar].append(item)

    if not by_bar:
        return series_map, plot_meta

    # Prefer bar 0 for call-site discovery; else the lowest bar index present.
    discovery_bar = 0 if 0 in by_bar else min(by_bar.keys())
    discovery = by_bar[discovery_bar]

    used: set[str] = set(existing_keys or ())
    sites: list[dict[str, Any]] = []
    for ev in discovery:
        kind = str(ev.get("kind") or "")
        raw_title = ev.get("title")
        if raw_title is None or (isinstance(raw_title, str) and raw_title.strip() == ""):
            base = _visual_default_title(kind)
        else:
            base = str(raw_title).strip() or _visual_default_title(kind)
        key = uniquify_series_title(base, used)
        used.add(key)
        meta: dict[str, Any] = {
            "title": key,
            "kind": kind,
            "index": len(sites),
            "linewidth": 1,
            "color": None,
        }
        style = ev.get("style")
        if style is not None and str(style) != "":
            meta["style"] = str(style)
        location = ev.get("location")
        if location is not None and str(location) != "":
            meta["location"] = str(location)
        char = ev.get("char")
        if char is not None and str(char) != "":
            meta["char"] = str(char)
            meta["text"] = str(char)
        color = ev.get("color")
        if color is not None and str(color).strip() != "":
            meta["color"] = str(color) if not isinstance(color, str) else color
        sites.append({"key": key, "kind": kind, "meta": meta})

    if not sites:
        return series_map, plot_meta

    for site in sites:
        series_map[site["key"]] = [None] * n_bars
        plot_meta[site["key"]] = dict(site["meta"])

    # Fill columns: zip per-bar visual events with discovered sites by position
    # when counts match; otherwise match by running kind-order index.
    for bar, events in by_bar.items():
        if bar < 0 or bar >= n_bars:
            continue
        if len(events) == len(sites):
            pairs = list(zip(sites, events, strict=True))
        else:
            # Fallback: assign in order, pad/truncate
            pairs = list(zip(sites, events))
        for site, ev in pairs:
            kind = site["kind"]
            # Prefer event kind if caller reordered (should not)
            ek = str(ev.get("kind") or kind)
            val = _json_safe_visual_value(ek, ev)
            series_map[site["key"]][bar] = val
            # Lazy first non-null color into meta
            if plot_meta[site["key"]].get("color") is None:
                c = ev.get("color")
                if c is not None and str(c).strip() != "":
                    plot_meta[site["key"]]["color"] = c if isinstance(c, str) else str(c)

    return series_map, plot_meta


def merge_visual_series_from_drawings(
    series: MutableMapping[str, list[Any]],
    drawings: Sequence[Any] | None,
    n_bars: int,
    *,
    plot_meta: MutableMapping[str, dict[str, Any]] | None = None,
) -> dict[str, list[Any]]:
    """Merge materialized visual series into *series* (no overwrite of existing keys).

    Returns the same *series* mapping for chaining. When *plot_meta* is provided,
    new keys get meta entries (existing meta keys are left untouched).
    """
    extra, meta = materialize_visual_series_from_drawings(
        drawings, n_bars, existing_keys=series.keys()
    )
    for key, col in extra.items():
        if key not in series:
            series[key] = col
            if plot_meta is not None and key not in plot_meta:
                plot_meta[key] = meta[key]
    return series  # type: ignore[return-value]


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

        Steady-state bars only setattr the provided fields (call site is fixed
        so kind/title/style defaults do not need a full ``_fill_plot`` rewrite).
        """
        if getattr(self, "_pine_bar_mode", False):
            # _plot_call_i is always an int in Runtime; avoid int() / or 0 each plot
            i = getattr(self, "_plot_call_i", 0)
            if i is None:
                i = 0
            self._plot_call_i = i + 1  # type: ignore[attr-defined]
            plots = PlotRegistry.plots
            if i < len(plots):
                p = plots[i]
                for k, v in fields.items():
                    setattr(p, k, v)
                p.deleted = False
                return p
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
