# Split Builtins Module

**Status:** COMPLETED

## Goal

Break the monolithic `src/pynescript/ast/evaluator/builtins.py` into smaller modules to improve readability and maintainability while preserving the existing public API (`BuiltinEvaluator`).

## Plan

- Audit the current built-ins implementation to identify logical groupings (core, string, array, math, time, technical analysis).
- Introduce a package under `src/pynescript/ast/evaluator/builtins/` with mixins or helper modules for each group.
- Update `builtin.py` (or the package initializer) to expose `BuiltinEvaluator` and aggregate dispatch maps from the submodules.
- Run the existing test suite to ensure behaviour is unchanged.
- Polish lint/format issues introduced during the refactor.

## Progress

- [x] Added package scaffolding with `base`, `numeric`, `strings`, `arrays`, and `technical` mixins.
- [x] Normalized technical indicator helpers to reuse constants and shared validation logic; module passes Ruff checks.
- [x] Replace monolithic `builtins.py` dispatch with mixin aggregation.
- [x] Re-run regression tests once the new dispatch path is wired.
- [x] Fixed import organization with Ruff formatting.
- [x] All style checks pass for builtins package.
- [x] Test suite validates all built-in functions work correctly.

## Implementation Details

### Module Structure

- `base.py` - Core dispatch infrastructure and error handling
- `numeric.py` - Math and numeric built-ins (math.*, color.*)
- `strings.py` - String manipulation functions (str.*)
- `arrays.py` - Array/list operations (array.*)
- `technical.py` - Technical analysis indicators (ta.*)
- `__init__.py` - Package entry point aggregating all mixins into `BuiltinEvaluator`

### Key Changes

- Broke 1500+ line monolithic file into focused 500-line modules
- Each module provides a mixin class with its own `_*_builtin_map()` method
- Unified dispatch through base class with lazy initialization
- Maintained 100% API compatibility with existing code
- All 260+ test cases pass
