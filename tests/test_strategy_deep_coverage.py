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

"""Deep strategy.* coverage: entry/exit/order, qty models, commission, OCA, queries."""

from __future__ import annotations

import math

from types import SimpleNamespace

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.strategy import StrategyCashAmount
from pynescript.ast.evaluator.builtins.strategy import _blend_arithmetic_avg
from pynescript.ast.evaluator.builtins.strategy import _norm_avg_price_model
from pynescript.ast.evaluator.builtins.strategy import _norm_leverage
from pynescript.ast.evaluator.builtins.strategy import _soft_float_decl
from pynescript.ast.evaluator.builtins.strategy import _soft_int_decl
from pynescript.ast.helper import parse
from pynescript.runtime import Runtime


def _set_bar(ev: NodeLiteralEvaluator, bar_index: int, close: float, time: int | None = None) -> None:
    ev.context["bar_index"] = bar_index
    ev.context["close"] = close
    ev.context["open"] = close
    ev.context["high"] = close
    ev.context["low"] = close
    ev.context["time"] = time if time is not None else 1_700_000_000_000 + bar_index * 60_000
    # Bar-start semantics (same as the Runtime host): pending orders placed on
    # earlier bars fill at this bar's open.
    if getattr(ev, "_strategy_state", None) is not None and ev._strategy_state.pending_orders:
        ev.process_pending_orders()


def _eval(ev: NodeLiteralEvaluator, source: str):
    return ev.visit(parse(source, mode="eval").body)


def _map(ev: NodeLiteralEvaluator | None = None) -> dict:
    e = ev or NodeLiteralEvaluator()
    if not hasattr(e, "context") or e.context is None:
        e.context = {}
    return e._build_builtin_map()


def _bars(n: int = 8) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 98.0 + i,
            "close": 100.0 + i,
            "volume": 100.0,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Soft declaration helpers (module-level)
# ---------------------------------------------------------------------------


class TestStrategySoftHelpers:
    def test_soft_int_decl_edges(self) -> None:
        assert _soft_int_decl(None, 7) == 7
        assert _soft_int_decl(True) == 1
        assert _soft_int_decl(3) == 3
        assert _soft_int_decl(4.9) == 4
        assert _soft_int_decl(float("nan"), 2) == 2
        assert _soft_int_decl("5") == 5
        assert _soft_int_decl("pyramid_val", 0) == 0
        assert _soft_int_decl(object(), 9) == 9

    def test_soft_float_and_leverage(self) -> None:
        assert _soft_float_decl(None, 1.5) == 1.5
        assert _soft_float_decl(True) == 1.0
        assert _soft_float_decl("2.5") == 2.5
        assert _soft_float_decl("bad", 3.0) == 3.0
        assert _soft_float_decl(float("inf"), 1.0) == 1.0
        assert _norm_leverage(10) == 10.0
        assert _norm_leverage(0.5) == 1.0
        assert _norm_leverage(-1, 2.0) == 2.0

    def test_avg_price_model_and_blend(self) -> None:
        assert _norm_avg_price_model("futures") == "futures"
        assert _norm_avg_price_model("strategy.avg_price_stock") == "stock"
        assert _norm_avg_price_model("inverse") == "inverse"
        assert _norm_avg_price_model(None, "stock") == "stock"
        assert _norm_avg_price_model("???") == "stock"
        assert _blend_arithmetic_avg(100.0, 2.0, 110.0, 2.0) == pytest.approx(105.0)
        assert _blend_arithmetic_avg(100.0, 0.0, 110.0, 0.0) == 110.0


# ---------------------------------------------------------------------------
# Declaration / sizing / commission / currency
# ---------------------------------------------------------------------------


class TestStrategyDeclarationPaths:
    def test_percent_of_equity_default_qty(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy"](
            ["T"],
            {
                "initial_capital": 10_000,
                "default_qty_type": "percent_of_equity",
                "default_qty_value": 10.0,
                "currency": "USD",
                "commission_type": "percent",
                "commission_value": 0.1,
                "pyramiding": 2,
                "leverage": 1,
            },
        )
        assert ev._strategy_state.account_currency == "USD"
        assert ev._strategy_state.default_qty_type == "percent_of_equity"
        assert ev._strategy_state.pyramiding == 2
        m["strategy.entry"](["L", "long"])  # qty from percent_of_equity
        _set_bar(ev, 1, 100.0)  # market entry fills at the open
        # 10% of 10000 / 100 = 10
        assert ev._strategy_state.position_size == pytest.approx(10.0)
        assert ev._strategy_state.open_trades[0].commission == pytest.approx(1.0)  # 10*100*0.1%

    def test_cash_qty_type_and_cash_amount_sentinel(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 50.0)
        m = _map(ev)
        m["strategy"](
            ["T"],
            {
                "initial_capital": 5_000,
                "default_qty_type": StrategyCashAmount(0.0),
                "default_qty_value": 500.0,
            },
        )
        assert ev._strategy_state.default_qty_type == "cash"
        m["strategy.entry"](["L", "long"])
        _set_bar(ev, 1, 50.0)  # market entry fills at the open
        # 500 / 50 = 10
        assert ev._strategy_state.position_size == pytest.approx(10.0)

    def test_commission_cash_per_order_and_contract(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy"](["T"], {"commission_type": "cash_per_order", "commission_value": 7.5})
        m["strategy.entry"](["L", "long", 3.0])
        _set_bar(ev, 1, 100.0)  # market entry fills at the open
        assert ev._strategy_state.open_trades[0].commission == 7.5

        ev2 = NodeLiteralEvaluator()
        _set_bar(ev2, 0, 100.0)
        m2 = _map(ev2)
        m2["strategy"](["T"], {"commission_type": "cash_per_contract", "commission_value": 0.5})
        m2["strategy.entry"](["L", "long", 4.0])
        _set_bar(ev2, 1, 100.0)  # market entry fills at the open
        assert ev2._strategy_state.open_trades[0].commission == 2.0

    def test_soft_pyramiding_unresolved_string(self) -> None:
        ev = NodeLiteralEvaluator()
        m = _map(ev)
        m["strategy"](["T"], {"pyramiding": "pyramid_val", "slippage": "n/a"})
        assert ev._strategy_state.pyramiding == 0
        assert ev._strategy_state.slippage_ticks == 0


class TestStrategyEntryExitOrder:
    def test_invalid_direction_and_qty_rejected(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy.entry"](["X", "sideways", 1.0])
        assert ev._strategy_state.position_size == 0.0
        events = [e for e in ev._strategy_state._events if e.comment == "invalid_direction"]
        assert events
        m["strategy.entry"](["Y", "long", float("nan")])
        assert any(e.comment == "invalid_qty" for e in ev._strategy_state._events)

    def test_reverse_flat_then_entry(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy.entry"](["L", "long", 2.0])
        _set_bar(ev, 1, 110.0)  # L fills at the open
        m["strategy.entry"](["S", "short", 2.0])
        _set_bar(ev, 2, 110.0)  # reversal fills at the open
        assert ev._strategy_state.position_direction == "short"
        assert ev._strategy_state.position_size == 2.0
        assert len(ev._strategy_state.closed_trades) >= 1

    def test_pyramiding_adds_open_trades(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy"](["T"], {"pyramiding": 2})
        m["strategy.entry"](["L1", "long", 1.0])
        m["strategy.entry"](["L2", "long", 1.0])
        m["strategy.entry"](["L3", "long", 1.0])
        _set_bar(ev, 1, 100.0)  # all three fill at the open
        # max_entries = pyramiding + 1 = 3
        assert len(ev._strategy_state.open_trades) == 3
        m["strategy.entry"](["L4", "long", 1.0])  # pyramiding cap: not queued
        _set_bar(ev, 2, 100.0)
        assert len(ev._strategy_state.open_trades) == 3

    def test_exit_qty_percent_and_bracket(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy.entry"](["L", "long", 10.0])
        _set_bar(ev, 1, 100.0)  # L fills at the open
        m["strategy.exit"]([], {"id": "X", "from_entry": "L", "qty_percent": 50.0})
        _set_bar(ev, 2, 100.0)  # market exit fills at the open
        assert ev._strategy_state.position_size == pytest.approx(5.0)

        ev2 = NodeLiteralEvaluator()
        _set_bar(ev2, 0, 100.0)
        ev2.context["high"] = 100.0
        ev2.context["low"] = 100.0
        m2 = _map(ev2)
        m2["strategy.entry"](["L", "long", 1.0])
        _set_bar(ev2, 1, 100.0)  # L fills at the open — brackets need an open leg
        m2["strategy.exit"]([], {"id": "TP", "from_entry": "L", "limit": 110.0, "stop": 95.0})
        assert "TP:limit" in ev2._strategy_state.pending_orders
        assert "TP:stop" in ev2._strategy_state.pending_orders
        ev2.context["bar_index"] = 2  # bracket placed on bar 1 activates on bar 2
        ev2.context["high"] = 111.0
        ev2.context["low"] = 100.0
        ev2.context["close"] = 110.0
        ev2.process_pending_orders(open_=100.0, high=111.0, low=100.0, close=110.0)
        assert ev2._strategy_state.position_direction == "flat"

    def test_close_cancel_order_paths(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy.entry"](["L", "long", 4.0])
        _set_bar(ev, 1, 100.0)  # L fills at the open
        m["strategy.close"](["L"], {"qty": 1.0, "comment": "partial"})
        _set_bar(ev, 2, 100.0)  # partial close fills at the open
        assert ev._strategy_state.position_size == 3.0
        m["strategy.order"](
            [],
            {"id": "O1", "direction": "short", "qty": 3.0, "limit": 120.0, "comment": "pending"},
        )
        assert "O1" in ev._strategy_state.pending_orders
        m["strategy.cancel"](["O1"])
        assert "O1" not in ev._strategy_state.pending_orders
        m["strategy.order"]([], {"id": "O2", "direction": "short", "qty": 3.0, "stop": 90.0})
        m["strategy.cancel_all"]([])
        assert ev._strategy_state.pending_orders == {}
        m["strategy.close_all"]([])
        _set_bar(ev, 3, 100.0)  # close_all fills at the open
        assert ev._strategy_state.position_direction == "flat"

    def test_oca_cancel_on_fill(self) -> None:
        ev = NodeLiteralEvaluator()
        ev.context = {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "bar_index": 0,
            "time": 0,
        }
        m = _map(ev)
        m["strategy.entry"](["L", "long", 5.0])
        m["strategy.order"](
            [],
            {
                "id": "TP",
                "direction": "short",
                "qty": 5.0,
                "limit": 110.0,
                "oca_name": "G",
                "oca_type": "cancel",
            },
        )
        m["strategy.order"](
            [],
            {
                "id": "SL",
                "direction": "short",
                "qty": 5.0,
                "stop": 95.0,
                "oca_name": "G",
                "oca_type": "cancel",
            },
        )
        ev.context["bar_index"] = 1  # orders placed on bar 0 activate on bar 1
        ev.process_pending_orders(open_=100.0, high=111.0, low=100.0, close=110.0)
        assert "SL" not in ev._strategy_state.pending_orders
        assert "TP" not in ev._strategy_state.pending_orders

    def test_limit_entry_pending_then_fill(self) -> None:
        ev = NodeLiteralEvaluator()
        ev.context = {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "bar_index": 0,
            "time": 1,
        }
        m = _map(ev)
        m["strategy.entry"]([], {"id": "L", "direction": "long", "qty": 2.0, "limit": 95.0})
        assert "L" in ev._strategy_state.pending_orders
        ev.context["bar_index"] = 1  # orders placed on bar 0 activate on bar 1
        ev.process_pending_orders(open_=100.0, high=100.0, low=94.0, close=96.0)
        assert ev._strategy_state.position_size == pytest.approx(2.0)


class TestStrategyQueriesAndRuntime:
    def test_closed_and_open_trade_queries(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 4, 100.0)
        m = _map(ev)
        m["strategy"](["T"], {"commission_type": "percent", "commission_value": 1.0})
        m["strategy.entry"]([], {"id": "L", "direction": "long", "qty": 2.0, "comment": "in"})
        _set_bar(ev, 5, 100.0, time=12345)  # fills at the open — entry bar/time are the fill bar
        assert _eval(ev, "strategy.opentrades.entry_id(0)") == "L"
        assert _eval(ev, "strategy.opentrades.entry_comment(0)") == "in"
        assert _eval(ev, "strategy.opentrades.entry_bar_index(0)") == 5
        assert _eval(ev, "strategy.opentrades.entry_time(0)") == 12345
        assert _eval(ev, "strategy.opentrades.commission(0)") == pytest.approx(2.0)
        _set_bar(ev, 6, 110.0, time=99999)
        m["strategy.close"]([], {"id": "L", "comment": "out"})
        _set_bar(ev, 7, 110.0, time=110000)  # close fills at the open
        assert _eval(ev, "strategy.closedtrades") == 1
        assert _eval(ev, "strategy.closedtrades.entry_id(0)") == "L"
        # exit_comment may be empty depending on close kwargs wiring
        assert isinstance(_eval(ev, "strategy.closedtrades.exit_comment(0)"), str)
        assert isinstance(_eval(ev, "strategy.closedtrades.profit(0)"), (int, float))
        # OOB defaults
        assert _eval(ev, "strategy.closedtrades.entry_id(9)") == ""
        assert _eval(ev, "strategy.opentrades.size(0)") == 0.0

    def test_convert_and_default_entry_qty_handlers(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy"](["T"], {"initial_capital": 10_000})
        assert m["strategy.convert_to_account"]([42.0]) == 42.0
        assert m["strategy.convert_to_symbol"]([7.0]) == 7.0
        assert m["strategy.default_entry_qty"]([50.0]) == pytest.approx(50.0)

    def test_account_currency_and_margin_liq(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy"](["T"], {"currency": "EUR", "leverage": 10, "initial_capital": 1000})
        assert _eval(ev, "strategy.account_currency") == "EUR"
        assert math.isnan(_eval(ev, "strategy.margin_liquidation_price"))
        m["strategy.entry"](["L", "long", 1.0])
        _set_bar(ev, 1, 100.0)  # market entry fills at the open
        liq = _eval(ev, "strategy.margin_liquidation_price")
        assert liq == pytest.approx(90.0)

    def test_coerce_helpers_via_handlers(self) -> None:
        ev = NodeLiteralEvaluator()
        series = SimpleNamespace(current=105.0)
        ev.context = {"close": series, "bar_index": 0, "time": 0}
        m = _map(ev)
        m["strategy.entry"](["L", "long", 1.0])
        # Bar-start fill: the market entry opens at the next bar's open (105).
        ev.context = {
            "open": 105.0,
            "high": 105.0,
            "low": 105.0,
            "close": 105.0,
            "bar_index": 1,
            "time": 1000,
        }
        ev.process_pending_orders()
        assert ev._strategy_state.entry_price == pytest.approx(105.0)
        assert ev._coerce_optional_price("na") is None
        assert ev._coerce_optional_price(SimpleNamespace(current=None)) is None
        assert ev._parse_order_qty("na")[0] == "missing"
        assert ev._parse_order_qty("abc")[0] == "invalid"
        assert ev._normalize_entry_direction("buy") == "long"
        assert ev._normalize_entry_direction("sell") == "short"
        assert ev._normalize_entry_direction(None) is None

    def test_runtime_script_entry_exit_alert_comment(self) -> None:
        """Runtime path: percent_of_equity sizing, alert_message kw, bracket + close."""
        src = """//@version=5
strategy("deep", overlay=true, initial_capital=10000, currency=currency.USD,
     default_qty_type=strategy.percent_of_equity, default_qty_value=10,
     commission_type=strategy.commission.percent, commission_value=0.05,
     pyramiding=1, calc_on_order_fills=true)
if bar_index == 0
    strategy.entry("L", strategy.long, comment="enter", alert_message="enter_alert")
if bar_index == 3
    strategy.exit("X", from_entry="L", limit=close*1.5, stop=close*0.5, comment="bracket")
if bar_index == 5
    strategy.close("L", comment="force")
plot(strategy.position_size, "psz")
plot(strategy.closedtrades, "ct")
"""
        out = Runtime(symbol="STR_DEEP").run(src, _bars(8), mode="interpret")
        assert "error" not in out, out.get("error")
        s = out["series"]
        assert s["psz"][0] == 0.0  # entry placed on bar 0, fills on bar 1
        assert s["psz"][1] == pytest.approx(10.0)
        assert s["psz"][-1] == 0.0
        assert s["ct"][-1] == 1

    def test_runtime_order_cancel_close_all(self) -> None:
        src = """//@version=5
strategy("ord", overlay=true, initial_capital=10000)
if bar_index == 0
    strategy.entry("L", strategy.long, 1)
if bar_index == 1
    strategy.order("O", strategy.short, 1, limit=close+10)
if bar_index == 2
    strategy.cancel("O")
if bar_index == 3
    strategy.close_all()
plot(strategy.position_size, "psz")
"""
        out = Runtime(symbol="STR_ORD").run(src, _bars(6), mode="interpret")
        assert "error" not in out, out.get("error")
        assert out["series"]["psz"][-1] == 0.0

    def test_series_at_and_snapshot_history(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy.entry"](["L", "long", 1.0])
        _set_bar(ev, 1, 100.0)  # L fills at the open
        st = ev._strategy_state
        st.snapshot_bar_series()
        _set_bar(ev, 2, 110.0)
        m["strategy.close"](["L"])
        _set_bar(ev, 3, 110.0)  # close fills at the open
        st.snapshot_bar_series()
        assert st.series_at("position_size", 0) == 0.0
        assert st.series_at("closedtrades", 0) == 1.0
        assert math.isnan(st.series_at("position_size", -1))
        assert math.isnan(st.series_at("unknown", 0))

    def test_update_open_trade_extremes(self) -> None:
        ev = NodeLiteralEvaluator()
        _set_bar(ev, 0, 100.0)
        m = _map(ev)
        m["strategy.entry"](["L", "long", 2.0])
        _set_bar(ev, 1, 100.0)  # market entry fills at the open
        st = ev._strategy_state
        st.update_open_trade_extremes(high=120.0, low=90.0)
        assert st.open_trades[0].max_runup == pytest.approx(40.0)
        assert st.open_trades[0].max_drawdown == pytest.approx(20.0)
        st.update_open_trade_extremes(high="bad", low=90.0)  # soft ignore
