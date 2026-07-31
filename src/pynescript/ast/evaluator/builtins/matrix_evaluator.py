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
            # Official TV v6 names (aliases + linear algebra)
            "matrix.row": self._builtin_matrix_row,
            "matrix.col": self._builtin_matrix_col,
            "matrix.submatrix": self._builtin_matrix_submatrix,
            "matrix.swap_rows": self._builtin_matrix_swap_rows,
            "matrix.swap_columns": self._builtin_matrix_swap_columns,
            "matrix.reverse": self._builtin_matrix_reverse,
            "matrix.sort": self._builtin_matrix_sort,
            "matrix.sort_indices": self._builtin_matrix_sort_indices,
            "matrix.avg": self._builtin_matrix_avg_all,
            "matrix.min": self._builtin_matrix_min_all,
            "matrix.max": self._builtin_matrix_max_all,
            "matrix.mode": self._builtin_matrix_mode_all,
            "matrix.median": self._builtin_matrix_median,
            "matrix.stdev": self._builtin_matrix_stdev,
            "matrix.variance": self._builtin_matrix_variance,
            "matrix.sum": self._builtin_matrix_sum,
            "matrix.diff": self._builtin_matrix_diff,
            "matrix.mult": self._builtin_matrix_mult,
            "matrix.det": self._builtin_matrix_det,
            "matrix.inv": self._builtin_matrix_inv,
            "matrix.pinv": self._builtin_matrix_pinv,
            "matrix.eigenvalues": self._builtin_matrix_eigenvalues,
            "matrix.eigenvectors": self._builtin_matrix_eigenvectors,
            "matrix.kron": self._builtin_matrix_kron,
            "matrix.pow": self._builtin_matrix_pow,
            "matrix.trace": self._builtin_matrix_trace,
            "matrix.rank": self._builtin_matrix_rank,
            "matrix.is_square": self._builtin_matrix_is_square,
            "matrix.is_zero": self._builtin_matrix_is_zero,
            "matrix.is_identity": self._builtin_matrix_is_identity,
            "matrix.is_diagonal": self._builtin_matrix_is_diagonal,
            "matrix.is_antidiagonal": self._builtin_matrix_is_antidiagonal,
            "matrix.is_symmetric": self._builtin_matrix_is_symmetric,
            "matrix.is_antisymmetric": self._builtin_matrix_is_antisymmetric,
            "matrix.is_triangular": self._builtin_matrix_is_triangular,
            "matrix.is_binary": self._builtin_matrix_is_binary,
            "matrix.is_stochastic": self._builtin_matrix_is_stochastic,
        }

    # ========== HELPER METHODS ==========

    def _expect_matrix(self, value: Any, message: str) -> Matrix[Any]:
        """Validate that value is a Matrix instance (or list-of-lists handle)."""
        if isinstance(value, Matrix):
            return value
        if value is None:
            self._error(f"{message} (got na)")
        # Compile-path / host bridges use list-of-lists matrices — share storage
        # so get/set/add_row mutate the original handle.
        if isinstance(value, list) and (not value or isinstance(value[0], list)):
            m: Matrix[Any] = Matrix(0, 0, None)
            m.data = value
            m.rows_count = len(value)
            m.cols_count = len(value[0]) if value and isinstance(value[0], list) else 0
            return m
        tname = type(value).__name__
        self._error(f"{message} (got {tname}, expected matrix)")

    # _expect_int: inherited from BuiltinDispatchMixin (pine_expect_int).
    # Note: floors fractional floats (TV length semantics) rather than rejecting.

    def _expect_list(self, value: Any, message: str) -> list[Any]:
        """Validate that value is a list."""
        if isinstance(value, list):
            return value
        if value is None:
            self._error(f"{message} (got na)")
        tname = type(value).__name__
        self._error(f"{message} (got {tname}, expected array)")

    # ========== CORE OPERATIONS ==========

    def _builtin_matrix_new(self, args: list[Any]) -> Matrix[Any]:
        """matrix.new() | matrix.new(rows, cols, default_value?) -> Matrix.

        Zero-arg form creates an empty 0×0 matrix (TV ``matrix.new<T>()``).
        """
        if not args:
            return Matrix(0, 0, None)
        if len(args) == UNARY:
            # Single arg is non-standard; treat as empty for soft recovery.
            return Matrix(0, 0, None)
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
        """matrix.add_row(id) | matrix.add_row(id, array) | matrix.add_row(id, row, array).

        TV: omitting the array appends a row of ``na`` (None) values. Instance
        form ``m.add_row()`` is common in scripts such as seasonality.
        Three-arg form inserts at *row* index (not always append).
        """
        if not args:
            self._error("matrix.add_row requires a matrix")
        matrix = self._expect_matrix(args[0], "matrix.add_row: first arg must be matrix")
        row_data: list[Any]
        row_index: int | None = None
        if len(args) == 1:
            row_data = [None] * matrix.cols_count
        elif len(args) == BINARY:
            # Could be (matrix, array) or (matrix, row_index) — prefer array
            if isinstance(args[UNARY], list):
                row_data = args[UNARY]
            else:
                row_index = self._expect_int(args[UNARY], "matrix.add_row: row index must be int")
                row_data = [None] * (matrix.cols_count if matrix.cols_count else 0)
        elif len(args) >= 3:
            # (matrix, row_index, array)
            row_index = self._expect_int(args[UNARY], "matrix.add_row: row index must be int")
            row_data = (
                args[2]
                if isinstance(args[2], list)
                else self._expect_list(args[2], "matrix.add_row: array required")
            )
        else:
            self._error("matrix.add_row requires matrix and optional row data")
            return
        try:
            matrix.add_row(row_data, index=row_index)
        except (ValueError, IndexError) as e:
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
        """matrix.add_col(id) | matrix.add_col(id, array) | matrix.add_col(id, column, array)."""
        if not args:
            self._error("matrix.add_col requires a matrix")
        matrix = self._expect_matrix(args[0], "matrix.add_col: first arg must be matrix")
        col_data: list[Any]
        col_index: int | None = None
        if len(args) == 1:
            col_data = [None] * matrix.rows_count
        elif len(args) == BINARY:
            if isinstance(args[UNARY], list):
                col_data = args[UNARY]
            else:
                col_index = self._expect_int(args[UNARY], "matrix.add_col: column index must be int")
                col_data = [None] * matrix.rows_count
        elif len(args) >= 3:
            col_index = self._expect_int(args[UNARY], "matrix.add_col: column index must be int")
            col_data = (
                args[2]
                if isinstance(args[2], list)
                else self._expect_list(args[2], "matrix.add_col: array required")
            )
        else:
            self._error("matrix.add_col requires matrix and optional column data")
            return
        try:
            matrix.add_col(col_data, index=col_index)
        except (ValueError, IndexError) as e:
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

    # ========== OFFICIAL TV v6 SURFACE ==========

    def _builtin_matrix_row(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("matrix.row requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.row: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.row: index must be int")
        try:
            return matrix.row(index)
        except IndexError as e:
            self._error(f"matrix.row: {e}")

    def _builtin_matrix_col(self, args: list[Any]) -> list[Any]:
        if len(args) != BINARY:
            self._error("matrix.col requires matrix and index")
        matrix = self._expect_matrix(args[0], "matrix.col: first arg must be matrix")
        index = self._expect_int(args[UNARY], "matrix.col: index must be int")
        try:
            return matrix.col(index)
        except IndexError as e:
            self._error(f"matrix.col: {e}")

    def _builtin_matrix_submatrix(self, args: list[Any]) -> Matrix[Any]:
        if len(args) < UNARY:
            self._error("matrix.submatrix requires a matrix")
        matrix = self._expect_matrix(args[0], "matrix.submatrix: first arg must be matrix")
        from_row = self._expect_int(args[1], "from_row") if len(args) > 1 and args[1] is not None else 0
        to_row = self._expect_int(args[2], "to_row") if len(args) > 2 and args[2] is not None else None
        from_col = self._expect_int(args[3], "from_col") if len(args) > 3 and args[3] is not None else 0
        to_col = self._expect_int(args[4], "to_col") if len(args) > 4 and args[4] is not None else None
        try:
            return matrix.submatrix(from_row, to_row, from_col, to_col)
        except (IndexError, ValueError) as e:
            self._error(f"matrix.submatrix: {e}")

    def _builtin_matrix_swap_rows(self, args: list[Any]) -> None:
        if len(args) != TERNARY:
            self._error("matrix.swap_rows requires matrix, row1, row2")
        matrix = self._expect_matrix(args[0], "matrix.swap_rows: first arg must be matrix")
        r1 = self._expect_int(args[UNARY], "matrix.swap_rows: row1 must be int")
        r2 = self._expect_int(args[BINARY], "matrix.swap_rows: row2 must be int")
        try:
            matrix.swap_rows(r1, r2)
        except IndexError as e:
            self._error(f"matrix.swap_rows: {e}")

    def _builtin_matrix_swap_columns(self, args: list[Any]) -> None:
        if len(args) != TERNARY:
            self._error("matrix.swap_columns requires matrix, col1, col2")
        matrix = self._expect_matrix(args[0], "matrix.swap_columns: first arg must be matrix")
        c1 = self._expect_int(args[UNARY], "matrix.swap_columns: col1 must be int")
        c2 = self._expect_int(args[BINARY], "matrix.swap_columns: col2 must be int")
        try:
            matrix.swap_columns(c1, c2)
        except IndexError as e:
            self._error(f"matrix.swap_columns: {e}")

    def _builtin_matrix_reverse(self, args: list[Any]) -> None:
        if len(args) != UNARY:
            self._error("matrix.reverse requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.reverse: arg must be matrix")
        matrix.reverse()

    def _builtin_matrix_sort(self, args: list[Any]) -> None:
        """matrix.sort(id, column?, order?, sort_field?) — UDT sort_field supported."""
        if len(args) < UNARY:
            self._error("matrix.sort requires a matrix")
        matrix = self._expect_matrix(args[0], "matrix.sort: first arg must be matrix")
        column = self._expect_int(args[1], "column") if len(args) > 1 and args[1] is not None else 0
        order = args[2] if len(args) > 2 else "ascending"
        sort_field = args[3] if len(args) > 3 else None
        try:
            matrix.sort(column, order, sort_field=sort_field)
        except (IndexError, TypeError, ValueError) as e:
            self._error(f"matrix.sort: {e}")

    def _builtin_matrix_sort_indices(self, args: list[Any]) -> list[int]:
        """matrix.sort_indices(id, column?, order?, sort_field?) — UDT sort_field supported."""
        if len(args) < UNARY:
            self._error("matrix.sort_indices requires a matrix")
        matrix = self._expect_matrix(args[0], "matrix.sort_indices: first arg must be matrix")
        column = self._expect_int(args[1], "column") if len(args) > 1 and args[1] is not None else 0
        order = args[2] if len(args) > 2 else "ascending"
        sort_field = args[3] if len(args) > 3 else None
        try:
            return matrix.sort_indices(column, order, sort_field=sort_field)
        except (IndexError, TypeError, ValueError) as e:
            self._error(f"matrix.sort_indices: {e}")

    def _builtin_matrix_median(self, args: list[Any]) -> float | None:
        if len(args) != UNARY:
            self._error("matrix.median requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.median: arg must be matrix")
        return matrix.median()

    def _builtin_matrix_stdev(self, args: list[Any]) -> float | None:
        if len(args) != UNARY:
            self._error("matrix.stdev requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.stdev: arg must be matrix")
        return matrix.stdev()

    def _builtin_matrix_variance(self, args: list[Any]) -> float | None:
        if len(args) != UNARY:
            self._error("matrix.variance requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.variance: arg must be matrix")
        return matrix.variance()

    def _builtin_matrix_sum(self, args: list[Any]) -> Any:
        """matrix.sum(id) → sum_all; matrix.sum(id1, id2) → element-wise add."""
        if len(args) == UNARY:
            matrix = self._expect_matrix(args[0], "matrix.sum: arg must be matrix")
            return matrix.sum_all()
        if len(args) == BINARY:
            m1 = self._expect_matrix(args[0], "matrix.sum: first arg must be matrix")
            m2 = self._expect_matrix(args[UNARY], "matrix.sum: second arg must be matrix")
            try:
                return m1.sum_matrices(m2)
            except ValueError as e:
                self._error(f"matrix.sum: {e}")
        self._error("matrix.sum requires one or two matrix arguments")

    def _builtin_matrix_diff(self, args: list[Any]) -> Matrix[Any]:
        if len(args) != BINARY:
            self._error("matrix.diff requires two matrices")
        m1 = self._expect_matrix(args[0], "matrix.diff: first arg must be matrix")
        m2 = self._expect_matrix(args[UNARY], "matrix.diff: second arg must be matrix")
        try:
            return m1.diff(m2)
        except ValueError as e:
            self._error(f"matrix.diff: {e}")

    def _builtin_matrix_mult(self, args: list[Any]) -> Any:
        if len(args) != BINARY:
            self._error("matrix.mult requires two arguments")
        m1 = self._expect_matrix(args[0], "matrix.mult: first arg must be matrix")
        other = args[UNARY]
        try:
            return m1.mult(other)
        except (ValueError, TypeError) as e:
            self._error(f"matrix.mult: {e}")

    def _builtin_matrix_det(self, args: list[Any]) -> float:
        if len(args) != UNARY:
            self._error("matrix.det requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.det: arg must be matrix")
        try:
            return matrix.det()
        except ValueError as e:
            self._error(f"matrix.det: {e}")

    def _builtin_matrix_inv(self, args: list[Any]) -> Matrix[Any]:
        if len(args) != UNARY:
            self._error("matrix.inv requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.inv: arg must be matrix")
        try:
            return matrix.inv()
        except Exception as e:
            self._error(f"matrix.inv: {e}")

    def _builtin_matrix_pinv(self, args: list[Any]) -> Matrix[Any]:
        if len(args) != UNARY:
            self._error("matrix.pinv requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.pinv: arg must be matrix")
        try:
            return matrix.pinv()
        except Exception as e:
            self._error(f"matrix.pinv: {e}")

    def _builtin_matrix_eigenvalues(self, args: list[Any]) -> list[float]:
        if len(args) != UNARY:
            self._error("matrix.eigenvalues requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.eigenvalues: arg must be matrix")
        try:
            return matrix.eigenvalues()
        except ValueError as e:
            self._error(f"matrix.eigenvalues: {e}")

    def _builtin_matrix_eigenvectors(self, args: list[Any]) -> Matrix[Any]:
        if len(args) != UNARY:
            self._error("matrix.eigenvectors requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.eigenvectors: arg must be matrix")
        try:
            return matrix.eigenvectors()
        except ValueError as e:
            self._error(f"matrix.eigenvectors: {e}")

    def _builtin_matrix_kron(self, args: list[Any]) -> Matrix[Any]:
        if len(args) != BINARY:
            self._error("matrix.kron requires two matrices")
        m1 = self._expect_matrix(args[0], "matrix.kron: first arg must be matrix")
        m2 = self._expect_matrix(args[UNARY], "matrix.kron: second arg must be matrix")
        return m1.kron(m2)

    def _builtin_matrix_pow(self, args: list[Any]) -> Matrix[Any]:
        if len(args) != BINARY:
            self._error("matrix.pow requires matrix and exponent")
        matrix = self._expect_matrix(args[0], "matrix.pow: first arg must be matrix")
        n = self._expect_int(args[UNARY], "matrix.pow: exponent must be int")
        try:
            return matrix.pow(n)
        except ValueError as e:
            self._error(f"matrix.pow: {e}")

    def _builtin_matrix_trace(self, args: list[Any]) -> float:
        if len(args) != UNARY:
            self._error("matrix.trace requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.trace: arg must be matrix")
        return matrix.trace()

    def _builtin_matrix_rank(self, args: list[Any]) -> int:
        if len(args) != UNARY:
            self._error("matrix.rank requires one matrix argument")
        matrix = self._expect_matrix(args[0], "matrix.rank: arg must be matrix")
        return matrix.rank()

    def _builtin_matrix_is_square(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_square requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_square").is_square()

    def _builtin_matrix_is_zero(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_zero requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_zero").is_zero()

    def _builtin_matrix_is_identity(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_identity requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_identity").is_identity()

    def _builtin_matrix_is_diagonal(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_diagonal requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_diagonal").is_diagonal()

    def _builtin_matrix_is_antidiagonal(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_antidiagonal requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_antidiagonal").is_antidiagonal()

    def _builtin_matrix_is_symmetric(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_symmetric requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_symmetric").is_symmetric()

    def _builtin_matrix_is_antisymmetric(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_antisymmetric requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_antisymmetric").is_antisymmetric()

    def _builtin_matrix_is_triangular(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_triangular requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_triangular").is_triangular()

    def _builtin_matrix_is_binary(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_binary requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_binary").is_binary()

    def _builtin_matrix_is_stochastic(self, args: list[Any]) -> bool:
        if len(args) != UNARY:
            self._error("matrix.is_stochastic requires one matrix argument")
        return self._expect_matrix(args[0], "matrix.is_stochastic").is_stochastic()


# Named-parameter order for list-style matrix handlers (Pine kwargs).
MatrixBuiltinsMixin._builtin_matrix_sort._KWARG_ORDER = ["id", "column", "order", "sort_field"]
MatrixBuiltinsMixin._builtin_matrix_sort_indices._KWARG_ORDER = ["id", "column", "order", "sort_field"]
MatrixBuiltinsMixin._builtin_matrix_add_row._KWARG_ORDER = ["id", "row", "array_id"]
MatrixBuiltinsMixin._builtin_matrix_add_col._KWARG_ORDER = ["id", "column", "array_id"]
MatrixBuiltinsMixin._builtin_matrix_new._KWARG_ORDER = ["rows", "columns", "initial_value"]
