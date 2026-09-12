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

"""``timeframe.change`` — calendar-aware D/W/M, fixed buckets otherwise."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace


try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore[assignment, misc]

from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_MONTH
from pynescript.ast.evaluator.builtins.timeframe import _period_flags
from pynescript.ast.evaluator.builtins.timeframe import timeframe_bucket_id
from pynescript.ast.evaluator.builtins.timeframe import timeframe_calendar_id
from pynescript.ast.evaluator.builtins.timeframe import timeframe_change
from pynescript.ast.evaluator.builtins.timeframe import timeframe_in_seconds
from pynescript.ast.evaluator.builtins.timeframe import timeframe_is_calendar_tf
from pynescript.ast.evaluator.builtins.timeframe import timeframe_period_changed
from pynescript.ast.evaluator.builtins.utility import UtilityFunctionsMixin
from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import has_numba
from pynescript.compiler.numba_builtins import timeframe_change_at
from pynescript.runtime import Runtime


# 2024-01-01 00:00:00 UTC
_T0_MS = 1_704_067_200_000
_HOUR_MS = 3_600_000


def _hourly_bars(n: int = 72) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for i in range(n):
        c = 100.0 + i * 0.1
        out.append(
            {
                "time": _T0_MS + i * _HOUR_MS,
                "open": c - 0.05,
                "high": c + 0.2,
                "low": c - 0.2,
                "close": c,
                "volume": 1000.0 + i,
            }
        )
    return out


def test_standalone_timeframe_change_still_false() -> None:
    assert timeframe_change("D") is False


def test_bucket_id_daily_and_hourly() -> None:
    t0 = _T0_MS
    t1 = _T0_MS + _HOUR_MS
    t_next_day = _T0_MS + 24 * _HOUR_MS
    assert timeframe_bucket_id(t0, "60") != timeframe_bucket_id(t1, "60")
    assert timeframe_bucket_id(t0, "D") == timeframe_bucket_id(t1, "D")
    assert timeframe_bucket_id(t0, "D") != timeframe_bucket_id(t_next_day, "D")
    assert timeframe_period_changed(t_next_day, t0, "D") is True
    assert timeframe_period_changed(t1, t0, "D") is False
    assert timeframe_period_changed(t0, None, "D") is True


def test_timeframe_change_daily_on_hourly_bars() -> None:
    src = """
//@version=6
indicator("tfchg")
plot(timeframe.change("D") ? 1 : 0, "chg")
plot(timeframe.change("60") ? 1 : 0, "chg_h")
"""
    clear_parse_cache()
    out = Runtime(symbol="TF").run(src, _hourly_bars(72), mode="interpret")
    assert "error" not in out, out.get("error")
    chg = out["series"]["chg"]
    chg_h = out["series"]["chg_h"]
    assert len(chg) == 72
    # First bar of each UTC day (0, 24, 48)
    expected_days = {0, 24, 48}
    for i, v in enumerate(chg):
        want = 1.0 if i in expected_days else 0.0
        assert float(v) == want, (i, v)
    # Each hourly bar is a new 60-minute period
    assert all(float(v) == 1.0 for v in chg_h)


def test_timeframe_change_compile_matches_interpret() -> None:
    if not has_numba():
        return
    src = """
//@version=6
indicator("tfchg")
plot(timeframe.change("D") ? 1 : 0, "chg")
plot(timeframe.change("240") ? 1 : 0, "chg4")
"""
    bars = _hourly_bars(48)
    clear_parse_cache()
    clear_compile_cache()
    ri = Runtime(symbol="TF").run(src, bars, mode="interpret")
    clear_parse_cache()
    rc = Runtime(symbol="TF").run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    for key in ("chg", "chg4"):
        a, b = ri["series"][key], rc["series"][key]
        assert len(a) == len(b)
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            assert float(x) == float(y), (key, i, x, y)


def test_timeframe_in_seconds_monthly_not_minutes() -> None:
    assert timeframe_in_seconds("M") == SECONDS_PER_MONTH
    assert timeframe_in_seconds("1M") == SECONDS_PER_MONTH
    assert timeframe_in_seconds("MO") == SECONDS_PER_MONTH
    assert timeframe_in_seconds("MONTH") == SECONDS_PER_MONTH
    assert timeframe_in_seconds("MONTHS") == SECONDS_PER_MONTH
    assert timeframe_in_seconds("3M") == 3 * SECONDS_PER_MONTH
    assert timeframe_in_seconds("6M") == 6 * SECONDS_PER_MONTH
    assert timeframe_in_seconds("12M") == 12 * SECONDS_PER_MONTH
    assert timeframe_in_seconds("1") == 60
    assert timeframe_in_seconds("5") == 300
    assert timeframe_in_seconds("15") == 900
    assert timeframe_in_seconds("60") == 3600
    flags_3m = _period_flags("3M")
    assert flags_3m["ismonthly"] is True
    assert flags_3m["isminutes"] is False
    flags_15 = _period_flags("15")
    assert flags_15["isminutes"] is True
    assert flags_15["ismonthly"] is False


def _monthly_change_indexes(n: int) -> set[int]:
    """Calendar-month change bars (Feb 1 + Mar 1 2024 for the hourly grid)."""
    expected = {0}
    prev = timeframe_calendar_id(_T0_MS, "1M")
    for i in range(1, n):
        cid = timeframe_calendar_id(_T0_MS + i * _HOUR_MS, "1M")
        if cid != prev:
            expected.add(i)
            prev = cid
    return expected


def test_timeframe_change_monthly_on_hourly_bars() -> None:
    src = """
//@version=6
indicator("tfchg_m")
plot(timeframe.change("M") ? 1 : 0, "chg_m")
plot(timeframe.change("1M") ? 1 : 0, "chg_1m")
"""
    n = 500
    bars = _hourly_bars(n)
    clear_parse_cache()
    out = Runtime(symbol="TF").run(src, bars, mode="interpret")
    assert "error" not in out, out.get("error")
    expected = _monthly_change_indexes(n)
    for key in ("chg_m", "chg_1m"):
        series = out["series"][key]
        assert len(series) == n
        hits = {i for i, v in enumerate(series) if float(v) == 1.0}
        assert hits == expected, (key, hits, expected)
        # Must not fire every hourly bar (the old "1M" == 1 minute bug)
        assert len(hits) < n
        assert float(series[1]) == 0.0


def test_timeframe_change_monthly_compile_matches_interpret() -> None:
    if not has_numba():
        return
    src = """
//@version=6
indicator("tfchg_m")
plot(timeframe.change("M") ? 1 : 0, "chg_m")
plot(timeframe.change("1M") ? 1 : 0, "chg_1m")
"""
    bars = _hourly_bars(500)
    clear_parse_cache()
    clear_compile_cache()
    ri = Runtime(symbol="TF").run(src, bars, mode="interpret")
    clear_parse_cache()
    rc = Runtime(symbol="TF").run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    for key in ("chg_m", "chg_1m"):
        a, b = ri["series"][key], rc["series"][key]
        assert len(a) == len(b)
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            assert float(x) == float(y), (key, i, x, y)


def test_missing_prev_after_bar_0_is_false() -> None:
    t1 = _T0_MS + _HOUR_MS
    assert timeframe_period_changed(t1, None, "D", bar_index=0) is True
    assert timeframe_period_changed(t1, None, "D", bar_index=1) is False
    assert timeframe_period_changed(t1, float("nan"), "D") is False
    assert timeframe_period_changed(t1, float("nan"), "D", bar_index=1) is False

    times = [_T0_MS, float("nan"), _T0_MS + 2 * _HOUR_MS]
    assert timeframe_change_at(times, 0, "D") is True
    assert timeframe_change_at(times, 1, "D") is False
    assert timeframe_change_at([float("nan"), t1], 1, "D") is False

    class _Host(UtilityFunctionsMixin):
        def __init__(self) -> None:
            self.context: dict = {}

    host = _Host()
    host.context = {"time": _T0_MS, "bar_index": 0}
    assert host._builtin_timeframe_change(["D"]) is True
    # Scalar time (no .history) after bar 0 cannot detect a change
    host.context = {"time": _T0_MS + 24 * _HOUR_MS, "bar_index": 1}
    assert host._builtin_timeframe_change(["D"]) is False

    if has_numba():
        import numpy as np

        from pynescript.compiler.numba_builtins import numba_timeframe_change

        day_ms = 86_400_000.0
        nan_curr = np.array([np.nan, float(_T0_MS)], dtype=np.float64)
        nan_prev = np.array([np.nan, float(t1)], dtype=np.float64)
        ok = np.array([float(_T0_MS), float(t1)], dtype=np.float64)
        assert bool(numba_timeframe_change(nan_curr, 0, day_ms)) is False
        assert bool(numba_timeframe_change(nan_prev, 1, day_ms)) is False
        assert bool(numba_timeframe_change(ok, 0, day_ms)) is True
        assert bool(numba_timeframe_change(ok, 1, day_ms)) is False


def _utc_ms(year: int, month: int, day: int, hour: int = 12) -> int:
    return int(datetime(year, month, day, hour).timestamp() * 1000)


def test_calendar_tf_routing() -> None:
    """Only bare D/W/M (plus 1D/1W/1M) take the calendar path."""
    for tf in ("D", "W", "M", "1D", "1W", "1M"):
        assert timeframe_is_calendar_tf(tf) is True, tf
    for tf in ("60", "240", "3D", "2W", "12M", "d", "", None):
        assert timeframe_is_calendar_tf(tf) is False, tf
    assert timeframe_calendar_id(_T0_MS, "60") is None
    assert timeframe_calendar_id(_T0_MS, None) is None


def test_calendar_week_starts_monday() -> None:
    """Sun→Mon is a change; 7-day epoch buckets (Thursday start) disagree."""
    sun = _utc_ms(2024, 1, 7)
    mon = _utc_ms(2024, 1, 8)
    tue = _utc_ms(2024, 1, 9)
    assert timeframe_period_changed(mon, sun, "W") is True
    assert timeframe_period_changed(tue, mon, "W") is False
    # Fixed 7d buckets count from a Thursday epoch — same bucket here.
    assert timeframe_bucket_id(mon, "W") == timeframe_bucket_id(sun, "W")


def test_calendar_month_lengths_leap_year() -> None:
    """Feb 29 → Mar 1 changes; Feb 1 → Feb 29 does not (30d buckets differ)."""
    feb1 = _utc_ms(2024, 2, 1)
    feb29 = _utc_ms(2024, 2, 29)
    mar1 = _utc_ms(2024, 3, 1)
    assert timeframe_period_changed(mar1, feb29, "M") is True
    assert timeframe_period_changed(mar1, feb29, "1M") is True
    assert timeframe_period_changed(feb29, feb1, "M") is False


def test_calendar_day_dst_spring_forward() -> None:
    """23-hour Sunday 2026-03-08 stays one New York day (UTC says two)."""
    if ZoneInfo is None:
        return
    ny = ZoneInfo("America/New_York")

    def _ny_ms(month: int, day: int, hour: int, minute: int = 30) -> int:
        return int(datetime(2026, month, day, hour, minute, tzinfo=ny).timestamp() * 1000)

    sun_am = _ny_ms(3, 8, 0)  # 05:30 UTC Sun (EST)
    sun_pm = _ny_ms(3, 8, 23)  # 03:30 UTC Mon (EDT) — still Sunday in NY
    mon_am = _ny_ms(3, 9, 0)  # 04:30 UTC Mon — Monday in NY
    assert timeframe_calendar_id(sun_am, "D", "America/New_York") == timeframe_calendar_id(
        sun_pm, "D", "America/New_York"
    )
    assert timeframe_period_changed(sun_pm, sun_am, "D", tz="America/New_York") is False
    # UTC date rolled over mid-day NY time.
    assert timeframe_period_changed(sun_pm, sun_am, "D") is True
    assert timeframe_period_changed(mon_am, sun_pm, "D", tz="America/New_York") is True


def test_calendar_bad_timezone_falls_back_utc() -> None:
    """Unknown zones behave like UTC instead of raising."""
    feb29 = _utc_ms(2024, 2, 29)
    mar1 = _utc_ms(2024, 3, 1)
    assert timeframe_period_changed(mar1, feb29, "M", tz="Mars/Olympus_Mons") is True
    assert timeframe_calendar_id(mar1, "M", tz="Mars/Olympus_Mons") == timeframe_calendar_id(mar1, "M")


def test_builtin_uses_syminfo_timezone() -> None:
    """Interpret ``timeframe.change`` reads the host exchange timezone."""
    if ZoneInfo is None:
        return
    ny = ZoneInfo("America/New_York")

    def _ny_ms(month: int, day: int, hour: int) -> int:
        return int(datetime(2026, month, day, hour, 30, tzinfo=ny).timestamp() * 1000)

    curr = _ny_ms(3, 8, 23)
    prev = _ny_ms(3, 8, 0)

    class _Host(UtilityFunctionsMixin):
        def __init__(self) -> None:
            self.context: dict = {}

    host = _Host()
    host.context = {
        "time": SimpleNamespace(current=curr, history=[curr, prev]),
        "bar_index": 5,
        "syminfo": SimpleNamespace(timezone="America/New_York"),
    }
    assert host._builtin_timeframe_change(["D"]) is False
    host.context["syminfo"] = SimpleNamespace(timezone="UTC")
    assert host._builtin_timeframe_change(["D"]) is True


def test_timeframe_change_weekly_compile_matches_interpret() -> None:
    """Weekly calendar routing (object mode) agrees on both hosts."""
    if not has_numba():
        return
    src = """
//@version=6
indicator("tfchg_w")
plot(timeframe.change("W") ? 1 : 0, "chg_w")
"""
    bars = _hourly_bars(24 * 21)
    clear_parse_cache()
    clear_compile_cache()
    ri = Runtime(symbol="TF").run(src, bars, mode="interpret")
    clear_parse_cache()
    rc = Runtime(symbol="TF").run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    a, b = ri["series"]["chg_w"], rc["series"]["chg_w"]
    assert len(a) == len(b)
    # Mondays at bar 0 (2024-01-01), 168, 336.
    assert {i for i, v in enumerate(a) if float(v) == 1.0} == {0, 168, 336}
    for i, (x, y) in enumerate(zip(a, b, strict=True)):
        assert float(x) == float(y), (i, x, y)


def test_timeframe_change_at_threads_timezone() -> None:
    """Compile helper must honor tz, not always UTC."""
    if ZoneInfo is None:
        return
    ny = ZoneInfo("America/New_York")

    def _ny_ms(month: int, day: int, hour: int) -> int:
        return int(datetime(2026, month, day, hour, 30, tzinfo=ny).timestamp() * 1000)

    times = [_ny_ms(3, 8, 0), _ny_ms(3, 8, 23), _ny_ms(3, 9, 0)]
    assert timeframe_change_at(times, 1, "D", "America/New_York") is False
    assert timeframe_change_at(times, 1, "D", "UTC") is True
    assert timeframe_change_at(times, 2, "D", "America/New_York") is True


def _ny_session_bars() -> list[dict[str, float | int]]:
    """Intraday bars across 2026-03-08 spring-forward and 2026-11-01 fall-back."""
    ny = ZoneInfo("America/New_York")
    stamps: list[tuple[int, int, int]] = [
        (3, 7, 12),
        (3, 8, 0),
        (3, 8, 12),
        (3, 8, 23),
        (3, 9, 0),
        (3, 9, 12),
        (11, 1, 0),
        (11, 1, 12),
        (11, 1, 23),
        (11, 2, 0),
    ]
    bars: list[dict[str, float | int]] = []
    for i, (month, day, hour) in enumerate(stamps):
        ts = int(datetime(2026, month, day, hour, 30, tzinfo=ny).timestamp() * 1000)
        c = 100.0 + i
        bars.append({"time": ts, "open": c, "high": c, "low": c, "close": c, "volume": 1000.0})
    return bars


def test_calendar_change_runtime_ny_dst_parity() -> None:
    """Runtime interpret/compile agree on NY midnight-to-midnight days (not session 09:30)."""
    if ZoneInfo is None:
        return
    src = """
//@version=6
indicator("tfchg_ny")
plot(timeframe.change("D") ? 1 : 0, "chg")
"""
    bars = _ny_session_bars()
    clear_parse_cache()
    clear_compile_cache()
    ri_host = Runtime(symbol="TF")
    ri_host._syminfo.timezone = "America/New_York"
    ri = ri_host.run(src, bars, mode="interpret")
    rc_host = Runtime(symbol="TF")
    rc_host._syminfo.timezone = "America/New_York"
    rc = rc_host.run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    a = [float(v) for v in ri["series"]["chg"]]
    b = [float(v) for v in rc["series"]["chg"]]
    assert a == b
    # bar 0 is a new period; 03-08 00:30 is a new NY day vs 03-07;
    # 03-08 12:30 and 23:30 stay the same NY day; 03-09 00:30 changes.
    assert a[0] == 1.0
    assert a[1] == 1.0
    assert a[2] == 0.0
    assert a[3] == 0.0
    assert a[4] == 1.0
    # Fall-back: 11-01 00:30 / 12:30 / 23:30 are one NY day; 11-02 changes.
    assert a[6] == 1.0
    assert a[7] == 0.0
    assert a[8] == 0.0
    assert a[9] == 1.0
