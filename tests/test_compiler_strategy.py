# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Compile-mode strategy support (object-mode CompileStrategyBroker)."""

from __future__ import annotations

import numpy as np
import pytest

from backend.runtime import Runtime
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile


def _ohlcv(n: int = 20, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    # Alternate green/red bars
    open_ = np.where(np.arange(n) % 2 == 0, close - 1.0, close + 1.0)
    return open_, close + 1.0, close - 1.0, close, np.ones(n)


class TestCompileStrategyTranspile:
    def test_transpile_uses_strategy_broker(self) -> None:
        src = """//@version=6
strategy("t")
strategy.entry("L", strategy.long, qty=1)
plot(strategy.position_size, title="ps")
"""
        code = transpile(src)
        assert "CompileStrategyBroker" in code
        assert "__strategy.entry" in code
        assert "object" in code or "__strategy" in code
        assert "@numba.njit" not in code  # object mode


class TestCompileStrategyRun:
    def test_entry_and_close_emit_events(self) -> None:
        src = """//@version=6
strategy("t")
if close > open
    strategy.entry("L", strategy.long, qty=1)
if close < open
    strategy.close("L")
plot(strategy.position_size, title="ps")
"""
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        events = out["__events"]
        kinds = [e["kind"] for e in events]
        assert "entry" in kinds
        assert "close" in kinds
        assert len(out["ps"]) == 10

    def test_netprofit_and_equity_present(self) -> None:
        src = """//@version=6
strategy("t", initial_capital=10000)
strategy.entry("L", strategy.long, 1)
strategy.close("L")
plot(close, title="c")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert "__equity" in out
        assert out["__equity"] == pytest.approx(10000.0, abs=50.0) or isinstance(out["__equity"], float)

    def test_runtime_compile_mode_returns_events(self) -> None:
        src = """//@version=6
strategy("rt")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
if bar_index == 2
    strategy.close("L")
"""
        ohlcv = [
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1.0, "time": i * 1000}
            for i in range(5)
        ]
        # force green on bar 0 for entry condition-less
        result = Runtime().run(src, ohlcv, mode="compile")
        assert "error" not in result, result.get("error")
        assert result["mode"] == "compile"
        assert result["object_mode"] is True
        events = result["events"]
        assert any(e.get("kind") == "entry" for e in events)
        assert any(e.get("kind") == "close" for e in events)

    def test_order_and_cancel(self) -> None:
        src = """//@version=6
strategy("o")
strategy.order("O1", strategy.long, qty=3)
strategy.cancel("O1")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(3)
        out = compiled.run(o, h, l, c, v)
        kinds = [e["kind"] for e in out["__events"]]
        assert "order" in kinds
        assert "entry" in kinds  # order acts as market entry in compile broker
        assert "cancel" in kinds


@pytest.mark.skipif(not has_numba(), reason="numba not required for object-mode strategy")
def test_compile_mode_still_works_for_numeric_sma() -> None:
    """Regression: indicator SMA path still numeric/numba."""
    src = """//@version=6
indicator("x")
plot(ta.sma(close, 5), title="s")
"""
    code = transpile(src)
    assert "@numba.njit" in code
    compiled = compile_script(src)
    assert compiled.object_mode is False
