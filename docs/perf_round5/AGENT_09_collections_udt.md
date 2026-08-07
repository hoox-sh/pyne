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

# AGENT 09 — Collections / UDT / matrix / map surface

**Date:** 2026-07-30  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Role:** Correctness + bugs (arrays, matrix, map, UDT sort/collection edges)

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/arrays.py` | `sort_field` for `array.sort` / `array.sort_indices`; `_KWARG_ORDER`; UDT field key helper |
| `src/pynescript/ast/evaluator/builtins/matrix.py` | `sort`/`sort_indices` UDT `sort_field` + na-last; fix descending (`order==1` was wrongly desc); `add_row`/`add_col` insert index + empty 0×0 adopt dims |
| `src/pynescript/ast/evaluator/builtins/matrix_evaluator.py` | wire sort_field; empty `matrix.new()`; insert-index `add_row`/`add_col`; kwargs orders |
| `src/pynescript/ast/evaluator/base.py` | `order.ascending=1`, `order.descending=-1` constants |
| `tests/test_matrix_v6_surface.py` | regression suite for order/sort_field/empty new/insert |
| `tests/test_matrix_collections.py` | unit tests for insert + empty add_row |

**Not touched:** compiler/numba emit (compile path already had better `matrix_add_row` insert), strategy, TA, LSP, grammar.

## 2. Bugs found

| Severity | Bug | Repro |
| --- | --- | --- |
| **P0 crash** | `matrix.sort` / `matrix.sort_indices` on UDT cells: `TypeError: '<' not supported between ObjectInstance` | `matrix.sort(m, 0, order.ascending, "v")` with `matrix.new<Item>` |
| **P0 wrong** | `sort_field` ignored on matrix (comment said “ignored”); same gap on `array.sort` / `array.sort_indices` (string field / int field index never keyed) | `array.sort(a, order.ascending, "id")` sorted by `repr` not `id` |
| **P1 wrong** | `matrix.add_row(id, row, array)` always **appended** (row index discarded) | insert at 0 left old row0 in place |
| **P1 wrong** | `matrix.new<T>()` with zero args rejected (`requires at least rows and cols`) | empty ICT-style matrices |
| **P1 wrong** | `order.ascending` / `order.descending` missing → always `None` → descending sorts no-ops | `matrix.sort(m, 0, order.descending)` stayed ascending |
| **P2 wrong** | `Matrix.sort` treated `order == 1` as descending (TV: ascending=1, descending=-1) | numeric order enum once registered |

Themes aligned with Round 4 set05 (OOB soft recovery already present on interpret `array.set`; matrix insert/empty + UDT sort were residual surface holes).

## 3. Changes (what/why)

1. **UDT collection sort** — extract key via field name or field index (`get_field` / `udt.fields` order); partition `na` last like array path; string fallback if keys incomparable.
2. **array sort args** — parse `(id)`, `(id, order)`, `(id, order, sort_field)`; kwargs via `_KWARG_ORDER = ["id","order","sort_field"]`.
3. **matrix row/col insert** — `add_row(data, index=)` / `add_col(data, index=)`; 0×0 adopts dimensions from first payload (matches compile `numba_builtins.matrix_add_row`).
4. **`matrix.new()`** — zero-arg → `Matrix(0, 0)`.
5. **`order.*` constants** — seed in `_MATH`/constant table like `size.*` / `format.*`.

## 4. Benchmarks

N/A (correctness agent; no perf claims). Micro overhead of UDT key extraction only on sort paths.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_collections.py tests/test_map_collections.py \
  tests/test_matrix_collections.py tests/test_matrix_v6_surface.py \
  tests/test_udt_instantiation.py tests/test_udt_methods.py tests/test_udt_types.py \
  -q --tb=line
# 232 passed
```

Baseline before fixes: **224 passed** (suite green; bugs were untested surface).  
After: **232 passed** (+8 regression cases).

## 6. Residual risks / follow-ups

- **array.fill** advertises `index_from`/`index_to` in `_KWARG_ORDER` but still requires exactly 2 args (range fill not implemented).
- **Compile-path** `array_sort_indices` helper still has no `sort_field` (object-mode); interpret is fixed.
- **matrix.get/set OOB** still hard-errors (unlike soft-grow `array.set`); intentional strictness unless product wants soft-na.
- **Field index `1` alone** as binary `array.sort(id, 1)` is ambiguous with `order.ascending=1`; prefer 3-arg or `sort_field=` kw.
- Agent 10 may still want broader v6 constant inventory; `order.*` only filled here for sort.

## 7. Out of scope / did not touch

- Strategy broker, TA incremental kernels, LSP, grammar/generated ANTLR  
- Compiler emit for sort_field (Agent 06 territory if needed)  
- Strict TV runtime.error on intentional array OOB demos (soft-grow retained)  
- AXIS / frontend  
