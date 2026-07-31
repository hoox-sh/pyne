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

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import lru_cache
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


@lru_cache(maxsize=4096)
def _timestamp_ms_from_components(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
) -> int:
    """UTC ms for calendar components (day overflow rolls months, matching TV).

    Cached: scripts often call ``timestamp(y, m, d, h, mi, s)`` with the same
    literals inside hot loops (e.g. TradingView "loop is too long" samples).
    """
    # Anchor on day 1 then add (day-1) so day overflow/underflow rolls months.
    base = datetime(int(year), int(month), 1, int(hour), int(minute), int(second), tzinfo=timezone.utc)
    dt = base + timedelta(days=int(day) - 1)
    return int(dt.timestamp() * 1000)


class UtilityFunctionsMixin(BuiltinDispatchMixin):
    """Utility and time-related built-in functions."""

    def _utility_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "time": self._builtin_time,
            "year": self._builtin_year,
            "month": self._builtin_month,
            "dayofmonth": self._builtin_dayofmonth,
            "dayofweek": self._builtin_dayofweek,
            "hour": self._builtin_hour,
            "minute": self._builtin_minute,
            "second": self._builtin_second,
            "time_close": self._builtin_time_close,
            "time_tradingday": self._builtin_time_tradingday,
            "weekofyear": self._builtin_weekofyear,
            "timestamp": self._builtin_timestamp,
            "last_bar_index": self._builtin_last_bar_index,
            "last_bar_time": self._builtin_last_bar_time,
            "max_bars_back": self._builtin_max_bars_back,
        }

    def _builtin_max_bars_back(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> None:
        """max_bars_back(var, num) — declare history buffer depth for a series.

        Runtime effect: recorded on evaluator for hosts; evaluation itself is
        unbounded within available OHLCV history.
        """
        kw = kwargs or {}
        var = args[0] if len(args) > 0 else kw.get("var")
        num = args[1] if len(args) > 1 else kw.get("num", 0)
        decls = getattr(self, "_max_bars_back_decls", None)
        if decls is None:
            decls = []
            try:
                self._max_bars_back_decls = decls  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 — setattr on frozen/partial mocks
                return
        decls.append({"var": var, "num": num})

    def _coerce_ctx_number(self, key: str, default: float = 0.0) -> float:
        ctx = getattr(self, "context", {}) or {}
        value = ctx.get(key, default)
        current = getattr(value, "current", None)
        if current is not None and not isinstance(value, (int, float, str)):
            value = current
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _builtin_last_bar_index(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """Index of the last bar in the dataset (falls back to bar_index)."""
        ctx = getattr(self, "context", {}) or {}
        if "last_bar_index" in ctx:
            return int(self._coerce_ctx_number("last_bar_index", 0))
        return int(self._coerce_ctx_number("bar_index", 0))

    def _builtin_last_bar_time(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """Time of the last bar in the dataset (falls back to time)."""
        ctx = getattr(self, "context", {}) or {}
        if "last_bar_time" in ctx:
            return int(self._coerce_ctx_number("last_bar_time", 0))
        return int(self._coerce_ctx_number("time", 0))

    def _bar_time_ms(self, key: str = "time") -> int:
        """Current bar open/close time from context (ms), falling back to *time*."""
        ctx = getattr(self, "context", {}) or {}
        if key in ctx:
            return int(self._coerce_ctx_number(key, 0))
        return int(self._coerce_ctx_number("time", 0))

    def _resolve_timestamp_arg(self, args: list[Any], *, name: str) -> float | None:
        """Resolve optional timestamp arg; bare form uses chart ``time``.

        Accepts optional timezone as 2nd arg (``hour(time, \"UTC-5\")``) and
        ignores it — chart timestamps are treated as UTC ms.

        Returns ``None`` (Pine ``na``) when the timestamp is missing — TV's
        ``year(na)`` / ``month(na)`` yield ``na`` rather than runtime.error.
        """
        if len(args) == 0:
            return float(self._bar_time_ms("time"))
        if len(args) > 2:
            self._error(f"{name}() takes zero or one argument (timestamp)")
        # args[1] may be timezone string — ignored
        ts = args[0]
        # Unwrap series wrappers
        current = getattr(ts, "current", None)
        if current is not None and not isinstance(ts, (list, tuple, str, bytes, int, float)):
            ts = current
        if ts is None:
            return None
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            try:
                ts = float(ts)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
        return float(ts)

    def _dt_from_ts(self, ts: float | None):
        """datetime from ms timestamp, or None if ts is na/invalid."""
        if ts is None:
            return None
        try:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    def _builtin_time(self, args: list[Any]) -> int:
        """Get timestamp for bar start time.

        Bare ``time`` / ``time()`` return the current bar open time from context.
        Extra session/timezone args are accepted and currently ignored (chart time).

        Returns Unix timestamp in milliseconds.
        """
        # Prefer host-injected bar time over wall clock.
        return int(self._bar_time_ms("time"))

    def _builtin_year(self, args: list[Any]) -> int | None:
        """Extract year from timestamp (bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="year"))
        return None if dt is None else dt.year

    def _builtin_month(self, args: list[Any]) -> int | None:
        """Extract month from timestamp (1-12; bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="month"))
        return None if dt is None else dt.month

    def _builtin_dayofmonth(self, args: list[Any]) -> int | None:
        """Extract day of month from timestamp (1-31; bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="dayofmonth"))
        return None if dt is None else dt.day

    def _builtin_dayofweek(self, args: list[Any]) -> int | None:
        """Extract day of week from timestamp (1=Sunday, 7=Saturday)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="dayofweek"))
        if dt is None:
            return None
        # Python: 0=Monday, 6=Sunday; PineScript: 1=Sunday, 7=Saturday
        return ((dt.weekday() + 1) % 7) + 1

    def _builtin_hour(self, args: list[Any]) -> int | None:
        """Extract hour from timestamp (0-23; bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="hour"))
        return None if dt is None else dt.hour

    def _builtin_minute(self, args: list[Any]) -> int | None:
        """Extract minute from timestamp (0-59; bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="minute"))
        return None if dt is None else dt.minute

    def _builtin_second(self, args: list[Any]) -> int | None:
        """Extract second from timestamp (0-59; bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="second"))
        return None if dt is None else dt.second

    def _builtin_time_close(self, args: list[Any]) -> int:
        """Get close time of current bar.

        Bare ``time_close`` / ``time_close()`` use host ``time_close`` when set,
        otherwise fall back to bar open ``time``.
        """
        return int(self._bar_time_ms("time_close"))

    def _builtin_time_tradingday(self, args: list[Any]) -> int:
        """Get trading day timestamp (midnight UTC of current trading day)."""
        # Optional timestamp arg is accepted; default to chart time.
        if len(args) > 1:
            self._error("time_tradingday() takes at most one argument")
        if args:
            ts = self._resolve_timestamp_arg(args, name="time_tradingday")
            now = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            ts = self._bar_time_ms("time")
            if ts:
                now = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            else:
                now = datetime.now(timezone.utc)
        trading_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(trading_day.timestamp() * 1000)

    def _builtin_weekofyear(self, args: list[Any]) -> int | None:
        """Get week number of the year (1-53; bare form uses chart time)."""
        dt = self._dt_from_ts(self._resolve_timestamp_arg(args, name="weekofyear"))
        return None if dt is None else dt.isocalendar()[1]

    def _coerce_timestamp_component(self, value: Any, *, default: int | None = 0, required: bool = False) -> int | None:
        """Coerce a timestamp() component to int; None → default or error."""
        if value is None:
            if required:
                self._error("timestamp() arguments must be numeric")
            return default
        current = getattr(value, "current", None)
        if current is not None and not isinstance(value, (list, tuple, str, bytes, int, float)):
            value = current
        if value is None:
            if required:
                self._error("timestamp() arguments must be numeric")
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                self._error("timestamp() arguments must be numeric")
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            self._error("timestamp() arguments must be numeric")
            return None

    def _parse_timestamp_string(self, text: str) -> int | None:
        """Parse TV-style date strings including optional timezone suffixes.

        Supported examples:
        - ``Dec 01 2021 23:59:59``
        - ``08 April 2024 00:00`` (full month, no seconds)
        - ``January 1, 2024`` / ``Jan 1, 2024`` (US comma form)
        - ``2023-01-01`` / ``2023-01-01T12:00:00`` (ISO)
        - ``01 Jan 2000 00:00:00 GMT+10``, ``UTC-5``, ``+0300``, ``+03:00``
        """
        import re
        from datetime import datetime
        from datetime import timedelta
        from datetime import timezone

        s0 = text.strip()
        if not s0:
            return None

        formats = (
            # Month name first
            "%b %d %Y %H:%M:%S",
            "%B %d %Y %H:%M:%S",
            "%b %d %Y %H:%M",
            "%B %d %Y %H:%M",
            "%b %d %Y",
            "%B %d %Y",
            # US comma forms: "January 1, 2024", "Jan 1, 2024 00:00"
            "%b %d, %Y %H:%M:%S",
            "%B %d, %Y %H:%M:%S",
            "%b %d, %Y %H:%M",
            "%B %d, %Y %H:%M",
            "%b %d, %Y",
            "%B %d, %Y",
            # Day first
            "%d %b %Y %H:%M:%S",
            "%d %B %Y %H:%M:%S",
            "%d %b %Y %H:%M",
            "%d %B %Y %H:%M",
            "%d %b %Y",
            "%d %B %Y",
            # Day first with comma after month name
            "%d %b, %Y %H:%M:%S",
            "%d %B, %Y %H:%M:%S",
            "%d %b, %Y %H:%M",
            "%d %B, %Y %H:%M",
            "%d %b, %Y",
            "%d %B, %Y",
            # ISO
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        )

        def _try_formats(s: str, tz_offset: timedelta) -> int | None:
            for fmt in formats:
                try:
                    # Interpret naive datetime in the stated offset, then convert to UTC ms
                    dt_local = datetime.strptime(s, fmt)
                    dt_utc = (dt_local - tz_offset).replace(tzinfo=timezone.utc)
                    return int(dt_utc.timestamp() * 1000)
                except ValueError:
                    continue
            return None

        # Try without timezone first so ISO dates like "2023-01-01" are not
        # misread as a bare "-01" UTC offset by the suffix stripper below.
        parsed = _try_formats(s0, timedelta(0))
        if parsed is not None:
            return parsed

        s = s0
        tz_offset = timedelta(0)

        # Timezone suffixes. Order matters:
        # 1) GMT/UTC[+/-H[:MM]] — may omit space: "GMT+10", "UTC-5"
        # 2) bare +HH:MM / +HHMM — require leading whitespace so we never eat
        #    the day part of "yyyy-mm-dd" (e.g. trailing "-01").
        m = re.search(
            r"\s*(?:GMT|UTC)\s*([+-])(\d{1,2})(?::?(\d{2}))?\s*$",
            s,
            re.I,
        )
        if m:
            sign = 1 if m.group(1) == "+" else -1
            hours = int(m.group(2))
            mins = int(m.group(3) or 0)
            tz_offset = sign * timedelta(hours=hours, minutes=mins)
            s = s[: m.start()].strip()
        else:
            m = re.search(r"\s+([+-])(\d{1,2}):(\d{2})\s*$", s)
            if m:
                sign = 1 if m.group(1) == "+" else -1
                tz_offset = sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
                s = s[: m.start()].strip()
            else:
                m = re.search(r"\s+([+-])(\d{2})(\d{2})\s*$", s)
                if m:
                    sign = 1 if m.group(1) == "+" else -1
                    tz_offset = sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
                    s = s[: m.start()].strip()
                else:
                    # Drop bare GMT/UTC without offset
                    s = re.sub(r"\s+(?:GMT|UTC)\s*$", "", s, flags=re.I).strip()

        return _try_formats(s, tz_offset)

    def _builtin_timestamp(self, args: list[Any]) -> int:
        """Create Unix timestamp from date/time components or a date string.

        Forms:
        - ``timestamp(\"Dec 01 2021 23:59:59\")``
        - ``timestamp(\"01 Jan 2000 00:00:00 GMT+10\")``
        - ``timestamp(year, month, day[, hour, minute, second])``
        - ``timestamp(timezone, year, month, day[, hour, minute, second])``
          e.g. ``timestamp(\"GMT\", 2019, 8, 5, 12, 0)`` or
          ``timestamp(syminfo.timezone, y, m, d, 0, 0)``

        Accepts overflow/underflow on day (e.g. day=40 or day=-5) via month
        rollover, matching TradingView ``timestamp`` arithmetic used by scripts
        such as dividend_yield.
        """
        # Single string form
        if len(args) == 1 and isinstance(args[0], str):
            parsed = self._parse_timestamp_string(args[0])
            if parsed is not None:
                return parsed
            self._error("timestamp() could not parse date string")
        if len(args) == 1:
            # series/int ms pass-through
            c = self._coerce_timestamp_component(args[0], required=True)
            return int(c or 0)

        # Optional leading timezone (string or non-year): ignored — components as UTC
        # e.g. timestamp("GMT", 2019, 8, 5, 12, 0) or timestamp(syminfo.timezone, y, m, d, 0, 0)
        comp = list(args)
        if comp:
            first = comp[0]
            if isinstance(first, str):
                if len(comp) >= 4:
                    comp = comp[1:]
                else:
                    parsed = self._parse_timestamp_string(str(first))
                    if parsed is not None:
                        return parsed
                    self._error("timestamp() could not parse date string")
            elif len(comp) >= 4:
                # Non-string timezone placeholder (None / enum) before year
                year_guess = self._coerce_timestamp_component(first, required=False)
                if year_guess is None or not (1900 <= year_guess <= 2200):
                    comp = comp[1:]

        if len(comp) < 3:
            msg = "timestamp() requires year, month, day"
            self._error(msg)
        year = self._coerce_timestamp_component(comp[0], required=True)
        month = self._coerce_timestamp_component(comp[1], required=True)
        day = self._coerce_timestamp_component(comp[2], required=True)
        hour = self._coerce_timestamp_component(comp[3] if len(comp) > 3 else 0, default=0)
        minute = self._coerce_timestamp_component(comp[4] if len(comp) > 4 else 0, default=0)
        second = self._coerce_timestamp_component(comp[5] if len(comp) > 5 else 0, default=0)
        assert year is not None and month is not None and day is not None
        assert hour is not None and minute is not None and second is not None

        try:
            return _timestamp_ms_from_components(
                int(year), int(month), int(day), int(hour), int(minute), int(second)
            )
        except (ValueError, OSError, OverflowError) as e:
            self._error(f"Invalid date/time arguments: {e}")
            return 0
