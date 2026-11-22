# PYNE library inlining — slice 1: exported pure function

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: inline exported library functions/methods on compile (execute, not stub)`
- **Status:** implementation slice in progress; no commit/push.

## Why this slice

Compile had no library-source plumbing; imported calls were stubbed to
`np.nan`/`None`, and the previous slice made explicit compile fail closed when
library sources were supplied. This slice resolves one simple exported free
function from the supplied library source and inlines it into the generated
Python module.

The existing UDF emitter can emit a parsed library `FunctionDef` directly, so
the minimal path is: parse the library, strip `export`, mangle the function name,
emit it as a local UDF, and map `alias.name(...)` calls to it. No disk/IR cache
is used for library runs because the same consumer source can produce different
IR for different library sources.

## Acceptance criteria

1. A library exporting a pure free function
   (`export add(float a, float b) => a + b`) compiles and runs.
2. Compiled output matches interpret for a small fixture
   (`lib.add(close, 1.0)` → `close + 1`).
3. Unsupported library constructs (methods, constants, missing exports, missing
   source, kwargs, overloads) fail closed with a clear compile error pointing to
   interpret/auto; no silent `na`.
4. No-library compile keeps the existing stub/no-raise contract (P1p residual).
5. Library runs bypass source-keyed host/disk caches; a later no-library run is
   not contaminated.
6. Builtin-named exports (`plot`, `alert`) resolve as library calls, not the
   builtin handlers.
7. Targeted library/compiler suites stay green.

## Out of scope

- Exported methods and UDT/type/enum exports.
- Library functions calling other library functions.
- Keyword-argument calls, overloaded library functions.
- Library-source caching / disk IR for library runs.

## Implementation sketch

- Thread `libraries` through `compile_script` / `_transpile_once` /
  `CompilerVisitor`.
- `visit_Import`: resolve the matching library source, parse it, emit exported
  free functions under `__lib_<alias>_<name>`, map `(alias, name)` to the
  emitted Python name.
- `visit_Call`: inline mapped calls with positional args; set
  `library_inline_error` for unsupported constructs.
- `compile_script(libraries=...)`: bypass memory/disk/IR caches.
- `Runtime._run_compiled`: pass `libraries`; skip host compile cache for library
  runs; remove the old blanket fail-closed early return.

## Proof plan

- Failing-before: explicit compile with library source returned the fail-closed
  compile error; interpret returned `101.5`.
- After: compile returns `101.5` matching interpret; unsupported method still
  fails closed.
- Named `oo proof attach --expect` assertion plus targeted pytest counts.

## Implementation

- `compiler/compiler.py:607` — `CompilerVisitor` accepts `libraries`;
  `library_methods` maps `(alias, Pine name)` to the emitted Python def.
- `compiler/compiler.py:1060-1116` — `visit_Import` resolves the matching
  library source, parses it, emits exported free functions as
  `__lib_<alias>_<name>`, and records the alias mapping.
- `compiler/compiler.py:7235-7243` — `visit_Call` inlines mapped positional
  calls; unsupported methods/kwargs set `library_inline_error` and fail closed.
- `compiler/engine.py:1192, 1693-1740` — `libraries` threaded through
  `_transpile_once` / `compile_script`; library runs bypass memory/disk/IR
  caches and are warmed directly.
- `runtime/host.py:4490-4496` — `_run_compiled` passes `libraries`, skips the
  source-keyed host cache for library runs, and no longer blanket-fails imports.

## Failing-before evidence

Before inlining, explicit compile with a supplied library source returned the
fail-closed compile error instead of executing:

```text
mode=compile, libraries=[Lib]  -> error_kind=compile
interpret                      -> plot_0 = 101.5, 102.5, 103.5, 104.5
```

## After evidence

```text
mode=compile, libraries=[Lib add]  -> sum = 101.5, 102.5, 103.5, 104.5
mode=compile, libraries=[Lib sub]  -> sum = 99.5, 100.5, 101.5, 102.5
mode=compile, unsupported method   -> error_kind=compile
mode=compile, no libraries         -> no error (legacy stub contract)
```

- New tests: `tests/test_compiler_library_inline.py` — **9 passed**.
- Targeted library/compiler suite — **287 passed**.
- Proof output:
  `LIBRARY_INLINE_OK sum=101.5 reuse=1 same_name=1 const=1 internal=1 plot_collision=1 alert_collision=1 unsupported=1 no_lib=1`.

## Proof

- `.oo/plans/pyne-library-inline-2026-11-15.proof.py`
- `oo proof attach --expect "LIBRARY_INLINE_OK sum=101.5 reuse=1 same_name=1 const=1 internal=1 plot_collision=1 alert_collision=1 unsupported=1 no_lib=1"`
- Proof records are attached to the card; the plan artifact proof is re-attached
  after this final edit so it pins the current content.

## Checker blocker fixes

1. **Parse-cache AST mutation** — `compiler.py:1091` deep-copies the cached
   library AST before renaming/stripping `export`. Regression: two consumers
   sharing one library source both compile (`reuse=1`).
2. **Script UDF shadowing** — alias calls resolve before script UDF dispatch
   (`compiler.py:5908`). Regression: script `add()` no longer captures
   `lib.add(...)`; result is 101.5 (`same_name=1`).
3. **Unsupported constructs fail closed** — `_library_function_unsupported`
   (`compiler.py:10357`) validates exported bodies. Library constants
   (`BIAS`) and calls to other library functions (`helper`) produce compile
   errors, not runtime NameError/silent na (`const=1`, `internal=1`).
4. **Nopython recovery path** — `_warm_numeric_or_fallback` now accepts and
   forwards `libraries` to `_transpile_once`, and uses `ir_key=None` for the
   recovered object-mode module (`engine.py:1590-1598`). Unit regression
   `test_library_nopython_recovery_passes_libraries` passes.
5. **Builtin-name collision** — alias resolution now runs immediately after
   argument resolution, before any builtin handler (`compiler.py:5330`).
   Regressions: library exports named `plot` and `alert` return `101.5…`, not
   the builtin behavior (`plot_collision=1`, `alert_collision=1`).

Out of scope remains: exported methods/UDTs/types/enums, library-to-library
calls, keyword args/overloads, and library IR caching.

## Pure-function allowlist

This slice's "pure free function" means: parameters, locals, literals,
`math.*`, `str.*`, and the bare calls `abs`, `min`, `max`, `round`, `int`,
`float`, `bool`, `nz`, `na`, `fixnan`. `ta.*` is intentionally rejected as
`unsupported namespace ta`; exported methods/UDTs/types/enums and calls to
other library functions also fail closed. A later slice can widen the allowlist.
