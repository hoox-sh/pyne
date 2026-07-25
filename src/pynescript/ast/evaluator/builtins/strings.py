# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import datetime
import re

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


UNARY = 1
BINARY = 2
TERNARY = 3


class StringBuiltinsMixin(BuiltinDispatchMixin):
    """String-related built-in functions."""

    def _string_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "str.length": self._builtin_str_length,
            "str.upper": self._builtin_str_upper,
            "str.lower": self._builtin_str_lower,
            "str.contains": self._builtin_str_contains,
            "str.startswith": self._builtin_str_startswith,
            "str.substring": self._builtin_str_substring,
            "str.endswith": self._builtin_str_endswith,
            "str.repeat": self._builtin_str_repeat,
            "str.replace": self._builtin_str_replace,
            "str.replace_all": self._builtin_str_replace_all,
            "str.split": self._builtin_str_split,
            "str.trim": self._builtin_str_trim,
            "str.tonumber": self._builtin_str_tonumber,
            "str.tostring": self._builtin_str_tostring,
            "str.format": self._builtin_str_format,
            "str.match": self._builtin_str_match,
            "str.pos": self._builtin_str_pos,
            "str.format_time": self._builtin_str_format_time,
            "str.join": self._builtin_str_join,
        }

    def _expect_string(self, value: Any, message: str) -> str:
        if not isinstance(value, str):
            self._error(message)
        return value

    def _expect_int(self, value: Any, message: str) -> int:
        if isinstance(value, float):
            if value == int(value):
                value = int(value)
            else:
                self._error(message)
        if not isinstance(value, int):
            self._error(message)
        return value

    def _builtin_str_length(self, args: list[Any]) -> int:
        if len(args) != UNARY:
            self._error("str.length takes a string argument")
        value = self._expect_string(
            args[0],
            "str.length takes a string argument",
        )
        return len(value)

    def _builtin_str_upper(self, args: list[Any]) -> str:
        if len(args) != UNARY:
            self._error("str.upper takes a string argument")
        value = self._expect_string(
            args[0],
            "str.upper takes a string argument",
        )
        return value.upper()

    def _builtin_str_lower(self, args: list[Any]) -> str:
        if len(args) != UNARY:
            self._error("str.lower takes a string argument")
        value = self._expect_string(
            args[0],
            "str.lower takes a string argument",
        )
        return value.lower()

    def _builtin_str_contains(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("str.contains takes two string arguments")
        haystack = self._expect_string(
            args[0],
            "str.contains takes two string arguments",
        )
        needle = self._expect_string(
            args[1],
            "str.contains takes two string arguments",
        )
        return needle in haystack

    def _builtin_str_startswith(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("str.startswith takes two string arguments")
        value = self._expect_string(
            args[0],
            "str.startswith takes two string arguments",
        )
        prefix = self._expect_string(
            args[1],
            "str.startswith takes two string arguments",
        )
        return value.startswith(prefix)

    def _builtin_str_substring(self, args: list[Any]) -> str:
        if len(args) == BINARY:
            value = self._expect_string(
                args[0],
                "str.substring takes string and 1-2 ints",
            )
            start = self._expect_int(
                args[1],
                "str.substring takes string and 1-2 ints",
            )
            return value[start:]
        if len(args) == TERNARY:
            value = self._expect_string(
                args[0],
                "str.substring takes string and 1-2 ints",
            )
            start = self._expect_int(
                args[1],
                "str.substring takes string and 1-2 ints",
            )
            end = self._expect_int(
                args[2],
                "str.substring takes string and 1-2 ints",
            )
            return value[start:end]
        self._error("str.substring takes string and 1-2 ints")

    def _builtin_str_endswith(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("str.endswith takes two string arguments")
        value = self._expect_string(
            args[0],
            "str.endswith takes two string arguments",
        )
        suffix = self._expect_string(
            args[1],
            "str.endswith takes two string arguments",
        )
        return value.endswith(suffix)

    def _builtin_str_repeat(self, args: list[Any]) -> str:
        if len(args) != BINARY:
            self._error("str.repeat takes string and int")
        value = self._expect_string(
            args[0],
            "str.repeat takes string and int",
        )
        count = self._expect_int(
            args[1],
            "str.repeat takes string and int",
        )
        return value * count

    def _builtin_str_replace(self, args: list[Any]) -> str:
        if len(args) != TERNARY:
            self._error("str.replace takes three string arguments")
        value = self._expect_string(
            args[0],
            "str.replace takes three string arguments",
        )
        old = self._expect_string(
            args[1],
            "str.replace takes three string arguments",
        )
        new = self._expect_string(
            args[2],
            "str.replace takes three string arguments",
        )
        return value.replace(old, new, 1)

    def _builtin_str_replace_all(self, args: list[Any]) -> str:
        if len(args) != TERNARY:
            self._error("str.replace_all takes three strings")
        value = self._expect_string(
            args[0],
            "str.replace_all takes three strings",
        )
        old = self._expect_string(
            args[1],
            "str.replace_all takes three strings",
        )
        new = self._expect_string(
            args[2],
            "str.replace_all takes three strings",
        )
        return value.replace(old, new)

    def _builtin_str_split(self, args: list[Any]) -> list[str]:
        if len(args) == UNARY:
            value = self._expect_string(
                args[0],
                "str.split takes str and opt separator",
            )
            return value.split()
        if len(args) == BINARY:
            value = self._expect_string(
                args[0],
                "str.split takes str and opt separator",
            )
            sep = self._expect_string(
                args[1],
                "str.split takes str and opt separator",
            )
            return value.split(sep)
        self._error("str.split takes str and opt separator")

    def _builtin_str_trim(self, args: list[Any]) -> str:
        if len(args) != UNARY:
            self._error("str.trim takes a string argument")
        value = self._expect_string(
            args[0],
            "str.trim takes a string argument",
        )
        return value.strip()

    def _builtin_str_tonumber(self, args: list[Any]) -> float:
        if len(args) != UNARY:
            self._error("str.tonumber takes a string argument")
        value = self._expect_string(
            args[0],
            "str.tonumber takes a string argument",
        )
        return float(value)

    def _builtin_str_tostring(self, args: list[Any]) -> str:
        if len(args) != UNARY:
            self._error("str.tostring takes one argument")
        return str(args[0])

    def _builtin_str_format(self, args: list[Any]) -> str:
        if len(args) < BINARY:
            self._error("str.format takes format string and args")
        value = self._expect_string(
            args[0],
            "str.format takes format string and args",
        )
        return value.format(*args[1:])

    def _builtin_str_match(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("str.match takes pattern and string")
        pattern = self._expect_string(
            args[0],
            "str.match takes pattern and string",
        )
        value = self._expect_string(
            args[1],
            "str.match takes pattern and string",
        )
        return bool(re.match(pattern, value))

    def _builtin_str_pos(self, args: list[Any]) -> int:
        if len(args) != BINARY:
            self._error("str.pos takes substring and string")
        needle = self._expect_string(
            args[0],
            "str.pos takes substring and string",
        )
        haystack = self._expect_string(
            args[1],
            "str.pos takes substring and string",
        )
        return haystack.find(needle)

    def _builtin_str_format_time(self, args: list[Any]) -> str:
        if len(args) not in {BINARY, TERNARY}:
            self._error(
                "str.format_time takes timestamp, format, and optional timezone",
            )
        timestamp = args[0]
        if not isinstance(timestamp, int):
            self._error("str.format_time expects timestamp in milliseconds")
        format_str = self._expect_string(
            args[1],
            "str.format_time expects format string",
        )
        timezone_str = args[2] if len(args) == TERNARY else None
        if timezone_str is not None and not isinstance(timezone_str, str):
            self._error("str.format_time expects timezone to be a string")
        return self._format_time(timestamp, format_str, timezone_str)

    def _builtin_str_join(self, args: list[Any]) -> str:
        if len(args) != BINARY:
            self._error("str.join takes an array and a separator string")
        sequence = args[0]
        if not isinstance(sequence, list):
            self._error("str.join takes an array and a separator string")
        separator = self._expect_string(
            args[1],
            "str.join takes an array and a separator string",
        )
        return separator.join(str(item) for item in sequence)

    def _format_time(
        self,
        timestamp: int,
        format_str: str,
        timezone_str: str | None,
    ) -> str:
        tz = datetime.timezone.utc
        if timezone_str:
            try:
                if "GMT" in timezone_str:
                    offset_str = timezone_str.replace("GMT", "").strip()
                    if offset_str:
                        offset = int(offset_str)
                        tz = datetime.timezone(
                            datetime.timedelta(hours=offset),
                        )
                else:
                    self._error(f"Unsupported timezone format: {timezone_str}")
            except (TypeError, ValueError):
                self._error(f"Invalid timezone format: {timezone_str}")

        dt = datetime.datetime.fromtimestamp(timestamp / 1000, tz=tz)
        replacements = {
            "yyyy": str(dt.year),
            "yy": str(dt.year)[-2:],
            "MMMM": dt.strftime("%B"),
            "MMM": dt.strftime("%b"),
            "MM": f"{dt.month:02d}",
            "M": str(dt.month),
            "dd": f"{dt.day:02d}",
            "d": str(dt.day),
            "HH": f"{dt.hour:02d}",
            "H": str(dt.hour),
            "hh": f"{(dt.hour - 1) % 12 + 1:02d}",
            "h": str((dt.hour - 1) % 12 + 1),
            "mm": f"{dt.minute:02d}",
            "m": str(dt.minute),
            "ss": f"{dt.second:02d}",
            "s": str(dt.second),
            "a": dt.strftime("%p"),
            "zzz": dt.strftime("%Z") or "",
            "z": dt.strftime("%z"),
        }

        formatted = format_str
        for key in sorted(replacements, key=len, reverse=True):
            formatted = formatted.replace(key, replacements[key])
        return formatted
