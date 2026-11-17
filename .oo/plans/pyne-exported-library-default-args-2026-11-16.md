# Exported library function defaults on direct and cross-library calls

**Date:** 2026-11-16
**Card:** `pyne-exported-library-function-w-e2d1bfbd`
**Status:** Working — first slice, no commit/push

## Why

A library export with a declared default:

```pine
library("Lib")
export helper(float a, float k = 2.0) =>
    a * k
```

called directly as `lib.helper(close)` compiled to `__lib_lib_helper(close)`.
The emitted Python def is `def __lib_lib_helper(a, k)` — defaults are
deliberately omitted because trailing series/context plumbing params would
make a mid-signature default invalid Python. The direct/cross-library call path
did not bind the default, so the call raised
`TypeError: __lib_lib_helper() missing 1 required positional argument: 'k'`.
The same-library internal-call path already filled defaults via
`_emit_user_func_call`; direct and cross-library A→B calls did not.

## Change

`CompileVisitor.visit_Call` library branch (`compiler.py`, `import_lib_method`
direct emit): when a mapped export is called without kwargs, bind missing
trailing parameters from `func_param_defaults[mapped]` before emitting the
call. Stop at the first parameter without a default, preserving the existing
short-call TypeError for genuinely missing required args. Signature defaults
are not emitted.

This covers both:
- direct consumer → library export (`lib.helper(close)`), and
- cross-library A→B call (`b.twice(close)` where B's `twice` calls A's
  `scale(x)` with `k=2.0`).

## Acceptance criteria

1. `lib.helper(close)` with `helper(a, k=2.0)` compiles without error and
   returns the same series as interpret: `[201.0, 203.0, 205.0, 207.0]`.
2. Cross-library `b.twice(close)` where B calls A's `scale(x)` with
   `scale(a, k=2.0)` compiles without error and matches interpret on the same
   series.
3. Existing same-library internal helper default coverage
   (`test_library_internal_helper_defaults_and_locals`) stays green.
4. Library/compiler targeted suite green; `./scripts/verify.sh` 5/5.
5. Failing-before captured before the compiler change.

## Failing before

`.oo/plans/pyne-exported-library-default-args-2026-11-16.failing-before.txt`
— 2 failed: direct `TypeError: __lib_lib_helper() missing 1 required
positional argument: 'k'`; cross-library
`TypeError: __lib___xlib_1_scale() missing 1 required positional argument:
'k'`.

## Results

- New tests: `test_exported_library_default_arg_direct_call`,
  `test_exported_library_default_arg_cross_library_call` — **2 passed**.
- Library suite (`test_compiler_library_inline`, `..._fail_closed`,
  `test_library_export_import`, `test_library_export_method`) — **64 passed**.
- Compiler/library targeted suite (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **501 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped**.

## Proof

Card `pyne-exported-library-function-w-e2d1bfbd` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named direct + cross tests | `2d810c49-6eb8-47e1-aecc-ee37419a9515` | `test_exported_library_default_arg_direct_call` + `..._cross_library_call` PASSED, 2 passed |
| targeted compiler/library suite | `0e93f4af-c3d1-4c33-aaf3-eb95811d81ff` | 501 passed |
| `./scripts/verify.sh` | `3a1d32e5-a4f8-4952-8de5-d18f633541aa` | all passed, 5 passed / 0 skipped |

SHA-256: compiler `79890028db298b0b78c5a60067f5d0e35e2f5120d74b7ca76459b7659f86a92a`,
tests `9f98a29cc12c426de26036227a17cd87cc351eb928da3d5db2e4308c4264d241`,
patch `ee4e5eefea784b4a8ad3412ea89f4a1b0aac55d20ea6abc25a51f8e08b8fb050`.
Verify transcript: `.oo/proof/verify-exported-library-defaults-2026-11-16.txt`.

## Files

- `src/pynescript/compiler/compiler.py` — call-site default binding for mapped
  library calls.
- `tests/test_compiler_library_inline.py` — direct and cross-library default
  regressions.
- `.oo/plans/pyne-exported-library-default-args-2026-11-16.{md,failing-before.txt}`.

## Residual

- Keyword arguments for inlined library calls remain fail-closed
  (`use mode=interpret or auto`), unchanged by this slice.
- Non-literal default expressions inherit the same call-site binding behavior
  as same-library internal calls; not separately audited here.
- No commit/push for this slice.
