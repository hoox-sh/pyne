# AGENT 04 — T2 Residual incremental TA (bb + nested full paths)

**AGENT_ID:** 04  
**ROLE:** T2 residual incremental TA — interpret (PERF + CORRECTNESS)  
**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Date:** 2026-08-02

## 1. Scope & files

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | New kernels: `_bb_inc_update`, `_kama_inc_update`, `_cmo_inc_update`, `_stochrsi_inc_update` |
| `…/moving_averages.py` | Wire `ta.kama` behind `_use_incremental_ta` + last-sample |
| `…/volatility.py` | Wire `ta.cmo`, `ta.bb`/`bbw` last-sample + `_bb_inc_update`; stochrsi dual path; **bbw unpack fix** |
| `…/basic.py` | `ta.bb` → `_bb_inc_update` when incremental |
| `…/advanced.py` | Wire `ta.stochrsi` (MRO owner) to `_stochrsi_inc_update` |
| `…/oscillators.py` | Wire stochrsi dual path (non-MRO safety) |
| `tests/test_ta_incremental.py` | Round 7 goldens + parse-cache isolation fixture |
| `docs/perf_round7/AGENT_04_ta_incremental.md` | This report |

**Owns (per PROMPT):** residual full-history / nested full `_sma`/`_ema` paths for heavy kernels.  
**Does not:** ATR EMA→Wilder (F1); TV supertrend ratchet; silent `na→0`; grammar; volume `obv` (left residual).

## 2. Bugs found

| Severity | Issue | Notes |
| --- | --- | --- |
| Med (correctness) | `ta.bbw` unpacked BB as `(middle, upper, lower)` but `_bollinger_bands` returns `(upper, middle, lower)` | Fixed to `(upper, middle, lower)`; width is now truly `(upper-lower)/middle` |
| Info | Concurrent Agent 05 parse cache shares AST by identity; second `Runtime.run` of same source → empty series | Test fixture clears cache before each `Runtime.run` (not a TA bug) |
| Info | `ta.bb` math already used nested sma/stdev inc (R1–R3); still full reverse materialize on Volatility path | Last-sample + dedicated `_bb_inc_update` |

## 3. Changes (what / why)

R6 left true full-history rebuilds: **`kama`**, **`stochrsi`**, window-only **`cmo`**, and incomplete **bb/bbw** last-sample hygiene.

### New kernels (call-site state, honor `PYNE_TA_INCREMENTAL`)

| Kernel | State key | Complexity | Semantics |
| --- | --- | --- | --- |
| `_bb_inc_update` | nested SMA + stdev slots | O(1)/bar after warm | upper/middle/lower ≡ `_bollinger_bands` |
| `_kama_inc_update` | `("kama", slot, length, fast, slow)` price ring + running \|Δ\| sum | O(1)/bar | Seed at bar `length`; first value at `length+1` samples — matches full rebuild last value |
| `_cmo_inc_update` | `("cmo", slot, length)` ring of length+1 | O(length)/bar | Same up/down window; na pairs skipped |
| `_stochrsi_inc_update` | `("stochrsi", slot, rsi_len, stoch_len)` | O(rsi_length)/bar | Simple (non-Wilder) RSI window + stoch ring; signal `0.33*x+0.67*prev` in **call-site** state (not shared instance attr) |

Builtins use `_as_series_or_raw(..., last_sample_ok=True)` / `_context_source` on the inc path so Runtime PineSeries avoid reverse materialization.

**Flag:** existing `PYNE_TA_INCREMENTAL=0` disables all of the above (default on in bar mode).

## 4. Benchmarks

Micro-bench: bar-walk growing prefix, n=2000, median of 3, `PYTHONPATH=src:.`, CPython 3.14.

| Kernel | Full recompute | Incremental | Speedup |
| --- | ---: | ---: | ---: |
| `kama(10)` | 1099 ms | 9.1 ms | **~121×** |
| `stochrsi(14,14)` | 10196 ms | 14.2 ms | **~717×** |
| `bb(20)` (sma+stdev full vs `_bb_inc_update`) | 2458 ms | 11.3 ms | **~217×** |
| `cmo(14)` | 13.5 ms | 11.4 ms | **~1.2×** |

### Kernel notes

- **kama / stochrsi** were true full-history rebuilds each bar → structural O(bars²) → O(1)/O(period). Primary T2 wins.
- **bb** nested path already incremental in bar mode since earlier rounds; microbench contrasts pure full `_sma`+`_stdev` vs dedicated inc. Runtime last-sample hygiene closes residual reverse tax on Volatility path.
- **cmo** was already O(period) window; gains are last-sample / ring hygiene (small microbench delta, real on PineSeries hosts).

No claim that `bench_pipeline.py` `minimal`/`ta_combo` change materially (those scripts do not call kama/stochrsi/cmo).

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ta_incremental.py -q --tb=line
# → 88 passed
```

New / extended cases:

- `test_incremental_kama_matches_full` (+ dual call sites)
- `test_incremental_cmo_matches_full`
- `test_incremental_bb_inc_update_matches_full`
- `test_incremental_bbw_matches_full`
- `test_incremental_stochrsi_matches_full`
- `test_runtime_round7_t2_incremental_vs_disabled` (kama/cmo/bb/bbw/sma)
- Autouse `_isolate_parse_cache` so dual-run Runtime goldens stay green with process parse LRU

## 6. Residual risks

1. **stochrsi oracle** — uses simple avg gain/loss RSI (not Wilder `ta.rsi`). Inc matches that quirky full path, not TV StochRSI-on-RMA.
2. **bbw unpack fix** — changes values vs previous swapped-tuple behavior. Inc on/off still match each other; TV-aligned width is the intended formula.
3. **obv / mode / range** — still full-history leftovers (out of this priority list).
4. **Parse-cache mutation** — product Runtime multi-run of identical source needs `clear_parse_cache()` or non-mutating eval (Agent 05 residual).

## 7. Out of scope / did not touch

- ATR EMA→Wilder re-baseline (F1)  
- TV supertrend band ratchet  
- Numba `*_inc` ports  
- Grammar / generated code  
- Commit / push  

## 8. Verdict

**win** — shipped residual T2 kernels with large structural speedups on kama/stochrsi/bb full paths, golden parity, Runtime on/off parity for kama/cmo/bb/bbw, flag-gated.
