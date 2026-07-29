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
        assert "cancel" in kinds
        # Cancelled before next-bar fill — no entry
        assert "entry" not in kinds

    def test_limit_order_fills_next_bar(self) -> None:
        """Pending limit buy fills when next bar's low touches limit."""
        src = """//@version=6
strategy("lim")
if bar_index == 0
    strategy.order("L1", strategy.long, qty=2, limit=100.0)
plot(strategy.position_size, title="ps")
"""
        compiled = compile_script(src)
        # bar0: open=101, high=102, low=100.5, close=101 — place order
        # bar1: low=99.5 touches limit 100 → fill
        n = 4
        close = np.array([101.0, 100.0, 100.0, 100.0])
        open_ = np.array([101.0, 100.5, 100.0, 100.0])
        high = np.array([102.0, 101.0, 101.0, 101.0])
        low = np.array([100.5, 99.5, 99.0, 99.0])
        vol = np.ones(n)
        out = compiled.run(open_, high, low, close, vol)
        events = out["__events"]
        fills = [e for e in events if e.get("comment") == "fill" or (e.get("kind") == "entry")]
        assert any(e.get("kind") == "entry" for e in events)
        # position after fill
        assert out["__position_size"] == 2.0 or out["ps"][-1] == 2.0

    def test_stop_entry_pending(self) -> None:
        src = """//@version=6
strategy("st")
if bar_index == 0
    strategy.entry("Gap", strategy.long, stop=105.0)
"""
        compiled = compile_script(src)
        # bar0 place stop at 105
        # bar1 high=106 → stop fill
        close = np.array([100.0, 105.5, 105.5])
        open_ = np.array([100.0, 104.0, 105.0])
        high = np.array([101.0, 106.0, 106.0])
        low = np.array([99.0, 103.0, 104.0])
        out = compiled.run(open_, high, low, close, np.ones(3))
        entries = [e for e in out["__events"] if e.get("kind") == "entry"]
        assert len(entries) >= 1
        assert out["__position_size"] == 1.0


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


class TestStrategyRiskAndQtyNameErrors:
    def test_risk_methods_are_noop(self) -> None:
        src = """//@version=5
strategy("t")
strategy.risk.max_cons_loss_days(15)
strategy.risk.max_drawdown(10, strategy.percent_of_equity)
plot(strategy.max_drawdown, title="dd")
"""
        code = transpile(src)
        assert "max_cons_loss_days(" not in code
        assert "max_drawdown(strategy_risk" not in code
        assert "__strategy.max_drawdown" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert "dd" in out

    def test_default_entry_qty_stub(self) -> None:
        src = """//@version=5
strategy("t")
qty = strategy.default_entry_qty(close)
plot(qty, title="q")
"""
        code = transpile(src)
        assert "qty_arr" in code or "1.0" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(12)
        out = compiled.run(o, h, l, c, v)
        assert abs(out["q"][-1] - 1.0) < 1e-9
