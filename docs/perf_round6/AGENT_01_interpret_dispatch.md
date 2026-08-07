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

# Round 6 Agent 01 — Interpret visit / Call residual tax

**AGENT_ID:** 01  
**ROLE:** Interpret visit / Call residual tax (PERF)  
**BASE_SHA:** `32697c97f7e56de817325356e4dbd692809ecbe8`  
**Date:** 2026-07-31  

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/expressions.py` | Call-site **arg plans** (Name/Const skip `visit`); unrolled 1/2/3-arg shapes; bare-name UDF site (`_SITE_GN`); shared empty kwargs; preserve fail-closed TypeError policy |
| `src/pynescript/ast/evaluator/statements.py` | Assign RHS Call fast path; Expr→Call fast path; pre-bound UDF param/body plan |

**Out of scope:** TA kernels, plot registry, Runtime host, series materialization, generated grammar, R5 dispatch cache redesign (extended, not rediscovered).

## 2. Bugs found

No correctness bugs requiring semantic changes.

| Area | Result |
| --- | --- |
| Name arg KeyError (bare `na`, calendar series) | Preserved via `_BARE_SERIES_BUILTINS` + `_call_builtin` fallback in arg plan |
| Body TypeError vs signature mismatch | Kept `_type_error_from_callee` fail-closed policy on bound/UDF paths |
| Script body “typed plan” dispatch | **Rejected** after measurement — extra Python layers regressed `minimal` under noise; lean Assign/Expr/Call handlers suffice |

## 3. Changes (what / why)

### 3.1 Call-site arg plan (extends R5 site cache)

R5 already classifies Call sites (`_SITE_Q`/`_SITE_QB`/`_SITE_B`/`_SITE_BB`). R6 attaches a **precompiled arg plan** at resolve time:

| Opcode | Meaning |
| --- | --- |
| `_AP_NAME` | `context[id]` (visit_Name hot path) |
| `_AP_CONST` | literal (kind `None` or `"#"`) |
| `_AP_VISIT` | full `visit(value_ast)` |
| `_AP_KW_*` | same for named args |

Bound sites store the plan: `(_SITE_QB, tag, handler, name, plan)`. Hot bars never walk `node.args` or pay `visit` frames for `close`/`14`/`plot(s)`.

### 3.2 Unrolled arg shapes

`_eval_arg_plan` special-cases the shapes that dominate TA/plot scripts:

- 1× Name — `plot(s)`, `ta.atr` length via Const
- Name + Const — `ta.sma(close, 14)`
- Name + Const + Const — `ta.bb(close, 20, 2.0)`

Avoids per-arg opcode branching and list appends on the common path.

### 3.3 Bare-name UDF site (`_SITE_GN`)

Non-builtin bare `Name` callees resolve via `context.get(name)` + arg plan — skips `visit(func)` / Attribute machinery. Fall back to general path if not callable.

### 3.4 Fewer visit frames on Assign / Expr

- Plain assign with Call RHS → `visit_Call` directly  
- Expr with Call value → `visit_Call` directly  

### 3.5 Pre-bound UDF bodies

`visit_FunctionDef` freezes param names, defaults, and body plan (`Expr` vs statement) once. Call path skips re-scanning `node.args` / `isinstance` on every invoke; Call body exprs use `visit_Call` when applicable.

### 3.6 Shared `_EMPTY_KW`

Empty kwargs reuse a module-level dict (never mutated) to avoid `{}` allocs.

## 4. Benchmarks

**Machine:** main workspace (other R6 agents concurrent — high noise).  
**Fair A/B:** only `expressions.py` + `statements.py` swapped vs `HEAD` versions of those two files; rest of tree held constant.  
**Method:** warmup 5, 13 iters interpret @ 2000 bars (`scripts/bench_pipeline` OHLCV helper).

### 4.1 Controlled A/B (HEAD of owned files → A01)

Quiet run (warmup 5, 13 iters, n=2000):

| script | before med_ms | after med_ms | Δ med | before min | after min | Δ min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **minimal** | 15.76 | **14.64** | **−7.1%** | 15.29 | **14.35** | **−6.1%** |
| **ta_sma** | 24.00 | **22.77** | **−5.1%** | 23.36 | **22.15** | **−5.2%** |
| **ta_combo** | 152.10 | **141.98** | **−6.7%** | 148.56 | **140.37** | **−5.5%** |
| **strategy_ish** | 69.14 | **63.09** | **−8.7%** | 67.81 | **62.29** | **−8.1%** |

Under concurrent agent load, larger gaps appeared (ta_combo med −50%+); treat quiet table as the conservative claim.  
**DoD wall ≥10–15%:** not claimed on quiet med alone. **DoD structural win:** yes (see 4.2). **No minimal regression:** yes (faster).

### 4.2 cProfile ta_combo interpret @ 1500 bars (structural)

| metric | R5 residual (session start) | A01 after |
| --- | ---: | ---: |
| Function calls | ~1.03 M | **~0.74 M (−28%)** |
| `visitor.visit` ncalls | ~90 k | **~27 k (−70%)** |
| `visit_Name` / `visit_Constant` | 22.5 k / 15 k | **gone from top-20** |
| `_collect_call_args` | 25.5 k top-10 | **replaced by `_eval_arg_plan`** (unrolled; low tottime) |
| Profiled wall (quiet-ish) | ~0.54–0.61 s | **~0.42 s** |

## 5. Tests run

```bash
.venv/bin/python -m pytest tests/test_evaluator.py tests/test_ta_incremental.py \
  tests/test_parity.py -q --tb=line
# → 341 passed
```

## 6. Residual risks / follow-ups

- Site + arg-plan cache keys on `id(Call)`; invalid if host rebuilds AST mid-run (none do today).
- Arg-plan Name KeyError path uses `_BARE_SERIES_BUILTINS` (must stay in sync with `names.py`).
- `_EMPTY_KW` must never be mutated by callees (handlers treat kwargs as read-only today).
- Next residual: series/`_expect_*` tax (Agent 02), residual full-history TA (Agent 03), visit_Call self-time still #1 after arg collect wins.
- Full-script body specialization was a net loss for tiny scripts; do not re-add without measuring `minimal`.

## 7. Explicit out of scope / did not touch

- TA incremental kernels / re-baseline ATR or supertrend  
- Plot steady-state / Runtime JSON pack  
- Numba compile path  
- Grammar / parser  
- Commit / push  

## Definition of Done

- **≥10–15% wall on ta_combo *or* structural win:** **structural win** (−28% calls, −70% `visit` frames; quiet wall ~−7% ta_combo / −9% strategy)  
- **No >5% regression on minimal:** yes (**−6–7%** quieter)  
- **Tests green:** 341 passed  
- **No na→0 / no bar parallelization / no whole-script vectorize**  
- **R5 dispatch cache extended (arg plan + UDF site), not rediscovered**  
