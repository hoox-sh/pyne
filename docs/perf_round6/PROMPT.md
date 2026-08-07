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

# PYNE / pynescript — Round 6: 12 Subagents
# Focus: performance + correctness + hardened error handling + compiler coverage
# Date: 2026-07-31
# BASE_SHA: 32697c97f7e56de817325356e4dbd692809ecbe8
# Prior: Round 5 (docs/perf_round5/00_summary.md) — do not rediscover shipped wins

You are one of 12 isolated subagents (git worktree). Optimize **pynescript**
(package `pynescript`, product “pyne”): parser, AST evaluator, Numba compiler,
Runtime host, strategy, LSP, Pro API.

## Goals (priority order)

1. **Correctness** — bar-by-bar Pine semantics; series offsets; `na`; `var`/`varip`;
   strategy event order. Prefer bit-identical vs current oracle; float noise only
   where documented with tests.
2. **Hardened error handling** — replace silent `except Exception: pass` with
   typed Pine errors / logging where it hides bugs; never swallow compile-time
   or bar-loop failures that should surface; improve messages for users.
3. **Compiler coverage** — more `ta.*` / math / strategy / chart surface that
   stays in **numeric nopython** (or correct object-mode) instead of stubs /
   force_object_mode thrash.
4. **Performance** — measurable wins on hot paths; no semantic “fixes” as speed hacks.

## Repo map

Workspace root of your worktree:
- Core: `src/pynescript/`
- Runtime SoT: `backend/runtime.py`, `backend/evaluator.py`
- Compiler: `src/pynescript/compiler/{compiler,engine,numba_builtins,strategy_broker}.py`
- Tests: `tests/`
- Bench: `scripts/bench_pipeline.py`
- Prior: `docs/perf_round5/00_summary.md`, `docs/COMPILER_PLAN.md`
- Perf skill: `.grok/skills/pynescript-perf/SKILL.md`
- Rules: `AGENTS.md`

Sister (document drift; only patch if your role owns dual-host):
- `/home/jango/Git/pyne-worker` — thin CF Runtime host
- AXIS is NOT here — do not create `frontend/`

## Hard constraints (never violate)

1. Zero correctness loss vs current oracle. Golden tests before behaviour change.
2. Do **not** vectorize whole scripts or parallelize bars of one run.
3. Do **not** silent-coerce `na` → 0 for speed.
4. Do **not** hand-edit generated grammar:
   - NEVER `src/pynescript/ast/grammar/antlr4/generated/`
   - NEVER `src/pynescript/ast/grammar/asdl/generated/`
   - Grammar only in `…/resource/` (+ selective regen per AGENTS.md)
5. No stale backups in `src/`.
6. `from __future__ import annotations` on every new Python file.
7. Risky TA re-baselines (ATR EMA→Wilder, TV supertrend ratchet) need explicit
   tests + docs — not silent perf patches.
8. New incremental TA / ring buffers / aggressive history caps → **behind flags**
   + goldens (mirror `PYNE_TA_INCREMENTAL`).
9. Do not re-implement Round 1–5 wins (dispatch cache, last-sample series,
   bulk `*_inc` kernels, plot steady-state, host JSON/OHLCV cache, dema/tema
   Numba, strategy.cash/pyramiding, sanitize FPs, UDT sort_field, P0 surface,
   LSP AST reuse). See `docs/perf_round5/00_summary.md` “Already solved”.
10. Small, reviewable diffs. Evaluator/TA math in `src/pynescript/ast/evaluator/`
    first; Runtime stays thin.
11. No secrets, no force-push, no commit of `.vsix` / `.metadata.key`.
12. Run targeted tests for your area; report commands + numbers.

## Measurement

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
# Correctness core (pick what you touch)
.venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py \
  tests/test_parity.py tests/test_compiler_numba.py tests/test_compiler_objects.py \
  tests/test_compiler_strategy.py -q --tb=line
```

Report before/after medians on `minimal`, `ta_sma`, `ta_combo`, `strategy_ish`
when claiming perf wins. DoD: ≥10–15% on a real path **or** structural win;
no >5% regression on `minimal`.

## Shared output

Write: `docs/perf_round6/AGENT_NN_<slug>.md` with:
1. Scope & files
2. Bugs found
3. Changes
4. Benchmarks
5. Tests run
6. Residual risks
7. Out of scope

Also leave ≤20 lines summary in the agent handoff message.

---

# Agent roster

## AGENT 01 — Interpret visit / Call residual tax (PERF)
**Owns:** `src/pynescript/ast/evaluator/expressions.py`, `names.py`, `statements.py`
**Target:** R5 residual #1 — further cut visit_Call / `_collect_call_args` /
typing tax without correctness loss. Pre-bound UDF bodies, fewer visit frames,
faster arg collect for hot builtins. Profile `ta_combo` interpret.
**Tests:** `test_evaluator.py`, `test_ta_incremental.py`, `test_parity.py`

## AGENT 02 — Series / expect / last-sample residual (PERF + CORRECTNESS)
**Owns:** series materialization helpers, `_expect_series`, `_expect_int`,
`backend/series.py`, evaluator series paths.
**Target:** residual typing/last-sample tax; fix any off-by-one / na leaks on
history access. Do not re-break last-sample pure-inc path.
**Tests:** `test_ta_incremental.py`, `test_evaluator.py`, multi-plot if needed

## AGENT 03 — Residual TA incremental: full-history leftovers (PERF + CORRECTNESS)
**Owns:** `technical_submodules/{volatility,volume,oscillators,moving_averages,common}.py`
**Target R5 P2:** `kc`/`kcw`, residual `mfi` paths, `sar`, `alma`, `correlation`,
percentiles / percentrank / nearest_rank — incremental or O(period) not O(bars²);
na-safe. Flag + goldens in `test_ta_incremental.py`.
**Do not** re-baseline ATR or supertrend TV semantics.

## AGENT 04 — Compiler numeric coverage: stubs → real kernels (COMPILER)
**Owns:** `compiler.py` call lowering, `numba_builtins.py`
**Target R5 P2:** replace/upgrade stubs for **dmi/adx**, **supertrend** (match
current interpret oracle, not invent TV ratchet), **alma**, **percentrank**,
any high-frequency full recompute still emitted as non-`*_inc`. Prefer staying
in nopython. Add tests in `test_compiler_numba.py`.
**Goal:** more scripts compile numeric without force_object_mode.

## AGENT 05 — Compiler coverage: language surface (COMPILER)
**Owns:** `compiler.py` visitor (control flow, strings, inputs, chart, library stubs)
**Target:** constructs that flip `object_mode` unnecessarily; chart viewport
time stubs that should use bar time when available; `input.*` defaults;
`math.*` gaps; keep numeric when possible. Document remaining force_object reasons.
**Tests:** `test_compiler_numba.py`, `test_compiler_objects.py`, surface tests

## AGENT 06 — Cold JIT / compile cache / engine hardening (COMPILER + PERF)
**Owns:** `engine.py`, compile_script cache, optional disk/IR warm
**Target R5 P1:** reduce cold JIT pain safely (module cache, builtin prewarm,
clearer fallback reasons). Harden engine error paths: typed exceptions,
`compile_fallback_reason` accuracy, no silent wrong results.
**Tests:** compiler suite + runtime compile mode tests

## AGENT 07 — Strategy correctness + compile broker (CORRECTNESS + PERF)
**Owns:** `evaluator/builtins/strategy.py`, `compiler/strategy_broker.py`,
`backend` strategy paths
**Target R5 P2:** exit commission / slippage parity where feasible; pyramiding
edge cases; compile↔interpret strategy parity for common scripts; safer errors
on bad order args (not silent zero fills).
**Tests:** `test_strategy_*`, `test_order_fills`, `test_compiler_strategy`, parity

## AGENT 08 — Hardened error handling across Runtime + evaluator (CORRECTNESS)
**Owns:** `backend/runtime.py`, `backend/evaluator.py`, high-churn `except Exception`
in evaluator builtins (`request.py`, statements, names, utility)
**Target:** classify errors (parse / compile / runtime / data); fail closed where
appropriate; preserve intentional soft-fail for request mocks; never hide
TypeError/AttributeError in bar loop as empty results without log/flag.
Add regression tests for previously silent failures where you tighten.
**Do not** make request.* hard-fail on missing mock data (by design soft).

## AGENT 09 — Collections / UDT / matrix correctness + object-mode compile (CORRECTNESS)
**Owns:** `arrays.py`, `map*.py`, `matrix*.py`, UDT paths, object-mode emit for collections
**Target:** edge crashes (OOB, empty, sort_field, insert), compile object-mode
parity for common array/map ops; better errors on type mismatches.
**Tests:** `test_collections*`, `test_matrix*`, `test_udt*`, `test_compiler_objects`

## AGENT 10 — na-safety audit on technical helpers (CORRECTNESS)
**Owns:** `technical_submodules/common.py` and helpers used by rising/falling/
highestbars/lowestbars/crossover and related; any remaining `>=` on None paths
(follow-on to 0.3.0 rising/falling fix).
**Target:** systematic na-safe comparisons; goldens for warmup-bar scripts;
ensure CommonIndicators does not reintroduce unsafe overrides.
**Tests:** `test_ta_incremental.py` (+ new cases), evaluator

## AGENT 11 — Parser / sanitize / corpus residual (CORRECTNESS)
**Owns:** `util/corpus_sanitize.py`, lexer resource only if needed, parse helpers
**Target:** set05 / residual FAIL patterns without weakening real syntax; safer
sanitize; no grammar generated edits unless resource-only + selective lexer copy.
**Tests:** `test_corpus_sanitize.py`, `test_lexer_corpus_fixes.py`, parse subset

## AGENT 12 — Runtime host product path + dual-host notes + synthesis prep (PERF + PRODUCT)
**Owns:** `backend/runtime.py` mode=auto/compile defaults documentation and any
safe host-side wins left after R5; dual-host drift notes for pyne-worker (patch
worker only if small and safe); write `docs/perf_round6/STATUS.md` update with
what you measured.
**Target:** warm compile path ergonomics; accurate auto fallback; no interpret
regression. Document recommended next steps for parent merge.
**Tests:** backend/runtime related + bench_pipeline

---

## Isolation note

Each agent runs in its own git worktree. Do not push. Do not merge other agents.
Land changes only in your worktree. Parent will merge by dependency order:

Correctness first: **10 → 07 → 09 → 08 → 11**  
Interpret perf: **01 → 02 → 03**  
Compiler: **04 → 05 → 06**  
Host/synth: **12** last
EOF
