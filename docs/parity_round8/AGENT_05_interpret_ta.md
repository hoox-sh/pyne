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
