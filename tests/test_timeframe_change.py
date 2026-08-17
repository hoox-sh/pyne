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

"""``timeframe.change`` — first bar of a new UTC fixed-width period."""

from __future__ import annotations

from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_MONTH
from pynescript.ast.evaluator.builtins.timeframe import timeframe_bucket_id
from pynescript.ast.evaluator.builtins.timeframe import timeframe_change
from pynescript.ast.evaluator.builtins.timeframe import timeframe_in_seconds
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


def _monthly_change_indexes(n: int) -> set[int]:
    expected = {0}
    prev = timeframe_bucket_id(_T0_MS, "1M")
    for i in range(1, n):
        bid = timeframe_bucket_id(_T0_MS + i * _HOUR_MS, "1M")
        if bid != prev:
            expected.add(i)
            prev = bid
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
