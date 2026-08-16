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

# AGENT 02 — T2 residual incremental TA (volume full-list leftovers)

**AGENT_ID:** 02
**ROLE:** Residual incremental TA — interpret (PERF + CORRECTNESS)
**BASE_SHA:** `41d3e491dc42c6ea918abc8e85e1065fae2e5af6`
**Date:** 2026-08-16
**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a0092a-d64b-7931-8873-62528f191d90`

## 1. Scope & files

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/volume.py` | New kernels: `_obv_inc_update`, `_wad_inc_update`, `_wvad_inc_update`, `_cmf_inc_update`, `_klinger_inc_update`; wire builtins behind `_use_incremental_ta` + last-sample |
| `tests/test_ta_incremental.py` | Round 9 goldens (inc ≡ full last value + Runtime on/off) |
| `docs/perf_round9/AGENT_02_ta_incremental.md` | This report |

**Owns (per PROMPT):** leftover full-list volume / nested TA that still rebuilds every bar.  
**Does not:** ATR EMA→Wilder (F1); TV supertrend ratchet; `expressions.py` / host / numba; silent `na→0`.

Profiled remaining wrappers. Picked **4** true O(bars²) rebuilds (corpus / bench hot over synthesizer helpers):

| Candidate | Why picked |
| --- | --- |
| `ta.obv` | R4/R7 leftover; walks all bars from 0 every call |
| `ta.wad` / `ta.wvad` | Full-list rebuild; wvad also rebuilds wad then divides |
| `ta.cmf` | Rebuilds CLV window for **every** prefix bar (O(n·period)) |
| `ta.klinger` | Full TRV + cumsum + two `_ema` series each bar |

Left residual (O(period) window or last-bar already): `ta.nvi`/`pvi`, `ta.vpt`, `ta.ao` (already nested SMA inc), `ta.aroon`, `ta.dpo`, `ta.kst`, `ta.uo`, `ta.ichimoku`, `ta.donchian`, `ta.mode`/`rci`/`cog`/`zigzag`.

## 2. Changes (what / why)

R7 left volume cumulants as full-history rebuilds. Same call-site pattern as `_accdist_inc_update` / `_mfi_inc_update`: `_ta_next_slot` + `_ta_state_bucket`, last sample via `_series_last` / `_context_source` / `_as_series_or_raw(..., last_sample_ok=True)`.

| Kernel | State key | Complexity | Semantics (match full last value) |
| --- | --- | --- | --- |
| `_obv_inc_update` | `("obv", slot)` | O(1)/bar | `0` until 3 samples; accumulate from index 2 (skips `close[0]` vs `close[1]`) |
| `_wad_inc_update` | `("wad", slot)` | O(1)/bar | First bar `0.0`; then `±vol·(close−low\|high−close)` |
| `_wvad_inc_update` | wad slot + `("wvad", slot, period)` | O(1)/bar | last WAD / rolling volume sum (partial window) |
| `_cmf_inc_update` | `("cmf", slot, period)` | O(1)/bar | running CLV·vol / vol (partial window, same as full) |
| `_klinger_inc_update` | `("klinger", slot)` + 2 EMA slots | O(1)/bar | signed volume cumulant; nested `_ema_inc_update` (SMA seed) |

**Flag:** existing `PYNE_TA_INCREMENTAL=0` disables all of the above (default on in bar mode).  
**na:** missing / non-numeric / NaN samples skip the increment (not coerced to 0 in the output). Volume missing on chart context still treats empty volume as 0 contribution, matching the full wrappers.

## 3. Benchmarks

### Kernel microbench

Bar-walk growing prefix, n=2000, median of 3, `PYTHONPATH=src:.`, CPython 3.14.

| Kernel | Full recompute | Incremental | Speedup |
| --- | ---: | ---: | ---: |
| `obv` | 248.5 ms | 13.4 ms | **~18.5×** |
| `wad` | 886.8 ms | 27.3 ms | **~32.5×** |
| `wvad(20)` | 7479.6 ms | 30.5 ms | **~245×** |
| `cmf(20)` | 16621.5 ms | 28.8 ms | **~577×** |
| `klinger(8,21)` | 1458.2 ms | 16.9 ms | **~86×** |

### Runtime interpret (volume-heavy script)

Same 2000-bar OHLCV, five plots (`obv`/`wad`/`wvad(20)`/`cmf(20)`/`klinger(8,21)`), median of 3:

| Path | med_ms | vs full |
| --- | ---: | --- |
| incremental (default) | 134.9 | — |
| `PYNE_TA_INCREMENTAL=0` | 5177.1 | **38.4×** (97.4% faster) |

### `scripts/bench_pipeline.py` (this worktree)

Interpret n=2000: `minimal` 24.31 ms, `ta_sma` 36.66 ms, `ta_combo` 199.06 ms, `strategy_ish` 97.09 ms.

Those stock scripts do **not** call the new kernels; no claim that combo/minimal moved. No expected `minimal` regression from this change (kernels are flag-gated and unused on that path). JSON: `/tmp/r9_a02.json`.

## 4. Tests run

```bash
PYTHONPATH=src:. /mnt/data/home/jango/Git/pynescript/.venv/bin/python -m pytest \
  tests/test_ta_incremental.py -q --tb=line
# → 105 passed

PYTHONPATH=src:. /mnt/data/home/jango/Git/pynescript/.venv/bin/python -m pytest \
  tests/test_first_party_ta_goldens.py tests/test_ta_indicators_1.py \
  tests/test_ta_indicators_2.py tests/test_evaluator.py tests/test_parity.py \
  -q --tb=line
# → 320 passed, 6 skipped
```

New / extended cases:

- `test_incremental_obv_matches_full` (+ dual call sites)
- `test_incremental_wad_matches_full`
- `test_incremental_wvad_matches_full`
- `test_incremental_cmf_matches_full`
- `test_incremental_klinger_matches_full`
- `test_runtime_round9_volume_incremental_vs_disabled`

## 5. Residual / follow-ups

1. **`ta.nvi` / `ta.pvi`** — still full-list cumulative walks (same shape as wad; easy next kernel).
2. **`ta.ichimoku` / `ta.donchian` / `ta.aroon`** — already O(period) window scans; last-sample + `_highest`/`_lowest` inc would drop materialization, not O(n²).
3. **`ta.vpt`** — last-bar only (not a true cumulative VPT); not a rebuild.
4. **`_SERIES_MAX`:** incremental keeps the running total across the cap window (same reason `_accdist_inc_update` exists). Goldens stay under 256 bars so inc ≡ full.
5. **F1** ATR Wilder / TV supertrend still out of scope.

## 6. Out of scope / did not touch

- ATR EMA→Wilder / TV supertrend ratchet  
- Numba `*_inc` ports  
- `expressions.py`, `runtime/host.py`, `runtime/evaluator.py`, compiler  
- Grammar / generated code  
- Commit / push  

## 7. Verdict

**win** — shipped four residual T2 volume kernels with structural O(n²)→O(1) speedups (18–577× kernel, **38×** Runtime volume script), golden last-value parity vs full path, Runtime on/off parity, flag-gated. No `minimal` path change.
