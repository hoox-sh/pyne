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

# AGENT 03 — Residual TA incremental (full-history leftovers)

**AGENT_ID:** 03  
**ROLE:** Residual TA incremental — interpret (PERF + CORRECTNESS)  
**BASE_SHA:** `32697c97f7e56de817325356e4dbd692809ecbe8`  
**Date:** 2026-07-31

## 1. Scope & files

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | New `*_inc_update` kernels: kc, mfi, sar, alma, correlation, percentile linear / nearest rank |
| `…/basic.py` | Wire `ta.sar`, `ta.kc`/`kcw`, percentile_* behind `_use_incremental_ta` + last-sample |
| `…/volume.py` | Wire `ta.mfi` residual paths (unary / binary / 5-arg) |
| `…/volatility.py` | Wire `ta.alma`, `ta.correlation`, dual `kc`/`kcw` (non-MRO path) |
| `tests/test_ta_incremental.py` | Round 6 goldens + Runtime on/off |
| `docs/perf_round6/AGENT_03_ta_incremental.md` | This report |

**Owns (per PROMPT):** residual full-history leftovers from R5 P2.  
**Does not:** ATR EMA→Wilder re-baseline; TV supertrend ratchet; silent `na→0`; grammar.

## 2. Bugs found

| Severity | Issue | Notes |
| --- | --- | --- |
| None new | — | Residual paths were correct but O(bars²) or full-history rebuilds |
| Info | Concurrent tree | Uncommitted Agent 10 tests (`test_runtime_warmup_rising_falling_vidya_style`, crossover last-sample) fail parity independently; not caused by these kernels |

## 3. Changes (what / why)

R5 left full-history / full-rebuild: `kc`/`kcw`, `mfi`, `sar`, `alma`, `correlation`, `percentile_*` (percentrank already had inc).

### New kernels (call-site state, honor `PYNE_TA_INCREMENTAL`)

| Kernel | State key | Complexity | Semantics |
| --- | --- | --- | --- |
| `_kc_inc_update` | nested EMA + ATR slots | O(1)/bar | middle=`EMA(close)`; bands=`± mult * ATR` — matches current oracle |
| `_mfi_inc_update` | `("mfi", slot, period)` pos/neg deques | O(period)/bar | Same early `n <= period+2 → 50.0`; signed MF window |
| `_sar_inc_update` | `("sar", slot, start, inc, max)` | O(1)/bar | State machine ≡ `_sar_full` last value; leading na → None |
| `_alma_inc_update` | ring + cached Gaussian weights | O(length)/bar | na in window → None (no coerce) |
| `_correlation_inc_update` | dual rings | O(length)/bar | Pearson over non-na pairs; short / zero var → None |
| `_percentile_linear_inc_update` | ring + sort | O(period log period) | Matches linear interpolation builtin |
| `_percentile_nearest_rank_inc_update` | ring + sort | O(period log period) | Matches nearest-rank ceil formula |

Builtins use `_as_series_or_raw(..., last_sample_ok=True)` / `_context_source` on the inc path so Runtime PineSeries avoid reverse materialization.

**Flag:** existing `PYNE_TA_INCREMENTAL=0` disables all of the above (default on in bar mode).

## 4. Benchmarks

Micro-bench: bar-walk growing prefix, n=2000, median of 3, `PYTHONPATH=src:.`, CPython 3.14.

| Kernel | Full recompute | Incremental | Speedup |
| --- | ---: | ---: | ---: |
| `mfi(14)` | 8508 ms | 60 ms | **~142×** |
| `sar` | 2096 ms | 35 ms | **~60×** |
| `kc(20,2)` | 2054 ms | 26 ms | **~78×** |
| `alma(9)` | 24 ms | 15 ms | **~1.6×** |
| `corr(20)` | 67 ms | 47 ms | **~1.4×** |
| `pct_nr(14)` | 11 ms | 51 ms | ~0.2× (see notes) |

### Kernel notes

- **mfi / sar / kc** were true full-history rebuilds each bar → structural O(bars²) → O(1)/O(period). Primary wins.
- **alma / correlation / percentiles** were already O(period) window scans; gains are weight cache + last-sample / ring hygiene. On plain list prefixes the ring+sort path can be *slower* than slicing a list (microbench artifact). Runtime path still benefits when sources are PineSeries (no reverse) and multi-call scripts share bar mode.
- **percentrank** already incremental (R3); re-covered by Runtime golden only.

No claim on `bench_pipeline.py` `minimal`/`ta_combo` (those scripts do not call these indicators).

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ta_incremental.py -q --tb=line \
  -k "mfi or sar or alma or correlation or incremental_kc or kcw or percentile or round6 or mfi_sar_alma"
# → 11 passed
```

New cases:

- `test_incremental_mfi_matches_full`
- `test_incremental_sar_matches_full`
- `test_incremental_alma_matches_full`
- `test_incremental_correlation_matches_full`
- `test_incremental_kc_matches_full` / `test_incremental_kcw_matches_full`
- `test_incremental_percentile_linear_matches_full`
- `test_incremental_percentile_nearest_rank_matches_full`
- `test_mfi_sar_alma_na_safe`
- `test_runtime_round6_residual_incremental_vs_disabled`

## 6. Residual risks

1. **MFI oracle quirk** — full `_mfi` returns 50.0 while `n <= period + 2` (not just `period+1`). Inc matches that; a TV-strict MFI may need a later correctness PR.
2. **KC ATR path** — still uses current ATR (EMA of TR), not Wilder RMA. Do not “fix” without dedicated goldens.
3. **Percentile ring sort** — O(period log period) each bar; fine for typical lengths; not a sliding-order-stat structure.
4. **Concurrent Agent 10** — rising/crossover warmup parity tests in the same file may be red independently; do not treat as Agent 03 regressions.
5. **Volatility vs Basic kc** — MRO prefers Basic; both paths now wire inc for safety.

## 7. Out of scope / did not touch

- ATR EMA→Wilder re-baseline  
- TV supertrend band ratchet  
- Numba `*_inc` for these (Agent 04)  
- visit/dispatch / series materialize core (Agents 01–02)  
- Grammar / generated code  
- Commit / push  
