# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Docs audit synthesis — 2026-08-16

Six worktree agents audited every Mintlify tab against `hoox-pyne` **0.3.10**
source. Parent merged exclusive trees; no `docs.json` nav change (no pages
added or deleted).

## Scorecard

| ID | Track | Verdict | Pages |
|---:|---|---|---|
| 01 | End User + product hub | **updated** | 15 |
| 02 | Core | **updated** | 10 |
| 03 | Runtime semantics + builtins | **updated** | 12 |
| 04 | Compiler + Pro API | **updated** | 13 |
| 05 | LSP + DevOps | **updated** | 22 (+ formatting already clean) |
| 06 | Reference + satellites | **updated** | 20+ |

## Cross-cutting corrections

- Runtime SoT is `src/pynescript/runtime/`; `backend.runtime` is a shim.
- Mode defaults: library **interpret**, `POST /run` **auto**, `pyne run` **compile-only**.
- `libraries=` on Flask `/run` (not `/run/batch`); `timeout_seconds` is
  `Runtime.run` / edge only.
- Incremental TA includes 0.3.10 volume kernels; leftover `nvi`/`pvi`.
- Interpret ATR is Wilder RMA of TR (parent aligned F1 wording).
- pine-worker is a **sister repo**; PyneTS submodule pin is 0.1.0 interpret-only
  vs published `@hoox-sh/pynets` 0.2.0.
- Extension `hoox-sh.pyne` 0.3.10; LSP image `ghcr.io/hoox-sh/pyne/lsp`;
  VPS AXIS `:80`.

## Parent glue

- F1 in `docs/ROADMAP.md` + roadmap/missing-features MDX: ATR already Wilder.
- `docs/compatibility_guarantee.md`: PyPI name `hoox-pyne`.

## Remaining (code, not docs)

- Flask `/run/batch` lacks `libraries` / `inputs`.
- `cloudbuild.yaml` / bake version defaults still `0.3.0`.
- PyneTS submodule lag vs npm 0.2.0.
- `GET /health` `version` is not package `0.3.10`.
- Generated `docs/pyne/llm.txt` not regenerated.

## Reports

Per-agent: `AGENT_01_enduser.md` … `AGENT_06_reference.md`.
