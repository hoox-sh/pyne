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

# Agent 05 — Interpret TA residual

| Field | Value |
| --- | --- |
| **Role / ID** | 05 — interpret TA |
| **Verdict** | **partial** |
| **Date** | 2026-08-04 |

## What landed

Strict-window alignment for sample statistics so interpret matches compile/TV
`na`-in-window → `na` (not skip-na window):

| File | Change |
| --- | --- |
| `technical_submodules/core.py` | `_stdev_inc` / `_dev_inc` / `_variance_inc` require full finite window; NaN → na |
| `technical_submodules/basic.py` | full `_dev` / `_variance` strict window |
| `technical_submodules/common.py` | related strict-window helpers (if present in diff) |

## Residual

- HMA / Kalman-style plot drift (`245_ind_hma_…`) — still MISMATCH
- Supertrend dual-path (`073_str_…`) — still MISMATCH
- BBI (`178_ind_…`) — still MISMATCH
- Session VWAP (`071_str_…`) — still MISMATCH

These need focused Agent 02 kernel work and/or Heikin-Ashi / session request path.

## Tests

Covered indirectly via existing TA suites; no new dedicated residual goldens
for HMA/BBI in this pass.
