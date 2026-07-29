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

"""Locks for Pine v6 surfaces (including Round-5 P0 gap fills).

See docs/perf_round4/08_v6_coverage_matrix.md.
"""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.logging import get_logger
from pynescript.ast.helper import parse
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry


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
    """log.info(message) single-arg form is supported."""
    get_logger().clear()
    _run(
        """//@version=6
indicator("log lock")
log.info("hello")
plot(1)
"""
    )
    logs = get_logger().get_logs()
    assert any(level == "INFO" and "hello" in msg for level, msg in logs)


def test_log_info_format_varargs() -> None:
    """log.info format + varargs (P0) — no TypeError, message formatted."""
    get_logger().clear()
    _run(
        """//@version=6
indicator("log multi")
log.info("x={0} y={1}", close, volume)
plot(1)
"""
    )
    logs = get_logger().get_logs()
    assert any("x=100" in msg and "y=1000" in msg for _, msg in logs)


def test_polyline_new_delete() -> None:
    """polyline.new / delete (minimal surface) works."""
    DrawingRegistry.reset()
    _run(
        """//@version=6
indicator("polyline lock")
pts = array.from(chart.point.from_index(bar_index, close))
pl = polyline.new(pts)
polyline.delete(pl)
plot(1)
"""
    )


def test_polyline_setters_and_get_points() -> None:
    """polyline.set_* / get_points (P0 surface)."""
    DrawingRegistry.reset()
    _run(
        """//@version=6
indicator("polyline set")
pts = array.from(chart.point.from_index(bar_index, close))
pl = polyline.new(pts)
polyline.set_line_color(pl, color.red)
polyline.set_line_width(pl, 3)
polyline.set_curved(pl, true)
got = polyline.get_points(pl)
plot(array.size(got))
"""
    )
    active = [p for p in DrawingRegistry.polylines if not p.deleted]
    assert active
    assert active[0].width == 3
    assert active[0].curved is True


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


def test_strategy_qty_constants_registered() -> None:
    """strategy.fixed / percent_of_equity / cash are zero-arg constants."""
    ev = NodeLiteralEvaluator()
    bmap = ev._build_builtin_map()
    assert "strategy.fixed" in bmap
    assert "strategy.percent_of_equity" in bmap
    assert "strategy.cash" in bmap
    assert bmap["strategy.fixed"]([], None) == "fixed"
    assert bmap["strategy.percent_of_equity"]([], None) == "percent_of_equity"


def test_strategy_percent_of_equity_default_qty() -> None:
    """strategy() default_qty_type=percent_of_equity sizes entry from equity."""
    ev = _run(
        """//@version=6
strategy("pct", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
if bar_index == 10
    strategy.entry("L", strategy.long)
plot(strategy.position_size)
"""
    )
    # 10% of 100000 at price 100 → 100 contracts
    assert abs(float(ev._strategy_state.position_size) - 100.0) < 1e-6


def test_unknown_attr_is_na_not_truthy_string() -> None:
    """Unknown host attrs resolve to na (falsy), not a truthy qualified string."""
    from backend.runtime import Chart
    from pynescript.ast.node import Attribute
    from pynescript.ast.node import Load
    from pynescript.ast.node import Name

    ev = NodeLiteralEvaluator()
    _seed(ev)
    ev.context["chart"] = Chart()
    n = Attribute(value=Name(id="chart", ctx=Load()), attr="totally_missing_attr", ctx=Load())
    assert ev.visit(n) is None


def test_chart_is_heikinashi_alias() -> None:
    """chart.is_heikinashi binds (Pine spelling) and is false by default."""
    from backend.runtime import Chart
    from pynescript.ast.node import Attribute
    from pynescript.ast.node import Load
    from pynescript.ast.node import Name

    ev = NodeLiteralEvaluator()
    _seed(ev)
    c = Chart()
    assert c.is_heikinashi is False
    ev.context["chart"] = c
    n = Attribute(value=Name(id="chart", ctx=Load()), attr="is_heikinashi", ctx=Load())
    assert ev.visit(n) is False
    c.is_heikin_ashi = True
    c.is_heikinashi = True
    assert ev.visit(n) is True
