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

"""Pine ``timeframe.*`` conversion and chart-period helpers.

Provides ``timeframe.in_seconds``, ``timeframe.from_seconds``,
``timeframe.change``, and period-flag resolution for the current chart.
Hosts may inject chart period via evaluator context; defaults assume the
loaded series period.

Registration
------------
:func:`register_timeframe_functions` injects handlers into the evaluator
dispatch map from :class:`~pynescript.ast.evaluator.builtins.BuiltinEvaluator`.
"""

from __future__ import annotations

import datetime as _datetime


try:
    from zoneinfo import ZoneInfo as _ZoneInfo
except ImportError:  # minimal platforms without tzdata
    _ZoneInfo = None  # type: ignore[assignment, misc]


# Time unit constants in seconds
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_WEEK = 604800
SECONDS_PER_MONTH = 2592000  # Approximate 30 days

# Timeframe format mappings
TIMEFRAME_SUFFIXES = {
    "M": SECONDS_PER_MONTH,
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
    "1M": SECONDS_PER_MONTH,
    "MONTH": SECONDS_PER_MONTH,
    "MONTHS": SECONDS_PER_MONTH,
}


def _normalize_time_ms(ts: object) -> float | None:
    """Coerce a bar timestamp to milliseconds. Seconds (< 1e11) are scaled."""
    if ts is None:
        return None
    current = getattr(ts, "current", None)
    if current is not None and not isinstance(ts, (int, float, bool, str)):
        ts = current
    try:
        t = float(ts)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if t != t:  # NaN
        return None
    if t < 1.0e11:
        t *= 1000.0
    return t


def timeframe_bucket_ms(timeframe_str: str | None) -> float | None:
    """Fixed-width HTF bucket in milliseconds, or None if *timeframe_str* is unusable."""
    if timeframe_str is None:
        return None
    raw = str(timeframe_str).strip()
    if not raw:
        return None
    try:
        sec = int(timeframe_in_seconds(raw))
    except (TypeError, ValueError):
        return None
    if sec <= 0:
        return None
    return float(sec) * 1000.0


def timeframe_bucket_id(ts: object, timeframe_str: str | None) -> int | None:
    """UTC fixed-width bucket id for *ts* under *timeframe_str*.

    Legacy fixed-width primitive (kept for intraday buckets and the Numba
    path). Daily/weekly/monthly use the same fixed-ms widths as
    :func:`timeframe_in_seconds` (UTC epoch alignment, not exchange
    calendar). Prefer :func:`timeframe_calendar_id` / calendar-aware
    :func:`timeframe_period_changed` for ``D`` / ``W`` / ``M``.
    """
    t = _normalize_time_ms(ts)
    bucket = timeframe_bucket_ms(timeframe_str)
    if t is None or bucket is None:
        return None
    return int(t // bucket)


#: Bare daily/weekly/monthly frames resolved on the exchange calendar
#: (``1D`` / ``1W`` / ``1M`` spellings included). Anything else — intraday,
#: multi-day (``3D``), seconds — keeps fixed-width UTC buckets.
_CALENDAR_TFS = frozenset({"D", "W", "M", "1D", "1W", "1M"})


def timeframe_is_calendar_tf(timeframe_str: object) -> bool:
    """True when *timeframe_str* is a bare ``D`` / ``W`` / ``M`` frame."""
    if timeframe_str is None:
        return False
    return str(timeframe_str).strip() in _CALENDAR_TFS


def _resolve_change_tz(tz: object) -> _datetime.tzinfo:
    """Coerce *tz* to a tzinfo, falling back to UTC — never raises.

    Accepts IANA names (``America/New_York``), ``datetime`` tzinfo /
    timedelta offsets, and the ``syminfo.timezone`` sentinel. Unknown or
    missing zoneinfo data → UTC.
    """
    utc = _datetime.timezone.utc
    if tz is None:
        return utc
    if isinstance(tz, _datetime.tzinfo):
        return tz
    if isinstance(tz, _datetime.timedelta):
        try:
            return _datetime.timezone(tz)
        except Exception:
            return utc
    s = str(tz).strip()
    if not s or s in {"syminfo.timezone", "UTC", "utc", "Etc/UTC", "GMT", "gmt"}:
        return utc
    if _ZoneInfo is None:
        return utc
    try:
        return _ZoneInfo(s)
    except Exception:
        return utc


def timeframe_calendar_id(ts: object, timeframe_str: str | None, tz: object = None) -> int | None:
    """Exchange-calendar period id for *ts* under a bare ``D`` / ``W`` / ``M`` frame.

    - ``D`` → proleptic ordinal (midnight-to-midnight in *tz*, DST-aware).
    - ``W`` → ISO year/week (Monday start, DST-aware).
    - ``M`` → calendar month (``year * 12 + month``).
    - Anything else → None (caller falls back to fixed buckets).

    Unusable timestamps → None. Unknown timezones → UTC.
    """
    raw = str(timeframe_str).strip() if timeframe_str is not None else ""
    if raw not in _CALENDAR_TFS:
        return None
    kind = raw[-1]
    t = _normalize_time_ms(ts)
    if t is None:
        return None
    d = _datetime.datetime.fromtimestamp(t / 1000.0, tz=_resolve_change_tz(tz))
    if kind == "D":
        return d.toordinal()
    if kind == "W":
        iso = d.isocalendar()
        return iso[0] * 100 + iso[1]
    return d.year * 12 + d.month


def _period_id(ts: object, timeframe_str: str | None, tz: object = None) -> int | None:
    """Calendar id for bare ``D`` / ``W`` / ``M``, else fixed-width bucket id."""
    if timeframe_is_calendar_tf(timeframe_str):
        return timeframe_calendar_id(ts, timeframe_str, tz)
    return timeframe_bucket_id(ts, timeframe_str)


def timeframe_period_changed(
    curr_ts: object,
    prev_ts: object,
    timeframe_str: str | None,
    bar_index: int | None = None,
    tz: object = None,
) -> bool:
    """True on the first bar of a new *timeframe_str* period.

    Bare ``D`` / ``W`` / ``M`` (plus ``1D`` / ``1W`` / ``1M``) resolve on
    the exchange calendar in *tz* (``syminfo.timezone``; UTC fallback):
    midnight-to-midnight days (DST-aware), ISO Monday-start weeks, calendar
    months. All other frames keep fixed-width UTC buckets.

    Bar 0 (``bar_index <= 0``) is a new period. Missing previous timestamp
    on later bars is not a change. Unusable times or timeframe strings
    return False (cannot detect a change). When *bar_index* is omitted,
    ``prev_ts is None`` is treated as bar 0 for the standalone helper.
    """
    curr_id = _period_id(curr_ts, timeframe_str, tz)
    if curr_id is None:
        return False
    if bar_index is not None:
        if bar_index <= 0:
            return True
        if prev_ts is None:
            return False
    elif prev_ts is None:
        return True
    prev_id = _period_id(prev_ts, timeframe_str, tz)
    if prev_id is None:
        return False
    return curr_id != prev_id


def timeframe_change(_timeframe_str: str) -> bool:
    """No-context fallback for ``timeframe.change``.

    The evaluator mixin uses :func:`timeframe_period_changed` with bar times.
    Standalone calls (no host series) cannot detect a change.
    """
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

    # Check shortcuts first (M / 1M / MO / MONTH / MONTHS are monthly)
    if timeframe_str in TIMEFRAME_SHORTCUTS:
        return TIMEFRAME_SHORTCUTS[timeframe_str]

    # NM (3M, 6M, 12M) is N months. Minutes are numeric-only ("1", "5", "15").
    if timeframe_str.endswith("M") and timeframe_str[:-1].isdigit():
        return int(timeframe_str[:-1]) * SECONDS_PER_MONTH

    if timeframe_str.isdigit():
        return int(timeframe_str) * SECONDS_PER_MINUTE

    # Handle suffixed formats (e.g., "5H", "1D")
    for suffix, multiplier in TIMEFRAME_SUFFIXES.items():
        if timeframe_str.endswith(suffix):
            try:
                number = int(timeframe_str[: -len(suffix)])
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
        # Empty request TF → treat as chart TF (reference defaults to chart)
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
        # "1M" is monthly on reference charts; bare "M" is also monthly in period form
        # (minute charts use numeric "1"/"5"/"15" without M suffix in reference period).
        p_norm = "M"
    else:
        p_norm = p

    is_seconds = p_norm.endswith("S") and p_norm[:-1].isdigit()
    is_nm_month = p_norm.endswith("M") and p_norm[:-1].isdigit()
    # Minutes are numeric-only ("1", "5", "15"); NM is N months.
    is_minutes = p_norm.isdigit()
    # reference period for minutes is "1","5","15","60"; hours "120","240" or "1H","4H"
    is_hours = p_norm.endswith("H") or (
        p_norm.isdigit() and int(p_norm) >= 60 and int(p_norm) % 60 == 0 and int(p_norm) < 1440
    )
    is_daily = p_norm in {"D", "1D"} or (p_norm.endswith("D") and p_norm[:-1].isdigit())
    is_weekly = p_norm in {"W", "1W"} or (p_norm.endswith("W") and p_norm[:-1].isdigit())
    is_monthly = p_norm in {"M", "1M", "MO"} or p_norm.endswith("MO") or is_nm_month
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
    # Prefer a bound mixin handler when the dispatcher already registered one.
    namespace.setdefault("timeframe.change", timeframe_change)
    namespace["timeframe.from_seconds"] = timeframe_from_seconds
    namespace["timeframe.in_seconds"] = timeframe_in_seconds

    # Property defaults (non-callable constants, like color.red). Hosts should
    # still inject flat context keys so local vars that shadow ``timeframe``
    # resolve via names.py's exact-key fast path.
    defaults = _period_flags("D")
    for key, value in defaults.items():
        namespace[f"timeframe.{key}"] = value
