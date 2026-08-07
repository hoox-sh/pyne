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

# Set05 recompile — missing names / object-mode stubs (Agent 3/4)

**Date:** 2026-07-29  
**Scope:** `src/pynescript/compiler/{compiler,numba_builtins}.py` + object-mode tests  
**Evidence:** `.cache/corpus_flow_set05_recompile_compile.csv` (60 FAIL / 1503, 96.01% OK)

## Inventory: `name 'X' is not defined`

| Name | Count | Classification | Action |
|------|------:|----------------|--------|
| `matrix` | 18 | Agent 1 ownership (matrix surface) | **Skipped** (do not fight Agent 1) |
| `pivotPoint` | 2 | Codegen: `Type.copy` stolen by `array_copy` → `list(pivotPoint)` | **Fixed** |
| `x_arr` | 1 | Codegen: nested `FunctionDef` clears parent scope | **Fixed** |
| `label` | 1 | Builtin: `label.all` treated as UDT field on bare ns | **Fixed** |
| `barmerge` | 1 | Builtin: `barmerge.lookahead_on` / `gaps_off` | **Fixed** |
| `array_mode` | 1 | Builtin: `array.mode` missing emit + helper | **Fixed** |
| `math_rphi` | 1 | Builtin: `math.rphi` golden-ratio conjugate | **Fixed** |

### Related float64 / handle errors (same root class)

| Error | Scripts (examples) | Action |
|-------|--------------------|--------|
| `'numpy.float64' object does not support item assignment` | `6787_ind_objects`, `7790_ind_objects_3` | UDT ref assign `p2 = p1` no longer `safe_float`s handle |
| `'numpy.float64' object has no attribute 'append'` | `7086_ind_table_array` | `array.new_table` → list handle; `safe_list_append` |
| `'numpy.float64' object has no attribute 'clear'` | `8102_ind_ezalgo_v5` | `safe_list_clear` / `safe_list_pop` on non-lists |

## Root causes → fixes

### 1. `math.rphi` → dead identifier `math_rphi`

Attribute fallthrough turned constants into `math_{attr}`.  
**Emit:** `(2.0 / (1.0 + np.sqrt(5.0)))` (matches evaluator `2/(1+√5)`).

### 2. `barmerge.*` → `barmerge_lookahead_on` / UDT-field on bare `barmerge`

**Emit:** `lookahead_on`/`gaps_on` → `True`; `lookahead_off`/`gaps_off` → `False`.

### 3. `label.all` → `(__u := (label), __u['all'] …)`

Drawing namespaces are not dicts.  
**Emit:** `[__d for __d in __drawings if … kind == 'label']` (same for line/box/table/polyline/linefill).

### 4. `array.mode` → bare `array_mode(...)` NameError

Registered in `_ARRAY_METHODS` + `_emit_array_or_matrix`.  
**Helper:** `array_mode` / `array_standardize` / `array_normalized` in `numba_builtins.py`.

### 5. `pivotPoint` via `Type.copy`

`copy` ∈ `_ARRAY_METHODS` → `array_copy` → `list(pivotPoint)`.  
**Emit:** `Type.copy(inst)` / `inst.copy()` → shallow `dict(inst)`.  
Assign path treats UDT copy / UDT name RHS as object-dtype series (not `safe_float`).

### 6. Nested FunctionDef → outer params as `x_arr`

`visit_FunctionDef` always set `in_function = False` and cleared `local_vars`, so after nested `g` the outer `f` body rewrote params as series free vars.  
**Fix:** full parent-scope save/restore (nested pure restore; top-level still accumulates `series_params`).

### 7. List-returning APIs mis-stored as float64

`array.sort_indices`, `matrix.remove_row/col`, etc. landed in `*_arr` + `safe_float(list)`.  
**Fix:** extend `_is_array_or_matrix_handle` / `_is_sequence_producing_call`.

### 8. Defensive list mutators

`safe_list_append` / `clear` / `pop` / `insert` — no-op / na when the “array” is a scalar (e.g. `request.security_lower_tf` stub returning series value).

### 9. Dual `array.fill` for matrix

If id is list-of-lists, fill cells; else fill flat slots (`m.fill(label.new(...))`).

## Docs-invalid / intentional soft paths

| Script | Note |
|--------|------|
| `6903_ind_invalid_nested_definition_demo.pine` | **Invalid Pine** (nested function defs). Still fixed codegen so nested demos do not NameError; nested `g` is hoisted as a module-level UDF. |
| `matrix` × 18 ICT scanners | Left to Agent 1 matrix work. |
| `NoneType` not callable × 13, nopython frontend × 6, None arithmetic × 7 | Out of this agent’s missing-name scope (separate stubs / na-coercion). |

## Verification

```text
pytest tests/test_compiler_objects.py tests/test_compiler_numba.py  → 142 passed
```

Target set05 scripts (compile + run, n=15):

| Script | Before | After |
|--------|--------|-------|
| `6788_ind_objects_2` / `7791` | `name 'pivotPoint'` | OK (1000 / 2000) |
| `6787_ind_objects` / `7790` | float64 item assignment | OK (shared 2000) |
| `6903_ind_invalid_nested_definition_demo` | `name 'x_arr'` | OK |
| `7690_ind_object_matrix_fill_demo` | `name 'label'` | OK |
| `8185_ind_mtf_candlesticks` | `name 'barmerge'` | OK |
| `8290_ind_test_024_newfu` | `name 'array_mode'` | OK |
| `8314_ind_fmin` | `name 'math_rphi'` | OK (~π minimizer) |
| `7086_ind_table_array` | float64.append | OK |
| `8102_ind_ezalgo_v5` | float64.clear | OK |

## Files touched

| File | Change |
|------|--------|
| `src/pynescript/compiler/compiler.py` | attrs (math.rphi, barmerge, *.all); UDT copy; nested FunctionDef restore; UDT ref assign; array.mode/new_table; sequence-handle classification; safe list mutators; dual fill |
| `src/pynescript/compiler/numba_builtins.py` | `safe_list_*`, `array_mode`, `array_standardize`, `array_normalized` |
| `tests/test_compiler_objects.py` | `TestSet05MissingNames` |
| `docs/perf_round4/set05_fix_missing_names.md` | this report |

## Remaining (not fixed here)

- **`matrix` NameError × 18** — Agent 1  
- **`'NoneType' object is not callable` × 13** — likely unresolved method/import stubs  
- **nopython frontend / non-precise type** — force object-mode on those scripts  
- **None arithmetic / compare** — na-safe binops (partial elsewhere)  
- **list index OOB / axis bounds** — intentional runtime of bad corpus scripts  
- **invalid syntax (loop keywords demo)** — separate emit bug  

**Estimated impact if only this agent’s names:** 2+1+1+1+1+1 = **7 direct NameError scripts** + **4 related float64 handle scripts** ≈ **11 / 60 FAIL** (~18% of remaining fails; matrix alone is 30%).
