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

"""Matrix collection evaluator for Pine Script v6."""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .matrix import Matrix


UNARY = 1
BINARY = 2
TERNARY = 3
QUATERNARY = 4


class MatrixBuiltinsMixin(BuiltinDispatchMixin):
    """Matrix collection built-in functions and methods."""

    def _matrix_builtin_map(self) -> dict[str, BuiltinHandler]:
        """Build dispatch map for matrix operations."""
        return {
            # Core operations
            "matrix.new": self._builtin_matrix_new,
            "matrix.get": self._builtin_matrix_get,
            "matrix.set": self._builtin_matrix_set,
            "matrix.rows": self._builtin_matrix_rows,
            "matrix.columns": self._builtin_matrix_columns,
            "matrix.elements_count": self._builtin_matrix_elements_count,
            # Row operations
            "matrix.add_row": self._builtin_matrix_add_row,
            "matrix.remove_row": self._builtin_matrix_remove_row,
            "matrix.copy_row": self._builtin_matrix_copy_row,
            "matrix.sum_row": self._builtin_matrix_sum_row,
            "matrix.avg_row": self._builtin_matrix_avg_row,
            "matrix.min_row": self._builtin_matrix_min_row,
            "matrix.max_row": self._builtin_matrix_max_row,
            "matrix.mode_row": self._builtin_matrix_mode_row,
            "matrix.fill_row": self._builtin_matrix_fill_row,
            # Column operations
            "matrix.add_col": self._builtin_matrix_add_col,
            "matrix.remove_col": self._builtin_matrix_remove_col,
            "matrix.copy_col": self._builtin_matrix_copy_col,
            "matrix.sum_col": self._builtin_matrix_sum_col,
            "matrix.avg_col": self._builtin_matrix_avg_col,
            "matrix.min_col": self._builtin_matrix_min_col,
            "matrix.max_col": self._builtin_matrix_max_col,
            "matrix.mode_col": self._builtin_matrix_mode_col,
            "matrix.fill_col": self._builtin_matrix_fill_col,
            # Aggregation operations
            "matrix.sum_all": self._builtin_matrix_sum_all,
            "matrix.avg_all": self._builtin_matrix_avg_all,
            "matrix.min_all": self._builtin_matrix_min_all,
            "matrix.max_all": self._builtin_matrix_max_all,
            "matrix.mode_all": self._builtin_matrix_mode_all,
            # Filling operations
            "matrix.fill": self._builtin_matrix_fill,
            "matrix.fill_diagonal": self._builtin_matrix_fill_diagonal,
            # Transformation operations
            "matrix.transpose": self._builtin_matrix_transpose,
            "matrix.reverse_rows": self._builtin_matrix_reverse_rows,
            "matrix.reverse_cols": self._builtin_matrix_reverse_cols,
            "matrix.reshape": self._builtin_matrix_reshape,
            "matrix.concat": self._builtin_matrix_concat,
            "matrix.copy": self._builtin_matrix_copy,
        }

    # ========== HELPER METHODS ==========

    def _expect_matrix(self, value: Any, message: str) -> Matrix[Any]:
        """Validate that value is a Matrix instance."""
        if not isinstance(value, Matrix):
            self._error(message)
        return value

    def _expect_int(self, value: Any, message: str) -> int:
        """Validate that value is an integer."""
        if not isinstance(value, int):
            self._error(message)
        return value

    def _expect_list(self, value: Any, message: str) -> list[Any]:
        """Validate that value is a list."""
        if not isinstance(value, list):
            self._error(message)
        return value

    # ========== CORE OPERATIONS ==========

    def _builtin_matrix_new(self, args: list[Any]) -> Matrix[Any]:
        """matrix.new(rows, cols, default_value) -> Matrix"""
        if len(args) < BINARY:
            self._error("matrix.new requires at least rows and cols")
        rows = self._expect_int(args[0], "matrix.new: rows must be int")
        cols = self._expect_int(args[UNARY], "matrix.new: cols must be int")
        default_value = args[BINARY] if len(args) > BINARY else None
        if rows < 0 or cols < 0:
            self._error("matrix.new: rows and cols must be non-negative")
        return Matrix(rows, cols, default_value)

    def _builtin_matrix_get(self, args: list[Any]) -> Any:
        """matrix.get(matrix, row, col) -> value"""
        if len(args) != TERNARY:
            self._error("matrix.get requires matrix, row, col")
        matrix = self._expect_matrix(args[0], "matrix.get: first arg must be matrix")
        row = self._expect_int(args[UNARY], "matrix.get: row must be int")
        col = self._expect_int(args[BINARY], "matrix.get: col must be int")
        try:
            return matrix.get(row, col)
        except IndexError as e:
            self._error(f"matrix.get: {e}")

    def _builtin_matrix_set(self, args: list[Any]) -> None:
        """matrix.set(matrix, row, col, value) -> void"""
        if len(args) != QUATERNARY:
            self._error("matrix.set requires matrix, row, col, value")
        matrix = self._expect_matrix(args[0], "matrix.set: first arg must be matrix")
        row = self._expect_int(args[UNARY], "matrix.set: row must be int")
        col = self._expect_int(args[BINARY], "matrix.set: col must be int")
        value = args[TERNARY]
        try:
            matrix.set(row, col, value)
        except IndexError as e:
            self._error(f"matrix.set: {e}")

    def _builtin_matrix_rows(self, args: list[Any]) -> int:
        """matrix.rows(matrix) -> int"""
        if len(args) != UNARY:
            self._error("matrix.rows requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.rows: arg must be matrix")
        return matrix.rows()

    def _builtin_matrix_columns(self, args: list[Any]) -> int:
        """matrix.columns(matrix) -> int"""
        if len(args) != UNARY:
            self._error("matrix.columns requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.columns: arg must be matrix")
        return matrix.columns()

    def _builtin_matrix_elements_count(self, args: list[Any]) -> int:
        """matrix.elements_count(matrix) -> int"""
        if len(args) != UNARY:
            self._error("matrix.elements_count requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.elements_count: arg must be matrix")
        return matrix.elements_count()

    # ========== ROW OPERATIONS ==========

    def _builtin_matrix_add_row(self, args: list[Any]) -> None:
        """matrix.add_row(matrix, row_data) -> void"""
        if len(args) != BINARY:
            self._error("matrix.add_row requires matrix and row data")
        matrix = self._expect_matrix(args[0], "matrix.add_row: first arg must be matrix")
        row_data = self._expect_list(args[UNARY], "matrix.add_row: second arg must be array")
        try:
            matrix.add_row(row_data)
        except ValueError as e:
            self._error(f"matrix.add_row: {e}")

    def _builtin_matrix_remove_row(self, args: list[Any]) -> None:
        """matrix.remove_row(matrix, index) -> void"""
        if len(args) != BINARY:
            self._error("matrix.remove_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.remove_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.remove_row: index must be int")
        try:
            matrix.remove_row(index)
        except IndexError as e:
            self._error(f"matrix.remove_row: {e}")

    def _builtin_matrix_copy_row(self, args: list[Any]) -> list[Any]:
        """matrix.copy_row(matrix, index) -> array"""
        if len(args) != BINARY:
            self._error("matrix.copy_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.copy_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.copy_row: index must be int")
        try:
            return matrix.copy_row(index)
        except IndexError as e:
            self._error(f"matrix.copy_row: {e}")

    def _builtin_matrix_sum_row(self, args: list[Any]) -> float:
        """matrix.sum_row(matrix, index) -> float"""
        if len(args) != BINARY:
            self._error("matrix.sum_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.sum_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.sum_row: index must be int")
        try:
            return matrix.sum_row(index)
        except IndexError as e:
            self._error(f"matrix.sum_row: {e}")

    def _builtin_matrix_avg_row(self, args: list[Any]) -> float:
        """matrix.avg_row(matrix, index) -> float"""
        if len(args) != BINARY:
            self._error("matrix.avg_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.avg_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.avg_row: index must be int")
        try:
            return matrix.avg_row(index)
        except IndexError as e:
            self._error(f"matrix.avg_row: {e}")

    def _builtin_matrix_min_row(self, args: list[Any]) -> Any:
        """matrix.min_row(matrix, index) -> value"""
        if len(args) != BINARY:
            self._error("matrix.min_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.min_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.min_row: index must be int")
        try:
            return matrix.min_row(index)
        except IndexError as e:
            self._error(f"matrix.min_row: {e}")

    def _builtin_matrix_max_row(self, args: list[Any]) -> Any:
        """matrix.max_row(matrix, index) -> value"""
        if len(args) != BINARY:
            self._error("matrix.max_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.max_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.max_row: index must be int")
        try:
            return matrix.max_row(index)
        except IndexError as e:
            self._error(f"matrix.max_row: {e}")

    def _builtin_matrix_mode_row(self, args: list[Any]) -> Any:
        """matrix.mode_row(matrix, index) -> value"""
        if len(args) != BINARY:
            self._error("matrix.mode_row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.mode_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.mode_row: index must be int")
        try:
            return matrix.mode_row(index)
        except IndexError as e:
            self._error(f"matrix.mode_row: {e}")

    def _builtin_matrix_fill_row(self, args: list[Any]) -> None:
        """matrix.fill_row(matrix, index, value) -> void"""
        if len(args) != TERNARY:
            self._error("matrix.fill_row requires matrix, index, value")
        matrix = self._expect_matrix(args[0], "matrix.fill_row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.fill_row: index must be int")
        value = args[BINARY]
        try:
            matrix.fill_row(index, value)
        except IndexError as e:
            self._error(f"matrix.fill_row: {e}")

    # ========== COLUMN OPERATIONS ==========

    def _builtin_matrix_add_col(self, args: list[Any]) -> None:
        """matrix.add_col(matrix, col_data) -> void"""
        if len(args) != BINARY:
            self._error("matrix.add_col requires matrix and column data")
        matrix = self._expect_matrix(args[0], "matrix.add_col: first arg must be matrix")
        col_data = self._expect_list(args[UNARY], "matrix.add_col: second arg must be array")
        try:
            matrix.add_col(col_data)
        except ValueError as e:
            self._error(f"matrix.add_col: {e}")

    def _builtin_matrix_remove_col(self, args: list[Any]) -> None:
        """matrix.remove_col(matrix, index) -> void"""
        if len(args) != BINARY:
            self._error("matrix.remove_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.remove_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.remove_col: index must be int")
        try:
            matrix.remove_col(index)
        except IndexError as e:
            self._error(f"matrix.remove_col: {e}")

    def _builtin_matrix_copy_col(self, args: list[Any]) -> list[Any]:
        """matrix.copy_col(matrix, index) -> array"""
        if len(args) != BINARY:
            self._error("matrix.copy_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.copy_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.copy_col: index must be int")
        try:
            return matrix.copy_col(index)
        except IndexError as e:
            self._error(f"matrix.copy_col: {e}")

    def _builtin_matrix_sum_col(self, args: list[Any]) -> float:
        """matrix.sum_col(matrix, index) -> float"""
        if len(args) != BINARY:
            self._error("matrix.sum_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.sum_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.sum_col: index must be int")
        try:
            return matrix.sum_col(index)
        except IndexError as e:
            self._error(f"matrix.sum_col: {e}")

    def _builtin_matrix_avg_col(self, args: list[Any]) -> float:
        """matrix.avg_col(matrix, index) -> float"""
        if len(args) != BINARY:
            self._error("matrix.avg_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.avg_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.avg_col: index must be int")
        try:
            return matrix.avg_col(index)
        except IndexError as e:
            self._error(f"matrix.avg_col: {e}")

    def _builtin_matrix_min_col(self, args: list[Any]) -> Any:
        """matrix.min_col(matrix, index) -> value"""
        if len(args) != BINARY:
            self._error("matrix.min_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.min_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.min_col: index must be int")
        try:
            return matrix.min_col(index)
        except IndexError as e:
            self._error(f"matrix.min_col: {e}")

    def _builtin_matrix_max_col(self, args: list[Any]) -> Any:
        """matrix.max_col(matrix, index) -> value"""
        if len(args) != BINARY:
            self._error("matrix.max_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.max_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.max_col: index must be int")
        try:
            return matrix.max_col(index)
        except IndexError as e:
            self._error(f"matrix.max_col: {e}")

    def _builtin_matrix_mode_col(self, args: list[Any]) -> Any:
        """matrix.mode_col(matrix, index) -> value"""
        if len(args) != BINARY:
            self._error("matrix.mode_col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.mode_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.mode_col: index must be int")
        try:
            return matrix.mode_col(index)
        except IndexError as e:
            self._error(f"matrix.mode_col: {e}")

    def _builtin_matrix_fill_col(self, args: list[Any]) -> None:
        """matrix.fill_col(matrix, index, value) -> void"""
        if len(args) != TERNARY:
            self._error("matrix.fill_col requires matrix, index, value")
        matrix = self._expect_matrix(args[0], "matrix.fill_col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.fill_col: index must be int")
        value = args[BINARY]
        try:
            matrix.fill_col(index, value)
        except IndexError as e:
            self._error(f"matrix.fill_col: {e}")

    # ========== AGGREGATION OPERATIONS ==========

    def _builtin_matrix_sum_all(self, args: list[Any]) -> float:
        """matrix.sum_all(matrix) -> float"""
        if len(args) != UNARY:
            self._error("matrix.sum_all requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.sum_all: arg must be matrix")
        return matrix.sum_all()

    def _builtin_matrix_avg_all(self, args: list[Any]) -> float:
        """matrix.avg_all(matrix) -> float"""
        if len(args) != UNARY:
            self._error("matrix.avg_all requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.avg_all: arg must be matrix")
        return matrix.avg_all()

    def _builtin_matrix_min_all(self, args: list[Any]) -> Any:
        """matrix.min_all(matrix) -> value"""
        if len(args) != UNARY:
            self._error("matrix.min_all requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.min_all: arg must be matrix")
        return matrix.min_all()

    def _builtin_matrix_max_all(self, args: list[Any]) -> Any:
        """matrix.max_all(matrix) -> value"""
        if len(args) != UNARY:
            self._error("matrix.max_all requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.max_all: arg must be matrix")
        return matrix.max_all()

    def _builtin_matrix_mode_all(self, args: list[Any]) -> Any:
        """matrix.mode_all(matrix) -> value"""
        if len(args) != UNARY:
            self._error("matrix.mode_all requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.mode_all: arg must be matrix")
        return matrix.mode_all()

    # ========== FILLING OPERATIONS ==========

    def _builtin_matrix_fill(self, args: list[Any]) -> None:
        """matrix.fill(matrix, value) -> void"""
        if len(args) != BINARY:
            self._error("matrix.fill requires matrix and value")
        matrix = self._expect_matrix(args[0], "matrix.fill: first arg must be matrix")
        value = args[UNARY]
        matrix.fill(value)

    def _builtin_matrix_fill_diagonal(self, args: list[Any]) -> None:
        """matrix.fill_diagonal(matrix, value) -> void"""
        if len(args) != BINARY:
            self._error("matrix.fill_diagonal requires matrix and value")
        matrix = self._expect_matrix(args[0], "matrix.fill_diagonal: first arg must be matrix")
        value = args[UNARY]
        matrix.fill_diagonal(value)

    # ========== TRANSFORMATION OPERATIONS ==========

    def _builtin_matrix_transpose(self, args: list[Any]) -> Matrix[Any]:
        """matrix.transpose(matrix) -> Matrix"""
        if len(args) != UNARY:
            self._error("matrix.transpose requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.transpose: arg must be matrix")
        return matrix.transpose()

    def _builtin_matrix_reverse_rows(self, args: list[Any]) -> None:
        """matrix.reverse_rows(matrix) -> void"""
        if len(args) != UNARY:
            self._error("matrix.reverse_rows requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.reverse_rows: arg must be matrix")
        matrix.reverse_rows()

    def _builtin_matrix_reverse_cols(self, args: list[Any]) -> None:
        """matrix.reverse_cols(matrix) -> void"""
        if len(args) != UNARY:
            self._error("matrix.reverse_cols requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.reverse_cols: arg must be matrix")
        matrix.reverse_cols()

    def _builtin_matrix_reshape(self, args: list[Any]) -> Matrix[Any]:
        """matrix.reshape(matrix, rows, cols) -> Matrix"""
        if len(args) != TERNARY:
            self._error("matrix.reshape requires matrix, rows, cols")
        matrix = self._expect_matrix(args[0], "matrix.reshape: first arg must be matrix")
        rows = self._expect_int(args[UNARY], "matrix.reshape: rows must be int")
        cols = self._expect_int(args[BINARY], "matrix.reshape: cols must be int")
        try:
            return matrix.reshape(rows, cols)
        except ValueError as e:
            self._error(f"matrix.reshape: {e}")

    def _builtin_matrix_concat(self, args: list[Any]) -> Matrix[Any]:
        """matrix.concat(matrix1, matrix2, axis) -> Matrix"""
        if len(args) < BINARY:
            self._error("matrix.concat requires at least two matrices")
        matrix1 = self._expect_matrix(args[0], "matrix.concat: first arg must be matrix")
        matrix2 = self._expect_matrix(args[UNARY], "matrix.concat: second arg must be matrix")
        axis = self._expect_int(args[BINARY], "matrix.concat: axis must be int") if len(args) > BINARY else 0
        try:
            return matrix1.concat(matrix2, axis)
        except ValueError as e:
            self._error(f"matrix.concat: {e}")

    def _builtin_matrix_copy(self, args: list[Any]) -> Matrix[Any]:
        """matrix.copy(matrix) -> Matrix"""
        if len(args) != UNARY:
            self._error("matrix.copy requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.copy: arg must be matrix")
        return matrix.copy()
