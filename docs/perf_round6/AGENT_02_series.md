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

# Round 6 — Agent 02: Series / expect / last-sample residual

**AGENT_ID:** 02  
**ROLE:** Series materialization helpers, `_expect_series`, `_expect_int`,
`backend/series.py`, evaluator series paths (PERF + CORRECTNESS)  
**BASE_SHA:** `32697c97f7e56de817325356e4dbd692809ecbe8`  
**Date:** 2026-07-31  
**Flag:** reuses `PYNE_TA_INCREMENTAL` (default on) — no new flag  

## 1. Scope & files touched

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/builtins/base.py` | Canonical `pine_expect_int` + `BuiltinDispatchMixin._expect_int` |
| `…/strings.py`, `arrays.py`, `matrix_evaluator.py` | Remove weaker `_expect_int` shadows |
| `…/technical_submodules/core.py` | Shared `_expect_int`; hot `_expect_series`; faster `_series_last`; `_cross_stateful` uses `_series_last` + either-direction; align prev `<=`/`>=` with list path |
| `…/basic.py`, `…/common.py` | Crossover/crossunder/cross last-sample (no PineSeries reverse) |
| `…/moving_averages.py` | dema/tema/swma last-sample residual |
| `backend/series.py` | `__slots__`; float/None index → na (no silent 0); OOB → na |
| `src/pynescript/ast/evaluator/names.py` | `series[na]` → na (no bar-loop crash) |
| `tests/test_ta_incremental.py` | +7 Round-6 tests |

**Out of scope:** visit_Call / arg plans (Agent 01), residual full-history TA kernels
(Agent 03), plot steady-state (Agent 04), compile, strategy, grammar.

## 2. Bugs found

| Severity | Issue | Fix |
| --- | --- | --- |
| **High (correctness)** | Live MRO used `StringBuiltinsMixin._expect_int`, which **rejected list periods** (`[…, 14]` → hard error) while `TechnicalHelpers._expect_int` accepted last-sample. Weaker messages (`Got:` missing). | Single `pine_expect_int`: list last-sample, series unwrap, `Got: type\|na` |
| **Med (perf residual)** | dema/tema (and MA swma) still `_as_series` every bar on pure-inc | `last_sample_ok=True` / raw pass-through |
| **Med (perf residual)** | `ta.crossover`/`crossunder`/`cross` always reversed PineSeries then discarded | last-sample + `_cross_stateful` |
| **Med (correctness)** | `_cross_stateful` used `series1[-1] if series1` — falsey PineSeries (`current=0`) or non-list broke | `_series_last` |
| **Low** | `close[na]` / PineSeries float-NaN index could crash or confuse | na → `None`; float trunc on PineSeries |
| **Doc** | Stateful prev compare must match list `_crossover` (`<=` then `>`) | Restored parity with list/numba |

**Preserved R5 win:** pure-inc last-sample path does **not** call `_as_series` reverse on ta_combo.

## 3. Changes (what / why)

### Canonical `_expect_int`

```text
pine_expect_int(value, message, error)
  type(value) is int → return          # hot path (bool excluded)
  dict default / .current / list[-1]
  float → floor; na/None → error "Got: na"
  else → error "Got: <type>"
```

Removed divergent copies from strings/arrays/matrix; TechnicalHelpers and
BuiltinDispatchMixin both delegate to `pine_expect_int`.

### `_expect_series` hot path

```text
(n == 2) and length == BINARY:
  period = args[1] if type is int else _expect_int(...)
  if last_sample_ok and incremental: return args[0], period
  else: return _as_series(args[0]), period
```

Avoids `_last_sample_path` extra frame and `_expect_int` when period is a
literal int (the common TA call shape).

### Crossover last-sample

Bar mode always uses `_expect_two_series(..., last_sample_ok=True)` +
`_cross_stateful` (prev pair state). Full recompute still materializes and uses
list `_crossover` / `_crossunder`.

### PineSeries

- `__slots__ = ("history", "current")`
- `__getitem__`: float trunc, `None`/NaN → na, OOB → na (never invent 0)

## 4. Benchmarks

Machine: main workspace `.venv`. Command:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
```

### Interpret Runtime (n=2000) vs Round 5 net map

| script | R5 med (ms) | R6 after (ms) | Δ |
| --- | ---: | ---: | ---: |
| **minimal** | 16.5 | **16.45** | ~0% (no regress) |
| **ta_sma** | 26.1 | **26.14** | ~0% |
| **ta_combo** | 170 | **150.43** | **~1.13×** |
| **strategy_ish** | 84.4 | **69.85** | **~1.21×** |

ta_combo ~**13 300 bars/s** (R5 ~11 800).

### Profile notes (ta multi-plot interpret @ 1500 bars)

- `_as_series` reverse still **absent** on pure-inc path
- `pine_expect_int` only on non-int period / unwrap paths; plain int periods skip it
- Residual tax still visit/Call (Agent 01), not series reverse

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_ta_incremental.py tests/test_evaluator.py -q --tb=line
# → 325 passed
```

New / extended:

- `test_expect_int_list_period_and_error_messages`
- `test_expect_int_plain_int_identity`
- `test_dema_tema_last_sample_skips_as_series`
- `test_crossover_last_sample_matches_full_list`
- `test_pineseries_history_offset_na_and_float`
- `test_subscript_na_index_returns_na`
- `test_runtime_crossover_dema_parity` (Runtime inc ≡ `PYNE_TA_INCREMENTAL=0`)

## 6. Residual risks

1. **MRO:** `TechnicalHelpers._expect_int` still wins over
   `BuiltinDispatchMixin` when TA is mixed in — both call the same helper.
2. **Non-inc residual materialize:** kc/mfi/sar/alma/correlation still full
   history (Agent 03).
3. **Crossover first-bar state:** stateful starts with no prev → False (same as
   short list path).
4. **`_expect_number`:** lighter hardening only; not as hot as periods.
5. Concurrent Agent 01 may shift absolute bench noise; relative series tax is down.

## 7. Explicit out of scope / did not touch

- Dispatch cache / visit_Call (Agent 01)
- New TA kernels (Agent 03)
- Plot capture (Agent 04)
- Compiler / strategy / LSP / grammar generated trees

---

**Definition of done:** structural + ~13% ta_combo interpret vs R5 map; no
minimal regression; goldens ≡ full recompute / inc-off; no na→0; errors surface
`Got: type`; R5 last-sample pure-inc preserved.
