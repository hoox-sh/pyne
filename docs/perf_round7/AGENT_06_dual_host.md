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

# AGENT 06 — H1 dual-host residual (pyne-worker parity)

**AGENT_ID:** 06  
**ROLE:** ADVANCE H1 dual-host residual — package-level Runtime unify still open; host surface ports  
**Date:** 2026-08-02  
**BASE_SHA:** `045190203a1991aa683147995b5f42ee71169756`  
**Ownership:** edits under `/home/jango/Git/pyne-worker`; report under this tree

## 1. Scope

Diff SoT `backend/runtime.py` vs pyne-worker `src/pynescript_backend/runtime.py` for residual H1 items after Aug 2026 host-surface port. Port highest-ROI safe parity into **worker only** without breaking CF constraints (timeouts, R2, no hard heavy deps).

## 2. Gap table (post this agent)

| Feature | SoT (`backend/runtime.py`) | Worker (before) | Worker (after R7 A06) | Notes |
| --- | --- | --- | --- | --- |
| `_HOST_COMPILE_CACHE` | yes | yes | yes | already ported |
| `_HOST_COMPILE_FAIL_CACHE` | yes | yes | yes | already ported |
| `error_kind` / `_error_payload` | yes | yes | yes | already ported |
| `inputs` → auto→interpret | yes | yes (route only) | **yes (apply + route)** | **was broken**: overrides never set on evaluator |
| Compile success `compile_cached` | yes | yes | yes | already ported |
| Alerts export (interpret) | yes | yes | yes | already ported |
| Alerts on compile path | `[]` | missing | **`[]`** | schema parity |
| Append-only `current_series` | yes | yes | yes | already aligned |
| `_pine_defs_locked` after bar 0 | yes | yes | yes | already aligned |
| `_pine_bar_mode` + `_pine_ta_incremental` | evaluator | evaluator | yes | already on worker `CustomEvaluator` |
| Multi-run shared parse tree | works* | **broken** | **fixed** | bound `_pine_call_site` handlers on AST |
| JSON-safe series (NaN→null) | full multi-plot | first plot only / raw | **full `series` map** | optional numpy, pure fallback |
| Compile OHLCV pack | numpy + cache | 5 list comps | optional numpy arrays / list fallback | no hard numpy dep for CF |
| `input.*` declarations export | yes | no | **yes** (`inputs` + meta) | |
| `_FILL_CALL_RE` / `_pine_need_plot_ids` | yes | no | **flag set** | worker plot still scalar-only |
| logs / profile / profiler | yes | no | **no** | AXIS/Pro-only; residual |
| `data_feed` / `resolve_request_sources` | yes | no | **no** | residual package unify |
| Columnar multi-plot + plot_meta | yes | first plot only | first plot only | CF API thin; residual |
| Order-fill `ERROR_KIND_ORDER` path | yes | no | no | residual |
| Strategy `bar_time` JSON-safe | scalar `time` | PineSeries leak | **sanitized on drain** | worker keeps series `time` for `time[n]` |

\*SoT multi-run with package `parse` cache has the same bound-handler hazard if trees are shared across evaluators without site clear; worker now clears per run.

## 3. Ports done (pyne-worker)

### Files touched

| Path | Change |
| --- | --- |
| `src/pynescript_backend/runtime.py` | call-site clear; apply `_input_overrides`; input_defs export; JSON series; optional numpy pack; compile `alerts: []`; strategy `bar_time` sanitize; `_pine_need_plot_ids` |
| `src/handler.py` | forward `inputs` in `/run` response |
| `tests/test_runtime_host.py` | multi-run + inputs-apply goldens |

### Critical correctness fixes

1. **Multi-run / warm parse** — `visit_Call` stores `_pine_call_site` *on the AST node* with bound methods from the first evaluator. Host + package parse caches share trees → second `Runtime.run` invoked the *dead* first evaluator’s `plot` (empty/`None` plots).  
   **Fix:** `_clear_pine_call_sites(tree)` via `walk` once per interpret run (bar 0 rebinds; later bars keep hot path).

2. **`inputs` overrides** — auto mode correctly forced interpret, but interpret never set `evaluator._input_overrides`.  
   **Fix:** apply overrides + reset `_input_declarations` like SoT.

3. **Strategy event `bar_time`** — worker hosts `time` as `PineSeries` for `time[n]`; some strategy paths put the series into events.  
   **Fix:** unwrap `.current` when draining events (host-only, no package change).

### Parity / product polish

- Compile path: multi-series NaN→null via `_series_values_jsonable`; `alerts: []`.
- Interpret: export `inputs` declaration list (and `meta.inputs`).
- Handler: include `inputs` in HTTP response when present.

## 4. Tests run

```bash
cd /home/jango/Git/pyne-worker
PYTHONPATH=src python -m pytest \
  tests/test_runtime_host.py tests/test_alerts.py tests/test_parity.py -q --tb=line
# → 25 passed
```

`tests/test_smoke.py` needs `pytest-asyncio` (not installed in this env) — async plugin missing; not a regression from these changes.

Manual:

```text
multi-run same script → identical plots
inputs Length 14 vs 5 → last SMA differs
inputs export includes title Length
```

## 5. Residual / package-level unify checklist

See `docs/perf_round7/H1_unify_checklist.md`.

Highest remaining items:

1. **Package fix for call-site cache** — either don’t bind instance handlers on shared AST, or key sites by evaluator id; hosts should not need `_clear_pine_call_sites` forever.
2. **Share host helpers** — extract SoT `_series_values_jsonable` / OHLCV pack / logs-profile into importable module used by both hosts (or vendor thin copies under a single contract).
3. **Worker multi-plot / plot_meta** — columnar capture from SoT `backend/evaluator.py` if CF `/run` consumers need AXIS-style series maps.
4. **logs / profiler** — optional for worker; Pro API primary.
5. **request.* wiring** — `resolve_request_sources` + `data_feed`/`data_provider` on worker Runtime when edge has chart history.
6. **True package Runtime unify** — single `pynescript.runtime` (or backend facade) with worker as thin CF adapter (timeout/R2 only).

## 6. Verdict

**partial** — host-surface H1 residual advanced with correctness fixes (multi-run + inputs + event JSON); package-level Runtime unify still open. Not a full dual-host merge.

## One-liner

**Worker now applies input overrides, clears bound call-sites on shared parse trees (multi-run safe), exports inputs/alerts schema parity, and JSON-sanitizes compile series — full package Runtime unify still residual.**
