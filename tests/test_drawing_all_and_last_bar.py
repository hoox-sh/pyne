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

"""Drawing *.all collections, last_bar_*, and risk max_position_size."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.helper import parse


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


class TestDrawingAllCollections:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def test_label_all_tracks_created_labels(self) -> None:
        ev = NodeLiteralEvaluator()
        DrawingRegistry.reset()
        _eval(ev, "label.new(0, 1.0, 'a')")
        _eval(ev, "label.new(1, 2.0, 'b')")
        all_labels = _eval(ev, "label.all")
        assert isinstance(all_labels, list)
        assert len(all_labels) == 2
        assert all_labels[0].text == "a"
        assert all_labels[1].text == "b"

    def test_line_box_table_polyline_all(self) -> None:
        ev = NodeLiteralEvaluator()
        DrawingRegistry.reset()
        _eval(ev, "line.new(0, 1.0, 1, 2.0)")
        _eval(ev, "box.new(0, 3.0, 1, 0.0)")
        _eval(ev, "table.new('top_left', 2, 2)")
        _eval(ev, "polyline.new(array.from(chart.point.new(0, 0, 1.0)))")
        assert len(_eval(ev, "line.all")) == 1
        assert len(_eval(ev, "box.all")) == 1
        assert len(_eval(ev, "table.all")) == 1
        assert len(_eval(ev, "polyline.all")) == 1

    def test_deleted_objects_excluded_from_all(self) -> None:
        ev = NodeLiteralEvaluator()
        DrawingRegistry.reset()
        ev.evaluate_script("lbl = label.new(0, 1.0, 'x')\nlabel.delete(lbl)\n")
        assert len(_eval(ev, "label.all")) == 0

    def test_linefill_all_empty_without_objects(self) -> None:
        ev = NodeLiteralEvaluator()
        DrawingRegistry.reset()
        assert _eval(ev, "linefill.all") == []


class TestLastBarVars:
    def test_last_bar_defaults_to_bar_index_and_time(self) -> None:
        ev = NodeLiteralEvaluator()
        ev.context["bar_index"] = 42
        ev.context["time"] = 1_700_000_000_000
        assert _eval(ev, "last_bar_index") == 42
        assert _eval(ev, "last_bar_time") == 1_700_000_000_000

    def test_last_bar_explicit_context_overrides(self) -> None:
        ev = NodeLiteralEvaluator()
        ev.context["bar_index"] = 10
        ev.context["time"] = 100
        ev.context["last_bar_index"] = 99
        ev.context["last_bar_time"] = 999
        assert _eval(ev, "last_bar_index") == 99
        assert _eval(ev, "last_bar_time") == 999


class TestRiskMaxPositionSize:
    def test_entry_qty_capped_by_max_position_size_percent(self) -> None:
        """max_position_size(percent) limits qty as % of equity / price."""
        ev = NodeLiteralEvaluator()
        ev.context["close"] = 100.0
        ev.context["bar_index"] = 0
        # 1% of 100000 equity = 1000 capital → at price 100 → max 10 contracts
        _eval(ev, "strategy.risk.max_position_size(1.0)")
        _eval(ev, "strategy.entry('L', strategy.long, 100.0)")
        assert _eval(ev, "strategy.position_size") == 10.0
