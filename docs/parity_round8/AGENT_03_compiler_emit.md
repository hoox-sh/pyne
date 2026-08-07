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

# Agent 03 — Compiler visitor emit (parent completion)

| Field | Value |
| --- | --- |
| **Role / ID** | 03 — compiler visitor emit |
| **Verdict** | **partial** (security SYMBOL + bare tickerid landed; other emit residual open) |
| **Date** | 2026-08-04 |

## Context

Original Agent 03 subagent did not finish a report (session drop). Parent completed
the highest-value emit fix identified by Agent 08 handoff.

## What landed

### `src/pynescript/compiler/compiler.py`

1. **`_is_chart_security_symbol`** — treat `SYMBOL` / `'SYMBOL'` / `"SYMBOL"` as
   chart identity (compile stubs for `syminfo.tickerid` / `ticker`).
2. **Bare v3 `tickerid` / `ticker` in `visit_Name`** — return `repr("SYMBOL")`
   before series-array allocation so `security(tickerid, "D", close)` passthrough
   works (was allocating `tickerid_arr` and emitting `np.nan`).

### Proof

```text
request.security(syminfo.tickerid, "D", close) → close_arr[__bar_idx]
security(tickerid, "D", close)                 → close_arr[__bar_idx]
```

Tests:

- `TestCompileCoverageSprint::test_request_security_syminfo_time_stubs`
- `TestCompileCoverageSprint3::test_bare_security_passthrough` (`use_cache=False`)

## Residual / handoff

| Item | Owner |
| --- | --- |
| `default_qty_*` into strategy broker ctor | 03 follow-up |
| `strategy.cash` series_map vs constant | 03 |
| `begin_bar(..., time_arr[…])` for bar_time | 03 |
| bgcolor `_emit_drawing` drop `title=` | 03 |
| Object-mode dict emit duplicate plot titles | 03 (engine pack fixed for numeric) |
| HMA / supertrend / VWAP / HA SSL value MISMATCH | 02 numba + 05 TA |

## Disk cache

Engine `_DISK_META_VERSION` bumped **2 → 3** so source-hash disk IR from pre-fix
emit is not reused.
