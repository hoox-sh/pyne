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

"""Pine ``array.*`` builtins for the AST evaluator.

Implements the ``array`` namespace (``array.new_*``, ``array.push``,
``array.get``, statistical helpers, binary search, …). Handlers treat Python
``list`` instances as Pine arrays and coerce series wrappers where needed.

Mixin composition
-----------------
:class:`ArrayBuiltinsMixin` contributes ``_array_builtin_map`` into
:class:`~pynescript.ast.evaluator.builtins.BuiltinEvaluator`. Dispatch keys are
fully qualified names such as ``array.size`` and bare type casts where
applicable.
"""

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
    """``array.*`` creation, mutation, query, and statistical builtins.

    Maps Pine array operations onto mutable Python lists. Validation helpers
    (``_expect_array``, index bounds) raise via the shared mixin ``_error`` path.
    """

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
            # CamelCase community aliases (no underscore) — set05 gradients etc.
            "array.newbool": self._builtin_array_new_empty,
            "array.newint": self._builtin_array_new_empty,
            "array.newfloat": self._builtin_array_new_empty,
            "array.newstring": self._builtin_array_new_empty,
            "array.newcolor": self._builtin_array_new_empty,
            "array.newlabel": self._builtin_array_new_empty,
            "array.newline": self._builtin_array_new_empty,
            "array.newbox": self._builtin_array_new_empty,
            "array.newtable": self._builtin_array_new_empty,
            "array.newpolyline": self._builtin_array_new_empty,
            "array.newlinefill": self._builtin_array_new_empty,
            "array.new_label": self._builtin_array_new_empty,
            "array.new_line": self._builtin_array_new_empty,
            "array.new_box": self._builtin_array_new_empty,
            "array.new_table": self._builtin_array_new_empty,
            "array.new_polyline": self._builtin_array_new_empty,
            "array.new_linefill": self._builtin_array_new_empty,
            "array.new_chart.point": self._builtin_array_new_empty,
            "array.unshift": self._builtin_array_unshift,
        }

    def _type_name(self, value: Any) -> str:
        """Short type label for error messages."""
        if value is None:
            return "na"
        t = type(value)
        return getattr(t, "__name__", str(t))

    def _expect_list(self, value: Any, message: str) -> list[Any]:
        """Coerce value to a list; unwrap series wrappers (list or deque history)."""
        if isinstance(value, list):
            return value
        if value is None:
            self._error(f"{message} (got na)")
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
        self._error(f"{message} (got {self._type_name(value)}, expected array)")

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
        """Coerce float indices (common after ``%`` / division) to int.

        TV v6: negative indices count from the end (``-1`` = last element).
        """
        try:
            coerced = self._coerce_index(index, soft=False)
        except (TypeError, ValueError):
            self._error(message)
        if coerced is None:
            self._error(message)
        if length <= 0:
            self._error(message)
        if coerced < 0:
            coerced = length + coerced
        if not 0 <= coerced < length:
            self._error(message)
        return coerced

    def _array_index_soft(self, raw_index: Any, message: str) -> int | None:
        """Coerce array index for get/set with TV-like soft-na.

        * ``na`` / NaN / unresolved import stubs → ``None`` (get returns na,
          set no-ops) — corpus residual resilience when library index helpers
          are stubbed.
        * Containers used as index (``array.get(a, a)``) still hard-error so
          fail-closed Runtime classification keeps working.
        * Does **not** resolve negative-from-end (callers use
          :meth:`_resolve_index_soft` when length is known).
        """
        if raw_index is None:
            return None
        # Fail closed on clear type confusion (array/map passed as index)
        if isinstance(raw_index, (list, dict)):
            self._error(message)
        # Import stubs (and similar) are non-numeric; soft-na rather than raise
        if getattr(raw_index, "__pine_import_stub__", False):
            return None
        try:
            return self._coerce_index(raw_index, soft=True)
        except (TypeError, ValueError):
            return None

    def _resolve_index_soft(
        self,
        raw_index: Any,
        length: int,
        message: str,
    ) -> int | None:
        """Soft-coerce index with TV v6 negative-from-end; OOB → ``None``.

        Used by ``array.get`` / soft paths. Hard-fail ops use ``_expect_index``.
        """
        idx = self._array_index_soft(raw_index, message)
        if idx is None:
            return None
        if idx < 0:
            idx = length + idx
        if idx < 0 or idx >= length:
            return None
        return idx

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
        """``array.get(id, index)`` — TV v6 negative index from end; OOB/na → na."""
        if len(args) != BINARY:
            self._error("array.get takes array and index")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        # Pine: array.get(id, na) → na; negative -1 → last element (v6)
        index = self._resolve_index_soft(
            args[1],
            len(sequence),
            "array.get takes array and index",
        )
        if index is None:
            return None
        return sequence[index]

    def _builtin_array_push(self, args: list[Any]) -> list[Any] | None:
        """``array.push(id, value)`` — append value; soft-na / incomplete call resilience.

        Corpus residuals (set05):
        - Zero-arg ``array.push()`` left by truncated TV docs demos → no-op.
        - ``array.push(id=na, value=…)`` / na receiver → no-op (TV soft-na).
        - Kwargs ``id=`` / ``value=`` via ``_KWARG_ORDER`` (including ``value=na``).
        """
        # Truncated docs / incomplete calls (arity 0 or lone value) → no-op
        if len(args) < BINARY:
            return None if not args else self._coerce_optional_list(args[0])
        if len(args) > BINARY:
            # Extra trailing args (plot-style leaks) ignored; still need id+value
            args = args[:BINARY]
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            # na / non-array receiver — soft-na rather than hard fail (gradients,
            # miswired security stubs). Wrong scalar types still error when the
            # value is clearly not an array-like optional miss.
            if args[0] is None:
                return None
            self._error(
                f"array.push takes array and value (got {self._type_name(args[0])}, expected array)",
            )
        # Pine mutates in place (void); return sequence for chaining / tests
        sequence.append(args[1])
        return sequence

    def _builtin_array_pop(self, args: list[Any]) -> Any:
        """``array.pop(id)`` — remove last; ``na`` id / empty → ``na`` (soft)."""
        if len(args) != UNARY:
            self._error("array.pop takes one array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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

    # _expect_int: inherited from BuiltinDispatchMixin (pine_expect_int)

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

    def _builtin_array_abs(self, args: list[Any]) -> list[Any] | None:
        if len(args) != UNARY:
            self._error("array.abs takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        out: list[Any] = []
        for item in sequence:
            if item is None:
                out.append(None)
                continue
            try:
                out.append(abs(item))
            except TypeError:
                self._error(
                    "array.abs requires numeric elements "
                    f"(got {self._type_name(item)})"
                )
        return out

    def _builtin_array_avg(self, args: list[Any]) -> float | None:
        if len(args) != UNARY:
            self._error("array.avg takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        # Empty / all-na → na (TradingView skips na values)
        nums = self._numeric_values(sequence)
        if not nums:
            return None
        return statistics.mean(nums)

    def _builtin_array_clear(self, args: list[Any]) -> list[Any] | None:
        """``array.clear(id)`` — clear in place; ``na`` id → no-op."""
        if len(args) != UNARY:
            self._error("array.clear takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        sequence.clear()
        return sequence

    def _builtin_array_concat(self, args: list[Any]) -> list[Any] | None:
        if len(args) != BINARY:
            self._error("array.concat takes two array arguments")
        left = self._coerce_optional_list(args[0])
        right = self._coerce_optional_list(args[1])
        if left is None or right is None:
            return None
        return left + right

    def _builtin_array_copy(self, args: list[Any]) -> list[Any] | None:
        if len(args) != UNARY:
            self._error("array.copy takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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
        """``array.fill(id, value)`` or ``array.fill(id, value, index_from, index_to)``.

        Range form fills half-open ``[index_from, index_to)`` (TradingView).
        Missing / na bounds fill the whole array; OOB bounds are clamped.
        """
        if len(args) not in {BINARY, TERNARY + 1}:
            # Accept ternary as (id, value, index_from) → fill to end
            if len(args) != TERNARY:
                self._error(
                    "array.fill takes array, value, and optional index_from, index_to"
                )
        sequence = self._expect_list(
            args[0],
            "array.fill takes array and fill value",
        )
        fill_val = args[1]
        n = len(sequence)
        if len(args) == BINARY:
            start, end = 0, n
        else:
            raw_from = args[2]
            raw_to = args[3] if len(args) > 3 else None
            if raw_from is None:
                start = 0
            else:
                try:
                    start = self._coerce_index(raw_from, soft=False)
                except (TypeError, ValueError):
                    self._error(
                        "array.fill index_from must be int "
                        f"(got {self._type_name(raw_from)})"
                    )
                if start is None:
                    start = 0
            if raw_to is None:
                end = n
            else:
                try:
                    end = self._coerce_index(raw_to, soft=False)
                except (TypeError, ValueError):
                    self._error(
                        "array.fill index_to must be int "
                        f"(got {self._type_name(raw_to)})"
                    )
                if end is None:
                    end = n
            if start < 0:
                start = 0
            if end > n:
                end = n
            if end < start:
                return sequence
        for i in range(start, end):
            sequence[i] = fill_val
        return sequence

    def _builtin_array_first(self, args: list[Any]) -> Any:
        """``array.first(id)`` — first element; ``na`` id → ``na``; empty still errors."""
        if len(args) != UNARY:
            self._error("array.first takes non-empty array")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        if not sequence:
            self._error("array.first takes non-empty array")
        return sequence[0]

    def _builtin_array_from(self, args: list[Any]) -> list[Any]:
        """``array.from(...)`` — build array; zero-arg → empty (truncated demos)."""
        if not args:
            return []
        return list(args)

    def _builtin_array_includes(self, args: list[Any]) -> bool | None:
        if len(args) != BINARY:
            self._error("array.includes takes array and search value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        return args[1] in sequence

    def _builtin_array_indexof(self, args: list[Any]) -> int | None:
        if len(args) != BINARY:
            self._error("array.indexof takes array and search value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        value = args[1]
        return sequence.index(value) if value in sequence else -1

    def _builtin_array_insert(self, args: list[Any]) -> list[Any] | None:
        """``array.insert(id, index, value)`` — insert at index (append if index ≥ size).

        TV v6: negative *index* counts from the end. ``na`` id → no-op.
        """
        if len(args) != TERNARY:
            self._error("array.insert takes array, index, and value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        raw_index = self._as_scalar(args[1])
        if raw_index is None or (
            isinstance(raw_index, float) and raw_index != raw_index
        ):
            self._error("array.insert index must be int (got na)")
        if isinstance(raw_index, bool):
            index = int(raw_index)
        elif isinstance(raw_index, float):
            index = int(raw_index)
        elif isinstance(raw_index, int):
            index = raw_index
        else:
            self._error(
                "array.insert index must be int "
                f"(got {self._type_name(raw_index)})"
            )
        n = len(sequence)
        if index < 0:
            index = n + index
            if index < 0:
                self._error(
                    f"array.insert index out of bounds: {index} (size={n})"
                )
        # index > len appends (Python list.insert clamps); allow == len as append
        sequence.insert(index, args[2])
        return sequence

    def _builtin_array_join(self, args: list[Any]) -> str | None:
        """array.join(id, separator?) / id.join(separator?) → concatenated string.

        Separator defaults to ``""`` when omitted (common in motion: ``this.join()``).
        ``na`` elements are stringified as empty. ``na`` id → ``na``.
        """
        if len(args) not in (UNARY, BINARY):
            self._error("array.join takes array and optional separator string")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        if len(args) == UNARY:
            separator = ""
        else:
            separator = args[1]
            if separator is None:
                separator = ""
            elif not isinstance(separator, str):
                separator = str(separator)
        return separator.join("" if item is None else str(item) for item in sequence)

    def _builtin_array_last(self, args: list[Any]) -> Any:
        """``array.last(id)`` — last element; ``na`` id → ``na``; empty still errors."""
        if len(args) != UNARY:
            self._error("array.last takes non-empty array")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        if not sequence:
            self._error("array.last takes non-empty array")
        return sequence[-1]

    def _builtin_array_lastindexof(self, args: list[Any]) -> int | None:
        if len(args) != BINARY:
            self._error("array.lastindexof takes array and value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        value = args[1]
        if value not in sequence:
            return -1
        return len(sequence) - 1 - sequence[::-1].index(value)

    def _array_nth_extreme(self, args: list[Any], *, op: str) -> Any:
        """``array.min/max(id)`` or ``array.min/max(id, nth)`` (0-based nth).

        TV: optional *nth* selects the nth smallest (min) or largest (max).
        ``na`` id / empty / all-na → ``na`` (soft; pairs with standardize na).
        """
        if len(args) not in {UNARY, BINARY}:
            self._error(f"array.{op} takes array and optional nth")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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
        """``array.remove(id, index)`` — TV v6 negative index from end.

        ``na`` id → ``na``; invalid index still hard-errors (library guards).
        """
        if len(args) != BINARY:
            self._error("array.remove takes array and valid index")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        index = self._expect_index(
            args[1],
            len(sequence),
            "array.remove takes array and valid index",
        )
        # Pine: remove and return the element at index
        return sequence.pop(index)

    def _builtin_array_reverse(self, args: list[Any]) -> list[Any] | None:
        if len(args) != UNARY:
            self._error("array.reverse takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        sequence.reverse()
        return sequence

    def _builtin_array_set(self, args: list[Any]) -> list[Any] | None:
        """``array.set(id, index, value)`` — TV v6 negative index from end.

        * ``na`` id / index → no-op
        * Negative in-range → set from end (``-1`` = last)
        * Positive OOB → soft-grow (ring-buffer UDF recovery)
        """
        if len(args) != TERNARY:
            self._error("array.set takes array, index, and value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        # Grow empty / undersized arrays when size was lost (e.g. non-int size
        # to array.new_*). Pine arrays are fixed-size; expanding to index is a
        # pragmatic recovery used by ring-buffer UDFs.
        # na / NaN / stub index → no-op (TV soft-na + corpus residual resilience)
        idx_guess = self._array_index_soft(
            args[1],
            "array.set takes array, index, and value",
        )
        if idx_guess is None:
            return sequence
        n = len(sequence)
        # Snapshot series handles (``array.set(a, i, close)``) so slots hold
        # bar values, not live PineSeries that all track the latest sample.
        store_val = args[2]
        if (
            store_val is not None
            and hasattr(store_val, "current")
            and hasattr(store_val, "history")
        ):
            store_val = getattr(store_val, "current", store_val)
        if idx_guess < 0:
            # v6: count from end; OOB negative → no-op (not grow)
            resolved = n + idx_guess
            if resolved < 0 or resolved >= n:
                return sequence
            sequence[resolved] = store_val
            return sequence
        if idx_guess >= n and idx_guess < 1_000_000:
            sequence.extend([None] * (idx_guess + 1 - n))
        if idx_guess >= len(sequence):
            return sequence
        sequence[idx_guess] = store_val
        return sequence

    def _builtin_array_shift(self, args: list[Any]) -> Any:
        """``array.shift(id)`` — remove first; ``na`` id / empty → ``na``."""
        if len(args) != UNARY:
            self._error("array.shift takes non-empty array")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        if not sequence:
            return None
        # Pine: remove and return first element
        return sequence.pop(0)

    def _builtin_array_some(self, args: list[Any]) -> bool | None:
        """``array.some(id, predicate)`` or unary ``id.some()`` on bool arrays.

        Corpus residual (confluence alerts): ``array.from(cond_1, …).some()``
        without a predicate treats the array as bool series and returns whether
        any element is truthy. Full form still requires a callable predicate.
        """
        if len(args) == UNARY:
            sequence = self._coerce_optional_list(args[0])
            if sequence is None:
                return None
            return any(bool(item) for item in sequence)
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

    def _parse_sort_args(self, args: list[Any]) -> tuple[bool, Any]:
        """Return ``(reverse, sort_field)`` from array.sort / sort_indices args.

        TV forms:
        - ``array.sort(id)``
        - ``array.sort(id, order)``
        - ``array.sort(id, order, sort_field)``
        - kwargs: ``sort_field=`` merges to ``[id, None, field]`` via ``_KWARG_ORDER``.
        """
        reverse = False
        sort_field: Any = None
        if len(args) <= UNARY:
            return reverse, sort_field
        if len(args) >= TERNARY:
            reverse = self._is_descending_order(args[1])
            sort_field = args[2]
            return reverse, sort_field
        # Binary: order only, or bare sort_field (string field name / field index).
        second = args[1]
        if second is None:
            return reverse, sort_field
        if isinstance(second, str):
            low = second.lower()
            if low in ("ascending", "descending", "asc", "desc"):
                reverse = self._is_descending_order(second)
            else:
                sort_field = second
            return reverse, sort_field
        if isinstance(second, (int, float)) and not isinstance(second, bool):
            # ±1 → order enum; other ints → UDT field index.
            if float(second) in (1.0, -1.0):
                reverse = self._is_descending_order(second)
            else:
                sort_field = second
            return reverse, sort_field
        reverse = self._is_descending_order(second)
        return reverse, sort_field

    @staticmethod
    def _udt_field_key(item: Any, sort_field: Any) -> Any:
        """Extract UDT field by name or int index for sorting."""
        if item is None or sort_field is None:
            return item
        get_field = getattr(item, "get_field", None)
        if get_field is None:
            return item
        if isinstance(sort_field, str):
            try:
                return get_field(sort_field)
            except (AttributeError, KeyError, TypeError):
                return item
        if isinstance(sort_field, (int, float)) and not isinstance(sort_field, bool):
            udt = getattr(item, "udt", None)
            fields = getattr(udt, "fields", None)
            if fields:
                names = list(fields.keys())
                idx = int(sort_field)
                if 0 <= idx < len(names):
                    try:
                        return get_field(names[idx])
                    except (AttributeError, KeyError, TypeError):
                        return item
        return item

    def _sort_with_na_last(
        self,
        sequence: list[Any],
        *,
        reverse: bool = False,
        sort_field: Any = None,
    ) -> list[Any]:
        """Sort like TradingView: comparable values first, ``na`` always at the end.

        Avoids ``TypeError: '<' not supported between instances of 'NoneType' and ...``.
        When *sort_field* is set, keys UDT elements by that field name/index.
        """
        if sort_field is None:
            non_na = [x for x in sequence if x is not None]
            na_count = len(sequence) - len(non_na)
            try:
                non_na.sort(reverse=reverse)
            except TypeError:
                # Mixed non-numeric types — fall back to string key
                non_na.sort(key=lambda x: (str(type(x)), str(x)), reverse=reverse)
            return non_na + [None] * na_count

        keyed: list[tuple[Any, Any]] = []
        na_items: list[Any] = []
        for item in sequence:
            if item is None:
                na_items.append(item)
                continue
            key = self._udt_field_key(item, sort_field)
            if key is None:
                na_items.append(item)
            else:
                keyed.append((key, item))
        try:
            keyed.sort(key=lambda x: x[0], reverse=reverse)
        except TypeError:
            keyed.sort(key=lambda x: (str(type(x[0])), str(x[0])), reverse=reverse)
        return [item for _, item in keyed] + na_items

    def _builtin_array_sort(self, args: list[Any]) -> list[Any] | None:
        if len(args) < UNARY:
            self._error("array.sort takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        reverse, sort_field = self._parse_sort_args(args)
        # In-place, TV semantics: na always last; optional UDT sort_field
        sequence[:] = self._sort_with_na_last(sequence, reverse=reverse, sort_field=sort_field)
        return sequence

    def _builtin_array_sum(self, args: list[Any]) -> Any:
        if len(args) != UNARY:
            self._error("array.sum takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        if not sequence:
            return None
        try:
            return statistics.mode(sequence)
        except statistics.StatisticsError:
            return None

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

    def _builtin_array_unshift(self, args: list[Any]) -> list[Any] | None:
        """``array.unshift(id, value)`` — prepend; ``na`` id → no-op."""
        if len(args) != BINARY:
            self._error("array.unshift takes array and value")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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

    def _builtin_array_standardize(self, args: list[Any]) -> list[Any] | None:
        """Standardize array values (z-score normalization).

        Drops ``na`` / non-numeric slots (``close[i]`` past history) rather than
        hard-failing ``statistics.mean`` with ``NoneType``. Fewer than 2 finite
        samples or zero stdev → ``na`` array (soft) instead of Runtime Error.
        """
        if len(args) != UNARY:
            self._error("array.standardize takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None

        nums: list[float] = []
        for x in sequence:
            if x is None or isinstance(x, bool):
                continue
            if isinstance(x, (int, float)):
                fx = float(x)
                if fx == fx:  # not NaN
                    nums.append(fx)

        if len(nums) < MIN_ARRAY_SIZE:
            return None

        mean = statistics.mean(nums)
        stdev = statistics.stdev(nums)

        if stdev == 0:
            return None

        # Preserve original length: non-finite slots stay na
        out: list[Any] = []
        for x in sequence:
            if x is None or isinstance(x, bool):
                out.append(None)
                continue
            if isinstance(x, (int, float)):
                fx = float(x)
                if fx != fx:
                    out.append(None)
                else:
                    out.append((fx - mean) / stdev)
            else:
                out.append(None)
        return out

    def _builtin_array_stdev(self, args: list[Any]) -> float | None:
        """array.stdev(id) | array.stdev(id, biased) → float.

        TV ``biased``: true → population (n); false → sample (n-1). Default true.
        ``na`` id → ``na``.
        """
        if len(args) not in {UNARY, BINARY}:
            self._error("array.stdev takes an array and optional biased flag")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
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
        """array.variance(id) | array.variance(id, biased) → float; na id → na."""
        if len(args) not in {UNARY, BINARY}:
            self._error("array.variance takes an array and optional biased flag")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        biased = True if len(args) < BINARY else bool(args[1])

        nums = [float(x) for x in sequence if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if len(nums) < MIN_ARRAY_SIZE:
            return None

        if biased:
            mean = statistics.mean(nums)
            return sum((x - mean) ** 2 for x in nums) / len(nums)
        return statistics.variance(nums)

    def _builtin_array_sort_indices(self, args: list[Any]) -> list[int] | None:
        """Return indices that would sort the array (``na`` indices last).

        Honors optional *order* and *sort_field* (UDT field name or index).
        ``na`` id → ``na``.
        """
        if len(args) < UNARY:
            self._error("array.sort_indices takes an array argument")
        sequence = self._coerce_optional_list(args[0])
        if sequence is None:
            return None
        reverse, sort_field = self._parse_sort_args(args)

        if not sequence:
            return []

        # Stable partition: comparable values first (sorted), na indices last
        non_na: list[tuple[Any, int]] = []
        na_idx: list[int] = []
        for idx, val in enumerate(sequence):
            if val is None:
                na_idx.append(idx)
                continue
            key = self._udt_field_key(val, sort_field) if sort_field is not None else val
            if key is None:
                na_idx.append(idx)
            else:
                non_na.append((key, idx))
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
ArrayBuiltinsMixin._builtin_array_sort._KWARG_ORDER = ["id", "order", "sort_field"]
ArrayBuiltinsMixin._builtin_array_sort_indices._KWARG_ORDER = ["id", "order", "sort_field"]
