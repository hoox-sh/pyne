# Pine Script v6 Feature Implementation Plan

**Created:** 2026-05-11
**Last Updated:** 2026-06-03
**Status:** approved
**Scope:** All missing Pine Script v6 features from 2024–April 2026 releases

---

## Overview

Implement all missing Pine Script v6 features into pynescript, organized into three phases:
- **Phase A** — Evaluator/Builtin additions (new builtins, parameters, variables)
- **Phase B** — Grammar/Parser & behavior changes (multiline strings, v6 semantics)
- **Phase C** — LSP metadata updates (builtin_metadata.json, completion items)

Phase B is explicitly a separate phase from A, as v6 behavior changes affect parser and evaluator deeply.

---

## Phase A — Evaluator/Builtin Additions

### A1: Negative array indices (Nov 2024)

`array.get()`, `array.set()`, `array.insert()`, `array.remove()` now accept negative index arguments referencing elements from the end.

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Remove the `Negative indices not supported` error, convert negative indices
- `src/pynescript/ast/evaluator/builtins/arrays.py` — Update `_builtin_array_get`, `_builtin_array_set`, `_builtin_array_insert`, `_builtin_array_remove` to handle negative indices
- `tests/test_evaluator.py` — Add test cases for negative indexing

**Current behavior:** `names.py` line 137–140 raises `ValueError("Negative indices not supported in PineScript")`

**New behavior:** Negative index `-1` maps to last element, `-2` to second-to-last, etc. Out-of-bounds returns `na` (None).

---

### A2: `syminfo.isin` (Nov 2025)

New built-in variable returning the 12-character ISIN for the current symbol, or empty string.

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add `"syminfo.isin": ""` to builtin names dict
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entry

---

### A3: `syminfo.current_contract` (July 2025)

New built-in variable returning the ticker identifier of the underlying contract for continuous futures, or `na`.

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add `"syminfo.current_contract": None` to builtin names dict
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entry

---

### A4: `timeframe.main_period` and `syminfo.main_tickerid` (Nov 2024)

Two new built-in variables that reference the main context's ticker ID and timeframe, even inside `request.*()` calls.

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add both variables
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A5: `time()`/`time_close()` `timeframe_bars_back` parameter (Oct 2025)

New parameter on `time()` and `time_close()` that determines bar offset on the specified timeframe rather than the main timeframe.

**Files:**
- `src/pynescript/ast/evaluator/builtins/timeframe.py` — Add `timeframe_bars_back` parameter handling
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update `time` and `time_close` entries

---

### A6: `box.set_xloc()` (March 2025)

New setter function for boxes, sets left and right coordinates and their xloc type.

**Files:**
- `src/pynescript/ast/evaluator/builtins/drawing.py` — Add `box.set_xloc` to builtin dispatch
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entry

---

### A7: `behind_chart` parameter on `indicator()`/`strategy()` (Oct 2024)

New optional parameter specifying whether plots appear behind the chart when `overlay=true`.

**Files:**
- `src/pynescript/ast/evaluator/builtins/declarations.py` — Add `behind_chart` parameter to indicator/strategy declaration handling
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update indicator/strategy entries

---

### A8: `force_overlay` parameter on drawing functions (June 2024)

New optional `force_overlay` parameter on `box.new()`, `label.new()`, `line.new()`, `polyline.new()`, `table.new()`.

**Files:**
- `src/pynescript/ast/evaluator/builtins/drawing.py` — Add `force_overlay` parameter to all drawing constructors
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update drawing function entries

---

### A9: `sort_field` parameter on `array.sort()`, `array.sort_indices()`, `matrix.sort()` (April 2026)

New `sort_field` parameter accepts const int (field index) or const string (field name) to sort UDT collections by a specific field.

**Files:**
- `src/pynescript/ast/evaluator/builtins/arrays.py` — Update `_builtin_array_sort` and `_builtin_array_sort_indices` to accept optional `sort_field`
- `src/pynescript/ast/evaluator/builtins/matrix.py` — Update `_builtin_matrix_sort` to accept optional `sort_field`
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update entries

---

### A10: `export const` for libraries (June 2025)

Libraries can now export constant variables of type int, float, bool, color, or string with the `const` keyword.

**Files:**
- `src/pynescript/ast/evaluator/builtins/declarations.py` — Handle `export const` syntax in library declarations
- `src/pynescript/ast/grammar/antlr4/resource/` — Grammar may need update if `const` keyword not yet supported

---

### A11: `ticker.renko/pointfigure/kagi` `"PercentageLTP"` style (April 2025)

New `style` argument value `"PercentageLTP"` for these ticker functions.

**Files:**
- `src/pynescript/ast/evaluator/builtins/ticker.py` — Add `"PercentageLTP"` as valid style value
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update ticker entries

---

### A12: `strategy.exit()` parameter pair evaluation (Dec 2024)

Changed behavior: `strategy.exit()` now evaluates both absolute and relative parameter pairs and uses whichever the market price would activate first.

**Files:**
- `src/pynescript/ast/evaluator/builtins/strategy.py` — Update exit logic to evaluate both `limit`/`profit` and `stop`/`loss` pairs

---

## Phase B — Grammar/Parser & Behavior Changes

### B1: Multiline strings (April 2026)

Support `"""..."""` and `'''...'''` string delimiters for multiline strings. Newlines between delimiters are literal; indentation is preserved.

**Files:**
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4` — Add `TRIPLE_DQUOTE` and `TRIPLE_SQUOTE` token rules, multiline string literal rule
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4` — Update string literal rule to accept triple-quoted strings
- `src/pynescript/ast/unparser.py` — Handle multiline string output
- `src/pynescript/ast/evaluator/literals.py` — Evaluate multiline strings (preserve newlines, indentation)
- Regenerate ANTLR parser: `hatch run lint:gen-parser`

---

### B2: Dynamic `for` loop boundaries (March 2025)

The `for` loop now evaluates `to_num` before every iteration, not just once at the start.

**Files:**
- `src/pynescript/ast/evaluator/statements.py` — Update for-loop evaluation to re-evaluate the end boundary on each iteration

---

### B3: v6 behavior — bool cannot be `na`

In v6, `bool` values are strictly `true` or `false`, never `na`. The `na()`, `nz()`, and `fixnan()` functions no longer accept `bool` arguments.

**Files:**
- `src/pynescript/ast/evaluator/expressions.py` — Ensure bool expressions never produce `na`
- `src/pynescript/ast/evaluator/names.py` — History-referencing on bool variables returns `false` instead of `na` on first bar
- `src/pynescript/ast/evaluator/builtins/` — Update `na()`, `nz()`, `fixnan()` to reject bool args

---

### B4: v6 behavior — explicit bool casting required

`int` and `float` values are no longer implicitly cast to `bool`. Must use `bool()` function.

**Files:**
- `src/pynescript/ast/evaluator/expressions.py` — Remove implicit int/float → bool casting in conditional contexts
- `src/pynescript/ast/evaluator/builtins/` — Add `bool()` builtin function

---

### B5: v6 behavior — fractional const division

Dividing two `const int` values now returns a fractional result (`5/2 = 2.5`), not integer division (`5/2 = 2`).

**Files:**
- `src/pynescript/ast/evaluator/expressions.py` — Update division operator to always return float result for int/int division

---

### B6: v6 behavior — `when` param removed from strategy functions

The `when` parameter is removed from `strategy.entry()`, `strategy.order()`, `strategy.exit()`, `strategy.close()`, `strategy.close_all()`, `strategy.cancel()`, `strategy.cancel_all()`.

**Files:**
- `src/pynescript/ast/evaluator/builtins/strategy.py` — Remove `when` parameter from all strategy order functions

---

### B7: v6 behavior — `transp` param removed

The `transp` parameter is removed from all applicable drawing functions. Use `color.new()` or `color.rgba()` instead.

**Files:**
- `src/pynescript/ast/evaluator/builtins/drawing.py` — Remove `transp` parameter from drawing constructors

---

### B8: v6 behavior — default margin 100%

Default `margin_long` and `margin_short` for strategies changed from 0 to 100.

**Files:**
- `src/pynescript/ast/evaluator/builtins/strategy.py` — Update default margin values

---

### B9: v6 behavior — `dynamic_requests` default true

The `dynamic_requests` parameter in `indicator()`, `strategy()`, `library()` now defaults to `true`.

**Files:**
- `src/pynescript/ast/evaluator/builtins/declarations.py` — Change `dynamic_requests` default to `True`

---

### B10: v6 behavior — color constant value changes

`color.red` → `#F23645`, `color.teal` → `#089981`, `color.yellow` → `#FDD835`. Default label text color → `color.white`.

**Files:**
- `src/pynescript/ast/evaluator/builtins/color.py` — Update color constant values

---

### B11: v6 behavior — `na` not allowed for unique-type params

Parameters expecting unique types (e.g., `plot.style_*`) no longer accept `na`. Switch statements must have `default` blocks.

**Files:**
- `src/pynescript/ast/evaluator/expressions.py` — Validate unique-type params reject `na`

---

### B12: v6 behavior — scope count limit removed

No longer a 550-scope limit. This is a runtime limit change, no code change needed in pynescript (we don't enforce this limit).

**No files to change** — pynescript doesn't enforce scope limits.

---

### B13: v6 behavior — string length limit 40,960

String values can now contain up to 40,960 encoded characters (up from 4,096).

**Files:**
- `src/pynescript/ast/evaluator/literals.py` — Update string length validation if enforced

---

---

### A13: `request.footprint()` + `footprint`/`volume_row` types (Jan 2026)

New `request.footprint()` function and two new data types for volume footprint data.

**Functions:**
- `request.footprint(numTicks, vaPercent)` — requests volume footprint data for the current bar
- `footprint.buy_volume()` — total buy volume
- `footprint.sell_volume()` — total sell volume
- `footprint.delta()` — volume delta (buy - sell)
- `footprint.vah()` — Value Area High row ID
- `footprint.val()` — Value Area Low row ID
- `footprint.poc()` — Point of Control row ID
- `volume_row.up_price()` / `down_price()` — price boundaries
- `volume_row.volume()` — row volume
- `volume_row.buy_volume()` / `sell_volume()` — row buy/sell volume
- `volume_row.delta()` — row volume delta
- `volume_row.up_imbalance()` / `down_imbalance()` — row imbalances
- `volume_row.is_poc()` — is this the Point of Control?
- `volume_row.is_vah()` / `is_val()` — is this a Value Area boundary?

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add builtin names
- `src/pynescript/ast/evaluator/builtins/requests.py` — Add `request.footprint()`
- `src/pynescript/ast/evaluator/builtins/__init__.py` — Register footprint/volume_row namespaces
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A14: `plot()` `linestyle` parameter (Sep 2025)

New `linestyle` parameter for `plot()` to draw dotted and dashed lines.

**Constants:** `plot.linestyle_solid`, `plot.linestyle_dashed`, `plot.linestyle_dotted`

**Files:**
- `src/pynescript/ast/evaluator/builtins/plot.py` — Add `linestyle` param to `plot()`
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A15: `input.*()` `active` parameter (July 2025)

All `input*()` functions gain an `active` parameter (bool). When `false`, the input is grayed out and users cannot change it.

**Files:**
- `src/pynescript/ast/evaluator/builtins/declarations.py` — Add `active` param to all input functions
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update entries

---

### A16: `bid` and `ask` built-in variables (Feb 2025)

New built-in variables for real-time market prices. Only available on `"1T"` timeframe.

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add `bid` and `ask` to builtin names dict
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A17: New `strategy.*` trade statistics variables (May 2024)

Six new strategy built-in variables for trade statistics.

**Variables:** `strategy.avg_trade`, `strategy.avg_trade_percent`, `strategy.avg_winning_trade`, `strategy.avg_winning_trade_percent`, `strategy.avg_losing_trade`, `strategy.avg_losing_trade_percent`

**Files:**
- `src/pynescript/ast/evaluator/builtins/strategy.py` — Add strategy trade stat vars
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A18: `calc_bars_count` parameter (May 2024)

New parameter on `indicator()`, `strategy()`, `request.security()`, `request.security_lower_tf()`, `request.seed()` to limit historical bars executed. Default: 0 (all data).

**Files:**
- `src/pynescript/ast/evaluator/builtins/declarations.py` — Add `calc_bars_count` to indicator/strategy
- `src/pynescript/ast/evaluator/builtins/requests.py` — Add `calc_bars_count` to request.* functions
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update entries

---

### A19: `force_overlay` on plot functions (Apr 2024)

New `force_overlay` parameter on `plot()`, `plotchar()`, `plotcandle()`, `plotbar()`, `plotarrow()`, `plotshape()`, `bgcolor()`.

**Files:**
- `src/pynescript/ast/evaluator/builtins/plot.py` — Add `force_overlay` to all plot functions
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update entries

---

### A20: `str.repeat()` and `str.trim()` string functions (Feb 2024)

Two new string functions for repetition and whitespace trimming.

**Functions:**
- `str.repeat(source, count, separator)` — Repeat string N times with separator
- `str.trim(source)` — Remove leading/trailing whitespace

**Files:**
- `src/pynescript/ast/evaluator/builtins/strings.py` — Add functions
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A21: `strategy.opentrades.capital_held` (Feb 2024)

New strategy variable returning capital held by open trades.

**Files:**
- `src/pynescript/ast/evaluator/builtins/strategy.py` — Add variable
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entry

---

### A22: `syminfo.*` expansion (Jan–Mar 2024)

~16 new syminfo built-in variables for company fundamentals, target prices, and recommendations.

**Variables:** `syminfo.employees`, `syminfo.shareholders`, `syminfo.shares_outstanding_float`, `syminfo.shares_outstanding_total`, `syminfo.target_price_average`, `syminfo.target_price_date`, `syminfo.target_price_estimates`, `syminfo.target_price_high`, `syminfo.target_price_low`, `syminfo.target_price_median`, `syminfo.recommendations_buy`, `syminfo.recommendations_buy_strong`, `syminfo.recommendations_date`, `syminfo.recommendations_hold`, `syminfo.recommendations_total`, `syminfo.recommendations_sell`, `syminfo.recommendations_sell_strong`, `syminfo.expiration_date`

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add all variables
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A23: v6 `text_formatting` parameter (Nov 2024)

New `text_formatting` parameter on `label.new()`, `box.new()`, `table.cell()` for bold/italic text.

**Constants:** `text.format_bold`, `text.format_italic`, `text.format_none`

**Setter functions:** `label.set_text_formatting()`, `box.set_text_formatting()`, `table.cell_set_text_formatting()`

**Files:**
- `src/pynescript/ast/evaluator/builtins/drawing.py` — Add text_formatting support
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries

---

### A24: v6 int values for `size`/`text_size` (Nov 2024)

Labels, boxes, and tables now support int values for `size` and `text_size` properties, representing typographic points.

**Files:**
- `src/pynescript/ast/evaluator/builtins/drawing.py` — Allow int values for size params
- `src/pynescript/langserver/providers/builtin_metadata.json` — Update entries

---

### A25: `syminfo.mincontract` (Nov 2024)

New built-in variable holding the smallest number of contracts/shares/lots/units required to trade the current symbol.

**Files:**
- `src/pynescript/ast/evaluator/names.py` — Add `syminfo.mincontract`
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entry

---

### B14: v6 behavior — short-circuit (`or`/`and`) evaluation (Nov 2024)

`or` and `and` operators now use short-circuit (lazy) evaluation. If the first expression of `or` is `true`, the second is not evaluated. If the first expression of `and` is `false`, the second is not evaluated.

**Files:**
- `src/pynescript/ast/evaluator/expressions.py` — Implement short-circuit logic in or/and evaluation

---

### B15: Updated line wrapping in parentheses (Dec 2025)

Lines wrapped in parentheses can now use any indentation (including multiples of 4 spaces). Non-parenthesized wrapped lines must still use non-multiple-of-4 indentation.

**Files:**
- `src/pynescript/ast/parser.py` — Remove 4-space restriction for parenthesized expressions
- ANTLR grammar may need updates

---

### C4: LSP metadata for new features (A13–A25, B14–B15)

Add metadata entries and completion items for all new features from A13–A25 and B14–B15.

**Files:**
- `src/pynescript/langserver/providers/builtin_metadata.json` — Add entries for all new builtins, params, constants
- `src/pynescript/langserver/providers/completion_items.py` — Update completions

---

## Phase C — LSP Metadata Updates

### C1: New builtins/params/variables metadata

Add metadata entries for all features from A1–A12 to `builtin_metadata.json`.

**Files:**
- `src/pynescript/langserver/providers/builtin_metadata.json`

### C2: New v6 constants metadata

Add metadata for `plot.linestyle_solid`, `plot.linestyle_dashed`, `plot.linestyle_dotted`, `text.format_bold`, `text.format_italic`, `text.format_none`, `backadjustment.*`, `settlement_as_close.*`, `strategy.closedtrades.first_index`.

**Files:**
- `src/pynescript/langserver/providers/builtin_metadata.json`

### C3: Completion items for new types

Update completion items for `footprint` and `volume_row` types and their methods.

**Files:**
- `src/pynescript/langserver/providers/completion_items.py`

---

## Execution Order

```
Phase A1 (original, parallelizable):
  A1  — Negative array indices
  A2  — syminfo.isin
  A3  — syminfo.current_contract
  A4  — timeframe.main_period, syminfo.main_tickerid
  A5  — time/time_close timeframe_bars_back
  A6  — box.set_xloc
  A7  — behind_chart parameter
  A8  — force_overlay parameter
  A9  — sort_field parameter
  A10 — export const
  A11 — PercentageLTP style
  A12 — strategy.exit parameter pairs

Phase A2 (new, parallelizable, no deps):
  A13 — request.footprint() + footprint/volume_row types
  A14 — plot() linestyle parameter
  A15 — input.*() active parameter
  A16 — bid/ask variables
  A17 — strategy.* trade statistics vars
  A18 — calc_bars_count parameter
  A19 — force_overlay on plot functions
  A20 — str.repeat()/str.trim()
  A21 — strategy.opentrades.capital_held
  A22 — syminfo.* expansion (16 vars)
  A23 — text_formatting param
  A24 — int size/text_size values
  A25 — syminfo.mincontract

Phase B1 (original, sequential, grammar first):
  B1  — Multiline strings (grammar change, requires ANTLR regen)
  B2  — Dynamic for-loop boundaries
  B3  — Bool cannot be na
  B4  — Explicit bool casting
  B5  — Fractional const division
  B6  — when param removed
  B7  — transp param removed
  B8  — Default margin 100%
  B9  — dynamic_requests default true
  B10 — Color constant changes
  B11 — na not allowed for unique types
  B12 — Scope limit removed (no change)
  B13 — String length limit 40960

Phase B2 (new, sequential, depends on A2):
  B14 — Short-circuit or/and evaluation
  B15 — Updated line wrapping in parentheses

Phase C1 (original, depends on A1 + B1):
  C1  — New builtins metadata
  C2  — New constants metadata
  C3  — Completion items for new types

Phase C2 (new, depends on B2):
  C4  — Metadata/completion for A13-A25, B14-B15
```

## Testing Strategy

- Each feature A1–A25, B1–B15 gets dedicated test cases
- Existing `.pine` fixtures in `tests/data/builtin_scripts/` must still pass
- Run `make test` after each phase to catch regressions
- LSP tests: `make test-lsp`
- Backend tests: `make test-backend`