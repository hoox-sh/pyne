# 🚀 Phase 2-5 Implementation Tracker

**Status:** Ready to Start Implementation  
**Date:** October 24, 2025  
**Target Completion:** Week of November 4, 2025

---

## Phase 2: Object Instantiation (Weeks 1-2)

### Task 2.1: Type System Foundation ⏳
- [ ] Add `UserDefinedType` class to `types.py`
- [ ] Add `Field` class to `types.py`
- [ ] Add `ObjectInstance` class to `types.py`
- [ ] Tests: 4/4 passing
- **Start:** Day 1 | **Duration:** 1 day

### Task 2.2: TypeRegistry Enhancement ⏳
- [ ] Add `register_udt()` method
- [ ] Add `get_udt()` method
- [ ] Add `list_udt_names()` method
- **Start:** Day 1 | **Duration:** 0.5 day

### Task 2.3: TypeDef Evaluation Update ⏳
- [ ] Update `visit_TypeDef()` in statements.py
- [ ] Extract fields from type body
- [ ] Register UDT in type_registry
- [ ] Tests: All phase 2 UDTs evaluate correctly
- **Start:** Day 2 | **Duration:** 1 day

### Task 2.4: .new() Constructor ⏳
- [ ] Implement `_handle_udt_new()` in expressions.py
- [ ] Support positional arguments
- [ ] Support keyword arguments
- [ ] Support .new() as method call on type
- **Start:** Day 3 | **Duration:** 1.5 days

### Task 2.5: Field Access ⏳
- [ ] Implement attribute access in `visit_Attribute()`
- [ ] Get field values from ObjectInstance
- [ ] Support nested field access
- **Start:** Day 4 | **Duration:** 1 day

### Task 2.6: Field Mutation ⏳
- [ ] Implement object field mutation in `visit_AugAssign()`
- [ ] Support `obj.field := value` syntax
- [ ] Track field changes correctly
- **Start:** Day 5 | **Duration:** 1 day

### Task 2.7: Testing Phase 2 ⏳
- [ ] Create `test_udt_instantiation.py`
- [ ] All 8 tests passing
- [ ] Round-trip parse/unparse verified
- **Start:** Day 5 | **Duration:** 1 day

### Task 2.8: Integration & Verification ⏳
- [ ] No breaking changes to v5 features
- [ ] All builtin scripts still parse/unparse correctly
- [ ] Performance acceptable
- **Start:** Day 6 | **Duration:** 1 day

**Phase 2 Completion:** 60% architecture → 75% working

---

## Phase 3: Method Invocation (Weeks 2-3)

### Task 3.1: Method Definition Processing ⏳
- [ ] Update AST builder to mark methods
- [ ] Extract method_type from context
- [ ] Update `visit_TypeDef()` to separate fields and methods
- **Start:** Day 7 | **Duration:** 1 day

### Task 3.2: Method Call Evaluation ⏳
- [ ] Implement `visit_Attribute()` for method name access
- [ ] Implement `_invoke_method()` in expressions.py
- [ ] Create method execution scope
- **Start:** Day 8 | **Duration:** 1.5 days

### Task 3.3: THIS Parameter Binding ⏳
- [ ] Handle THIS in method parameters
- [ ] Bind THIS to method scope
- [ ] Access THIS fields in method body
- **Start:** Day 9 | **Duration:** 1 day

### Task 3.4: Method Return Values ⏳
- [ ] Support explicit return statements
- [ ] Handle implicit returns
- [ ] Return type checking (optional)
- **Start:** Day 10 | **Duration:** 0.5 day

### Task 3.5: Testing Phase 3 ⏳
- [ ] Create `test_udt_methods.py`
- [ ] All 5 tests passing
- [ ] Method chaining works
- [ ] THIS binding verified
- **Start:** Day 10 | **Duration:** 1 day

### Task 3.6: Integration & Verification ⏳
- [ ] Phase 2 tests still pass
- [ ] v5 features unaffected
- [ ] No performance regressions
- **Start:** Day 11 | **Duration:** 1 day

**Phase 3 Completion:** 75% → 85% working

---

## Phase 4: Collections (Week 3-4)

### Task 4.1: Matrix Type Implementation ⏳
- [ ] Create `matrix.py` module
- [ ] Implement `Matrix` class
- [ ] Implement 70+ matrix operations
- [ ] Tests: 20/20 passing
- **Start:** Day 12 | **Duration:** 2 days

### Task 4.2: Map Type Implementation ⏳
- [ ] Create `map.py` module
- [ ] Implement `Map` class
- [ ] Implement 10+ map operations
- [ ] Tests: 10/10 passing
- **Start:** Day 14 | **Duration:** 1.5 days

### Task 4.3: Collections Integration ⏳
- [ ] Register Matrix in type system
- [ ] Register Map in type system
- [ ] Update evaluator dispatch tables
- **Start:** Day 15 | **Duration:** 1 day

### Task 4.4: Testing Collections ⏳
- [ ] Create `test_collections.py`
- [ ] Matrix operations: 20 tests
- [ ] Map operations: 10 tests
- [ ] Nested collections: 5 tests
- **Start:** Day 16 | **Duration:** 1 day

**Phase 4 Completion:** 85% → 90% working

---

## Phase 5: Built-in Functions (Weeks 4-5)

### Task 5.1: Ticker Functions ⏳
- [ ] Create `ticker.py` module
- [ ] Implement 8 ticker functions
- [ ] Tests: 8/8 passing
- **Start:** Day 17 | **Duration:** 1 day

### Task 5.2: Logging Functions ⏳
- [ ] Create `logging.py` module
- [ ] Implement 3 logging functions
- [ ] Tests: 3/3 passing
- **Start:** Day 18 | **Duration:** 0.5 day

### Task 5.3: Chart Point & Polyline Functions ⏳
- [ ] Extend `drawing.py` module
- [ ] Implement 5 chart.point functions
- [ ] Implement 3 polyline functions
- [ ] Tests: 8/8 passing
- **Start:** Day 18 | **Duration:** 1.5 days

### Task 5.4: Testing Built-ins ⏳
- [ ] Create `test_builtins_v6.py`
- [ ] All function groups tested
- [ ] Edge cases covered
- [ ] Integration tests
- **Start:** Day 20 | **Duration:** 1 day

### Task 5.5: Final Integration ⏳
- [ ] All phases working together
- [ ] No conflicts between features
- [ ] Performance verified
- [ ] Documentation updated
- **Start:** Day 21 | **Duration:** 2 days

**Phase 5 Completion:** 90% → 100% working

---

## Key Metrics to Track

### Completion Status
- [ ] Phase 2: 0% → 100% (Days 1-6)
- [ ] Phase 3: 0% → 100% (Days 7-11)
- [ ] Phase 4: 0% → 100% (Days 12-16)
- [ ] Phase 5: 0% → 100% (Days 17-21)

### Quality Gates
- [ ] All tests passing (95%+ pass rate)
- [ ] Code coverage > 90%
- [ ] No breaking changes to v5
- [ ] Round-trip parse/unparse verified
- [ ] Performance acceptable

### Files to Create
1. `src/pynescript/ast/evaluator/builtins/matrix.py` (Phase 4)
2. `src/pynescript/ast/evaluator/builtins/map.py` (Phase 4)
3. `src/pynescript/ast/evaluator/builtins/ticker.py` (Phase 5)
4. `src/pynescript/ast/evaluator/builtins/logging.py` (Phase 5)
5. `tests/test_udt_instantiation.py` (Phase 2)
6. `tests/test_udt_methods.py` (Phase 3)
7. `tests/test_collections.py` (Phase 4)
8. `tests/test_builtins_v6.py` (Phase 5)

### Files to Modify
1. `src/pynescript/ast/evaluator/types.py` (Phase 2)
2. `src/pynescript/ast/evaluator/base.py` (Phase 2)
3. `src/pynescript/ast/evaluator/statements.py` (Phases 2-3)
4. `src/pynescript/ast/evaluator/expressions.py` (Phases 2-3)
5. `src/pynescript/ast/evaluator/builtins/drawing.py` (Phase 5)
6. `docs/pinescript_implementation_status.md` (All phases)

---

## Daily Standup Template

### Daily Update (at end of day)
```
**Date:** [Day X]
**Phase:** [Phase 2/3/4/5]
**Tasks Today:**
- [x] Task A - Description
- [ ] Task B - Blocked by X

**Completed:**
- Count tests passing: N/total
- Line of code written: N

**Blockers:**
- None / Description

**Tomorrow:**
- Task C - Description
```

---

## Success Looks Like

### Phase 2 Complete ✅
```pine
indicator("Test")

type Trade
    float price = 0.0
    int qty = 0

t = Trade.new(99.50, 100)
plot(t.price)  // Works!
```

### Phase 3 Complete ✅
```pine
indicator("Test")

type Account
    float balance = 0.0

method withdraw(Account this, float amount) =>
    this.balance := this.balance - amount
    this.balance

a = Account.new(1000.0)
result = a.withdraw(100.0)
plot(result)  // Works!
```

### Phase 4 Complete ✅
```pine
indicator("Test")

// Matrix
m = matrix.new<float>(3, 3, 0.0)
matrix.set(m, 0, 0, 100.0)

// Map
trades = map.new<string, float>()
trades.put("BTC", 50000.0)
```

### Phase 5 Complete ✅
```pine
indicator("Test")

// Ticker
ticker = ticker.new("EURUSD", session=session.extended)

// Logging
log.info("Processing bar: " + str.tostring(bar_index))

// Chart points
pt = chart.point.new(time, close)

// Polyline
points = array.new<chart.point>()
array.push(points, pt)
```

---

## Quick Reference: Next Steps

1. **Read** `PHASE_2_ROADMAP.md` (detailed specs)
2. **Understand** current types.py structure
3. **Start** Task 2.1: Add UDT classes to types.py
4. **Write** tests as you implement
5. **Verify** round-trip parse/unparse
6. **Move** to next task

---

**Ready to begin Phase 2? Start with Task 2.1! 🚀**

