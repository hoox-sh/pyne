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
        assert "numba_macd" in code
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
