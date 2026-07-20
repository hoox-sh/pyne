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
