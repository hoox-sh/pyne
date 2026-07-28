# Evaluate residual TA round 3

**Date:** 2026-07-28  
**Scope:** Interpret-mode series materialization (`_as_series`) + residual incremental TA  
**Constraint:** zero correctness loss; `PYNE_TA_INCREMENTAL` honored; no whole-script vectorization / parallel bars / na→0  
**Flag:** `PYNE_TA_INCREMENTAL` (default on in bar mode; `=0` disables)

## Summary

1. **`_as_series`**: same-bar cache for `PineSeries` reverse materialization; only newest `_SERIES_MAX` samples reversed (no full-history reverse then slice). `_series_last` accepts `PineSeries` / `.current` so pure-inc kernels need not force a full chrono list.
2. **New incremental kernels** (call-site state, last-value ≡ full recompute):
   - `ta.hma` — `_hma_inc_update` (half / full / outer WMA windows)
   - `ta.rising` / `ta.falling` — window + delegate to full `_rising`/`_falling`
   - `ta.median` / `ta.percentrank` — period window, O(period log period) / O(period)
3. **Correctness fix (full path):** `_hma` previously assumed `_wma` returned a series list (TypeError). Rewritten as last-value Hull MA matching the numba readiness rule `period + sqrt(period) - 1`.
4. **Regression:** variance / dev / cci incremental paths unchanged; covered by existing + extended Runtime on/off test.

## Changes

| Area | File | Notes |
|---|---|---|
| `_as_series` cache + cap reverse | `technical_submodules/core.py` | `_pine_as_series_cache`: `(len, head, take) → list` |
| `_series_last` | `core.py` | list / `.current` / newest-first `.history[0]` / scalar |
| `_hma_inc_update` etc. | `core.py` | + `_wma_from_window` shared helper |
| Wire hma / rising / falling / median / percentrank | `basic.py`, `moving_averages.py`, `common.py` | behind `_use_incremental_ta()` |
| Full `_hma` fix | `moving_averages.py` | scalar WMA composition |
| Golden tests | `tests/test_ta_incremental.py` | round 3 suite |

## Microbench (this session, 2000 bars)

| Kernel | notes |
|---|---|
| HMA full walk vs `_hma_inc_update` | **~3.7×** (71 ms → 19 ms) |
| `_as_series` cache hit vs miss (5k, PineSeries n=500) | **~17×** (49 ms → 2.9 ms) |
| Runtime minimal | no regression (~35 ms) |
| Runtime `hma+median+percentrank` | ~1.17× vs `PYNE_TA_INCREMENTAL=0` (host OHLCV already chronological; HMA dominates) |

Median/percentrank helper walks are already O(period) on the full path’s last window; ROI is mainly avoiding PineSeries reverse when sources are series wrappers, plus HMA’s nested WMA cost.

## Verify

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py -q --tb=line
```

**Result:** `275 passed` (includes round 3 golden + Runtime on/off for hma/median/percentrank/rising/falling + variance/dev/cci).

## Residual

- Non-inc builtins still materialize chrono lists (cache helps multi-call same bar).
- Cap append-only Runtime lists already handled host-side; further last-scalar-only path for *all* pure-inc call sites could skip `_expect_series` entirely.
- More kernels: linreg, correlation, ADX, etc.
