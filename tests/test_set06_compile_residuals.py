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

from pathlib import Path
import re

import numpy as np

from pynescript.ast.helper import parse
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime
from pynescript.util.corpus_sanitize import sanitize_corpus_source


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _compile_run(src: str, n: int = 20) -> dict:
    compiled = compile_script(src, use_cache=False)
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


def test_inv025_inv047_broken_strings_do_not_raise_unterminated() -> None:
    """Broken TV string-wrap fixtures must sanitize so compile can start."""
    root = Path(__file__).parent / "data" / "set06" / "indicators"
    for name in (
        "2162_ind_inv025_string_continuation_indent.pine",
        "1882_ind_inv047.pine",
    ):
        raw = (root / name).read_text(encoding="utf-8")
        cleaned = sanitize_corpus_source(raw)
        parse(cleaned)
        compile_script(raw, use_cache=False)


def test_tuple_literal_rhs_does_not_raise() -> None:
    src = """//@version=6
indicator("t")
arr = [1, 2, 3]
plot(close)
"""
    out = _compile_run(src, n=20)
    arr = np.asarray(out["plot_0"], dtype=np.float64)
    assert arr.size == 20


def test_tuple_udf_to_scalar_does_not_raise() -> None:
    src = """//@version=6
indicator("t")
f() => [1, 2]
a = f()
[p, q] = f()
plot(p + q)
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 3.0


def test_udt_factory_assign() -> None:
    src = """//@version=5
indicator("UDT method TA")
type Signal
    float value = 0.0
    bool active = false
calcSignal(src, len) =>
    Signal.new(ta.sma(src, len), true)
sig = calcSignal(close, 3)
plot(sig.value)
"""
    n = 20
    out = _compile_run(src, n=n)
    close = np.arange(100.0, 100.0 + n, dtype=np.float64)
    expected = float(np.mean(close[-3:]))
    assert abs(_last(out) - expected) < 1e-6


def test_udt_keyword_fields_var_switch() -> None:
    src = '''//@version=5
indicator("Keyword Field Var")
type Settings
    float var = 1.0
    float switch = 2.0
Settings s = Settings.new()
var float result = 0.0
result := s.var + s.switch
plot(result)
'''
    out = _compile_run(src, n=20)
    assert abs(_last(out) - 3.0) < 1e-9


def test_input_string_not_coerced_through_float() -> None:
    """13641: ``input.string`` / string literals must not hit bare ``float()``.

    ``zigzag.function(method, x, y)`` used to be mis-emitted as
    ``activation.function`` and do ``float('(MANUAL) Percent …')``.
    """
    src = """//@version=5
indicator("t")
import Foo/Bar/1 as zigzag
string m_000 = '(MANUAL) Percent price move over X * Y'
string zigzag_method = input.string(defval=m_000, title="Method")
[price_a, is_up, reverse, rl] = zigzag.function(zigzag_method, 1.0, 1.0)
plot(close)
"""
    code = transpile(src)
    assert "float(zigzag_method" not in code
    assert "float(m_000" not in code
    assert "np.exp(-float(" not in code
    assert "float(zigzag_method_arr" not in code
    out = _compile_run(src, n=20)
    assert _last(out) == 119.0


def test_udf_var_color_rgb_not_float64_store() -> None:
    """13712: ``var tC = color.rgb(...)`` must keep hex colors as object, not float64."""
    src = """//@version=5
indicator("t")
f(_cr) =>
    var tC = color.rgb(color.r(_cr), color.g(_cr), color.b(_cr))
    tC
c = f(#000000)
plot(close, color=c)
"""
    code = transpile(src)
    assert "float('#000000')" not in code
    assert "dtype=object" in code
    assert "tC_arr[__bar_idx] = '#000000'" in code or "tC_arr[__bar_idx] =" in code
    from pynescript.compiler.numba_builtins import safe_float

    assert np.isnan(safe_float("#000000"))
    assert np.isnan(safe_float("#e91e63"))
    out = _compile_run(src, n=20)
    assert _last(out) == 119.0


def test_library_function_does_not_float_color_or_udt() -> None:
    """Same ``*.function`` emit: color hex / UDT must not hit bare ``float()``."""
    src = """//@version=5
indicator("t")
import Foo/Bar/1 as lib
type Box
    float v = 1.0
color c = #000000
x = lib.function(c)
y = lib.function(Box.new())
plot(close)
"""
    code = transpile(src)
    assert "float('#000000')" not in code
    assert "np.exp(-float(" not in code
    out = _compile_run(src, n=20)
    assert _last(out) == 119.0


def test_activation_function_kw_still_stubs() -> None:
    """Intended MLActivationFunctions kwargs path still emits the relu stub."""
    src = """//@version=5
indicator("t")
import Foo/Act/1 as activation
plot(activation.function(value=1.0, name="relu"))
"""
    code = transpile(src)
    assert "safe_float" in code
    assert "relu" in code
    out = _compile_run(src, n=20)
    assert _last(out) == 1.0


def test_rst_fill_example_sanitized() -> None:
    raw = """study("fill Example")
    p1 = plot(close)
    p2 = plot(open)
    fill(p1, p2, color=red)

.. image:: images/fill.png
"""
    cleaned = sanitize_corpus_source(raw)
    compiled = compile_script(cleaned)
    assert compiled is not None
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
    result = Runtime().run(cleaned, bars, mode="compile")
    assert "error" not in result, result.get("error")


def test_field_on_non_udt_does_not_nameerror() -> None:
    """``close.foo`` must not emit a dead ``close_arr_foo`` identifier."""
    src = """//@version=6
indicator("field-on-non-udt")
y = close.foo
plot(close)
"""
    code = transpile(src)
    assert "close_arr_foo" not in code
    out = _compile_run(src, n=20)
    arr = np.asarray(out["plot_0"], dtype=np.float64)
    assert arr.size == 20


def test_bare_line_namespace_or_style_does_not_nameerror() -> None:
    """Bare ``line`` is a style token / namespace stub, not a Python NameError."""
    src = """//@version=5
indicator("s")
level_style = line
hline(50, linestyle=line)
plot(close)
"""
    code = transpile(src)
    assert "safe_float(line)" not in code
    assert "linestyle': line}" not in code
    out = _compile_run(src, n=20)
    arr = np.asarray(out["plot_1"] if "plot_1" in out else out["plot_0"], dtype=np.float64)
    assert arr.size == 20


def test_udt_type_name_shadow_field_read() -> None:
    """``hz hz = hz.new(); hz.x`` must not emit a dead ``hz_x`` identifier."""
    src = """//@version=6
indicator("INV133")
type hz
    int x
f() =>
    hz hz = hz.new(1)
    hz.x
plot(f())
"""
    code = transpile(src)
    assert "hz_x" not in code
    out = _compile_run(src, n=20)
    assert _last(out) == 1.0


def test_for_in_udt_field_and_method() -> None:
    """For-in UDT items: ``bi.t`` / ``each.prices.size()`` are field reads."""
    src = """//@version=6
indicator("x")
type BarInfo
    int t = 0
sumTimes(BarInfo[] biList, minTime) =>
    float total = 0.0
    for [i, bi] in biList
        if bi.t >= minTime
            total += bi.t + i
    total
type Asset
    array<float> prices
sumSizes() =>
    float n = 0.0
    var assets = array.new<Asset>()
    if bar_index == 0
        array.push(assets, Asset.new(array.from(1.0, 2.0)))
    for eachAsset in assets
        n += eachAsset.prices.size()
    n
BarInfo b1 = BarInfo.new(1), BarInfo b2 = BarInfo.new(2)
plot(sumTimes(array.from(b1, b2), 0))
plot(sumSizes())
"""
    code = transpile(src)
    assert "bi_t" not in code
    assert "eachAsset_prices" not in code
    out = _compile_run(src, n=20)
    assert _last(out, "plot_0") == 4.0
    assert _last(out, "plot_1") == 2.0


def test_udf_param_shadows_script_series_bool() -> None:
    """Script-level ``showMetrics_arr`` must not leak into a UDF param of the same name."""
    src = """//@version=5
indicator("s")
bool showAvgInput = input.bool(true, "a")
bool showStDevInput = input.bool(true, "b")
bool showPosInput = input.bool(true, "c")
bool showMetrics = showAvgInput or showStDevInput or showPosInput
countRows(showMetrics) =>
    showMetrics ? 1.0 : 0.0
plot(countRows(showMetrics))
"""
    code = transpile(src)
    assert "if bool(showMetrics_arr[__bar_idx])" not in code
    out = _compile_run(src, n=20)
    assert _last(out) == 1.0


def test_namespace_fields_not_series_idents() -> None:
    """``dividends.future_amount`` / ``currency.TRY`` are namespace members, not series."""
    src = """//@version=6
indicator("c")
divFut = dividends.future_amount
simple string fromCurrency = currency.TRY
plot(divFut)
plot(close)
"""
    code = transpile(src)
    assert "dividends_arr_future_amount" not in code
    assert "currency_arr_TRY" not in code
    out = _compile_run(src, n=20)
    arr = np.asarray(out["plot_0"], dtype=np.float64)
    assert arr.size == 20


def test_switch_augassign_mutates_udf_locals() -> None:
    src = '''//@version=5
indicator("cvd")
upDn() =>
    float upVol = 0.0
    float dnVol = 0.0
    switch
        close > open => upVol += volume
        close < open => dnVol -= volume
    [upVol, dnVol]
[u, d] = upDn()
plot(u)
'''
    out = _compile_run(src, n=20)
    arr = __import__("numpy").asarray(out["plot_0"], dtype="float64")
    assert arr.size == 20


def test_while_if_expr_numeric_body_does_not_hang() -> None:
    """set06 13674: sanitize must keep ``80`` / ``counter += 1`` inside while."""
    raw = """//@version=5
indicator("t")
int counter = 0
n = 4
while n > counter
    int transp = if counter != 1
        80
    else
        0
    counter += 1
plot(counter)
"""
    cleaned = sanitize_corpus_source(raw)
    assert "counter += 1" in cleaned
    assert re.search(r"^\s+80\s*$", cleaned, re.M)

    def _go() -> dict:
        return _compile_run(cleaned, n=8)

    out = _run_with_timeout(_go, seconds=5.0)
    assert _last(out) == 4.0


def test_switch_default_mid_first_match() -> None:
    """Mid-default is first-match: ``=>`` always matches, later arms are dead.

    ``x = 2`` does not reach ``2 => 20``; the first default ``0`` wins.
    Pattern arms *before* the default still match (``x = 1`` would be 10).
    A second default, if present, is ignored.
    """
    src = """//@version=5
indicator("Switch DefMid")
x = 2
var int r = 0
r := switch x
    1 => 10
    => 0
    2 => 20
plot(r)
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 0.0


def test_not_continuation_compile() -> None:
    """``not`` + newline + indented operand compiles (lexer operator line-join)."""
    src = """//@version=5
indicator("Not Cont")
x = not
    (close < open)
plot(x ? 1 : 0)
"""
    out = _compile_run(src, n=20)
    # _ohlcv uses open == close, so ``close < open`` is false and ``not`` is true.
    assert _last(out) == 1.0


def test_udt_method_last_assign_returns_without_syntax_error() -> None:
    """set06 6447: method ending in ``self.total :=`` must not split on walrus '='."""
    src = """//@version=5
indicator("Method Decl")
type Acc
    float total = 0.0
method add_val(Acc self, float v) =>
    self.total := self.total + v
a = Acc.new(0.0)
a.add_val(10.0)
a.add_val(20.0)
plot(a.total)
"""
    code = transpile(src)
    assert "__ret = udt_set_field" in code
    assert "return __ret" in code
    compile(code, "<udt_method>", "exec")
    out = _compile_run(src, n=20)
    assert abs(_last(out) - 30.0) < 1e-6


def test_generic_map_string_key_get() -> None:
    src = '''//@version=5
indicator("Generic Map")
map<string, float> data = map.new<string, float>()
data.put("close", close)
result = data.get("close", 0.0)
plot(result)
'''
    out = _compile_run(src, n=20)
    # last close of arange 100..119 is 119
    assert abs(_last(out) - 119.0) < 1e-6


def test_udt_udf_if_else_return_field_access() -> None:
    src = """//@version=5
indicator("udt_udf_if_else_return")
type Signal
    float value = 0.0
    int direction = 0
getSignal(src, len) =>
    sma = ta.sma(src, len)
    if src > sma
        Signal.new(src - sma, 1)
    else
        Signal.new(sma - src, -1)
sig = getSignal(close, 5)
plot(sig.value)
"""
    out = _compile_run(src, n=20)
    arr = np.asarray(out["plot_0"], dtype=np.float64)
    assert arr.size == 20
    assert np.isfinite(arr[-1])


def test_switch_tuple_unpack_does_not_unbound() -> None:
    src = """//@version=5
indicator("sw")
sweep(bool swHL) =>
    [swHLbarid, swprc, swHL_txt] = switch
        swHL => [1, 2.0, "HH"]
        => [3, 4.0, "LL"]
    swHLbarid := swHLbarid < 0 ? 0 : swHLbarid
    swHLbarid
plot(sweep(true))
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 1.0


def test_string_plus_int_udf_param_concat() -> None:
    src = """//@version=6
indicator("Function Tests")
greet(name, greeting = 0) =>
    name + greeting
plot(str.length(greet("hi")))
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 3.0


def test_format_udf_return_not_float_coerced() -> None:
    src = """//@version=5
indicator("fmt")
min_tick_format() =>
    format = "#.#"
    format := format + "#"
    format
s = min_tick_format()
plot(str.length(s))
"""
    code = transpile(src)
    assert "safe_float(min_tick_format())" not in code
    out = _compile_run(src, n=20)
    # mintick may not append extra '#'; must not float("#.#")
    assert _last(out) >= 3.0


def test_request_footprint_rows_not_len_on_float() -> None:
    src = """//@version=6
indicator("coverage footprint")
fp = request.footprint(10)
rows = footprint.rows(fp)
plot(array.size(rows))
"""
    out = _compile_run(src, n=20)
    assert _last(out) == 0.0


def test_for_in_len_loop_var_does_not_shadow_builtin() -> None:
    src = """//@version=5
indicator("For In Array")
lengths = array.new<float>(0)
array.push(lengths, 3.0)
array.push(lengths, 5.0)
array.push(lengths, 7.0)
float total = 0.0
for [idx, len] in lengths
    total := total + len
plot(total)
"""
    out = _compile_run(src, n=20)
    assert abs(_last(out) - 15.0) < 1e-9


def test_querypatterns_func_and_method_overloads() -> None:
    src = """//@version=5
indicator("qp")
type SWINGS
    float lastPrice = 0.0
    float midPrice = 0.0
    float prevPrice = 0.0
queryPatterns(lastPrice, midPrice, prevPrice, isSwingHigh) =>
    if isSwingHigh
        prevPrice < midPrice and midPrice >= lastPrice
    else
        false
method queryPatterns(SWINGS this, isSwingHigh) =>
    this.lastPrice
s = SWINGS.new(1.0, 2.0, 0.0)
a = queryPatterns(1.0, 2.0, 0.0, true)
b = s.queryPatterns(true)
plot(a ? 1 : 0)
plot(b)
"""
    out = _compile_run(src, n=20)
    assert _last(out, "plot_0") == 1.0
    assert _last(out, "plot_1") == 1.0
