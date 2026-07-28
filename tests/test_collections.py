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

"""Integration tests for collections (arrays, matrices, maps)."""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.ast.evaluator.builtins import BuiltinEvaluator
from pynescript.ast.evaluator.builtins.map import Map
from pynescript.ast.evaluator.builtins.matrix import Matrix


class TestMatrixEvaluatorIntegration:
    """Integration tests for Matrix builtin evaluator."""

    def setup_method(self) -> None:
        """Set up test evaluator."""
        self.evaluator = BuiltinEvaluator()

    def _call_builtin(self, name: str, args: list[Any]) -> Any:
        """Helper to call builtin method."""
        return self.evaluator._call_builtin(name, args)

    # ========== CORE OPERATIONS ==========

    def test_matrix_new_basic(self) -> None:
        """Test matrix.new creates matrix."""
        matrix = self._call_builtin("matrix.new", [3, 4])
        assert isinstance(matrix, Matrix)
        assert matrix.rows() == 3
        assert matrix.columns() == 4

    def test_matrix_new_with_default(self) -> None:
        """Test matrix.new with default value."""
        matrix = self._call_builtin("matrix.new", [2, 2, 5])
        assert matrix.rows() == 2
        assert matrix.columns() == 2
        assert matrix.get(0, 0) == 5

    def test_matrix_get_basic(self) -> None:
        """Test matrix.get retrieves value."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        matrix.set(0, 0, 42)
        result = self._call_builtin("matrix.get", [matrix, 0, 0])
        assert result == 42

    def test_matrix_set_basic(self) -> None:
        """Test matrix.set modifies value."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        self._call_builtin("matrix.set", [matrix, 0, 0, 99])
        assert matrix.get(0, 0) == 99

    def test_matrix_rows(self) -> None:
        """Test matrix.rows returns row count."""
        matrix = self._call_builtin("matrix.new", [5, 3])
        result = self._call_builtin("matrix.rows", [matrix])
        assert result == 5

    def test_matrix_columns(self) -> None:
        """Test matrix.columns returns column count."""
        matrix = self._call_builtin("matrix.new", [3, 7])
        result = self._call_builtin("matrix.columns", [matrix])
        assert result == 7

    def test_matrix_elements_count(self) -> None:
        """Test matrix.elements_count returns total elements."""
        matrix = self._call_builtin("matrix.new", [4, 5])
        result = self._call_builtin("matrix.elements_count", [matrix])
        assert result == 20

    # ========== ROW OPERATIONS ==========

    def test_matrix_add_row(self) -> None:
        """Test matrix.add_row adds new row."""
        matrix = self._call_builtin("matrix.new", [1, 3])
        self._call_builtin("matrix.add_row", [matrix, [1, 2, 3]])
        assert matrix.rows() == 2
        assert matrix.get(1, 0) == 1

    def test_matrix_remove_row(self) -> None:
        """Test matrix.remove_row removes row."""
        matrix = self._call_builtin("matrix.new", [3, 2])
        self._call_builtin("matrix.remove_row", [matrix, 1])
        assert matrix.rows() == 2

    def test_matrix_copy_row(self) -> None:
        """Test matrix.copy_row returns row data."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 3)
        row = self._call_builtin("matrix.copy_row", [matrix, 0])
        assert row == [1, 2, 3]

    def test_matrix_sum_row(self) -> None:
        """Test matrix.sum_row sums row values."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 3)
        result = self._call_builtin("matrix.sum_row", [matrix, 0])
        assert result == 6

    def test_matrix_avg_row(self) -> None:
        """Test matrix.avg_row averages row values."""
        matrix = self._call_builtin("matrix.new", [1, 4])
        matrix.set(0, 0, 2)
        matrix.set(0, 1, 4)
        matrix.set(0, 2, 6)
        matrix.set(0, 3, 8)
        result = self._call_builtin("matrix.avg_row", [matrix, 0])
        assert result == 5.0

    def test_matrix_min_row(self) -> None:
        """Test matrix.min_row finds minimum in row."""
        matrix = self._call_builtin("matrix.new", [1, 4])
        matrix.set(0, 0, 5)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 8)
        matrix.set(0, 3, 1)
        result = self._call_builtin("matrix.min_row", [matrix, 0])
        assert result == 1

    def test_matrix_max_row(self) -> None:
        """Test matrix.max_row finds maximum in row."""
        matrix = self._call_builtin("matrix.new", [1, 4])
        matrix.set(0, 0, 5)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 8)
        matrix.set(0, 3, 1)
        result = self._call_builtin("matrix.max_row", [matrix, 0])
        assert result == 8

    def test_matrix_fill_row(self) -> None:
        """Test matrix.fill_row fills row with value."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        self._call_builtin("matrix.fill_row", [matrix, 0, 7])
        assert matrix.get(0, 0) == 7
        assert matrix.get(0, 1) == 7
        assert matrix.get(0, 2) == 7

    # ========== COLUMN OPERATIONS ==========

    def test_matrix_add_col(self) -> None:
        """Test matrix.add_col adds new column."""
        matrix = self._call_builtin("matrix.new", [2, 1])
        self._call_builtin("matrix.add_col", [matrix, [1, 2]])
        assert matrix.columns() == 2
        assert matrix.get(0, 1) == 1

    def test_matrix_remove_col(self) -> None:
        """Test matrix.remove_col removes column."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        self._call_builtin("matrix.remove_col", [matrix, 1])
        assert matrix.columns() == 2

    def test_matrix_copy_col(self) -> None:
        """Test matrix.copy_col returns column data."""
        matrix = self._call_builtin("matrix.new", [3, 2])
        matrix.set(0, 0, 1)
        matrix.set(1, 0, 2)
        matrix.set(2, 0, 3)
        col = self._call_builtin("matrix.copy_col", [matrix, 0])
        assert col == [1, 2, 3]

    def test_matrix_sum_col(self) -> None:
        """Test matrix.sum_col sums column values."""
        matrix = self._call_builtin("matrix.new", [3, 1])
        matrix.set(0, 0, 1)
        matrix.set(1, 0, 2)
        matrix.set(2, 0, 3)
        result = self._call_builtin("matrix.sum_col", [matrix, 0])
        assert result == 6

    def test_matrix_avg_col(self) -> None:
        """Test matrix.avg_col averages column values."""
        matrix = self._call_builtin("matrix.new", [4, 1])
        matrix.set(0, 0, 2)
        matrix.set(1, 0, 4)
        matrix.set(2, 0, 6)
        matrix.set(3, 0, 8)
        result = self._call_builtin("matrix.avg_col", [matrix, 0])
        assert result == 5.0

    def test_matrix_fill_col(self) -> None:
        """Test matrix.fill_col fills column with value."""
        matrix = self._call_builtin("matrix.new", [3, 2])
        self._call_builtin("matrix.fill_col", [matrix, 0, 7])
        assert matrix.get(0, 0) == 7
        assert matrix.get(1, 0) == 7
        assert matrix.get(2, 0) == 7

    # ========== AGGREGATION OPERATIONS ==========

    def test_matrix_sum_all(self) -> None:
        """Test matrix.sum_all sums all elements."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(1, 0, 3)
        matrix.set(1, 1, 4)
        result = self._call_builtin("matrix.sum_all", [matrix])
        assert result == 10

    def test_matrix_avg_all(self) -> None:
        """Test matrix.avg_all averages all elements."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(1, 0, 3)
        matrix.set(1, 1, 4)
        result = self._call_builtin("matrix.avg_all", [matrix])
        assert result == 2.5

    def test_matrix_min_all(self) -> None:
        """Test matrix.min_all finds minimum of all elements."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        matrix.set(0, 0, 5)
        matrix.set(0, 1, 2)
        matrix.set(1, 0, 8)
        matrix.set(1, 1, 1)
        result = self._call_builtin("matrix.min_all", [matrix])
        assert result == 1

    def test_matrix_max_all(self) -> None:
        """Test matrix.max_all finds maximum of all elements."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        matrix.set(0, 0, 5)
        matrix.set(0, 1, 2)
        matrix.set(1, 0, 8)
        matrix.set(1, 1, 1)
        result = self._call_builtin("matrix.max_all", [matrix])
        assert result == 8

    # ========== FILLING OPERATIONS ==========

    def test_matrix_fill(self) -> None:
        """Test matrix.fill fills entire matrix."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        self._call_builtin("matrix.fill", [matrix, 5])
        for i in range(2):
            for j in range(3):
                assert matrix.get(i, j) == 5

    def test_matrix_fill_diagonal(self) -> None:
        """Test matrix.fill_diagonal fills diagonal."""
        matrix = self._call_builtin("matrix.new", [3, 3])
        self._call_builtin("matrix.fill_diagonal", [matrix, 7])
        assert matrix.get(0, 0) == 7
        assert matrix.get(1, 1) == 7
        assert matrix.get(2, 2) == 7
        assert matrix.get(0, 1) != 7

    # ========== TRANSFORMATION OPERATIONS ==========

    def test_matrix_transpose(self) -> None:
        """Test matrix.transpose returns transposed matrix."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 3)
        matrix.set(1, 0, 4)
        matrix.set(1, 1, 5)
        matrix.set(1, 2, 6)
        transposed = self._call_builtin("matrix.transpose", [matrix])
        assert transposed.rows() == 3
        assert transposed.columns() == 2
        assert transposed.get(0, 0) == 1
        assert transposed.get(0, 1) == 4

    def test_matrix_reverse_rows(self) -> None:
        """Test matrix.reverse_rows reverses row order."""
        matrix = self._call_builtin("matrix.new", [3, 1])
        matrix.set(0, 0, 1)
        matrix.set(1, 0, 2)
        matrix.set(2, 0, 3)
        self._call_builtin("matrix.reverse_rows", [matrix])
        assert matrix.get(0, 0) == 3
        assert matrix.get(1, 0) == 2
        assert matrix.get(2, 0) == 1

    def test_matrix_reverse_cols(self) -> None:
        """Test matrix.reverse_cols reverses column order."""
        matrix = self._call_builtin("matrix.new", [1, 3])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 3)
        self._call_builtin("matrix.reverse_cols", [matrix])
        assert matrix.get(0, 0) == 3
        assert matrix.get(0, 1) == 2
        assert matrix.get(0, 2) == 1

    def test_matrix_reshape(self) -> None:
        """Test matrix.reshape reshapes matrix."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)
        matrix.set(0, 2, 3)
        matrix.set(1, 0, 4)
        matrix.set(1, 1, 5)
        matrix.set(1, 2, 6)
        reshaped = self._call_builtin("matrix.reshape", [matrix, 3, 2])
        assert reshaped.rows() == 3
        assert reshaped.columns() == 2
        assert reshaped.get(0, 0) == 1
        assert reshaped.get(1, 0) == 3

    def test_matrix_concat_rows(self) -> None:
        """Test matrix.concat concatenates by rows."""
        m1 = self._call_builtin("matrix.new", [2, 2])
        m1.set(0, 0, 1)
        m1.set(0, 1, 2)
        m1.set(1, 0, 3)
        m1.set(1, 1, 4)

        m2 = self._call_builtin("matrix.new", [1, 2])
        m2.set(0, 0, 5)
        m2.set(0, 1, 6)

        result = self._call_builtin("matrix.concat", [m1, m2, 0])
        assert result.rows() == 3
        assert result.columns() == 2
        assert result.get(2, 0) == 5

    def test_matrix_concat_cols(self) -> None:
        """Test matrix.concat concatenates by columns."""
        m1 = self._call_builtin("matrix.new", [2, 2])
        m1.set(0, 0, 1)
        m1.set(0, 1, 2)
        m1.set(1, 0, 3)
        m1.set(1, 1, 4)

        m2 = self._call_builtin("matrix.new", [2, 1])
        m2.set(0, 0, 5)
        m2.set(1, 0, 6)

        result = self._call_builtin("matrix.concat", [m1, m2, 1])
        assert result.rows() == 2
        assert result.columns() == 3
        assert result.get(0, 2) == 5

    def test_matrix_copy(self) -> None:
        """Test matrix.copy creates deep copy."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        matrix.set(0, 0, 1)
        matrix.set(0, 1, 2)

        copy = self._call_builtin("matrix.copy", [matrix])
        assert copy.rows() == 2
        assert copy.columns() == 2
        assert copy.get(0, 0) == 1

        matrix.set(0, 0, 99)
        assert copy.get(0, 0) == 1

    # ========== ERROR HANDLING ==========

    def test_matrix_invalid_dimensions(self) -> None:
        """Test matrix.new rejects negative dimensions."""
        with pytest.raises(ValueError):
            self._call_builtin("matrix.new", [-1, 3])

    def test_matrix_get_out_of_bounds(self) -> None:
        """Test matrix.get raises error for out of bounds."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        with pytest.raises(ValueError):
            self._call_builtin("matrix.get", [matrix, 5, 5])

    def test_matrix_set_out_of_bounds(self) -> None:
        """Test matrix.set raises error for out of bounds."""
        matrix = self._call_builtin("matrix.new", [2, 2])
        with pytest.raises(ValueError):
            self._call_builtin("matrix.set", [matrix, 5, 5, 42])

    def test_matrix_reshape_invalid_dimensions(self) -> None:
        """Test matrix.reshape rejects incompatible dimensions."""
        matrix = self._call_builtin("matrix.new", [2, 3])
        with pytest.raises(ValueError):
            self._call_builtin("matrix.reshape", [matrix, 2, 2])

    def test_matrix_concat_column_mismatch(self) -> None:
        """Test matrix.concat rejects column mismatch for row concat."""
        m1 = self._call_builtin("matrix.new", [2, 2])
        m2 = self._call_builtin("matrix.new", [2, 3])
        with pytest.raises(ValueError):
            self._call_builtin("matrix.concat", [m1, m2, 0])

    # ========== COMPLEX SCENARIOS ==========

    def test_matrix_complex_workflow(self) -> None:
        """Test complex workflow with multiple operations."""
        # Create 2x3 matrix
        matrix = self._call_builtin("matrix.new", [2, 3, 0])

        # Fill with values
        self._call_builtin("matrix.fill", [matrix, 1])

        # Verify fill (2x3 = 6 elements * 1 = 6)
        assert self._call_builtin("matrix.sum_all", [matrix]) == 6

        # Add a row (now 3x3)
        self._call_builtin("matrix.add_row", [matrix, [2, 2, 2]])
        assert matrix.rows() == 3

        # Verify sum (6 ones + 3 twos = 12)
        assert self._call_builtin("matrix.sum_all", [matrix]) == 12

        # Get average (12 / 9 elements = 1.333...)
        avg = self._call_builtin("matrix.avg_all", [matrix])
        assert avg == pytest.approx(1.3333333333333333)

    def test_matrix_operations_chain(self) -> None:
        """Test chaining operations on matrix."""
        # Create 4x4 matrix with default value 1
        matrix = self._call_builtin("matrix.new", [4, 4, 1])

        # Transpose
        transposed = self._call_builtin("matrix.transpose", [matrix])
        assert transposed.rows() == 4
        assert transposed.columns() == 4

        # Fill diagonal on copy
        copy = self._call_builtin("matrix.copy", [transposed])
        self._call_builtin("matrix.fill_diagonal", [copy, 5])

        # Verify diagonal
        assert copy.get(0, 0) == 5
        assert copy.get(1, 1) == 5
        assert copy.get(2, 2) == 5
        assert copy.get(3, 3) == 5

        # Original unchanged
        assert transposed.get(0, 0) == 1


class TestMapEvaluatorIntegration:
    """Integration tests for Map builtin evaluator."""

    def setup_method(self) -> None:
        """Set up test evaluator."""
        self.evaluator = BuiltinEvaluator()

    def _call_builtin(self, name: str, args: list[Any]) -> Any:
        """Helper to call builtin method."""
        return self.evaluator._call_builtin(name, args)

    # ========== CORE OPERATIONS ==========

    def test_map_new(self) -> None:
        """Test map.new creates map."""
        map_obj = self._call_builtin("map.new", [])
        assert isinstance(map_obj, Map)
        assert map_obj.size() == 0

    def test_map_put_get(self) -> None:
        """Test map.put and map.get."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "key1", 42])
        result = self._call_builtin("map.get", [map_obj, "key1"])
        assert result == 42

    def test_map_put_multiple(self) -> None:
        """Test putting multiple items."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        self._call_builtin("map.put", [map_obj, "c", 3])
        assert self._call_builtin("map.size", [map_obj]) == 3
        assert self._call_builtin("map.get", [map_obj, "b"]) == 2

    def test_map_contains(self) -> None:
        """Test map.contains."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "key", 100])
        assert self._call_builtin("map.contains", [map_obj, "key"]) is True
        assert self._call_builtin("map.contains", [map_obj, "missing"]) is False

    def test_map_remove(self) -> None:
        """Test map.remove."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        self._call_builtin("map.remove", [map_obj, "a"])
        assert self._call_builtin("map.size", [map_obj]) == 1
        assert self._call_builtin("map.contains", [map_obj, "a"]) is False

    def test_map_clear(self) -> None:
        """Test map.clear."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        self._call_builtin("map.put", [map_obj, "c", 3])
        self._call_builtin("map.clear", [map_obj])
        assert self._call_builtin("map.size", [map_obj]) == 0

    def test_map_keys(self) -> None:
        """Test map.keys."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        self._call_builtin("map.put", [map_obj, "c", 3])
        keys = self._call_builtin("map.keys", [map_obj])
        assert len(keys) == 3
        assert "a" in keys
        assert "b" in keys
        assert "c" in keys

    def test_map_values(self) -> None:
        """Test map.values."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        self._call_builtin("map.put", [map_obj, "c", 3])
        values = self._call_builtin("map.values", [map_obj])
        assert len(values) == 3
        assert 1 in values
        assert 2 in values
        assert 3 in values

    def test_map_size(self) -> None:
        """Test map.size."""
        map_obj = self._call_builtin("map.new", [])
        assert self._call_builtin("map.size", [map_obj]) == 0
        self._call_builtin("map.put", [map_obj, "a", 1])
        assert self._call_builtin("map.size", [map_obj]) == 1
        self._call_builtin("map.put", [map_obj, "b", 2])
        assert self._call_builtin("map.size", [map_obj]) == 2

    def test_map_copy(self) -> None:
        """Test map.copy."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        map_copy = self._call_builtin("map.copy", [map_obj])
        assert self._call_builtin("map.size", [map_copy]) == 2
        assert self._call_builtin("map.get", [map_copy, "a"]) == 1

    def test_map_copy_independence(self) -> None:
        """Test copy is independent."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        map_copy = self._call_builtin("map.copy", [map_obj])
        self._call_builtin("map.put", [map_copy, "b", 2])
        assert self._call_builtin("map.size", [map_obj]) == 1
        assert self._call_builtin("map.size", [map_copy]) == 2

    def test_map_put_all(self) -> None:
        """Test map.put_all."""
        map1 = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map1, "a", 1])
        self._call_builtin("map.put", [map1, "b", 2])

        map2 = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map2, "c", 3])
        self._call_builtin("map.put_all", [map2, map1])
        assert self._call_builtin("map.size", [map2]) == 3
        assert self._call_builtin("map.get", [map2, "a"]) == 1
        assert self._call_builtin("map.get", [map2, "c"]) == 3

    # ========== EDGE CASES ==========

    def test_map_integer_keys(self) -> None:
        """Test map with integer keys."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, 1, "one"])
        self._call_builtin("map.put", [map_obj, 2, "two"])
        assert self._call_builtin("map.get", [map_obj, 1]) == "one"
        assert self._call_builtin("map.get", [map_obj, 2]) == "two"

    def test_map_mixed_types(self) -> None:
        """Test map with mixed value types."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "str", "hello"])
        self._call_builtin("map.put", [map_obj, "int", 42])
        self._call_builtin("map.put", [map_obj, "float", 3.14])
        assert self._call_builtin("map.get", [map_obj, "str"]) == "hello"
        assert self._call_builtin("map.get", [map_obj, "int"]) == 42
        assert self._call_builtin("map.get", [map_obj, "float"]) == 3.14

    def test_map_operations_chain(self) -> None:
        """Test chaining map operations."""
        # Create map with initial values
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "a", 1])
        self._call_builtin("map.put", [map_obj, "b", 2])
        self._call_builtin("map.put", [map_obj, "c", 3])
        assert self._call_builtin("map.size", [map_obj]) == 3

        # Remove one
        self._call_builtin("map.remove", [map_obj, "b"])
        assert self._call_builtin("map.size", [map_obj]) == 2

        # Copy and add more
        map_copy = self._call_builtin("map.copy", [map_obj])
        self._call_builtin("map.put", [map_copy, "d", 4])
        assert self._call_builtin("map.size", [map_copy]) == 3
        assert self._call_builtin("map.size", [map_obj]) == 2

        # Clear original
        self._call_builtin("map.clear", [map_obj])
        assert self._call_builtin("map.size", [map_obj]) == 0
        assert self._call_builtin("map.size", [map_copy]) == 3

    def test_map_overwrite_value(self) -> None:
        """Test overwriting existing value."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "key", 100])
        assert self._call_builtin("map.get", [map_obj, "key"]) == 100
        self._call_builtin("map.put", [map_obj, "key", 200])
        assert self._call_builtin("map.get", [map_obj, "key"]) == 200
        assert self._call_builtin("map.size", [map_obj]) == 1

    def test_map_none_value(self) -> None:
        """Test storing None as value."""
        map_obj = self._call_builtin("map.new", [])
        self._call_builtin("map.put", [map_obj, "null_key", None])
        assert self._call_builtin("map.get", [map_obj, "null_key"]) is None
        assert self._call_builtin("map.contains", [map_obj, "null_key"]) is True
