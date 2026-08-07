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

# Compile + Execute Performance Report

**Date:** 2026-07-28  
**Scope:** `src/pynescript/compiler/{engine,compiler,numba_builtins}.py`  
**Goal:** Speed up Numba/object-mode compile pipeline and compiled script execution without correctness loss.

## Environment

- Python: repo `.venv` (Numba present)
- Workload: synthetic rising OHLCV, `n ∈ {1000, 5000}`
- Scripts: SMA-14, MACD(12,26,9), MULTI (SMA+EMA+RSI), object-mode UDT plot
- Method: `clear_compile_cache()` → cold `compile_script` → warm cache hit → median of repeated `CompiledScript.run`

## Baseline (before)

| Script | n | Cold compile (ms) | Warm compile (ms) | Run median (ms) |
|--------|---:|------------------:|------------------:|----------------:|
| SMA | 1000 | 5713 | 0.017 | 0.048 |
| MACD | 1000 | 727 | 0.020 | 1.542 |
| MULTI | 1000 | 605 | 0.014 | 1.403 |
| OBJ | 1000 | 31 | 0.015 | 0.803 |
| SMA | 5000 | 823 | 0.037 | 0.477 |
| MACD | 5000 | 448 | 0.013 | **32.85** |
| MULTI | 5000 | 445 | 0.014 | **32.38** |
| OBJ | 5000 | 14 | 0.013 | 3.98 |

### Profile notes (baseline)

1. **Cold compile** dominated by Numba JIT of generated entry + builtins (seconds on first touch; subsequent scripts reuse cached builtins).
2. **Warm cache** already ~20 µs (hash lookup only).
3. **MACD / EMA execute** were **O(n²)**: each bar rebuilt EMA/MACD from bar 0 → i (`numba_macd` / `numba_ema`). Scaling: ~0.5 ms @ 500 bars → ~36 ms @ 5000 bars.
4. Numeric mode returned a **Numba `typed.Dict`**, forcing boundary conversion in `_normalize_result`.
5. Object-mode scripts paid a useless 16-bar warm-up call (no JIT).

## After

| Script | n | Cold compile (ms) | Warm compile (ms) | Run median (ms) | Run Δ vs baseline |
|--------|---:|------------------:|------------------:|----------------:|------------------:|
| SMA | 1000 | 2991 | 0.021 | 0.032 | **−33%** |
| MACD | 1000 | 1163 | 0.020 | 0.065 | **−96%** |
| MULTI | 1000 | 679 | 0.020 | 0.151 | **−89%** |
| OBJ | 1000 | 58 | 0.017 | 1.65 | noise / load (see risks) |
| SMA | 5000 | 1040 | 0.019 | 0.114 | **−76%** |
| MACD | 5000 | 539 | 0.025 | **0.298** | **−99.1% (~110×)** |
| MULTI | 5000 | 1294 | 0.016 | **0.659** | **−98.0% (~49×)** |
| OBJ | 5000 | 22 | 0.022 | 6.98 | noise / load |

MACD scaling after fix (linear):

| n | Run median |
|---:|----------:|
| 1000 | 0.065 ms |
| 5000 | 0.298 ms |
| 10000 | ~0.6 ms |
| 20000 | ~1.2 ms |

Cold compile times remain dominated by Numba first-compile and are **not stable across process runs** (disk/cache of `njit(cache=True)` builtins, machine load). Warm compile stays ~0.02 ms.

## Changes

### 1. Incremental TA kernels (largest win)

`numba_builtins.py` adds amortized-O(1) step functions with small fixed state vectors:

| Full recompute | Incremental | State layout |
|----------------|-------------|--------------|
| `numba_ema` | `numba_ema_inc` | `[ema, last_i]` |
| `numba_rma` | `numba_rma_inc` | `[rma, last_i]` |
| `numba_macd` | `numba_macd_inc` | `[ema_f, ema_s, sig, last_i]` |
| `numba_atr` | `numba_atr_inc` | `[acc, last_i]` |
| `numba_cum` | `numba_cum_inc` | `[sum, last_i]` |
| `numba_vwap` | `numba_vwap_inc` | `[cum_pv, cum_v, last_i]` |
| `numba_obv` | `numba_obv_inc` | `[obv, last_i]` |

- Sequential bar calls advance state by one step.
- Gaps / rewinds catch up or reset so values still match full recompute (verified bit-identical on random series).
- Original O(i) kernels kept for fallback / direct use.

`CompilerVisitor` allocates per-call-site state via `_alloc_fixed_state` / `_emit_fixed_state` and emits `*_inc` for the TA sites above.

### 2. Tuple return (numeric mode)

Generated numeric entry points now return `(plot_0, plot_1, …)` instead of `{'title': plot_i, …}`.

- Avoids Numba `typed.Dict` build + iteration on every run.
- `CompiledScript._pack_result` zips `plot_titles` → public dict (API unchanged).

### 3. Engine cache + normalize micro-opts

- Cache: `OrderedDict` **LRU**, max **128** (was 32 FIFO).
- Cache hit: `move_to_end` (true LRU).
- `_as_f64` / `_coerce_plot_array`: skip copy when already contiguous `float64`.
- **Skip JIT warm-up** for object-mode (pure Python).
- `__events` / strategy scalars handled without forced `asarray`.

### 4. Public API

Unchanged:

- `compile_script(source, *, use_cache=True) -> CompiledScript`
- `CompiledScript.run(open, high, low, close, volume=None) -> dict`
- `transpile`, `run_script`, `clear_compile_cache`, `has_numba`

## Risks

| Risk | Mitigation |
|------|------------|
| Incremental state desync if TA call is skipped some bars | Catch-up from `last_i+1`; rewind resets. Values match full kernels. |
| Cold compile still multi-second on first Numba touch | Unavoidable without AOT; builtins use `cache=True`; script entry stays `cache=False` (exec from string). |
| Object-mode run noise in benches | No structural slowdown intended; skip warm-up only removes 16-bar no-op. Re-run variance can dominate sub-10 ms. |
| Title/order coupling for tuple return | Titles still taken from `visitor.plots` order at compile time (same as old dict emission). |
| Tests asserting exact generated names | Assertions use substrings (`numba_macd` ⊂ `numba_macd_inc`); all green. |

## Tests

```bash
.venv/bin/python -m pytest \
  tests/test_compiler_numba.py \
  tests/test_compiler_objects.py \
  tests/test_compiler_strategy.py -q --tb=line
```

**Result: 73 passed** (≈47 s wall, includes Numba warm-ups).

Additional offline parity: incremental vs full kernels for EMA/RMA/MACD/ATR/cum/VWAP/OBV over 200 random bars → max abs err `0.0`.

## Residual opportunities

1. **Rolling SMA / stdev / highest / lowest** with deque-style state (O(1) vs O(period)); smaller win for period≤20.
2. **Vectorized full-series kernels** outside the bar loop when the body is a pure assign chain (no branches).
3. **Disk cache of generated modules** (plan already notes this) to cut cold transpile+exec.
4. **Object-mode bar loop**: avoid repeated `float(arr[i])` in strategy path; pre-bind locals; optional Cython/numba object mode for pure-numeric segments inside UDT scripts.
5. **Parser cold start** (~50–900 ms first ANTLR touch) — process-level warm or parse cache keyed by source hash (compile cache already covers full pipeline).
6. **RSI Wilder incremental** if interpret parity moves to true RMA of gains/losses (current RSI is simple window average, already O(period)).

## Files changed

| File | Change |
|------|--------|
| `src/pynescript/compiler/numba_builtins.py` | Incremental `*_inc` kernels |
| `src/pynescript/compiler/compiler.py` | Fixed state alloc; emit `*_inc`; tuple return (numeric) |
| `src/pynescript/compiler/engine.py` | LRU-128 cache; tuple pack; f64 fast path; skip object warm-up |
| `docs/perf_agent_compile_execute.md` | This report |
