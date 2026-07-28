# Runtime evaluate / interpret performance (agent report)

**Date:** 2026-07-28  
**Scope:** AST evaluator bar-loop + incremental `ta.*` (interpret mode)  
**Constraint:** zero correctness loss; no whole-script vectorization; no `na`→0  
**Flag:** `PYNE_TA_INCREMENTAL` (default on in bar mode; `=0` disables)

## Summary

Extended Phase 2.1 incremental TA beyond sma/ema/rma/rsi/macd/atr to cover the next hot kernels: **stdev, Bollinger bands (full), highest, lowest, wma, tr, change**. Also fixed `ta.bb` to take **chronological** series via `_as_series` (PineSeries history is newest-first; reverse order made incremental last-sample permanently wrong).

Result: **≥3×** on stdev/BB Runtime scripts, **~5×** on multi-indicator combo, **~19×** microbench on stdev, **~270×** microbench on full BB vs pure full-recompute. Minimal script **no regression**.

## Baseline (this session, before 2.1c)

Runtime host: `backend.runtime.Runtime`, 2000 synthetic bars, `PYTHONPATH=src`.

| Script | inc=1 avg_ms | inc=0 avg_ms | notes |
|---|---:|---:|---|
| minimal | 93.6 | 94.1 | ~1.0× |
| ta_stdev_bb | 934.3 | 4776.6 | BB middle already incremental; stdev still full `statistics.stdev` |
| ta_hl_wma | 799.8 | 1299.4 | window/lowest/wma/change/tr full path |
| ta_combo2 | 1703.4 | 7554.1 | sma/ema/rsi + bb + highest + stdev + wma |

cProfile on `ta_stdev_bb` (inc=1, 1500 bars): **~37%** of time in `core._stdev` → `statistics.stdev` / `_ss` / fractions exact-ratio path.

Microbench (2000 bars, pure helper walk, before):

| Kernel | ms |
|---|---:|
| sma_inc | 11.8 |
| stdev_full | 233.9 |
| bb_full | 4027 |
| bb_partial_inc (sma only) | 238 |

## After (Phase 2.1c)

Runtime, 2000 bars, median of 5 iters (2 warmup):

| Script | inc=1 med_ms | inc=0 med_ms | speedup |
|---|---:|---:|---:|
| minimal | 97.6 | 100.1 | **1.03×** (no regression) |
| ta_stdev_bb | 591.8 | 1908.4 | **3.22×** |
| ta_hl_wma | 855.3 | 1600.0 | **1.87×** |
| ta_combo2 | 710.6 | 3719.7 | **5.23×** |
| ta_sma | 94.6 | 617.1 | **6.52×** |

vs previous inc=1 baseline (same machine/scripts):

| Script | before 2.1c inc=1 | after | gain |
|---|---:|---:|---:|
| ta_stdev_bb | 934 ms | 592 ms | **~1.58×** further |
| ta_combo2 | 1703 ms | 711 ms | **~2.4×** further |

Microbench after:

| Kernel | ms | vs full |
|---|---:|---|
| stdev_inc | 8.6 | ~19× vs 162 |
| bb_inc (sma+stdev) | 11.6 | ~270× vs 3144 |
| highest+lowest+wma inc | 33.8 | — |

## Changes

### Flagged (behind `PYNE_TA_INCREMENTAL`, bar mode only)

| Function | Helper | Notes |
|---|---|---|
| `ta.stdev` | `_stdev_inc_update` | Running sum/sumsq, sample stdev (ddof=1) |
| `ta.bb` / `_bollinger_bands` | SMA + stdev inc slots | Both call-sites; order fixed |
| `ta.highest` / `ta.lowest` | `_highest_inc_update` / `_lowest_inc_update` | Period window deque |
| `ta.wma` | `_wma_inc_update` | Matches na-weight rules of full `_wma` |
| `ta.tr` | `_tr_inc_update` | First bar `None` (matches full `_tr`) |
| `ta.change` | `_change_inc_update` | Window of length+1 |
| `ta.sma` (existing) | `_sma_inc_update` | **Also** O(1) running sum/count (was O(period) filter) |

### Always-on correctness fix

- `BasicIndicators._builtin_ta_bb`: use `_as_series` (chronological) instead of `_expect_list` (newest-first PineSeries history). Required for incremental last-sample; also aligns full-path BB with chronological semantics when source is a `PineSeries`.
- `AdvancedIndicators._builtin_ta_stdev` (MRO winner): delegate to `_expect_series` + `_stdev` / `_stdev_inc_update` instead of wrapping non-list args as a single-element list (which made Runtime `ta.stdev(close, n)` always na).

### Tests

- Extended `tests/test_ta_incremental.py`: golden parity for stdev, highest, lowest, wma, tr, change + Runtime on/off for bb/stdev/hl/wma/change/tr.
- `tests/test_evaluator.py::test_evaluator_ta_tr`: accept `None` or nan for first-bar TR (implementation uses `None`).

## Test results

```text
$ PYTHONPATH=src .venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py -q --tb=line
258 passed in 3.93s
```

## Residual opportunities

1. **Series materialization** — even with incremental kernels, `_as_series` / `_context_series` still cap/copy up to `_SERIES_MAX` (256) per call when history is a PineSeries. Bar-mode could pass last scalar only for pure-inc builtins.
2. **Cap append-only `current_series` in Runtime** (plan 2.3) — avoid unbounded list growth and repeated `[-max:]` slices.
3. **More incremental TA** — stoch, CCI, ADX, VWMA, HMA, rolling corr; same call-site pattern.
4. **AST / call dispatch** — `visit_Call` + `_call_builtin` still dominate non-TA time (minimal ~50 µs/bar). Cache builtin map lookups further if needed.
5. **Plotting path** — `_builtin_plot` shows up in profiles; lighter registries for corpus/success-only (plan 2.5).
6. **Ring buffer reindex** (plan 2.2) — O(1) lookback without reverse copies for non-incremental consumers.

## Files changed

| File | Change |
|---|---|
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | New `_*_inc_update` helpers; SMA running sum |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/basic.py` | Wire highest/lowest/wma/stdev/change/tr; BB `_as_series` |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/volatility.py` | Wire stdev/tr; BB uses stdev_inc |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/moving_averages.py` | Wire wma_inc |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/advanced.py` | Fix stdev MRO path; drop unused `statistics` import |
| `tests/test_ta_incremental.py` | Golden + Runtime parity for new kernels |
| `tests/test_evaluator.py` | TR first-bar na assertion |
| `docs/perf_agent_evaluate.md` | This report |

## How to verify

```bash
cd /path/to/worktree
PYTHONPATH=src python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py -q --tb=line
# Disable incremental:
PYNE_TA_INCREMENTAL=0 PYTHONPATH=src python -m pytest tests/test_ta_incremental.py -q
```
