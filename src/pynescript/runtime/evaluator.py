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

"""Host-side Pine evaluator with columnar plot capture for the Runtime.

Extends :class:`~pynescript.ast.evaluator.NodeLiteralEvaluator` so
:class:`~pynescript.runtime.Runtime` can execute scripts bar-by-bar and export
plot series, shapes, and bgcolors as JSON-safe columns for AXIS.
"""

from __future__ import annotations

from typing import Any
from typing import Callable

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.runtime.series import PineSeries

_MISSING: Any = object()
# Type-identity for plot(close) / host OHLCV series (no getattr).
_PINE_SERIES_T = PineSeries


def _serialize_color(c: Any) -> str | None:
    """JSON-safe color string for plot_meta / bgcolor series values."""
    if c is None:
        return None
    # Hot path: color.* constants are already hex/rgba strings
    t = type(c)
    if t is str:
        return c if c else None
    if t is int:
        return f"#{c & 0xFFFFFF:06X}"
    to_rgba = getattr(c, "to_rgba", None)
    if callable(to_rgba):
        try:
            return str(to_rgba())
        except Exception:
            pass
    to_hex = getattr(c, "to_hex", None)
    if callable(to_hex):
        try:
            return str(to_hex())
        except Exception:
            pass
    s = str(c)
    return s if s else None


def _unwrap_scalar(value: Any) -> Any:
    """Bar-mode: PineSeries / list → current scalar for plot capture."""
    t = type(value)
    # Dominant after incremental TA: already a scalar
    if t is float or t is int or value is None or t is bool or t is str:
        return value
    if t is _PINE_SERIES_T:
        return value.current
    if t is list:
        return value[-1] if value else None
    current = getattr(value, "current", _MISSING)
    if current is not _MISSING and t is not tuple and t is not bytes:
        # PineSeries: .current is authoritative (None = na); has .history always
        if current is not None or getattr(value, "history", _MISSING) is not _MISSING:
            return current
    return value


def _plot_numeric_cell(raw: Any) -> Any:
    """JSON-safe numeric plot/hline cell (float/int/None identity; never na→0)."""
    t = type(raw)
    if t is float:
        return None if raw != raw else raw
    if t is int or raw is None:
        return raw
    return _coerce_plot_numeric(_unwrap_scalar(raw))


def _coerce_plot_numeric(value: Any) -> Any:
    """JSON-safe plot/hline cell. NaN → None; bool → 0.0/1.0; never na→0."""
    t = type(value)
    if t is float:
        return None if value != value else value
    if t is int or value is None:
        return value
    if t is bool:
        return 1.0 if value else 0.0
    if getattr(value, "__pine_import_stub__", False):
        return None
    return value


def _coerce_plot_shape(value: Any) -> Any:
    """JSON-safe plotshape/plotchar/plotarrow cell (matches host packing)."""
    if value is None:
        return None
    t = type(value)
    if t is bool:
        return value
    if t is int or t is float:
        try:
            fv = float(value)
            if fv != fv:  # NaN
                return False
            return fv != 0.0
        except (TypeError, ValueError):
            return bool(value)
    return bool(value)


def _as_plot_int(value: Any, default: int = 1) -> int:
    """Coerce plot linewidth / similar to int without crashing on list/series.

    AXIS may re-send input overrides as full series arrays (or last-run snapshots
    as lists). ``int([1, 2, 3])`` raises TypeError and aborts the bar loop —
    unwrap to the current sample first (same as ``_unwrap_scalar``).
    """
    t = type(value)
    if t is int:
        return value
    if value is None:
        return default
    if t is float:
        if value != value:  # NaN
            return default
        return int(value)
    if t is bool:
        return int(value)
    v = _unwrap_scalar(value)
    if v is None:
        return default
    # Nested list (e.g. override was [[1]]) — peel once more
    vt = type(v)
    if vt is list:
        v = v[-1] if v else None
        if v is None:
            return default
        vt = type(v)
    try:
        if vt is bool:
            return int(v)
        if vt is int:
            return v
        if vt is float:
            if v != v:  # NaN
                return default
            return int(v)
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class CustomEvaluator(NodeLiteralEvaluator):
    """
    Evaluator that captures plot commands.
    Supports optional data_feed / data_provider for request.* integration.

    Plot capture (bar mode / Runtime host):
      - Values go into columnar ``_plot_value_cols`` (one list per call-site order).
      - Meta (title/color/kind/…) is recorded once in ``_plot_meta_list``.
      - Host sets ``_plot_n_bars`` so columns are pre-sized; steady-state writes
        the current bar index (no append/resize). JSON-safe cells are stored
        at capture so packing can reuse the lists.
      - ``plot_outputs`` stays as a per-bar legacy buffer (cleared each bar) for
        any mid-bar readers; Runtime prefers columns when present.
      - ``PlotRegistry`` (super()) is optional: Runtime disables it when the
        script has no ``fill()`` so plot() need not return Plot handles.
    """

    def __init__(self, context=None, data_feed=None, data_provider=None):
        super().__init__(context, data_feed=data_feed, data_provider=data_provider)
        self.plot_outputs: list[Any] = []
        # Columnar capture (preferred by Runtime post-process)
        self._plot_value_cols: list[list[Any]] = []
        self._plot_meta_list: list[dict[str, Any]] = []
        self._plot_capture_i = 0
        self._plot_bars_done = 0
        # Host sets this to OHLCV length so columns are pre-sized (index write).
        self._plot_n_bars = 0
        # True if a stored cell still needs host ``_json_plot_value``.
        self._plot_pack_dirty = False
        # When False, skip PlotRegistry super() path (fill() needs True).
        # Default True so non-Runtime CustomEvaluator users keep registry semantics.
        self._pine_need_plot_ids = True
        # Bound super()._builtin_plot* after first fill-script registry hit.
        self._registry_handlers: dict[str, Callable[..., Any]] = {}
        # Call-site index for PlotRegistry reuse (plotting.py); host resets per bar.
        self._plot_call_i = 0
        # Sites whose meta.color is still None (dynamic first-non-null). 0 → skip.
        self._plot_color_pending = 0
        # PYNE_LIGHT_PLOTS=1: skip columnar capture + registry (corpus OK/fail only).
        self._pine_light_plots = False
        # Bar-by-bar mode: TA helpers return current scalar instead of full series
        self._pine_bar_mode = True
        # O(1)/O(period) call-site TA for sma/ema/rma/rsi (disable via PYNE_TA_INCREMENTAL=0)
        self._pine_ta_incremental = True
        # OHLCV history lists for ta helpers that read high/low/close by name
        self.current_series: dict[str, list] = {}
        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

    def _write_plot_cell(self, i: int, value: Any) -> None:
        """Write one cell at the current bar (pre-sized index, else append)."""
        t = type(value)
        if t is not float and t is not int and value is not None and t is not bool and t is not str:
            self._plot_pack_dirty = True
        col = self._plot_value_cols[i]
        bar = self._plot_bars_done
        if bar < len(col):
            col[bar] = value
        else:
            col.append(value)

    def _new_plot_column(self, value: Any) -> list[Any]:
        """Allocate a column; pre-size to ``_plot_n_bars`` when the host set it."""
        n = self._plot_n_bars
        bar = self._plot_bars_done
        if n > 0:
            col: list[Any] = [None] * n
            if 0 <= bar < n:
                col[bar] = value
            elif bar >= n:
                col.append(value)
            return col
        col = [None] * bar
        col.append(value)
        return col

    def _capture_plot(
        self,
        kind: str,
        value: Any,
        title: str | None,
        color_s: str | None,
        linewidth: int = 1,
        **extra: Any,
    ) -> None:
        """Write one plot cell for this bar into columnar buffers."""
        if self._pine_light_plots:
            return
        i = self._plot_capture_i
        self._plot_capture_i = i + 1
        cols = self._plot_value_cols
        meta = self._plot_meta_list
        if i >= len(cols):
            cols.append(self._new_plot_column(value))
            entry: dict[str, Any] = {
                "type": kind,
                "kind": kind,
                "title": title,
                "color": color_s,
                "linewidth": _as_plot_int(linewidth, 1),
            }
            for k, v in extra.items():
                if v is not None and v != "":
                    entry[k] = v
            meta.append(entry)
            return
        m = meta[i]
        if m.get("color") is None and color_s is not None:
            m["color"] = color_s
        for k, v in extra.items():
            if v is not None and v != "" and m.get(k) is None:
                m[k] = v
        self._write_plot_cell(i, value)

    def _append_plot_value(self, value: Any) -> int:
        """Steady-state: known call-site → write value only (no meta work).

        Returns the call-site index used (for optional lazy meta fill).
        """
        if self._pine_light_plots:
            return 0
        t = type(value)
        if t is not float and t is not int and value is not None and t is not bool and t is not str:
            self._plot_pack_dirty = True
        i = self._plot_capture_i
        self._plot_capture_i = i + 1
        col = self._plot_value_cols[i]
        bar = self._plot_bars_done
        if bar < len(col):
            col[bar] = value
        else:
            col.append(value)
        return i

    def finish_bar_plots(self) -> None:
        """Pad short columns for call sites not hit this bar; advance bar counter."""
        if self._pine_light_plots:
            self._plot_capture_i = 0
            self._plot_bars_done += 1
            return
        if self._plot_n_bars <= 0:
            n = self._plot_capture_i
            cols = self._plot_value_cols
            n_cols = len(cols)
            if n < n_cols:
                for j in range(n, n_cols):
                    cols[j].append(None)
        self._plot_bars_done += 1
        self._plot_capture_i = 0

    def _maybe_registry(self, method_name: str, args: list[Any], kwargs: dict[str, Any] | None) -> Any:
        """Optional PlotRegistry path for fill() handles; never abort the bar loop.

        Soft-fails expected registry/shape errors. Re-raises programming bugs
        (TypeError / AttributeError outside the super call surface) only when
        the exception is clearly not from optional registry plumbing — kept
        broad so fill()-less hosts stay resilient.
        """
        if not self._pine_need_plot_ids:
            return None
        fn = self._registry_handlers.get(method_name)
        if fn is None:
            fn = getattr(super(), method_name)
            self._registry_handlers[method_name] = fn
        try:
            return fn(args, kwargs)
        except (TypeError, AttributeError, ValueError, KeyError, IndexError):
            # Optional plot-id plumbing — soft-fail (fill still works without ids).
            return None
        except Exception:  # noqa: BLE001 — never kill plot capture for registry
            return None

    def _lazy_plot_color(self, i: int, args: list[Any], kwargs: dict[str, Any] | None) -> None:
        """Fill meta.color on the first non-null sighting (pending sites only)."""
        color = None
        if kwargs:
            color = kwargs.get("color")
            if color is None and len(args) > 2:
                color = args[2]
        elif len(args) > 2:
            color = args[2]
        if color is None:
            return
        m = self._plot_meta_list[i]
        if m.get("color") is None:
            m["color"] = _serialize_color(color)
            pending = self._plot_color_pending - 1
            self._plot_color_pending = pending if pending > 0 else 0

    def _builtin_plot(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture plot value + title/color for multi-series AXIS response."""
        if self._pine_light_plots:
            return None
        i = self._plot_capture_i
        cols = self._plot_value_cols
        # Steady-state (positional or kwargs): value write only after first register.
        if i < len(cols):
            if kwargs:
                raw = kwargs.get("series", args[0] if args else None)
            elif args:
                raw = args[0]
            else:
                return None
            t = type(raw)
            if t is float:
                value = None if raw != raw else raw
            elif t is int or raw is None:
                value = raw
            else:
                value = _coerce_plot_numeric(_unwrap_scalar(raw))
            self._plot_capture_i = i + 1
            col = cols[i]
            bar = self._plot_bars_done
            if bar < len(col):
                col[bar] = value
            else:
                col.append(value)
            if self._plot_color_pending:
                self._lazy_plot_color(i, args, kwargs)
            if self._pine_need_plot_ids:
                return self._maybe_registry("_builtin_plot", args, kwargs)
            return None

        # First sighting: record meta + allocate / fill pre-sized column.
        if kwargs:
            if not args and "series" not in kwargs:
                return None
            raw = kwargs.get("series", args[0] if args else None)
            title = kwargs.get("title", args[1] if len(args) > 1 else "")
            color = kwargs.get("color", args[2] if len(args) > 2 else None)
            style = kwargs.get("style", args[3] if len(args) > 3 else None)
            linewidth = kwargs.get("linewidth", args[5] if len(args) > 5 else 1)
            linestyle = kwargs.get("linestyle", None)
            color_s = _serialize_color(color) if color is not None else None
            title_s = str(title or "") or None
            style_s = None if style is None or style == "" else str(style)
            linestyle_s = None if linestyle is None or linestyle == "" else str(linestyle)
            if color_s is None and ("color" in kwargs or len(args) > 2):
                self._plot_color_pending += 1
            self._capture_plot(
                "plot",
                _plot_numeric_cell(raw),
                title_s,
                color_s,
                _as_plot_int(linewidth, 1),
                style=style_s,
                linestyle=linestyle_s,
            )
            return self._maybe_registry("_builtin_plot", args, kwargs) if self._pine_need_plot_ids else None

        if not args:
            return None
        n = len(args)
        title = args[1] if n > 1 else ""
        color = args[2] if n > 2 else None
        style = args[3] if n > 3 else None
        linewidth = args[5] if n > 5 else 1
        color_s = _serialize_color(color) if color is not None else None
        title_s = str(title or "") or None
        style_s = None if style is None or style == "" else str(style)
        if color_s is None and n > 2:
            self._plot_color_pending += 1
        self._capture_plot(
            "plot",
            _plot_numeric_cell(args[0]),
            title_s,
            color_s,
            _as_plot_int(linewidth, 1),
            style=style_s,
        )
        return self._maybe_registry("_builtin_plot", args, None) if self._pine_need_plot_ids else None

    def _builtin_hline(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture hline as a constant-price series for AXIS (kind=hline)."""
        if self._pine_light_plots:
            return None
        if self._plot_capture_i < len(self._plot_value_cols):
            if kwargs:
                raw = kwargs.get("price", args[0] if args else None)
            elif args:
                raw = args[0]
            else:
                return None
            self._append_plot_value(_plot_numeric_cell(raw))
            if self._pine_need_plot_ids:
                return self._maybe_registry("_builtin_hline", args, kwargs)
            return None
        if kwargs:
            if not args and "price" not in kwargs:
                return None
            price = _plot_numeric_cell(kwargs.get("price", args[0] if args else None))
            title = kwargs.get("title", args[1] if len(args) > 1 else "hline")
            color = kwargs.get("color", args[2] if len(args) > 2 else None)
            linestyle = kwargs.get("linestyle", args[3] if len(args) > 3 else "linestyle_solid")
            linewidth = kwargs.get("linewidth", args[4] if len(args) > 4 else 1)
            color_s = _serialize_color(color) if color is not None else None
            self._capture_plot(
                "hline",
                price,
                str(title or "") or "hline",
                color_s,
                _as_plot_int(linewidth, 1),
                linestyle=str(linestyle or "linestyle_solid"),
                style="hline",
            )
            return self._maybe_registry("_builtin_hline", args, kwargs) if self._pine_need_plot_ids else None

        if not args:
            return None
        price = _plot_numeric_cell(args[0])
        n = len(args)
        title = args[1] if n > 1 else "hline"
        color = args[2] if n > 2 else None
        linestyle = args[3] if n > 3 else "linestyle_solid"
        linewidth = args[4] if n > 4 else 1
        color_s = _serialize_color(color) if color is not None else None
        self._capture_plot(
            "hline",
            price,
            str(title or "") or "hline",
            color_s,
            _as_plot_int(linewidth, 1),
            linestyle=str(linestyle or "linestyle_solid"),
            style="hline",
        )
        return self._maybe_registry("_builtin_hline", args, None) if self._pine_need_plot_ids else None

    def _builtin_bgcolor(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture bgcolor per-bar color for AXIS background bands."""
        if self._pine_light_plots:
            return None
        if kwargs:
            raw = kwargs.get("color", args[0] if args else None)
        else:
            raw = args[0] if args else None
        color_s = _serialize_color(_unwrap_scalar(raw))
        if self._plot_capture_i < len(self._plot_value_cols):
            i = self._append_plot_value(color_s)
            if self._plot_color_pending and color_s is not None:
                m = self._plot_meta_list[i]
                if m.get("color") is None:
                    m["color"] = color_s
                    pending = self._plot_color_pending - 1
                    self._plot_color_pending = pending if pending > 0 else 0
            if self._pine_need_plot_ids:
                return self._maybe_registry("_builtin_bgcolor", args, kwargs)
            return None
        title = (kwargs.get("title", args[1] if len(args) > 1 else "bgcolor") if kwargs else (args[1] if len(args) > 1 else "bgcolor"))
        if color_s is None:
            self._plot_color_pending += 1
        self._capture_plot(
            "bgcolor",
            color_s,
            str(title or "") or "bgcolor",
            color_s,
        )
        return self._maybe_registry("_builtin_bgcolor", args, kwargs) if self._pine_need_plot_ids else None

    @staticmethod
    def _plot_ref_title(ref: Any) -> str | None:
        """Resolve a fill()/hline plot handle or string title for AXIS plot_meta."""
        if ref is None:
            return None
        title = getattr(ref, "title", None)
        if title is not None and str(title).strip() != "":
            return str(title)
        if type(ref) is str and ref.strip():
            return ref.strip()
        return None

    def _builtin_fill(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture ``fill(plot1, plot2, color=…)`` for AXIS band overlay.

        Meta stores ``plot1`` / ``plot2`` as series titles (from ``plot()`` handles).
        Series column holds per-bar color (string) or null when inactive.
        """
        if self._pine_light_plots:
            return None
        kwargs = kwargs or {}
        p1 = kwargs.get("plot1", args[0] if args else None)
        p2 = kwargs.get("plot2", args[1] if len(args) > 1 else None)
        color = kwargs.get("color", args[2] if len(args) > 2 else None)
        title = kwargs.get("title", args[3] if len(args) > 3 else "fill")
        # Registry first so plot() handles stay usable; soft-fail if disabled.
        reg = (
            self._maybe_registry("_builtin_fill", args, kwargs)
            if self._pine_need_plot_ids
            else None
        )
        t1 = self._plot_ref_title(p1) or self._plot_ref_title(getattr(reg, "plot1", None) if reg is not None else None)
        t2 = self._plot_ref_title(p2) or self._plot_ref_title(getattr(reg, "plot2", None) if reg is not None else None)
        # Prefer titles from registry fill object's plot refs when args were handles
        if reg is not None:
            t1 = t1 or self._plot_ref_title(getattr(reg, "plot1", None))
            t2 = t2 or self._plot_ref_title(getattr(reg, "plot2", None))
        color_s = _serialize_color(_unwrap_scalar(color)) if color is not None else None
        # Exported fill series is all-null (color lives on plot_meta).
        fill_cell = None

        if self._plot_capture_i < len(self._plot_value_cols):
            i = self._append_plot_value(fill_cell)
            m = self._plot_meta_list[i]
            if t1 and not m.get("plot1"):
                m["plot1"] = t1
            if t2 and not m.get("plot2"):
                m["plot2"] = t2
            if color_s is not None and m.get("color") is None:
                m["color"] = color_s
            return reg

        self._capture_plot(
            "fill",
            fill_cell,
            str(title or "") or "fill",
            color_s,
            style="fill",
            plot1=t1,
            plot2=t2,
        )
        return reg

    def _builtin_plotshape(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture plotshape condition + style for AXIS bar markers."""
        if self._pine_light_plots:
            return None
        if kwargs:
            if not args and "series" not in kwargs:
                return None
            value = _coerce_plot_shape(_unwrap_scalar(kwargs.get("series", args[0] if args else None)))
            if self._plot_capture_i < len(self._plot_value_cols):
                self._append_plot_value(value)
                if self._pine_need_plot_ids:
                    return self._maybe_registry("_builtin_plotshape", args, kwargs)
                return None
            title = kwargs.get("title", args[1] if len(args) > 1 else "shape")
            style = kwargs.get("style", args[2] if len(args) > 2 else "shape")
            location = kwargs.get("location", args[3] if len(args) > 3 else "")
            color = _unwrap_scalar(kwargs.get("color", args[4] if len(args) > 4 else None))
            text = kwargs.get("text", None)
            size = kwargs.get("size", None)
            # Treat missing enum constants (None) as empty, not the string "None"
            style_s = "" if style is None else str(style)
            location_s = "" if location is None else str(location)
            size_s = None if size is None or size == "" else size
            self._capture_plot(
                "plotshape",
                value,
                str(title or "") or "shape",
                _serialize_color(color) if color is not None else None,
                style=style_s,
                location=location_s,
                text=str(text) if text is not None else "",
                size=size_s,
                text_size=size_s,
            )
            return self._maybe_registry("_builtin_plotshape", args, kwargs) if self._pine_need_plot_ids else None

        if not args:
            return None
        value = _coerce_plot_shape(_unwrap_scalar(args[0]))
        if self._plot_capture_i < len(self._plot_value_cols):
            self._append_plot_value(value)
            if self._pine_need_plot_ids:
                return self._maybe_registry("_builtin_plotshape", args, None)
            return None
        n = len(args)
        title = args[1] if n > 1 else "shape"
        style = args[2] if n > 2 else "shape"
        location = args[3] if n > 3 else ""
        color = _unwrap_scalar(args[4] if n > 4 else None)
        self._capture_plot(
            "plotshape",
            value,
            str(title or "") or "shape",
            _serialize_color(color) if color is not None else None,
            style="" if style is None else str(style),
            location="" if location is None else str(location),
            text="",
        )
        return self._maybe_registry("_builtin_plotshape", args, None) if self._pine_need_plot_ids else None

    def _builtin_plotchar(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Capture plotchar condition + char for AXIS bar markers."""
        if self._pine_light_plots:
            return None
        if kwargs:
            if not args and "series" not in kwargs:
                return None
            value = _coerce_plot_shape(_unwrap_scalar(kwargs.get("series", args[0] if args else None)))
            if self._plot_capture_i < len(self._plot_value_cols):
                self._append_plot_value(value)
                if self._pine_need_plot_ids:
                    return self._maybe_registry("_builtin_plotchar", args, kwargs)
                return None
            title = kwargs.get("title", args[1] if len(args) > 1 else "char")
            char = kwargs.get("char", args[2] if len(args) > 2 else "")
            location = kwargs.get("location", args[3] if len(args) > 3 else "")
            color = _unwrap_scalar(kwargs.get("color", args[4] if len(args) > 4 else None))
            char_s = "" if char is None else str(char)
            location_s = "" if location is None else str(location)
            self._capture_plot(
                "plotchar",
                value,
                str(title or "") or "char",
                _serialize_color(color) if color is not None else None,
                style="char",
                location=location_s,
                text=char_s,
                char=char_s,
            )
            return self._maybe_registry("_builtin_plotchar", args, kwargs) if self._pine_need_plot_ids else None

        if not args:
            return None
        value = _coerce_plot_shape(_unwrap_scalar(args[0]))
        if self._plot_capture_i < len(self._plot_value_cols):
            self._append_plot_value(value)
            if self._pine_need_plot_ids:
                return self._maybe_registry("_builtin_plotchar", args, None)
            return None
        n = len(args)
        title = args[1] if n > 1 else "char"
        char = args[2] if n > 2 else ""
        location = args[3] if n > 3 else ""
        color = _unwrap_scalar(args[4] if n > 4 else None)
        char_s = "" if char is None else str(char)
        self._capture_plot(
            "plotchar",
            value,
            str(title or "") or "char",
            _serialize_color(color) if color is not None else None,
            style="char",
            location="" if location is None else str(location),
            text=char_s,
            char=char_s,
        )
        return self._maybe_registry("_builtin_plotchar", args, None) if self._pine_need_plot_ids else None

    def reset_plots(self):
        # Per-bar index reset; columns accumulate across the run.
        # Legacy plot_outputs kept empty (Runtime uses columns).
        if self.plot_outputs:
            self.plot_outputs.clear()
        self._plot_capture_i = 0

    def reset_var_declarations(self):
        """Reset var declarations set for per-run (from plan branch var support)."""
        self._var_declarations = set()

    def reset_events(self):
        """Reset per-bar events (from strategy events integration)."""
        # Events are typically drained from strategy state in the integrated flow
        if hasattr(self, "_strategy_state"):
            self._strategy_state._events = []  # type: ignore[attr-defined]
