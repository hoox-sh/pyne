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

# Missing Features — Pine Script v6 Implementation

**Live package:** `hoox-pyne` **0.6.23** (`src/pynescript/__about__.py`).

---

## Summary

PYNE implements Pine Script™ v5/v6 as a complete parse → AST → bar-loop evaluation pipeline. The core language, builtins, strategy broker, collections, and drawing surface are fully functional. This document describes the architecture, what is implemented, and where intentional boundaries exist.

The open-source corpus (set01–04, 2,477 scripts) achieves **99.96%** parse success and **100%** runtime interpretation (excluding 11 intentional demo scripts that test error paths). This is not a claim of TradingView® platform parity — it is a measure of language coverage.

---

## Architecture

PYNE's evaluation pipeline has four stages:

1. **Lexer** (ANTLR4-generated) — tokenizes Pine source, including multiline strings, soft keywords, and bitwise operators
2. **Parser** (ANTLR4) — produces an ASDL AST with full structural fidelity
3. **Builder** — transforms the parse tree into the evaluator's node representation
4. **Evaluator** (`NodeLiteralEvaluator`) — walks the AST in bar-loop mode, dispatching builtins through a registry of 941 callables across 255 namespaces

The compile path (`mode="compile"`) lowers the AST to Python/numpy source, optionally JIT-compiled via Numba. Scripts using UDTs, maps, or drawings automatically fall back to an object-mode Python bar loop.

---

## What Is Implemented

### Language Core

The full v5/v6 language surface is implemented: variables and types, control flow (`if`/`for`/`while`/`switch`/`once`), functions and methods with type annotations, user-defined types (UDTs) with `.new`, libraries with `export`/`import`, enums, string interpolation, tuple unpacking, and method chaining. Series history access (`close[n]`) follows Pine semantics — out-of-bounds and negative indices return `na`.

Line wrapping is supported at any indentation level inside parentheses and square brackets. The `table.new` constructor uses Pine's columns-then-rows argument order.

### Builtins and Technical Analysis

All 434 symbols from the public TradingView® v6 function reference are registered in the dispatch inventory. The `ta.*` namespace includes 165 functions covering moving averages (SMA, EMA, RMA, WMA, HMA, VWMA, KAMA, DEMA, TEMA, ALMA), oscillators (RSI, MACD, Stochastic, CCI, CMO, TSI, ROC, WPR), volatility and structure (ATR, Bollinger Bands, Keltner Channels, Standard Deviation, Linear Regression, ADX/DMI, Supertrend, SAR), and volume indicators (OBV, WAD, WVAD, CMF, Klinger, MFI, VWAP, NVI, PVI).

Incremental bar-mode evaluation is the default for performance-critical kernels. Each TA function maintains call-site state and updates one sample per bar, achieving 3–10x speedups over full recompute on multi-thousand-bar series. This can be disabled via `PYNE_TA_INCREMENTAL=0`.

### Strategy and Broker

The strategy engine emits `StrategyEvent` objects for entries, exits, orders, and cancels. It supports OCA groups (none/cancel/reduce), commission models (percent, cash per order, cash per contract), slippage in ticks, and risk enforcement (max position size, max drawdown, max consecutive loss days, intraday loss limits, directional filters).

Pending fills are processed each bar before the script body: limit, stop, and stop-limit orders activate when their price conditions are met. Market orders fill on the next bar. Partial fills are supported via `max_fill_per_bar`.

### Collections

Arrays, matrices, and maps are fully implemented. Arrays support negative indices, UDT `sort_field` on `array.sort()` and `array.binary_search*()`. Matrices include linear algebra operations (determinant, inverse, eigenvalues, Kronecker product, trace, rank) and predicates (symmetric, triangular, stochastic, etc.).

### Drawing and Plotting

All drawing objects — `line`, `box`, `label`, `table`, `polyline`, `linefill` — are implemented with full property accessors. The `plot()` family (`plot`, `plotshape`, `plotchar`, `plotarrow`, `plotbar`, `plotcandle`) registers on a `PlotRegistry`. Drawing garbage collection (`max_*_count`) is enforced on the package, Pro API, and AXIS hosts.

Drawing export parity is maintained between interpret and compile modes: both hosts emit cell styles, dimensions, tooltips, `force_overlay`, `merged_cells`, and polyline curve/fill properties.

### Alerts and Webhooks

The alert engine supports all frequency rules (`alert.freq_once_per_bar`, `alert.freq_all`, etc.). Webhook delivery is available on both the Pro API and pyne-worker via `ALERT_WEBHOOK_URL` or per-call `webhook_url`.

### Data and Requests

`input.*` functions return values with metadata side-channels for backends and LSP. The `active` parameter is accepted across all input handlers. `request.*` functions support dynamic symbols (series strings) inside loops and conditionals. Same-symbol OHLCV and HTF requests are resolved; foreign symbols and complex expressions return `na` rather than inventing data.

Data providers include Mock, Yahoo Finance, AlphaVantage, and CCXT (100+ crypto exchanges). A realtime datafeed using CCXT Pro is integrated into the evaluator context.

### Compiler

The Numba compile path handles pure numeric scripts: series assignments, arithmetic, history access, control flow, selected `ta.*` routines, tuple unpack, scalar math, plots, and `var`/`varip` persistence. Object mode handles UDTs, maps, and drawings. Warm-compile with disk IR cache is available via prewarm API/CLI.

---

## What Is Partial or by Design

### Request Data

`request.security` on foreign symbols or complex expressions returns `na` on both interpret and compile hosts. This is an honest policy — no chart-close is invented as foreign fundamentals. Fundamental fields (`request.dividends` / `earnings` / `splits` / `financial` / `quandl` / `economic` / `currency_rate`) follow the same rule: without a host `fetch_fundamental(kind, symbol, **params)` hook on `data_feed` / `data_provider` (or a live feed FX pair for `currency_rate`) they return `na` — the former mock tables are gone. Real multi-symbol market data requires a host adapter (B1 in the roadmap).

### Auto Fib and Pivot-Heavy Scripts

Scripts that require real pivot structure (Auto Fib Extension/Retracement) will raise `runtime.error` for insufficient pivots when swing arrays are empty. Both interpret and compile hosts agree on this error. Supply enough bars or lower the Depth parameter.

### Platform-Specific Features

The following are intentionally out of scope:

- **Pixel chart rendering** — AXIS and client applications consume series and drawings
- **Editor UI** — word wrap defaults, release notes for editor-only features
- **Bit-identical recursive smoothers** — numerical bounds are tracked, not bit-exact parity
- **Tick-path broker** — the strategy engine models OHLC bar paths, not tick-level fills
- **TV Supertrend band ratchet** — the simplified mid ± factor × ATR model is locked by goldens

### PyneTS

The TypeScript library (`@hoox-sh/pynets` 0.5.0) provides interpret and JS compile modes. Python remains the language oracle. PyneTS does not invent TradingView® behavior.

---

## Corpus Performance

Open-source sets 01–04 (2,477 scripts, measured locally, not shipped in git):

| Stage | Result |
| --- | --- |
| Parse + unparse | 99.96% (2,476/2,477) |
| Runtime interpret (50 bars) | 100% excluding 11 intentional demos |
| Set 01 runtime | 249/249 (100%) |

The 11 EXPECTED_FAIL scripts are intentional demos: library `runtime.error` guards, lower-TF security, invalid line-wrap documentation, pathological loops, and truncated mid-call scrapes. These are not silent suppressions — they are path-listed in test fixtures.

---

## Recent Releases (0.6.10–0.6.14)

### 0.6.10 — Observability and Engine Parity

Engine parity improvements, observability tooling, and documentation refresh.

### 0.6.11 — Live Plane and Sessions

- **Engine-owned subscription plane** — WebSocket `/ws/live` for realtime data
- **Refcount-pooled shared sessions** (F-29) — sessions shared by content hash
- **Opt-in delta envelopes** — tick/append routes with delta compression
- **Live session persistence** — SQLite journal for cross-restart continuity
- **CCORS fix** — `X-Api-Key` header for AXIS authenticated requests

### 0.6.12 — Production Hardening

- **Gevent WebSocket worker** (F-30) — API default worker class
- **CCXT provider caching** — reuse cached providers + longer tick-walk sharing
- **Production profile** — `PYNE_DATA_DIR` pinned to persistent volume
- **Docker prod on VPS** — retired venv+systemd path
- **Redis unpublished** — opt-in auth after internet wipe
- **CCORS for AXIS** — authenticated cross-origin requests

### 0.6.13 — Dual-host HTF, LSP, host hardening

- **Compile HTF `request.security`** (D-06) — same-symbol simple OHLCV / `close[1]` / allowlisted `ta.*` resample matches interpret
- **LSP signature help** — `textDocument/signatureHelp` for builtins and user functions
- **JSON key-store atomic save** — flock + `os.replace`
- **Webhook DNS pin** — POST connects to the resolved public IP with HTTPS SNI on the original name

### 0.6.19 — HTF allowlist, incremental TA, LSP

- **T2 incremental** — `rsi_oversold_overbought`, `zigzag`, `volatility_regime`, `momentum_filter`, `acceleration_factor`, `mean_reversion_score`, `market_condition`, `order_flow_imbalance`, `volume_thrust`, `liquidity_score`, `fear_greed_index`, `crowd_sentiment`, `smart_money_flow`, `trend_confirmation_score`, `atr_stop`, `max_loss_level`, `profit_lock_level`
- **HTF allowlist** (D-06) — 0-arg `ta.obv()` / 1-arg `ta.cmf(n)` / 0-arg `ta.nvi()` / 0-arg `ta.pvi()` / 0-arg `ta.accdist()` / 0-arg `ta.wad()` / 0-arg `ta.tr()` / 2-arg `ta.tsi(short, long)` / 2-arg/3-arg `ta.bbw` / 1-arg/2-arg `ta.stoch` / 2-arg `ta.pivothigh` / `ta.pivotlow` / 3-arg `ta.percentile_nearest_rank` / `ta.percentile_linear_interpolation` / 1-arg `ta.dpo(n)` / 2-arg `ta.dpo(source, n)` / 2-arg `ta.crossover` / `ta.crossunder` / `ta.cross` of OHLCV names / 3-arg `ta.correlation` of two OHLCV names / 0-arg `ta.vpt()` / `ta.pvt()` / 1-arg `ta.wvad(n)` / 3-arg `ta.uo(n1, n2, n3)` / 3-arg `ta.apo(source, fast, slow)` / 1-arg `ta.emv(n)` (disk IR v50)
- **LSP** — `textDocument/documentLink` for http(s) URLs in comments and strings, `documentLink/resolve`, `textDocument/semanticTokens/range`, hover Pine v6 docs links, `textDocument/linkedEditingRange`, `textDocument/onTypeFormatting`, `inlayHint/resolve`, parameter-name inlay hints

### 0.6.14 — HTF allowlist, incremental TA, LSP

- **HTF allowlist** (D-06) — `cmo`/`stdev`/`linreg`, `cci`/`roc`/`mom`, `hma`/`vwma` + 1-arg `ta.cci(n)`, `dema`/`tema` + 1-arg `ta.wpr(n)`, `highest`/`lowest` (2-arg and 1-arg high/low) + `ta.range` (2-arg and 1-arg high−low), `median`/`dev`/`variance`, `mode`/`percentrank`/`change`, `cog`/`highestbars`/`lowestbars` (2-arg and 1-arg high/low), 2-arg `kama` (Kaufman 2/30) / `rising` / `falling`, `swma` (1-arg source, 4-period) / 0-arg `ao()` / 2-arg `ao(fast, slow)` / 3-arg `linreg(source, n, offset)` / 0-arg `vwap()` (HTF hlc3) / 1-arg `vwap(source)` / 1-arg `ta.cum(source)` / 1-arg `ta.ao(fast)` (slow 34) (disk IR v34)
- **T2 incremental** — `rci`/`bb_pct`/`atr_normalized`, `cumulative_delta`/`volume_momentum`, `sma_weighted`, `range`/`max`/`min`, `stoch_smooth`, `rsi_divergence`, `fractal`, `engulfing`/`hammer`, `double_top_bottom`, `gap_detector`, `inside_bar_pattern`, `ema_cross_signal`
- **Forming-bar realtime** — trail ratchet (D-01), MAE/MFE (D-03), nested list/dict snapshot (D-04)
- **LSP** — document highlight + rename (open docs), W001/W002/C002 QuickFix, `textDocument/foldingRange`, `textDocument/selectionRange`, `documentColor` / `colorPresentation`
- **GitHub Release notes** — `CHANGELOG.md` `## [X.Y.Z]` is the GitHub Release body

---

## Recommendations

1. **Prefer golden tests** over changing TA seed rules (ATR → RMA, VWMA volume, etc.)
2. **Land evaluator/TA math** in `src/pynescript/ast/evaluator/`; keep pyne-worker as a thin host
3. **Re-run corpus fails** via `scripts/corpus_rerun_fails.py` after each fix
4. **Update this document** and `pinescript_implementation_status.md` after each addition

---

*This document is maintained alongside the codebase. For the dispatch-oriented inventory, see `docs/pine_v6_full_surface_inventory.md`. For the product-facing summary, see `docs/pyne/reference/missing-features.mdx`.*
