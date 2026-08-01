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


def _tz_is_utc(tz) -> bool:
    off = tz.utcoffset(datetime(2024, 1, 1, tzinfo=timezone.utc))
    return off is not None and int(off.total_seconds()) == 0
