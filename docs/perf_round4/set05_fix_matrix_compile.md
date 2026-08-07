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

# set05 fix: `name 'matrix' is not defined` (compile path)

## Symptom

Corpus recompile (`corpus_flow_set05_recompile_compile.csv`) failed ~18 scripts with:

```text
Compiled Runtime Error: name 'matrix' is not defined
```

Examples:

- `set05/indicators/7277_ind_ict_liquidity_void_fill_scanner.pine`
- `set05/indicators/7285_ind_ict_fair_value_gap_fvg_scanner.pine`
- ICT screeners `8122`/`8123`/`8132`/`8133`, market-profile screener `8124`

## Root cause

Scripts name the collection handle **`matrix`**, shadowing the builtin namespace:

```pine
var matrix = matrix.new<string>(0, 6, na)
mtxFun(...) =>
    matrix.add_row(matrix, 0, array.from(...))
```

Compile object-mode emits UDFs as **module-level** functions (no closure over
`execute_script_compiled` locals). Outer scalars are plumbed as **free-scalar
parameters**.

Two bugs blocked that for namespace-shadowing names:

1. **`free_scalars` filter** dropped any free name in `_NS` (`matrix`, `array`,
   `map`, …), even when it was a real user scalar in `scalar_vars`.
2. **`visit_Name` order**: bare free-scalar capture ran **before** the `_NS`
   check, so pure namespace tokens could be mis-tracked; user-shadowed names
   that *were* tracked were then stripped by (1).

Emitted UDF body still referenced bare `matrix` (e.g.
`matrix_add_row(matrix, …)`) with **no** `matrix` formal → `NameError` at run.

Interpret path was unaffected (evaluator binds the `matrix` namespace and
locals separately).

## Fix

File: `src/pynescript/compiler/compiler.py`

1. **`visit_FunctionDef` free_scalars set**: keep names that are in
   `scalar_vars` / `map_vars` even if they are also in `_NS` / color / enum
   namespaces.
2. **`visit_Name`**: resolve pure `_NS` tokens (not user scalar/map) **before**
   the bare free-scalar path so namespaces are never free params; user shadows
   still go through the early `scalar_vars | map_vars` free-scalar path.

Namespace calls (`matrix.add_row` → `matrix_add_row`) unchanged; only the
**handle** is passed as a free scalar.

Same plumbing also fixes `var array = array.new_…` used inside UDFs.

## Verification

### Minimal repro (before → after)

```pine
//@version=5
indicator("x")
var matrix = matrix.new<string>(0, 6, na)
mtxFun(symbol, _time, price, signal) =>
    matrix.add_row(matrix, 0, array.from(symbol, _time, price, signal, "x", "1"))
if bar_index == 0
    mtxFun("A", "t", "1", "1")
plot(matrix.rows(matrix), title="rows")
```

| | Result |
| --- | --- |
| **Before** | `NameError: name 'matrix' is not defined` in `mtxFun` |
| **After** | `def mtxFun(..., matrix, …)`; run 50 bars → `rows == 1.0` |

### Sample corpus scripts (Runtime mode=compile, 50 bars)

All previously matrix-NameError scripts complete without that error:

| Script | Result |
| --- | --- |
| 7277 liquidity void fill scanner | OK (dict plots/`__drawings`) |
| 7285 FVG scanner | OK |
| 8122 / 8123 liquidity void screener | OK |
| 8124 market profile screener | OK |
| 8132 / 8133 MSS screener | OK |

### Tests

- New: `TestSet03MatrixArrayApis::test_matrix_var_shadows_namespace_free_scalar_udf`
- New: `TestSet03MatrixArrayApis::test_array_var_shadows_namespace_free_scalar_udf`
- Suite: `pytest tests/test_compiler_numba.py tests/test_compiler_objects.py -q`
  - **142 passed**, 2 failed (pre-existing `TestSet03MatrixArrayApis`
    sort_indices / remove_row size asserts — unrelated to this fix)

## Files changed

| File | Change |
| --- | --- |
| `src/pynescript/compiler/compiler.py` | free-scalar `_NS` keep + `visit_Name` order |
| `tests/test_compiler_numba.py` | two focused shadow-namespace UDF tests |
| `docs/perf_round4/set05_fix_matrix_compile.md` | this report |

## Non-goals / left alone

- Interpret evaluator path
- Grammar / generated ANTLR
- Broader matrix API surface (already stubbed via `numba_builtins.matrix_*`)
- Pre-existing set03 array/matrix API assertion failures
