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

# Round 5 — Agent 02: Series materialization `_as_series` / `_expect_series`

**AGENT_ID:** 02  
**ROLE:** Series materialization (PERF + CORRECTNESS)  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30  
**Flag:** reuses `PYNE_TA_INCREMENTAL` (default on) — no new flag required  

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | `last_sample_ok` on `_expect_series` / `_expect_two_series`; `_as_series_or_raw`, `_context_source`, `_last_sample_path` |
| `…/basic.py` | Pure-inc builtins use last-sample path (sma/ema/wma/rma/hma/vwma/falling/rising/highest/lowest/change/stdev/bb/atr/tr/cum/dev/median/percentrank/variance) |
| `…/common.py` | Mirror last-sample wire for falling/rising/highestbars/lowestbars/change/mom/cum/dev/median/percentrank/variance |
| `…/oscillators.py` | rsi/macd/stoch/cci/roc/tsi last-sample |
| `…/moving_averages.py` | MA fallbacks last-sample |
| `…/advanced.py` | **MRO winner** `ta.stdev` last-sample (was still materializing) |
| `tests/test_ta_incremental.py` | +7 Round-5 golden / unit tests |

**Out of scope (not touched):** `visit_Call` dispatch, strategy, compiler, LSP, Runtime host, residual non-inc kernels (dmi/supertrend/valuewhen) — Agent 03.

## 2. Bugs found

| Severity | Issue | Fix |
| --- | --- | --- |
| **Med (perf correctness)** | Pure-inc TA still called `_as_series` every bar on PineSeries `close`/`high`/`low`, reversing up to `_SERIES_MAX` samples even though kernels only use `_series_last` | `last_sample_ok=True` skips reverse; pass raw source |
| **Med (MRO footgun)** | `AdvancedIndicators._builtin_ta_stdev` wins over Basic; Basic’s last-sample wire was dead code for Runtime | Wire Advanced stdev with `last_sample_ok=True` |
| **Low (pre-existing, documented)** | Non-inc `ta.barssince` scalar still 0/1 only | Unchanged; Round-4 note retained |

Hunts checked (no new semantic bugs found under last-sample):

- **Series cap length:** `_as_series` still caps at `_SERIES_MAX`; inc path does not depend on list length (deque state). Test: `test_as_series_cap_length`.
- **Off-by-one change/mom:** `_change_inc_update` window `maxlen=length+1`; golden + `test_change_na_propagation_last_sample`.
- **na propagation:** None lag/current → None (no silent 0).
- **Shared call-site state:** slot via `_ta_next_slot`; `test_two_builtin_call_sites_independent_pineseries`.

## 3. Changes (what / why)

### Core API

```text
_expect_series(..., last_sample_ok=False)
  if last_sample_ok and _use_incremental_ta():
      return raw args[0] (or _context_source for period-only), period
  else:
      return _as_series(...), period   # chrono list, capped

_as_series_or_raw(value, last_sample_ok=False)
_context_source(name)   # live list, no cap-slice alloc
_last_sample_path()     # alias of _use_incremental_ta for clarity
```

### Call-site pattern

```python
series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
if self._use_incremental_ta():
    return self._sma_inc_update(series, period)  # uses _series_last
return self._finalize_series(self._sma(series, period))  # full list
```

Full-recompute / non-inc / `PYNE_TA_INCREMENTAL=0` still materializes chronological history. Behaviour is flag-gated by existing incremental gate (not a silent semantic change).

## 4. Benchmarks

Machine: worktree + main `.venv` Python. Commands:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
```

### Interpret Runtime (n=2000) vs Round-4 map

| script | R4 med (ms) | R5 after (ms) | Speedup |
| --- | ---: | ---: | ---: |
| **minimal** | 27.8 | **20.52** | **1.35×** |
| **ta_sma** | 79.5 | **38.64** | **2.06×** |
| **ta_combo** | 411 | **273.49** | **1.50×** |
| **strategy_ish** | 177 | **112.70** | **1.57×** |

Official `bench_pipeline.py` (this worktree): ta_combo **7313 bars/s**, minimal **97462 bars/s**.

### Profile (ta_combo interpret @ 1500 bars)

| metric | Before (R4 / early R5) | After |
| --- | ---: | ---: |
| `_as_series` ncalls | ~1×bars (and more with multi-source) | **0** on ta_combo pure-inc path |
| `_as_series` tottime | ~0.065 s (R4 #2 self-time) | **absent** from top profile |
| `_expect_series` | full materialize inside | period + raw pass-through |

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py -q --tb=line
# 294 passed
```

New tests:

- `test_expect_series_last_sample_skips_materialize`
- `test_series_last_on_pineseries_and_list`
- `test_builtin_sma_via_pineseries_matches_list_inc`
- `test_as_series_cap_length`
- `test_change_na_propagation_last_sample`
- `test_two_builtin_call_sites_independent_pineseries`
- `test_runtime_last_sample_multi_ta_vs_disabled` (Runtime inc ≡ `PYNE_TA_INCREMENTAL=0`)

Correctness: golden last-bar values ≡ full recompute; Runtime on/off parity for multi-TA.

## 6. Residual risks / follow-ups

1. **MRO duplicates:** any other Advanced/Common/MA shadows of Basic pure-inc builtins should get the same `last_sample_ok` (stdev was the live footgun).
2. **Non-inc TA** (dmi, supertrend, valuewhen, pivots, percentiles) still materialize — Agent 03.
3. **Crossover `_expect_two_series`:** left default materialize (needs ≥2 samples or stateful path); optional later.
4. **`_last_sample_path` + `_use_incremental_ta`:** thin wrapper; could fold if desired.
5. Compile path / Numba wrap not in scope (still host-bound vs bare run).

## 7. Explicit out of scope / did not touch

- `expressions.py` / `visit_Call` (Agent 01)
- Residual inc kernels (Agent 03)
- Plot path (Agent 04)
- Runtime host bookkeeping (Agent 05)
- Compiler / strategy / LSP / grammar

---

**Definition of done:** ≥10–15% on multi-TA interpret (**~50% ta_combo**, **~2× ta_sma**); no minimal regression; golden ≡ full recompute; no na→0; flag via existing `PYNE_TA_INCREMENTAL`.
