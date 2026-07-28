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
            "array.new": self._builtin_array_new_empty,
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
        """Coerce value to a list; unwrap series wrappers (list or deque history)."""
        if isinstance(value, list):
            return value
        if value is None:
            self._error(message)
        # Series / history wrappers (PineSeries.history is a deque, most-recent-first)
        if hasattr(value, "history"):
            hist = value.history
            if isinstance(hist, list):
                return list(hist)
            # deque / other Sequence — materialize without requiring list type
            try:
                return list(hist)
            except TypeError:
                pass
        current = getattr(value, "current", None)
        if isinstance(current, list):
            return current
        # Tuple from failed destructure / fixed-size collections
        if isinstance(value, tuple):
            return list(value)
        self._error(message)

    def _coerce_optional_list(self, value: Any) -> list[Any] | None:
        """Like ``_expect_list`` but returns ``None`` for na / non-array (TV soft-na)."""
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if hasattr(value, "history"):
            hist = value.history
            if isinstance(hist, list):
                return list(hist)
            try:
                return list(hist)
            except TypeError:
                pass
        current = getattr(value, "current", None)
        if isinstance(current, list):
            return current
        if isinstance(value, tuple):
            return list(value)
        return None

    def _numeric_values(self, sequence: list[Any]) -> list[float]:
        """Filter out na/None and non-numeric entries (TV skips na in avg/stdev)."""
        out: list[float] = []
        for item in sequence:
            if item is None:
                continue
            if isinstance(item, bool):
                out.append(float(item))
                continue
            if isinstance(item, (int, float)):
                out.append(float(item))
        return out

    def _coerce_index(self, index: Any, *, soft: bool = True) -> int | None:
        """Coerce an index to int, or ``None`` for na.

        When *soft* is False, non-numeric garbage raises via the caller.
        Returns ``None`` only for genuine na/NaN (TV soft-na paths).
        """
        if index is None:
            return None
        current = getattr(index, "current", None)
        if current is not None and not isinstance(index, (list, tuple, str, bytes, int, float, bool)):
            # Series wrapper — unwrap; if the wrapper itself is not a series-like
            # numeric (e.g. stub lib object), fall through to int() attempt.
            if isinstance(current, (int, float, bool)) or current is None:
                index = current
                if index is None:
                    return None
        if isinstance(index, bool):
            return int(index)
        if isinstance(index, float):
            if index != index:  # NaN
                return None
            return int(index)
        if isinstance(index, int):
            return index
        # Refuse non-numeric objects (stub libs, etc.) — signal with sentinel error
        try:
            # Only accept clean numeric strings / Integral
            if isinstance(index, str):
                return int(float(index)) if soft else int(index)
            # Reject arbitrary objects that happen to define __int__
            if type(index).__module__.startswith("pynescript"):
                raise TypeError("non-numeric index")
            return int(index)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            if soft:
                return None
            raise

    def _expect_index(self, index: Any, length: int, message: str) -> int:
        """Coerce float indices (common after ``%`` / division) to int."""
        try:
            coerced = self._coerce_index(index, soft=False)
        except (TypeError, ValueError):
            self._error(message)
        if coerced is None:
            self._error(message)
        if length <= 0 or not 0 <= coerced < length:
            self._error(message)
        return coerced

    def _builtin_array_size(self, args: list[Any]) -> int | None:
        """``array.size(id)`` — size of array; ``na`` id → ``na`` (TV)."""
        if len(args) != UNARY:
            self._error("array.size takes an array argument")
        value = args[0]
        # TV: array.size(na) → na
        if value is None:
            return None
        sequence = self._coerce_optional_list(value)
        if sequence is None:
            # Non-array (e.g. stub/miswired security) — soft-na rather than hard fail
            return None
        return len(sequence)

    def _builtin_array_get(self, args: list[Any]) -> Any:
        if len(args) != BINARY:
            self._error("array.get takes array and index")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        raw_index = args[1]
        # Pine: array.get(id, na) → na (Console show loops with optional indices)
        if raw_index is None:
            return None
        try:
            index = self._coerce_index(raw_index, soft=False)
        except (TypeError, ValueError):
            self._error("array.get takes array and index")
        if index is None:
            return None
        if index < 0 or index >= len(sequence):
            return None
        return sequence[index]

    def _builtin_array_push(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.push takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.push takes array and value",
        )
        # Pine mutates in place (void); return sequence for chaining / tests
        sequence.append(args[1])
        return sequence

    def _builtin_array_pop(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.pop takes one array argument")
        sequence = self._expect_list(
            args[0],
            "array.pop takes one array argument",
        )
        if not sequence:
            return None
        # Pine: remove and return last element
        return sequence.pop()

    def _builtin_array_slice(self, args: list[Any]) -> list[Any]:
        """``array.slice(id, index_from, index_to)`` — half-open ``[from, to)``.

        TV: na bounds → empty result rather than a hard runtime error when
        intermediate length math produces na (common in NN weight slicing).
        """
        if len(args) != TERNARY:
            self._error("array.slice takes array, start, end")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return []
        # na bounds → empty; non-numeric garbage still errors
        if args[1] is None or args[2] is None:
            return []
        try:
            start = self._coerce_index(args[1], soft=False)
            end = self._coerce_index(args[2], soft=False)
        except (TypeError, ValueError):
            self._error("array.slice takes array, start, end")
        if start is None or end is None:
            return []
        # Clamp like Python slice semantics (TV returns empty if out of range)
        if start < 0:
            start = 0
        if end < start:
            return []
        return sequence[start:end]

    def _expect_int(self, value: Any, message: str) -> int:
        import math

        value = self._as_scalar(value)
        if value is None:
            self._error(message)
        if isinstance(value, float):
            if value != value:  # NaN
                self._error(message)
            value = int(math.floor(value))
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, int):
            self._error(message)
        return value

    def _as_scalar(self, value: Any) -> Any:
        """Extract scalar from PineSeries/_SeriesResult/list."""
        if hasattr(value, "current"):
            v = value.current
            if v is not None:
                return v
        if isinstance(value, list) and len(value) > 0:
            v = value[-1]
            if v is not None:
                return v
        return value

    def _builtin_array_abs(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.abs takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.abs takes an array argument",
        )
        return [abs(item) for item in sequence]

    def _builtin_array_avg(self, args: list[Any]) -> float | None:
        if len(args) != UNARY:
            self._error("array.avg takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.avg takes an array argument",
        )
        # Empty / all-na → na (TradingView skips na values)
        nums = self._numeric_values(sequence)
        if not nums:
            return None
        return statistics.mean(nums)

    def _builtin_array_clear(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.clear takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.clear takes an array argument",
        )
        sequence.clear()
        return sequence

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

    def _builtin_array_covariance(self, args: list[Any]) -> float | None:
        """``array.covariance(id1, id2, biased=true)`` — covariance of two arrays.

        TradingView signature is two equal-length arrays plus optional ``biased``
        (default true = population / n; false = sample / n-1). Older internal
        ternary form ``(series1, series2, length)`` is still accepted when the
        third argument is an int length (not a bool).
        """
        if len(args) not in {BINARY, TERNARY}:
            self._error("array.covariance takes two arrays and optional biased")
        series1 = self._coerce_optional_list(args[0])
        series2 = self._coerce_optional_list(args[1])
        if series1 is None or series2 is None:
            return None

        # Detect legacy (s1, s2, length) vs TV (id1, id2, biased)
        biased = True
        length: int | None = None
        if len(args) == TERNARY:
            third = self._as_scalar(args[2])
            if isinstance(third, bool):
                biased = third
            elif isinstance(third, (int, float)) and not isinstance(third, bool):
                # int length → legacy windowed covariance over trailing segment
                if third != third:  # NaN
                    return None
                length = int(third)
            else:
                biased = bool(third)

        nums1 = self._numeric_values(series1)
        nums2 = self._numeric_values(series2)
        if length is not None:
            if length < MIN_ARRAY_SIZE:
                return None
            if len(nums1) < length or len(nums2) < length:
                return None
            nums1 = nums1[-length:]
            nums2 = nums2[-length:]
        n = min(len(nums1), len(nums2))
        if n < MIN_ARRAY_SIZE:
            return None
        nums1 = nums1[:n]
        nums2 = nums2[:n]
        mean1 = statistics.mean(nums1)
        mean2 = statistics.mean(nums2)
        numerator = sum((x - mean1) * (y - mean2) for x, y in zip(nums1, nums2, strict=True))
        denom = n if biased else (n - 1)
        if denom <= 0:
            return None
        return numerator / denom

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
        fill_val = args[1]
        for i in range(len(sequence)):
            sequence[i] = fill_val
        return sequence

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
        sequence.insert(index, args[2])
        return sequence

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

    def _array_nth_extreme(self, args: list[Any], *, op: str) -> Any:
        """``array.min/max(id)`` or ``array.min/max(id, nth)`` (0-based nth).

        TV: optional *nth* selects the nth smallest (min) or largest (max).
        """
        if len(args) not in {UNARY, BINARY}:
            self._error(f"array.{op} takes array and optional nth")
        sequence = self._expect_list(
            args[0],
            f"array.{op} takes non-empty array",
        )
        nums = self._numeric_values(sequence)
        if not nums:
            return None
        if len(args) == UNARY:
            return min(nums) if op == "min" else max(nums)
        nth = args[1]
        current = getattr(nth, "current", None)
        if current is not None and not isinstance(nth, (list, tuple, str, bytes, int, float)):
            nth = current
        if isinstance(nth, float) and nth == int(nth):
            nth = int(nth)
        if not isinstance(nth, int) or isinstance(nth, bool):
            self._error(f"array.{op} nth must be int")
        if nth < 0:
            return None
        ordered = sorted(nums) if op == "min" else sorted(nums, reverse=True)
        if nth >= len(ordered):
            return None
        return ordered[nth]

    def _builtin_array_max(self, args: list[Any]) -> Any:
        return self._array_nth_extreme(args, op="max")

    def _builtin_array_median(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.median takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.median takes an array argument",
        )
        nums = self._numeric_values(sequence)
        if not nums:
            return None
        return statistics.median(nums)

    def _builtin_array_min(self, args: list[Any]) -> Any:
        return self._array_nth_extreme(args, op="min")

    def _builtin_array_range(self, args: list[Any]) -> float | None:
        """``array.range(id)`` — difference between max and min of array values.

        TradingView statistical helper (not Python ``range``). Empty / all-na → na.
        """
        if len(args) != UNARY:
            self._error("array.range takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        nums = self._numeric_values(sequence)
        if not nums:
            return None
        return max(nums) - min(nums)

    def _builtin_array_remove(self, args: list[Any]) -> Any:
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
        # Pine: remove and return the element at index
        return sequence.pop(index)

    def _builtin_array_reverse(self, args: list[Any]) -> list[Any]:
        if len(args) != UNARY:
            self._error("array.reverse takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.reverse takes an array argument",
        )
        sequence.reverse()
        return sequence

    def _builtin_array_set(self, args: list[Any]) -> list[Any] | None:
        if len(args) != TERNARY:
            self._error("array.set takes array, index, and value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        # Grow empty / undersized arrays when size was lost (e.g. non-int size
        # to array.new_*). Pine arrays are fixed-size; expanding to index is a
        # pragmatic recovery used by ring-buffer UDFs.
        raw_index = args[1]
        if raw_index is None:
            return sequence  # na index → no-op
        try:
            idx_guess = self._coerce_index(raw_index, soft=False)
        except (TypeError, ValueError):
            self._error("array.set takes array, index, and value")
        # Negative / na index (e.g. mergeIdx == -1) → no-op, avoid hard fail
        if idx_guess is None or idx_guess < 0:
            return sequence
        if idx_guess >= len(sequence) and idx_guess < 1_000_000:
            sequence.extend([None] * (idx_guess + 1 - len(sequence)))
        if idx_guess >= len(sequence):
            return sequence
        sequence[idx_guess] = args[2]
        return sequence

    def _builtin_array_shift(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.shift takes non-empty array")
        sequence = self._expect_list(
            args[0],
            "array.shift takes non-empty array",
        )
        if not sequence:
            return None
        # Pine: remove and return first element
        return sequence.pop(0)

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

    def _is_descending_order(self, order_arg: Any) -> bool:
        """Interpret Pine ``order.ascending`` / ``order.descending`` (or bool/str)."""
        if order_arg is None:
            return False
        if isinstance(order_arg, bool):
            return order_arg
        if isinstance(order_arg, (int, float)) and not isinstance(order_arg, bool):
            # TV: order.ascending = 1, order.descending = -1 (historically)
            return float(order_arg) < 0
        name = getattr(order_arg, "name", None) or getattr(order_arg, "id", None)
        text = str(name if name is not None else order_arg).lower()
        return "desc" in text

    def _sort_with_na_last(self, sequence: list[Any], *, reverse: bool = False) -> list[Any]:
        """Sort like TradingView: comparable values first, ``na`` always at the end.

        Avoids ``TypeError: '<' not supported between instances of 'NoneType' and ...``.
        """
        non_na = [x for x in sequence if x is not None]
        na_count = len(sequence) - len(non_na)
        try:
            non_na.sort(reverse=reverse)
        except TypeError:
            # Mixed non-numeric types — fall back to string key
            non_na.sort(key=lambda x: (str(type(x)), str(x)), reverse=reverse)
        return non_na + [None] * na_count

    def _builtin_array_sort(self, args: list[Any]) -> list[Any]:
        if len(args) < UNARY:
            self._error("array.sort takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.sort takes an array argument",
        )
        reverse = self._is_descending_order(args[1]) if len(args) > 1 else False
        # In-place, TV semantics: na always last
        sequence[:] = self._sort_with_na_last(sequence, reverse=reverse)
        return sequence

    def _builtin_array_sum(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.sum takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.sum takes an array argument",
        )
        nums = self._numeric_values(sequence)
        if not nums:
            return None
        return sum(nums)

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
            self._error("array.mode takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.mode takes an array argument",
        )
        if not sequence:
            return None
        return statistics.mode(sequence)

    def _builtin_array_new_empty(self, args: list[Any]) -> list[Any]:
        """Create a new array. Optional size / initial value: ``array.new<float>(size, initial)``."""
        if not args:
            return []
        size = args[0]
        # Unwrap series / float sizes (input.int and simple int params)
        current = getattr(size, "current", None)
        if current is not None and not isinstance(size, (list, tuple, str, bytes, int, float)):
            size = current
        if isinstance(size, float) and size == int(size):
            size = int(size)
        if isinstance(size, bool):
            size = int(size)
        if not isinstance(size, int) or size < 0:
            # Ignore non-size first args and return empty
            return []
        initial = args[1] if len(args) > 1 else None
        return [initial] * size

    def _builtin_array_unshift(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("array.unshift takes array and value")
        sequence = self._expect_list(
            args[0],
            "array.unshift takes array and value",
        )
        sequence.insert(0, args[1])
        return sequence

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

        # Binary search assumes a sorted array without na (TV). Soft-fail na.
        if value is None or any(x is None for x in sequence):
            try:
                return sequence.index(value)
            except ValueError:
                return -1

        # Find leftmost position where value could be inserted
        left, right = 0, len(sequence)
        while left < right:
            mid = (left + right) // 2
            mid_v = sequence[mid]
            if mid_v is not None and mid_v < value:
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

        if value is None or any(x is None for x in sequence):
            try:
                # last occurrence
                return len(sequence) - 1 - sequence[::-1].index(value)
            except ValueError:
                return -1

        # Find rightmost position where value could be inserted
        left, right = 0, len(sequence)
        while left < right:
            mid = (left + right) // 2
            mid_v = sequence[mid]
            if mid_v is None or value < mid_v:
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

        # Skip na — sorting None raises TypeError
        sorted_seq = self._sort_with_na_last([x for x in sequence if x is not None])
        if not sorted_seq:
            return None
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

        sorted_seq = self._sort_with_na_last([x for x in sequence if x is not None])
        if not sorted_seq:
            return None
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
        if value is None:
            return None

        # Count how many non-na values are <= the given value
        nums = [x for x in sequence if x is not None]
        if not nums:
            return None
        try:
            count = sum(1 for x in nums if x <= value)
        except TypeError:
            return None
        # Percent rank is (count - 1) / (n - 1) * 100
        n = len(nums)
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

    def _builtin_array_stdev(self, args: list[Any]) -> float | None:
        """array.stdev(id) | array.stdev(id, biased) → float.

        TV ``biased``: true → population (n); false → sample (n-1). Default true.
        """
        if len(args) not in {UNARY, BINARY}:
            self._error("array.stdev takes an array and optional biased flag")
        sequence = self._expect_list(
            args[0],
            "array.stdev takes an array argument",
        )
        biased = True if len(args) < BINARY else bool(args[1])

        # Drop na values
        nums = [float(x) for x in sequence if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if len(nums) < MIN_ARRAY_SIZE:
            return None

        if biased:
            # population stdev
            mean = statistics.mean(nums)
            var = sum((x - mean) ** 2 for x in nums) / len(nums)
            return var**0.5
        return statistics.stdev(nums)

    def _builtin_array_variance(self, args: list[Any]) -> float | None:
        """array.variance(id) | array.variance(id, biased) → float."""
        if len(args) not in {UNARY, BINARY}:
            self._error("array.variance takes an array and optional biased flag")
        sequence = self._expect_list(
            args[0],
            "array.variance takes an array argument",
        )
        biased = True if len(args) < BINARY else bool(args[1])

        nums = [float(x) for x in sequence if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if len(nums) < MIN_ARRAY_SIZE:
            return None

        if biased:
            mean = statistics.mean(nums)
            return sum((x - mean) ** 2 for x in nums) / len(nums)
        return statistics.variance(nums)

    def _builtin_array_sort_indices(self, args: list[Any]) -> list[int]:
        """Return indices that would sort the array (``na`` indices last)."""
        if len(args) < UNARY:
            self._error("array.sort_indices takes an array argument")
        sequence = self._expect_list(
            args[0],
            "array.sort_indices takes an array argument",
        )
        reverse = self._is_descending_order(args[1]) if len(args) > 1 else False

        if not sequence:
            return []

        # Stable partition: comparable values first (sorted), na indices last
        non_na = [(val, idx) for idx, val in enumerate(sequence) if val is not None]
        na_idx = [idx for idx, val in enumerate(sequence) if val is None]
        try:
            non_na.sort(key=lambda x: x[0], reverse=reverse)
        except TypeError:
            non_na.sort(key=lambda x: (str(type(x[0])), str(x[0])), reverse=reverse)
        return [idx for _, idx in non_na] + na_idx


# Named-parameter order for list-style array handlers (Pine kwargs: id=, index=, …).
ArrayBuiltinsMixin._builtin_array_size._KWARG_ORDER = ["id"]
ArrayBuiltinsMixin._builtin_array_get._KWARG_ORDER = ["id", "index"]
ArrayBuiltinsMixin._builtin_array_set._KWARG_ORDER = ["id", "index", "value"]
ArrayBuiltinsMixin._builtin_array_push._KWARG_ORDER = ["id", "value"]
ArrayBuiltinsMixin._builtin_array_pop._KWARG_ORDER = ["id"]
ArrayBuiltinsMixin._builtin_array_slice._KWARG_ORDER = ["id", "index_from", "index_to"]
ArrayBuiltinsMixin._builtin_array_covariance._KWARG_ORDER = ["id1", "id2", "biased"]
ArrayBuiltinsMixin._builtin_array_range._KWARG_ORDER = ["id"]
ArrayBuiltinsMixin._builtin_array_stdev._KWARG_ORDER = ["id", "biased"]
ArrayBuiltinsMixin._builtin_array_variance._KWARG_ORDER = ["id", "biased"]
ArrayBuiltinsMixin._builtin_array_avg._KWARG_ORDER = ["id"]
ArrayBuiltinsMixin._builtin_array_sum._KWARG_ORDER = ["id"]
ArrayBuiltinsMixin._builtin_array_min._KWARG_ORDER = ["id", "nth"]
ArrayBuiltinsMixin._builtin_array_max._KWARG_ORDER = ["id", "nth"]
ArrayBuiltinsMixin._builtin_array_remove._KWARG_ORDER = ["id", "index"]
ArrayBuiltinsMixin._builtin_array_insert._KWARG_ORDER = ["id", "index", "value"]
ArrayBuiltinsMixin._builtin_array_fill._KWARG_ORDER = ["id", "value", "index_from", "index_to"]
ArrayBuiltinsMixin._builtin_array_new_empty._KWARG_ORDER = ["size", "initial_value"]
