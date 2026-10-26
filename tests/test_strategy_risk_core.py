# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit coverage for shared strategy risk / bracket helpers."""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.strategy_risk_core import StrategyBracketCore
from pynescript.strategy_risk_core import StrategyRiskCore


class _Risk(StrategyRiskCore):
    def __init__(self) -> None:
        self.max_drawdown_risk = None
        self.max_drawdown_risk_percent = None
        self.max_cons_loss_days = None
        self._max_drawdown = 0.0
        self._max_drawdown_percent = 0.0
        self.consecutive_loss_days = 0
        self.entries_blocked = False
        self._calendar_day = None
        self._fills_day = None
        self._last_trade_day = None
        self._day_pnl = 0.0
        self._day_filled_orders = 0
        self._days: dict[int, int] = {}

    def _day_bucket(self, ts: int, tz: Any = None) -> int:
        return self._days.get(ts, ts // 86_400_000)


class _Bracket(StrategyBracketCore):
    def __init__(self, entry_avg: float | None = 100.0, tick: float = 0.25) -> None:
        self._avg = entry_avg
        self._tick = tick

    def _exit_entry_avg(self, from_entry: str | None) -> float | None:
        return self._avg

    def _tick_offset_price(
        self,
        ticks: float | None,
        entry_avg: float | None,
        *,
        is_long: bool,
        is_profit: bool,
    ) -> float | None:
        if ticks is None or entry_avg is None:
            return None
        offset = float(ticks) * self._tick
        if is_long:
            return entry_avg + offset if is_profit else entry_avg - offset
        return entry_avg - offset if is_profit else entry_avg + offset


class TestPermanentRiskHalt:
    def test_no_limits_never_halts(self) -> None:
        r = _Risk()
        r._max_drawdown = 1e9
        r.consecutive_loss_days = 99
        assert r._permanent_risk_halt() is False

    def test_max_drawdown_cash(self) -> None:
        r = _Risk()
        r.max_drawdown_risk = 500.0
        r._max_drawdown = 499.9
        assert r._permanent_risk_halt() is False
        r._max_drawdown = 500.0
        assert r._permanent_risk_halt() is True

    def test_max_drawdown_percent(self) -> None:
        r = _Risk()
        r.max_drawdown_risk_percent = 10.0
        r._max_drawdown_percent = 9.9
        assert r._permanent_risk_halt() is False
        r._max_drawdown_percent = 10.0
        assert r._permanent_risk_halt() is True

    def test_consecutive_loss_days(self) -> None:
        r = _Risk()
        r.max_cons_loss_days = 3
        r.consecutive_loss_days = 2
        assert r._permanent_risk_halt() is False
        r.consecutive_loss_days = 3
        assert r._permanent_risk_halt() is True


class TestEnsureCalendarDay:
    def test_first_call_seeds_day(self) -> None:
        r = _Risk()
        r._days[1] = 10
        r._ensure_calendar_day(1)
        assert r._calendar_day == 10
        assert r._fills_day == 10
        assert r._day_pnl == 0.0

    def test_same_day_is_noop(self) -> None:
        r = _Risk()
        r._days[1] = 10
        r._ensure_calendar_day(1)
        r._day_pnl = -12.5
        r.entries_blocked = True
        r._ensure_calendar_day(1)
        assert r._day_pnl == -12.5
        assert r.entries_blocked is True

    def test_day_roll_resets_intraday_and_clears_non_permanent(self) -> None:
        r = _Risk()
        r._days[1] = 10
        r._days[2] = 11
        r._ensure_calendar_day(1)
        r.entries_blocked = True  # intraday halt
        r._day_pnl = -40.0
        r._day_filled_orders = 3
        r._ensure_calendar_day(2)
        assert r._calendar_day == 11
        assert r._day_pnl == 0.0
        assert r._day_filled_orders == 0
        assert r._fills_day == 11
        assert r.entries_blocked is False

    def test_day_roll_keeps_permanent_drawdown_halt(self) -> None:
        r = _Risk()
        r.max_drawdown_risk = 100.0
        r._max_drawdown = 150.0
        r._days[1] = 10
        r._days[2] = 11
        r._ensure_calendar_day(1)
        r.entries_blocked = True
        r._ensure_calendar_day(2)
        assert r.entries_blocked is True

    def test_loss_day_increments_consecutive_and_can_block(self) -> None:
        r = _Risk()
        r.max_cons_loss_days = 2
        r._days[1] = 10
        r._days[2] = 11
        r._days[3] = 12
        r._ensure_calendar_day(1)
        r._last_trade_day = 10
        r._day_pnl = -5.0
        r._ensure_calendar_day(2)
        assert r.consecutive_loss_days == 1
        assert r.entries_blocked is False
        # next roll with another losing day
        r._last_trade_day = 11
        r._day_pnl = -1.0
        r._ensure_calendar_day(3)
        assert r.consecutive_loss_days == 2
        assert r.entries_blocked is True

    def test_profit_day_resets_consecutive_losses(self) -> None:
        r = _Risk()
        r.consecutive_loss_days = 4
        r._days[1] = 10
        r._days[2] = 11
        r._ensure_calendar_day(1)
        r._last_trade_day = 10
        r._day_pnl = 25.0
        r._ensure_calendar_day(2)
        assert r.consecutive_loss_days == 0

    def test_flat_day_does_not_change_consecutive(self) -> None:
        r = _Risk()
        r.consecutive_loss_days = 2
        r._days[1] = 10
        r._days[2] = 11
        r._ensure_calendar_day(1)
        r._last_trade_day = 10
        r._day_pnl = 0.0
        r._ensure_calendar_day(2)
        assert r.consecutive_loss_days == 2

    def test_same_trade_day_skip_consecutive_update(self) -> None:
        """When last trade day equals the new calendar day, skip loss streak logic."""
        r = _Risk()
        r.consecutive_loss_days = 1
        r._days[1] = 10
        r._days[2] = 11
        r._ensure_calendar_day(1)
        r._last_trade_day = 11  # already stamped as new day
        r._day_pnl = -9.0
        r._ensure_calendar_day(2)
        assert r.consecutive_loss_days == 1


class TestMergeExitBracketPrices:
    def test_absolute_prices_win(self) -> None:
        b = _Bracket()
        limit, stop = b._merge_exit_bracket_prices(
            limit_p=110.0,
            stop_p=90.0,
            profit_ticks=10,
            loss_ticks=10,
            is_long=True,
            from_entry="e1",
        )
        assert limit == 110.0
        assert stop == 90.0

    def test_long_ticks_fill_missing_legs(self) -> None:
        b = _Bracket(entry_avg=100.0, tick=0.5)
        limit, stop = b._merge_exit_bracket_prices(
            limit_p=None,
            stop_p=None,
            profit_ticks=4,
            loss_ticks=2,
            is_long=True,
            from_entry=None,
        )
        assert limit == pytest.approx(102.0)
        assert stop == pytest.approx(99.0)

    def test_short_ticks_fill_missing_legs(self) -> None:
        b = _Bracket(entry_avg=200.0, tick=1.0)
        limit, stop = b._merge_exit_bracket_prices(
            limit_p=None,
            stop_p=None,
            profit_ticks=3,
            loss_ticks=5,
            is_long=False,
            from_entry="short1",
        )
        assert limit == pytest.approx(197.0)
        assert stop == pytest.approx(205.0)

    def test_none_ticks_leave_none(self) -> None:
        b = _Bracket()
        limit, stop = b._merge_exit_bracket_prices(
            limit_p=None,
            stop_p=None,
            profit_ticks=None,
            loss_ticks=None,
            is_long=True,
            from_entry=None,
        )
        assert limit is None
        assert stop is None

    def test_missing_entry_avg_yields_none_tick_legs(self) -> None:
        b = _Bracket(entry_avg=None)
        limit, stop = b._merge_exit_bracket_prices(
            limit_p=None,
            stop_p=95.0,
            profit_ticks=2,
            loss_ticks=2,
            is_long=True,
            from_entry="x",
        )
        assert limit is None
        assert stop == 95.0


def test_base_day_bucket_raises() -> None:
    class Bare(StrategyRiskCore):
        pass

    with pytest.raises(NotImplementedError):
        Bare()._day_bucket(0)  # type: ignore[call-arg]


def test_base_bracket_hooks_raise() -> None:
    class Bare(StrategyBracketCore):
        pass

    b = Bare()
    with pytest.raises(NotImplementedError):
        b._exit_entry_avg(None)
    with pytest.raises(NotImplementedError):
        b._tick_offset_price(1, 100.0, is_long=True, is_profit=True)
