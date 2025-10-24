"""Integration tests for Matrix evaluator in Phase 4."""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.ast.evaluator.builtins import BuiltinEvaluator
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
