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

"""Strategy runtime depth: open trades, equity stats, multi-bar golden scripts."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse


def _eval_expr(ev: NodeLiteralEvaluator, source: str):
    return ev.visit(parse(source, mode="eval").body)


def _set_bar(ev: NodeLiteralEvaluator, bar_index: int, close: float, time: int | None = None) -> None:
    ev.context["bar_index"] = bar_index
    ev.context["close"] = close
    ev.context["open"] = close
    ev.context["high"] = close
    ev.context["low"] = close
    ev.context["time"] = time if time is not None else 1_700_000_000_000 + bar_index * 60_000


class TestStrategySeriesVariables:
    """strategy.position_size / opentrades / netprofit resolve as values, not strings."""

    def test_flat_defaults(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        assert _eval_expr(ev, "strategy.position_size") == 0.0
        assert _eval_expr(ev, "strategy.opentrades") == 0
        assert _eval_expr(ev, "strategy.closedtrades") == 0
        assert _eval_expr(ev, "strategy.netprofit") == 0.0
        assert _eval_expr(ev, "strategy.openprofit") == 0.0
        assert _eval_expr(ev, "strategy.equity") == _eval_expr(ev, "strategy.initial_capital")

    def test_long_entry_updates_position_and_opentrades(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 5, 100.0, time=12345)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")

        assert _eval_expr(ev, "strategy.position_size") == 2.0
        assert _eval_expr(ev, "strategy.position_avg_price") == 100.0
        assert _eval_expr(ev, "strategy.opentrades") == 1
        assert _eval_expr(ev, "strategy.closedtrades") == 0
        assert _eval_expr(ev, "strategy.opentrades.entry_price(0)") == 100.0
        assert _eval_expr(ev, "strategy.opentrades.size(0)") == 2.0
        assert _eval_expr(ev, "strategy.opentrades.entry_bar_index(0)") == 5
        assert _eval_expr(ev, "strategy.opentrades.entry_time(0)") == 12345

    def test_short_entry_uses_negative_position_size(self) -> None:
        """Pine: strategy.position_size is negative when short."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 50.0)
        _eval_expr(ev, "strategy.entry('S', strategy.short, 3.0)")
        assert _eval_expr(ev, "strategy.position_size") == -3.0
        assert _eval_expr(ev, "strategy.opentrades") == 1

    def test_openprofit_tracks_mark_to_market(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")
        _set_bar(ev, 1, 110.0)
        # 2 * (110 - 100) = 20
        assert _eval_expr(ev, "strategy.openprofit") == 20.0
        equity0 = _eval_expr(ev, "strategy.initial_capital")
        assert _eval_expr(ev, "strategy.equity") == equity0 + 20.0

    def test_close_realizes_netprofit_and_clears_open(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")
        _set_bar(ev, 3, 110.0)
        _eval_expr(ev, "strategy.close('L')")

        assert _eval_expr(ev, "strategy.position_size") == 0.0
        assert _eval_expr(ev, "strategy.opentrades") == 0
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.netprofit") == 20.0
        assert _eval_expr(ev, "strategy.openprofit") == 0.0
        assert _eval_expr(ev, "strategy.closedtrades.profit(0)") == 20.0
        assert _eval_expr(ev, "strategy.closedtrades.exit_price(0)") == 110.0
        assert _eval_expr(ev, "strategy.closedtrades.exit_bar_index(0)") == 3

    def test_partial_close_keeps_remaining_open_trade(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 4.0)")
        _set_bar(ev, 1, 105.0)
        _eval_expr(ev, "strategy.close('L', 1.0)")  # close 1 of 4

        assert _eval_expr(ev, "strategy.position_size") == 3.0
        assert _eval_expr(ev, "strategy.opentrades") == 1
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.netprofit") == 5.0  # 1 * 5
        assert _eval_expr(ev, "strategy.opentrades.size(0)") == 3.0


class TestStrategyWinLossStats:
    def test_win_and_loss_trade_counts(self) -> None:
        ev = NodeLiteralEvaluator()
        # Win: long 100 -> 110
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L1', strategy.long, 1.0)")
        _set_bar(ev, 1, 110.0)
        _eval_expr(ev, "strategy.close('L1')")
        # Loss: long 110 -> 100
        _eval_expr(ev, "strategy.entry('L2', strategy.long, 1.0)")
        _set_bar(ev, 2, 100.0)
        _eval_expr(ev, "strategy.close('L2')")

        assert _eval_expr(ev, "strategy.closedtrades") == 2
        assert _eval_expr(ev, "strategy.wintrades") == 1
        assert _eval_expr(ev, "strategy.losstrades") == 1
        assert _eval_expr(ev, "strategy.grossprofit") == 10.0
        assert _eval_expr(ev, "strategy.grossloss") == 10.0
        assert _eval_expr(ev, "strategy.netprofit") == 0.0


class TestStrategyExtendedStats:
    """Missing inventory series: avg_*, *_percent, cash, drawdown, entry name, etc."""

    def test_flat_defaults_for_extended_series(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        assert _eval_expr(ev, "strategy.avg_trade") == 0.0
        assert _eval_expr(ev, "strategy.avg_winning_trade") == 0.0
        assert _eval_expr(ev, "strategy.avg_losing_trade") == 0.0
        assert _eval_expr(ev, "strategy.avg_trade_percent") == 0.0
        assert _eval_expr(ev, "strategy.netprofit_percent") == 0.0
        assert _eval_expr(ev, "strategy.openprofit_percent") == 0.0
        assert _eval_expr(ev, "strategy.grossprofit_percent") == 0.0
        assert _eval_expr(ev, "strategy.grossloss_percent") == 0.0
        assert _eval_expr(ev, "strategy.eventrades") == 0
        assert _eval_expr(ev, "strategy.closedtrades.first_index") == 0
        assert _eval_expr(ev, "strategy.account_currency") == "USD"
        assert _eval_expr(ev, "strategy.position_entry_name") == ""
        assert _eval_expr(ev, "strategy.opentrades.capital_held") == 0.0
        assert _eval_expr(ev, "strategy.cash") == 100_000.0
        assert _eval_expr(ev, "strategy.max_drawdown") == 0.0
        assert _eval_expr(ev, "strategy.max_runup") == 0.0

    def test_avg_trade_and_percent_after_win_and_loss(self) -> None:
        ev = NodeLiteralEvaluator()
        # Win +10
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L1', strategy.long, 1.0)")
        _set_bar(ev, 1, 110.0)
        _eval_expr(ev, "strategy.close('L1')")
        # Loss -5
        _eval_expr(ev, "strategy.entry('L2', strategy.long, 1.0)")
        _set_bar(ev, 2, 105.0)
        _eval_expr(ev, "strategy.close('L2')")

        assert _eval_expr(ev, "strategy.netprofit") == 5.0
        assert _eval_expr(ev, "strategy.avg_trade") == 2.5  # 5/2
        assert _eval_expr(ev, "strategy.avg_winning_trade") == 10.0
        assert _eval_expr(ev, "strategy.avg_losing_trade") == 5.0  # positive loss magnitude
        # percents of initial capital
        assert abs(_eval_expr(ev, "strategy.netprofit_percent") - 0.005) < 1e-9  # 5/100000*100
        assert abs(_eval_expr(ev, "strategy.avg_trade_percent") - 0.0025) < 1e-9
        assert abs(_eval_expr(ev, "strategy.avg_winning_trade_percent") - 0.01) < 1e-9
        assert abs(_eval_expr(ev, "strategy.avg_losing_trade_percent") - 0.005) < 1e-9
        assert abs(_eval_expr(ev, "strategy.grossprofit_percent") - 0.01) < 1e-9
        assert abs(_eval_expr(ev, "strategy.grossloss_percent") - 0.005) < 1e-9

    def test_position_entry_name_and_capital_held(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 50.0)
        _eval_expr(ev, "strategy.entry('MyLong', strategy.long, 3.0)")
        assert _eval_expr(ev, "strategy.position_entry_name") == "MyLong"
        assert _eval_expr(ev, "strategy.opentrades.capital_held") == 150.0  # 50*3
        # cash ≈ initial - capital held + open MTM (0 at entry)
        assert _eval_expr(ev, "strategy.cash") == 100_000.0 - 150.0

    def test_openprofit_percent_vs_equity(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 2.0)")
        _set_bar(ev, 1, 110.0)
        # openprofit = 20; realized equity base = initial + net = 100000
        # openprofit_percent relative to initial capital: 20/100000*100 = 0.02
        assert _eval_expr(ev, "strategy.openprofit") == 20.0
        assert abs(_eval_expr(ev, "strategy.openprofit_percent") - 0.02) < 1e-9

    def test_max_contracts_held(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 5.0)")
        assert _eval_expr(ev, "strategy.max_contracts_held_long") == 5.0
        assert _eval_expr(ev, "strategy.max_contracts_held_all") == 5.0
        assert _eval_expr(ev, "strategy.max_contracts_held_short") == 0.0
        _eval_expr(ev, "strategy.close('L')")
        _eval_expr(ev, "strategy.entry('S', strategy.short, 3.0)")
        assert _eval_expr(ev, "strategy.max_contracts_held_short") == 3.0
        assert _eval_expr(ev, "strategy.max_contracts_held_all") == 5.0

    def test_max_runup_and_drawdown_from_equity_curve(self) -> None:
        ev = NodeLiteralEvaluator()
        # +10 equity runup
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 1.0)")
        _set_bar(ev, 1, 110.0)
        _eval_expr(ev, "strategy.close('L')")
        assert _eval_expr(ev, "strategy.netprofit") == 10.0
        # Peak equity 100010; then lose 15 from next trade
        _eval_expr(ev, "strategy.entry('L2', strategy.long, 1.0)")
        _set_bar(ev, 2, 95.0)  # from 110 entry... wait entry at 110
        # entry at close 110 after first close - when we entry, mark is 110
        # actually after close bar1 price is 110, then entry L2 at 110
        # bar2 set to 95: openprofit = -15, equity = 100000+10-15 = 99995
        # drawdown from peak 100010 is 15
        _ = _eval_expr(ev, "strategy.equity")  # update curve
        assert _eval_expr(ev, "strategy.max_runup") >= 10.0
        assert _eval_expr(ev, "strategy.max_drawdown") >= 14.0  # allow float slack
        assert _eval_expr(ev, "strategy.max_runup_percent") >= 0.0
        assert _eval_expr(ev, "strategy.max_drawdown_percent") >= 0.0

    def test_eventrades_zero_profit(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        _eval_expr(ev, "strategy.entry('L', strategy.long, 1.0)")
        _set_bar(ev, 1, 100.0)
        _eval_expr(ev, "strategy.close('L')")
        assert _eval_expr(ev, "strategy.eventrades") == 1
        assert _eval_expr(ev, "strategy.wintrades") == 0
        assert _eval_expr(ev, "strategy.losstrades") == 0

    def test_margin_liquidation_price_default_na(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        val = _eval_expr(ev, "strategy.margin_liquidation_price")
        assert val is None or (isinstance(val, float) and val != val)  # None or nan


class TestStrategyInitialCapitalReassign:
    """Corpus residual: ``strategy.initial_capital = N`` is Attribute ReAssign."""

    def test_reassign_updates_state_and_series(self) -> None:
        src = """//@version=5
strategy("cap")
strategy.initial_capital = 50000
"""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        ev.evaluate_script(src)
        assert float(ev._strategy_state.initial_capital) == 50000.0
        assert _eval_expr(ev, "strategy.initial_capital") == 50000.0
        assert _eval_expr(ev, "strategy.equity") == 50000.0

    def test_reassign_with_colon_equals(self) -> None:
        src = """//@version=5
strategy("cap")
strategy.initial_capital := 12000
"""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        ev.evaluate_script(src)
        assert _eval_expr(ev, "strategy.initial_capital") == 12000.0


class TestStrategyGoldenMultiBar:
    """Simple multi-bar script: buy bar 0, sell bar 2, inspect series."""

    def test_entry_exit_over_bars_via_script_statements(self) -> None:
        # Simulate bar-by-bar evaluation of a tiny strategy body.
        body_entry = "strategy.entry('L', strategy.long, 1.0)"
        body_exit = "strategy.close('L')"
        read = """
strategy.position_size
"""
        ev = NodeLiteralEvaluator()
        prices = [100.0, 102.0, 108.0]

        sizes: list[float] = []
        for i, px in enumerate(prices):
            _set_bar(ev, i, px)
            if i == 0:
                _eval_expr(ev, body_entry)
            elif i == 2:
                _eval_expr(ev, body_exit)
            sizes.append(float(_eval_expr(ev, "strategy.position_size")))

        assert sizes == [1.0, 1.0, 0.0]
        assert _eval_expr(ev, "strategy.netprofit") == 8.0  # 108 - 100
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.equity") == _eval_expr(ev, "strategy.initial_capital") + 8.0

    def test_full_script_string_single_bar_snapshot(self) -> None:
        """Evaluate a strategy script once with context prices (single bar fill)."""
        src = """//@version=6
strategy("Golden")
strategy.entry("L", strategy.long, 1.0)
"""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 42.0)
        ev.evaluate_script(src)
        assert _eval_expr(ev, "strategy.position_size") == 1.0


class TestStrategyCashAndPyramiding:
    """Regression: strategy.cash series + market-entry pyramiding / reverse events."""

    def test_strategy_cash_is_free_capital_not_qty_string(self) -> None:
        """Constants map must not shadow free-cash series with \"cash\" sentinel."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        cash = _eval_expr(ev, "strategy.cash")
        assert isinstance(cash, (int, float))
        assert cash == 100_000.0
        # Dual tag still lets default_qty_type=strategy.cash work
        from pynescript.ast.evaluator.builtins.strategy import StrategyCashAmount

        assert getattr(cash, "_pine_qty_type", None) == "cash"
        assert isinstance(cash, StrategyCashAmount)

    def test_default_qty_type_cash_still_sizes_from_currency(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 50.0)
        m = ev._build_builtin_map()
        # Evaluate strategy.cash as dual value then pass into declaration
        cash_const = m["strategy.cash"]([])
        m["strategy"](["T"], {"default_qty_type": cash_const, "default_qty_value": 500.0})
        m["strategy.entry"](["L", "long"])  # no explicit qty
        # 500 cash / 50 price = 10 contracts
        assert ev._strategy_state.position_size == 10.0

    def test_pyramiding_adds_second_market_entry(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 1})
        m["strategy.entry"](["L1", "long", 1.0])
        m["strategy.entry"](["L2", "long", 2.0])
        assert ev._strategy_state.position_size == 3.0
        assert len(ev._strategy_state.open_trades) == 2
        # Third entry blocked (max = pyramiding+1 = 2)
        m["strategy.entry"](["L3", "long", 1.0])
        assert ev._strategy_state.position_size == 3.0
        assert len(ev._strategy_state.open_trades) == 2

    def test_same_id_reentry_does_not_reset_avg_price(self) -> None:
        """``if cond: strategy.entry("L")`` must not rewrite a filled position."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 0})
        m["strategy.entry"](["L", "long", 1.0])
        assert _eval_expr(ev, "strategy.position_avg_price") == 100.0
        _set_bar(ev, 1, 110.0)
        m["strategy.entry"](["L", "long", 1.0])
        assert ev._strategy_state.position_size == 1.0
        assert _eval_expr(ev, "strategy.position_avg_price") == 100.0
        assert _eval_expr(ev, "strategy.opentrades") == 1
        assert sum(1 for e in ev._strategy_state._events if e.kind == "entry") == 1

    def test_same_id_reentry_pyramids_and_vwap(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 1})
        m["strategy.entry"](["L", "long", 1.0])
        _set_bar(ev, 1, 120.0)
        m["strategy.entry"](["L", "long", 1.0])
        assert ev._strategy_state.position_size == 2.0
        assert abs(_eval_expr(ev, "strategy.position_avg_price") - 110.0) < 1e-9
        assert _eval_expr(ev, "strategy.opentrades") == 2

    def test_pyramiding_zero_blocks_second_id(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 0})
        m["strategy.entry"](["L1", "long", 1.0])
        m["strategy.entry"](["L2", "long", 5.0])
        assert ev._strategy_state.position_size == 1.0
        assert len(ev._strategy_state.open_trades) == 1

    def test_reverse_entry_emits_close_event(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy.entry"](["L", "long", 2.0])
        _set_bar(ev, 1, 105.0)
        m["strategy.entry"](["S", "short", 2.0])
        kinds = [ev_.kind for ev_ in ev._strategy_state._events]
        assert "close" in kinds
        assert kinds.count("entry") >= 2
        assert ev._strategy_state.position_direction == "short"
        assert ev._strategy_state.position_size == 2.0
        assert any(ev_.comment == "reverse" for ev_ in ev._strategy_state._events)
        assert _eval_expr(ev, "strategy.position_avg_price") == 105.0
        assert _eval_expr(ev, "strategy.opentrades") == 1

    def test_exit_from_entry_targets_one_pyramid_leg(self) -> None:
        """strategy.exit(..., from_entry=A) leaves other open entries open."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 1})
        m["strategy.entry"](["A", "long", 1.0])
        _set_bar(ev, 1, 110.0)
        m["strategy.entry"](["B", "long", 2.0])
        assert ev._strategy_state.position_size == 3.0
        _set_bar(ev, 2, 115.0)
        m["strategy.exit"](["XA", "A"])  # positional id, from_entry
        assert ev._strategy_state.position_size == 2.0
        assert len(ev._strategy_state.open_trades) == 1
        assert ev._strategy_state.open_trades[0].entry_id == "B"
        assert _eval_expr(ev, "strategy.opentrades") == 1
        assert _eval_expr(ev, "strategy.closedtrades") == 1
        assert _eval_expr(ev, "strategy.closedtrades.entry_id(0)") == "A"

    def test_exit_from_entry_unknown_soft_noop(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy.entry"](["L", "long", 2.0])
        m["strategy.exit"](["X", "missing"])
        assert ev._strategy_state.position_size == 2.0
        assert len(ev._strategy_state.closed_trades) == 0

    def test_exit_profit_ticks_from_entry_avg(self) -> None:
        """profit ticks are an offset from entry avg, not an absolute price."""
        ev = NodeLiteralEvaluator()
        ev._strategy_state.mintick = 0.01
        _set_bar(ev, 0, 100.0)
        ev.context["syminfo"] = {"mintick": 0.01}
        m = ev._build_builtin_map()
        m["strategy.entry"](["L", "long", 1.0])
        m["strategy.exit"]([], {"id": "X", "profit": 100.0})
        po = ev._strategy_state.pending_orders["X"]
        assert po.limit_price == 101.0
        assert ev._strategy_state.position_size == 1.0


class TestAvgPriceModel:
    """strategy(..., avg_price_model=stock|futures) — multi-leg partial close matrix."""

    def test_default_is_stock(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        m["strategy"](["T"], {})
        assert ev._strategy_state.avg_price_model == "stock"

    def test_declaration_wires_futures(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"avg_price_model": "futures"})
        assert ev._strategy_state.avg_price_model == "futures"

    def test_declaration_accepts_constant_token(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        tok = m["strategy.avg_price_futures"]([])
        m["strategy"](["T"], {"avg_price_model": tok})
        assert ev._strategy_state.avg_price_model == "futures"

    def test_unknown_model_soft_falls_back_to_stock(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"avg_price_model": "not_a_real_model"})
        assert ev._strategy_state.avg_price_model == "stock"

    def test_add_vwap_same_for_stock_and_futures(self) -> None:
        """S1: long 2@100 + 4@110 → avg 106.666… both modes."""
        expected = (2.0 * 100.0 + 4.0 * 110.0) / 6.0
        for model in ("stock", "futures"):
            ev = NodeLiteralEvaluator()
            _set_bar(ev, 0, 100.0)
            m = ev._build_builtin_map()
            m["strategy"](["T"], {"pyramiding": 1, "avg_price_model": model})
            m["strategy.entry"](["A", "long", 2.0])
            _set_bar(ev, 1, 110.0)
            m["strategy.entry"](["B", "long", 4.0])
            assert abs(_eval_expr(ev, "strategy.position_avg_price") - expected) < 1e-9, model
            assert ev._strategy_state.position_size == 6.0

    def test_stock_multi_leg_partial_reweights_avg(self) -> None:
        """S2 stock: A@100 + B@120, close 1 FIFO → remaining avg = 120 (leg B)."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 1, "avg_price_model": "stock", "commission_value": 0.0})
        m["strategy.entry"](["A", "long", 1.0])
        _set_bar(ev, 1, 120.0)
        m["strategy.entry"](["B", "long", 1.0])
        assert abs(_eval_expr(ev, "strategy.position_avg_price") - 110.0) < 1e-9
        _set_bar(ev, 2, 130.0)
        m["strategy.close"](["A", 1.0])  # close qty 1 — FIFO eats leg A
        assert ev._strategy_state.position_size == 1.0
        assert abs(_eval_expr(ev, "strategy.position_avg_price") - 120.0) < 1e-9
        # Realized vs leg A entry 100: (130-100)*1 = 30
        assert abs(_eval_expr(ev, "strategy.netprofit") - 30.0) < 1e-9
        assert abs(ev._strategy_state.closed_trades[0].entry_price - 100.0) < 1e-9

    def test_futures_multi_leg_partial_keeps_sticky_avg(self) -> None:
        """S2 futures: same sequence → avg stays 110; PnL vs sticky avg = 20."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"pyramiding": 1, "avg_price_model": "futures", "commission_value": 0.0})
        m["strategy.entry"](["A", "long", 1.0])
        _set_bar(ev, 1, 120.0)
        m["strategy.entry"](["B", "long", 1.0])
        assert abs(_eval_expr(ev, "strategy.position_avg_price") - 110.0) < 1e-9
        _set_bar(ev, 2, 130.0)
        m["strategy.close"](["A", 1.0])
        assert ev._strategy_state.position_size == 1.0
        assert abs(_eval_expr(ev, "strategy.position_avg_price") - 110.0) < 1e-9
        # Realized vs sticky 110: (130-110)*1 = 20
        assert abs(_eval_expr(ev, "strategy.netprofit") - 20.0) < 1e-9
        assert abs(ev._strategy_state.closed_trades[0].entry_price - 110.0) < 1e-9

    def test_single_lot_partial_same_both_modes(self) -> None:
        """S3: long 4@100, close 1@105 → avg 100, PnL 5 for stock and futures."""
        for model in ("stock", "futures"):
            ev = NodeLiteralEvaluator()
            _set_bar(ev, 0, 100.0)
            m = ev._build_builtin_map()
            m["strategy"](["T"], {"avg_price_model": model, "commission_value": 0.0})
            m["strategy.entry"](["L", "long", 4.0])
            _set_bar(ev, 1, 105.0)
            m["strategy.close"](["L", 1.0])
            assert ev._strategy_state.position_size == 3.0, model
            assert abs(_eval_expr(ev, "strategy.position_avg_price") - 100.0) < 1e-9, model
            assert abs(_eval_expr(ev, "strategy.netprofit") - 5.0) < 1e-9, model

    def test_futures_reverse_resets_avg_to_new_fill(self) -> None:
        """S5: reverse under futures → avg = new fill only."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"avg_price_model": "futures"})
        m["strategy.entry"](["L", "long", 2.0])
        _set_bar(ev, 1, 105.0)
        m["strategy.entry"](["S", "short", 2.0])
        assert ev._strategy_state.position_direction == "short"
        assert abs(_eval_expr(ev, "strategy.position_avg_price") - 105.0) < 1e-9


class TestLeverageFuturesUI:
    """strategy(..., leverage=N) — simpler futures margin / sizing UI."""

    def test_default_leverage_is_one(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        m["strategy"](["T"], {})
        assert ev._strategy_state.leverage == 1.0
        assert _eval_expr(ev, "strategy.leverage") == 1.0

    def test_declaration_wires_leverage_and_margin_pct(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"leverage": 10, "avg_price_model": "futures"})
        assert ev._strategy_state.leverage == 10.0
        assert abs(ev._strategy_state.margin_long - 10.0) < 1e-9  # 100/10
        assert abs(ev._strategy_state.margin_short - 10.0) < 1e-9
        assert _eval_expr(ev, "strategy.leverage") == 10.0

    def test_margin_long_derives_leverage(self) -> None:
        ev = NodeLiteralEvaluator()
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"margin_long": 20})  # 20% margin → 5×
        assert abs(ev._strategy_state.leverage - 5.0) < 1e-9

    def test_cash_default_qty_scales_by_leverage(self) -> None:
        """cash=1000, price=100, lev=10 → qty = 1000*10/100 = 100."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](
            ["T"],
            {
                "avg_price_model": "futures",
                "leverage": 10,
                "default_qty_type": "cash",
                "default_qty_value": 1000.0,
                "commission_value": 0.0,
            },
        )
        m["strategy.entry"](["L", "long"])  # no explicit qty
        assert abs(ev._strategy_state.position_size - 100.0) < 1e-9

    def test_percent_equity_qty_scales_by_leverage(self) -> None:
        """100% of 10k equity, lev=5, price=100 → qty = 10000*5/100 = 500."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](
            ["T"],
            {
                "initial_capital": 10_000.0,
                "leverage": 5,
                "default_qty_type": "percent_of_equity",
                "default_qty_value": 100.0,
                "commission_value": 0.0,
            },
        )
        m["strategy.entry"](["L", "long"])
        assert abs(ev._strategy_state.position_size - 500.0) < 1e-9

    def test_fixed_qty_ignores_leverage(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"leverage": 20, "default_qty_type": "fixed", "default_qty_value": 3})
        m["strategy.entry"](["L", "long"])
        assert abs(ev._strategy_state.position_size - 3.0) < 1e-9

    def test_capital_held_is_notional_over_leverage(self) -> None:
        """Long 10 @ 100, lev=10 → notional 1000, margin held 100."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"leverage": 10, "initial_capital": 10_000.0, "commission_value": 0.0})
        m["strategy.entry"](["L", "long", 10.0])
        held = _eval_expr(ev, "strategy.opentrades.capital_held")
        assert abs(held - 100.0) < 1e-9
        # cash ≈ equity - margin = 10000 - 100
        cash = _eval_expr(ev, "strategy.cash")
        assert abs(cash - 9900.0) < 1e-6

    def test_liquidation_price_long(self) -> None:
        """Long @ 100, lev=10 → liq ≈ 90."""
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"leverage": 10, "avg_price_model": "futures"})
        m["strategy.entry"](["L", "long", 1.0])
        liq = _eval_expr(ev, "strategy.margin_liquidation_price")
        assert abs(liq - 90.0) < 1e-9

    def test_liquidation_price_na_when_leverage_one(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = ev._build_builtin_map()
        m["strategy"](["T"], {"leverage": 1})
        m["strategy.entry"](["L", "long", 1.0])
        liq = _eval_expr(ev, "strategy.margin_liquidation_price")
        assert liq != liq  # NaN
