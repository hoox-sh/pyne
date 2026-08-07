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

# AGENT 12 — Harness + goldens + sanitize

**Role / ID:** Round 8 Agent 12 · P1p / C1 harness  
**Date:** 2026-08-04  
**Verdict:** **win**

## What you did (files touched)

| File | Change |
| --- | --- |
| `scripts/compare_interp_compile.py` | Richer MISMATCH detail (`interp=` / `compile=` / `n_bad` / `max_abs`); `expected_error` bucket for intentional dual-backend demos; float bar-time in `normalize_error`; report samples print series detail |
| `tests/test_interp_compile_parity.py` | Always-on smoke **5 → 17** scripts; unit tests for mismatch detail, expected-error classifier, float-bar normalize |
| `scripts/corpus_run_runtime.py` | `EXPECTED_FAIL` status + path list (R7 residual 6 demos); summary/progress exclude them from OK-rate denominator |
| `tests/test_corpus_runtime_residuals.py` | `TestIntentionalRuntimeErrorDemos` — classifier goldens + sample scripts still hard-fail |
| `src/pynescript/util/corpus_sanitize.py` | Doc/guard: truncated real Pine never replaced by minimal stub (chrome-only policy) |
| `tests/test_corpus_sanitize.py` | Truncated indicator + Expand-chrome strategy must keep body / roundtrip |

**Did not touch:** parser grammar, generated ANTLR, product builtins, parent CSV locks.

## Always-on smoke expansion

Verified OK @ 80–200 bars under harness `make_bars` (no value MISMATCH) before adding:

| Prior (5) | R8 additions (12) |
| --- | --- |
| `advance_decline_line` | `bbtrend` |
| `arnaud_legoux_moving_average` | `bollinger_bands` |
| `aroon` | `chande_momentum_oscillator` |
| `average_true_range` | `correlation_coefficient` |
| `awesome_oscillator` | `donchian_channels` |
| | `money_flow_index` |
| | `moving_average_exponential` |
| | `moving_average_simple` |
| | `on_balance_volume` |
| | `relative_strength_index` |
| | `supertrend` |
| | `williams_percent_range` |

**Explicitly excluded (not green):** `stochastic.pine` — type/na MISMATCH (`%K`/`%D` one-sided na) under synthetic bars (handoff to TA/compile agents).

## Harness bucket / reporting

### MISMATCH detail

`series_allclose` now reports e.g.:

```text
index 2: interp=61.7… compile=None (type/na) n_bad=2
index 0: interp=1.0 compile=1.001 (value) n_bad=12 max_abs=0.05
```

CLI residual dump prints up to 4 series keys with full detail strings.

### `expected_error` (parity harness)

When both backends fail with the **same** normalized message matching intentional needles (auto-fib depth / pivot “not enough data”…):

- status = `expected_error` (non-fatal unless `--strict-errors`)
- distinct from generic `both_error_same`

Also fixed `normalize_error` to strip `Runtime Error at bar 4234600000.0 (index N):` (float timestamps). Before this fix, auto-fib landed in `both_error` with mismatched raw prefixes.

### `EXPECTED_FAIL` (corpus Runtime runner)

Path-authoritative list (do not soft-suppress):

1. `set02/libraries/019_lib_functionnnetwork.pine`
2. `set02/libraries/021_lib_analysisinterpolationloess.pine`
3. `set02/libraries/026_lib_mathcomplexoperator.pine`
4. `set02/libraries/032_lib_colorscheme.pine`
5. `set02/libraries/036_lib_mathcomplextrigonometry.pine`
6. `set04/indicators/0703_ind_higher_timeframe_security_demo.pine`

Overrides the generic “library residual → OK” codegen path so intentional demos do not inflate OK%. Summary reports `EXPECTED_FAIL=N` and OK rate **excluding** them.

## Sanitize policy

- **Chrome only:** fences, Expand UI, FMZ footers, foreign shell/python → strip / minimal stub.
- **Truncated real Pine:** keep declaration + body; repair trailing parens / ellipsis — never overwrite with `indicator("x"); plot(close)`.
- **Parser:** untouched.

## Tests run

```text
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_interp_compile_parity.py \
  tests/test_corpus_sanitize.py \
  tests/test_corpus_runtime_residuals.py::TestIntentionalRuntimeErrorDemos \
  -q --tb=line
→ 91 passed, 1 skipped in ~43s
  (skip = opt-in -m interp_compile_full)
```

Smoke candidates serial check (pre-add): 27/28 OK; `stochastic` MISMATCH only.

## Residual / handoff

| Item | Owner |
| --- | --- |
| `stochastic.pine` interp↔compile type/na on `%K`/`%D` | Agent 02/05 (stoch kernel / na policy) |
| Broader `both_error_same` → `expected_error` needles if more intentional demos appear | Agent 12 follow-up |
| Parent full-corpus CSV baselines may still be running — this agent avoided long exclusive writes on shared result CSVs | Agent 01 inventory |
| Expand smoke further only after stochastic + other MISMATCH scripts go green | Agent 12 |

## Verdict

**win** — always-on smoke ×3.4 coverage on stable TA scripts; clearer MISMATCH diagnostics; honest `expected_error` / `EXPECTED_FAIL` buckets for intentional runtime.error demos; sanitize guard + goldens that truncated Pine is not stubbed; no parser weakening.
