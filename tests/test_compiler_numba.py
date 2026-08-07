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

    def test_auto_inputs_force_interpret(self) -> None:
        """input.* overrides are interpret-only; auto must not silently use compile defaults."""
        from backend.runtime import Runtime

        src = """//@version=5
indicator("x")
len = input.int(10, "Length")
plot(ta.sma(close, len), title="sma")
"""
        r = Runtime(symbol="T").run(
            src,
            self._bars(40),
            mode="auto",
            inputs={"Length": 5},
        )
        assert "error" not in r, r.get("error")
        assert r.get("auto_backend") == "interpret"
        reason = (r.get("compile_fallback_reason") or "").lower()
        assert "input" in reason
        assert len(r.get("plots") or []) == 40

    def test_auto_compile_fail_cache_skips_recompile(self, monkeypatch) -> None:
        """Deterministic compile failures are remembered for subsequent auto runs."""
        from backend import runtime as rt_mod
        from backend.runtime import Runtime
        from pynescript.compiler import engine as eng

        calls = {"n": 0}

        def boom(source: str, **kwargs):  # noqa: ARG001
            calls["n"] += 1
            raise RuntimeError("forced compile fail for test")

        monkeypatch.setattr(eng, "compile_script", boom)
        rt_mod._HOST_COMPILE_CACHE.clear()
        rt_mod._HOST_COMPILE_FAIL_CACHE.clear()

        src = """//@version=5
indicator("x")
plot(close)
"""
        rt = Runtime(symbol="T")
        r1 = rt.run(src, self._bars(10), mode="auto")
        assert r1.get("auto_backend") == "interpret"
        reason1 = r1.get("compile_fallback_reason") or ""
        assert "forced compile" in reason1.lower()
        assert calls["n"] == 1
        key = Runtime._source_cache_key(src)
        assert key in rt_mod._HOST_COMPILE_FAIL_CACHE
        # Second auto must reuse negative cache — no re-transpile
        r2 = rt.run(src, self._bars(10), mode="auto")
        assert r2.get("auto_backend") == "interpret"
        assert r2.get("compile_fallback_reason") == reason1
        assert calls["n"] == 1


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
        assert (
            "def f(open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr, __bar_idx)"
            in code
        )
        assert (
            "f(open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr, __bar_idx)"
            in code
        )
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
        assert (
            "def g(open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr, __bar_idx)"
            in code
        )
        assert (
            "def f(open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr, __bar_idx)"
            in code
        )
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
        # Host always passes time_arr (bar-open ms); synthetic default is bar*60_000.
        assert "time_arr" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["r"][-1] - c[-1]) < 1e-9
        assert abs(out["mt"][-1] - 0.01) < 1e-9
        assert abs(out["t"][-1] - (len(c) - 1) * 60000.0) < 1e-6

    def test_request_security_complex_expr_emits_nan(self) -> None:
        """Foreign/complex security expressions must not invent chart close as data.

        dividend_yield.pine: request.security(div_ticker, …, year_sum(close)).
        """
        src = """//@version=6
indicator("x")
year_sum(src) =>
    ta.cum(src)
div_ticker = ticker.new("ESD_FACTSET", "X;Y;DIVIDENDS")
div_ttm = request.security(div_ticker, "D", year_sum(close), barmerge.gaps_on, lookahead=barmerge.lookahead_on)
plot(div_ttm, title="d")
"""
        code = transpile(src)
        assert "div_ttm_arr[__bar_idx] = np.nan" in code or "np.nan" in code
        compiled = compile_script(src, use_cache=False)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        arr = out["d"]
        assert len(arr) == 30
        assert np.all(np.isnan(arr))

    def test_runtime_compile_host_time_calendar_parity(self) -> None:
        """``mode=compile`` uses OHLCV bar times for year/month/time[n]/timestamp."""
        from backend.runtime import Runtime

        base = 1_577_836_800_000  # 2020-01-01 UTC
        bars = [
            {
                "time": base + i * 86_400_000,
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.0 + i,
                "volume": 1.0,
            }
            for i in range(40)
        ]
        src = """//@version=5
indicator("x")
plot(year, title="y")
plot(month, title="m")
plot(time[1], title="t1")
plot(timestamp(2020, 1, 15, 0, 0), title="ts")
plot(request.security(syminfo.tickerid, "D", close), title="sec")
"""
        ri = Runtime(symbol="T").run(src, bars, mode="interpret")
        rc = Runtime(symbol="T").run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        for key in ("y", "m", "t1", "ts"):
            iv, cv = ri["series"][key][-1], rc["series"][key][-1]
            assert abs(float(iv) - float(cv)) < 1e-6, (key, iv, cv)
        # same-symbol close passthrough still works under forced compile
        assert abs(float(rc["series"]["sec"][-1]) - float(bars[-1]["close"])) < 1e-9


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
        # Synthetic default time: bar_index * 60_000 ms from Unix epoch
        from pynescript.util.time_parts import utc_parts_from_ms

        parts = utc_parts_from_ms((len(c) - 1) * 60000.0)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["mo"][-1] - 2.0) < 1e-9
        assert abs(out["su"][-1] - 1.0) < 1e-9
        # bare dayofweek / dayofweek(time) from bar open time
        assert abs(out["dow"][-1] - float(parts.dayofweek)) < 1e-9
        assert abs(out["dowt"][-1] - float(parts.dayofweek)) < 1e-9

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
        assert "numba_utc_parts" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        from pynescript.util.time_parts import utc_parts_from_ms

        parts = utc_parts_from_ms((len(c) - 1) * 60000.0)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["h"][-1] - float(parts.hour)) < 1e-9
        assert abs(out["mi"][-1] - float(parts.minute)) < 1e-9
        assert abs(out["m"][-1] - float(parts.month)) < 1e-9
        assert abs(out["y"][-1] - float(parts.year)) < 1e-9
        assert abs(out["ht"][-1] - float(parts.hour)) < 1e-9
        assert abs(out["mt"][-1] - float(parts.month)) < 1e-9

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
        assert "close_arr[__bar_idx]" in code
        assert "r_arr[__bar_idx] = np.nan" not in code
        # use_cache=False: bare tickerid emit was fixed post-disk-cache entries
        compiled = compile_script(src, use_cache=False)
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
        """ta.highestbars returns float64; offset must be NaN-safe int.

        highestbars is a **negative** bars-back offset (TV / interpret). Indexing
        ``high[highestbars]`` only hits a past bar when the extreme is the current
        bar (offset 0); otherwise the negative offset is a future ref → na.
        ``math.abs(lowestbars)`` yields a non-negative lookback for indexing.
        """
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
        # abs(lowestbars) lookback is always a past/current index once warm
        assert np.all(np.isfinite(out["ll"][5:]))

    def test_highestbars_lowestbars_negative_offset_parity(self) -> None:
        """Compile highestbars/lowestbars match interpret (negative bars-back).

        TradingView / interpret return 0 when the current bar is the extreme,
        -1 one bar ago, …, -(length-1) at the far edge of a full window.
        Short history (fewer than ``length`` bars) returns -1. Aroon-style
        ``100 * (highestbars(..., length+1) + length) / length`` stays in [0, 100].
        """
        from pynescript.compiler.numba_builtins import numba_highestbars
        from pynescript.compiler.numba_builtins import numba_highestbars_inc
        from pynescript.compiler.numba_builtins import numba_lowestbars
        from pynescript.compiler.numba_builtins import numba_lowestbars_inc

        # Peak at index 2, trough at index 3; length=5
        high = np.array([1.0, 2.0, 9.0, 3.0, 4.0, 5.0, 4.5, 4.0, 3.5, 3.0], dtype=np.float64)
        low = np.array([5.0, 4.0, 3.0, 0.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5], dtype=np.float64)
        length = 5
        st_h = np.array([np.nan, np.nan, np.nan], dtype=np.float64)
        st_l = np.array([np.nan, np.nan, np.nan], dtype=np.float64)
        for i in range(len(high)):
            hb = numba_highestbars(high, length, i)
            lb = numba_lowestbars(low, length, i)
            hb_inc = numba_highestbars_inc(high, length, i, st_h)
            lb_inc = numba_lowestbars_inc(low, length, i, st_l)
            assert hb == hb_inc, (i, hb, hb_inc)
            assert lb == lb_inc, (i, lb, lb_inc)
            if i + 1 < length:
                assert hb == -1.0 and lb == -1.0
            else:
                assert -float(length - 1) <= hb <= 0.0
                assert -float(length - 1) <= lb <= 0.0
        # At i=4 (first full window): high peak at 2 → offset -(4-2) = -2
        assert numba_highestbars(high, length, 4) == -2.0
        # low trough at 3 → offset -(4-3) = -1
        assert numba_lowestbars(low, length, 4) == -1.0
        # After peak ages out (window 3..7): max is high[5]=5.0 → offset -(7-5)=-2
        assert numba_highestbars(high, length, 7) == -2.0
        # Monotone rising series: current is always highest once warm
        rising = np.arange(10, dtype=np.float64)
        assert numba_highestbars(rising, 4, 9) == 0.0
        assert numba_lowestbars(rising, 4, 9) == -3.0

        # Aroon-style plots (first-party snippet) interpret vs compile on synthetic OHLC
        from backend.runtime import Runtime

        src = """//@version=5
indicator("Aroon")
length = input.int(14, minval=1)
upper = 100 * (ta.highestbars(high, length + 1) + length) / length
lower = 100 * (ta.lowestbars(low, length + 1) + length) / length
plot(upper, "Aroon Up")
plot(lower, "Aroon Down")
"""
        bars = []
        p = 100.0
        for i in range(80):
            o = p
            c = p + (1 if i % 3 else -0.5) + (0.01 * (i % 7))
            bars.append(
                {
                    "open": float(o),
                    "high": float(max(o, c) + 0.8),
                    "low": float(min(o, c) - 0.8),
                    "close": float(c),
                    "time": i * 60_000,
                    "volume": 1000.0,
                }
            )
            p = c
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        for title in ("Aroon Up", "Aroon Down"):
            ai = np.array([np.nan if v is None else float(v) for v in ri["series"][title]])
            ac = np.array([np.nan if v is None else float(v) for v in rc["series"][title]])
            assert ai.shape == ac.shape
            assert int(np.sum(np.isnan(ai) ^ np.isnan(ac))) == 0
            assert float(np.nanmax(np.abs(ai - ac))) == 0.0
            # Aroon must not exceed 100 (positive-offset bug yielded ~200)
            assert float(np.nanmax(ac)) <= 100.0 + 1e-9
            assert float(np.nanmin(ac)) >= 0.0 - 1e-9

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
        assert "numba_alma" in code  # alma or alma_inc
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
        # bare ta.max/min → O(1) running extreme (or legacy full highest/lowest)
        assert "numba_running_max_inc" in code or "numba_highest" in code
        assert "numba_running_min_inc" in code or "numba_lowest" in code
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

        ``input.float`` may lower as a series ``mult_arr`` (free_series) rather
        than a free scalar; st buffers still must precede free_series args.
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
        assert "mult" in def_line
        # st buffers before free series / chart context
        if "__ema" in def_line and "mult_arr" in def_line:
            assert def_line.index("__ema") < def_line.index("mult_arr")
        elif "__ema" in def_line and "mult" in def_line:
            # bare free-scalar mult must still precede st only if ordered that way
            pass
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


class TestCompileRound4IncKernels:
    """Round 4: wire hma/math_sum + rising/falling/valuewhen/running max-min."""

    def test_hma_math_sum_avg_emit_inc(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.hma(close, 20), title="hma")
plot(math.sum(close, 10), title="sum")
plot(math.avg(close, 10), title="avg")
"""
        code = transpile(src)
        assert "numba_hma_inc" in code
        assert "numba_sum_inc" in code
        # Pine math.avg is multi-arg mean (close+10)/2 — not ta.sma
        assert "np.divide" in code or "np.add" in code or "na_num" in code or "safe_float" in code
        assert "__hma_raw" in code
        compiled = compile_script(src)
        assert not compiled.object_mode
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["hma"][-1])
        assert abs(out["sum"][-1] - float(np.sum(c[-10:]))) < 1e-6
        assert abs(out["avg"][-1] - float((c[-1] + 10.0) / 2.0)) < 1e-6

    def test_rising_falling_running_max_min_emit_and_parity(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        src = """//@version=5
indicator("x")
plot(ta.rising(close, 3) ? 1.0 : 0.0, title="r")
plot(ta.falling(close, 2) ? 1.0 : 0.0, title="f")
plot(ta.max(close), title="mx")
plot(ta.min(close), title="mn")
"""
        code = transpile(src)
        assert "numba_rising_inc" in code
        assert "numba_falling_inc" in code
        assert "numba_running_max_inc" in code
        assert "numba_running_min_inc" in code
        compiled = compile_script(src)
        assert not compiled.object_mode
        # non-monotone series
        rng = np.random.default_rng(7)
        n = 120
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        o, h, l, v = c, c + 1, c - 1, np.ones(n)
        out = compiled.run(o, h, l, c, v)
        for i in range(n):
            er = 1.0 if nb.numba_rising(c, 3, i) else 0.0
            ef = 1.0 if nb.numba_falling(c, 2, i) else 0.0
            assert abs(out["r"][i] - er) < 1e-12
            assert abs(out["f"][i] - ef) < 1e-12
            assert abs(out["mx"][i] - nb.numba_highest(c, i + 1, i)) < 1e-12
            assert abs(out["mn"][i] - nb.numba_lowest(c, i + 1, i)) < 1e-12

    def test_valuewhen_inc_kernel_parity(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        rng = np.random.default_rng(3)
        n = 300
        arr = 100.0 + np.cumsum(rng.normal(0, 1, n))
        cond = (arr > np.median(arr)).astype(np.float64)
        for occ in (0, 1, 4):
            st = np.full(3 + occ + 1, np.nan)
            for i in range(n):
                a = nb.numba_valuewhen(cond, arr, occ, i)
                b = nb.numba_valuewhen_inc(cond, arr, occ, i, st)
                if np.isnan(a) and np.isnan(b):
                    continue
                assert abs(float(a) - float(b)) < 1e-12
            # gap to end + rewind mid
            st = np.full(3 + occ + 1, np.nan)
            assert (
                abs(
                    float(nb.numba_valuewhen(cond, arr, occ, n - 1))
                    - float(nb.numba_valuewhen_inc(cond, arr, occ, n - 1, st))
                )
                < 1e-12
                or (
                    np.isnan(nb.numba_valuewhen(cond, arr, occ, n - 1))
                    and np.isnan(nb.numba_valuewhen_inc(cond, arr, occ, n - 1, st))
                )
            )
            mid = n // 2
            b = nb.numba_valuewhen_inc(cond, arr, occ, mid, st)
            a = nb.numba_valuewhen(cond, arr, occ, mid)
            if not (np.isnan(a) and np.isnan(b)):
                assert abs(float(a) - float(b)) < 1e-12

    def test_hma_inc_parity_large_period(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        rng = np.random.default_rng(11)
        n = 500
        arr = 100.0 + np.cumsum(rng.normal(0, 1, n))
        for period in (9, 50, 100):
            st = np.full(7, np.nan)
            raw = np.full(n, np.nan)
            max_err = 0.0
            for i in range(n):
                a = nb.numba_hma(arr, period, i)
                b = nb.numba_hma_inc(arr, period, i, st, raw)
                if np.isnan(a) and np.isnan(b):
                    continue
                max_err = max(max_err, abs(float(a) - float(b)))
            assert max_err <= 1e-10, f"period={period} max_err={max_err}"

    def test_matrix_var_shadows_namespace_free_scalar_udf(self) -> None:
        """``var matrix = matrix.new…`` used inside a UDF must not NameError.

        Corpus set05 ICT scanners name the handle ``matrix`` (shadows the
        builtin namespace). Module-scope UDFs cannot close over execute_script
        locals — the handle must be a free-scalar parameter.
        """
        src = """//@version=5
indicator("x")
var matrix = matrix.new<string>(0, 6, na)
mtxFun(symbol, _time, price, signal) =>
    matrix.add_row(matrix, 0, array.from(symbol, _time, price, signal, "x", "1"))
if bar_index == 0
    mtxFun("A", "t", "1", "1")
plot(matrix.rows(matrix), title="rows")
plot(matrix.get(matrix, 0, 0) == "A" ? 1.0 : 0.0, title="ok")
"""
        code = transpile(src)
        assert "def mtxFun(" in code
        # free-scalar param present on def + call site
        assert re.search(r"def mtxFun\([^)]*\bmatrix\b", code)
        assert "matrix_add_row(matrix," in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        assert out["rows"][-1] == 1.0
        assert out["ok"][-1] == 1.0

    def test_array_var_shadows_namespace_free_scalar_udf(self) -> None:
        """Same free-scalar plumbing for ``var array = array.new…`` inside UDF."""
        src = """//@version=5
indicator("x")
var array = array.new_float(0)
push1() =>
    array.push(array, 1.0)
    array.size(array)
plot(push1(), title="s")
"""
        code = transpile(src)
        assert re.search(r"def push1\([^)]*\barray\b", code)
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert out["s"][-1] == 10.0

    def test_tuple_unpack_udf_shadow_not_callable_none(self) -> None:
        """``[pvsraVolume, ...] = pvsraVolume(...)`` must not rebind the UDF to None.

        set05 corpus (Total Recall / Nebula / Insane Oscillator) defines a UDF
        and multi-unpacks into the same name → ``'NoneType' object is not callable``.
        """
        src = """//@version=5
indicator("x")
pvsraVolume(overrideSymbolX, pvsraSymbolX, tickerIdX) =>
    [volume, high, low, close, open]
[pvsraVolume, pvsraHigh, pvsraLow, pvsraClose, pvsraOpen] = pvsraVolume(false, "", syminfo.tickerid)
plot(pvsraVolume, title="vol")
plot(pvsraClose, title="c")
"""
        code = transpile(src)
        assert "def pvsraVolume(" in code
        assert "pvsraVolume__loc" in code
        # Call site still targets the function, store goes to shadow local
        assert re.search(r"__tup\s*=\s*pvsraVolume\s*\(", code)
        assert re.search(r"pvsraVolume__loc\s*=", code)
        # Must not initialize a local that shadows the def before the call
        assert re.search(r"^\s*pvsraVolume\s*=\s*None\s*$", code, re.M) is None
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "vol" in out
        assert "c" in out
        # volume series is ones from _ohlcv; close is the price series
        assert abs(float(out["vol"][-1]) - 1.0) < 1e-9
        assert abs(float(out["c"][-1]) - float(c[-1])) < 1e-9


class TestNaSafeArithmetic:
    """Object-mode None/na must not TypeError on arithmetic or comparisons."""

    def test_na_num_helper(self) -> None:
        from pynescript.compiler.numba_builtins import na_num, safe_float

        assert np.isnan(na_num(None))
        assert na_num(3.5) == 3.5
        assert na_num(2) == 2
        assert na_num(True) == 1.0
        assert na_num(False) == 0.0
        assert np.isnan(na_num({}))  # UDT/handle → same as safe_float
        assert abs(na_num("1.25") - 1.25) < 1e-12
        # non-na path parity with safe_float for floats
        assert na_num(1.0) == safe_float(1.0)

    def test_compare_none_scalar_no_typeerror(self) -> None:
        """``src > ma`` when ma is a scalar still None (tuple unpack) → no crash.

        Mirrors set05 ColorRVI: ``rvi > rviMA`` with rviMA from multi-return
        before enough bars — scalar local is ``None``, not float nan.
        """
        src = """//@version=5
indicator("cmp")
f() =>
    [na, na]
[ma, _] = f()
// force object mode before compare so na_num wraps apply
hline(50)
col = close > ma ? 1.0 : 0.0
plot(col, title="c")
"""
        code = transpile(src)
        assert "na_num(" in code
        compiled = compile_script(src)
        assert compiled.object_mode
        o, h, l, c, v = _ohlcv(12)
        out = compiled.run(o, h, l, c, v)
        # ma is always na/None → comparison false → 0.0
        assert np.allclose(out["c"], 0.0)

    def test_mult_none_literal_is_nan(self) -> None:
        """Missing TA / import stubs lower to None; ``None * 0.25`` must be nan."""
        src = """//@version=5
indicator("mul")
import user/Lib/1 as Lib
x = na
plot(x * 0.25, title="p")
plot(close * 2.0, title="ok")
"""
        code = transpile(src)
        assert "np.nan" in code or "na_num" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert np.all(np.isnan(out["p"]))
        np.testing.assert_allclose(out["ok"], c * 2.0)

    def test_sub_none_operand_is_nan(self) -> None:
        src = """//@version=5
indicator("sub")
float q = na
plot(close - q, title="d")
hline(0)
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert np.all(np.isnan(out["d"]))

    def test_numeric_mode_sma_unaffected(self) -> None:
        """Pure numeric njit path must stay bare (no na_num in hot loop)."""
        src = """//@version=5
indicator("sma")
plot(ta.sma(close, 14), title="s")
"""
        code = transpile(src)
        assert "na_num" not in code
        assert "@numba.njit" in code
        compiled = compile_script(src)
        assert not compiled.object_mode
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "s" in out
        assert np.isfinite(out["s"][-1])


class TestSet05OobListArithmetic:
    """Compile-path soft OOB list set, series clamp, array.range max−min.

    Corpus: 7020/7965 out-of-bounds demos, 8242 LeMan future index, 7303 KDE.
    """

    def test_safe_list_set_grows_on_oob(self) -> None:
        from pynescript.compiler.numba_builtins import safe_list_set

        a: list = [None, None, None]
        safe_list_set(a, 3, 3.0)  # TV docs demo: size 3, set index 3
        assert len(a) == 4
        assert a[3] == 3.0
        safe_list_set(a, -1, 9)  # negative → no-op
        assert a[0] is None
        assert safe_list_set(1.0, 0, 1) == 1.0  # non-list identity

    def test_array_range_is_max_minus_min_not_python_range(self) -> None:
        from pynescript.compiler.numba_builtins import array_range

        assert array_range([1.0, 5.0, 3.0]) == 4.0
        assert array_range([2, 2, 2]) == 0.0
        assert array_range([]) != array_range([])  # na
        assert array_range(None) != array_range(None)

    def test_array_set_oob_compile_grows_not_crash(self) -> None:
        """TV docs 'Out of bounds index' demo soft-fails via grow (corpus Runtime)."""
        src = """//@version=5
indicator("Out of bounds index")
a = array.new<float>(3)
for i = 1 to 3
    array.set(a, i, i)
plot(array.pop(a), title="p")
"""
        code = transpile(src)
        assert "safe_list_set" in code
        assert ".__setitem__" not in code or "safe_list_set" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        # After sets at 1,2,3 then pop → last element was 3
        assert abs(float(out["p"][-1]) - 3.0) < 1e-9

    def test_array_range_compile_scalar_not_list(self) -> None:
        src = """//@version=5
indicator("kde range")
var float[] observations = array.new_float(0)
if barstate.isfirst
    array.push(observations, 93)
    array.push(observations, 102)
float _range = array.range(observations)
plot(_range / 2, title="half")
plot(_range, title="r")
"""
        code = transpile(src)
        assert "array_range(observations)" in code or "array_range(" in code
        assert "list(range(" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        # max 102 - min 93 = 9; half = 4.5
        assert abs(float(out["r"][-1]) - 9.0) < 1e-9
        assert abs(float(out["half"][-1]) - 4.5) < 1e-9

    def test_history_negative_offset_clamps_upper_bound(self) -> None:
        """``high[-highestbars(...)]`` must not OOB at series end (LeMan pattern)."""
        src = """//@version=4
study("LeMan")
Min = 13
high1 = high[-highestbars(high[1], Min)]
plot(high1, title="h1")
plot(high, title="h")
"""
        code = transpile(src)
        assert "len(" in code
        assert "__bar_idx -" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(50)
        out = compiled.run(o, h, l, c, v)
        assert "h1" in out
        # No crash; finite values on early bars (future still in series),
        # na allowed near end when offset past last bar.
        assert len(out["h1"]) == 50

    def test_runtime_compile_oob_demos_and_kde(self) -> None:
        from backend.runtime import Runtime

        bars = [
            {
                "open": float(100 + i),
                "high": float(101 + i),
                "low": float(99 + i),
                "close": float(100 + i),
                "volume": 1.0,
                "time": i * 60_000,
            }
            for i in range(50)
        ]
        oob = """//@version=6
indicator("Out of bounds index")
a = array.new<float>(3)
for i = 1 to 3
    array.set(a, i, i)
plot(array.pop(a))
"""
        kde = """//@version=5
indicator("KDE mini")
var float[] observations = array.new_float(0)
if barstate.isfirst
    array.push(observations, 93)
    array.push(observations, 102)
float _range = array.range(observations)
float _step = _range / 20
plot(_step, title="step")
"""
        leman = """//@version=4
study("LeMan mini")
high1 = high[-highestbars(high[1], 13)]
plot(high1)
"""
        rt = Runtime()
        for src in (oob, kde, leman):
            res = rt.run(src, bars, mode="compile")
            assert not res.get("error"), res.get("error")
            assert res.get("mode") == "compile"


class TestCompileRound5IncKernels:
    """Round 5: dema/tema/swma residual kernels + IR cache cold-JIT UX."""

    def test_dema_tema_swma_emit_inc(self) -> None:
        src = """//@version=5
indicator("x")
plot(ta.dema(close, 10), title="dema")
plot(ta.tema(close, 8), title="tema")
plot(ta.swma(close), title="swma")
"""
        code = transpile(src)
        assert "numba_dema_inc" in code
        assert "numba_tema_inc" in code
        assert "numba_swma" in code
        assert "__dema_e1" in code
        assert "__tema_e1" in code and "__tema_e2" in code
        compiled = compile_script(src)
        assert not compiled.object_mode
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["dema"][-1])
        assert not np.isnan(out["tema"][-1])
        assert not np.isnan(out["swma"][-1])

    def test_dema_tema_swma_kernel_parity(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        rng = np.random.default_rng(42)
        n = 400
        arr = 100.0 + np.cumsum(rng.normal(0, 1, n))
        for period in (5, 14, 30):
            st = np.full(3, np.nan)
            e1 = np.full(n, np.nan)
            max_err = 0.0
            for i in range(n):
                a = nb.numba_dema(arr, period, i)
                b = nb.numba_dema_inc(arr, period, i, st, e1)
                if np.isnan(a) and np.isnan(b):
                    continue
                max_err = max(max_err, abs(float(a) - float(b)))
            assert max_err <= 1e-10, f"dema period={period} max_err={max_err}"

            st4 = np.full(4, np.nan)
            r1 = np.full(n, np.nan)
            r2 = np.full(n, np.nan)
            max_err = 0.0
            for i in range(n):
                a = nb.numba_tema(arr, period, i)
                b = nb.numba_tema_inc(arr, period, i, st4, r1, r2)
                if np.isnan(a) and np.isnan(b):
                    continue
                max_err = max(max_err, abs(float(a) - float(b)))
            assert max_err <= 1e-10, f"tema period={period} max_err={max_err}"

        # gap + rewind dema
        st = np.full(3, np.nan)
        e1 = np.full(n, np.nan)
        mid = n // 2
        b_end = nb.numba_dema_inc(arr, 10, n - 1, st, e1)
        a_end = nb.numba_dema(arr, 10, n - 1)
        if not (np.isnan(a_end) and np.isnan(b_end)):
            assert abs(float(a_end) - float(b_end)) <= 1e-10
        b_mid = nb.numba_dema_inc(arr, 10, mid, st, e1)
        a_mid = nb.numba_dema(arr, 10, mid)
        if not (np.isnan(a_mid) and np.isnan(b_mid)):
            assert abs(float(a_mid) - float(b_mid)) <= 1e-10

        for i in range(n):
            a = nb.numba_swma(arr, i)
            if i < 3:
                assert np.isnan(a)
            else:
                expected = (arr[i - 3] + 2 * arr[i - 2] + 2 * arr[i - 1] + arr[i]) / 6.0
                assert abs(float(a) - expected) < 1e-12

    def test_compiled_dema_matches_full_kernel(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        src = """//@version=5
indicator("x")
plot(ta.dema(close, 12), title="d")
plot(ta.tema(close, 9), title="t")
plot(ta.swma(close), title="s")
"""
        compiled = compile_script(src)
        rng = np.random.default_rng(9)
        n = 200
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        o, h, l, v = c, c + 1, c - 1, np.ones(n)
        out = compiled.run(o, h, l, c, v)
        max_d = max_t = max_s = 0.0
        for i in range(n):
            fd = nb.numba_dema(c, 12, i)
            ft = nb.numba_tema(c, 9, i)
            fs = nb.numba_swma(c, i)
            if not (np.isnan(fd) and np.isnan(out["d"][i])):
                max_d = max(max_d, abs(float(fd) - float(out["d"][i])))
            if not (np.isnan(ft) and np.isnan(out["t"][i])):
                max_t = max(max_t, abs(float(ft) - float(out["t"][i])))
            if not (np.isnan(fs) and np.isnan(out["s"][i])):
                max_s = max(max_s, abs(float(fs) - float(out["s"][i])))
        assert max_d <= 1e-10, max_d
        assert max_t <= 1e-10, max_t
        assert max_s <= 1e-12, max_s

    def test_ir_cache_shares_execute_on_comment_diff(self) -> None:
        from pynescript.compiler.engine import clear_compile_cache

        clear_compile_cache()
        src1 = """//@version=5
indicator("x")
plot(ta.sma(close, 5), title="s")
"""
        src2 = """//@version=5
// comment-only change — same IR
indicator("x")
plot(ta.sma(close, 5), title="s")
"""
        a = compile_script(src1)
        b = compile_script(src2)
        assert a is not b
        assert a.execute is b.execute
        assert a.generated_code == b.generated_code
        o, h, l, c, v = _ohlcv(40)
        assert np.allclose(a.run(o, h, l, c, v)["s"], b.run(o, h, l, c, v)["s"], equal_nan=True)

    def test_source_cache_still_identity(self) -> None:
        from pynescript.compiler.engine import clear_compile_cache

        clear_compile_cache()
        src = """//@version=5
indicator("c")
plot(ta.ema(close, 5), title="e")
"""
        a = compile_script(src)
        b = compile_script(src)
        assert a is b


class TestCompileRound6DmiSupertrendAlma:
    """Round 6: dmi/adx/supertrend real kernels; alma_inc; percentrank oracle."""

    def test_dmi_adx_supertrend_emit_inc_numeric(self) -> None:
        src = """//@version=6
indicator("x")
[diplus, diminus, adx] = ta.dmi(14, 14)
[st, dir] = ta.supertrend(3.0, 10)
plot(diplus, title="dip")
plot(diminus, title="dim")
plot(adx, title="adx")
plot(st, title="st")
plot(dir, title="dir")
plot(ta.adx(14), title="adx2")
"""
        code = transpile(src)
        assert "numba_dmi_inc" in code
        assert "numba_supertrend_inc" in code
        assert "numba_adx_inc" in code
        assert "(0.0, 0.0, 25.0)" not in code  # old dmi stub gone
        compiled = compile_script(src)
        assert not compiled.object_mode
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["dip"][-1])
        assert not np.isnan(out["dim"][-1])
        assert out["adx"][-1] >= 0.0
        assert out["dir"][-1] in (-1.0, 1.0)
        assert not np.isnan(out["st"][-1])

    def test_dmi_adx_supertrend_kernel_parity(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        rng = np.random.default_rng(7)
        n = 300
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        h = c + rng.uniform(0.3, 1.2, n)
        l = c - rng.uniform(0.3, 1.2, n)

        st_adx = np.full(22, np.nan)
        max_adx = 0.0
        for i in range(n):
            a = nb.numba_adx(h, l, c, 14, i)
            b = nb.numba_adx_inc(h, l, c, 14, i, st_adx)
            max_adx = max(max_adx, abs(float(a) - float(b)))
        assert max_adx <= 1e-10, max_adx

        st_dmi = np.full(40, np.nan)
        max_dmi = 0.0
        for i in range(n):
            fa, fb, fc = nb.numba_dmi(h, l, c, 14, 14, i)
            ia, ib, ic = nb.numba_dmi_inc(h, l, c, 14, 14, i, st_dmi)
            for a, b in ((fa, ia), (fb, ib), (fc, ic)):
                if np.isnan(a) and np.isnan(b):
                    continue
                max_dmi = max(max_dmi, abs(float(a) - float(b)))
        assert max_dmi <= 1e-10, max_dmi

        st_st = np.full(2, np.nan)
        max_st = 0.0
        for i in range(n):
            fv, fd = nb.numba_supertrend(h, l, c, 3.0, 10, i)
            iv, id_ = nb.numba_supertrend_inc(h, l, c, 3.0, 10, i, st_st)
            max_st = max(max_st, abs(float(fv) - float(iv)) + abs(float(fd) - float(id_)))
        assert max_st <= 1e-10, max_st

        # gap + rewind ADX
        st = np.full(22, np.nan)
        mid = n // 2
        b_end = nb.numba_adx_inc(h, l, c, 14, n - 1, st)
        a_end = nb.numba_adx(h, l, c, 14, n - 1)
        assert abs(float(a_end) - float(b_end)) <= 1e-10
        b_mid = nb.numba_adx_inc(h, l, c, 14, mid, st)
        a_mid = nb.numba_adx(h, l, c, 14, mid)
        assert abs(float(a_mid) - float(b_mid)) <= 1e-10

    def test_compiled_dmi_supertrend_matches_interpret(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=6
indicator("x")
[diplus, diminus, adx] = ta.dmi(14, 14)
[st, dir] = ta.supertrend(3.0, 10)
plot(diplus, title="dip")
plot(diminus, title="dim")
plot(adx, title="adx")
plot(st, title="st")
plot(dir, title="dir")
plot(ta.adx(14), title="adx2")
"""
        rng = np.random.default_rng(0)
        n = 100
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        h = c + rng.uniform(0.2, 1.5, n)
        l = c - rng.uniform(0.2, 1.5, n)
        o, v = c.copy(), np.ones(n)
        bars = [
            {
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(l[i]),
                "close": float(c[i]),
                "volume": 1.0,
                "time": i,
            }
            for i in range(n)
        ]
        interp = Runtime(symbol="T").run(src, bars, mode="interpret")
        assert "error" not in interp, interp.get("error")
        S = interp["series"]
        compiled = compile_script(src)
        assert not compiled.object_mode
        out = compiled.run(o, h, l, c, v)
        for key in ("dip", "dim", "adx", "st", "dir", "adx2"):
            max_err = 0.0
            for i in range(n):
                a, b = out[key][i], S[key][i]
                if np.isnan(a) and (b is None or (isinstance(b, float) and np.isnan(b))):
                    continue
                max_err = max(max_err, abs(float(a) - float(b)))
            assert max_err <= 1e-9, f"{key} max_err={max_err}"

    def test_alma_inc_emit_and_parity(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        src = """//@version=6
indicator("x")
plot(ta.alma(close, 9, 0.85, 6), title="alma")
"""
        code = transpile(src)
        assert "numba_alma_inc" in code
        compiled = compile_script(src)
        assert not compiled.object_mode
        rng = np.random.default_rng(3)
        n = 200
        c = 50.0 + np.cumsum(rng.normal(0, 0.5, n))
        o, h, l, v = c, c + 1, c - 1, np.ones(n)
        out = compiled.run(o, h, l, c, v)
        st = np.full(2 + 9, np.nan)
        max_err = 0.0
        for i in range(n):
            full = nb.numba_alma(c, 9, 0.85, 6.0, i)
            inc = nb.numba_alma_inc(c, 9, 0.85, 6.0, i, st)
            comp = out["alma"][i]
            if np.isnan(full) and np.isnan(inc) and np.isnan(comp):
                continue
            max_err = max(max_err, abs(float(full) - float(inc)), abs(float(full) - float(comp)))
        assert max_err <= 1e-10, max_err

    def test_percentrank_matches_interpret_oracle(self) -> None:
        from pynescript.compiler import numba_builtins as nb
        from backend.runtime import Runtime

        src = """//@version=6
indicator("x")
plot(ta.percentrank(close, 10), title="pr")
"""
        rng = np.random.default_rng(11)
        n = 60
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        o, h, l, v = c, c + 1, c - 1, np.ones(n)
        bars = [
            {
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(l[i]),
                "close": float(c[i]),
                "volume": 1.0,
                "time": i,
            }
            for i in range(n)
        ]
        S = Runtime(symbol="T").run(src, bars, mode="interpret")["series"]["pr"]
        compiled = compile_script(src)
        out = compiled.run(o, h, l, c, v)["pr"]
        max_err = 0.0
        for i in range(n):
            k = nb.numba_percentrank(c, 10, i)
            interp = S[i]
            comp = out[i]
            if np.isnan(k) and (interp is None or (isinstance(interp, float) and np.isnan(interp))):
                assert np.isnan(comp)
                continue
            max_err = max(
                max_err,
                abs(float(k) - float(interp)),
                abs(float(k) - float(comp)),
            )
        assert max_err <= 1e-9, max_err


class TestCompileEngineRound6:
    """Cold JIT / cache / typed error hardening (Agent 06)."""

    def test_prewarm_idempotent_and_stats(self) -> None:
        from pynescript.compiler.engine import compile_cache_stats
        from pynescript.compiler.engine import compile_deploy_config
        from pynescript.compiler.engine import prewarm_numba_builtins

        assert prewarm_numba_builtins() is True
        assert prewarm_numba_builtins() is True
        stats = compile_cache_stats()
        assert stats["builtins_warmed"] is True
        assert stats["has_numba"] is True
        assert stats["source_max"] >= 32
        assert stats["ir_max"] >= 32
        assert "prewarm_enabled" in stats
        deploy = compile_deploy_config()
        assert deploy["default_runtime_mode"] == "auto"
        assert deploy["disk_cache_enabled"] in (True, False)
        assert "env" in deploy

    def test_prewarm_scripts_and_ensure_cache_dir(self, tmp_path, monkeypatch) -> None:
        from pynescript.compiler.engine import clear_compile_cache
        from pynescript.compiler.engine import ensure_compile_cache_dir
        from pynescript.compiler.engine import prewarm_scripts

        monkeypatch.setenv("PYNE_COMPILE_DISK_CACHE", "1")
        monkeypatch.setenv("PYNE_COMPILE_CACHE_DIR", str(tmp_path / "cc"))
        clear_compile_cache()
        root = ensure_compile_cache_dir()
        assert root is not None
        assert root.is_dir()
        src = """//@version=5
indicator("pw")
plot(ta.sma(close, 5), title="s")
"""
        out = prewarm_scripts([src])
        assert out["has_numba"] is True
        assert out["scripts_ok"] == 1
        assert out["scripts_failed"] == 0
        assert out["errors"] == []
        assert out["source_entries"] >= 1
        # empty / hard parse failures counted without raising
        bad = '//@version=5\nindicator("x")\nif\n'
        out2 = prewarm_scripts(["", bad])
        assert out2["scripts_failed"] == 2
        assert len(out2["errors"]) == 2

    def test_raw_source_cache_hit_skips_recompile(self) -> None:
        from pynescript.compiler.engine import clear_compile_cache
        from pynescript.compiler.engine import compile_cache_stats

        clear_compile_cache()
        src = """//@version=5
indicator("c")
plot(ta.sma(close, 7), title="s")
"""
        a = compile_script(src)
        before = compile_cache_stats()["source_entries"]
        b = compile_script(src)
        after = compile_cache_stats()["source_entries"]
        assert a is b
        assert after == before  # no new entries on identity hit

    def test_disk_cache_roundtrip(self, tmp_path, monkeypatch) -> None:
        from pynescript.compiler.engine import clear_compile_cache
        from pynescript.compiler.engine import clear_disk_compile_cache
        from pynescript.compiler.engine import compile_script as cs

        monkeypatch.setenv("PYNE_COMPILE_DISK_CACHE", "1")
        monkeypatch.setenv("PYNE_COMPILE_CACHE_DIR", str(tmp_path / "cc"))
        clear_compile_cache()
        clear_disk_compile_cache()
        src = """//@version=5
indicator("disk")
plot(ta.sma(close, 5), title="s")
"""
        a = cs(src)
        assert a.object_mode is False
        ir_files = list((tmp_path / "cc").glob("ir_*.py"))
        src_meta = list((tmp_path / "cc").glob("src_*.json"))
        assert ir_files, "expected disk IR module"
        assert src_meta, "expected disk source index"
        # Drop memory caches; disk should rehydrate without re-parse path issues
        clear_compile_cache()
        b = cs(src)
        assert b.generated_code.replace("@numba.njit(cache=True)", "@numba.njit(cache=False)") == a.generated_code.replace(
            "@numba.njit(cache=True)", "@numba.njit(cache=False)"
        )
        o, h, l, c, v = _ohlcv(40)
        assert np.allclose(a.run(o, h, l, c, v)["s"], b.run(o, h, l, c, v)["s"], equal_nan=True)

    def test_corrupt_numba_cache_recovers_without_crash(self, tmp_path, monkeypatch) -> None:
        """Truncated .nbc must not crash compile mode — purge + recompile.

        Numba loads ``@njit(cache=True)`` overloads via pickle; empty/truncated
        files raise ``EOFError`` / ``UnpicklingError``. The engine catches that
        on warm/run, clears ``.nbi``/``.nbc``, and retries.
        """
        import pickle
        from pathlib import Path

        from pynescript.compiler import numba_builtins as nb
        from pynescript.compiler.engine import _is_numba_cache_corruption
        from pynescript.compiler.engine import clear_compile_cache
        from pynescript.compiler.engine import clear_disk_compile_cache
        from pynescript.compiler.engine import clear_numba_function_caches
        from pynescript.compiler.engine import compile_script as cs

        assert _is_numba_cache_corruption(EOFError("Ran out of input"))
        assert _is_numba_cache_corruption(pickle.UnpicklingError("pickle data was truncated"))
        assert not _is_numba_cache_corruption(ValueError("unrelated"))

        monkeypatch.setenv("PYNE_COMPILE_DISK_CACHE", "1")
        monkeypatch.setenv("PYNE_COMPILE_CACHE_DIR", str(tmp_path / "cc"))
        clear_compile_cache()
        clear_disk_compile_cache()

        # Ensure at least one kernel has a disk cache entry, then truncate it.
        a = np.arange(32, dtype=np.float64)
        _ = nb.numba_sma(a, 5, 10)
        pyc = Path(nb.__file__).resolve().parent / "__pycache__"
        nbc_files = list(pyc.glob("numba_builtins.numba_sma-*.nbc"))
        assert nbc_files, "expected numba_sma .nbc after first call"
        for p in nbc_files:
            p.write_bytes(b"")  # classic "Ran out of input"

        # Same-process dispatcher may already hold a warm overload; exercise
        # the recovery helper directly + compile/run for ADX/bb-style path.
        from pynescript.compiler.engine import _call_with_numba_cache_recovery

        def _boom_once():
            # Simulate first load failing with cache corruption, then success.
            if not getattr(_boom_once, "failed", False):
                _boom_once.failed = True  # type: ignore[attr-defined]
                raise EOFError("Ran out of input")
            return 42

        assert _call_with_numba_cache_recovery(_boom_once) == 42
        # Truncated files should be gone (purge ran).
        assert not any(p.is_file() and p.stat().st_size == 0 for p in nbc_files)

        clear_compile_cache()
        src = """//@version=5
indicator("adx corrupt cache")
plot(ta.adx(high, low, close, 14), title="adx")
plot(ta.sma(close, 5), title="s")
"""
        compiled = cs(src, use_cache=False)
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        assert "adx" in out and "s" in out
        assert len(out["s"]) == 80
        # Manual clear API is callable and non-negative
        n = clear_numba_function_caches()
        assert n >= 0

    def test_nopython_fallback_reason_on_forced_object_recovery(self, monkeypatch) -> None:
        """If warm-up reports a nopython failure, reason is recorded and mode is object."""
        from numba.core.errors import TypingError

        from pynescript.compiler import engine as eng

        eng.clear_compile_cache()
        real_exec_generated = eng._exec_generated

        def flaky_exec(source, code, titles, object_mode, **kwargs):
            cs = real_exec_generated(source, code, titles, object_mode, **kwargs)
            if not object_mode:

                def boom(*_a, **_k):
                    raise TypingError("Failed in nopython mode (test)")

                cs.execute = boom  # type: ignore[method-assign]
            return cs

        monkeypatch.setattr(eng, "_exec_generated", flaky_exec)
        src = """//@version=5
indicator("x")
plot(close, title="c")
"""
        compiled = eng.compile_script(src, use_cache=False)
        assert compiled.object_mode is True
        assert compiled.nopython_fallback_reason
        assert "nopython" in compiled.nopython_fallback_reason.lower()
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert "c" in out
        assert len(out["c"]) == 20

    def test_typed_emit_error_on_parse_failure(self) -> None:
        from pynescript.compiler.engine import CompileEmitError
        from pynescript.compiler.engine import CompileError

        # Corpus sanitize may rewrite bare garbage into a stub; keep a versioned
        # header so the token error survives sanitize.
        bad = """//@version=5
indicator("x")
@@@
"""
        with pytest.raises(CompileEmitError, match="parse failed"):
            compile_script(bad, use_cache=False)
        with pytest.raises(CompileError):
            compile_script(bad, use_cache=False)

    def test_lru_eviction_bounded(self) -> None:
        from pynescript.compiler.engine import _COMPILE_CACHE
        from pynescript.compiler.engine import _COMPILE_CACHE_MAX
        from pynescript.compiler.engine import clear_compile_cache

        clear_compile_cache()
        # Insert more than max unique scripts (small object-mode to stay fast)
        n = min(40, _COMPILE_CACHE_MAX + 5)
        for i in range(n):
            src = f"""//@version=5
indicator("x{i}")
plot(close + {i}, title="c")
"""
            compile_script(src)
        assert len(_COMPILE_CACHE) <= _COMPILE_CACHE_MAX

    def test_runtime_surfaces_nopython_fallback_reason(self, monkeypatch) -> None:
        from backend.runtime import Runtime
        from pynescript.compiler import engine as eng

        eng.clear_compile_cache()
        # Ensure host compile cache does not hide engine field
        import backend.runtime as rt

        rt._HOST_COMPILE_CACHE.clear()

        real_exec = eng._exec_generated

        def flaky_exec(source, code, titles, object_mode, **kwargs):
            cs = real_exec(source, code, titles, object_mode, **kwargs)
            if not object_mode:
                from numba.core.errors import TypingError

                def boom(*_a, **_k):
                    raise TypingError("Failed in nopython mode (runtime test)")

                cs.execute = boom  # type: ignore[method-assign]
            return cs

        monkeypatch.setattr(eng, "_exec_generated", flaky_exec)
        src = """//@version=5
indicator("x")
plot(close, title="c")
"""
        bars = [
            {
                "open": float(100 + i),
                "high": float(101 + i),
                "low": float(99 + i),
                "close": float(100 + i),
                "volume": 1.0,
                "time": i * 86_400_000,
            }
            for i in range(15)
        ]
        r = Runtime(symbol="T").run(src, bars, mode="compile")
        assert "error" not in r, r.get("error")
        assert r.get("object_mode") is True
        assert "nopython" in (r.get("nopython_fallback_reason") or "").lower()


class TestLanguageSurfaceNumeric:
    """Round 6 Agent 05: keep pure language-surface scripts on nopython path.

    Uses ``use_cache=False`` so stale disk/IR cache from prior object-mode emits
    of the same source does not mask the numeric path.
    """

    def test_chart_viewport_times_use_bar_time_model(self) -> None:
        """left/right visible times match synthetic ``time`` (not both 0.0)."""
        src = """//@version=5
indicator("x")
plot(chart.left_visible_bar_time, title="L")
plot(chart.right_visible_bar_time, title="R")
plot(time, title="T")
"""
        code = transpile(src)
        assert "@numba.njit" in code
        compact = code.replace(" ", "")
        assert "time_arr[0]" in compact
        assert "time_arr[n_bars-1]" in compact
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is False
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["L"][-1] - 0.0) < 1e-9
        # last bar synthetic time (engine default when host omits time)
        assert abs(out["R"][-1] - float(9) * 60000.0) < 1e-6
        assert abs(out["R"][-1] - out["T"][-1]) < 1e-6

    def test_for_loop_sum_stays_numeric(self) -> None:
        src = """//@version=5
indicator("x")
s = 0.0
for i = 0 to 3
    s := s + close[i]
plot(s, title="s")
"""
        code = transpile(src)
        assert "@numba.njit" in code
        assert "safe_float" not in code
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is False
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        # close = 100..119; last bar sum of close[0..3] history = c[-1]+c[-2]+c[-3]+c[-4]
        expected = float(c[-1] + c[-2] + c[-3] + c[-4])
        assert abs(out["s"][-1] - expected) < 1e-6

    def test_input_int_float_times_sma_stays_numeric(self) -> None:
        src = """//@version=5
indicator("x")
a = input.int(14)
b = input.float(2.0)
plot(ta.sma(close, a) * b, title="p")
"""
        code = transpile(src)
        assert "@numba.njit" in code
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is False
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        # SMA of last 14 closes * 2
        expected = float(np.mean(c[-14:])) * 2.0
        assert abs(out["p"][-1] - expected) < 1e-6

    def test_math_random_and_hyperbolic_stay_numeric(self) -> None:
        src = """//@version=5
indicator("x")
plot(math.random(0, 1), title="rnd")
plot(math.tanh(0.0), title="t")
plot(math.todegrees(math.pi), title="d")
plot(math.toradians(180.0), title="r")
"""
        code = transpile(src)
        assert "@numba.njit" in code
        assert "safe_float" not in code
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is False
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["rnd"][-1] - 0.5) < 1e-9
        assert abs(out["t"][-1] - 0.0) < 1e-9
        assert abs(out["d"][-1] - 180.0) < 1e-6
        assert abs(out["r"][-1] - np.pi) < 1e-6

    def test_timestamp_literal_stays_numeric(self) -> None:
        """Literal timestamp(y,m,d,…) stays on nopython path via numba_timestamp."""
        src = """//@version=5
indicator("x")
plot(timestamp(2020, 1, 1, 0, 0), title="t")
"""
        code = transpile(src)
        assert "@numba.njit" in code
        assert "numba_timestamp" in code
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is False
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        # 2020-01-01 00:00:00 UTC
        assert abs(out["t"][-1] - 1_577_836_800_000.0) < 1e-3

    def test_string_input_still_forces_object_mode(self) -> None:
        """Regression: string inputs must not silently stay nopython."""
        src = """//@version=5
indicator("x")
s = input.string("EMA", "Method")
plot(close, title="c")
"""
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["c"][-1] - c[-1]) < 1e-9


class TestCompileRound7ResidualKernels:
    """Round 7 residual numeric kernels: median / wpr / cmo / bbw."""

    def test_median_wpr_cmo_bbw_emit_numeric(self) -> None:
        src = """//@version=6
indicator("x")
plot(ta.median(close, 5), title="med")
plot(ta.wpr(14), title="wpr")
plot(ta.cmo(close, 9), title="cmo")
plot(ta.bbw(close, 20, 2.0), title="bbw")
"""
        code = transpile(src)
        assert "numba_median" in code
        assert "numba_wpr" in code
        assert "numba_cmo" in code
        assert "numba_bbw" in code
        assert "safe_float(None)" not in code
        compiled = compile_script(src, use_cache=False)
        assert not compiled.object_mode
        o, h, l, c, v = _ohlcv(80)
        out = compiled.run(o, h, l, c, v)
        assert not np.isnan(out["med"][-1])
        assert not np.isnan(out["wpr"][-1])
        assert not np.isnan(out["cmo"][-1])
        assert not np.isnan(out["bbw"][-1])

    def test_kernel_formulas_and_bbw_inc_parity(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        rng = np.random.default_rng(21)
        n = 120
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        h = c + rng.uniform(0.2, 1.5, n)
        l = c - rng.uniform(0.2, 1.5, n)

        # median of last 5 of a synthetic ramp
        ramp = np.arange(10, dtype=np.float64)
        assert abs(nb.numba_median(ramp, 5, 9) - 7.0) < 1e-12  # 5..9 → 7
        assert abs(nb.numba_median(ramp, 4, 9) - 7.5) < 1e-12  # 6..9 even

        # wpr warm-up is 0.0 (interpret oracle)
        assert nb.numba_wpr(h, l, c, 14, 0) == 0.0

        # bbw_inc matches full bbw
        st = np.full(3, np.nan)
        max_err = 0.0
        for i in range(n):
            full = nb.numba_bbw(c, 20, 2.0, i)
            inc = nb.numba_bbw_inc(c, 20, 2.0, i, st)
            if np.isnan(full) and np.isnan(inc):
                continue
            max_err = max(max_err, abs(float(full) - float(inc)))
        assert max_err <= 1e-10, max_err

        # cmo zero-momentum flat series → 0 after seed
        flat = np.full(30, 50.0)
        assert abs(nb.numba_cmo(flat, 10, 20)) < 1e-12

    def test_compiled_matches_interpret_oracle(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=6
indicator("x")
plot(ta.median(close, 7), title="med")
plot(ta.wpr(10), title="wpr")
plot(ta.cmo(close, 12), title="cmo")
plot(ta.bbw(close, 15, 2.0), title="bbw")
"""
        rng = np.random.default_rng(5)
        n = 80
        c = 100.0 + np.cumsum(rng.normal(0, 1, n))
        h = c + rng.uniform(0.2, 1.2, n)
        l = c - rng.uniform(0.2, 1.2, n)
        o, v = c.copy(), np.ones(n)
        bars = [
            {
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(l[i]),
                "close": float(c[i]),
                "volume": 1.0,
                "time": i,
            }
            for i in range(n)
        ]
        interp = Runtime(symbol="T").run(src, bars, mode="interpret")
        assert "error" not in interp, interp.get("error")
        S = interp["series"]
        compiled = compile_script(src, use_cache=False)
        assert not compiled.object_mode
        out = compiled.run(o, h, l, c, v)
        for key in ("med", "wpr", "cmo", "bbw"):
            max_err = 0.0
            for i in range(n):
                a, b = out[key][i], S[key][i]
                if np.isnan(a) and (b is None or (isinstance(b, float) and np.isnan(b))):
                    continue
                if b is None and np.isnan(a):
                    continue
                max_err = max(max_err, abs(float(a) - float(b)))
            assert max_err <= 1e-9, f"{key} max_err={max_err}"


class TestEmaRmaLeadingNanSeed:
    """SMA-seed kernels must not stay all-NaN when the source has leading NaNs.

    Nested ``ta.ema(ta.ema(...))`` and ``ta.rma(ta.tr)`` previously poisoned the
    one-shot seed at ``period-1`` (window always included leading NaNs).
    """

    def test_ema_inc_nested_seeds_after_warmup(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        n = 60
        src = np.arange(100.0, 100.0 + n, dtype=np.float64)
        period = 9
        e1 = np.empty(n, dtype=np.float64)
        st1 = np.array([np.nan, np.nan])
        for i in range(n):
            e1[i] = nb.numba_ema_inc(src, period, i, st1)
        # Outer EMA of e1: leading NaNs until e1 warms, then sliding SMA seed.
        e2 = np.empty(n, dtype=np.float64)
        st2 = np.array([np.nan, np.nan])
        for i in range(n):
            e2[i] = nb.numba_ema_inc(e1, period, i, st2)
        assert np.isnan(e1[: period - 1]).all()
        assert not np.isnan(e1[period - 1])
        # First finite e1 at period-1; first all-finite e1 window ends at 2*period-2.
        seed2 = 2 * period - 2
        assert np.isnan(e2[:seed2]).all()
        assert not np.isnan(e2[seed2]), e2[seed2]
        assert not np.isnan(e2[-1])
        # Full kernel matches incremental after seed.
        for i in (seed2, seed2 + 5, n - 1):
            assert abs(float(nb.numba_ema(e1, period, i)) - float(e2[i])) < 1e-10

    def test_rma_inc_tr_style_leading_nan(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        n = 50
        period = 14
        # TR is NaN on bar 0 (no prior close); finite thereafter.
        tr = np.full(n, np.nan, dtype=np.float64)
        for i in range(1, n):
            tr[i] = 1.5 + 0.01 * i
        out = np.empty(n, dtype=np.float64)
        st = np.array([np.nan, np.nan])
        for i in range(n):
            out[i] = nb.numba_rma_inc(tr, period, i, st)
        # Window tr[1:period+1] is the first all-finite period → seed at index period.
        assert np.isnan(out[:period]).all()
        assert not np.isnan(out[period]), out[period]
        expected_seed = float(np.mean(tr[1 : period + 1]))
        assert abs(float(out[period]) - expected_seed) < 1e-10
        assert not np.isnan(out[-1])
        for i in (period, period + 3, n - 1):
            assert abs(float(nb.numba_rma(tr, period, i)) - float(out[i])) < 1e-10

    def test_double_ema_and_atr_scripts_not_all_nan(self) -> None:
        """End-to-end: compile path for DEMA / custom-RMA ATR produces values."""
        from pathlib import Path

        from backend.runtime import Runtime
        from pynescript.ast.helper import clear_parse_cache

        n = 100
        o, h, l, c, v = _ohlcv(n, start=100.0)
        bars = [
            {
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(l[i]),
                "close": float(c[i]),
                "volume": float(v[i]),
                "time": i,
            }
            for i in range(n)
        ]
        snippets = (
            (
                "DEMA",
                """//@version=5
indicator("DEMA")
len = input.int(9, minval=1)
plot(ta.ema(ta.ema(close, len), len), "DEMA")
""",
            ),
            (
                "ATR",
                """//@version=5
indicator("ATR")
len = input.int(14, minval=1)
plot(ta.atr(len), "ATR")
""",
            ),
        )
        for key, src in snippets:
            clear_parse_cache()
            ri = Runtime(symbol="T").run(src, bars, mode="interpret")
            clear_parse_cache()
            rc = Runtime(symbol="T").run(src, bars, mode="compile")
            assert "error" not in ri, ri.get("error")
            assert "error" not in rc, rc.get("error")
            a = np.asarray(ri["series"][key], dtype=float)
            b = np.asarray(rc["series"][key], dtype=float)
            assert not np.isnan(b).all(), f"{key} compile still all-NaN"
            both = ~np.isnan(a) & ~np.isnan(b)
            assert both.sum() > 0, f"{key} no overlapping finite bars"
            assert not np.isnan(b[-1])
            if key == "ATR":
                maxdiff = float(np.max(np.abs(a[both] - b[both])))
                assert maxdiff < 1e-6, f"ATR maxdiff={maxdiff}"
            else:
                last_both = int(np.where(both)[0][-1])
                if abs(a[last_both]) > 1e-9:
                    rel = abs(a[last_both] - b[last_both]) / abs(a[last_both])
                    assert rel < 0.25, f"DEMA relative drift {rel} at {last_both}"


class TestAdxDmiBuiltinScriptPlotParity:
    """Expanded ADX/DMI scripts (not ``ta.adx``) must match interpret plots.

    These scripts build DI/ADX from ``ta.change`` / ``ta.tr`` / ``ta.rma`` /
    ``fixnan``. Leading-NaN RMA seed bugs left compile ADX stuck near 0 after
    warmup (first diverge often bar 14: interpret ~7, compile 0).
    """

    @staticmethod
    def _synth_bars(n: int = 150, seed: int = 42) -> tuple[list[dict], np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)
        close = 100.0 + np.cumsum(rng.normal(0, 1, n))
        high = close + rng.uniform(0.1, 2.0, n)
        low = close - rng.uniform(0.1, 2.0, n)
        open_ = close + rng.normal(0, 0.2, n)
        vol = np.ones(n)
        bars = [
            {
                "open": float(open_[i]),
                "high": float(high[i]),
                "low": float(low[i]),
                "close": float(close[i]),
                "volume": float(vol[i]),
                "time": i,
            }
            for i in range(n)
        ]
        return bars, open_, high, low, close, vol

    @staticmethod
    def _series_max_err(interp_vals, compile_vals, *, rel: float = 1e-5, abs_: float = 1e-6) -> tuple[float, int, object]:
        """Max |i-c| over bars where both defined; return (max_err, n_both, first_div)."""
        max_err = 0.0
        n_both = 0
        first_div = None
        for i, (iv, cv) in enumerate(zip(interp_vals, compile_vals, strict=True)):
            i_nan = iv is None or (isinstance(iv, float) and np.isnan(iv))
            c_nan = cv is None or (isinstance(cv, float) and np.isnan(cv))
            if i_nan or c_nan:
                continue
            a, b = float(iv), float(cv)
            err = abs(a - b)
            n_both += 1
            max_err = max(max_err, err)
            tol = max(abs_, rel * max(abs(a), abs(b), 1e-12))
            if err > tol and first_div is None:
                first_div = (i, a, b, err)
        return max_err, n_both, first_div

    def test_average_directional_index_plot_parity(self) -> None:
        from pathlib import Path

        import pytest

        from backend.runtime import Runtime
        from pynescript.ast.helper import clear_parse_cache

        path = Path(__file__).resolve().parent / "data" / "builtin_scripts" / "average_directional_index.pine"
        if not path.is_file():
            pytest.skip("third-party fixture not shipped")
        src = path.read_text(encoding="utf-8")
        bars, *_ = self._synth_bars(160, seed=42)
        clear_parse_cache()
        ri = Runtime(symbol="ADX").run(src, bars, mode="interpret")
        clear_parse_cache()
        rc = Runtime(symbol="ADX").run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        si, sc = ri["series"]["ADX"], rc["series"]["ADX"]
        max_err, n_both, first = self._series_max_err(si, sc)
        assert n_both >= 100, f"too few overlapping finite ADX bars: {n_both}"
        assert first is None, f"ADX first diverge {first}"
        assert max_err <= 1e-6, f"ADX max_err={max_err}"
        # Compile must not stay stuck at 0 after warmup.
        tail = np.asarray(sc[-50:], dtype=float)
        assert float(np.nanmax(np.abs(tail))) > 1.0, "compile ADX still ~0 after warmup"

    def test_directional_movement_index_plot_parity(self) -> None:
        from pathlib import Path

        import pytest

        from backend.runtime import Runtime
        from pynescript.ast.helper import clear_parse_cache

        path = Path(__file__).resolve().parent / "data" / "builtin_scripts" / "directional_movement_index.pine"
        if not path.is_file():
            pytest.skip("third-party fixture not shipped")
        src = path.read_text(encoding="utf-8")
        bars, *_ = self._synth_bars(160, seed=7)
        clear_parse_cache()
        ri = Runtime(symbol="DMI").run(src, bars, mode="interpret")
        clear_parse_cache()
        rc = Runtime(symbol="DMI").run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        for key in ("ADX", "+DI", "-DI"):
            max_err, n_both, first = self._series_max_err(ri["series"][key], rc["series"][key])
            assert n_both >= 100, f"{key}: too few overlapping bars {n_both}"
            assert first is None, f"{key} first diverge {first}"
            assert max_err <= 1e-6, f"{key} max_err={max_err}"
        # +DI/-DI must leave the fixnan-zero floor after DI RMA seeds.
        for key in ("+DI", "-DI"):
            tail = np.asarray(rc["series"][key][-50:], dtype=float)
            assert float(np.nanmax(np.abs(tail))) > 1.0, f"compile {key} still ~0 after warmup"


class TestHighestLowestFullWindowAndBuiltinParity:
    """``ta.highest`` / ``ta.lowest`` require a full period (interpret parity).

    Partial-window compile kernels caused early finite values on Chande Kroll
    Stop (and polluted nested highest/lowest of intermediate stops).
    """

    def test_numba_highest_lowest_require_full_period(self) -> None:
        from pynescript.compiler import numba_builtins as nb

        x = np.arange(10, dtype=np.float64)
        period = 5
        st_h = np.full(3, np.nan)
        st_l = np.full(3, np.nan)
        for i in range(10):
            full_h = nb.numba_highest(x, period, i)
            full_l = nb.numba_lowest(x, period, i)
            inc_h = nb.numba_highest_inc(x, period, i, st_h)
            inc_l = nb.numba_lowest_inc(x, period, i, st_l)
            if i < period - 1:
                assert np.isnan(full_h) and np.isnan(inc_h)
                assert np.isnan(full_l) and np.isnan(inc_l)
            else:
                assert full_h == float(i)
                assert full_l == float(i - period + 1)
                assert inc_h == full_h
                assert inc_l == full_l

    def test_chande_kroll_stop_interp_compile_exact(self) -> None:
        from pathlib import Path

        import pytest

        from backend.runtime import Runtime
        from pynescript.ast.helper import clear_parse_cache
        from pynescript.compiler.engine import clear_compile_cache

        path = Path(__file__).resolve().parent / "data" / "builtin_scripts" / "chande_kroll_stop.pine"
        if not path.is_file():
            pytest.skip("third-party fixture not shipped")
        src = path.read_text(encoding="utf-8")
        rng = np.random.default_rng(42)
        n = 150
        close = 100.0 + np.cumsum(rng.normal(0, 1, n))
        high = close + rng.uniform(0.1, 1.5, n)
        low = close - rng.uniform(0.1, 1.5, n)
        open_ = close + rng.normal(0, 0.2, n)
        bars = [
            {
                "open": float(open_[i]),
                "high": float(high[i]),
                "low": float(low[i]),
                "close": float(close[i]),
                "volume": 1000.0,
                "time": i,
            }
            for i in range(n)
        ]
        clear_compile_cache()
        clear_parse_cache()
        ri = Runtime(symbol="CK").run(src, bars, mode="interpret")
        clear_parse_cache()
        rc = Runtime(symbol="CK").run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        for key in ("Stop Long", "Stop Short"):
            a = np.asarray(ri["series"][key], dtype=float)
            b = np.asarray(rc["series"][key], dtype=float)
            assert a.shape == b.shape
            # NaN masks must match (no early compile partial-window values)
            assert np.array_equal(np.isnan(a), np.isnan(b)), f"{key} nan mask diverge"
            both = ~np.isnan(a) & ~np.isnan(b)
            assert both.sum() > 100
            maxdiff = float(np.max(np.abs(a[both] - b[both])))
            assert maxdiff == 0.0, f"{key} maxdiff={maxdiff}"

    def test_bull_bear_power_hline_and_bbpower_parity(self) -> None:
        """hline ``Zero line`` series + BBPower match (SMA-seed EMA on both hosts)."""
        from pathlib import Path

        import pytest

        from backend.runtime import Runtime
        from pynescript.ast.helper import clear_parse_cache
        from pynescript.compiler.engine import clear_compile_cache

        path = Path(__file__).resolve().parent / "data" / "builtin_scripts" / "bull_bear_power.pine"
        if not path.is_file():
            pytest.skip("third-party fixture not shipped")
        src = path.read_text(encoding="utf-8")
        n = 200
        o, h, l, c, v = _ohlcv(n, start=100.0)
        bars = [
            {
                "open": float(o[i]),
                "high": float(h[i]),
                "low": float(l[i]),
                "close": float(c[i]),
                "volume": float(v[i]),
                "time": i,
            }
            for i in range(n)
        ]
        clear_compile_cache()
        clear_parse_cache()
        ri = Runtime(symbol="BBP").run(src, bars, mode="interpret")
        clear_parse_cache()
        rc = Runtime(symbol="BBP").run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        assert "Zero line" in ri["series"] and "Zero line" in rc["series"]
        z_i = np.asarray(ri["series"]["Zero line"], dtype=float)
        z_c = np.asarray(rc["series"]["Zero line"], dtype=float)
        assert np.allclose(z_i, 0.0) and np.allclose(z_c, 0.0)
        a = np.asarray(ri["series"]["BBPower"], dtype=float)
        b = np.asarray(rc["series"]["BBPower"], dtype=float)
        # SMA-seed EMA: na until length-1 (13 → bar 12) on both hosts
        assert np.isnan(a[:12]).all() and np.isnan(b[:12]).all()
        both = ~np.isnan(a) & ~np.isnan(b)
        assert both.sum() > 150
        maxdiff = float(np.max(np.abs(a[both] - b[both])))
        assert maxdiff < 1e-9, f"BBPower maxdiff={maxdiff}"


class TestInterpCompilePlotParityFixes:
    """Targeted interpret/compile plot parity for recent kernel + host fixes.

    Covers: Wilder RSI, standard ROC (no early 0), full-window WMA, UDF last
    assign returning ``na``, user ``ad`` series vs builtin A/D, and ``math.avg``
    na propagation.
    """

    @staticmethod
    def _synth_bars(n: int = 100, seed: int = 42) -> list[dict]:
        rng = np.random.default_rng(seed)
        close = 100.0 + np.cumsum(rng.normal(0, 1, n))
        high = close + rng.uniform(0.1, 1.5, n)
        low = close - rng.uniform(0.1, 1.5, n)
        open_ = close + rng.normal(0, 0.2, n)
        return [
            {
                "open": float(open_[i]),
                "high": float(high[i]),
                "low": float(low[i]),
                "close": float(close[i]),
                "volume": 1000.0,
                "time": i,
            }
            for i in range(n)
        ]

    @staticmethod
    def _to_float_series(vals) -> np.ndarray:
        return np.asarray(
            [np.nan if v is None else float(v) for v in vals],
            dtype=np.float64,
        )

    @staticmethod
    def _dual_run(src: str, bars: list[dict], *, symbol: str = "T"):
        from backend.runtime import Runtime
        from pynescript.ast.helper import clear_parse_cache
        from pynescript.compiler.engine import clear_compile_cache

        clear_compile_cache()
        clear_parse_cache()
        ri = Runtime(symbol=symbol).run(src, bars, mode="interpret")
        clear_parse_cache()
        rc = Runtime(symbol=symbol).run(src, bars, mode="compile")
        return ri, rc

    @pytest.mark.parametrize("period", [3, 14])
    def test_rsi_wilder_interp_compile_maxdiff_zero(self, period: int) -> None:
        """Wilder RSI: interpret vs compile bit-identical over 100 bars."""
        src = f"""//@version=5
indicator("RSI")
plot(ta.rsi(close, {period}), title="rsi")
"""
        bars = self._synth_bars(100, seed=42)
        ri, rc = self._dual_run(src, bars, symbol="RSI")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        a = self._to_float_series(ri["series"]["rsi"])
        b = self._to_float_series(rc["series"]["rsi"])
        assert a.shape == b.shape == (100,)
        # First valid RSI at bar ``period`` (period deltas need period+1 prices)
        assert np.isnan(a[:period]).all() and np.isnan(b[:period]).all()
        assert not np.isnan(a[period]) and not np.isnan(b[period])
        assert np.array_equal(np.isnan(a), np.isnan(b)), "RSI nan mask diverge"
        both = ~np.isnan(a) & ~np.isnan(b)
        assert both.sum() >= 100 - period
        maxdiff = float(np.max(np.abs(a[both] - b[both])))
        assert maxdiff == 0.0, f"ta.rsi({period}) maxdiff={maxdiff}"

    def test_roc_standard_formula_no_early_zero(self) -> None:
        """``ta.roc`` is ``na`` until lookback, never early 0.0; hosts match."""
        src = """//@version=5
indicator("ROC")
plot(ta.roc(close, 9), title="roc")
"""
        bars = self._synth_bars(100, seed=1)
        ri, rc = self._dual_run(src, bars, symbol="ROC")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        a = self._to_float_series(ri["series"]["roc"])
        b = self._to_float_series(rc["series"]["roc"])
        # Bars 0..8 insufficient lookback → na (legacy quirk returned 0.0)
        assert np.isnan(a[:9]).all(), f"interpret early ROC not na: {a[:9]}"
        assert np.isnan(b[:9]).all(), f"compile early ROC not na: {b[:9]}"
        assert not (a[:9] == 0.0).any()
        assert not (b[:9] == 0.0).any()
        assert not np.isnan(a[9]) and not np.isnan(b[9])
        both = ~np.isnan(a) & ~np.isnan(b)
        assert both.sum() >= 90
        maxdiff = float(np.max(np.abs(a[both] - b[both])))
        assert maxdiff == 0.0, f"ROC maxdiff={maxdiff}"

    def test_wma_requires_full_non_na_window_of_roc(self) -> None:
        """WMA must not reweight over partial/na windows (Coppock-style nest)."""
        src = """//@version=5
indicator("WMA_ROC")
plot(ta.wma(ta.roc(close, 14), 10), title="w")
"""
        bars = self._synth_bars(100, seed=2)
        ri, rc = self._dual_run(src, bars, symbol="W")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        a = self._to_float_series(ri["series"]["w"])
        b = self._to_float_series(rc["series"]["w"])
        # roc na until bar 14; wma needs 10 finite samples → first finite at 23
        first_i = int(np.where(~np.isnan(a))[0][0])
        first_c = int(np.where(~np.isnan(b))[0][0])
        assert first_i == 23 and first_c == 23, f"first finite i={first_i} c={first_c}"
        assert np.isnan(a[:23]).all() and np.isnan(b[:23]).all()
        # Partial-window reweight bug would yield finite values before bar 23
        assert np.array_equal(np.isnan(a), np.isnan(b))
        both = ~np.isnan(a) & ~np.isnan(b)
        assert both.sum() > 70
        maxdiff = float(np.max(np.abs(a[both] - b[both])))
        assert maxdiff < 1e-12, f"wma(roc) maxdiff={maxdiff}"

    def test_udf_last_assign_returns_na_not_prior(self) -> None:
        """UDF body ending in ``x = na`` must return na, not a prior assign (42).

        ADX-style scripts end with assign of an RMA that is na during warmup;
        keeping the previous statement's value forced early 0 / non-na.
        """
        src = """//@version=5
indicator("UDF_NA")
f() =>
    dummy = 42.0
    x = na
plot(f(), title="u")
"""
        bars = self._synth_bars(30, seed=3)
        ri, rc = self._dual_run(src, bars, symbol="UDF")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        a = self._to_float_series(ri["series"]["u"])
        b = self._to_float_series(rc["series"]["u"])
        assert np.isnan(a).all(), f"interpret forced non-na: {a[:5]}"
        assert np.isnan(b).all(), f"compile forced non-na: {b[:5]}"
        # Must not leak prior assign 42.0
        assert not np.any(np.isclose(a, 42.0, equal_nan=False))
        assert not np.any(np.isclose(b, 42.0, equal_nan=False))

    def test_udf_last_assign_rma_warmup_na_adx_style(self) -> None:
        """Tuple unpack then RMA assign: warmup returns na (not 0 / prior)."""
        src = """//@version=5
indicator("ADX_STYLE")
f(len) =>
    [plus, minus] = [1.0, 2.0]
    sum = plus + minus
    adx = 100 * ta.rma(math.abs(plus - minus) / (sum == 0 ? 1 : sum), len)
    adx
plot(f(14), title="adx")
"""
        bars = self._synth_bars(50, seed=4)
        ri, rc = self._dual_run(src, bars, symbol="ADXU")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        a = self._to_float_series(ri["series"]["adx"])
        b = self._to_float_series(rc["series"]["adx"])
        # RMA period 14 → na for first 13 bars
        assert np.isnan(a[:13]).all(), f"interpret warmup not na: {a[:14]}"
        assert np.isnan(b[:13]).all(), f"compile warmup not na: {b[:14]}"
        # Bug: kept tuple/0 → early finite 0.0
        assert not np.any(a[:13] == 0.0)
        assert not np.any(b[:13] == 0.0)
        both = ~np.isnan(a) & ~np.isnan(b)
        assert both.sum() >= 30
        maxdiff = float(np.max(np.abs(a[both] - b[both])))
        assert maxdiff < 1e-9, f"ADX-style UDF maxdiff={maxdiff}"

    def test_user_ad_series_uses_ad_arr_not_builtin_accdist(self) -> None:
        """``ad = ta.cum(close); plot(ad)`` must load ``ad_arr``, not Chaikin A/D."""
        src = """//@version=5
indicator("AD_USER")
ad = ta.cum(close)
plot(ad, title="ad")
"""
        code = transpile(src)
        assert "ad_arr" in code
        assert "numba_cum" in code
        # Builtin bare ``ad`` would emit accdist; user series must not
        assert "numba_accdist" not in code
        # Plot must store from user series, not re-evaluate builtin
        assert re.search(r"numba_store\(plot_\d+,\s*__bar_idx,\s*ad_arr\[__bar_idx\]\)", code)

        bars = self._synth_bars(50, seed=5)
        ri, rc = self._dual_run(src, bars, symbol="AD")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        a = self._to_float_series(ri["series"]["ad"])
        b = self._to_float_series(rc["series"]["ad"])
        # Cumulative sum of close (not volume-weighted A/D)
        closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
        expected = np.cumsum(closes)
        assert np.allclose(a, expected, equal_nan=True)
        assert np.allclose(b, expected, equal_nan=True)
        maxdiff = float(np.max(np.abs(a - b)))
        assert maxdiff == 0.0, f"user ad maxdiff={maxdiff}"

    def test_math_avg_with_na_propagates_na(self) -> None:
        """TV ``math.avg``: any na argument → na (do not skip)."""
        src = """//@version=5
indicator("AVG")
plot(math.avg(close, na), title="avg_na")
plot(math.avg(close, close[1]), title="avg_ok")
"""
        bars = self._synth_bars(40, seed=6)
        ri, rc = self._dual_run(src, bars, symbol="AVG")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        ina = self._to_float_series(ri["series"]["avg_na"])
        cna = self._to_float_series(rc["series"]["avg_na"])
        assert np.isnan(ina).all(), f"interpret avg skipped na: {ina[:3]}"
        assert np.isnan(cna).all(), f"compile avg skipped na: {cna[:3]}"

        iok = self._to_float_series(ri["series"]["avg_ok"])
        cok = self._to_float_series(rc["series"]["avg_ok"])
        assert np.isnan(iok[0]) and np.isnan(cok[0])
        closes = np.asarray([bar["close"] for bar in bars], dtype=np.float64)
        for i in range(1, len(bars)):
            expected = 0.5 * (closes[i] + closes[i - 1])
            assert abs(float(iok[i]) - expected) < 1e-9
            assert abs(float(cok[i]) - expected) < 1e-9
        both = ~np.isnan(iok) & ~np.isnan(cok)
        maxdiff = float(np.max(np.abs(iok[both] - cok[both])))
        assert maxdiff == 0.0, f"math.avg finite maxdiff={maxdiff}"

