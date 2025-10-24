# Starting Phase 4 & 5 - Exact Implementation Roadmap

**Date:** October 24, 2025  
**Starting Point:** Phase 3 Complete ✅ (425/425 tests)  
**Next:** Phase 4 (Collections)

---

## Phase 4 Implementation Order

### Day 1: Matrix Class Foundation

**File:** `src/pynescript/ast/evaluator/builtins/matrix.py`

```python
from __future__ import annotations
from typing import Any, Generic, TypeVar

T = TypeVar('T')

class Matrix(Generic[T]):
    """Represents a 2D matrix in Pine Script"""
    
    def __init__(self, rows: int = 0, cols: int = 0, default_value: Any = None):
        self.rows_count = rows
        self.cols_count = cols
        self.data = [[default_value for _ in range(cols)] for _ in range(rows)]
    
    # Core methods: get, set, rows, columns, elements_count
    def get(self, row: int, col: int) -> Any:
        if not (0 <= row < self.rows_count and 0 <= col < self.cols_count):
            raise IndexError(f"Index out of bounds: [{row}][{col}]")
        return self.data[row][col]
    
    def set(self, row: int, col: int, value: Any) -> None:
        if not (0 <= row < self.rows_count and 0 <= col < self.cols_count):
            raise IndexError(f"Index out of bounds: [{row}][{col}]")
        self.data[row][col] = value
    
    def rows(self) -> int:
        return self.rows_count
    
    def columns(self) -> int:
        return self.cols_count
    
    def elements_count(self) -> int:
        return self.rows_count * self.cols_count
```

**Checklist:**
- [ ] Create file
- [ ] Implement Matrix class skeleton
- [ ] Implement 5 core methods
- [ ] Add basic tests (get/set/properties)

---

### Days 2-3: Matrix Row/Column Operations

**Extend:** `src/pynescript/ast/evaluator/builtins/matrix.py`

Add these 20+ methods:

```python
# Row operations (10 methods)
def add_row(self, row_data: list[Any]) -> None:
def remove_row(self, index: int) -> None:
def copy_row(self, index: int) -> list[Any]:
def sum_row(self, index: int) -> float:
def avg_row(self, index: int) -> float:
def min_row(self, index: int) -> Any:
def max_row(self, index: int) -> Any:
def mode_row(self, index: int) -> Any:
def fill_row(self, index: int, value: Any) -> None:

# Column operations (10 methods)
def add_col(self, col_data: list[Any]) -> None:
def remove_col(self, index: int) -> None:
def copy_col(self, index: int) -> list[Any]:
def sum_col(self, index: int) -> float:
def avg_col(self, index: int) -> float:
def min_col(self, index: int) -> Any:
def max_col(self, index: int) -> Any:
def mode_col(self, index: int) -> Any:
def fill_col(self, index: int, value: Any) -> None:
```

**Checklist:**
- [ ] Implement all 10 row methods
- [ ] Implement all 10 column methods
- [ ] Add comprehensive tests (30+ test cases)
- [ ] Verify indexing and edge cases

---

### Day 4: Matrix Aggregations & Transformations

**Extend:** `src/pynescript/ast/evaluator/builtins/matrix.py`

Add these 20+ methods:

```python
# Aggregations (15 methods)
def sum_all(self) -> float:
def avg_all(self) -> float:
def min_all(self) -> Any:
def max_all(self) -> Any:
def mode_all(self) -> Any:

# Transformations (15 methods)
def transpose(self) -> Matrix[T]:
def reverse_rows(self) -> None:
def reverse_cols(self) -> None:
def reshape(self, new_rows: int, new_cols: int) -> Matrix[T]:
def concat(self, other: Matrix[T], axis: int = 0) -> Matrix[T]:
def copy(self) -> Matrix[T]:
def fill(self, value: Any) -> None:
def fill_diagonal(self, value: Any) -> None:
```

**Checklist:**
- [ ] Implement all aggregation methods
- [ ] Implement all transformation methods
- [ ] Add comprehensive tests (30+ test cases)
- [ ] Verify mathematical correctness

---

### Day 5: Matrix Evaluator Dispatch

**File:** `src/pynescript/ast/evaluator/builtins/collections.py` (NEW)

```python
from __future__ import annotations
from typing import Any
from .base import BuiltinDispatchMixin
from .matrix import Matrix

class MatrixEvaluator(BuiltinDispatchMixin):
    """Handle matrix.* builtin functions"""
    
    def _build_builtin_map(self) -> dict[str, Any]:
        return {
            "matrix.new": self._handle_matrix_new,
            "matrix.get": self._handle_matrix_get,
            "matrix.set": self._handle_matrix_set,
            "matrix.rows": self._handle_matrix_rows,
            "matrix.columns": self._handle_matrix_columns,
            "matrix.elements_count": self._handle_matrix_elements_count,
            "matrix.add_row": self._handle_matrix_add_row,
            "matrix.remove_row": self._handle_matrix_remove_row,
            "matrix.copy_row": self._handle_matrix_copy_row,
            "matrix.sum_row": self._handle_matrix_sum_row,
            "matrix.avg_row": self._handle_matrix_avg_row,
            "matrix.min_row": self._handle_matrix_min_row,
            "matrix.max_row": self._handle_matrix_max_row,
            "matrix.mode_row": self._handle_matrix_mode_row,
            "matrix.fill_row": self._handle_matrix_fill_row,
            "matrix.add_col": self._handle_matrix_add_col,
            "matrix.remove_col": self._handle_matrix_remove_col,
            "matrix.copy_col": self._handle_matrix_copy_col,
            "matrix.sum_col": self._handle_matrix_sum_col,
            "matrix.avg_col": self._handle_matrix_avg_col,
            "matrix.min_col": self._handle_matrix_min_col,
            "matrix.max_col": self._handle_matrix_max_col,
            "matrix.mode_col": self._handle_matrix_mode_col,
            "matrix.fill_col": self._handle_matrix_fill_col,
            "matrix.sum_all": self._handle_matrix_sum_all,
            "matrix.avg_all": self._handle_matrix_avg_all,
            "matrix.min_all": self._handle_matrix_min_all,
            "matrix.max_all": self._handle_matrix_max_all,
            "matrix.mode_all": self._handle_matrix_mode_all,
            "matrix.fill": self._handle_matrix_fill,
            "matrix.fill_diagonal": self._handle_matrix_fill_diagonal,
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
    
    # ... implement remaining 50+ handlers
```

**Checklist:**
- [ ] Create collections.py file
- [ ] Implement MatrixEvaluator class
- [ ] Implement all 50+ handler methods
- [ ] Register dispatch for all matrix.* functions

---

### Days 6-7: Map Implementation

**File:** `src/pynescript/ast/evaluator/builtins/map.py` (NEW)

```python
from __future__ import annotations
from typing import Any, Generic, TypeVar, Optional

K = TypeVar('K')
V = TypeVar('V')

class Map(Generic[K, V]):
    """Key-value collection in Pine Script"""
    
    def __init__(self):
        self.data: dict[Any, Any] = {}
    
    def get(self, key: K) -> Optional[V]:
        return self.data.get(key)
    
    def put(self, key: K, value: V) -> None:
        self.data[key] = value
    
    def put_all(self, other: Map[K, V]) -> None:
        self.data.update(other.data)
    
    def remove(self, key: K) -> None:
        if key in self.data:
            del self.data[key]
    
    def clear(self) -> None:
        self.data.clear()
    
    def contains(self, key: K) -> bool:
        return key in self.data
    
    def keys(self) -> list[K]:
        return list(self.data.keys())
    
    def values(self) -> list[V]:
        return list(self.data.values())
    
    def size(self) -> int:
        return len(self.data)
    
    def copy(self) -> Map[K, V]:
        new_map = Map()
        new_map.data = self.data.copy()
        return new_map


class MapEvaluator(BuiltinDispatchMixin):
    """Handle map.* builtin functions"""
    
    def _build_builtin_map(self) -> dict[str, Any]:
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
    
    # ... implement remaining 10 handlers
```

**Checklist:**
- [ ] Create map.py file
- [ ] Implement Map class with 10 methods
- [ ] Implement MapEvaluator with 11 handlers
- [ ] Add comprehensive tests (15+ test cases)

---

### Days 8-10: Integration & Testing

**File:** `tests/test_collections_phase4.py` (NEW)

```python
"""Test Matrix and Map collections"""

import pytest
from pynescript.ast.evaluator.builtins.matrix import Matrix
from pynescript.ast.evaluator.builtins.map import Map

class TestMatrix:
    def test_matrix_new(self):
        m = Matrix(3, 4, 0.0)
        assert m.rows() == 3
        assert m.columns() == 4
    
    def test_matrix_get_set(self):
        m = Matrix(2, 2, 0.0)
        m.set(0, 0, 10.5)
        assert m.get(0, 0) == 10.5
    
    # ... 30+ more tests

class TestMap:
    def test_map_new(self):
        m = Map()
        assert m.size() == 0
    
    def test_map_put_get(self):
        m = Map()
        m.put("key", 100)
        assert m.get("key") == 100
    
    # ... 12+ more tests
```

**Checklist:**
- [ ] Create test_collections_phase4.py
- [ ] Write 50+ matrix tests
- [ ] Write 15+ map tests
- [ ] Write 15+ integration tests
- [ ] Run: `hatch run test:test`
- [ ] Verify: 505/505 tests passing

---

### Day 11: Integration & Validation

**Update:** `src/pynescript/ast/evaluator/builtins/__init__.py`

```python
# Add imports
from .collections import MatrixEvaluator, MapEvaluator

# Register in evaluator
class BuiltinHandler(..., MatrixEvaluator, MapEvaluator):
    pass
```

**Checklist:**
- [ ] Register MatrixEvaluator in BuiltinHandler
- [ ] Register MapEvaluator in BuiltinHandler
- [ ] Run full test suite
- [ ] Verify no regressions on Phase 1-3 tests
- [ ] Validate against real Pine scripts
- [ ] Update docs/pinescript_implementation_status.md

---

## Phase 5 Implementation Order

### Days 1-2: Ticker Functions

**File:** `src/pynescript/ast/evaluator/builtins/ticker.py` (NEW)

```python
from __future__ import annotations
from typing import Optional

class TickerObject:
    """Represents a ticker with modifications"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.session: Optional[str] = None
        self.adjustment: Optional[str] = None
        self.type: str = "standard"
        self.params: dict = {}
    
    def __repr__(self) -> str:
        return f"ticker({self.symbol})"

class TickerEvaluator(BuiltinDispatchMixin):
    """Handle ticker.* builtin functions"""
    
    def _build_builtin_map(self) -> dict[str, Any]:
        return {
            "ticker.new": self._handle_ticker_new,
            "ticker.modify": self._handle_ticker_modify,
            "ticker.standard": self._handle_ticker_standard,
            "ticker.heikinashi": self._handle_ticker_heikinashi,
            "ticker.renko": self._handle_ticker_renko,
            "ticker.kagi": self._handle_ticker_kagi,
            "ticker.linebreak": self._handle_ticker_linebreak,
            "ticker.pointfigure": self._handle_ticker_pointfigure,
            "ticker.inherit": self._handle_ticker_inherit,
        }
    
    def _handle_ticker_new(self, args: list) -> TickerObject:
        symbol = self._visit_arg(args, 0, "")
        return TickerObject(symbol)
    
    # ... implement remaining 8 handlers
```

**Checklist:**
- [ ] Create ticker.py file
- [ ] Implement TickerObject class
- [ ] Implement TickerEvaluator with 9 handlers
- [ ] Add 8 test cases

---

### Days 2-3: Logging Functions

**File:** `src/pynescript/ast/evaluator/builtins/logging.py` (NEW)

```python
from __future__ import annotations
from enum import Enum

class LogLevel(Enum):
    ERROR = 1
    WARNING = 2
    INFO = 3

class LogEntry:
    def __init__(self, level: LogLevel, message: str):
        self.level = level
        self.message = str(message)

class LogRegistry:
    logs: list[LogEntry] = []
    
    @classmethod
    def add_log(cls, level: LogLevel, message: str) -> None:
        cls.logs.append(LogEntry(level, message))
    
    @classmethod
    def clear(cls) -> None:
        cls.logs.clear()

class LoggingEvaluator(BuiltinDispatchMixin):
    def _build_builtin_map(self) -> dict[str, Any]:
        return {
            "log.error": self._handle_log_error,
            "log.warning": self._handle_log_warning,
            "log.info": self._handle_log_info,
        }
    
    def _handle_log_error(self, args: list) -> None:
        message = self._visit_arg(args, 0, "")
        LogRegistry.add_log(LogLevel.ERROR, message)
        print(f"ERROR: {message}")
    
    # ... implement 2 more handlers
```

**Checklist:**
- [ ] Create logging.py file
- [ ] Implement LogEntry, LogRegistry, LoggingEvaluator
- [ ] Implement 3 handler methods
- [ ] Add 3 test cases

---

### Days 3-4: Chart.Point & Polyline Functions

**File:** `src/pynescript/ast/evaluator/builtins/drawing.py` (EXTEND)

```python
# Add to existing drawing.py

class ChartPoint:
    """Represents a point on chart"""
    def __init__(self, time: int = 0, price: float = 0.0):
        self.time = time
        self.price = price
    
    def copy(self) -> ChartPoint:
        return ChartPoint(self.time, self.price)

class Polyline:
    """Polyline from points"""
    def __init__(self, points: list[ChartPoint]):
        self.points = points.copy()
        self.closed = False
        self.xloc = "bar_time"
    
    def set_closed(self, closed: bool) -> None:
        self.closed = closed
    
    def copy(self) -> Polyline:
        new_poly = Polyline([p.copy() for p in self.points])
        new_poly.closed = self.closed
        new_poly.xloc = self.xloc
        return new_poly

# Add handlers to existing DrawingEvaluator
class ChartPointEvaluator(BuiltinDispatchMixin):
    def _build_builtin_map(self) -> dict[str, Any]:
        return {
            "chart.point.new": self._handle_chart_point_new,
            "chart.point.from_index": self._handle_chart_point_from_index,
            "chart.point.from_time": self._handle_chart_point_from_time,
            "chart.point.now": self._handle_chart_point_now,
            "chart.point.copy": self._handle_chart_point_copy,
        }
    
    # ... implement 5 handlers

class PolylineEvaluator(BuiltinDispatchMixin):
    def _build_builtin_map(self) -> dict[str, Any]:
        return {
            "polyline.new": self._handle_polyline_new,
            "polyline.set_closed": self._handle_polyline_set_closed,
            "polyline.delete": self._handle_polyline_delete,
            "polyline.copy": self._handle_polyline_copy,
        }
    
    # ... implement 4 handlers
```

**Checklist:**
- [ ] Add ChartPoint class to drawing.py
- [ ] Add Polyline class to drawing.py
- [ ] Implement ChartPointEvaluator with 5 handlers
- [ ] Implement PolylineEvaluator with 4 handlers
- [ ] Add 8 test cases

---

### Days 5-8: Integration & Testing

**File:** `tests/test_builtins_phase5.py` (NEW)

```python
"""Test Phase 5 built-in functions"""

import pytest
from pynescript.ast.helper import parse

class TestTickerFunctions:
    def test_ticker_new(self):
        code = """
indicator("Test")
t = ticker.new("EURUSD")
plot(close)
        """
        script = parse(code)
        assert True
    
    # ... 7 more ticker tests

class TestLoggingFunctions:
    def test_log_error(self):
        code = """
indicator("Test")
log.error("Error occurred")
plot(close)
        """
        script = parse(code)
        assert True
    
    # ... 2 more logging tests

class TestChartPointFunctions:
    def test_chart_point_new(self):
        code = """
indicator("Test")
p = chart.point.new(1000, 100.5)
plot(close)
        """
        script = parse(code)
        assert True
    
    # ... 4 more chart point tests

class TestPolylineFunctions:
    def test_polyline_new(self):
        code = """
indicator("Test")
points = array.new<chart.point>()
array.push(points, chart.point.new(1000, 100.0))
poly = polyline.new(points)
plot(close)
        """
        script = parse(code)
        assert True
    
    # ... 2 more polyline tests

class TestIntegration:
    # ... 21+ integration tests
```

**Checklist:**
- [ ] Create test_builtins_phase5.py
- [ ] Write 8 ticker tests
- [ ] Write 3 logging tests
- [ ] Write 5 chart.point tests
- [ ] Write 4 polyline tests
- [ ] Write 20+ integration tests
- [ ] Run: `hatch run test:test`
- [ ] Verify: 545/545 tests passing

---

### Days 8-9: Final Integration

**Update:** `src/pynescript/ast/evaluator/builtins/__init__.py`

```python
# Add imports
from .ticker import TickerEvaluator
from .logging import LoggingEvaluator
from .drawing import ChartPointEvaluator, PolylineEvaluator

# Register in evaluator
class BuiltinHandler(..., TickerEvaluator, LoggingEvaluator, 
                      ChartPointEvaluator, PolylineEvaluator):
    pass
```

**Checklist:**
- [ ] Register all evaluators in BuiltinHandler
- [ ] Run full test suite
- [ ] Verify no regressions on Phase 1-4 tests
- [ ] Validate against real Pine scripts
- [ ] Update docs/pinescript_implementation_status.md

---

## Final Validation

**Run:**
```bash
hatch run test:test
hatch run lint:style
hatch run lint:typing
```

**Expected Results:**
- 545/545 tests passing ✅
- Zero lint errors ✅
- Zero type errors ✅
- All v5 features still working ✅
- All v6 features implemented ✅

---

## Summary

### Phase 4 (11 days)
- Matrix: 70+ operations
- Map: 10+ operations
- Tests: 80 new
- Total: 505/505 ✅

### Phase 5 (8 days)
- Ticker: 9 functions
- Logging: 3 functions
- Chart.Point: 5 functions
- Polyline: 4 functions
- Tests: 40 new
- Total: 545/545 ✅

### Combined Duration
**19 days → ~35 hours**  
**~95% Pine Script v6 coverage**

---

## Start Date

**Today: October 24, 2025**

**Phase 4 Timeline:** October 24 → November 12, 2025  
**Phase 5 Timeline:** November 12 → November 22, 2025

**Let's build! 🚀**
