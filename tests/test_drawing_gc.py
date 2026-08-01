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

"""Drawing garbage collection (max_lines/labels/boxes/polylines_count)."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.helper import parse


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


class TestDrawingGarbageCollection:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def teardown_method(self) -> None:
        DrawingRegistry.reset()

    def test_default_limit_is_50(self) -> None:
        assert DrawingRegistry.limits_dict() == {
            "max_lines_count": 50,
            "max_labels_count": 50,
            "max_boxes_count": 50,
            "max_polylines_count": 50,
        }

    def test_label_gc_keeps_newest(self) -> None:
        DrawingRegistry.configure_limits(max_labels_count=3)
        ev = NodeLiteralEvaluator()
        for i in range(5):
            _eval(ev, f"label.new({i}, {float(i)}, 'L{i}')")
        active = _eval(ev, "label.all")
        assert len(active) == 3
        assert [lb.text for lb in active] == ["L2", "L3", "L4"]
        # Registry still holds deleted shells
        assert len(DrawingRegistry.labels) == 5
        assert sum(1 for lb in DrawingRegistry.labels if lb.deleted) == 2

    def test_indicator_declaration_sets_limits(self) -> None:
        ev = NodeLiteralEvaluator()
        ev.evaluate_script(
            'indicator("gc", max_labels_count=2, max_lines_count=1)\n'
            "label.new(0, 1.0, 'a')\n"
            "label.new(1, 2.0, 'b')\n"
            "label.new(2, 3.0, 'c')\n"
            "line.new(0, 1.0, 1, 2.0)\n"
            "line.new(1, 2.0, 2, 3.0)\n"
        )
        assert DrawingRegistry.max_labels_count == 2
        assert DrawingRegistry.max_lines_count == 1
        assert len(_eval(ev, "label.all")) == 2
        assert len(_eval(ev, "line.all")) == 1
        assert _eval(ev, "label.all")[-1].text == "c"

    def test_export_skips_gc_deleted(self) -> None:
        DrawingRegistry.configure_limits(max_labels_count=2)
        ev = NodeLiteralEvaluator()
        for i in range(4):
            _eval(ev, f"label.new({i}, 1.0, 'x{i}')")
        exported = DrawingRegistry.export_for_api(bar_times=[0, 1, 2, 3, 4])
        labels = [d for d in exported if d.get("type") == "label"]
        assert len(labels) == 2

    def test_hard_cap_polylines_100(self) -> None:
        DrawingRegistry.configure_limits(max_polylines_count=9999)
        assert DrawingRegistry.max_polylines_count == 100

    def test_gc_exported_drawings_list(self) -> None:
        raw = [
            {"kind": "label", "x": i, "y": 1.0, "text": f"t{i}"} for i in range(5)
        ] + [
            {"type": "bgcolor", "color": "red"},
            {"type": "line", "t1": 0, "p1": 1, "t2": 1, "p2": 2},
            {"type": "line", "t1": 1, "p1": 2, "t2": 2, "p2": 3},
            {"type": "line", "t1": 2, "p1": 3, "t2": 3, "p2": 4},
        ]
        out = DrawingRegistry.gc_exported_drawings(
            raw,
            {
                "max_lines_count": 2,
                "max_labels_count": 2,
                "max_boxes_count": 50,
                "max_polylines_count": 50,
            },
        )
        labels = [d for d in out if (d.get("kind") or d.get("type")) == "label"]
        lines = [d for d in out if d.get("type") == "line"]
        bg = [d for d in out if d.get("type") == "bgcolor"]
        assert len(labels) == 2
        assert labels[0]["text"] == "t3"
        assert labels[1]["text"] == "t4"
        assert len(lines) == 2
        assert len(bg) == 1  # non-geometry preserved
