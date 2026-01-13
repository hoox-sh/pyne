# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
    # Stub implementation - would need actual timeframe tracking
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


def timeframe_in_seconds(timeframe_str: str) -> int:
    """Convert timeframe string to seconds.

    Converts the timeframe string to the number of seconds in that timeframe.

    Args:
        timeframe_str: Timeframe specification (e.g., "5", "15", "H", "D", "W", "M")

    Returns:
        Number of seconds in the timeframe
    """
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


def register_timeframe_functions(namespace: dict) -> None:
    """Register all timeframe functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["timeframe.change"] = timeframe_change
    namespace["timeframe.from_seconds"] = timeframe_from_seconds
    namespace["timeframe.in_seconds"] = timeframe_in_seconds

