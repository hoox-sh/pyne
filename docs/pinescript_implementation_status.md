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

# PineScript v6 Implementation Status

**Live package:** `hoox-pyne` **0.6.30**.

---

## Overview

This document provides a high-level summary of Pine Script™ v6 implementation status in PYNE. For the dispatch-oriented inventory with per-namespace counts, see `docs/pine_v6_full_surface_inventory.md`.

PYNE implements Pine Script™ v5/v6 as a complete parse, AST, bar-loop evaluation pipeline. The core language, builtins, strategy broker, collections, and drawing surface are fully functional. This is not a claim of TradingView(R) platform parity.

---

## Language Core

The full v5/v6 language surface is implemented:

- **Variables and types** — `int`, `float`, `bool`, `string`, `color`, series, const, and user-defined types
- **Control flow** — `if`/`else`, `for`, `while`, `switch`, `once` (statement-only)
- **Functions** — User-defined functions with type annotations, method chaining, tuple unpacking
- **UDTs** — User-defined types with `.new`, field defaults, and method support
- **Libraries** — `export`/`import` with `export const`, `export type`, `export enum`
- **Enums** — Full runtime and type integration with `input.enum`
- **Series history** — `close[n]` with out-of-bounds and negative indices returning `na`
- **Line wrapping** — Any indentation inside parentheses and square brackets

---

## Builtins

All 434 symbols from the public TradingView(R) v6 function reference are registered in the dispatch inventory. The evaluator dispatches through 941 callables across 255 namespaces.

### Technical Analysis (`ta.*`)

165 functions covering:

- **Moving averages** — SMA, EMA, RMA, WMA, HMA, VWMA, KAMA, DEMA, TEMA, ALMA
- **Oscillators** — RSI, MACD, Stochastic, CCI, CMO, TSI, ROC, WPR, Aroon, DPO, KST
- **Volatility and structure** — ATR (Wilder RMA of TR), Bollinger Bands, Keltner Channels, Standard Deviation, Linear Regression, ADX/DMI, Supertrend, SAR, Donchian
- **Volume** — OBV, WAD, WVAD, CMF, Klinger, MFI, VWAP, NVI, PVI

Incremental bar-mode evaluation is the default for performance-critical kernels. Each function maintains call-site state and updates one sample per bar.

### Strategy (`strategy.*`)

95 functions covering:

- **Order management** — `entry`, `close`, `cancel`, `exit` with stop/limit/OCA
- **Position tracking** — `position_size`, `opentrades`, `closedtrades`, `netprofit`, `equity`
- **Risk management** — `max_position_size`, `max_drawdown`, `max_cons_loss_days`, `allow_entry_in`
- **Trade metrics** — `from_entry`, `qty_percent`, `profit`, `loss`, MAE/MFE
- **Commission and slippage** — Percent, cash per order, cash per contract models

### Collections

- **`array.*`** — 68 functions including `sort`, `sort_indices`, `binary_search*` with UDT `sort_field`
- **`matrix.*`** — 74 functions including linear algebra (`det`, `inv`, `eigen`, `kron`, `trace`, `rank`) and predicates
- **`map.*`** — 11 functions for key-value storage

### Drawing and Plotting

- **`line`, `box`, `label`, `table`, `polyline`, `linefill`** — Full property accessors and `.all` collections
- **`plot` family** — `plot`, `plotshape`, `plotchar`, `plotarrow`, `plotbar`, `plotcandle`, `hline`, `bgcolor`, `barcolor`, `fill`
- **Garbage collection** — `max_*_count` enforced on package, Pro API, and AXIS hosts

### Other Namespaces

- **`request.*`** — 11 functions with dynamic symbol resolution; foreign/complex returns `na`
- **`input.*`** — 14 functions with `active` parameter and metadata side-channels
- **`math.*`** — 25 functions
- **`str.*`** — 19 functions
- **`color.*`** — 26 functions
- **`timeframe.*`** — 15 functions including `timeframe.change` with intraday buckets and exchange calendar

---

## Strategy Broker

The strategy engine models OHLC bar paths:

- **Event emission** — `StrategyEvent` for entries, exits, orders, cancels
- **Pending fills** — Limit, stop, stop-limit, and market orders processed each bar
- **OCA groups** — None, cancel, and reduce with `oca_name`/`oca_type` on orders
- **Risk enforcement** — Entries blocked when risk limits exceeded; emits `risk_blocked` events
- **Position tracking** — Signed `position_size`, open/closed trade counts, equity, netprofit
- **Compile-mode broker** — `CompileStrategyBroker` provides parity with interpret path

---

## Compiler

The compile path has two modes:

### Numeric Mode (Numba)

Pure numeric scripts are lowered to Python/numpy source and JIT-compiled via Numba. Handles series assignments, arithmetic, history access, control flow, selected `ta.*` routines, tuple unpack, scalar math, plots, and `var`/`varip` persistence.

### Object Mode

Scripts using UDTs, maps, or drawings use a pure-Python bar loop. UDT instances are field dictionaries, maps are Python dictionaries, and drawing calls are structured events in a `__drawings` list.

### Warm-Compile

Disk IR cache with prewarm API/CLI. Cache meta v18. Corrupt-cache recovery for Numba `.nb*` files.

---

## Hosts

| Host | Description |
| --- | --- |
| **Package Runtime** | `pynescript.runtime.Runtime` — the language oracle |
| **Pro API** | Flask REST API with auth, rate limiting, Docker |
| **pyne-worker** | Python Cloudflare Worker — edge `POST /run` |
| **pyne-agent-worker** | NL authoring host — `POST /v1/chat` |
| **CLI** | `pyne` and `pyne-lsp` with Nuitka binaries |
| **LSP** | Full language server — diagnostics, completion, hover, formatting, navigation |

---

## Data Providers

- **Mock** — Synthetic OHLCV for testing
- **Yahoo Finance** — Via `yfinance`
- **AlphaVantage** — Free API tier
- **CCXT** — 100+ crypto exchanges (historical)
- **CCXT Pro** — Realtime datafeed via WebSocket

---

## Corpus Performance

Open-source sets 01-04 (2,477 scripts, measured locally, not shipped in git):

| Stage | Result |
| --- | --- |
| Parse + unparse | 99.96% (2,476/2,477) |
| Runtime interpret (50 bars) | 100% excluding 11 intentional demos |
| Set 01 runtime | 249/249 (100%) |

The 11 EXPECTED_FAIL scripts are intentional demos of error paths, not silent suppressions.

---

*This document is maintained alongside the codebase.*
