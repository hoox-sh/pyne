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

import re

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import lru_cache
from typing import Any


try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover — Python < 3.9
    ZoneInfo = None  # type: ignore[misc, assignment]

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


def _normalize_year_month(year: int | float, month: int | float) -> tuple[int, int]:
    """Normalize year/month for ``datetime`` construction (shared by timestamp).

    Rules (set05 residual / TV-like leniency):

    - **Floats** are truncated toward zero via ``int(...)`` (``3.9`` → March).
    - **Month 0 → January** of the same year. Corpus scripts use
      ``timestamp(2020, 0, 0, …)`` as a backtest start; treating 0 as a
      0-based / unset month (January) matches that intent better than rolling
      to the previous December.
    - **Month 13+ and negatives** roll across years (``13`` → Jan next year,
      ``14`` → Feb next year, ``-1`` → Nov previous year). Same spirit as day
      overflow via ``timedelta``.
    - **Year** is clamped to Python ``datetime`` range **1..9999**. Far-future
      backtest ends such as ``999999`` become year ``9999`` (end of range).
    """
    y = int(year)
    m = int(month)
    if m == 0:
        m = 1
    elif m < 1 or m > 12:
        m0 = m - 1
        y += m0 // 12
        m = m0 % 12 + 1
    if y < 1:
        y = 1
    elif y > 9999:
        y = 9999
    return y, m


@lru_cache(maxsize=4096)
def _timestamp_ms_from_components(  # noqa: PLR0913 — year..second + optional UTC offset
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    offset_seconds: int = 0,
) -> int:
    """Unix ms for calendar components with TV-like overflow normalization.

    Cached: scripts often call ``timestamp(y, m, d, h, mi, s)`` with the same
    literals inside hot loops (e.g. TradingView "loop is too long" samples).

    *offset_seconds* is the fixed UTC offset of the local timezone
    (e.g. ``UTC-5`` → ``-5 * 3600``). Components are interpreted in that zone.

    Normalization is shared with hour/day overflow:

    - **year/month** via :func:`_normalize_year_month` (month 0 → January;
      13+ rolls years; year clamped to 1..9999).
    - **day/hour/minute/second** via ``timedelta`` on a day-1 midnight anchor
      (``hour=24`` → next day 00:00; ``day=40`` rolls months; ``minute=60`` →
      +1 hour). Avoids ``datetime()`` constructor range errors.
    """
    y, m = _normalize_year_month(year, month)

    tz = timezone.utc if offset_seconds == 0 else timezone(timedelta(seconds=int(offset_seconds)))
    # Midnight day-1 anchor + full timedelta so day/hour/min/sec may overflow
    # (datetime() constructor rejects hour not in 0..23, month not in 1..12).
    base = datetime(y, m, 1, 0, 0, 0, tzinfo=tz)
    dt = base + timedelta(days=int(day) - 1, hours=int(hour), minutes=int(minute), seconds=int(second))
    return int(dt.timestamp() * 1000)


def _fixed_offset_tz(sign: str, hours: int, mins: int) -> timezone:
    mult = 1 if sign == "+" else -1
    return timezone(mult * timedelta(hours=hours, minutes=mins))


def _parse_pine_timezone(tz_spec: Any) -> Any:  # noqa: PLR0911 — early-exit coerce ladder
    """Parse a Pine timezone string into a ``tzinfo`` (UTC on failure / empty).

    Accepts:
    - bare ``UTC`` / ``GMT`` / unresolved ``syminfo.timezone``
    - ``UTC±H``, ``GMT±H``, ``UTC±H:MM``, ``UTC±HHMM``
    - IANA names via ``zoneinfo`` when available (``America/New_York``)
    """
    if tz_spec is None:
        return timezone.utc
    current = getattr(tz_spec, "current", None)
    if current is not None and not isinstance(tz_spec, (str, bytes, int, float)):
        tz_spec = current
    if not isinstance(tz_spec, str):
        return timezone.utc
    z = tz_spec.strip()
    if not z or z in {"syminfo.timezone", "UTC", "utc", "Etc/UTC", "GMT", "gmt"}:
        return timezone.utc

    # GMT/UTC with numeric offset (optional minutes), or bare ±H[:MM]
    m = re.fullmatch(
        r"(?:(?:UTC|GMT)\s*)?([+-])\s*(\d{1,2})(?::(\d{2})|(\d{2}))?",
        z,
        re.I,
    )
    if m:
        return _fixed_offset_tz(m.group(1), int(m.group(2)), int(m.group(3) or m.group(4) or 0))

    if ZoneInfo is not None:
        try:
            return ZoneInfo(z)
        except Exception:
            return timezone.utc
    return timezone.utc


def _tz_offset_seconds(tzinfo: Any, ref: datetime | None = None) -> int:
    """Fixed offset seconds for *tzinfo* at *ref* (or epoch); 0 if unknown."""
    if tzinfo is None or tzinfo is timezone.utc:
        return 0
    try:
        anchor = ref if ref is not None else datetime(2000, 1, 1, tzinfo=timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        # Convert anchor into tz then read utcoffset
        local = anchor.astimezone(tzinfo)
        off = local.utcoffset()
        return 0 if off is None else int(off.total_seconds())
    except Exception:
        return 0


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
            "timenow": self._builtin_timenow,
            "max_bars_back": self._builtin_max_bars_back,
            # Community / v3-style series shift (Ichimoku lead lines, etc.)
            "offset": self._builtin_offset,
            # Dual-mode: property (0-arg) + function (tickerid) — see ticker.split_symbol
            "syminfo.prefix": self._builtin_syminfo_prefix,
            "syminfo.ticker": self._builtin_syminfo_ticker,
        }

    def _builtin_offset(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        """``offset(source, length)`` — series lookback, equivalent to ``source[length]``.

        Used by community scripts (esp. Ichimoku) as a bare helper. Pine has no
        official global ``offset()``; plot ``offset=`` is display-only. When the
        source is a :class:`PineSeries` (or list), return the value *length* bars
        ago; scalars with no history return themselves for ``length==0`` and
        ``na`` otherwise.
        """
        kw = kwargs or {}
        if not args and "source" not in kw:
            self._error("offset takes source and optional length")
        source = args[0] if args else kw.get("source")
        length_raw = args[1] if len(args) > 1 else kw.get("length", kw.get("offset", 0))
        try:
            length = int(float(length_raw)) if length_raw is not None else 0
        except (TypeError, ValueError):
            length = 0
        if length < 0:
            length = 0

        # PineSeries / history wrappers (most-recent-first)
        hist = getattr(source, "history", None)
        if hist is not None:
            try:
                if length < len(hist):
                    return hist[length]
                return None
            except Exception:
                cur = getattr(source, "current", None)
                return cur if length == 0 else None

        # Chronological list series (oldest first)
        if isinstance(source, list):
            if not source:
                return None
            if length == 0:
                return source[-1]
            idx = len(source) - 1 - length
            return source[idx] if idx >= 0 else None

        # Scalar / na
        if length == 0:
            return source
        return None

    def _syminfo_host(self) -> Any:
        """Return the host ``syminfo`` object from context, if any."""
        ctx = getattr(self, "context", {}) or {}
        return ctx.get("syminfo")

    def _syminfo_tickerid_fallback(self) -> str:
        """Best-effort chart ticker id for zero-arg ``syminfo.*`` properties."""
        ctx = getattr(self, "context", {}) or {}
        flat = ctx.get("syminfo.tickerid")
        if flat is not None and str(flat):
            return str(flat)
        host = ctx.get("syminfo")
        if host is not None:
            for attr in ("tickerid", "name", "ticker"):
                val = getattr(host, attr, None)
                if val is not None and str(val):
                    return str(val)
        return ""

    def _builtin_syminfo_prefix(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        """``syminfo.prefix`` / ``syminfo.prefix(tickerid)``.

        Zero-arg returns the chart exchange prefix; one-arg parses the given
        ticker id (``"NASDAQ:AAPL"`` → ``"NASDAQ"``).
        """
        from .ticker import extract_prefix

        kw = kwargs or {}
        if args or "tickerid" in kw or "symbol" in kw:
            symbol = args[0] if args else kw.get("tickerid", kw.get("symbol"))
            return extract_prefix(symbol)

        host = self._syminfo_host()
        if host is not None:
            p = getattr(host, "prefix", None)
            if p is not None and str(p) != "":
                return str(p)
            # Derive when host left prefix empty (bare ``AAPL`` chart symbol).
            return extract_prefix(self._syminfo_tickerid_fallback())
        flat = (getattr(self, "context", {}) or {}).get("syminfo.prefix")
        if flat is not None:
            return str(flat)
        return extract_prefix(self._syminfo_tickerid_fallback())

    def _builtin_syminfo_ticker(self, args: list[Any], kwargs: dict[str, Any] | None = None) -> str:
        """``syminfo.ticker`` / ``syminfo.ticker(tickerid)``.

        Zero-arg returns the chart ticker without exchange; one-arg parses the
        given ticker id (``"NASDAQ:AAPL"`` → ``"AAPL"``).
        """
        from .ticker import extract_ticker

        kw = kwargs or {}
        if args or "tickerid" in kw or "symbol" in kw:
            symbol = args[0] if args else kw.get("tickerid", kw.get("symbol"))
            return extract_ticker(symbol)

        host = self._syminfo_host()
        if host is not None:
            t = getattr(host, "ticker", None)
            if t is not None and str(t) != "":
                return str(t)
            # Prefer name when it is the bare ticker; else parse tickerid.
            name = getattr(host, "name", None)
            if name is not None and ":" not in str(name) and str(name):
                return str(name)
            return extract_ticker(self._syminfo_tickerid_fallback())
        flat = (getattr(self, "context", {}) or {}).get("syminfo.ticker")
        if flat is not None:
            return str(flat)
        return extract_ticker(self._syminfo_tickerid_fallback())

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

    def _builtin_timenow(self, _args: list[Any], kwargs: dict[str, Any] | None = None) -> int:
        """Current UNIX time in ms (TV ``timenow``).

        Hosts may seed ``context['timenow']``. Otherwise prefer the dataset's
        last bar time (deterministic backtests / corpus), then the current bar
        ``time``, then wall-clock UTC ms.
        """
        ctx = getattr(self, "context", {}) or {}
        if "timenow" in ctx:
            raw = ctx.get("timenow")
            # Avoid recursion if the map entry is this handler itself
            if raw is not None and not callable(raw):
                current = getattr(raw, "current", None)
                if current is not None and not isinstance(raw, (int, float, str)):
                    raw = current
                try:
                    return int(float(raw))  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    pass
        if "last_bar_time" in ctx:
            return int(self._coerce_ctx_number("last_bar_time", 0))
        t = int(self._coerce_ctx_number("time", 0))
        if t:
            return t
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _bar_time_ms(self, key: str = "time") -> int:
        """Current bar open/close time from context (ms), falling back to *time*."""
        ctx = getattr(self, "context", {}) or {}
        if key in ctx:
            return int(self._coerce_ctx_number(key, 0))
        return int(self._coerce_ctx_number("time", 0))

    def _resolve_timestamp_arg(
        self, args: list[Any], *, name: str
    ) -> tuple[float | None, Any]:
        """Resolve optional timestamp + timezone; bare form uses chart ``time``.

        Forms (TV):
        - ``hour()`` / bare series
        - ``hour(time)``
        - ``hour(time, timezone)`` e.g. ``hour(timenow, \"UTC-5\")``

        *time* may be a scalar ms, series wrapper (``.current``), or a list
        series sample (last element). Returns ``(None, tz)`` (Pine ``na``) when
        the timestamp is missing — TV's ``year(na)`` yields ``na``.
        """
        tzinfo: Any = timezone.utc
        if len(args) == 0:
            return float(self._bar_time_ms("time")), tzinfo
        if len(args) > 2:
            self._error(f"{name}() takes at most two arguments (time, timezone)")
        if len(args) >= 2:
            tzinfo = _parse_pine_timezone(args[1])

        ts = args[0]
        # Unwrap series wrappers (PineSeries / _SeriesResult)
        current = getattr(ts, "current", None)
        if current is not None and not isinstance(ts, (list, tuple, str, bytes, int, float)):
            ts = current
        # List/tuple series samples → current (last) bar
        if isinstance(ts, (list, tuple)) and not isinstance(ts, (str, bytes)):
            if not ts:
                return None, tzinfo
            ts = ts[-1]
            current = getattr(ts, "current", None)
            if current is not None and not isinstance(ts, (list, tuple, str, bytes, int, float)):
                ts = current
        if ts is None:
            return None, tzinfo
        # _NaValue / non-numeric → na
        if type(ts).__name__ == "_NaValue":
            return None, tzinfo
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            try:
                ts = float(ts)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None, tzinfo
        return float(ts), tzinfo

    def _dt_from_ts(self, ts: float | None, tzinfo: Any = None):
        """datetime from ms timestamp in *tzinfo* (default UTC), or None if na."""
        if ts is None:
            return None
        if tzinfo is None:
            tzinfo = timezone.utc
        try:
            return datetime.fromtimestamp(ts / 1000, tz=tzinfo)
        except (ValueError, OSError, OverflowError, TypeError):
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
        ts, tz = self._resolve_timestamp_arg(args, name="year")
        dt = self._dt_from_ts(ts, tz)
        return None if dt is None else dt.year

    def _builtin_month(self, args: list[Any]) -> int | None:
        """Extract month from timestamp (1-12; bare form uses chart time)."""
        ts, tz = self._resolve_timestamp_arg(args, name="month")
        dt = self._dt_from_ts(ts, tz)
        return None if dt is None else dt.month

    def _builtin_dayofmonth(self, args: list[Any]) -> int | None:
        """Extract day of month from timestamp (1-31; bare form uses chart time)."""
        ts, tz = self._resolve_timestamp_arg(args, name="dayofmonth")
        dt = self._dt_from_ts(ts, tz)
        return None if dt is None else dt.day

    def _builtin_dayofweek(self, args: list[Any]) -> int | None:
        """Extract day of week from timestamp (1=Sunday, 7=Saturday)."""
        ts, tz = self._resolve_timestamp_arg(args, name="dayofweek")
        dt = self._dt_from_ts(ts, tz)
        if dt is None:
            return None
        # Python: 0=Monday, 6=Sunday; PineScript: 1=Sunday, 7=Saturday
        return ((dt.weekday() + 1) % 7) + 1

    def _builtin_hour(self, args: list[Any]) -> int | None:
        """Extract hour from timestamp (0-23; bare form uses chart time)."""
        ts, tz = self._resolve_timestamp_arg(args, name="hour")
        dt = self._dt_from_ts(ts, tz)
        return None if dt is None else dt.hour

    def _builtin_minute(self, args: list[Any]) -> int | None:
        """Extract minute from timestamp (0-59; bare form uses chart time)."""
        ts, tz = self._resolve_timestamp_arg(args, name="minute")
        dt = self._dt_from_ts(ts, tz)
        return None if dt is None else dt.minute

    def _builtin_second(self, args: list[Any]) -> int | None:
        """Extract second from timestamp (0-59; bare form uses chart time)."""
        ts, tz = self._resolve_timestamp_arg(args, name="second")
        dt = self._dt_from_ts(ts, tz)
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
            ts, _tz = self._resolve_timestamp_arg(args[:1], name="time_tradingday")
            if ts is None:
                ts = float(self._bar_time_ms("time"))
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
        ts, tz = self._resolve_timestamp_arg(args, name="weekofyear")
        dt = self._dt_from_ts(ts, tz)
        return None if dt is None else dt.isocalendar()[1]

    def _coerce_timestamp_component(self, value: Any, *, default: int | None = 0, required: bool = False) -> int | None:
        """Coerce a timestamp() component to int.

        Soft-coerce policy (set05 residual):

        - ``na`` / ``None`` / NaN → ``None`` when *required* (caller returns na),
          else *default* (optional hour/minute/second).
        - Numeric strings (``\"2024\"``, ``\" 1.0 \"``) via ``int(float(...))``.
        - Series wrappers unwrap ``.current``.
        - Unparseable non-numeric strings still hard-error (not silently zero).
        """
        if value is None or type(value).__name__ == "_NaValue":
            return None if required else default
        current = getattr(value, "current", None)
        if current is not None and not isinstance(value, (list, tuple, str, bytes, int, float)):
            value = current
        if value is None or type(value).__name__ == "_NaValue":
            return None if required else default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, float):
            if value != value:  # NaN
                return None if required else default
            return int(value)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None if required else default
            try:
                return int(float(s))
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
        - ``2022-01-01T00:00:00+0000`` / ``2013-01-01T00:00:00+08:00`` (ISO+offset)
        - ``2021 01 01`` (space-separated Y M D)
        - ``15Aug 2022 14:00 +0000`` (missing day/month space)
        - ``01 Sept 2021 06:00`` / ``1 Janv 2020`` (month aliases)
        - ``UTC 01 Jan 2020 00:00`` (leading UTC/GMT)
        - ``01 Jan 2000 00:00:00 GMT+10``, ``UTC-5``, ``+0300``, ``+000``
        - ``0000-01-01 09:00:00`` (year 0 → year 1 for Python datetime)
        """
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
            # ISO (space or T separator)
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
            # Space-separated numeric: "2021 01 01"
            "%Y %m %d %H:%M:%S",
            "%Y %m %d %H:%M",
            "%Y %m %d",
        )

        def _normalize(s: str) -> str:
            """Light, loss-safe normalizations before strptime."""
            s = re.sub(r"\s+", " ", s.strip())
            # Python datetime year range is 1..9999; TV session templates use 0000.
            s = re.sub(r"\b0000-", "0001-", s)
            # Odd colon between date and time: "2021-01-13:05:00" → space.
            s = re.sub(r"(\d{4}-\d{2}-\d{2}):(\d{1,2}:\d{2})", r"\1 \2", s)
            # Missing space between day and month name: "15Aug 2022" → "15 Aug 2022".
            # Require 3+ letters so ISO "T" is not split ("2022-01-01T00:00").
            s = re.sub(r"(\d)([A-Za-z]{3,})", r"\1 \2", s)
            # English/French month aliases seen in corpus (strptime %b is Sep/Jan).
            s = re.sub(r"\bSept\b", "Sep", s, flags=re.I)
            s = re.sub(r"\bJanv\b", "Jan", s, flags=re.I)
            return s

        def _offset_from_h_m(sign: str, hours: int, mins: int) -> timedelta:
            mult = 1 if sign == "+" else -1
            return mult * timedelta(hours=hours, minutes=mins)

        def _offset_from_digits(sign: str, digits: str) -> timedelta | None:
            """Interpret 1-4 digit numeric offsets: H, HH, HMM/0HH, HHMM."""
            if not digits or len(digits) > 4 or not digits.isdigit():
                return None
            if len(digits) <= 2:
                hours, mins = int(digits), 0
            else:
                # 3-digit: pad left so +000 → 0000, +530 → 0530
                padded = digits.zfill(4)
                hours, mins = int(padded[:2]), int(padded[2:])
            return _offset_from_h_m(sign, hours, mins)

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

        def _strip_timezone(s: str) -> tuple[str, timedelta]:
            """Return (date_part, offset) after removing a trailing/leading TZ token."""
            tz_offset = timedelta(0)

            # Leading "UTC ..." / "GMT ..." (offset 0 unless suffix also present later)
            m = re.match(r"^(?:UTC|GMT)\s+", s, re.I)
            if m:
                s = s[m.end() :].strip()

            # 1) GMT/UTC[+/-H[:MM]] — may omit space: "GMT+10", "UTC-5"
            m = re.search(
                r"\s*(?:GMT|UTC)\s*([+-])(\d{1,2})(?::?(\d{2}))?\s*$",
                s,
                re.I,
            )
            if m:
                tz_offset = _offset_from_h_m(m.group(1), int(m.group(2)), int(m.group(3) or 0))
                return s[: m.start()].strip(), tz_offset

            # 2) Trailing Z (Zulu)
            m = re.search(r"Z\s*$", s, re.I)
            if m and len(s) > 1:
                return s[: m.start()].strip(), tz_offset

            # 3) Spaced +HH:MM
            m = re.search(r"\s+([+-])(\d{1,2}):(\d{2})\s*$", s)
            if m:
                tz_offset = _offset_from_h_m(m.group(1), int(m.group(2)), int(m.group(3)))
                return s[: m.start()].strip(), tz_offset

            # 4) Spaced numeric offset: +0000, +000, +0530, +5 (1-4 digits)
            m = re.search(r"\s+([+-])(\d{1,4})\s*$", s)
            if m:
                off = _offset_from_digits(m.group(1), m.group(2))
                if off is not None:
                    return s[: m.start()].strip(), off

            # 5) ISO-attached (no space) after a digit: +08:00 / +0300 / +00:00
            m = re.search(r"(?<=\d)([+-])(\d{2}):(\d{2})\s*$", s)
            if m:
                tz_offset = _offset_from_h_m(m.group(1), int(m.group(2)), int(m.group(3)))
                return s[: m.start()].strip(), tz_offset

            m = re.search(r"(?<=\d)([+-])(\d{4})\s*$", s)
            if m:
                off = _offset_from_digits(m.group(1), m.group(2))
                if off is not None:
                    return s[: m.start()].strip(), off

            m = re.search(r"(?<=\d)([+-])(\d{2})\s*$", s)
            if m:
                # Only if looks like a time-attached offset (preceded by time-ish colon)
                head = s[: m.start()]
                if re.search(r"\d{1,2}:\d{2}$", head) or head.endswith("T") or re.search(r"T\d", head):
                    off = _offset_from_digits(m.group(1), m.group(2))
                    if off is not None:
                        return head.strip(), off

            # 6) Drop bare trailing GMT/UTC without offset
            s2 = re.sub(r"\s+(?:GMT|UTC)\s*$", "", s, flags=re.I).strip()
            return s2, tz_offset

        s_norm = _normalize(s0)

        # Try without timezone first so ISO dates like "2023-01-01" are not
        # misread as a bare "-01" UTC offset by the suffix stripper below.
        parsed = _try_formats(s_norm, timedelta(0))
        if parsed is not None:
            return parsed

        s, tz_offset = _strip_timezone(s_norm)
        s = _normalize(s)
        if not s:
            return None
        return _try_formats(s, tz_offset)

    def _builtin_timestamp(self, args: list[Any]) -> int | None:
        """Create Unix timestamp from date/time components or a date string.

        Forms:
        - ``timestamp(\"Dec 01 2021 23:59:59\")``
        - ``timestamp(\"01 Jan 2000 00:00:00 GMT+10\")``
        - ``timestamp(year, month, day[, hour, minute, second])``
        - ``timestamp(timezone, year, month, day[, hour, minute, second])``
          e.g. ``timestamp(\"GMT\", 2019, 8, 5, 12, 0)`` or
          ``timestamp(syminfo.timezone, y, m, d, 0, 0)``
        - kwargs: ``timestamp(timezone=…, year=…, month=…, day=…, …)``

        Accepts overflow/underflow on month/day/hour/minute/second (e.g.
        month=0 → January, month=13 → next Jan, day=40, hour=24, minute=60)
        via calendar rollover, matching TradingView ``timestamp`` arithmetic
        used by dividend_yield and backtest windows (``ToYear=9999`` /
        ``999999`` clamped to 9999).

        ``na`` year/month/day soft-returns ``na`` (None) rather than hard-failing
        (set05 residual: ``year(timenow)`` before ``timenow`` was wired).

        Timezone-first form interprets components in that zone and returns UTC ms.
        """
        n = len(args)
        # Hot path: year-first form with plain int/float components (no TZ string).
        # Nested-loop corpus demos re-evaluate ``timestamp(2017, 02, 23, 00, 00)``
        # hundreds of thousands of times; skip coerce/timezone detection and hit
        # the lru_cache on ``_timestamp_ms_from_components`` immediately.
        if n >= 3:
            a0 = args[0]
            t0 = type(a0)
            if t0 is int or t0 is float:
                pure = True
                for a in args:
                    ta = type(a)
                    if ta is not int and ta is not float:
                        pure = False
                        break
                if pure:
                    return _timestamp_ms_from_components(
                        int(args[0]),
                        int(args[1]),
                        int(args[2]),
                        int(args[3]) if n > 3 else 0,
                        int(args[4]) if n > 4 else 0,
                        int(args[5]) if n > 5 else 0,
                        0,
                    )

        # Single string form
        if n == 1 and isinstance(args[0], str):
            parsed = self._parse_timestamp_string(args[0])
            if parsed is not None:
                return parsed
            self._error("timestamp() could not parse date string")
        if n == 1:
            # series/int ms pass-through
            c = self._coerce_timestamp_component(args[0], required=True)
            if c is None:
                return None
            return int(c)

        # Optional leading timezone (string or non-year placeholder)
        # e.g. timestamp("UTC-5", 2019, 8, 5, 12, 0) or timestamp(syminfo.timezone, y, m, d, 0, 0)
        # Numeric first args are always the year (never a timezone). Far-future
        # backtest ends (defval=9999 / 999999) clamp later via _normalize_year_month.
        # Pure numeric *strings* (\"2024\") are years, not timezone names.
        comp = list(args)
        tzinfo: Any = timezone.utc
        if comp:
            first = comp[0]
            if isinstance(first, str):
                stripped = first.strip()
                is_numeric_str = bool(stripped) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?", stripped)
                if len(comp) >= 4 and not is_numeric_str:
                    tzinfo = _parse_pine_timezone(first)
                    comp = comp[1:]
                elif len(comp) < 4 or not is_numeric_str:
                    # Date-string form (1–3 args) or non-numeric short form
                    if len(comp) < 4:
                        parsed = self._parse_timestamp_string(str(first))
                        if parsed is not None:
                            return parsed
                        self._error("timestamp() could not parse date string")
                    # else: pure numeric string year kept in comp
            elif first is None and len(comp) >= 4:
                # kwargs merge padding for omitted timezone= slot
                comp = comp[1:]
            elif len(comp) >= 4:
                # Non-string leading slot: only skip when it is *not* a year
                # number. Any numeric value (including 999999 / 3333) is year;
                # far-future years are clamped later. Non-numeric (NA / enum /
                # timezone objects) is treated as a timezone placeholder.
                year_guess = self._coerce_timestamp_component(first, required=False)
                if year_guess is None:
                    # Leading na timezone slot (kwargs) vs na year — if remaining
                    # looks like y,m,d keep treating first as omitted timezone.
                    tzinfo = _parse_pine_timezone(first)
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
        # Required components na → timestamp() yields na (TV-like soft fail)
        if year is None or month is None or day is None:
            return None
        if hour is None:
            hour = 0
        if minute is None:
            minute = 0
        if second is None:
            second = 0

        try:
            y_ref, m_ref = _normalize_year_month(int(year), int(month))
            off = _tz_offset_seconds(
                tzinfo,
                datetime(y_ref, m_ref, 1, tzinfo=timezone.utc),
            )
            return _timestamp_ms_from_components(
                int(year), int(month), int(day), int(hour), int(minute), int(second), off
            )
        except (ValueError, OSError, OverflowError) as e:
            self._error(f"Invalid date/time arguments: {e}")
            return 0


# Named-parameter order for list-style time helpers (Pine kwargs).
_TIME_PART_KWARG_ORDER = ["time", "timezone"]
UtilityFunctionsMixin._builtin_year._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_month._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_dayofmonth._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_dayofweek._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_hour._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_minute._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_second._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_weekofyear._KWARG_ORDER = _TIME_PART_KWARG_ORDER
UtilityFunctionsMixin._builtin_timestamp._KWARG_ORDER = [
    "timezone",
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
]
