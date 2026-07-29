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

"""Small locks for implemented Pine v6 surfaces that are easy to regress.

These assert *current* supported behavior (not future P0/P1 gap fills).
See docs/perf_round4/08_v6_coverage_matrix.md.
"""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse


def _seed(ev: NodeLiteralEvaluator) -> None:
    for key, val in {
        "close": 100.0,
        "open": 99.0,
        "high": 101.0,
        "low": 98.0,
        "volume": 1000.0,
        "time": 1_700_000_000_000,
        "bar_index": 10,
        "hl2": 99.5,
        "hlc3": 99.666,
        "ohlc4": 99.5,
        "hlcc4": 99.75,
        "syminfo.tickerid": "BTCUSD",
    }.items():
        ev.context.setdefault(key, val)


def _run(src: str) -> NodeLiteralEvaluator:
    tree = parse(src)
    ev = NodeLiteralEvaluator()
    _seed(ev)
    ev.visit(tree)
    return ev


def test_enum_member_compare_runtime() -> None:
    """EnumDef + member equality (v6) evaluates without error."""
    _run(
        """//@version=6
indicator("enum lock")
enum Side
    buy = "B"
    sell = "S"
s = Side.buy
plot(s == Side.buy ? 1 : 0)
"""
    )


def test_timeframe_seconds_helpers() -> None:
    """timeframe.in_seconds / from_seconds are callable builtins."""
    _run(
        """//@version=6
indicator("tf lock")
sec = timeframe.in_seconds("60")
tf = timeframe.from_seconds(sec)
plot(sec)
"""
    )


def test_map_put_get_runtime() -> None:
    """map.new + put/get (typed specialize) returns stored value path."""
    _run(
        """//@version=6
indicator("map lock")
m = map.new<string, float>()
map.put(m, "k", 1.5)
plot(map.get(m, "k"))
"""
    )


def test_log_info_single_arg() -> None:
    """log.info(message) single-arg form is supported (multi-arg is a known gap)."""
    _run(
        """//@version=6
indicator("log lock")
log.info("hello")
plot(1)
"""
    )


def test_polyline_new_delete() -> None:
    """polyline.new / delete (minimal surface) works."""
    _run(
        """//@version=6
indicator("polyline lock")
pts = array.from(chart.point.from_index(bar_index, close))
pl = polyline.new(pts)
polyline.delete(pl)
plot(1)
"""
    )


def test_export_enum_registers_on_library() -> None:
    """export enum is registered on the library module exports."""
    src = """//@version=6
library("EnumLib")
export enum Mode
    fast = 1
    slow = 2
"""
    ev = NodeLiteralEvaluator()
    ev.evaluate_script(src)
    mod = ev.lookup_library(name="EnumLib")
    assert mod is not None
    assert "Mode" in mod.exports
    mode = mod.exports["Mode"]
    assert isinstance(mode, dict)
    assert "fast" in mode
