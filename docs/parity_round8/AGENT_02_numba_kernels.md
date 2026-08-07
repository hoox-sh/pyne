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

# Agent 02 — Numba TA kernels

| Field | Value |
| --- | --- |
| **Role / ID** | 02 — numba kernels |
| **Verdict** | **blocked** (subagent did not land product edits) |
| **Date** | 2026-08-04 |

## Status

No changes to `numba_builtins.py` in this round. Subagent timed out / dropped
before a fix.

## Open MISMATCH (post-R8)

| Script | Symptom |
| --- | --- |
| `245_ind_hma_kahlman_…` | plot_0 max_abs ~0.4; shape None↔bool residual partly host |
| `073_str_stochrsi_plus_supertrend` | Up/Down Trend 2 drift; Tendence MA na vs value |
| `178_ind_bulls_bears_index_bbi_2` | BBI systematic drift |
| `071_str_multi_vwap_crossover` | Midnight/Session VWAP seed + signal cascade |
| `045_str_ha_univlong…` | HA/SSL warm-up na vs value (may be security/HA, not pure numba) |

## Follow-up

Re-run Agent 02 with exclusive ownership of `numba_builtins.py` + goldens in
`test_compiler_numba.py` for HMA / VWAP session / BBI / supertrend seed.
