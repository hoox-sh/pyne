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

# Agent 08 — request / MTF / ticker

| Field | Value |
| --- | --- |
| **Role / ID** | 08 — request / MTF / ticker residual |
| **Verdict** | **win** (targeted MTF + foreign-na) |
| **Date** | 2026-08-04 |

## What you did (files touched)

### Primary (owned)

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/request.py` | Foreign-na under host chart (no mock invent); same-symbol simple OHLCV passthrough (incl. `PineSeries` / `high[1]`); same-symbol **complex** expr on a **different** TF → `na` (no invented HTF structure) |
| `src/pynescript/ast/evaluator/builtins/timeframe.py` | `timeframes_equivalent()` for chart vs request TF compare |
| `tests/test_request_data_feed.py` | Foreign-na + same-symbol HTF/UDF + full MTF Structure Bias parity goldens |
| `tests/test_dividend_yield_parity.py` | Foreign string/`close` both-mode all-na (UPVOL/DNVOL) |

### Supporting (not exclusive, unowned surface)

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/numeric.py` | `_as_num` treats IEEE NaN as Pine `na` so `math.round(na)` → `na` (was `ValueError`) — required so honest HTF `na` does not RUN_FAIL MTF dashboard `str.tostring(math.round(score))` |

### Not edited

- `ticker.py` — already has TickerInfo / `ticker.new` / modify overloads; no residual found this round
- `compiler/compiler.py` — handoff only (below)

## Policy (interpret oracle)

1. **Foreign + host chart wired + no multi-symbol feed hit → `na`**
   - Applies to pre-eval UDF/expr **and** bare string `"close"` (previously invented mock OHLCV for `UPVOL.NY` / `MSFT`).
   - Standalone `NodeLiteralEvaluator` **without** chart identity still uses legacy mock prices for offline demos.
2. **Same-symbol simple OHLCV may passthrough**
   - String names, host `PineSeries` identity (`close`), and numeric samples matching chart OHLCV history (`high[1]`, …).
3. **Same-symbol complex (UDF / non-OHLCV) + request TF ≠ chart TF → `na`**
   - Without a multi-TF re-eval engine, do not invent HTF structure from chart bars (`f_struct` on `"60"` while chart is `"D"`).
4. **Same-symbol + same TF** pre-eval → chart eval is correct; allow.

## Before / after

### `tests/data/set02/indicators/156_ind_mtf_structure_bias.pine`

| Mode | Before | After |
| --- | --- | --- |
| Interpret | Chart UDF passthrough for HTF → Structure Score ~±100 | HTF UDF → `na` → score all-`na` (honest) |
| Compile | Complex security → `np.nan` → score all-`na` | unchanged |
| Parity harness | **MISMATCH** on `Structure Score` | **OK** (`--bars 200`) |

### Foreign OHLCV

| Case | Before (interpret) | After |
| --- | --- | --- |
| `request.security("UPVOL.NY", "D", "close")` under chart AAPL | mock ~100 series | all-`na` (matches compile) |
| `request.security("MSFT", "D", close)` | all-`na` (pre-eval path) | all-`na` |
| `ESD_FACTSET` + `year_sum(close)` | all-`na` | all-`na` (still) |

## Tests run

```text
pytest tests/test_request_data_feed.py tests/test_dividend_yield_parity.py  → 14 passed
pytest tests/test_datafeed_wiring.py tests/test_error_handling.py          → 30 passed
pytest tests/test_evaluator.py -k "request or security or …round…"         → 21 passed
pytest tests/test_error_handling.py::TestCamarillaPlotLinewidth            → 2 passed
scripts/compare_interp_compile.py --files …/156_ind_mtf_structure_bias.pine --bars 200
  → OK
```

## Residual / handoff

### Agent 03 — `compiler/compiler.py` (required for broader security parity)

1. **`_is_chart_security_symbol` does not treat `'SYMBOL'` / `"SYMBOL"` as chart**
   - Observed emit: `request.security(syminfo.tickerid, "D", close)` → `r_arr[__bar_idx] = np.nan`.
   - `transpile` debug: `chart? "'SYMBOL'" -> False`.
   - Existing tests fail: `test_request_security_syminfo_time_stubs`, `test_bare_security_passthrough`.
   - Fix: treat quoted `SYMBOL` / empty / `syminfo.*` lowers as same-symbol; for simple OHLCV return chart array sample.

2. **Same-symbol complex expressions**
   - Compile currently always `np.nan` for non-simple expr (including same-TF UDF).
   - Interpret now: same-TF complex **passthrough**; different-TF complex **`na`**.
   - After (1), prefer either:
     - **A (parity-friendly):** same-symbol → always emit already-lowered third arg (chart-TF eval), foreign → `np.nan`; or
     - **B (conservative):** keep complex → `np.nan` for all TF (score stays all-`na` when any HTF term is complex — matches today’s MTF OK).

3. **Do not** lower foreign fundamentals / UPVOL as chart close (already documented).

### Agent 10 / numeric (done this round if kept)

- `math.round(na)` ValueError was a real corpus footgun; `_as_num` NaN→None is the fix. If another agent owns `numeric.py`, re-home or keep as shared hygiene.

### Real multi-TF evaluation

- Not in scope: no HTF bar aggregation + expression re-eval engine. Honest `na` preferred over invented structure.

## Verdict

**win** — recovered `156_ind_mtf_structure_bias.pine` to interp↔compile **OK**; closed foreign string-mock invent hole; goldens under owned tests. Compile same-symbol simple OHLCV still broken (`'SYMBOL'` detection) — handoff Agent 03; does not block MTF residual once both sides use `na` for complex HTF.
