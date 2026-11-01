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

"""D-02: ``max_intraday_loss`` halt resumes the next ``syminfo.timezone`` day.

Day buckets are DST-aware midnight-to-midnight (same rules as
``timeframe.change``). ``max_drawdown`` stays a permanent halt.
``max_intraday_filled_orders`` uses the same timezone-aware bucket.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.timeframe import timeframe_calendar_id
from pynescript.compiler.numba_builtins import set_chart_identity
from pynescript.compiler.strategy_broker import CompileStrategyBroker
from pynescript.runtime import Runtime


try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - platforms without tzdata
    ZoneInfo = None  # type: ignore[assignment, misc]


_NY = "America/New_York"

_RESUME_SRC = """//@version=6
strategy("dayresume", overlay=true, initial_capital=100000)
strategy.risk.max_intraday_loss(1.0)
if bar_index == 0
    strategy.entry("L", strategy.long, 100)
if bar_index == 1
    strategy.close("L")
if bar_index >= 2
    strategy.entry("L2", strategy.long, 100)
plot(strategy.position_size, "ps")
"""

_DRAWDOWN_SRC = """//@version=6
strategy("ddhalt", overlay=true, initial_capital=10000)
strategy.risk.max_drawdown(50)
if bar_index == 0
    strategy.entry("L", strategy.long, 100)
if bar_index == 1
    strategy.close("L")
if bar_index >= 2
    strategy.entry("L2", strategy.long, 100)
plot(strategy.position_size, "ps")
"""

_FILLS_TZ_SRC = """//@version=6
strategy("filltz", overlay=true)
strategy.risk.max_intraday_filled_orders(2)
if bar_index == 0
    strategy.entry("L", strategy.long, 1)
if bar_index == 1
    strategy.close("L")
if bar_index == 2
    strategy.entry("L2", strategy.long, 1)
if bar_index == 3
    strategy.entry("L3", strategy.long, 1)
plot(strategy.position_size, "ps")
"""


def _ny_ms(year: int, month: int, day: int, hour: int, minute: int = 0) -> int:
    assert ZoneInfo is not None
    ny = ZoneInfo(_NY)
    return int(datetime(year, month, day, hour, minute, tzinfo=ny).timestamp() * 1000)


def _bar(ts: int, close: float) -> dict[str, float | int]:
    return {
        "time": ts,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 1000.0,
    }


def _ny_resume_bars() -> list[dict[str, float | int]]:
    """Enter/close on 2024-01-02 NY; bar 2 is still 2 Jan in NY (3 Jan UTC).

    Market orders fill one bar after placement, so bar 1 opens at the entry
    price (100) and bar 2 opens at the exit price (80, -$2000 = -2%).
    """
    bars = [
        _bar(_ny_ms(2024, 1, 2, 10), 100.0),  # entry placed
        _bar(_ny_ms(2024, 1, 2, 15), 80.0),  # entry fills @100; close placed
        _bar(_ny_ms(2024, 1, 2, 20), 80.0),  # close fills @80; 01:00 UTC Jan 3
        _bar(_ny_ms(2024, 1, 3, 0, 30), 80.0),  # first NY calendar day after
        _bar(_ny_ms(2024, 1, 3, 1, 30), 80.0),  # resume entry fills here
    ]
    bars[1]["open"] = 100.0
    return bars


def _run(src: str, bars: list[dict[str, float | int]], mode: str, timezone: str = "UTC") -> list[float]:
    host = Runtime(symbol="RISK")
    host._syminfo.timezone = timezone
    out = host.run(src, bars, mode=mode)
    assert "error" not in out, out.get("error")
    return [float(v) for v in out["series"]["ps"]]


def _evaluator(time_ms: int, timezone: str | None = None) -> tuple[NodeLiteralEvaluator, dict]:
    e = NodeLiteralEvaluator()
    ctx: dict = {"close": 100.0, "bar_index": 0, "time": time_ms}
    if timezone is not None:
        ctx["syminfo"] = SimpleNamespace(timezone=timezone)
    e.context = ctx
    return e, e._build_builtin_map()


@pytest.fixture(autouse=True)
def _reset_chart_timezone() -> None:
    set_chart_identity(timezone="UTC")
    yield
    set_chart_identity(timezone="UTC")


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
def test_calendar_id_utc_vs_ny_disagrees_after_utc_midnight() -> None:
    """A 20:00 NY bar is still 2 Jan locally and already 3 Jan in UTC."""
    ts = _ny_ms(2024, 1, 2, 20)
    utc_id = timeframe_calendar_id(ts, "D", "UTC")
    ny_id = timeframe_calendar_id(ts, "D", _NY)
    assert utc_id is not None and ny_id is not None
    assert utc_id != ny_id
    assert ny_id == timeframe_calendar_id(_ny_ms(2024, 1, 2, 10), "D", _NY)
    assert utc_id == timeframe_calendar_id(_ny_ms(2024, 1, 3, 0, 30), "D", "UTC")


class TestInterpretDayResume:
    def test_cash_loss_resumes_next_utc_day(self) -> None:
        day1 = 1_704_067_200_000  # 2024-01-01 00:00 UTC
        e, m = _evaluator(day1)
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        e._strategy_state._day_pnl = -600.0
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        assert e._strategy_state.entries_blocked is True
        e.context["time"] = day1 + 86_400_000
        e.context["bar_index"] = 1
        m["strategy.entry"](["L2", "long", 1.0])
        e.context["bar_index"] = 2
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
        assert e._strategy_state.position_direction == "long"
        assert e._strategy_state.entries_blocked is False

    @pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
    def test_ny_evening_stays_blocked_until_ny_midnight(self) -> None:
        e, m = _evaluator(_ny_ms(2024, 1, 2, 15), timezone=_NY)
        m["strategy.risk.max_intraday_loss"]([500.0, "cash"])
        e._strategy_state._day_pnl = -600.0
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        e.context["time"] = _ny_ms(2024, 1, 2, 20)
        e.context["bar_index"] = 1
        m["strategy.entry"](["L2", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        assert e._strategy_state.entries_blocked is True
        e.context["time"] = _ny_ms(2024, 1, 3, 0, 30)
        e.context["bar_index"] = 2
        m["strategy.entry"](["L3", "long", 1.0])
        e.context["bar_index"] = 3
        e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
        assert e._strategy_state.position_direction == "long"
        assert e._strategy_state.entries_blocked is False

    def test_max_drawdown_stays_blocked_across_day_roll(self) -> None:
        day1 = 1_704_067_200_000
        e, m = _evaluator(day1)
        m["strategy.risk.max_drawdown"]([50.0])
        e._strategy_state._equity_peak = 100_000.0
        e._strategy_state._max_drawdown = 100.0
        m["strategy.entry"](["L", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        assert e._strategy_state.entries_blocked is True
        e.context["time"] = day1 + 86_400_000
        e.context["bar_index"] = 1
        m["strategy.entry"](["L2", "long", 1.0])
        assert e._strategy_state.position_direction == "flat"
        assert e._strategy_state.entries_blocked is True

    def test_allow_entry_in_survives_day_roll(self) -> None:
        day1 = 1_704_067_200_000
        e, m = _evaluator(day1)
        m["strategy.risk.allow_entry_in"](["long"])
        e.context["time"] = day1 + 86_400_000
        m["strategy.entry"](["S", "short", 1.0])
        assert e._strategy_state.position_direction == "flat"


class TestCompileBrokerDayResume:
    def test_cash_loss_resumes_next_utc_day(self) -> None:
        day1 = 1_704_067_200_000
        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=day1)
        b.risk_max_intraday_loss(500.0, "cash")
        b._day_pnl = -600.0
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True
        b.begin_bar(1, 100.0, 100.0, 100.0, 100.0, bar_time=day1 + 86_400_000)
        b.entry("L2", "long", 1.0)
        b.begin_bar(2, 100.0, 100.0, 100.0, 100.0, bar_time=day1 + 86_400_000 + 60_000)
        assert b.position_size == 1.0
        assert b.entries_blocked is False

    @pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
    def test_ny_evening_stays_blocked_until_ny_midnight(self) -> None:
        set_chart_identity(timezone=_NY)
        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=_ny_ms(2024, 1, 2, 15))
        b.risk_max_intraday_loss(500.0, "cash")
        b._day_pnl = -600.0
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        b.begin_bar(1, 100.0, 100.0, 100.0, 100.0, bar_time=_ny_ms(2024, 1, 2, 20))
        b.entry("L2", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True
        b.begin_bar(2, 100.0, 100.0, 100.0, 100.0, bar_time=_ny_ms(2024, 1, 3, 0, 30))
        b.entry("L3", "long", 1.0)
        b.begin_bar(3, 100.0, 100.0, 100.0, 100.0, bar_time=_ny_ms(2024, 1, 3, 1, 30))
        assert b.position_size == 1.0
        assert b.entries_blocked is False

    def test_max_drawdown_stays_blocked_across_day_roll(self) -> None:
        day1 = 1_704_067_200_000
        b = CompileStrategyBroker(initial_capital=10_000.0)
        b.begin_bar(0, 100.0, 100.0, 100.0, 100.0, bar_time=day1)
        b.risk_max_drawdown(50.0)
        b._equity_peak = 10_000.0
        b._max_drawdown = 100.0
        b.entry("L", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True
        b.begin_bar(1, 100.0, 100.0, 100.0, 100.0, bar_time=day1 + 86_400_000)
        b.entry("L2", "long", 1.0)
        assert b.position_size == 0.0
        assert b.entries_blocked is True


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
def test_intraday_loss_resumes_next_ny_day_dual_host() -> None:
    """Loss on 2 Jan NY blocks the 20:00 bar; 00:30 3 Jan NY re-enters on both hosts."""
    bars = _ny_resume_bars()
    pi = _run(_RESUME_SRC, bars, "interpret", _NY)
    pc = _run(_RESUME_SRC, bars, "compile", _NY)
    assert pi == pc
    assert pi[0] == 0.0
    assert pi[1] == 100.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0
    assert pi[4] == 100.0


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
def test_utc_vs_ny_disagree_on_resume_bar_dual_host() -> None:
    """Same stamps: the close fills at the 20:00 bar (01:00 UTC Jan 3), so the
    loss lands on Jan 3 for UTC (blocked through these bars) but on Jan 2 for
    NY, which resumes at local midnight and fills on the last bar."""
    bars = _ny_resume_bars()
    pi_utc = _run(_RESUME_SRC, bars, "interpret", "UTC")
    pc_utc = _run(_RESUME_SRC, bars, "compile", "UTC")
    pi_ny = _run(_RESUME_SRC, bars, "interpret", _NY)
    pc_ny = _run(_RESUME_SRC, bars, "compile", _NY)
    assert pi_utc == pc_utc
    assert pi_ny == pc_ny
    assert pi_utc[2] == 0.0
    assert pi_ny[2] == 0.0
    assert pi_utc[3] == 0.0
    assert pi_ny[3] == 0.0
    # NY's loss belongs to Jan 2 → resumes at local midnight (bar 3) and the
    # entry fills at bar 4's open. UTC's loss lands on Jan 3 → still blocked.
    assert pi_utc[4] == 0.0
    assert pi_ny[4] == 100.0


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
def test_max_drawdown_halt_survives_ny_day_roll_dual_host() -> None:
    bars = _ny_resume_bars()
    pi = _run(_DRAWDOWN_SRC, bars, "interpret", _NY)
    pc = _run(_DRAWDOWN_SRC, bars, "compile", _NY)
    assert pi == pc
    assert pi[0] == 0.0
    assert pi[1] == 100.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0
    assert pi[4] == 0.0


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo/tzdata unavailable")
def test_fills_cap_uses_ny_calendar_bucket_dual_host() -> None:
    """Two fills on 2 Jan NY; 20:00 NY is still that day so a third entry waits."""
    bars = [
        _bar(_ny_ms(2024, 1, 2, 10), 100.0),
        _bar(_ny_ms(2024, 1, 2, 15), 100.0),
        _bar(_ny_ms(2024, 1, 2, 20), 100.0),
        _bar(_ny_ms(2024, 1, 3, 0, 30), 100.0),
        _bar(_ny_ms(2024, 1, 3, 1, 30), 100.0),
    ]
    pi = _run(_FILLS_TZ_SRC, bars, "interpret", _NY)
    pc = _run(_FILLS_TZ_SRC, bars, "compile", _NY)
    assert pi == pc
    # Bar 0 places the entry (fills bar 1); bar 1 places the close (fills
    # bar 2); bar 2's entry hits the two-fill cap (still 2 Jan NY); the
    # bar-3 entry (3 Jan NY) fills at bar 4's open.
    assert pi[0] == 0.0
    assert pi[1] == 1.0
    assert pi[2] == 0.0
    assert pi[3] == 0.0
    assert pi[4] == 1.0
