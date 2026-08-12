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
