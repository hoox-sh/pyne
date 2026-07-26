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

    def _bar_time_ms(self, key: str = "time") -> int:
        """Current bar open/close time from context (ms), falling back to *time*."""
        ctx = getattr(self, "context", {}) or {}
        if key in ctx:
            return int(self._coerce_ctx_number(key, 0))
        return int(self._coerce_ctx_number("time", 0))

    def _resolve_timestamp_arg(self, args: list[Any], *, name: str) -> float | None:
        """Resolve optional timestamp arg; bare form uses chart ``time``.

        Returns ``None`` (Pine ``na``) when the timestamp is missing — TV's
        ``year(na)`` / ``month(na)`` yield ``na`` rather than runtime.error.
        """
        if len(args) == 0:
            return float(self._bar_time_ms("time"))
        if len(args) != 1:
            self._error(f"{name}() takes zero or one argument (timestamp)")
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

    def _builtin_timestamp(self, args: list[Any]) -> int:
        """Create Unix timestamp from date/time components.

        Accepts overflow/underflow on day (e.g. day=40 or day=-5) via month
        rollover, matching TradingView ``timestamp`` arithmetic used by scripts
        such as dividend_yield.
        """
        if len(args) < 3:
            msg = "timestamp() requires year, month, day"
            self._error(msg)
        year = self._coerce_timestamp_component(args[0], required=True)
        month = self._coerce_timestamp_component(args[1], required=True)
        day = self._coerce_timestamp_component(args[2], required=True)
        hour = self._coerce_timestamp_component(args[3] if len(args) > 3 else 0, default=0)
        minute = self._coerce_timestamp_component(args[4] if len(args) > 4 else 0, default=0)
        second = self._coerce_timestamp_component(args[5] if len(args) > 5 else 0, default=0)
        assert year is not None and month is not None and day is not None
        assert hour is not None and minute is not None and second is not None

        try:
            # Anchor on day 1 then add (day-1) so day overflow/underflow rolls months.
            from datetime import timedelta

            base = datetime(int(year), int(month), 1, int(hour), int(minute), int(second), tzinfo=timezone.utc)
            dt = base + timedelta(days=int(day) - 1)
            return int(dt.timestamp() * 1000)
        except (ValueError, OSError, OverflowError) as e:
            self._error(f"Invalid date/time arguments: {e}")
            return 0
