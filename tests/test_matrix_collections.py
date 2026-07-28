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

"""Tests for Matrix collection type (Phase 4)."""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.ast.evaluator.builtins.matrix import Matrix


class TestMatrixCore:
    """Test core Matrix methods."""

    def test_matrix_init_empty(self) -> None:
        """Test creating empty matrix."""
        m: Matrix[Any] = Matrix()
        assert m.rows() == 0
        assert m.columns() == 0
        assert m.elements_count() == 0

    def test_matrix_init_with_dimensions(self) -> None:
        """Test creating matrix with dimensions."""
        m: Matrix[Any] = Matrix(3, 4, default_value=0)
        assert m.rows() == 3
        assert m.columns() == 4
        assert m.elements_count() == 12

    def test_matrix_init_with_default_value(self) -> None:
        """Test all elements initialized to default value."""
        m: Matrix[Any] = Matrix(2, 3, default_value=5)
        for i in range(2):
            for j in range(3):
                assert m.get(i, j) == 5

    def test_matrix_get_set(self) -> None:
        """Test get and set operations."""
        m: Matrix[Any] = Matrix(2, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(1, 0, 3)
        m.set(1, 1, 4)
        assert m.get(0, 0) == 1
        assert m.get(0, 1) == 2
        assert m.get(1, 0) == 3
        assert m.get(1, 1) == 4

    def test_matrix_get_out_of_bounds(self) -> None:
        """Test get with out of bounds index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.get(2, 0)
        with pytest.raises(IndexError):
            m.get(0, 2)
        with pytest.raises(IndexError):
            m.get(-1, 0)

    def test_matrix_set_out_of_bounds(self) -> None:
        """Test set with out of bounds index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.set(2, 0, 5)
        with pytest.raises(IndexError):
            m.set(0, 2, 5)

    def test_matrix_repr(self) -> None:
        """Test matrix string representation."""
        m: Matrix[Any] = Matrix(3, 4)
        assert repr(m) == "matrix(3x4)"


class TestMatrixRowOperations:
    """Test row operations."""

    def test_add_row(self) -> None:
        """Test adding a row."""
        m: Matrix[Any] = Matrix(1, 3, default_value=0)
        m.add_row([1, 2, 3])
        assert m.rows() == 2
        assert m.get(1, 0) == 1
        assert m.get(1, 1) == 2
        assert m.get(1, 2) == 3

    def test_add_row_wrong_size(self) -> None:
        """Test adding row with wrong size."""
        m: Matrix[Any] = Matrix(1, 3)
        with pytest.raises(ValueError):
            m.add_row([1, 2])

    def test_remove_row(self) -> None:
        """Test removing a row."""
        m: Matrix[Any] = Matrix(3, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(1, 0, 2)
        m.set(2, 0, 3)
        m.remove_row(1)
        assert m.rows() == 2
        assert m.get(0, 0) == 1
        assert m.get(1, 0) == 3

    def test_remove_row_out_of_bounds(self) -> None:
        """Test removing row at invalid index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.remove_row(2)

    def test_copy_row(self) -> None:
        """Test copying a row."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        row: list[Any] = m.copy_row(0)
        assert row == [1, 2, 3]
        row[0] = 99
        assert m.get(0, 0) == 1

    def test_copy_row_out_of_bounds(self) -> None:
        """Test copying row at invalid index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.copy_row(2)

    def test_sum_row(self) -> None:
        """Test summing row elements."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        assert m.sum_row(0) == 6

    def test_sum_row_with_floats(self) -> None:
        """Test summing row with float values."""
        m: Matrix[Any] = Matrix(1, 3, default_value=0)
        m.set(0, 0, 1.5)
        m.set(0, 1, 2.5)
        m.set(0, 2, 3.0)
        assert m.sum_row(0) == 7.0

    def test_sum_row_with_non_numeric(self) -> None:
        """Test summing row with non-numeric elements."""
        m: Matrix[Any] = Matrix(1, 3)
        m.set(0, 0, 1)
        m.set(0, 1, "text")
        m.set(0, 2, 3)
        assert m.sum_row(0) == 4

    def test_avg_row(self) -> None:
        """Test averaging row elements."""
        m: Matrix[Any] = Matrix(1, 4, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        m.set(0, 3, 4)
        assert m.avg_row(0) == 2.5

    def test_avg_row_empty_numeric(self) -> None:
        """Test averaging row with no numeric elements."""
        m: Matrix[Any] = Matrix(1, 2)
        m.set(0, 0, "a")
        m.set(0, 1, "b")
        assert m.avg_row(0) == 0

    def test_min_row(self) -> None:
        """Test finding minimum in row."""
        m: Matrix[Any] = Matrix(1, 4, default_value=0)
        m.set(0, 0, 5)
        m.set(0, 1, 2)
        m.set(0, 2, 8)
        m.set(0, 3, 1)
        assert m.min_row(0) == 1

    def test_min_row_no_numeric(self) -> None:
        """Test minimum with no numeric elements."""
        m: Matrix[Any] = Matrix(1, 2)
        m.set(0, 0, "a")
        m.set(0, 1, "b")
        assert m.min_row(0) is None

    def test_max_row(self) -> None:
        """Test finding maximum in row."""
        m: Matrix[Any] = Matrix(1, 4, default_value=0)
        m.set(0, 0, 5)
        m.set(0, 1, 2)
        m.set(0, 2, 8)
        m.set(0, 3, 1)
        assert m.max_row(0) == 8

    def test_max_row_no_numeric(self) -> None:
        """Test maximum with no numeric elements."""
        m: Matrix[Any] = Matrix(1, 2)
        m.set(0, 0, "a")
        m.set(0, 1, "b")
        assert m.max_row(0) is None

    def test_mode_row(self) -> None:
        """Test finding mode in row."""
        m: Matrix[Any] = Matrix(1, 5, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 2)
        m.set(0, 3, 3)
        m.set(0, 4, 2)
        assert m.mode_row(0) == 2

    def test_mode_row_empty(self) -> None:
        """Test mode on empty row."""
        m: Matrix[Any] = Matrix(0, 3)
        m.data = [[]]
        m.rows_count = 1
        assert m.mode_row(0) is None

    def test_fill_row(self) -> None:
        """Test filling a row with value."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.fill_row(0, 5)
        assert m.get(0, 0) == 5
        assert m.get(0, 1) == 5
        assert m.get(0, 2) == 5
        assert m.get(1, 0) == 0

    def test_fill_row_out_of_bounds(self) -> None:
        """Test filling row at invalid index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.fill_row(2, 5)


class TestMatrixColumnOperations:
    """Test column operations."""

    def test_add_col(self) -> None:
        """Test adding a column."""
        m: Matrix[Any] = Matrix(3, 1, default_value=0)
        m.add_col([1, 2, 3])
        assert m.columns() == 2
        assert m.get(0, 1) == 1
        assert m.get(1, 1) == 2
        assert m.get(2, 1) == 3

    def test_add_col_wrong_size(self) -> None:
        """Test adding column with wrong size."""
        m: Matrix[Any] = Matrix(3, 1)
        with pytest.raises(ValueError):
            m.add_col([1, 2])

    def test_remove_col(self) -> None:
        """Test removing a column."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        m.remove_col(1)
        assert m.columns() == 2
        assert m.get(0, 0) == 1
        assert m.get(0, 1) == 3

    def test_remove_col_out_of_bounds(self) -> None:
        """Test removing column at invalid index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.remove_col(2)

    def test_copy_col(self) -> None:
        """Test copying a column."""
        m: Matrix[Any] = Matrix(3, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(1, 0, 2)
        m.set(2, 0, 3)
        col: list[Any] = m.copy_col(0)
        assert col == [1, 2, 3]
        col[0] = 99
        assert m.get(0, 0) == 1

    def test_copy_col_out_of_bounds(self) -> None:
        """Test copying column at invalid index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.copy_col(2)

    def test_sum_col(self) -> None:
        """Test summing column elements."""
        m: Matrix[Any] = Matrix(3, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(1, 0, 2)
        m.set(2, 0, 3)
        assert m.sum_col(0) == 6

    def test_avg_col(self) -> None:
        """Test averaging column elements."""
        m: Matrix[Any] = Matrix(4, 1, default_value=0)
        m.set(0, 0, 1)
        m.set(1, 0, 2)
        m.set(2, 0, 3)
        m.set(3, 0, 4)
        assert m.avg_col(0) == 2.5

    def test_min_col(self) -> None:
        """Test finding minimum in column."""
        m: Matrix[Any] = Matrix(4, 1, default_value=0)
        m.set(0, 0, 5)
        m.set(1, 0, 2)
        m.set(2, 0, 8)
        m.set(3, 0, 1)
        assert m.min_col(0) == 1

    def test_max_col(self) -> None:
        """Test finding maximum in column."""
        m: Matrix[Any] = Matrix(4, 1, default_value=0)
        m.set(0, 0, 5)
        m.set(1, 0, 2)
        m.set(2, 0, 8)
        m.set(3, 0, 1)
        assert m.max_col(0) == 8

    def test_mode_col(self) -> None:
        """Test finding mode in column."""
        m: Matrix[Any] = Matrix(5, 1, default_value=0)
        m.set(0, 0, 1)
        m.set(1, 0, 2)
        m.set(2, 0, 2)
        m.set(3, 0, 3)
        m.set(4, 0, 2)
        assert m.mode_col(0) == 2

    def test_fill_col(self) -> None:
        """Test filling a column with value."""
        m: Matrix[Any] = Matrix(3, 2, default_value=0)
        m.fill_col(0, 7)
        assert m.get(0, 0) == 7
        assert m.get(1, 0) == 7
        assert m.get(2, 0) == 7
        assert m.get(0, 1) == 0

    def test_fill_col_out_of_bounds(self) -> None:
        """Test filling column at invalid index."""
        m: Matrix[Any] = Matrix(2, 2)
        with pytest.raises(IndexError):
            m.fill_col(2, 5)


class TestMatrixAggregations:
    """Test aggregation operations."""

    def test_sum_all(self) -> None:
        """Test summing all elements."""
        m: Matrix[Any] = Matrix(2, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(1, 0, 3)
        m.set(1, 1, 4)
        assert m.sum_all() == 10

    def test_sum_all_with_non_numeric(self) -> None:
        """Test sum_all with non-numeric elements."""
        m: Matrix[Any] = Matrix(2, 2)
        m.set(0, 0, 1)
        m.set(0, 1, "text")
        m.set(1, 0, 3)
        m.set(1, 1, 4)
        assert m.sum_all() == 8

    def test_avg_all(self) -> None:
        """Test averaging all elements."""
        m: Matrix[Any] = Matrix(2, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(1, 0, 3)
        m.set(1, 1, 4)
        assert m.avg_all() == 2.5

    def test_avg_all_empty_matrix(self) -> None:
        """Test avg_all on empty matrix."""
        m: Matrix[Any] = Matrix()
        assert m.avg_all() == 0

    def test_min_all(self) -> None:
        """Test finding minimum of all elements."""
        m: Matrix[Any] = Matrix(2, 2, default_value=0)
        m.set(0, 0, 5)
        m.set(0, 1, 2)
        m.set(1, 0, 8)
        m.set(1, 1, 1)
        assert m.min_all() == 1

    def test_max_all(self) -> None:
        """Test finding maximum of all elements."""
        m: Matrix[Any] = Matrix(2, 2, default_value=0)
        m.set(0, 0, 5)
        m.set(0, 1, 2)
        m.set(1, 0, 8)
        m.set(1, 1, 1)
        assert m.max_all() == 8

    def test_mode_all(self) -> None:
        """Test finding mode of all elements."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 2)
        m.set(1, 0, 3)
        m.set(1, 1, 2)
        m.set(1, 2, 4)
        assert m.mode_all() == 2


class TestMatrixFilling:
    """Test filling operations."""

    def test_fill(self) -> None:
        """Test filling entire matrix."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.fill(5)
        for i in range(2):
            for j in range(3):
                assert m.get(i, j) == 5

    def test_fill_diagonal(self) -> None:
        """Test filling diagonal."""
        m: Matrix[Any] = Matrix(3, 3, default_value=0)
        m.fill_diagonal(7)
        assert m.get(0, 0) == 7
        assert m.get(1, 1) == 7
        assert m.get(2, 2) == 7
        assert m.get(0, 1) == 0
        assert m.get(1, 0) == 0

    def test_fill_diagonal_rectangular(self) -> None:
        """Test filling diagonal on non-square matrix."""
        m: Matrix[Any] = Matrix(2, 4, default_value=0)
        m.fill_diagonal(5)
        assert m.get(0, 0) == 5
        assert m.get(1, 1) == 5
        assert m.get(0, 2) == 0


class TestMatrixTransformations:
    """Test transformation operations."""

    def test_transpose(self) -> None:
        """Test matrix transpose."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        m.set(1, 0, 4)
        m.set(1, 1, 5)
        m.set(1, 2, 6)
        t: Matrix[Any] = m.transpose()
        assert t.rows() == 3
        assert t.columns() == 2
        assert t.get(0, 0) == 1
        assert t.get(0, 1) == 4
        assert t.get(1, 0) == 2
        assert t.get(1, 1) == 5
        assert t.get(2, 0) == 3
        assert t.get(2, 1) == 6

    def test_reverse_rows(self) -> None:
        """Test reversing row order."""
        m: Matrix[Any] = Matrix(3, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(1, 0, 2)
        m.set(2, 0, 3)
        m.reverse_rows()
        assert m.get(0, 0) == 3
        assert m.get(1, 0) == 2
        assert m.get(2, 0) == 1

    def test_reverse_cols(self) -> None:
        """Test reversing column order."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        m.reverse_cols()
        assert m.get(0, 0) == 3
        assert m.get(0, 1) == 2
        assert m.get(0, 2) == 1

    def test_reshape(self) -> None:
        """Test reshaping matrix."""
        m: Matrix[Any] = Matrix(2, 3, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(0, 2, 3)
        m.set(1, 0, 4)
        m.set(1, 1, 5)
        m.set(1, 2, 6)
        r: Matrix[Any] = m.reshape(3, 2)
        assert r.rows() == 3
        assert r.columns() == 2
        assert r.get(0, 0) == 1
        assert r.get(0, 1) == 2
        assert r.get(1, 0) == 3
        assert r.get(1, 1) == 4

    def test_reshape_invalid(self) -> None:
        """Test reshape with incompatible dimensions."""
        m: Matrix[Any] = Matrix(2, 3)
        with pytest.raises(ValueError):
            m.reshape(2, 2)

    def test_concat_rows(self) -> None:
        """Test concatenating matrices by rows."""
        m1: Matrix[Any] = Matrix(2, 2, default_value=0)
        m1.set(0, 0, 1)
        m1.set(0, 1, 2)
        m1.set(1, 0, 3)
        m1.set(1, 1, 4)

        m2: Matrix[Any] = Matrix(1, 2, default_value=0)
        m2.set(0, 0, 5)
        m2.set(0, 1, 6)

        result: Matrix[Any] = m1.concat(m2, axis=0)
        assert result.rows() == 3
        assert result.columns() == 2
        assert result.get(2, 0) == 5
        assert result.get(2, 1) == 6

    def test_concat_cols(self) -> None:
        """Test concatenating matrices by columns."""
        m1: Matrix[Any] = Matrix(2, 2, default_value=0)
        m1.set(0, 0, 1)
        m1.set(0, 1, 2)
        m1.set(1, 0, 3)
        m1.set(1, 1, 4)

        m2: Matrix[Any] = Matrix(2, 1, default_value=0)
        m2.set(0, 0, 5)
        m2.set(1, 0, 6)

        result: Matrix[Any] = m1.concat(m2, axis=1)
        assert result.rows() == 2
        assert result.columns() == 3
        assert result.get(0, 2) == 5
        assert result.get(1, 2) == 6

    def test_concat_rows_column_mismatch(self) -> None:
        """Test concat rows with mismatched columns."""
        m1: Matrix[Any] = Matrix(2, 2)
        m2: Matrix[Any] = Matrix(2, 3)
        with pytest.raises(ValueError):
            m1.concat(m2, axis=0)

    def test_concat_cols_row_mismatch(self) -> None:
        """Test concat cols with mismatched rows."""
        m1: Matrix[Any] = Matrix(2, 2)
        m2: Matrix[Any] = Matrix(3, 2)
        with pytest.raises(ValueError):
            m1.concat(m2, axis=1)

    def test_copy(self) -> None:
        """Test deep copying matrix."""
        m: Matrix[Any] = Matrix(2, 2, default_value=0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(1, 0, 3)
        m.set(1, 1, 4)

        copy: Matrix[Any] = m.copy()
        assert copy.rows() == 2
        assert copy.columns() == 2
        assert copy.get(0, 0) == 1
        m.set(0, 0, 99)
        assert copy.get(0, 0) == 1
