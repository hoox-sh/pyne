# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# set05: Fix compile-path NoneType arithmetic / comparisons

**Date:** 2026-07-29  
**Agent:** 1/4  
**Scope:** object-mode numeric BinOp / Compare / UnaryOp + ForTo UDF return  
**Evidence:** set05 recompile residual — 6× `Compiled Runtime Error` with
`NoneType` / float operand TypeError on `*`, `-`, `>`.

## Failing corpus (mode=compile, 50 synthetic bars)

| File (set05/indicators/) | Error |
| --- | --- |
| `7349_ind_colorrvi.pine` | `'>' not supported between instances of 'float' and 'NoneType'` |
| `7439_ind_calculator_binom_da_l_m.pine` | `*` `NoneType` * `NoneType` |
| `7463_ind_calculator_negatif_binom_da_l_m.pine` | same |
| `7517_ind_extracting_local_variables_with_tuples_demo.pine` | float `-` `NoneType` |
| `7762_ind_libraries_3.pine` | `NoneType` `*` float |
| `8130_ind_overlay_indicators.pine` | `NoneType` `*` float |

## Root causes

### 1. Bare Python operators on Pine `na` (`None`)

Object-mode bar loops lower Pine `na` to Python `None` (scalar locals from
tuple unpacks, missing TA stubs like `ta.median` / `ta.range`, import aliases,
uninitialized UDF returns). Generated code used bare `+` / `-` / `*` / `/` /
`>` / `<` / unary `-`, which raise `TypeError` when either operand is `None`.

Interpreter already uses `_na_safe_binary` / `_na_safe_unary` in
`ast/evaluator/expressions.py`. Compile path had no equivalent.

### 2. Binom calculators: ForTo UDF drop of last body expr

```pine
f_factorial(n) =>
    r = 1
    for i = 1 to n
        r := n == 0 ? 1 : r * i
        r
```

`visit_ForTo` appends `i += __step_i` after the body. Function return detection
only looked at the **last** physical line of the for-block, so it saw the
auto-increment and never emitted `return r`. `f_factorial` always returned
`None` → `None * None` in `f_combination`.

### 3. Literal `None` left of arithmetic

Stubs that lower to the constant `None` (e.g. unimplemented `ta.range` →
`(None * 0.25)`) were treated as “numeric literals” by the first wrap heuristic
and skipped — still crashed.

## Fix

### `numba_builtins.na_num`

Fast object-mode coercion:

- `None` → `np.nan`
- `float` / `int` identity
- `bool` → 0.0 / 1.0
- else → `safe_float`

Never used under `@numba.njit` (only when `CompilerVisitor.object_mode`).

### `CompilerVisitor`

| Hook | Behavior |
| --- | --- |
| `_na_wrap_num(expr)` | If `object_mode`: wrap with `na_num(...)`; `None` → `np.nan`; skip pure numeric literals / already-wrapped |
| `visit_BinOp` | Wrap both operands before `+ - * / %` |
| `visit_Compare` | Wrap numeric relational compares; **skip** stringy / color `==` / `!=` so `matrix.get(...) == "A"` stays correct |
| `visit_UnaryOp` | Wrap for `UAdd` / `USub` |
| `math_pow` / `pow` | Wrap base & exponent |
| ForTo UDF return | When scanning for-block tail, **skip** `i += __step_i` so bare `r` still becomes `return r` |

Numeric njit scripts (`plot(ta.sma(...))`) stay bare — no `na_num` in the hot
loop, no correctness/perf loss on non-na float64 paths.

## Recovery

**6 / 6** scripts OK under `Runtime.run(..., mode="compile")` with 50 bars.

| Script | Notes after fix |
| --- | --- |
| ColorRVI | `na_num(rvi) > na_num(rviMA)` when MA scalar is None |
| Binom ×2 | factorial returns `r`; binomial probs finite |
| Tuple locals demo | `source - q3` with missing percentile → nan plots, no crash |
| Libraries demo | import / missing TA → nan channels |
| Overlay indicators | missing `std` scalar → nan band math |

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/test_compiler_numba.py \
  tests/test_compiler_objects.py -q
# 162 passed
```

New / extended:

| Test | File |
| --- | --- |
| `TestNaSafeArithmetic::*` (`na_num`, compare None scalar, mult None, sub None, numeric SMA unaffected) | `tests/test_compiler_numba.py` |
| `test_for_to_udf_returns_last_body_expr_factorial` | `tests/test_compiler_numba.py` |
| `TestObjectModeNaArithmetic::*` (unary neg, add/mul chain) | `tests/test_compiler_objects.py` |

## Files changed

- `src/pynescript/compiler/numba_builtins.py` — `na_num`
- `src/pynescript/compiler/compiler.py` — na-wrap BinOp/Compare/Unary/pow; ForTo return
- `tests/test_compiler_numba.py` — unit tests
- `tests/test_compiler_objects.py` — unit tests
- `docs/perf_round4/set05_fix_none_arith.md` — this report

## Correctness notes

- Non-na float/int path: `na_num` is identity → same IEEE results as bare ops.
- `nan` ops: same as before (`nan * x` → `nan`, `x > nan` → False).
- String equality intentionally **not** wrapped (would turn labels into nan).
- Residual: scripts that need real `ta.median` / `ta.percentile_*` / library
  imports still plot nan where stubs return na — they no longer crash.
