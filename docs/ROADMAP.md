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

# PYNE Roadmap

**Live package:** `hoox-pyne` **0.6.30**.

---

## Current Status

PYNE has reached a mature stage of development. The core Pine Script™ v6 language, builtins, strategy broker, collections, drawing surface, and compiler are fully functional. The open-source corpus (2,477 scripts) achieves 99.96% parse success and 100% runtime interpretation excluding intentional error-path demos.

The project's focus has shifted from feature completion to production hardening: live data planes, session management, deployment infrastructure, and observability.

---

## Architecture Overview

PYNE's evaluation pipeline consists of four stages:

1. **Lexing** — ANTLR4-generated lexer handles Pine source including multiline strings, soft keywords, and bitwise operators
2. **Parsing** — ANTLR4 parser produces an ASDL AST with full structural fidelity
3. **Building** — The builder transforms the parse tree into the evaluator's node representation
4. **Evaluation** — `NodeLiteralEvaluator` walks the AST in bar-loop mode, dispatching through a registry of 941 callables across 255 namespaces

The compile path lowers the AST to Python/numpy source. Pure numeric scripts are JIT-compiled via Numba; scripts using UDTs, maps, or drawings use an object-mode Python bar loop. Both paths produce identical series output for eligible scripts.

---

## What Has Been Completed

### Language and Parser

The full v5/v6 language surface is implemented and tested. This includes variables and types, control flow (`if`/`for`/`while`/`switch`/`once`), functions with type annotations, user-defined types, libraries with `export`/`import`, enums, string interpolation, tuple unpacking, and method chaining. Series history access follows Pine semantics with out-of-bounds indices returning `na`.

### Builtins and Technical Analysis

All 434 symbols from the public TradingView® v6 function reference are registered. The `ta.*` namespace spans 165 functions covering moving averages, oscillators, volatility, structure, and volume indicators. Incremental bar-mode evaluation is the default, achieving 3–10x speedups over full recompute on multi-thousand-bar series.

### Strategy and Broker

The strategy engine emits `StrategyEvent` objects for all order lifecycle events. It supports OCA groups, commission models, slippage, and risk enforcement. Pending fills are processed each bar before the script body. The compile-mode strategy broker (`CompileStrategyBroker`) provides parity with the interpret path.

### Collections and Drawings

Arrays, matrices, and maps are fully implemented with UDT support. All drawing objects (`line`, `box`, `label`, `table`, `polyline`, `linefill`) have complete property accessors. Drawing garbage collection is enforced across all hosts. Drawing export parity between interpret and compile modes is maintained.

### Alerts and Webhooks

The alert engine supports all frequency rules. Webhook delivery is available on both the Pro API and pyne-worker.

### Compiler

The Numba compile path handles pure numeric scripts. Object mode handles UDTs, maps, and drawings. Warm-compile with disk IR cache is available via prewarm API/CLI. Interpret-to-compile plot parity is verified by an always-on smoke test and a full corpus harness.

### Hosts and Infrastructure

- **Pro API** — Flask-based REST API with authentication, rate limiting, and Docker deployment
- **pyne-worker** — Python Cloudflare Worker for edge evaluation
- **pyne-agent-worker** — Natural language authoring host
- **CLI** — `pyne` and `pyne-lsp` commands with Nuitka binaries
- **LSP** — Full language server with diagnostics, completion, hover, formatting, and navigation

### Converter

`pyne convert` rewrites Pine source between versions without touching comments or string literals: version pragma, v3→v4 color/timeframe/plot-style constants, v4→v5 `ta.*` / `math.*` / `request.*` namespaces, `study(` → `indicator(`, typed `input.*()` and `iff`/`offset`, plus v5→v6 request-namespace leftovers. The same transform backs the `pynescript.convertToV6` LSP command and code action.

---

## Release History

### 0.6.10 — Observability and Engine Parity

Engine parity improvements, observability tooling, and documentation refresh.

### 0.6.11 — Live Plane and Sessions

The engine-owned subscription plane (WebSocket `/ws/live`) enables realtime data streaming. Refcount-pooled shared sessions (F-29) allow multiple clients to share evaluation state by content hash. Opt-in delta envelopes reduce bandwidth on tick/append routes. Live session persistence via SQLite journal enables cross-restart continuity.

### 0.6.12 — Production Hardening

The gevent WebSocket worker (F-30) is now the API default. CXT provider caching reduces connection overhead. The production profile pins `PYNE_DATA_DIR` to a persistent volume. Docker production is deployed on VPS. Redis is unpublished with opt-in authentication. CORS allows AXIS authenticated requests.

### 0.6.13 — Dual-host HTF, LSP, host hardening

Compile-mode `request.security` matches interpret on allowlisted HTF resample. LSP advertises `textDocument/signatureHelp`. JSON key-store writes are flock-serialized; webhook POSTs pin to the resolved IP.

### 0.6.14 — HTF allowlist, incremental TA, LSP

Allowlisted HTF `ta.*` resample expanded through `vwap` / `ao` / `linreg` offset / `ta.cum` / 1-arg `ta.ao(fast)` / 1-arg `ta.change(source)` (disk IR v35). Incremental TA covers `sma_weighted`, `stoch_smooth`, `rsi_divergence`, pattern kernels, `ema_cross_signal`. LSP folding, selectionRange, documentColor, W001/W002/C002 QuickFixes. GitHub Release notes come from `CHANGELOG.md`.

### 0.6.19 — HTF allowlist, incremental TA, LSP

Allowlisted HTF `ta.*` resample expanded through `ta.emv` (disk IR v50). Incremental TA covers `volatility_regime` through `profit_lock_level`. LSP range tokens, hover Pine v6 docs links, linked editing, on-type formatting, inlay resolve plus parameter-name hints, `documentLink/resolve`.

---

## What Remains

### By Design

The following are intentional boundaries, not missing features:

- **Foreign `request.security` data** — Returns `na` rather than inventing chart-close as foreign fundamentals. Real multi-symbol market data requires a host adapter.
- **Pixel chart rendering** — AXIS and client applications consume series and drawings; PYNE does not render pixels.
- **Editor UI** — Word wrap defaults and editor-only release notes are not applicable to a headless runtime.
- **Bit-identical recursive smoothers** — Numerical bounds are tracked, not bit-exact parity with TradingView®.
- **Tick-path broker** — The strategy engine models OHLC bar paths, not tick-level fills.
- **Semantic version migration** — `pyne convert` performs source-level rewrites (pragma, namespaces, declarations, `request.*`); bool-as-number and `na`-tightening changes require a type checker and stay out of scope.

### Open Items

- **PyneTS parity** — The TypeScript library provides interpret and JS compile; Python remains the oracle.
- **Community corpus sweep** — Optional set0x community corpus value comparison remains unmeasured.

---

## Design Principles

1. **Python wins** language semantics — PyneTS does not invent TradingView® behavior
2. **Interpret is the oracle** — Compile matches where eligible; `mode=auto` falls back
3. **Honest `na`** — Foreign request data returns `na`, never invented values
4. **Bar-by-bar semantics** — No whole-script vectorization; incremental kernels preserve exact bar-loop behavior
5. **Golden tests** — Changes to TA math require golden tests against the current oracle

---

*This roadmap is a living document. For the dispatch-oriented inventory, see `docs/pine_v6_full_surface_inventory.md`. For the product-facing summary, see `docs/pyne/reference/roadmap.mdx`.*
