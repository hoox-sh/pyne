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

# AST evaluator dispatch / series materialization (round 2)

**Date:** 2026-07-28  
**Scope:** Interpret-mode non-TA cost — visitor dispatch, operator maps, name lookup, scalar unwrap  
**Constraint:** zero correctness loss; no whole-script vectorization; no `na`→0  
**Owned files:** `visitor.py`, `evaluator/base.py` (no changes needed), `expressions.py`, `names.py`, `statements.py` (unwrap only)

## Summary

Hot-path micro-optimizations for bar-mode expression evaluation. Same-session microbench shows **~2.0–2.8×** on pure AST expression walks and **~6–7×** on bare float binary ops. Runtime minimal script (2000 bars) lands ~73 ms median (vs ~97 ms in the prior evaluate report on a similar machine/scripts). **261** tests pass (`test_evaluator` + `test_ta_incremental`).

## Profile (before)

cProfile on mixed + binop + names expression walks (30k each):

| Symbol | share |
|---|---|
| `NodeVisitor.visit` (string-keyed cache) | ~20% tottime |
| `isinstance` (BinOp op chain + operand checks) | ~19% |
| `_elementwise_binary` | ~18% |
| `visit_BinOp` | ~15% |
| `_as_scalar_operand` | ~9% |
| `visit_Name` | ~4% |

`visit_Compare` paid a full `visit(op_node)` per comparison just to return a module-level function.

## Baseline microbench (before)

`NodeLiteralEvaluator`, warm visitor cache, 80k visits, float context:

| Expression | ms (80k) | µs/visit |
|---|---:|---:|
| `a + b * c - d / e` | 602 | 7.53 |
| `a < b and b <= c and c > d` | 775 | 9.69 |
| `close + open - high + low + volume` | 603 | 7.54 |
| ternary | 455 | 5.69 |
| mixed | 668 | 8.35 |

Helper (300k calls):

| Op | ms |
|---|---:|
| `_as_scalar_operand(float)` | 160 |
| `_as_scalar_operand(PineSeries)` | 180 |
| `ADD(float, float)` | 511 |
| `ADD(series, float)` | 421 |

## After microbench (same session)

| Expression | ms (80k) | µs/visit | vs before |
|---|---:|---:|---:|
| binop_chain | 218 | 2.73 | **2.76×** |
| compare_chain | 385 | 4.82 | **2.01×** |
| names | 221 | 2.76 | **2.73×** |
| ternary | 199 | 2.49 | **2.29×** |
| mixed | 255 | 3.18 | **2.63×** |
| mixed + PineSeries ctx | 379 | 4.74 | **1.76×** vs prior 665 ms |

| Op | ms (300k) | vs before |
|---|---:|---:|
| `_as_scalar_operand(float)` | 40 | **4.0×** |
| `_as_scalar_operand(PineSeries)` | 91 | **2.0×** |
| `ADD(float, float)` | 74 | **6.9×** |
| `ADD(series, float)` | 169 | **2.5×** |

### Runtime (interpret, 2000 synthetic bars, median of 5, 2 warmup)

| Script | med_ms |
|---|---:|
| minimal (`close+open-high+low`) | **72.7** |
| arith_heavy (mul/div/compare/ternary) | 122.2 |
| ta_sma(14) (reference; TA-owned) | 111.6 |

Prior evaluate-agent minimal was ~97–100 ms on the same class of host (not a controlled A/B; treat as directional).

## Changes

### 1. Type-keyed visitor dispatch — `src/pynescript/ast/visitor.py`

- `_visitor_cache: dict[type, Callable]` instead of class-name strings.
- Avoids per-call `node.__class__.__name__` and string concat on cache miss path.
- Aligns with the unparser’s `_type_visitor_cache` pattern.

### 2. Operator type maps + scalar fast path — `expressions.py`

- Module-level `_BINOP_DISPATCH`, `_UNARYOP_DISPATCH`, `_CMPOP_DISPATCH` keyed by AST op **type**.
- `visit_BinOp` / `visit_UnaryOp` / `visit_BoolOp`: `type(node.op) is …` / dict get — no `isinstance` chains.
- `visit_Compare`: resolve ops via `_CMPOP_DISPATCH` — **no** `visit(Eq/Lt/…)` round-trip.
- `_as_scalar_operand`: identity type checks (`type(x) is float`) + module-level `_SERIES_TYPE_NAMES` frozenset; duck-type via `getattr(..., "current")` only on the rare path.
- `_elementwise_binary`: **zero-allocation** fast path for bare `int`/`float` pairs (dominant bar-mode case after hosts inject scalars). List/NA/series paths unchanged semantically.
- Unary wrapper: same numeric short-circuit.
- `_is_registered_builtin`: single `__dict__` lookup + build-once cache shared with `_call_builtin`.

### 3. Faster name / drawing dispatch — `names.py`

- `visit_Name`: one `ctx[name]` with `KeyError` instead of `in` + `[]` (one hash).
- Drawing methods: `type(value)` → `_DRAWING_METHOD_NS` instead of isinstance loop.

### 4. Series unwrap helper — `statements.py`

- `_unwrap_series_receiver` shares the same identity-type / frozenset pattern as `_as_scalar_operand` (hot multi-dispatch path).

### Not touched (out of ownership / residual)

| Item | Notes |
|---|---|
| `technical_submodules/*` `_as_series` reverse-copy of PineSeries history | Owned by evaluate-TA agent; still caps/copies up to `_SERIES_MAX` per TA call. Note residual from `perf_agent_evaluate.md`. |
| Whole-script vectorization / parallel bars | Forbidden. |
| `na`→0 coercion | Forbidden. |
| `base.py` | No hot path left after visitor/op work. |

## Correctness

- NA propagation: `None` operands still return `None`; comparisons with na still fail the branch (`False`).
- Series lists: element-wise + trailing-edge align preserved.
- Division by zero: still na via `_safe_truediv`.
- Tests:

```text
$ PYTHONPATH=src python -m pytest tests/test_evaluator.py tests/test_ta_incremental.py -q --tb=line
261 passed in 2.63s
```

## Residual opportunities

1. **`_as_series` reverse-copy** in TA core (not this agent) — bar-mode pure-inc builtins could take last scalar only.
2. **Skip `_na_safe_binary` wrapper frame** — dispatch `_elementwise_binary(operator.add, …)` directly from `_BINOP_DISPATCH` values to save one Python call (minor).
3. **BoolOp short-circuit without generator** — manual loop slightly cheaper than `all(...)` / `any(...)` on CPython.
4. **Context local caching** for `close`/`open`/`high`/`low` when Runtime mutates in place (already dict; further wins are small after this round).
5. **Plotting path** — still shows up in full Runtime profiles (plan 2.5).
