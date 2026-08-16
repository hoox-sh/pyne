# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 01 — End User + product hub

**Date:** 2026-08-16  
**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a009bb-1189-7621-9dc5-4a90dbaf57ce`  
**Verdict:** **updated**

Exclusive track only. Did not edit `docs.json`, runtime/core/lsp/api/devops/reference pages. Did not commit.

`AGENTS.md` is not present in this worktree (referenced by older audit notes / `DESIGN.md`). Followed `docs/docs_audit_2026-08-16/PROMPT.md` + `docs/WRITING.md`.

## Pages read

All exclusive pages:

- `docs/pyne/index.mdx`
- `docs/pyne/enduser/index.mdx`
- `docs/pyne/enduser/getting-started/installation.mdx`
- `docs/pyne/enduser/getting-started/quick-start.mdx`
- `docs/pyne/enduser/getting-started/configuration.mdx`
- `docs/pyne/enduser/guides/cli.mdx`
- `docs/pyne/enduser/guides/library-api.mdx`
- `docs/pyne/enduser/guides/evaluate-scripts.mdx`
- `docs/pyne/enduser/guides/editors.mdx`
- `docs/pyne/enduser/guides/pro-api-usage.mdx`
- `docs/pyne/enduser/guides/troubleshooting.mdx`
- `docs/pyne/enduser/reference/cli-commands.mdx`
- `docs/pyne/enduser/reference/modes.mdx`
- `docs/pyne/enduser/reference/glossary.mdx`
- `docs/pyne/enduser/reference/faq.mdx`

## Pages edited

Same 15 files (no pages added, no pages deleted). No `docs.json` insertion needed.

## Pages added / deleted

None.

## Code checked

| Path | What was verified |
| --- | --- |
| `src/pynescript/__about__.py` | `__version__ = "0.3.10"` |
| `src/pynescript/__main__.py` | Commands: `info`, `check`, `parse-and-dump`, `parse-and-unparse`, `format`, `lint`, `compile`, `prewarm`, `run`, `data`. Aliases `dump`/`ast`/`unparse`/`fmt`/`ls`. **No** `--fix`, **no** `download`, **no** `--mode` on `run`. `run` = `compile_script` + synthetic OHLCV (`--bars` default 50). |
| `src/pynescript/ast/helper.py` | `parse` / `unparse` / `dump` / `walk` / `literal_eval`. Parse LRU (`PYNE_PARSE_CACHE`, default on). `dump(indent)` is `int \| str \| None`. |
| `src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py` | `Name` fields: `id`, `ctx`. |
| `src/pynescript/runtime/host.py` | `Runtime.run(..., mode, inputs, profiler, timeout_seconds, libraries, realtime_*)`. `mode=None` → `PYNE_RUNTIME_MODE` else **interpret**. |
| `src/pynescript/runtime/__init__.py` | Package SoT; documents `backend.runtime` as shim. |
| `backend/runtime.py` | Compat re-export (`sys.modules` alias to `pynescript.runtime.host`). |
| `backend/app.py` | Routes: `GET /`, `GET /health`, `POST /run`, `POST /compile/prewarm`, `POST /run/batch`, `WS /ws/run`, auth; blueprints preview/backtest/lsp/git-oauth. `/run` does **not** pass `timeout_seconds`. `libraries` capped at 32. |
| `backend/middleware/schemas.py` | `RUN_SCHEMA` default `mode="auto"`; fields include `inputs`, `libraries`, `profiler`, alert flags. **No** `timeout_seconds`. `RUN_BATCH_SCHEMA` has no `libraries`/`inputs`. |
| `backend/middleware/free_limits.py` | Defaults 5000 / 256 KiB / 4 / 60 per 60s — already correct on the Pro API page. |
| `backend/api/preview.py` | `/preview/chart`, `/preview/indicator`, `/backtest/quick`. |
| `pyproject.toml` | Dist `hoox-pyne`; extras `lsp`, `dev-lsp`, `data`, `datafeed`, `compile`, `pro`; scripts `pyne` / `pyne-lsp` + aliases. |
| `vscode-extension/package.json` | Version 0.3.10; publisher `hoox-sh`; id **`hoox-sh.pyne`**; `lsp.command` default **`auto`**. |
| `clients/README.md`, `clients/neovim.lua`, `clients/zed.json`, `clients/emacs.el` | Preferred binary `pyne-lsp`. |
| `pynets/src/runtime/interpret.ts`, `pynets/src/cli.ts` | PyneTS Runtime is **interpret-only**. Options: `inputs` / `broker` / `timeframe`. CLI `pynets run` has **no** `--mode`; `--bars` default **20**. No `src/runtime/compile/`. |
| `src/pynescript/ext/jupyter.py` | `%%pinescript` is lint + parse + unparse, not `Runtime.run`. |

## What was stale (and fixed)

- Product hub claimed Library + CLI evaluate as `mode=auto`. Library default is **interpret**; `pyne run` is **compile-only**.
- End User hub omitted [modes](/pyne/docs/enduser/reference/modes) from the reference list.
- `configuration.mdx`: invented `lint --fix`; treated `backend.runtime` as SoT; VS Code command default was `pyne-lsp` (actual `auto`); missing `PYNE_PARSE_CACHE`, `libraries`, `profiler`.
- `evaluate-scripts.mdx` worked example imported `backend.runtime`; prewarm described as “when the CLI subcommand is present”.
- `glossary.mdx`: PyPI name still `pynescript`; Runtime defined as `backend.runtime.Runtime`.
- `faq.mdx`: “no evaluate subcommand”; bar-loops via `backend.runtime`; Jupyter path unverified.
- `editors.mdx`: marketplace TODO; settings/snippets used `pynescript-lsp` as default; Helix missing `.pyne`.
- `pro-api-usage.mdx`: invented `pynescript.api.PynescriptAPI`; `/run` table missing `libraries`/`profiler`; `backend/runtime.py` described as the evaluate engine.
- `cli.mdx`: phantom “Download command”; lint directory TODO; “CLI stops at parse/lint/data”; stale data table labels.
- `modes.mdx`: PyneTS claimed compile/`auto`/`libraries`/`--mode` and `src/runtime/compile/`. This checkout is interpret-only.
- Troubleshooting used `pip show pynescript` (wrong dist name).

## Remaining holes

- `POST /run/batch` schema has no `libraries` / `inputs` / `timeout_seconds` — called out only indirectly. Agent 04 (API) owns the systems page.
- `timeout_seconds` is library-only; HTTP callers cannot set it. Documented, but there is no worker-side substitute on this page.
- `realtime_*` kwargs exist on Python `Runtime.run` and are tabulated on modes; no end-user tutorial.
- AXIS-facing `POST /lsp/preevaluate` and `POST /api/git/oauth/*` are not walked as consumer recipes (LSP/API tracks).
- Marketplace listing at `itemName=hoox-sh.pyne` is cited from `README.md` / `package.json`; this agent did not fetch the live Marketplace page.
- Jupyter extra is not a `pyproject.toml` extra; `IPython` is an implicit optional import.
- `AGENTS.md` missing from the worktree (not a docs-page hole).

## Verdict

**updated** — exclusive pages now match 0.3.10 CLI/runtime/backend/editor surface. No nav change required.
