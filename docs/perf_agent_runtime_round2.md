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

# Runtime host bar-loop performance (round 2)

**Date:** 2026-07-28  
**Scope:** Interpret-mode `Runtime.run` bar loop host overhead (`backend/runtime.py`)  
**Constraint:** zero correctness loss; no script vectorization; no bar parallelization; stable Runtime API  
**Dual-host:** same pattern mirrored in `pyne-worker` `src/pynescript_backend/runtime.py`

## Summary

Round-2 micro-opts on the **host** bar loop (series updates, context/barstate, plot/event bookkeeping, series cap). Evaluator / incremental `ta.*` unchanged.

**A/B (same process, stash baseline → optimized), 2000 synthetic bars, median of 9 iters (3 warmup):**

| Script | baseline med_ms | optimized med_ms | gain |
|---|---:|---:|---:|
| minimal (`plot(close)`) | 53.2 | 34.0 | **+36.0%** |
| ta_multi (sma/ema/rsi/atr/stdev) | 407.3 | 322.5 | **+20.8%** |
| ta_combo (+bb/highest/lowest) | 500.7 | 442.9 | **+11.6%** |

- TA multi hits **≥15%** target.
- Minimal improves strongly (host-dominated) with **no regression**.
- Combo still benefits (~12%); remaining time is mostly AST visit / builtins (out of host scope).

Correctness: plot/series snapshots for minimal, multi-TA, and calendar scripts matched pre-change digests on 500 bars.  
Tests: `tests/test_ta_incremental.py` + `tests/test_evaluator.py` (261 passed); runtime-related suite (multi-plot, strategy events, surface gaps, datafeed) 53 passed.

## What changed (backend SoT)

File: `backend/runtime.py` interpret path only.

### 1. Pre-bind hot locals
- Column series list refs (`sl_open`, …) instead of `_series_lists["open"].append` every bar
- `PineSeries.update` methods bound once
- `visit`, `reset_plots`, `plot_outputs`, strategy `pending_orders` / `_events`, `run_id`

### 2. In-place series cap (no rebind)
- Hoist `_SERIES_MAX` (+64 slack) outside the loop
- Trim with `del lst[:drop]` so pre-bound list refs and `evaluator.current_series` stay valid
- Semantics unchanged: keep last `_SERIES_MAX` samples after slack overrun

### 3. Single-pass OHLC floats + local prev close
- One `float()` set drives `hl2` / `hlc3` / `ohlc4` / `tr`
- `prev_close_f` local replaces `close_series[1]` lookup for true range

### 4. Cheaper barstate / bid-ask / strategy paths
- Set static flags once (`isnew`, `ishistory`, `isconfirmed`, `isrealtime`); only `isfirst` / `islast` / `islastconfirmedhistory` per bar
- Pre-scan `has_bid_ask` once; skip per-bar bar dict access when absent
- Call `process_pending_orders` only when `pending_orders` non-empty
- Clear/drain strategy events only when buffer non-empty (skip alloc for indicators)
- Set `_pine_defs_locked` once after first bar (not every bar)

### 5. Lighter plot collection + post-process
- Per-bar `plot_rows` snapshots (`plot_outputs[:]`) instead of per-bar result dicts + `f"plot_{i}"` keys
- Build `series_map` / `plot_meta` / primary `plots` once after the loop
- Reuse pre-extracted `col_time` for drawing export

### Already present (kept)
- Parse tree cache (`_PARSE_CACHE`)
- `need_calendar` skip for UTC parts
- Append-only `current_series`, one-pass derived series, `_pine_defs_locked` semantics

## Dual-host (pyne-worker)

Mirrored in `/home/jango/Git/pyne-worker/src/pynescript_backend/runtime.py`:
- Same pre-bind / in-place cap / static barstate / bid-ask / event skip / single float+prev close path
- Worker-specific: timeout every 32 bars, `hlcc4` + `time`/`time_close` series, simpler `plots` = first plot values only
- No `process_pending_orders` on worker path (unchanged)

## Non-goals / left on table
- Evaluator dispatch / plot builtin cost (dominates TA scripts under cProfile)
- Vectorizing scripts or parallel bars
- Skipping DrawingRegistry export when no drawings (once-per-run; low ROI)
- Changing series semantics or raising `_SERIES_MAX`

## Method notes
- Baseline/optimized compared via `git stash` of `backend/runtime.py` in one shell session to reduce machine noise
- Wall times still vary under load; report **medians** of multi-iter runs
- cProfile: host `run` tottime ~71ms → ~43ms on ta_multi @ 2000 bars; visit/builtins remain the bulk of cumtime
