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
from pynescript.ast.evaluator.builtins.strategy import StrategyCashAmount
from pynescript.compiler.engine import transpile
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
        e, _m = _evaluator()
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

    def test_cash_identifier_qty_type(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([500.0, StrategyCashAmount(100_000.0)])
        assert e._strategy_state.max_intraday_loss_cash == 500.0
        assert e._strategy_state.max_intraday_loss == float("inf")


class TestInterpretEnforcement:
    def test_percent_loss_blocks_entry(self) -> None:
        e, m = _evaluator()
        m["strategy"](["T"], {"initial_capital": 100_000.0})
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
        e.context["bar_index"] = 1
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
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
        e.context["bar_index"] = 1
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
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
        e.context["bar_index"] = 1
        m["strategy.entry"](["L2", "long", 1.0])
        e.context["bar_index"] = 2
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
        assert st.position_direction == "long"
        assert st._day_filled_orders == 1

    def test_entry_and_close_count_as_fills(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_filled_orders"]([2])
        st = e._strategy_state
        m["strategy.entry"](["L", "long", 1.0])
        e.context["bar_index"] = 1
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
        assert st._day_filled_orders == 1
        m["strategy.close"](["L"])
        e.context["bar_index"] = 2
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
        assert st._day_filled_orders == 2
        m["strategy.entry"](["L2", "long", 1.0])
        assert st.position_direction == "flat"
        assert _risk_blocked(e)

    def test_pending_stop_fill_blocked_after_halt(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        m["strategy.entry"](["P", "long", 1.0], {"stop": 120.0})
        assert e._strategy_state.position_direction == "flat"
        assert "P" in e._strategy_state.pending_orders
        e._strategy_state._day_pnl = -600.0
        e.context["bar_index"] = 1
        e.process_pending_orders(open_=100.0, high=130.0, low=100.0, close=125.0)
        assert e._strategy_state.position_direction == "flat"
        assert "P" not in e._strategy_state.pending_orders
        assert _risk_blocked(e)

    def test_covering_fill_gates_leftover_open(self) -> None:
        e, m = _evaluator()
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        m["strategy.entry"](["S", "short", 5.0])
        e.context["bar_index"] = 1
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
        m["strategy.entry"](["L", "long", 10.0], {"limit": 80.0})
        st = e._strategy_state
        assert st.position_direction == "short"
        assert "L" in st.pending_orders
        st._last_trade_day = st._day_bucket(_DAY_MS)
        st._day_pnl = -600.0
        e.context["bar_index"] = 2
        e.process_pending_orders(open_=100.0, high=100.0, low=70.0, close=80.0)
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
        b.begin_bar(1, 100.0, 100.0, 100.0, 100.0)
        assert b.position_size == 1.0

    def test_pending_entry_fill_blocked_after_halt(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=_DAY_MS)
        b.risk_max_intraday_loss(500.0, "cash")
        b.entry("P", "long", 1.0, limit=90.0)
        assert b.position_size == 0.0
        assert "P" in b.pending_orders
        b._day_pnl = -600.0
        b.begin_bar(1, 100.0, 100.0, 80.0, 85.0, bar_time=_DAY_MS + 60_000)
        assert b.position_size == 0.0
        assert "P" not in b.pending_orders
        assert any(e.get("comment") == "risk_blocked" for e in b.events)

    def test_covering_fill_gates_leftover_open(self) -> None:
        from pynescript.compiler.strategy_broker import CompileStrategyBroker

        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=_DAY_MS)
        b.risk_max_intraday_loss(500.0, "cash")
        b.entry("S", "short", 5.0)
        b.begin_bar(1, 100.0, 100.0, 100.0, 100.0, bar_time=_DAY_MS + 60_000)
        assert b.position_size == -5.0
        b.entry("L", "long", 10.0, limit=80.0)
        assert "L" in b.pending_orders
        b._last_trade_day = b._day_bucket(_DAY_MS)
        b._day_pnl = -600.0
        b.begin_bar(2, 100.0, 100.0, 70.0, 80.0, bar_time=_DAY_MS + 120_000)
        assert b.position_size == 0.0
        assert any(e.get("comment") == "risk_blocked" for e in b.events)


def _losing_bars() -> list[dict[str, float | int]]:
    # Day 0: entry placed (fills at bar 1's open = 100). Next UTC day the
    # close fills at bar 2's open = 80 (-$2000 = -2% of 100k). Later bars
    # stay on that close day so the 1% cap still blocks re-entry (halt
    # resumes only on the next calendar day — see D-02 day-resume tests).
    ohlcv = [
        (100.0, 100.0, 100.0, 100.0),
        (100.0, 100.0, 80.0, 80.0),
        (80.0, 80.0, 80.0, 80.0),
        (80.0, 80.0, 80.0, 80.0),
    ]
    times = [_DAY_MS, _DAY_MS + 86_400_000, _DAY_MS + 86_400_000 + 3_600_000, _DAY_MS + 86_400_000 + 7_200_000]
    return [
        {
            "time": times[i],
            "open": o,
            "high": h,
            "low": low,
            "close": c,
            "volume": 1000.0,
        }
        for i, (o, h, low, c) in enumerate(ohlcv)
    ]


_LOSING_SRC = """//@version=6
strategy("riskday", overlay=true, initial_capital=100000)
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
    """Day-1 -2% loss trips the 1% cap; same-day re-entry stays blocked on both hosts."""
    bars = _losing_bars()
    ri = Runtime(symbol="RISK").run(_LOSING_SRC, bars, mode="interpret")
    assert "error" not in ri, ri.get("error")
    rc = Runtime(symbol="RISK").run(_LOSING_SRC, bars, mode="compile")
    assert "error" not in rc, rc.get("error")
    pi = [float(v) for v in ri["series"]["ps"]]
    pc = [float(v) for v in rc["series"]["ps"]]
    assert pi == pc
    # Entry fills at bar 1's open (100); the day-1 close fills at bar 2's
    # open (80); same-day re-entry stays blocked.
    assert pi[0] == 0.0
    assert pi[1] == 100.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0


_CASH_ID_SRC = """//@version=6
strategy("cashid", overlay=true, initial_capital=10000)
strategy.risk.max_intraday_loss(500, strategy.cash)
if bar_index == 0
    strategy.entry("L", strategy.long, 10)
if bar_index == 1
    strategy.close("L")
if bar_index >= 2
    strategy.entry("L2", strategy.long, 10)
plot(strategy.position_size, "ps")
"""


def test_strategy_cash_identifier_dual_host() -> None:
    """``strategy.cash`` as the type arg is cash mode, not a 500% cap."""
    code = transpile(_CASH_ID_SRC)
    assert "risk_max_intraday_loss" in code
    assert "__strategy.cash" not in code.split("risk_max_intraday_loss", 1)[1][:120]
    assert "'cash'" in code or '"cash"' in code
    ohlcv = [
        (100.0, 100.0, 100.0, 100.0),
        (100.0, 100.0, 50.0, 50.0),
        (50.0, 50.0, 50.0, 50.0),
        (50.0, 50.0, 50.0, 50.0),
    ]
    times = [_DAY_MS, _DAY_MS + 86_400_000, _DAY_MS + 86_400_000 + 3_600_000, _DAY_MS + 86_400_000 + 7_200_000]
    bars = [
        {
            "time": times[i],
            "open": o,
            "high": h,
            "low": low,
            "close": c,
            "volume": 1000.0,
        }
        for i, (o, h, low, c) in enumerate(ohlcv)
    ]
    ri = Runtime(symbol="RISK").run(_CASH_ID_SRC, bars, mode="interpret")
    assert "error" not in ri, ri.get("error")
    rc = Runtime(symbol="RISK").run(_CASH_ID_SRC, bars, mode="compile")
    assert "error" not in rc, rc.get("error")
    pi = [float(v) for v in ri["series"]["ps"]]
    pc = [float(v) for v in rc["series"]["ps"]]
    assert pi == pc
    assert pi[0] == 0.0
    assert pi[1] == 10.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0


_FILLS_CAP_SRC = """//@version=6
strategy("fillcap", overlay=true)
strategy.risk.max_intraday_filled_orders(2)
if bar_index == 0
    strategy.entry("L", strategy.long, 1)
if bar_index == 1
    strategy.close("L")
if bar_index == 2
    strategy.entry("L2", strategy.long, 1)
if bar_index == 4
    strategy.entry("L3", strategy.long, 1)
plot(strategy.position_size, "ps")
"""


def test_fills_cap_rolls_next_day_dual_host() -> None:
    """Compile Runtime.begin_bar must receive bar time so the day bucket rolls."""
    code = transpile(_FILLS_CAP_SRC)
    assert "time_arr[__bar_idx]" in code
    bars = [
        {
            "time": _DAY_MS + (0 if i < 4 else 86_400_000) + i * 60_000,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000.0,
        }
        for i in range(6)
    ]
    ri = Runtime(symbol="RISK").run(_FILLS_CAP_SRC, bars, mode="interpret")
    assert "error" not in ri, ri.get("error")
    rc = Runtime(symbol="RISK").run(_FILLS_CAP_SRC, bars, mode="compile")
    assert "error" not in rc, rc.get("error")
    pi = [float(v) for v in ri["series"]["ps"]]
    pc = [float(v) for v in rc["series"]["ps"]]
    assert pi == pc
    # Bar 0 places the entry (fills bar 1 open); bar 1 places the close
    # (fills bar 2 open); bar 2/3 entries hit the same-day fill cap; the
    # bar-4 entry (next UTC day) fills at bar 5's open.
    assert pi[0] == 0.0
    assert pi[1] == 1.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0
    assert pi[4] == 0.0
    assert pi[5] == 1.0


_PENDING_RISK_SRC = """//@version=6
strategy("pendrisk", overlay=true, initial_capital=100000)
strategy.risk.max_intraday_loss(1.0)
if bar_index == 0
    strategy.entry("L", strategy.long, 20)
    strategy.entry("P", strategy.long, 1, stop=120)
if bar_index == 1
    strategy.close("L")
plot(strategy.position_size, "ps")
"""


def test_pending_limit_blocked_after_intraday_loss_dual_host() -> None:
    """Pending stop placed before the halt must not fill after the loss."""
    bars = [
        {"time": _DAY_MS, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1000.0},
        {"time": _DAY_MS + 60_000, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1000.0},
        {"time": _DAY_MS + 120_000, "open": 50.0, "high": 50.0, "low": 50.0, "close": 50.0, "volume": 1000.0},
        {"time": _DAY_MS + 180_000, "open": 100.0, "high": 125.0, "low": 95.0, "close": 122.0, "volume": 1000.0},
    ]
    ri = Runtime(symbol="RISK").run(_PENDING_RISK_SRC, bars, mode="interpret")
    assert "error" not in ri, ri.get("error")
    rc = Runtime(symbol="RISK").run(_PENDING_RISK_SRC, bars, mode="compile")
    assert "error" not in rc, rc.get("error")
    pi = [float(v) for v in ri["series"]["ps"]]
    pc = [float(v) for v in rc["series"]["ps"]]
    assert pi == pc
    # Bar 0 places both orders; bar 1 fills the market entry (open 100);
    # bar 2 fills the close at the open (50) → loss trips the cap; the
    # pending stop tries to fill on bar 3 and is rejected (risk_blocked).
    assert pi[0] == 0.0
    assert pi[1] == 20.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0
    comments = [str(e.get("comment") or "") for e in (ri.get("events") or [])]
    comments += [str(e.get("comment") or "") for e in (rc.get("events") or [])]
    assert any("risk_blocked" in c for c in comments)
