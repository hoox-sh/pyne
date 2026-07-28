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

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


# ── export helpers (module-level: no per-call nested-def cost) ──────────────


def _export_num(v: Any) -> float | int | None:
    if v is None:
        return None
    if hasattr(v, "current"):
        v = getattr(v, "current", None)
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v != v:  # NaN
            return None
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _export_x_to_time(x: Any, xloc: str, times: list[int]) -> int | float | None:
    xv = _export_num(x)
    if xv is None:
        return None
    loc = (xloc or "bar_index").lower()
    if "time" in loc:
        return xv
    # bar_index → wall time
    idx = int(xv)
    if 0 <= idx < len(times):
        return times[idx]
    # already looks like unix seconds / ms
    if xv > 1_000_000_000:
        return xv
    return None


def _export_color(c: Any) -> str:
    if c is None:
        return "#939fff"
    if isinstance(c, str) and c:
        return c
    if isinstance(c, int):
        # 0xAARRGGBB or 0xRRGGBB
        if c > 0xFFFFFF:
            r = (c >> 16) & 0xFF
            g = (c >> 8) & 0xFF
            b = c & 0xFF
            return f"#{r:02X}{g:02X}{b:02X}"
        return f"#{c & 0xFFFFFF:06X}"
    return str(c)


def _export_extend(e: Any) -> str:
    s = str(e or "none").lower().replace("extend.", "").strip()
    if s in {"none", "left", "right", "both"}:
        return s
    return "none"


# Drawing object registries
class DrawingRegistry:
    """Global registry for drawing objects."""

    lines: ClassVar[list[Line]] = []
    boxes: ClassVar[list[Box]] = []
    labels: ClassVar[list[Label]] = []
    tables: ClassVar[list[Table]] = []
    polylines: ClassVar[list[Polyline]] = []
    linefills: ClassVar[list[LineFill]] = []

    @classmethod
    def reset(cls) -> None:
        """Reset all registries for testing / start of a run."""
        cls.lines = []
        cls.boxes = []
        cls.labels = []
        cls.tables = []
        cls.polylines = []
        cls.linefills = []
        # Also reset plot real effects
        from .plotting import PlotRegistry
        PlotRegistry.reset()

    @classmethod
    def is_empty(cls) -> bool:
        """True when no drawing objects exist (O(1) list-length checks).

        Used by Runtime to skip ``export_for_api`` and bar_times materialization.
        """
        # truthiness of a list is len != 0 — no iteration
        return not (
            cls.lines or cls.boxes or cls.labels or cls.tables or cls.polylines or cls.linefills
        )

    @classmethod
    def export_for_api(cls, bar_times: list[int] | None = None) -> list[dict[str, Any]]:
        """Serialize active drawing objects for the Pro API / AXIS chart.

        ``bar_times`` maps ``xloc=bar_index`` coordinates to unix seconds.

        Fast path: empty registry returns ``[]`` without allocating helpers or
        walking collections (most indicator scripts never draw).
        """
        # Exportable collections only (linefills are not serialized today)
        if not (cls.lines or cls.boxes or cls.labels or cls.tables or cls.polylines):
            return []

        out: list[dict[str, Any]] = []
        times = bar_times if bar_times is not None else []
        _num = _export_num
        _x_to_time = _export_x_to_time
        _color = _export_color
        _extend = _export_extend

        for ln in cls.lines:
            if getattr(ln, "deleted", False):
                continue
            xloc = str(getattr(ln, "xloc", "bar_index") or "bar_index")
            # Guard mis-merged kwargs (color hex landed in xloc)
            if xloc.startswith("#") or xloc.startswith("rgb"):
                xloc = "bar_index"
            t1 = _x_to_time(ln.x1, xloc, times)
            t2 = _x_to_time(ln.x2, xloc, times)
            y1 = _num(ln.y1)
            y2 = _num(ln.y2)
            if t1 is None or t2 is None or y1 is None or y2 is None:
                continue
            out.append(
                {
                    "type": "line",
                    "t1": t1,
                    "p1": y1,
                    "t2": t2,
                    "p2": y2,
                    "color": _color(ln.color),
                    "width": int(_num(ln.width) or 1),
                    "style": str(ln.style or "solid"),
                    "extend": _extend(ln.extend),
                }
            )

        for bx in cls.boxes:
            if getattr(bx, "deleted", False):
                continue
            xloc = str(getattr(bx, "xloc", "bar_index") or "bar_index")
            if xloc.startswith("#") or xloc.startswith("rgb"):
                xloc = "bar_index"
            t1 = _x_to_time(bx.left, xloc, times)
            t2 = _x_to_time(bx.right, xloc, times)
            top = _num(bx.top)
            bottom = _num(bx.bottom)
            if t1 is None or t2 is None or top is None or bottom is None:
                continue
            out.append(
                {
                    "type": "box",
                    "t1": t1,
                    "p1": top,
                    "t2": t2,
                    "p2": bottom,
                    "color": _color(bx.border_color),
                    "bgcolor": _color(bx.bgcolor) if bx.bgcolor else "rgba(0,0,0,0)",
                    "width": int(_num(bx.border_width) or 1),
                    "text": str(bx.text or ""),
                }
            )

        for lb in cls.labels:
            if getattr(lb, "deleted", False):
                continue
            xloc = str(getattr(lb, "xloc", "bar_index") or "bar_index")
            if xloc.startswith("#") or xloc.startswith("rgb"):
                xloc = "bar_index"
            t = _x_to_time(lb.x, xloc, times)
            y = _num(lb.y)
            if t is None or y is None:
                continue
            out.append(
                {
                    "type": "label",
                    "t1": t,
                    "p1": y,
                    "text": str(lb.text or ""),
                    "color": _color(lb.color),
                    "textcolor": _color(lb.textcolor),
                    "style": str(lb.style or "label_center"),
                }
            )

        for pl in cls.polylines:
            if getattr(pl, "deleted", False):
                continue
            xloc = str(getattr(pl, "xloc", "bar_index") or "bar_index")
            pts_out: list[dict[str, float | int]] = []
            for pt in getattr(pl, "points", None) or []:
                # ChartPoint: time / index / price
                price = _num(getattr(pt, "price", None))
                if price is None:
                    continue
                if getattr(pt, "time", None) is not None:
                    t = _num(pt.time)
                elif getattr(pt, "index", None) is not None:
                    t = _x_to_time(pt.index, xloc, times)
                else:
                    t = None
                if t is None:
                    continue
                pts_out.append({"time": t, "price": price})
            if len(pts_out) < 2:
                continue
            out.append(
                {
                    "type": "polyline",
                    "points": pts_out,
                    "closed": bool(getattr(pl, "closed", False)),
                    "color": _color(pl.color),
                    "width": int(_num(pl.width) or 1),
                    "style": str(pl.style or "solid"),
                    "t1": pts_out[0]["time"],
                    "p1": pts_out[0]["price"],
                    "t2": pts_out[-1]["time"],
                    "p2": pts_out[-1]["price"],
                }
            )

        # Tables are UI overlays (not price-scale geometry) — emit metadata only
        for tb in cls.tables:
            if getattr(tb, "deleted", False):
                continue
            cells: list[dict[str, Any]] = []
            for (row, col), cell in (getattr(tb, "cells", None) or {}).items():
                cells.append(
                    {
                        "row": row,
                        "col": col,
                        "text": str(getattr(cell, "text", "") or ""),
                        "text_color": _color(getattr(cell, "text_color", "#eceef4")),
                        "bgcolor": _color(getattr(cell, "bgcolor", "transparent")),
                    }
                )
            pos = str(getattr(tb, "position", "top_right") or "top_right")
            pos = pos.replace("position.", "")
            out.append(
                {
                    "type": "table",
                    "position": pos,
                    "rows": int(getattr(tb, "rows", 0) or 0),
                    "columns": int(getattr(tb, "columns", 0) or 0),
                    "cells": cells,
                    "frame_color": _color(getattr(tb, "frame_color", "#3a3d4a")),
                    "bgcolor": _color(getattr(tb, "bgcolor", "rgba(17,18,24,0.92)")),
                    "t1": 0,
                    "p1": 0,
                    "color": _color(getattr(tb, "frame_color", "#939fff")),
                }
            )

        return out


@dataclass
class Line:
    """Line drawing object."""

    x1: int | float
    y1: float
    x2: int | float
    y2: float
    xloc: str = "bar_index"  # "bar_index" or "time"
    color: str = "#000000"
    width: int = 1
    style: str = "solid"  # "solid", "dashed", "dotted"
    extend: str = "none"  # "none", "left", "right", "both"
    force_overlay: bool = False  # v6
    deleted: bool = False


@dataclass
class Box:
    """Box drawing object."""

    left: int | float
    top: float
    right: int | float
    bottom: float
    xloc: str = "bar_index"
    closed: bool = True
    bgcolor: str = "rgba(0,0,0,0)"
    border_color: str = "#000000"
    border_width: int = 1
    border_style: str = "solid"
    extend: str = "none"
    text: str = ""
    text_color: str = "#000000"
    text_font_family: str = "default"
    text_halign: str = "center"
    text_valign: str = "center"
    text_size: int | str = "auto"
    text_formatting: str = ""
    text_wrap: str = "none"
    force_overlay: bool = False  # v6
    deleted: bool = False


@dataclass
class Label:
    """Label drawing object."""

    x: int | float
    y: float
    text: str = ""
    xloc: str = "bar_index"
    yloc: str = "price"
    color: str = "#000000"
    textcolor: str = "#000000"
    text_font_family: str = "default"
    text_halign: str = "center"
    text_valign: str = "center"
    text_size: int | str = "auto"  # v6: supports int (points) or size.* consts
    text_formatting: str = ""  # v6: "", "bold", "italic", or combination like "bold italic"
    size: int | str = "auto"  # alias of text_size for label.set_size
    tooltip: str = ""
    style: str = "label_center"
    border_color: str = "rgba(0,0,0,0)"
    border_width: int = 0
    border_style: str = "solid"
    force_overlay: bool = False  # v6
    deleted: bool = False


@dataclass
class Table:
    """Table drawing object."""

    position: str = "top_left"  # Position on screen
    rows: int = 0
    columns: int = 0
    frame_color: str = "#000000"
    frame_width: int = 1
    border_color: str = "#000000"
    border_width: int = 1
    bgcolor: str = "rgba(255,255,255,255)"
    force_overlay: bool = False  # v6
    cells: dict[tuple[int, int], TableCell] = field(default_factory=dict)
    deleted: bool = False


@dataclass
class TableCell:
    """Table cell content."""

    text: str = ""
    text_color: str = "#000000"
    bgcolor: str = "rgba(255,255,255,255)"
    border_color: str = "#000000"
    border_width: int = 1
    width: int | float | None = None
    height: int | float | None = None
    text_halign: str = "left"
    text_valign: str = "top"
    text_size: int | str = "auto"
    text_font_family: str = "default"
    text_formatting: str = ""
    tooltip: str = ""


@dataclass
class LineFill:
    """Fill between two lines."""

    line1: Line | None = None
    line2: Line | None = None
    color: str = "rgba(0,0,0,0)"
    deleted: bool = False


@dataclass
class ChartPoint:
    """Represents a point on the chart."""

    time: int | float | None = None
    index: int | None = None
    price: float = 0.0

    def copy(self) -> ChartPoint:
        """Create a copy of the chart point."""
        return ChartPoint(self.time, self.index, self.price)


@dataclass
class Polyline:
    """Polyline drawing object."""

    points: list[ChartPoint] = field(default_factory=list)
    closed: bool = False
    xloc: str = "bar_index"
    color: str = "#000000"
    width: int = 1
    style: str = "solid"
    force_overlay: bool = False  # v6
    deleted: bool = False


class DrawingBuiltinsMixin(BuiltinDispatchMixin):
    """Drawing functions for line, box, label, and table annotations."""

    def _drawing_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            # Line functions
            # Bare type cast: line(na) / line(id) — identity cast used in TV scripts
            "line": self._handle_type_cast,
            "box": self._handle_type_cast,
            "label": self._handle_type_cast,
            "table": self._handle_type_cast,
            "line.new": self._handle_line_new,
            "line.delete": self._handle_line_delete,
            "line.copy": self._handle_line_copy,
            "line.set_x1": self._handle_line_set_x1,
            "line.set_y1": self._handle_line_set_y1,
            "line.set_x2": self._handle_line_set_x2,
            "line.set_y2": self._handle_line_set_y2,
            "line.set_extend": self._handle_line_set_extend,
            "line.set_xloc": self._handle_line_set_xloc,
            "line.set_color": self._handle_line_set_color,
            "line.set_width": self._handle_line_set_width,
            "line.set_style": self._handle_line_set_style,
            "line.get_x1": self._handle_line_get_x1,
            "line.get_y1": self._handle_line_get_y1,
            "line.get_x2": self._handle_line_get_x2,
            "line.get_y2": self._handle_line_get_y2,
            "line.get_price": self._handle_line_get_price,
            "line.set_xy1": self._handle_line_set_xy1,
            "line.set_xy2": self._handle_line_set_xy2,
            "line.set_first_point": self._handle_line_set_first_point,
            "line.set_second_point": self._handle_line_set_second_point,
            # Box functions
            "box.new": self._handle_box_new,
            "box.delete": self._handle_box_delete,
            "box.copy": self._handle_box_copy,
            "box.set_left": self._handle_box_set_left,
            "box.set_right": self._handle_box_set_right,
            "box.set_top": self._handle_box_set_top,
            "box.set_bottom": self._handle_box_set_bottom,
            "box.set_bgcolor": self._handle_box_set_bgcolor,
            "box.set_border_color": self._handle_box_set_border_color,
            "box.set_border_width": self._handle_box_set_border_width,
            "box.set_border_style": self._handle_box_set_border_style,
            "box.set_extend": self._handle_box_set_extend,
            "box.set_xloc": self._handle_box_set_xloc,
            "box.set_closed": self._handle_box_set_closed,
            "box.set_lefttop": self._handle_box_set_lefttop,
            "box.set_rightbottom": self._handle_box_set_rightbottom,
            "box.set_top_left_point": self._handle_box_set_top_left_point,
            "box.set_bottom_right_point": self._handle_box_set_bottom_right_point,
            "box.set_text": self._handle_box_set_text,
            "box.set_text_color": self._handle_box_set_text_color,
            "box.set_text_font_family": self._handle_box_set_text_font_family,
            "box.set_text_halign": self._handle_box_set_text_halign,
            "box.set_text_valign": self._handle_box_set_text_valign,
            "box.set_text_size": self._handle_box_set_text_size,
            "box.set_text_formatting": self._handle_box_set_text_formatting,
            "box.set_text_wrap": self._handle_box_set_text_wrap,
            "box.get_left": self._handle_box_get_left,
            "box.get_right": self._handle_box_get_right,
            "box.get_top": self._handle_box_get_top,
            "box.get_bottom": self._handle_box_get_bottom,
            # Label functions
            "label.new": self._handle_label_new,
            "label.delete": self._handle_label_delete,
            "label.copy": self._handle_label_copy,
            "label.set_xy": self._handle_label_set_xy,
            "label.set_x": self._handle_label_set_x,
            "label.set_y": self._handle_label_set_y,
            "label.set_text": self._handle_label_set_text,
            "label.set_textcolor": self._handle_label_set_textcolor,
            "label.set_textalign": self._handle_label_set_textalign,
            "label.set_text_font_family": self._handle_label_set_text_font_family,
            "label.set_text_halign": self._handle_label_set_text_halign,
            "label.set_text_valign": self._handle_label_set_text_valign,
            "label.set_text_size": self._handle_label_set_text_size,
            "label.set_size": self._handle_label_set_size,
            "label.set_text_formatting": self._handle_label_set_text_formatting,
            "label.set_tooltip": self._handle_label_set_tooltip,
            "label.set_color": self._handle_label_set_color,
            "label.set_border_color": self._handle_label_set_border_color,
            "label.set_border_width": self._handle_label_set_border_width,
            "label.set_border_style": self._handle_label_set_border_style,
            "label.set_style": self._handle_label_set_style,
            "label.set_xloc": self._handle_label_set_xloc,
            "label.set_yloc": self._handle_label_set_yloc,
            "label.set_point": self._handle_label_set_point,
            "label.get_x": self._handle_label_get_x,
            "label.get_y": self._handle_label_get_y,
            "label.get_text": self._handle_label_get_text,
            # Table functions
            "table.new": self._handle_table_new,
            "table.delete": self._handle_table_delete,
            "table.cell": self._handle_table_cell,
            "table.cell_set_text": self._handle_table_cell_set_text,
            "table.cell_set_text_color": self._handle_table_cell_set_text_color,
            "table.cell_set_bgcolor": self._handle_table_cell_set_bgcolor,
            "table.cell_set_border_color": self._handle_table_cell_set_border_color,
            "table.cell_set_border_width": self._handle_table_cell_set_border_width,
            "table.cell_set_width": self._handle_table_cell_set_width,
            "table.cell_set_height": self._handle_table_cell_set_height,
            "table.cell_set_text_halign": self._handle_table_cell_set_text_halign,
            "table.cell_set_text_valign": self._handle_table_cell_set_text_valign,
            "table.cell_set_text_size": self._handle_table_cell_set_text_size,
            "table.cell_set_text_font_family": self._handle_table_cell_set_text_font_family,
            "table.cell_set_text_formatting": self._handle_table_cell_set_text_formatting,
            "table.cell_set_tooltip": self._handle_table_cell_set_tooltip,
            "table.cell_get_text": self._handle_table_cell_get_text,
            "table.clear": self._handle_table_clear,
            "table.merge_cells": self._handle_table_merge_cells,
            "table.set_position": self._handle_table_set_position,
            "table.set_bgcolor": self._handle_table_set_bgcolor,
            "table.set_border_color": self._handle_table_set_border_color,
            "table.set_border_width": self._handle_table_set_border_width,
            "table.set_frame_color": self._handle_table_set_frame_color,
            "table.set_frame_width": self._handle_table_set_frame_width,
            # Linefill
            "linefill.new": self._handle_linefill_new,
            "linefill.delete": self._handle_linefill_delete,
            "linefill.set_color": self._handle_linefill_set_color,
            "linefill.get_line1": self._handle_linefill_get_line1,
            "linefill.get_line2": self._handle_linefill_get_line2,
            # Chart point functions
            "chart.point.new": self._handle_chart_point_new,
            "chart.point.from_index": self._handle_chart_point_from_index,
            "chart.point.from_time": self._handle_chart_point_from_time,
            "chart.point.now": self._handle_chart_point_now,
            "chart.point.copy": self._handle_chart_point_copy,
            # Polyline functions
            "polyline.new": self._handle_polyline_new,
            "polyline.delete": self._handle_polyline_delete,
            # Collection accessors (array of non-deleted objects)
            "line.all": self._handle_line_all,
            "box.all": self._handle_box_all,
            "label.all": self._handle_label_all,
            "table.all": self._handle_table_all,
            "polyline.all": self._handle_polyline_all,
            "linefill.all": self._handle_linefill_all,
        }

    @staticmethod
    def _active(items: list[Any]) -> list[Any]:
        return [obj for obj in items if not getattr(obj, "deleted", False)]

    def _handle_line_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> list[Any]:
        return self._active(DrawingRegistry.lines)

    def _handle_box_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> list[Any]:
        return self._active(DrawingRegistry.boxes)

    def _handle_label_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> list[Any]:
        return self._active(DrawingRegistry.labels)

    def _handle_table_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> list[Any]:
        return self._active(DrawingRegistry.tables)

    def _handle_polyline_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> list[Any]:
        return self._active(DrawingRegistry.polylines)

    def _handle_linefill_all(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> list[Any]:
        return self._active(DrawingRegistry.linefills)

    def _handle_type_cast(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """Identity cast for drawing types: ``line(na)``, ``label(x)``, etc."""
        return args[0] if args else None

    # LINE HANDLERS

    def _handle_line_new(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Line:
        """line.new(x1, y1, x2, y2, xloc=..., color=..., width=..., style=..., extend=...)."""
        kw = kwargs or {}
        x1 = kw.get("x1", args[0] if len(args) > 0 else 0)
        y1 = kw.get("y1", args[1] if len(args) > 1 else 0.0)
        x2 = kw.get("x2", args[2] if len(args) > 2 else 0)
        y2 = kw.get("y2", args[3] if len(args) > 3 else 0.0)
        xloc = kw.get("xloc", args[4] if len(args) > 4 else "bar_index")
        # Pine often passes color as first keyword after positionals
        color = kw.get("color", args[5] if len(args) > 5 else "#000000")
        width = kw.get("width", args[6] if len(args) > 6 else 1)
        style = kw.get("style", args[7] if len(args) > 7 else "solid")
        extend = kw.get("extend", args[8] if len(args) > 8 else "none")
        force_overlay = kw.get("force_overlay", args[9] if len(args) > 9 else False)
        # Defensive: color hex accidentally in xloc from old merge path
        if isinstance(xloc, str) and (xloc.startswith("#") or xloc.startswith("rgb")):
            color = xloc
            xloc = "bar_index"

        line = Line(x1, y1, x2, y2, str(xloc), color, width, style, extend, force_overlay=bool(force_overlay))
        DrawingRegistry.lines.append(line)
        return line

    def _handle_line_delete(self, args: list[Any]) -> None:
        """line.delete(line)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.deleted = True

    def _handle_line_copy(self, args: list[Any]) -> Line:
        """line.copy(line) - Returns a new line with same properties"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            new_line = Line(
                line.x1, line.y1, line.x2, line.y2, line.xloc, line.color, line.width, line.style, line.extend
            )
            DrawingRegistry.lines.append(new_line)
            return new_line
        return Line(0, 0.0, 0, 0.0)

    def _handle_line_set_x1(self, args: list[Any]) -> Line:
        """line.set_x1(line, x1)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.x1 = args[1] if len(args) > 1 else line.x1
        return line

    def _handle_line_set_y1(self, args: list[Any]) -> Line:
        """line.set_y1(line, y1)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.y1 = args[1] if len(args) > 1 else line.y1
        return line

    def _handle_line_set_x2(self, args: list[Any]) -> Line:
        """line.set_x2(line, x2)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.x2 = args[1] if len(args) > 1 else line.x2
        return line

    def _handle_line_set_y2(self, args: list[Any]) -> Line:
        """line.set_y2(line, y2)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.y2 = args[1] if len(args) > 1 else line.y2
        return line

    def _handle_line_set_extend(self, args: list[Any]) -> Line:
        """line.set_extend(line, extend)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.extend = args[1] if len(args) > 1 else line.extend
        return line

    def _handle_line_set_xloc(self, args: list[Any]) -> Line:
        """line.set_xloc(line, xloc)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.xloc = args[1] if len(args) > 1 else line.xloc
        return line

    def _handle_line_set_color(self, args: list[Any]) -> Line:
        """line.set_color(line, color)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.color = args[1] if len(args) > 1 else line.color
        return line

    def _handle_line_set_width(self, args: list[Any]) -> Line:
        """line.set_width(line, width)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.width = args[1] if len(args) > 1 else line.width
        return line

    def _handle_line_set_style(self, args: list[Any]) -> Line:
        """line.set_style(line, style)"""
        line = args[0] if len(args) > 0 else None
        if isinstance(line, Line):
            line.style = args[1] if len(args) > 1 else line.style
        return line

    def _handle_line_get_x1(self, args: list[Any]) -> int | float:
        """line.get_x1(line)"""
        line = args[0] if len(args) > 0 else None
        return line.x1 if isinstance(line, Line) else 0

    def _handle_line_get_y1(self, args: list[Any]) -> float:
        """line.get_y1(line)"""
        line = args[0] if len(args) > 0 else None
        return line.y1 if isinstance(line, Line) else 0.0

    def _handle_line_get_x2(self, args: list[Any]) -> int | float:
        """line.get_x2(line)"""
        line = args[0] if len(args) > 0 else None
        return line.x2 if isinstance(line, Line) else 0

    def _handle_line_get_y2(self, args: list[Any]) -> float:
        """line.get_y2(line)"""
        line = args[0] if len(args) > 0 else None
        return line.y2 if isinstance(line, Line) else 0.0

    # BOX HANDLERS

    def _handle_box_new(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Box:
        """box.new(left, top, right, bottom, xloc=..., bgcolor=..., border_color=..., ...)."""
        kw = kwargs or {}
        left = kw.get("left", args[0] if len(args) > 0 else 0)
        top = kw.get("top", args[1] if len(args) > 1 else 0.0)
        right = kw.get("right", args[2] if len(args) > 2 else 0)
        bottom = kw.get("bottom", args[3] if len(args) > 3 else 0.0)
        xloc = kw.get("xloc", args[4] if len(args) > 4 else "bar_index")
        closed = kw.get("closed", args[5] if len(args) > 5 else True)
        bgcolor = kw.get("bgcolor", args[6] if len(args) > 6 else "rgba(0,0,0,0)")
        border_color = kw.get(
            "border_color",
            args[7] if len(args) > 7 else "#000000",
        )
        border_width = kw.get("border_width", args[8] if len(args) > 8 else 1)
        border_style = kw.get("border_style", args[9] if len(args) > 9 else "solid")
        extend = kw.get("extend", args[10] if len(args) > 10 else "none")
        force_overlay = kw.get("force_overlay", args[11] if len(args) > 11 else False)
        text = kw.get("text", "")
        text_color = kw.get("text_color", "#000000")

        box = Box(
            left,
            top,
            right,
            bottom,
            str(xloc),
            bool(closed),
            bgcolor,
            border_color,
            border_width,
            border_style,
            extend,
            text=str(text) if text is not None else "",
            text_color=str(text_color) if text_color is not None else "#000000",
            force_overlay=bool(force_overlay),
        )
        DrawingRegistry.boxes.append(box)
        return box

    def _handle_box_delete(self, args: list[Any]) -> None:
        """box.delete(box)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.deleted = True

    def _handle_box_copy(self, args: list[Any]) -> Box:
        """box.copy(box)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            new_box = Box(
                box.left,
                box.top,
                box.right,
                box.bottom,
                box.xloc,
                box.closed,
                box.bgcolor,
                box.border_color,
                box.border_width,
                box.border_style,
                box.extend,
            )
            DrawingRegistry.boxes.append(new_box)
            return new_box
        return Box(0, 0.0, 0, 0.0)

    def _handle_box_set_left(self, args: list[Any]) -> Box:
        """box.set_left(box, left)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.left = args[1] if len(args) > 1 else box.left
        return box

    def _handle_box_set_right(self, args: list[Any]) -> Box:
        """box.set_right(box, right)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.right = args[1] if len(args) > 1 else box.right
        return box

    def _handle_box_set_top(self, args: list[Any]) -> Box:
        """box.set_top(box, top)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.top = args[1] if len(args) > 1 else box.top
        return box

    def _handle_box_set_bottom(self, args: list[Any]) -> Box:
        """box.set_bottom(box, bottom)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.bottom = args[1] if len(args) > 1 else box.bottom
        return box

    def _handle_box_set_bgcolor(self, args: list[Any]) -> Box:
        """box.set_bgcolor(box, color)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.bgcolor = args[1] if len(args) > 1 else box.bgcolor
        return box

    def _handle_box_set_border_color(self, args: list[Any]) -> Box:
        """box.set_border_color(box, color)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.border_color = args[1] if len(args) > 1 else box.border_color
        return box

    def _handle_box_set_border_width(self, args: list[Any]) -> Box:
        """box.set_border_width(box, width)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.border_width = args[1] if len(args) > 1 else box.border_width
        return box

    def _handle_box_set_border_style(self, args: list[Any]) -> Box:
        """box.set_border_style(box, style)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.border_style = args[1] if len(args) > 1 else box.border_style
        return box

    def _handle_box_set_extend(self, args: list[Any]) -> Box:
        """box.set_extend(box, extend)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.extend = args[1] if len(args) > 1 else box.extend
        return box

    def _handle_box_set_xloc(self, args: list[Any]) -> Box:
        """box.set_xloc(box, left, right, xloc)

        Set the left and right coordinates of the box borders.
        Added March 2025: Full parameter support for left, right, and xloc.

        Parameters:
            box: The box object to modify
            left: Left coordinate (bar index or timestamp based on xloc)
            right: Right coordinate (bar index or timestamp based on xloc)
            xloc: Coordinate type ("bar_index" or "time")

        Returns the modified box.
        """
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            if len(args) > 1:
                box.left = args[1]
            if len(args) > 2:
                box.right = args[2]
            if len(args) > 3:
                box.xloc = args[3]
        return box

    def _handle_box_set_closed(self, args: list[Any]) -> Box:
        """box.set_closed(box, closed)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.closed = args[1] if len(args) > 1 else box.closed
        return box

    def _handle_box_get_left(self, args: list[Any]) -> int | float:
        """box.get_left(box)"""
        box = args[0] if len(args) > 0 else None
        return box.left if isinstance(box, Box) else 0

    def _handle_box_get_right(self, args: list[Any]) -> int | float:
        """box.get_right(box)"""
        box = args[0] if len(args) > 0 else None
        return box.right if isinstance(box, Box) else 0

    def _handle_box_get_top(self, args: list[Any]) -> float:
        """box.get_top(box)"""
        box = args[0] if len(args) > 0 else None
        return box.top if isinstance(box, Box) else 0.0

    def _handle_box_get_bottom(self, args: list[Any]) -> float:
        """box.get_bottom(box)"""
        box = args[0] if len(args) > 0 else None
        return box.bottom if isinstance(box, Box) else 0.0

    # LABEL HANDLERS

    def _handle_label_new(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Label:
        """label.new(x, y, text, ...) or label.new(point, text, ...).

        Pine v5+ accepts ``label.new(point = chart.point.now(), ...)`` where
        *point* supplies both coordinates. Without expanding ChartPoint here,
        ``label.x`` stored the object and ``get_x()`` returned it — Console's
        ``chart.point.tostring()`` (label.new → get_x → x.tostring) then
        recursed forever.
        """
        kwargs = kwargs or {}

        def _coord_from_point(point: ChartPoint) -> tuple[int | float, float]:
            x_val: int | float
            if point.index is not None:
                x_val = point.index
            elif point.time is not None:
                x_val = point.time
            else:
                x_val = 0
            return x_val, float(point.price)

        point = kwargs.get("point")
        if point is None and args and isinstance(args[0], ChartPoint):
            # Positional point form: label.new(point, text, xloc, yloc, color, style, ...)
            point = args[0]
            x, y = _coord_from_point(point)
            text = kwargs.get("text", args[1] if len(args) > 1 else "")
            xloc = kwargs.get("xloc", args[2] if len(args) > 2 else "bar_index")
            yloc = kwargs.get("yloc", args[3] if len(args) > 3 else "price")
            color = kwargs.get("color", args[4] if len(args) > 4 else "#000000")
            # style comes before textcolor in the point overload
            style = kwargs.get("style", args[5] if len(args) > 5 else "label_center")
            textcolor = kwargs.get("textcolor", args[6] if len(args) > 6 else "#000000")
            text_size = kwargs.get("size", kwargs.get("text_size", args[7] if len(args) > 7 else "auto"))
            text_halign = kwargs.get("textalign", kwargs.get("text_halign", args[8] if len(args) > 8 else "center"))
            tooltip = kwargs.get("tooltip", args[9] if len(args) > 9 else "")
            force_overlay = kwargs.get("force_overlay", args[10] if len(args) > 10 else False)
            text_font_family = kwargs.get("text_font_family", args[11] if len(args) > 11 else "default")
            text_valign = kwargs.get("text_valign", "center")
            text_formatting = kwargs.get("text_formatting", "")
        elif isinstance(point, ChartPoint):
            # Keyword point form: label.new(point=..., text=..., ...)
            x, y = _coord_from_point(point)
            text = kwargs.get("text", args[0] if len(args) > 0 else "")
            xloc = kwargs.get("xloc", "bar_index")
            yloc = kwargs.get("yloc", "price")
            color = kwargs.get("color", "#000000")
            textcolor = kwargs.get("textcolor", "#000000")
            text_font_family = kwargs.get("text_font_family", "default")
            text_halign = kwargs.get("textalign", kwargs.get("text_halign", "center"))
            text_valign = kwargs.get("text_valign", "center")
            text_size = kwargs.get("size", kwargs.get("text_size", "auto"))
            text_formatting = kwargs.get("text_formatting", "")
            tooltip = kwargs.get("tooltip", "")
            style = kwargs.get("style", "label_center")
            force_overlay = kwargs.get("force_overlay", False)
        else:
            # Classic label.new(x, y, text, xloc, yloc, color, textcolor, ...)
            x = kwargs.get("x", args[0] if len(args) > 0 else 0)
            y = kwargs.get("y", args[1] if len(args) > 1 else 0.0)
            text = kwargs.get("text", args[2] if len(args) > 2 else "")
            xloc = kwargs.get("xloc", args[3] if len(args) > 3 else "bar_index")
            yloc = kwargs.get("yloc", args[4] if len(args) > 4 else "price")
            color = kwargs.get("color", args[5] if len(args) > 5 else "#000000")
            textcolor = kwargs.get("textcolor", args[6] if len(args) > 6 else "#000000")
            text_font_family = kwargs.get("text_font_family", args[7] if len(args) > 7 else "default")
            text_halign = kwargs.get("text_halign", args[8] if len(args) > 8 else "center")
            text_valign = kwargs.get("text_valign", args[9] if len(args) > 9 else "center")
            text_size = kwargs.get("text_size", kwargs.get("size", args[10] if len(args) > 10 else "auto"))
            text_formatting = kwargs.get("text_formatting", args[11] if len(args) > 11 else "")
            tooltip = kwargs.get("tooltip", args[12] if len(args) > 12 else "")
            style = kwargs.get("style", args[13] if len(args) > 13 else "label_center")
            force_overlay = kwargs.get("force_overlay", args[14] if len(args) > 14 else False)
            # Defensive: x accidentally a ChartPoint (legacy merge path)
            if isinstance(x, ChartPoint):
                x, y = _coord_from_point(x)

        label = Label(
            x,
            y,
            text,
            xloc,
            yloc,
            color,
            textcolor,
            text_font_family,
            text_halign,
            text_valign,
            text_size,
            text_formatting,
            tooltip,
            style,
            force_overlay=force_overlay,
        )
        DrawingRegistry.labels.append(label)
        return label

    def _handle_label_delete(self, args: list[Any]) -> None:
        """label.delete(label)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.deleted = True

    def _handle_label_copy(self, args: list[Any]) -> Label:
        """label.copy(label)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            new_label = Label(
                label.x,
                label.y,
                label.text,
                label.xloc,
                label.yloc,
                label.color,
                label.textcolor,
                label.text_font_family,
                label.text_halign,
                label.text_valign,
                label.text_size,
                label.text_formatting,
                label.tooltip,
                label.style,
                force_overlay=label.force_overlay,
            )
            DrawingRegistry.labels.append(new_label)
            return new_label
        return Label(0, 0.0)

    def _handle_label_set_xy(self, args: list[Any]) -> Label:
        """label.set_xy(label, x, y)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.x = args[1] if len(args) > 1 else label.x
            label.y = args[2] if len(args) > 2 else label.y
        return label

    def _handle_label_set_x(self, args: list[Any]) -> Label:
        """label.set_x(label, x)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.x = args[1] if len(args) > 1 else label.x
        return label

    def _handle_label_set_y(self, args: list[Any]) -> Label:
        """label.set_y(label, y)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.y = args[1] if len(args) > 1 else label.y
        return label

    def _handle_label_set_text(self, args: list[Any]) -> Label:
        """label.set_text(label, text)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.text = args[1] if len(args) > 1 else label.text
        return label

    def _handle_label_set_textcolor(self, args: list[Any]) -> Label:
        """label.set_textcolor(label, color)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.textcolor = args[1] if len(args) > 1 else label.textcolor
        return label

    def _handle_label_set_text_font_family(self, args: list[Any]) -> Label:
        """label.set_text_font_family(label, font_family)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.text_font_family = args[1] if len(args) > 1 else label.text_font_family
        return label

    def _handle_label_set_text_halign(self, args: list[Any]) -> Label:
        """label.set_text_halign(label, halign)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.text_halign = args[1] if len(args) > 1 else label.text_halign
        return label

    def _handle_label_set_text_valign(self, args: list[Any]) -> Label:
        """label.set_text_valign(label, valign)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.text_valign = args[1] if len(args) > 1 else label.text_valign
        return label

    def _handle_label_set_text_size(self, args: list[Any]) -> Label:
        """label.set_text_size(label, size)  # v6 int (points) or const supported"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            new_size = args[1] if len(args) > 1 else label.text_size
            label.text_size = new_size
        return label

    def _handle_label_set_text_formatting(self, args: list[Any]) -> Label:
        """label.set_text_formatting(label, formatting)  # v6"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.text_formatting = args[1] if len(args) > 1 else label.text_formatting
        return label

    def _handle_label_set_tooltip(self, args: list[Any]) -> Label:
        """label.set_tooltip(label, tooltip)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.tooltip = args[1] if len(args) > 1 else label.tooltip
        return label

    def _handle_label_set_color(self, args: list[Any]) -> Label:
        """label.set_color(label, color)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.color = args[1] if len(args) > 1 else label.color
        return label

    def _handle_label_set_border_color(self, args: list[Any]) -> Label:
        """label.set_border_color(label, color)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.border_color = args[1] if len(args) > 1 else label.border_color
        return label

    def _handle_label_set_border_width(self, args: list[Any]) -> Label:
        """label.set_border_width(label, width)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.border_width = args[1] if len(args) > 1 else label.border_width
        return label

    def _handle_label_set_border_style(self, args: list[Any]) -> Label:
        """label.set_border_style(label, style)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.border_style = args[1] if len(args) > 1 else label.border_style
        return label

    def _handle_label_set_style(self, args: list[Any]) -> Label:
        """label.set_style(label, style)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.style = args[1] if len(args) > 1 else label.style
        return label

    def _handle_label_set_xloc(self, args: list[Any]) -> Label:
        """label.set_xloc(label, xloc)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.xloc = args[1] if len(args) > 1 else label.xloc
        return label

    def _handle_label_set_yloc(self, args: list[Any]) -> Label:
        """label.set_yloc(label, yloc)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.yloc = args[1] if len(args) > 1 else label.yloc
        return label

    def _handle_label_get_x(self, args: list[Any]) -> int | float:
        """label.get_x(label)"""
        label = args[0] if len(args) > 0 else None
        if not isinstance(label, Label):
            return 0
        x = label.x
        # Unwrap if x was stored as ChartPoint (legacy label.new(point=...))
        if isinstance(x, ChartPoint):
            if x.index is not None:
                return x.index
            return x.time if x.time is not None else 0
        return x

    def _handle_label_get_y(self, args: list[Any]) -> float:
        """label.get_y(label)"""
        label = args[0] if len(args) > 0 else None
        if not isinstance(label, Label):
            return 0.0
        y = label.y
        if isinstance(y, ChartPoint):
            return float(y.price)
        return y

    def _handle_label_get_text(self, args: list[Any]) -> str:
        """label.get_text(label)"""
        label = args[0] if len(args) > 0 else None
        return label.text if isinstance(label, Label) else ""

    # TABLE HANDLERS

    def _handle_table_new(self, args: list[Any]) -> Table:
        """table.new(position, rows, columns, ...)"""
        position = args[0] if len(args) > 0 else "top_left"
        rows = args[1] if len(args) > 1 else 0
        columns = args[2] if len(args) > 2 else 0
        frame_color = args[3] if len(args) > 3 else "#000000"
        frame_width = args[4] if len(args) > 4 else 1
        border_color = args[5] if len(args) > 5 else "#000000"
        border_width = args[6] if len(args) > 6 else 1
        bgcolor = args[7] if len(args) > 7 else "rgba(255,255,255,255)"
        force_overlay = args[8] if len(args) > 8 else False

        table = Table(
            position, rows, columns, frame_color, frame_width,
            border_color, border_width, bgcolor,
            force_overlay=force_overlay
        )
        DrawingRegistry.tables.append(table)
        return table

    def _handle_table_delete(self, args: list[Any]) -> None:
        """table.delete(table)"""
        table = args[0] if len(args) > 0 else None
        if isinstance(table, Table):
            table.deleted = True

    def _handle_table_cell(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> TableCell:
        """table.cell(table_id, column, row, text, ...).

        TradingView order is **column then row** (not row, column).
        Optional text and style kwargs update the cell in place.
        """
        kw = kwargs or {}
        table = kw.get("table_id", kw.get("table", args[0] if len(args) > 0 else None))
        # TV: column, row — also accept swapped if named
        column = kw.get("column", args[1] if len(args) > 1 else 0)
        row = kw.get("row", args[2] if len(args) > 2 else 0)
        text = kw.get("text", args[3] if len(args) > 3 else None)
        text_color = kw.get("text_color", args[6] if len(args) > 6 else None)
        bgcolor = kw.get("bgcolor", args[10] if len(args) > 10 else None)
        tooltip = kw.get("tooltip", args[11] if len(args) > 11 else None)

        try:
            col_i = int(column)
            row_i = int(row)
        except (TypeError, ValueError):
            col_i, row_i = 0, 0

        if isinstance(table, Table):
            key = (row_i, col_i)
            if key not in table.cells:
                table.cells[key] = TableCell()
            cell = table.cells[key]
            if text is not None:
                cell.text = str(text)
            if text_color is not None:
                cell.text_color = str(text_color)
            if bgcolor is not None:
                cell.bgcolor = str(bgcolor)
            if tooltip is not None:
                cell.tooltip = str(tooltip)
            return cell
        return TableCell()

    def _handle_table_cell_set_text(self, args: list[Any]) -> None:
        """table.cell_set_text(table, row, column, text)"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0
        text = args[3] if len(args) > 3 else ""

        if isinstance(table, Table):
            key = (row, column)
            if key not in table.cells:
                table.cells[key] = TableCell()
            table.cells[key].text = text

    def _handle_table_cell_set_text_color(self, args: list[Any]) -> None:
        """table.cell_set_text_color(table, row, column, color)"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0
        color = args[3] if len(args) > 3 else "#000000"

        if isinstance(table, Table):
            key = (row, column)
            if key not in table.cells:
                table.cells[key] = TableCell()
            table.cells[key].text_color = color

    def _handle_table_cell_set_bgcolor(self, args: list[Any]) -> None:
        """table.cell_set_bgcolor(table, row, column, color)"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0
        color = args[3] if len(args) > 3 else "rgba(255,255,255,255)"

        if isinstance(table, Table):
            key = (row, column)
            if key not in table.cells:
                table.cells[key] = TableCell()
            table.cells[key].bgcolor = color

    def _handle_table_cell_set_border_color(self, args: list[Any]) -> None:
        """table.cell_set_border_color(table, row, column, color)"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0
        color = args[3] if len(args) > 3 else "#000000"

        if isinstance(table, Table):
            key = (row, column)
            if key not in table.cells:
                table.cells[key] = TableCell()
            table.cells[key].border_color = color

    def _handle_table_cell_set_border_width(self, args: list[Any]) -> None:
        """table.cell_set_border_width(table, row, column, width)"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0
        width = args[3] if len(args) > 3 else 1

        if isinstance(table, Table):
            key = (row, column)
            if key not in table.cells:
                table.cells[key] = TableCell()
            table.cells[key].border_width = width

    def _handle_table_cell_get_text(self, args: list[Any]) -> str:
        """table.cell_get_text(table, row, column)"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0

        if isinstance(table, Table):
            key = (row, column)
            if key in table.cells:
                return table.cells[key].text
        return ""

    def _handle_table_clear(self, args: list[Any]) -> None:
        """table.clear(table, start_row, start_col, end_row, end_col)"""
        table = args[0] if len(args) > 0 else None

        if isinstance(table, Table):
            table.cells.clear()

    def _handle_table_merge_cells(self, args: list[Any]) -> None:
        """table.merge_cells(table, start_row, start_col, end_row, end_col)"""
        # Mock implementation - in real Pine Script this would merge cells
        # For now, we just register the merge without doing anything special
        pass

    # CHART POINT HANDLERS

    def _chart_point_price(self, price: Any) -> float | None:
        """Coerce price for ChartPoint; unwrap PineSeries; ``na`` → None."""
        if price is None:
            return None
        if hasattr(price, "current"):
            price = getattr(price, "current", None)
        if price is None:
            return None
        try:
            return float(price)
        except (TypeError, ValueError):
            return None

    def _handle_chart_point_new(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> ChartPoint | None:
        """chart.point.new(time, price) - Create a point from time and price"""
        kw = kwargs or {}
        time = kw.get("time", args[0] if len(args) > 0 else None)
        price = self._chart_point_price(kw.get("price", args[1] if len(args) > 1 else 0.0))
        if price is None:
            return None
        return ChartPoint(time=time, price=price)

    def _handle_chart_point_from_index(
        self, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> ChartPoint | None:
        """chart.point.from_index(index, price) - Create a point from bar index and price"""
        kw = kwargs or {}
        index = kw.get("index", args[0] if len(args) > 0 else 0)
        price = self._chart_point_price(kw.get("price", args[1] if len(args) > 1 else 0.0))
        if price is None or index is None:
            return None
        try:
            return ChartPoint(index=int(index), price=price)
        except (TypeError, ValueError):
            return None

    def _handle_chart_point_from_time(
        self, args: list[Any], kwargs: dict[str, Any] | None = None
    ) -> ChartPoint | None:
        """chart.point.from_time(time, price) - Create a point from timestamp and price"""
        kw = kwargs or {}
        time = kw.get("time", args[0] if len(args) > 0 else None)
        price = self._chart_point_price(kw.get("price", args[1] if len(args) > 1 else 0.0))
        if price is None:
            return None
        return ChartPoint(time=time, price=price)

    def _handle_chart_point_now(self, args: list[Any]) -> ChartPoint | None:
        """chart.point.now(price) - Create a point at current bar with given price"""
        price = self._chart_point_price(args[0] if len(args) > 0 else 0.0)
        if price is None:
            return None
        # Prefer live bar context so label.new(point=...) / get_x get a real index
        ctx = getattr(self, "context", None) or {}
        bar_index = ctx.get("bar_index")
        bar_time = ctx.get("time")
        try:
            index = int(bar_index) if bar_index is not None else None
        except (TypeError, ValueError):
            index = None
        try:
            tval = int(bar_time) if bar_time is not None else None
        except (TypeError, ValueError):
            tval = None
        return ChartPoint(time=tval, index=index, price=price)

    def _handle_chart_point_copy(self, args: list[Any]) -> ChartPoint:
        """chart.point.copy(point) - Create a copy of a chart point"""
        point = args[0] if len(args) > 0 else None
        if isinstance(point, ChartPoint):
            return point.copy()
        return ChartPoint()

    # POLYLINE HANDLERS

    def _handle_polyline_new(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Polyline:
        """polyline.new(points, closed=..., xloc=..., color=..., width=..., style=...)."""
        kw = kwargs or {}
        points = kw.get("points", args[0] if len(args) > 0 else [])
        closed = kw.get("closed", args[1] if len(args) > 1 else False)
        xloc = kw.get("xloc", args[2] if len(args) > 2 else "bar_index")
        color = kw.get("color", args[3] if len(args) > 3 else "#000000")
        width = kw.get("width", args[4] if len(args) > 4 else 1)
        style = kw.get("style", args[5] if len(args) > 5 else "solid")
        force_overlay = kw.get("force_overlay", args[6] if len(args) > 6 else False)
        # Normalize xloc enums like xloc.bar_index
        xloc_s = str(xloc or "bar_index").replace("xloc.", "")
        pts = list(points) if isinstance(points, list) else []
        # Drop None entries from failed chart.point factories
        pts = [p for p in pts if p is not None]

        polyline = Polyline(
            points=pts,
            closed=bool(closed),
            xloc=xloc_s,
            color=str(color),
            width=int(width) if width is not None else 1,
            style=str(style or "solid"),
            force_overlay=bool(force_overlay),
        )
        DrawingRegistry.polylines.append(polyline)
        return polyline

    def _handle_polyline_delete(self, args: list[Any]) -> None:
        """polyline.delete(polyline)"""
        polyline = args[0] if len(args) > 0 else None
        if isinstance(polyline, Polyline):
            polyline.deleted = True


    # ========== MISSING TV SURFACE HANDLERS ==========

    def _handle_line_get_price(self, args: list[Any]) -> float | None:
        """line.get_price(id, x) — interpolate Y at X between endpoints."""
        line = args[0] if args else None
        x = args[1] if len(args) > 1 else None
        if not isinstance(line, Line) or x is None:
            return None
        x1, x2 = float(line.x1), float(line.x2)
        if x1 == x2:
            return float(line.y1)
        t = (float(x) - x1) / (x2 - x1)
        return float(line.y1) + t * (float(line.y2) - float(line.y1))

    def _handle_line_set_xy1(self, args: list[Any]) -> None:
        line = args[0] if args else None
        if isinstance(line, Line) and len(args) >= 3:
            line.x1, line.y1 = args[1], args[2]

    def _handle_line_set_xy2(self, args: list[Any]) -> None:
        line = args[0] if args else None
        if isinstance(line, Line) and len(args) >= 3:
            line.x2, line.y2 = args[1], args[2]

    def _handle_line_set_first_point(self, args: list[Any]) -> None:
        """line.set_first_point(id, point) where point is ChartPoint."""
        line = args[0] if args else None
        point = args[1] if len(args) > 1 else None
        if isinstance(line, Line) and isinstance(point, ChartPoint):
            line.x1 = point.index if point.index is not None else (point.time or 0)
            line.y1 = point.price

    def _handle_line_set_second_point(self, args: list[Any]) -> None:
        line = args[0] if args else None
        point = args[1] if len(args) > 1 else None
        if isinstance(line, Line) and isinstance(point, ChartPoint):
            line.x2 = point.index if point.index is not None else (point.time or 0)
            line.y2 = point.price

    def _handle_box_set_lefttop(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) >= 3:
            box.left, box.top = args[1], args[2]

    def _handle_box_set_rightbottom(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) >= 3:
            box.right, box.bottom = args[1], args[2]

    def _handle_box_set_top_left_point(self, args: list[Any]) -> None:
        box = args[0] if args else None
        point = args[1] if len(args) > 1 else None
        if isinstance(box, Box) and isinstance(point, ChartPoint):
            box.left = point.index if point.index is not None else (point.time or 0)
            box.top = point.price

    def _handle_box_set_bottom_right_point(self, args: list[Any]) -> None:
        box = args[0] if args else None
        point = args[1] if len(args) > 1 else None
        if isinstance(box, Box) and isinstance(point, ChartPoint):
            box.right = point.index if point.index is not None else (point.time or 0)
            box.bottom = point.price

    def _handle_box_set_text(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text = str(args[1])

    def _handle_box_set_text_color(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_color = args[1]

    def _handle_box_set_text_font_family(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_font_family = str(args[1])

    def _handle_box_set_text_halign(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_halign = str(args[1])

    def _handle_box_set_text_valign(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_valign = str(args[1])

    def _handle_box_set_text_size(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_size = args[1]

    def _handle_box_set_text_formatting(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_formatting = str(args[1])

    def _handle_box_set_text_wrap(self, args: list[Any]) -> None:
        box = args[0] if args else None
        if isinstance(box, Box) and len(args) > 1:
            box.text_wrap = str(args[1])

    def _handle_label_set_textalign(self, args: list[Any]) -> None:
        """label.set_textalign — alias of set_text_halign."""
        label = args[0] if args else None
        if isinstance(label, Label) and len(args) > 1:
            label.text_halign = str(args[1])

    def _handle_label_set_size(self, args: list[Any]) -> None:
        label = args[0] if args else None
        if isinstance(label, Label) and len(args) > 1:
            label.size = args[1]
            label.text_size = args[1]

    def _handle_label_set_point(self, args: list[Any]) -> None:
        label = args[0] if args else None
        point = args[1] if len(args) > 1 else None
        if isinstance(label, Label) and isinstance(point, ChartPoint):
            label.x = point.index if point.index is not None else (point.time or 0)
            label.y = point.price

    def _table_cell_at(self, table: Table, col: int, row: int) -> TableCell:
        key = (int(col), int(row))
        if key not in table.cells:
            table.cells[key] = TableCell()
        return table.cells[key]

    def _handle_table_cell_set_width(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).width = val

    def _handle_table_cell_set_height(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).height = val

    def _handle_table_cell_set_text_halign(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).text_halign = str(val)

    def _handle_table_cell_set_text_valign(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).text_valign = str(val)

    def _handle_table_cell_set_text_size(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).text_size = val

    def _handle_table_cell_set_text_font_family(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).text_font_family = str(val)

    def _handle_table_cell_set_text_formatting(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).text_formatting = str(val)

    def _handle_table_cell_set_tooltip(self, args: list[Any]) -> None:
        table, col, row, val = (args + [None] * 4)[:4]
        if isinstance(table, Table):
            self._table_cell_at(table, col, row).tooltip = str(val)

    def _handle_table_set_position(self, args: list[Any]) -> None:
        table = args[0] if args else None
        if isinstance(table, Table) and len(args) > 1:
            table.position = str(args[1])

    def _handle_table_set_bgcolor(self, args: list[Any]) -> None:
        table = args[0] if args else None
        if isinstance(table, Table) and len(args) > 1:
            table.bgcolor = args[1]

    def _handle_table_set_border_color(self, args: list[Any]) -> None:
        table = args[0] if args else None
        if isinstance(table, Table) and len(args) > 1:
            table.border_color = args[1]

    def _handle_table_set_border_width(self, args: list[Any]) -> None:
        table = args[0] if args else None
        if isinstance(table, Table) and len(args) > 1:
            table.border_width = int(args[1])

    def _handle_table_set_frame_color(self, args: list[Any]) -> None:
        table = args[0] if args else None
        if isinstance(table, Table) and len(args) > 1:
            table.frame_color = args[1]

    def _handle_table_set_frame_width(self, args: list[Any]) -> None:
        table = args[0] if args else None
        if isinstance(table, Table) and len(args) > 1:
            table.frame_width = int(args[1])

    def _handle_linefill_new(self, args: list[Any]) -> LineFill:
        line1 = args[0] if len(args) > 0 else None
        line2 = args[1] if len(args) > 1 else None
        color = args[2] if len(args) > 2 else "rgba(0,0,0,0)"
        fill = LineFill(
            line1=line1 if isinstance(line1, Line) else None,
            line2=line2 if isinstance(line2, Line) else None,
            color=str(color),
        )
        DrawingRegistry.linefills.append(fill)
        return fill

    def _handle_linefill_delete(self, args: list[Any]) -> None:
        fill = args[0] if args else None
        if isinstance(fill, LineFill):
            fill.deleted = True

    def _handle_linefill_set_color(self, args: list[Any]) -> None:
        fill = args[0] if args else None
        if isinstance(fill, LineFill) and len(args) > 1:
            fill.color = str(args[1])

    def _handle_linefill_get_line1(self, args: list[Any]) -> Line | None:
        fill = args[0] if args else None
        return fill.line1 if isinstance(fill, LineFill) else None

    def _handle_linefill_get_line2(self, args: list[Any]) -> Line | None:
        fill = args[0] if args else None
        return fill.line2 if isinstance(fill, LineFill) else None
