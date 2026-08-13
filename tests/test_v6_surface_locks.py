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


def test_array_binary_search_udt_sort_field_lock() -> None:
    """August 2026: binary_search on UDT arrays via sort_field (name + default 0)."""
    ev = _run(
        """//@version=6
indicator("bsearch lock")
type Data
    float price
    int timestamp
a = array.new<Data>(0)
array.push(a, Data.new(3.0, 30))
array.push(a, Data.new(1.0, 10))
array.push(a, Data.new(2.0, 20))
array.sort(a, sort_field="timestamp")
found = array.binary_search(a, 20, "timestamp")
deflt = array.binary_search(a, 1.0)
plot(found)
plot(deflt)
"""
    )
    assert ev.context["found"] == 1
    # default sort_field=0 is `price`; after sort by timestamp order is 1,2,3
    assert ev.context["deflt"] == 0


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


def test_log_info_printf_varargs() -> None:
    """log.info printf ``%s`` style (corpus residual) formats args."""
    get_logger().clear()
    _run(
        """//@version=6
indicator("log printf")
log.info("x=%s y=%s", close, volume)
log.warning("w=%f", open)
plot(1)
"""
    )
    logs = get_logger().get_logs()
    assert any("x=100" in msg and "y=1000" in msg for _, msg in logs)
    assert any(level == "WARNING" and "w=" in msg and "99" in msg for level, msg in logs)


def test_log_format_join_fallback() -> None:
    """Multi-arg log without placeholders joins parts (no silent drop)."""
    from pynescript.ast.evaluator.builtins.logging import format_log_message

    assert format_log_message("hi", 1, 2) == "hi 1 2"
    assert format_log_message("x=%s", None) == "x=na"
    assert format_log_message("a={0}", 7) == "a=7"


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


def test_ta_official_aliases_and_ao_aroon() -> None:
    """ta.willr/ad/pvt aliases + ta.ao / ta.aroon produce values on Runtime."""
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101 + i * 0.2,
            "low": 99 + i * 0.05,
            "close": 100.5 + i * 0.1,
            "volume": 1000 + i,
            "time": i * 86_400_000,
        }
        for i in range(80)
    ]
    src = """//@version=6
indicator("ta p1")
w = ta.willr(14)
ad = ta.ad
pvt = ta.pvt
ao = ta.ao
[adown, aup] = ta.aroon(14)
plot(w)
plot(ao)
plot(aup)
"""
    r = Runtime().run(src, bars, mode="interpret")
    assert "error" not in r, r.get("error")
    series = r.get("series") or {}
    assert len(series) >= 2
    # last values should be finite numbers
    for vals in series.values():
        assert vals
        assert vals[-1] is not None


def test_import_stub_emits_warning() -> None:
    """Unresolved TradingView imports soft-stub and log a warning."""
    from backend.runtime import Runtime
    from pynescript.ast.evaluator.builtins.logging import get_logger

    get_logger().clear()
    bars = [
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "time": i}
        for i in range(3)
    ]
    src = """//@version=6
indicator("imp")
import TradingView/MissingLib/1 as mlib
plot(1)
"""
    r = Runtime().run(src, bars, mode="interpret")
    assert "error" not in r, r.get("error")
    logs = get_logger().get_logs()
    assert any("Unresolved import" in msg and "MissingLib" in msg for _, msg in logs)


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


def test_chart_is_pnf_and_visible_bar_times() -> None:
    """chart.is_pnf + left/right_visible_bar_time (P0 chart host surface)."""
    from backend.runtime import Runtime

    bars = [
        {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "time": 1000 + i * 100}
        for i in range(5)
    ]
    src = """//@version=6
indicator("chart p0")
plot(chart.is_pnf ? 1 : 0)
plot(chart.left_visible_bar_time)
plot(chart.right_visible_bar_time)
plot(chart.is_standard ? 1 : 0)
"""
    r = Runtime().run(src, bars, mode="interpret")
    assert "error" not in r, r.get("error")
    series = r.get("series") or {}
    # is_pnf false by default; is_standard true
    assert series["plot_0"][-1] == 0
    assert series["plot_1"][-1] == 1000
    assert series["plot_2"][-1] == 1000 + 4 * 100
    assert series["plot_3"][-1] == 1


def test_strategy_cash_default_qty() -> None:
    """strategy() default_qty_type=cash sizes entry from cash / price."""
    from backend.runtime import Runtime

    bars = [
        {"open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0, "volume": 1.0, "time": i}
        for i in range(3)
    ]
    src = """//@version=6
strategy("cash", overlay=true, initial_capital=100000, default_qty_type=strategy.cash, default_qty_value=5000)
if bar_index == 0
    strategy.entry("L", strategy.long)
plot(strategy.position_size)
"""
    r = Runtime().run(src, bars, mode="interpret")
    assert "error" not in r, r.get("error")
    # 5000 cash / 50 price → 100 contracts
    assert abs(float((r.get("plots") or [0])[-1]) - 100.0) < 1e-6
