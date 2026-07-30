# AGENT 03 — Residual incremental TA (interpret)

**AGENT_ID:** 03  
**ROLE:** Residual incremental TA interpret (PERF + CORRECTNESS)  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | `_rma_state_*`, residual `*_inc_update` kernels |
| `…/basic.py` | Wire `dmi`, `supertrend`, `pivothigh`, `pivotlow` |
| `…/common.py` | Wire `adx` |
| `…/moving_averages.py` | Wire `dema`, `tema` |
| `…/oscillators.py` | Wire `valuewhen` |
| `tests/test_ta_incremental.py` | Round 5 golden + Runtime on/off |
| `docs/perf_round5/AGENT_03_ta_incremental.md` | This report |

## 2. Bugs found

| Severity | Issue | Notes |
| --- | --- | --- |
| Low (pre-existing) | Runtime `ta.valuewhen` off-path sees ephemeral 1-bar condition | Full list-walk only has current cond sample; inc ring is correct. Documented; unit golden covers list-walk parity. |
| Info | `basic._builtin_ta_dmi` uses 0-first DM; `_adx` uses nan-first DM | Preserved exactly in separate inc paths. |

No ATR seed/RMA semantic changes.

## 3. Changes (what / why)

Inventory (Round 4 residual still full-history before this pass):

- `ta.dmi` / `ta.adx` — O(n) DM + multi-RMA every bar  
- `ta.supertrend` — full ATR recompute  
- `ta.valuewhen` — full condition scan  
- `ta.pivothigh` / `pivotlow` — full left-window scan  
- `ta.dema` / `tema` — nested full `_ema`  

### New kernels (call-site state, honor `PYNE_TA_INCREMENTAL`)

| Kernel | State key | Semantics |
| --- | --- | --- |
| `_adx_inc_update` | `("adx", slot, period)` | nan-first DM + 4 nested Wilder RMAs; early `len < period` → 0.0 |
| `_dmi_inc_update` | `("dmi", slot, di, adx)` + nested ADX slot | 0-first DM for +DI/-DI; ADX via `_adx_inc_update` |
| `_supertrend_inc_update` | ATR slot via `_atr_inc_update` | Same simplified mid/band/direction as BasicIndicators |
| `_valuewhen_inc_update` | `("valuewhen", slot, occ)` | Ring of last `occ+1` true sources |
| `_pivothigh_inc_update` / `_pivotlow_inc_update` | window + bar count | Left-only local extremum; right gates readiness |
| `_dema_inc_update` / `_tema_inc_update` | nested `_ema_state_step` | Compose existing EMA seed rules |

Helpers: `_rma_state_new` / `_rma_state_step` (slot-free, match `_rma_inc_update`).

## 4. Benchmarks

Micro-bench: bar-walk growing prefix, n=2000, median of 3, CPython 3.x, `PYTHONPATH=src:.`

| Kernel | Full recompute | Incremental | Speedup |
| --- | --- | --- | --- |
| `dema(20)` | 472.61 ms | 10.14 ms | **46.6×** |
| `adx(14)` | 5085.45 ms | 27.85 ms | **182.6×** |
| `dmi(14)` | 8095.58 ms | 36.53 ms | **221.6×** |
| `valuewhen` | 96.66 ms | 10.66 ms | **9.1×** |

Structural win: ADX/DMI drop from O(bars²) full RMA rebuilds to O(1)/bar.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_ta_incremental.py \
  tests/test_ta_indicators_1.py \
  tests/test_ta_indicators_2.py -q --tb=line
# → 97 passed
```

New goldens: dema, tema, valuewhen, pivothigh/low, adx, dmi, supertrend + `test_runtime_round5_incremental_vs_disabled`.

## 6. Residual risks / follow-ups

1. **True TV supertrend** — current oracle is simplified (no band ratchet state machine); inc matches that oracle only.  
2. **Pivots** — left-only confirmation (right lag not applied); inc matches current builtin.  
3. **valuewhen Runtime** — host should feed multi-bar condition history (or always use inc) so off-path matches; not fixed here.  
4. **common.py dmi/supertrend** — MRO prefers BasicIndicators; common variants still full-history if ever selected.  
5. Still full-history (out of this priority list): `kc`, `obv`, `mfi`, `sar`, `percentile_*`, `kama`, `correlation`, `alma`, `mode`, `range`.

## 7. Out of scope / did not touch

- ATR EMA→RMA re-baseline  
- Dispatch / `_as_series` plumbing (agents 01–02)  
- Numba `*_inc` kernels (agent 06)  
- Grammar / generated code  
- Commit / push  
