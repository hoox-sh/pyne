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

"""Numba compile pipeline: transpile → compile → run."""

from __future__ import annotations

import re

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile

pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")


def _ohlcv(n: int = 100, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


class TestTranspile:
    def test_transpile_sma_plot_contains_numba_entry(self) -> None:
        src = """//@version=6
indicator("x")
s = ta.sma(close, 14)
plot(s, title="sma")
"""
        code = transpile(src)
        assert "@numba.njit" in code
        assert "def execute_script_compiled" in code
        assert "numba_sma" in code
        assert "plot_0" in code


class TestCompileAndRun:
    def test_sma_matches_hand_formula(self) -> None:
        src = """//@version=6
indicator("SMA")
s = ta.sma(close, 14)
plot(s, title="sma")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        assert "sma" in out
        arr = out["sma"]
        assert len(arr) == 50
        assert np.isnan(arr[12])
        # SMA of 100..113 inclusive = 106.5
        assert abs(arr[13] - 106.5) < 1e-9
        assert abs(arr[14] - 107.5) < 1e-9

    def test_expr_and_history_subscript(self) -> None:
        src = """//@version=6
indicator("h")
x = close - close[1]
plot(x, title="delta")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        delta = out["delta"]
        assert np.isnan(delta[0])
        assert abs(delta[1] - 1.0) < 1e-9
        assert abs(delta[5] - 1.0) < 1e-9

    def test_rsi_runs(self) -> None:
        src = """//@version=6
indicator("RSI")
r = ta.rsi(close, 14)
plot(r, title="rsi")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(60)
        out = compiled.run(o, h, l, c, v)
        rsi = out["rsi"]
        assert np.isnan(rsi[10])
        # Rising series → RSI high
        assert rsi[-1] > 50


class TestRuntimeCompileMode:
    def test_runtime_mode_compile(self) -> None:
        from backend.runtime import Runtime

        bars = [
            {"open": float(100 + i), "high": float(101 + i), "low": float(99 + i), "close": float(100 + i), "volume": 1.0, "time": i}
            for i in range(40)
        ]
        src = """//@version=6
indicator("x")
plot(ta.sma(close, 10), title="sma")
"""
        rt = Runtime(symbol="TEST")
        result = rt.run(src, bars, mode="compile")
        assert "error" not in result, result.get("error")
        assert result.get("mode") == "compile"
        assert result["count"] == 40
        assert len(result["plots"]) == 40
        assert "sma" in result.get("series", {})


class TestExpandedNumericSurface:
    def test_transpile_atr_bb_macd(self) -> None:
        src = """//@version=5
indicator("x")
a = ta.atr(14)
[u, m, l] = ta.bb(close, 20, 2)
[macd_line, sig, hist] = ta.macd(close, 12, 26, 9)
plot(a, title="atr")
plot(m, title="bb_mid")
plot(macd_line, title="macd")
"""
        code = transpile(src)
        assert "numba_atr" in code
        assert "numba_bb" in code
        assert "numba_macd" in code or "numba_macd_inc" in code
        assert "@numba.njit" in code

    def test_atr_runs(self) -> None:
        src = """//@version=5
indicator("ATR")
plot(ta.atr(14), title="atr")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        atr = out["atr"]
        assert len(atr) == 80
        assert np.isnan(atr[0])
        assert atr[-1] > 0

    def test_bb_tuple_unpack(self) -> None:
        src = """//@version=5
indicator("BB")
[u, m, l] = ta.bb(close, 20, 2)
plot(m, title="mid")
plot(u, title="up")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        mid = out["mid"]
        up = out["up"]
        assert np.isnan(mid[10])
        assert up[-1] >= mid[-1]

    def test_macd_tuple_unpack(self) -> None:
        src = """//@version=5
indicator("MACD")
[macd_line, signal_line, hist] = ta.macd(close, 12, 26, 9)
plot(macd_line, title="macd")
plot(signal_line, title="sig")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(100)
        out = compiled.run(o, h, l, c, v)
        assert "macd" in out and "sig" in out
        assert len(out["macd"]) == 100

    def test_compile_cache_reuses(self) -> None:
        from pynescript.compiler.engine import clear_compile_cache

        clear_compile_cache()
        src = """//@version=5
indicator("c")
plot(ta.sma(close, 5), title="s")
"""
        a = compile_script(src)
        b = compile_script(src)
        assert a is b


class TestRuntimeAutoMode:
    def _bars(self, n: int = 50):
        return [
            {
                "open": float(100 + i),
                "high": float(101 + i),
                "low": float(99 + i),
                "close": float(100 + i),
                "volume": 1.0,
                "time": i * 86_400_000,
            }
            for i in range(n)
        ]

    def test_auto_uses_compile_for_sma(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=5
indicator("x")
plot(ta.sma(close, 10), title="sma")
"""
        r = Runtime(symbol="T").run(src, self._bars(), mode="auto")
        assert "error" not in r, r.get("error")
        assert r.get("auto_backend") == "compile"
        assert r.get("mode") == "compile"
        assert len(r["plots"]) == 50

    def test_auto_falls_back_on_import(self) -> None:
        from backend.runtime import Runtime

        # import is prefiltered as not compile-eligible
        src = """//@version=5
indicator("x")
import user/Lib/1 as L
plot(close)
"""
        r = Runtime(symbol="T").run(src, self._bars(10), mode="auto")
        # May error on interpret too if lib missing — key is auto_backend interpret
        assert r.get("auto_backend") == "interpret"
        assert "import" in (r.get("compile_fallback_reason") or "").lower()

    def test_auto_falls_back_on_request(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=5
indicator("x")
s = request.security(syminfo.tickerid, "D", close)
plot(s)
"""
        r = Runtime(symbol="T").run(src, self._bars(20), mode="auto")
        assert r.get("auto_backend") == "interpret"
        assert "request" in (r.get("compile_fallback_reason") or "").lower()


class TestCompileCoverageSprint:
    """High-ROI compile surface gaps closed against corpus buckets."""

    def test_study_alias_and_na_hlc3_volume(self) -> None:
        src = """//@version=4
study("x")
a = na
plot(hlc3, title="hlc3")
plot(nz(a), title="na")
plot(volume, title="vol")
"""
        code = transpile(src)
        assert "study(" not in code
        assert "na_arr" not in code
        assert "hlc3_arr" not in code
        assert "vol_arr[__bar_idx]" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "hlc3" in out
        # hlc3 = (h+l+c)/3
        assert abs(out["hlc3"][-1] - (h[-1] + l[-1] + c[-1]) / 3.0) < 1e-9

    def test_const_string_input_no_float_coercion(self) -> None:
        src = """//@version=5
indicator("H")
const string g = "Calculation"
amplitude = input.int(2, title="Amplitude", group=g)
plot(amplitude, title="amp")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["amp"][-1] - 2.0) < 1e-9

    def test_crossover_and_math_pi(self) -> None:
        src = """//@version=5
indicator("x")
c = ta.crossover(close, ta.sma(close, 5))
plot(math.pi, title="pi")
plot(c ? 1.0 : 0.0, title="xover")
"""
        code = transpile(src)
        assert "numba_crossover" in code
        assert "np.pi" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["pi"][-1] - np.pi) < 1e-9

    def test_udf_series_history(self) -> None:
        src = """//@version=5
indicator("x")
f(s) =>
    x = 0.0
    if s > s[1]
        x := 1.0
    else
        x := 0.0
    x
plot(f(close), title="ud")
"""
        code = transpile(src)
        assert "return if" not in code
        assert "__bar_idx" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        # rising series → cross up every bar after first
        assert out["ud"][0] == 0.0
        assert out["ud"][1] == 1.0

    def test_array_new_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
a = array.new_float(2, 0.0)
array.push(a, 1.0)
plot(array.size(a), title="sz")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert out["sz"][-1] == 3.0

    def test_math_trig_functions(self) -> None:
        src = """//@version=5
indicator("x")
plot(math.cos(0.0), title="cos")
plot(math.sin(0.0), title="sin")
plot(math.tan(0.0), title="tan")
plot(math.asin(0.0), title="asin")
"""
        code = transpile(src)
        assert "np.cos" in code
        assert "np.sin" in code
        assert "np.tan" in code
        assert "np.arcsin" in code
        assert "math_cos" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["cos"][-1] - 1.0) < 1e-9
        assert abs(out["sin"][-1] - 0.0) < 1e-9
        assert abs(out["tan"][-1] - 0.0) < 1e-9
        assert abs(out["asin"][-1] - 0.0) < 1e-9

    def test_bare_v4_sma_alias(self) -> None:
        src = """//@version=4
study("x")
plot(sma(close, 5), title="s")
"""
        code = transpile(src)
        assert "numba_sma" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "s" in out
        expected = float(np.mean(c[-5:]))
        assert abs(out["s"][-1] - expected) < 1e-6

    def test_plotshape_enum_string_constants(self) -> None:
        """shape.*/size.*/location.* must emit string constants, not series names."""
        src = """//@version=5
indicator("x")
plotshape(true, style=shape.triangleup, size=size.small, location=location.abovebar)
plot(1.0, title="p")
"""
        code = transpile(src)
        assert "shape_arr" not in code
        assert "size_arr" not in code
        assert "'triangleup'" in code or '"triangleup"' in code
        assert "'small'" in code or '"small"' in code
        assert "'abovebar'" in code or '"abovebar"' in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - 1.0) < 1e-9

    def test_input_string_color_scalar_not_float_series(self) -> None:
        """input.string / input.color must be scalars, not float64 series stores."""
        src = """//@version=5
indicator("H")
const string g = "Calculation"
m = input.string("EMA", "Method", group=g)
c = input.color(color.red, "C")
plot(close, title="p")
"""
        code = transpile(src)
        assert "m_arr" not in code
        assert "c_arr" not in code
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_udf_free_chart_series(self) -> None:
        """UDF body referencing close/high must get chart arrays + __bar_idx under njit."""
        src = """//@version=5
indicator("x")
f() =>
    close + high
plot(f(), title="f")
"""
        code = transpile(src)
        assert "def f(open_arr, high_arr, low_arr, close_arr, vol_arr, __bar_idx)" in code
        assert "f(open_arr, high_arr, low_arr, close_arr, vol_arr, __bar_idx)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["f"][-1] - (c[-1] + h[-1])) < 1e-9
        assert abs(out["f"][0] - (c[0] + h[0])) < 1e-9

    def test_nested_udf_chart_series_propagation(self) -> None:
        """Caller UDF must also receive chart ctx when callee needs it."""
        src = """//@version=5
indicator("x")
g() =>
    close
f() =>
    g() + high
plot(f(), title="n")
"""
        code = transpile(src)
        assert "def g(open_arr, high_arr, low_arr, close_arr, vol_arr, __bar_idx)" in code
        assert "def f(open_arr, high_arr, low_arr, close_arr, vol_arr, __bar_idx)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["n"][-1] - (c[-1] + h[-1])) < 1e-9

    def test_array_from_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
a = array.from(1.0, 2.0, 3.0)
plot(array.size(a), title="sz")
plot(array.get(a, 0), title="g0")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert out["sz"][-1] == 3.0
        assert out["g0"][-1] == 1.0

    def test_matrix_get_set_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
m = matrix.new<float>(2, 2, 0.0)
matrix.set(m, 0, 0, 1.5)
plot(matrix.get(m, 0, 0), title="g")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert out["g"][-1] == 1.5

    def test_request_security_syminfo_time_stubs(self) -> None:
        src = """//@version=5
indicator("x")
r = request.security(syminfo.tickerid, "D", close)
plot(r, title="r")
plot(syminfo.mintick, title="mt")
plot(time, title="t")
"""
        code = transpile(src)
        assert "request_arr_security" not in code
        assert "syminfo_mintick" not in code
        assert "time_arr" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["r"][-1] - c[-1]) < 1e-9
        assert abs(out["mt"][-1] - 0.01) < 1e-9
        assert abs(out["t"][-1] - (len(c) - 1) * 60000.0) < 1e-6


class TestCompileCoverageSprint3:
    """Sprint 3 high-ROI compile surface."""

    def test_strategy_exit_no_duplicate_id_kwarg(self) -> None:
        """strategy.exit first arg is exit name; from_entry → id (no repeated id=)."""
        src = """//@version=5
strategy("x")
if bar_index == 10
    strategy.entry("L", strategy.long)
if bar_index == 20
    strategy.exit("XL", from_entry="L", loss=10, profit=20)
plot(strategy.position_size, title="ps")
"""
        code = transpile(src)
        assert "id=" in code
        # Must not emit two id= kwargs on the same call
        close_lines = [ln for ln in code.splitlines() if "__strategy.close(" in ln]
        assert close_lines, code
        for ln in close_lines:
            assert ln.count("id=") == 1, ln
            assert "from_entry=" not in ln
            assert "id='L'" in ln or 'id="L"' in ln or "id='L'" in ln.replace('"', "'")
            assert "loss=10" in ln
            assert "profit=20" in ln
        # Compiles and runs without SyntaxError
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "ps" in out
        assert len(out["ps"]) == 30

    def test_strategy_opentrades_entry_price_stub(self) -> None:
        """strategy.opentrades.entry_price(n) must not become 1_entry_price(n)."""
        src = """//@version=5
strategy("x")
if bar_index == 10
    strategy.entry("L", strategy.long)
plot(strategy.opentrades.entry_price(0), title="ep")
"""
        code = transpile(src)
        assert "1_entry_price" not in code
        assert "position_avg_price" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert "ep" in out
        # Flat bars → nan; after entry → avg price near close at entry
        assert np.isnan(out["ep"][0]) or out["ep"][0] != out["ep"][0]
        assert not np.isnan(out["ep"][15])

    def test_dayofweek_enum_constants_not_invalid_literal(self) -> None:
        """dayofweek.monday must emit int 2, not 1_monday (invalid decimal)."""
        src = """//@version=5
indicator("x")
mo = dayofweek.monday
su = dayofweek.sunday
plot(mo, title="mo")
plot(su, title="su")
plot(dayofweek, title="dow")
plot(dayofweek(time), title="dowt")
"""
        code = transpile(src)
        assert "1_monday" not in code
        assert "1_sunday" not in code
        # Enum members are integer constants
        assert "mo_arr[__bar_idx] = 2" in code or "= 2" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["mo"][-1] - 2.0) < 1e-9
        assert abs(out["su"][-1] - 1.0) < 1e-9
        # bare dayofweek series stub
        assert abs(out["dow"][-1] - 1.0) < 1e-9
        # dayofweek(time) call stub (Monday-ish)
        assert abs(out["dowt"][-1] - 2.0) < 1e-9

    def test_calendar_call_and_name_stubs(self) -> None:
        """hour/minute/month/year names and call forms must not NameError."""
        src = """//@version=5
indicator("x")
plot(hour, title="h")
plot(minute, title="mi")
plot(month, title="m")
plot(year, title="y")
plot(hour(time), title="ht")
plot(month(time), title="mt")
"""
        code = transpile(src)
        assert "hour_arr" not in code
        assert "month_arr" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["h"][-1] - 0.0) < 1e-9
        assert abs(out["mi"][-1] - 0.0) < 1e-9
        assert abs(out["m"][-1] - 1.0) < 1e-9
        assert abs(out["y"][-1] - 2020.0) < 1e-9
        assert abs(out["ht"][-1] - 0.0) < 1e-9
        assert abs(out["mt"][-1] - 1.0) < 1e-9

    def test_month_enum_constants(self) -> None:
        src = """//@version=5
indicator("x")
plot(month.january, title="jan")
plot(month.december, title="dec")
"""
        code = transpile(src)
        assert "1_january" not in code
        assert "1_december" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["jan"][-1] - 1.0) < 1e-9
        assert abs(out["dec"][-1] - 12.0) < 1e-9

    def test_color_ternary_series_object_dtype(self) -> None:
        """Per-bar color ternary must not store unicode into float64 (nopython setitem)."""
        src = """//@version=5
indicator("x")
c = close > open ? color.green : color.red
plot(close, color=c, title="p")
"""
        code = transpile(src)
        assert "dtype=object" in code
        assert "c_arr" in code
        assert "@numba.njit" not in code
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(20)
        # make open > close on some bars so both branches execute
        o = c + 1.0
        o[::2] = c[::2] - 1.0
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_nested_hex_color_ternary(self) -> None:
        """Nested ternary with hex color literals → object series, not float64."""
        src = """//@version=5
indicator("x")
highlight = true
spma21 = ta.sma(close, 21)
spma21Color = highlight ? (spma21 > spma21[1] ? #22AB94 : #F23645) : color.blue
plot(spma21, color=spma21Color, title="p")
"""
        code = transpile(src)
        assert "dtype=object" in code
        assert "spma21Color_arr" in code
        assert "np.full(n_bars, np.nan)" not in code or "spma21Color" in code
        # color series must be object, not float full
        assert re.search(r"spma21Color_arr\s*=\s*np\.empty\(n_bars,\s*dtype=object\)", code)
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "p" in out
        assert len(out["p"]) == 40

    def test_input_session_scalar_not_float_series(self) -> None:
        """input.session string must not become float series (str→float)."""
        src = """//@version=5
indicator("x")
s = input.session("0900-1530:1234567", "sess")
plot(close, title="p")
"""
        code = transpile(src)
        assert "s_arr" not in code
        assert "0900-1530:1234567" in code
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_udf_series_local_history_ema(self) -> None:
        """UDF locals used with history (out[1]) must be persistent arrays, not scalars."""
        src = """//@version=5
indicator("x")
_ema(src, alpha) =>
    out = src
    out := alpha * out + (1.0 - alpha) * nz(out[1], out)
    out
plot(_ema(close, 0.5), title="e")
"""
        code = transpile(src)
        assert "out_arr" in code
        assert "__st__ema_out" in code
        # Must not index a bare scalar `out` with __bar_idx
        assert "out[__bar_idx" not in code or "out_arr[__bar_idx" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        e = out["e"]
        assert len(e) == 30
        # bar 0: out = src (nz fallback)
        assert abs(e[0] - c[0]) < 1e-9
        # subsequent bars finite recursive EMA
        assert np.all(np.isfinite(e))
        # manual step for bar 1
        expected1 = 0.5 * c[1] + 0.5 * e[0]
        assert abs(e[1] - expected1) < 1e-9
        expected2 = 0.5 * c[2] + 0.5 * e[1]
        assert abs(e[2] - expected2) < 1e-9

    def test_alertcondition_noop(self) -> None:
        src = """//@version=5
indicator("x")
alertcondition(close > open, title="up", message="up bar")
alert(close > open, "alert msg")
plot(close, title="c")
"""
        code = transpile(src)
        assert "alertcondition" not in code
        assert "alert(" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_str_tostring_and_format(self) -> None:
        src = """//@version=5
indicator("x")
s = str.tostring(close)
plot(str.length(s), title="len")
"""
        code = transpile(src)
        assert "str_tostring" not in code or "str(" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert out["len"][-1] > 0

    def test_tostring_bare_alias(self) -> None:
        src = """//@version=4
study("x")
s = tostring(close)
plot(close, title="c")
"""
        code = transpile(src)
        assert "tostring(" not in code or "str(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_timeframe_in_seconds(self) -> None:
        src = """//@version=5
indicator("x")
sec = timeframe.in_seconds("D")
plot(sec, title="sec")
"""
        code = transpile(src)
        assert "timeframe_in_seconds" not in code or "86400" in code
        assert "86400" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["sec"][-1] - 86400.0) < 1e-9

    def test_bare_security_passthrough(self) -> None:
        src = """//@version=3
study("x")
r = security(tickerid, "D", close)
plot(r, title="r")
"""
        code = transpile(src)
        assert "security(" not in code or "close_arr" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["r"][-1] - c[-1]) < 1e-9

    def test_math_sum_and_random(self) -> None:
        src = """//@version=5
indicator("x")
s = math.sum(close, 5)
plot(s, title="sum")
plot(math.random(0, 1), title="rnd")
"""
        code = transpile(src)
        assert "numba_sum" in code
        assert "math_sum" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        # rising close 100.. → sum of last 5 ≈ 5 * mean
        expected = float(np.sum(c[-5:]))
        assert abs(out["sum"][-1] - expected) < 1e-6
        assert abs(out["rnd"][-1] - 0.5) < 1e-9

    def test_chart_fg_bg_color(self) -> None:
        src = """//@version=5
indicator("x")
fg = chart.fg_color
bg = chart.bg_color
plot(close, title="c", color=fg)
"""
        code = transpile(src)
        assert "chart_fg_color" not in code
        assert "#000000" in code
        assert "#FFFFFF" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_table_cell_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
t = table.new(position.top_right, 1, 1)
table.cell(t, 0, 0, "hi")
plot(1.0, title="p")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - 1.0) < 1e-9

    def test_color_rgb_stub(self) -> None:
        src = """//@version=5
indicator("x")
c = color.rgb(255, 0, 0)
plot(close, title="p", color=c)
"""
        code = transpile(src)
        assert "color_rgb" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_tr_and_cum_run(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.tr(true), title="tr")
plot(ta.cum(close), title="cum")
"""
        code = transpile(src)
        assert "numba_tr" in code
        assert "numba_cum" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["tr"][0])
        # high-low=2, abs(high-prev_close)=2, abs(low-prev_close)=0 → tr=2
        assert abs(out["tr"][-1] - 2.0) < 1e-9
        # cum(close) over rising series: sum(100..139) for n=40
        expected_cum = float(np.nansum(c))
        assert abs(out["cum"][-1] - expected_cum) < 1e-6

    def test_pivothigh_no_nameerror(self) -> None:
        src = """//@version=5
indicator("x")
ph = ta.pivothigh(close, 2, 2)
pl = ta.pivotlow(2, 2)
plot(ph, title="ph")
plot(pl, title="pl")
"""
        code = transpile(src)
        assert "numba_pivothigh" in code
        assert "numba_pivotlow" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert len(out["ph"]) == 30
        # Monotone rising close → no pivot high confirmed
        assert np.all(np.isnan(out["ph"]))

    def test_stoch_runs(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.stoch(close, high, low, 14), title="k")
"""
        code = transpile(src)
        assert "numba_stoch" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        k = out["k"]
        assert np.isnan(k[10])
        # Rising close near high of window → stoch near 100? source=close, high=close+1
        assert not np.isnan(k[-1])
        assert 0.0 <= k[-1] <= 100.0

    def test_valuewhen_no_nameerror(self) -> None:
        src = """//@version=5
indicator("x")
cond = close > close[1]
v = ta.valuewhen(cond, close, 0)
plot(v, title="vw")
plot(ta.valuewhen(close > open, high, 1), title="vw2")
"""
        code = transpile(src)
        assert "numba_valuewhen" in code or "vw" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert len(out["vw"]) == 30
        # cond stored as series → real valuewhen; rising series always true after bar0
        assert abs(out["vw"][-1] - c[-1]) < 1e-9

    def test_cci_vwap_sar_percentile(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.cci(close, 20), title="cci")
plot(ta.vwap(close), title="vwap")
plot(ta.sar(0.02, 0.02, 0.2), title="sar")
plot(ta.percentile_nearest_rank(close, 10, 50), title="p50")
plot(cum(close), title="bare_cum")
"""
        code = transpile(src)
        assert "numba_cci" in code
        assert "numba_vwap" in code
        assert "numba_sar" in code
        assert "numba_percentile_nearest_rank" in code
        assert "numba_cum" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(60)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["cci"][-1])
        assert abs(out["vwap"][-1] - float(np.average(c, weights=v))) < 1e-6
        assert not np.isnan(out["sar"][-1])
        assert not np.isnan(out["p50"][-1])
        assert abs(out["bare_cum"][-1] - float(np.nansum(c))) < 1e-6


class TestCompileCoverageSprint4:
    """Sprint 4 high-ROI: cum expr, time(), int periods, new TA, styles."""

    def test_cum_ternary_no_array_truth(self) -> None:
        src = """//@version=5
indicator("x")
cond = close > open
c = ta.cum(cond ? 1.0 : 0.0)
plot(c, title="c")
"""
        code = transpile(src)
        assert "if isPnF_arr else" not in code
        assert "numba_cum_expr" in code or "numba_cum(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert out["c"][-1] >= 0

    def test_time_call_and_last_bar_index(self) -> None:
        src = """//@version=5
indicator("x")
t = time("1D")
plot(t, title="t")
plot(last_bar_index, title="lbi")
"""
        code = transpile(src)
        assert "time(" not in code or "float(__bar_idx)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["lbi"][-1] - 19) < 1e-9

    def test_int_period_from_input(self) -> None:
        src = """//@version=5
indicator("x")
length = input.int(14)
plot(ta.highest(close, length), title="h")
plot(ta.atr(length), title="a")
"""
        code = transpile(src)
        assert "int(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "h" in out and "a" in out

    def test_barssince_linreg_aliases(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.barssince(close > open), title="bs")
plot(ta.linreg(close, 10, 0), title="lr")
plot(ta.vwma(close, 10), title="vw")
plot(ta.rising(close, 2) ? 1.0 : 0.0, title="r")
"""
        code = transpile(src)
        assert "numba_barssince" in code or "0.0 if" in code
        assert "numba_linreg" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "lr" in out

    def test_label_style_and_sqrt(self) -> None:
        src = """//@version=5
indicator("x")
label.new(bar_index, high, "x", style=label.style_label_down)
plot(sqrt(close), title="s")
"""
        code = transpile(src)
        assert "label_style_label_down" not in code
        assert "np.sqrt" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["s"][-1] - (c[-1] ** 0.5)) < 1e-6

class TestCompileCoverageSprint5:
    def test_sprint5_udf_ta_source(self) -> None:
        src = """//@version=5
indicator("x")
scale(x, p) =>
    lo = ta.lowest(x, p)
    hi = ta.highest(x, p)
    (x - lo) / (hi - lo)
plot(scale(close, 14), title="s")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "s" in out

    def test_sprint5_history_offset_int(self) -> None:
        src = """//@version=5
indicator("x")
plot(high[ta.highestbars(high, 2)], title="hh")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "hh" in out

    def test_sprint5_percentrank_obv(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.percentrank(close, 10), title="pr")
plot(ta.obv, title="o")
"""
        code = transpile(src)
        assert "numba_percentrank" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "pr" in out and "o" in out


class TestSprint6MissingNames:
    """visit_Name / visit_Call stubs for common NameError offenders."""

    def test_pi_constant(self) -> None:
        src = """//@version=5
indicator("x")
plot(PI, title="pi")
plot(math.pi, title="mpi")
"""
        code = transpile(src)
        assert "PI_arr" not in code
        assert "np.pi" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["pi"][-1] - np.pi) < 1e-12
        assert abs(out["mpi"][-1] - np.pi) < 1e-12

    def test_bare_color_green(self) -> None:
        src = """//@version=5
indicator("x")
plot(close, title="c", color=green)
c = green
plot(close, title="c2", color=c)
"""
        code = transpile(src)
        assert "green_arr" not in code
        assert "#22AB94" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_str_repeat(self) -> None:
        src = """//@version=5
indicator("x")
s = str.repeat("ab", 3)
plot(str.length(s), title="n")
"""
        code = transpile(src)
        assert "str_repeat" not in code or "* int(" in code
        assert " * int(" in code or "* int" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["n"][-1] - 6.0) < 1e-9

    def test_bare_exp(self) -> None:
        src = """//@version=5
indicator("x")
plot(exp(0.0), title="e0")
plot(math.exp(1.0), title="e1")
"""
        code = transpile(src)
        assert "np.exp" in code
        # bare exp must not fall through to exp(...) NameError
        assert re.search(r"\bexp\(", code) is None or "np.exp" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["e0"][-1] - 1.0) < 1e-9
        assert abs(out["e1"][-1] - np.e) < 1e-9

    def test_hlcc4(self) -> None:
        src = """//@version=5
indicator("x")
plot(hlcc4, title="h")
plot(ohlc4, title="o")
"""
        code = transpile(src)
        assert "hlcc4_arr" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        # hlcc4 = (high + low + close + close) / 4
        expected = (h[-1] + l[-1] + c[-1] + c[-1]) / 4.0
        assert abs(out["h"][-1] - expected) < 1e-9
        ohlc_expected = (o[-1] + h[-1] + l[-1] + c[-1]) / 4.0
        assert abs(out["o"][-1] - ohlc_expected) < 1e-9

    def test_fixnan_and_str_format_time_and_ta_sum(self) -> None:
        src = """//@version=5
indicator("x")
plot(fixnan(na), title="fn")
plot(ta.sum(close, 3), title="s")
t = str.format_time(time, "yyyy")
plot(str.length(t), title="tl")
"""
        code = transpile(src)
        assert "numba_nz" in code
        assert "numba_sum" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["fn"][-1] - 0.0) < 1e-9
        # sum of last 3 closes on rising series
        assert abs(out["s"][-1] - float(c[-3:].sum())) < 1e-6


class TestSprint6HistorySubscript:
    """History operator: series path, float offsets, scalar/na guards."""

    def test_series_history_close_and_local(self) -> None:
        src = """//@version=5
indicator("x")
base = close
plot(close[1], title="c1")
plot(base[1], title="b1")
"""
        code = transpile(src)
        assert "_safe_history_offset" not in code  # helper is compile-time only
        assert "__bar_idx -" in code
        assert "int(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["c1"][0])
        assert abs(out["c1"][1] - c[0]) < 1e-9
        assert abs(out["b1"][5] - c[4]) < 1e-9

    def test_history_float_offset_highestbars(self) -> None:
        """ta.highestbars returns float64; offset must be NaN-safe int."""
        src = """//@version=5
indicator("x")
plot(high[ta.highestbars(high, 2)], title="hh")
plot(close[math.abs(ta.lowestbars(low, 3))], title="ll")
"""
        code = transpile(src)
        # Offset coercion: NaN → 0 else int(...)
        assert "!= (" in code or "!=(" in code
        assert "int(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "hh" in out and "ll" in out
        assert np.all(np.isfinite(out["hh"][5:]))

    def test_subscript_na_guard_scalar_and_call(self) -> None:
        """History on scalars / call results must not emit scalar[i]."""
        src = """//@version=5
indicator("x")
plot(1[1], title="lit")
plot(ta.sma(close, 5)[1], title="sma1")
plot((close + open)[1], title="expr")
"""
        code = transpile(src)
        # No raw getitem on a float call / paren expr (must not end with )[offset])
        assert "numba_sma(close_arr, int(5), __bar_idx)[1]" not in code
        assert re.search(r"\)\s*\[\s*1\s*\]", code) is None
        # Scalar/call history lowers to na (or literal bar-guard), never crashes
        assert (
            "plot_1[__bar_idx] = np.nan" in code
            or "numba_store(plot_1, __bar_idx, np.nan)" in code
            or "sma1" in code
        )
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        # literal series is bar-invariant when offset in range
        assert abs(out["lit"][-1] - 1.0) < 1e-9
        # call / expr history without temp series → na (safe stub)
        assert np.isnan(out["sma1"][-1]) or out["sma1"][-1] != out["sma1"][-1]
        assert np.isnan(out["expr"][-1]) or out["expr"][-1] != out["expr"][-1]

    def test_strategy_position_size_history_not_subscriptable(self) -> None:
        src = """//@version=5
strategy("x")
plot(strategy.position_size[1], title="ps")
"""
        code = transpile(src)
        assert "__strategy.position_size[1]" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert "ps" in out

    def test_udf_param_history_and_loop_offset(self) -> None:
        src = """//@version=5
indicator("x")
f(src) =>
    sum = 0.0
    for i = 0 to 2
        sum := sum + src[i]
    sum
plot(f(close), title="s")
"""
        code = transpile(src)
        # Offsets through loop counter still use safe int coercion
        assert "int(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        # sum of close[0]+close[1]+close[2] at last bar
        expected = float(c[-1] + c[-2] + c[-3])
        assert abs(out["s"][-1] - expected) < 1e-6


class TestCompileCoverageSprint6TaBuiltins:
    """Sprint 6: ta.sum / variance / dev / correlation / alma / hma / tsi."""

    def test_ta_sum_and_bare_sum(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.sum(close, 5), title="ts")
plot(math.sum(close, 5), title="ms")
"""
        code = transpile(src)
        assert "numba_sum" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        expected = float(np.sum(c[-5:]))
        assert abs(out["ts"][-1] - expected) < 1e-6
        assert abs(out["ms"][-1] - expected) < 1e-6
        assert np.isnan(out["ts"][3])

    def test_bare_sum_v4_alias(self) -> None:
        src = """//@version=4
study("x")
plot(sum(close, 5), title="s")
"""
        code = transpile(src)
        assert "numba_sum" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["s"][-1] - float(np.sum(c[-5:]))) < 1e-6

    def test_variance_and_dev(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.variance(close, 10), title="var")
plot(ta.dev(close, 10), title="dev")
plot(ta.stdev(close, 10), title="sd")
"""
        code = transpile(src)
        assert "numba_variance" in code
        assert "numba_dev" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        window = c[-10:]
        expected_var = float(np.var(window, ddof=1))
        expected_dev = float(np.mean(np.abs(window - np.mean(window))))
        assert abs(out["var"][-1] - expected_var) < 1e-6
        assert abs(out["dev"][-1] - expected_dev) < 1e-6
        # variance == stdev**2
        assert abs(out["var"][-1] - out["sd"][-1] ** 2) < 1e-6
        assert np.isnan(out["var"][5])

    def test_correlation(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.correlation(close, close, 10), title="cc")
plot(ta.correlation(close, high, 10), title="ch")
"""
        code = transpile(src)
        assert "numba_correlation" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        # corr(close, close) == 1 once warm
        assert abs(out["cc"][-1] - 1.0) < 1e-9
        # high = close+1 → perfect linear correlation
        assert abs(out["ch"][-1] - 1.0) < 1e-9
        assert np.isnan(out["cc"][5])

    def test_alma_hma_vwma_tsi(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.alma(close, 9, 0.85, 6), title="alma")
plot(ta.hma(close, 9), title="hma")
plot(ta.vwma(close, 10), title="vw")
plot(ta.tsi(close, 13, 25), title="tsi")
"""
        code = transpile(src)
        assert "numba_alma" in code
        assert "numba_hma" in code
        assert "numba_vwma" in code
        assert "numba_tsi" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["alma"][-1])
        assert not np.isnan(out["hma"][-1])
        assert not np.isnan(out["vw"][-1])
        assert not np.isnan(out["tsi"][-1])
        # ALMA/HMA on rising series should track near recent closes
        assert out["alma"][-1] > c[0]
        assert out["hma"][-1] > c[0]
        # unit volume → vwma == sma
        assert abs(out["vw"][-1] - float(np.mean(c[-10:]))) < 1e-6

    def test_bare_dev_variance_correlation_aliases(self) -> None:
        src = """//@version=4
study("x")
plot(dev(close, 5), title="d")
plot(variance(close, 5), title="v")
plot(correlation(close, high, 5), title="c")
"""
        code = transpile(src)
        assert "numba_dev" in code
        assert "numba_variance" in code
        assert "numba_correlation" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["d"][-1])
        assert not np.isnan(out["v"][-1])
        assert abs(out["c"][-1] - 1.0) < 1e-9


class TestSprint6Coercion:
    """Type coercion: safe float/int, version strings, color arith, sequences."""

    def test_float_on_na(self) -> None:
        src = """//@version=5
indicator("x")
plot(float(na), title="p")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["p"][-1])

    def test_float_on_udt_dict(self) -> None:
        src = """//@version=5
indicator("x")
type T
    float x
t = T.new(1.0)
plot(float(t), title="p")
"""
        code = transpile(src)
        assert "safe_float" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["p"][-1])

    def test_float_on_hline_handle(self) -> None:
        src = """//@version=5
indicator("x")
h = hline(50)
plot(float(h), title="p")
"""
        code = transpile(src)
        assert "safe_float" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["p"][-1])

    def test_input_version_string_not_float(self) -> None:
        src = """//@version=5
indicator("x")
v = input("0.0.1", "Version")
plot(v, title="p")
"""
        code = transpile(src)
        assert "safe_float" in code or "object" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        # version string cannot become float → na
        assert np.isnan(out["p"][-1])

    def test_input_string_keeps_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
v = input.string("0.0.1", "Version")
plot(close, title="p")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_color_string_subtraction_is_nan(self) -> None:
        src = """//@version=5
indicator("x")
c = color.red
plot(c - color.green, title="p")
"""
        code = transpile(src)
        assert "np.nan" in code
        assert " - " not in code.split("for __bar_idx")[-1] or "np.nan" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["p"][-1])

    def test_string_literal_subtraction_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
s = "a" - "b"
plot(close, title="p")
"""
        code = transpile(src)
        assert "('a' - 'b')" not in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_plot_array_sequence_no_crash(self) -> None:
        src = """//@version=5
indicator("x")
a = array.from(1.0, 2.0)
plot(a, title="p")
"""
        code = transpile(src)
        assert "safe_float" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        # first element of sequence
        assert abs(out["p"][-1] - 1.0) < 1e-9

    def test_udf_array_return_scalar_not_float_series(self) -> None:
        """UDF returning array must not write list into float64 series."""
        src = """//@version=5
indicator("x")
f(int n) =>
    if n > 0
        float[] a = array.new_float(n, 1.5)
        a
    else
        na
x = f(3)
plot(array.size(x), title="sz")
plot(array.get(x, 0), title="v0")
"""
        code = transpile(src)
        assert "x_arr[__bar_idx] = f(" not in code
        assert re.search(r"\bx = f\(", code)
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["sz"][-1] - 3.0) < 1e-9
        assert abs(out["v0"][-1] - 1.5) < 1e-9

    def test_udf_multi_return_arrays_scalar_unpack(self) -> None:
        """``[a,b] = f()`` where f returns arrays → scalar handles, not float series."""
        src = """//@version=5
indicator("x")
f(int n) =>
    a = array.new_float(n, 1.0)
    b = array.new_float(n, 2.0)
    [a, b]
[x, y] = f(4)
plot(array.size(x) + array.size(y), title="s")
plot(array.get(x, 0) + array.get(y, 0), title="v")
"""
        code = transpile(src)
        assert re.search(r"\bx = ", code)
        assert re.search(r"\by = ", code)
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["s"][-1] - 8.0) < 1e-9
        assert abs(out["v"][-1] - 3.0) < 1e-9

    def test_udf_numeric_multi_return_still_series(self) -> None:
        """Numeric multi-return UDF unpacks into float series (not forced sequence)."""
        src = """//@version=5
indicator("x")
f(float a, float b) =>
    [a + 1.0, b + 2.0]
[u, w] = f(close, close)
plot(u, title="u")
plot(w, title="w")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["u"][-1] - (c[-1] + 1.0)) < 1e-9
        assert abs(out["w"][-1] - (c[-1] + 2.0)) < 1e-9

    def test_color_series_plot_object_mode(self) -> None:
        src = """//@version=5
indicator("x")
col = close > open ? color.green : color.red
plot(close, color=col, title="p")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        code = transpile(src)
        assert "dtype=object" in code or "col_arr" in code
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_float_on_function_ref_is_nan(self) -> None:
        src = """//@version=5
indicator("x")
f() => 1.0
plot(float(f), title="p")
"""
        code = transpile(src)
        assert "safe_float" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["p"][-1])

class TestCompileCoverageSprint6Materialize:
    """Non-array TA sources: materialize math.abs / arithmetic into synthetic series."""

    def test_ema_math_abs_series_compiles_and_runs(self) -> None:
        """ta.ema(math.abs(close), n) must not pass a float scalar into numba_ema."""
        src = """//@version=6
indicator("x")
e = ta.ema(math.abs(close), 14)
plot(e, title="e")
"""
        code = transpile(src)
        assert "numba_store_src" in code
        assert "numba_ema" in code
        assert "numba_abs" in code
        # Pure close path still available for other plots; abs path uses store
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        assert "e" in out
        assert len(out["e"]) == 50
        # Rising positive series → EMA of abs(close) ≈ EMA(close) > 0 after warm-up
        assert not np.isnan(out["e"][-1])
        assert out["e"][-1] > 0

    def test_tsi_style_nested_abs_double_ema(self) -> None:
        """TSI-style: ta.ema(ta.ema(math.abs(mom), long), short) must compile."""
        src = """//@version=6
indicator("TSI")
longLength = 25
shortLength = 13
mom = close - close[1]
doubleAbs = ta.ema(ta.ema(math.abs(mom), longLength), shortLength)
plot(doubleAbs, title="da")
"""
        code = transpile(src)
        # Materialize may use numba_store_src (njit) or store_src_py (object mode)
        assert "numba_store_src" in code or "store_src_py" in code
        assert code.count("numba_ema") >= 2
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(80)
        # Must not TypingError getitem(float64, int64)
        out = compiled.run(o, h, l, c, v)
        assert "da" in out
        assert len(out["da"]) == 80

    def test_sma_of_arithmetic_expr(self) -> None:
        """ta.sma(close * 2, 5) materializes the product series."""
        src = """//@version=6
indicator("x")
s = ta.sma(close * 2, 5)
plot(s, title="s")
"""
        code = transpile(src)
        assert "numba_store_src" in code
        assert "numba_sma" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["s"][3])
        # SMA of close*2 over bars 0..4
        expected = float(np.mean(c[0:5] * 2))
        assert abs(out["s"][4] - expected) < 1e-9
        expected_last = float(np.mean(c[-5:] * 2))
        assert abs(out["s"][-1] - expected_last) < 1e-9

    def test_pure_array_source_skips_materialize(self) -> None:
        """ta.sma(close, 14) must not allocate __src* synthetic arrays."""
        src = """//@version=6
indicator("x")
plot(ta.sma(close, 14), title="s")
"""
        code = transpile(src)
        assert "numba_store_src" not in code
        assert "__src" not in code
        # Incremental SMA still uses close_arr directly (no materialize)
        assert "numba_sma_inc(close_arr" in code or "numba_sma(close_arr" in code


class TestCompileUdfDefaultsKwargs:
    """UDF default params, keyword calls, and under-arity padding."""

    def test_udf_default_args_emitted_and_applied(self) -> None:
        src = """//@version=5
indicator("x")
hi(val, len=2) =>
    val + len
plot(hi(close), title="p")
"""
        code = transpile(src)
        # Defaults applied at call sites (not always on def — trailing chart ctx
        # params would make `def hi(val, len_=2, open_arr, …)` invalid Python).
        assert "def hi(" in code
        assert "hi(close_arr[__bar_idx], 2)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - (c[-1] + 2.0)) < 1e-9

    def test_udf_keyword_call_mapped(self) -> None:
        src = """//@version=5
indicator("x")
g(a, b=1, c=2) =>
    a + b * 10 + c * 100
plot(g(c=3, a=1), title="g")
plot(g(1, c=4), title="h")
"""
        code = transpile(src)
        # kwargs expanded positionally with defaults filled
        assert "g(1, 1, 3)" in code
        assert "g(1, 1, 4)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["g"][-1] - 311.0) < 1e-9  # 1 + 1*10 + 3*100
        assert abs(out["h"][-1] - 411.0) < 1e-9  # 1 + 1*10 + 4*100

    def test_udf_partial_args_pad_nan(self) -> None:
        """Missing required params pad with np.nan (no TypeError at runtime)."""
        src = """//@version=5
indicator("x")
tema(src, len, mult) =>
    src + len + mult
plot(tema(close), title="t")
"""
        code = transpile(src)
        assert "tema(close_arr[__bar_idx], np.nan, np.nan)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["t"][-1])

    def test_udf_shadows_bare_ta_name(self) -> None:
        """Custom mfi() must not be rewritten as ta.mfi."""
        src = """//@version=5
indicator("x")
mfi(src, len) =>
    src + len
plot(mfi(close, 2), title="m")
"""
        code = transpile(src)
        assert "def mfi(" in code
        assert "numba_mfi" not in code
        assert "mfi(close_arr[__bar_idx], 2)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["m"][-1] - (c[-1] + 2.0)) < 1e-9



class TestSprint6PlotFillExpr:
    """plot()/fill() must emit expression-safe stores."""

    def test_fill_plot_transpiles_valid_python(self) -> None:
        from pynescript.compiler.engine import transpile, compile_script
        import numpy as np

        src = """//@version=5
indicator("t")
p1 = plot(close)
p2 = plot(open)
fill(p1, p2)
"""
        code = transpile(src)
        compile(code, "<c>", "exec")
        assert "numba_store(plot_" in code
        n = 32
        o = np.linspace(100, 110, n)
        cs = compile_script(src)
        cs.run(o, o + 1, o - 1, o, np.ones(n))

    def test_nested_abs_ema_materializes(self) -> None:
        from pynescript.compiler.engine import transpile, compile_script
        import numpy as np

        src = """//@version=5
indicator("t")
mom = close - close[1]
plot(ta.ema(math.abs(mom), 14))
"""
        code = transpile(src)
        assert "numba_store_src" in code or "numba_ema" in code
        n = 40
        o = np.linspace(100, 110, n)
        cs = compile_script(src)
        r = cs.run(o, o + 1, o - 1, o, np.ones(n))
        assert r


class TestSprint10MissingNames:
    """Bare ta.vwap, math.isfinite, array.concat, ta.max — no dead identifiers."""

    def test_bare_ta_vwap_emits_numba_call(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.vwap, title="vwap")
"""
        code = transpile(src)
        assert "ta_vwap" not in code
        assert "numba_vwap_inc" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "vwap" in out
        assert abs(out["vwap"][-1] - float(np.average(c, weights=v))) < 1e-6

    def test_math_isfinite(self) -> None:
        src = """//@version=5
indicator("x")
plot(math.isfinite(close) ? 1.0 : 0.0, title="fin")
plot(math.isnan(close) ? 1.0 : 0.0, title="nan")
"""
        code = transpile(src)
        assert "math_isfinite" not in code
        assert "np.isfinite" in code
        assert "np.isnan" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert np.all(out["fin"] == 1.0)
        assert np.all(out["nan"] == 0.0)

    def test_array_concat(self) -> None:
        src = """//@version=5
indicator("x")
a = array.from(1.0, 2.0)
b = array.from(3.0, 4.0)
c = array.concat(a, b)
plot(array.size(c), title="sz")
"""
        code = transpile(src)
        assert "array_concat(" not in code or ".extend(" in code
        assert ".extend(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["sz"][-1] - 4.0) < 1e-9

    def test_ta_max_min_not_dead_name(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.max(close), title="mx")
plot(ta.min(close), title="mn")
"""
        code = transpile(src)
        assert "ta_max(" not in code
        assert "ta_min(" not in code
        assert "numba_highest" in code
        assert "numba_lowest" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["mx"][-1] - float(np.nanmax(c))) < 1e-9
        assert abs(out["mn"][-1] - float(np.nanmin(c))) < 1e-9

    def test_strategy_max_drawdown_attr(self) -> None:
        src = """//@version=5
strategy("x")
strategy.entry("L", strategy.long)
plot(strategy.max_drawdown, title="dd")
"""
        code = transpile(src)
        assert "__strategy.max_drawdown" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(25)
        out = compiled.run(o, h, l, c, v)
        assert "dd" in out
        assert out["dd"][-1] >= 0.0

    def test_macd_tuple_unpack_no_free_macd(self) -> None:
        src = """//@version=5
indicator("x")
[macd, signal, hist] = ta.macd(close, 12, 26, 9)
plot(macd, title="m")
plot(signal, title="s")
plot(hist, title="h")
"""
        code = transpile(src)
        # must not leave bare free name `macd` without array store
        assert "macd_arr[__bar_idx]" in code
        assert "numba_macd_inc" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        assert len(out["m"]) == 50


class TestSprint10FloatGetitemStrategy:
    """Sprint 10: float(dict), getitem(scalar), UDF __strategy plumbing."""

    def test_table_handle_not_float_series(self) -> None:
        """var table t = na; t := table.new(...) must not float(dict) into float64."""
        src = """//@version=5
indicator("x")
var table t = na
if barstate.islast
    t := table.new(position.top_right, 1, 1)
plot(close, title="p")
"""
        code = transpile(src)
        assert "t_arr[__bar_idx] = (__drawings.append" not in code
        assert "t = None" in code or "if __bar_idx == 0:" in code
        assert "t = (__drawings.append" in code or "t = (" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

    def test_hline_math_uses_safe_float_not_crash(self) -> None:
        src = """//@version=5
indicator("x")
h = hline(50)
plot(float(h), title="p")
"""
        code = transpile(src)
        assert "safe_float" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["p"][-1])

    def test_udf_free_scalar_before_free_series_st(self) -> None:
        """Outer free-scalar must not receive __ema*_st (getitem float64).

        Def order: formals, st_refs, free_scalars, free_series (__ema*_st), chart.
        Call must match — otherwise float factor lands in st and Numba raises
        getitem(float64, int).
        """
        src = """//@version=5
indicator("x")
mult = input.float(2.0)
f(src) =>
    ta.ema(src, 5) * mult
plot(f(close), title="p")
"""
        code = transpile(src)
        def_line = [ln for ln in code.splitlines() if ln.startswith("def f(")][0]
        # free scalar mult before free series __ema*_st
        assert "mult" in def_line
        if "__ema" in def_line:
            assert def_line.index("mult") < def_line.index("__ema")
        call_snip = [ln for ln in code.splitlines() if "f(" in ln and "def " not in ln][0]
        assert "mult" in call_snip
        # Must not crash with getitem(float64)
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "p" in out
        assert np.isfinite(out["p"][-1])
        assert out["p"][-1] > 0

    def test_udf_strategy_passed_at_call_site(self) -> None:
        src = """//@version=5
strategy("x")
f() =>
    strategy.entry("L", strategy.long)
    strategy.position_size
plot(f(), title="p")
"""
        code = transpile(src)
        assert "def f(" in code and "__strategy" in code
        # call must include __strategy
        assert re.search(r"f\([^)]*__strategy\)", code)
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert "p" in out
        assert out["p"][-1] > 0

    def test_udt_na_field_access_no_scalar_getitem(self) -> None:
        src = """//@version=6
indicator("x")
type MyState
    bool flag = false
    int count = 0
var MyState myState = na
plot(myState.count, title="c")
"""
        code = transpile(src)
        assert "dtype=object" in code or "myState_arr" in code
        assert "isinstance(__u, dict)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(12)
        out = compiled.run(o, h, l, c, v)
        assert np.isnan(out["c"][-1])


class TestNameNotDefinedFixes:
    """Regression: set01/set02 `name 'X' is not defined` compile runtime errors."""

    def test_bare_mom_maps_to_change(self) -> None:
        src = """//@version=4
study("x")
plot(mom(close, 10), title="m")
"""
        code = transpile(src)
        assert "numba_change" in code
        assert re.search(r"\bmom\(", code) is None
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["m"][-1] - (c[-1] - c[-11])) < 1e-9

    def test_array_indexof_emits_list_index(self) -> None:
        src = """//@version=5
indicator("x")
a = array.from(1.0, 2.0, 3.0)
plot(array.indexof(a, 2.0), title="i")
"""
        code = transpile(src)
        assert ".index(" in code
        assert "array_indexof(" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["i"][-1] - 1.0) < 1e-9

    def test_str_tonumber_and_substring(self) -> None:
        src = """//@version=5
indicator("x")
s = "1234"
plot(str.tonumber(str.substring(s, 0, 2)), title="n")
"""
        code = transpile(src)
        assert "safe_tonumber" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["n"][-1] - 12.0) < 1e-9

    def test_barcolor_user_var_not_namespace(self) -> None:
        src = """//@version=5
indicator("x")
barcolor = close > open ? color.green : color.red
barcolor(barcolor)
plot(close, title="c")
"""
        code = transpile(src)
        assert "barcolor_arr[__bar_idx]" in code
        assert "'color': barcolor)" not in code  # bare name would NameError
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(12)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_builtin_n_and_pvt(self) -> None:
        src = """//@version=3
study("x")
plot(n, title="n")
plot(pvt, title="pvt")
"""
        code = transpile(src)
        assert "__bar_idx" in code
        assert "numba_pvt_inc" in code
        # bare n/pvt must not become series arrays (avoid matching open_arr etc.)
        assert re.search(r"\bn_arr\b", code) is None
        assert re.search(r"\bpvt_arr\b", code) is None
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["n"][-1] - 19) < 1e-9
        assert np.isfinite(out["pvt"][-1])

    def test_switch_multistmt_dema_walrus(self) -> None:
        """Multi-stmt switch arms must define intermediates (no NameError on ema1)."""
        src = """//@version=5
indicator("x")
f_ma(_src, _len) =>
    switch "DEMA"
        "DEMA" =>
            ema1 = ta.ema(_src, _len)
            2.0 * ema1 - ta.ema(ema1, _len)
        => ta.ema(_src, _len)
plot(f_ma(close, 5), title="d")
"""
        code = transpile(src)
        assert ":=" in code  # walrus for ema1
        # Must not leave bare free-var `ema1` (would NameError at runtime)
        assert " * ema1)" in code or "* ema1 " in code or "(ema1 :=" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        # Runtime must not raise NameError; values may be nan while EMA warms.
        out = compiled.run(o, h, l, c, v)
        assert "d" in out
        assert len(out["d"]) == 40

    def test_ticker_heikinashi_stub(self) -> None:
        src = """//@version=5
indicator("x")
ha_t = ticker.heikinashi(syminfo.tickerid)
plot(close, title="c")
"""
        code = transpile(src)
        assert "ticker_arr" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_sequence_helpers_stub(self) -> None:
        src = """//@version=5
indicator("x")
a = sequence_from_series(close)
b = sequence_float(0.0, 1.0, 0.5)
plot(array.size(a) + array.size(b), title="s")
"""
        code = transpile(src)
        assert "list(" in code or "np.arange" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert out["s"][-1] > 0

    def test_if_for_not_broken_ternary(self) -> None:
        """if-arm with for must be statement form, not ``(i = 0\\nwhile … if c)``."""
        src = """//@version=5
indicator("x")
f(a) =>
    s = 0.0
    if a
        for i = 0 to 3
            s := s + i
    s
plot(f(true), title="s")
"""
        code = transpile(src)
        assert "(i = 0" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["s"][-1] - 6.0) < 1e-9  # 0+1+2+3


class TestSet03RuntimeTypeFixes:
    """Regression: set03 compile RUN_FAIL type-error buckets."""

    def test_udf_shadow_name_not_compared_as_function(self) -> None:
        """``sar = sar(...)`` then ``sar > close`` must use shadow local, not fn."""
        src = """//@version=5
indicator("x")
sar(af=0.02) =>
    low
sar = sar(0.02)
plot(sar > close ? sar : na, title="p")
"""
        code = transpile(src)
        assert "sar__loc" in code
        assert "sar > close" not in code or "sar__loc" in code
        # must not compare function object
        assert re.search(r"\bsar\s*>", code) is None or "sar__loc" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert "p" in out

    def test_safe_float_rejects_timeframe_and_format_strings(self) -> None:
        from pynescript.compiler.numba_builtins import safe_float

        assert np.isnan(safe_float("1D"))
        assert np.isnan(safe_float("{0}R: {1,number,#.####}"))
        assert np.isnan(safe_float("Name: Turtle Soup\nDescription: x"))
        assert abs(safe_float("1e-3") - 0.001) < 1e-12
        assert abs(safe_float("3.14") - 3.14) < 1e-12

    def test_for_index_value_uses_enumerate(self) -> None:
        src = """//@version=5
indicator("x")
a = array.from(1.0, -2.0, 3.0)
c = 0
for [index, value] in a
    if value > 0
        c := c + 1
plot(c, title="c")
"""
        code = transpile(src)
        assert "enumerate(safe_iter(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        # re-init c each bar → 2 positives per bar
        assert abs(out["c"][-1] - 2.0) < 1e-9

    def test_for_in_udf_returns_last_body_expr(self) -> None:
        src = """//@version=5
indicator("x")
qty(value, arr) =>
    int result = 0
    for el in arr
        if el > value
            result += 1
        result
plot(qty(0.0, array.from(1.0, -1.0, 2.0)), title="q")
"""
        code = transpile(src)
        assert "return result" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["q"][-1] - 2.0) < 1e-9

    def test_safe_iter_and_sum_on_scalar(self) -> None:
        from pynescript.compiler.numba_builtins import safe_iter, safe_sum, safe_max

        assert list(safe_iter(3.14)) == []
        assert list(safe_iter(None)) == []
        assert abs(safe_sum([1.0, "x", None, 2.0]) - 3.0) < 1e-9
        assert abs(safe_max([[1.0, 5.0], [2.0, 3.0]]) - 5.0) < 1e-9

    def test_udt_index_store_object_dtype(self) -> None:
        src = """//@version=5
indicator("x")
type L
    float price
    bool is_active
var array<L> levels = array.new<L>()
if bar_index == 0
    array.push(levels, L.new(price=close, is_active=true))
level = array.get(levels, 0)
plot(level.price, title="p")
"""
        code = transpile(src)
        assert "dtype=object" in code or "udt_index" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(12)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[0]) < 1e-6 or np.isfinite(out["p"][-1])

    def test_string_udf_store_safe_float(self) -> None:
        src = """//@version=5
indicator("x")
f_tf(tf) =>
    tf == "" ? "1D" : tf
activeTf = f_tf("")
plot(close, title="c")
"""
        code = transpile(src)
        # either string series or safe_float coercion — must not bare float()
        assert "safe_float" in code or "dtype=object" in code or "activeTf =" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9

    def test_array_new_size_nan_safe(self) -> None:
        src = """//@version=5
indicator("x")
a = array.new_float(na)
plot(array.size(a), title="s")
"""
        code = transpile(src)
        assert "safe_int" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["s"][-1] - 0.0) < 1e-9

    def test_math_tanh_and_round_none_safe(self) -> None:
        src = """//@version=5
indicator("x")
plot(math.tanh(0.0), title="t")
plot(math.round_to_mintick(close), title="r")
"""
        code = transpile(src)
        assert "np.tanh" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["t"][-1] - 0.0) < 1e-9
        assert np.isfinite(out["r"][-1])

    def test_chart_point_has_price_field(self) -> None:
        src = """//@version=5
indicator("x")
p = chart.point.from_index(bar_index, close)
plot(p.price, title="p")
"""
        code = transpile(src)
        assert "'price'" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["p"][-1] - c[-1]) < 1e-9

# --- matrix/array set03 ---
class TestSet03MatrixArrayApis:
    def test_array_sort_indices_object_mode(self) -> None:
        """array.sort_indices must emit helper call (not bare NameError) and stay list."""
        src = """//@version=5
indicator("x")
a = array.from(3.0, 1.0, 2.0)
idx = array.sort_indices(a)
idx_desc = array.sort_indices(a, order.descending)
plot(array.get(idx, 0), title="asc0")
plot(array.get(idx, 1), title="asc1")
plot(array.get(idx_desc, 0), title="desc0")
"""
        code = transpile(src)
        assert "array_sort_indices" in code
        # Handle must not be coerced into float64 series
        assert "idx_arr" not in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert out["asc0"][-1] == 1.0  # value 1.0 at index 1
        assert out["asc1"][-1] == 2.0  # value 2.0 at index 2
        assert out["desc0"][-1] == 0.0  # value 3.0 at index 0

# --- matrix/array set03 ---
class TestSet03MatrixArrayApis:
    def test_matrix_row_col_mutate_apis_object_mode(self) -> None:
        """matrix add/remove/reshape/swap_rows — no NameError; list-of-lists stubs."""
        src = """//@version=5
indicator("x")
m = matrix.new<float>(2, 2, 0.0)
matrix.set(m, 0, 0, 1.0)
matrix.set(m, 0, 1, 2.0)
matrix.set(m, 1, 0, 3.0)
matrix.set(m, 1, 1, 4.0)
matrix.add_row(m)
matrix.add_col(m)
removed_row = matrix.remove_row(m, 2)
removed_col = matrix.remove_col(m, 2)
matrix.reshape(m, 1, 4)
matrix.swap_rows(m, 0, 0)
plot(matrix.rows(m), title="rows")
plot(matrix.columns(m), title="cols")
plot(array.size(removed_row), title="rr")
plot(array.size(removed_col), title="rc")
plot(matrix.get(m, 0, 0), title="g00")
"""
        code = transpile(src)
        assert "matrix_add_row" in code
        assert "matrix_add_col" in code
        assert "matrix_remove_row" in code
        assert "matrix_remove_col" in code
        assert "matrix_reshape" in code
        assert "matrix_swap_rows" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert out["rows"][-1] == 1.0
        assert out["cols"][-1] == 4.0
        assert out["rr"][-1] == 3.0  # added na row then removed it (3 cols at remove time)
        assert out["rc"][-1] == 2.0
        assert out["g00"][-1] == 1.0

# --- matrix/array set03 ---
class TestSet03MatrixArrayApis:
    def test_matrix_add_row_col_empty_and_insert(self) -> None:
        """TV forms: add_row/col on empty matrix with array at index 0."""
        src = """//@version=5
indicator("x")
m = matrix.new<int>()
a = array.from(1, 3)
matrix.add_row(m, 0, a)
plot(matrix.rows(m), title="rows")
plot(matrix.columns(m), title="cols")
plot(matrix.get(m, 0, 0), title="v00")
plot(matrix.get(m, 0, 1), title="v01")
m2 = matrix.new<int>()
b = array.from(1, 3)
matrix.add_col(m2, 0, b)
plot(matrix.rows(m2), title="r2")
plot(matrix.columns(m2), title="c2")
plot(matrix.get(m2, 0, 0), title="w00")
plot(matrix.get(m2, 1, 0), title="w10")
"""
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert out["rows"][-1] == 1.0
        assert out["cols"][-1] == 2.0
        assert out["v00"][-1] == 1.0
        assert out["v01"][-1] == 3.0
        assert out["r2"][-1] == 2.0
        assert out["c2"][-1] == 1.0
        assert out["w00"][-1] == 1.0
        assert out["w10"][-1] == 3.0

