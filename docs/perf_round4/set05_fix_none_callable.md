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

# set05 fix: `'NoneType' object is not callable` (compile path)

**Date:** 2026-07-29  
**Evidence:** `.cache/corpus_flow_set05_recompile_compile.csv` — 13 `RUN_FAIL` with  
`Compiled Runtime Error: 'NoneType' object is not callable`

## Root cause

**Python local-name shadowing of a user-defined function (UDF) after multi-value unpack.**

Corpus scripts (Total Recall / Nebula / Insane Oscillator family) define a helper and immediately unpack into the **same** name:

```pine
pvsraVolume(overrideSymbolX, pvsraSymbolX, tickerIdX) =>
    request.security(...)
[pvsraVolume, pvsraHigh, pvsraLow, pvsraClose, pvsraOpen] = pvsraVolume(false, "", syminfo.tickerid)
```

The compiler already handled the **simple** assign case (`sar = sar(...)` → store as `sar__loc`) in `visit_Assign`, but **`_visit_tuple_assign` did not**:

1. Target `pvsraVolume` was registered as a scalar local and initialized as `pvsraVolume = None`.
2. The bar-loop call still emitted `__tup = pvsraVolume(...)`.
3. In Python, assignment to a name makes it **local for the whole function**, so the call resolved to the local `None` → `TypeError: 'NoneType' object is not callable`.

Not a missing builtin emit or a stub that returned a callable; the UDF **was** correctly defined at module scope, then shadowed by the unpack store.

## Failing files (all same pattern)

| File | Pattern |
| --- | --- |
| `set05/indicators/7307_ind_total_recall.pine` | `[pvsraVolume, ...] = pvsraVolume(...)` |
| `set05/indicators/7397_ind_total_recall_2.pine` | same |
| `set05/indicators/7511_ind_vector_candles_2.pine` | same |
| `set05/indicators/7392_ind_insane_oscillator.pine` | same |
| `set05/indicators/8163_ind_insane_oscillator_2.pine` | same |
| `set05/indicators/8167_ind_insane_oscillator_v2.pine` | same |
| `set05/indicators/7393_ind_nebula.pine` | same |
| `set05/indicators/8157_ind_nebula_v1_5.pine` | same |
| `set05/indicators/8158_ind_nebula_v1_51.pine` | same |
| `set05/indicators/8159_ind_nebula_v1_52.pine` | same |
| `set05/indicators/8164_ind_nebula_v1_8.pine` | same |
| `set05/indicators/8166_ind_nebula_v1_9.pine` | same |
| `set05/indicators/8172_ind_nebula_v2_0.pine` | same |

## Fix

**File:** `src/pynescript/compiler/compiler.py` — `_visit_tuple_assign`

Mirror the simple-assign UDF shadow rule:

- When a multi-unpack target name is in `self.user_funcs`, map it to `{safe}__loc` via `ident_map`.
- Stores (numeric / sequence / empty-stub) write to the shadow local.
- UDF **calls** still use the bare function name (`_emit_user_func_call` / `def pvsraVolume(...)`).
- Subsequent reads go through `visit_Name` → `pvsraVolume__loc` (existing `__loc` path).

No silent math stubs; the real UDF body still runs. Values that would have been lost to `None` now come from the function return (e.g. same-bar `request.security` chart fields).

## Sample recovery

### Before (generated excerpt)

```python
def pvsraVolume(...):
    return (vol_arr[__bar_idx], high_arr[__bar_idx], ...)

def execute_script_compiled(...):
    pvsraVolume = None   # local shadows the def
    for __bar_idx in range(n_bars):
        __tup = pvsraVolume(...)  # TypeError: NoneType not callable
        pvsraVolume = (__tup[0] if ...)
```

### After

```python
def pvsraVolume(...):
    return (vol_arr[__bar_idx], high_arr[__bar_idx], ...)

def execute_script_compiled(...):
    pvsraVolume__loc = None
    for __bar_idx in range(n_bars):
        __tup = pvsraVolume(...)           # module-level UDF
        pvsraVolume__loc = (__tup[0] if ...)
```

### Runtime check

```text
compile_script: 13 ok, 0 fail  (all listed set05 scripts)
Runtime 7307_ind_total_recall.pine: error=None mode=compile count=80
Runtime 7392_ind_insane_oscillator.pine: error=None mode=compile count=80
```

## Tests

`tests/test_compiler_numba.py` · `TestSet03RuntimeTypeFixes`:

- **Existing:** `test_udf_shadow_name_not_compared_as_function` — simple `sar = sar(...)`.
- **New:** `test_tuple_unpack_udf_shadow_not_callable_none` — multi-unpack `[pvsraVolume, ...] = pvsraVolume(...)`:
  - asserts `pvsraVolume__loc` store + bare call
  - asserts no `pvsraVolume = None` local init
  - runs compiled script; plots volume/close from UDF multi-return

```bash
PYTHONPATH=src:. python -m pytest \
  tests/test_compiler_numba.py::TestSet03RuntimeTypeFixes::test_tuple_unpack_udf_shadow_not_callable_none \
  tests/test_compiler_numba.py::TestSet03RuntimeTypeFixes::test_udf_shadow_name_not_compared_as_function -v
# 2 passed
```

Full `tests/test_compiler_numba.py`: **134 passed**; 2 failures in `TestSet03MatrixArrayApis` (`array.sort_indices` / matrix mutate) are **pre-existing** and unrelated to UDF shadow (list handles still coerced to float series).

## Notes / non-goals

- Did **not** change import-library stubs (`trLib.calcPvsra` → `None` multi-unpack still yields NaN/None fields via existing guards).
- Did **not** add new builtins; fix is pure name-resolution correctness.
- Other set05 `RUN_FAIL` buckets (`matrix` undefined, numba nopython, etc.) are out of scope for this ticket.
