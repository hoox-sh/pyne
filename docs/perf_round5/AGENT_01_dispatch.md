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

# Round 5 Agent 01 — Interpret dispatch / call plumbing

**AGENT_ID:** 01  
**ROLE:** Interpret dispatch / call plumbing (PERF + BUGS)  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30  

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/expressions.py` | Call-site cache, bound-handler fast path, general-path split, leaner arg collect |
| `src/pynescript/ast/evaluator/names.py` | Iterative `ast_qualified_name` (unroll depth-2 `ta.x`) |
| `src/pynescript/ast/evaluator/statements.py` | Plain-assign fast path (`mode is None`); extract `_assign_tuple_unpack` |
| `src/pynescript/ast/evaluator/base.py` | Pre-allocate `_call_site_cache`, `_builtin_resolved` |
| `src/pynescript/ast/evaluator/builtins/base.py` | `_call_builtin` resolved-handler cache (tag + handler) |
| `src/pynescript/ast/visitor.py` | Hit-path early return on type-keyed visitor cache |

**Out of scope (not touched):** TA kernel math, plot registry, strategy broker, grammar, Runtime host, series `_as_series`.

## 2. Bugs found

No correctness bugs requiring semantic changes. Hunted:

| Area | Result |
| --- | --- |
| Double `ast_qualified_name` on every qualified call | **Fixed** (site cache + single resolve) |
| Short-circuit `and`/`or` with series/`na` | Reviewed; existing truthiness semantics left intact |
| Method / UDT dispatch | General path unchanged; UDT tests green |
| Kwargs on bound handlers | Bound path falls back to full `_call_builtin` when kwargs present |

## 3. Changes (what / why)

### 3.1 Call-site resolution cache (`id(Call node)`)

AST Call nodes are stable across the bar loop (same `visit(tree)` each bar). Classify once:

- `_SITE_Q` → qualified Attribute builtin (`ta.sma`)
- `_SITE_B` → bare Name builtin (`plot`)
- `_SITE_G` → methods / UDFs / UDT `.new` / recovery

After first invoke, upgrade to:

- `_SITE_QB` → bound `(tag, handler, name)` — direct handler call, no dispatch map
- `_SITE_BB` → bare bound with per-bar user-callable shadow check

Eliminates per-bar: `ast_qualified_name`, `_is_registered_builtin`, `_is_qualified_attribute_builtin_call`, and most `_call_builtin` overhead.

### 3.2 `_call_builtin` resolved cache

`name → (tag, handler)` where tag is constant / list-style / plain `*args`. Avoids `dispatch.get` + `_is_list_style_handler` after first hit.

### 3.3 `ast_qualified_name` iterative

Depth-2 unroll (`ta.sma`); longer paths use a part list. No recursive frames.

### 3.4 Assign hot path

Plain `name = expr` (`mode is None`) skips Var/VarIp/Const isinstance checks every bar.

## 4. Benchmarks

**Machine:** worktree + shared `.venv` Python 3.x  
**Command:** `PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py`  
**Bars:** 2000 interpret  

### 4.1 Official `bench_pipeline` (before → after)

| script | before med_ms | after med_ms | Δ | bars/s after |
| --- | ---: | ---: | ---: | ---: |
| **minimal** | 22.62 | 23.12 | **+2.2%** (within ≤5% reg) | 86 516 |
| **ta_sma** | 74.05 | 54.88 | **−25.9%** | 36 440 |
| **ta_combo** | 371.45 | 284.53 | **−23.4%** | 7 029 |
| **strategy_ish** | 142.27 | 112.17 | **−21.2%** | 17 830 |

Dedicated multi-iter (warmup 4, iters 9, best of 3 medians) was slightly better (ta_combo **273.5** ms, minimal **18.4** ms) under quieter CPU.

### 4.2 cProfile ta_combo interpret (structural)

| metric | before | after |
| --- | ---: | ---: |
| Function calls | ~1.53 M | **~1.19 M** (−22%) |
| Wall (profiled single run) | ~0.99 s | **~0.74 s** |
| `_is_qualified_attribute_builtin_call` | top-20 | **gone** |
| `_dispatch_qualified_attribute_builtin` | top-20 | **gone** |
| `_call_builtin` | top-6 cumtime | **gone from top-20** (bound path) |

Remaining cost: `_as_series` / `_expect_series`, plot path, visitor frame tax (Agents 02 / 04).

## 5. Tests run

```bash
.venv/bin/python -m pytest tests/test_evaluator.py tests/test_ta_incremental.py \
  tests/test_udt_methods.py tests/test_udt_instantiation.py -q --tb=line
# 332 passed
```

## 6. Residual risks / follow-ups

- Site cache keys on `id(node)`; invalid if a host mutates/rebuilds AST mid-run (none do today).
- User shadowing bare builtins still checked every bar on `_SITE_B`/`_SITE_BB` (correctness).
- Kwargs on bound sites re-enter full `_call_builtin` (rare on ta/plot hot path).
- Next residual: Agent 02 (`_as_series`) and Agent 04 (plot) now dominate tottime after this cut.

## 7. Explicit out of scope / did not touch

- TA incremental kernels / `technical_submodules/*` math  
- Plot registry / DrawingRegistry  
- Strategy broker / events  
- Grammar / parser  
- Numba compile path  
- Commit / push  

## Definition of Done

- **≥10–15% on ta_combo interpret:** yes (**−23%** wall)  
- **No >5% regression on minimal:** yes (**+2%** official; improved on multi-iter)  
- **Tests green:** 332 passed  
- **No na→0 / no bar parallelization**  
