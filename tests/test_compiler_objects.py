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

"""Compile path: UDT, maps, full drawing surface (object mode)."""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


class TestUDTCompile:
    def test_udt_new_and_field_plot(self) -> None:
        src = """//@version=6
indicator("udt")
type Point
    float x
    float y
p = Point.new(close, open)
plot(p.x, title="px")
plot(p.y, title="py")
"""
        code = transpile(src)
        assert "object_mode" in code or "__type__" in code or "Point" in code
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert "px" in out and "py" in out
        # p.x == close
        np.testing.assert_allclose(out["px"], c)
        np.testing.assert_allclose(out["py"], o)

    def test_udt_var_persists(self) -> None:
        src = """//@version=6
indicator("v")
type Box
    float v
var b = Box.new(1.0)
plot(b.v, title="v")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        # var keeps first-bar value
        assert np.allclose(out["v"], 1.0)


class TestMapCompile:
    def test_map_put_get(self) -> None:
        src = """//@version=6
indicator("map")
var m = map.new<string, float>()
map.put(m, "k", close)
plot(map.get(m, "k"), title="g")
"""
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        # map retains last put; each bar puts current close — get returns that bar's close
        np.testing.assert_allclose(out["g"], c)

    def test_map_size_and_contains(self) -> None:
        src = """//@version=6
indicator("map2")
var m = map.new<string, float>()
map.put(m, "a", 1.0)
map.put(m, "b", 2.0)
plot(map.size(m), title="sz")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["sz"][1:], 2.0)


class TestDrawingCompile:
    def test_hline_label_bgcolor_events(self) -> None:
        src = """//@version=6
indicator("d", overlay=true)
hline(50, title="mid", color=color.gray)
bgcolor(color.red)
label.new(bar_index, high, "hi")
line.new(bar_index, low, bar_index + 1, high)
plot(close, title="c")
"""
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert "c" in out
        drawings = out.get("__drawings", [])
        assert len(drawings) >= 8  # at least one event per bar types * bars
        kinds = {d["kind"] for d in drawings}
        assert "hline" in kinds
        assert "bgcolor" in kinds
        assert "label" in kinds
        assert "line" in kinds

    def test_plotshape_and_fill_recorded(self) -> None:
        src = """//@version=6
indicator("s")
p1 = plot(close, title="a")
p2 = plot(open, title="b")
fill(p1, p2, color=color.blue)
plotshape(close > open, title="up")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(12)
        out = compiled.run(o, h, l, c, v)
        drawings = out.get("__drawings", [])
        kinds = {d["kind"] for d in drawings}
        assert "fill" in kinds
        assert "plotshape" in kinds


class TestNumericStillNumba:
    @pytest.mark.skipif(not has_numba(), reason="numba required")
    def test_pure_numeric_stays_numba(self) -> None:
        src = """//@version=6
indicator("n")
plot(ta.sma(close, 5), title="s")
"""
        compiled = compile_script(src)
        assert compiled.object_mode is False
        assert "@numba.njit" in compiled.generated_code


class TestSet05MissingNames:
    """Object-mode stubs for set05 recompile NameErrors / float64 handle bugs."""

    def test_udt_copy_independent(self) -> None:
        """Type.copy(instance) is a shallow dict clone, not list(TypeName)."""
        src = """//@version=6
indicator("")
type pivotPoint
    int x
    float y
pivot1 = pivotPoint.new()
pivot1.x := 1000
pivot2 = pivotPoint.copy(pivot1)
pivot2.x := 2000
plot(pivot1.x, title="p1")
plot(pivot2.x, title="p2")
"""
        code = transpile(src)
        assert "list(pivotPoint)" not in code
        assert "dict(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["p1"], 1000.0)
        assert np.allclose(out["p2"], 2000.0)

    def test_udt_reference_share(self) -> None:
        """pivot2 = pivot1 shares the handle; field write mutates both."""
        src = """//@version=6
indicator("")
type pivotPoint
    int x
    float y
pivot1 = pivotPoint.new()
pivot1.x := 1000
pivot2 = pivot1
pivot2.x := 2000
plot(pivot1.x, title="p1")
plot(pivot2.x, title="p2")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["p1"], 2000.0)
        assert np.allclose(out["p2"], 2000.0)

    def test_nested_function_def_params_not_series(self) -> None:
        """Nested UDF defs must not clobber outer params into x_arr NameError."""
        src = """//@version=6
indicator("nested")
f(x, y) =>
    g(a, b) => math.sqrt(a * a + b * b)
    g(x, y) / (x + y)
plot(f(3.0, 4.0), title="r")
"""
        code = transpile(src)
        assert "x_arr" not in code
        assert "def g(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        # 5 / 7
        assert abs(out["r"][-1] - 5.0 / 7.0) < 1e-9

    def test_math_rphi_constant(self) -> None:
        src = """//@version=5
indicator("r")
plot(math.rphi, title="r")
plot(1.0 - math.rphi, title="c")
"""
        code = transpile(src)
        assert "math_rphi" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(4)
        out = compiled.run(o, h, l, c, v)
        rphi = 2.0 / (1.0 + np.sqrt(5.0))
        assert abs(out["r"][-1] - rphi) < 1e-12
        assert abs(out["c"][-1] - (1.0 - rphi)) < 1e-12

    def test_barmerge_constants(self) -> None:
        src = """//@version=4
study("b")
bm = barmerge.lookahead_on
gp = barmerge.gaps_off
plot(bm ? 1 : 0, title="bm")
plot(gp ? 1 : 0, title="gp")
"""
        code = transpile(src)
        assert "barmerge_lookahead" not in code
        assert "name 'barmerge'" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(4)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["bm"], 1.0)
        assert np.allclose(out["gp"], 0.0)

    def test_array_mode(self) -> None:
        src = """//@version=5
indicator("m")
a = array.from(1.0, 2.0, 1.0)
plot(array.mode(a), title="mode")
"""
        code = transpile(src)
        assert "array_mode" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(4)
        out = compiled.run(o, h, l, c, v)
        assert out["mode"][-1] == 1.0

    def test_label_all_size(self) -> None:
        src = """//@version=5
indicator("la")
if bar_index == 0
    label.new(0, 0, "x")
n = label.all.size()
plot(n, title="n")
"""
        code = transpile(src)
        assert "label.all" not in code or "__drawings" in code
        assert "(__u := (label)" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        # one label created on bar 0; count persists via __drawings appends
        assert out["n"][-1] >= 1.0

    def test_array_new_table_and_push(self) -> None:
        src = """//@version=6
indicator("t")
tables = array.new_table()
array.push(tables, table.new(position.top_left, 1, 2))
plot(array.size(tables), title="sz")
"""
        code = transpile(src)
        assert "tables_arr" not in code or "safe_list_append" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["sz"], 1.0)

    def test_safe_list_clear_on_scalar(self) -> None:
        """array.clear on a non-list (security_lower_tf stub) must not AttributeError."""
        src = """//@version=5
indicator("c")
f(src) =>
    a = src
    array.clear(a)
    1.0
plot(f(close), title="ok")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(6)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["ok"], 1.0)
