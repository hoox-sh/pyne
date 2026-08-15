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

import pytest

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


def test_strategy_exit_from_entry_market_leaves_other_leg():
    """Market exit from_entry=A closes only A; pyramided B remains open."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 1})
    m["strategy.entry"](["A", "long", 2.0])
    e.context.update({"close": 110.0, "open": 110.0, "high": 110.0, "low": 110.0, "bar_index": 1})
    m["strategy.entry"](["B", "long", 3.0])
    assert e._strategy_state.position_size == 5.0
    assert len(e._strategy_state.open_trades) == 2
    e.context.update({"close": 120.0, "open": 120.0, "high": 120.0, "low": 120.0, "bar_index": 2})
    m["strategy.exit"]([], {"id": "XA", "from_entry": "A"})
    st = e._strategy_state
    assert st.position_size == 3.0
    assert len(st.open_trades) == 1
    assert st.open_trades[0].entry_id == "B"
    assert st.open_trades[0].size == 3.0
    assert len(st.closed_trades) == 1
    assert st.closed_trades[0].entry_id == "A"
    # Exit placement event recorded (from_entry applied to fill, not event schema)
    exit_evs = [ev for ev in st._events if ev.kind == "exit"]
    assert exit_evs
    assert exit_evs[-1].id == "XA"
    assert exit_evs[-1].qty == 2.0


def test_strategy_exit_from_entry_unknown_soft_noop():
    """from_entry that matches no open leg is a soft no-op (no crash, no close)."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 4.0])
    m["strategy.exit"]([], {"id": "X", "from_entry": "NOPE"})
    st = e._strategy_state
    assert st.position_size == 4.0
    assert st.position_direction == "long"
    assert len(st.closed_trades) == 0
    assert not st.pending_orders
    assert any(ev.kind == "exit" for ev in st._events)


def test_strategy_exit_from_entry_pending_stop_limit():
    """Pending stop/limit exit with from_entry only reduces that entry's qty."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 1})
    m["strategy.entry"](["A", "long", 2.0])
    e.context.update({"close": 105.0, "open": 105.0, "high": 105.0, "low": 105.0, "bar_index": 1})
    m["strategy.entry"](["B", "long", 4.0])
    # Bracket only against A
    m["strategy.exit"](
        [],
        {"id": "XA", "from_entry": "A", "qty": 2.0, "limit": 120.0, "stop": 90.0},
    )
    assert e._strategy_state.position_size == 6.0
    pending = e._strategy_state.pending_orders
    assert any(k.startswith("XA") for k in pending)
    for po in pending.values():
        assert po.from_entry == "A"
        assert po.quantity == 2.0
    # TP fills A only
    e.context.update({"open": 100.0, "high": 125.0, "low": 99.0, "close": 122.0, "bar_index": 2})
    e.process_pending_orders(open_=100.0, high=125.0, low=99.0, close=122.0)
    st = e._strategy_state
    assert st.position_size == 4.0
    assert len(st.open_trades) == 1
    assert st.open_trades[0].entry_id == "B"
    assert st.closed_trades[-1].entry_id == "A"


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


def test_strategy_exit_qty_percent_partial_market():
    """qty_percent=50 closes half the open size (market exit)."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 10.0])
    m["strategy.exit"]([], {"id": "X", "from_entry": "L", "qty_percent": 50.0})
    st = e._strategy_state
    assert st.position_size == 5.0
    assert st.position_direction == "long"
    assert len(st.closed_trades) == 1
    assert st.closed_trades[0].size == 5.0
    exit_evs = [ev for ev in st._events if ev.kind == "exit"]
    assert exit_evs and exit_evs[-1].qty == 5.0


def test_strategy_exit_qty_percent_caps_over_100():
    """qty_percent > 100 is capped to full target size."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 4.0])
    m["strategy.exit"]([], {"id": "X", "qty_percent": 250.0})
    assert e._strategy_state.position_size == 0.0
    assert e._strategy_state.position_direction == "flat"


def test_strategy_exit_qty_percent_zero_noop_na_falls_back():
    """qty_percent 0 → soft no-op; na ignores percent (falls back to qty or full)."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 6.0])
    m["strategy.exit"]([], {"id": "X0", "qty_percent": 0.0})
    assert e._strategy_state.position_size == 6.0
    # na percent + explicit qty → use qty
    m["strategy.exit"]([], {"id": "Xna", "qty": 2.0, "qty_percent": float("nan")})
    assert e._strategy_state.position_size == 4.0


def test_strategy_exit_qty_percent_wins_over_qty():
    """When both qty and qty_percent set, percent wins (Pine-like)."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 10.0])
    # qty alone would close 1; percent 40 closes 4
    m["strategy.exit"]([], {"id": "X", "qty": 1.0, "qty_percent": 40.0})
    assert e._strategy_state.position_size == 6.0


def test_strategy_exit_qty_percent_respects_from_entry():
    """qty_percent is relative to from_entry open size, not whole position."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 1})
    m["strategy.entry"](["A", "long", 4.0])
    e.context.update({"close": 110.0, "open": 110.0, "high": 110.0, "low": 110.0, "bar_index": 1})
    m["strategy.entry"](["B", "long", 6.0])
    assert e._strategy_state.position_size == 10.0
    # 50% of A (4) → close 2; B untouched
    m["strategy.exit"]([], {"id": "XA", "from_entry": "A", "qty_percent": 50.0})
    st = e._strategy_state
    assert st.position_size == 8.0
    a_legs = [t for t in st.open_trades if t.entry_id == "A"]
    assert len(a_legs) == 1 and a_legs[0].size == 2.0
    b_legs = [t for t in st.open_trades if t.entry_id == "B"]
    assert len(b_legs) == 1 and b_legs[0].size == 6.0


def test_strategy_exit_trail_offset_long_ratchets_and_fills():
    """trail_offset (ticks) arms immediately; stop ratchets with high then fills on pullback."""
    e = NodeLiteralEvaluator()
    e._strategy_state.mintick = 0.01
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 2.0])
    # 100 ticks * 0.01 = $1 trail distance; no activation → active immediately
    m["strategy.exit"]([], {"id": "XT", "trail_offset": 100.0})
    pending = e._strategy_state.pending_orders
    assert "XT" in pending
    trail = pending["XT"]
    assert trail.is_trail
    assert trail.trail_offset == pytest.approx(1.0)
    # Favorable bar: high 110 → stop 109; low must stay above stop or OHLC fills same bar
    e.context.update({"open": 109.5, "high": 110.0, "low": 109.2, "close": 109.8, "bar_index": 1})
    e.process_pending_orders(open_=109.5, high=110.0, low=109.2, close=109.8)
    assert e._strategy_state.position_direction == "long"
    assert "XT" in e._strategy_state.pending_orders
    assert e._strategy_state.pending_orders["XT"].stop_price == pytest.approx(109.0)
    # Mild pullback still above stop — no fill; trail does not lower
    e.context.update({"open": 109.5, "high": 109.6, "low": 109.1, "close": 109.2, "bar_index": 2})
    e.process_pending_orders(open_=109.5, high=109.6, low=109.1, close=109.2)
    assert e._strategy_state.position_direction == "long"
    assert e._strategy_state.pending_orders["XT"].stop_price == pytest.approx(109.0)
    # Break stop
    e.context.update({"open": 109.2, "high": 109.3, "low": 108.0, "close": 108.5, "bar_index": 3})
    e.process_pending_orders(open_=109.2, high=109.3, low=108.0, close=108.5)
    assert e._strategy_state.position_direction == "flat"
    assert e._strategy_state.position_size == 0.0


def test_strategy_exit_trail_price_activation_long():
    """trail_price delays arming until high reaches activation; then trails."""
    e = NodeLiteralEvaluator()
    e._strategy_state.mintick = 1.0
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 1.0])
    # Activate at 110; trail 2 ticks (= $2 with mintick 1)
    m["strategy.exit"]([], {"id": "XT", "trail_price": 110.0, "trail_offset": 2.0})
    # Below activation — still open, stop not set (or not fillable)
    e.context.update({"open": 105.0, "high": 108.0, "low": 104.0, "close": 107.0, "bar_index": 1})
    e.process_pending_orders(open_=105.0, high=108.0, low=104.0, close=107.0)
    assert e._strategy_state.position_direction == "long"
    po = e._strategy_state.pending_orders["XT"]
    assert po.trail_active is False
    # Activate: high 112 → stop = 110; low 111 → no fill
    e.context.update({"open": 109.0, "high": 112.0, "low": 111.0, "close": 111.5, "bar_index": 2})
    e.process_pending_orders(open_=109.0, high=112.0, low=111.0, close=111.5)
    assert e._strategy_state.position_direction == "long"
    po = e._strategy_state.pending_orders["XT"]
    assert po.trail_active is True
    assert po.stop_price == pytest.approx(110.0)
    # Fill on pullback through 110
    e.context.update({"open": 111.0, "high": 111.0, "low": 109.0, "close": 109.5, "bar_index": 3})
    e.process_pending_orders(open_=111.0, high=111.0, low=109.0, close=109.5)
    assert e._strategy_state.position_direction == "flat"


def test_strategy_exit_trail_points_wins_over_offset():
    """When both set, trail_points is the tick distance (TV); wider offset is ignored."""
    e = NodeLiteralEvaluator()
    e._strategy_state.mintick = 0.01
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 2.0])
    # points=100 → $1; offset=500 would be $5 if it won
    m["strategy.exit"]([], {"id": "XT", "trail_points": 100.0, "trail_offset": 500.0})
    trail = e._strategy_state.pending_orders["XT"]
    assert trail.is_trail
    assert trail.trail_offset == pytest.approx(1.0)
    e.context.update({"open": 109.5, "high": 110.0, "low": 109.2, "close": 109.8, "bar_index": 1})
    e.process_pending_orders(open_=109.5, high=110.0, low=109.2, close=109.8)
    assert e._strategy_state.position_direction == "long"
    assert e._strategy_state.pending_orders["XT"].stop_price == pytest.approx(109.0)


def test_strategy_exit_trail_nonpositive_points_falls_back_to_offset():
    """na / ≤0 trail_points is ignored (not na→0) so a valid trail_offset still trails."""
    e = NodeLiteralEvaluator()
    e._strategy_state.mintick = 0.01
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 1.0])
    # 0 "wins" would disable trail and market-close; must fall back to offset=100
    m["strategy.exit"]([], {"id": "XT", "trail_points": 0.0, "trail_offset": 100.0})
    assert e._strategy_state.position_direction == "long"
    trail = e._strategy_state.pending_orders["XT"]
    assert trail.is_trail
    assert trail.trail_offset == pytest.approx(1.0)
    e2 = NodeLiteralEvaluator()
    e2._strategy_state.mintick = 0.01
    e2.context = dict(e.context)
    m2 = e2._build_builtin_map()
    m2["strategy.entry"](["L", "long", 1.0])
    m2["strategy.exit"]([], {"id": "XT", "trail_points": float("nan"), "trail_offset": 100.0})
    assert e2._strategy_state.pending_orders["XT"].trail_offset == pytest.approx(1.0)
    assert e2._strategy_state.position_direction == "long"


def test_strategy_exit_trail_offset_short_ratchets_and_fills():
    """Short trail: buy-stop ratchets down with low, then fills on a bounce."""
    e = NodeLiteralEvaluator()
    e._strategy_state.mintick = 0.01
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["S", "short", 2.0])
    m["strategy.exit"]([], {"id": "XT", "trail_offset": 100.0})
    trail = e._strategy_state.pending_orders["XT"]
    assert trail.is_trail
    assert trail.direction == "buy"
    assert trail.trail_offset == pytest.approx(1.0)
    # Favorable drop: low 90 → stop 91; high stays below stop
    e.context.update({"open": 90.5, "high": 90.8, "low": 90.0, "close": 90.2, "bar_index": 1})
    e.process_pending_orders(open_=90.5, high=90.8, low=90.0, close=90.2)
    assert e._strategy_state.position_direction == "short"
    assert e._strategy_state.pending_orders["XT"].stop_price == pytest.approx(91.0)
    # Mild bounce still below stop — no fill; trail does not raise
    e.context.update({"open": 90.5, "high": 90.9, "low": 90.4, "close": 90.8, "bar_index": 2})
    e.process_pending_orders(open_=90.5, high=90.9, low=90.4, close=90.8)
    assert e._strategy_state.position_direction == "short"
    assert e._strategy_state.pending_orders["XT"].stop_price == pytest.approx(91.0)
    # Break stop
    e.context.update({"open": 90.8, "high": 92.0, "low": 90.7, "close": 91.5, "bar_index": 3})
    e.process_pending_orders(open_=90.8, high=92.0, low=90.7, close=91.5)
    assert e._strategy_state.position_direction == "flat"
    assert e._strategy_state.position_size == 0.0
    assert e._strategy_state.closed_trades[0].exit_price == pytest.approx(91.0)


def _exit_eval(*, px: float = 100.0, mintick: float = 0.01):
    e = NodeLiteralEvaluator()
    e._strategy_state.mintick = mintick
    e.context = {
        "open": px,
        "high": px,
        "low": px,
        "close": px,
        "bar_index": 0,
        "time": 0,
        "syminfo": {"mintick": mintick},
    }
    return e, e._build_builtin_map()


def test_strategy_exit_profit_ticks_long_target():
    """profit=100 ticks from long entry 100 @ mintick 0.01 → limit 101.00."""
    e, m = _exit_eval()
    m["strategy.entry"](["L", "long", 1.0])
    m["strategy.exit"]([], {"id": "X", "profit": 100.0})
    assert e._strategy_state.position_size == 1.0
    pending = e._strategy_state.pending_orders
    assert "X" in pending
    assert pending["X"].order_type == "limit"
    assert pending["X"].limit_price == pytest.approx(101.00)
    # high 100.5 does not touch 101
    e.context.update({"open": 100.2, "high": 100.5, "low": 100.0, "close": 100.4, "bar_index": 1})
    e.process_pending_orders(open_=100.2, high=100.5, low=100.0, close=100.4)
    assert e._strategy_state.position_size == 1.0
    # high 101.5 fills at 101
    e.context.update({"open": 100.4, "high": 101.5, "low": 100.2, "close": 101.2, "bar_index": 2})
    e.process_pending_orders(open_=100.4, high=101.5, low=100.2, close=101.2)
    assert e._strategy_state.position_size == 0.0
    assert e._strategy_state.closed_trades[0].exit_price == pytest.approx(101.00)


def test_strategy_exit_loss_ticks_long_stop():
    """loss=50 ticks from long entry 100 @ mintick 0.01 → stop 99.50."""
    e, m = _exit_eval()
    m["strategy.entry"](["L", "long", 1.0])
    m["strategy.exit"]([], {"id": "X", "loss": 50.0})
    po = e._strategy_state.pending_orders["X"]
    assert po.order_type == "stop"
    assert po.stop_price == pytest.approx(99.50)
    e.context.update({"open": 100.0, "high": 100.2, "low": 99.6, "close": 99.8, "bar_index": 1})
    e.process_pending_orders(open_=100.0, high=100.2, low=99.6, close=99.8)
    assert e._strategy_state.position_size == 1.0
    e.context.update({"open": 99.8, "high": 99.9, "low": 99.0, "close": 99.2, "bar_index": 2})
    e.process_pending_orders(open_=99.8, high=99.9, low=99.0, close=99.2)
    assert e._strategy_state.position_size == 0.0
    assert e._strategy_state.closed_trades[0].exit_price == pytest.approx(99.50)


def test_strategy_exit_profit_ticks_short_target():
    """profit=100 ticks from short entry 100 @ mintick 0.01 → limit 99.00."""
    e, m = _exit_eval()
    m["strategy.entry"](["S", "short", 1.0])
    m["strategy.exit"]([], {"id": "X", "profit": 100.0})
    po = e._strategy_state.pending_orders["X"]
    assert po.order_type == "limit"
    assert po.limit_price == pytest.approx(99.00)
    e.context.update({"open": 100.0, "high": 100.2, "low": 99.4, "close": 99.6, "bar_index": 1})
    e.process_pending_orders(open_=100.0, high=100.2, low=99.4, close=99.6)
    assert e._strategy_state.position_size == 1.0
    e.context.update({"open": 99.6, "high": 99.7, "low": 98.5, "close": 98.8, "bar_index": 2})
    e.process_pending_orders(open_=99.6, high=99.7, low=98.5, close=98.8)
    assert e._strategy_state.position_size == 0.0
    assert e._strategy_state.closed_trades[0].exit_price == pytest.approx(99.00)


def test_strategy_exit_limit_stop_remain_absolute_prices():
    """Named limit/stop stay prices; profit/loss do not rewrite them."""
    e, m = _exit_eval()
    m["strategy.entry"](["L", "long", 1.0])
    m["strategy.exit"]([], {"id": "X", "limit": 110.0, "stop": 90.0, "profit": 100.0, "loss": 50.0})
    pending = e._strategy_state.pending_orders
    lim = pending["X:limit"]
    stp = pending["X:stop"]
    assert lim.limit_price == pytest.approx(110.0)
    assert stp.stop_price == pytest.approx(90.0)


def test_strategy_exit_profit_loss_na_and_nonpositive_ignored():
    """na / None / <=0 profit or loss do not place that bracket (no na→0)."""
    e, m = _exit_eval()
    m["strategy.entry"](["L", "long", 2.0])
    m["strategy.exit"]([], {"id": "X0", "profit": 0.0, "loss": -10.0})
    # No levels → market close
    assert e._strategy_state.position_size == 0.0
    e, m = _exit_eval()
    m["strategy.entry"](["L", "long", 2.0])
    m["strategy.exit"]([], {"id": "Xna", "profit": float("nan"), "loss": None, "limit": 110.0})
    assert e._strategy_state.position_size == 2.0
    po = e._strategy_state.pending_orders["Xna"]
    assert po.order_type == "limit"
    assert po.limit_price == pytest.approx(110.0)
    assert po.stop_price is None


def test_strategy_exit_profit_from_entry_uses_that_leg_avg():
    """from_entry profit ticks are measured from that leg's entry, not the VWAP."""
    e, m = _exit_eval()
    m["strategy"](["T"], {"pyramiding": 1})
    m["strategy.entry"](["A", "long", 1.0])
    e.context.update({"open": 110.0, "high": 110.0, "low": 110.0, "close": 110.0, "bar_index": 1})
    m["strategy.entry"](["B", "long", 1.0])
    # Drop back below A's 101 target so the bracket stays pending
    e.context.update({"open": 100.5, "high": 100.8, "low": 100.2, "close": 100.4, "bar_index": 2})
    m["strategy.exit"]([], {"id": "XA", "from_entry": "A", "profit": 100.0})
    po = next(p for p in e._strategy_state.pending_orders.values() if p.from_entry == "A")
    assert po.limit_price == pytest.approx(101.00)
    assert e._strategy_state.position_size == 2.0


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
