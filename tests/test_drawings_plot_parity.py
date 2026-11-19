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
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Drawings + plot parity: .all collections, merge_cells, time funcs, plot family.

Pins the formerly-🔄-partial inventory rows as ✅ implemented on the
interpret host (Runtime.run): drawing `.all` views, `table.merge_cells`,
`time`/`time_close`, `last_bar_index`/`last_bar_time`, and the full
`plot*`/`hline`/`fill`/`bgcolor`/`barcolor` family via PlotRegistry export.
"""

from __future__ import annotations


def _bars(n: int = 5) -> list[dict]:
    out = []
    for i in range(n):
        c = 100 + i
        o = c - 0.5 if i % 2 == 0 else c + 0.5
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": o,
                "high": max(o, c) + 1,
                "low": min(o, c) - 1,
                "close": c,
                "volume": 1000,
            }
        )
    return out


def test_all_collections_and_merge_cells() -> None:
    from pynescript.runtime import Runtime

    src = """//@version=6
indicator("t")
l1 = line.new(bar_index, high, bar_index + 1, low)
l2 = line.new(bar_index, high, bar_index + 1, low)
box.new(bar_index, high, bar_index + 1, low)
label.new(bar_index, high, "hi")
t = table.new(position.top_right, 2, 2)
table.cell(t, 0, 0, "a")
table.merge_cells(t, 0, 0, 0, 1)
plot(array.size(line.all), "nl")
plot(array.size(box.all), "nb")
plot(array.size(label.all), "nla")
plot(array.size(table.all), "nt")
plot(array.size(polyline.all), "np")
plot(array.size(linefill.all), "nf")
"""
    res = Runtime().run(src, _bars(5))
    assert res["series"]["nl"] == [2, 4, 6, 8, 10]
    assert res["series"]["nb"] == [1, 2, 3, 4, 5]
    assert res["series"]["nla"] == [1, 2, 3, 4, 5]
    assert res["series"]["nt"] == [1, 2, 3, 4, 5]
    assert res["series"]["np"] == [0, 0, 0, 0, 0]
    assert res["series"]["nf"] == [0, 0, 0, 0, 0]
    # drawings export carries the created objects
    assert len(res["drawings"]) == 10 + 5 + 5 + 5  # lines x2 + boxes + labels + tables per bar


def test_time_and_last_bar() -> None:
    from pynescript.runtime import Runtime

    src = """//@version=6
indicator("t2")
t = time(timeframe.period)
tc = time_close(timeframe.period)
plot(last_bar_index, "lbi")
plot(last_bar_time, "lbt")
plot(t, "tt")
"""
    res = Runtime().run(src, _bars(5))
    assert res["series"]["lbi"] == [4, 4, 4, 4, 4]
    assert res["series"]["lbt"] == [1700345600.0] * 5
    assert len(res["series"]["tt"]) == 5


def test_plot_family_kinds() -> None:
    from pynescript.runtime import Runtime

    src = """//@version=6
indicator("t3", overlay=true)
p1 = plot(close, "p1")
p2 = plot(open, "p2")
fill(p1, p2, color=color.red)
hline(100, "hl")
bgcolor(color.new(color.blue, 90))
barcolor(close > open ? color.green : color.red)
plotshape(close > open, style=shape.triangleup, location=location.abovebar, color=color.green)
plotchar(close > open, char="A", location=location.belowbar, color=color.blue)
plotbar(open, high, low, close)
plotcandle(open, high, low, close)
plotarrow(close - open)
"""
    res = Runtime().run(src, _bars(5))
    kinds = {v.get("kind") for v in res["plot_meta"].values()}
    assert {
        "plot",
        "fill",
        "hline",
        "bgcolor",
        "barcolor",
        "plotshape",
        "plotchar",
        "plotbar",
        "plotcandle",
        "plotarrow",
    } <= kinds
