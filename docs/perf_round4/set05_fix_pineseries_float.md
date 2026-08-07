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

# set05: Fix interpret `float() … not 'PineSeries'`

**Date:** 2026-07-29  
**Evidence:** `.cache/corpus_flow_set05_runtime_auto.csv` — 13× `RUN_FAIL`  
`Runtime Error at bar …: float() argument must be a string or a real number, not 'PineSeries'`

## Root cause

Not a bare Python `float()` in `backend/runtime.py` plot/OHLCV paths.

**Site:** `ta.pivothigh` / `ta.pivotlow` in

- `src/pynescript/ast/evaluator/builtins/technical_submodules/basic.py` (live MRO winner)
- `…/common.py` (fallback duplicate)

**Mechanism:**

1. Runtime host injects `high` / `low` / `close` as `backend.series.PineSeries`.
2. Scripts call the 3-arg form, e.g. `ta.pivothigh(high, left, right)` or `ta.pivothigh(_high, …)`.
3. Handler only special-cased `isinstance(source, list)` (the `current_series` chronological lists used by the 2-arg form via `_context_series`).
4. For a `PineSeries` source it fell through to:

   ```python
   return float(source) if source is not None else None
   ```

5. Python’s built-in `float()` cannot coerce `PineSeries` → `TypeError` → Runtime `RUN_FAIL` on bar 0.

Confirmed with traceback on `7414_ind_ict_equal_highs_and_lows_indicator.pine`:

```
… basic.py _builtin_ta_pivothigh → float(source)  # PineSeries
```

All 13 corpus hits use `ta.pivothigh` / `ta.pivotlow` with series sources (`high`/`low`/`src*` or derived `_high`/`_low`).

| File (set05/indicators/) |
| --- |
| `7395_ind_nebula_light_v2_3.pine` |
| `7396_ind_nebula_light_v2_2.pine` |
| `7414_ind_ict_equal_highs_and_lows_indicator.pine` |
| `7416_ind_ict_equal_highs_and_lows_indicator_2.pine` |
| `8107_ind_ict_equal_highs_and_lows_with_screener.pine` |
| `8108_ind_ict_equal_highs_and_lows_with_screener_2.pine` |
| `8114_ind_ict_external_range_liquidity_static_multi_timeframe_swing_high_and_low.pine` |
| `8115_ind_ict_external_range_liquidity_static_multi_timeframe_swing_high_and_low_2.pine` |
| `8147_ind_ict_external_and_internal_range_liquidity_multi_timeframe.pine` |
| `8148_ind_ict_external_and_internal_range_liquidity_multi_timeframe_2.pine` |
| `8151_ind_elitealgo_v22.pine` |
| `8171_ind_ezalgo_v9.pine` |
| `8173_ind_nebula_v2_2.pine` |

## Fix

**Same NA / series semantics** as other TA kernels: materialize via existing `_as_series` (chronological, capped, same-bar cache) and coerce samples with a small `_pivot_scalar` (unwrap `.current` like `_as_scalar_operand` / `_as_num`).

### `basic.py` (primary)

- `_pivot_scalar(value)` — float | None; identity fast-path for `float`/`int`; PineSeries → `.current`; soft-fail TypeError → `None` (na).
- `_pivot_source_series(source)` — list as-is (capped) else `_as_series`.
- `_builtin_ta_pivothigh` / `_builtin_ta_pivotlow`:
  - 2-arg form unchanged (`_context_series("high"|"low")`).
  - 3-arg form always materializes source before window checks.
  - Never call bare `float(PineSeries)`.

### `common.py` (fallback MRO)

Same idea: `_as_series(args[0])` + try/except float; no bare `float(source)` on wrappers.

## Correctness notes

- **Before (list path):** left-window local max/min; return float of current or na if short history — unchanged.
- **Before (non-list path):** crashed on PineSeries; for a bare scalar incorrectly returned `float(source)` without a pivot check (not a real host path for OHLC).
- **After:** PineSeries takes the same list pivot path as `current_series` lists → proper left-window check + na when `len <= left+right`.
- Right-bars confirmation is still simplified (pre-existing; not expanded here).

## Tests

In `tests/test_evaluator.py`:

| Test | Intent |
| --- | --- |
| `test_ta_pivothigh_pivotlow_accept_pineseries_via_runtime` | Full Runtime interpret with `high`/`low` PineSeries; no error |
| `test_ta_pivothigh_on_pineseries_direct` | Direct builtin + `PineSeries` history; local max/min values |
| `test_pivot_scalar_unwraps_nested_series` | Scalar helper unit |

```bash
PYTHONPATH=src python -m pytest \
  tests/test_evaluator.py::test_ta_pivothigh_pivotlow_accept_pineseries_via_runtime \
  tests/test_evaluator.py::test_ta_pivothigh_on_pineseries_direct \
  tests/test_evaluator.py::test_pivot_scalar_unwraps_nested_series -q
# 3 passed
```

**Corpus recheck (13 files, interpret, synthetic 80 bars):** `OK=13 pineseries=0 other=0`.

**Parity:** non-corpus `tests/test_parity.py` subset 10 passed (corpus strategy fixtures absent in this sparse worktree).

> Note: editable install may point at main repo; use `PYTHONPATH=src` in the worktree when verifying.

## Optional: PARSE_FAIL easy wins (sanitize)

set05 runtime CSV: **42 PARSE_FAIL**. Mini recheck of truncated TV demos shows **current `sanitize_corpus_source` already repairs several** that fail on raw source:

| File | raw | sanitized |
| --- | --- | --- |
| `6785_ind_nested_map_demo.pine` | EOF/INDENT | **PARSE_OK** |
| `6797_ind_scope_and_history_demo.pine` | EOF/INDENT | **PARSE_OK** |
| `6879_ind_split_a_string_into_characters.pine` | “Previous” junk | **PARSE_OK** |
| `6897_ind_for_in_loop_demo.pine` | method/EOF | **PARSE_OK** |

If the CSV was produced without sanitize (or with an older sanitizer), re-running parse/runtime **with** current sanitize should reclaim those stubs without grammar work. Residual PARSE_FAIL after sanitize tend to be true grammar/token gaps (ZWSP, prose lines, recursion, etc.).

## Impact

| Metric | Before (set05 auto CSV) | After (this fix) |
| --- | --- | --- |
| `float()…PineSeries` RUN_FAIL | **13** | **0** (rechecked) |
| Interpret safe-fallback narrative | blocked by this bucket | unblocked for pivot-heavy ICT/Nebula scripts |

## Files touched

- `src/pynescript/ast/evaluator/builtins/technical_submodules/basic.py`
- `src/pynescript/ast/evaluator/builtins/technical_submodules/common.py`
- `tests/test_evaluator.py`
- `docs/perf_round4/set05_fix_pineseries_float.md` (this file)
