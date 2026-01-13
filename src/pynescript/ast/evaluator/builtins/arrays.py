# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import statistics

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


UNARY = 1
BINARY = 2
TERNARY = 3
MIN_ARRAY_SIZE = 2
MAX_PERCENTILE = 100


class ArrayBuiltinsMixin(BuiltinDispatchMixin):
    """Array-oriented built-in functions."""

    def _array_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "array.size": self._builtin_array_size,
            "array.get": self._builtin_array_get,
            "array.push": self._builtin_array_push,
            "array.pop": self._builtin_array_pop,
            "array.slice": self._builtin_array_slice,
            "array.abs": self._builtin_array_abs,
            "array.avg": self._builtin_array_avg,
            "array.clear": self._builtin_array_clear,
            "array.concat": self._builtin_array_concat,
            "array.copy": self._builtin_array_copy,
            "array.covariance": self._builtin_array_covariance,
            "array.every": self._builtin_array_every,
            "array.fill": self._builtin_array_fill,
            "array.first": self._builtin_array_first,
            "array.from": self._builtin_array_from,
            "array.includes": self._builtin_array_includes,
            "array.indexof": self._builtin_array_indexof,
            "array.insert": self._builtin_array_insert,
            "array.join": self._builtin_array_join,
            "array.last": self._builtin_array_last,
            "array.lastindexof": self._builtin_array_lastindexof,
            "array.max": self._builtin_array_max,
            "array.median": self._builtin_array_median,
            "array.min": self._builtin_array_min,
            "array.range": self._builtin_array_range,
            "array.remove": self._builtin_array_remove,
            "array.reverse": self._builtin_array_reverse,
            "array.set": self._builtin_array_set,
            "array.shift": self._builtin_array_shift,
            "array.some": self._builtin_array_some,
            "array.sort": self._builtin_array_sort,
            "array.sum": self._builtin_array_sum,
            "array.binary_search": self._builtin_array_binary_search,
            "array.binary_search_leftmost": self._builtin_array_binary_search_leftmost,
            "array.binary_search_rightmost": self._builtin_array_binary_search_rightmost,
            "array.mode": self._builtin_array_mode,
            "array.percentile_linear_interpolation": self._builtin_array_percentile_linear_interpolation,
            "array.percentile_nearest_rank": self._builtin_array_percentile_nearest_rank,
            "array.percentrank": self._builtin_array_percentrank,
            "array.standardize": self._builtin_array_standardize,
            "array.stdev": self._builtin_array_stdev,
            "array.variance": self._builtin_array_variance,
            "array.sort_indices": self._builtin_array_sort_indices,
            "array.new_bool": self._builtin_array_new_empty,
            "array.new_int": self._builtin_array_new_empty,
            "array.new_float": self._builtin_array_new_empty,
            "array.new_string": self._builtin_array_new_empty,
            "array.new_color": self._builtin_array_new_empty,
            "array.new_label": self._builtin_array_new_empty,
            "array.new_line": self._builtin_array_new_empty,
            "array.new_box": self._builtin_array_new_empty,
            "array.new_table": self._builtin_array_new_empty,
            "array.new_polyline": self._builtin_array_new_empty,
            "array.new_linefill": self._builtin_array_new_empty,
            "array.new_chart.point": self._builtin_array_new_empty,
            "array.unshift": self._builtin_array_unshift,
        }

    def _expect_list(self, value: Any, message: str) -> list[Any]:
        if not isinstance(value, list):
            self._error(message)
        return value

    def _expect_index(self, index: Any, length: int, message: str) -> int:
        if not isinstance(index, int) or not 0 <= index < length:
            self._error(message)
        return index

    def _builtin_array_size(self, args: list[Any]) -> int:
        if len(args) != UNARY:
            self._error("array.size takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.size takes an array argument",
        )
        return len(sequence)

    def _builtin_array_get(self, args: list[Any]) -> Any:
        if len(args) != BINARY:
            self._error("array.get takes array and index")
        sequence = self._expect_list(
            args[0],
            "array.get takes array and index",
        )
        index = args[1]
        if not isinstance(index, int):
            self._error("array.get takes array and index")
        return sequence[index]

    def _builtin_array_push(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.push takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.push takes array and value",
        )
        return [*sequence, args[1]]

    def _builtin_array_pop(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.pop takes one array argument")
        sequence = self._expect_list(
            args[0],
            "array.pop takes one array argument",
        )
        return sequence[:-1]

    def _builtin_array_slice(self, args: list[Any]) -> list[Any]:
        if len(args) != TERNARY:
            self._error("array.slice takes array, start, end")
        sequence = self._expect_list(
            args[0],
            "array.slice takes array, start, end",
        )
        start = self._expect_int(
            args[1],
            "array.slice takes array, start, end",
        )
        end = self._expect_int(
            args[2],
            "array.slice takes array, start, end",
        )
        return sequence[start:end]

    def _expect_int(self, value: Any, message: str) -> int:
        if not isinstance(value, int):
            self._error(message)
        return value

    def _builtin_array_abs(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.abs takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.abs takes an array argument",
        )
        return [abs(item) for item in sequence]

    def _builtin_array_avg(self, args: list[Any]) -> float:
        if len(args) != UNARY:
            self._error("array.avg takes a non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.avg takes a non-empty array",
        )
        if not sequence:
            self._error("array.avg takes a non-empty array")
        return statistics.mean(sequence)

    def _builtin_array_clear(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.clear takes an array argument")
        self._expect_list(
            args[0],
            "array.clear takes an array argument",
        )
        return []

    def _builtin_array_concat(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.concat takes two array arguments")
        left = self._expect_list(
            args[0],
            "array.concat takes two array arguments",
        )
        right = self._expect_list(
            args[1],
            "array.concat takes two array arguments",
        )
        return left + right

    def _builtin_array_copy(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.copy takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.copy takes an array argument",
        )
        return sequence.copy()

    def _builtin_array_covariance(self, args: list[Any]) -> float:
        if len(args) != TERNARY:
            self._error("array.covariance takes two series and length")
        series1 = self._expect_list(
            args[0],
            "array.covariance takes two series and length",
        )
        series2 = self._expect_list(
            args[1],
            "array.covariance takes two series and length",
        )
        length = self._expect_int(
            args[2],
            "array.covariance takes two series and length",
        )
        if length < 2:
            self._error("array.covariance requires length >= 2")
        return self._covariance(series1, series2, length)

    def _builtin_array_every(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("array.every takes array and predicate")
        sequence = self._expect_list(
            args[0],
            "array.every takes array and predicate",
        )
        predicate = args[1]
        if not callable(predicate):
            self._error("array.every takes array and predicate")
        return all(predicate(item) for item in sequence)

    def _builtin_array_fill(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.fill takes array and fill value")
        sequence = self._expect_list(
            args[0],
            "array.fill takes array and fill value",
        )
        return [args[1]] * len(sequence)

    def _builtin_array_first(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.first takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.first takes non-empty array",
        )
        if not sequence:
            self._error("array.first takes non-empty array")
        return sequence[0]

    def _builtin_array_from(self, args: list[Any]) -> list[Any]:
        if not args:
            self._error("array.from takes at least one argument")
        return list(args)

    def _builtin_array_includes(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("array.includes takes array and search value")
        sequence = self._expect_list(
            args[0],
            "array.includes takes array and search value",
        )
        return args[1] in sequence

    def _builtin_array_indexof(self, args: list[Any]) -> int:
        if len(args) != BINARY:
            self._error("array.indexof takes array and search value")
        sequence = self._expect_list(
            args[0],
            "array.indexof takes array and search value",
        )
        value = args[1]
        return sequence.index(value) if value in sequence else -1

    def _builtin_array_insert(self, args: list[Any]) -> list[Any]:
        if len(args) != TERNARY:
            self._error("array.insert takes array, index, and value")
        sequence = self._expect_list(
            args[0],
            "array.insert takes array, index, and value",
        )
        index = self._expect_int(
            args[1],
            "array.insert takes array, index, and value",
        )
        if index < 0:
            self._error("array.insert takes array, index, and value")
        return [*sequence[:index], args[2], *sequence[index:]]

    def _builtin_array_join(self, args: list[Any]) -> str:
        if len(args) != BINARY:
            self._error("array.join takes array and separator string")
        sequence = self._expect_list(
            args[0],
            "array.join takes array and separator string",
        )
        separator = args[1]
        if not isinstance(separator, str):
            self._error("array.join takes array and separator string")
        return separator.join(str(item) for item in sequence)

    def _builtin_array_last(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.last takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.last takes non-empty array",
        )
        if not sequence:
            self._error("array.last takes non-empty array")
        return sequence[-1]

    def _builtin_array_lastindexof(self, args: list[Any]) -> int:
        if len(args) != BINARY:
            self._error("array.lastindexof takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.lastindexof takes array and value",
        )
        value = args[1]
        if value not in sequence:
            return -1
        return len(sequence) - 1 - sequence[::-1].index(value)

    def _builtin_array_max(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.max takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.max takes non-empty array",
        )
        if not sequence:
            self._error("array.max takes non-empty array")
        return max(sequence)

    def _builtin_array_median(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.median takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.median takes non-empty array",
        )
        if not sequence:
            self._error("array.median takes non-empty array")
        return statistics.median(sequence)

    def _builtin_array_min(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.min takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.min takes non-empty array",
        )
        if not sequence:
            self._error("array.min takes non-empty array")
        return min(sequence)

    def _builtin_array_range(self, args: list[Any]) -> list[int]:
        if len(args) != BINARY:
            self._error("array.range takes start and end integers")
        start = self._expect_int(
            args[0],
            "array.range takes start and end integers",
        )
        end = self._expect_int(
            args[1],
            "array.range takes start and end integers",
        )
        return list(range(start, end + 1))

    def _builtin_array_remove(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.remove takes array and valid index")
        sequence = self._expect_list(
            args[0],
            "array.remove takes array and valid index",
        )
        index = self._expect_index(
            args[1],
            len(sequence),
            "array.remove takes array and valid index",
        )
        return sequence[:index] + sequence[index + 1 :]

    def _builtin_array_reverse(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.reverse takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.reverse takes an array argument",
        )
        return sequence[::-1]

    def _builtin_array_set(self, args: list[Any]) -> list[Any]:
        if len(args) != TERNARY:
            self._error("array.set takes array, index, and value")
        sequence = self._expect_list(
            args[0],
            "array.set takes array, index, and value",
        )
        index = self._expect_index(
            args[1],
            len(sequence),
            "array.set takes array, index, and value",
        )
        return [*sequence[:index], args[2], *sequence[index + 1 :]]

    def _builtin_array_shift(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.shift takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.shift takes non-empty array",
        )
        if not sequence:
            self._error("array.shift takes non-empty array")
        return sequence[1:]

    def _builtin_array_some(self, args: list[Any]) -> bool:
        if len(args) != BINARY:
            self._error("array.some takes array and predicate")
        sequence = self._expect_list(
            args[0],
            "array.some takes array and predicate",
        )
        predicate = args[1]
        if not callable(predicate):
            self._error("array.some takes array and predicate")
        return any(predicate(item) for item in sequence)

    def _builtin_array_sort(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.sort takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.sort takes an array argument",
        )
        return sorted(sequence)

    def _builtin_array_sum(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.sum takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.sum takes an array argument",
        )
        return sum(sequence)

    def _builtin_array_binary_search(self, args: list[Any]) -> int:
        if len(args) != BINARY:
            self._error("array.binary_search takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.binary_search takes array and value",
        )
        return self._binary_search(sequence, args[1])

    def _builtin_array_mode(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.mode takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.mode takes non-empty array",
        )
        if not sequence:
            self._error("array.mode takes non-empty array")
        return statistics.mode(sequence)

    def _builtin_array_new_empty(self, args: list[Any]) -> list[Any]:
        if args:
            self._error("array.new_* takes no arguments")
        return []

    def _builtin_array_unshift(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.unshift takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.unshift takes array and value",
        )
        return [args[1], *sequence]

    def _covariance(
        self,
        series1: list[Any],
        series2: list[Any],
        length: int,
    ) -> float:
        if len(series1) < length or len(series2) < length:
            self._error(
                "Series length must be greater than or equal to the lookback period.",
            )
        segment1 = series1[-length:]
        segment2 = series2[-length:]
        mean1 = statistics.mean(segment1)
        mean2 = statistics.mean(segment2)
        numerator = sum((x - mean1) * (y - mean2) for x, y in zip(segment1, segment2, strict=True))
        return numerator / (length - 1)

    def _binary_search(self, sequence: list[Any], value: Any) -> int:
        try:
            return sequence.index(value)
        except ValueError:
            return -1

    def _builtin_array_binary_search_leftmost(self, args: list[Any]) -> int:
        """Binary search for the leftmost (first) occurrence of a value."""
        if len(args) != BINARY:
            self._error("array.binary_search_leftmost takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.binary_search_leftmost takes array and value",
        )
        value = args[1]

        # Find leftmost position where value could be inserted
        left, right = 0, len(sequence)
        while left < right:
            mid = (left + right) // 2
            if sequence[mid] < value:
                left = mid + 1
            else:
                right = mid

        # Check if value exists at this position
        if left < len(sequence) and sequence[left] == value:
            return left
        return -1

    def _builtin_array_binary_search_rightmost(self, args: list[Any]) -> int:
        """Binary search for the rightmost (last) occurrence of a value."""
        if len(args) != BINARY:
            self._error("array.binary_search_rightmost takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.binary_search_rightmost takes array and value",
        )
        value = args[1]

        # Find rightmost position where value could be inserted
        left, right = 0, len(sequence)
        while left < right:
            mid = (left + right) // 2
            if value < sequence[mid]:
                right = mid
            else:
                left = mid + 1

        # Check if value exists at position left-1
        if left > 0 and sequence[left - 1] == value:
            return left - 1
        return -1

    def _builtin_array_percentile_linear_interpolation(self, args: list[Any]) -> float:
        """Calculate percentile using linear interpolation method."""
        if len(args) != BINARY:
            self._error("array.percentile_linear_interpolation takes array and percentile")
        sequence = self._expect_list(
            args[0],
            "array.percentile_linear_interpolation takes array and percentile",
        )
        percentile = args[1]

        if not isinstance(percentile, (int, float)) or not 0 <= percentile <= MAX_PERCENTILE:
            self._error("Percentile must be between 0 and 100")
        if not sequence:
            self._error("array.percentile_linear_interpolation requires non-empty array")

        sorted_seq = sorted(sequence)
        n = len(sorted_seq)
        h = (percentile / MAX_PERCENTILE) * (n - 1)
        h_floor = int(h)
        h_frac = h - h_floor

        if h_floor >= n - 1:
            return float(sorted_seq[-1])
        if h_floor < 0:
            return float(sorted_seq[0])

        # Linear interpolation between h_floor and h_floor+1
        return float(sorted_seq[h_floor] * (1 - h_frac) + sorted_seq[h_floor + 1] * h_frac)

    def _builtin_array_percentile_nearest_rank(self, args: list[Any]) -> Any:
        """Calculate percentile using nearest rank method."""
        if len(args) != BINARY:
            self._error("array.percentile_nearest_rank takes array and percentile")
        sequence = self._expect_list(
            args[0],
            "array.percentile_nearest_rank takes array and percentile",
        )
        percentile = args[1]

        if not isinstance(percentile, (int, float)) or not 0 <= percentile <= MAX_PERCENTILE:
            self._error("Percentile must be between 0 and 100")
        if not sequence:
            self._error("array.percentile_nearest_rank requires non-empty array")

        sorted_seq = sorted(sequence)
        n = len(sorted_seq)
        rank = max(1, int((percentile / MAX_PERCENTILE) * n + 0.5))
        return sorted_seq[rank - 1]

    def _builtin_array_percentrank(self, args: list[Any]) -> float:
        """Calculate percent rank of a value in an array (0-100)."""
        if len(args) != BINARY:
            self._error("array.percentrank takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.percentrank takes array and value",
        )
        value = args[1]

        if not sequence:
            self._error("array.percentrank requires non-empty array")

        # Count how many values are <= the given value
        count = sum(1 for x in sequence if x <= value)
        # Percent rank is (count - 1) / (n - 1) * 100
        n = len(sequence)
        if n == 1:
            return 0.0
        return ((count - 1) / (n - 1)) * 100

    def _builtin_array_standardize(self, args: list[Any]) -> list[Any]:
        """Standardize array values (z-score normalization)."""
        if len(args) != UNARY:
            self._error("array.standardize takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.standardize takes an array argument",
        )

        if len(sequence) < MIN_ARRAY_SIZE:
            self._error("array.standardize requires at least 2 values")

        mean = statistics.mean(sequence)
        stdev = statistics.stdev(sequence)

        if stdev == 0:
            self._error("Cannot standardize array with zero standard deviation")

        return [(x - mean) / stdev for x in sequence]

    def _builtin_array_stdev(self, args: list[Any]) -> float:
        """Calculate standard deviation of array values."""
        if len(args) != UNARY:
            self._error("array.stdev takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.stdev takes an array argument",
        )

        if len(sequence) < MIN_ARRAY_SIZE:
            self._error("array.stdev requires at least 2 values")

        return statistics.stdev(sequence)

    def _builtin_array_variance(self, args: list[Any]) -> float:
        """Calculate variance of array values."""
        if len(args) != UNARY:
            self._error("array.variance takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.variance takes an array argument",
        )

        if len(sequence) < MIN_ARRAY_SIZE:
            self._error("array.variance requires at least 2 values")

        return statistics.variance(sequence)

    def _builtin_array_sort_indices(self, args: list[Any]) -> list[int]:
        """Return indices that would sort the array."""
        if len(args) != UNARY:
            self._error("array.sort_indices takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.sort_indices takes an array argument",
        )

        if not sequence:
            return []

        # Create list of (value, original_index) tuples, sort by value
        indexed = [(val, idx) for idx, val in enumerate(sequence)]
        sorted_indexed = sorted(indexed, key=lambda x: x[0])
        return [idx for _, idx in sorted_indexed]
