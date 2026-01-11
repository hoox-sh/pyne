# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import ClassVar

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


# Drawing object registries
class DrawingRegistry:
    """Global registry for drawing objects."""

    lines: ClassVar[list[Line]] = []
    boxes: ClassVar[list[Box]] = []
    labels: ClassVar[list[Label]] = []
    tables: ClassVar[list[Table]] = []
    polylines: ClassVar[list[Polyline]] = []

    @classmethod
    def reset(cls) -> None:
        """Reset all registries for testing."""
        cls.lines = []
        cls.boxes = []
        cls.labels = []
        cls.tables = []
        cls.polylines = []


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
    text_size: str = "auto"
    tooltip: str = ""
    style: str = "label_center"
    border_color: str = "rgba(0,0,0,0)"
    border_width: int = 0
    border_style: str = "solid"
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
    deleted: bool = False


class DrawingBuiltinsMixin(BuiltinDispatchMixin):
    """Drawing functions for line, box, label, and table annotations."""

    def _drawing_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            # Line functions
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
            "label.set_text_font_family": self._handle_label_set_text_font_family,
            "label.set_text_halign": self._handle_label_set_text_halign,
            "label.set_text_valign": self._handle_label_set_text_valign,
            "label.set_text_size": self._handle_label_set_text_size,
            "label.set_tooltip": self._handle_label_set_tooltip,
            "label.set_color": self._handle_label_set_color,
            "label.set_border_color": self._handle_label_set_border_color,
            "label.set_border_width": self._handle_label_set_border_width,
            "label.set_border_style": self._handle_label_set_border_style,
            "label.set_style": self._handle_label_set_style,
            "label.set_xloc": self._handle_label_set_xloc,
            "label.set_yloc": self._handle_label_set_yloc,
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
            "table.cell_get_text": self._handle_table_cell_get_text,
            "table.clear": self._handle_table_clear,
            "table.merge_cells": self._handle_table_merge_cells,
            # Chart point functions
            "chart.point.new": self._handle_chart_point_new,
            "chart.point.from_index": self._handle_chart_point_from_index,
            "chart.point.from_time": self._handle_chart_point_from_time,
            "chart.point.now": self._handle_chart_point_now,
            "chart.point.copy": self._handle_chart_point_copy,
            # Polyline functions
            "polyline.new": self._handle_polyline_new,
            "polyline.delete": self._handle_polyline_delete,
        }

    # LINE HANDLERS

    def _handle_line_new(self, args: list[Any]) -> Line:
        """line.new(x1, y1, x2, y2, xloc, closed, color, width, style, extend)"""
        x1 = args[0] if len(args) > 0 else 0
        y1 = args[1] if len(args) > 1 else 0.0
        x2 = args[2] if len(args) > 2 else 0
        y2 = args[3] if len(args) > 3 else 0.0
        xloc = args[4] if len(args) > 4 else "bar_index"
        color = args[5] if len(args) > 5 else "#000000"
        width = args[6] if len(args) > 6 else 1
        style = args[7] if len(args) > 7 else "solid"
        extend = args[8] if len(args) > 8 else "none"

        line = Line(x1, y1, x2, y2, xloc, color, width, style, extend)
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

    def _handle_box_new(self, args: list[Any]) -> Box:
        """box.new(left, top, right, bottom, xloc, closed, bgcolor, ...)"""
        left = args[0] if len(args) > 0 else 0
        top = args[1] if len(args) > 1 else 0.0
        right = args[2] if len(args) > 2 else 0
        bottom = args[3] if len(args) > 3 else 0.0
        xloc = args[4] if len(args) > 4 else "bar_index"
        closed = args[5] if len(args) > 5 else True
        bgcolor = args[6] if len(args) > 6 else "rgba(0,0,0,0)"
        border_color = args[7] if len(args) > 7 else "#000000"
        border_width = args[8] if len(args) > 8 else 1
        border_style = args[9] if len(args) > 9 else "solid"
        extend = args[10] if len(args) > 10 else "none"

        box = Box(left, top, right, bottom, xloc, closed, bgcolor, border_color, border_width, border_style, extend)
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
        """box.set_xloc(box, xloc)"""
        box = args[0] if len(args) > 0 else None
        if isinstance(box, Box):
            box.xloc = args[1] if len(args) > 1 else box.xloc
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

    def _handle_label_new(self, args: list[Any]) -> Label:
        """label.new(x, y, text, xloc, yloc, color, textcolor, ...)"""
        x = args[0] if len(args) > 0 else 0
        y = args[1] if len(args) > 1 else 0.0
        text = args[2] if len(args) > 2 else ""
        xloc = args[3] if len(args) > 3 else "bar_index"
        yloc = args[4] if len(args) > 4 else "price"
        color = args[5] if len(args) > 5 else "#000000"
        textcolor = args[6] if len(args) > 6 else "#000000"
        text_font_family = args[7] if len(args) > 7 else "default"
        text_halign = args[8] if len(args) > 8 else "center"
        text_valign = args[9] if len(args) > 9 else "center"
        text_size = args[10] if len(args) > 10 else "auto"
        tooltip = args[11] if len(args) > 11 else ""
        style = args[12] if len(args) > 12 else "label_center"

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
            tooltip,
            style,
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
                label.tooltip,
                label.style,
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
        """label.set_text_size(label, size)"""
        label = args[0] if len(args) > 0 else None
        if isinstance(label, Label):
            label.text_size = args[1] if len(args) > 1 else label.text_size
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
        return label.x if isinstance(label, Label) else 0

    def _handle_label_get_y(self, args: list[Any]) -> float:
        """label.get_y(label)"""
        label = args[0] if len(args) > 0 else None
        return label.y if isinstance(label, Label) else 0.0

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

        table = Table(position, rows, columns, frame_color, frame_width, border_color, border_width, bgcolor)
        DrawingRegistry.tables.append(table)
        return table

    def _handle_table_delete(self, args: list[Any]) -> None:
        """table.delete(table)"""
        table = args[0] if len(args) > 0 else None
        if isinstance(table, Table):
            table.deleted = True

    def _handle_table_cell(self, args: list[Any]) -> TableCell:
        """table.cell(table, row, column) - Returns cell object"""
        table = args[0] if len(args) > 0 else None
        row = args[1] if len(args) > 1 else 0
        column = args[2] if len(args) > 2 else 0

        if isinstance(table, Table):
            key = (row, column)
            if key not in table.cells:
                table.cells[key] = TableCell()
            return table.cells[key]
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

    def _handle_chart_point_new(self, args: list[Any]) -> ChartPoint:
        """chart.point.new(time, price) - Create a point from time and price"""
        time = args[0] if len(args) > 0 else None
        price = args[1] if len(args) > 1 else 0.0
        return ChartPoint(time=time, price=float(price))

    def _handle_chart_point_from_index(self, args: list[Any]) -> ChartPoint:
        """chart.point.from_index(index, price) - Create a point from bar index and price"""
        index = args[0] if len(args) > 0 else 0
        price = args[1] if len(args) > 1 else 0.0
        return ChartPoint(index=int(index), price=float(price))

    def _handle_chart_point_from_time(self, args: list[Any]) -> ChartPoint:
        """chart.point.from_time(time, price) - Create a point from timestamp and price"""
        time = args[0] if len(args) > 0 else None
        price = args[1] if len(args) > 1 else 0.0
        return ChartPoint(time=time, price=float(price))

    def _handle_chart_point_now(self, args: list[Any]) -> ChartPoint:
        """chart.point.now(price) - Create a point at current bar with given price"""
        price = args[0] if len(args) > 0 else 0.0
        # Returns a point at current bar (index not specified, time not specified)
        return ChartPoint(price=float(price))

    def _handle_chart_point_copy(self, args: list[Any]) -> ChartPoint:
        """chart.point.copy(point) - Create a copy of a chart point"""
        point = args[0] if len(args) > 0 else None
        if isinstance(point, ChartPoint):
            return point.copy()
        return ChartPoint()

    # POLYLINE HANDLERS

    def _handle_polyline_new(self, args: list[Any]) -> Polyline:
        """polyline.new(points, closed, xloc, color, width, style)"""
        points = args[0] if len(args) > 0 else []
        closed = args[1] if len(args) > 1 else False
        xloc = args[2] if len(args) > 2 else "bar_index"
        color = args[3] if len(args) > 3 else "#000000"
        width = args[4] if len(args) > 4 else 1
        style = args[5] if len(args) > 5 else "solid"

        polyline = Polyline(
            points=list(points) if isinstance(points, list) else [],
            closed=bool(closed),
            xloc=str(xloc),
            color=str(color),
            width=int(width),
            style=str(style),
        )
        DrawingRegistry.polylines.append(polyline)
        return polyline

    def _handle_polyline_delete(self, args: list[Any]) -> None:
        """polyline.delete(polyline)"""
        polyline = args[0] if len(args) > 0 else None
        if isinstance(polyline, Polyline):
            polyline.deleted = True
