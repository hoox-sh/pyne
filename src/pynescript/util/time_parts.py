# Copyright (C) 2025 jango-blockchained
#
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Fast UTC calendar parts from bar timestamps (ms).

Used by Runtime hosts instead of ``datetime.fromtimestamp`` every bar.
"""

from __future__ import annotations

from typing import NamedTuple


class UtcParts(NamedTuple):
    """UTC calendar fields for a bar open time."""

    year: int
    month: int
    dayofmonth: int
    hour: int
    minute: int
    second: int
    # Pine Script: 1=Sunday … 7=Saturday
    dayofweek: int


def utc_parts_from_ms(ms: int | float) -> UtcParts:
    """Convert Unix epoch milliseconds to UTC calendar parts.

    Matches ``datetime.fromtimestamp(ms/1000, tz=UTC)`` for year/month/day/h/m/s
    and Pine ``dayofweek`` via ``((weekday()+1)%7)+1`` (Mon=0 → Pine Sunday=1).
    """
    try:
        t = int(ms) // 1000
    except (TypeError, ValueError, OverflowError):
        t = 0
    # Clamp pathological values so civil conversion stays in int range
    if t < -62_167_219_200:  # ~year 0001
        t = -62_167_219_200
    elif t > 253_402_300_799:  # ~year 9999
        t = 253_402_300_799

    days, rem = divmod(t, 86_400)
    if rem < 0:
        # Python divmod toward -inf; normalize positive rem
        days -= 1
        rem += 86_400
    hour, rem = divmod(rem, 3600)
    minute, second = divmod(rem, 60)

    # Epoch day 0 (1970-01-01) was Thursday. Python weekday: Mon=0 … Sun=6.
    weekday = (days + 3) % 7  # 0=Mon … 6=Sun
    dayofweek = ((weekday + 1) % 7) + 1  # Pine: 1=Sun … 7=Sat

    # Civil date from days since Unix epoch (Howard Hinnant algorithms)
    z = days + 719_468
    era = (z if z >= 0 else z - 146_096) // 146_097
    doe = z - era * 146_097
    yoe = (doe - doe // 1460 + doe // 36_524 - doe // 146_096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + 3 if mp < 10 else mp - 9
    year = y + (1 if month <= 2 else 0)

    return UtcParts(
        year=int(year),
        month=int(month),
        dayofmonth=int(day),
        hour=int(hour),
        minute=int(minute),
        second=int(second),
        dayofweek=int(dayofweek),
    )


def apply_utc_parts_to_context(context: dict, ms: int | float) -> None:
    """Write year/month/dayofmonth/hour/minute/second/dayofweek into *context*."""
    try:
        parts = utc_parts_from_ms(ms)
    except (ValueError, OverflowError, TypeError):
        return
    context["year"] = parts.year
    context["month"] = parts.month
    context["dayofmonth"] = parts.dayofmonth
    context["hour"] = parts.hour
    context["minute"] = parts.minute
    context["second"] = parts.second
    context["dayofweek"] = parts.dayofweek
