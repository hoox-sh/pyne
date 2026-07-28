# Copyright (C) 2025 jango-blockchained
#
# SPDX-License-Identifier: LGPL-3.0-or-later
"""utc_parts_from_ms matches datetime UTC + Pine dayofweek."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from pynescript.util.time_parts import apply_utc_parts_to_context
from pynescript.util.time_parts import utc_parts_from_ms


def _ref(ms: int) -> tuple[int, int, int, int, int, int, int]:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    pine_dow = ((dt.weekday() + 1) % 7) + 1
    return dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, pine_dow


def test_utc_parts_matches_datetime_samples() -> None:
    samples = [
        0,  # 1970-01-01 Thu
        1_000_000,
        1_609_459_200_000,  # 2021-01-01
        1_704_067_200_000,  # 2024-01-01
        1_720_051_200_000,  # mid 2024
        86_400_000 - 1,  # end of first day
        1_234_567_890_123,
    ]
    for ms in samples:
        p = utc_parts_from_ms(ms)
        y, m, d, h, mi, s, dow = _ref(ms)
        assert (p.year, p.month, p.dayofmonth, p.hour, p.minute, p.second, p.dayofweek) == (
            y,
            m,
            d,
            h,
            mi,
            s,
            dow,
        ), f"ms={ms}"


def test_pine_dayofweek_sunday_is_one() -> None:
    # 2024-01-07 was a Sunday UTC
    ms = int(datetime(2024, 1, 7, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
    p = utc_parts_from_ms(ms)
    assert p.dayofweek == 1
    assert p.year == 2024 and p.month == 1 and p.dayofmonth == 7


def test_apply_utc_parts_to_context() -> None:
    ctx: dict = {}
    apply_utc_parts_to_context(ctx, 1_609_459_200_000)
    assert ctx["year"] == 2021
    assert ctx["month"] == 1
    assert ctx["dayofmonth"] == 1
    assert "dayofweek" in ctx
