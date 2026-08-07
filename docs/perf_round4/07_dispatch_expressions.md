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

# Visitor dispatch + expression evaluator (round 4 / agent 7)

**Date:** 2026-07-29  
**Scope:** Remaining Python overhead on expression/statement visitor hot path  
**Constraint:** zero correctness loss; preserve strict bool / short-circuit / na semantics  
**Prior:** type-keyed visitor, op maps, scalar fast path ~2–7× — `docs/perf_agent_dispatch_round2.md`

**Owned files:**

| File | Role |
|---|---|
| `src/pynescript/ast/evaluator/expressions.py` | BinOp / BoolOp / Unary / Compare / Conditional |
| `src/pynescript/ast/evaluator/names.py` | Name + Subscript |
| `src/pynescript/ast/evaluator/statements.py` | AugAssign uses same raw binop path |
| `src/pynescript/ast/evaluator/literals.py` | Constant kind short-circuit |
| `src/pynescript/ast/visitor.py` | `type(node)` dispatch polish |
| `src/pynescript/ast/evaluator/base.py` | unchanged (no residual hot path) |

## Summary

Round-2 left residual costs: `_na_safe_binary` wrapper frame, BoolOp generator/`all`/`any`, Compare zip, Subscript `isinstance`/`abs`, and repeated `self.visit` attribute loads.

This round:

1. **Inlines bare int/float arithmetic and comparisons** in `visit_BinOp` / `visit_Compare` / `visit_UnaryOp` (no wrapper, no `_elementwise_binary` on the dominant bar-mode path).
2. **Dispatches residual series/list/na paths** via `_BINOP_RAW` / `_CMPOP_RAW` → `_elementwise_binary(op, a, b)` (one less Python frame).
3. **Manual BoolOp short-circuit** (no generator, no `all`/`any`).
4. **Faster series subscript** (`type is list` + `slice_ >= len` bounds; no `abs`).
5. **Local `visit = self.visit`** on hot methods; Constant `kind is None` fast return.

Same-session microbench (80k visits, median of 5) shows **~1.1–2.7×** vs pre-change single-shot baseline on this host. cProfile call counts drop **~25–40%** on pure expression walks; scalar BinOp no longer appears under `_elementwise_binary` / `wrapper`.

**275** tests pass (`test_evaluator` + `test_ta_incremental`).

## Profile (before this round)

cProfile on mixed / binop / compare / subscript (30k each), warm visitor cache, float context:

| Symbol | share (mixed) |
|---|---|
| `NodeVisitor.visit` | ~32% tottime |
| `visit_BinOp` | ~21% |
| `dict.get` (cache + op maps + names) | ~12% |
| `_na_safe_binary` wrapper | ~7% |
| `_elementwise_binary` | ~8% |
| `visit_Compare` | ~8% |
| `visit_Name` | ~4% |

Subscript path paid ~450k `isinstance` + 90k `abs` + 90k `len` per 30k top-level visits.

BoolOp paid genexpr frames (`visit_BoolOp.<genexpr>`) under `all`/`any`.

Round-2 residual notes explicitly called out: skip wrapper frame, BoolOp manual loop, context cache (small).

## Baseline microbench (before, single trial, 80k)

| Expression | ms (80k) | µs/visit |
|---|---:|---:|
| `a + b * c - d / e` | 239.9 | 3.00 |
| `a < b and b <= c and c > d` | 438.0 | 5.48 |
| `close + open - high + low + volume` | 239.9 | 3.00 |
| ternary `a > b ? a : b` | 151.9 | 1.90 |
| mixed (binop + compare + ternary) | 728.9 | 9.11 |
| and/or chain | 564.8 | 7.06 |
| unary `-a + +b * -c` | 406.0 | 5.08 |
| `a + na * b` | 230.5 | 2.88 |
| `close[1] + open[0] - high[2]` | 545.0 | 6.81 |

Helper (300k): `ADD(float,float)` via wrapper ≈ 81 ms; `_elementwise_binary` alone ≈ 68 ms.

### Call counts (before, 30k)

| Walk | primitive-ish total calls |
|---|---:|
| mixed | 2.10M |
| binop_chain | 1.32M |
| compare_chain | 1.38M |
| subscript | 1.86M |

## After microbench (same host, median of 5, 80k)

| Expression | med_ms | µs/visit | vs before |
|---|---:|---:|---:|
| binop_chain | **210.1** | 2.63 | **1.14×** |
| compare_chain | **251.5** | 3.14 | **1.74×** |
| names | **183.4** | 2.29 | **1.31×** |
| ternary | **107.3** | 1.34 | **1.42×** |
| mixed | **354.5** | 4.43 | **2.06×** |
| and_or | **211.5** | 2.64 | **2.67×** |
| unary | **166.4** | 2.08 | **2.44×** |
| na_prop | **99.4** | 1.24 | **2.32×** |
| subscript | **239.4** | 2.99 | **2.28×** |

### Call counts (after, 30k)

| Walk | total calls | vs before |
|---|---:|---:|
| mixed | 1.44M | **−31%** |
| binop_chain | 0.87M | **−34%** |
| compare_chain | 0.99M | **−28%** |
| subscript | 1.08M | **−42%** |

cProfile after: scalar BinOp/Compare paths no longer enter `_elementwise_binary` or the `_na_safe_binary` wrapper. Dominant remaining cost is `NodeVisitor.visit` dict dispatch + recursive Python calls (~45% tottime on mixed).

## Changes

### 1. Scalar-inlined BinOp / Unary / Compare — `expressions.py`

```text
visit_BinOp:
  visit left/right
  if both type is float|int:
    identity-dispatch Add/Sub/Mult/Div/Mod  (Div → _safe_truediv)
  elif left None and right scalar/None → None
  else: _elementwise_binary(_BINOP_RAW[op], left, right)
```

- New module maps `_BINOP_RAW` / `_CMPOP_RAW` hold bare `operator.*` (and `_safe_truediv`).
- Existing `_OPERATOR_*` / `_BINOP_DISPATCH` / `_CMPOP_DISPATCH` kept for `visit_Eq` etc. and any external use.
- Unary: float/int/bool inlined; `None` → `None` (including `not na` → na, matching prior `_na_safe_unary`).

### 2. BoolOp manual short-circuit — `expressions.py`

```python
# and
for value in values:
    if not visit(value):
        return False
return True
# or
for value in values:
    if visit(value):
        return True
return False
```

Preserves `all`/`any` bool result and short-circuit; na is falsy (`na and true` → False, `na or true` → True).

### 3. Compare loop polish — `expressions.py`

- Index loop over `ops` / `comparators` (no `zip(..., strict=True)`).
- Scalar numeric compare inlined (`left < right` etc.).
- Fallthrough uses `_CMPOP_RAW` + `_elementwise_binary` for series/list/na.

### 4. Series subscript fast path — `names.py`

- `type(value) is list` + `type(slice_) is int` before general `isinstance`.
- Bounds: `slice_ >= len(value)` instead of `abs(-(i+1)) > len`.
- Float→int coerce via `type(slice_) is float`.
- Scalar `x[0]` / `x[n>0]` path unchanged.

### 5. Name / Constant / visitor polish

- `visit_Name`: single `self.context[name]` try/except (unchanged strategy; drop redundant local `ctx` bind noise).
- `visit_Constant`: `kind is None` → return value immediately (numeric/bool hot path).
- `NodeVisitor.visit`: `type(node)` instead of `node.__class__`.
- Local `visit = self.visit` in BinOp / BoolOp / Compare / Conditional / Subscript.

### 6. AugAssign shares raw path — `statements.py`

`x += 1` uses `_BINOP_RAW` + `_elementwise_binary` (same semantics as BinOp, no wrapper).

## Correctness

Smoke (NodeLiteralEvaluator, mode=eval):

| Expr | Result |
|---|---|
| `true and false` | False |
| `na and true` / `true and na` | False |
| `na or true` | True |
| `1 + na` / `na * 2` / `-na` / `not na` | None |
| `1 / 0` | None |
| `a < na` | False (failed branch) |
| `close[0]` / `[1]` / OOB | current / prev / None |
| scalar `5[0]` / `5[1]` | 5 / None |

Full suite:

```text
$ PYTHONPATH=src python -m pytest tests/test_evaluator.py tests/test_ta_incremental.py -q --tb=line
275 passed in 3.28s
```

## Not done / residual

| Item | Notes |
|---|---|
| `NodeVisitor.visit` dict dispatch | Still ~40–50% tottime on pure expr walks; next step is compile-to-bytecode / numba plan, not more Python micro-opts. |
| Series-wrapper arithmetic | Still goes through `_elementwise_binary` + `_as_scalar_operand` (hosts that inject bare floats win the fast path). |
| Whole-script vectorization | Forbidden by charter. |
| `na`→0 coercion | Forbidden. |
| Runtime 2000-bar e2e | `backend.runtime.Runtime` not imported as `pynescript.runtime` in this worktree; expression microbench is the controlled measure. |

## Wins (headline)

| Area | Win |
|---|---|
| and/or + compare chains | **~1.7–2.7×** microbench |
| unary / na-propagating arith | **~2.3–2.4×** |
| series subscript | **~2.3×** |
| mixed expr | **~2.1×** |
| pure binop (already hot) | **~1.1–1.2×** (wrapper removed; visit still dominates) |
| function calls / 30k walk | **−28% to −42%** |

**Report path:** `docs/perf_round4/07_dispatch_expressions.md`
