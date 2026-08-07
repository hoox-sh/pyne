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

# Compile-mode Numba TA — Round 3 (HMA + math_sum residuals)

**Date:** 2026-07-28  
**Scope:** remaining residual full recompute paths in `numba_builtins.py` + surgical compiler emit  
**Goal:** finish high-ROI incremental kernels without correctness loss  

## Environment

- Python / Numba: repo `.venv` (Numba 0.65.1)
- Workload: synthetic random-walk OHLCV, `n = 5000`
- Method: warm `CompiledScript.run` median of 21 reps after 5 warm-ups; kernel-level full recompute as “before” proxy for HMA/sum
- Parity: full kernel vs `*_inc` sequential + gap/rewind; compiled vs full

## Targets

| Target | Decision |
|--------|----------|
| **HMA** | **Implemented** multi-stage WMA_inc + intermediate `raw` series buffer |
| **math_sum** | **Wired** → `numba_sum_inc` (same as `ta.sum`) |
| **math_avg** | **Wired** → `numba_sma_inc` (bonus, same as `ta.sma`) |
| **percentrank** | **Skipped** — see rationale |
| **percentile_nearest_rank** | **Skipped** — sort-heavy; no cheap sliding structure |
| **roc** | Already O(1) full (`arr[i]-arr[i-length]`); no rebuild |

## Baseline (before)

Kernel-level full recompute each bar (same cost as pre-wire compiled emit):

| Script / kernel | period | Run median (ms) @ n=5000 |
|-----------------|-------:|-------------------------:|
| HMA full | 9 | 2.76 |
| HMA full | 20 | 3.38 |
| HMA full | 50 | 5.97 |
| HMA full | 100 | 12.61 |
| HMA full | 200 | 29.36 |
| sum full | 5 | 2.23 |
| sum full | 20 | 2.34 |
| sum full | 100 | 2.69 |
| sum full | 500 | 4.39 |
| percentrank (compiled, unchanged) | 20+100 | 0.57 |

HMA full is **O(√n · n)** per bar (nested WMAs over `sqrt(length)` ends) → clear period scaling.

## After (wired)

| Script | period | After (ms) | Before (ms) | Speedup |
|--------|-------:|-----------:|------------:|--------:|
| HMA compiled | 9 | 0.225 | 2.76 | **12×** |
| HMA compiled | 20 | 0.226 | 3.38 | **15×** |
| HMA compiled | 50 | 0.221 | 5.97 | **27×** |
| HMA compiled | 100 | 0.234 | 12.61 | **54×** |
| HMA compiled | 200 | 0.219 | 29.36 | **134×** |
| math.sum compiled | 5–500 | 0.032 | 2.2–4.4 | **~70–140×** |

HMA after is **flat vs period** (~0.22 ms @ 5000 bars). math.sum matches existing `ta.sum` O(1) path.

## Changes

### Files

| File | Change |
|------|--------|
| `src/pynescript/compiler/numba_builtins.py` | `numba_hma_inc`, helper `_wma_window_sums` |
| `src/pynescript/compiler/compiler.py` | `ta_hma` → `numba_hma_inc` + fixed state + raw series; `math_sum` → `numba_sum_inc`; `math_avg` → `numba_sma_inc` |
| `tests/test_compiler_numba.py` | `TestCompileRound3HmaMathSum` |
| `docs/perf_agent_compile_round3.md` | This report |

### Kernel state — `numba_hma_inc`

```
st[7]: [half_s, half_ws, full_s, full_ws, outer_s, outer_ws, last_i]
raw[]: full-length intermediate series  2*WMA(half) - WMA(full)
```

- Half / full / outer WMA advance with the same O(1) sliding identity as `numba_wma_inc`.
- Intermediate `raw[j]` written each bar so the outer WMA can drop the leaving sample.
- **Reseed** half/full/outer from the window every `length` bars (amortized O(1)) to bound multi-stage float drift.
- Catch-up (gap) and rewind (`i < last_i`) match other `*_inc` kernels.
- Full `numba_hma` retained for direct/fallback use.

### Compiler emit (surgical)

```python
# ta.hma
st = self._alloc_fixed_state("hma", 7)
raw = f"__hma_raw{...}_arr"; self.arrays.add(raw)
→ numba_hma_inc(src, length, __bar_idx, st, raw)

# math.sum / math.avg (series, length)
→ numba_sum_inc / numba_sma_inc + _alloc_fixed_state
```

**Not done:** no bare `_ARRAY_METHODS` remapping for `sum`/`variance`.

## Skipped (with rationale)

| Target | Why skipped |
|--------|-------------|
| `numba_percentrank` | Already ~O(period) integer comparisons only; compiled p=20+100 is **0.57 ms** @ 5k bars. Sliding fenwick / sorted multiset needs large aux state in Numba for a modest win. Left full. |
| `numba_percentile_nearest_rank` | Requires sorted window (copy + sort) every bar; order-statistic tree is high state/complexity for rare call sites. |
| `numba_roc` | Already O(1) full formula; nothing to incrementalize. |
| `numba_alma` | Gaussian weights over full window; no simple O(1) identity without storing the whole window of weights×values. Out of ROI for this round. |

## Correctness

### Offline full vs `numba_hma_inc` (random series, n=5000)

| period | max abs err |
|-------:|------------:|
| 9 | ~2.7e-13 |
| 20 | ~3.6e-13 |
| 50 | ~8.2e-13 |
| 100 | ~1.3e-12 |
| 200 | ~1.1e-12 |

Gap jump to last bar + rewind mid-series: same order. Threshold ≤ 1e-10: **pass**.

### math.sum / sum_inc

Matches existing `numba_sum_inc` (already used by `ta.sum`). Typical max abs err ≤ 1e-11 at moderate periods; p=500 float drift ~2e-10 on large running sums (pre-existing sum_inc behavior).

### Tests

```text
.venv/bin/python -m pytest tests/test_compiler_numba.py \
  tests/test_compiler_objects.py tests/test_compiler_strategy.py -q --tb=line
# 112 passed (110 prior + 2 new)
```

## Residuals after round 3

1. **percentrank / percentile_*** — still full; only worth it if profiles show them hot at large windows.
2. **ALMA** — still O(length) Gaussian window.
3. **CCI / dev MAD** — still O(period) MAD half (from round 2).
4. **sum_inc float drift** at very large periods / long runs — optional periodic reseed like HMA (not done; ta.sum already shipped this way).

## Summary

Real wins this round:

- **HMA**: multi-stage incremental WMA + raw buffer → **~12–134×** vs full nested recompute, flat ~0.22 ms @ 5000 bars, max abs err ~1e-12.
- **math.sum / math.avg**: aligned with `ta.sum` / `ta.sma` incremental paths.
- **percentrank / percentile / roc**: documented skip / already O(1).

Zero intentional correctness loss; public APIs unchanged.
