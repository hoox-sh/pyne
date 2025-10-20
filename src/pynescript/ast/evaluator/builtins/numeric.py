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
        return {
            "abs": self._builtin_abs,
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
            "color.new": self._builtin_color_new,
            "na": self._builtin_na,
            "nz": self._builtin_nz,
            "bool": self._builtin_bool,
            "int": self._builtin_int,
            "float": self._builtin_float,
            "string": self._builtin_string,
            "fixnan": self._builtin_fixnan,
        }

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
        return abs(args[0])

    def _builtin_math_max(self, args: list[Any]) -> Any:
        return max(args)

    def _builtin_math_min(self, args: list[Any]) -> Any:
        return min(args)

    def _builtin_math_abs(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.abs takes exactly one argument")
        return abs(args[0])

    def _builtin_math_sqrt(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.sqrt takes exactly one argument")
        return math.sqrt(args[0])

    def _builtin_math_round(self, args: list[Any]) -> Any:
        if len(args) == UNARY:
            return round(args[0])
        if len(args) == BINARY:
            return round(args[0], args[1])
        self._error("math.round takes one or two arguments")

    def _builtin_math_floor(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.floor takes exactly one argument")
        return math.floor(args[0])

    def _builtin_math_ceil(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.ceil takes exactly one argument")
        return math.ceil(args[0])

    def _builtin_math_pow(self, args: list[Any]) -> Any:
        self._require_len(args, BINARY, "math.pow takes exactly two arguments")
        return math.pow(args[0], args[1])

    def _builtin_math_log(self, args: list[Any]) -> Any:
        if len(args) == UNARY:
            return math.log(args[0])
        if len(args) == BINARY:
            return math.log(args[0], args[1])
        self._error("math.log takes one or two arguments")

    def _builtin_math_sin(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.sin takes exactly one argument")
        return math.sin(args[0])

    def _builtin_math_cos(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.cos takes exactly one argument")
        return math.cos(args[0])

    def _builtin_math_tan(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.tan takes exactly one argument")
        return math.tan(args[0])

    def _builtin_math_acos(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.acos takes exactly one argument")
        return math.acos(args[0])

    def _builtin_math_asin(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.asin takes exactly one argument")
        return math.asin(args[0])

    def _builtin_math_atan(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.atan takes exactly one argument")
        return math.atan(args[0])

    def _builtin_math_exp(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.exp takes exactly one argument")
        return math.exp(args[0])

    def _builtin_math_log10(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.log10 takes exactly one argument")
        return math.log10(args[0])

    def _builtin_math_sign(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.sign takes exactly one argument")
        value = args[0]
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def _builtin_math_sum(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.sum takes an array argument")
        series = args[0]
        if not isinstance(series, list):
            self._error("math.sum takes an array argument")
        return sum(series)

    def _builtin_math_avg(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.avg takes a non-empty array")
        series = args[0]
        if not isinstance(series, list) or not series:
            self._error("math.avg takes a non-empty array")
        return statistics.mean(series)

    def _builtin_math_todegrees(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.todegrees takes one argument")
        return math.degrees(args[0])

    def _builtin_math_toradians(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "math.toradians takes one argument")
        return math.radians(args[0])

    def _builtin_math_random(self, args: list[Any]) -> Any:
        if args:
            self._error("math.random takes no arguments")
        return random.random()  # noqa: S311

    def _builtin_color_new(self, args: list[Any]) -> Any:
        self._require_len(args, UNARY, "color.new takes one argument")
        return f"color({args[0]})"

    def _builtin_na(self, args: list[Any]) -> None:
        """Return None (not available/NA value in PineScript)."""
        if args:
            self._error("na() takes no arguments")
        return None

    def _builtin_nz(self, args: list[Any]) -> Any:
        """Replace None with default value."""
        if not args or len(args) < 2:
            self._error("nz() takes value and default arguments")
        value = args[0]
        default = args[1]
        return default if value is None else value

    def _builtin_bool(self, args: list[Any]) -> bool:
        """Convert value to boolean."""
        self._require_len(args, UNARY, "bool() takes one argument")
        value = args[0]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return bool(value.lower() in {"true", "yes", "1"})
        return bool(value)

    def _builtin_int(self, args: list[Any]) -> int:
        """Convert value to integer."""
        self._require_len(args, UNARY, "int() takes one argument")
        value = args[0]
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                self._error(f"Cannot convert '{value}' to int")
        return int(value)

    def _builtin_float(self, args: list[Any]) -> float:
        """Convert value to float."""
        self._require_len(args, UNARY, "float() takes one argument")
        value = args[0]
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                self._error(f"Cannot convert '{value}' to float")
        return float(value)

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
