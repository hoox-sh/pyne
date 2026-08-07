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

# AGENT 04 — Compiler numeric coverage: stubs → real kernels

**Date:** 2026-07-31  
**Role:** Compiler numeric coverage (COMPILER + PERF)  
**Owns:** `src/pynescript/compiler/compiler.py` (call lowering), `numba_builtins.py`

## 1. Scope & files

| File | Change |
| --- | --- |
| `src/pynescript/compiler/numba_builtins.py` | Real `numba_adx`/`_inc`, `numba_dmi`/`_inc`, `numba_supertrend`/`_inc`; `numba_alma_inc` weight cache; `numba_percentrank` aligned to interpret oracle |
| `src/pynescript/compiler/compiler.py` | Replace dmi/supertrend stubs; wire `ta.adx`, `*_inc` emit; multi-return for supertrend/dmi_inc; const-length `alma_inc` |
| `tests/test_compiler_numba.py` | `TestCompileRound6DmiSupertrendAlma` (+5 tests) |
| `docs/perf_round6/AGENT_04_compiler_numba.md` | This report |

## 2. Bugs found

1. **Compile stubs:** `ta.dmi` → `(0.0, 0.0, 25.0)`, `ta.supertrend` → `(close, 1.0)` — numeric but wrong vs interpret.
2. **No `ta.adx` compile path** (only via dmi third component, also stubbed).
3. **`numba_percentrank` ≠ interpret:** used `<=` and `length` denominator; interpret uses strict `<` on non-nan window and returns `50.0` when fewer than 2 valid samples.
4. **ADX/DMI inc init:** `n_seen` stayed `nan` on first entry (`nan+1→nan`); fixed by full state reset when `last_i` unset / rewind.

## 3. Changes

### Kernels (match **current interpret oracle**, not TV supertrend ratchet)

| API | Behavior |
| --- | --- |
| `numba_adx` / `numba_adx_inc` | nan-first DM, Wilder RMA TR/+DM/-DM + RMA(DX); early bars **0.0** |
| `numba_dmi` / `numba_dmi_inc` | +DI/-DI **0-first** DM + RMA(`di_len`); ADX via nan-first path / `adx_smooth` |
| `numba_supertrend` / `_inc` | Simplified: mid=(H+L)/2, ATR=`numba_atr(_inc)`, dir=-1 if close≥mid else +1; band = lower/upper |
| `numba_alma_inc` | Precompute Gaussian weights in `st[2:]`; same values as `numba_alma` |
| `numba_percentrank` | Interpret parity (`<`, valid-only, 50.0 short window) |

State sizes: ADX `st[22]`, DMI `st[40]` (embeds ADX), Supertrend `st[2]` (ATR), ALMA `st[2+L]` for const length L.

### Compiler emit

- Stays **nopython** for scripts using only these TA + plots.
- Multi-return: `numba_dmi_inc` / `numba_supertrend_inc` added to `known_multi`.
- `ta.adx` bare alias + handlers (1-arg length, 2-arg di/adxSmooth, 4-arg OHLC).
- `ta.alma` with literal length → `numba_alma_inc`; dynamic length → full `numba_alma`.

## 4. Benchmarks

Kernel micro (random walk, n=5000, sequential `*_inc` after warm; not full `bench_pipeline`):

| Path | Notes |
| --- | --- |
| DMI/ADX | O(1)/bar after seed (was O(n) stub constant or full rebuild) |
| Supertrend | O(1) via existing ATR_inc |
| ALMA | Still O(L) MAC; avoids `exp` rebuild each bar when weights cached |
| percentrank | Still O(L); correctness fix only |

No claim of ≥10% on `bench_pipeline` scripts (those do not call dmi/supertrend). Structural win: scripts with dmi/adx/supertrend stay numeric and produce interpret-parity series.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py::TestCompileRound6DmiSupertrendAlma -q
# → 5 passed

PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_compiler_numba.py -q --tb=line
# → 172 passed, 2 failed (unrelated to this agent):
#   - TestCompileRound5IncKernels::test_ir_cache_shares_execute_on_comment_diff (Agent 06 engine IR)
#   - TestLanguageSurfaceNumeric::test_chart_viewport_times_use_bar_time_model (Agent 05 surface;
#     assertion is space-sensitive vs `float(n_bars-1)*60000.0`)
```

New tests: **5** (`TestCompileRound6DmiSupertrendAlma`).  
Suite collect: **174** tests in `test_compiler_numba.py`.

## 6. Residual risks

- Supertrend is the **simplified** interpret path (no TV final-band ratchet). P3 product track if TV parity required later.
- DMI DI RMA vs ADX RMA are independent states (same as interpret slots); dual-period `dmi(di, adxSmooth)` covered.
- Dynamic-length ALMA still full recompute; rare.
- percentrank still O(period); fenwick not justified.

## 7. Out of scope

- ATR Wilder re-baseline; TV supertrend ratchet  
- Interpret TA modules (Agent 03)  
- engine cold JIT / IR cache (Agent 06)  
- strategy broker  

## New `ta.*` that stay numeric (nopython)

| Function | Kernel |
| --- | --- |
| `ta.dmi` | `numba_dmi_inc` |
| `ta.adx` | `numba_adx_inc` |
| `ta.supertrend` | `numba_supertrend_inc` |
| `ta.alma` (const length) | `numba_alma_inc` |
| `ta.percentrank` | `numba_percentrank` (fixed oracle) |
