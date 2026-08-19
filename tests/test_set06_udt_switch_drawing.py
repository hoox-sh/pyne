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

"""UDT return stores, switch-assign, drawing copy, na-safe pivothigh."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.compiler.numba_builtins import numba_pivothigh
from pynescript.compiler.numba_builtins import udt_get_field
from pynescript.util.corpus_sanitize import sanitize_corpus_source


_REPO = Path(__file__).resolve().parents[1]


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _last(out: dict, name: str = "plot_0") -> float:
    return float(np.asarray(out[name], dtype=np.float64)[-1])


def test_udt_get_field_helper() -> None:
    assert udt_get_field({"strength": 1.5}, "strength") == 1.5
    assert np.isnan(udt_get_field(np.nan, "strength"))
    assert np.isnan(udt_get_field(None, "x"))


def test_udf_returns_udt_field_not_float_dict() -> None:
    src = """//@version=5
indicator("Enum UDT")
type Signal
    float strength = 0.0
getSignal() =>
    sig = Signal.new()
    sig.strength := 2.0
    sig
s = getSignal()
plot(s.strength)
"""
    code = transpile(src)
    assert "dtype=object" in code or "s = getSignal" in code
    assert "float(" not in code.split("getSignal")[-1] or "safe_float(udt_get_field" in code or "udt_get_field" in code
    out = compile_script(src, use_cache=False).run(*_ohlcv(12))
    assert abs(_last(out) - 2.0) < 1e-9


def test_switch_with_nested_if_assigns_local() -> None:
    src = """//@version=5
indicator("sw")
f(int x) =>
    float r = switch x
        1 => 10.0
        2 =>
            if x > 0
                20.0
            else
                0.0
        => 0.0
    r
plot(f(2))
"""
    code = transpile(src)
    assert "= if " not in code
    out = compile_script(src, use_cache=False).run(*_ohlcv(8))
    assert abs(_last(out) - 20.0) < 1e-9


def test_chart_point_copy_not_list_none() -> None:
    src = """//@version=6
indicator("pt")
pt = chart.point.from_index(bar_index, high)
pt2 = chart.point.copy(pt)
plot(pt2.price)
"""
    code = transpile(src)
    assert "list(None)" not in code
    out = compile_script(src, use_cache=False).run(*_ohlcv(10))
    assert abs(_last(out) - float(_ohlcv(10)[1][-1])) < 1e-9


def test_box_copy_is_dict_not_none() -> None:
    src = """//@version=6
indicator("b")
b = box.new(bar_index - 1, high, bar_index, low)
b2 = box.copy(b)
plot(b2.get_top())
"""
    code = transpile(src)
    assert "list(None)" not in code
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(12))
    assert "plot_0" in out


def test_pivothigh_nan_length_is_nan() -> None:
    src = np.arange(10.0)
    st = numba_pivothigh(src, np.nan, 2.0, 5)
    assert st != st
    pine = """//@version=5
indicator("ph")
type S
    int length = 5
    int look_forward = 2
S settings = S.new()
plot(ta.pivothigh(high, settings.length, settings.look_forward))
"""
    compile_script(pine, use_cache=False).run(*_ohlcv(20))


def test_ta_cum_none_src_does_not_raise() -> None:
    src = """//@version=5
indicator("c")
float x = na
plot(ta.cum(x))
"""
    compile_script(src, use_cache=False).run(*_ohlcv(8))


def test_corpus_5027_enum_udt() -> None:
    pine = (_REPO / "tests/data/set06/indicators/5027_ind_enum_udt_5.pine").read_text()
    compile_script(pine, use_cache=False).run(*_ohlcv(24))


def test_corpus_1626_drawing_copy() -> None:
    pine = (_REPO / "tests/data/set06/indicators/1626_ind_coverage_drawing_round2.pine").read_text()
    compile_script(pine, use_cache=False).run(*_ohlcv(16))


def test_corpus_0018_distance_ratio_library_compiles() -> None:
    pine = (_REPO / "tests/data/set06/libraries/0018_lib_16.pine").read_text()
    src = sanitize_corpus_source(pine)
    compile_script(src, use_cache=False).run(*_ohlcv(12))


def test_corpus_13720_pivothigh_udt_length() -> None:
    pine = (_REPO / "tests/data/set06/indicators/13720_ind_channels_with_patterns.pine").read_text()
    compile_script(pine, use_cache=False).run(*_ohlcv(24))
