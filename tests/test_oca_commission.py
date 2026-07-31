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

"""OCA groups, commission, and slippage broker settings."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator


def test_oca_constants_resolve():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    assert m["strategy.oca.reduce"]([]) == "reduce"
    assert m["strategy.oca.cancel"]([]) == "cancel"
    assert m["strategy.oca.none"]([]) == "none"
    assert m["strategy.commission.percent"]([]) == "percent"


def test_oca_reduce_cancels_sibling_on_full_fill():
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 10.0])
    # TP limit sell + SL stop sell in same OCA reduce group
    m["strategy.order"](
        [],
        {
            "id": "TP",
            "direction": "short",
            "qty": 10.0,
            "limit": 110.0,
            "oca_name": "TPSL",
            "oca_type": "reduce",
        },
    )
    m["strategy.order"](
        [],
        {
            "id": "SL",
            "direction": "short",
            "qty": 10.0,
            "stop": 95.0,
            "oca_name": "TPSL",
            "oca_type": "reduce",
        },
    )
    assert set(e._strategy_state.pending_orders) == {"TP", "SL"}
    # High touches TP
    e.process_pending_orders(open_=100.0, high=111.0, low=100.0, close=108.0)
    assert e._strategy_state.position_direction == "flat"
    # SL should be gone via OCA reduce (full fill)
    assert "SL" not in e._strategy_state.pending_orders
    assert "TP" not in e._strategy_state.pending_orders


def test_commission_percent_on_entry():
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    # 1% commission on notional
    m["strategy"](["T"], {"commission_type": "percent", "commission_value": 1.0})
    m["strategy.entry"](["L", "long", 10.0])
    # 10 * 100 * 1% = 10
    assert e._strategy_state.open_trades[0].commission == 10.0
    assert e._strategy_state.commission == 10.0


def test_slippage_ticks_worsens_entry():
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0, "syminfo": type("S", (), {"mintick": 0.25})()}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"slippage": 2})  # 2 ticks * 0.25 = 0.5
    m["strategy.entry"](["L", "long", 1.0])
    assert e._strategy_state.entry_price == 100.5


def test_strategy_declaration_sets_initial_capital():
    e = NodeLiteralEvaluator()
    m = e._build_builtin_map()
    m["strategy"](["Cap"], {"initial_capital": 50_000})
    assert e._strategy_state.initial_capital == 50_000


def test_greedy_oca_positional_args_parse():
    """Mirrors greedy_strategy.pine order arg layout."""
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 5.0])
    # strategy.order(id, dir, qty, limit, stop, oca_name, oca_type, comment)
    m["strategy.order"](["TP", "short", 5.0, 110.0, None, "TPSL", "reduce", "TPSL"])
    m["strategy.order"](["SL", "short", 5.0, None, 95.0, "TPSL", "reduce", "TPSL"])
    assert e._strategy_state.pending_orders["TP"].oca_name == "TPSL"
    assert e._strategy_state.pending_orders["TP"].oca_type == "reduce"
    assert e._strategy_state.pending_orders["SL"].oca_type == "reduce"


def test_compile_entry_commission_matches_interpret():
    """Both paths: entry commission (open drag) + exit commission on close."""
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    # Interpret oracle
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0, "open": 100.0, "high": 100.0, "low": 100.0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"commission_type": "percent", "commission_value": 1.0, "initial_capital": 100_000})
    m["strategy.entry"](["L", "long", 10.0])
    assert e._strategy_state.equity(100.0) == 99_990.0  # openprofit = -entry commission
    e.context["close"] = 110.0
    m["strategy.close"](["L"])
    i_net = e._strategy_state.netprofit()
    # (110-100)*10 - entry 10 - exit 11 = 79
    assert i_net == 79.0

    # Compile path
    b = CompileStrategyBroker(initial_capital=100_000, commission_value=1.0, commission_type="percent")
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.entry("L", "long", 10.0)
    assert b.equity == 99_990.0
    b.begin_bar(1, 110.0, 110.0, 110.0, 110.0)
    b.close("L")
    assert b.netprofit == i_net
    assert b.equity == 100_000.0 + i_net


def test_exit_slippage_worsens_close_both_paths():
    """Close fills slip against the trader on interpret and compile."""
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    e = NodeLiteralEvaluator()
    e.context = {
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
        "syminfo": type("S", (), {"mintick": 0.25})(),
    }
    m = e._build_builtin_map()
    m["strategy"](["T"], {"slippage": 2})  # 0.5
    m["strategy.entry"](["L", "long", 1.0])
    assert e._strategy_state.entry_price == 100.5
    e.context["close"] = 110.0
    m["strategy.close"](["L"])
    # exit at 110 - 0.5 = 109.5; profit = 109.5 - 100.5 = 9.0
    assert e._strategy_state.netprofit() == 9.0
    assert e._strategy_state.closed_trades[0].exit_price == 109.5

    b = CompileStrategyBroker(slippage_ticks=2, mintick=0.25)
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.entry("L", "long", 1.0)
    assert b.position_avg_price == 100.5
    b.begin_bar(1, 110.0, 110.0, 110.0, 110.0)
    b.close("L")
    assert b.netprofit == 9.0


def test_invalid_qty_and_direction_do_not_fill():
    """Bad order args emit diagnostic events; no silent 1.0 / NaN fills."""
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", "not_a_number"])
    assert e._strategy_state.position_size == 0.0
    assert any(ev.comment == "invalid_qty" for ev in e._strategy_state._events)

    m["strategy.entry"](["L2", "sideways", 1.0])
    assert e._strategy_state.position_size == 0.0
    assert any(ev.comment == "invalid_direction" for ev in e._strategy_state._events)

    m["strategy.entry"](["L3", "long", float("nan")])
    assert e._strategy_state.position_size == 0.0
    assert e._strategy_state.position_size == e._strategy_state.position_size  # not NaN

    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    b = CompileStrategyBroker()
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.entry("X", "long", "bad")
    assert b.position_size == 0.0
    assert any(ev.get("comment") == "invalid_qty" for ev in b.events)
    b.entry("Y", "diagonal", 1.0)
    assert b.position_size == 0.0
    assert any(ev.get("comment") == "invalid_direction" for ev in b.events)


def test_compile_pyramiding_matches_interpret():
    """Compile broker must honor strategy() pyramiding like interpret market path."""
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"pyramiding": 1})
    m["strategy.entry"](["L1", "long", 1.0])
    m["strategy.entry"](["L2", "long", 2.0])
    m["strategy.entry"](["L3", "long", 1.0])
    assert e._strategy_state.position_size == 3.0
    assert len(e._strategy_state.open_trades) == 2

    b = CompileStrategyBroker(pyramiding=1)
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.entry("L1", "long", 1.0)
    b.entry("L2", "long", 2.0)
    b.entry("L3", "long", 1.0)
    assert b.position_size == 3.0
    assert b.open_entry_count == 2

    b0 = CompileStrategyBroker(pyramiding=0)
    b0.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b0.entry("L1", "long", 1.0)
    b0.entry("L2", "long", 5.0)
    assert b0.position_size == 1.0
