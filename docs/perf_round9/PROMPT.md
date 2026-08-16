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

# PYNE / pynescript — Round 9: 4 Subagents
# Focus: remaining interpret hot path (plot + dispatch + nested TA + host)
# Date: 2026-08-16
# BASE_SHA: 41d3e491dc42c6ea918abc8e85e1065fae2e5af6
# Prior: Round 7 (`docs/perf_round7/00_summary.md`) + Round 8 parity
#        (`docs/parity_round8/00_summary.md`) — do not rediscover shipped wins

You are one of 4 isolated worktree subagents. Optimize **pynescript** Runtime
interpret bar-loop throughput without correctness loss.

## Goals (priority order)

1. **Correctness** — bar-by-bar Pine semantics; series offsets; `na`; `var`/`varip`;
   strategy event order. Prefer bit-identical vs current oracle.
2. **Performance** — measurable interpret wins on `ta_combo` / `ta_sma` /
   `strategy_ish`; no semantic “fixes” as speed hacks.
3. **Documentation** — agent report under `docs/perf_round9/`.

## Why this round

Rounds 1–7 already shipped incremental TA for the hot kernels, series cap,
parse cache, light plots, lazy calendar, and call-site dispatch. Round 7
cProfile still showed:

| residual | share of interpret `ta_combo` |
| --- | --- |
| plot capture + `_builtin_plot` + packing | ~75% wall with 8 plots; ~24% exclusive |
| `expressions.visit_Call` envelope | ~82% cumulative (frame volume) |
| nested full-list TA (`obv`, `ao`, `ichimoku`, …) | T2 leftover |
| host bar-loop dual-write / series update | Phase 2.2 still flagged off |

Do **not** re-implement Phase 1–2.1, R5–R7 wins, or flip `PYNE_SERIES_RING`
default on (corpus + polarity still dual-path).

## Repo map

- Core: `src/pynescript/`
- Runtime SoT: `src/pynescript/runtime/host.py` (backend re-exports)
- Evaluator/TA: `src/pynescript/ast/evaluator/`
- Tests: `tests/`
- Bench: `scripts/bench_pipeline.py`
- Prior: `docs/perf_round7/00_summary.md`, `docs/ROADMAP.md`
- Perf skill: `.grok/skills/pynescript-perf/SKILL.md`
- Rules: `AGENTS.md`

## Hard constraints

1. Zero correctness loss vs current oracle. Golden tests before behaviour change.
2. Do **not** vectorize whole scripts or parallelize bars of one run.
3. Do **not** silent-coerce `na` → 0 for speed.
4. Do **not** hand-edit generated grammar under `…/generated/`.
5. No stale backups in `src/`.
6. `from __future__ import annotations` on every new Python file.
7. Risky TA re-baselines (ATR Wilder, TV supertrend) need explicit goldens + docs.
8. New incremental TA / ring buffers / history caps → **behind flags** + goldens.
9. Do not re-implement Round 1–8 wins.
10. Small, reviewable diffs. TA math in `src/pynescript/ast/evaluator/` first.
11. No secrets, no force-push, no commit of `.vsix` / `.metadata.key`.
12. Run targeted tests; report commands + numbers.
13. Keep exclusive ownership of assigned files; do not thrash other agents.

## Measurement

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --json /tmp/r9_agent.json
.venv/bin/python -m pytest tests/test_ta_incremental.py tests/test_evaluator.py \
  tests/test_parity.py tests/test_plotting_effects.py tests/test_series_ring_buffer.py \
  -q --tb=line
```

DoD for perf claims: ≥10–15% on a real path **or** structural win;
no >5% regression on `minimal`.

## Shared output

Write: `docs/perf_round9/AGENT_NN_<slug>.md` with:

- Role / ID
- What you did (files touched)
- Before/after bench or structural proof
- Tests run + pass/fail
- Residual / follow-ups
- Verdict: **win** | **partial** | **blocked** | **research-only**
