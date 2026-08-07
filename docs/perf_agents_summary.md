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

# Performance agents summary (2026-07-28)

Four isolated worktree agents optimized **parse**, **unparse**, **evaluate**,
and **compile+execute**. Results were merged into the main workspace.

Full writeups: `perf_agent_parse.md`, `perf_agent_unparse.md`,
`perf_agent_evaluate.md`, `perf_agent_compile_execute.md`.

## Headlines

| Area | Win | Notes |
|---|---|---|
| **Parse** | **~5.4×** (complex ~16 KB script) | SLL-first + LL fallback; skip annotations without `@`; `_setLocations` fast path |
| **Unparse** | **~1.95×** (99 set01 scripts) | Thread-local unparser reuse; type-keyed dispatch; less CM overhead |
| **Evaluate** | **~1.9–6.5×** TA Runtime paths | Incremental stdev/BB/highest/lowest/wma/tr/change (`PYNE_TA_INCREMENTAL`) |
| **Compile+exec** | **~49–110×** MACD/MULTI run | Incremental Numba kernels + tuple plot returns + LRU cache 128 |

## Verification

```text
506 passed  (test_ta_incremental, test_evaluator, test_parse_and_unparse,
             test_compiler_numba, test_compiler_objects, test_compiler_strategy)
```

## Key code touch points

- Parse: `src/pynescript/ast/helper.py`, `builder.py`
- Unparse: `src/pynescript/ast/unparser.py` (+ thin `helper.unparse` wire-up)
- Evaluate: `ast/evaluator/builtins/technical_submodules/{core,basic,volatility,moving_averages,advanced}.py`, `tests/test_ta_incremental.py`
- Compile: `compiler/{compiler,engine,numba_builtins}.py`

## Flags

- Interpret incremental TA: default **on**; disable with `PYNE_TA_INCREMENTAL=0`
- Compile path always uses incremental kernels for ema/rma/atr/macd/cum/vwap/obv when those builtins are emitted

## Follow-up (same day)

| Area | Change |
|---|---|
| **Compile rolling O(1)** | `numba_sma/sum/stdev/variance/bb/rsi/tsi_inc` wired in `CompilerVisitor` |
| **Runtime series cap** | `backend/runtime.py` (+ pyne-worker twin) trims `current_series` to `_SERIES_MAX`+slack |

Compile execute (n=5000, median): SMA ~0.04 ms, RSI ~0.08 ms, MULTI ~0.21 ms, BB ~0.15 ms, TSI ~0.11 ms.
Kernel parity vs full recompute: max abs err ~1e-11 (float noise) / 0 for RSI & TSI.

### Follow-up 2

| Area | Change |
|---|---|
| **Compile** | `highest/lowest/vwma/stoch/wma_inc` (amortized / O(1) rolling) |
| **Evaluate** | Incremental `ta.stoch` %K + real `ta.vwma` (was SMA stub) + `_vwma_inc_update` |

Bench n=5000: highest/lowest ~0.23 ms, stoch ~0.22 ms, vwma ~0.10 ms, wma ~0.08 ms.

### Follow-up 3

| Area | Change |
|---|---|
| **Compile** | `barssince_inc`, `linreg_inc`, `sar_inc` (O(1) / amortized) |
| **Evaluate** | `_cum_inc_update` for `ta.cum` in bar mode |

Bench n=5000: SAR ~0.04 ms, linreg ~0.18 ms (was O(n·period) style pressure).

### Follow-up 4 (4-agent round)

| Agent | Wins |
|---|---|
| **Compile** | `cci/dev/mfi/highestbars/lowestbars/correlation_inc` — MFI ~4–65×, corr ~3–39× @ n=5000 |
| **Evaluate** | Incremental CCI, TSI, ROC, WPR, dev (+ golden tests) |
| **Runtime** | Bar-loop pre-bind, in-place series cap, lighter plots — minimal **+36%**, TA multi **+21%** |
| **Dispatch** | Type-keyed visitor, op maps, scalar fast path — expression walks **~2–7×** |

Reports: `docs/perf_agent_{compile,runtime,dispatch}_round2.md`

### Follow-up 5 (4-agent round 3)

| Agent | Wins |
|---|---|
| **Compile** | `hma_inc` (**12–134×**), `math_sum`/`math_avg` → `*_inc` |
| **Evaluate** | `_as_series` same-bar cache; HMA/rising/falling/median/percentrank inc |
| **Object-mode** | strategy begin_bar + lighter emit — strategy **4.5–6×**, UDT/draw **~2.5×** |
| **Plot/draw** | O(plots) registry upsert; skip empty DrawingRegistry export |

Reports: `docs/perf_agent_*_round3.md`

### Follow-up 6 (10-agent round 4 — 2026-07-29)

| Agent | Wins |
|---|---|
| **Corpus** | set01–04 parse **99.64%** OK (sanitize polish; 9 residual scrapes) |
| **Parse** | Large script **~14%**; builder **~33%** |
| **Unparse** | **~1.28×** this round (byte-identical set01) |
| **Evaluate TA** | vwap/mom/swma/barssince/hlbars/linreg inc — Runtime mix **~1.9–2.2×** |
| **Compile** | HMA/math/rising/falling/valuewhen/running max·min `*_inc` |
| **Runtime host** | Minimal **~20–23%**; columnar plots + fill-gated registry |
| **Dispatch** | Mixed expr **~2.1×** |
| **Coverage audit** | Runtime fidelity ~84% weighted; P0 gaps listed |
| **Strategy** | Compile **~1.75×** / interpret **~1.54×** |
| **Bottleneck map** | `scripts/bench_pipeline.py` + `docs/perf_round4/` |

Full writeups: `docs/perf_round4/00_summary.md` and `01`–`10_*.md`.
