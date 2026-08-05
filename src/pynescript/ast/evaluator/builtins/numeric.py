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

import math
import random
import statistics

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


UNARY = 1
BINARY = 2


class NumericBuiltinsMixin(BuiltinDispatchMixin):
    """Numeric, math, and misc built-in functions."""

    def _numeric_builtin_map(self) -> dict[str, BuiltinHandler]:
        # Bare names (pow, max, …) are Pine v3/v4 global math; math.* is v5+.
        return {
            "abs": self._builtin_abs,
            "pow": self._builtin_math_pow,
            "max": self._builtin_math_max,
            "min": self._builtin_math_min,
            "sqrt": self._builtin_math_sqrt,
            "round": self._builtin_math_round,
            "floor": self._builtin_math_floor,
            "ceil": self._builtin_math_ceil,
            "log": self._builtin_math_log,
            "log10": self._builtin_math_log10,
            "exp": self._builtin_math_exp,
            "sign": self._builtin_math_sign,
            "sin": self._builtin_math_sin,
            "cos": self._builtin_math_cos,
            "tan": self._builtin_math_tan,
            "acos": self._builtin_math_acos,
            "asin": self._builtin_math_asin,
            "atan": self._builtin_math_atan,
            "sum": self._builtin_math_sum,
            "avg": self._builtin_math_avg,
            "math.max": self._builtin_math_max,
            "math.min": self._builtin_math_min,
            "math.abs": self._builtin_math_abs,
            "math.sqrt": self._builtin_math_sqrt,
            "math.round": self._builtin_math_round,
            "math.floor": self._builtin_math_floor,
            "math.ceil": self._builtin_math_ceil,
            "math.pow": self._builtin_math_pow,
            "math.log": self._builtin_math_log,
            "math.sin": self._builtin_math_sin,
            "math.cos": self._builtin_math_cos,
            "math.tan": self._builtin_math_tan,
            "math.acos": self._builtin_math_acos,
            "math.asin": self._builtin_math_asin,
            "math.atan": self._builtin_math_atan,
            "math.exp": self._builtin_math_exp,
            "math.log10": self._builtin_math_log10,
            "math.sign": self._builtin_math_sign,
            "math.sum": self._builtin_math_sum,
            "math.avg": self._builtin_math_avg,
            "math.todegrees": self._builtin_math_todegrees,
            "math.toradians": self._builtin_math_toradians,
            "math.random": self._builtin_math_random,
            # v4 / community bare alias (pre-math. namespace)
            "random": self._builtin_math_random,
            "math.isfinite": self._builtin_math_isfinite,
            "color.new": self._builtin_color_new,
            "na": self._builtin_na,
            "nz": self._builtin_nz,
            # Pine v4 ternary helper: iff(cond, then, else)
            "iff": self._builtin_iff,
            "bool": self._builtin_bool,
            "int": self._builtin_int,
            "float": self._builtin_float,
            "string": self._builtin_string,
            "fixnan": self._builtin_fixnan,
            "math.round_to_mintick": self._builtin_math_round_to_mintick,
            # v4 / community bare alias
            "round_to_mintick": self._builtin_math_round_to_mintick,
        }

    def _as_scalar(self, value: Any) -> Any:
        """Extract the scalar value from PineSeries, _SeriesResult-like, or list."""
        # Walk wrappers (PineSeries / _SeriesResult may nest)
        for _ in range(4):
            if value is None or isinstance(value, (bool, int, float, str)):
                break
            name = type(value).__name__
            if name in {"PineSeries", "_SeriesResult", "_NaValue"} or hasattr(value, "current"):
                cur = getattr(value, "current", None)
                # Some series expose history without a useful current
                if cur is None and hasattr(value, "history"):
                    hist = value.history
                    if hist:
                        cur = hist[0] if not isinstance(hist, list) else hist[-1]
                if cur is value:
                    break
                value = cur
                continue
            if isinstance(value, list) and value:
                value = value[-1]
                continue
            break
        return value

    def _require_len(
        self,
        args: list[Any],
        expected: int,
        message: str,
    ) -> None:
        if len(args) != expected:
            self._error(message)

    def _builtin_abs(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "abs takes exactly one argument")
        n = args[0]
        if n is None:
            return None
        try:
            return abs(n)
        except TypeError:
            return None

    def _as_num(self, value: Any) -> float | None:
        """Coerce a Pine value to float, treating na / NaN as None."""
        if value is None:
            return None
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes)):
            value = value.current
        if value is None:
            return None
        try:
            n = float(value)
        except (TypeError, ValueError):
            return None
        # float('nan') must not reach Python round()/floor()/int() (ValueError).
        # Pine: math.round(na) → na.
        if n != n:  # NaN
            return None
        return n

    def _builtin_math_max(self, args: list[Any]) -> Any:
        nums = [self._as_num(a) for a in args]
        nums = [n for n in nums if n is not None]
        if not nums:
            return None
        return max(nums)

    def _builtin_math_min(self, args: list[Any]) -> Any:
        nums = [self._as_num(a) for a in args]
        nums = [n for n in nums if n is not None]
        if not nums:
            return None
        return min(nums)

    def _builtin_math_abs(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.abs takes exactly one argument")
        n = self._as_num(args[0])
        return None if n is None else abs(n)

    def _builtin_math_sqrt(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.sqrt takes exactly one argument")
        n = self._as_num(args[0])
        return None if n is None or n < 0 else math.sqrt(n)

    def _builtin_math_round(self, args: list[Any]) -> Any:
        if len(args) == UNARY:
            n = self._as_num(args[0])
            return None if n is None else round(n)
        if len(args) == BINARY:
            n = self._as_num(args[0])
            d = self._as_num(args[1])
            if n is None:
                return None
            return round(n, int(d) if d is not None else 0)
        self._error("math.round takes one or two arguments")

    def _builtin_math_floor(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.floor takes exactly one argument")
        n = self._as_num(args[0])
        return None if n is None else math.floor(n)

    def _builtin_math_ceil(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.ceil takes exactly one argument")
        n = self._as_num(args[0])
        return None if n is None else math.ceil(n)

    def _builtin_math_pow(self, args: list[Any]) -> Any:
        self._require_len(args, BINARY, "math.pow takes exactly two arguments")
        a, b = self._as_num(args[0]), self._as_num(args[1])
        if a is None or b is None:
            return None
        return math.pow(a, b)

    def _builtin_math_log(self, args: list[Any]) -> Any:
        if len(args) == UNARY:
            n = self._as_num(args[0])
            return None if n is None or n <= 0 else math.log(n)
        if len(args) == BINARY:
            n, base = self._as_num(args[0]), self._as_num(args[1])
            if n is None or base is None or n <= 0 or base <= 0:
                return None
            return math.log(n, base)
        self._error("math.log takes one or two arguments")

    def _math_unary(self, args: list[Any], name: str, fn) -> Any:
        """Apply unary *fn* with Pine NA semantics (None in → None out)."""
        self._require_len(args, UNARY, f"{name} takes exactly one argument")
        n = self._as_num(args[0])
        if n is None:
            return None
        try:
            return fn(n)
        except (ValueError, OverflowError):
            # Domain errors (e.g. acos(|x|>1), log10(x<=0)) → na
            return None

    def _builtin_math_sin(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.sin", math.sin)

    def _builtin_math_cos(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.cos", math.cos)

    def _builtin_math_tan(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.tan", math.tan)

    def _builtin_math_acos(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.acos", math.acos)

    def _builtin_math_asin(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.asin", math.asin)

    def _builtin_math_atan(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.atan", math.atan)

    def _builtin_math_exp(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.exp", math.exp)

    def _builtin_math_log10(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.log10 takes exactly one argument")
        n = self._as_num(args[0])
        if n is None or n <= 0:
            return None
        return math.log10(n)

    def _builtin_math_sign(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.sign takes exactly one argument")
        value = self._as_num(args[0])
        if value is None:
            return None
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def _builtin_math_sum(self, args: list[Any]) -> Any:
        """Sum of array, or rolling sum ``math.sum(source, length)`` (TV)."""
        if len(args) == BINARY:
            # Rolling sum over last `length` values of a series
            length = args[1]
            # Unwrap series-int period (input / user series may be PineSeries)
            if hasattr(length, "current"):
                length = getattr(length, "current", length)
            if isinstance(length, float) and length == int(length):
                length = int(length)
            if not isinstance(length, int) or length <= 0:
                self._error("math.sum length must be a positive integer")
            # Bar-mode incremental path: O(1) per bar, works for scalar samples
            # (user vars without PineSeries history — CMO m1/m2, CMF ad).
            if hasattr(self, "_use_incremental_ta") and self._use_incremental_ta():  # type: ignore[attr-defined]
                if hasattr(self, "_sum_inc_update"):
                    return self._sum_inc_update(args[0], length)  # type: ignore[attr-defined]
            series = args[0]
            if hasattr(series, "history"):
                series = list(reversed(series.history))
            elif not isinstance(series, list):
                series = [series]
            # Full-window only (match compile / numba_sum_inc); any na → na
            if len(series) < length:
                return None
            window = series[-length:]
            try:
                total = 0.0
                for v in window:
                    if v is None:
                        return None
                    fv = float(v)
                    if fv != fv:  # NaN
                        return None
                    total += fv
                return total
            except (TypeError, ValueError):
                return None
        self._require_len(args, UNARY, "math.sum takes an array or (series, length)")
        series = args[0]
        if hasattr(series, "history"):
            series = list(reversed(series.history))
        if not isinstance(series, list):
            self._error("math.sum takes an array argument")
        try:
            return sum(float(v) for v in series if v is not None)
        except (TypeError, ValueError):
            return None

    def _builtin_math_avg(self, args: list[Any]) -> Any:
        """Average of array, or of multiple scalar/series args (TV ``math.avg(a,b,...)``)."""
        if not args:
            self._error("math.avg takes a non-empty array or multiple values")
        # Single list argument
        if len(args) == UNARY and isinstance(args[0], list):
            series = [v for v in args[0] if v is not None]
            if not series:
                self._error("math.avg takes a non-empty array")
            return statistics.mean(float(v) for v in series)
        # Multiple values (scalars or series current).
        # TV: if any argument is ``na``, the result is ``na`` (do not skip).
        values: list[float] = []
        for a in args:
            if hasattr(a, "current"):
                a = a.current
            if a is None:
                return None
            if isinstance(a, list):
                if not a or a[-1] is None:
                    return None
                try:
                    values.append(float(a[-1]))
                except (TypeError, ValueError):
                    return None
            else:
                try:
                    values.append(float(a))
                except (TypeError, ValueError):
                    return None
        if not values:
            return None
        return statistics.mean(values)

    def _builtin_math_todegrees(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.todegrees", math.degrees)

    def _builtin_math_toradians(self, args: list[Any]) -> Any:
        return self._math_unary(args, "math.toradians", math.radians)

    def _builtin_math_random(self, args: list[Any]) -> Any:
        """Uniform random.

        Forms:
        - ``math.random()`` → [0, 1)
        - ``math.random(min, max)`` → [min, max] (TV docs; both inclusive floats)
        """
        if not args:
            return random.random()
        if len(args) == 1:
            # Treat single arg as max with min=0
            hi = self._as_num(args[0])
            if hi is None:
                return None
            return random.uniform(0.0, float(hi))
        if len(args) >= 2:
            lo = self._as_num(args[0])
            hi = self._as_num(args[1])
            if lo is None or hi is None:
                return None
            return random.uniform(float(lo), float(hi))
        self._error("math.random takes 0 or 2 arguments")

    def _builtin_math_isfinite(self, args: list[Any]) -> bool | None:
        """``math.isfinite(x)`` — True when *x* is finite; ``na`` → ``na``."""
        self._require_len(args, UNARY, "math.isfinite takes exactly one argument")
        n = self._as_num(args[0])
        if n is None:
            return None
        return bool(math.isfinite(n))

    def _builtin_color_new(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "color.new takes one argument")
        return f"color({args[0]})"

    def _builtin_na(self, args: list[Any]) -> Any:
        """Return None (na) or check if a value is na.

        - ``na`` → None (the na sentinel value, zero args)
        - ``na(x)`` → True if x is None, else False
        """
        if not args:
            return None
        if len(args) == 1:
            return args[0] is None
        self._error("na() takes 0 or 1 arguments")

    def _builtin_nz(self, args: list[Any]) -> Any:
        """Replace None with default value (0 if not specified)."""
        if not args:
            self._error("nz() takes value and default arguments")
        value = args[0]
        default = args[1] if len(args) > 1 else 0
        return default if value is None else value

    def _builtin_iff(self, args: list[Any]) -> Any:
        """Pine v4 ``iff(condition, if_true, if_false)`` — ternary expression."""
        if len(args) < 3:
            self._error("iff() takes condition, then, else")
        cond, then_v, else_v = args[0], args[1], args[2]
        if cond is None:
            return None
        return then_v if cond else else_v

    def _builtin_bool(self, args: list[Any]) -> bool:
        """Convert value to boolean. v6: strict, never na; explicit cast required."""
        self._require_len(args, UNARY, "bool() takes one argument")
        value = args[0]
        if value is None:  # na
            return False  # or error; v6 bool never na
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)  # explicit via bool()
        if isinstance(value, str):
            return bool(value.lower() in {"true", "yes", "1"})
        return bool(value)

    def _builtin_int(self, args: list[Any]) -> int | None:
        """Convert value to integer. ``int(na)`` / non-numeric → na (None).

        TradingView soft-fails non-numeric strings (enum labels, unresolved
        name leaks such as ``\"pyramid_val\"``) to ``na`` rather than aborting
        the bar. Numeric strings accept a float step so ``int(\"2.01\")`` → 2.
        """
        self._require_len(args, UNARY, "int() takes one argument")
        value = self._as_scalar(args[0])
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if value != value:  # NaN
                return None
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _builtin_float(self, args: list[Any]) -> float | None:
        """Convert value to float. ``float(na)`` → na (None)."""
        self._require_len(args, UNARY, "float() takes one argument")
        value = self._as_scalar(args[0])
        if value is None:
            return None
        if isinstance(value, float):
            return value
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, int):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                self._error(f"Cannot convert '{value}' to float")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _builtin_string(self, args: list[Any]) -> str:
        """Convert value to string."""
        self._require_len(args, UNARY, "string() takes one argument")
        value = args[0]
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "na"
        return str(value)

    def _builtin_fixnan(self, args: list[Any]) -> Any:
        """Replace NaN/None values with previous non-NaN value or 0."""
        self._require_len(args, UNARY, "fixnan() takes one argument")
        value = args[0]
        # If the value is None (NA), return 0
        if value is None:
            return 0
        # If it's NaN (float NaN), return 0
        if isinstance(value, float) and math.isnan(value):
            return 0
        return value

    def _builtin_math_round_to_mintick(self, args: list[Any]) -> float | None:
        """Round value to the nearest tick (minimum price increment)."""
        self._require_len(args, UNARY, "math.round_to_mintick() takes one")
        value = self._as_num(args[0])
        if value is None:
            return None
        # In real Pine, this rounds to the symbol's minimum tick size
        # For general use, we round to 8 decimal places (common default)
        return round(value, 8)
