# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
