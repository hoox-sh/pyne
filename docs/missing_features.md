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

# Missing Features - Pine Script v6 Implementation

**Current Status (as of 2026-08-19, hoox-pyne 0.3.16):** Strong core support (parser + evaluator + **2474** collected tests). Open-source corpus set01–04 (local measurement, not shipped in git): **parse 99.96%** (2476/2477), **Runtime interpret 100% excl. EXPECTED_FAIL** (2466 OK + 11 intentional demos), set01 **249/249** — not a claim of 100% TradingView® platform parity. Drawing `max_*_count` GC landed. **Alert engine + L2 webhooks** closed on Pro API and pyne-worker. **Warm-compile (H2)** + **series caps (T1)** + incremental TA (bb/kama/cmo/stochrsi/wma/hma/linreg + **0.3.10 volume `obv`/`wad`/`wvad`/`cmf`/`klinger`**) landed. Package Runtime SoT + pyne-worker thin wrap landed (**H1** largely done). **Compile object-mode residuals (0.3.16):** UDF locals / free-series capture, nopython `None`/unicode helpers, matrix handles, `x = switch`, UDT returns, drawing/`chart.point` copy, Pine `int(na)`, sanitize chrome. Residual: interpret↔compile plot MISMATCH corpus tail (**P1p**). Incremental `ta.nvi`/`ta.pvi` and Supertrend mid±factor·ATR goldens landed.

**Last Updated:** 2026-08-19 (align with `docs/ROADMAP.md` + 0.3.16; pine-worker is **not** colocated)

**Overall Support Assessment:** ~99%+ for core v6. Multiline strings + `export const` integrated. Remaining gaps are mostly by-design (mock/foreign request data, platform/editor-only) plus long-tail Runtime fails on truncated scrape sources — **not** missing alert/webhook/drawing-GC product surface.
- Parser: Excellent for v5/v6 core + multiline, soft keywords, bitwise, typed UDF returns.
- Evaluator/Builtins: Broad coverage + data context injection + **incremental hot-path TA** + **alert freq engine**.
- Recent: corpus sanitize, series caps, warm-compile, dual-host alerts + L2 webhooks, drawing GC, plot parity harness.
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
- **Binary search in UDT arrays** (August 2026): `array.binary_search()`, `array.binary_search_leftmost()`, `array.binary_search_rightmost()` accept `sort_field` (const int index, default 0, or const string name).
  - **Status**: ✅ Implemented (interpret + compile object-mode; same field-key rules as UDT sort).
- **Other updates** (multiline in editor, line wrapping changes, dynamic loops, bid/ask on 1T, etc.): Mostly editor or minor; runtime support varies (bid/ask referenced in tests).

---

## Current Missing / Incomplete Features List (Accurate as of July 2026)

### High Priority (Syntax / Core Language - Breaks 100% Parser)
- ✅ **Multiline string literals** (`"""` / `'''` delimiters) — resource lexer rules + committed generated lexer; LexerBase preserves triple-quoted newlines/indent (does not strip wrap-indent); unparser emits triple quotes for multiline values; real tests assert content + roundtrip.
- ✅ **Library `export const`** (June 2025) — parse/AST/unparse + **runtime**: library scripts register exports; `import user/Lib/1 as x` resolves via in-process registry / `register_library_source`; `x.MEMBER` attribute access; exported functions callable; **exported types** (`export type` + `.new`) and **enums** (`export enum` + members) via import alias.
- ✅ **UDT collection sorting with `sort_field`** — arrays had support; matrix.sort + matrix.sort_indices now fully implemented in Matrix class + evaluator mixin with int index or str name + UDT get_field keys.
- ✅ **Binary search in UDT arrays** (August 2026) — `array.binary_search*` honor `sort_field` (int index default 0, or string name) on UDT collections, matching sort.
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
- **`request.security` foreign data on compile** — still **not filled**. Compile lowers only chart-symbol simple OHLCV; foreign tickers and complex security expressions emit `na` (no invent of chart series as foreign fundamentals / advance-decline volume). Interpret path may still serve mocks or wired feeds. Parity tests expect all-`na` foreign UDF plots on both hosts when data is absent (`tests/test_dividend_yield_parity.py`).
- **Auto Fib Extension/Retracement (and similar pivot scripts)** — need real pivot/swing structure (or a registered `TradingView/ZigZag` library). Flat synthetic bars intentionally surface the same insufficient-pivot `runtime.error` on interpret and compile (`both_error_same` in `scripts/compare_interp_compile.py`); do not “fix” by inventing pivots.
- ✅ Real effects for plots — Plot dataclass + PlotRegistry; plot(), plotshape, plotarrow now register instances. Other plot* lightweight. Extended ticker styles with PercentageLTP support for renko/kagi/pointfigure.
- Some strategy backtest trimming / unlimited history behaviors (high-level support exists).
- ✅ Strategy runtime depth (2026-07-20): open trades list, signed `strategy.position_size`, `opentrades`/`closedtrades` counts, `netprofit`/`openprofit`/`equity`/`grossprofit`/`grossloss`/`wintrades`/`losstrades`, mark-to-market vs `close`, partial closes; golden multi-bar tests in `tests/test_strategy_runtime.py`.
- ✅ Strategy extended series (2026-07-20): `avg_trade`/`avg_winning_trade`/`avg_losing_trade` + percent forms, `*_percent` for net/open/gross, `cash`, `account_currency`, `position_entry_name`, `opentrades.capital_held`, `closedtrades.first_index`, `eventrades`, `max_drawdown`/`max_runup` (+ percent), `max_contracts_held_*`, `margin_liquidation_price` (na).
- ✅ Drawing `*.all` collections (2026-07-20): `line/box/label/table/polyline.all` return non-deleted DrawingRegistry objects; `linefill.all` empty until modeled.
- ✅ `last_bar_index` / `last_bar_time` resolve as series (context override or bar_index/time fallback).
- ✅ `strategy.risk.max_position_size(percent)` caps entry qty by equity %.
- ✅ Plotting real effects (2026-07-20): all `plot*`/`hline`/`bgcolor`/`barcolor`/`fill` register on `PlotRegistry`; `plot()` returns Plot id for `fill`.
- ✅ request.* data_feed depth: shared `_ohlcv_closes`/`_ticker_last`; MockDataFeed sync `fetch_latest_*`; currency_rate prefers feed pair; seed stored in context.
- ✅ **Numba compile path (MVP, 2026-07-20)**: `pynescript.compiler.compile_script` / `Runtime.run(mode="compile")` — Pine → `@numba.njit` bar loop for ta.sma/ema/rsi, plots, history, inputs. See `docs/COMPILER_PLAN.md`.
- ✅ **Compile object mode (2026-07-20)**: UDTs, maps, full drawing surface auto-switch to Python/numpy bar loop; `__drawings` events + plots.
- ✅ **Compile object-mode corpus residuals (0.3.16)**: UDF `if`/for-in locals, nested UDF free-series (`a_arr` / `vol_arr`), nopython `None`/timezone `timestamp`, object `valuewhen`/`running_max`, matrix UDF/`kron` handles, statement `x = switch`, UDT `Type.new()` returns, `chart.point.copy`/`box.copy`, `pine_int(na)`, sanitize of Hugo/`/* */`/jinja chrome. Leftover: some library-stub `float(None)` / UDF arity, INV expected-fail fixtures, **P1p** plot MISMATCH tail.
- Editor-specific (word wrap defaults, etc.) — irrelevant for this runtime/parser.
- Minor post-2025 behaviors (specific request.* changes, updated wrapping rules if they affect AST).

### Already Well Supported (from v6+)
- Dynamic requests (core), short-circuit bool logic, negative array indices, truediv, polylines, logging, bid/ask refs, var/varip, most TA/strategy builtins, UDTs, collections, full parser for pre-2026 v6.

---


### Matrix surface (2026-07-25)
- ✅ Official TV matrix linear algebra: `det`, `inv`, `pinv`, `eigenvalues`, `eigenvectors`, `kron`, `pow`, `trace`, `rank`, `mult`, `diff`
- ✅ Official names: `matrix.avg/min/max/mode/sum/median/stdev/variance`, `row`/`col`/`submatrix`/`sort`/`sort_indices`/`reverse`/`swap_*`
- ✅ Predicate suite: `is_square/zero/identity/diagonal/antidiagonal/symmetric/antisymmetric/triangular/binary/stochastic`
- ✅ `runtime.error`, `input.text_area`, `ta.percentile_linear_interpolation`, `ta.percentile_nearest_rank`
- ✅ `input.*` now returns values (Pine semantics) with metadata side-channel `_input_declarations`

### Full reference surface (2026-07-25 cont.)
- ✅ **0 missing** vs official TV v6 function reference list (434 symbols checked against live dispatch)
- ✅ TA: `ta.alma`, `ta.bbw`, `ta.cmo`, `ta.correlation`
- ✅ Drawing: full `linefill.*`, `line.get_price`/`set_xy*`/`set_*_point`, box text setters, label `set_point`/`set_size`/`set_textalign`, table cell/frame setters
- ✅ `strategy.risk.max_drawdown` / `max_cons_loss_days` / `allow_entry_in`
- ✅ `max_bars_back`, `ticker.inherit`
- ✅ Footprint/volume_row accessors (`rows`, `total_volume`, `get_row_by_price`, imbalances)
- ✅ Runtime plot values are **bar scalars** (not nested full-series lists)
- ✅ Bar-mode TA (`_pine_bar_mode`): `ta.sma/ema/rma/vwma/atr/tr` return current scalar in Runtime, full series in unit/list mode
- ✅ `strategy.risk.allow_entry_in` / `max_drawdown` / `max_cons_loss_days` **enforced** at `strategy.entry` (blocked entries emit `order` + `risk_blocked`)
- ✅ Inventory summary regenerated from live dispatch (640 callables)
- ✅ Broker: `process_pending_orders` fills limit/stop/stop-limit (and market next bar); partial fills via `max_fill_per_bar`; stop/limit `strategy.entry` pending; `na` prices coerced
- ✅ `ta.kama`/`dema`/`tema` bar-mode scalars; `request.seed` seeds stdlib + numpy for reproducible mocks
- ✅ OCA: `strategy.oca.none/cancel/reduce` + oca_name/type on orders; fill cancels/reduces siblings
- ✅ Commission (`percent` / `cash_per_order` / `cash_per_contract`) + slippage ticks from `strategy()` kwargs; applied on fills
- ✅ **Compile-mode strategy** (object mode): `CompileStrategyBroker` emits entry/close/order/cancel events; `Runtime.run(..., mode="compile")` returns `events`; position_size/equity/netprofit available
- ✅ **Compile pending fills**: limit/stop/stop-limit/market pending orders + OCA reduce/cancel; `process_pending_orders` each bar before script body (interpreter-aligned)
- ✅ **Datafeed wiring**: `ChartOHLCVProvider` from Runtime bars; `resolve_request_sources()`; Composite sync `fetch_latest_*`; `/run` accepts `data_source`/`data_options`/`symbol`

### Corpus + Runtime performance (2026-07-28)

Open-source Pine corpus (`tests/data/set01`–`set04`) and bar-loop throughput work. Plan:
`.opencode/plans/2026-07-28-runtime-performance.md`, skill `.grok/skills/pynescript-perf/`.

#### Parser / sanitize (closed)
- ✅ Soft keywords, bitwise ops, `=` reassignment, typed UDF returns (`int f(n) => …`)
- ✅ `corpus_sanitize` for scrape chrome (fences, FMZ footers, missing commas between `var` decls)
- ✅ Parse rate set01–04 **99.96%** (2476/2477); residual **1** intentional invalid line-wrap docs demo (not a grammar hole). Truncated scrapes recovered via sanitize where high-confidence

#### Runtime host hygiene (closed — no semantic change)
- ✅ `_pine_defs_locked` after first bar (pynescript backend + **pyne-worker**) — stops O(bars²) FunctionDef/method multi-dispatch growth
- ✅ Append-only `current_series` OHLCV lists (no per-bar `list(reversed(history))` rebuild)
- ✅ One-pass derived prices (`hl2`/`hlc3`/…) per bar on worker host
- ✅ Worker aligns with backend: `_pine_bar_mode` + `_pine_ta_incremental` (default on)

#### Incremental bar-mode TA (closed — golden ≡ full recompute)
Call-site state (`_ta_call_i` reset each bar), one sample per site per bar (safe with `_SERIES_MAX`):

| Builtin | Notes |
| --- | --- |
| ✅ `ta.sma` / `ta.ema` / `ta.rma` / `ta.rsi` | O(period) / O(1) vs full-history recompute |
| ✅ `ta.macd` | Fast/slow/signal internal EMAs, one slot |
| ✅ `ta.atr` | Matches current full path (EMA of TR after warm-up mean) |

- Golden: `tests/test_ta_incremental.py` (inc ≡ full last values; Runtime on vs `PYNE_TA_INCREMENTAL=0`)
- Disable: env **`PYNE_TA_INCREMENTAL=0`**
- Bench (≈3264 BTC daily bars, worker Runtime): **~9.5×** `ta_sma`, **~4.9×** sma+ema+rsi, **~3×** macd, **~10×** atr, **~8.5×** macd+atr+rsi+sma combo vs flag off

#### Still open / residual (not “missing syntax”)

| ID | Item | Pri |
| --- | --- | --- |
| **H1** | Dual-host Runtime unify | P1 ✅ package SoT `pynescript.runtime` + backend shims + **pyne-worker thin wrap** (sibling repo, not colocated) — residual CF deploy smoke only |
| **H2** | Product warm-compile path (SLOs, prewarm, IR cache on in deploy) | P1 ✅ (2026-08) |
| **C1** | Corpus Runtime residual | P1 ✅ (2026-08-09) — set01–04 Runtime interpret **100%** excl. EXPECTED_FAIL (2466 OK + 11 intentional demos); parse **99.96%**. Residual = intentional demos only. set05 long-tail separate |
| **T1** | Cap unbounded `current_series` lists to `max_bars_back` / `_SERIES_MAX` | P2 ✅ R7 — `PYNE_SERIES_CAP` (default ON), `PYNE_SERIES_MAX`, goldens `tests/test_series_cap.py` |
| **T2** | Incremental for remaining heavy kernels | P2 ✅ R7: bb/kama/cmo/stochrsi + wma/hma/linreg; **0.3.10** `obv`/`wad`/`wvad`/`cmf`/`klinger` + `nvi`/`pvi`; **aroon/dpo/donchian/kst** |
| **L2** | Webhook alerts productization | P3 ✅ pyne-worker + Pro API `/run` export + outbound `ALERT_WEBHOOK_URL` / `webhook_url` |
| **F1** | `ta.atr` is **Wilder RMA of TR** (interpret + Numba). Supertrend is simplified mid±factor·ATR (not TV ratchet); goldens lock that contract | P2 ✅ |
| — | Bit-identical recursive smoothers vs live TV | numerical-parity track |
| — | Drawing `max_*_count` GC / alert engine | ✅ shipped (not missing) |

Canonical priority table: `docs/ROADMAP.md`.

#### Corpus Runtime snapshot (set01–set04, 50 bars · 2026-08-09)

| Stage | Parse | Runtime interpret |
| --- | ---: | ---: |
| Historical baseline (pyne-worker) | — | 1851 / 2477 (**74.7%**) |
| After early fail re-runs | — | ~2224 / 2477 (**89.8%**) projected |
| After C1 8-agent pass (2026-08-01) | ~94.8% era | ~2337 / 2477 (**94.3%**) projected |
| **Current (pynescript Runtime, 2026-08-09)** | **2476 / 2477 (99.96%)** | **2466 OK + 11 EXPECTED_FAIL → 100% excl. intentional demos** |

- set01 Runtime: **249 / 249 (100%)**
- EXPECTED_FAIL (11): intentional library `runtime.error` demos, lower-TF security guards, invalid line-wrap docs demo, truncated mid-call scrape, pathological nested-loop demo
- Not shipped in-repo (legal / ToS hygiene); measured locally from pre-drop restore
- Not a claim of TradingView® platform or bit-identical execution parity

## Recommendations
- Prefer **golden tests vs current oracle** before changing TA seed rules (ATR→RMA, VWMA volume, etc.).
- Land evaluator/TA math in `src/pynescript/ast/evaluator/`; keep pyne-worker as thin host (timeout/R2/CF).
- Re-run corpus fails only via `scripts/corpus_rerun_fails.py` / pyne-worker `scripts/corpus_rerun_fails.py` after each fix.
- Update `pinescript_implementation_status.md` and this file after each addition.
- Current overall: Excellent for most real-world scripts (parser + common builtins + bar Runtime). Not drop-in 100% for latest 2026 platform/editor-only or exotic broker edges.

See also:
- `docs/pine_v6_full_surface_inventory.md` — **full schema + every inventory name** (dispatch, series, language, graphs)
- `docs/pinescript_implementation_status.md` (detailed ✅ matrix)
- `tests/test_v6_features.py` (good coverage of dynamic requests, footprint, etc.)
- Official: https://www.tradingview.com/pine-script-docs/release-notes/ and migration guide to v6.

---

## 🎉 Project Completion Status

PyneScript core is mature, with significant July 2026 enhancements:

- ✅ **Strategy Events** - Full StrategyEvent capture, parity corpus (13+ tests), strategy.long/short constants, var/varip + ReAssign support.
- ✅ **pine-worker** — legacy TypeScript Cloudflare Worker in sibling [`hoox-sh/pine-worker`](https://github.com/hoox-sh/pine-worker) (**not** colocated). New TS library work is [`@hoox-sh/pynets`](https://github.com/hoox-sh/pynets) (`pynets/` submodule here).
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
- ✅ Alerts: alert, alertcondition (+ freq rules, host export, pyne-worker last-bar + webhooks)

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

1. **Mock / host data** - `request.*` uses mock or host-injected feeds; foreign symbols on compile emit `na` (no invented multi-asset series)
2. **Not a TV chart host** - Plot/drawing/fill are registry + export for AXIS/clients; pixels are external
3. **Deterministic bar evaluation** - Interpreter + optional Numba compile (`mode=auto` / warm-compile); not a licensed broker
4. **Realtime optional** - CCXT Pro / composite feeds exist; live multi-symbol TV-grade data remains host responsibility

### Practical Constraints

1. **Performance** - Interpret is Python-first; compile + incremental TA + series caps harden bar loops (not HFT microsecond infra)
2. **Numerical Precision** - IEEE 754 float-based; interpret↔compile plot parity harness tracks residuals (not bit-identical every smoother vs live TV)
3. **Memory** - Series capped via `PYNE_SERIES_CAP` / `max_bars_back`; large matrices/arrays still proportional
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
   - ✅ Webhook support for alerts (pyne-worker + Pro API L2; `ALERT_WEBHOOK_URL` / `webhook_url`)

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
- pine-worker is **not** in this tree (removed 0.3.7). Sister [`hoox-sh/pine-worker`](https://github.com/hoox-sh/pine-worker) holds the legacy TS Worker + historical `scripts/convert-python-to-ts.py`. PyneTS (`pynets/` submodule / standalone `hoox-sh/pynets`) is the TS library.
- var / varip declaration modes and ReAssign handling.
- Updated test coverage with dedicated `test_strategy_events.py` and `test_parity.py`.

**Conclusion:** Core Pine Script language/builtins are mature. July–August 2026 work added strategy events, package Runtime SoT, corpus hardening, incremental TA (through 0.3.10 volume kernels), and dual-host hosts. The TypeScript Worker is a **sister** repo, not an in-tree extra. Remaining work is plot-parity residual, leftover full-list TA (`nvi`/`pvi`), optional fidelity goldens, and real data adapters — not missing syntax.

---

_Last updated: 2026-08-17_  
_Version: 1.3 (0.3.12)_
