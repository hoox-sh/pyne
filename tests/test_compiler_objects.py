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
from pynescript.runtime import Runtime


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

    def test_udt_bool_default_false_not_nan_truthy(self) -> None:
        """Omitted ``bool x = false`` must stay False (``bool(np.nan)`` is True)."""
        src = """//@version=5
indicator("udt-bool")
type State
    bool be_active = false
    float sl_value = 500.0
var s = State.new()
plot(s.be_active ? 1 : 0, title="be")
plot(s.sl_value, title="sl")
"""
        code = transpile(src)
        assert "be_active" in code
        assert "False" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["be"], 0.0)
        assert np.allclose(out["sl"], 500.0)
        ri = Runtime().run(src, [
            {"open": float(o[i]), "high": float(h[i]), "low": float(l[i]),
             "close": float(c[i]), "volume": 1.0, "time": i * 60_000}
            for i in range(8)
        ], mode="interpret")
        assert "error" not in ri, ri.get("error")
        assert ri["series"]["be"] == [0] * 8 or all(float(x) == 0.0 for x in ri["series"]["be"])


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
        # hline also materializes as a constant series (interpret parity)
        assert "mid" in out
        mid = np.asarray(out["mid"], dtype=np.float64)
        assert mid.shape == (8,)
        assert np.allclose(mid, 50.0)
        drawings = out.get("__drawings", [])
        assert len(drawings) >= 8  # at least one event per bar types * bars
        kinds = {d["kind"] for d in drawings}
        assert "hline" in kinds
        assert "bgcolor" in kinds
        assert "label" in kinds
        assert "line" in kinds

    def test_hline_default_titles_unique_series(self) -> None:
        """Untitled hlines become hline / hline_2 / … series keys."""
        src = """//@version=6
indicator("hl")
plot(close, title="c")
hline(1)
hline(0, color=color.gray)
hline(-1)
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(6)
        out = compiled.run(o, h, l, c, v)
        assert "c" in out
        assert "hline" in out and "hline_2" in out and "hline_3" in out
        assert np.allclose(np.asarray(out["hline"], dtype=np.float64), 1.0)
        assert np.allclose(np.asarray(out["hline_2"], dtype=np.float64), 0.0)
        assert np.allclose(np.asarray(out["hline_3"], dtype=np.float64), -1.0)
        assert any(isinstance(d, dict) and d.get("kind") == "hline" for d in out.get("__drawings", []))

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
        # Untitled fill still exports a series key (interpret default title "fill")
        assert "fill" in out
        fill_series = np.asarray(out["fill"], dtype=np.float64)
        assert fill_series.shape == (12,)
        assert np.all(np.isnan(fill_series))

    def test_fill_title_series_key_and_drawings(self) -> None:
        """Titled fill() is a null series key + fill drawing (interpret parity)."""
        src = """//@version=6
indicator("bb", overlay=true)
p1 = plot(high, title="Upper")
p2 = plot(low, title="Lower")
fill(p1, p2, title="Background", color=color.blue)
fill(p1, p2, color=color.red, title="Background")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert "Upper" in out and "Lower" in out
        assert "Background" in out
        assert "Background_2" in out  # uniquified like Runtime packaging
        bg = np.asarray(out["Background"], dtype=np.float64)
        assert bg.shape == (10,)
        assert np.all(np.isnan(bg))
        fill_events = [
            d for d in (out.get("__drawings") or []) if isinstance(d, dict) and d.get("kind") == "fill"
        ]
        assert len(fill_events) >= 10
        titles = {d.get("title") for d in fill_events}
        assert "Background" in titles or "Background_2" in titles


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


class TestObjectModeNaArithmetic:
    """None (Pine na) arithmetic in object-mode bar loop."""

    def test_unary_neg_none_is_nan(self) -> None:
        src = """//@version=5
indicator("u")
float x = na
plot(-x, title="n")
hline(0)
"""
        code = transpile(src)
        # float x = na → np.nan series; -x is safe without na_num when RHS is float64
        assert "x_arr" in code or "na_num" in code or "safe_float" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert np.all(np.isnan(out["n"]))

    def test_add_mul_chain_with_na(self) -> None:
        src = """//@version=5
indicator("ch")
float a = na
float b = 2.0
plot((a + 1.0) * b, title="p")
hline(1)
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert np.all(np.isnan(out["p"]))


class TestCollectionObjectModeParity:
    """Round 6: array.fill range, sort_field, map.keys/values compile parity."""

    def test_array_fill_range(self) -> None:
        src = """//@version=6
indicator("fill")
var a = array.from(0.0, 0.0, 0.0, 0.0, 0.0)
if bar_index == 0
    array.fill(a, 7.0, 1, 4)
plot(array.get(a, 0), title="p0")
plot(array.get(a, 1), title="p1")
plot(array.get(a, 3), title="p3")
plot(array.get(a, 4), title="p4")
"""
        code = transpile(src)
        assert "array_fill" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(6)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["p0"], 0.0)
        assert np.allclose(out["p1"], 7.0)
        assert np.allclose(out["p3"], 7.0)
        assert np.allclose(out["p4"], 0.0)

    def test_array_sort_udt_sort_field(self) -> None:
        src = """//@version=6
indicator("sortf")
type Item
    int id
    float v
var a = array.new<Item>()
if bar_index == 0
    array.push(a, Item.new(2, 20.0))
    array.push(a, Item.new(1, 10.0))
    array.push(a, Item.new(3, 30.0))
    array.sort(a, order.ascending, "id")
plot(array.get(a, 0).id, title="id0")
plot(array.get(a, 1).id, title="id1")
plot(array.get(a, 2).id, title="id2")
"""
        code = transpile(src)
        assert "array_sort" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["id0"], 1.0)
        assert np.allclose(out["id1"], 2.0)
        assert np.allclose(out["id2"], 3.0)

    def test_array_sort_indices_udt_sort_field(self) -> None:
        src = """//@version=6
indicator("si")
type Item
    int id
    float v
var a = array.new<Item>()
if bar_index == 0
    array.push(a, Item.new(2, 20.0))
    array.push(a, Item.new(1, 10.0))
    array.push(a, Item.new(3, 30.0))
si = array.sort_indices(a, order.ascending, "id")
plot(array.get(si, 0), title="i0")
plot(array.get(si, 1), title="i1")
plot(array.get(si, 2), title="i2")
"""
        code = transpile(src)
        assert "array_sort_indices" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        # ids were [2,1,3] → sorted indices [1,0,2]
        assert np.allclose(out["i0"], 1.0)
        assert np.allclose(out["i1"], 0.0)
        assert np.allclose(out["i2"], 2.0)

    def test_array_binary_search_udt_sort_field(self) -> None:
        src = """//@version=6
indicator("bs")
type Item
    int id
    float v
var a = array.new<Item>()
if bar_index == 0
    array.push(a, Item.new(2, 20.0))
    array.push(a, Item.new(1, 10.0))
    array.push(a, Item.new(2, 25.0))
    array.push(a, Item.new(3, 30.0))
    array.sort(a, order.ascending, "id")
plot(array.binary_search(a, 1, "id"), title="hit")
plot(array.binary_search(a, 9, "id"), title="miss")
plot(array.binary_search_leftmost(a, 2, "id"), title="left")
plot(array.binary_search_rightmost(a, 2, "id"), title="right")
plot(array.binary_search(a, 3, 0), title="idx0")
plot(array.binary_search(a, 1, sort_field="id"), title="kw")
plot(a.binary_search(3, "id"), title="method")
plot(array.binary_search(a, 3), title="deflt")
p = array.from(1, 2, 2, 3)
plot(array.binary_search(p, 3), title="prim")
plot(array.binary_search_leftmost(p, 2), title="pleft")
plot(array.binary_search_rightmost(p, 2), title="pright")
"""
        code = transpile(src)
        assert "array_binary_search" in code
        assert "array_binary_search_leftmost" in code
        assert "array_binary_search_rightmost" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        # after sort by id: [1, 2, 2, 3]
        assert np.allclose(out["hit"], 0.0)
        assert np.allclose(out["miss"], -1.0)
        assert np.allclose(out["left"], 1.0)
        assert np.allclose(out["right"], 2.0)
        assert np.allclose(out["idx0"], 3.0)
        assert np.allclose(out["kw"], 0.0)
        assert np.allclose(out["method"], 3.0)
        assert np.allclose(out["deflt"], 3.0)
        assert np.allclose(out["prim"], 3.0)
        assert np.allclose(out["pleft"], 1.0)
        assert np.allclose(out["pright"], 2.0)

    def test_array_binary_search_udt_interp_compile_parity(self) -> None:
        """Same UDT + primitive search script: interpret and compile agree."""
        src = """//@version=6
indicator("bs-parity")
type Item
    int id
    float v
var a = array.new<Item>()
if bar_index == 0
    array.push(a, Item.new(2, 20.0))
    array.push(a, Item.new(1, 10.0))
    array.push(a, Item.new(2, 25.0))
    array.push(a, Item.new(3, 30.0))
    array.sort(a, order.ascending, "id")
plot(array.binary_search(a, 1, "id"), title="hit")
plot(array.binary_search(a, 9, "id"), title="miss")
plot(array.binary_search_leftmost(a, 2, "id"), title="left")
plot(array.binary_search_rightmost(a, 2, "id"), title="right")
plot(array.binary_search(a, 3, 0), title="idx0")
plot(array.binary_search(a, 1, sort_field="id"), title="kw")
plot(a.binary_search(3, "id"), title="method")
plot(array.binary_search(a, 3), title="deflt")
p = array.from(1, 2, 2, 3)
plot(array.binary_search(p, 3), title="prim")
plot(array.binary_search_leftmost(p, 2), title="pleft")
plot(array.binary_search_rightmost(p, 2), title="pright")
"""
        bars = [
            {
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1000.0,
                "time": 1_700_000_000_000 + i * 60_000,
            }
            for i in range(6)
        ]
        expected = {
            "hit": 0.0,
            "miss": -1.0,
            "left": 1.0,
            "right": 2.0,
            "idx0": 3.0,
            "kw": 0.0,
            "method": 3.0,
            "deflt": 3.0,
            "prim": 3.0,
            "pleft": 1.0,
            "pright": 2.0,
        }
        rt = Runtime(symbol="TEST")
        ri = rt.run(src, bars, mode="interpret")
        rc = rt.run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        si = ri.get("series") or {}
        sc = rc.get("series") or {}
        for key, want in expected.items():
            assert key in si, (key, sorted(si))
            assert key in sc, (key, sorted(sc))
            assert si[key][-1] == pytest.approx(want), (key, "interpret", si[key][-1])
            assert sc[key][-1] == pytest.approx(want), (key, "compile", sc[key][-1])
            assert si[key][-1] == pytest.approx(sc[key][-1]), (key, si[key][-1], sc[key][-1])

    def test_map_new_is_scalar_not_series(self) -> None:
        src = """//@version=6
indicator("m")
var m = map.new<string, float>()
map.put(m, "k", close)
plot(map.get(m, "k"), title="g")
"""
        code = transpile(src)
        assert "m_arr" not in code
        assert "m = {}" in code or "m = None" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        np.testing.assert_allclose(out["g"], c)

    def test_map_keys_values_sequence_handles(self) -> None:
        src = """//@version=6
indicator("kv")
var m = map.new<string, float>()
if bar_index == 0
    map.put(m, "a", 1.0)
    map.put(m, "b", 2.0)
ks = map.keys(m)
vs = map.values(m)
plot(map.size(m), title="sz")
plot(array.size(ks), title="ksz")
plot(array.get(vs, 0) + array.get(vs, 1), title="vsum")
"""
        code = transpile(src)
        # keys/values must not be forced through safe_float into float series
        assert "safe_float(list(" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(6)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["sz"], 2.0)
        assert np.allclose(out["ksz"], 2.0)
        assert np.allclose(out["vsum"], 3.0)

    def test_array_insert_at_end_compile(self) -> None:
        src = """//@version=6
indicator("ins")
var a = array.from(1.0, 2.0, 3.0)
if bar_index == 0
    array.insert(a, 3, 99.0)
plot(array.size(a), title="sz")
plot(array.get(a, 3), title="v")
"""
        code = transpile(src)
        assert "safe_list_insert" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(4)
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["sz"], 4.0)
        assert np.allclose(out["v"], 99.0)

