# 🎯 Phase 2-5 Implementation: Quick Start

**Status:** Ready to Start 🚀  
**Date:** October 24, 2025  
**Phases:** 2 (Object Instantiation), 3 (Methods), 4 (Collections), 5 (Built-ins)

---

## What's Ready?

✅ **Foundation Complete (Phase 1)**
- Grammar updated and regenerated
- Parser understands all UDT/method syntax
- AST builder processes type definitions
- Type system foundation in place
- Evaluator integrated

✅ **Ready to Implement**
- Object instantiation (.new() method)
- Field access and mutation
- Method definitions and invocation
- Matrix and Map collections
- Built-in functions

---

## Phase 2: Object Instantiation

**Goal:** Create and use UDT instances

### Step 1: Understand Current State

Review these files to understand the architecture:

```bash
# Type system (see what's already there)
cat src/pynescript/ast/evaluator/types.py

# Evaluator base (TypeRegistry)
cat src/pynescript/ast/evaluator/base.py

# Where TypeDef is evaluated
grep -n "visit_TypeDef" src/pynescript/ast/evaluator/statements.py
```

### Step 2: Add UDT Classes (4 hours)

**File:** `src/pynescript/ast/evaluator/types.py`

Add these three classes:
- `UserDefinedType` - Represents a UDT definition
- `Field` - Represents a type field
- `ObjectInstance` - Represents a runtime instance

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.1

### Step 3: Test UDT Classes (2 hours)

**File:** `tests/test_udt_types.py` (NEW)

Write 4 simple tests:
- Create UDT with fields
- Create ObjectInstance
- Access/set fields
- Copy instance

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.1

### Step 4: Enhance TypeRegistry (2 hours)

**File:** `src/pynescript/ast/evaluator/base.py`

Add three methods:
- `register_udt(udt)` - Register a UDT
- `get_udt(name)` - Retrieve by name
- `list_udt_names()` - List all UDTs

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.2

### Step 5: Update TypeDef Evaluation (3 hours)

**File:** `src/pynescript/ast/evaluator/statements.py`

Modify `visit_TypeDef()` to:
- Extract field definitions
- Create UserDefinedType
- Register in TypeRegistry

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.3

### Step 6: Implement .new() Constructor (5 hours)

**File:** `src/pynescript/ast/evaluator/expressions.py`

Add methods to CallEvaluator:
- `_handle_udt_new()` - Create instance
- Update `visit_Call()` - Detect .new() calls

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.4

### Step 7: Implement Field Access (3 hours)

**File:** `src/pynescript/ast/evaluator/expressions.py`

Modify `visit_Attribute()` to:
- Get field value from ObjectInstance
- Support nested access

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.5

### Step 8: Implement Field Mutation (3 hours)

**File:** `src/pynescript/ast/evaluator/statements.py`

Modify `visit_AugAssign()` to:
- Detect `obj.field := value`
- Update field via `set_field()`

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.6

### Step 9: Comprehensive Tests (4 hours)

**File:** `tests/test_udt_instantiation.py` (NEW)

Write 8 tests covering:
- Simple object creation
- Object with arguments
- Named arguments
- Field access
- Field mutation
- .copy() method
- Objects in arrays
- Nested objects

**Spec in:** `PHASE_2_ROADMAP.md` → Section 2.7

**Total Phase 2: ~25 hours over 5-6 days**

---

## Phase 3: Method Invocation

**Goal:** Support method definitions and calls with THIS binding

### Overview

Once Phase 2 is complete:
1. Process method definitions (attach to UDT)
2. Handle method calls (obj.method(args))
3. Bind THIS parameter to instance
4. Execute method body with bound THIS

**Details in:** `PHASE_2_ROADMAP.md` → Phases 3.1-3.6

**Total Phase 3: ~15 hours over 3-4 days**

---

## Phase 4: Collections

**Goal:** Implement Matrix and Map types

### Overview

1. Create Matrix class with 70+ operations
2. Create Map class with 10+ operations
3. Integrate with evaluator
4. Comprehensive testing

**Details in:** `PHASE_2_ROADMAP.md` → Phases 4.1-4.4

**Total Phase 4: ~20 hours over 4-5 days**

---

## Phase 5: Built-in Functions

**Goal:** Implement specialized functions

### Overview

1. Ticker functions (8 functions)
2. Logging functions (3 functions)
3. Chart.point functions (5 functions)
4. Polyline functions (3 functions)

**Details in:** `PHASE_2_ROADMAP.md` → Phases 5.1-5.5

**Total Phase 5: ~15 hours over 3-4 days**

---

## Implementation Commands

### Check current state
```bash
cd /home/jango/Git/pynescript

# View current types
head -50 src/pynescript/ast/evaluator/types.py

# Check TypeRegistry
grep -A 20 "class TypeRegistry" src/pynescript/ast/evaluator/base.py

# See TypeDef handling
grep -A 30 "def visit_TypeDef" src/pynescript/ast/evaluator/statements.py
```

### Run tests
```bash
# After implementing Phase 2
pytest tests/test_udt_types.py -v
pytest tests/test_udt_instantiation.py -v

# After implementing Phase 3
pytest tests/test_udt_methods.py -v

# After implementing Phase 4
pytest tests/test_collections.py -v

# After implementing Phase 5
pytest tests/test_builtins_v6.py -v
```

### Verify round-trip
```bash
# Make sure parse/unparse still works
python -m pytest tests/test_parse_and_unparse.py -v
```

---

## Success Checklist

### Phase 2: Object Instantiation
- [ ] UDT classes added to types.py
- [ ] TypeRegistry methods added
- [ ] visit_TypeDef registers UDTs
- [ ] .new() creates instances
- [ ] Field access works
- [ ] Field mutation works
- [ ] 8/8 tests passing
- [ ] v5 features still work

### Phase 3: Method Invocation
- [ ] Methods attached to UDT
- [ ] Method calls evaluated
- [ ] THIS binding works
- [ ] Method returns work
- [ ] 5/5 tests passing
- [ ] Phase 2 tests still pass

### Phase 4: Collections
- [ ] Matrix class implemented
- [ ] Map class implemented
- [ ] 70+ matrix operations
- [ ] 10+ map operations
- [ ] 35/35 tests passing
- [ ] Previous phases still work

### Phase 5: Built-in Functions
- [ ] 8 ticker functions
- [ ] 3 logging functions
- [ ] 5 chart.point functions
- [ ] 3 polyline functions
- [ ] 19/19 tests passing
- [ ] All previous phases work

---

## Documentation

### Main Roadmap
📄 `PHASE_2_ROADMAP.md` - Detailed specifications for all phases

### Implementation Tracker
📄 `IMPLEMENTATION_TRACKER.md` - Daily checklist and progress

### Quick References
- `copilot-instructions.md` - Architecture overview
- `V6_UDT_METHODS_IMPLEMENTATION.md` - Original design doc

---

## Key Files to Know

### Type System
- `src/pynescript/ast/evaluator/types.py` - Core types (EXTEND)
- `src/pynescript/ast/evaluator/base.py` - TypeRegistry (EXTEND)

### Evaluators
- `src/pynescript/ast/evaluator/statements.py` - Statement evaluation (EXTEND)
- `src/pynescript/ast/evaluator/expressions.py` - Expression evaluation (EXTEND)

### Built-ins
- `src/pynescript/ast/evaluator/builtins/` - Built-in functions (CREATE new modules)

### Tests
- `tests/test_udt_*.py` - UDT tests (CREATE new files)
- `tests/test_collections.py` - Collection tests (CREATE new)
- `tests/test_builtins_v6.py` - Built-in tests (CREATE new)

---

## Next Immediate Actions

1. **Read** `PHASE_2_ROADMAP.md` sections 2.1-2.8
2. **Review** `src/pynescript/ast/evaluator/types.py` to understand existing structure
3. **Review** `src/pynescript/ast/evaluator/base.py` TypeRegistry class
4. **Start** Task 2.1: Add UserDefinedType, Field, ObjectInstance classes
5. **Write** initial tests in `test_udt_types.py`
6. **Iterate** through remaining Phase 2 tasks

---

## Timeline Estimate

**Week 1 (Oct 28 - Nov 1)**
- Phase 2: Object instantiation complete

**Week 2 (Nov 4 - Nov 8)**
- Phase 3: Method invocation complete

**Week 3 (Nov 11 - Nov 15)**
- Phase 4: Collections complete (partial)

**Week 4 (Nov 18 - Nov 22)**
- Phase 4: Collections complete
- Phase 5: Built-in functions complete

**Target:** All v6 major features complete by late November ✅

---

## Support & Resources

### Need help understanding?
- Check `PHASE_2_ROADMAP.md` detailed specs
- Review existing evaluator patterns
- Look at test examples

### Stuck on implementation?
- Break task into smaller steps
- Write test first, then implementation
- Verify round-trip parse/unparse
- Run full test suite

### Performance concerns?
- Profile with larger scripts
- Optimize critical paths
- Document performance tradeoffs

---

## 🚀 Ready to Begin?

Start with Phase 2, Task 2.1:

```bash
cd /home/jango/Git/pynescript

# Open types.py and add the three UDT classes
# Follow the spec in PHASE_2_ROADMAP.md section 2.1

# Then create and run tests
python -m pytest tests/test_udt_types.py -v
```

Let's build this! 💪

