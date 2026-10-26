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

"""Compile emit-path coverage via Runtime mode=compile / auto scripts.

Targets uncovered branches in compiler.py: visit_Call / _unpack_call /
_cross_pair, _emit_array_or_matrix, assign/reassign/augassign, switch/if
walrus arms, UDT/map/drawing/strategy emit, and _fold_const helpers.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pynescript.compiler.compiler import CompilerVisitor
from pynescript.runtime import Runtime


def _bars(n: int = 32, *, start: float = 100.0) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": start + i * 0.15,
            "high": start + i * 0.15 + 1.0,
            "low": start + i * 0.15 - 1.0,
            "close": start + i * 0.15 + 0.4,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


def _run(src: str, n: int = 32, *, mode: str = "compile") -> dict:
    return Runtime(symbol="EMIT").run(src, _bars(n), mode=mode)


def _ok(out: dict) -> dict:
    assert "error" not in out or out.get("error") is None, out.get("error")
    return out


def _series(out: dict) -> dict:
    return out.get("series") or {}


def _last(out: dict, name: str) -> float:
    s = _series(out)[name]
    return float(np.asarray(s, dtype=np.float64)[-1])


# ---------------------------------------------------------------------------
# Pure CompilerVisitor helpers (no full compile)
# ---------------------------------------------------------------------------


class TestFoldConstHelpers:
    def test_fold_const_literals_and_display(self) -> None:
        assert CompilerVisitor._fold_const(3) == 3
        assert CompilerVisitor._fold_const(True) is True
        assert CompilerVisitor._fold_const(1.5) == 1.5
        assert CompilerVisitor._fold_const('"abc"') == "abc"
        assert CompilerVisitor._fold_const("'x'") == "x"
        assert CompilerVisitor._fold_const("display.pane") == 1
        assert CompilerVisitor._fold_const("display.data_window") == 2
        assert CompilerVisitor._fold_const("display.pane + display.data_window") == 3
        assert CompilerVisitor._fold_const("display.pane | display.data_window") == 3
        assert CompilerVisitor._fold_const("not_a_const") is None
        assert CompilerVisitor._fold_const(None) is None
        assert CompilerVisitor._fold_const([]) is None
        assert CompilerVisitor._fold_const("x" * 10_000) is None

    def test_literal_str_and_coerce_attrs(self) -> None:
        assert CompilerVisitor._literal_str("'hi'") == "hi"
        assert CompilerVisitor._literal_str('"mid"') == "mid"
        assert CompilerVisitor._literal_str("") == ""
        assert CompilerVisitor._literal_str("dynamic", default="d") == "dynamic"
        assert CompilerVisitor._coerce_folded_attr("linewidth", 3) == 3
        assert CompilerVisitor._coerce_folded_attr("linewidth", 1) is None  # default omitted
        assert CompilerVisitor._coerce_folded_attr("display", 2) == 2
        assert CompilerVisitor._coerce_folded_attr("display", 15) is None
        assert CompilerVisitor._coerce_folded_attr("style", "style_histogram") == "style_histogram"
        assert CompilerVisitor._coerce_folded_attr("style", "style_line") is None
        assert CompilerVisitor._coerce_folded_attr("trackprice", True) is True
        # offset is a wire int attr — float literals fold via int()
        assert CompilerVisitor._coerce_folded_attr("offset", 2.5) == 2
        assert CompilerVisitor._coerce_folded_attr("offset", 0) is None


# ---------------------------------------------------------------------------
# Array / matrix emit
# ---------------------------------------------------------------------------


class TestArrayMatrixEmit:
    def test_array_lifecycle_and_stats(self) -> None:
        src = """//@version=6
indicator("arr")
a = array.from(3.0, 1.0, 2.0, 2.0)
array.sort(a, order.descending)
array.reverse(a)
b = array.copy(a)
c = array.slice(a, 0, 2)
array.concat(a, c)
array.unshift(a, 9.0)
p = array.pop(a)
s = array.shift(a)
array.set(a, 0, 7.0)
g = array.get(a, 0)
inc = array.includes(a, 7.0)
j = array.join(a, ",")
r = array.range(a)
avg = array.avg(a)
sd = array.stdev(a)
vr = array.variance(a)
md = array.mode(a)
array.remove(a, 0)
array.clear(a)
plot(p + nz(s, 0.0) + g + (inc ? 1.0 : 0.0) + r + avg, "p")
plot(array.size(a), "sz")
plot(str.length(j), "jl")
plot(sd + vr + md, "stats")
"""
        out = _ok(_run(src, 24))
        assert "p" in _series(out)
        assert _last(out, "sz") == 0.0

    def test_array_new_typed_and_method_form(self) -> None:
        src = """//@version=6
indicator("an")
a = array.new_float(0)
array.push(a, close)
array.push(a, open)
plot(array.size(a), "s")
plot(array.get(a, 0), "g")
a.push(high)
plot(a.size(), "s2")
ln = array.new_line(0)
lb = array.new_label(0)
bx = array.new_box(0)
plot(array.size(ln) + array.size(lb) + array.size(bx), "z")
"""
        out = _ok(_run(src, 20))
        assert _last(out, "s") == 2.0
        assert _last(out, "s2") == 3.0

    def test_matrix_mutate_and_queries(self) -> None:
        src = """//@version=6
indicator("mat")
m = matrix.new<float>(2, 2, 1.0)
matrix.set(m, 0, 1, 3.0)
x = matrix.get(m, 0, 1)
matrix.fill(m, 2.0)
matrix.add_row(m, 2, array.from(9.0, 8.0))
matrix.add_col(m, 2, array.from(1.0, 2.0, 3.0))
matrix.swap_rows(m, 0, 1)
matrix.swap_columns(m, 0, 1)
matrix.remove_row(m, 0)
matrix.remove_col(m, 0)
matrix.reshape(m, 2, 2)
matrix.sort(m)
matrix.reverse(m)
row = matrix.row(m, 0)
col = matrix.col(m, 0)
sub = matrix.submatrix(m, 0, 1, 0, 1)
e = matrix.eigenvalues(m)
v = matrix.eigenvectors(m)
plot(x + matrix.rows(m) + matrix.columns(m) + matrix.avg(m) + matrix.sum(m), "p")
plot(matrix.max(m) + matrix.min(m) + matrix.trace(m) + matrix.rank(m), "q")
plot(array.size(row) + array.size(col) + array.size(e) + array.size(v), "z")
"""
        out = _ok(_run(src, 16))
        assert math.isfinite(_last(out, "p"))

    def test_matrix_copy_and_kw_get(self) -> None:
        src = """//@version=6
indicator("mc")
m = matrix.new<float>(2, 2, 5.0)
m2 = matrix.copy(m)
matrix.set(m2, 1, 1, 9.0)
plot(matrix.get(m, row=0, column=0), "a")
plot(matrix.get(m2, 1, 1), "b")
"""
        out = _ok(_run(src, 12))
        assert _last(out, "a") == 5.0
        assert _last(out, "b") == 9.0


# ---------------------------------------------------------------------------
# Map / UDT / drawing emit
# ---------------------------------------------------------------------------


class TestMapUdtDrawingEmit:
    def test_map_full_surface(self) -> None:
        src = """//@version=6
indicator("map")
var m = map.new<string, float>()
map.put(m, "a", 1.0)
map.put(m, "b", close)
has = map.contains(m, "a")
k = map.keys(m)
v = map.values(m)
c = map.copy(m)
map.put_all(m, c)
map.remove(m, "a")
sz = map.size(m)
map.clear(m)
plot(has ? 1.0 : 0.0, "has")
plot(sz, "sz")
plot(map.size(m), "z")
plot(array.size(k) + array.size(v), "kv")
"""
        out = _ok(_run(src, 18))
        assert _last(out, "has") == 1.0
        assert _last(out, "z") == 0.0

    def test_map_method_form(self) -> None:
        src = """//@version=6
indicator("mm")
var m = map.new<string, float>()
m.put("k", close)
plot(m.get("k"), "g")
plot(m.size(), "s")
plot(m.contains("k") ? 1.0 : 0.0, "c")
"""
        out = _ok(_run(src, 15))
        assert abs(_last(out, "g") - _bars(15)[-1]["close"]) < 1e-9

    def test_udt_new_copy_field_aug(self) -> None:
        src = """//@version=6
indicator("udt")
type Pt
    float x = 0.0
    float y = 1.0
p = Pt.new(close, open)
p.x := high
p.y += 2.0
q = Pt.copy(p)
q.x := low
plot(p.x, "px")
plot(p.y, "py")
plot(q.x, "qx")
"""
        out = _ok(_run(src, 20))
        assert abs(_last(out, "px") - _bars(20)[-1]["high"]) < 1e-9
        assert abs(_last(out, "qx") - _bars(20)[-1]["low"]) < 1e-9

    def test_udt_method_outside_type(self) -> None:
        src = """//@version=6
indicator("udtm")
type Pt
    float x = 0.0
method add(Pt this, float d) =>
    this.x := this.x + d
    this
var p = Pt.new()
if barstate.isfirst
    p.add(1.5)
plot(p.x, "x")
"""
        out = _ok(_run(src, 12))
        assert abs(_last(out, "x") - 1.5) < 1e-9

    def test_udt_kw_new_and_bool_default(self) -> None:
        src = """//@version=6
indicator("udtk")
type Box
    float a = 1.0
    bool flag = false
    float b = 2.0
x = Box.new(flag=true, b=close)
plot(x.flag ? x.a + x.b : -1.0, "p")
"""
        out = _ok(_run(src, 16))
        assert abs(_last(out, "p") - (1.0 + _bars(16)[-1]["close"])) < 1e-9

    def test_drawing_line_label_box_table(self) -> None:
        src = """//@version=6
indicator("dr")
var table t = table.new(position.top_right, 2, 2)
if barstate.islast
    ln = line.new(bar_index - 1, high, bar_index, low, color=color.red, width=2)
    line.set_color(ln, color.blue)
    lb = label.new(bar_index, high, "hi")
    bx = box.new(bar_index - 1, high, bar_index, low)
    b2 = box.copy(bx)
    table.cell(t, 0, 0, "ok")
plot(close, "c")
"""
        out = _ok(_run(src, 14))
        assert "c" in _series(out)

    def test_chart_point_ctors(self) -> None:
        src = """//@version=6
indicator("cp")
pt = chart.point.from_index(bar_index, high)
pt2 = chart.point.new(time, bar_index, low)
pt3 = chart.point.copy(pt)
plot(pt.price, "p")
plot(pt2.price, "p2")
plot(pt3.price, "p3")
"""
        out = _ok(_run(src, 12))
        assert abs(_last(out, "p") - _bars(12)[-1]["high"]) < 1e-9


# ---------------------------------------------------------------------------
# Switch / if walrus / assign forms
# ---------------------------------------------------------------------------


class TestSwitchIfAssignEmit:
    def test_switch_expr_and_multi_pattern(self) -> None:
        src = """//@version=6
indicator("sw")
v = int(close) % 5
y = switch v
    1, 2 => 10
    3, 4 => 20
    => 0
z = switch
    close > open => 1
    close < open => -1
    => 0
plot(y, "y")
plot(z, "z")
"""
        out = _ok(_run(src, 24))
        assert _last(out, "y") in (0.0, 10.0, 20.0)

    def test_switch_walrus_and_aug_arms(self) -> None:
        src = """//@version=6
indicator("swa")
var float x = 0.0
y = switch close > open
    true =>
        x := close
        x
    => open
var float acc = 0.0
switch bar_index % 3
    0 =>
        acc += 1.0
    1 =>
        acc -= 0.5
    =>
        acc := acc
plot(y, "y")
plot(acc, "acc")
"""
        out = _ok(_run(src, 30))
        assert math.isfinite(_last(out, "y"))
        assert math.isfinite(_last(out, "acc"))

    def test_switch_nested_if_side_effects(self) -> None:
        src = """//@version=6
indicator("sni")
var float acc = 0.0
y = switch int(bar_index) % 2
    0 =>
        acc := acc + 1
        acc
    1 =>
        if close > open
            acc := acc + 2
            acc
        else
            acc
plot(y, "y")
"""
        out = _ok(_run(src, 28))
        assert _last(out, "y") >= 0.0

    def test_if_assign_multi_stmt_and_nested(self) -> None:
        src = """//@version=6
indicator("ifa")
x = if close > open
    a = close
    a + 1.0
else
    open
y = if close > open
    if high > close
        high
    else
        close
else
    low
z = 0.0
z := if close > open
    close
else
    open
plot(x, "x")
plot(y, "y")
plot(z, "z")
"""
        out = _ok(_run(src, 22))
        assert math.isfinite(_last(out, "x"))

    def test_augassign_ops_and_udt_field(self) -> None:
        src = """//@version=6
indicator("aug")
x = 2.0
x *= 3.0
x /= 2.0
x %= 3.0
x -= 0.5
type S
    float v = 0.0
var s = S.new()
if barstate.isfirst
    s.v += 1.0
plot(x, "x")
plot(s.v, "v")
"""
        out = _ok(_run(src, 10))
        # ((2*3)/2)%3 - 0.5 = 0 - 0.5 = -0.5
        assert abs(_last(out, "x") - (-0.5)) < 1e-9
        assert abs(_last(out, "v") - 1.0) < 1e-9

    def test_for_while_assign_and_enum(self) -> None:
        src = """//@version=6
indicator("fe")
s = 0.0
for i = 0 to 5
    s := s + i
t = 0.0
i = 0
while i < 4
    t := t + i
    i := i + 1
enum Mode
    a
    b
Mode m = Mode.a
m := close > open ? Mode.b : Mode.a
plot(s + t, "st")
plot(m == Mode.b ? 1 : 0, "m")
"""
        out = _ok(_run(src, 18))
        assert _last(out, "st") == 15.0 + 6.0  # 0..5 + 0..3

    def test_varip_and_reassign_series(self) -> None:
        src = """//@version=6
indicator("vp")
varip float x = 0.0
x := x + 1.0
var float y = 0.0
y := y + close
plot(x, "x")
plot(y, "y")
"""
        out = _ok(_run(src, 20))
        assert _last(out, "x") >= 1.0


# ---------------------------------------------------------------------------
# visit_Call: TA cross, unpack, methods, strategy
# ---------------------------------------------------------------------------


class TestCallCrossUnpackStrategy:
    def test_cross_pair_series_and_scalar(self) -> None:
        src = """//@version=6
indicator("cr")
plot(ta.crossover(close, open) ? 1 : 0, "x")
plot(ta.crossunder(close, 100.0) ? 1 : 0, "u")
plot(ta.cross(close, hl2) ? 1 : 0, "c")
plot(ta.crossover(ta.sma(close, 3), ta.sma(close, 5)) ? 1 : 0, "xs")
"""
        out = _ok(_run(src, 40))
        assert set(_series(out)) >= {"x", "u", "c", "xs"}

    def test_tuple_unpack_macd_bb_dmi(self) -> None:
        src = """//@version=6
indicator("tup")
[macdLine, signalLine, histLine] = ta.macd(close, 12, 26, 9)
[mid, upper, lower] = ta.bb(close, 20, 2.0)
[diplus, diminus, adx] = ta.dmi(14, 14)
plot(macdLine, "m")
plot(signalLine, "s")
plot(histLine, "h")
plot(mid, "mid")
plot(upper, "up")
plot(lower, "lo")
plot(adx, "adx")
"""
        out = _ok(_run(src, 50))
        assert math.isfinite(_last(out, "mid")) or math.isnan(_last(out, "mid"))

    def test_method_style_ta_and_series_max_min(self) -> None:
        src = """//@version=6
indicator("mta")
plot(close.sma(5), "s")
plot(close.ema(5), "e")
plot(close.rma(5), "r")
plot(close.max(10), "mx")
plot(close.min(10), "mn")
plot(nz(close[100], 0.0), "n")
plot(fixnan(close[100], 1.0), "f")
"""
        out = _ok(_run(src, 30))
        assert math.isfinite(_last(out, "s"))

    def test_ta_extras_surface(self) -> None:
        src = """//@version=6
indicator("tex")
plot(ta.cum(close), "cum")
plot(ta.sum(close, 5), "sum")
plot(ta.dev(close, 5), "dev")
plot(ta.variance(close, 5), "var")
plot(ta.correlation(close, open, 10), "corr")
plot(ta.hma(close, 9), "hma")
plot(ta.dema(close, 9), "dema")
plot(ta.tema(close, 9), "tema")
plot(ta.swma(close), "swma")
plot(ta.tr(), "tr")
plot(ta.valuewhen(close > open, close, 0), "vw")
plot(ta.pivothigh(2, 2), "ph")
plot(ta.pivotlow(2, 2), "pl")
plot(ta.alma(close, 9, 0.85, 6), "alma")
plot(ta.tsi(close, 13, 25), "tsi")
"""
        out = _ok(_run(src, 40))
        assert "cum" in _series(out)

    def test_udf_typed_and_series_arg(self) -> None:
        src = """//@version=6
indicator("udf")
f(float x, int n) =>
    x * n
g(src, len) =>
    ta.sma(src, len)
plot(f(close, 2), "p")
plot(g(close, 5), "g")
"""
        out = _ok(_run(src, 25))
        assert abs(_last(out, "p") - 2.0 * _bars(25)[-1]["close"]) < 1e-6

    def test_strategy_entry_exit_order_cancel(self) -> None:
        src = """//@version=6
strategy("st")
if bar_index == 3
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 8
    strategy.exit("XL", from_entry="L", profit=50, loss=25)
if bar_index == 12
    strategy.order("O", strategy.short, 1)
if bar_index == 14
    strategy.cancel("O")
if bar_index == 15
    strategy.cancel_all()
if bar_index == 16
    strategy.close_all()
plot(strategy.position_size, "ps")
plot(strategy.convert_to_account(close), "cv")
"""
        out = _ok(_run(src, 40))
        assert "ps" in _series(out)

    def test_strategy_opentrades_query(self) -> None:
        src = """//@version=6
strategy("stq")
if bar_index == 2
    strategy.entry("L", strategy.long)
plot(strategy.opentrades, "ot")
plot(strategy.opentrades > 0 ? strategy.opentrades.entry_price(0) : na, "ep")
"""
        out = _ok(_run(src, 20))
        assert "ot" in _series(out)

    def test_plot_attrs_fold_and_hline(self) -> None:
        src = """//@version=6
indicator("pa")
plot(close, title="c", color=color.red, linewidth=2, style=plot.style_histogram, display=display.pane)
hline(100, "hl", color=color.blue, linestyle=hline.style_dashed)
bgcolor(close > open ? color.new(color.green, 90) : color.new(color.red, 90))
"""
        out = _ok(_run(src, 16))
        assert "c" in _series(out)

    def test_math_str_input_request(self) -> None:
        src = """//@version=6
indicator("msi")
len = input.int(14, "Length")
plot(math.max(close, open), "mx")
plot(math.min(close, open), "mn")
plot(math.abs(close - open), "ab")
plot(math.round(close), "rd")
s = str.tostring(close)
plot(str.length(s), "sl")
v = request.security(syminfo.tickerid, "60", close)
plot(nz(v, close), "v")
plot(ta.sma(close, len), "sma")
plot(syminfo.mintick, "mt")
"""
        out = _ok(_run(src, 30))
        # Same-symbol HTF may be na on short synthetic feeds; nz falls back to close.
        assert abs(_last(out, "v") - _bars(30)[-1]["close"]) < 1e-6
        assert abs(_last(out, "mx") - max(_bars(30)[-1]["close"], _bars(30)[-1]["open"])) < 1e-9

    def test_subscript_history_and_fix_na(self) -> None:
        src = """//@version=6
indicator("sub")
float x = na
plot(close[1], "c1")
plot(high[2], "h2")
plot(nz(x, close), "nx")
"""
        out = _ok(_run(src, 20))
        assert abs(_last(out, "nx") - _bars(20)[-1]["close"]) < 1e-9

    def test_mode_auto_numeric_and_object(self) -> None:
        num = _ok(
            _run(
                """//@version=6
indicator("n")
plot(ta.sma(close, 5), "s")
""",
                25,
                mode="auto",
            )
        )
        assert "s" in _series(num)
        obj = _ok(
            _run(
                """//@version=6
indicator("o")
var m = map.new<string, float>()
map.put(m, "k", close)
plot(map.get(m, "k"), "g")
""",
                20,
                mode="auto",
            )
        )
        assert "g" in _series(obj)


# ---------------------------------------------------------------------------
# Parity smokes (compile vs interpret) — catch real bugs, not silent weaken
# ---------------------------------------------------------------------------


class TestCompileInterpretParity:
    @pytest.mark.parametrize(
        ("src", "key"),
        [
            (
                """//@version=6
indicator("p1")
plot(close * 2, "p")
""",
                "p",
            ),
            (
                """//@version=6
indicator("p2")
a = array.from(1.0, 2.0, 3.0)
plot(array.sum(a), "p")
""",
                "p",
            ),
            (
                """//@version=6
indicator("p3")
plot(math.max(close, open), "p")
""",
                "p",
            ),
            (
                """//@version=6
indicator("p4")
type Pt
    float x = 0.0
p = Pt.new(close)
plot(p.x, "p")
""",
                "p",
            ),
            (
                """//@version=6
indicator("p5")
x = 1.0
x *= 4.0
plot(x, "p")
""",
                "p",
            ),
        ],
    )
    def test_last_value_parity(self, src: str, key: str) -> None:
        bars = _bars(28)
        ri = Runtime(symbol="P").run(src, bars, mode="interpret")
        rc = Runtime(symbol="P").run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        iv = float(np.asarray(ri["series"][key], dtype=np.float64)[-1])
        cv = float(np.asarray(rc["series"][key], dtype=np.float64)[-1])
        if math.isnan(iv) and math.isnan(cv):
            return
        assert cv == pytest.approx(iv, rel=1e-5, abs=1e-6)
