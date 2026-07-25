# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


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
            except Exception:
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

    def _builtin_time(self, args: list[Any]) -> int:
        """Get timestamp for bar start time.

        time(timezone, session, expression, lookback, gaps, lookahead,
             ignore_invalid_timezone, timeframe, bars_back, timeframe_bars_back)

        Added October 2025: timeframe_bars_back parameter for calculating timestamps
        relative to a specific timeframe's bars.

        Parameters:
            timezone: Timezone string (e.g., "UTC", "America/New_York")
            session: Session filter (e.g., "regular", "extended")
            expression: Expression to evaluate
            lookback: Number of bars back to look
            gaps: Gap handling ("na", "barmerge.gaps")
            lookahead: Lookahead mode ("na", "barmerge.lookahead")
            ignore_invalid_timezone: Ignore invalid timezone errors
            timeframe: Timeframe for calculation
            bars_back: Bar offset on main timeframe
            timeframe_bars_back: Bar offset on specified timeframe (October 2025 feature)

        Returns Unix timestamp in milliseconds.
        """
        # Mock implementation - returns current time
        # In real implementation, would handle all parameters
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _builtin_year(self, args: list[Any]) -> int:
        """Extract year from timestamp."""
        if len(args) != 1:
            self._error("year() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("year() requires a numeric timestamp")
        # PineScript timestamps are in milliseconds
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.year

    def _builtin_month(self, args: list[Any]) -> int:
        """Extract month from timestamp (1-12)."""
        if len(args) != 1:
            self._error("month() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("month() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.month

    def _builtin_dayofmonth(self, args: list[Any]) -> int:
        """Extract day of month from timestamp (1-31)."""
        if len(args) != 1:
            self._error("dayofmonth() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("dayofmonth() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.day

    def _builtin_dayofweek(self, args: list[Any]) -> int:
        """Extract day of week from timestamp (1=Sunday, 7=Saturday)."""
        if len(args) != 1:
            self._error("dayofweek() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("dayofweek() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        # Python: 0=Monday, 6=Sunday; PineScript: 1=Sunday, 7=Saturday
        return ((dt.weekday() + 1) % 7) + 1

    def _builtin_hour(self, args: list[Any]) -> int:
        """Extract hour from timestamp (0-23)."""
        if len(args) != 1:
            self._error("hour() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("hour() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.hour

    def _builtin_minute(self, args: list[Any]) -> int:
        """Extract minute from timestamp (0-59)."""
        if len(args) != 1:
            self._error("minute() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("minute() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.minute

    def _builtin_second(self, args: list[Any]) -> int:
        """Extract second from timestamp (0-59)."""
        if len(args) != 1:
            self._error("second() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("second() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.second

    def _builtin_time_close(self, args: list[Any]) -> int:
        """Get close time of current bar.

        time_close(timezone, session, lookback, gaps, lookahead,
                   ignore_invalid_timezone, timeframe, bars_back, timeframe_bars_back)

        Added October 2025: timeframe_bars_back parameter for calculating timestamps
        relative to a specific timeframe's bars.
        Added May 2025: Improved behavior on tick charts and price-based charts
        (Renko, Kagi, line break, point & figure, range).

        Parameters:
            timezone: Timezone string (e.g., "UTC", "America/New_York")
            session: Session filter
            lookback: Number of bars back to look
            gaps: Gap handling
            lookahead: Lookahead mode
            ignore_invalid_timezone: Ignore invalid timezone errors
            timeframe: Timeframe for calculation
            bars_back: Bar offset on main timeframe
            timeframe_bars_back: Bar offset on specified timeframe (October 2025 feature)

        Returns Unix timestamp in milliseconds.
        """
        # Mock implementation - returns close time of current bar
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _builtin_time_tradingday(self, args: list[Any]) -> int:
        """Get trading day timestamp (midnight UTC of current trading day)."""
        if args:
            self._error("time_tradingday() takes no arguments")
        # Return current date at midnight UTC (trading day boundary)
        now = datetime.now(timezone.utc)
        trading_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int(trading_day.timestamp() * 1000)

    def _builtin_weekofyear(self, args: list[Any]) -> int:
        """Get week number of the year (1-53)."""
        if len(args) != 1:
            self._error("weekofyear() takes exactly one argument (timestamp)")
        ts = args[0]
        if not isinstance(ts, (int, float)):
            self._error("weekofyear() requires a numeric timestamp")
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return dt.isocalendar()[1]

    def _builtin_timestamp(self, args: list[Any]) -> int:
        """Create Unix timestamp from date/time components."""
        if len(args) < 3:
            msg = "timestamp() requires year, month, day"
            self._error(msg)
        year = args[0]
        month = args[1]
        day = args[2]
        hour = args[3] if len(args) > 3 else 0
        minute = args[4] if len(args) > 4 else 0
        second = args[5] if len(args) > 5 else 0

        for val in [year, month, day, hour, minute, second]:
            if not isinstance(val, (int, float)):
                self._error("timestamp() arguments must be numeric")

        try:
            dt = datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute),
                int(second),
                tzinfo=timezone.utc,
            )
            # Return milliseconds since epoch (PineScript standard)
            return int(dt.timestamp() * 1000)
        except (ValueError, OSError) as e:
            # Raise evaluation error; function _error will likely raise an exception
            self._error(f"Invalid date/time arguments: {e}")
            # For type-checkers, ensure a return value is present
            return 0
