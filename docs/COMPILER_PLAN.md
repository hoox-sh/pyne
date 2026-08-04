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

## Implementation Status

As of mid-2026, the plan is no longer purely prospective: an MVP compile path is landed and covered by automated tests (`tests/test_compiler_numba.py`, `tests/test_compiler_objects.py`). Follow-on sprints and residual passes (through 2026-08) expanded numeric/object coverage, host warm-compile (H2), and interpret↔compile series parity tooling.

**Numeric mode** targets the common indicator subset—series assignments, arithmetic and logical operators, history access (`close[n]`), control flow (`if`, `for`, `while`), selected `ta.*` routines (`sma`, `ema`, `rma`, `rsi`, `highest`/`lowest`/`highestbars`/`lowestbars`, `stdev`, `change`, `atr`, `bb`, `macd`, `rci`, …), tuple unpack (`[u,m,l] = ta.bb(...)`), scalar math helpers, `plot` / titled `fill()`, `input.*` defaults, and `var`/`varip` persistence—executed under `@numba.njit` when Numba is installed. `compile_script` uses in-process + disk IR caches (and product prewarm; see H2 below) so warm re-runs skip re-transpile/JIT.

**Object mode** is selected automatically when the visitor observes UDT definitions, map operations, or drawing APIs. In that regime the generator emits a pure-Python bar loop that represents UDT instances as field dictionaries, maps as ordinary Python dictionaries, and drawing calls as structured events accumulated in a `__drawings` list, while plot series remain full-length arrays. The runtime response includes `series`, `drawings`, and an `object_mode` flag so callers can distinguish the two backends.

Microbenchmarks on multi-thousand-bar series show large speedups for numeric scripts after a one-time JIT warm-up (on the order of tens to hundreds of times versus list-based interpreter evaluation of equivalent `ta.sma` work). Object mode trades some of that peak throughput for broader language coverage.

### Landed correctness / host surface (2026-08 residual)

These are implementation status notes for constructs that previously diverged from the interpret oracle or lacked host plumbing. They do not change the four-layer architecture below.

| Area | Status |
| --- | --- |
| **`time_arr`** | Compiled `execute_script_compiled(..., time_arr)` always receives bar-open Unix ms. Hosts (Runtime) pass real OHLCV timestamps; engine synthesizes `bar * 60_000` when time is omitted. Bare `time` / `time_close` / calendar parts / viewport times lower against `time_arr` (not a separate synthetic calendar). |
| **`request.security` policy** | Compile lowers same-symbol simple OHLCV expressions as chart series passthrough only. Foreign tickers and complex expressions (UDFs, `year_sum(close)`, …) emit `na` — no inventing chart close as dividends/fundamentals. Aligns with interpret foreign-na policy (`request.py` + `ChartOHLCVProvider` chart-symbol filter). |
| **RSI Wilder** | `numba_rsi` / `numba_rsi_inc` use Wilder seed (SMA of first `period` deltas) then RMA of gain/loss (`alpha = 1/period`), matching interpret `_rsi` / `_rsi_inc_update` and TV `ta.rsi` (no longer a simple rolling window average of gains). |
| **`highestbars` / `lowestbars`** | Negative bars-back offsets (TV / interpret contract); all-na window → `-1.0`. History indexing uses NaN-safe int coercion so `high[ta.highestbars(...)]` and `high[-highestbars(...)]` stay in-bounds. |
| **`fill()` series** | Titled `fill(plot1, plot2, …)` exports a series key for interpret/compile plot-key parity and AXIS band wiring; compile leaves the fill series as float NaN (band color/plot refs remain in plot meta / drawings as applicable). |
| **Numba cache recovery** | Truncated/corrupt `.nbi`/`.nbc` (EOFError / UnpicklingError) purge via `clear_numba_function_caches` and retry once on warm/prewarm/run. Disk IR clear remains separate (`clear_disk_compile_cache`). |
| **`ta.rci`** | `numba_rci` + compiler emit for Spearman rank correlation; matches interpret window/rank contract. |
| **Interpret oracle parity harness** | `scripts/compare_interp_compile.py` runs the same scripts under `mode=interpret` and `mode=compile`, compares `result["series"]` with nan-aware allclose, and buckets residuals (`OK`, `fill_background_only`, `both_error_same`, `MISMATCH`, …). Always-on smoke: `tests/test_interp_compile_parity.py`; focused foreign-security: `tests/test_dividend_yield_parity.py`. |

## Architecture

Compilation is organized as four cooperating layers: an AST visitor that emits Python, a Numba-oriented builtin library for numeric kernels, flat array storage for series history, and a thin engine/runtime façade that packages results for the backend. The subsections below describe each layer in turn.

### 1. `CompilerVisitor` (AST to executable Python)

The module `src/pynescript/compiler/compiler.py` defines `CompilerVisitor`, an AST walker that does not evaluate the tree. Instead, it transpiles statements into a Python source string that indexes OHLCV and user series by an explicit bar index (`__bar_idx`). The visitor tracks plot titles, allocates series storage, and sets `object_mode` when non-numeric constructs appear.

**Example transpilation (numeric mode):**

*Pine Script:*
```pine
my_sma = ta.sma(close, 14)
plot(my_sma)
```

*Compiled Python (generated by `CompilerVisitor`):*
```python
import numpy as np
import numba
from pynescript.compiler.numba_builtins import *

@numba.njit(cache=False)
def execute_script_compiled(open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr):
    n_bars = len(close_arr)
    my_sma_arr = np.full(n_bars, np.nan)
    plot_0 = np.full(n_bars, np.nan)

    for __bar_idx in range(n_bars):
        my_sma_arr[__bar_idx] = numba_sma(close_arr, 14, __bar_idx)
        plot_0[__bar_idx] = my_sma_arr[__bar_idx]

    return {'plot_0': plot_0}
```

Object-mode generation follows the same structural outline but omits the Numba decorator, uses object-dtype series where UDT values must be retained, and appends drawing events to an in-function `__drawings` list returned alongside plot arrays. (Host always supplies `time_arr`; see Implementation Status.)

### 2. Numba Built-ins Module

Pine’s standard library cannot be invoked from JIT code as ordinary Python callables. Selected `ta.*` and math primitives are therefore reimplemented in `src/pynescript/compiler/numba_builtins.py` as `@numba.njit` functions that accept full arrays plus the current bar index. The initial set includes moving averages, RSI, range statistics, and scalar helpers such as `nz`, `abs`, `min`, and `max`. Expanding this library remains the principal path to broader numeric coverage without leaving the JIT path.

*Example:*
```python
@numba.njit
def numba_sma(arr, period, i):
    if i < period - 1:
        return np.nan
    sum_val = 0.0
    for j in range(period):
        val = arr[i - j]
        if np.isnan(val):
            return np.nan
        sum_val += val
    return sum_val / period
```

### 3. Data Structure Overhaul

The compiled engine does not use `PineSeries` deques. Built-in price, volume, and time series are supplied as flat `numpy` arrays (`open_arr`, `high_arr`, `low_arr`, `close_arr`, `vol_arr`, `time_arr`). User `series` variables are allocated once as `np.full(n_bars, np.nan)` (or object arrays for UDT series) outside the bar loop, then written at `__bar_idx`. The `var` qualifier is lowered so that only the first bar evaluates the initializer and subsequent bars forward the previous value—matching Pine’s carry semantics without interpreter bookkeeping.

### 4. Engine API and integration with `backend/runtime.py`

The module `src/pynescript/compiler/engine.py` provides the stable entry points: `transpile` returns the generated source; `compile_script` executes that source in a private namespace and returns a `CompiledScript` whose `run` method accepts OHLCV arrays; `run_script` performs a one-shot compile-and-run. Numeric mode requires Numba; object mode does not.

`Runtime.run()` accepts `mode="interpret"` (default), `mode="compile"`, and `mode="auto"`. Compile mode converts bar dictionaries to arrays, invokes `compile_script`, and reshapes the result into the familiar response envelope (`plots`, `series`, `drawings`, `count`, identifiers), including `object_mode` and the generated source for inspection and debugging.

**`mode="auto"` (2026-07-28):** tries the compile path when eligible (Numba present; no top-level `import` / `request.*`), and on any compile or compiled-runtime error falls back to interpret. Response fields:

| Field | Meaning |
| --- | --- |
| `auto_backend` | `"compile"` or `"interpret"` — backend that produced the result |
| `compile_fallback_reason` | Present when auto fell back; human-readable cause |
| `mode` | `"compile"` or `"interpret"` matching the successful backend |

pyne-worker `Runtime.run(..., mode=...)` mirrors the same contract.

## Benefits

The compile path is motivated by three practical properties of the pynescript stack: throughput on long histories, debuggability of generated code, and packaging simplicity relative to a native rewrite.

**Speed.** Replacing per-node visitor dispatch with a tight bar loop—and, where possible, Numba JIT—reduces constant factors that dominate multi-thousand-bar evaluations. After warm-up, numeric scripts can process millions of bars per second on typical workstation hardware for simple indicator workloads. Object mode forgoes peak JIT throughput but still avoids AST visitation costs on every expression.

**Safety and debugging.** Lowering to readable Python before JIT or object-mode execution preserves inspectability: failures can be diagnosed against the generated source rather than opaque native IR alone. The dual-mode design also isolates constructs that Numba cannot represent cleanly (UDTs, maps, drawings) without abandoning compilation entirely.

**Compatibility.** The approach reuses the existing ANTLR parser and ASDL AST and depends only on optional Numba/numpy in the environment. No separate C/Rust toolchain is required for the MVP, which keeps packaging aligned with the rest of the Python codebase and with the backend’s `mode="compile"` switch.

## Product warm-compile path (H2, 2026-08)

Deploy and Pro API defaults prefer **warm compile** while remaining correctness-first.

### Runtime modes

| Mode | Behavior |
| --- | --- |
| `auto` (**default** on Pro API `/run`, `/run/batch`) | Prefer compile when eligible; fall back to interpret on hard failure or known gaps |
| `compile` | Compile only (error if transpile/exec fails; nopython→object recovery still inside compile) |
| `interpret` | AST evaluator only |

**Safe auto gates (no silent wrong results):** non-empty `inputs` → interpret; top-level `import` / `request.*` → interpret; any compile error → interpret with `compile_fallback_reason`. Response fields: `auto_backend`, `compile_cached`, `compile_ms`, optional `nopython_fallback_reason`.

### Cache layers

| Layer | Key | Size / default | Cross-process? |
| --- | --- | --- | --- |
| Source LRU | sha256(raw) then sanitized | max 128 | no |
| IR LRU | sha256(generated Python) | max 64 | no |
| Host Runtime cache | raw source sha256 | bounded | no |
| Disk module + src meta | under `PYNE_COMPILE_CACHE_DIR` | **on** by default | yes (+ Numba `.nbc` when file-backed) |

Env (product defaults):

| Env | Default | Role |
| --- | --- | --- |
| `PYNE_COMPILE_DISK_CACHE` | `1` | Opt-out disk IR/module cache |
| `PYNE_COMPILE_CACHE_DIR` | XDG/`~/.cache`…; Docker `/data/compile-cache` | Persistent IR volume |
| `PYNE_COMPILE_PREWARM` | `1` | Once-per-worker builtin prewarm on first `/run` |

### Prewarm hooks

- Python: `prewarm_numba_builtins()`, `prewarm_scripts([...])`, `ensure_compile_cache_dir()`, `compile_deploy_config()`
- CLI: `pynescript prewarm [PATH…]`
- Pro API: `POST /compile/prewarm` (optional `scripts`, `force`); `GET /health` → `compile` section
- Lazy host prewarm on first non-test `/run` when `PYNE_COMPILE_PREWARM=1`

### SLOs (indicative, workstation + Numba; see Round 6 benches)

Targets for **ops / product**, not hard CI gates. Measure with `scripts/bench_pipeline.py`.

| Path | SLO band | Notes |
| --- | --- | --- |
| Interpret `minimal` @ 2k bars | ≤ **25 ms** median | Pure AST walker |
| Interpret `ta_combo` @ 2k bars | ≤ **200 ms** median | Residual TA still interpret-first |
| Cold compile (empty memory + cold Numba) first SMA-class script | ≤ **2 s** | Dominated by njit first-touch |
| Warm compile (same process, source cache hit) | ≤ **1 ms** | Typically ~0.01–0.05 ms |
| Warm compile run `ta_combo` @ 5k bars | ≤ **5 ms** | Often ~1 ms after warm |
| Cross-process disk IR rehydrate (same machine) | ≤ **~60–70%** of full cold | Still not free AOT |

**Product rule:** first user-visible latency after deploy should use prewarm + disk cache so cold JIT is paid by readiness, not interactive `/run` when possible.

## Remaining Work

Further work includes more `ta.*` / math helpers so fewer scripts fall out of numeric mode, strategy execution under compile mode (orders and `StrategyState` side effects remain interpret-first for complex paths; basic entry/close exist in object mode), richer drawing semantics (deletes, full style parity with the interpreter’s registries), and nested UDTs/methods. In-process + **disk** `compile_script` caching and product prewarm (H2) are landed (2026-07/08). Numba function-cache recovery and `time_arr` host plumbing are landed (2026-08 residual).

**Parity (ongoing):** the interpret oracle harness (`scripts/compare_interp_compile.py`) is the growth path for residual plot-value and structural mismatches (hline-only / fill-background key sets, true value MISMATCH, one-sided runtime errors). Prefer goldens under that harness when lowering new constructs rather than ad-hoc one-off scripts.
