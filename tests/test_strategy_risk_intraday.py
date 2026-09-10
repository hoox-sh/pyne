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

"""strategy.risk intraday gates: cash-vs-percent loss types (D-02 increment).

Covers type parsing (both brokers), interpret enforcement parity with the
compile broker (intraday loss + day-scoped fill cap), and a dual-host
end-to-end losing strategy that must agree on blocked entries.
"""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.runtime import Runtime

_DAY_MS = 1_704_067_200_000  # 2024-01-01 00:00 UTC


def _evaluator(time_ms: int = _DAY_MS) -> tuple[NodeLiteralEvaluator, dict]:
    e = NodeLiteralEvaluator()
    e.context = {"close": 100.0, "bar_index": 0, "time": time_ms}
    return e, e._build_builtin_map()


def _risk_blocked(e: NodeLiteralEvaluator) -> bool:
    return any(ev.comment == "risk_blocked" for ev in e._strategy_state._events)


class TestIntradayLossTypeParsing:
    def test_percent_default(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([10.0])
        assert e._strategy_state.max_intraday_loss == 10.0
        assert e._strategy_state.max_intraday_loss_cash is None

    def test_percent_of_equity_keyword(self) -> None:
        e, m = _evaluator()
        e._handle_strategy_risk_max_intraday_loss([10.0], {"type": "strategy.percent_of_equity"})
        assert e._strategy_state.max_intraday_loss == 10.0
        assert e._strategy_state.max_intraday_loss_cash is None

    def test_cash_positional_and_keyword(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([500.0, "strategy.cash"])
        assert e._strategy_state.max_intraday_loss_cash == 500.0
        assert e._strategy_state.max_intraday_loss == float("inf")
        e2, _ = _evaluator()
        e2._handle_strategy_risk_max_intraday_loss([250.0], {"type": "cash"})
        assert e2._strategy_state.max_intraday_loss_cash == 250.0

    def test_cash_clears_percent_and_vice_versa(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([10.0])
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        assert e._strategy_state.max_intraday_loss_cash == 500.0
        assert e._strategy_state.max_intraday_loss == float("inf")
        m["strategy.risk.max_intraday_loss"]([5.0])
        assert e._strategy_state.max_intraday_loss == 5.0
        assert e._strategy_state.max_intraday_loss_cash is None

    def test_invalid_values_ignored(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([-5.0])
        m["strategy.risk.max_intraday_loss"]([float("nan")])
        assert e._strategy_state.max_intraday_loss == float("inf")
        assert e._strategy_state.max_intraday_loss_cash is None


class TestInterpretEnforcement:
    def test_percent_loss_blocks_entry(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([10.0])
        e._strategy_state._day_pnl = -15_000.0  # 15% of 100k
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        assert e._strategy_state.entries_blocked is True
        assert _risk_blocked(e)

    def test_percent_loss_below_limit_allows_entry(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([10.0])
        e._strategy_state._day_pnl = -5_000.0  # 5% < 10%
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "long"

    def test_cash_loss_blocks_entry(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        e._strategy_state._day_pnl = -600.0
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        assert e._strategy_state.entries_blocked is True

    def test_cash_loss_below_limit_allows_entry(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        e._strategy_state._day_pnl = -400.0
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "long"

    def test_fills_cap_blocks_and_rolls_next_day(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_filled_orders"]([2])
        st = e._strategy_state
        st.note_fill_day(_DAY_MS)
        st.note_fill_day(_DAY_MS)
        assert st._day_filled_orders == 2
        m["strategy.entry"](["L", "long", 1.0])
        assert st.position_direction == "flat"
        assert _risk_blocked(e)
        # Cap is day-scoped: next day bucket admits entries again.
        e.context["time"] = _DAY_MS + 86_400_000
        m["strategy.entry"](["L2", "long", 1.0])
        assert st.position_direction == "long"
        assert st._day_filled_orders == 1

    def test_entry_and_close_count_as_fills(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_filled_orders"]([2])
        st = e._strategy_state
        m["strategy.entry"](["L", "long", 1.0])
        assert st._day_filled_orders == 1
        m["strategy.close"](["L"])
        assert st._day_filled_orders == 2
        m["strategy.entry"](["L2", "long", 1.0])
        assert st.position_direction == "flat"
        assert _risk_blocked(e)


class TestCompileBrokerParity:
    def test_cash_type_parsing(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.risk_max_intraday_loss(500.0, "strategy.cash")
        assert b.max_intraday_loss_cash == 500.0
        assert b.max_intraday_loss == float("inf")
        b.risk_max_intraday_loss(5.0)
        assert b.max_intraday_loss == 5.0
        assert b.max_intraday_loss_cash is None

    def test_cash_loss_blocks_entry(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.risk_max_intraday_loss(500.0, "cash")
        b._day_pnl = -600.0
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True
        assert any(e.get("comment") == "risk_blocked" for e in b.events)

    def test_percent_still_works(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
        b.risk_max_intraday_loss(10.0)
        b._day_pnl = -500.0  # 5% < 10%
        b.entry("L", "long", 1.0)
        assert b.position_size == 1.0


def _losing_bars() -> list[dict[str, float | int]]:
    # Day 0: enter 100 @ 100. Day 1: exit @ 80 (-$2000 = -2% of 100k).
    # Days 2-3: re-entry attempts must stay blocked (1% cap).
    closes = [100.0, 80.0, 80.0, 80.0]
    return [
        {
            "time": _DAY_MS + i * 86_400_000,
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": 1000.0,
        }
        for i, c in enumerate(closes)
    ]


_LOSING_SRC = """//@version=6
strategy("riskday", overlay=true)
strategy.risk.max_intraday_loss(1.0)
if bar_index == 0
    strategy.entry("L", strategy.long, 100)
if bar_index == 1
    strategy.close("L")
if bar_index >= 2
    strategy.entry("L2", strategy.long, 100)
plot(strategy.position_size, "ps")
"""


def test_losing_strategy_blocked_dual_host() -> None:
    """Day-1 -2% loss trips the 1% cap; both hosts block days 2-3 identically."""
    bars = _losing_bars()
    ri = Runtime(symbol="RISK").run(_LOSING_SRC, bars, mode="interpret")
    assert "error" not in ri, ri.get("error")
    rc = Runtime(symbol="RISK").run(_LOSING_SRC, bars, mode="compile")
    assert "error" not in rc, rc.get("error")
    pi = [float(v) for v in ri["series"]["ps"]]
    pc = [float(v) for v in rc["series"]["ps"]]
    assert pi == pc
    # Entered day 0, flat after day-1 close, never re-enters.
    assert pi[0] == 100.0
    assert pi[1] == 0.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0
