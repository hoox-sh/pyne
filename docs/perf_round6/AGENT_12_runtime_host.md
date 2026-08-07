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

# AGENT 12 — Runtime host product path + dual-host notes

**AGENT_ID:** 12  
**ROLE:** Runtime host product path + dual-host drift (PERF + PRODUCT)  
**Date:** 2026-07-31  
**BASE_SHA:** `32697c97f7e56de817325356e4dbd692809ecbe8`

## 1. Scope & files

| Path | Change |
| --- | --- |
| `/mnt/data/home/jango/Git/pynescript/backend/runtime.py` | auto/compile ergonomics: eligibility, fail cache, inputs force interpret, drop hard Numba gate on compile path, non-mutating series meta read |
| `/mnt/data/home/jango/Git/pynescript/tests/test_compiler_numba.py` | `TestRuntimeAutoMode`: inputs → interpret; compile fail negative cache |
| `/home/jango/Git/pyne-worker` | **not patched** (drift documented below) |

Preserved concurrent Agent 08 surface: `_error_payload` / `ERROR_KIND_*` on compile failures.

## 2. Bugs found

1. **Auto + `inputs` correctness:** `mode=auto` preferred compile even when `inputs={...}` was passed. Compile path never applies overrides → silent wrong SMA/length etc. vs interpret defaults.  
   **Fix:** non-empty `inputs` short-circuits to interpret with  
   `compile_fallback_reason="input.* overrides require interpret path"`.

2. **Hard Numba gate on compile:** `_run_compiled` / `_compile_eligible` refused all compile when Numba missing. Engine already supports **object-mode without Numba** (strategy/collections). Worker already aligned.  
   **Fix:** eligibility only requires `pynescript.compiler.engine`; Numba absence surfaces as compile error for pure-numeric scripts (auto-cached).

3. **Broken intermediate state:** first patch renamed `_HAS_NUMBA` → `_HAS_COMPILER` before updating body (would NameError). Completed rewrite of eligibility/auto/compile block.

4. **series_map mutation:** host `pop`’d `__drawings` / `__events` from `CompiledScript.run` result. Switched to `.get` so shared/reused maps cannot lose meta.

## 3. Changes

### Warm compile path ergonomics

- Host success cache (`_HOST_COMPILE_CACHE`) unchanged (R5 Agent 05).
- **New** `_HOST_COMPILE_FAIL_CACHE` (sha256 → reason, max 128): after a deterministic **compile-time** failure, auto skips re-transpile/JIT attempt and goes straight to interpret with the same reason. Does **not** cache `Compiled Runtime Error` (data-dependent).
- Success clears any prior negative entry for that source hash.

### Accurate auto fallback reasons

| Situation | `auto_backend` | `compile_fallback_reason` |
| --- | --- | --- |
| compile OK | `compile` | (absent) |
| `import` prefilter | `interpret` | `import statements not supported in compile path` |
| `request.*` prefilter | `interpret` | `request.* not supported in compile path` |
| non-empty `inputs` | `interpret` | `input.* overrides require interpret path` |
| transpile/exec fail | `interpret` | `Compile Error: …` (cached) |
| compiled bar-loop fail | `interpret` | `Compiled Runtime Error: …` (not cached) |
| no compiler package | `interpret` | `compiler package unavailable` |

Docstring on `Runtime.run` now matches Pro API (`RUN_SCHEMA` default `mode=auto`) vs bare `Runtime` default (`PYNE_RUNTIME_MODE` or `interpret`).

### Residual host perf (measure-first)

R5 JSON pack + OHLCV identity cache remain the SoT wins. Re-measure (this tree):

| Path | Result |
| --- | --- |
| Warm host `mode=compile` wrap (multi-plot TA @ 2k bars) | ~0.5–2.6 ms total; `compile_ms≈0` when cached |
| Official bare compile run ta_combo @ 5k | **1.095 ms** (matches R5) |
| Cold OHLCV pack @ 2k (first touch) | ~1.2 ms residual; warm identity hit ~0.01 ms |
| JSON series pack (3 float64 series) | ~half of thin wrap when multi-plot |

**No further host micro-opt landed** — residual wrap is dominated by cold dict→array pack on new bar lists and multi-series JSON; not ≥10–15% on a real warm path after R5. Product leverage remains **default auto + warm workers**, not more pack micro-wins.

### Dual-host (pyne-worker) — skip patch

Worker twin: `/home/jango/Git/pyne-worker/src/pynescript_backend/runtime.py` (~798 LOC vs SoT ~1550).

| Feature | SoT | worker |
| --- | --- | --- |
| `_HOST_COMPILE_CACHE` | yes | **no** |
| `_HOST_COMPILE_FAIL_CACHE` | yes | **no** |
| OHLCV numpy pack + cache | yes | **no** (list comps) |
| `_series_values_jsonable` NaN→null | yes | partial (first plot only / raw tolist) |
| logs / profile / error_kind | yes | **no** |
| `inputs` / profiler | yes | **no** |
| auto_backend + fallback reason | yes | yes |
| Numba not required for object mode | yes (after this) | yes (already) |
| request.* / chart viewport / fill path | richer | thinner worker API |

**Why skip worker patch:** not a small safe port — would need host cache + pack helpers + optional inputs semantics + tests under CF packaging. Recommend a dedicated dual-host PR that **vendors or shares** SoT helpers rather than copy-paste 400+ lines.

## 4. Benchmarks

```bash
PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
```

### Interpret Runtime (n=2000) — this measurement

| script | med_ms | bars/s | vs R5 net |
| --- | ---: | ---: | --- |
| minimal | **15.85** | 126k | R5 16.5 — no regression |
| ta_sma | **23.97** | 83k | R5 26.1 |
| ta_combo | **148.78** | 13.4k | R5 170 |
| strategy_ish | **70.03** | 28.6k | R5 84.4 |

(Interpret improvements may include concurrent R6 agents; Agent 12 did not change interpret loop.)

### Compile + execute (n=5000)

| script | cold_ms | warm_ms | run_med_ms | mode |
| --- | ---: | ---: | ---: | --- |
| minimal | ~595 | 0.05 | 0.031 | numba |
| ta_sma | ~591 | 0.01 | 0.059 | numba |
| ta_combo | ~4452 | 0.01 | **1.095** | numba |
| strategy_ish | ~17 | 0.01 | ~28.5 | object |

### Host wrap (manual)

Warm `Runtime.run(..., mode=compile)` multi-plot TA @ 2k: **~0.5–2.6 ms** with `compile_cached=True`. Auto warm tracks compile when eligible.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py::TestRuntimeAutoMode \
  tests/test_backend.py -k "mode or compile or auto or profile" -q --tb=short
# → 10 passed (5 auto + backend mode subset)
```

## 6. Residual risks

- Fail cache keys by **raw source only** — env change (install Numba mid-process) needs process restart or success-path clear (success already clears).
- Empty `inputs={}` is falsy → still tries compile (OK). Non-empty with keys the script ignores still forces interpret (conservative).
- Agent 08 may still land more error_kind wiring; merge carefully around `_run_compiled` / interpret bar-loop errors.
- Worker lag remains product dual-host risk (R5 #9).

## 7. Out of scope

- Cold JIT / disk njit cache (Agent 06)
- Interpret visit/Call tax (Agent 01)
- Porting full SoT runtime into pyne-worker
- Changing Pro API schema default (already `auto`)

## Parent merge notes

1. Land **after** Agent 08 if both touch `backend/runtime.py` (resolve `_error_payload` + auto fail-cache).
2. Keep Agent 12 tests in `TestRuntimeAutoMode`.
3. Do **not** re-gate compile on Numba for object mode.
4. Product: document that AXIS/Pro should pass `mode=auto` (schema default) and warm-pool workers; bare library default remains interpret for unit tests.
5. Next dual-host PR: port fail-cache + host compile cache + OHLCV/JSON pack first; leave logs/profile second.

## One-liner

**Auto mode now respects input overrides, allows object-mode compile without Numba, and caches compile-time failures for warm auto fallback; host wrap already R5-fast — dual-host port still open.**
