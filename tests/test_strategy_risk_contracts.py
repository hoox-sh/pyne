# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you are redistribute it and/or modify
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

"""`strategy.risk.max_position_size` contracts mode + `strategy.entry` max-fill parity.

Default stays %-of-equity (pinned). With
``PYNE_STRATEGY_RISK_CONTRACTS=1`` the value is an absolute contracts cap
on both hosts (interpret + compile). Separately, `strategy.entry` pending
limit/stop orders honor `max_fill_per_bar` like `strategy.order` already
does (multi-bar partial fills).
"""

from __future__ import annotations

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


CONTRACTS_ENV = "PYNE_STRATEGY_RISK_CONTRACTS"


def _ctx() -> dict:
    return {"open": 100.0, "high": 100.0, "low": 90.0, "close": 100.0, "bar_index": 0, "time": 0}


def test_percent_mode_default_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CONTRACTS_ENV, raising=False)
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy"](["T"], {"initial_capital": 100_000.0})
    m["strategy.risk.max_position_size"]([1.0])
    m["strategy.entry"](["L", "long", 1000.0])
    # Market entry fills at the next bar's open (reference Pine).
    e.context["bar_index"] = 1
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=100.0)
    assert e._strategy_state.position_size == 10.0


def test_contracts_mode_caps_absolute_qty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONTRACTS_ENV, "1")
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy.risk.max_position_size"]([10.0])
    assert e._strategy_state.max_position_size_contracts == 10.0
    assert e._strategy_state.max_position_size_percent is None
    m["strategy.entry"](["L", "long", 1000.0])
    e.context["bar_index"] = 1
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=100.0)
    assert e._strategy_state.position_size == 10.0


def test_contracts_mode_invalid_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CONTRACTS_ENV, "1")
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": 0}
    m = e._build_builtin_map()
    m["strategy.risk.max_position_size"]([0.0])
    m["strategy.entry"](["L", "long", 1000.0])
    e.context["bar_index"] = 1
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=100.0)
    assert e._strategy_state.position_size == 1000.0


def test_contracts_mode_compile_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    monkeypatch.setenv(CONTRACTS_ENV, "1")
    b = CompileStrategyBroker(initial_capital=10_000.0)
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.risk_max_position_size(10.0)
    b.entry("L", "long", 50.0)
    b.begin_bar(1, 100.0, 100.0, 90.0, 100.0)
    assert b.position_size == pytest.approx(10.0)


def test_percent_mode_compile_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    monkeypatch.delenv(CONTRACTS_ENV, raising=False)
    b = CompileStrategyBroker(initial_capital=10_000.0)
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.risk_max_position_size(10.0)
    b.entry("L", "long", 50.0)
    b.begin_bar(1, 100.0, 100.0, 90.0, 100.0)
    assert b.position_size == pytest.approx(10.0)


def test_entry_pending_honors_max_fill_per_bar() -> None:
    e = NodeLiteralEvaluator()
    e.context = _ctx()
    m = e._build_builtin_map()
    m["strategy.entry"]([], {"id": "L", "direction": "long", "qty": 10.0, "limit": 100.0, "max_fill_per_bar": 4.0})
    assert "L" in e._strategy_state.pending_orders
    e.context["bar_index"] = 1
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 4.0
    assert e._strategy_state.pending_orders["L"].remaining_qty == 6.0
    e.context["bar_index"] = 2
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 8.0
    e.context["bar_index"] = 3
    e.process_pending_orders(open_=100.0, high=100.0, low=90.0, close=95.0)
    assert e._strategy_state.position_size == 10.0
    assert "L" not in e._strategy_state.pending_orders


def test_entry_pending_max_fill_compile_parity() -> None:
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    b = CompileStrategyBroker(initial_capital=100_000.0)
    b.begin_bar(0, 100.0, 100.0, 90.0, 95.0)
    b.entry("L", "long", 10.0, limit=100.0, max_fill_per_bar=4.0)
    assert "L" in b.pending_orders
    # begin_bar already processes pending (fills up to max_fill_per_bar).
    b.begin_bar(1, 100.0, 100.0, 90.0, 95.0)
    assert b.position_size == pytest.approx(4.0)
    assert b.pending_orders["L"].remaining == pytest.approx(6.0)
    b.begin_bar(2, 100.0, 100.0, 90.0, 95.0)
    assert b.position_size == pytest.approx(8.0)
    b.begin_bar(3, 100.0, 100.0, 90.0, 95.0)
    assert b.position_size == pytest.approx(10.0)
    assert "L" not in b.pending_orders
