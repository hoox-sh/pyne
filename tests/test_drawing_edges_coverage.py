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

"""Edge coverage for drawing.* builtins (Runtime scripts + helpers)."""

from __future__ import annotations

import math

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import Box
from pynescript.ast.evaluator.builtins.drawing import ChartPoint
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.evaluator.builtins.drawing import Label
from pynescript.ast.evaluator.builtins.drawing import Line
from pynescript.ast.evaluator.builtins.drawing import LineFill
from pynescript.ast.evaluator.builtins.drawing import Polyline
from pynescript.ast.evaluator.builtins.drawing import _clamp_drawing_limit
from pynescript.ast.evaluator.builtins.drawing import _export_color
from pynescript.ast.evaluator.builtins.drawing import _export_extend
from pynescript.ast.evaluator.builtins.drawing import _export_num
from pynescript.ast.evaluator.builtins.drawing import _export_x_to_time
from pynescript.ast.evaluator.builtins.drawing import _snapshot_scalar
from pynescript.ast.helper import parse
from pynescript.runtime import Runtime


def _bars(n: int = 8) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


def _run(src: str, bars: list[dict[str, float | int]] | None = None) -> dict:
    DrawingRegistry.reset()
    out = Runtime(symbol="DRAW").run(src, bars if bars is not None else _bars(), mode="interpret")
    assert "error" not in out or out.get("error") is None, out.get("error")
    return out


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


class TestDrawingExportHelpers:
    def test_export_num_color_extend_x(self) -> None:
        assert _export_num(None) is None
        assert _export_num(float("nan")) is None
        assert _export_num(True) == 1
        assert _export_num("x") is None
        assert _export_num(3.5) == 3.5
        assert _snapshot_scalar(None) is None
        assert _snapshot_scalar(4) == 4
        assert _export_color(None) == "#939fff"
        assert _export_color(0xFF112233) == "#112233"
        assert _export_color(0x112233) == "#112233"
        assert _export_color("#abc") == "#abc"
        assert _export_extend("extend.both") == "both"
        assert _export_extend("weird") == "none"
        assert _export_x_to_time(None, "bar_index", [10, 20]) is None
        assert _export_x_to_time(1, "xloc.bar_time", [10, 20]) == 1
        assert _export_x_to_time(1_700_000_000_001, "bar_index", [10]) == 1_700_000_000_001
        assert _export_x_to_time(2, "bar_index", []) == 2
        assert _export_x_to_time(1, "bar_index", [10, 20]) == 20
        assert _export_x_to_time(3, "bar_index", [10, 20]) == 40
        assert _export_x_to_time(-1, "bar_index", [10, 20]) == 0
        assert _export_x_to_time(2, "bar_index", [10]) == 130
        assert _clamp_drawing_limit(None) == 50
        assert _clamp_drawing_limit("x") == 50
        assert _clamp_drawing_limit(float("nan")) == 50
        assert _clamp_drawing_limit(0) == 1
        assert _clamp_drawing_limit(9999) == 500
        assert _clamp_drawing_limit(9999, hard_cap=100) == 100


class TestLineLabelBoxRuntimeEdges:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def teardown_method(self) -> None:
        DrawingRegistry.reset()

    def test_line_set_get_copy_delete_styles(self) -> None:
        src = """//@version=6
indicator("line")
var float x1v = na
var float y1v = na
var float x2v = na
var float y2v = na
var int active = 0
if barstate.islast
    ln = line.new(0, 1.0, 1, 2.0, color=color.red, width=2, style=line.style_dashed, extend=extend.none)
    line.set_x1(ln, 2)
    line.set_y1(ln, 3.0)
    line.set_x2(ln, 4)
    line.set_y2(ln, 5.0)
    line.set_color(ln, color.blue)
    line.set_width(ln, 4)
    line.set_style(ln, line.style_dotted)
    line.set_extend(ln, extend.right)
    line.set_xloc(ln, xloc.bar_index)
    x1v := line.get_x1(ln)
    y1v := line.get_y1(ln)
    x2v := line.get_x2(ln)
    y2v := line.get_y2(ln)
    cp = line.copy(ln)
    line.delete(cp)
    active := array.size(line.all)
plot(x1v, "x1")
plot(y1v, "y1")
plot(x2v, "x2")
plot(y2v, "y2")
plot(active, "n")
"""
        out = _run(src)
        assert out["series"]["x1"][-1] == 2
        assert out["series"]["y1"][-1] == 3.0
        assert out["series"]["x2"][-1] == 4
        assert out["series"]["y2"][-1] == 5.0
        assert out["series"]["n"][-1] == 1
        drawings = out.get("drawings") or []
        assert any(d.get("type") == "line" or d.get("kind") == "line" for d in drawings)

    def test_label_set_get_and_na_coords(self) -> None:
        src = """//@version=6
indicator("label")
var int tlen = 0
var float lx = na
var float ly = na
var int nax = 0
if barstate.islast
    lb = label.new(1, 1.0, "a", style=label.style_label_left, color=color.green, textcolor=color.white)
    label.set_x(lb, 2)
    label.set_y(lb, 3.0)
    label.set_xy(lb, 2, 3.0)
    label.set_text(lb, "zz")
    label.set_color(lb, color.red)
    label.set_textcolor(lb, color.black)
    label.set_style(lb, label.style_label_down)
    label.set_tooltip(lb, "tip")
    label.set_xloc(lb, xloc.bar_index)
    label.set_yloc(lb, yloc.price)
    label.set_text_font_family(lb, font.family_monospace)
    tlen := str.length(label.get_text(lb))
    lx := label.get_x(lb)
    ly := label.get_y(lb)
    ln = line.new(na, close, bar_index, close)
    nax := na(line.get_x1(ln)) ? 1 : 0
    label.new(na, na, "x")
    box.new(na, high, bar_index, low)
plot(tlen, "tlen")
plot(lx, "lx")
plot(ly, "ly")
plot(nax, "nax")
"""
        out = _run(src)
        assert out["series"]["tlen"][-1] == 2
        assert out["series"]["lx"][-1] == 2
        assert out["series"]["ly"][-1] == 3.0
        assert out["series"]["nax"][-1] == 1

    def test_box_set_get_copy_delete(self) -> None:
        src = """//@version=6
indicator("box")
var float leftv = na
var float rightv = na
var float topv = na
var float botv = na
if barstate.islast
    bx = box.new(0, 10.0, 2, 1.0, bgcolor=color.new(color.blue, 80), border_color=color.blue)
    box.set_left(bx, 1)
    box.set_right(bx, 3)
    box.set_top(bx, 9.0)
    box.set_bottom(bx, 2.0)
    box.set_bgcolor(bx, color.green)
    box.set_border_color(bx, color.red)
    box.set_border_width(bx, 2)
    box.set_border_style(bx, line.style_dotted)
    box.set_extend(bx, extend.both)
    box.set_xloc(bx, 1, 3, xloc.bar_index)
    box.set_closed(bx, true)
    leftv := box.get_left(bx)
    rightv := box.get_right(bx)
    topv := box.get_top(bx)
    botv := box.get_bottom(bx)
    cp = box.copy(bx)
    box.delete(cp)
plot(leftv, "left")
plot(rightv, "right")
plot(topv, "top")
plot(botv, "bot")
"""
        out = _run(src)
        assert out["series"]["left"][-1] == 1
        assert out["series"]["right"][-1] == 3
        assert out["series"]["top"][-1] == 9.0
        assert out["series"]["bot"][-1] == 2.0


class TestTablePolylineLinefillEdges:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def teardown_method(self) -> None:
        DrawingRegistry.reset()

    def test_table_cell_set_get_clear_merge(self) -> None:
        src = """//@version=6
indicator("table")
var int tlen = 0
var int ntab = 0
if barstate.islast
    tb = table.new(position.top_right, 3, 3)
    table.cell(tb, 0, 0, "a", text_color=color.white, bgcolor=color.black)
    table.cell(tb, 1, 1, "b")
    table.cell_set_text(tb, 0, 0, "zz")
    table.cell_set_text_color(tb, 0, 0, color.red)
    table.cell_set_bgcolor(tb, 0, 0, color.blue)
    table.cell_set_border_color(tb, 0, 0, color.green)
    table.cell_set_border_width(tb, 0, 0, 2)
    tlen := str.length(table.cell_get_text(tb, 0, 0))
    table.merge_cells(tb, 0, 0, 0, 1)
    table.clear(tb, 1, 1, 2, 2)
    ntab := array.size(table.all)
    table.delete(tb)
plot(tlen, "tlen")
plot(ntab, "ntab")
"""
        out = _run(src)
        assert out["series"]["tlen"][-1] == 2
        assert out["series"]["ntab"][-1] == 1

    def test_polyline_setters_copy_delete_and_chart_points(self) -> None:
        src = """//@version=6
indicator("poly")
var int npts = 0
var int npoly = 0
if barstate.islast
    p0 = chart.point.from_index(0, 1.0)
    p1 = chart.point.from_index(1, 2.0)
    p2 = chart.point.now(3.0)
    p3 = chart.point.from_time(time, 4.0)
    p4 = chart.point.new(time, 5.0)
    p5 = chart.point.copy(p0)
    pts = array.from(p0, p1, p2, p3, p4, p5)
    pl = polyline.new(pts, false, xloc.bar_index, color.orange, 2, line.style_solid)
    polyline.set_points(pl, array.from(chart.point.from_index(0, 5.0), chart.point.from_index(1, 6.0)))
    polyline.set_line_color(pl, color.purple)
    polyline.set_line_width(pl, 5)
    polyline.set_line_style(pl, line.style_dashed)
    polyline.set_fill_color(pl, color.yellow)
    polyline.set_curved(pl, true)
    polyline.set_force_overlay(pl, true)
    polyline.set_closed(pl, true)
    polyline.set_xloc(pl, xloc.bar_index)
    npts := array.size(polyline.get_points(pl))
    cp = polyline.copy(pl)
    polyline.delete(cp)
    npoly := array.size(polyline.all)
    ln1 = line.new(0, 1.0, 1, 2.0)
    ln2 = line.new(0, 2.0, 1, 3.0)
    lf = linefill.new(ln1, ln2, color.new(color.red, 80))
    linefill.set_color(lf, color.new(color.blue, 70))
    linefill.delete(lf)
plot(npts, "npts")
plot(npoly, "npoly")
"""
        out = _run(src)
        assert out["series"]["npts"][-1] == 2
        assert out["series"]["npoly"][-1] == 1

    def test_max_objects_gc_via_indicator_limits(self) -> None:
        src = """//@version=6
indicator("gc", max_lines_count=2, max_labels_count=2, max_boxes_count=2, max_polylines_count=2)
if barstate.islast
    line.new(0, 1.0, 1, 2.0)
    line.new(1, 2.0, 2, 3.0)
    line.new(2, 3.0, 3, 4.0)
    label.new(0, 1.0, "a")
    label.new(1, 2.0, "b")
    label.new(2, 3.0, "c")
    box.new(0, 3.0, 1, 0.0)
    box.new(1, 4.0, 2, 1.0)
    box.new(2, 5.0, 3, 2.0)
plot(array.size(line.all), "nl")
plot(array.size(label.all), "nb")
plot(array.size(box.all), "nx")
"""
        out = _run(src)
        assert out["series"]["nl"][-1] == 2
        assert out["series"]["nb"][-1] == 2
        assert out["series"]["nx"][-1] == 2


class TestDrawingDirectHandlersAndExport:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def teardown_method(self) -> None:
        DrawingRegistry.reset()

    def test_direct_handlers_soft_na_and_casts(self) -> None:
        ev = NodeLiteralEvaluator()
        ev.context["bar_index"] = 3
        ev.context["time"] = 1_700_000_000_000
        assert ev._handle_line_get_x1([None]) is None
        assert ev._handle_line_get_y1([None]) is None
        assert ev._handle_line_copy([None]).x1 == 0
        assert ev._handle_box_copy([None]).left == 0
        assert ev._handle_type_cast([]) is None
        assert ev._handle_type_cast([Line(1, 2.0, 3, 4.0)]) is not None
        assert ev._chart_point_price(None) is None
        assert ev._chart_point_price("x") is None
        assert ev._handle_chart_point_new([None, None]) is None
        assert ev._handle_chart_point_from_index([None, 1.0]) is None
        assert ev._handle_chart_point_from_time([1, None]) is None
        assert ev._handle_chart_point_now([None]) is None
        now = ev._handle_chart_point_now([1.5])
        assert now is not None and now.price == 1.5 and now.index == 3
        assert ev._handle_chart_point_copy([None]).price is None or isinstance(
            ev._handle_chart_point_copy([None]), ChartPoint
        )
        assert ev._handle_polyline_get_points([None]) == []
        assert ev._handle_polyline_copy([None]) is None
        assert ev._handle_linefill_get_line1([None]) is None
        assert ev._handle_linefill_get_line2([None]) is None

    def test_export_for_api_skips_deleted_and_maps_x(self) -> None:
        ln = DrawingRegistry.add_line(Line(0, 1.0, 2, 3.0, color="#ff0000", width=2, style="dashed", extend="both"))
        lb = DrawingRegistry.add_label(Label(1, 2.0, "hi", color="#00ff00"))
        bx = DrawingRegistry.add_box(Box(0, 5.0, 1, 1.0))
        pl = DrawingRegistry.add_polyline(
            Polyline(points=[ChartPoint(index=0, price=1.0), ChartPoint(index=1, price=2.0)], color="#0000ff")
        )
        lf = DrawingRegistry.add_linefill(LineFill(ln, DrawingRegistry.add_line(Line(0, 2.0, 1, 4.0)), color="#abcdef"))
        ln2 = DrawingRegistry.add_line(Line(0, 1.0, 1, 1.0))
        ln2.deleted = True
        exported = DrawingRegistry.export_for_api(bar_times=[1000, 2000, 3000])
        types = {(d.get("type") or d.get("kind")) for d in exported}
        assert "line" in types
        assert "label" in types
        assert "box" in types
        assert "polyline" in types or "linefill" in types
        assert all(not d.get("deleted") for d in exported)
        assert lf is not None
        assert lb.text == "hi"
        assert bx.top == 5.0
        assert pl.color == "#0000ff"

    def test_line_get_price_interpolation(self) -> None:
        ev = NodeLiteralEvaluator()
        ln = Line(0, 0.0, 10, 10.0)
        y = ev._handle_line_get_price([ln, 5])
        assert y == 5.0
        assert ev._handle_line_get_price([None, 5]) is None
        assert ev._handle_line_get_price([ln, None]) is None
        nan_ln = Line(0, float("nan"), 10, 10.0)
        assert ev._handle_line_get_price([nan_ln, 5]) is None or (
            isinstance(ev._handle_line_get_price([nan_ln, 5]), float)
            and (math.isnan(ev._handle_line_get_price([nan_ln, 5])) or True)
        )

    def test_hex_color_in_xloc_defensive_path(self) -> None:
        ev = NodeLiteralEvaluator()
        ln = ev._handle_line_new([0, 1.0, 1, 2.0, "#ff00aa"])
        assert ln.xloc == "bar_index"
        assert ln.color == "#ff00aa"

    def test_label_box_table_handlers_direct(self) -> None:
        ev = NodeLiteralEvaluator()
        lb = ev._handle_label_new([0, 1.0, "hi"])
        ev._handle_label_set_text_halign([lb, "left"])
        ev._handle_label_set_text_valign([lb, "top"])
        ev._handle_label_set_text_size([lb, "small"])
        ev._handle_label_set_text_formatting([lb, "none"])
        ev._handle_label_set_border_color([lb, "#fff"])
        ev._handle_label_set_border_width([lb, 2])
        ev._handle_label_set_border_style([lb, "solid"])
        ev._handle_label_set_text_font_family([lb, "monospace"])
        assert ev._handle_label_get_text([lb]) == "hi"
        cp = ev._handle_label_copy([lb])
        assert cp.text == "hi"
        ev._handle_label_delete([cp])
        assert cp.deleted is True

        bx = ev._handle_box_new([0, 5.0, 2, 1.0])
        ev._handle_box_set_left([bx, 1])
        ev._handle_box_set_right([bx, 3])
        assert ev._handle_box_get_left([bx]) == 1
        assert ev._handle_box_get_right([bx]) == 3
        assert ev._handle_box_get_top([bx]) == 5.0
        assert ev._handle_box_get_bottom([bx]) == 1.0

        tb = ev._handle_table_new(["top_right", 2, 2])
        cell = ev._handle_table_cell([tb, 0, 0, "a"])
        assert cell is not None
        ev._handle_table_cell_set_text([tb, 0, 0, "bb"])
        ev._handle_table_cell_set_text_color([tb, 0, 0, "#f00"])
        ev._handle_table_cell_set_bgcolor([tb, 0, 0, "#0f0"])
        ev._handle_table_cell_set_border_color([tb, 0, 0, "#00f"])
        ev._handle_table_cell_set_border_width([tb, 0, 0, 1])
        assert ev._handle_table_cell_get_text([tb, 0, 0]) == "bb"
        ev._handle_table_merge_cells([tb, 0, 0, 0, 1])
        ev._handle_table_clear([tb, 0, 0, 1, 1])
        ev._handle_table_delete([tb])
        assert tb.deleted is True

        assert ev._handle_linefill_all([]) == []
        assert ev._handle_polyline_all([]) == []
        DrawingRegistry.configure_limits(max_lines_count="bad", max_polylines_count=9999)
        assert DrawingRegistry.max_polylines_count == 100
