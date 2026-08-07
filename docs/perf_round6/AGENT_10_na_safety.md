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

# AGENT 10 — na-safety audit on technical helpers

**Role:** CORRECTNESS (merge-first)  
**Base:** `32697c97` (na-safe rising/falling remove CommonIndicators overrides)  
**Date:** 2026-07-31

## 1. Scope & files

| Path | Role |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | SoT helpers: `_cmp_*`, `_crossover`/`_crossunder`, `_rising`/`_falling`, `_highestbars`/`_lowestbars` |
| `…/common.py` | CommonIndicators builtins + note not to re-override helpers; supertrend direction na-guard |
| `…/basic.py` | Active MRO winner for rising/falling/highestbars/lowestbars/cross builtins |
| `tests/test_ta_incremental.py` | Goldens + MRO guard + Runtime MA-STER-style warmup |

**Not owned:** volatility `_atr` None subtraction (Basic supertrend path), Agent 02 series materialization for local vars as PineSeries.

## 2. Bugs found

### Audit checklist

| Surface | Path | Was unsafe? | Status |
| --- | --- | --- | --- |
| `_rising` / `_falling` | TechnicalHelpers | Fixed in 0.3.0 (None ≥ None TypeError) | **OK** — None / non-numeric → False |
| CommonIndicators `_rising`/`_falling` overrides | common.py | **0.3.0 bug class** | **OK** — removed; MRO test locks it |
| `_highestbars` / `_lowestbars` | TechnicalHelpers | max/min on None window | **OK** — float-skip, all-na → `-1` |
| `_highestbars_inc` / `_lowestbars_inc` | core | Already skipped None | **OK** — parity with full |
| `_crossover` / `_crossunder` list path | TechnicalHelpers | na-safe via `_cmp_*`, but **strict** prev `<`/`>` vs TV/numba/`_cross_stateful` (`<=`/`>=`) | **Fixed** — `_cmp_le`/`_cmp_ge` |
| `_cross_stateful` | core | Already na-safe | **OK** |
| `ta.max` / `ta.min` | basic/common | Filter None before max/min | **OK** |
| `_highest` / `_lowest` / `_range` | core/common | Filter None | **OK** |
| `_change` / `_momentum` | common | None guards | **OK** |
| Bar-mode rising on **derived local** (SMA/VIDYA) with `PYNE_TA_INCREMENTAL=0` | basic/common builtins | visit_Call passes **scalar** → `_rising` always `len<period` → always False | **Fixed** — short bar-mode series uses `*_inc_update` window |
| CommonIndicators `_builtin_ta_supertrend` direction | common (MRO-shadowed by Basic) | `highs[-1] > band` on None | **Hardened** (defensive) |
| Basic `_atr` / live supertrend | volatility/basic | `high - low` on None | Residual — not this agent |

### Proven issues fixed this round

1. **Crossover equality semantics:** list-path used `_cmp_lt`/`_cmp_gt` on previous bar; TV / `numba_crossover` / `_cross_stateful` use `<=` / `>=`. Equal-then-above did not fire on full-series path.
2. **Bar-mode non-inc rising/falling/highestbars/lowestbars on locals:** when history is a last-sample scalar list, fall back to call-site ring buffer (same kernels as incremental).
3. **`_highestbars`/`_lowestbars` full:** float conversion + skip non-numeric (aligned with inc; no TypeError on junk).

## 3. Changes

- **core.py:** `_cmp_le` / `_cmp_ge`; crossover/crossunder TV prev inequality; clean `_falling`; harden highestbars/lowestbars.
- **basic.py + common.py:** bar-mode short-series fallback to `*_inc_update` for rising/falling/highestbars/lowestbars.
- **common.py:** supertrend direction/atr_last na-safe.
- **tests:** expanded na goldens, MRO override guard, crossover equality, mixed-na highestbars parity, Runtime warmup script (SMA → rising/falling/cross/max/min).

## 4. Benchmarks

N/A (correctness only; no intentional hot-path speed change). Short-series fallback only when `len < period` in bar mode with inc disabled.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ta_incremental.py -q --tb=line
# + tests/test_multi_plot_cross.py
```

Expected: all green after this agent’s patches.

## 6. Residual risks

- **BasicIndicators supertrend** still goes through Volatility `_atr`, which subtracts OHLCV without None guards (TypeError on all-na high/low). Separate from helper comparison class.
- **Local vars are scalars** in bar mode (not PineSeries). Helpers now window statefully when short; Agent 02 may still want locals to retain PineSeries for full-history non-inc paths of other `ta.*`.
- **highestbars ties:** interpret prefers **oldest** extreme; numba prefers **most recent**. Pre-existing oracle difference — not changed.
- Compiler `numba_rising` already NaN-safe; no interpret↔compile parity work in this agent.

## 7. Out of scope

- ATR / KC / MFI / SAR incremental (Agent 03)
- Compiler kernels (Agent 04)
- Strategy / collections / parser agents
- Re-baselining ATR EMA vs Wilder or supertrend TV ratchet
