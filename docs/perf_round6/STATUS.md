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

# Round 6 status

**Started:** 2026-07-31  
**BASE_SHA:** `0fc741bba73895ced13fe83b739c0d955f9c50f7`  
**Prompt:** `docs/perf_round6/PROMPT.md`  
**Synthesis:** `docs/perf_round6/00_summary.md`  
**Prior:** Round 5 complete (`docs/perf_round5/00_summary.md`)

## Agents

| ID | Role | Status | Verdict |
|---:|---|---|---|
| 01 | Interpret visit/Call residual | **done** | win |
| 02 | Series / expect residual | **done** | win |
| 03 | Residual TA incremental | **done** | win |
| 04 | Compiler numeric kernels | **done** | win |
| 05 | Compiler language surface | **done** | win |
| 06 | Cold JIT / engine harden | **done** | win |
| 07 | Strategy broker | **done** | win |
| 08 | Error handling harden | **done** | win |
| 09 | Collections / UDT | **done** | win |
| 10 | na-safety audit | **done** | win |
| 11 | Parser / sanitize | **done** | win |
| 12 | Runtime host + notes | **done** | win |

## Net benchmarks (interpret @ 2000 bars)

| script | R5 med_ms | R6 net med_ms | Speedup |
| --- | ---: | ---: | --- |
| minimal | 16.5 | **14.92** | 1.11× |
| ta_sma | 26.1 | **22.53** | 1.16× |
| ta_combo | 170 | **137.23** | 1.24× |
| strategy_ish | 84.4 | **63.07** | 1.34× |

## Verify (parent)

```text
763 passed  (R6 core cluster)
168 passed, 1 xfailed  (secondary collections/plot/risk)
```
