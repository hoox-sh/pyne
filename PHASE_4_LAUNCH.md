# Phase 4: Collections (Matrix & Map) - Launch Guide

**Date Started:** October 24, 2025  
**Estimated Duration:** 75-80 hours (16-19 days)  
**Preceding Phase:** Phase 3 ✅ Complete (425/425 tests)  
**Target Completion:** ~November 12, 2025

---

## Executive Summary

Phase 4 implements Pine Script v6 collection types: **Matrix** and **Map**.

- **Matrix:** 70+ operations for 2D arrays (get, set, rows, columns, transpose, reshape, etc.)
- **Map:** Dictionary-like key-value collections (put, get, keys, values, contains, etc.)
- **Array Extensions:** New array operations compatible with these collections
- **Integration:** Full evaluator and test coverage

---

## Architecture Overview

### Collection Type System

```
Collection (Base)
├── Array<T> (existing - extend)
├── Matrix<T> (new)
└── Map<K, V> (new)
```

### Implementation Pattern

1. **Type Classes** → Core data structures with operations
2. **Evaluator Builtins** → Dispatch handlers (e.g., `matrix.new()`)
3. **Test Coverage** → Comprehensive unit + integration tests
4. **Real-World Validation** → Test against actual Pine scripts

---

## Phase 4 Implementation Plan

### 4.1 Matrix Type Implementation (Days 1-4)

**File:** `src/pynescript/ast/evaluator/builtins/matrix.py` (NEW - 800-900 lines)

#### 4.1.1 Core Matrix Class

```python
"""Matrix collection type and operations"""

from __future__ import annotations
from typing import Any, Generic, TypeVar, Optional
import math

T = TypeVar('T')

class Matrix(Generic[T]):
    """Represents a 2D matrix in Pine Script"""
    
    def __init__(
        self, 
        rows: int = 0, 
        cols: int = 0, 
        default_value: Any = None
    ):
        self.rows_count = rows
        self.cols_count = cols
        # Initialize 2D data structure
        self.data = [
            [default_value for _ in range(cols)] 
            for _ in range(rows)
        ]
    
    def get(self, row: int, col: int) -> Any:
        """Get element at row, col"""
        if not (0 <= row < self.rows_count and 0 <= col < self.cols_count):
            raise IndexError(f"Index out of bounds: [{row}][{col}]")
        return self.data[row][col]
    
    def set(self, row: int, col: int, value: Any) -> None:
        """Set element at row, col"""
        if not (0 <= row < self.rows_count and 0 <= col < self.cols_count):
            raise IndexError(f"Index out of bounds: [{row}][{col}]")
        self.data[row][col] = value
    
    def rows(self) -> int:
        """Get number of rows"""
        return self.rows_count
    
    def columns(self) -> int:
        """Get number of columns"""
        return self.cols_count
    
    def elements_count(self) -> int:
        """Get total element count"""
        return self.rows_count * self.cols_count
    
    # Row operations
    def add_row(self, row_data: list[Any]) -> None:
        """Add row to end of matrix"""
        if len(row_data) != self.cols_count:
            raise ValueError(f"Row size {len(row_data)} != matrix columns {self.cols_count}")
        self.data.append(row_data.copy())
        self.rows_count += 1
    
    def add_col(self, col_data: list[Any]) -> None:
        """Add column to end of matrix"""
        if len(col_data) != self.rows_count:
            raise ValueError(f"Column size {len(col_data)} != matrix rows {self.rows_count}")
        for i in range(self.rows_count):
            self.data[i].append(col_data[i])
        self.cols_count += 1
    
    def remove_row(self, index: int) -> None:
        """Remove row at index"""
        if not (0 <= index < self.rows_count):
            raise IndexError(f"Row index {index} out of range")
        self.data.pop(index)
        self.rows_count -= 1
    
    def remove_col(self, index: int) -> None:
        """Remove column at index"""
        if not (0 <= index < self.cols_count):
            raise IndexError(f"Column index {index} out of range")
        for row in self.data:
            row.pop(index)
        self.cols_count -= 1
    
    def transpose(self) -> Matrix[T]:
        """Return transposed matrix"""
        result = Matrix(self.cols_count, self.rows_count)
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                result.set(j, i, self.get(i, j))
        return result
    
    def reverse_rows(self) -> None:
        """Reverse row order"""
        self.data.reverse()
    
    def reverse_cols(self) -> None:
        """Reverse column order in each row"""
        for row in self.data:
            row.reverse()
    
    def reshape(self, new_rows: int, new_cols: int) -> Matrix[T]:
        """Reshape matrix (flattens and reforms)"""
        total = self.elements_count()
        if new_rows * new_cols != total:
            raise ValueError(f"Cannot reshape {total} elements to {new_rows}x{new_cols}")
        
        flat = [elem for row in self.data for elem in row]
        result = Matrix(new_rows, new_cols)
        for i in range(new_rows):
            for j in range(new_cols):
                result.set(i, j, flat[i * new_cols + j])
        return result
    
    def concat(self, other: Matrix[T], axis: int = 0) -> Matrix[T]:
        """Concatenate with another matrix along axis (0=rows, 1=cols)"""
        if axis == 0:  # Stack rows
            if self.cols_count != other.cols_count:
                raise ValueError("Column count must match for row concatenation")
            result = Matrix(self.rows_count + other.rows_count, self.cols_count)
            for i in range(self.rows_count):
                for j in range(self.cols_count):
                    result.set(i, j, self.get(i, j))
            for i in range(other.rows_count):
                for j in range(self.cols_count):
                    result.set(self.rows_count + i, j, other.get(i, j))
            return result
        else:  # Stack columns
            if self.rows_count != other.rows_count:
                raise ValueError("Row count must match for column concatenation")
            result = Matrix(self.rows_count, self.cols_count + other.cols_count)
            for i in range(self.rows_count):
                for j in range(self.cols_count):
                    result.set(i, j, self.get(i, j))
                for j in range(other.cols_count):
                    result.set(i, self.cols_count + j, other.get(i, j))
            return result
    
    def copy(self) -> Matrix[T]:
        """Deep copy of matrix"""
        result = Matrix(self.rows_count, self.cols_count)
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                result.set(i, j, self.get(i, j))
        return result
    
    def copy_row(self, index: int) -> list[Any]:
        """Get copy of row as array"""
        if not (0 <= index < self.rows_count):
            raise IndexError(f"Row index {index} out of range")
        return self.data[index].copy()
    
    def copy_col(self, index: int) -> list[Any]:
        """Get copy of column as array"""
        if not (0 <= index < self.cols_count):
            raise IndexError(f"Column index {index} out of range")
        return [self.data[i][index] for i in range(self.rows_count)]
    
    def sum_row(self, index: int) -> float:
        """Sum all elements in row"""
        row_data = self.copy_row(index)
        return sum(x for x in row_data if isinstance(x, (int, float)))
    
    def sum_col(self, index: int) -> float:
        """Sum all elements in column"""
        col_data = self.copy_col(index)
        return sum(x for x in col_data if isinstance(x, (int, float)))
    
    def sum_all(self) -> float:
        """Sum all elements"""
        total = 0
        for row in self.data:
            for elem in row:
                if isinstance(elem, (int, float)):
                    total += elem
        return total
    
    def avg_row(self, index: int) -> float:
        """Average of row elements"""
        row_data = self.copy_row(index)
        numeric = [x for x in row_data if isinstance(x, (int, float))]
        return sum(numeric) / len(numeric) if numeric else 0
    
    def avg_col(self, index: int) -> float:
        """Average of column elements"""
        col_data = self.copy_col(index)
        numeric = [x for x in col_data if isinstance(x, (int, float))]
        return sum(numeric) / len(numeric) if numeric else 0
    
    def avg_all(self) -> float:
        """Average of all elements"""
        total = 0
        count = 0
        for row in self.data:
            for elem in row:
                if isinstance(elem, (int, float)):
                    total += elem
                    count += 1
        return total / count if count > 0 else 0
    
    def min_row(self, index: int) -> Any:
        """Minimum in row"""
        row_data = self.copy_row(index)
        numeric = [x for x in row_data if isinstance(x, (int, float))]
        return min(numeric) if numeric else None
    
    def min_col(self, index: int) -> Any:
        """Minimum in column"""
        col_data = self.copy_col(index)
        numeric = [x for x in col_data if isinstance(x, (int, float))]
        return min(numeric) if numeric else None
    
    def min_all(self) -> Any:
        """Minimum of all elements"""
        values = []
        for row in self.data:
            for elem in row:
                if isinstance(elem, (int, float)):
                    values.append(elem)
        return min(values) if values else None
    
    def max_row(self, index: int) -> Any:
        """Maximum in row"""
        row_data = self.copy_row(index)
        numeric = [x for x in row_data if isinstance(x, (int, float))]
        return max(numeric) if numeric else None
    
    def max_col(self, index: int) -> Any:
        """Maximum in column"""
        col_data = self.copy_col(index)
        numeric = [x for x in col_data if isinstance(x, (int, float))]
        return max(numeric) if numeric else None
    
    def max_all(self) -> Any:
        """Maximum of all elements"""
        values = []
        for row in self.data:
            for elem in row:
                if isinstance(elem, (int, float)):
                    values.append(elem)
        return max(values) if values else None
    
    def mode_row(self, index: int) -> Any:
        """Most common element in row"""
        row_data = self.copy_row(index)
        if not row_data:
            return None
        from collections import Counter
        counts = Counter(row_data)
        return counts.most_common(1)[0][0]
    
    def mode_col(self, index: int) -> Any:
        """Most common element in column"""
        col_data = self.copy_col(index)
        if not col_data:
            return None
        from collections import Counter
        counts = Counter(col_data)
        return counts.most_common(1)[0][0]
    
    def mode_all(self) -> Any:
        """Most common element in matrix"""
        all_elems = [elem for row in self.data for elem in row]
        if not all_elems:
            return None
        from collections import Counter
        counts = Counter(all_elems)
        return counts.most_common(1)[0][0]
    
    def fill(self, value: Any) -> None:
        """Fill entire matrix with value"""
        for i in range(self.rows_count):
            for j in range(self.cols_count):
                self.data[i][j] = value
    
    def fill_row(self, index: int, value: Any) -> None:
        """Fill row with value"""
        if not (0 <= index < self.rows_count):
            raise IndexError(f"Row index {index} out of range")
        for j in range(self.cols_count):
            self.data[index][j] = value
    
    def fill_col(self, index: int, value: Any) -> None:
        """Fill column with value"""
        if not (0 <= index < self.cols_count):
            raise IndexError(f"Column index {index} out of range")
        for i in range(self.rows_count):
            self.data[i][index] = value
    
    def fill_diagonal(self, value: Any) -> None:
        """Fill diagonal with value"""
        for i in range(min(self.rows_count, self.cols_count)):
            self.data[i][i] = value
    
    def __repr__(self) -> str:
        return f"matrix({self.rows_count}x{self.cols_count})"
```

#### 4.1.2 Matrix Builtin Dispatch

**File:** `src/pynescript/ast/evaluator/builtins/collections.py` (NEW - 600+ lines)

```python
"""Builtin handlers for Matrix and Map collections"""

from __future__ import annotations
from typing import Any
from .base import BuiltinDispatchMixin
from .matrix import Matrix
from .map import Map

class MatrixEvaluator(BuiltinDispatchMixin):
    """Handle matrix.* builtin functions"""
    
    def _build_builtin_map(self) -> dict[str, Any]:
        """Register matrix builtins"""
        return {
            # Creation
            "matrix.new": self._handle_matrix_new,
            
            # Access
            "matrix.get": self._handle_matrix_get,
            "matrix.set": self._handle_matrix_set,
            
            # Properties
            "matrix.rows": self._handle_matrix_rows,
            "matrix.columns": self._handle_matrix_columns,
            "matrix.elements_count": self._handle_matrix_elements_count,
            
            # Row operations
            "matrix.add_row": self._handle_matrix_add_row,
            "matrix.remove_row": self._handle_matrix_remove_row,
            "matrix.copy_row": self._handle_matrix_copy_row,
            "matrix.sum_row": self._handle_matrix_sum_row,
            "matrix.avg_row": self._handle_matrix_avg_row,
            "matrix.min_row": self._handle_matrix_min_row,
            "matrix.max_row": self._handle_matrix_max_row,
            "matrix.mode_row": self._handle_matrix_mode_row,
            "matrix.fill_row": self._handle_matrix_fill_row,
            
            # Column operations
            "matrix.add_col": self._handle_matrix_add_col,
            "matrix.remove_col": self._handle_matrix_remove_col,
            "matrix.copy_col": self._handle_matrix_copy_col,
            "matrix.sum_col": self._handle_matrix_sum_col,
            "matrix.avg_col": self._handle_matrix_avg_col,
            "matrix.min_col": self._handle_matrix_min_col,
            "matrix.max_col": self._handle_matrix_max_col,
            "matrix.mode_col": self._handle_matrix_mode_col,
            "matrix.fill_col": self._handle_matrix_fill_col,
            
            # Matrix-wide operations
            "matrix.sum_all": self._handle_matrix_sum_all,
            "matrix.avg_all": self._handle_matrix_avg_all,
            "matrix.min_all": self._handle_matrix_min_all,
            "matrix.max_all": self._handle_matrix_max_all,
            "matrix.mode_all": self._handle_matrix_mode_all,
            "matrix.fill": self._handle_matrix_fill,
            "matrix.fill_diagonal": self._handle_matrix_fill_diagonal,
            
            # Transformations
            "matrix.transpose": self._handle_matrix_transpose,
            "matrix.reverse_rows": self._handle_matrix_reverse_rows,
            "matrix.reverse_cols": self._handle_matrix_reverse_cols,
            "matrix.reshape": self._handle_matrix_reshape,
            "matrix.concat": self._handle_matrix_concat,
            "matrix.copy": self._handle_matrix_copy,
        }
    
    def _handle_matrix_new(self, args: list[Any]) -> Matrix:
        """matrix.new(rows, cols, default)"""
        rows = self._visit_arg(args, 0, 0)
        cols = self._visit_arg(args, 1, 0)
        default = self._visit_arg(args, 2, None) if len(args) > 2 else None
        return Matrix(rows, cols, default)
    
    def _handle_matrix_get(self, args: list[Any]) -> Any:
        """matrix.get(matrix, row, col)"""
        matrix = args[0]
        row = self._visit_arg(args, 1, 0)
        col = self._visit_arg(args, 2, 0)
        return matrix.get(row, col)
    
    def _handle_matrix_set(self, args: list[Any]) -> None:
        """matrix.set(matrix, row, col, value)"""
        matrix = args[0]
        row = self._visit_arg(args, 1, 0)
        col = self._visit_arg(args, 2, 0)
        value = self._visit_arg(args, 3, None)
        matrix.set(row, col, value)
    
    # ... implement all 50+ handlers
    
    def _visit_arg(self, args: list, index: int, default: Any) -> Any:
        """Get argument or default"""
        if index < len(args):
            arg = args[index]
            return self.visit(arg) if hasattr(self, 'visit') else arg
        return default
```

---

### 4.2 Map Type Implementation (Days 5-7)

**File:** `src/pynescript/ast/evaluator/builtins/map.py` (NEW - 300+ lines)

```python
"""Map collection type (key-value pairs)"""

from __future__ import annotations
from typing import Any, Generic, TypeVar, Optional

K = TypeVar('K')
V = TypeVar('V')

class Map(Generic[K, V]):
    """Key-value collection in Pine Script"""
    
    def __init__(self):
        self.data: dict[Any, Any] = {}
    
    def get(self, key: K) -> Optional[V]:
        """Get value by key"""
        return self.data.get(key)
    
    def put(self, key: K, value: V) -> None:
        """Insert or update key-value pair"""
        self.data[key] = value
    
    def put_all(self, other: Map[K, V]) -> None:
        """Insert all pairs from another map"""
        self.data.update(other.data)
    
    def remove(self, key: K) -> None:
        """Remove key"""
        if key in self.data:
            del self.data[key]
    
    def clear(self) -> None:
        """Remove all entries"""
        self.data.clear()
    
    def contains(self, key: K) -> bool:
        """Check if key exists"""
        return key in self.data
    
    def keys(self) -> list[K]:
        """Get all keys"""
        return list(self.data.keys())
    
    def values(self) -> list[V]:
        """Get all values"""
        return list(self.data.values())
    
    def size(self) -> int:
        """Get number of entries"""
        return len(self.data)
    
    def copy(self) -> Map[K, V]:
        """Deep copy of map"""
        new_map = Map()
        new_map.data = self.data.copy()
        return new_map
    
    def __repr__(self) -> str:
        return f"map({self.size()})"

class MapEvaluator(BuiltinDispatchMixin):
    """Handle map.* builtin functions"""
    
    def _build_builtin_map(self) -> dict[str, Any]:
        """Register map builtins"""
        return {
            "map.new": self._handle_map_new,
            "map.get": self._handle_map_get,
            "map.put": self._handle_map_put,
            "map.put_all": self._handle_map_put_all,
            "map.remove": self._handle_map_remove,
            "map.clear": self._handle_map_clear,
            "map.contains": self._handle_map_contains,
            "map.keys": self._handle_map_keys,
            "map.values": self._handle_map_values,
            "map.size": self._handle_map_size,
            "map.copy": self._handle_map_copy,
        }
    
    def _handle_map_new(self, args: list[Any]) -> Map:
        """map.new()"""
        return Map()
    
    def _handle_map_get(self, args: list[Any]) -> Any:
        """map.get(map, key)"""
        map_obj = args[0]
        key = self._visit_arg(args, 1)
        return map_obj.get(key)
    
    # ... implement all handlers
```

---

### 4.3 Testing Collections (Days 8-10)

**File:** `tests/test_collections_phase4.py` (NEW - 500+ lines)

```python
"""Test Matrix and Map collections"""

import pytest
from pynescript.ast.helper import parse
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.matrix import Matrix
from pynescript.ast.evaluator.builtins.map import Map

class TestMatrixBasics:
    """Test basic matrix operations"""
    
    def test_matrix_new(self):
        """Create matrix"""
        m = Matrix(3, 4, 0.0)
        assert m.rows() == 3
        assert m.columns() == 4
        assert m.elements_count() == 12
    
    def test_matrix_get_set(self):
        """Get and set elements"""
        m = Matrix(2, 2, 0.0)
        m.set(0, 0, 10.5)
        assert m.get(0, 0) == 10.5
    
    def test_matrix_add_row(self):
        """Add row to matrix"""
        m = Matrix(2, 3, 0.0)
        m.add_row([1, 2, 3])
        assert m.rows() == 3
    
    def test_matrix_transpose(self):
        """Transpose matrix"""
        m = Matrix(2, 3, 0.0)
        m.set(0, 0, 1)
        m.set(0, 1, 2)
        m.set(1, 0, 3)
        m.set(1, 1, 4)
        
        t = m.transpose()
        assert t.rows() == 3
        assert t.columns() == 2
        assert t.get(0, 0) == 1
        assert t.get(1, 0) == 2

class TestMapBasics:
    """Test basic map operations"""
    
    def test_map_new(self):
        """Create map"""
        m = Map()
        assert m.size() == 0
    
    def test_map_put_get(self):
        """Put and get values"""
        m = Map()
        m.put("key1", 100)
        assert m.get("key1") == 100
    
    def test_map_contains(self):
        """Check key existence"""
        m = Map()
        m.put("x", 10)
        assert m.contains("x")
        assert not m.contains("y")
    
    def test_map_keys_values(self):
        """Get keys and values"""
        m = Map()
        m.put("a", 1)
        m.put("b", 2)
        assert m.keys() == ["a", "b"]
        assert m.values() == [1, 2]

# ... 50+ additional tests
```

---

### 4.4 Integration Checklist (Day 11)

- [ ] Create `src/pynescript/ast/evaluator/builtins/matrix.py` with Matrix class
- [ ] Implement all 50+ matrix operations
- [ ] Create `src/pynescript/ast/evaluator/builtins/map.py` with Map class
- [ ] Implement all 10+ map operations
- [ ] Add MatrixEvaluator and MapEvaluator builtin dispatch
- [ ] Integrate into BuiltinHandler
- [ ] Create comprehensive test suite (60+ tests)
- [ ] Validate against real Pine scripts
- [ ] All tests passing ✅
- [ ] No regressions on existing tests ✅

---

## Expected Outcomes

### Code Changes
- **New Files:** 3 (matrix.py, map.py, test_collections_phase4.py)
- **Modified Files:** 2 (builtins/__init__.py, evaluator.py)
- **Lines Added:** ~2,000
- **Test Cases Added:** 60+

### Test Coverage
- **Matrix Operations:** 50+
- **Map Operations:** 10+
- **Integration Tests:** 20+
- **Total New Tests:** 80+
- **Expected Pass Rate:** 100%

### Metrics
- **Phase 4 Tests:** 80 ✅
- **Total Tests (1-4):** 505 ✅
- **Code Coverage:** 95%+
- **Documentation:** Complete

---

## Success Criteria

- ✅ All 50+ matrix operations working correctly
- ✅ All 10+ map operations working correctly
- ✅ 95%+ test coverage
- ✅ Zero regressions on existing tests
- ✅ Round-trip fidelity maintained
- ✅ Performance acceptable (< 100ms for typical operations)
- ✅ Ready for Phase 5 built-in functions

---

## Next Phase: Phase 5

When Phase 4 completes, Phase 5 will implement:

1. **Ticker Functions** (8 functions) - Day 1-2
2. **Logging Functions** (3 functions) - Day 2-3
3. **Chart.Point Functions** (5 functions) - Day 3-4
4. **Polyline Functions** (3 functions) - Day 4-5

**Estimated Duration:** 30-40 hours (8-10 days)  
**Target Completion:** ~November 22, 2025

---

## Files to Create/Modify

### New Files (3)
1. `src/pynescript/ast/evaluator/builtins/matrix.py` - Matrix class (800+ lines)
2. `src/pynescript/ast/evaluator/builtins/map.py` - Map class (300+ lines)
3. `tests/test_collections_phase4.py` - Comprehensive tests (500+ lines)

### Modified Files (2)
1. `src/pynescript/ast/evaluator/builtins/__init__.py` - Register collection evaluators
2. `src/pynescript/ast/evaluator.py` - Integrate collection handlers

### Updated Documentation
1. `docs/pinescript_implementation_status.md` - Update collection coverage
2. `PHASE_4_LAUNCH.md` - This file (launch guide)

---

## Starting Immediately

The implementation roadmap is complete and ready to begin. All architectural decisions are made, and the type system from Phases 1-3 provides the foundation.

**Next Step:** Begin with 4.1 (Matrix Implementation)

Let's build! 🚀
