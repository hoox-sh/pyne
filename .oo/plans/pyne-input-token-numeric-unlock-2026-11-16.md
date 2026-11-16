# `input.*` type-token numeric unlock — first slice

**Date:** 2026-11-16
**Card:** `pyne-input-type-token-numeric-un-1638a3b4`
**Status:** Working — first slice, no commit/push

## Why / scope

Bare `input(..., type=input.integer/float/bool/source)` tokens fell through
`visit_Attribute` to the generic UDT/object-field path, which set
`object_mode=True`. The function forms `input.int` / `input.float` / `input.bool`
were already numeric (existing regression), so the actual failing inventory
shape is the bare token form.

**First slice:** treat numeric/boolean/source input tokens as compile-time
metadata: `input.integer` / `input.int` / `input.float` / `input.bool` /
`input.source` / `input.price` / `input.time` return a token string without
forcing object mode. `input()` then folds the constant defval as before.

**Kept object:** `input.string` / `input.text_area` / `input.color` /
`input.symbol` / `input.timeframe` / `input.session`, and unknown/dynamic
tokens. In particular, `input.color` still forces object mode because the
color value flows through the compiler's string/color scalar assignment path,
not only the token visit; metadata-only plot-color folding is a separate
scalar-metadata slice.

## Change

- `compiler.py` `visit_Attribute`: explicit `input.*` token branch. Numeric
  attrs return `repr(attr)` without object mode; all other input attrs set
  object mode and return the token.
- `tests/test_compiler_numba.py`: bare numeric/source token regressions and a
  string/color object-mode boundary test.

## Acceptance criteria

1. A numeric indicator using `input(3, type=input.integer)`,
   `input(2.0, type=input.float)`, and `input(true, type=input.bool)` compiles
   with `object_mode=False`, njit code, and matches interpret.
2. `input(close, type=input.source)` stays numeric and matches the close series.
3. `input.string` and `input.color` remain object mode.
4. Existing `input.int` / `input.float` numeric coverage stays green.
5. Targeted compiler/library suite green; `./scripts/verify.sh` 5/5.

## Failing before

`.oo/plans/pyne-input-token-numeric-unlock-2026-11-16.failing-before.txt` —
pre-fix worktree at `98cc8e70` + the new tests: 2 failed (numeric token emitted
object code; source token `object_mode=True`); the string/color boundary test
passed.

## Results

- New input-token tests — **3 passed**.
- `tests/test_compiler_numba.py` — **213 passed**.
- Compiler/library targeted (`tests/test_compiler*.py`,
  `tests/test_library*.py`) — **512 passed**.
- `./scripts/verify.sh` — **5 passed, 0 skipped** (single final run after the
  input-token change).

## Proof

Card `pyne-input-type-token-numeric-un-1638a3b4` (HQ board), attached from the
workspace root with `OO_SEAT=oo-spec-2`:

| Proof | Id | Assertion |
| --- | --- | --- |
| named input-token tests | `7078ab2f-4b8a-4fd4-844c-4dcd20f9c8c3` | 3 tests PASSED (numeric, source, string/color boundary) |
| named token | `2c971c5f-5bc4-4476-8341-7cecd06eca8a` | `INPUT_TOKEN_OK int=1 float=1 bool=1 source=1 string=object color=object` |
| targeted compiler/library | `b13fea54-f112-4978-a906-c9a0941f9bdd` | 512 passed |
| verify (no re-run) | `ff329f41-ab76-48c5-9ef8-f3a4e087cdfe` | recorded exit 0 |
| verify transcript | `79f94d13-8aa6-40d6-858f-df44f2b65396` | `.oo/proof/verify-input-token-numeric-2026-11-16.txt` |

SHA-256: compiler `8b59b23164a39e95a877c4488cdcef52da9979763942821a1bf8a75f438820c0`,
tests `8e40edc4d30459df2b90b11213be31c36baab55d47c2e67dfa1da242a7c58641`,
patch `b39d8459aefb170298883d3687772c7ab702bd485ea0f8467b4b5fbf64b0a4be`.

## Files

- `src/pynescript/compiler/compiler.py`
- `tests/test_compiler_numba.py`
- `.oo/plans/pyne-input-token-numeric-unlock-2026-11-16.{md,failing-before.txt,proof.py}`

## Residual

- String/color/symbol/timeframe/session input tokens and unknown/dynamic type
  tokens stay object mode. Color metadata-only folding is a separate slice.
- Input defvals remain compile-time constants (existing behavior).
- No commit/push for this slice.
