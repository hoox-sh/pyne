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

# Round 9 summary — interpret residual perf (4 agents)

**BASE_SHA:** `41d3e491dc42c6ea918abc8e85e1065fae2e5af6`  
**Measured:** 2026-08-16 after 4 worktree agents + parent merge  
**Prompt:** `docs/perf_round9/PROMPT.md`

## Headlines

| script (interpret @ 2000) | R9 baseline med_ms | R9 net med_ms | Speedup |
| --- | ---: | ---: | ---: |
| **minimal** | 27.61 | **10.21** | **2.70×** |
| **ta_sma** | 39.29 | **19.98** | **1.97×** |
| **ta_combo** | 200.59 | **138.11** | **1.45×** |
| **strategy_ish** | 100.62 | **64.66** | **1.56×** |

Compile warm ta_combo run still **~1.03 ms @ 5k** (flat; already µs-scale).

## Per-agent scorecard

| ID | Role | Verdict | Evidence |
| ---: | --- | --- | --- |
| **01** | Plot-path structural | **partial** | fill+2 plots −13–16%; official ta_combo −1.8% (visit_Call-bound). Unified steady-state write, `_plot_color_pending`, `_bar_reuse_plot`. |
| **02** | Residual incremental TA | **win** | `obv`/`wad`/`wvad`/`cmf`/`klinger` inc; kernel 18–577×; volume script 38× vs `PYNE_TA_INCREMENTAL=0`. |
| **03** | Interpret dispatch | **win** | Direct Assign/Expr(Call) walk; arg-plan first-bar only. Agent A/B: minimal −31%, ta_combo −25%. `visitor.visit` 36k → 2k. |
| **04** | Runtime host + series | **win** | Skip unused derived series; packed OHLCV; skip indicator strategy snapshot. Agent A/B: minimal −35%, ta_sma −31%. Ring still default **off**. |

## Parent glue

- **`ta.vwap()` default source** — host skip of unused `hlc3` would have fallen back to `close`. Force `hlc3` when `ta.vwap` / `vwap` appears (`_VWAP_RE`). Golden: `test_ta_vwap_default_source_uses_live_hlc3`.

## Verify (parent merge)

```text
595 passed, 6 skipped   (TA inc, evaluator, expr, plots, series, runtime, parity, v6)
449 passed, 22 skipped  (strategy, compiler, interp/compile parity, TA indicators 1–2)
```

## Residual / next

| Priority | Item |
| --- | --- |
| P2 | T2 leftover: `ta.nvi` / `ta.pvi` still full-list |
| P2 | Plot packing still ~50 ms of ta_combo vs no-plot (now mostly 8× `visit_Call`) |
| P2 | F1 ATR Wilder / TV supertrend goldens only |
| P3 | Default-on `PYNE_SERIES_RING` still rejected |

## One-liner

**Round 9 cut interpret wall ~1.5–2.7× vs the same-machine baseline by stacking dispatch inlining, unused-derived host skip, plot steady-state reuse, and incremental volume kernels — 595-core + 449-strategy/compiler verify green; ring stays off.**
