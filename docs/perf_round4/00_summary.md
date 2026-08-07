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

# Performance + coverage agents summary (Round 4, 2026-07-29)

Ten parallel worktree agents analysed, polished, and optimised the full
pipeline: corpus → parse/unparse → interpret → compile, plus a v6 surface
audit. Patches were selectively merged into `main` (no worktree data
deletions).

Per-agent reports: `docs/perf_round4/01_*.md` … `10_*.md`.

## Headlines

| # | Area | Result |
|---|---|---|
| 1 | **Corpus parse** | set01–04 **99.64%** OK (2468/2477) after sanitize polish; residual 9 = scrape/truncation |
| 2 | **Parser** | Large ~78 KB script **~14%** faster; builder stage **~33%** |
| 3 | **Unparser** | **~1.28×** this round (~2.34× vs original baseline); byte-identical on set01 |
| 4 | **Interpreter TA** | New inc: vwap (**~217×** kernel), mom, swma, barssince, highestbars/lowestbars, linreg; Runtime mix **~1.9–2.2×** |
| 5 | **Compiler Numba** | HMA/math sum·avg wired to `*_inc`; rising/falling/valuewhen/running max·min; **4–10×** kernels |
| 6 | **Runtime host** | Minimal **~20–23%**; TA multi **~11%** (columnar plots, fill-gated registry, derived-series skip) |
| 7 | **Dispatch/expr** | Mixed expr walks **~2.1×**; and/or/unary/subscript **~1.7–2.7×** |
| 8 | **v6 coverage** | Dispatch ~97–99%; Runtime fidelity ~**84%** weighted; top gaps: log arity, polyline setters, strategy qty consts |
| 9 | **Strategy/plot** | Compile strategy **~1.75×**; interpret strategy **~1.54×** (O(1) PnL, begin_bar) |
| 10 | **Bottleneck map** | Interpret still **dispatch + `_as_series` + plot** bound; compile run is µs-scale; cold JIT dominates oneshot |

## Verification (merged main)

```text
445 passed  (ta_incremental + corpus_sanitize + v6_locks + compiler_numba + evaluator)
  2 failed  TestSet03MatrixArrayApis (pre-existing object-mode; unrelated)
 74 passed  strategy + parity + plotting + order fills
```

## Key files touched

| Layer | Paths |
|---|---|
| Sanitize | `src/pynescript/util/corpus_sanitize.py` |
| Parse | `helper.py`, `builder.py`, `LexerBase.py` (resource + generated twin) |
| Unparse | `unparser.py` |
| Evaluate | `expressions.py`, `names.py`, `statements.py`, TA `technical_submodules/*` |
| Runtime | `backend/runtime.py`, `backend/evaluator.py` |
| Compile | `compiler/compiler.py`, `numba_builtins.py`, `strategy_broker.py` |
| Strategy | `evaluator/builtins/strategy.py`, `events.py` |
| Bench | `scripts/bench_pipeline.py` |
| Tests | `test_ta_incremental.py`, `test_corpus_sanitize.py`, `test_compiler_numba.py`, `test_v6_surface_locks.py` |

## Flags (unchanged)

- `PYNE_TA_INCREMENTAL` default **on**
- Compile path uses incremental kernels when emitted; full kernels remain as fallback

## Top remaining bottlenecks (engineering order)

1. Prefer **default compile / warm workers** for Pro API (interpret is 40× slower on ta_combo @ 2k bars once compiled).
2. Cut **Runtime compile host wrap** vs bare `CompiledScript.run`.
3. **Scalar / skip `_as_series`** for pure incremental TA call sites.
4. **Call-site builtin resolution cache** on interpret path.
5. Product coverage P0: unknown-attr safety, `log.*` varargs, `strategy.percent_of_equity`, chart aliases, polyline mutators.
6. Remaining TA: dmi/adx, supertrend, valuewhen (interpret), pivots, dema/tema compose.

## Coverage snapshot

| Metric | Value |
|---|---|
| Parse set01–04 | **99.64%** OK |
| Compile set01+02 (prior) | **100%** |
| Runtime product fidelity (audit) | **~84%** weighted |
| Builtin registration | **870** callables ~97–99% |

## One-liner

**Corpus parse is effectively saturated; interpret is dispatch/series/plot bound; compile is kernel-fast after cold JIT.** Round 4 stacked real wins on every layer; next product leverage is **default-compile + residual interpret plumbing + P0 Runtime surface fixes**, not more SMA kernels.
