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
# SPDX-License-Identifier: AGPL-3.0-or-later

# PYNE Progress Report — hoox-pyne 0.6.14

## Summary

PYNE is a complete Pine Script™ v5/v6 toolchain: ANTLR4 grammar → ASDL AST → bar-loop evaluator (interpret / compile / `mode=auto`), Language Server Protocol, Flask Pro API, and edge workers sharing one evaluate contract. The project is **not** a TradingView® platform clone — it is an independent, inspectable language engine whose canonical claim is **language coverage**, not bit-identical platform parity.

Live package: **`hoox-pyne` 0.6.24** (`src/pynescript/__about__.py`). Import package: `pynescript`. CLIs: **`pyne`** / **`pyne-lsp`** (aliases `pynescript` / `pynescript-lsp`).

## Components Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Parser** (ANTLR4 v5/v6) | Working | Multiline strings, soft keywords, bitwise ops, typed UDF returns, `once`, `export const`. `resource/*.g4` is source of truth; `generated/` never hand-edited. |
| **AST / Builder** | Working | `PinescriptASTBuilder` lowers CST → ASDL nodes with locations + comment annotations. `parse` → `unparse` round-trip is the test oracle. |
| **Evaluator** | Working | `NodeLiteralEvaluator` bar loop; series history (`close[n]` → `na` OOB/negative); `var`/`varip`; `input.*`; `request.*` (foreign/complex → `na`). |
| **Builtins / TA** | Working | 941 callables across 255 dispatch namespaces; 0 missing vs public TV v6 function reference (434 symbols). `ta.*` 165 functions with incremental bar-mode hot path (default on). |
| **Collections** | Working | `array.*` (68), `matrix.*` (74 incl. LA + predicates), `map.*` (11). Negative indices, UDT `sort_field`, `binary_search*`. |
| **Strategy broker** | Working | `StrategyEvent` stream, pending limit/stop fills, OCA groups, commission/slippage models, risk cascade (max size/drawdown/cons-loss-days/intraday), `from_entry`/`qty_percent`, trail (OHLC-path approx). |
| **Drawing / plotting** | Working | `line`/`box`/`label`/`table`/`polyline`/`linefill` + `plot` family; `max_*_count` GC; drawing export parity (interpret ↔ compile). |
| **Alerts** | Working | `alert()`/`alertcondition()` frequency rules; L2 webhooks (`webhook_url` / `ALERT_WEBHOOK_URL`). Interpret is the alert oracle; compile returns `[]`. |
| **Compiler** (Numba/object) | Working | `mode=auto` falls back to interpret; warm-compile / disk IR cache (prewarm CLI/API); object mode for UDT/maps/drawings. `time_arr` for calendar/time builtins. |
| **Pro API** | Working | Flask `/run`, `/run/batch`, `/session*`, `/data/series*`, `/optimize`, `/preview*`, `/backtest*`, `/stats`, auth (API keys + admin token), free-tier guards (opt-in). |
| **LSP** (`pyne-lsp`) | Working | Diagnostics, completion, hover, definition/references, symbols, formatting, inlay hints, semantic tokens. Fernet-optional builtin metadata (`.enc`). VS Code extension `hoox-sh.pyne` 0.4.5. |
| **PyneTS** | Partial | `@hoox-sh/pynets` 0.5.0 interpret + JS compile; Python Runtime remains the oracle. |

## Corpus Performance (set01–04 · 2,477 scripts · 2026-08-09)

Open-source sets, **not shipped** in git. Not a TradingView® platform score.

| Metric | Result |
|--------|--------|
| Parse + unparse | **99.96%** (2,476/2,477) — residual: 1 intentional invalid line-wrap demo |
| Runtime interpret (50 bars) | **100%** excl. EXPECTED_FAIL — 2466 OK + 11 intentional demos |
| set01 Runtime | **249/249** (100%) |

EXPECTED_FAIL scripts are path-listed intentional demos (library `runtime.error` guards, lower-TF security, pathological loops, truncated mid-call scrapes) — not silent suppressions.

## Recently Completed Themes (do not re-plan as greenfield)

- **0.6.10–0.6.24**: engine-owned live plane (WS `/ws/live`), refcount-pooled shared sessions (F-29), opt-in delta envelopes, gevent WebSocket worker (F-30), CCXT provider caching + tick-walk sharing, live session persistence (SQLite journal), production profile + `PYNE_DATA_DIR`, Docker prod on VPS, Redis unpublished + opt-in auth, CORS for AXIS authenticated requests.
- **0.6.7–0.6.9**: response windowing (`from_bar`/`to_bar`), live evaluation sessions (O(1) tick / O(delta) append), engine-owned OHLCV store, `GET /stats`, `PYNE_DEBUG`, faster interpret dispatch, compile `ta.uo`.
- **Earlier**: interpret↔compile plot parity harness (official TV builtins **0 MISMATCH**), series caps (`PYNE_SERIES_CAP`, T1), pending-fill averaging (F2), Supertrend goldens (F1), `timeframe.change` D/W/M exchange calendar, UDT `sort_field` on `array.binary_search*`, `export const`/types/enums, multiline strings, square-bracket wrapping, drawing export parity.

## Open Backlog (IDs stable)

| ID | Item | Pri | Status |
|----|------|-----|--------|
| **P1p** | Compile/interpret plot parity residual | P1 | Official TV builtins **0 MISMATCH**; optional set0x community corpus unmeasured |
| **T2** | Incremental TA for remaining heavy kernels | P2 | Volume/oscillator/band kernels done; more where profiled |
| **F1** | ATR Wilder / TV supertrend re-baseline | P2 | mid±factor·ATR locked; TV band ratchet out of scope |
| **L1** | v5↔v6 converter maturity | P3 | Done — source-level rewrites both ways |
| **B1** | Real (non-mock) multi-symbol `request.*` feeds | — | By design; foreign-na policy landed (no invent) |
| **H1 residual** | Dual-host Runtime worker-only extras (logs/profile) | P1 | Largely done; residual = worker-only extras, not a forked bar loop |

Longer horizon (not next): ML wrappers, automatic refactor, parallel/distributed eval experiments.

## Documentation Truth Map

| Doc | Role | Status |
|-----|------|--------|
| `docs/pyne/index.mdx` | Product hub + what's new | Current (0.6.24) |
| `docs/missing_features.md` | Living gap analysis | Current (0.6.24) |
| `docs/pinescript_implementation_status.md` | High-level impl summary | Current (0.6.24) |
| `docs/pyne/reference/compatibility.mdx` | Grouped compatibility map | Current (honest "working / partial / by design") |
| `docs/pyne/reference/missing-features.mdx` | Product-facing gap annex | Current |
| `docs/pyne/reference/pine-v6-surface.mdx` | Name-level dispatch summary | Current (941 / 255 / 0 missing) |
| `docs/pine_v6_full_surface_inventory.md` | Exhaustive builtin tables | Source of truth; regenerate after builtin PRs |
| `docs/known_divergences.md` | Semantic deltas vs reference Pine | Current (D-01…D-06 open; F-01…F-16 fixed) |
| `docs/numerical_validation_report.md` | Methodology + error bounds | v1.0 Nov 2025; treat as report-era, not eternal SLA |

## What To Avoid

- **Do not** cite "100% TradingView parity" — PYNE is language coverage, not platform identity.
- **Do not** hand-edit `generated/` ANTLR/ASDL artifacts; edit `resource/` only.
- **Do not** recreate stale backups (`builder.py.bak`, etc.).
- **Do not** conflate `pyne` (Click CLI) with `pyne-lsp` (pygls LSP).
- **Do not** install plain `pyne`/`pynescript` from PyPI — the distribution is **`hoox-pyne`**.

## See Also

- `docs/pyne/devops/release.mdx` — how to cut a `v*` release
- `docs/pyne/reference/roadmap.mdx` — forward plan
- `docs/pyne/devops/ci.mdx` — CI matrix (3.10–3.13)
- `CONTRIBUTING.md` — hatch workflow + PyPI release steps
