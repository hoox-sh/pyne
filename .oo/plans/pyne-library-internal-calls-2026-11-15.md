# PYNE library-to-library calls — slice 1: same-library internal calls

- **Date:** 2026-11-15
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `PYNE: support library-to-library calls on compile (currently fail closed)`
- **Status:** implementation slice; no commit/push.

## Slice choice and why

The card covers two shapes:

1. **same-library internal calls** — an exported library function calls another
   function in the same library source (exported or not);
2. **cross-library calls** — one supplied library imports and calls another
   supplied library.

This slice implements (1) only. It is the smaller, self-contained step: the
library source is already parsed and deep-copied, so callees are local AST
nodes. Cross-library calls need recursive library resolution, alias scoping and
cross-library cycle handling; that is a separate slice (see Out of scope).

Current behavior (measured): any call to a library-local function fails closed
at import with `library function <name> calls unsupported function <callee>`.
Non-exported helpers are never emitted, so even a defined helper is rejected.

## Acceptance criteria

1. An exported function calling a **non-exported helper** inlines:
   `export add(a) => helper(a) + 1`, `helper(a) => a * 2`,
   `lib.add(close)` → `202.0, 204.0, 206.0, 208.0`; compile equals interpret.
2. A **chain through an exported callee** works, including both entry points:
   `add → twice → deep`; `lib.add(close)` and `lib.twice(close)` both inline.
3. Helper **params, defaults and locals** are honored (`helper(a, k = 2.0)` with
   a local body).
4. An **unknown** function call still fails closed
   (`unsupported function missing`) — no silent na.
5. A **recursive/cyclic** helper graph fails closed
   (`recursive library function <name>`), no recursion at runtime.
6. An **unreachable** helper with an unsupported body (e.g. `ta.sma`) does not
   break the import; only the reachable closure is validated/emitted.
7. Existing behavior unchanged: free-function inlining, scalar-receiver methods,
   library UDTs/methods, parse-cache deep copy, alias-before-builtin, no-library
   stub, nopython recovery.
8. Targeted library/compiler suites stay green.

## Out of scope (documented, still fail closed)

- **Cross-library calls**: a library source importing another supplied library
  and calling `other.fn(...)`. Needs recursive library resolution and alias
  scoping; next slice.
- **Method-form helpers** as internal callees (`scale(x, 2.0)` where `scale` is
  an `export method`). Only non-method `FunctionDef`s are internal targets.
- **Library constants** referenced by a helper (still `unsupported name`).
- `ta.*` / drawing / request.* inside helpers.

## Implementation sketch

- Collect every non-method `FunctionDef` in the library body as `local_funcs`
  (exported and non-exported).
- `_library_called_names(fn)` returns call targets that are `Name` nodes.
- `emit_local(name)` walks callees first (DFS postorder), detects cycles via the
  active stack, validates with local names allowed, rewrites call targets to the
  mangled `__lib_<alias>_<name>`, then emits via `visit_FunctionDef`.
- The exported-function loop validates the entry point first (so its own errors
  win), emits its reachable helpers, rewrites its calls, then emits it.
- Already-emitted exported callees are not emitted twice; they are still mapped
  in `library_methods` so both `lib.add` and `lib.twice` resolve.
- `_library_function_unsupported(fn, params, local_names)` allows local function
  names as call targets/values; everything else stays fail-closed.

## Proof plan

- Failing-before: `lib.add(close)` with a helper returns
  `library function add calls unsupported function helper`.
- After: helper / chain / defaults values; unknown + recursive fail closed;
  unreachable helper ignored; previous slice tokens still green.
- Proof script prints one `LIBRARY_INTERNAL_OK ...` token per criterion;
  attached with a named `--expect` assertion.
- Targeted pytest counts recorded below.

## Results

### Failing-before (HEAD `b2f2012f` compiler, internal-call + regression tests)

```text
9 failed, 3 passed, 19 deselected
FAILED test_library_internal_helper_inlines
FAILED test_library_internal_chain_and_exported_callee_inline
FAILED test_library_internal_helper_defaults_and_locals
FAILED test_library_recursive_helper_fails_closed
FAILED test_library_duplicate_helper_names_fail_closed
FAILED test_library_duplicate_exported_and_helper_names_fail_closed
FAILED test_library_duplicate_exported_arities_fail_closed
FAILED test_library_helper_and_method_same_name_fail_closed
FAILED test_library_bare_builtin_call_inlines
```

Passed before: unknown callee (already fail-closed), unreachable helper (inert),
bare reference (already rejected as `uses unsupported name helper`). The duplicate and
helper/method shapes failed closed at HEAD with `calls unsupported function …`;
the tests pin the stricter exported-overload message. `bare_builtin` is a latent
validator bug fixed alongside this slice (allowed bare builtins were rejected
as free names). Transcript:
`pyne-library-internal-calls-2026-11-15.failing-before.txt`.

Before: `lib.add(close)` with a defined helper raised
`library function add calls unsupported function helper`.

### After

- `tests/test_compiler_library_inline.py` — **31 passed**.
- Targeted library/UDT/compiler suites — **139 passed**.
- Full `tests/test_compiler_*.py` — **463 passed**.
- Proof token:
  `LIBRARY_INTERNAL_OK helper=202.0 chain=203.0 twice=202.0 defaults=202.0 unknown=1 recursive=1 unused=1 method_helper=101.5 deep_chain=202.0 udt=101.5 free=101.5 scalar=201.0 dup=3 bare_ref=1 bare_builtin=100.5 helper_method=1 no_lib=1`.
- Extra coverage beyond the criteria: a UDT method body calling a helper, and
  a two-level non-exported chain, both compile==interpret.

## Checker conditions (round 2)

- **Duplicate same-library names (silent miscompile).** `local_funcs` collapsed
  duplicate non-method `FunctionDef`s by name (last wins), and the exported
  loop's "already emitted as callee" shortcut was keyed by Pine name, so a
  different same-name node bypassed the exported-overload guard. Fixed by:
  - failing closed eagerly while building `local_funcs` when a non-method
    `FunctionDef` name repeats, with the existing
    `overloaded library method/function <name> is not supported; use mode=interpret or auto`;
  - tracking emitted callees by **node identity** (`id(fn)`), so the shortcut
    fires only for the exact node; the name→mangled map remains for call
    rewriting only.
  Regressions: `test_library_duplicate_helper_names_fail_closed`,
  `test_library_duplicate_exported_and_helper_names_fail_closed`,
  `test_library_duplicate_exported_arities_fail_closed` — all assert
  `error_kind == "compile"`, the overload message, and no series.
- **Local helper vs exported method (same mangled name).** A non-exported
  `helper` and `export method helper(float this)` both lowered to
  `__lib_<alias>_helper`, so `lib.helper(close)` silently called the free
  helper. Fixed by failing closed when an exported method name exists in
  `local_funcs`. Regression:
  `test_library_helper_and_method_same_name_fail_closed`.
- **Bare local function reference.** Local names are now allowed only as a
  `Call.func`; a bare `helper` reference fails closed with
  `uses unsupported name helper` (pre-slice behavior). Regression:
  `test_library_bare_function_reference_fails_closed`.
- **Side effect of the validator restructure:** `Call.func` is no longer walked
  as a value, so allowed bare builtins (`abs`, `min`, …) now inline instead of
  being rejected as free names. Regression:
  `test_library_bare_builtin_call_inlines`.

### Follow-up filed (not fixed here)

- Pre-existing at HEAD `b2f2012f`: an exported library function with a default
  parameter called directly (`lib.add(close)` for
  `export add(float a, float k = 2.0)`) raises a runtime
  `TypeError: … missing 1 required positional argument: 'k'`. Internal direct
  calls now fill defaults; the consumer alias path still does not. Card already
  filed on the HQ board: `pyne-exported-library-function-w-e2d1bfbd` (Todo,
  `oo-spec-2`).

### Files

- `src/pynescript/compiler/compiler.py` — local-function collection, postorder
  emission with cycle detection, call rewriting, validator allowlist.
- `tests/test_compiler_library_inline.py` — 11 net new tests (31 total).
- `.oo/plans/pyne-library-internal-calls-2026-11-15.md` (this file),
  `.proof.py`, `.failing-before.txt`.
