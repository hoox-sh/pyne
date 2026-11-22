# PYNE library methods — slice 1: fail closed on compile

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: library/exported method calls execute on compile (currently stubbed to np.nan/None — silent na)`
- **Status:** implementation slice in progress; no commit/push.

## Why this slice

The inventory found imported library calls are stubbed to `np.nan`/`None` on
compile (`compiler.py:7129, 7144`), so a library-based indicator can silently
return `na` while interpret returns the real value.

Inlining exported library ASTs would require new compile/disk-cache plumbing
(library sources are currently registered only in the interpret evaluator).
This slice takes option (b): **fail loudly when a caller supplies library
sources and explicitly asks for compile**. `mode="auto"` already skips imports
and falls back to interpret. The no-library stub contract is preserved so the
existing P1p residual test (`VAT.getArrayFromString` no-raise) stays intact.

## Acceptance criteria

1. `Runtime.run(..., mode="compile", libraries=[...])` on a script with a
   top-level library import returns `error_kind="compile"` with a message that
   says compile does not execute library imports and points to interpret/auto.
2. The error result has no `series` payload (no silent `na` values).
3. `mode="auto"` with the same library source still uses interpret and returns
   the real value.
4. Explicit compile with an import but **no** supplied library source keeps the
   existing stub/no-raise behavior (P1p residual preserved).
5. A multi-line string containing a line that starts with `import` is **not**
   treated as an import by compile or auto eligibility.
6. Targeted library/compiler suites stay green.

## Out of scope

- Actually executing/inlining exported library functions or methods.
- Direct `compile_script()` stub behavior (host `Runtime.run` is the contract).
- Library constants/enums beyond the existing interpret path.
- **Carve-out:** the no-libraries path still silently stubs to `na`. Follow-up:
  fail closed on any real import + update the P1p residual test, or implement
  library inlining on compile.

## Implementation sketch

- Thread `libraries` into `Runtime._run_compiled`.
- `_has_top_level_import` (`runtime/host.py:459`) uses the cheap line regex only
  as a prefilter, then parses and checks for real `Import` AST nodes. Shared by
  `_compile_eligible` (`host.py:4279`) and `_run_compiled` (`host.py:4479`).
- Before compile/cache, if `libraries` is non-empty and the source has a real
  top-level `import`, return a classified compile error:
  `"Compile mode does not execute library imports; use mode=interpret or auto"`.
- `auto` uses the same detector for eligibility, so string contents no longer
  force an unnecessary interpret fallback.

## Proof plan

- Failing-before: explicit compile with library source returns `None` series and
  no error.
- After: compile error; auto returns `1.5`.
- Named `oo proof attach --expect` assertion plus targeted pytest counts.

## Implementation

- `runtime/host.py:4409` — `_run_compiled` accepts `libraries`.
- `runtime/host.py:4459-4470` — before compile/cache, when `libraries` is
  non-empty and the source has a top-level `import`, return a classified
  `error_kind="compile"` error pointing to `interpret`/`auto`.
- `Runtime.run` and `_run_auto` pass `libraries` through; `auto` still rejects
  imports during eligibility and uses interpret.

## Failing-before evidence

```text
mode=compile, libraries=[Lib]  -> error=None, series={'plot_0': [None, None, None, None]}
mode=auto,    libraries=[Lib]  -> auto_backend=interpret, series={'plot_0': [1.5, ...]}
```

## After evidence

```text
mode=compile, libraries=[Lib]  -> error_kind=compile,
  "Compile mode does not execute library imports; use mode=interpret or auto"
mode=auto,    libraries=[Lib]  -> auto_backend=interpret, series=1.5
mode=compile, no libraries     -> no error (existing stub contract preserved)
```

- New tests: `tests/test_compiler_library_fail_closed.py` — **4 passed**
  (fail-closed, auto fallback, string-import compile, string-import auto).
- Targeted library/compiler suite — **278 passed**.
- Checker false-positive regression (`90bd81ac`): a multi-line string containing
  `import fake/lib/1` now compiles with libraries supplied; `auto` stays
  compile-eligible.
- Proof output:
  `LIBRARY_FAIL_CLOSED_OK compile_error=1 auto=1.5 no_lib_stub=1 string_import=0`.

## Proof

- `.oo/plans/pyne-library-methods-2026-11-15.proof.py`
- `oo proof attach --expect "LIBRARY_FAIL_CLOSED_OK compile_error=1 auto=1.5 no_lib_stub=1 string_import=0"`
- Proof records are attached to the card; the plan artifact proof is re-attached
  after this final edit so it pins the current content.
