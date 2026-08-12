# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""export_for_api must keep lines that use bar_index past the last bar.

Classic Pine pattern on barstate.islast::

    line.new(bar_index, low, bar_index + 1, high)

Previously ``_export_x_to_time`` returned None for bar_index+1, and the whole
line was skipped — AXIS never received geometry.
"""

from __future__ import annotations

from pynescript.ast.evaluator.builtins.drawing import (
    DrawingRegistry,
    Line,
    LineFill,
    _export_x_to_time,
)


class TestExportXToTime:
    def test_in_range_maps_to_bar_time(self) -> None:
        times = [1_700_000_000, 1_700_086_400, 1_700_172_800]
        assert _export_x_to_time(0, "bar_index", times) == times[0]
        assert _export_x_to_time(2, "bar_index", times) == times[2]

    def test_bar_index_plus_one_extrapolates(self) -> None:
        times = [1_700_000_000, 1_700_086_400]
        # period = 86400; last idx 1 → idx 2 is last + period
        assert _export_x_to_time(2, "bar_index", times) == 1_700_086_400 + 86_400
        assert _export_x_to_time(3, "bar_index", times) == 1_700_086_400 + 2 * 86_400

    def test_bar_time_xloc_passthrough(self) -> None:
        times = [1_700_000_000]
        assert _export_x_to_time(1_700_000_999, "bar_time", times) == 1_700_000_999

    def test_empty_times_returns_bar_index(self) -> None:
        assert _export_x_to_time(5, "bar_index", []) == 5


class TestExportForApiLastBarLine:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def test_line_bar_index_plus_one_on_last_bar_is_exported(self) -> None:
        times = [1_700_000_000 + i * 86_400 for i in range(5)]
        last = len(times) - 1
        DrawingRegistry.lines.append(
            Line(
                x1=last,
                y1=100.0,
                x2=last + 1,
                y2=110.0,
                xloc="bar_index",
                color="#F23645",
                width=1,
                style="solid",
                extend="none",
            )
        )
        out = DrawingRegistry.export_for_api(times)
        assert len(out) == 1
        d = out[0]
        assert d["type"] == "line"
        assert d["t1"] == times[last]
        assert d["t2"] == times[last] + 86_400
        assert d["p1"] == 100.0
        assert d["p2"] == 110.0


class TestFoldCompileDrawingMutations:
    def test_set_xy2_updates_line_handle(self) -> None:
        from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

        line = {"kind": "line", "x1": 0, "y1": 10.0, "x2": 1, "y2": 11.0}
        events = [
            line,
            {
                "kind": "set",
                "method": "line.set_xy2",
                "target": line,
                "args": [5, 20.0],
            },
            {"kind": "bgcolor", "color": "red"},
        ]
        out = DrawingRegistry.fold_compile_drawing_mutations(events)
        assert len(out) == 2
        geom = [d for d in out if d.get("kind") == "line"][0]
        assert geom["x2"] == 5
        assert geom["y2"] == 20.0
        assert any(d.get("kind") == "bgcolor" for d in out)
        assert not any(d.get("kind") == "set" for d in out)

    def test_delete_marks_target_omitted(self) -> None:
        from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry

        line = {"kind": "line", "x1": 0, "y1": 1.0, "x2": 2, "y2": 3.0}
        events = [
            line,
            {"kind": "set", "method": "line.delete", "target": line, "args": []},
        ]
        out = DrawingRegistry.fold_compile_drawing_mutations(events)
        assert out == []


class TestExportLineFill:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def test_linefill_exports_quad_between_two_lines(self) -> None:
        times = [1_700_000_000 + i * 86_400 for i in range(4)]
        l1 = Line(x1=0, y1=10.0, x2=3, y2=12.0, xloc="bar_index", color="#f00")
        l2 = Line(x1=0, y1=5.0, x2=3, y2=7.0, xloc="bar_index", color="#0f0")
        DrawingRegistry.lines.extend([l1, l2])
        DrawingRegistry.linefills.append(
            LineFill(line1=l1, line2=l2, color="rgba(41,98,255,0.2)")
        )
        out = DrawingRegistry.export_for_api(times)
        fills = [d for d in out if d.get("type") == "linefill"]
        assert len(fills) == 1
        f = fills[0]
        assert f["t1"] == times[0]
        assert f["t2"] == times[3]
        assert f["p1"] == 10.0
        assert f["p2"] == 12.0
        assert f["t3"] == times[0]
        assert f["t4"] == times[3]
        assert f["p3"] == 5.0
        assert f["p4"] == 7.0
        assert "rgba" in str(f["color"]) or str(f["color"]).startswith("#")
