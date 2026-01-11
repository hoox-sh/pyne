# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
        }

    def _builtin_time(self, args: list[Any]) -> int:
        """Get current time in Unix timestamp (milliseconds)."""
        if args:
            self._error("time() takes no arguments")
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
        """Get close time of current bar (same as time in most contexts)."""
        if args:
            self._error("time_close() takes no arguments")
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
