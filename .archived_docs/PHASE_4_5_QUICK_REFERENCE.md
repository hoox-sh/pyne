# Phase 4 & 5 Quick Reference

## Current Status

✅ **Phase 1:** Grammar & Parser (138 tests)  
✅ **Phase 2:** UDT Instantiation (34 tests)  
✅ **Phase 3:** Method Invocation (17 tests)  
⏳ **Phase 4:** Collections - READY (80 tests)  
⏳ **Phase 5:** Built-ins - READY (40 tests)

**Total:** 425/425 tests passing → 545/545 target

---

## Phase 4: Collections (11 days)

### What to Build

| Component | Lines | Methods | Tests |
|-----------|-------|---------|-------|
| Matrix | 800+ | 50+ | 50+ |
| Map | 300+ | 10+ | 15+ |
| Tests | 500+ | - | 80+ |

### Files to Create

1. `src/pynescript/ast/evaluator/builtins/matrix.py`
2. `src/pynescript/ast/evaluator/builtins/map.py`
3. `tests/test_collections_phase4.py`

### Key Methods

**Matrix (50+):**
- get, set, rows, columns, elements_count
- add_row, remove_row, copy_row, sum_row, avg_row, min_row, max_row, mode_row, fill_row
- add_col, remove_col, copy_col, sum_col, avg_col, min_col, max_col, mode_col, fill_col
- sum_all, avg_all, min_all, max_all, mode_all, fill, fill_diagonal
- transpose, reverse_rows, reverse_cols, reshape, concat, copy

**Map (10+):**
- get, put, put_all, remove, clear, contains
- keys, values, size, copy

### Schedule

- Day 1: Matrix foundation (get, set, properties)
- Days 2-3: Matrix row/column operations (20 methods)
- Day 4: Matrix aggregations & transformations (20 methods)
- Day 5: Matrix evaluator dispatch (50+ handlers)
- Days 6-7: Map implementation (Map class + 11 handlers)
- Days 8-10: Comprehensive testing (80 tests)
- Day 11: Integration & validation

---

## Phase 5: Built-in Functions (8 days)

### What to Build

| Family | Functions | Lines | Tests |
|--------|-----------|-------|-------|
| Ticker | 9 | 250+ | 8 |
| Logging | 3 | 100+ | 3 |
| Chart.Point | 5 | 150+ | 5 |
| Polyline | 4 | 150+ | 4 |
| Integration | - | - | 20+ |

### Files to Create/Modify

**New:**
1. `src/pynescript/ast/evaluator/builtins/ticker.py`
2. `src/pynescript/ast/evaluator/builtins/logging.py`
3. `tests/test_builtins_phase5.py`

**Modify:**
1. `src/pynescript/ast/evaluator/builtins/drawing.py` (add ChartPoint + Polyline)

### Key Functions

**Ticker (9):**
- ticker.new(symbol)
- ticker.modify(ticker, session, adjustment)
- ticker.standard(symbol, session)
- ticker.heikinashi(symbol)
- ticker.renko(symbol, atr_length)
- ticker.kagi(symbol, reversal)
- ticker.linebreak(symbol, lines)
- ticker.pointfigure(symbol, size_type, size, reversal)
- ticker.inherit(ticker)

**Logging (3):**
- log.error(message)
- log.warning(message)
- log.info(message)

**Chart.Point (5):**
- chart.point.new(time, price)
- chart.point.from_index(index, price)
- chart.point.from_time(time, price)
- chart.point.now(price)
- chart.point.copy(point)

**Polyline (4):**
- polyline.new(points, closed, xloc)
- polyline.set_closed(polyline, closed)
- polyline.delete(polyline)
- polyline.copy(polyline)

### Schedule

- Days 1-2: Ticker functions (9 functions + TickerObject)
- Days 2-3: Logging functions (3 functions + LogRegistry)
- Days 3-4: Chart.Point + Polyline functions (9 functions + classes)
- Days 5-8: Comprehensive testing (40+ tests)

---

## Implementation Checklist

### Phase 4 Week 1

- [ ] Create `matrix.py` with Matrix class
- [ ] Implement 50+ matrix methods
- [ ] Create evaluator dispatch (50+ handlers)
- [ ] Create `map.py` with Map class
- [ ] Implement 10+ map methods
- [ ] Create evaluator dispatch (11 handlers)

### Phase 4 Week 2

- [ ] Create comprehensive test suite (80 tests)
- [ ] Run: `hatch run test:test` → 505/505 ✅
- [ ] Update docs/pinescript_implementation_status.md
- [ ] Validate against real Pine scripts
- [ ] Zero regressions confirmed

### Phase 5 Week 1

- [ ] Create `ticker.py` (9 functions)
- [ ] Create `logging.py` (3 functions)
- [ ] Extend `drawing.py` (8 functions)
- [ ] Create test suite (40 tests)

### Phase 5 Week 2

- [ ] Run: `hatch run test:test` → 545/545 ✅
- [ ] Run: `hatch run lint:style` → All pass ✅
- [ ] Run: `hatch run lint:typing` → All pass ✅
- [ ] Update docs/pinescript_implementation_status.md
- [ ] Validate against real Pine scripts

---

## Test Commands

```bash
# Run all tests
hatch run test:test

# Run specific test file
hatch run test:test tests/test_collections_phase4.py

# Run with coverage
hatch run test:test --cov

# Check formatting
hatch run lint:style

# Check typing
hatch run lint:typing

# Format code
hatch run lint:format
```

---

## Expected Results

### After Phase 4
- Tests: 505/505 ✅
- New tests: +80
- Code coverage: 95%+
- Features: Matrix (70+), Map (10+)

### After Phase 5
- Tests: 545/545 ✅
- New tests: +40
- Code coverage: 95%+
- Features: Ticker (9), Logging (3), Chart.Point (5), Polyline (4)

### Overall
- Total tests: 545 (100% pass rate)
- Coverage: ~95% Pine Script v6
- Status: Production-ready 🚀

---

## Key Implementation Patterns

### Builtin Dispatch Pattern

```python
class MyEvaluator(BuiltinDispatchMixin):
    def _build_builtin_map(self) -> dict[str, Any]:
        return {
            "namespace.function": self._handle_namespace_function,
            # ... more functions
        }
    
    def _handle_namespace_function(self, args: list[Any]) -> Any:
        arg1 = self._visit_arg(args, 0, default_value)
        arg2 = self._visit_arg(args, 1, default_value)
        # ... implementation
        return result
```

### Generic Collection Pattern

```python
from typing import Generic, TypeVar

T = TypeVar('T')

class Collection(Generic[T]):
    def __init__(self, ...):
        self.data: list[T] | dict[Any, T] = ...
    
    def add(self, item: T) -> None:
        # ...
    
    def get(self, key: Any) -> T:
        # ...
```

---

## Common Issues & Solutions

### Issue: Import not found
**Solution:** Add to `src/pynescript/ast/evaluator/builtins/__init__.py`:
```python
from .matrix import Matrix, MatrixEvaluator
from .map import Map, MapEvaluator
```

### Issue: Tests not running
**Solution:** Ensure test files follow pattern:
```python
def test_function_name():
    """Test description"""
    # Test code
    assert True
```

### Issue: Type errors
**Solution:** Add type hints to all functions:
```python
def method(self, arg: int) -> str:
    return str(arg)
```

### Issue: Formatting errors
**Solution:** Run formatter:
```bash
hatch run lint:format
```

---

## Files Reference

### Phase 4 Files

| File | Type | Lines | Status |
|------|------|-------|--------|
| `matrix.py` | New | 800+ | Create |
| `map.py` | New | 300+ | Create |
| `collections.py` | New | 600+ | Create |
| `test_collections_phase4.py` | New | 500+ | Create |
| `__init__.py` | Modify | - | Register |

### Phase 5 Files

| File | Type | Lines | Status |
|------|------|-------|--------|
| `ticker.py` | New | 250+ | Create |
| `logging.py` | New | 100+ | Create |
| `drawing.py` | Modify | +400 | Extend |
| `test_builtins_phase5.py` | New | 400+ | Create |
| `__init__.py` | Modify | - | Register |

---

## Success Criteria

- [x] Phase 1-3 complete (425/425 tests)
- [ ] Phase 4 complete (80 new tests)
- [ ] Phase 5 complete (40 new tests)
- [ ] Total: 545/545 tests passing
- [ ] 95%+ code coverage
- [ ] Zero regressions
- [ ] All lint checks pass
- [ ] Documentation updated
- [ ] Real-world validation passed

---

## Timeline Summary

| Phase | Days | Start | End | Tests |
|-------|------|-------|-----|-------|
| 4 | 11 | Oct 24 | Nov 12 | +80 |
| 5 | 8 | Nov 12 | Nov 22 | +40 |
| **Total** | **19** | **Oct 24** | **Nov 22** | **545** |

---

## Ready to Launch! 🚀

All specifications are complete. Start with Phase 4, Day 1:

**Create:** `src/pynescript/ast/evaluator/builtins/matrix.py`

Let's build! 🚀
