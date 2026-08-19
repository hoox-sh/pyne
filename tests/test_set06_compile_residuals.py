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

"""Compile-path locks for set06 residuals (continue, for-expr, array/map, enum hoist)."""

from __future__ import annotations

import signal

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime
from pynescript.util.corpus_sanitize import sanitize_corpus_source


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _compile_run(src: str, n: int = 20) -> dict:
    compiled = compile_script(src)
    return compiled.run(*_ohlcv(n))


def _last(out: dict, name: str = "plot_0") -> float:
    return float(np.asarray(out[name], dtype=np.float64)[-1])


class _TimeoutError(Exception):
    """SIGALRM fired while a compile/run was expected to finish quickly."""


def _run_with_timeout(fn, seconds: float = 5.0):
    def _handler(_signum, _frame):
        msg = "compile/run exceeded timeout"
        raise _TimeoutError(msg)

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, old)


def test_for_continue_does_not_hang_and_sums_odds() -> None:
    src = """//@version=5
indicator("For Continue")
float total = 0.0
for i = 1 to 10
    if i % 2 == 0
        continue
    total := total + i
plot(total)
"""

    def _go() -> dict:
        return _compile_run(src, n=20)

    out = _run_with_timeout(_go, seconds=5.0)
    assert _last(out) == 25.0


def test_for_as_expression_assign() -> None:
    src = """//@version=5
indicator("For Expr")
float total = 0.0
float result_expr = for i = 1 to 5
    total := total + i
    total
plot(result_expr)
"""
    code = transpile(src)
    assert "= for " not in code
    assert "= i =" not in code
    compiled = compile_script(src)
    assert compiled is not None
    out = compiled.run(*_ohlcv(20))
    assert _last(out) == 15.0


def test_array_percentile_and_every_compile() -> None:
    src = """//@version=5
indicator("arr")
var arr = array.from(10.0, 20.0, 30.0, 40.0, 50.0)
p = array.percentile_linear_interpolation(arr, 50)
ok = array.every(arr)
plot(p)
plot(ok ? 1 : 0)
"""
    out = _compile_run(src, n=20)
    assert abs(_last(out, "plot_0") - 30.0) < 1e-9
    assert _last(out, "plot_1") == 1.0


def test_map_put_all_compile() -> None:
    src = """//@version=5
indicator("m")
var m1 = map.new<string,int>()
var m2 = map.new<string,int>()
map.put(m1, "a", 1)
map.put_all(m2, m1)
plot(map.get(m2, "a"))
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 1.0


def test_enum_hoist_forward_ref() -> None:
    src = """//@version=5
indicator("Hoisting Enum")
Dir d = Dir.Up
plot(d == Dir.Up ? 1.0 : 0.0)
enum Dir
    Up = 1
    Down = 2
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 1.0


def test_switch_multi_compile() -> None:
    src = """//@version=5
indicator("Switch Multi")
x = 2
val = switch x
    1, 2 => 100
    => 0
plot(val)
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 100.0


def test_switch_default_only() -> None:
    src = """//@version=5
indicator("UDF Switch Default")
f_always() =>
    switch
        => 42.0
plot(f_always())
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 42.0


def test_map_for_in_pairs() -> None:
    src = """//@version=5
indicator("Map Iter")
var m = map.new<string, float>()
if bar_index == 0
    map.put(m, "a", 10.0)
    map.put(m, "b", 20.0)
total = 0.0
for [k, v] in m
    total += v
plot(total)
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 30.0


def test_dmi_scalar_assign_not_sequence() -> None:
    src = """//@version=5
indicator("ADX")
d = ta.dmi(14, 14)
plot(d)
"""
    out = _compile_run(src, n=20)
    arr = np.asarray(out["plot_0"], dtype=np.float64)
    assert arr.size == 20


def test_mustache_placeholder_sanitized() -> None:
    raw = """//@version=5
indicator("Mustache")
x = {{FOO}}
plot(close)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "{{FOO}}" not in cleaned
    o, h, l, c, v = _ohlcv(8)
    bars = [
        {
            "open": float(o[i]),
            "high": float(h[i]),
            "low": float(l[i]),
            "close": float(c[i]),
            "volume": float(v[i]),
            "time": int(i * 60_000),
        }
        for i in range(len(c))
    ]
    result = Runtime().run(cleaned, bars)
    assert "error" not in result, result.get("error")
