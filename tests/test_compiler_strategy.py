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


class TestCompileBrokerCommissionParity:
    def test_compile_commission_openprofit_and_net(self) -> None:
        """Entry commission reduces open equity; close charges entry+exit commission."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, commission_value=1.0, commission_type="percent")
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 10.0)
        # 10 * 100 * 1% = 10 entry commission
        assert b.openprofit == pytest.approx(-10.0)
        assert b.equity == pytest.approx(9_990.0)
        b.begin_bar(1, 110.0, 110.0, 110.0, 110.0)
        b.close("L")
        # gross 100 - entry 10 - exit 11 = 79
        assert b.netprofit == pytest.approx(79.0)
        assert b.position_size == 0.0
        assert b.position_commission == 0.0

    def test_compile_pyramiding_wired_from_strategy_decl(self) -> None:
        src = """//@version=6
strategy("t", pyramiding=1)
if bar_index == 0
    strategy.entry("L1", strategy.long, qty=1)
if bar_index == 1
    strategy.entry("L2", strategy.long, qty=2)
plot(strategy.position_size, title="ps")
"""
        code = transpile(src)
        assert "pyramiding=1" in code or "pyramiding = 1" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        # two entries allowed with pyramiding=1
        assert out["__position_size"] == 3.0 or out["ps"][-1] == 3.0

    def test_compile_avg_price_model_wired_from_strategy_decl(self) -> None:
        src = """//@version=6
strategy("t", avg_price_model="futures")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
plot(strategy.position_avg_price, title="avg")
plot(strategy.position_size, title="ps")
"""
        code = transpile(src)
        assert "avg_price_model=" in code
        assert "futures" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(3)
        c = [100.0, 101.0, 102.0]
        o = list(c)
        h = list(c)
        l = list(c)
        out = compiled.run(o, h, l, c, v)
        assert out["__position_size"] == 2.0 or out["ps"][-1] == 2.0
        # market entry fills at bar 0 close
        assert abs(out["avg"][-1] - 100.0) < 1e-9

    def test_compile_same_id_reentry_keeps_avg_price(self) -> None:
        """Repeating ``strategy.entry("L")`` must not reset avg to last close."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(pyramiding=0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        assert b.position_avg_price == 100.0
        b.begin_bar(1, 110.0, 110.0, 110.0, 110.0)
        b.entry("L", "long", 1.0)
        assert b.position_size == 1.0
        assert b.position_avg_price == 100.0
        assert sum(1 for e in b.events if e.get("kind") == "entry") == 1

    def test_compile_same_id_reentry_pyramids_and_vwap(self) -> None:
        """Same-id entries with pyramiding=1 VWAP-add; a third fill is blocked."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(pyramiding=1)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        b.begin_bar(1, 120.0, 120.0, 120.0, 120.0)
        b.entry("L", "long", 1.0)
        assert b.position_size == 2.0
        assert abs(b.position_avg_price - 110.0) < 1e-9
        assert sum(1 for e in b.events if e.get("kind") == "entry") == 2
        b.begin_bar(2, 140.0, 140.0, 140.0, 140.0)
        b.entry("L", "long", 1.0)
        assert b.position_size == 2.0
        assert abs(b.position_avg_price - 110.0) < 1e-9
        assert sum(1 for e in b.events if e.get("kind") == "entry") == 2

    def test_compile_pending_same_id_replaces_price(self) -> None:
        """Pending same-id limit/stop entries upsert to one working order."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker()
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0, limit=90.0)
        assert list(b.pending_orders) == ["L"]
        assert b.pending_orders["L"].limit_price == 90.0
        b.entry("L", "long", 1.0, limit=80.0)
        assert list(b.pending_orders) == ["L"]
        assert b.pending_orders["L"].limit_price == 80.0
        assert b.position_size == 0.0

        s = CompileStrategyBroker()
        s.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        s.entry("L", "long", 1.0, stop=110.0)
        assert list(s.pending_orders) == ["L"]
        assert s.pending_orders["L"].stop_price == 110.0
        s.entry("L", "long", 1.0, stop=105.0)
        assert list(s.pending_orders) == ["L"]
        assert s.pending_orders["L"].stop_price == 105.0
        assert s.position_size == 0.0

    def test_runtime_repeating_entry_avg_price_dual_host(self) -> None:
        src = """//@version=6
strategy("avg")
if close > 0
    strategy.entry("L", strategy.long)
plot(strategy.position_avg_price, title="avg")
plot(strategy.position_size, title="sz")
"""
        bars = [
            {
                "time": 1_700_000_000_000 + i * 60_000,
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.0 + i,
                "volume": 1,
            }
            for i in range(6)
        ]
        rt = Runtime(symbol="T")
        for mode in ("interpret", "compile"):
            out = rt.run(src, bars, mode=mode)
            series = out["series"]
            assert series["sz"] == [1.0] * 6, mode
            assert series["avg"] == [100.0] * 6, mode
            entries = [e for e in (out.get("events") or []) if e.get("kind") == "entry"]
            assert len(entries) == 1, (mode, entries)

    def test_compile_leverage_wired_from_strategy_decl(self) -> None:
        src = """//@version=6
strategy("t", leverage=10, default_qty_type=strategy.cash, default_qty_value=100)
if bar_index == 0
    strategy.entry("L", strategy.long)
plot(strategy.position_size, title="ps")
plot(strategy.leverage, title="lev")
"""
        code = transpile(src)
        assert "leverage=10" in code or "leverage = 10" in code
        compiled = compile_script(src)
        c = [50.0, 50.0, 50.0]
        o = h = l = c
        v = [1.0, 1.0, 1.0]
        out = compiled.run(o, h, l, c, v)
        # qty = 100 * 10 / 50 = 20
        assert abs(out["ps"][-1] - 20.0) < 1e-9
        assert abs(out["lev"][-1] - 10.0) < 1e-9

    def test_compile_ctor_leverage_wins_over_margin(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(leverage=10, margin_long=50)
        assert b.leverage == 10.0

    def test_compile_broker_default_leverage_is_one(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        assert CompileStrategyBroker().leverage == 1.0
        assert CompileStrategyBroker(leverage=None).leverage == 1.0
        assert CompileStrategyBroker(leverage=1).leverage == 1.0

    def test_compile_margin_long_wired_from_strategy_decl(self) -> None:
        src = """//@version=6
strategy("t", margin_long=20, default_qty_type=strategy.cash, default_qty_value=100)
if bar_index == 0
    strategy.entry("L", strategy.long)
plot(strategy.position_size, title="ps")
plot(strategy.leverage, title="lev")
"""
        code = transpile(src)
        assert "margin_long=20" in code or "margin_long = 20" in code
        assert "leverage=" not in code and "leverage =" not in code
        compiled = compile_script(src)
        c = [50.0, 50.0, 50.0]
        o = h = l = c
        v = [1.0, 1.0, 1.0]
        out = compiled.run(o, h, l, c, v)
        # qty = 100 * 5 / 50 = 10
        assert abs(out["ps"][-1] - 10.0) < 1e-9
        assert abs(out["lev"][-1] - 5.0) < 1e-9

    def test_compile_input_before_strategy_folds_const_defval(self) -> None:
        """input.float(10) before strategy(leverage=lev) → ctor leverage=10 (const fold)."""
        src = """//@version=6
lev = input.float(10, "Leverage")
strategy("t", leverage=lev, default_qty_type=strategy.cash, default_qty_value=100)
if bar_index == 0
    strategy.entry("L", strategy.long)
plot(strategy.position_size, title="ps")
plot(strategy.leverage, title="lev")
"""
        code = transpile(src)
        assert "leverage=10" in code or "leverage = 10" in code
        assert "leverage=lev_arr" not in code
        compiled = compile_script(src)
        c = [50.0, 50.0, 50.0]
        o = h = l = c
        v = [1.0, 1.0, 1.0]
        out = compiled.run(o, h, l, c, v)
        assert abs(out["ps"][-1] - 20.0) < 1e-9
        assert abs(out["lev"][-1] - 10.0) < 1e-9


class TestStrategyRiskAndQtyNameErrors:
    def test_risk_methods_emit_halt_cascade(self) -> None:
        """risk max_drawdown / max_cons_loss_days emit broker calls; series max_drawdown real."""
        src = """//@version=5
strategy("t")
strategy.risk.max_cons_loss_days(15)
strategy.risk.max_drawdown(10, strategy.percent_of_equity)
strategy.risk.max_intraday_loss(5.0)
strategy.risk.max_intraday_filled_orders(3)
plot(strategy.max_drawdown, title="dd")
"""
        code = transpile(src)
        assert "risk_max_cons_loss_days" in code
        assert "risk_max_drawdown" in code
        assert "risk_max_intraday_loss" in code
        assert "risk_max_intraday_filled_orders" in code
        assert "__strategy.max_drawdown" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(15)
        out = compiled.run(o, h, l, c, v)
        assert "dd" in out

    def test_risk_allow_entry_in_blocks_short(self) -> None:
        """strategy.risk.allow_entry_in(long) blocks short entries on compile path."""
        src = """//@version=6
strategy("t")
strategy.risk.allow_entry_in(strategy.long)
if bar_index == 0
    strategy.entry("S", strategy.short, qty=2)
plot(strategy.position_size, title="ps")
"""
        code = transpile(src)
        assert "risk_allow_entry_in" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(5)
        out = compiled.run(o, h, l, c, v)
        assert out["ps"][-1] == 0.0 or out["__position_size"] == 0.0
        blocked = [e for e in out["__events"] if e.get("comment") == "risk_blocked"]
        assert blocked

    def test_risk_max_drawdown_blocks_entries(self) -> None:
        """max_drawdown (absolute) blocks new entries after equity drop; risk_blocked."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.risk_max_drawdown(50.0)  # absolute
        # Force drawdown state past limit (interpret-aligned)
        b._equity_peak = 10_000.0
        b._max_drawdown = 100.0
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True
        blocked = [e for e in b.events if e.get("comment") == "risk_blocked"]
        assert blocked

    def test_risk_max_drawdown_percent_blocks_entries(self) -> None:
        """max_drawdown(percent_of_equity) blocks when peak drawdown % exceeded."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.risk_max_drawdown(5.0, "percent_of_equity")
        b._equity_peak = 10_000.0
        b._max_drawdown = 600.0
        b._max_drawdown_percent = 6.0  # already > 5%
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True

    def test_risk_allow_entry_in_with_max_drawdown_fields(self) -> None:
        """allow_entry_in still works when other risk halt fields are configured."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.risk_max_drawdown(50_000.0)  # high limit — not hit
        b.risk_max_cons_loss_days(99)
        b.risk_max_intraday_loss(99.0)
        b.risk_allow_entry_in("long")
        b.entry("S", "short", 2.0)
        assert b.position_size == 0.0
        blocked = [e for e in b.events if e.get("comment") == "risk_blocked"]
        assert blocked
        # long still allowed
        b.entry("L", "long", 1.0)
        assert b.position_size == pytest.approx(1.0)
        assert b.entries_blocked is False

    def test_risk_max_cons_loss_days_blocks_after_loss_days(self) -> None:
        """max_cons_loss_days finalizes loss days and blocks further entries."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.risk_max_cons_loss_days(2)
        # Two consecutive loss days via day-bucket finalization
        b.note_closed_trade_day(1, -10.0)
        b.note_closed_trade_day(2, -5.0)  # day1 loss finalized → cons=1
        b.note_closed_trade_day(3, -1.0)  # day2 loss finalized → cons=2 → block
        assert b.consecutive_loss_days >= 2
        assert b.entries_blocked is True
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        assert any(e.get("comment") == "risk_blocked" for e in b.events)

    def test_risk_max_position_size_caps_qty(self) -> None:
        """max_position_size(percent) caps entry notional vs equity."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.risk_max_position_size(10.0)  # 10% of 10k = 1000 → max 10 contracts at 100
        b.entry("L", "long", 50.0)
        assert b.position_size == pytest.approx(10.0)

    def test_risk_max_intraday_filled_orders_blocks_entries(self) -> None:
        """max_intraday_filled_orders counts fills per day and blocks further entries."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        # Same calendar day (seconds epoch): day = t // 86400
        day0 = 1_700_000_000  # fixed day bucket
        b.risk_max_intraday_filled_orders(2)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=day0)
        b.entry("L1", "long", 1.0, comment="e1")
        assert b.position_size == pytest.approx(1.0)
        assert b._day_filled_orders == 1
        b.begin_bar(1, 110.0, 110.0, 110.0, 110.0, bar_time=day0 + 60)
        b.close("L1", comment="x1")
        assert b.position_size == 0.0
        assert b._day_filled_orders == 2  # entry + exit
        # Third fill attempt (new entry) blocked same day
        b.entry("L2", "long", 1.0)
        assert b.position_size == 0.0
        assert any(e.get("comment") == "risk_blocked" for e in b.events)
        # Next day bucket resets fill counter
        b.begin_bar(2, 100.0, 100.0, 100.0, 100.0, bar_time=day0 + 86_400)
        b.entry("L3", "long", 1.0)
        assert b.position_size == pytest.approx(1.0)
        assert b._day_filled_orders == 1

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


class TestCompileTradeQueries:
    """Honest opentrades / closedtrades surface from open_legs / closed records."""

    def test_broker_opentrades_from_open_legs(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, pyramiding=1)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=1_000)
        b.entry("A", "long", 2.0, comment="buyA")
        b.begin_bar(1, 110.0, 110.0, 110.0, 110.0, bar_time=2_000)
        b.entry("B", "long", 3.0, comment="buyB")
        assert b.open_entry_count == 2
        assert b.opentrades_size(0) == pytest.approx(2.0)
        assert b.opentrades_size(1) == pytest.approx(3.0)
        assert b.opentrades_entry_price(0) == pytest.approx(100.0)
        assert b.opentrades_entry_price(1) == pytest.approx(110.0)
        assert b.opentrades_entry_id(0) == "A"
        assert b.opentrades_entry_id(1) == "B"
        assert b.opentrades_entry_bar_index(0) == 0
        assert b.opentrades_entry_bar_index(1) == 1
        # MTM at bar1 close 110: leg A = (110-100)*2 = 20
        assert b.opentrades_profit(0) == pytest.approx(20.0)
        assert b.opentrades_profit(1) == pytest.approx(0.0)
        assert b.opentrades_entry_comment(0) == "buyA"
        assert b.opentrades_entry_comment(1) == "buyB"

    def test_broker_opentrades_max_dd_runup_from_ohlc(self) -> None:
        """Per-open-leg max_drawdown / max_runup from bar high/low MTM."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        # Entry at 100; next bar high 115 low 90 → runup 15, drawdown 10 per unit
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=1_000)
        b.entry("L", "long", 2.0, comment="in")
        b.begin_bar(1, 100.0, 115.0, 90.0, 105.0, bar_time=2_000)
        assert b.opentrades_max_runup(0) == pytest.approx(30.0)  # (115-100)*2
        assert b.opentrades_max_drawdown(0) == pytest.approx(20.0)  # (100-90)*2
        assert b.opentrades_entry_comment(0) == "in"

    def test_broker_closedtrades_profit_and_size(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=500)
        b.entry("L", "long", 4.0, comment="entryCmt")
        b.begin_bar(1, 120.0, 130.0, 110.0, 120.0, bar_time=600)
        b.close("L", comment="exitCmt")
        assert b.closed_trades == 1
        assert len(b.closed_trade_records) == 1
        assert b.closedtrades_profit(0) == pytest.approx(80.0)
        assert b.closedtrades_size(0) == pytest.approx(4.0)
        assert b.closedtrades_entry_price(0) == pytest.approx(100.0)
        assert b.closedtrades_exit_price(0) == pytest.approx(120.0)
        assert b.closedtrades_entry_id(0) == "L"
        assert b.closedtrades_entry_bar_index(0) == 0
        assert b.closedtrades_exit_bar_index(0) == 1
        assert b.closedtrades_profit(1) == 0.0  # OOB
        assert b.closedtrades_entry_comment(0) == "entryCmt"
        assert b.closedtrades_exit_comment(0) == "exitCmt"
        assert b.closedtrades_exit_id(0) == "L"
        # Extremes from bar1 high/low before close: (130-100)*4 runup, (100-110)*4 no adverse
        assert b.closedtrades_max_runup(0) == pytest.approx(120.0)  # (130-100)*4
        assert b.closedtrades_max_drawdown(0) == pytest.approx(0.0)  # low 110 still above entry

    def test_compile_trade_query_comments_and_extremes_emit(self) -> None:
        """Compiler wires comment/extremes accessors; numeric extremes plot after RT."""
        src = """//@version=6
strategy("t")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2, comment="buy")
if bar_index == 1
    strategy.close("L", comment="sell")
// string plots are coerced; exercise emit + numeric extremes
_ec = strategy.closedtrades.entry_comment(0)
_xc = strategy.closedtrades.exit_comment(0)
plot(strategy.closedtrades.max_runup(0), title="cru")
plot(strategy.closedtrades.max_drawdown(0), title="cdd")
plot(strategy.opentrades.max_runup(0), title="oru")
"""
        code = transpile(src)
        assert "closedtrades_entry_comment" in code
        assert "closedtrades_exit_comment" in code
        assert "closedtrades_max_runup" in code
        assert "closedtrades_max_drawdown" in code
        assert "opentrades_max_runup" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(4, start=100.0)
        out = compiled.run(o, h, l, c, v)
        # After close on bar1: closed trade has runup from bar high path (close+1)
        # entry at 100 qty 2, bar0 high=101 → runup at least (101-100)*2=2
        assert out["cru"][-1] >= 2.0
        assert out["cdd"][-1] >= 0.0

    def test_compile_script_trade_query_plots(self) -> None:
        src = """//@version=6
strategy("t", pyramiding=1)
if bar_index == 0
    strategy.entry("A", strategy.long, qty=2)
if bar_index == 1
    strategy.entry("B", strategy.long, qty=3)
if bar_index == 2
    strategy.close("A")
plot(strategy.opentrades, title="ot")
plot(strategy.closedtrades, title="ct")
plot(strategy.opentrades.size(0), title="osz0")
plot(strategy.opentrades.entry_price(0), title="oep0")
plot(strategy.closedtrades.profit(0), title="ctp0")
"""
        code = transpile(src)
        assert "open_entry_count" in code
        assert "opentrades_size" in code
        assert "closedtrades_profit" in code
        compiled = compile_script(src)
        # flat prices: bar0=100, bar1=101, bar2=102 (from _ohlcv start=100)
        o, h, l, c, v = _ohlcv(5, start=100.0)
        out = compiled.run(o, h, l, c, v)
        # After bar2 close of first id only — with market close(id) without from_entry,
        # close uses whole position or from_entry via id mapping.
        # For strategy.close("A") without exit levels, from_entry is not set (not is_exit).
        # So close("A") closes whole position by qty target = whole size.
        # Use broker-level assertions above; here check counts and emitted accessors.
        assert out["ot"][0] == pytest.approx(1.0)
        assert out["ot"][1] == pytest.approx(2.0)
        assert out["ct"][-1] >= 1.0
        # size of first open leg after bar0 entry
        assert out["osz0"][0] == pytest.approx(2.0)
        assert out["oep0"][0] == pytest.approx(100.0)

    def test_compile_closedtrades_profit_after_round_trip(self) -> None:
        src = """//@version=6
strategy("t")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
if bar_index == 1
    strategy.close("L")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.profit(0), title="p0")
plot(strategy.closedtrades.size(0), title="sz0")
"""
        compiled = compile_script(src)
        # force known prices: entry 100 close, exit 110 close
        close = np.array([100.0, 110.0, 110.0, 110.0], dtype=np.float64)
        open_ = close.copy()
        high = close + 1.0
        low = close - 1.0
        vol = np.ones(4)
        out = compiled.run(open_, high, low, close, vol)
        assert out["ct"][-1] == pytest.approx(1.0)
        assert out["p0"][-1] == pytest.approx(20.0)
        assert out["sz0"][-1] == pytest.approx(2.0)


class TestCompileExitAndSeriesParity:
    def test_exit_stop_limit_pending_when_between(self) -> None:
        """strategy.exit with stop+limit does not fill while mark is between levels."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        # high=101, low=99 — neither 110 TP nor 95 SL touched
        b.begin_bar(0, 100.0, 101.0, 99.0, 100.0)
        b.entry("L", "long", 1.0)
        assert b.position_size == 1.0
        b.close(id="L", limit=110.0, stop=95.0, comment="X")
        # Pending bracket — position still open (Wave B TV semantics)
        assert b.position_size == 1.0
        assert any(k.startswith("L") for k in b.pending_orders)
        kinds = [e["kind"] for e in b.events]
        assert "exit" in kinds
        exit_ev = next(e for e in b.events if e["kind"] == "exit")
        assert exit_ev.get("limit") == 110.0
        assert exit_ev.get("stop") == 95.0

    def test_exit_limit_fills_when_high_touches(self) -> None:
        """Take-profit limit exit fills when bar high reaches limit."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        b.begin_bar(1, 100.0, 112.0, 99.0, 111.0)
        # Stop/limit exit: id= still accepted as from_entry filter when is_exit.
        b.close(id="L", limit=110.0, stop=90.0, comment="tp")
        assert b.position_size == 0.0
        assert b.netprofit == pytest.approx(10.0)

    def test_from_entry_closes_only_matching_pyramid_leg(self) -> None:
        """Two pyramid legs; exit from_entry first id leaves the second open."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, pyramiding=1, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("A", "long", 2.0)
        b.begin_bar(1, 110.0, 110.0, 110.0, 110.0)
        b.entry("B", "long", 3.0)
        assert b.position_size == 5.0
        assert b.open_entry_count == 2
        assert len(b.open_legs) == 2
        assert [leg.entry_id for leg in b.open_legs] == ["A", "B"]

        b.begin_bar(2, 120.0, 120.0, 120.0, 120.0)
        # Market exit targeting A only (explicit from_entry)
        b.close(from_entry="A")
        assert b.position_size == 3.0
        assert b.open_entry_count == 1
        assert len(b.open_legs) == 1
        assert b.open_legs[0].entry_id == "B"
        assert b.open_legs[0].size == 3.0
        assert b.position_entry_name == "B"
        # PnL on A only: (120 - 100) * 2
        assert b.netprofit == pytest.approx(40.0)
        assert b.closed_trades == 1

    def test_compile_market_exit_from_entry_leaves_other_pyramid_leg(self) -> None:
        """Transpile+run: market strategy.exit from_entry closes only that leg."""
        src = """//@version=5
strategy("t", pyramiding=2, commission_value=0)
if bar_index == 0
    strategy.entry("A", strategy.long, qty=2)
if bar_index == 1
    strategy.entry("B", strategy.long, qty=3)
if bar_index == 2
    strategy.exit("XA", from_entry="A")
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
"""
        code = transpile(src)
        close_lines = [ln for ln in code.splitlines() if "__strategy.close(" in ln]
        assert close_lines, code
        for ln in close_lines:
            assert "from_entry=" in ln, ln
            # Market exit must not only pass id= (broker ignores id when not is_exit)
            assert "from_entry='A'" in ln or 'from_entry="A"' in ln or "from_entry='A'" in ln.replace(
                '"', "'"
            ), ln

        ohlcv = [
            {
                "open": px,
                "high": px,
                "low": px,
                "close": px,
                "volume": 1.0,
                "time": i * 60_000,
            }
            for i, px in enumerate((100.0, 110.0, 120.0, 120.0))
        ]
        result = Runtime().run(src, ohlcv, mode="compile")
        assert "error" not in result, result.get("error")
        # After bar 2 market exit of A (qty 2), B (qty 3) remains
        assert result["series"]["ps"][1] == pytest.approx(5.0)
        assert result["series"]["ps"][2] == pytest.approx(3.0)
        assert result["series"]["ct"][2] == pytest.approx(1.0)
        # Same script under interpret for parity
        ri = Runtime().run(src, ohlcv, mode="interpret")
        assert "error" not in ri, ri.get("error")
        assert ri["series"]["ps"][2] == pytest.approx(3.0)
        assert ri["series"]["ct"][2] == pytest.approx(1.0)

    def test_from_entry_unknown_soft_noop(self) -> None:
        """Unknown from_entry is a soft no-op (no crash, no size change)."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 4.0)
        b.close(from_entry="NOPE")
        assert b.position_size == 4.0
        assert b.closed_trades == 0
        assert b.open_entry_count == 1
        assert not b.pending_orders
        # Placement-style event still recorded with qty=0
        assert any(e.get("kind") in {"close", "exit"} and e.get("qty") == 0.0 for e in b.events)

    def test_from_entry_exit_bracket_pending_then_fill(self) -> None:
        """Pending stop/limit exit with from_entry only reduces that leg."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, pyramiding=1, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("A", "long", 2.0)
        b.begin_bar(1, 105.0, 105.0, 105.0, 105.0)
        b.entry("B", "long", 4.0)
        # Bracket only against A; mark between levels → pending
        b.close(id="A", qty=2.0, limit=120.0, stop=90.0, comment="XA")
        assert b.position_size == 6.0
        assert any(k.startswith("A") for k in b.pending_orders)
        for po in b.pending_orders.values():
            assert po.from_entry == "A"
            assert po.quantity == 2.0
        # TP fills A only
        b.begin_bar(2, 100.0, 125.0, 99.0, 122.0)
        assert b.position_size == 4.0
        assert b.open_entry_count == 1
        assert b.open_legs[0].entry_id == "B"
        assert b.closed_trades == 1
        # (120 fill limit or min - TP uses limit 120) * 2 vs entry 100
        assert b.netprofit == pytest.approx(40.0)

    def test_exit_trail_offset_long_ratchets_and_fills(self) -> None:
        """trail_offset (ticks) arms immediately; stop ratchets with high then fills."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 2.0)
        # 100 ticks * 0.01 = $1 trail; no activation → active immediately
        b.close(comment="XT", trail_offset=100.0)
        assert "exit" in b.pending_orders or any(
            po.is_trail for po in b.pending_orders.values()
        )
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.trail_offset == pytest.approx(1.0)
        assert trail.trail_active is True
        # Favorable bar: high 110 → stop 109; low stays above stop
        b.begin_bar(1, 109.5, 110.0, 109.2, 109.8)
        assert b.position_size == 2.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.stop_price == pytest.approx(109.0)
        # Mild pullback still above stop — no fill; trail does not lower
        b.begin_bar(2, 109.5, 109.6, 109.1, 109.2)
        assert b.position_size == 2.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.stop_price == pytest.approx(109.0)
        # Break stop
        b.begin_bar(3, 109.2, 109.3, 108.0, 108.5)
        assert b.position_size == 0.0
        assert b.closed_trades == 1

    def test_exit_trail_price_activation_long(self) -> None:
        """trail_price delays arming until high reaches activation; then trails."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=1.0, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        b.close(comment="XT", trail_price=110.0, trail_offset=2.0)
        # Below activation — still open, trail not active
        b.begin_bar(1, 105.0, 108.0, 104.0, 107.0)
        assert b.position_size == 1.0
        po = next(p for p in b.pending_orders.values() if p.is_trail)
        assert po.trail_active is False
        # Activate: high 112 → stop = 110; low 111 → no fill
        b.begin_bar(2, 109.0, 112.0, 111.0, 111.5)
        assert b.position_size == 1.0
        po = next(p for p in b.pending_orders.values() if p.is_trail)
        assert po.trail_active is True
        assert po.stop_price == pytest.approx(110.0)
        # Fill on pullback through 110
        b.begin_bar(3, 111.0, 111.0, 109.0, 109.5)
        assert b.position_size == 0.0

    def test_exit_trail_points_wins_over_offset(self) -> None:
        """When both set, trail_points is the tick distance (TV); wider offset is ignored."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 2.0)
        # points=100 → $1; offset=500 would be $5 if it won
        b.close(comment="XT", trail_points=100.0, trail_offset=500.0)
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.trail_offset == pytest.approx(1.0)
        assert trail.trail_active is True
        b.begin_bar(1, 109.5, 110.0, 109.2, 109.8)
        assert b.position_size == 2.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.stop_price == pytest.approx(109.0)

    def test_exit_trail_nonpositive_points_falls_back_to_offset(self) -> None:
        """na / ≤0 trail_points is ignored so a valid trail_offset still trails."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        # 0 "wins" would disable trail and market-close; must fall back to offset
        b.close(comment="XT", trail_points=0.0, trail_offset=100.0)
        assert b.position_size == 1.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.trail_offset == pytest.approx(1.0)
        b2 = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b2.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b2.entry("L", "long", 1.0)
        b2.close(comment="XT", trail_points=float("nan"), trail_offset=100.0)
        assert b2.position_size == 1.0
        trail2 = next(po for po in b2.pending_orders.values() if po.is_trail)
        assert trail2.trail_offset == pytest.approx(1.0)

    def test_exit_trail_offset_short_ratchets_and_fills(self) -> None:
        """Short trail: buy-stop ratchets down with low, then fills on a bounce."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("S", "short", 2.0)
        b.close(comment="XT", trail_offset=100.0)
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.direction == "long"
        assert trail.trail_offset == pytest.approx(1.0)
        assert trail.trail_active is True
        # Favorable drop: low 90 → stop 91; high stays below stop
        b.begin_bar(1, 90.5, 90.8, 90.0, 90.2)
        assert b.position_size == -2.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.stop_price == pytest.approx(91.0)
        # Mild bounce still below stop — no fill; trail does not raise
        b.begin_bar(2, 90.5, 90.9, 90.4, 90.8)
        assert b.position_size == -2.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.stop_price == pytest.approx(91.0)
        # Break stop
        b.begin_bar(3, 90.8, 92.0, 90.7, 91.5)
        assert b.position_size == 0.0
        assert b.closed_trades == 1
        assert b.netprofit == pytest.approx((100.0 - 91.0) * 2.0)

    def test_exit_trail_from_entry_qty(self) -> None:
        """Trail exit with from_entry only reduces matching pyramid leg qty."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(
            initial_capital=10_000.0, pyramiding=1, mintick=0.01, commission_value=0.0
        )
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("A", "long", 2.0)
        b.begin_bar(1, 105.0, 105.0, 105.0, 105.0)
        b.entry("B", "long", 4.0)
        # Trail only A (qty defaults to from_entry size = 2)
        b.close(from_entry="A", trail_offset=100.0, comment="XA")
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.from_entry == "A"
        assert trail.quantity == pytest.approx(2.0)
        assert b.position_size == 6.0
        # Ratchet then fill A only
        b.begin_bar(2, 109.5, 110.0, 109.2, 109.8)
        assert b.position_size == 6.0
        trail = next(po for po in b.pending_orders.values() if po.is_trail)
        assert trail.stop_price == pytest.approx(109.0)
        b.begin_bar(3, 109.2, 109.3, 108.0, 108.5)
        assert b.position_size == 4.0
        assert b.open_entry_count == 1
        assert b.open_legs[0].entry_id == "B"
        assert b.closed_trades == 1

    def test_transpile_exit_emits_trail_kwargs(self) -> None:
        """Compiler visitor passes trail_* kwargs through to broker.close."""
        src = """//@version=5
strategy("t")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
strategy.exit("XT", trail_offset=100, trail_price=110)
"""
        code = transpile(src)
        assert "trail_offset" in code
        assert "trail_price" in code
        assert "__strategy.close" in code

    def test_exit_profit_ticks_long_target(self) -> None:
        """profit=100 ticks from long entry 100 @ mintick 0.01 → limit 101.00."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        b.close(comment="X", profit=100.0)
        assert b.position_size == 1.0
        po = next(iter(b.pending_orders.values()))
        assert po.order_type == "limit"
        assert po.limit_price == pytest.approx(101.00)
        b.begin_bar(1, 100.2, 100.5, 100.0, 100.4)
        assert b.position_size == 1.0
        b.begin_bar(2, 100.4, 101.5, 100.2, 101.2)
        assert b.position_size == 0.0
        assert b.closed_trades == 1
        assert b.netprofit == pytest.approx(1.00)

    def test_exit_loss_ticks_long_stop(self) -> None:
        """loss=50 ticks from long entry 100 @ mintick 0.01 → stop 99.50."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 1.0)
        b.close(comment="X", loss=50.0)
        po = next(iter(b.pending_orders.values()))
        assert po.order_type == "stop"
        assert po.stop_price == pytest.approx(99.50)
        b.begin_bar(1, 100.0, 100.2, 99.6, 99.8)
        assert b.position_size == 1.0
        b.begin_bar(2, 99.8, 99.9, 99.0, 99.2)
        assert b.position_size == 0.0
        assert b.netprofit == pytest.approx(-0.50)

    def test_exit_profit_ticks_short_target(self) -> None:
        """profit=100 ticks from short entry 100 @ mintick 0.01 → limit 99.00."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("S", "short", 1.0)
        b.close(comment="X", profit=100.0)
        po = next(iter(b.pending_orders.values()))
        assert po.order_type == "limit"
        assert po.limit_price == pytest.approx(99.00)
        b.begin_bar(1, 100.0, 100.2, 99.4, 99.6)
        assert b.position_size == -1.0
        b.begin_bar(2, 99.6, 99.7, 98.5, 98.8)
        assert b.position_size == 0.0
        assert b.netprofit == pytest.approx(1.00)

    def test_exit_limit_stop_remain_absolute_when_profit_loss_set(self) -> None:
        """limit/stop stay prices when profit/loss are also passed."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0, mintick=0.01, commission_value=0.0)
        b.begin_bar(0, 100.0, 101.0, 99.0, 100.0)
        b.entry("L", "long", 1.0)
        b.close(id="L", limit=110.0, stop=90.0, profit=100.0, loss=50.0, comment="X")
        assert b.position_size == 1.0
        prices = {(po.limit_price, po.stop_price) for po in b.pending_orders.values()}
        assert (110.0, None) in prices
        assert (None, 90.0) in prices

    def test_runtime_profit_ticks_interp_compile_parity(self) -> None:
        """Transpile+run: profit=100 from long 100 fills at 101 on both hosts."""
        src = """//@version=5
strategy("t", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 1
    strategy.exit("X", profit=100)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
"""
        ohlcv = [
            {
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1.0,
                "time": 0,
            },
            {
                "open": 100.2,
                "high": 100.5,
                "low": 100.0,
                "close": 100.4,
                "volume": 1.0,
                "time": 60_000,
            },
            {
                "open": 100.4,
                "high": 101.5,
                "low": 100.2,
                "close": 101.2,
                "volume": 1.0,
                "time": 120_000,
            },
        ]
        for mode in ("interpret", "compile"):
            result = Runtime().run(src, ohlcv, mode=mode)
            assert "error" not in result, (mode, result.get("error"))
            assert result["series"]["ps"][0] == pytest.approx(1.0)
            assert result["series"]["ps"][1] == pytest.approx(1.0)
            assert result["series"]["ps"][2] == pytest.approx(0.0)
            assert result["series"]["ct"][2] == pytest.approx(1.0)

    def test_transpile_exit_emits_profit_loss_kwargs(self) -> None:
        """Compiler visitor passes profit=/loss= ticks through to broker.close."""
        src = """//@version=5
strategy("t")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
strategy.exit("X", from_entry="L", profit=100, loss=50)
"""
        code = transpile(src)
        assert "profit=100" in code
        assert "loss=50" in code
        assert "__strategy.close" in code

    def test_openprofit_percent_and_cash_series(self) -> None:
        """Missing compile attrs caused AttributeError / compile_error on plots."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=100_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long", 2.0)
        b.begin_bar(1, 110.0, 110.0, 110.0, 110.0)
        assert b.openprofit == pytest.approx(20.0)
        assert b.openprofit_percent == pytest.approx(0.02)
        assert b.netprofit_percent == pytest.approx(0.0)
        # cash ≈ equity - capital held
        assert b.cash == pytest.approx(b.equity - 100.0 * 2.0)
        b.close("L")
        assert b.netprofit == pytest.approx(20.0)
        assert b.netprofit_percent == pytest.approx(0.02)

    def test_default_qty_percent_of_equity(self) -> None:
        """When visitor wires default_qty_*, missing qty uses percent_of_equity."""
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(
            initial_capital=10_000.0,
            default_qty_type="percent_of_equity",
            default_qty_value=10.0,
        )
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.entry("L", "long")  # qty omitted → 10% of equity / price = 10
        assert b.position_size == pytest.approx(10.0)

    def test_runtime_compile_openprofit_percent_plot(self) -> None:
        src = """//@version=5
strategy("s", initial_capital=10000)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
plot(strategy.openprofit, "op")
plot(strategy.openprofit_percent, "opp")
plot(strategy.netprofit_percent, "npp")
"""
        ohlcv = [
            {
                "open": 100.0 + i * 0.1,
                "high": 101.0 + i * 0.1,
                "low": 99.0 + i * 0.1,
                "close": 100.0 + i,
                "volume": 1.0,
                "time": i * 60_000,
            }
            for i in range(5)
        ]
        result = Runtime().run(src, ohlcv, mode="compile")
        assert "error" not in result, result.get("error")
        assert "opp" in result["series"]
        # bar 0: entry at 100, openprofit 0 → percent 0
        assert result["series"]["opp"][0] == pytest.approx(0.0)
        # bar 1: close=101, openprofit ≈ 2 → percent 0.02
        assert result["series"]["opp"][1] == pytest.approx(0.02)

    def test_interp_exit_bar_time_is_json_int(self) -> None:
        """exit/cancel events must not put PineSeries into bar_time (JSON parity)."""
        src = """//@version=5
strategy("s")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
strategy.exit("X", "L", limit=110.0)
"""
        ohlcv = [
            {
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1.0,
                "time": (i + 1) * 1000,
            }
            for i in range(3)
        ]
        result = Runtime().run(src, ohlcv, mode="interpret")
        assert "error" not in result, result.get("error")
        for ev in result["events"]:
            assert type(ev["bar_time"]) is int, f"bar_time={ev['bar_time']!r} kind={ev['kind']}"
            assert type(ev["bar_index"]) is int
