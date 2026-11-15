# PYNE cross-library calls — slice 1: A calls B's export, alias scoping + cycles

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: cross-library calls between supplied libraries on compile (alias scoping + cycles)`
- **Status:** implementation slice; no commit/push.

## Slice choice and why

Same-library internal calls are inlined (previous slice). A library source that
imports another supplied library and calls its export still fails closed with
`calls unsupported namespace <alias>`.

This slice covers the two-library shape: library **A** imports library **B**
(`import ns/B/1 as b`) and an A export calls `b.fn(...)`. The import alias is
local to A, so the compiler must:

1. resolve B from the supplied library set;
2. inline B's exported functions under a synthetic alias that cannot collide
   with the consumer's aliases;
3. rewrite A's `b.fn(...)` call targets to that synthetic alias;
4. reject cycles (A imports B, B imports A) instead of recursing forever.

Nesting is implemented recursively, but only two libraries are covered by tests.
Cross-library UDTs, methods and constants stay out of scope.

## Acceptance criteria

1. Libraries A (`export add(float x) => b.twice(x) + 1`, `import ns/B/1 as b`)
   and B (`export twice(float x) => x * 2`): consumer imports A as `a`,
   `a.add(close)` → `202.0, 204.0, 206.0, 208.0`; compile equals interpret.
2. **Alias scoping:** A's internal alias `b` is local to A. The consumer can also
   import B under a different alias and call it directly; both paths work and
   neither leaks into the other.
3. **Missing source:** if A imports B but B is not supplied, compile fails
   closed with `library source not supplied for ns/B/...`.
4. **Cycle:** A imports B and B imports A fails closed with a recursive-import
   error; no infinite recursion, no silent na.
5. **Unknown export:** A calls `b.missing(...)` where B has no such export →
   compile error (unsupported library method), no silent na.
6. Same-library internal calls, UDTs/methods, free functions, scalar methods,
   parse-cache deep copy, alias-before-builtin, no-library stub and nopython
   recovery remain unchanged.
7. Targeted library/compiler suites stay green.

## Out of scope (documented, still fail closed)

- Cross-library UDT types/constructors/methods.
- Library constants imported across libraries.
- Re-exported aliases (`export` of an imported name).
- **Cross-library default arguments**: an exported callee with a default param
  called directly from another library inherits the pre-existing consumer
  default-fill gap (card `pyne-exported-library-function-w-e2d1bfbd`).
- `ta.*` / drawings / request.* inside cross-library callees.

## Implementation sketch

- Split `visit_Import` into a wrapper + `_visit_import_inner`:
  - wrapper computes `(namespace, name, version)`, rejects it if already on
    `_library_import_stack`, pushes, delegates, pops in `finally`.
- In the inner, before types/functions, walk the library's own `Import` nodes:
  - resolve the target from `self.libraries` (missing → existing fail-closed);
  - allocate a collision-free synthetic alias (`__xlib_<n>`, checked against
    existing aliases and assigned synthetics) and reuse it when the same
    library is imported twice;
  - set the import node's alias to the synthetic alias and call `visit_Import`
    recursively (this registers B's exports in
    `library_methods[(synthetic, fn)]`);
  - rewrite `alias.fn(...)` call bases in the library body to the synthetic
    alias (only `Call.func` attributes; a bare alias stays fail-closed).
- `_library_function_unsupported` accepts the synthetic aliases as call
  namespaces for that library's bodies.
- Existing paths handle missing source (`library source not supplied`) and
  unknown exports (`unsupported library method <synthetic>.<fn>`).

## Proof plan

- Failing-before: `a.add(close)` with A→B returns
  `library function add calls unsupported namespace b`.
- After: `202.0, 204.0, 206.0, 208.0`; alias scoping, missing source, cycle and
  unknown export fail closed as specified.
- Proof script prints `CROSS_LIBRARY_OK ...`; attached with a named `--expect`
  assertion. Targeted pytest counts recorded below.

## Results

### Failing-before

**A. Feature absent (HEAD `1a632f0e`)** — the five original cross-library
shapes all fail:

```text
5 failed, 31 deselected
FAILED test_cross_library_call_inlines
FAILED test_cross_library_alias_scoping
FAILED test_cross_library_missing_source_fails_closed
FAILED test_cross_library_cycle_fails_closed
FAILED test_cross_library_unknown_export_fails_closed
```

Every shape failed at HEAD with
`library function add calls unsupported namespace b`.

**B. Alias collisions (pre-fix `6b3599ef`)** — the three collision regressions
fail against the old cross-library code:

```text
3 failed, 39 deselected
FAILED test_cross_library_synthetic_alias_tuple_collision
FAILED test_cross_library_consumer_alias_lookalike_is_scoped
FAILED test_cross_library_parameter_shadowing_fails_closed
```

**C. Incoming-alias guard (pre-fix `6b3599ef`)** — the real `__xlib_1`
collision test fails against the old code, which had no incoming-alias check:

```text
1 failed, 2 passed, 39 deselected
FAILED test_cross_library_incoming_alias_after_a_fails_closed
```

The library-local edge failing-before is checker proof `24f1038c` (the
round-2 compiler silently sent both calls to one library). Transcript:
`pyne-cross-library-calls-2026-11-15.failing-before.txt`.

### After

- `tests/test_compiler_library_inline.py` — **42 passed**.
- Targeted library/UDT/compiler suites — **150 passed**.
- Full `tests/test_compiler_*.py` — **474 passed**.
- Proof token:
  `CROSS_LIBRARY_OK call=202.0 alias_add=202.0 alias_twice=201.0 nest=203.0 missing=1 cycle=1 unknown=1 same_lib=202.0 udt=101.5 tuple_collision=302.0 consumer_alias=202.0 param_shadow=1 local_alias=1202.0 incoming_after=1 incoming_before=202.0 no_lib=1`.
- Extra coverage beyond the criteria: two-level nesting (A → B → C) compiles
  and matches interpret (`203, 205, 207, 209`).
- Note: two different libraries using the **same internal alias** for different
  targets compiles correctly, but the interpreter has a pre-existing global
  alias-scoping limitation for that shape. Compile is this card's scope; the
  tested alias-scoping case (consumer imports B under its own alias) is green in
  both modes.

## Checker conditions (round 2)

- **Synthetic alias collision.** `__xlib_<namespace>_<name>_<version>`
  collapsed `a/b_c/1` and `a_b/c/1` to the same alias, so one callee won and
  `b1.fn + b2.fn` returned the wrong series. Fixed with a monotonic
  `__xlib_<n>` allocator that checks `import_aliases` and every assigned
  synthetic; the tuple→alias map stays the single source of truth. Regression:
  `test_cross_library_synthetic_alias_tuple_collision` (302…).
- **Consumer alias collision.** A consumer alias equal to a synthetic alias
  could overwrite another library's `(alias, fn)` mapping. Fixed by the
  collision-free allocator plus a fail-closed check when an incoming import
  alias equals an assigned synthetic for a different target. Regression:
  `test_cross_library_consumer_alias_lookalike_is_scoped` (add 202…, d 200.5…).
- **Parameter shadowing.** The alias rewrite ignored scope, so
  `export add(float b) => b.fn()` with `b` also an import alias was sent to the
  library. Fixed by rewriting per function and skipping functions where the
  alias is a parameter or assigned local; the validator then fails closed
  (`unsupported namespace b`). Regression:
  `test_cross_library_parameter_shadowing_fails_closed` (compile error, no
  series).
- **Library-local alias collision (round 3).** A library's own import alias can
  equal an allocated synthetic (`import ... as __xlib_1`). The sequential
  rewrite then re-mapped the earlier synthetic, silently sending both calls to
  one library. Fixed by pre-collecting local aliases for allocation and
  rewriting all local aliases once from a map (no chaining). Regression:
  `test_cross_library_local_alias_collision` (1202…). Also added
  `test_cross_library_incoming_alias_after_a_fails_closed` (`import alias
  __xlib_1 collides`) and `test_cross_library_incoming_alias_before_a_is_skipped`
  (allocator skips; add 202…, d 200.5…).

### Files

- `src/pynescript/compiler/compiler.py` — import-stack wrapper, collision-free
  synthetic aliases, scope-aware call-target rewriting, validator namespaces.
- `tests/test_compiler_library_inline.py` — 11 new tests (42 total).
- `.openorchestrate/plans/pyne-cross-library-calls-2026-11-15.md` (this file),
  `.proof.py`, `.failing-before.txt`.
