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
