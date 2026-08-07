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

# set05 sanitize rest — scrape/syntax PARSE recovery (4 files)

**Agent:** FIX remaining scrape/syntax compile fails via sanitize (not grammar)  
**Scope:** `src/pynescript/util/corpus_sanitize.py` + `tests/test_corpus_sanitize.py`  
**Date:** 2026-07-29

## Target residual PARSE_FAIL (from `.cache/set05_recompile_still_fail.txt` / older parse CSV)

| # | File | Raw parse error | Root cause |
|---|------|-----------------|------------|
| 1 | `set05/indicators/7289_ind_ai_supertrend_clustering_oscillator.pine` | `no viable alternative at input 'Expand (152 lines'` | TV UI stub at EOF |
| 2 | `set05/indicators/7410_ind_fukuiz_octa_ema_ichimoku.pine` | `else if sell2` … fence `` ``` `` / `> Detail` | FMZ fence + footer after valid `else if` / `strategy.entry` |
| 3 | `set05/indicators/7448_ind_pivot_based_trailing_maxima_and_minima.pine` | `else if ph` … fence / `> Detail` | Same FMZ pattern |
| 4 | `set05/indicators/7739_ind_loop_keywords_and_variable_assignment_demo.pine` | `mismatched input '<DEDENT>' expecting INDENT` | Truncated loops.md demo: empty `if` under `for..in` expr assignment |

## Recovery count: **4 / 4**

After `sanitize_corpus_source`:

| File | parse+unparse | `compile_script` | notes |
|------|---------------|------------------|-------|
| 7289 | **OK** | OK | `Expand` stripped; trailing chrome cut |
| 7410 | **OK** | OK | fence + FMZ footer stripped; `else if` body kept |
| 7448 | **OK** | OK | same as 7410 |
| 7739 | **OK** | **OK** (+ Runtime compile OK) | empty `if` → then collapse na-only `for` RHS → `finalLabelText = na` |

Raw (unsanitized) still fails all four — sanitize is required on the corpus path (already wired in `corpus_run_runtime.py` / `showcase.py` / `corpus_parse_sets.py`).

## Fixes landed

### 1. Expand residual

- Broadened `_EXPAND_RE` to accept incomplete `Expand (152 lines` (missing `)`).
- In `_line_filter`, after real Pine is seen, `Expand …` **stops** the script so residual page chrome cannot re-enter.

### 2. else if / strategy.entry + FMZ fence

- Existing fence/footer strip + same-indent body promotion already healed 7410/7448.
- Unit tests lock the exact FMZ shape: `if` / `else if` + indented `strategy.entry` + `` ``` `` + `> Detail`.

### 3. DEDENT / empty blocks + truncated for-expression

- Empty `if` / `for` / `while` still inject `na` bodies.
- Empty RHS structures now include **`for` / `while`** (not only `switch` / `if`).
- New post-pass `_collapse_na_only_control_expr_assignments`: when  
  `lhs = for|while|if|switch …` body is only comments / nested controls / bare `na|continue|break`, rewrite to `lhs = na`.  
  Rationale: na-only truncated expression-`for` **parses** after empty-body injection but the compiler emits invalid Python (`x = for number in …`). Collapse keeps real expression-for bodies (any non-`na` leaf).

## Tests

```bash
PYTHONPATH=src python -m pytest tests/test_corpus_sanitize.py -q
# 40 passed
```

New coverage:

- `test_strips_expand_ui_stub_incomplete_paren`
- `test_expand_after_pine_stops_trailing_chrome`
- `test_fmz_else_if_strategy_entry_with_fence`
- `test_fmz_else_if_pivot_strategy_entry`
- `test_empty_if_under_for_in_expression_assignment`
- `test_injects_na_for_empty_for_while_if_statements`
- `test_injects_na_for_empty_if_at_eof`
- `test_preserves_real_for_in_expression_with_body`

## Out of scope (not sanitize)

Post-parse Runtime `mode=compile` **RUN_FAIL** on 7289 / 7410 / 7448 (e.g. `float - NoneType`, numba `isnan(unicode)`, pyobject arrays) are evaluator/compiler runtime issues, not scrape syntax. 7739 was the only one of the four that still failed at **compile emit** after a naive empty-`if` inject; collapse to `na` clears that.

## Files touched

- `src/pynescript/util/corpus_sanitize.py`
- `tests/test_corpus_sanitize.py`
- `docs/perf_round4/set05_fix_sanitize_rest.md` (this file)
