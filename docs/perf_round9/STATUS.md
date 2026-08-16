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

# Round 9 status — interpret residual perf (4 agents)

**Started:** 2026-08-16
**BASE_SHA:** `41d3e491dc42c6ea918abc8e85e1065fae2e5af6`
**Prompt:** `docs/perf_round9/PROMPT.md`
**Prior:** Round 7 complete (`docs/perf_round7/STATUS.md`); Round 8 was parity

## Agents

| ID | Role | Status | Verdict |
|---:|---|---|---|
| 01 | Plot-path structural (capture / pack) | **done** | **partial** |
| 02 | Residual incremental TA (nested full paths) | **done** | **win** |
| 03 | Interpret dispatch (`visit_Call` envelope) | **done** | **win** |
| 04 | Runtime host + series hot path | **done** | **win** |

## Net (parent merge)

| script | baseline med_ms | net med_ms | Speedup |
| --- | ---: | ---: | ---: |
| minimal | 27.61 | **10.21** | 2.70× |
| ta_sma | 39.29 | **19.98** | 1.97× |
| ta_combo | 200.59 | **138.11** | 1.45× |
| strategy_ish | 100.62 | **64.66** | 1.56× |

Verify: **595 + 449** passed (6 + 22 skipped). Synthesis: `00_summary.md`.

## Parent baseline (interpret @ 2000 bars)

Frozen: `docs/perf_round9/bench_r9_baseline.json` on `41d3e491`.

| script | med_ms | µs/bar | bars/s |
| --- | ---: | ---: | ---: |
| minimal | **27.61** | 13.8 | 72 400 |
| ta_sma | **39.29** | 19.6 | 50 900 |
| ta_combo | **200.59** | 100.3 | 9 970 |
| strategy_ish | **100.62** | 50.3 | 19 900 |

Compile warm ta_combo run **1.00 ms @ 5k**. Do not flip `PYNE_SERIES_RING` default on.

Worktree-isolated. Parent merges after agents report.
