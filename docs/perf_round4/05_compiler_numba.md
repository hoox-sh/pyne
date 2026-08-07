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

# Compile-mode Numba TA — Round 4 (HMA wire + residual O(n) paths)

**Date:** 2026-07-29  
**Scope:** `src/pynescript/compiler/{numba_builtins,compiler}.py` + compiler tests  
**Goal:** finish incomplete round-3 wiring; add 2–5 high-ROI `*_inc` kernels for remaining full recompute emits  

## Environment

- Python / Numba: system Python 3 + Numba 0.65.1 (`PYTHONPATH=src`)
- Workload: synthetic random-walk OHLCV, `n = 5000` (plus strict-rise / sparse-cond worst cases)
- Method: kernel full vs `*_inc` median of 7–21 reps after warm-up; warm `CompiledScript.run` median of 21 after 5 warm-ups
- Parity: full kernel vs `*_inc` (sequential + gap + rewind); compiled vs full ≤ **1e-10**

## Map: full vs incremental (post round 4)

| Category | Emit path | Status |
|----------|-----------|--------|
| sma/ema/rma/wma/rsi/macd/atr/bb | `*_inc` | already |
| stdev/var/sum/cum/vwap/obv/pvt | `*_inc` | already |
| highest/lowest (window) | `*_inc` | already |
| stoch/cci/dev/mfi/corr/hbars/lbars | `*_inc` | already (r2) |
| tsi/vwma/linreg/sar/barssince | `*_inc` | already |
| **hma** | **`numba_hma_inc`** | **wired this round** (kernel existed, emit was full) |
| **math.sum / math.avg** | **`numba_sum_inc` / `numba_sma_inc`** | **wired this round** |
| **ta.max / ta.min** (no length) | **`numba_running_max/min_inc`** | **new + wired** |
| **ta.rising / ta.falling** | **`numba_rising/falling_inc`** | **new + wired** |
| **ta.valuewhen** (const occ) | **`numba_valuewhen_inc`** | **new + wired** |
| change/mom/roc/tr | O(1) full formula | no rebuild needed |
| pivothigh/pivotlow | full O(left+right) | skip (window tiny) |
| alma | full O(length) Gaussian | skip (no cheap slide identity) |
| percentrank / percentile_* | full O(period) / sort | skip (aux state cost) |
| valuewhen (dynamic occ) | full scan fallback | const occ only for ring |

## Profile notes (cold/warm compile vs execute)

| Script | Cold compile (ms) | Warm compile (ms) | Warm run @5k (ms) |
|--------|------------------:|------------------:|------------------:|
| MULTI (hma+sum+max+rising) | ~1500 | **0.017** | **0.456** |
| HMA-20 / HMA-100 | (shared builtins) | ~0.02 | **0.253** (flat vs period) |
| math.sum-500 | | | **0.061** |
| ta.max (running) | | | **0.059** |
| ta.rising-50 | | | **0.033** |

- **Cold compile** dominated by Numba JIT of generated entry (+ first-touch builtins). Unstable across process runs when disk cache is cold/warm.
- **Warm compile** is LRU hash lookup only (~20 µs).
- **Execute** after wiring is linear in bars; HMA no longer scales with period.

## Kernel-level before/after @ n=5000

| Kernel | full (ms) | inc (ms) | Speedup | Notes |
|--------|----------:|---------:|--------:|-------|
| HMA p=9 | 2.71 | 3.64 | 0.7× | fixed-state overhead at tiny period |
| HMA p=50 | 6.74 | 3.62 | **1.9×** | |
| HMA p=100 | 14.0 | 3.53 | **4.0×** | |
| HMA p=200 | 36.3 | 3.75 | **9.7×** | was O(√n·n) nested WMA |
| sum p=20 | 2.28 | 2.62 | 0.9× | overhead at small window |
| sum p=500 | 4.78 | 2.56 | **1.9×** | |
| running_max | 17.4 | 2.45 | **7.1×** | was O(i) per bar → O(n²) script |
| running_min | 19.6 | 2.48 | **7.9×** | |
| rising p=500 (strict rise) | 4.02 | 2.15 | **1.9×** | random walk ~flat (early exit) |
| valuewhen occ=5 (sparse cond) | 12.4 | 2.68 | **4.6×** | dense cond ~flat |

Compiled end-to-end (warm) is far below kernel microbench overhead because the full script entry is one njit loop with inlined state:

| Script | Warm run (ms) @ 5000 |
|--------|---------------------:|
| HMA20 / HMA100 | 0.253 |
| math.sum 500 | 0.061 |
| ta.max | 0.059 |
| rising 50 | 0.033 |
| MULTI | 0.456 |

## Changes

### Files

| File | Change |
|------|--------|
| `src/pynescript/compiler/numba_builtins.py` | `numba_rising_inc`, `numba_falling_inc`, `numba_valuewhen_inc`, `numba_running_max_inc`, `numba_running_min_inc` |
| `src/pynescript/compiler/compiler.py` | wire hma→`hma_inc`+raw series; math_sum/avg→sum/sma_inc; rising/falling/valuewhen/running max-min; `_try_nonneg_int_const` |
| `tests/test_compiler_numba.py` | `TestCompileRound4IncKernels` + update `test_ta_max_min_not_dead_name` |
| `docs/perf_round4/05_compiler_numba.md` | this report |

### Kernel state layouts

| Kernel | State | Complexity (sequential bar) |
|--------|-------|------------------------------|
| `numba_hma_inc` (pre-existing) | 7 floats + `raw[]` series | amortized O(1) multi-stage WMA |
| `numba_rising_inc` | `[streak, last_i]` | **O(1)** |
| `numba_falling_inc` | `[streak, last_i]` | **O(1)** |
| `numba_valuewhen_inc` | `[n_found, head, last_i, hist…]` size `3+occ+1` | **O(1)** ring |
| `numba_running_max_inc` | `[max_val, last_i]` | **O(1)** |
| `numba_running_min_inc` | `[min_val, last_i]` | **O(1)** |

All support catch-up (gap) and rewind (`i < last_i`). Full kernels retained for fallback / direct use. Dynamic `valuewhen` occurrence falls back to full `numba_valuewhen`.

### Compiler emit (surgical)

```python
# ta.hma
st = self._alloc_fixed_state("hma", 7)
raw = f"__hma_raw…_arr"; self.arrays.add(raw)
→ numba_hma_inc(src, length, __bar_idx, st, raw)

# math.sum / math.avg
→ numba_sum_inc / numba_sma_inc + _alloc_fixed_state

# ta.max / ta.min bare
→ numba_running_max_inc / numba_running_min_inc

# ta.rising / ta.falling
→ numba_rising_inc / numba_falling_inc

# ta.valuewhen(cond, src, occ) with const nonneg occ
→ numba_valuewhen_inc(..., st)  # else full
```

## Correctness

### Offline full vs `*_inc`

| Kernel | max abs err | gap/rewind |
|--------|------------:|-----------|
| hma p=9..100 | ≤ ~1e-12 | ok |
| rising / falling | **0** | ok |
| valuewhen occ=0..5 | **0** | ok |
| running_max / min | **0** | ok |
| sum / sma (existing) | ≤ ~1e-11 | ok |

### Compiled MULTI vs full kernels (n=5000)

| Series | max abs err |
|--------|------------:|
| hma(50) | ~8e-13 |
| math.sum(100) | ~1e-11 |
| ta.max | **0** |
| ta.rising(10) | **0** |

Threshold ≤ 1e-10: **pass**.

### Tests

```text
PYTHONPATH=src python3 -m pytest \
  tests/test_compiler_numba.py::TestCompileRound4IncKernels \
  tests/test_compiler_numba.py::TestSprint10MissingNames::test_ta_max_min_not_dead_name \
  tests/test_compiler_objects.py tests/test_compiler_strategy.py -q
# 22 passed

PYTHONPATH=src python3 -m pytest tests/test_compiler_numba.py \
  tests/test_compiler_objects.py tests/test_compiler_strategy.py -q
# 150 passed, 2 failed (pre-existing TestSet03MatrixArrayApis — array_sort_indices /
# matrix_row_col_mutate; unrelated to TA kernels)
```

**Runtime auto/interpret fallback:** untouched (`backend/runtime.py` still compile→interpret on failure).

## Skipped (rationale)

| Target | Why |
|--------|-----|
| `numba_alma` | Gaussian weights re-bind every slide; no O(1) identity without full window buffer + reweight |
| `numba_percentrank` | Rank vs current value forces O(period) comps; fenwick/multiset heavy for modest gain |
| `numba_percentile_nearest_rank` | Sort window every bar; order-stat tree not worth state complexity |
| `numba_pivothigh/low` | Window is left+right (~10); already ~2 ms @ 5k bars full |
| `roc` / `change` | Already O(1) formula |

## Residuals after round 4

1. ALMA / percentrank / percentile — still full (see above).
2. CCI / dev MAD half still O(period) (from round 2).
3. Small-period HMA/sum fixed-state overhead vs full (sub-ms; large-period wins dominate).
4. valuewhen with non-const `occurrence` still full scan.
5. Pre-existing matrix object-mode test failures (out of scope).

## Summary

- **Wired unfinished round-3 work:** HMA → `numba_hma_inc` (**~4–10×** at p≥100; flat ~0.25 ms compiled @ 5k); math.sum/avg → sliding sum/sma.
- **New kernels:** rising/falling streaks, valuewhen ring (const occ), running max/min for bare `ta.max`/`ta.min` (**~7–8×** vs O(n²) full scan).
- **Parity** ≤ 1e-10 (most bit-identical); public APIs unchanged; auto/interpret fallback intact.
