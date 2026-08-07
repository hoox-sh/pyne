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

# Agent 01 — Inventory

| Field | Value |
| --- | --- |
| **Role / ID** | 01 — measure only |
| **Verdict** | **measure-only** (partial inventory; heavy sweeps aborted under load) |
| **Date** | 2026-08-04 |

## Baselines completed

| Run | Result |
| --- | --- |
| set01 interpret (249, 25 bars) | **249/249 OK (100%)** |
| set01 compile Runtime OK (249, 25 bars) | **249/249 OK (100%)** |
| builtin smoke 50 @ 200 bars | 48 OK + 2 both_error_same (auto_fib_*) |
| Known MISMATCH list (pre-fix) | 7 scripts sampled from aborted 1000-run |

## Note

Full set02–04 Runtime and 632-script parity sweep were **killed** after host
overload (12 agents + multi-worker corpus → false TIMEOUT storm). Prefer
targeted residual lists over concurrent full-set sweeps while agents edit.

## Artifacts

- `.cache/runtime_corpus_set01_interpret_r8.csv` (+ summary)
- `.cache/runtime_corpus_set01_compile_r8.csv` (+ summary)
- `.cache/parity_r8_sample120.json` (limit default 50)
- `.cache/parity_r8_known_mismatch.json` / `parity_r8_post_fix.json`
