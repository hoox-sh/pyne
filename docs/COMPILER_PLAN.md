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

# Pine Script to Numba Compiler Plan

## Overview

Pynescript historically executed scripts with an **AST-walking interpreter** in pure Python. Because Pine Script evaluation is dominated by per-bar traversal of time series, that design incurs substantial interpretive overhead relative to a closed-form bar loop.

To approach TradingView-like execution speeds for realtime streams and large historical backtests, the project introduces a **source-to-source compilation step**. Pine Script is parsed to the existing ASDL AST, then lowered by `CompilerVisitor` into Python that operates on contiguous `numpy` arrays. For pure numeric scripts, the generated entry point is decorated with **Numba** (`@numba.njit`) so the bar loop can be JIT-compiled to machine code. When the script uses user-defined types, maps, or the drawing surface, compilation automatically selects an **object-mode** Python/numpy bar loop that preserves those constructs while remaining substantially faster than full AST interpretation.

The public surface is exposed as `pynescript.compiler.transpile`, `compile_script`, and `run_script`, and is integrated with the backend via `Runtime.run(..., mode="compile")`.

## Architecture

The compiler has four layers:

1. **AST lowering** — `CompilerVisitor` walks the ASDL AST and emits Python source
2. **Type inference** — The visitor infers numpy dtypes for series variables
3. **Code generation** — Python source is generated with Numba-compatible constructs
4. **Caching** — In-process + disk IR caches store compiled artifacts

### Numeric Mode

Targets the common indicator subset: series assignments, arithmetic and logical operators, history access (`close[n]`), control flow (`if`, `for`, `while`), selected `ta.*` routines (`sma`, `ema`, `rma`, `rsi`, `highest`/`lowest`/`highestbars`/`lowestbars`, `stdev`, `change`, `atr`, `bb`, `macd`, `rci`, ...), tuple unpack (`[u,m,l] = ta.bb(...)`), scalar math helpers, `plot` / titled `fill()`, `input.*` defaults, and `var`/`varip` persistence.

Executed under `@numba.njit` when Numba is installed. `compile_script` uses in-process + disk IR caches (and product prewarm; see H2) so warm re-runs skip re-transpile/JIT.

### Object Mode

Selected automatically when the visitor observes UDT definitions, map operations, or drawing APIs. The generator emits a pure-Python bar loop that represents UDT instances as field dictionaries, maps as ordinary Python dictionaries, and drawing calls as structured events accumulated in a `__drawings` list, while plot series remain full-length arrays.

The runtime response includes `series`, `drawings`, and an `object_mode` flag so callers can distinguish the two backends.

### Warm-Compile

Disk IR cache with prewarm API/CLI. Cache meta v18. Corrupt-cache recovery for Numba `.nb*` files.

## Implementation Status

As of **hoox-pyne 0.6.23** (late 2026), the plan is no longer purely prospective: an MVP compile path is landed and covered by automated tests (`tests/test_compiler_numba.py`, `tests/test_compiler_objects.py`). Follow-on sprints and residual passes (through 2026-10) expanded numeric/object coverage, host warm-compile (H2), and interpret-to-compile series parity tooling.

### Landed Correctness and Host Surface

These are implementation status notes for constructs that previously diverged from the interpret oracle or lacked host plumbing. They do not change the four-layer architecture above.

| Area | Status |
| --- | --- |
| **`time_arr`** | Compiled `execute_script_compiled(..., time_arr)` always receives bar-open Unix ms. Hosts (Runtime) pass real OHLCV timestamps; engine synthesizes `bar * 60_000` when time is omitted. Bare `time` / `time_close` / calendar parts / viewport times lower against `time_arr` (not a separate synthetic calendar). |
| **`request.security` policy** | Compile lowers same-symbol simple OHLCV expressions as chart series passthrough only. Foreign tickers and complex expressions (UDFs, `year_sum(close)`, ...) emit `na` — no inventing chart close as dividends/fundamentals. Aligns with interpret foreign-na policy (`request.py` + `ChartOHLCVProvider` chart-symbol filter). |
| **RSI Wilder** | `numba_rsi` / `numba_rsi_inc` use Wilder seed (SMA of first `period` deltas) then RMA of gain/loss (`alpha = 1/period`), matching interpret `_rsi` / `_rsi_inc_update` and TV `ta.rsi` (no longer a simple rolling window average of gains). |
| **`highestbars` / `lowestbars`** | Negative bars-back offsets (TV / interpret contract); all-na window → `-1.0`. History indexing uses NaN-safe int coercion so `high[ta.highestbars(...)]` and `high[-highestbars(...)]` stay in-bounds. |
| **`fill()` series** | Titled `fill(plot1, plot2, ...)` exports a series key for interpret/compile plot-key parity and AXIS band wiring; compile leaves the fill series as float NaN (band color/plot refs remain in plot meta / drawings as applicable). |
| **Object-mode residuals** | UDF `if`/for-in locals, nested UDF free-series, nopython `None`/timezone `timestamp`, object `valuewhen`/`running_max`, matrix UDF/`kron` handles, statement `x = switch`, UDT `Type.new()` returns, `chart.point.copy`/`box.copy`, `pine_int(na)`, sanitize of Hugo/`/* */`/jinja chrome, `round()` extras, import stubs as `na`, color type dispatch, nested UDT methods. |

### Performance

Microbenchmarks on multi-thousand-bar series show large speedups for numeric scripts after a one-time JIT warm-up (on the order of tens to hundreds of times versus list-based interpreter evaluation of equivalent `ta.sma` work). Object mode trades some of that peak throughput for broader language coverage.

### Interpret-to-Compile Parity

The `scripts/compare_interp_compile.py` harness compares series output between interpret and compile modes with nan-aware allclose (`rtol=1e-5`, `atol=1e-6`). First-party goldens cover ATR, Supertrend, and Keltner dual-host. Official TV `builtin_scripts` (148) have **0 MISMATCH** vs compile (2026-09-12).

## Recent Releases (0.6.10–0.6.14)

### 0.6.10 — Observability and Engine Parity

Engine parity improvements, observability tooling, and documentation refresh.

### 0.6.11 — Live Plane and Sessions

- **Engine-owned subscription plane** — WebSocket `/ws/live` for realtime data
- **Refcount-pooled shared sessions** (F-29) — sessions shared by content hash
- **Opt-in delta envelopes** — tick/append routes with delta compression
- **Live session persistence** — SQLite journal for cross-restart continuity

### 0.6.12 — Production Hardening

- **Gevent WebSocket worker** (F-30) — API default worker class
- **CXT provider caching** — reuse cached providers + longer tick-walk sharing
- **Production profile** — `PYNE_DATA_DIR` pinned to persistent volume
- **Docker prod on VPS** — retired venv+systemd path
- **Redis unpublished** — opt-in auth after internet wipe

### 0.6.13 — Dual-host HTF

Compile-mode `request.security` resamples the same allowlisted HTF shapes as interpret (object-mode helpers).

### 0.6.14 — HTF allowlist expansion

Allowlisted HTF `ta.*` resample through `vwap` / `ao(fast, slow)` / 3-arg `linreg` / `ta.cum` / 1-arg `ta.ao(fast)` / 1-arg `ta.change(source)` (disk IR v35).

---

*This document is maintained alongside the codebase.*
