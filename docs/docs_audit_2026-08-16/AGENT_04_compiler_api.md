# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 04 — Compiler + Pro API

**Verdict:** **updated**

**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a009bb-118a-7e01-b58e-3736cb4a1cd8`

No pages added or deleted. Do not change `docs.json`.

## Pages read

- `docs/pyne/runtime/compiler/overview.mdx`
- `docs/pyne/runtime/compiler/numba.mdx`
- `docs/pyne/runtime/compiler/strategy-broker.mdx`
- `docs/pyne/runtime/compiler/parity.mdx`
- `docs/pyne/api/index.mdx`
- `docs/pyne/api/app-lifecycle.mdx`
- `docs/pyne/api/auth-and-keys.mdx`
- `docs/pyne/api/contract.mdx`
- `docs/pyne/api/runtime-bridge.mdx`
- `docs/pyne/api/endpoints/run.mdx`
- `docs/pyne/api/endpoints/preview.mdx`
- `docs/pyne/api/endpoints/backtest.mdx`
- `docs/pyne/api/services/chart-renderer.mdx`

## Pages edited

All 13 exclusive pages above.

## Pages added / deleted

None.

## Code checked

- `src/pynescript/__about__.py` (`hoox-pyne` **0.3.10**)
- `src/pynescript/compiler/engine.py` (`_DISK_META_VERSION = 9`, caches, prewarm, `CompiledScript.run` + `time=`, `plot_kinds`)
- `src/pynescript/compiler/compiler.py` (statement-form `hline`/`fill` stay nopython)
- `src/pynescript/compiler/numba_builtins.py` (SMA/EMA/RMA/RSI/highestbars/timestamp kernels)
- `src/pynescript/compiler/strategy_broker.py` (`begin_bar`, `_trigger_price`, `closed_trade_records`, event `kind`)
- `src/pynescript/compiler/__init__.py`
- `src/pynescript/runtime/host.py` (`Runtime.run`: `mode`/`libraries`/`timeout_seconds`, `_run_auto` + `compile_fallback_reason`, `_compile_eligible` skips `import`/`request.`, `_run_compiled` passes `time=`)
- `src/pynescript/runtime/series.py` (`PYNE_SERIES_RING` default off, `PYNE_SERIES_CAP` default on, maxlen floor 1000)
- `backend/runtime.py` (compat re-export, not SoT)
- `backend/app.py` (`GET /` + `/health`, CORS, `/run` + batch + prewarm + `WS /ws/run`, `libraries` pass-through, **no** `timeout_seconds`)
- `backend/middleware/schemas.py` (`RUN_SCHEMA` has `libraries`, not `timeout_seconds`; batch lacks both + `inputs`)
- `backend/middleware/auth.py` (fail-closed `ADMIN_TOKEN` → 403 `FORBIDDEN`; JSON store is **hash-only**)
- `backend/middleware/free_limits.py` (5000 bars / 256 KiB / 60 per 60s / 4 concurrent)
- `backend/api/preview.py`, `backend/services/backtest.py`, `backend/services/chart_renderer.py`
- `scripts/compare_interp_compile.py` + `tests/test_interp_compile_parity.py` (`--ignore-hline-keys` / `--ignore-fill-keys`, `expected_error` bucket)

## Must-fix status

| Item | Was | Now |
| --- | --- | --- |
| `libraries[]` on `/run` | Present on `run.mdx`; missing from contract TS + batch caveats | Documented on `/run`; **not** on `/run/batch` schema |
| `timeout_seconds` on `/run` | Contract listed it as if Flask accepted it | Clarified: `Runtime.run` / edge only; Flask `RUN_SCHEMA` → `UNKNOWN_FIELDS` |
| Disk IR cache meta version | Not numbered | `_DISK_META_VERSION = 9` on overview + numba cache table |
| Auth fail-closed `ADMIN_TOKEN` | Already correct | Kept; added `FORBIDDEN` failure row |
| `--ignore-hline-keys` / `--ignore-fill-keys` | Already present | Kept; added `expected_error` bucket |
| `mode=auto` + `compile_fallback_reason` | Partial (`auto_backend` only) | Eligibility rules + response field on index, contract, run, runtime-bridge, parity |

Other stale claims fixed: `backend/runtime.py` as SoT; `has_numba()` required for compile; `hline`/`fill` always object mode; JSON store raw-key files; `API_KEY_STORE` default `/root/...`; CORS methods GET/POST-only; missing `GET /health`; chart `height` as figsize; version pins `0.3.4+` / `0.3.7+` / `0.3.8+`.

## Remaining holes

- Flask `/run` still does not accept `timeout_seconds` (code, not docs). Edge workers / in-process `Runtime.run` do.
- `/run/batch` schema still omits `libraries` and `inputs`.
- Preview / backtest handlers still skip `PREVIEW_*` / `BACKTEST_QUICK_SCHEMA` (documented).
- `/backtest/quick` still ignores Pine strategy body (SMA-cross MVP).
- LSP-HTTP (`/lsp/completion|hover|diagnostics`) and `WS /ws/run` are listed, not fully specified (Agent 05 / LSP track).
- Health JSON `version` is the service label `1.0.0`, not package `0.3.10`.
- `_DISK_META_VERSION` will drift if the engine integer is bumped again.
- Repo `docs/COMPILER_PLAN.md` is not a Mintlify page (links converted to repo-path mentions).
- Compile emitter can lower same-symbol `request.security`, but `mode=auto` skips **any** `request.` source — explicit `mode=compile` is required to exercise that lowering.

## `docs.json`

No insertion. No nav change.
