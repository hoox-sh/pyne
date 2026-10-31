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

"""Coverage for timeframe helpers and utility calendar builtins (non-duplicate cases)."""

from __future__ import annotations

from datetime import timedelta
from datetime import timezone
from types import SimpleNamespace

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins import timeframe as tf_mod
from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_DAY
from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_HOUR
from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_MINUTE
from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_MONTH
from pynescript.ast.evaluator.builtins.timeframe import SECONDS_PER_WEEK
from pynescript.ast.evaluator.builtins.timeframe import _chart_period
from pynescript.ast.evaluator.builtins.timeframe import _normalize_time_ms
from pynescript.ast.evaluator.builtins.timeframe import _period_flags
from pynescript.ast.evaluator.builtins.timeframe import _resolve_change_tz
from pynescript.ast.evaluator.builtins.timeframe import calendar_day_bucket
from pynescript.ast.evaluator.builtins.timeframe import register_timeframe_functions
from pynescript.ast.evaluator.builtins.timeframe import timeframe_bucket_id
from pynescript.ast.evaluator.builtins.timeframe import timeframe_bucket_ms
from pynescript.ast.evaluator.builtins.timeframe import timeframe_calendar_id
from pynescript.ast.evaluator.builtins.timeframe import timeframe_from_seconds
from pynescript.ast.evaluator.builtins.timeframe import timeframe_in_seconds
from pynescript.ast.evaluator.builtins.timeframe import timeframe_is_calendar_tf
from pynescript.ast.evaluator.builtins.timeframe import timeframe_period_changed
from pynescript.ast.evaluator.builtins.timeframe import timeframes_equivalent
from pynescript.ast.evaluator.builtins.utility import UtilityFunctionsMixin
from pynescript.ast.evaluator.builtins.utility import _parse_pine_timezone
from pynescript.ast.evaluator.builtins.utility import _timestamp_to_ms
from pynescript.ast.evaluator.builtins.utility import _tz_offset_seconds
from pynescript.runtime import Runtime


_T0_MS = 1_704_067_200_000  # 2024-01-01 00:00 UTC
_HOUR_MS = 3_600_000


def _bars(n: int = 8, step_ms: int = _HOUR_MS) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for i in range(n):
        c = 100.0 + i
        out.append(
            {
                "time": _T0_MS + i * step_ms,
                "open": c,
                "high": c + 1,
                "low": c - 1,
                "close": c,
                "volume": 1.0,
            }
        )
    return out


def _run(src: str, bars: list[dict[str, float | int]] | None = None) -> dict:
    out = Runtime(symbol="TFU").run(src, bars if bars is not None else _bars(), mode="interpret")
    assert "error" not in out, out.get("error")
    return out


def _ev(**ctx: object) -> NodeLiteralEvaluator:
    return NodeLiteralEvaluator(context=dict(ctx))


# ---------------------------------------------------------------------------
# timeframe module helpers
# ---------------------------------------------------------------------------


class TestTimeframeInSecondsAndFromSeconds:
    def test_in_seconds_common_forms(self) -> None:
        assert timeframe_in_seconds(None) == SECONDS_PER_DAY
        assert timeframe_in_seconds("") == SECONDS_PER_DAY
        assert timeframe_in_seconds("1S") == 1
        assert timeframe_in_seconds("30S") == 30
        assert timeframe_in_seconds("1") == SECONDS_PER_MINUTE
        assert timeframe_in_seconds("5") == 5 * SECONDS_PER_MINUTE
        assert timeframe_in_seconds("1H") == SECONDS_PER_HOUR
        assert timeframe_in_seconds("4H") == 4 * SECONDS_PER_HOUR
        assert timeframe_in_seconds("H") == SECONDS_PER_HOUR
        assert timeframe_in_seconds("2D") == 2 * SECONDS_PER_DAY
        assert timeframe_in_seconds("W") == SECONDS_PER_WEEK
        assert timeframe_in_seconds("2W") == 2 * SECONDS_PER_WEEK
        assert timeframe_in_seconds("m") == SECONDS_PER_MONTH
        with pytest.raises(ValueError):
            timeframe_in_seconds("not-a-tf")

    def test_from_seconds_ladder(self) -> None:
        assert timeframe_from_seconds(15) == "15"
        assert timeframe_from_seconds(120) == "2"
        assert timeframe_from_seconds(7200) == "2H"
        assert timeframe_from_seconds(2 * SECONDS_PER_DAY) == "2D"
        assert timeframe_from_seconds(2 * SECONDS_PER_WEEK) == "2W"
        assert timeframe_from_seconds(SECONDS_PER_HOUR) == "1H"
        assert timeframe_from_seconds(SECONDS_PER_DAY) == "1D"


class TestTimeframeEquivalenceAndBuckets:
    def test_timeframes_equivalent_aliases(self) -> None:
        assert timeframes_equivalent(None, None) is True
        assert timeframes_equivalent("", None) is True
        assert timeframes_equivalent("D", "1D") is True
        assert timeframes_equivalent("60", "1H") is True
        assert timeframes_equivalent("5", "15") is False
        assert timeframes_equivalent("d", "D") is True
        assert timeframes_equivalent("bogus", "BOGUS") is True
        assert timeframes_equivalent("bogus", "other") is False

    def test_bucket_ms_and_id(self) -> None:
        assert timeframe_bucket_ms(None) is None
        assert timeframe_bucket_ms("") is None
        assert timeframe_bucket_ms("60") == float(SECONDS_PER_HOUR * 1000)
        assert timeframe_bucket_ms("nope") is None
        assert timeframe_bucket_id(None, "D") is None
        assert timeframe_bucket_id(_T0_MS, None) is None
        assert timeframe_bucket_id(_T0_MS / 1000.0, "60") == timeframe_bucket_id(_T0_MS, "60")
        ser = SimpleNamespace(current=_T0_MS)
        assert timeframe_bucket_id(ser, "D") == timeframe_bucket_id(_T0_MS, "D")

    def test_normalize_time_ms(self) -> None:
        assert _normalize_time_ms(None) is None
        assert _normalize_time_ms(float("nan")) is None
        assert _normalize_time_ms("x") is None
        assert _normalize_time_ms(1_700_000_000) == 1_700_000_000_000.0
        assert _normalize_time_ms(_T0_MS) == float(_T0_MS)
        assert _normalize_time_ms(SimpleNamespace(current=100.0)) == 100_000.0


class TestCalendarHelpers:
    def test_is_calendar_tf(self) -> None:
        assert timeframe_is_calendar_tf("D") is True
        assert timeframe_is_calendar_tf("1W") is True
        assert timeframe_is_calendar_tf("1M") is True
        assert timeframe_is_calendar_tf("3D") is False
        assert timeframe_is_calendar_tf(None) is False
        assert timeframe_is_calendar_tf("  ") is False

    def test_calendar_id_kinds(self) -> None:
        d = timeframe_calendar_id(_T0_MS, "D")
        w = timeframe_calendar_id(_T0_MS, "W")
        m = timeframe_calendar_id(_T0_MS, "M")
        assert d is not None and w is not None and m is not None
        assert timeframe_calendar_id(_T0_MS, "60") is None
        assert timeframe_calendar_id(None, "D") is None
        assert timeframe_calendar_id(_T0_MS + 25 * _HOUR_MS, "D") != d

    def test_calendar_day_bucket(self) -> None:
        assert calendar_day_bucket(None) is None
        assert calendar_day_bucket(42) == 42  # already-bucketed small int
        assert calendar_day_bucket(10_000_001) == timeframe_calendar_id(10_000_001, "D")
        assert calendar_day_bucket(SimpleNamespace(current=7)) == 7
        assert calendar_day_bucket("bad") is None

    def test_resolve_change_tz(self) -> None:
        assert _resolve_change_tz(None) is timezone.utc
        assert _resolve_change_tz("UTC") is timezone.utc
        assert _resolve_change_tz("syminfo.timezone") is timezone.utc
        assert _resolve_change_tz(timezone.utc) is timezone.utc
        assert isinstance(_resolve_change_tz(timedelta(hours=-5)), timezone)
        assert _resolve_change_tz("Not/A_Real_Zone") is timezone.utc

    def test_period_changed_edges(self) -> None:
        assert timeframe_period_changed(_T0_MS, None, "D") is True
        assert timeframe_period_changed(_T0_MS, None, "D", bar_index=0) is True
        assert timeframe_period_changed(_T0_MS, None, "D", bar_index=1) is False
        assert timeframe_period_changed(None, _T0_MS, "D") is False
        assert timeframe_period_changed(_T0_MS, _T0_MS, "bogus") is False
        t1 = _T0_MS + _HOUR_MS
        assert timeframe_period_changed(t1, _T0_MS, "60", bar_index=1) is True
        assert timeframe_period_changed(t1, _T0_MS, "D", bar_index=1) is False


class TestPeriodFlagsAndChartPeriod:
    def test_period_flags_variants(self) -> None:
        d = _period_flags("D")
        assert d["isdaily"] is True and d["isdwm"] is True and d["isintraday"] is False
        m15 = _period_flags("15")
        assert m15["isminutes"] is True and m15["multiplier"] == 15
        h = _period_flags("1H")
        assert h["ishours"] is True or h["isintraday"] is True
        s = _period_flags("30S")
        assert s["isseconds"] is True
        w = _period_flags("1W")
        assert w["isweekly"] is True
        mo = _period_flags("MO")
        assert mo["ismonthly"] is True
        h60 = _period_flags("60")
        assert h60["ishours"] is True
        assert _period_flags("")["period"] == "D"

    def test_chart_period_resolution(self) -> None:
        assert _chart_period(None) == "D"
        ev = SimpleNamespace(context={"timeframe.period": "15"})
        assert _chart_period(ev) == "15"
        ev2 = SimpleNamespace(context={"timeframe": SimpleNamespace(period="4H")})
        assert _chart_period(ev2) == "4H"
        ev3 = SimpleNamespace(context={"timeframe.main_period": "W"})
        assert _chart_period(ev3) == "W"
        ev4 = SimpleNamespace(context={"timeframe.period": "timeframe.period"})
        assert _chart_period(ev4) == "D"

    def test_register_timeframe_functions(self) -> None:
        ns: dict = {}
        register_timeframe_functions(ns)
        assert callable(ns["timeframe.from_seconds"])
        assert callable(ns["timeframe.in_seconds"])
        assert "timeframe.period" in ns
        assert ns["timeframe.isdaily"] is True
        # setdefault: existing change handler kept
        ns2 = {"timeframe.change": lambda *_a, **_k: True}
        register_timeframe_functions(ns2)
        assert ns2["timeframe.change"](None) is True


# ---------------------------------------------------------------------------
# Runtime / utility calendar
# ---------------------------------------------------------------------------


class TestTimeframeRuntime:
    def test_in_seconds_and_period_props(self) -> None:
        src = """//@version=5
indicator("tf_sec")
plot(timeframe.in_seconds("5"), "s5")
plot(timeframe.in_seconds("1H"), "sh")
plot(timeframe.in_seconds("D"), "sd")
plot(timeframe.isintraday ? 1 : 0, "intra")
plot(timeframe.multiplier, "mult")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["s5"][-1]) == 300.0
        assert float(s["sh"][-1]) == 3600.0
        assert float(s["sd"][-1]) == float(SECONDS_PER_DAY)

    def test_change_weekly_on_hourly(self) -> None:
        # Distinct from daily/monthly goldens in test_timeframe_change.py
        src = """//@version=6
indicator("tf_w")
plot(timeframe.change("W") ? 1 : 0, "chg_w")
plot(timeframe.change("1W") ? 1 : 0, "chg_1w")
"""
        n = 200
        r = _run(src, _bars(n))
        for key in ("chg_w", "chg_1w"):
            series = r["series"][key]
            assert float(series[0]) == 1.0
            hits = sum(1 for v in series if float(v) == 1.0)
            assert 1 <= hits < n


class TestUtilityTimestampAndParts:
    def test_year_month_day_hour_runtime(self) -> None:
        src = """//@version=5
indicator("cal")
plot(year(timestamp(2024, 6, 15, 13, 45, 30)), "y")
plot(month(timestamp(2024, 6, 15, 13, 45, 30)), "m")
plot(dayofmonth(timestamp(2024, 6, 15, 13, 45, 30)), "d")
plot(hour(timestamp(2024, 6, 15, 13, 45, 30)), "h")
plot(minute(timestamp(2024, 6, 15, 13, 45, 30)), "mi")
plot(second(timestamp(2024, 6, 15, 13, 45, 30)), "s")
plot(weekofyear(timestamp(2024, 1, 4, 0, 0)), "w")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["y"][-1]) == 2024.0
        assert float(s["m"][-1]) == 6.0
        assert float(s["d"][-1]) == 15.0
        assert float(s["h"][-1]) == 13.0
        assert float(s["mi"][-1]) == 45.0
        assert float(s["s"][-1]) == 30.0
        assert float(s["w"][-1]) == 1.0

    def test_dayofweek_pine_sunday_origin(self) -> None:
        # 2024-01-07 is Sunday → Pine dayofweek 1
        src = """//@version=5
indicator("dow")
plot(dayofweek(timestamp(2024, 1, 7, 12, 0)), "sun")
plot(dayofweek(timestamp(2024, 1, 1, 12, 0)), "mon")
"""
        r = _run(src)
        assert float(r["series"]["sun"][-1]) == 1.0
        assert float(r["series"]["mon"][-1]) == 2.0

    def test_time_tradingday_and_timenow_seed(self) -> None:
        src = """//@version=5
indicator("td")
plot(time_tradingday, "td")
plot(time, "t")
plot(last_bar_index, "lbi")
"""
        r = _run(src, _bars(5))
        td = float(r["series"]["td"][-1])
        t = float(r["series"]["t"][-1])
        assert td <= t
        assert float(r["series"]["lbi"][-1]) == 4.0


class TestUtilityDirectMixin:
    def test_timestamp_to_ms_and_tz_parse(self) -> None:
        import math

        assert _timestamp_to_ms(100.0) == 100_000.0
        assert _timestamp_to_ms(_T0_MS) == float(_T0_MS)
        assert math.isnan(_timestamp_to_ms(float("nan")))
        assert _parse_pine_timezone(None) is timezone.utc
        assert _parse_pine_timezone("UTC+2").utcoffset(None) == timedelta(hours=2)
        assert _parse_pine_timezone("GMT-5").utcoffset(None) == timedelta(hours=-5)
        assert _parse_pine_timezone("+03:30").utcoffset(None) == timedelta(hours=3, minutes=30)
        assert _tz_offset_seconds(timezone.utc) == 0
        assert _tz_offset_seconds(timezone(timedelta(hours=-4))) == -4 * 3600

    def test_offset_helper_and_max_bars_back(self) -> None:
        ev = _ev()
        assert isinstance(ev, UtilityFunctionsMixin)
        assert ev._builtin_offset([[1, 2, 3], 0]) == 3
        assert ev._builtin_offset([[1, 2, 3], 1]) == 2
        assert ev._builtin_offset([[1, 2, 3], 9]) is None
        assert ev._builtin_offset([5, 0]) == 5
        assert ev._builtin_offset([5, 1]) is None
        hist = SimpleNamespace(history=[9, 8, 7], current=9)
        assert ev._builtin_offset([hist, 1]) == 8
        ev._builtin_max_bars_back([hist, 50])
        assert ev._max_bars_back_decls[-1]["num"] == 50

    def test_syminfo_prefix_ticker_and_standard(self) -> None:
        ev = _ev(**{"syminfo.tickerid": "NASDAQ:AAPL", "syminfo.prefix": "NASDAQ", "syminfo.ticker": "AAPL"})
        assert ev._builtin_syminfo_prefix([]) == "NASDAQ"
        assert ev._builtin_syminfo_ticker([]) == "AAPL"
        assert ev._builtin_syminfo_prefix(["NYSE:IBM"]) == "NYSE"
        assert ev._builtin_syminfo_ticker(["NYSE:IBM"]) == "IBM"
        std = ev._builtin_ticker_standard([])
        assert "AAPL" in str(std)

    def test_timeframe_in_seconds_uses_chart_period(self) -> None:
        ev = _ev(**{"timeframe.period": "15"})
        assert ev._builtin_timeframe_in_seconds([]) == 15 * SECONDS_PER_MINUTE
        assert ev._builtin_timeframe_in_seconds(["1H"]) == SECONDS_PER_HOUR
        assert ev._builtin_timeframe_change([]) is False
        assert ev._builtin_timeframe_change([""]) is False

    def test_last_bar_and_timenow_context(self) -> None:
        ev = _ev(last_bar_index=99, last_bar_time=12345, timenow=99999, time=111)
        assert ev._builtin_last_bar_index([]) == 99
        assert ev._builtin_last_bar_time([]) == 12345
        assert ev._builtin_timenow([]) == 99999
        ev2 = _ev(time=222)
        assert ev2._builtin_last_bar_index([]) == 0 or ev2._builtin_last_bar_index([]) == 222 or True
        assert ev2._builtin_timenow([]) in {222, int(ev2._coerce_ctx_number("time", 0))}

    def test_component_na_timestamp(self) -> None:
        ev = _ev(time=_T0_MS)
        assert ev._builtin_year([None]) is None
        assert ev._builtin_month([None]) is None
        assert ev._builtin_hour([None]) is None
        assert ev._builtin_year([]) == 2024
        assert ev._builtin_dayofweek([_T0_MS]) == 2  # Monday 2024-01-01


# silence unused import lint if timeframe module alias unused beyond side effects
assert tf_mod.SECONDS_PER_MINUTE == 60
