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

"""Literal ``color.new`` must not force object mode.

A constant color is metadata: it is folded into plot/fill attributes at
transpile time and never evaluated in the bar loop.  Dynamic colors (input /
series expressions) keep the object-mode runtime helper.
"""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile


pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")


def _ohlcv(n: int = 40, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


@pytest.fixture(autouse=True)
def _fresh_caches():
    clear_parse_cache()
    clear_compile_cache()
    yield
    clear_parse_cache()
    clear_compile_cache()


class TestLiteralColorNew:
    def test_plot_color_stays_numeric(self) -> None:
        src = """//@version=6
indicator("x")
plot(close, title="p", color=color.new(color.red, 50))
"""
        compiled = compile_script(src)
        assert compiled.object_mode is False
        code = transpile(src)
        assert "pine_color_new(" not in code
        o, h, l, c, v = _ohlcv()
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["p"], c)

    def test_fill_color_is_folded_into_attrs(self) -> None:
        src = """//@version=6
indicator("x")
upper = plot(high, title="upper")
lower = plot(low, title="lower")
fill(upper, lower, color=color.new(color.green, 50))
"""
        compiled = compile_script(src)
        assert compiled.object_mode is False
        # fill() is the third plot entry; color.new(green, 50) → rgba(...)
        assert compiled.plot_attrs[2]["color"] == "rgba(34, 171, 148, 0.4980392156862745)"
        o, h, l, c, v = _ohlcv()
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["upper"], h)
        assert np.allclose(out["lower"], l)

    def test_keyword_color_and_hex_base_fold(self) -> None:
        src = """//@version=6
indicator("x")
plot(close, title="a", color=color.new(color=color.red, transp=50))
plot(open, title="b", color=color.new("#00ff00", 25))
"""
        compiled = compile_script(src)
        assert compiled.object_mode is False
        code = transpile(src)
        assert "pine_color_new(" not in code

    def test_dynamic_transparency_stays_object(self) -> None:
        src = """//@version=6
indicator("x")
transp = close > open ? 50 : 25
plot(close, title="p", color=color.new(color.red, transp))
"""
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv()
        out = compiled.run(o, h, l, c, v)
        assert np.allclose(out["p"], c)

    def test_color_series_stays_object(self) -> None:
        src = """//@version=6
indicator("x")
col = close > open ? color.green : color.red
plot(close, title="p", color=col)
"""
        compiled = compile_script(src)
        assert compiled.object_mode is True

    def test_one_arg_rgba_string_keeps_original_text(self) -> None:
        src = """//@version=6
indicator("x")
upper = plot(high, title="upper")
lower = plot(low, title="lower")
fill(upper, lower, color=color.new("#FF000080"))
"""
        compiled = compile_script(src)
        assert compiled.object_mode is False
        assert compiled.plot_attrs[2]["color"] == "#FF000080"

    def test_hline_attrs_survive_numeric_synthesis(self) -> None:
        src = """//@version=6
indicator("x")
hline(50, "h", color=color.new(color.gray, 60), linestyle=hline.style_dashed)
plot(close)
"""
        compiled = compile_script(src)
        assert compiled.object_mode is False
        assert compiled.plot_attrs[0]["color"] == "rgba(120, 123, 134, 0.4)"
        assert compiled.plot_attrs[0]["linestyle"] == "style_dashed"
        o, h, l, c, v = _ohlcv()
        out = compiled.run(o, h, l, c, v)
        ev = out["__drawings"][0]
        assert ev["kind"] == "hline"
        assert ev["color"] == "rgba(120, 123, 134, 0.4)"
        assert ev["linestyle"] == "style_dashed"
