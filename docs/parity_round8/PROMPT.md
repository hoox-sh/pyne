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

# PYNE / pynescript — Round 8: Corpus Parity (Interpreter + Compiler)
# Focus: full-system interpret↔compile plot parity + Runtime corpus OK rate
# Date: 2026-08-04
# BASE_SHA: b1035b106a17a735b9608250d82fc433194007b2
# Prior: Round 7 (docs/perf_round7/), ROADMAP P1p + C1

You are one of **12 isolated subagents**. Raise **corpus parity** across the
**full system**: AST interpreter, Numba/object compiler, and Runtime host.

## Goals (priority order)

1. **Correctness** — interpret is the oracle for plot series unless a bug is
   proven in interpret (then fix both). Prefer nan-aware allclose parity
   (`rtol=1e-5`, `atol=1e-6`) via `scripts/compare_interp_compile.py`.
2. **P1p** — cut value `MISMATCH` / one-sided `compile_error` / `interp_error`
   on corpus + builtin_scripts.
3. **C1** — cut honest Runtime `RUN_FAIL` residual on set01–04 (not PARSE stubs
   from truncated scrapes; do not weaken parser for non-Pine).
4. **Goldens** — every semantic fix gets a minimal unit test under `tests/`.
5. **Docs** — write your agent report; do not thrash other agents’ files.

## Open backlog (this round)

| ID | Item | Pri |
| --- | --- | --- |
| **P1p** | Interpret ↔ compile **plot series** residual | P0 |
| **C1** | Corpus Runtime RUN_FAIL / TIMEOUT residual (set01–04) | P0 |
| **C1c** | Compile-mode corpus coverage (scripts that compile+run) | P1 |
| **F1** | ATR/supertrend re-baseline **only** with explicit goldens | P2 (avoid unless assigned) |

## Repo map

| Want | Path |
| --- | --- |
| Compile visitor | `src/pynescript/compiler/compiler.py` |
| Numba kernels | `src/pynescript/compiler/numba_builtins.py` |
| Compile engine | `src/pynescript/compiler/engine.py` |
| Strategy broker (compile) | `src/pynescript/compiler/strategy_broker.py` |
| Runtime host | `backend/runtime.py` |
| Interpreter builtins | `src/pynescript/ast/evaluator/builtins/` |
| Parity harness | `scripts/compare_interp_compile.py` |
| Runtime corpus | `scripts/corpus_run_runtime.py` |
| Parse corpus | `scripts/corpus_parse_sets.py` |
| Always-on parity tests | `tests/test_interp_compile_parity.py` |
| Corpus residual tests | `tests/test_corpus_runtime_residuals.py` |
| Rules | `AGENTS.md` |
| Prior residual | `docs/perf_round7/AGENT_08_corpus_residual.md` |
| Contract | `docs/pyne/runtime/compiler/parity.mdx` |

## Measurement (run from repo root)

```bash
# Interpret↔compile plot parity (builtin + file list)
PYTHONPATH=src:. .venv/bin/python scripts/compare_interp_compile.py \
  --bars 200 --limit 50 --workers 4 \
  --ignore-hline-keys --ignore-fill-keys \
  --out .cache/parity_r8_smoke.json

# Targeted files
PYTHONPATH=src:. .venv/bin/python scripts/compare_interp_compile.py \
  --files tests/data/set01/indicators/193_ind_self_adjusting_rsi.pine \
  --bars 500 --ignore-hline-keys --ignore-fill-keys

# Runtime corpus (interpret or compile)
PYTHONPATH=src:. .venv/bin/python scripts/corpus_run_runtime.py \
  --sets set01 --mode interpret --bars 25 --timeout 12 --workers 4

# Unit suites (pick those you own)
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_interp_compile_parity.py \
  tests/test_compiler_numba.py \
  tests/test_corpus_runtime_residuals.py -q --tb=line
```

Known mid-run MISMATCH samples (partial 1000@1000bars, 2026-08-03):

- `set01/indicators/193_ind_self_adjusting_rsi.pine`
- `set01/indicators/245_ind_hma_kahlman_trend_clipping_and_trendlines.pine`
- `set01/strategies/045_str_ha_univlong_and_short_futures.pine`
- `set01/strategies/073_str_stochrsi_plus_supertrend_strategy.pine`
- `set02/indicators/156_ind_mtf_structure_bias.pine`
- `set02/indicators/178_ind_bulls_bears_index_bbi_2.pine`
- `set02/strategies/071_str_multi_vwap_crossover.pine`

## Hard constraints

1. Zero intentional correctness loss vs current interpret oracle (unless both
   wrong vs Pine semantics — then fix both + golden).
2. Do **not** silent-coerce `na` → 0 for “parity”.
3. Do **not** hand-edit generated grammar under `…/antlr4/generated/` or ASDL
   generated nodes. Grammar only via `resource/` if Agent 12.
4. Do **not** weaken parser for truncated scrape stubs.
5. Do **not** soft-suppress real library `runtime.error` validation demos
   (see R7 Agent 08 remaining 6 intentional fails).
6. `from __future__ import annotations` on every new Python file.
7. Small, reviewable diffs. Exclusive file ownership (below).
8. No secrets, no force-push, no commit of `.vsix` / `.metadata.key`.
9. Prefer **minimal reproduction + unit test** over full corpus rewrites.
10. Clear compile caches after kernel/emit changes if tests look stale:
    `clear_compile_cache` / `clear_disk_compile_cache` / `clear_numba_function_caches`.

## Agent roster (exclusive ownership — do not edit others’ primary files)

| ID | Role | Owns (primary) | Hunt |
|---:|---|---|---|
| **01** | Inventory + residual buckets | `docs/parity_round8/INVENTORY.md`, `.cache/parity_r8_*` only | Full bucket report; no product code |
| **02** | Numba TA kernels | `numba_builtins.py`, `tests/test_compiler_numba.py` | Value MISMATCH on rsi/ema/hma/atr/stoch/vwap/supertrend kernels |
| **03** | Compiler visitor emit | `compiler/compiler.py` | compile_error, missing ta.* emit, history/`var`, tuple unpack, security na policy |
| **04** | Compile engine + IR | `compiler/engine.py` | Result normalize, object_mode flag, cache, series key packing |
| **05** | Interpret TA residual | `evaluator/builtins/technical.py` + `technical_submodules/` | Interpret RUN_FAIL + oracle fixes that unstick parity |
| **06** | Strategy dual-path | `strategy_broker.py`, `builtins/strategy.py`, strategy tests | Strategy plot/openprofit MISMATCH; event-adjacent series |
| **07** | Plot / fill / hline keys | `builtins/plotting.py`, `builtins/drawing.py` | structural_only / fill / bgcolor / titled fill parity |
| **08** | request / MTF / ticker | `builtins/request.py`, `ticker.py`, `timeframe.py` | MTF structure bias, security, foreign-na both modes |
| **09** | Collections / strings | `arrays.py`, `matrix*.py`, `strings.py`, `map*.py` | C1 RUN_FAIL long-tail collections/str |
| **10** | Expressions / control | `evaluator/expressions.py`, statements if present, `utility.py` | Soft concat, period-or-none, bare aliases, na arithmetic |
| **11** | Runtime host packing | `backend/runtime.py`, `backend/series.py` (if needed) | time_arr, OHLCV packing, mode=compile envelope |
| **12** | Harness + goldens + sanitize | `compare_interp_compile.py`, `test_interp_compile_parity.py`, `test_corpus_runtime_residuals.py`, `corpus_sanitize.py` | Expand always-on smoke; EXPECTED_FAIL class; harness buckets |

**Shared read-only:** `AGENTS.md`, docs, corpus under `tests/data/`.  
**If you need a file another agent owns:** write a note in your report under
`Residual / handoff` — do not edit it.

## Shared output

Write: `docs/parity_round8/AGENT_NN_<slug>.md` with:

- Role / ID
- What you did (files touched)
- Before/after: parity counts, recovered scripts, or structural proof
- Tests run + pass/fail
- Residual / handoff
- Verdict: **win** | **partial** | **blocked** | **measure-only**

DoD for claims: recovered scripts with names, or pp estimate on a stated set,
plus green targeted pytest.
