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

"""Pending order fill + partial fill broker simulation."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator


def test_limit_buy_fills_when_low_touches():
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 105.0,
        "high": 106.0,
        "low": 99.0,
        "close": 101.0,
        "bar_index": 1,
        "time": 1000,
    }
    m = e._build_builtin_map()
    # limit buy: (id, action, qty, limit)
    m["strategy.order"](["L1", "buy", 2.0, 100.0])
    assert "L1" in e._strategy_state.pending_orders
    filled = e.process_pending_orders(open_=105.0, high=106.0, low=99.0, close=101.0)
    assert "L1" in filled
    assert e._strategy_state.position_direction == "long"
    assert e._strategy_state.position_size == 2.0


def test_partial_fill_across_bars():
    e = NodeLiteralEvaluator()
    e.context = {"open": 100.0, "high": 100.0, "low": 90.0, "close": 95.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy.order"]([], {"id": "L", "action": "buy", "qty": 10.0, "limit": 100.0, "max_fill_per_bar": 3.0})
    assert "L" in e._strategy_state.pending_orders
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 3.0
    assert "L" in e._strategy_state.pending_orders
    assert e._strategy_state.pending_orders["L"].remaining_qty == 7.0
    e.context["bar_index"] = 1
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 6.0
    # finish remaining
    e._strategy_state.pending_orders["L"].max_fill_per_bar = 0.0
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 10.0
    assert "L" not in e._strategy_state.pending_orders


def test_strategy_exit_pending_between_stop_limit():
    """strategy.exit with stop+limit stays pending while OHLC is between levels."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 5.0])
    assert e._strategy_state.position_size == 5.0
    m["strategy.exit"]([], {"id": "X", "from_entry": "L", "qty": 5.0, "limit": 110.0, "stop": 90.0})
    assert e._strategy_state.position_size == 5.0
    assert any(k.startswith("X") for k in e._strategy_state.pending_orders)
    # TP touch
    e.context.update({"open": 100.0, "high": 112.0, "low": 99.0, "close": 111.0, "bar_index": 1})
    e.process_pending_orders(open_=100.0, high=112.0, low=99.0, close=111.0)
    assert e._strategy_state.position_direction == "flat"
    assert e._strategy_state.position_size == 0.0


def test_stop_sell_closes_long():
    e = NodeLiteralEvaluator()
    e.context = {"open": 100.0, "high": 110.0, "low": 100.0, "close": 105.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 5.0])
    assert e._strategy_state.position_size == 5.0
    # stop-only sell: limit=None, stop=95 via kwargs
    m["strategy.order"]([], {"id": "SL", "action": "sell", "qty": 5.0, "stop": 95.0})
    assert "SL" in e._strategy_state.pending_orders
    # bar does not touch 95
    e.process_pending_orders(open_=100.0, high=102.0, low=98.0, close=101.0)
    assert e._strategy_state.position_direction == "long"
    # bar hits stop
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=92.0)
    assert e._strategy_state.position_direction == "flat"
    assert len(e._strategy_state.closed_trades) >= 1


def test_request_seed_reproducible_footprint():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    m["request.seed"]([42])
    fp1 = m["request.footprint"]([5, 70])
    m["request.seed"]([42])
    fp2 = m["request.footprint"]([5, 70])
    assert fp1.rows[0].buy_volume == fp2.rows[0].buy_volume


def test_bar_mode_kama_dema_scalar():
    e = NodeLiteralEvaluator()
    e._pine_bar_mode = True
    m = e._build_builtin_map()
    series = [float(i) for i in range(1, 30)]
    k = m["ta.kama"]([series, 10, 2, 30])
    d = m["ta.dema"]([series, 5])
    t = m["ta.tema"]([series, 5])
    assert isinstance(k, (int, float)) or k is None
    assert isinstance(d, (int, float)) or d is None
    assert isinstance(t, (int, float)) or t is None


# ---------------------------------------------------------------------------
# F2: pending-fill averaging when pyramiding ≤ 0 (single leg + VWAP)
# ---------------------------------------------------------------------------


def test_pyramiding0_partial_fills_single_leg_vwap():
    """Same order partial-fills merge into one open trade with VWAP entry."""
    e = NodeLiteralEvaluator()
    e.context = {"open": 100.0, "high": 100.0, "low": 90.0, "close": 95.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 0})
    m["strategy.order"]([], {"id": "L", "action": "buy", "qty": 10.0, "limit": 100.0, "max_fill_per_bar": 4.0})

    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 4.0
    assert len(e._strategy_state.open_trades) == 1
    assert e._strategy_state.entry_price == 100.0

    e.context["bar_index"] = 1
    # Second slice fills at limit 100 still (low touches)
    e.process_pending_orders(open_=98.0, high=100.0, low=90.0, close=95.0)
    st = e._strategy_state
    assert st.position_size == 8.0
    assert len(st.open_trades) == 1
    # open gap below limit → fill min(lim, open)=98 for first bar of second slice
    # bar open=98 < lim=100 → fill at 98
    expected = (4.0 * 100.0 + 4.0 * 98.0) / 8.0
    assert abs(st.entry_price - expected) < 1e-9
    assert abs(st.open_trades[0].entry_price - expected) < 1e-9
    assert st.open_trades[0].size == 8.0
    assert st.open_trades[0].entry_id == "L"


def test_pyramiding0_multiple_pending_orders_vwap_single_leg():
    """Two different pending buy limits → size sum, VWAP avg, one open trade."""
    e = NodeLiteralEvaluator()
    e.context = {"open": 105.0, "high": 110.0, "low": 90.0, "close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 0})
    m["strategy.order"]([], {"id": "A", "action": "buy", "qty": 2.0, "limit": 100.0})
    m["strategy.order"]([], {"id": "B", "action": "buy", "qty": 4.0, "limit": 95.0})

    filled = e.process_pending_orders(open_=105.0, high=110.0, low=90.0, close=100.0)
    assert set(filled) == {"A", "B"}
    st = e._strategy_state
    assert st.position_direction == "long"
    assert st.position_size == 6.0
    assert len(st.open_trades) == 1
    # A fills at 100 (open>lim), B at 95
    expected = (2.0 * 100.0 + 4.0 * 95.0) / 6.0
    assert abs(st.entry_price - expected) < 1e-9
    assert abs(st.open_trades[0].entry_price - expected) < 1e-9
    assert st.open_trades[0].size == 6.0
    # First fill keeps first entry id on the merged leg
    assert st.open_trades[0].entry_id == "A"
    # Still emit one entry event per fill (event order parity)
    entry_events = [ev for ev in st._events if ev.kind == "entry"]
    assert len(entry_events) == 2
    assert {ev.id for ev in entry_events} == {"A", "B"}


def test_pyramiding0_limit_entry_pending_single_leg():
    """strategy.entry limit orders with pyramiding=0 also merge to one leg."""
    e = NodeLiteralEvaluator()
    e.context = {"open": 105.0, "high": 110.0, "low": 90.0, "close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 0})
    m["strategy.entry"](["E1", "long", 2.0], {"limit": 100.0})
    m["strategy.entry"](["E2", "long", 3.0], {"limit": 100.0})
    e.process_pending_orders(open_=105.0, high=110.0, low=90.0, close=100.0)
    st = e._strategy_state
    assert st.position_size == 5.0
    assert len(st.open_trades) == 1
    assert st.entry_price == 100.0
    assert st.open_trades[0].size == 5.0


def test_pyramiding0_short_pending_fills_vwap():
    """Short side: stacked sell limits average down correctly as single leg."""
    e = NodeLiteralEvaluator()
    e.context = {"open": 90.0, "high": 110.0, "low": 85.0, "close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 0})
    m["strategy.order"]([], {"id": "S1", "action": "sell", "qty": 1.0, "limit": 100.0})
    m["strategy.order"]([], {"id": "S2", "action": "sell", "qty": 3.0, "limit": 105.0})
    e.process_pending_orders(open_=90.0, high=110.0, low=85.0, close=100.0)
    st = e._strategy_state
    assert st.position_direction == "short"
    assert st.position_size == 4.0
    assert len(st.open_trades) == 1
    # sell limit: fill max(lim, open) when open > lim else lim
    # S1: open 90 < 100 → fill 100; S2: open 90 < 105 → fill 105
    expected = (1.0 * 100.0 + 3.0 * 105.0) / 4.0
    assert abs(st.entry_price - expected) < 1e-9


def test_pyramiding_gt0_pending_still_appends_legs():
    """pyramiding>0 pending fills keep multi-leg open_trades (no silent change)."""
    e = NodeLiteralEvaluator()
    e.context = {"open": 105.0, "high": 110.0, "low": 90.0, "close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 1})  # max 2 open trades
    m["strategy.order"]([], {"id": "A", "action": "buy", "qty": 2.0, "limit": 100.0})
    m["strategy.order"]([], {"id": "B", "action": "buy", "qty": 3.0, "limit": 100.0})
    e.process_pending_orders(open_=105.0, high=110.0, low=90.0, close=100.0)
    st = e._strategy_state
    assert st.position_size == 5.0
    assert len(st.open_trades) == 2
    assert st.open_trades[0].entry_id == "A"
    assert st.open_trades[1].entry_id == "B"
    assert abs(st.entry_price - 100.0) < 1e-9
    # Third fill blocked at cap (pyramiding+1 == 2)
    m["strategy.order"]([], {"id": "C", "action": "buy", "qty": 1.0, "limit": 100.0})
    e.process_pending_orders(open_=105.0, high=110.0, low=90.0, close=100.0)
    assert st.position_size == 5.0
    assert len(st.open_trades) == 2


def test_pyramiding0_pending_vwap_close_uses_avg():
    """Closing after averaged fills realizes PnL vs single VWAP entry."""
    e = NodeLiteralEvaluator()
    e.context = {"open": 105.0, "high": 110.0, "low": 90.0, "close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 0, "commission_value": 0.0})
    m["strategy.order"]([], {"id": "A", "action": "buy", "qty": 2.0, "limit": 100.0})
    m["strategy.order"]([], {"id": "B", "action": "buy", "qty": 2.0, "limit": 90.0})
    e.process_pending_orders(open_=105.0, high=110.0, low=90.0, close=100.0)
    # VWAP = (2*100 + 2*90)/4 = 95
    assert abs(e._strategy_state.entry_price - 95.0) < 1e-9
    e.context["bar_index"] = 1
    e.context["close"] = 105.0
    m["strategy.close"](["X"])
    assert e._strategy_state.position_direction == "flat"
    assert len(e._strategy_state.closed_trades) == 1
    ct = e._strategy_state.closed_trades[0]
    assert ct.size == 4.0
    assert abs(ct.entry_price - 95.0) < 1e-9
    # profit = (105 - 95) * 4 = 40
    assert abs(ct.profit - 40.0) < 1e-9


def test_compile_pyramiding0_pending_fill_vwap():
    """Compile broker pending path: single open_entry_count + VWAP avg."""
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    b = CompileStrategyBroker(pyramiding=0)
    b.begin_bar(0, 105.0, 110.0, 90.0, 100.0)
    b.order("A", "long", 2.0, limit=100.0)
    b.order("B", "long", 4.0, limit=95.0)
    # begin_bar already processed pending empty; place then process
    b.process_pending_orders(105.0, 110.0, 90.0, 100.0)
    assert abs(b.position_size - 6.0) < 1e-9
    expected = (2.0 * 100.0 + 4.0 * 95.0) / 6.0
    assert abs(b.position_avg_price - expected) < 1e-9
    assert b.open_entry_count == 1
    entry_ev = [ev for ev in b.events if ev.get("kind") == "entry"]
    assert len(entry_ev) == 2


def test_compile_pyramiding0_partial_pending_vwap():
    from pynescript.compiler.strategy_broker import CompileStrategyBroker, PendingOrder

    b = CompileStrategyBroker(pyramiding=0)
    b.begin_bar(0, 100.0, 100.0, 90.0, 95.0)
    b.pending_orders["L"] = PendingOrder(
        order_id="L",
        order_type="limit",
        direction="long",
        quantity=10.0,
        limit_price=100.0,
        max_fill_per_bar=4.0,
    )
    b.process_pending_orders(100.0, 100.0, 90.0, 95.0)
    assert abs(b.position_size - 4.0) < 1e-9
    b.begin_bar(1, 98.0, 100.0, 90.0, 95.0)
    # remaining 6, max_fill 4 → +4 at fill min(100, 98)=98
    assert abs(b.position_size - 8.0) < 1e-9
    expected = (4.0 * 100.0 + 4.0 * 98.0) / 8.0
    assert abs(b.position_avg_price - expected) < 1e-9
    assert b.open_entry_count == 1
