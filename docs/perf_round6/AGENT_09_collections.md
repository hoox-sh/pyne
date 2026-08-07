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

# AGENT 09 — Collections / UDT / matrix + object-mode compile

**Date:** 2026-07-31  
**BASE_SHA:** 32697c97f7e56de817325356e4dbd692809ecbe8  
**Role:** Correctness (arrays, map, matrix, UDT sort, compile object-mode parity)

## 1. Scope & files

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/arrays.py` | `array.fill` range `[from,to)`; insert OOB/type errors; abs non-numeric; richer `_expect_list` type messages |
| `src/pynescript/ast/evaluator/builtins/map_evaluator.py` | type-mismatch messages; accept plain `dict` map handles |
| `src/pynescript/ast/evaluator/builtins/matrix_evaluator.py` | type-mismatch messages; list-of-lists share wrap |
| `src/pynescript/compiler/compiler.py` | `map.new` before UDT/`{}` path; `map.keys`/`values` as sequences; `array_sort`/`sort_indices`/`fill` emit; `safe_list_insert` |
| `src/pynescript/compiler/numba_builtins.py` | `array_sort`, `array_fill`, `array_sort_indices(sort_field)`, `_udt_sort_key`, safer insert |
| `tests/test_collections.py` | `TestArrayEdgeCorrectness` |
| `tests/test_compiler_objects.py` | `TestCollectionObjectModeParity` (+ soft assert on unary-na smoke) |

## 2. Bugs found

| Severity | Bug | Notes |
| --- | --- | --- |
| **P0 wrong** | Compile `array.sort(id, order, sort_field)` ignored positional 3rd arg; UDT order wrong | emit only read kwargs; aliased `sort_field`→`order` |
| **P0 wrong** | Compile `array.sort_indices` had no `sort_field` | R5 residual |
| **P0 wrong** | Compile `array.fill(id,v,from,to)` filled entire array | range args dropped |
| **P0 wrong** | Compile `map.keys`/`map.values` → `safe_float(list(...))` into float series | size always 0 / na |
| **P1 wrong** | `var m = map.new` stored as `m_arr` UDT series | bare `{}` hit object-handle path before map detection |
| **P1 gap** | Interpret `array.fill` rejected 4-arg range form | advertised `_KWARG_ORDER` only |
| **P2 UX** | Type mismatches said “takes array…” without actual type | push/map/matrix/abs |
| **P2 edge** | `array.insert` negative index message weak; compile used raw `.insert` | now `safe_list_insert` |

## 3. Changes (what/why)

1. **Interpret `array.fill` range** — half-open `[index_from, index_to)`, clamp OOB, ternary `from` → to end.
2. **Type errors** — `_expect_list` / map / matrix report `(got T, expected …)`; `array.abs` rejects non-numeric cells.
3. **Compiler map.new** — detect *before* `{}` UDT-handle classification → scalar `map_vars`.
4. **Compiler sequences** — `map.keys` / `map.values` are sequence-producing (no float64 store).
5. **Object-mode helpers** — `array_sort` / `array_fill` / `array_sort_indices(..., sort_field)` with UDT dict key (skip `__type__`), na-last.
6. **Insert** — compile uses `safe_list_insert`; interpret rejects negative index with size context.

## 4. Benchmarks

N/A (correctness agent). Micro cost only on sort/fill paths.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_collections.py tests/test_map_collections.py \
  tests/test_matrix_collections.py tests/test_matrix_v6_surface.py \
  tests/test_udt_instantiation.py tests/test_udt_methods.py tests/test_udt_types.py \
  tests/test_compiler_objects.py -q --tb=line
# 271 passed

# Related numba suite (1 pre-existing IR-cache identity flake, unrelated):
# tests/test_compiler_numba.py — 1 failed (cache share), rest green
```

New cases: fill range, insert edges, type messages, map dict handle, compile sort_field / fill range / map keys+values / map scalar.

## 6. Residual risks

- Matrix list-of-lists wrap recalculates dims per call; fine for get/set, edge-case if bare flat list mis-detected (guarded by `isinstance(row0, list)`).
- `map.copy` still lands via object-handle `dict(...)` path (not `map_vars`); put/get/keys OK for common scripts.
- Field-index-only binary `array.sort(id, 1)` still ambiguous with `order.ascending=1` (prefer 3-arg / kw).
- Intentional hard OOB on `matrix.get`/`set` (vs soft `array.set` grow) unchanged.

## 7. Out of scope

- Strategy broker, TA kernels, LSP, grammar/generated ANTLR  
- Numeric nopython collection kernels  
- AXIS / frontend / pyne-worker dual-host  
- Silent IR-cache identity test in `test_compiler_numba` (Agent 06)
