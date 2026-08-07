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

# AGENT 08 — C1 Corpus Runtime residual

**Role / ID:** Round 7 Agent 08 · Roadmap **C1**  
**Date:** 2026-08-02  
**Verdict:** **win** (high-frequency RUN_FAIL residual cut; intentional library `runtime.error` demos left)

## Goal

Advance **C1** corpus Runtime residual with unit goldens (not one-off scrapes): fix high-frequency RUN_FAIL patterns on set01–04 (~21 residual class: library `runtime.error` demos, period edges, `str.contains`/`str.tonumber`, missing import-only names) without weakening the parser for truncated non-Pine stubs.

## What was failing (evidence)

Prior residual inventory: `.cache/c1b_still_fail.txt` (34 historical rows; many already fixed in earlier C1 passes).

**Before this agent (live re-run of c1b list, interpret, 25 bars):** **16 FAIL / 18 OK**

High-frequency buckets still open:

| Bucket | Examples | Fix type |
| --- | --- | --- |
| Unresolved period name | `ta.sma(close, length)`, FlowBias `rsiLen` (module not inlined) | soft-na period |
| `str.contains` / family + `na` | na source/needle hard-fail | real soft-na |
| `ticker.standard()` 0-arg | substring demos | real dual-mode |
| `matrix.fill` 6-arg region | TV docs demo | real semantics |
| `array.some()` unary bools | confluence alerts | soft polyfill |
| `array.standardize` + `close[i]` na | early bars → `statistics.mean(None)` | soft skip na |
| Extra TA / bare `alert()` | linter signature demos | soft ignore / no-op |
| str + number / list | ISIN / timezone demos via `request.security` list leak | soft concat |
| Import stub timestamps | VisibleChart `highBarTime` → format_time | soft `"NaN"` |

## Fixes (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/strings.py` | `str.contains` / `startswith` / `endswith`: `na` → `na`, coerce non-str; `format_time` soft on stub/timezone |
| `src/pynescript/ast/evaluator/builtins/base.py` | `pine_period_or_none`: non-numeric identifier strings → `None` (na period) |
| `src/pynescript/ast/evaluator/builtins/technical_submodules/core.py` | `_expect_series`: soft-ignore trailing extra TA args |
| `src/pynescript/ast/evaluator/builtins/ticker.py` | `ticker.standard` optional arg; `TickerInfo` stringify + `__add__`/`__radd__` |
| `src/pynescript/ast/evaluator/builtins/utility.py` | dual-mode `_builtin_ticker_standard` (chart ticker when 0-arg) |
| `src/pynescript/ast/evaluator/builtins/matrix.py` + `matrix_evaluator.py` | `matrix.fill` region form (half-open rows/cols) |
| `src/pynescript/ast/evaluator/builtins/arrays.py` | unary `array.some`; standardize skip na; `min`/`max` soft on na id |
| `src/pynescript/ast/evaluator/builtins/alerts.py` | zero-arg `alert()` soft no-op |
| `src/pynescript/ast/evaluator/expressions.py` | str+non-str concat coerce; list broadcast TypeError soft |
| `backend/runtime.py` | **unrelated host fix:** broken walrus `env_override_missing := True` → plain `if` (blocked all Runtime imports) |
| `tests/test_corpus_runtime_residuals.py` | +5 test classes + 10 corpus recovery samples |

## After (same c1b list)

**28 OK / 6 FAIL** — **+10 recovered** from the live residual list.

Remaining 6 are **intentional** RuntimeError demos / guards (do not soft-kill real `runtime.error`):

1. `set02/libraries/019_lib_functionnnetwork.pine` — library validates NN sizes via `runtime.error`
2. `set02/libraries/021_lib_analysisinterpolationloess.pine` — loess empty-sample error
3. `set02/libraries/026_lib_mathcomplexoperator.pine` — complex size check
4. `set02/libraries/032_lib_colorscheme.pine` — delete missing key
5. `set02/libraries/036_lib_mathcomplextrigonometry.pine` — sinh size check
6. `set04/indicators/0703_ind_higher_timeframe_security_demo.pine` — lower TF vs chart guard

PARSE_FAIL ~118 truncated scrapes **untouched** (no parser weakening).

## Estimated OK-rate impact

| Scope | Before (this agent start) | After | Delta |
| --- | ---: | ---: | ---: |
| c1b residual list (34) | 18 OK (52.9%) | **28 OK (82.4%)** | **+10 scripts** |
| set01–04 projected Runtime OK | ~94.3% (docs prior) | **~94.7%** | ~+0.4 pp (~10 / 2477) |
| set01 sample (65 files, interpret) | — | **65/65 OK** | smoke |

Remaining ~6 intentional RUN_FAIL + PARSE stubs ~118 dominate the long tail. True open RUN_FAIL class now ≈ library `runtime.error` demos + lower-TF security guard + sparse long-tail.

## Tests

```text
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_corpus_runtime_residuals.py -q --tb=line
→ 161 passed in ~37s

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_collections.py tests/test_builtins.py \
  tests/test_alerts.py tests/test_v4_bare_aliases.py -q --tb=line
→ 120 passed
```

## Residual / follow-ups

- Do **not** soft-suppress library `runtime.error` validation demos — they match TV fail-closed library unit tests.
- Optional: classify intentional `runtime.error` / lower-TF guard as `EXPECTED_FAIL` in corpus runner so OK% excludes them.
- `request.security(..., syminfo.isin)` still returns price series list (mock); string demos survive via concat soft-path — real `syminfo.isin` string feed is B1 / host data.
- set05 TIMEOUT / ML / SuperTrend AI still out of C1 unit-golden scope.

## Verdict

**win** — 10 high-frequency RUN_FAIL recoveries with unit goldens; real semantics preferred (`matrix.fill` region, `ticker.standard()`, str-na family); soft only for unresolved periods / incomplete demos / import stubs.
