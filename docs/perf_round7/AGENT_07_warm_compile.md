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

# AGENT 07 — H2 warm-compile product path

**Date:** 2026-08-02  
**Role / ID:** Round 7 Agent 07  
**Roadmap:** **H2** product warm-compile (SLOs, prewarm, IR disk cache on in deploy)  
**Verdict:** **win**

## What you did (files touched)

| File | Change |
|------|--------|
| `src/pynescript/compiler/engine.py` | `prewarm_scripts`, `ensure_compile_cache_dir`, `compile_deploy_config`, `prewarm_enabled`, env helpers; disk cache still **default on** |
| `src/pynescript/compiler/__init__.py` | Export new public hooks |
| `backend/app.py` | Lazy host prewarm (skip under `TESTING`); `POST /compile/prewarm`; health `compile` section; pass-through `auto_backend` / `compile_*` / `nopython_fallback_reason`; free CORS for `/compile` |
| `src/pynescript/__main__.py` | CLI `pynescript prewarm [PATH…]` |
| `.env.example`, `Dockerfile`, `docker/entrypoint-api.sh` | Deploy defaults: disk cache dir `/data/compile-cache`, `PYNE_COMPILE_PREWARM=1` |
| `docs/COMPILER_PLAN.md` | Product warm path + **SLOs** + env table |
| `docs/pyne/runtime/compiler/overview.mdx` | Short warm-compile product note |
| `docs/ROADMAP.md`, `docs/missing_features.md` | H2 marked delivered |
| `tests/test_compiler_numba.py` | prewarm_scripts / deploy config |
| `tests/test_backend.py` | health compile, prewarm endpoint, auto default |

## SLOs (documented, indicative)

| Path | SLO band |
| --- | --- |
| Interpret minimal @ 2k | ≤ 25 ms median |
| Interpret ta_combo @ 2k | ≤ 200 ms median |
| Cold compile (first SMA-class) | ≤ 2 s |
| Warm compile (source cache hit) | ≤ 1 ms (typ. ~0.01–0.05 ms) |
| Warm run ta_combo @ 5k | ≤ 5 ms |
| Cross-process disk rehydrate | ≤ ~60–70% of full cold |

Evidence base: Round 6 benches (`docs/perf_round6/00_summary.md`, AGENT_06).

## Flags / deploy defaults

| Env | Default | Meaning |
| --- | --- | --- |
| `PYNE_COMPILE_DISK_CACHE` | `1` | Disk IR/module cache on |
| `PYNE_COMPILE_CACHE_DIR` | XDG / Docker `/data/compile-cache` | Persistent volume |
| `PYNE_COMPILE_PREWARM` | `1` | Once-per-worker builtins on first `/run` |

Pro API: `mode` schema default **`auto`** (prefer compile; interpret fallback).  
Hooks: `POST /compile/prewarm`, `pynescript prewarm`, `prewarm_scripts(...)`.

## Before / after (structural)

| Gap | After |
| --- | --- |
| Engine prewarm only library-internal | Public scripts + CLI + Pro API |
| No health visibility | `GET /health` → `compile` section |
| Docker no compile cache volume path | `/data/compile-cache` ENV + mkdir |
| Auto diagnostics not always on wire | `/run` surfaces `auto_backend`, `compile_cached`, `compile_ms` |
| H2 undocumented SLOs | `docs/COMPILER_PLAN.md` section |

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_compiler_numba.py::TestCompileEngineRound6 \
  tests/test_backend.py::TestHealth \
  tests/test_backend.py -k "prewarm or mode_auto or mode_compile or health" \
  -q --tb=line
# 7 passed
```

## Residual / follow-ups

1. Multi-worker gunicorn still warms **per worker** (no `--preload` by default; SQLite/state safety).
2. True AOT of generated scripts not attempted — disk + Numba `.nbc` only.
3. pyne-worker edge host may want the same prewarm/health surface (H1 residual).
4. Optional: readiness probe that blocks until `builtins_warmed` when Numba present.

## Verdict

**win** — H2 productized: SLOs documented, disk IR cache deploy defaults, prewarm API + CLI, Pro API `mode=auto` prefers warm compile with soft fail without Numba.
