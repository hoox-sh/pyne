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

# H1 — Dual-host Runtime unify checklist

**Status:** host surface largely aligned (Aug 2026 + R7 Agent 06); package-level unify open  
**SoT:** `backend/runtime.py` (+ `backend/evaluator.py`, `backend/series.py`)  
**Worker:** `/home/jango/Git/pyne-worker/src/pynescript_backend/`

## Closed on worker (do not re-discover)

- [x] `_HOST_COMPILE_CACHE` / `compile_cached`
- [x] `_HOST_COMPILE_FAIL_CACHE` (deterministic compile fails only)
- [x] `error_kind` + `_error_payload` (parse/compile/runtime/data/mode)
- [x] `mode=auto` prefilter (`import` / `request.*`)
- [x] Numba not required for object-mode eligibility
- [x] `inputs` non-empty → interpret under auto
- [x] **`inputs` applied** as `_input_overrides` on interpret (R7 A06)
- [x] Alerts export on interpret + empty on compile
- [x] Append-only OHLCV `current_series` + series cap
- [x] `_pine_defs_locked` after first bar
- [x] `_pine_bar_mode` + `_pine_ta_incremental` on worker evaluator
- [x] Multi-run shared AST: **clear `_pine_call_site` per run** (R7 A06)
- [x] Compile series NaN→null multi-plot (R7 A06)
- [x] `input.*` declarations on result (`inputs` / meta)
- [x] Strategy event `bar_time` JSON-safe when `time` is series (R7 A06)

## Residual — host (worker-only OK)

| Item | Pri | Notes |
| --- | --- | --- |
| logs / `profile` / `profiler` flag | P2 | AXIS gutter; soft-optional on CF |
| `resolve_request_sources` + data_feed args | P2 | when edge has chart/history wiring |
| Columnar multi-plot + `plot_meta` | P2 | CF `/run` still first-plot-centric |
| `ERROR_KIND_ORDER` pending-fill path | P3 | SoT process_pending guard |
| OHLCV pack identity cache | P3 | SoT warm bench; worker optional |
| Chart viewport / `_make_chart` | P3 | Pro API richer |

## Residual — package (true H1 unify)

| Item | Pri | Notes |
| --- | --- | --- |
| **Bound call-site on shared AST** | P0 | Fix in `expressions.py`: don’t pin instance methods on cached trees; or site key includes evaluator generation |
| Extract shared host helpers module | P1 | jsonable series, OHLCV pack, error_payload, compile caches |
| Single Runtime implementation | P1 | `pynescript` package owns bar loop; worker = timeout/R2/HTTP |
| Align `time` host model | P2 | SoT scalar vs worker series — pick one + goldens |
| Vendor sync policy | P2 | `scripts/sync_vendor.sh` after package Runtime move |
| Goldens: multi-run + inputs on both hosts | P1 | already on worker; mirror SoT tests |

## Suggested unify PR sequence

1. **Package:** call-site cache not evaluator-bound (or invalidate on new evaluator) + multi-run golden.  
2. **Extract** pure helpers (no Flask/CF) → importable from SoT backend and worker.  
3. **Thin worker:** delete duplicated bar loop; wrap package Runtime with `timeout_seconds` + response shaping.  
4. **CF smoke:** deploy path still uses `python_modules/` via `sync_vendor.sh`.

## DoD for “H1 closed”

- [ ] One bar-loop implementation for interpret used by Pro API and pyne-worker  
- [ ] Multi-run + inputs + auto/compile caches identical semantics  
- [ ] Worker pytest + SoT `TestRuntimeAutoMode` green  
- [ ] No CF regression (timeouts, R2, no new hard native deps)
