# Round 4 — Interpreter / Evaluator TA Performance

**Agent:** 4 (INTERPRETER / EVALUATOR TA PERFORMANCE)  
**Date:** 2026-07-29  
**Flag:** `PYNE_TA_INCREMENTAL` (default on; set `0` / `false` / `no` / `off` to disable)

## Scope

Continue bar-mode incremental TA kernels in the expression evaluator:

- `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` — kernels
- `…/basic.py`, `…/common.py`, `…/moving_averages.py` — call sites
- `tests/test_ta_incremental.py` — golden parity
- `backend/runtime.py` — **not edited** (bar-mode flags read only)

Hard constraints held: no na→0 coercion, no whole-script vectorization, no parallel bars, `from __future__ import annotations` on new code.

## Prior art (already incremental)

`sma`, `ema`, `rma`, `wma`, `vwma`, `hma`, `rsi`, `stoch` (%K), `macd`, `cci`, `roc`, `wpr`, `tsi`, `atr`, `tr`, `stdev`, `variance`, `highest`, `lowest`, `rising`, `falling`, `change`, `cum`, `dev`, `median`, `percentrank`, BB (via sma+stdev).

## Remaining full-recompute inventory (ranked)

Corpus frequency (`tests/data/**/*.pine`, main repo) among **non-incremental** call sites:

| Rank | Function | Corpus hits | Cost before | Notes |
| --- | --- | --- | --- | --- |
| 1 | `ta.barssince` | 709 | O(n) list scan; scalar path broken (0/1 only) | High ROI + correctness |
| 2 | `ta.linreg` | 367 | O(period) least-squares / bar | Common in strategies |
| 3 | `ta.vwap` | 267 | **O(n) full re-sum every bar** | Worst asymptotics |
| 4 | `ta.supertrend` | 242 | ATR + mid (partial) | Deferred (state machine) |
| 5 | `ta.dmi` / ADX | 154 | O(n) DM + multi-RMA | Deferred (complex) |
| 6 | `ta.highestbars` / `lowestbars` | 82 / 72 | O(period) argmax | Easy window |
| 7 | `ta.mom` | 75 | O(1) lag (same as change) | Wire-through |
| 8 | `ta.obv` / `mfi` | 64 / 104 | Cumulative / window | Deferred |
| 9 | `ta.swma` | 43 | Fixed 4-sample | Easy |
| 10 | `ta.sar`, pivots, alma, … | lower | Varies | Later rounds |

Also still full-recompute (not this round): `dmi`, `supertrend`, `kc`, `obv`, `mfi`, `sar`, `pivothigh`/`pivotlow`, `valuewhen`, `percentile_*`, `dema`/`tema`/`kama`, `correlation`, `alma`, `mode`, `range`.

## Implemented this round (6 kernels)

| Kernel | Pattern | Call-site key |
| --- | --- | --- |
| `_mom_inc_update` | Delegates to `_change_inc_update` (identical lag) | `("change", slot, period)` via change |
| `_swma_inc_update` | 4-sample deque; weights 1/6, 2/6, 2/6, 1/6 | `("swma", slot)` |
| `_highestbars_inc_update` | Rolling window; argmax → offset | `("highestbars", slot, period)` |
| `_lowestbars_inc_update` | Rolling window; argmin → offset | `("lowestbars", slot, period)` |
| `_vwap_inc_update` | Running `cum_pv` / `cum_v` O(1) | `("vwap", slot)` |
| `_barssince_inc_update` | Scalar state machine (bars since true) | `("barssince", slot)` |
| `_linreg_inc_update` | Rolling window; OLS endpoint O(period) | `("linreg", slot, length)` |

### Call-site notes

- Incremental paths prefer **raw** source args (PineSeries / scalar) so kernels use `_series_last` and avoid `_as_series` materialization where safe (`vwap`, `mom`, `swma`, `linreg`, highest/lowestbars with explicit source).
- `ta.barssince` in bar mode with a **boolean** condition was previously stuck at 0/1. Incremental state matches growing-list full-scan semantics (true→0; never true after *k* bars→*k*−1; true then *d* falses→*d*). This is a correctness fix for Runtime hosts, not just perf.

## Golden tests

File: `tests/test_ta_incremental.py` (Round 4 section)

- `test_incremental_mom_matches_full`
- `test_incremental_swma_matches_full`
- `test_incremental_highestbars_lowestbars_matches_full`
- `test_incremental_vwap_matches_full`
- `test_incremental_barssince_matches_full`
- `test_incremental_linreg_matches_full`
- `test_runtime_round4_incremental_vs_disabled` (Runtime on vs `PYNE_TA_INCREMENTAL=0`; omits barssince because off-path scalar is intentionally weaker)

Tolerance: `rel=1e-9`, `abs=1e-9` (well under 1e-10 class for float OLS / VWAP).

```text
PYTHONPATH=src python -m pytest tests/test_ta_incremental.py -q
# 42 passed
```

## Benchmarks

### Kernel microbench (bar-walk; full = growing prefix; inc = last sample only)

| Function | n | Full | Inc | Speedup |
| --- | ---: | ---: | ---: | ---: |
| mom | 3000 | 20.6 ms | 6.4 ms | **3.2×** |
| swma | 3000 | 24.6 ms | 10.9 ms | **2.3×** |
| highestbars | 3000 | 24.8 ms | 14.3 ms | **1.7×** |
| **vwap** | 3000 | 998 ms | 5.2 ms | **193×** |
| linreg | 3000 | 38.8 ms | 29.8 ms | **1.3×** |
| barssince | 3000 | 9.4 ms | 3.0 ms | **3.1×** |
| mom | 5000 | 42.8 ms | 5.7 ms | **7.5×** |
| swma | 5000 | 48.0 ms | 10.1 ms | **4.7×** |
| highestbars | 5000 | 47.1 ms | 14.0 ms | **3.4×** |
| **vwap** | 5000 | 1669 ms | 7.7 ms | **217×** |
| linreg | 5000 | 71.2 ms | 42.4 ms | **1.7×** |
| barssince | 5000 | 21.6 ms | 4.6 ms | **4.8×** |

### Runtime host (backend `Runtime`, 2000 bars)

| Script | Inc on | Inc off | Speedup |
| --- | ---: | ---: | ---: |
| mom+swma+highestbars+lowestbars+vwap+linreg | 252 ms | 478 ms | **1.90×** |
| vwap+barssince+linreg | 149 ms | 321 ms | **2.16×** |

## Expression-evaluator TA call path (profile notes)

Hot path per bar for a `ta.*` call:

1. Builtin dispatch map (`TechnicalAnalysisMixin._technical_builtin_map`)
2. `_use_incremental_ta()` — **cached** once per evaluator (`_pine_ta_inc_cached`)
3. Arg extract: prefer raw source + `_expect_int(period)`; avoid `_as_series` when incremental
4. `_ta_next_slot()` — call-site index reset by Runtime each bar
5. `_ta_state_bucket()` — dict keyed by `(name, slot, …params)`
6. Kernel: `_series_last` (list / PineSeries `.current` / history[0]) → update state → scalar return

Remaining cost after kernels:

- AST re-walk every bar (intentional Pine semantics)
- Non-incremental TA still materializing `_SERIES_MAX` (256) windows
- Strategy / plot side effects outside this agent

## Remaining highest-ROI backlog

1. **`ta.dmi` / `ta.adx`** — full DM loop + multi-RMA every bar (~154 corpus)
2. **`ta.supertrend`** — stateful bands + ATR (~242)
3. **`ta.obv` / `ta.mfi` / `ta.accdist`** — cumulative / MF windows
4. **`ta.valuewhen`** — high frequency (1167); needs event history ring
5. **`ta.pivothigh` / `pivotlow`** — confirmed pivots with left/right lag
6. **`ta.dema` / `tema`** — nested EMA (compose existing `_ema_inc_update`)
7. **`ta.sar`**, **`ta.kc`**, **`ta.correlation`**, percentiles

## Files touched

| File | Change |
| --- | --- |
| `technical_submodules/core.py` | +7 incremental update methods |
| `technical_submodules/basic.py` | Wire mom/swma/highestbars/lowestbars/vwap/barssince/linreg |
| `technical_submodules/common.py` | Mirror wire for mom/highestbars/lowestbars/barssince |
| `technical_submodules/moving_averages.py` | Wire swma incremental |
| `tests/test_ta_incremental.py` | Round 4 golden + Runtime tests |
| `docs/perf_round4/04_interpreter_ta.md` | This report |

## Definition of done checklist

- [x] Zero correctness loss vs full recompute (golden abs err ≤ 1e-9)
- [x] Flag-gated (`PYNE_TA_INCREMENTAL`, default on)
- [x] 2–5+ new incremental kernels (7)
- [x] Golden tests green (42 / 42)
- [x] Bench before/after documented (n=3000–5000 + Runtime 2000)
- [x] No `backend/runtime.py` edits
- [x] Report at `docs/perf_round4/04_interpreter_ta.md`
