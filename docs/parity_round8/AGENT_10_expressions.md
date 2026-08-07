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

# AGENT 10 — Expressions / control residuals

**Role / ID:** Round 8 Agent 10 · Expressions / control  
**Date:** 2026-08-04  
**Verdict:** **win**

## Goal

Fix expression/control residuals that break corpus Runtime or dual-mode parity:
soft concat, period-or-none, bare aliases, na arithmetic, switch/if edge cases.
Prefer interpret oracle correctness with minimal unit goldens.

## What was failing (evidence)

1. **`switch` with subject = `na`** (e.g. `switch na` / `switch float(na)`) treated
   a present-but-na subject as **boolean switch mode**. First **truthy** pattern
   matched (`1 => 10` ran instead of default / `na => …`). Root cause: both
   `ExpressionEvaluator.visit_Switch` and `StatementEvaluator.visit_Switch`
   used `if subject_val is not None` to choose equality vs bool arms, so
   `None` (na) was indistinguishable from *no subject*.
2. **If/switch arm return value** only tracked bare `ast.Expr` nodes; trailing
   assignments did not contribute a block result (diverged from
   `_execute_block` / UDF last-statement convention).
3. **Soft concat** used Python `str(True)` → `"True"`; Pine-like demos expect
   `"true"` / `"false"`.
4. **`pine_period_or_none`**: already soft on identifier strings; hardened
   `nan`/`inf` string sentinels and fast-path pure `None`.

Prior R7 Agent 08 already landed str+number soft concat and period identifier
soft-na; this round closed the switch-na control bug and aligned if/switch
block returns.

## Fixes (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/ast/evaluator/expressions.py` | `_switch_case_matches(has_subject, …)`; `_pine_soft_str`; soft concat uses it; `visit_Switch` / `visit_If` via `_eval_local_block` → `_execute_block` |
| `src/pynescript/ast/evaluator/statements.py` | Mirror switch `has_subject` equality semantics (aligned for non-MRO hosts) |
| `src/pynescript/ast/evaluator/builtins/base.py` | `pine_period_or_none`: fast `None`; soft `"nan"`/`"inf"` strings |
| `tests/test_expr_parity_r8.py` | **New** unit + Runtime goldens (32 tests) |

**Not edited:** `technical.py` (Agent 05), compiler paths, harness.

### Switch semantics (after)

| Form | Behavior |
| --- | --- |
| `switch` (no subject) | Pattern must be truthy |
| `switch <expr>` subject finite | Equality match (`0` / `false` work) |
| `switch` subject `na` | Only `na` pattern matches; else default |
| Default `=>` | First unmatched fall-through |

### Soft concat (after)

- `None` still propagates **na** (not `"None"`).
- `"x" + 1` / `1 + "x"` → coerced concat.
- `"flag=" + true` → `"flag=true"`.
- List broadcast unchanged (element-wise soft concat).

## Before / after

| Check | Before | After |
| --- | --- | --- |
| `switch na` / default `=> 99` | matched `1 => 10` | **99** |
| `switch float(na)` / `na => 1` | matched `1.0 => 2` | **1** |
| `if true` / `1` then `y = 2` | returned `1` | **2** (assign value) |
| `"flag=" + true` length | 9 (`flag=True`) | **9** (`flag=true`) |
| `"x" + na` | na | na (unchanged) |
| `ta.sma(close, na)` | soft na | soft na (unchanged) |

Structural proof: unit helpers + Runtime interpret goldens (no full corpus
re-score required for this residual class; set01 interpret already 249/249 OK
pre-agent).

## Tests

```text
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_expr_parity_r8.py -q --tb=short
→ 32 passed

PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_corpus_runtime_residuals.py::TestStrConcatAndAlertSoft \
  tests/test_v4_bare_aliases.py tests/test_error_handling.py -q --tb=line
→ 25 passed

PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_evaluator.py \
  -q -k 'switch or if or concat or timestamp or year'
→ 3 passed, 248 deselected
```

## Residual / handoff

- **Compiler emit** of `switch` with na subject (Agent 03): interpret now
  correct; compile-path should mirror equality-not-bool when subject present.
- **Multi-pattern arms** (`0, 1 =>`) still parse-fail (grammar / Agent 12) —
  out of scope.
- **`na == na`** remains non-true in Compare (Pine gotcha; use `na()`); not
  changed intentionally.
- **Utility bare aliases** (`offset`, dual-mode `ticker.standard` /
  `syminfo.prefix`/`ticker`, timestamp month-0) already present; goldens added
  for year/offset/timestamp(…, 0, …).
- Do **not** silent-coerce numeric `na` → 0 for parity.

## Verdict

**win** — control-flow residual (`switch` subject-na) fixed with shared matcher;
if/switch blocks share `_execute_block` return semantics; soft concat bool
polish; period-or-none sentinel harden; 32 new goldens green.
