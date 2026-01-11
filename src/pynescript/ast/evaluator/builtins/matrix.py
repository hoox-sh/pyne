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

"""Matrix collection type and operations for Pine Script v6."""

from __future__ import annotations

from collections import Counter
from typing import Any
from typing import Generic
from typing import TypeVar


__all__ = ["Matrix"]

T = TypeVar("T")


class Matrix(Generic[T]):
    """Represents a 2D matrix in Pine Script."""

    def __init__(self, rows: int = 0, cols: int = 0, default_value: Any = None):
        """Initialize matrix with given dimensions and default value."""
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

    def add_row(self, row_data: list[Any]) -> None:
        """Add row to end of matrix."""
        if len(row_data) != self.cols_count:
            msg = f"Row size {len(row_data)} != matrix columns {self.cols_count}"
            raise ValueError(msg)
        self.data.append(row_data.copy())
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

    def add_col(self, col_data: list[Any]) -> None:
        """Add column to end of matrix."""
        if len(col_data) != self.rows_count:
            msg = f"Column size {len(col_data)} != matrix rows {self.rows_count}"
            raise ValueError(msg)
        for i in range(self.rows_count):
            self.data[i].append(col_data[i])
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

    def fill(self, value: Any) -> None:
        """Fill entire matrix with value."""
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                self.data[i][j] = value

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
