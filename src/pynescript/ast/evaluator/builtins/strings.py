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
            # v4 bare aliases (scraped corpus still uses un-namespaced forms)
            "tostring": self._builtin_str_tostring,
            "tonumber": self._builtin_str_tonumber,
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

    # _expect_int: inherited from BuiltinDispatchMixin (pine_expect_int)

    def _builtin_str_length(self, args: list[Any]) -> int | None:
        """str.length(string) → int, or ``na`` when *string* is ``na``.

        Motion uses ``str.length(seqArr.get(pointer))``; out-of-range / unset
        ``array.get`` yields ``na`` and must not hard-fail the bar.
        """
        if len(args) != UNARY:
            self._error("str.length takes a string argument")
        value = args[0]
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
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

    def _builtin_str_contains(self, args: list[Any]) -> bool | None:
        """TV: ``str.contains(source, str)`` → bool; either arg ``na`` → ``na``.

        Soft-coerces non-strings (numbers / series scalars) via ``str(...)`` so
        corpus residual paths that leak non-string types do not hard-fail.
        """
        if len(args) != BINARY:
            self._error("str.contains takes two string arguments")
        if args[0] is None or args[1] is None:
            return None
        haystack = self._coerce_str_arg(args[0])
        needle = self._coerce_str_arg(args[1])
        return needle in haystack

    def _builtin_str_startswith(self, args: list[Any]) -> bool | None:
        """TV: ``str.startswith(source, str)`` → bool; either arg ``na`` → ``na``."""
        if len(args) != BINARY:
            self._error("str.startswith takes two string arguments")
        if args[0] is None or args[1] is None:
            return None
        value = self._coerce_str_arg(args[0])
        prefix = self._coerce_str_arg(args[1])
        return value.startswith(prefix)

    def _builtin_str_substring(self, args: list[Any]) -> str | None:
        """str.substring(source, begin_pos, end_pos?) → substring or ``na``.

        Any ``na`` argument propagates ``na`` (motion: ``sub_start`` /
        ``sub_length`` often unset → end becomes ``na``).
        """
        if len(args) not in (BINARY, TERNARY):
            self._error("str.substring takes string and 1-2 ints")
        raw = args[0]
        if raw is None:
            return None
        value = raw if isinstance(raw, str) else str(raw)
        start = args[1]
        if start is None:
            return None
        start_i = self._expect_int(start, "str.substring takes string and 1-2 ints")
        if len(args) == BINARY:
            return value[start_i:]
        end = args[2]
        if end is None:
            return None
        end_i = self._expect_int(end, "str.substring takes string and 1-2 ints")
        return value[start_i:end_i]

    def _builtin_str_endswith(self, args: list[Any]) -> bool | None:
        """TV: ``str.endswith(source, str)`` → bool; either arg ``na`` → ``na``."""
        if len(args) != BINARY:
            self._error("str.endswith takes two string arguments")
        if args[0] is None or args[1] is None:
            return None
        value = self._coerce_str_arg(args[0])
        suffix = self._coerce_str_arg(args[1])
        return value.endswith(suffix)

    def _builtin_str_repeat(self, args: list[Any]) -> str | None:
        """str.repeat(source, num) → string, or ``na`` if either arg is ``na``."""
        if len(args) != BINARY:
            self._error("str.repeat takes string and int")
        raw, count = args[0], args[1]
        if raw is None or count is None:
            return None
        value = raw if isinstance(raw, str) else str(raw)
        n = self._expect_int(count, "str.repeat takes string and int")
        if n < 0:
            n = 0
        return value * n

    @staticmethod
    def _coerce_str_arg(value: Any) -> str:
        """Coerce Pine series scalars / na to str for replace family.

        ``na`` → empty string (same soft path as ``str.split``) so corpus
        scripts that feed ``syminfo.ticker`` before host seeds it do not hard-fail.
        Non-strings (int/float/bool) → ``str(value)``.
        """
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _replace_nth(source: str, target: str, replacement: str, occurrence: int) -> str:
        """Replace the *occurrence*-th match of *target* (0-based), TV semantics.

        If that occurrence does not exist, return *source* unchanged.
        Empty *target* replaces the zero-width boundary at index *occurrence*
        (``0..len(source)`` inclusive), matching ``str.replace_all`` boundary inserts.
        """
        if occurrence < 0:
            return source
        if target == "":
            if occurrence > len(source):
                return source
            return source[:occurrence] + replacement + source[occurrence:]
        start = 0
        for n in range(occurrence + 1):
            idx = source.find(target, start)
            if idx < 0:
                return source
            if n == occurrence:
                return source[:idx] + replacement + source[idx + len(target) :]
            start = idx + len(target)
        return source

    def _builtin_str_replace(self, args: list[Any]) -> str | None:
        """TV: ``str.replace(source, target, replacement, occurrence=0)``.

        Accepts 3 or 4 arguments. Optional *occurrence* (int, 0-based) selects
        which match to replace; default ``0`` replaces the first match only.
        """
        if len(args) not in (TERNARY, 4):
            self._error("str.replace takes three string arguments")
        # Propagate pure-na source (no host string) as na — but only when the
        # other args are also missing would be stricter; for residual C1 we
        # coerce so scripts keep running. Prefer: source na → na when all none.
        if args[0] is None and all(a is None for a in args[1:3]):
            return None
        value = self._coerce_str_arg(args[0])
        old = self._coerce_str_arg(args[1])
        new = self._coerce_str_arg(args[2])
        occurrence = 0
        if len(args) == 4 and args[3] is not None:
            occurrence = self._expect_int(
                args[3],
                "str.replace occurrence must be an int",
            )
        return self._replace_nth(value, old, new, occurrence)

    def _builtin_str_replace_all(self, args: list[Any]) -> str | None:
        """TV: ``str.replace_all(source, target, replacement)``."""
        if len(args) != TERNARY:
            self._error("str.replace_all takes three strings")
        if args[0] is None and args[1] is None and args[2] is None:
            return None
        value = self._coerce_str_arg(args[0])
        old = self._coerce_str_arg(args[1])
        new = self._coerce_str_arg(args[2])
        return value.replace(old, new)

    def _builtin_str_split(self, args: list[Any]) -> list[str]:
        """str.split(source, separator?) → array of substrings.

        Aligns with :func:`pynescript.compiler.numba_builtins.str_split`:

        - ``na`` / ``None`` source → empty string (so ``x.isset(str.split(na, …))``
          patterns in motion/console libraries do not hard-fail while evaluating
          the fallback).
        - empty separator → split into characters (Python forbids ``"".split("")``).
        """
        if len(args) not in (UNARY, BINARY):
            self._error("str.split takes str and opt separator")
        raw = args[0]
        if raw is None:
            value = ""
        elif isinstance(raw, str):
            value = raw
        else:
            # Coerce numbers / series scalars rather than hard-fail (TV tostring-ish)
            value = str(raw)
        if len(args) == UNARY:
            return value.split()
        sep_raw = args[1]
        if sep_raw is None:
            return value.split()
        sep = sep_raw if isinstance(sep_raw, str) else str(sep_raw)
        if sep == "":
            return list(value)
        return value.split(sep)

    def _builtin_str_trim(self, args: list[Any]) -> str:
        if len(args) != UNARY:
            self._error("str.trim takes a string argument")
        value = self._expect_string(
            args[0],
            "str.trim takes a string argument",
        )
        return value.strip()

    def _builtin_str_tonumber(self, args: list[Any]) -> float | None:
        """TV: ``str.tonumber(string)`` → float, or ``na`` when not parseable.

        Placeholder defaults such as ``"YYYY-MM"`` must not raise — scripts
        like seasonality push rounded tonumber results into arrays and rely
        on na propagation.

        Soft-coerces ``na`` / non-string (array.get miss, numbers) → ``na`` or
        ``float(value)`` rather than hard-failing ``takes a string argument``.
        """
        if len(args) != UNARY:
            self._error("str.tonumber takes a string argument")
        value = args[0]
        if value is None:
            return None
        if not isinstance(value, str):
            # Numbers already numeric; other types → best-effort / na.
            if isinstance(value, bool):
                return float(int(value))
            if isinstance(value, (int, float)):
                if isinstance(value, float) and value != value:
                    return None
                return float(value)
            try:
                value = str(value)
            except (TypeError, ValueError):
                return None
        value = value.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _builtin_str_tostring(self, args: list[Any]) -> str:
        """TV: ``str.tostring(value)`` or ``str.tostring(value, format)``."""
        if not args:
            self._error("str.tostring takes one or two arguments")
        value = args[0]
        if value is None:
            return "NaN"
        if len(args) >= 2 and args[1] is not None:
            fmt = str(args[1])
            try:
                if isinstance(value, (int, float)):
                    # Pine format tokens are simplified: # / 0.00 etc.
                    if "#" in fmt or "0" in fmt:
                        return f"{float(value):g}"
                    return format(value, fmt) if fmt else str(value)
            except (ValueError, TypeError):
                pass
        return str(value)

    def _builtin_str_format(self, args: list[Any]) -> str:
        """Pine ``str.format(fmt, ...)`` — Java MessageFormat-ish placeholders.

        Supports ``{0}``, ``{1,number}``, ``{0,number,#.####}``. Falls back to
        a best-effort string when the placeholder is unknown (Console.show uses
        ``{0,number,#####}`` for bar indices).

        Arity edges:
        - 0 args → error
        - 1 arg (format only, or corpus-sanitize ``str.format(na)``) → format
          with empty placeholders / ``\"NaN\"`` when the sole arg is ``na``
        - 2+ args → normal MessageFormat path
        """
        if not args:
            self._error("str.format takes format string and args")
        if args[0] is None:
            # Truncated corpus often becomes ``str.format(na)`` after sanitize.
            if len(args) == UNARY:
                return "NaN"
            # fmt is na but extra args present — soft empty
            return "NaN"
        value = self._expect_string(
            args[0],
            "str.format takes format string and args",
        )
        fmt_args = list(args[1:])

        def _replace(match: re.Match[str]) -> str:
            body = match.group(1)
            parts = [p.strip() for p in body.split(",")]
            try:
                idx = int(parts[0])
            except (TypeError, ValueError):
                return match.group(0)
            if idx < 0 or idx >= len(fmt_args):
                return ""
            arg = fmt_args[idx]
            if arg is None:
                return "NaN"
            kind = parts[1].lower() if len(parts) > 1 else ""
            pattern = parts[2] if len(parts) > 2 else ""
            if kind in {"", "string"}:
                return str(arg)
            if kind == "number":
                try:
                    num = float(arg)
                except (TypeError, ValueError):
                    return str(arg)
                if pattern:
                    # Map # / 0 patterns roughly to decimal places
                    if "." in pattern:
                        decimals = len(pattern.split(".", 1)[1])
                        return f"{num:.{decimals}f}"
                    try:
                        return str(int(num))
                    except (TypeError, ValueError):
                        return f"{num:g}"
                return f"{num:g}"
            if kind == "integer":
                try:
                    return str(int(float(arg)))
                except (TypeError, ValueError):
                    return str(arg)
            return str(arg)

        try:
            return re.sub(r"\{([^{}]+)\}", _replace, value)
        except Exception:
            # Never abort a library demo on format quirks
            try:
                return value.format(*fmt_args)
            except Exception:
                return value + "".join(str(a) for a in fmt_args)

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
        """``str.format_time(time[, format[, timezone]])``.

        Unary form uses the ISO-8601 default format
        ``yyyy-MM-dd'T'HH:mm:ssZ`` (TradingView default when *format* is omitted).
        """
        # UNARY = timestamp only; BINARY = + format; TERNARY = + timezone
        if len(args) not in {UNARY, BINARY, TERNARY}:
            self._error(
                "str.format_time takes timestamp, format, and optional timezone",
            )
        timestamp = args[0]
        # Accept int/float; coerce seconds → ms when value looks like Unix seconds
        if isinstance(timestamp, float):
            if timestamp != timestamp:  # NaN
                return "NaN"
            timestamp = int(timestamp)
        if not isinstance(timestamp, int):
            # Unresolved bare name / na / import-stub objects (VisibleChart.*)
            if timestamp is None or isinstance(timestamp, str):
                return "NaN"
            # series wrapper
            cur = getattr(timestamp, "current", None)
            if isinstance(cur, (int, float)) and not isinstance(cur, bool):
                if isinstance(cur, float) and cur != cur:
                    return "NaN"
                timestamp = int(cur)
            else:
                # Soft-fail: PineImportStub / UDT / wrong type → "NaN" text
                return "NaN"
        if 0 < timestamp < 10_000_000_000:
            # Likely seconds (e.g. chart bars with s-epoch) — Pine uses ms
            timestamp = timestamp * 1000
        # TV default when format omitted
        if len(args) == UNARY or args[1] is None:
            format_str = "yyyy-MM-dd'T'HH:mm:ssZ"
        else:
            format_str = self._expect_string(
                args[1],
                "str.format_time expects format string",
            )
        timezone_str = args[2] if len(args) == TERNARY else None
        if timezone_str is not None and not isinstance(timezone_str, str):
            # request.security(syminfo.timezone) may yield series list / float stub
            if isinstance(timezone_str, (list, tuple)):
                timezone_str = timezone_str[-1] if timezone_str else None
            if timezone_str is not None and not isinstance(timezone_str, str):
                # Soft: non-string timezone → ignore (use UTC default)
                timezone_str = None
        formatted = self._format_time(timestamp, format_str, timezone_str)
        # Strip TV literal-quote markers (e.g. 'T' in ISO default)
        return formatted.replace("'", "")

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
                z = timezone_str.strip()
                # Unresolved bare name from context (``syminfo.timezone`` not seeded)
                if z in {"syminfo.timezone", "UTC", "utc", "Etc/UTC", "GMT"}:
                    tz = datetime.timezone.utc
                elif "GMT" in z.upper() or z.startswith(("UTC+", "UTC-", "utc+", "utc-")):
                    offset_str = (
                        z.upper()
                        .replace("GMT", "")
                        .replace("UTC", "")
                        .strip()
                    )
                    if offset_str:
                        # Accept "+2", "-5", "2"
                        offset = int(offset_str)
                        tz = datetime.timezone(datetime.timedelta(hours=offset))
                else:
                    # IANA names when zoneinfo is available (Python 3.9+)
                    try:
                        from zoneinfo import ZoneInfo

                        tz = ZoneInfo(z)
                    except Exception:
                        # Soft-fail to UTC rather than aborting Console.show()
                        tz = datetime.timezone.utc
            except (TypeError, ValueError):
                tz = datetime.timezone.utc

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


# TV parameter names for kwargs → positional merge (BuiltinDispatchMixin).
StringBuiltinsMixin._builtin_str_replace._KWARG_ORDER = [  # type: ignore[attr-defined]
    "source",
    "target",
    "replacement",
    "occurrence",
]
StringBuiltinsMixin._builtin_str_replace_all._KWARG_ORDER = [  # type: ignore[attr-defined]
    "source",
    "target",
    "replacement",
]
