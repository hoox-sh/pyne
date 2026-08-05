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

"""Timeframe functions for PineScript v6 evaluator."""

from __future__ import annotations


# Time unit constants in seconds
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_WEEK = 604800
SECONDS_PER_MONTH = 2592000  # Approximate 30 days

# Timeframe format mappings
TIMEFRAME_SUFFIXES = {
    "M": SECONDS_PER_MINUTE,
    "H": SECONDS_PER_HOUR,
    "D": SECONDS_PER_DAY,
    "W": SECONDS_PER_WEEK,
    "MO": SECONDS_PER_MONTH,
}

TIMEFRAME_SHORTCUTS = {
    "1H": SECONDS_PER_HOUR,
    "H": SECONDS_PER_HOUR,
    "D": SECONDS_PER_DAY,
    "W": SECONDS_PER_WEEK,
    "MO": SECONDS_PER_MONTH,
    "M": SECONDS_PER_MONTH,
}


def timeframe_change(_timeframe_str: str) -> bool:
    """Check if the timeframe has changed on the current bar.

    Returns true if the timeframe specified in the argument has changed
    on the current bar.

    Args:
        _timeframe_str: Timeframe specification (e.g., "5", "15", "D", "W", "M")

    Returns:
        Boolean indicating if timeframe has changed
    """
    # Stub: in a real implementation this would compare current bar's timeframe state.
    # For now returns False (no change detected) to avoid breaking scripts.
    return False


def timeframe_from_seconds(seconds: int) -> str:
    """Convert seconds to timeframe string format.

    Converts the number of seconds to the timeframe string format.

    Args:
        seconds: Number of seconds

    Returns:
        Timeframe string (e.g., "5" for 5 minutes, "H" for 1 hour)
    """
    if seconds < SECONDS_PER_MINUTE:
        return str(seconds)
    if seconds < SECONDS_PER_HOUR:
        minutes = seconds // SECONDS_PER_MINUTE
        return str(minutes)
    if seconds < SECONDS_PER_DAY:
        hours = seconds // SECONDS_PER_HOUR
        return f"{hours}H"
    if seconds < SECONDS_PER_WEEK:
        days = seconds // SECONDS_PER_DAY
        return f"{days}D"
    weeks = seconds // SECONDS_PER_WEEK
    return f"{weeks}W"


def timeframe_in_seconds(timeframe_str: str | None = None) -> int:
    """Convert timeframe string to seconds.

    Converts the timeframe string to the number of seconds in that timeframe.
    When called with no args (``timeframe.in_seconds()``), defaults to daily.

    Args:
        timeframe_str: Timeframe specification (e.g., "5", "15", "H", "D", "W", "M")

    Returns:
        Number of seconds in the timeframe
    """
    if timeframe_str is None or timeframe_str == "":
        timeframe_str = "D"
    timeframe_str = str(timeframe_str).strip().upper()

    # Check shortcuts first
    if timeframe_str in TIMEFRAME_SHORTCUTS:
        return TIMEFRAME_SHORTCUTS[timeframe_str]

    # Handle minute timeframes (just numbers or numbers with "m" suffix)
    if timeframe_str.endswith("M"):
        timeframe_str = timeframe_str[:-1]

    if timeframe_str.isdigit():
        return int(timeframe_str) * SECONDS_PER_MINUTE

    # Handle suffixed formats (e.g., "5H", "1D")
    for suffix, multiplier in TIMEFRAME_SUFFIXES.items():
        if timeframe_str.endswith(suffix):
            try:
                number = int(timeframe_str[:-len(suffix)])
                return number * multiplier
            except ValueError:
                continue

    # Default: treat as minutes
    try:
        return int(timeframe_str) * SECONDS_PER_MINUTE
    except ValueError as e:
        msg = f"Invalid timeframe format: {timeframe_str}"
        raise ValueError(msg) from e


def timeframes_equivalent(a: str | None, b: str | None) -> bool:
    """True when two timeframe strings denote the same bar duration.

    Used by ``request.security`` to decide whether a chart-evaluated expression
    is a same-TF passthrough (safe) or a higher/lower-TF request that would need
    real multi-TF data (otherwise honest ``na`` for complex exprs).
    """
    sa = "" if a is None else str(a).strip()
    sb = "" if b is None else str(b).strip()
    if not sa and not sb:
        return True
    if not sa or not sb:
        # Empty request TF → treat as chart TF (TV defaults to chart)
        return True
    if sa.upper() == sb.upper():
        return True
    # Alias families: "D"/"1D", "60"/"1H", …
    try:
        return timeframe_in_seconds(sa) == timeframe_in_seconds(sb)
    except (TypeError, ValueError):
        return sa.upper() == sb.upper()


def _chart_period(evaluator: object | None = None) -> str:
    """Resolve chart timeframe.period from host context / Timeframe object."""
    ctx = getattr(evaluator, "context", None) or {}
    flat = ctx.get("timeframe.period")
    if isinstance(flat, str) and flat and not flat.startswith("timeframe."):
        return flat
    tf = ctx.get("timeframe")
    if tf is not None:
        period = getattr(tf, "period", None)
        if isinstance(period, str) and period:
            return period
    main = ctx.get("timeframe.main_period")
    if isinstance(main, str) and main:
        return main
    return "D"


def _period_flags(period: str) -> dict[str, bool | int | str]:
    """Derive Pine timeframe.* boolean flags from a period string."""
    p = (period or "D").strip().upper()
    # Normalize common aliases
    if p in {"1D", "D", "DAY", "DAYS"}:
        p_norm = "D"
    elif p in {"1W", "W", "WEEK", "WEEKS"}:
        p_norm = "W"
    elif p in {"1M", "M", "MO", "MONTH", "MONTHS"}:
        # "1M" is monthly on TV charts; bare "M" is also monthly in period form
        # (minute charts use numeric "1"/"5"/"15" without M suffix in TV period).
        p_norm = "M"
    else:
        p_norm = p

    is_seconds = p_norm.endswith("S") and p_norm[:-1].isdigit()
    is_minutes = p_norm.isdigit() or (p_norm.endswith("M") and p_norm[:-1].isdigit() and p_norm not in {"M", "1M"})
    # TV period for minutes is "1","5","15","60"; hours "120","240" or "1H","4H"
    is_hours = p_norm.endswith("H") or (p_norm.isdigit() and int(p_norm) >= 60 and int(p_norm) % 60 == 0 and int(p_norm) < 1440)
    is_daily = p_norm in {"D", "1D"} or (p_norm.endswith("D") and p_norm[:-1].isdigit())
    is_weekly = p_norm in {"W", "1W"} or (p_norm.endswith("W") and p_norm[:-1].isdigit())
    is_monthly = p_norm in {"M", "1M", "MO"} or (p_norm.endswith("MO"))
    # Numeric-only periods are minutes (intraday)
    if p_norm.isdigit():
        is_minutes = True
        is_hours = int(p_norm) >= 60
        is_daily = is_weekly = is_monthly = False

    is_intraday = is_seconds or is_minutes or is_hours
    is_dwm = is_daily or is_weekly or is_monthly

    multiplier = 1
    if p_norm.isdigit():
        multiplier = int(p_norm)
    else:
        for suffix in ("MO", "S", "H", "D", "W", "M"):
            if p_norm.endswith(suffix) and p_norm[: -len(suffix)].isdigit():
                multiplier = int(p_norm[: -len(suffix)]) or 1
                break

    return {
        "period": period if period else "D",
        "multiplier": multiplier,
        "isintraday": bool(is_intraday and not is_dwm),
        "isdaily": bool(is_daily),
        "isweekly": bool(is_weekly),
        "ismonthly": bool(is_monthly),
        "isseconds": bool(is_seconds),
        "isinseconds": bool(is_seconds),
        "isminutes": bool(is_minutes and not is_hours),
        "ishours": bool(is_hours and not is_daily),
        "isdwm": bool(is_dwm),
        "main_period": period if period else "D",
    }


def register_timeframe_functions(namespace: dict) -> None:
    """Register all timeframe functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["timeframe.change"] = timeframe_change
    namespace["timeframe.from_seconds"] = timeframe_from_seconds
    namespace["timeframe.in_seconds"] = timeframe_in_seconds

    # Property defaults (non-callable constants, like color.red). Hosts should
    # still inject flat context keys so local vars that shadow ``timeframe``
    # resolve via names.py's exact-key fast path.
    defaults = _period_flags("D")
    for key, value in defaults.items():
        namespace[f"timeframe.{key}"] = value

