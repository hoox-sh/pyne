# `runtime.error` numeric support — first slice

**Date:** 2026-11-16
**Card:** `pyne-runtime-error-numeric-suppo-22cc06b1`
**Status:** Working — first slice, no commit/push

## Why / scope

`runtime.error(...)` emitted `pine_raise(msg)` and unconditionally set
`object_mode=True`, even though the common corpus shape is a compile-time
string literal inside a guard (`if len <= 2: runtime.error("Length must be ...")`).
Numba supports raising with a Unicode argument, so a literal message can use an
njit-safe helper without forcing object mode.

**First slice:** allow `runtime.error` with **one compile-time string literal**
(or no args, default message) in numeric mode. Emit `pine_raise_njit(<literal>)`,
which is an njit function raising `RuntimeError(str(msg))`. Unreachable branches
are a no-op; reachable branches raise and map to `ERROR_KIND_RUNTIME` like
interpret.

**Kept object:** dynamic/string-heavy message construction, multi-arg messages
(the compiler only folds the first arg today), and `runtime.error_code`. These
still use the plain-Python `pine_raise` + object mode.

## Change

- `numba_builtins.py`: add `pine_raise_njit(msg)` (`@numba.njit(cache=False)`)
  raising `RuntimeError(str(msg))`; plain `pine_raise` unchanged for object mode.
- `compiler.py` `runtime_error` branch: literal single-arg messages and no-arg
  `runtime.error()` return `pine_raise_njit(...)` without object mode. The
  no-arg default is the **empty string** (`repr("")`), matching interpret's
  empty-message `RuntimeError`. Dynamic/multi-arg and `runtime_error_code`
  keep `object_mode=True` + `pine_raise(...)`.
- `engine.py`: disk IR cache version 57 (runtime.error codegen changed).
- `tests/test_compiler_numba.py`: literal unreachable, literal reachable
  (interpret parity), no-arg parity, and dynamic-message boundary tests.

## Acceptance criteria

1. A numeric script with a literal `runtime.error` in an unreachable branch
   compiles with `object_mode=False`, njit code, and no error; plotted series
   match.
2. A reachable literal `runtime.error` raises on both hosts with
   `error_kind="runtime"` and the literal message; compile stays numeric.
3. No-arg `runtime.error()` raises an empty-message `RuntimeError` on both
   hosts (`error_kind="runtime"`, message ends with `RuntimeError`, no
   `runtime.error` text); compile stays numeric.
4. Dynamic/string-heavy message construction remains object mode.
5. Existing error-handling and interpret behavior stay green.
6. Targeted compiler/library suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-runtime-error-numeric-2026-11-16.failing-before.txt` — pre-fix
worktree at `885dc745` + new tests: 2 failed (both literal cases
`object_mode=True`); the dynamic boundary test passed.

`.oo/plans/pyne-runtime-error-numeric-2026-11-16.failing-before-noarg.txt` —
no-arg parity failed before the empty-string default: compile raised
`RuntimeError("runtime.error")` → `Compiled Runtime Error: RuntimeError:
runtime.error`; interpret raises an empty-message `RuntimeError`.

## Results

- New runtime.error tests — **4 passed**.
- `tests/test_compiler_numba.py` — **217 passed**.
- Compiler/library targeted (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **516 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped** (single final run after the
  no-arg fix). Transcript SHA-256:
  `602ed2bffa69c227980bf1c2adb96a8377929a2ce5c6f36606a0d92506dbc1ed`.

## Proof

Card `pyne-runtime-error-numeric-suppo-22cc06b1` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named runtime.error tests | `e0ce0cde-47df-4f0c-961c-5f63de5b9fa6` | 4 tests PASSED (literal numeric, reachable parity, no-arg parity, dynamic object) |
| named token | `58ed39ac-a094-4b75-aa93-84e9cd7204ac` | `RUNTIME_ERROR_OK literal_numeric=1 reachable=runtime noarg=runtime dynamic=object` |
| targeted compiler/library | `360dd39b-019d-4919-b781-61f103b47fbf` | 516 passed |
| verify (no re-run) | `c385afec-7c2d-42af-9987-c453a43d7866` | recorded exit 0 |
| verify transcript | `881d014b-b561-45e9-9204-22e12dad3e76` | `.oo/proof/verify-runtime-error-numeric-2026-11-16.txt` |

SHA-256: compiler `a7f48ab22dd5faf442663bf47e98b1b627a8675b1736c411bd025c990fca571c`,
builtins `3ba857a254b219d1019911f26764399b10e98419be7c883abe4b20e6d9917d12`,
engine `45b3e165b6d28c52f6336451ce1dc90e395d7fa2d6b65bd99a80a8eac56f50bb`,
tests `d27aa325721fc56a7e2a65c7fdc0959ae41fc0a2c76d728aebd10d28808eed03`,
patch `3e420d9fcf01cf0bb93045faf54541ffef48df7216745499d641e373e08a90e0`.

## Files

- `src/pynescript/compiler/compiler.py`
- `src/pynescript/compiler/numba_builtins.py`
- `src/pynescript/compiler/engine.py`
- `tests/test_compiler_numba.py`
- `.oo/plans/pyne-runtime-error-numeric-2026-11-16.{md,failing-before.txt,failing-before-noarg.txt,proof.py}`

## Residual

- Dynamic/string-heavy messages, multi-arg messages, and `runtime.error_code`
  remain object mode. The multi-arg object-mode first-arg-only forwarding is
  already carded separately (Todo); not fixed here.
- Host error formatting differs (`Runtime Error at bar …` vs
  `Compiled Runtime Error`) but kind and message match; no-arg both end with
  `RuntimeError`.
- No commit/push for this slice.
