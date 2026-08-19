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

"""Same-arity color/bool/float UDF overloads must not store hex as float64."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


_SET06 = Path(__file__).parent / "data" / "set06" / "indicators"
_2682 = _SET06 / "2682_ind_function_overloading_demo.pine"
_2693 = _SET06 / "2693_ind_function_overloading_demo_2.pine"

_OVERLOAD_SRC = """//@version=6
indicator("Function overloading demo")
negate(float value) =>
    -value
negate(bool value) =>
    not value
negate(color value) =>
    color.rgb(255 - color.r(value), 255 - color.g(value), 255 - color.b(value), color.t(value))
bool notUpBar = negate(close > open)
float plotSeries = notUpBar ? negate(close) : close
color plotColor = negate(chart.bg_color)
plot(plotSeries, "Test plot", plotColor, style = plot.style_area)
"""


def _ohlcv(n: int = 20, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    open_ = close.copy()
    open_[1::2] = close[1::2] - 1.0
    return open_, close + 1.0, close - 1.0, close, np.ones(n)


def _compile_run(src: str, n: int = 20) -> dict:
    compiled = compile_script(src, use_cache=False)
    return compiled.run(*_ohlcv(n))


def _assert_hex_not_floated(code: str) -> None:
    assert "float('#000000')" not in code
    assert 'float("#000000")' not in code
    assert "float('#FFFFFF')" not in code
    assert "dtype=object" in code
    assert "'#000000'" in code or '"#000000"' in code or "'#FFFFFF'" in code


def test_transpile_color_overload_keeps_hex_object() -> None:
    code = transpile(_OVERLOAD_SRC)
    _assert_hex_not_floated(code)
    assert "plotColor_arr" in code
    assert "safe_float(plotColor" not in code
    assert "float(plotColor" not in code


def test_same_arity_overloads_dispatch_by_arg_type() -> None:
    code = transpile(_OVERLOAD_SRC)
    defs = [ln for ln in code.splitlines() if ln.startswith("def negate")]
    assert len(defs) >= 3, defs
    # bool comparison, numeric close, hex/chart color each hit a distinct impl
    assert "negate(" in code
    body = code.split("for __bar_idx")[-1]
    assert "notUpBar_arr" in body
    assert "plotSeries_arr" in body
    assert "plotColor_arr[__bar_idx]" in body
    assert "safe_float(plotColor" not in body


def test_compile_run_color_overload_plot_series() -> None:
    out = _compile_run(_OVERLOAD_SRC, n=20)
    series = np.asarray(out["Test plot"], dtype=np.float64)
    open_, _h, _l, close, _v = _ohlcv(20)
    not_up = ~(close > open_)
    expected = np.where(not_up, -close, close)
    np.testing.assert_allclose(series, expected, rtol=0, atol=1e-9)


def test_corpus_2682_hex_not_float64_and_runs() -> None:
    src = _2682.read_text(encoding="utf-8")
    code = transpile(src)
    _assert_hex_not_floated(code)
    out = compile_script(src, use_cache=False).run(*_ohlcv(20))
    assert "error" not in out
    series = np.asarray(out["Test plot"], dtype=np.float64)
    assert series.shape == (20,)
    assert np.isfinite(series).all()


def test_corpus_2693_same_class() -> None:
    if not _2693.is_file():
        return
    src = _2693.read_text(encoding="utf-8")
    code = transpile(src)
    _assert_hex_not_floated(code)
    out = compile_script(src, use_cache=False).run(*_ohlcv(16))
    assert "error" not in out
    series = np.asarray(out["Test plot"], dtype=np.float64)
    assert np.isfinite(series).all()
