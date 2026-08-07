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

"""Pine ``matrix`` collection type (2-D rectangular array).

Defines the runtime :class:`Matrix` value used by ``matrix.*`` builtins.
Dispatch handlers live in :mod:`matrix_evaluator`
(:class:`MatrixBuiltinsMixin`); this module is the pure data structure only.
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from typing import Generic
from typing import TypeVar


__all__ = ["Matrix"]

T = TypeVar("T")


class Matrix(Generic[T]):
    """Row-major 2-D matrix for Pine ``matrix.*`` operations.

    Supports ``m[row, col]`` indexing and row/column mutation. Evaluator
    dispatch is in
    :class:`~pynescript.ast.evaluator.builtins.matrix_evaluator.MatrixBuiltinsMixin`.
    """

    def __init__(self, rows: int = 0, cols: int = 0, default_value: Any = None):
        """Initialize matrix with given dimensions and default value."""
        if rows < 0 or cols < 0:
            msg = f"Matrix dimensions must be non-negative, got {rows}x{cols}"
            raise ValueError(msg)
        self.rows_count = rows
        self.cols_count = cols
        # Initialize 2D data structure
        self.data: list[list[Any]] = [[default_value for _ in range(cols)] for _ in range(rows)]

    def __getitem__(self, key: tuple[int, int]) -> Any:
        """Support m[row, col] syntax."""
        if not isinstance(key, tuple) or len(key) != 2:
            msg = "Matrix index must be a tuple (row, col)"
            raise TypeError(msg)
        return self.get(key[0], key[1])

    def __setitem__(self, key: tuple[int, int], value: Any) -> None:
        """Support m[row, col] = value syntax."""
        if not isinstance(key, tuple) or len(key) != 2:
            msg = "Matrix index must be a tuple (row, col)"
            raise TypeError(msg)
        self.set(key[0], key[1], value)

    # ========== CORE METHODS ==========

    def get(self, row: int, col: int) -> Any:
        """Get element at row, col."""
        if not (0 <= row < self.rows_count and 0 <= col < self.cols_count):
            msg = f"Index out of bounds: [{row}][{col}]"
            raise IndexError(msg)
        return self.data[row][col]

    def set(self, row: int, col: int, value: Any) -> None:
        """Set element at row, col."""
        if not (0 <= row < self.rows_count and 0 <= col < self.cols_count):
            msg = f"Index out of bounds: [{row}][{col}]"
            raise IndexError(msg)
        self.data[row][col] = value

    def rows(self) -> int:
        """Get number of rows."""
        return self.rows_count

    def columns(self) -> int:
        """Get number of columns."""
        return self.cols_count

    def elements_count(self) -> int:
        """Get total element count."""
        return self.rows_count * self.cols_count

    # ========== ROW OPERATIONS ==========

    def add_row(self, row_data: list[Any], index: int | None = None) -> None:
        """Add row at *index* (or append when *index* is None / past end).

        Empty (0×0) matrices adopt column count from *row_data* so TV form
        ``matrix.add_row(m, 0, array.from(...))`` works on ``matrix.new<T>()``.
        """
        row = list(row_data)
        if self.rows_count == 0 and self.cols_count == 0:
            self.cols_count = len(row)
        elif len(row) != self.cols_count:
            msg = f"Row size {len(row)} != matrix columns {self.cols_count}"
            raise ValueError(msg)
        if index is None or index >= self.rows_count:
            self.data.append(row)
        else:
            if index < 0:
                msg = f"Row index {index} out of range"
                raise IndexError(msg)
            self.data.insert(int(index), row)
        self.rows_count += 1

    def remove_row(self, index: int) -> None:
        """Remove row at index."""
        if not (0 <= index < self.rows_count):
            msg = f"Row index {index} out of range"
            raise IndexError(msg)
        self.data.pop(index)
        self.rows_count -= 1

    def copy_row(self, index: int) -> list[Any]:
        """Get copy of row as array."""
        if not (0 <= index < self.rows_count):
            msg = f"Row index {index} out of range"
            raise IndexError(msg)
        return self.data[index].copy()

    def sum_row(self, index: int) -> float:
        """Sum all numeric elements in row."""
        row_data = self.copy_row(index)
        total: float = sum(float(x) for x in row_data if isinstance(x, int | float))
        return total

    def avg_row(self, index: int) -> float:
        """Average of numeric elements in row."""
        row_data = self.copy_row(index)
        numeric = [float(x) for x in row_data if isinstance(x, int | float)]
        return sum(numeric) / len(numeric) if numeric else 0

    def min_row(self, index: int) -> Any:
        """Minimum numeric element in row."""
        row_data = self.copy_row(index)
        numeric = [float(x) for x in row_data if isinstance(x, int | float)]
        return min(numeric) if numeric else None

    def max_row(self, index: int) -> Any:
        """Maximum numeric element in row."""
        row_data = self.copy_row(index)
        numeric = [float(x) for x in row_data if isinstance(x, int | float)]
        return max(numeric) if numeric else None

    def mode_row(self, index: int) -> Any:
        """Most common element in row."""
        row_data = self.copy_row(index)
        if not row_data:
            return None
        counts = Counter(row_data)
        return counts.most_common(1)[0][0]

    def fill_row(self, index: int, value: Any) -> None:
        """Fill row with value."""
        if not (0 <= index < self.rows_count):
            msg = f"Row index {index} out of range"
            raise IndexError(msg)
        for j in range(self.cols_count):
            self.data[index][j] = value

    # ========== COLUMN OPERATIONS ==========

    def add_col(self, col_data: list[Any], index: int | None = None) -> None:
        """Add column at *index* (or append when *index* is None / past end).

        Empty matrices adopt row count from *col_data* (one row per element).
        """
        col = list(col_data)
        if self.rows_count == 0 and self.cols_count == 0:
            # 0×0 → N×1 from column values
            for v in col:
                self.data.append([v])
            self.rows_count = len(col)
            self.cols_count = 1 if col else 0
            return
        if len(col) != self.rows_count:
            msg = f"Column size {len(col)} != matrix rows {self.rows_count}"
            raise ValueError(msg)
        insert_at = self.cols_count if index is None else int(index)
        if insert_at < 0:
            msg = f"Column index {insert_at} out of range"
            raise IndexError(msg)
        if insert_at > self.cols_count:
            insert_at = self.cols_count
        for i in range(self.rows_count):
            self.data[i].insert(insert_at, col[i])
        self.cols_count += 1

    def remove_col(self, index: int) -> None:
        """Remove column at index."""
        if not (0 <= index < self.cols_count):
            msg = f"Column index {index} out of range"
            raise IndexError(msg)
        for row in self.data:
            row.pop(index)
        self.cols_count -= 1

    def copy_col(self, index: int) -> list[Any]:
        """Get copy of column as array."""
        if not (0 <= index < self.cols_count):
            msg = f"Column index {index} out of range"
            raise IndexError(msg)
        return [self.data[i][index] for i in range(self.rows_count)]

    def sum_col(self, index: int) -> float:
        """Sum all numeric elements in column."""
        col_data = self.copy_col(index)
        total: float = sum(float(x) for x in col_data if isinstance(x, int | float))
        return total

    def avg_col(self, index: int) -> float:
        """Average of numeric elements in column."""
        col_data = self.copy_col(index)
        numeric = [float(x) for x in col_data if isinstance(x, int | float)]
        return sum(numeric) / len(numeric) if numeric else 0

    def min_col(self, index: int) -> Any:
        """Minimum numeric element in column."""
        col_data = self.copy_col(index)
        numeric = [float(x) for x in col_data if isinstance(x, int | float)]
        return min(numeric) if numeric else None

    def max_col(self, index: int) -> Any:
        """Maximum numeric element in column."""
        col_data = self.copy_col(index)
        numeric = [float(x) for x in col_data if isinstance(x, int | float)]
        return max(numeric) if numeric else None

    def mode_col(self, index: int) -> Any:
        """Most common element in column."""
        col_data = self.copy_col(index)
        if not col_data:
            return None
        counts = Counter(col_data)
        return counts.most_common(1)[0][0]

    def fill_col(self, index: int, value: Any) -> None:
        """Fill column with value."""
        if not (0 <= index < self.cols_count):
            msg = f"Column index {index} out of range"
            raise IndexError(msg)
        for i in range(self.rows_count):
            self.data[i][index] = value

    # ========== AGGREGATION OPERATIONS ==========

    def sum_all(self) -> float:
        """Sum all numeric elements."""
        total: float = 0
        for row in self.data:
            for elem in row:
                if isinstance(elem, int | float):
                    total += float(elem)
        return total

    def avg_all(self) -> float:
        """Average of all numeric elements."""
        total: float = 0
        count: int = 0
        for row in self.data:
            for elem in row:
                if isinstance(elem, int | float):
                    total += float(elem)
                    count += 1
        return total / count if count > 0 else 0

    def min_all(self) -> Any:
        """Minimum numeric element."""
        values: list[float] = []
        for row in self.data:
            for elem in row:
                if isinstance(elem, int | float):
                    values.append(float(elem))
        return min(values) if values else None

    def max_all(self) -> Any:
        """Maximum numeric element."""
        values: list[float] = []
        for row in self.data:
            for elem in row:
                if isinstance(elem, int | float):
                    values.append(float(elem))
        return max(values) if values else None

    def mode_all(self) -> Any:
        """Most common element."""
        all_elems: list[Any] = [elem for row in self.data for elem in row]
        if not all_elems:
            return None
        counts = Counter(all_elems)
        return counts.most_common(1)[0][0]

    # ========== FILLING OPERATIONS ==========

    def fill(
        self,
        value: Any,
        from_row: int | None = None,
        to_row: int | None = None,
        from_column: int | None = None,
        to_column: int | None = None,
    ) -> None:
        """Fill matrix (or a half-open rectangular region) with *value*.

        TV: ``matrix.fill(id, value)`` or
        ``matrix.fill(id, value, from_row, to_row, from_column, to_column)``
        with half-open ranges ``[from, to)``.
        """
        r0 = 0 if from_row is None else int(from_row)
        r1 = self.rows_count if to_row is None else int(to_row)
        c0 = 0 if from_column is None else int(from_column)
        c1 = self.cols_count if to_column is None else int(to_column)
        # Clamp to matrix bounds (soft; out-of-range slice is empty)
        r0 = max(0, min(r0, self.rows_count))
        r1 = max(0, min(r1, self.rows_count))
        c0 = max(0, min(c0, self.cols_count))
        c1 = max(0, min(c1, self.cols_count))
        for i in range(r0, r1):
            row = self.data[i]
            for j in range(c0, c1):
                row[j] = value

    def fill_diagonal(self, value: Any) -> None:
        """Fill diagonal with value."""
        for i in range(min(self.rows_count, self.cols_count)):
            self.data[i][i] = value

    # ========== TRANSFORMATION OPERATIONS ==========

    def transpose(self) -> Matrix[T]:
        """Return transposed matrix."""
        result: Matrix[T] = Matrix(self.cols_count, self.rows_count)
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                result.set(j, i, self.get(i, j))
        return result

    def reverse_rows(self) -> None:
        """Reverse row order."""
        self.data.reverse()

    def reverse_cols(self) -> None:
        """Reverse column order in each row."""
        for row in self.data:
            row.reverse()

    def reshape(self, new_rows: int, new_cols: int) -> Matrix[T]:
        """Reshape matrix (flattens and reforms)."""
        total = self.elements_count()
        if new_rows * new_cols != total:
            msg = f"Cannot reshape {total} elements to {new_rows}x{new_cols}"
            raise ValueError(msg)

        flat: list[Any] = [elem for row in self.data for elem in row]
        result: Matrix[T] = Matrix(new_rows, new_cols)
        for i in range(new_rows):
            for j in range(new_cols):
                result.set(i, j, flat[i * new_cols + j])
        return result

    def _concat_rows(self, other: Matrix[T]) -> Matrix[T]:
        """Stack matrices by rows (helper for concat)."""
        if self.cols_count != other.cols_count:
            msg = "Column count must match for row concatenation"
            raise ValueError(msg)
        result: Matrix[T] = Matrix(self.rows_count + other.rows_count, self.cols_count)
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                result.set(i, j, self.get(i, j))
        for i in range(other.rows_count):
            for j in range(self.cols_count):
                result.set(self.rows_count + i, j, other.get(i, j))
        return result

    def _concat_cols(self, other: Matrix[T]) -> Matrix[T]:
        """Stack matrices by columns (helper for concat)."""
        if self.rows_count != other.rows_count:
            msg = "Row count must match for column concatenation"
            raise ValueError(msg)
        result: Matrix[T] = Matrix(self.rows_count, self.cols_count + other.cols_count)
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                result.set(i, j, self.get(i, j))
            for j in range(other.cols_count):
                result.set(i, self.cols_count + j, other.get(i, j))
        return result

    def concat(self, other: Matrix[T], axis: int = 0) -> Matrix[T]:
        """Concatenate with another matrix along axis (0=rows, 1=cols)."""
        if axis == 0:
            return self._concat_rows(other)
        return self._concat_cols(other)

    def copy(self) -> Matrix[T]:
        """Deep copy of matrix."""
        result: Matrix[T] = Matrix(self.rows_count, self.cols_count)
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                result.set(i, j, self.get(i, j))
        return result

    def __repr__(self) -> str:
        """String representation."""
        return f"matrix({self.rows_count}x{self.cols_count})"


    # ========== OFFICIAL TV v6 SURFACE ==========

    def row(self, index: int) -> list[Any]:
        """Return a copy of the row (alias of copy_row)."""
        return self.copy_row(index)

    def col(self, index: int) -> list[Any]:
        """Return a copy of the column (alias of copy_col)."""
        return self.copy_col(index)

    def submatrix(
        self,
        from_row: int = 0,
        to_row: int | None = None,
        from_col: int = 0,
        to_col: int | None = None,
    ) -> Matrix[T]:
        """Extract a submatrix [from_row:to_row, from_col:to_col] (exclusive end)."""
        to_row = self.rows_count if to_row is None else to_row
        to_col = self.cols_count if to_col is None else to_col
        if not (0 <= from_row <= to_row <= self.rows_count):
            msg = f"Invalid row range {from_row}:{to_row}"
            raise IndexError(msg)
        if not (0 <= from_col <= to_col <= self.cols_count):
            msg = f"Invalid col range {from_col}:{to_col}"
            raise IndexError(msg)
        result: Matrix[T] = Matrix(to_row - from_row, to_col - from_col)
        for i, r in enumerate(range(from_row, to_row)):
            for j, c in enumerate(range(from_col, to_col)):
                result.set(i, j, self.get(r, c))
        return result

    def swap_rows(self, row1: int, row2: int) -> None:
        """Swap two rows in place."""
        if not (0 <= row1 < self.rows_count and 0 <= row2 < self.rows_count):
            msg = f"Row index out of range: {row1}, {row2}"
            raise IndexError(msg)
        self.data[row1], self.data[row2] = self.data[row2], self.data[row1]

    def swap_columns(self, col1: int, col2: int) -> None:
        """Swap two columns in place."""
        if not (0 <= col1 < self.cols_count and 0 <= col2 < self.cols_count):
            msg = f"Column index out of range: {col1}, {col2}"
            raise IndexError(msg)
        for row in self.data:
            row[col1], row[col2] = row[col2], row[col1]

    def reverse(self) -> None:
        """Reverse element order (TV matrix.reverse): reverse rows then each row."""
        self.reverse_rows()
        self.reverse_cols()

    def _flat(self) -> list[Any]:
        return [elem for row in self.data for elem in row]

    def median(self) -> float | None:
        """Median of all numeric elements."""
        vals = [v for v in self._flat() if isinstance(v, (int, float))]
        if not vals:
            return None
        s = sorted(vals)
        n = len(s)
        mid = n // 2
        if n % 2:
            return float(s[mid])
        return (float(s[mid - 1]) + float(s[mid])) / 2.0

    def stdev(self) -> float | None:
        """Sample standard deviation of all numeric elements."""
        import statistics

        vals = [float(v) for v in self._flat() if isinstance(v, (int, float))]
        if len(vals) < 2:
            return None
        return float(statistics.stdev(vals))

    def variance(self) -> float | None:
        """Sample variance of all numeric elements."""
        import statistics

        vals = [float(v) for v in self._flat() if isinstance(v, (int, float))]
        if len(vals) < 2:
            return None
        return float(statistics.variance(vals))

    @staticmethod
    def _is_descending(order: Any) -> bool:
        """True for TV ``order.descending`` (-1), ``\"descending\"``, etc."""
        if order is None:
            return False
        if isinstance(order, bool):
            return order
        if isinstance(order, (int, float)) and not isinstance(order, bool):
            # TV: order.ascending = 1, order.descending = -1
            return float(order) < 0
        name = getattr(order, "name", None) or getattr(order, "id", None)
        text = str(name if name is not None else order).lower()
        return "desc" in text

    @staticmethod
    def _udt_field_key(value: Any, sort_field: Any) -> Any:
        """Extract comparable key from a cell (UDT field name or int index)."""
        if value is None or sort_field is None:
            return value
        get_field = getattr(value, "get_field", None)
        if get_field is None:
            return value
        if isinstance(sort_field, str):
            try:
                return get_field(sort_field)
            except (AttributeError, KeyError, TypeError):
                return value
        if isinstance(sort_field, (int, float)) and not isinstance(sort_field, bool):
            udt = getattr(value, "udt", None)
            fields = getattr(udt, "fields", None)
            if fields:
                names = list(fields.keys())
                idx = int(sort_field)
                if 0 <= idx < len(names):
                    try:
                        return get_field(names[idx])
                    except (AttributeError, KeyError, TypeError):
                        return value
        return value

    @staticmethod
    def _comparable_key(value: Any) -> Any:
        """Return a key that sorts without TypeError (string fallback)."""
        try:
            _ = value < value  # noqa: B015
            return value
        except TypeError:
            return (str(type(value)), str(value))

    def _cell_sort_value(self, cell: Any, sort_field: Any) -> Any:
        if sort_field is not None:
            return self._udt_field_key(cell, sort_field)
        return cell

    def sort(
        self,
        column: int = 0,
        order: Any = "ascending",
        sort_field: Any = None,
    ) -> None:
        """Sort rows by values in ``column`` (TV matrix.sort).

        Optional *sort_field* (field name or field index) keys UDT cells.
        ``na`` cells always sort last (TV semantics).
        """
        if self.rows_count == 0:
            return
        if not (0 <= column < self.cols_count):
            msg = f"Column index {column} out of range"
            raise IndexError(msg)
        reverse = self._is_descending(order)

        non_na: list[list[Any]] = []
        na_rows: list[list[Any]] = []
        for row in self.data:
            v = self._cell_sort_value(row[column], sort_field)
            if v is None:
                na_rows.append(row)
            else:
                non_na.append(row)

        def key_fn(row: list[Any]) -> Any:
            return self._comparable_key(self._cell_sort_value(row[column], sort_field))

        try:
            non_na.sort(key=key_fn, reverse=reverse)
        except TypeError:
            non_na.sort(
                key=lambda r: (str(type(self._cell_sort_value(r[column], sort_field))),
                               str(self._cell_sort_value(r[column], sort_field))),
                reverse=reverse,
            )
        self.data = non_na + na_rows

    def sort_indices(
        self,
        column: int = 0,
        order: Any = "ascending",
        sort_field: Any = None,
    ) -> list[int]:
        """Return row indices that would sort the matrix by ``column``."""
        if self.rows_count == 0:
            return []
        if not (0 <= column < self.cols_count):
            msg = f"Column index {column} out of range"
            raise IndexError(msg)
        reverse = self._is_descending(order)

        non_na: list[tuple[Any, int]] = []
        na_idx: list[int] = []
        for i, row in enumerate(self.data):
            v = self._cell_sort_value(row[column], sort_field)
            if v is None:
                na_idx.append(i)
            else:
                non_na.append((v, i))

        try:
            non_na.sort(key=lambda x: self._comparable_key(x[0]), reverse=reverse)
        except TypeError:
            non_na.sort(key=lambda x: (str(type(x[0])), str(x[0])), reverse=reverse)
        return [idx for _, idx in non_na] + na_idx

    def _as_float_grid(self) -> list[list[float]]:
        grid: list[list[float]] = []
        for row in self.data:
            grid.append([float(v) if isinstance(v, (int, float)) else 0.0 for v in row])
        return grid

    def _from_float_grid(self, grid: list[list[float]]) -> Matrix[T]:
        rows = len(grid)
        cols = len(grid[0]) if rows else 0
        result: Matrix[T] = Matrix(rows, cols)
        for i in range(rows):
            for j in range(cols):
                result.set(i, j, grid[i][j])
        return result

    def mult(self, other: Matrix[T] | list[Any] | float | int) -> Matrix[T] | list[Any]:
        """Matrix multiplication / scalar multiply / matrix×vector."""
        if isinstance(other, (int, float)):
            result = self.copy()
            for i in range(self.rows_count):
                for j in range(self.cols_count):
                    v = self.get(i, j)
                    result.set(i, j, (v * other) if isinstance(v, (int, float)) else v)
            return result
        if isinstance(other, list):
            if len(other) != self.cols_count:
                msg = "Vector length must match matrix columns"
                raise ValueError(msg)
            out: list[Any] = []
            for i in range(self.rows_count):
                s = 0.0
                for j in range(self.cols_count):
                    s += float(self.get(i, j) or 0) * float(other[j] or 0)
                out.append(s)
            return out
        if not isinstance(other, Matrix):
            msg = "matrix.mult expects matrix, array, or scalar"
            raise TypeError(msg)
        if self.cols_count != other.rows_count:
            msg = "Incompatible dimensions for matrix multiply"
            raise ValueError(msg)
        result: Matrix[T] = Matrix(self.rows_count, other.cols_count, 0.0)
        for i in range(self.rows_count):
            for j in range(other.cols_count):
                s = 0.0
                for k in range(self.cols_count):
                    s += float(self.get(i, k) or 0) * float(other.get(k, j) or 0)
                result.set(i, j, s)
        return result

    def diff(self, other: Matrix[T]) -> Matrix[T]:
        """Element-wise subtraction (self - other)."""
        if self.rows_count != other.rows_count or self.cols_count != other.cols_count:
            msg = "Matrices must have same dimensions for diff"
            raise ValueError(msg)
        result = self.copy()
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                a = self.get(i, j)
                b = other.get(i, j)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    result.set(i, j, a - b)
                else:
                    result.set(i, j, None)
        return result

    def sum_matrices(self, other: Matrix[T]) -> Matrix[T]:
        """Element-wise addition (self + other)."""
        if self.rows_count != other.rows_count or self.cols_count != other.cols_count:
            msg = "Matrices must have same dimensions for sum"
            raise ValueError(msg)
        result = self.copy()
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                a = self.get(i, j)
                b = other.get(i, j)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    result.set(i, j, a + b)
                else:
                    result.set(i, j, None)
        return result

    def _numpy(self):
        """Import numpy or raise a Pine-friendly error when missing."""
        try:
            import numpy as np
        except ImportError as exc:
            msg = "matrix linear-algebra ops require numpy (pip install numpy)"
            raise ValueError(msg) from exc
        return np

    def det(self) -> float:
        """Determinant of a square matrix."""
        np = self._numpy()
        if self.rows_count != self.cols_count:
            msg = "matrix.det requires a square matrix"
            raise ValueError(msg)
        if self.rows_count == 0:
            return 1.0
        arr = np.array(self._as_float_grid(), dtype=float)
        return float(np.linalg.det(arr))

    def inv(self) -> Matrix[T]:
        """Inverse of a square matrix."""
        np = self._numpy()
        if self.rows_count != self.cols_count:
            msg = "matrix.inv requires a square matrix"
            raise ValueError(msg)
        arr = np.array(self._as_float_grid(), dtype=float)
        inv = np.linalg.inv(arr)
        return self._from_float_grid(inv.tolist())

    def pinv(self) -> Matrix[T]:
        """Moore–Penrose pseudoinverse."""
        np = self._numpy()
        arr = np.array(self._as_float_grid(), dtype=float)
        pin = np.linalg.pinv(arr)
        return self._from_float_grid(pin.tolist())

    def eigenvalues(self) -> list[float]:
        """Eigenvalues of a square matrix as a list."""
        np = self._numpy()
        if self.rows_count != self.cols_count:
            msg = "matrix.eigenvalues requires a square matrix"
            raise ValueError(msg)
        arr = np.array(self._as_float_grid(), dtype=float)
        vals = np.linalg.eigvals(arr)
        return [float(v.real) for v in vals]

    def eigenvectors(self) -> Matrix[T]:
        """Eigenvectors as columns of a matrix."""
        np = self._numpy()
        if self.rows_count != self.cols_count:
            msg = "matrix.eigenvectors requires a square matrix"
            raise ValueError(msg)
        arr = np.array(self._as_float_grid(), dtype=float)
        _vals, vecs = np.linalg.eig(arr)
        # Real parts only for Pine float matrices
        real = np.real(vecs)
        return self._from_float_grid(real.tolist())

    def kron(self, other: Matrix[T]) -> Matrix[T]:
        """Kronecker product."""
        np = self._numpy()
        a = np.array(self._as_float_grid(), dtype=float)
        b = np.array(other._as_float_grid(), dtype=float)
        k = np.kron(a, b)
        return self._from_float_grid(k.tolist())

    def pow(self, n: int) -> Matrix[T]:
        """Matrix power (square matrix raised to non-negative integer)."""
        np = self._numpy()
        if self.rows_count != self.cols_count:
            msg = "matrix.pow requires a square matrix"
            raise ValueError(msg)
        if n < 0:
            msg = "matrix.pow exponent must be non-negative"
            raise ValueError(msg)
        arr = np.array(self._as_float_grid(), dtype=float)
        result = np.linalg.matrix_power(arr, int(n))
        return self._from_float_grid(result.tolist())

    def trace(self) -> float:
        """Sum of diagonal elements."""
        n = min(self.rows_count, self.cols_count)
        total = 0.0
        for i in range(n):
            v = self.get(i, i)
            if isinstance(v, (int, float)):
                total += float(v)
        return total

    def rank(self) -> int:
        """Matrix rank."""
        import numpy as np

        if self.rows_count == 0 or self.cols_count == 0:
            return 0
        arr = np.array(self._as_float_grid(), dtype=float)
        return int(np.linalg.matrix_rank(arr))

    def is_square(self) -> bool:
        return self.rows_count == self.cols_count

    def is_zero(self) -> bool:
        for row in self.data:
            for v in row:
                if isinstance(v, (int, float)):
                    if v != 0:
                        return False
                elif v is not None:
                    return False
        return True

    def is_identity(self) -> bool:
        if not self.is_square():
            return False
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                expected = 1.0 if i == j else 0.0
                v = self.get(i, j)
                if not isinstance(v, (int, float)) or float(v) != expected:
                    return False
        return True

    def is_diagonal(self) -> bool:
        if not self.is_square():
            return False
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                if i != j:
                    v = self.get(i, j)
                    if isinstance(v, (int, float)) and v != 0:
                        return False
                    if v is not None and not isinstance(v, (int, float)):
                        return False
        return True

    def is_antidiagonal(self) -> bool:
        if not self.is_square():
            return False
        n = self.rows_count
        for i in range(n):
            for j in range(n):
                if i + j != n - 1:
                    v = self.get(i, j)
                    if isinstance(v, (int, float)) and v != 0:
                        return False
        return True

    def is_symmetric(self) -> bool:
        if not self.is_square():
            return False
        for i in range(self.rows_count):
            for j in range(i + 1, self.cols_count):
                a, b = self.get(i, j), self.get(j, i)
                if a != b:
                    return False
        return True

    def is_antisymmetric(self) -> bool:
        if not self.is_square():
            return False
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                a, b = self.get(i, j), self.get(j, i)
                if i == j:
                    if isinstance(a, (int, float)) and a != 0:
                        return False
                else:
                    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                        if a != -b:
                            return False
                    elif a != b:  # non-numeric mismatch
                        return False
        return True

    def is_triangular(self) -> bool:
        """True if upper- or lower-triangular."""
        if not self.is_square():
            return False
        upper = True
        lower = True
        n = self.rows_count
        for i in range(n):
            for j in range(n):
                v = self.get(i, j)
                nonzero = isinstance(v, (int, float)) and v != 0
                if i > j and nonzero:
                    upper = False
                if i < j and nonzero:
                    lower = False
        return upper or lower

    def is_binary(self) -> bool:
        for row in self.data:
            for v in row:
                if not isinstance(v, (int, float)) or v not in (0, 1, 0.0, 1.0):
                    return False
        return True

    def is_stochastic(self) -> bool:
        """Row-stochastic: each row non-negative and sums to 1."""
        for i in range(self.rows_count):
            total = 0.0
            for j in range(self.cols_count):
                v = self.get(i, j)
                if not isinstance(v, (int, float)) or v < 0:
                    return False
                total += float(v)
            if abs(total - 1.0) > 1e-9:
                return False
        return True
