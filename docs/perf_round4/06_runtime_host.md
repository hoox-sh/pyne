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

# Runtime host bar-loop performance (round 4 / Agent 6)

**Date:** 2026-07-29  
**Scope:** Interpret-mode `Runtime.run` host overhead outside pure TA kernels  
(`backend/runtime.py`, `backend/evaluator.py`, light `backend/series.py` usage)  
**Constraint:** no parallel bars; no `na→0`; no whole-script vectorize; Runtime API stable  
**Canonical SoT:** `backend/runtime.py`  
**Prior:** round 2 host opts — `docs/perf_agent_runtime_round2.md`  
**Related:** plot bookkeeping round 3 left *columnar plot_outputs* on the table —
`docs/perf_agent_plot_round3.md`

## Summary

Round-4 targets remaining bar-loop host cost: **plot collection**, **PlotRegistry
super() on every `plot()`**, unused **derived series** updates, and **mode=auto**
eligibility caching.

### Microbench (synthetic OHLCV, median of 21 iters, 5 warmup)

| Script | baseline med_ms† | optimized med_ms | gain |
|---|---:|---:|---:|
| minimal `plot(close)` @ 2k | 26.8 | **20.6** | **~23%** |
| minimal @ 5k | 64.0 | **51.3** | **~20%** |
| ta_multi (sma/ema/rsi/atr/stdev ×5 plots) @ 2k | 218 | **195** | **~11%** |
| ta_multi @ 5k | 546 | ~549‡ | ~flat (TA-dominated) |

† Same-session stable baseline before this patch (see Method).  
‡ TA multi at 5k is visit/builtin-dominated; host opts still apply but wall noise
swallows small % gains.

**≥10% on minimal and on ta_multi@2k achieved.** No semantic regressions on
plot/series/plot_meta probes (see Correctness).

### cProfile deltas (minimal @ 2k, 1 warm run)

| Metric | pre (round4 start) | post |
|---|---:|---:|
| total function calls | ~261k | ~229k |
| `PineSeries.update` ncalls | 18 000 (9 series) | **12 000** (6 series) |
| `_plot_upsert` / PlotRegistry fill | in top callees | **gone** (no-fill scripts) |
| `run` exclusive tottime | ~26 ms | ~17 ms |

Top remaining callees are AST `visit` / `visit_Call` / dict `.get` — out of host
scope (evaluator dispatch agents).

## What changed

### 1. Columnar plot capture + once-only meta (`backend/evaluator.py`)

Left on table by plot round 3: one dict per `plot()` per bar.

- `_plot_value_cols: list[list]` — one column per call-site order index  
- `_plot_meta_list: list[dict]` — title/color/kind/… recorded once (first
  non-null color wins, matching prior post-process)  
- `finish_bar_plots()` pads short columns when a call site is skipped that bar  
- Runtime builds `series` / `plot_meta` / primary `plots` from columns — no
  per-bar `plot_outputs[:]` shallow copy of dict lists  

### 2. Conditional PlotRegistry (`_pine_need_plot_ids`)

`CustomEvaluator` used to **always** call `super()._builtin_plot` →
`_plot_upsert` / `_fill_plot` every bar. That path is required only when
`plot()` must return a `Plot` handle (mainly `fill(p1, p2)`).

- Runtime scans source with `\bfill\s*\(`  
- Sets `evaluator._pine_need_plot_ids` accordingly  
- Default remains **True** when `CustomEvaluator` is used outside Runtime  
- Isolated A/B (columnar already on): force registry **31.9 ms** vs skip
  **23.9 ms** on minimal@2k (~25% of that path)

PlotRegistry unit tests use `NodeLiteralEvaluator`, not Runtime — unchanged.

### 3. Skip unused derived series (`hl2` / `hlc3` / `ohlc4`)

Cheap `\bhl2\b` (etc.) scans; when absent, skip `PineSeries.update` + list
append for that series. Always keep OHLCV + `tr` (needed by `ta.atr` and peers
even when names never appear in source).

Cuts 3 of 9 series updates on minimal/ta_multi scripts.

### 4. mode=auto: cache numba probe

`_HAS_NUMBA` module cache so `_compile_eligible` does not re-import / re-probe
numba every auto run.

## Dual-host (`pyne-worker`)

Path: `/home/jango/Git/pyne-worker/src/pynescript_backend/`

| Topic | backend SoT | worker twin |
|---|---|---|
| Canonical API | multi-series `series`/`plot_meta`/drawings | simple `plots` = first series only |
| PlotRegistry on plot() | conditional (fill) | already skipped (capture-only) |
| Columnar multi-plot | yes | N/A (plot0 only); **value-only** `plot_outputs` (no per-bar dict) |
| Derived series skip | hl2/hlc3/ohlc4 | **mirrored** + `hlcc4` |
| time/time_close series | scalar context keys | PineSeries + lists (worker-specific) |
| timeout | no | every 32 bars |
| mode=auto | numba cache + import/request prefilter | import/request prefilter (object-mode may not need numba) |

Worker files touched this round:

- `runtime.py` — derived-series skip (incl. hlcc4)  
- `evaluator.py` — scalar `plot_outputs.append(value)`  

## Correctness

Probes on 500 synthetic bars (digests of series tails + plot_meta kinds):

| Script | notes |
|---|---|
| minimal `plot(close)` | `plots[-1] == close`, count=500 |
| ta_multi 5 plots | 5 series keys, full length |
| calendar `hour`/`dayofweek` | 3 series |
| hline + bgcolor + plot | kinds `plot`/`hline`/`bgcolor`; bgcolor nulls preserved |

Tests (this worktree):

```text
305 passed  (evaluator + ta_incremental + bgcolor/plotshape + multi_plot +
             plotting_effects + drawing + parity fixtures)
6 failed    test_parity corpus_* — missing tests/data/builtin_scripts/*.pine
            in worktree (env; not regressions from this patch)
```

Targeted re-run after dual-host edits: **43 passed**
(`test_parity -k 'not corpus'`, bgcolor, multi_plot, ta_incremental).

## Non-goals / left on table

- Evaluator dispatch / `visit_Call` (dominates TA multi under cProfile)  
- Parallel bars / vectorize script body  
- Raising `_SERIES_MAX` or changing series semantics  
- Skipping OHLCV/tr when static analysis proves unused (riskier than derived)  
- Deep copy-free `fill()` path still pays PlotRegistry when `fill(` present  

## Method notes

- Baseline = same Python process session measurements immediately before
  patch application (median of multi-iter runs).  
- Wall times vary under load; report **medians**.  
- cProfile absolute times inflated vs wall; use for ranking callees and
  ncall deltas.  
- Force-registry A/B used `_FILL_CALL_RE` monkeypatch to isolate registry cost
  with columnar capture held constant.

## Files

| File | Role |
|---|---|
| `backend/runtime.py` | bar loop, derived skip, columnar post-process, auto cache |
| `backend/evaluator.py` | columnar capture, conditional PlotRegistry |
| `docs/perf_round4/06_runtime_host.md` | this report |
| `pyne-worker/.../runtime.py` | dual-host derived skip |
| `pyne-worker/.../evaluator.py` | value-only plot capture |
