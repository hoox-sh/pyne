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

# PYNE / pynescript — Round 5: 12 Subagents
# Focus: performance + correctness (bugs, parity, residual surface)
# Date baseline: post Round 4 (2026-07-29) — see docs/perf_round4/ and docs/perf_agents_summary.md
# BASE_SHA at round start: ca5215ac33c34f9b60584f8c230bc281dc768782

You are one of 12 isolated subagents. Optimize and fine-tune **pynescript** (Python
toolchain for TradingView Pine Script: parser, AST, evaluator, Numba compiler,
Runtime host, LSP, Pro API). Primary goals:

1. **Correctness first** — bar-by-bar Pine semantics, series offsets, `na`, `var`/`varip`,
   strategy event order must match the **current pynescript oracle** (prefer bit-identical
   last-bar values; float noise only where documented).
2. **Performance second** — measurable speedups on real hot paths; no silent semantic
   “fixes” disguised as optimisations.
3. **Bug hunt** — find and fix real defects (crashes, wrong results, O(n²) regressions,
   dual-host drift) with tests.

## Repo map (work only here unless dual-host noted)

Workspace: pynescript (package `pynescript`, product “pyne”)
- Core: `src/pynescript/`
- Runtime host SoT: `backend/runtime.py`, `backend/evaluator.py`
- Compiler: `src/pynescript/compiler/{compiler,engine,numba_builtins,strategy_broker}.py`
- Tests: `tests/`
- Corpus: `tests/data/set0{1,2,3,4,5}/`, sanitize `src/pynescript/util/corpus_sanitize.py`
- Bench: `scripts/bench_pipeline.py`
- Prior perf writeups: `docs/perf_agents_summary.md`, `docs/perf_round4/00_summary.md`,
  `docs/perf_round4/10_bottleneck_map.md`
- Perf skill: `.grok/skills/pynescript-perf/SKILL.md`
- Project rules: `AGENTS.md`

Sister hosts (document drift; only patch if your agent owns dual-host):
- `/home/jango/Git/pyne-worker` — thin CF Runtime host
- AXIS is NOT in this repo — do not recreate `frontend/`

## Hard constraints (ALL agents — never violate)

1. **Zero correctness loss** vs current oracle. Prefer golden tests before behaviour change.
2. **Do not** vectorize whole scripts or parallelize bars of one run.
3. **Do not** silent-coerce `na` → 0 for speed.
4. **Do not** hand-edit generated grammar:
   - NEVER touch `src/pynescript/ast/grammar/antlr4/generated/`
   - NEVER touch `src/pynescript/ast/grammar/asdl/generated/`
   - Grammar edits ONLY in `src/pynescript/ast/grammar/antlr4/resource/` (+ selective regen per AGENTS.md)
5. **No stale backups** in `src/` (no `*.bak`, no second `technical_refactored.py`).
6. **`from __future__ import annotations`** on every new Python file.
7. Risky TA semantic re-baselines (e.g. ATR EMA→Wilder RMA, TV numerical parity) require
   explicit tests + docs; never as a silent perf patch.
8. Phase-risky optimisations (new incremental TA, ring buffers, history caps below warm-up)
   → **behind flags** + golden tests (mirror `PYNE_TA_INCREMENTAL`).
9. Do **not** re-implement already-shipped wins (see “Do not rediscover” below).
10. Prefer small, reviewable diffs. Land evaluator/TA math in
    `src/pynescript/ast/evaluator/` first; Runtime host stays thin.
11. Do not commit secrets (`.metadata.key`, API tokens). Do not force-push.
12. Run targeted tests for your area before claiming done; report command + numbers.

## Do not rediscover (already done — do not “re-optimize” as new work)

| Layer | Already shipped |
|---|---|
| Parse | SLL-first + LL fallback; skip annotations without `@`; builder location fast path |
| Unparse | Thread-local reuse; type-keyed dispatch |
| Evaluate TA | Incremental sma/ema/rma/rsi/macd/atr/stdev/bb/highest/lowest/wma/vwma/stoch/cci/tsi/… |
| Host | `_pine_defs_locked`, append-only series, bar pre-bind, series cap, plot registry O(plots) |
| Compile | Numba `*_inc` kernels (sma…hma, rolling, rising/falling, valuewhen, …) |
| Dispatch | Type-keyed visitor, op maps, scalar paths (partial) |
| Strategy | begin_bar, O(1) PnL paths, compile object-mode broker improvements |

**Current truth (Round 4):** Interpret is **dispatch / `_as_series` / plot** bound
(kernels ~5–10%). Compile run is µs-scale after warm JIT; cold JIT dominates oneshot.
Corpus parse set01–04 ~**99.64%**. Prefer **default compile + residual plumbing + P0 surface**.

## Measurement (every performance agent)

```bash
# From repo root with venv
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile   # if supported

# Correctness core (pick what you touch)
.venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py \
  tests/test_parity.py tests/test_compiler_numba.py -q --tb=line

# Broader when strategy/runtime touched
.venv/bin/python -m pytest tests/test_strategy_events.py tests/test_strategy_runtime.py \
  tests/test_order_fills.py tests/test_plotting_effects.py -q --tb=line
```

Report for any claimed win:
- **before / after** median ms (or bars/s) on named scripts (`minimal`, `ta_sma`, `ta_combo`, `strategy_ish`)
- bar count, Python version, command
- test command + pass count
- correctness: golden ≡ full recompute (inc path) or parity suite green

**Definition of Done (perf):** ≥10–15% on a real path **or** clear structural win;
no >5% regression on `minimal`. Corpus Runtime OK rate must not fall if you touch Runtime.

**Definition of Done (bugs):** repro + fix + regression test; no “drive-by” refactors.

## Shared output format (write at end)

Create: `docs/perf_round5/AGENT_NN_<slug>.md` with:

1. Scope & files touched
2. Bugs found (severity, repro)
3. Changes (what/why)
4. Benchmarks (before/after table)
5. Tests run
6. Residual risks / follow-ups
7. Explicit “out of scope / did not touch”

Also leave a short summary (≤20 lines) in the agent handoff message.

---

# Agent roster (exactly one role per agent)

## AGENT 01 — Interpret dispatch / call plumbing (PERF + BUGS)
**Owns:** `src/pynescript/ast/evaluator/expressions.py`, `names.py`, `statements.py`,
visitor dispatch paths used in bar loop.
**Goal:** Cut `visit` / `visit_Call` / `_call_builtin` / qualified `ta.*` resolution cost
(Round 4 #1 bottleneck, ~55–70% of interpret).
**Hunt:** double resolution, repeated `ast_qualified_name`, cache misses per bar,
incorrect short-circuit of `and`/`or` with series/`na`, wrong call arity handling.
**Do not:** rewrite whole evaluator; do not break method dispatch / UDT calls.
**Verify:** `test_evaluator`, `test_ta_incremental`, `test_udt_*`, bench `ta_combo` interpret.

## AGENT 02 — Series materialization `_as_series` / `_expect_series` (PERF + CORRECTNESS)
**Owns:** technical helpers + series coercion in
`ast/evaluator/builtins/technical_submodules/common.py` (and call sites in `core`/`basic`/…),
any `_as_series` in evaluator builtins.
**Goal:** Scalar / last-sample fast path for pure incremental TA call sites; avoid full
history lists when bar-mode only needs one sample.
**Hunt:** wrong length after series cap; off-by-one offsets `[1]`; `na` propagation bugs;
sharing incremental state across distinct call sites.
**Flag any new behaviour** if needed. Golden: `tests/test_ta_incremental.py` expansions.
**Verify:** ta incremental + evaluator; bench `ta_combo` / multi-TA.

## AGENT 03 — Residual incremental TA (interpret) (PERF + CORRECTNESS)
**Owns:** `technical.py` + `technical_submodules/*` (not already-inc kernels unless buggy).
**Priority residual kernels (from Round 4 residual list):**
`ta.dmi`/`adx`, `supertrend`, `valuewhen` (interpret), pivots, compose paths for
`dema`/`tema` if still full-history; any nested helpers still calling full `_ema`/`_sma`.
**Rule:** call-site state (`_ta_call_i`), one sample/site/bar, honor `PYNE_TA_INCREMENTAL`,
golden ≡ full recompute.
**Do not:** change ATR seed/RMA semantics without an explicit correctness track + tests.
**Verify:** extend `test_ta_incremental.py`; relevant `test_ta_indicators_*.py`.

## AGENT 04 — Plot / drawing export path (PERF + BUGS)
**Owns:** `ast/evaluator/builtins/plotting.py`, `drawing.py`,
`backend/evaluator.py` plot helpers, DrawingRegistry export.
**Goal:** Cut plot path self-time (Round 4 top-3 tottime on `ta_combo`); keep multi-plot correct.
**Hunt:** O(plots×bars) upsert bugs, missing `plotshape`/`bgcolor`/`fill` series alignment,
empty registry export waste, last-bar-only vs all-bars inconsistencies
(`test_drawing_all_and_last_bar.py`, `test_bgcolor_plotshape_export.py`).
**Verify:** plotting/drawing tests + bench multi-plot interpret.

## AGENT 05 — Runtime host wrap & series bookkeeping (PERF + DUAL-HOST)
**Owns:** `backend/runtime.py`, `backend/evaluator.py`, `backend/series.py`
(and document twin in pyne-worker if you change host contracts).
**Goal:** Shrink Runtime `mode=compile` wrap vs bare `CompiledScript.run` (still ~10× on
table for ta_combo); keep interpret host bookkeeping lean.
**Hunt:** per-bar allocations, reverse rebuild regressions, unlocked defs tables,
series cap correctness vs max_bars_back / warm-up, result packing bloat.
**Do not:** change Pine bar semantics; keep `_pine_defs_locked` behaviour.
**Verify:** parity + strategy runtime + bench interpret vs compile host.

## AGENT 06 — Compiler Numba residual + cold JIT UX (PERF + CORRECTNESS)
**Owns:** `compiler/compiler.py`, `engine.py`, `numba_builtins.py`.
**Goal:** (a) residual `*_inc` kernels not yet wired; (b) reduce cold-compile pain
(cache keys, avoid re-JIT identical IR, safer fallbacks) without wrong numeric results.
**Hunt:** object-mode fallback when nopython should work; kernel parity drift vs interpret;
tuple/plot return packing bugs; LRU cache collisions.
**Verify:** `test_compiler_numba.py`, `test_compiler_objects.py`; bare `CompiledScript.run`
benches; max abs err vs full recompute where applicable.

## AGENT 07 — Strategy broker correctness (CORRECTNESS primary, perf secondary)
**Owns:** `ast/evaluator/builtins/strategy.py`, `events.py`, `compiler/strategy_broker.py`,
related tests (`test_strategy_*`, `test_order_fills.py`, `test_oca_commission.py`,
`test_strategy_risk_enforcement.py`).
**Goal:** Bug hunt on fills, OCA, commission/slippage, risk blocks, pending orders,
compile vs interpret event parity.
**Hunt:** double fills, wrong bar for market/limit, risk_blocked missing events,
position_size/equity drift, compile broker missing fields vs interpret.
**Perf:** only if correctness suite stays green (O(1) paths, avoid full history scans).
**Verify:** full strategy test cluster + a small corpus strategy sample if available.

## AGENT 08 — Parser / builder residual + corpus sanitize (CORRECTNESS + light PERF)
**Owns:** `ast/helper.py`, `builder.py`, `util/corpus_sanitize.py`,
resource lexer only if truly needed (`grammar/antlr4/resource/*`) — **prefer sanitize over grammar**.
**Goal:** Drive residual PARSE_FAIL / scrape junk down; any safe builder micro-opts
without touching generated parser wholesale.
**Hunt:** soft-keyword edge cases, typed UDF returns, reassignment `=`, multiline strings,
sanitize false positives that corrupt real Pine.
**Do not:** mass-regenerate parser/visitor unless unavoidable; follow grammar-changes guide.
**Verify:** `test_parse_and_unparse` sample or narrowed dir; `test_corpus_sanitize.py`,
`test_lexer_corpus_fixes.py`, `test_v6_features.py`.

## AGENT 09 — Collections, UDT, matrix/map surface (CORRECTNESS + BUGS)
**Owns:** `builtins/arrays.py`, `matrix*.py`, `map*.py`, UDT paths
(`test_udt_*`, `test_map_*`, `test_matrix_*`, `test_collections.py`).
**Goal:** Find crashes / wrong methods / v6 surface gaps; fix with tests.
**Hunt:** `array.*`/`matrix.*`/`map.*` arity, bounds, `na` elements, method syntax,
type fields, copy vs ref semantics, set05-style none-callable / OOB issues
(see `docs/perf_round4/set05_fix_*.md` themes).
**Perf:** only micro (avoid O(n²) copies in hot loops) with tests.
**Verify:** collection + UDT + v6 surface lock tests.

## AGENT 10 — v6 / builtin surface P0 gaps (CORRECTNESS product)
**Owns:** dispatch registration, `builtins/*` gaps from
`docs/perf_round4/08_v6_coverage_matrix.md` and `docs/missing_features.md` P0 list:
unknown-attr safety, `log.*` varargs, `strategy.percent_of_equity` / qty consts,
chart aliases, polyline mutators, request/datafeed edges as needed.
**Goal:** Raise Runtime product fidelity (was ~84% weighted) on P0 items only —
not a full inventory rewrite.
**Hunt:** AttributeError on valid Pine; wrong defaults; missing constants;
silent no-ops that should error or vice versa.
**Verify:** `test_v6_surface_locks.py`, `test_pine_surface_gaps.py`, `test_v6_features.py`,
targeted new tests per gap closed. Update notes in agent report (not drive-by docs spam).

## AGENT 11 — LSP + diagnostics correctness/perf (EDITOR PATH)
**Owns:** `src/pynescript/langserver/**`, `tests/test_lsp_features.py`, `test_langserver.py`.
**Goal:** Correct diagnostics/hover/completion/semantic tokens; reduce redundant full
re-parses on large docs where safe (cache invalidation correctness is critical).
**Hunt:** stale diagnostics after edit, wrong positions, crash on incomplete input,
advertised-but-unimplemented capabilities, metadata load failures.
**Do not:** encrypt key churn; do not hand-edit `builtin_metadata.json` — regenerate via
`scripts/generate_builtin_metadata.py` if builtins added (then note encrypt step).
**Verify:** `make test-lsp` or pytest lsp modules; smoke open large `.pine` if practical.

## AGENT 12 — Synthesis / bottleneck re-measure / regression net (META + BUGS)
**Owns:** measurement only + small glue fixes if blocking benches; write
`docs/perf_round5/00_summary.md` and refresh bottleneck ranking.
**Goal:** Re-run `scripts/bench_pipeline.py` (+ `--profile`) on post-merge or sequential
baselines; produce updated top-10 bottleneck table; flag regressions >5% on `minimal`
or any agent that broke tests.
**Also:** quick bug sweep from recent failures:
`pytest` flaky/failing modules, set05 fix themes, dual-host comment drift.
**Do not:** large feature work; you are the net that keeps the round honest.
**Deliverable:** ranking table, per-agent scorecard (win / noop / regress), merge order
recommendation (correctness agents before pure perf if conflicts).

---

# Orchestration rules (for the parent agent)

1. Prefer **isolated git worktrees** per agent (or sequential if single tree).
2. Merge order recommendation:
   - Correctness first: 07 → 09 → 10 → 08
   - Then interpret stack: 01 → 02 → 03 → 04 → 05
   - Then compile: 06
   - LSP can parallel: 11
   - Last: 12 synthesis after others land or against each worktree tip
3. Conflict hotspots: `expressions.py`, `technical_submodules/*`, `backend/runtime.py`,
   `compiler/numba_builtins.py` — serialize those owners.
4. If two agents touch same function: **correctness wins**; perf must re-bench after.
5. Each agent must refuse scope creep into another agent’s primary files unless blocked;
   file a note for Agent 12 instead.
6. Explicit non-goals for the whole round:
   - Whole-script vectorization / parallel bars
   - Numba-on-edge as default product path
   - Recreating AXIS frontend
   - Mass grammar regeneration
   - “Fixing” ATR/TV oracle without a dedicated correctness PR

# Quick commands reference

```bash
make install          # pip install -e ".[lsp]"
make test             # full (heavy)
make lint             # ruff
make test-lsp
make test-backend     # needs backend reqs / ADMIN_TOKEN in tests

# Narrow
.venv/bin/python -m pytest tests/test_ta_incremental.py -q
.venv/bin/python -m pytest tests/test_compiler_numba.py -q
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
```

# Agent self-brief (fill at start)

```
AGENT_ID: NN
ROLE: <title>
BASE_SHA: ca5215ac33c34f9b60584f8c230bc281dc768782
BRANCH/WORKTREE: <name>
SUCCESS METRIC: <one sentence>
OUT OF SCOPE: <one sentence>
```

Start by reading your owned files + the matching Round 4 report if any, then
**profile or reproduce before editing**. Ship tests with every behaviour change.
```
