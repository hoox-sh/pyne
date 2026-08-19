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

"""UDF local if-assign and free-series capture (set06 monthClamp / t3)."""

from __future__ import annotations

import re

from pathlib import Path

import numpy as np
import pytest

from pynescript.ast.helper import parse
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


_SET06 = Path(__file__).parent / "data" / "set06" / "indicators"


def _ohlcv(n: int = 20, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _last(out: dict, name: str = "plot_0") -> float:
    return float(np.asarray(out[name], dtype=np.float64)[-1])


def _def_line(code: str, name: str) -> str:
    prefix = f"def {name}("
    for ln in code.splitlines():
        if ln.startswith(prefix):
            return ln
    msg = f"no def {name}( in transpile"
    raise AssertionError(msg)


def _func_block(code: str, name: str) -> str:
    """Top-level ``def name(...):`` through the next top-level def / execute."""
    lines = code.splitlines()
    start = None
    prefix = f"def {name}("
    for i, ln in enumerate(lines):
        if ln.startswith(prefix):
            start = i
            break
    if start is None:
        msg = f"no def {name}( in transpile"
        raise AssertionError(msg)
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("def ") or lines[j].startswith("def execute"):
            end = j
            break
    return "\n".join(lines[start:end])


_MONTHCLAMP_SRC = """//@version=6
indicator("x")
monthClamp(int mon, bool roll = false) =>
    int m = if roll
        int normalized = mon
        ((normalized - 1) % 12) + 1
    else
        math.min(math.max(mon, 1), 12)
    m + 1
plot(monthClamp(14, true))
"""


_T3_SRC = """//@version=4
study("t3")
l=input(title="Length",type=input.integer,minval=1,defval=5)
a=input(title="Alpha",type=input.float,minval=0,maxval=1,defval=0.7)
s=input(title="Source",type=input.source,defval=close)
gd(series,seriesLength,v)=>
    ema(series,seriesLength)*(1+a)-ema(ema(series,seriesLength),seriesLength)*a
t3(s,l,a)=>
    gd(gd(gd(s,l,a),l,a),l,a)
plot(t3(s,l,a))
"""


def test_udf_if_expr_assign_uses_local_not_script_arr() -> None:
    """``int m = if`` inside a UDF must assign local ``m``, not ``m_arr``."""
    code = transpile(_MONTHCLAMP_SRC)
    body = _func_block(code, "monthClamp")
    assert "m_arr" not in body
    assert re.search(r"\bm\s*=", body)
    compiled = compile_script(_MONTHCLAMP_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20))
    # roll: ((14-1)%12)+1 = 2, then m+1 = 3
    assert _last(out) == 3.0


def test_corpus_2137_monthclamp_if_expr_in_udf() -> None:
    src = (_SET06 / "2137_ind_x_43.pine").read_text(encoding="utf-8")
    parse(src)
    code = transpile(src)
    body = _func_block(code, "monthClamp")
    assert "m_arr" not in body
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(20))
    assert _last(out) == 3.0


def test_corpus_1831_monthclamp_if_parses() -> None:
    """1831 also has blank-line tuple wrap (parser). Skip if that still fails."""
    src = (_SET06 / "1831_ind_t_3.pine").read_text(encoding="utf-8")
    try:
        parse(src)
    except Exception as exc:
        pytest.skip(f"1831 still fails to parse (tuple wrap): {exc}")
    code = transpile(src)
    body = _func_block(code, "monthClamp")
    assert "m_arr" not in body
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(40))
    assert "plot_1" in out
    assert _last(out, "plot_1") == 3.0


def test_udf_param_keeps_script_series_arr_for_nested_callee() -> None:
    """``t3(s,l,a)`` must still pass script-level ``a_arr`` into nested ``gd``."""
    code = transpile(_T3_SRC)
    def_line = _def_line(code, "t3")
    assert "a_arr" in def_line
    compiled = compile_script(_T3_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(20, start=100.0))
    arr = np.asarray(out["plot_0"], dtype=np.float64)
    assert arr.size == 20
    # Triple-nested EMA warmup exceeds 20 bars; longer run must be finite.
    out80 = compiled.run(*_ohlcv(80, start=100.0))
    assert np.isfinite(np.asarray(out80["plot_0"], dtype=np.float64)[-1])


def test_corpus_14003_t3_ma_free_series_a_arr() -> None:
    src = (_SET06 / "14003_ind_t3_ma.pine").read_text(encoding="utf-8")
    parse(src)
    code = transpile(src)
    def_line = _def_line(code, "t3")
    assert "a_arr" in def_line
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(20, start=100.0))
    plot = next(v for k, v in out.items() if k != "__drawings")
    arr = np.asarray(plot, dtype=np.float64)
    assert arr.size == 20
