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

# Round 9 Agent 03 — Interpret dispatch / visit_Call envelope

| Field | Value |
| --- | --- |
| **Role / ID** | 03 — interpret dispatch (`visit_Call` envelope) |
| **Date** | 2026-08-16 |
| **BASE_SHA** | `41d3e491dc42c6ea918abc8e85e1065fae2e5af6` |
| **Worktree** | `/home/jango/.grok/worktrees/git-pynescript/subagent-01a0092a-d64b-7931-8873-62687dcdc8df` |
| **Verdict** | **win** |

Did **not** redo R5–R6 site kinds, arg-plan opcodes, `_pine_site_id`, Wave 3 P1
scratch lists (`_arg1/_arg2/_arg3`), visitor method cache, or
`_PURE_CONST_FOLD_BUILTINS`. Those stay; this round removes leftover frames
and allocations around them.

## 1. Files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/expressions.py` | Inline site lookup; shaped arg load; skip security-attach / empty-UDF lookup; `_EMPTY_ARGS`; lazy PineSeries unwrap |
| `src/pynescript/ast/evaluator/statements.py` | Fix `_bind_series_name` empty-set alloc; direct Assign/Expr(Call) body walk; skip no-op stmts after defs lock |
| `src/pynescript/ast/evaluator/names.py` | Local `ctx` bind on `visit_Name` hit/miss |
| `tests/test_evaluator.py` | Arg-plan / assign / TypeError / UDF-shadow / hot-body / strategy.entry / na tests |
| `tests/test_expr_parity_r8.py` | PineSeries unwrap + na-current goldens |
| `docs/perf_round9/AGENT_03_dispatch.md` | This report |

`visitor.py` unchanged (cache already present; body walk no longer needs it
on the bar loop). Did **not** edit TA submodules, `runtime/host.py`,
`runtime/evaluator.py`, or `plotting.py`.

## 2. What changed (remaining micros)

### 2.1 `visit_Call` envelope

R7 still paid, every call, every bar:

- `_call_site_for_evaluator` + `_evaluator_generation` (34k frames)
- `_eval_arg_plan` opcode scan (34k)
- `_maybe_attach_security_simple_ta` even for `ta.sma` / `plot` (34k)
- `_lookup_user_callable` on every bound bare site (`plot`, `indicator`) (18k)

Now:

- Site is `getattr(node, "_pine_call_site")` + `self._eval_generation`
  (generation still last tuple element; stale 5-tuples still re-resolve).
- Bound sites store a **shape tag** (`_PS_N1/_PS_C1/_PS_NC/_PS_NCC/…`).
  Hot bars call `_eval_shaped_args` (scratch reuse) instead of the opcode
  interpreter. `_eval_arg_plan` remains for kwargs / OTHER / first-bar bind.
- Security attach runs only when the name is `request.security` / `security`.
- Dual-namespace UDF lookup runs only when `_user_functions` is non-empty.
- `indicator`/`strategy`/`library`/`study` return the existing declaration
  after `_pine_defs_locked` (no arg load / handler).
- Empty plans return shared `_EMPTY_ARGS` + `_EMPTY_KW` (never mutate).

Bound layout (generation still last; existing tests keep using `site[0]`,
`site[2]`, `site[-1]`):

```
_SITE_QB = (kind, tag, handler, name, plan, shape, gen)
_SITE_BB = (kind, name, tag, handler, plan, shape, gen)
```

### 2.2 `visit_Assign` / `visit_Script`

- `_bind_series_name` used `getattr(..., None) or set()`. An empty
  `_history_names` is falsy → **new `set()` on every assign** (16–20k/run
  on ta_combo). Now: `if not history_names or name not in history_names`.
- Plain assign uses `node.type` / `node.export` (always present on Assign)
  and skips `hasattr` on numeric / list / tuple results.
- `visit_Script` no longer allocates `{}` for pending library exports
  every bar; library `isinstance` only on the unlocked first pass.
- After `_pine_defs_locked`, `_build_hot_body` drops `FunctionDef` /
  `TypeDef` / `EnumDef` / `Import` and already-recorded script declarations.
- `_run_body_hot` dispatches `Assign` / `Expr(Call)` directly — no
  `visitor.visit` / `visit_Expr` frames per statement.

### 2.3 Names / compare / binop

- `visit_Name` binds `ctx = self.context` once (hit + miss).
- `_as_scalar_operand` / BinOp / Compare: lazy type-identity for
  `PineSeries` (import deferred so `pynescript.runtime` does not cycle
  through `NodeLiteralEvaluator`). `na` current stays `None`.

## 3. Before / after

**Machine:** this worktree, Python 3.14.6, same process pair.
**Controlled A/B:** warmup 3 / 9 iters interpret @ 2000 bars
(`scripts.bench_pipeline._make_ohlcv` + `Runtime.run(..., mode="interpret")`).
Before = HEAD of exclusive files; after = this diff only.

| script | before med_ms | after med_ms | Δ med | before min | after min |
| --- | ---: | ---: | ---: | ---: | ---: |
| **minimal** | 25.16 | **17.33** | **−31.1%** | 24.37 | **17.03** |
| **ta_sma** | 37.70 | **28.90** | **−23.3%** | 37.15 | **28.32** |
| **ta_combo** | 202.80 | **152.29** | **−24.9%** | 201.77 | **151.32** |
| **strategy_ish** | 102.52 | **70.84** | **−30.9%** | 101.45 | **69.70** |

Official `scripts/bench_pipeline.py --skip-compile --json /tmp/r9_a03.json`
(warmup 2 / iters 5, noisier): minimal **20.72**, ta_sma **33.74**,
ta_combo **173.00**, strategy_ish **81.26** — still well under the
controlled-before table; no minimal regression.

### 3.1 cProfile ta_combo interpret @ 2000 (structural)

| metric | before | after |
| --- | ---: | ---: |
| Function calls | 1 317 136 | **909 349 (−31%)** |
| Profiled wall | 0.749 s | **0.545 s** |
| `visitor.visit` ncalls | 36 000 | **2 000 (−94%)** |
| `visit_Expr` | 18 000 | **0** |
| `visit_Call` ncalls | 34 000 | **32 001** (dropped `indicator()` after lock) |
| `_eval_arg_plan` ncalls | 34 000 | **17** (first-bar bind only) |
| `_call_site_for_evaluator` | 34 000 | **0** |
| `_lookup_user_callable` | 18 000 | **0** on this script |
| `_eval_shaped_args` | — | 31 984 / 0.017 tot |
| `_bind_series_name` tot | 0.013 | **0.008** |

## 4. Tests

```bash
PYTHONPATH=src:. /mnt/data/home/jango/Git/pynescript/.venv/bin/python -m pytest \
  tests/test_evaluator.py tests/test_expr_parity_r8.py tests/test_v6_features.py \
  tests/test_parity.py tests/test_for_loop_syntax.py tests/test_udt_methods.py \
  -q --tb=line
# → 382 passed, 6 skipped
```

Preserved: `na` propagation (not coerced to 0), series element-wise ops,
UDF/`var` history keys (unchanged bind path when `_history_names` is
non-empty), `strategy.entry` via qualified AST path, body `TypeError`
fail-closed (`_type_error_from_callee`). Shared-AST generation stamp and
stale 5-tuple tests still pass.

## 5. Residual / follow-ups

- `visit_Call` exclusive time is still ~0.070 s @ 32k calls (frame volume).
  Next: inline `_eval_shaped_args` or mypyc/C (R7 Agent 12).
- `getattr` ~189k / host `context.__getitem__` 30k — host-side (Agent 04).
- Plot capture + pack still dominate multi-plot wall (Agent 01).
- Nested TA kernels unchanged (Agent 02).
- `_EMPTY_ARGS` / `_EMPTY_KW` must never be mutated by callees (handlers
  treat them as read-only today, same contract as R6).

## 6. Out of scope / did not touch

- TA incremental kernels / ATR or supertrend re-baseline
- Plot registry / Runtime JSON pack / `host.py` bar loop
- `PYNE_SERIES_RING` default
- Grammar / parser / commit

## Definition of Done

- **≥10–15% on `minimal` or `ta_sma`:** **yes** (minimal **−31%**, ta_sma **−23%**)
- **Structural win:** **yes** (−31% calls, −94% `visit` frames)
- **No >5% regression on minimal:** yes (faster)
- **Tests green:** 382 passed, 6 skipped
- **No na→0 / no bar parallelization / no whole-script vectorize**
- **R5/R6/W3 caches extended, not rediscovered**
