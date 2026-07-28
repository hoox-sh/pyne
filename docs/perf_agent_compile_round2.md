# Compile-mode Numba TA — Round 2 (incremental kernels)

**Date:** 2026-07-28  
**Scope:** remaining non-incremental TA kernels in `numba_builtins.py` + surgical compiler emit wiring  
**Goal:** speed up sequential-bar Numba execution without correctness loss  

## Environment

- Python / Numba: repo `.venv` (Numba 0.65.1, NumPy 2.4.6)
- Workload: synthetic random-walk OHLCV, `n = 5000`
- Method: warm `CompiledScript.run` median of 15–21 reps after 5 warm-up runs
- Parity: full kernel vs `*_inc` sequential + gap/rewind; end-to-end compiled vs full

## Baseline (before, full recompute each bar)

| Script | period | Run median (ms) @ n=5000 |
|--------|-------:|-------------------------:|
| CCI | 20 | 0.223 |
| MFI | 20 | 1.441 |
| HBARS (highest+lowest) | 20 | 0.341 |
| CORR | 20 | 0.540 |
| DEV | 20 | 0.168 |
| percentrank | 20 | 0.152 |
| SMA (ref, already `_inc`) | 20 | 0.034 |
| CCI | 100 | 1.049 |
| MFI | 100 | 5.613 |
| HBARS | 100 | 0.960 |
| CORR | 100 | 1.877 |
| DEV | 100 | 0.977 |
| CCI | 500 | 4.455 |
| MFI | 500 | 21.838 |
| HBARS | 500 | 3.286 |
| CORR | 500 | 7.561 |
| DEV | 500 | 4.395 |

Clear **O(period)** scaling on MFI / CORR / HBARS / CCI / DEV.

## After (wired `*_inc`)

| Script | period | After (ms) | Before (ms) | Speedup |
|--------|-------:|-----------:|------------:|--------:|
| CCI | 20 | 0.273 | 0.223 | ~0.8× (overhead) |
| MFI | 20 | 0.331 | 1.441 | **4.4×** |
| HBARS | 20 | 0.230 | 0.341 | **1.5×** |
| CORR | 20 | 0.182 | 0.540 | **3.0×** |
| DEV | 20 | 0.215 | 0.168 | ~0.8× (overhead) |
| CCI | 100 | 0.706 | 1.049 | **1.5×** |
| MFI | 100 | 0.370 | 5.613 | **15×** |
| HBARS | 100 | 0.244 | 0.960 | **3.9×** |
| CORR | 100 | 0.190 | 1.877 | **9.9×** |
| DEV | 100 | 0.695 | 0.977 | **1.4×** |
| CCI | 500 | 2.85 | 4.46 | **1.6×** |
| MFI | 500 | 0.338 | 21.8 | **65×** |
| HBARS | 500 | 0.308 | 3.29 | **11×** |
| CORR | 500 | 0.193 | 7.56 | **39×** |
| DEV | 500 | 2.96 | 4.40 | **1.5×** |

**MFI** and **correlation** are effectively **O(1)** per bar (flat vs period).  
**highestbars/lowestbars** are amortized O(1) with occasional O(window) rescans.  
**CCI / dev** keep an O(period) MAD scan (mean is sliding O(1)); wins show at larger periods; tiny periods pay fixed-state overhead.

## Changes

### Files

| File | Change |
|------|--------|
| `src/pynescript/compiler/numba_builtins.py` | Added `numba_cci_inc`, `numba_dev_inc`, `numba_mfi_inc`, `numba_highestbars_inc`, `numba_lowestbars_inc`, `numba_correlation_inc` |
| `src/pynescript/compiler/compiler.py` | Surgical emit: `ta_cci`, `ta_dev`, `ta_mfi`, `ta_highestbars`, `ta_lowestbars`, `ta_correlation` → `*_inc` + `_alloc_fixed_state` |
| `docs/perf_agent_compile_round2.md` | This report |

### Kernel state layouts

| Kernel | State | Complexity (sequential bar) |
|--------|-------|------------------------------|
| `numba_cci_inc` | `[sum, last_i]` | O(1) mean + **O(period)** MAD |
| `numba_dev_inc` | `[sum, last_i]` | same as CCI MAD half |
| `numba_mfi_inc` | `[pos, neg, last_i]` | **O(1)** sliding signed money flow |
| `numba_highestbars_inc` | `[max_val, max_idx, last_i]` | amortized O(1); ties → most recent |
| `numba_lowestbars_inc` | `[min_val, min_idx, last_i]` | amortized O(1); ties → most recent |
| `numba_correlation_inc` | `[sa, sb, saa, sbb, sab, last_i]` | **O(1)** sliding Pearson sums |

All support catch-up (gap advance) and rewind (reset when `i < last_i`), matching existing `numba_*_inc` patterns. Full kernels remain for direct/fallback use.

### Skipped (with rationale)

| Target | Why skipped |
|--------|-------------|
| `numba_percentrank` | Rank vs `arr[i]` forces O(period) comparisons every bar; no cheap sliding structure in Numba without large aux state. Left full. |
| `numba_hma` | Nested WMAs; real win needs multi-buffer state; out of scope / low ROI vs size. |

**Not done (per constraints):** no bare `_ARRAY_METHODS` remapping for `sum`/`variance`; no large unrelated compiler rewrites.

## Correctness

### Offline full vs `*_inc` (random series, n=800)

| Kernel | max abs err | notes |
|--------|------------:|-------|
| cci | ~2e-12 | + rewind/gap OK |
| dev | ~2e-14 | |
| mfi | ~6e-14 | p=14 and p=100 |
| highestbars | **0** (bit-identical) | |
| lowestbars | **0** (bit-identical) | |
| correlation | ~1e-12 | p=20 and p=100 |

Threshold: ≤ 1e-10 (preferred bit-identical where possible). **All pass.**

### End-to-end compiled script vs full kernels (n=500)

| Indicator | max abs err |
|-----------|------------:|
| ta.cci(close,20) | ~5e-12 |
| ta.mfi(14) | ~7e-14 |
| ta.highestbars / lowestbars | **0** |
| ta.correlation(close,open,20) | ~6e-12 |
| ta.dev(close,20) | ~3e-14 |

### Tests

```text
.venv/bin/python -m pytest tests/test_compiler_numba.py \
  tests/test_compiler_objects.py tests/test_compiler_strategy.py -q --tb=line
# 110 passed in ~34s
```

## Residuals / next opportunities

1. **CCI / dev MAD** still O(period). True O(1) MAD needs order-statistic structure (heavy). Optional: accept window O(period) only; already ~1.5× at p=500.
2. **percentrank** — skip unless a fenwick/sorted-window approach is justified.
3. **Small-period overhead** — p=20 CCI/DEV slightly slower than full due to state + catch-up loop; still sub-ms @ 5000 bars. Could dual-emit full for tiny constant periods (not done; keeps emit simple).
4. **HMA** — still full recompute; only worth multi-stage WMA state if HMA shows up hot in profiles.
5. Already incremental (unchanged): sma/ema/rma/rsi/macd/atr/cum/vwap/obv/stdev/var/bb/tsi/highest/lowest/vwma/stoch/wma/barssince/linreg/sar.

## Summary

Largest wins: **MFI (~4–65×)** and **correlation (~3–39×)** via true sliding sums; **highestbars/lowestbars (~1.5–11×)** via argmax/argmin index state; modest **CCI/dev (~1.4–1.6×)** at large windows. Zero correctness loss vs full kernels; public APIs unchanged.
