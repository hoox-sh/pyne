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

"""Residual statement/expression branches via tiny Runtime.interpret scripts."""

from __future__ import annotations

from pynescript.runtime import Runtime


def _bars(n: int = 24) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": 100.0 + (i % 5) * 0.1,
            "high": 101.0 + (i % 5) * 0.1,
            "low": 99.0 + (i % 5) * 0.1,
            "close": 100.5 + (i % 5) * 0.1,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


def _run(src: str, n: int = 24) -> dict:
    out = Runtime(symbol="EDGE").run(src, _bars(n), mode="interpret")
    assert "error" not in out, out.get("error")
    return out


def _last(series: dict, name: str):
    return series[name][-1]


class TestSwitchCase:
    def test_boolean_switch(self) -> None:
        src = """//@version=6
indicator("bool_sw")
x = switch close >= open
    true => 1
    false => -1
    => 0
plot(x, "x")
"""
        assert _last(_run(src)["series"], "x") in (1, -1)

    def test_subject_switch_default(self) -> None:
        src = """//@version=6
indicator("subj_sw")
v = 99
x = switch v
    1 => 10
    2 => 20
    => 7
plot(x, "x")
"""
        assert _last(_run(src)["series"], "x") == 7

    def test_enum_switch_v6(self) -> None:
        src = """//@version=6
indicator("enum_sw")
enum Side
    buy
    sell
s = Side.sell
x = switch s
    Side.buy => 1
    Side.sell => -1
    => 0
plot(x, "x")
"""
        assert _last(_run(src)["series"], "x") == -1


class TestLoopsBreakContinue:
    def test_for_break_continue(self) -> None:
        src = """//@version=5
indicator("for_bc")
s = 0
for i = 0 to 10
    if i == 3
        continue
    if i == 7
        break
    s := s + i
plot(s, "s")
"""
        # 0+1+2+4+5+6
        assert _last(_run(src)["series"], "s") == 18

    def test_for_downward_and_step(self) -> None:
        src = """//@version=5
indicator("for_down")
s = 0
for i = 5 to 1
    s := s + i
plot(s, "s")
t = 0
for i = 0 to 6 by 2
    t := t + i
plot(t, "t")
"""
        series = _run(src)["series"]
        assert _last(series, "s") == 15
        assert _last(series, "t") == 12

    def test_while_break_continue(self) -> None:
        src = """//@version=5
indicator("while_bc")
i = 0
s = 0
while i < 10
    i := i + 1
    if i == 3
        continue
    if i == 8
        break
    s := s + i
plot(s, "s")
"""
        # 1+2+4+5+6+7
        assert _last(_run(src)["series"], "s") == 25

    def test_for_in_index_value_unpack(self) -> None:
        src = """//@version=5
indicator("for_in")
arr = array.from(10, 20, 30)
s = 0
for [i, v] in arr
    s := s + i + v
plot(s, "s")
"""
        # (0+10)+(1+20)+(2+30) = 63
        assert _last(_run(src)["series"], "s") == 63


class TestIfElseNestedAndTernary:
    def test_nested_if_else(self) -> None:
        src = """//@version=5
indicator("nif")
x = 0.0
if close > open
    if high > close
        x := 2.0
    else
        x := 1.0
else
    if low < open
        x := -2.0
    else
        x := -1.0
plot(x, "x")
"""
        assert _last(_run(src)["series"], "x") in (2.0, 1.0, -2.0, -1.0)

    def test_ternary_and_na_test(self) -> None:
        src = """//@version=5
indicator("tern")
x = close > open ? 1.0 : 0.0
y = na(close) ? 9.0 : 3.0
z = 0 ? 1.0 : 2.0
plot(x, "x")
plot(y, "y")
plot(z, "z")
"""
        series = _run(src)["series"]
        assert _last(series, "y") == 3.0
        assert _last(series, "z") == 2.0
        assert _last(series, "x") in (0.0, 1.0)


class TestTupleUnpackAndNaBool:
    def test_tuple_unpack_assign(self) -> None:
        src = """//@version=5
indicator("tup")
[a, b] = [1.5, 2.5]
plot(a, "a")
plot(b, "b")
plot(a + b, "sum")
"""
        series = _run(src)["series"]
        assert _last(series, "a") == 1.5
        assert _last(series, "b") == 2.5
        assert _last(series, "sum") == 4.0

    def test_na_propagation_binop(self) -> None:
        src = """//@version=5
indicator("na_bin")
x = na + 1.0
y = 2.0 * na
z = close / 0.0
plot(na(x) ? 1 : 0, "xna")
plot(na(y) ? 1 : 0, "yna")
plot(na(z) ? 1 : 0, "zna")
"""
        series = _run(src)["series"]
        assert _last(series, "xna") == 1
        assert _last(series, "yna") == 1
        assert _last(series, "zna") == 1

    def test_and_or_short_circuit(self) -> None:
        src = """//@version=5
indicator("sc")
a = false and (1 / 0)
b = true or (1 / 0)
c = na and true
d = false or na
e = true and true
f = false or false
plot(a ? 1 : 0, "a")
plot(b ? 1 : 0, "b")
plot(c ? 1 : 0, "c")
plot(d ? 1 : 0, "d")
plot(e ? 1 : 0, "e")
plot(f ? 1 : 0, "f")
"""
        series = _run(src)["series"]
        assert _last(series, "a") == 0
        assert _last(series, "b") == 1
        assert _last(series, "c") == 0
        assert _last(series, "d") == 0
        assert _last(series, "e") == 1
        assert _last(series, "f") == 0


class TestSwitchExpressionStatementMix:
    def test_if_expression_assign(self) -> None:
        src = """//@version=5
indicator("if_expr")
x = if close > open
    1.0
else
    0.0
plot(x, "x")
"""
        assert _last(_run(src)["series"], "x") in (0.0, 1.0)

    def test_switch_expression_assign(self) -> None:
        src = """//@version=6
indicator("sw_expr")
n = 1
x = switch n
    1 => 42.0
    2 => 7.0
    => 0.0
plot(x, "x")
"""
        assert _last(_run(src)["series"], "x") == 42.0
