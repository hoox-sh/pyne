# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

# Missing Features - Pine Script v6 Implementation

**Current Status (as of 2026-07):** Strong core support (parser + evaluator + 1142+ tests passing). Full suite: 1142 passed. Not 100% for all post-v6 launch features.

**Last Updated:** 2026-07-20 (multiline triple-quoted strings fully wired; library `export const` parse/AST/unparse; tests no longer placeholders)

**Overall Support Assessment:** ~99%+ for core v6. Multiline strings + `export const` integrated (grammar/lexer + builder/unparser). Remaining gaps are mostly by-design (mock request data, platform/editor-only). 
- Parser: Excellent for v5/v6 core + multiline, dynamic etc.
- Evaluator/Builtins: Broad coverage + data context injection.
- Recent: datafeed (CCXTPro/Mock/Composite + Broker + evaluator wiring) + backend/runtime support, enums type kind + improved access.
- Full test runs + lint clean targeted. See details.

---

## Latest Pine Script Releases & Gaps (2024-2026)

Pine Script v6 launched December 2024, followed by monthly updates. Key sources: official release notes and migration guide.

### v6 Launch Features (Dec 2024) - Mostly Supported
- ✅ Dynamic requests (series strings for symbol/tf by default, inside loops/conditionals/scopes) — partial-to-good support in request.py + extensive tests.
- ✅ Strict `bool` (never `na`); short-circuit `and`/`or` — implemented in expressions.py.
- ✅ `text_size` as `int` (points) + `text_formatting` (bold/italic) — partial (noted in plotting.py, drawing).
- ✅ Enums, polylines, runtime logging (`log.*`), negative array indices, `truediv` (5/2=2.5), strategy improvements — supported or stubbed.
- ✅ Full dynamic `request.*()` for *every* function + all contexts — expanded with shared _resolve_symbol + _get_request_data helpers. security/lower_tf + dividends/earnings/splits/financial/quandl/economic/currency/footprint now support dynamic symbols (list/series last), data_feed scaling where applicable. 

### 2025-2026 Monthly Updates - Significant Gaps
- **Footprint requests** (Jan 2026): `request.footprint()`, `footprint` type, `volume_row` type + methods (`buy_volume()`, `vah()`, etc.). 
  - **Status**: ✅ Mock data generator + methods + now dynamic symbol + data_feed volume scaling in _handle_request_footprint. 
- **active parameter on `input.*()`** (July 2025): `active` to enable/disable inputs in settings.
  - **Status**: ✅ Integrated — accepted across all input handlers, stored in metadata dict (default true). Metadata-driven for backends/LSP.
- **Multiline strings** (`"""..."""` / `'''...'''`, April 2026): Literal strings spanning lines (auto newlines, literal indentation).
  - **Status**: ✅ Fully wired (2026-07-20). Generated lexer includes `TRIPLE_*` rules; LexerBase skips wrap-indent stripping for triple quotes; unparser prefers `"""..."""` when value has newlines.
- **Library `export const`** (June 2025): Export const int/float/bool/color/string from libraries.
  - **Status**: ✅ Implemented (2026-07-20). Parser `EXPORT?` on name initialization; Assign.export in ASDL; builder + unparser.
- **Sorting UDT collections with `sort_field`** (April 2026): `array.sort()`, `array.sort_indices()`, `matrix.sort()` accept `sort_field` (const int index or string name) for UDT arrays/matrices.
  - **Status**: ✅ Implemented (arrays pre-existing; matrix added with UDT key support + basic numeric sort).
- **Other updates** (multiline in editor, line wrapping changes, dynamic loops, bid/ask on 1T, etc.): Mostly editor or minor; runtime support varies (bid/ask referenced in tests).

---

## Current Missing / Incomplete Features List (Accurate as of July 2026)

### High Priority (Syntax / Core Language - Breaks 100% Parser)
- ✅ **Multiline string literals** (`"""` / `'''` delimiters) — resource lexer rules + committed generated lexer; LexerBase preserves triple-quoted newlines/indent (does not strip wrap-indent); unparser emits triple quotes for multiline values; real tests assert content + roundtrip.
- ✅ **Library `export const`** (June 2025) — parse/AST/unparse + **runtime**: library scripts register exports; `import user/Lib/1 as x` resolves via in-process registry / `register_library_source`; `x.MEMBER` attribute access; exported functions callable; **exported types** (`export type` + `.new`) and **enums** (`export enum` + members) via import alias.
- ✅ **UDT collection sorting with `sort_field`** — arrays had support; matrix.sort + matrix.sort_indices now fully implemented in Matrix class + evaluator mixin with int index or str name + UDT get_field keys.
- ✅ Additional v6 syminfo/timeframe constants (isin, current_contract, main_tickerid, main_period) added to default context.
- ✅ behind_chart on indicator/strategy/library, force_overlay on drawing objects (line, box, label, polyline, table) and plot() - captured in metadata and ctors.
- ✅ timeframe_bars_back documented and accepted in time()/time_close().

### Medium Priority (Builtins / Recent Additions)
- ✅ **Full `request.footprint()` + footprint/volume_row types and methods**. Mock data generator + all listed methods (buy/sell/delta/vah etc) implemented in request.py. (Real data by design not present.)
- ✅ **`active` parameter** on all `input.*()` functions — accepted in all handlers (generic + specific bool/int/float/.../enum/color), stored in returned metadata dict with default True. Runtime/UI effect is metadata-driven (for backends/LSP); integrated July 2025+ followups.
- ✅ **Complete `text_formatting` + integer `text_size`** — text_size now supports int (points) or size.* consts in Label (and context has size.auto/tiny/...). text_formatting wired for labels. Extended to plot(). Real size values supported.
- ✅ **Dynamic requests** full coverage: all major request.* now use dynamic resolution; works inside loops/conditionals (args visited by evaluator). Datafeed provides live values. 
- ✅ Dynamic `for` loop end bounds (v6): now re-evaluated each iteration in visit_ForTo.
- ✅ **Enums** full runtime + type integration — visit_EnumDef, member .attr access, symbolic + value support, context storage, works in expr/switch/assign. Added BuiltinTypeKind.ENUM + registry entry. input.enum supported (metadata + defaults). LSP semantic tokens + metadata; completion/hover for user enums partial. 
- ✅ strategy.exit() v6 pair evaluation (limit/profit + stop/loss) — chooses based on current price which activates first.
- ✅ ticker renko/pointfigure/kagi support "PercentageLTP" style (v6).
- ✅ **Realtime data feeds** (CCXT Pro + Mock/Composite) — full module, sync wrappers, broker for orders/positions, wired to request.security + lower_tf + evaluator context + backend. (July 2026)
- ✅ **Strict boolean semantics** — core short-circuit, na->false in conditions implemented in expressions/statements. Edge cases covered in v6 tests; no `na` bools in main paths. 

### Lower Priority / Platform Features
- Real (non-mock) data for `request.*()` (by design for this library).
- ✅ Real effects for plots — Plot dataclass + PlotRegistry; plot(), plotshape, plotarrow now register instances. Other plot* lightweight. Extended ticker styles with PercentageLTP support for renko/kagi/pointfigure.
- Some strategy backtest trimming / unlimited history behaviors (high-level support exists).
- ✅ Strategy runtime depth (2026-07-20): open trades list, signed `strategy.position_size`, `opentrades`/`closedtrades` counts, `netprofit`/`openprofit`/`equity`/`grossprofit`/`grossloss`/`wintrades`/`losstrades`, mark-to-market vs `close`, partial closes; golden multi-bar tests in `tests/test_strategy_runtime.py`.
- ✅ Strategy extended series (2026-07-20): `avg_trade`/`avg_winning_trade`/`avg_losing_trade` + percent forms, `*_percent` for net/open/gross, `cash`, `account_currency`, `position_entry_name`, `opentrades.capital_held`, `closedtrades.first_index`, `eventrades`, `max_drawdown`/`max_runup` (+ percent), `max_contracts_held_*`, `margin_liquidation_price` (na).
- ✅ Drawing `*.all` collections (2026-07-20): `line/box/label/table/polyline.all` return non-deleted DrawingRegistry objects; `linefill.all` empty until modeled.
- ✅ `last_bar_index` / `last_bar_time` resolve as series (context override or bar_index/time fallback).
- ✅ `strategy.risk.max_position_size(percent)` caps entry qty by equity %.
- ✅ Plotting real effects (2026-07-20): all `plot*`/`hline`/`bgcolor`/`barcolor`/`fill` register on `PlotRegistry`; `plot()` returns Plot id for `fill`.
- ✅ request.* data_feed depth: shared `_ohlcv_closes`/`_ticker_last`; MockDataFeed sync `fetch_latest_*`; currency_rate prefers feed pair; seed stored in context.
- Editor-specific (word wrap defaults, etc.) — irrelevant for this runtime/parser.
- Minor post-2025 behaviors (specific request.* changes, updated wrapping rules if they affect AST).

### Already Well Supported (from v6+)
- Dynamic requests (core), short-circuit bool logic, negative array indices, truediv, polylines, logging, bid/ask refs, var/varip, most TA/strategy builtins, UDTs, collections, full parser for pre-2026 v6.

---

## Recommendations
- **Grammar first**: Add triple-quoted multiline string support to `PinescriptLexer.g4` + handling in lexer/parser.
- **Arrays/Drawing**: Implement `sort_field` logic + full text_formatting.
- **Request/Types**: Flesh out footprint objects and dynamic handling.
- Update `pinescript_implementation_status.md` and this file after each addition.
- Add dedicated tests for multiline strings and UDT sort_field once implemented.
- Current overall: Excellent for most real-world scripts (parser + common builtins). Not drop-in 100% for latest 2026 syntax/features.

See also:
- `docs/pine_v6_full_surface_inventory.md` — **full schema + every inventory name** (dispatch, series, language, graphs)
- `docs/pinescript_implementation_status.md` (detailed ✅ matrix)
- `tests/test_v6_features.py` (good coverage of dynamic requests, footprint, etc.)
- Official: https://www.tradingview.com/pine-script-docs/release-notes/ and migration guide to v6.

---

## 🎉 Project Completion Status

PyneScript core is mature, with significant July 2026 enhancements:

- ✅ **Strategy Events** - Full StrategyEvent capture, parity corpus (13+ tests), strategy.long/short constants, var/varip + ReAssign support.
- ✅ **pine-worker** - TypeScript port of evaluator + Python→TS converter script as extra tool (colocated in repo).
- ✅ **200+ Built-in Functions** (including advanced strategy)
- ✅ **1000+ Tests** (core + parity + strategy events green)
- ✅ **Complete Parser** - Full support for Pine Script v5-v6 grammar
- ✅ **Full AST Support** - Complete abstract syntax tree representation
- ✅ **Expression Evaluator** - Evaluate deterministic expressions and functions
- ✅ **Type System** - All Pine Script types implemented
- ✅ **Collections** - Arrays, matrices, and maps fully supported
- ✅ **Drawing Objects** - All plot and drawing functions available
- ✅ **Strategy Functions** - Strategy execution framework implemented

---

## 🚀 What's Implemented

### Parser & Language Features

- ✅ Full Pine Script v5-v6 grammar support
- ✅ ANTLR4-based parsing with robust error handling
- ✅ Complete type system (int, float, bool, string, color, series, array, matrix, map)
- ✅ User-defined types (UDT) and objects
- ✅ Control flow (if/else, for, while)
- ✅ Functions and methods
- ✅ Comments and annotations
- ✅ String interpolation and formatting

### Built-in Functions (149+)

#### Technical Analysis (85+ functions)

- ✅ Moving averages: SMA, EMA, WMA, VWMA, HMA, DEMA, TEMA, SWMA
- ✅ Oscillators: RSI, MACD, Stochastic, Williams %R, CCI, CMO
- ✅ Trend: ADX, Keltner Channels, Bollinger Bands, Supertrend
- ✅ Volume: OBV, MFI, Volume Rate of Change
- ✅ Momentum: ROC, KDJ, Ichimoku, Zigzag, Linear Regression
- ✅ Correlation: RCI, Rank Correlation Index
- ✅ Pattern Detection: Pivots, Support/Resistance

#### Math Functions (20+ functions)

- ✅ Basic: abs, max, min, pow, sqrt, log
- ✅ Rounding: round, floor, ceil, round_to_mintick
- ✅ Trigonometry: sin, cos, tan, asin, acos, atan
- ✅ Statistical: sum, avg, stddev, variance

#### String Functions (15+ functions)

- ✅ Case conversion: upper, lower
- ✅ Search: contains, startswith, endswith, substring
- ✅ Formatting: tostring, tonumber, format
- ✅ Length and manipulation

#### Array Functions (25+ functions)

- ✅ Basic: size, get, push, pop, slice, join
- ✅ Searching: includes, indexof, lastindexof, findindex
- ✅ Statistics: sum, avg, min, max, stddev, variance
- ✅ Percentiles: percentile_linear_interpolation, percentile_nearest_rank
- ✅ Binary search: binary_search_leftmost, binary_search_rightmost
- ✅ Sorting: sort, reverse, sort_indices

#### Time Functions (10+ functions)

- ✅ Time extraction: year, month, dayofmonth, dayofweek, hour, minute, second
- ✅ Timestamps: time, timestamp, time_close, weekofyear
- ✅ Utilities: timenow, time_tradingday

#### Drawing Functions (10+ functions)

- ✅ Plotting: plot, plotarrow, plotbar, plotcandle, plotchar, plotshape
- ✅ Overlays: fill, hline, bgcolor, barcolor
- ✅ All with styling options

#### Strategy Functions (15+ functions)

- ✅ Orders: entry, exit, close, closeallornoorder
- ✅ Position management: position management hooks
- ✅ Risk management: stop loss, take profit
- ✅ Accounting: entry price, position size

#### Input Functions (10+ functions)

- ✅ All input types: int, float, bool, string, symbol, session, source, time, timeframe, color, price
- ✅ Input validation and constraints
- ✅ Group organization

#### Request Functions

- ✅ Security data requests
- ✅ Economic indicators
- ✅ Splits and dividends data
- ✅ Mock implementations for testing

#### Utility Functions (10+ functions)

- ✅ Type checking: na, nz, fixnan
- ✅ Type conversion: int, float, bool, string
- ✅ Color operations: color.new, color.rgb
- ✅ Alerts: alert, alertcondition

### Collections

- ✅ Arrays with full manipulation support
- ✅ Matrices with linear algebra operations
- ✅ Maps with key-value storage
- ✅ Statistical operations on all collections

### Advanced Features

- ✅ Series history access (close[0], close[1], etc.)
- ✅ Expression evaluation engine
- ✅ AST transformation framework
- ✅ Complete round-trip parsing (parse → transform → unparse)
- ✅ Type inference and checking

---

## 📊 Implementation Metrics

| Metric | Value |
|--------|-------|
| **Built-in Functions Implemented** | 149+ |
| **Total Test Coverage** | 997 tests |
| **Test Pass Rate** | 100% |
| **Grammar Completeness** | ~95% |
| **Parser Success Rate** | ~99% |
| **Lines of Code** | 15,000+ |
| **Documentation Coverage** | 100+ pages |

---

## 🔄 Known Limitations

### Intentional Design Decisions

1. **Mock Data** - Request functions return synthetic test data, not real market data
2. **Interpretation Only** - No JIT compilation or optimization
3. **Deterministic Evaluation** - Evaluator covers deterministic values and built-ins
4. **No Real-Time Data** - Not designed for live trading feeds

### Practical Constraints

1. **Performance** - Pure Python implementation, not optimized for high-frequency operations
2. **Numerical Precision** - IEEE 754 float-based, subject to floating-point precision limits
3. **Memory** - Large matrices/arrays consume proportional memory (no sparse implementations)
4. **Unicode** - Limited support for non-ASCII characters in some edge cases

---

## 🎯 Future Enhancement Opportunities

### High Value (Nice to Have)

1. **Real Data Integration**
   - Live market data feeds
   - Actual economic indicators
   - Real stock split/dividend data

2. **Performance Optimizations**
   - JIT compilation for critical paths
   - Vectorized array operations
   - Caching for repeated calculations

3. **Extended Analysis**
   - Machine learning indicator wrappers
   - Advanced statistical functions
   - Complex derivation functions

### Medium Value (Polish)

1. **Developer Experience**
   - IDE integration and autocomplete
   - Debugging tools and profiling
   - Better error messages

2. **Documentation**
   - Video tutorials
   - Interactive examples
   - Real-world trading examples

3. **Integration**
   - Jupyter notebook support
   - API server for remote execution
   - Webhook support for alerts

### Low Value (Research)

1. **Experimental Features**
   - Parallel execution
   - Distributed computing
   - Graph-based optimization

2. **Research Tools**
   - Formal verification
   - Symbolic execution
   - Constraint solving

---

## 📝 Recommendations

### For Users

- ✅ Use pynescript for Pine Script analysis and transformation
- ✅ Leverage 149+ built-in functions for calculations
- ✅ Parse and unparse scripts for validation and normalization
- ✅ Transform ASTs for custom script modifications
- ✅ Evaluate expressions for deterministic computations

### For Contributors

- Contribute real data adapters for request functions
- Optimize hot paths for performance-critical use cases
- Extend evaluator for additional deterministic functions
- Add domain-specific analysis tools
- Improve error messages and diagnostics

### For Production Deployment

- ✅ Suitable for offline script analysis
- ✅ Good for batch processing and validation
- ✅ Excellent for educational purposes
- ⚠️ Limited for real-time trading (mock data only)
- ⚠️ Requires additional components for live integration

---

## 📚 Related Documents

- **[Implementation Status](docs/pinescript_implementation_status.md)** - Detailed feature matrix
- **[Progress Report](docs/PROGRESS_REPORT.md)** - Historical development notes
- Phase 8 (advanced indicators) completed as part of core implementation. See consolidation plan for details.
- **[Consolidation Plan (2026-07-09)](.opencode/plans/2026-07-09-main-consolidation-remaining-work.md)** - Current remaining work and integration

---

## July 2026 Additions (Main Consolidation)

- Full strategy event system: `StrategyEvent` dataclass, event emission from all strategy.* calls, bar_index/time threading, parity fixtures for testing against TS port.
- `pine-worker/` directory: TypeScript re-implementation of key evaluator parts + `scripts/convert-python-to-ts.py` for porting aid. Treated as extra tool of the main repo.
- var / varip declaration modes and ReAssign handling.
- Updated test coverage with dedicated `test_strategy_events.py` and `test_parity.py`.

**Conclusion:** PyneScript has successfully implemented all core Pine Script features. The project provides a robust, well-tested foundation. July 2026 work added first-class strategy events and a colocated TS port. Future work focuses on enhancements (perf, LSP polish, converters, real data) per the consolidation plan.

---

_Last updated: 2026-07-09_  
_Version: 1.1_
