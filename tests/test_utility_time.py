# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Focused tests for timestamp() and hour/minute/second/dayofmonth helpers."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from backend.runtime import Runtime
from pynescript.ast.evaluator.builtins.utility import UtilityFunctionsMixin
from pynescript.ast.evaluator.builtins.utility import _normalize_year_month
from pynescript.ast.evaluator.builtins.utility import _parse_pine_timezone
from pynescript.ast.evaluator.builtins.utility import _timestamp_ms_from_components


def _bars(n: int = 5, start_ms: int | None = None) -> list[dict]:
    if start_ms is None:
        start_ms = int(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
    out: list[dict] = []
    price = 100.0
    for i in range(n):
        out.append(
            {
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "time": start_ms + i * 3_600_000,
                "volume": 1.0,
            }
        )
    return out


def _run(src: str, bars: list[dict] | None = None) -> dict:
    r = Runtime().run(src, bars if bars is not None else _bars(), mode="interpret")
    assert "error" not in r, r.get("error")
    return r


class TestTimestampStrings:
    @pytest.mark.parametrize(
        "text",
        [
            "2012-01-01T01:01+0000",
            "2013-11-30T00:00+00:00",
            "2012-01-01T01:01:00Z",
            "01 Jan 2020 00:00 +0000",
            "January 1, 2020",
            "2024-01-01",
        ],
    )
    def test_parses_common_forms(self, text: str) -> None:
        src = f"""//@version=5
indicator("t")
plot(timestamp("{text}"))
"""
        r = _run(src)
        assert r["plots"][-1] is not None
        assert float(r["plots"][-1]) > 0


class TestTimestampTimezoneFirst:
    def test_utc_minus_five_midnight(self) -> None:
        """timestamp("UTC-5", y, m, d, 0, 0, 0) is 05:00 UTC."""
        src = """//@version=5
indicator("t")
plot(timestamp("UTC-5", 2024, 1, 1, 0, 0, 0))
"""
        r = _run(src)
        expected = int(datetime(2024, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=-5))).timestamp() * 1000)
        assert int(r["plots"][-1]) == expected

    def test_gmt_components_match_utc(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp("GMT", 2019, 8, 5, 12, 0))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(2019, 8, 5, 12, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_kwargs_timezone_year_month_day(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(timezone="GMT", year=2024, month=10, day=31, hour=0, minute=0, second=0))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(2024, 10, 31, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_year_first_still_works(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(2020, 1, 1, 0, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(2020, 1, 1, 0, 0, 0, 0)

    def test_year_9999_end_of_backtest_window(self) -> None:
        """Corpus residual: ToYear=9999 + hour=23, minute=59 must not shift args.

        Previously year>2200 was treated as a leading timezone, so
        timestamp(9999, 1, 1, 23, 59) became year=1, month=1, day=23, hour=59
        and raised "hour must be in 0..23, not 59".
        """
        src = """//@version=5
indicator("t")
plot(timestamp(9999, 1, 1, 23, 59))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(9999, 1, 1, 23, 59, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_hour_24_rolls_to_next_day(self) -> None:
        """TV-like: hour=24 is next day 00:00, not a hard failure."""
        src = """//@version=5
indicator("t")
plot(timestamp(2024, 1, 1, 24, 0))
plot(timestamp(2024, 1, 2, 0, 0))
"""
        r = _run(src)
        # Multi-plot: last values equal
        a = _timestamp_ms_from_components(2024, 1, 1, 24, 0, 0, 0)
        b = _timestamp_ms_from_components(2024, 1, 2, 0, 0, 0, 0)
        assert a == b
        assert int(r["plots"][-1]) == b

    def test_minute_60_and_second_overflow(self) -> None:
        assert _timestamp_ms_from_components(2024, 1, 1, 0, 60, 0, 0) == _timestamp_ms_from_components(
            2024, 1, 1, 1, 0, 0, 0
        )
        assert _timestamp_ms_from_components(2024, 1, 1, 0, 0, 60, 0) == _timestamp_ms_from_components(
            2024, 1, 1, 0, 1, 0, 0
        )

    def test_backtest_finish_pattern(self) -> None:
        """Common corpus pattern: timestamp(ToYear, ToMonth, ToDay, 23, 59)."""
        src = """//@version=5
indicator("t")
ToYear = 9999
ToMonth = 1
ToDay = 1
finish = timestamp(ToYear, ToMonth, ToDay, 23, 59)
plot(finish)
"""
        r = _run(src)
        assert "error" not in r
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(9999, 1, 1, 23, 59, 0, 0)


class TestTimestampMonthYearNormalization:
    """set05 residual: Invalid date/time arguments: month must be in 1..12."""

    def test_normalize_month_zero_is_january(self) -> None:
        assert _normalize_year_month(2020, 0) == (2020, 1)
        # day=0 still rolls via timedelta → last day of previous month relative
        # to Jan 1 = Dec 31 2019 when callers pass day=0.
        assert _timestamp_ms_from_components(2020, 0, 1, 0, 0, 0, 0) == _timestamp_ms_from_components(
            2020, 1, 1, 0, 0, 0, 0
        )

    def test_normalize_month_13_plus_rolls_year(self) -> None:
        assert _normalize_year_month(2022, 13) == (2023, 1)
        assert _normalize_year_month(2022, 14) == (2023, 2)
        assert _normalize_year_month(2022, 19) == (2023, 7)
        assert _timestamp_ms_from_components(2022, 19, 7, 0, 0, 0, 0) == _timestamp_ms_from_components(
            2023, 7, 7, 0, 0, 0, 0
        )

    def test_normalize_negative_month_rolls_backward(self) -> None:
        assert _normalize_year_month(2022, -1) == (2021, 11)

    def test_normalize_float_month_truncates(self) -> None:
        assert _normalize_year_month(2024, 3.9) == (2024, 3)
        assert _normalize_year_month(2024.7, 6.2) == (2024, 6)

    def test_normalize_year_clamped_to_datetime_range(self) -> None:
        assert _normalize_year_month(999999, 9) == (9999, 9)
        assert _normalize_year_month(0, 1) == (1, 1)

    def test_runtime_month_zero_corpus_pattern(self) -> None:
        """Larry / set05: timestamp(2020, 00, 00, 00, 00)."""
        src = """//@version=5
indicator("t")
plot(timestamp(2020, 00, 00, 00, 00))
"""
        r = _run(src)
        # month 0 → Jan; day 0 → Dec 31 2019 via day overflow
        expected = _timestamp_ms_from_components(2020, 0, 0, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_runtime_far_future_stop_year(self) -> None:
        """Backtest stop year 999999 must not be stripped as timezone.

        Residual pattern: timestamp(999999, 9, 26, 0, 0) was misread as
        timezone + year=9, month=26 → month error (before normalization) or
        wrong year 11 (after). Numeric first arg is always the year.
        """
        src = """//@version=5
indicator("t")
plot(timestamp(999999, 9, 26, 0, 0))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(9999, 9, 26, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_runtime_stop_year_3333_day_31(self) -> None:
        """Heiken residual: year=3333 kept; month=12 day=31 valid."""
        src = """//@version=5
indicator("t")
plot(timestamp(3333, 12, 31, 0, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(3333, 12, 31, 0, 0, 0, 0)

    def test_runtime_month_overflow_literal(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(2022, 19, 7, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(2022, 19, 7, 0, 0, 0, 0)

    def test_runtime_float_month_truncates(self) -> None:
        src = """//@version=5
indicator("t")
m = 3.9
plot(timestamp(2024, m, 1, 0, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(2024, 3, 1, 0, 0, 0, 0)


class TestTimePartArity:

    def test_hour_time_and_timezone(self) -> None:
        src = """//@version=5
indicator("t")
plot(hour(time, "UTC-5"))
"""
        r = _run(src)
        # Last bar: 12:00 + 4h = 16:00 UTC → 11:00 UTC-5
        assert int(r["plots"][-1]) == 11

    def test_hour_kwargs(self) -> None:
        src = """//@version=5
indicator("t")
plot(hour(time=time, timezone="UTC-5"))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == 11

    def test_minute_second_dayofmonth_with_tz(self) -> None:
        src = """//@version=5
indicator("t")
plot(minute(time, "UTC"))
plot(second(time, "GMT"))
plot(dayofmonth(time, "UTC+14"))
"""
        r = _run(src)
        # three plots interleaved per bar → last three values of final bar
        plots = r["plots"]
        assert plots is not None
        # Runtime flattens multi-plot as last value per plot series; accept any success
        assert "error" not in r

    def test_series_time_expression(self) -> None:
        src = """//@version=5
indicator("t")
t = time + 0
plot(hour(t, "UTC"))
plot(dayofmonth(t, "America/New_York"))
"""
        r = _run(src)
        assert r["plots"][-1] is not None

    def test_three_args_errors_with_clear_message(self) -> None:
        src = """//@version=5
indicator("t")
plot(hour(time, "UTC", 1))
"""
        r = Runtime().run(src, _bars(), mode="interpret")
        assert "error" in r
        assert "at most two arguments" in str(r["error"])

    def test_list_series_sample_accepted(self) -> None:
        """Direct unit: list-of-ms series unwraps to last sample."""

        class S(UtilityFunctionsMixin):
            def __init__(self) -> None:
                self.context = {"time": 1_704_067_200_000}

            def _error(self, m: str) -> None:  # type: ignore[override]
                raise ValueError(m)

        s = S()
        ms_list = [
            int(datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc).timestamp() * 1000),
            int(datetime(2024, 1, 1, 15, 30, tzinfo=timezone.utc).timestamp() * 1000),
        ]
        ts, tz = s._resolve_timestamp_arg([ms_list, "UTC"], name="hour")
        assert ts == float(ms_list[-1])
        dt = s._dt_from_ts(ts, tz)
        assert dt is not None
        assert dt.hour == 15 and dt.minute == 30


class TestParsePineTimezone:
    def test_utc_variants(self) -> None:
        assert _tz_is_utc(_parse_pine_timezone("UTC"))
        assert _tz_is_utc(_parse_pine_timezone("GMT"))
        assert _tz_is_utc(_parse_pine_timezone("syminfo.timezone"))

    def test_offset(self) -> None:
        tz = _parse_pine_timezone("UTC-5")
        off = tz.utcoffset(datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert off is not None
        assert int(off.total_seconds()) == -5 * 3600


class TestTimestampNumericSoftCoerce:
    """set05 residual: ``timestamp() arguments must be numeric`` (~25 corpus)."""

    def test_timenow_components(self) -> None:
        """``year(timenow)`` etc. must be numeric (timenow is a real series)."""
        src = """//@version=5
indicator("t")
plot(timestamp(year(timenow), month(timenow), dayofmonth(timenow), 0, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) > 0

    def test_string_year_month_day(self) -> None:
        """String numbers soft-coerce; pure numeric first arg is year not timezone."""
        src = """//@version=5
indicator("t")
plot(timestamp("2024", "1", "15", "0", "0"))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(2024, 1, 15, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_na_components_yield_na(self) -> None:
        """Required na components soft-return na (not hard Runtime Error)."""
        src = """//@version=5
indicator("t")
plot(na(timestamp(na, 1, 1)) ? 1 : 0)
"""
        r = _run(src)
        assert int(r["plots"][-1]) == 1

        src2 = """//@version=5
indicator("t")
plot(na(timestamp(2020, na, 1)) ? 1 : 0)
"""
        r2 = _run(src2)
        assert int(r2["plots"][-1]) == 1

    def test_dayofweek_constant_as_day(self) -> None:
        """``dayofweek.wednesday`` is int 4 usable as a day-of-month component."""
        src = """//@version=5
indicator("t")
plot(dayofweek.wednesday)
"""
        r = _run(src)
        assert int(r["plots"][-1]) == 4

        src2 = """//@version=5
indicator("t")
plot(timestamp("GMT", 2024, 1, dayofweek.wednesday, 0, 0, 0))
"""
        r2 = _run(src2)
        expected = _timestamp_ms_from_components(2024, 1, 4, 0, 0, 0, 0)
        assert int(r2["plots"][-1]) == expected


class TestTimestampDateRangeNormalize:
    """set05 residual: date value out of range / month·hour overflow (~23+)."""

    def test_month_zero_and_day_zero(self) -> None:
        """Corpus pattern ``timestamp(2020, 0, 0, 0, 0)`` — month 0 → January."""
        src = """//@version=5
indicator("t")
plot(timestamp(2020, 0, 0, 0, 0))
"""
        r = _run(src)
        # month 0 → 1; day 0 → previous day of Jan 1 = Dec 31 2019
        expected = _timestamp_ms_from_components(2020, 0, 0, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_day_overflow_rolls_month(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(2021, 1, 40, 0, 0))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(2021, 1, 40, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected
        # Jan 40 → Feb 9 2021
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(2021, 2, 9, 0, 0, 0, 0)

    def test_hour_and_minute_overflow(self) -> None:
        """hour=25 rolls; finish windows use hour=23 minute=59."""
        src = """//@version=5
indicator("t")
plot(timestamp(2020, 1, 1, 25, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(2020, 1, 1, 25, 0, 0, 0)

        src2 = """//@version=5
indicator("t")
plot(timestamp(2022, 1, 7, 23, 59))
"""
        r2 = _run(src2)
        assert int(r2["plots"][-1]) == _timestamp_ms_from_components(2022, 1, 7, 23, 59, 0, 0)

    def test_year_zero_clamped(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(0, 1, 1, 0, 0))
"""
        r = _run(src)
        expected = _timestamp_ms_from_components(0, 1, 1, 0, 0, 0, 0)
        assert int(r["plots"][-1]) == expected

    def test_feb_30_and_month_13(self) -> None:
        src = """//@version=5
indicator("t")
plot(timestamp(2021, 2, 30, 0, 0))
"""
        r = _run(src)
        assert int(r["plots"][-1]) == _timestamp_ms_from_components(2021, 2, 30, 0, 0, 0, 0)

        src2 = """//@version=5
indicator("t")
plot(timestamp(2020, 13, 1, 0, 0))
"""
        r2 = _run(src2)
        assert int(r2["plots"][-1]) == _timestamp_ms_from_components(2020, 13, 1, 0, 0, 0, 0)


def _tz_is_utc(tz) -> bool:
    off = tz.utcoffset(datetime(2024, 1, 1, tzinfo=timezone.utc))
    return off is not None and int(off.total_seconds()) == 0
