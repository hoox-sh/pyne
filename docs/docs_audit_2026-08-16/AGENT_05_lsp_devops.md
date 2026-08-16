# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Agent 05 — LSP + DevOps

**Worktree:** `/home/jango/.grok/worktrees/git-pynescript/subagent-01a009bb-118d-7880-aea4-fb814312cd76`  
**Verdict:** **updated**  
**docs.json:** not edited (no pages added or deleted)

## Pages read

All exclusive pages:

- `docs/pyne/lsp/index.mdx`
- `docs/pyne/lsp/architecture.mdx`
- `docs/pyne/lsp/builtin-metadata.mdx`
- `docs/pyne/lsp/clients.mdx`
- `docs/pyne/lsp/vscode-extension.mdx`
- `docs/pyne/lsp/features/diagnostics.mdx`
- `docs/pyne/lsp/features/completion.mdx`
- `docs/pyne/lsp/features/hover.mdx`
- `docs/pyne/lsp/features/navigation.mdx`
- `docs/pyne/lsp/features/formatting.mdx` (accurate; no edit)
- `docs/pyne/lsp/features/semantic-tokens.mdx`
- `docs/pyne/lsp/features/inlay-hints.mdx`
- `docs/pyne/devops/index.mdx`
- `docs/pyne/devops/local-dev.mdx`
- `docs/pyne/devops/ci.mdx`
- `docs/pyne/devops/release.mdx`
- `docs/pyne/devops/pypi-publish.mdx`
- `docs/pyne/devops/publish-checklist.mdx`
- `docs/pyne/devops/docker.mdx`
- `docs/pyne/devops/nuitka-build.mdx`
- `docs/pyne/devops/metadata-crypto.mdx`
- `docs/pyne/devops/gcp.mdx`
- `docs/pyne/devops/observability.mdx`
- `docs/pyne/devops/security.mdx`

Also: `docs/WRITING.md`, `docs/docs_audit_2026-08-16/PROMPT.md`. Root `AGENTS.md` is **absent** in this worktree.

## Pages edited

22 MDX files (formatting.mdx left as-is).

### Must-fix facts (now aligned)

| Claim | Was | Now |
| --- | --- | --- |
| Publisher / extension id | implied; trademark on vscode page | `hoox-sh` / `hoox-sh.pyne` **0.3.10**; trademark removed (product `index.mdx` only) |
| LSP Docker image | missing / local `pynescript-lsp` only | `ghcr.io/hoox-sh/pyne/lsp` (+ api/cli); workflow **GHCR** |
| VPS AXIS port | leftover `:8081` as if production | VPS AXIS **:80**, API **:5002**; local AXIS **:8081** called out |
| PyPI | checklist `pyne-0.3.0*.whl`, tag `v0.3.0` | `hoox-pyne` / `hoox_pyne-0.3.10-*.whl`, tag `v0.3.10` |
| Compose fail-closed | already mostly right | restated: `volumes: !override`, `ADMIN_TOKEN:?` required |
| Workflow names / tags | missing `ghcr.yml`; “Build & Release LSP”; Python 3.12 / Nuitka 2.0.* | **CI**, **Build & Release**, **Publish**, **GHCR**; tags `v*`; Nuitka pin **3.11** + `nuitka>=2.5.1,<2.8` |

### Other corrections

- Semantic tokens are an AST visitor (custom 13-type / 4-modifier legend), not an empty stub.
- Server version is `__about__.__version__` (0.3.10), not `0.1.0`. Signature help / code actions are **not** advertised.
- Feature handlers take the workspace-cached AST; incremental edits pad/clamp instead of dropping.
- Completion/hover include keywords + user enums.
- VS Code compile is **esbuild** (`out/extension.js`); launch is PATH auto-detect, not `--parent-dir`.
- Metadata loader prefers **plaintext** then `.enc`. Encrypt uses `_resolve_fernet_key` (env/file before generate).
- Gunicorn entrypoint default timeout is **120s**; prod compose defaults **60s**; Cloud Run `--timeout=60s`.
- Dropped AXIS nightly / `bun run test:security` / Playwright artifacts from this repo’s DevOps pages.
- Clients snippets now match `clients/zed.json` / `emacs.el` / `neovim.lua` (`pyne-lsp` preferred).

## Pages added / deleted

None. No `docs.json` insertion.

## Code checked

- `src/pynescript/__about__.py` (`0.3.10`)
- `src/pynescript/langserver/` (`server.py`, `config.py`, `workspace.py`, `features/*`, `providers/builtin_metadata.py`, `metadata_decrypt.py`, `__main__.py`)
- `vscode-extension/package.json` (`publisher: hoox-sh`, `version: 0.3.10`, id `hoox-sh.pyne`)
- `vscode-extension/src/extension.ts` (auto-detect, file watcher, init options)
- `clients/neovim.lua`, `clients/emacs.el`, `clients/zed.json`, `clients/README.md`
- `Makefile` (docker-build-lsp, docker-push-ghcr, deploy-vps)
- `Dockerfile`, `docker-bake.hcl`, `docker-compose.yml`, `docker-compose.prod.yml`
- `docker/entrypoint-api.sh` (`GUNICORN_TIMEOUT` default 120), `docker/entrypoint-cli.sh` (`pyne`)
- `.github/workflows/ci.yml` (`name: CI`), `release.yml` (`name: Build & Release`), `publish.yml` (`name: Publish`), `ghcr.yml` (`name: GHCR`)
- `scripts/build/compile.py`, `scripts/build/ci_build.py`, `scripts/build/README.md`
- `scripts/deploy_vps.sh` (health API `:5002`, AXIS `:80`)
- `cloudbuild.yaml`
- `pyproject.toml` (scripts `pyne` / `pyne-lsp`, extras, hatch matrices)

## Remaining holes

Code / ops drift (not invented in docs):

1. `cloudbuild.yaml` substitution `_PYNESCRIPT_VERSION` is still `"0.3.0"`.
2. `docker-bake.hcl` `PYNESCRIPT_VERSION` default is `"0.3.0"` (Make overrides from `__about__.py`).
3. Compose `args.PYNESCRIPT_VERSION` defaults to `0.2.0` in both compose files.
4. `config.get_filter_options()` still lists only `*.pine` / `*.pinev5` / `*.pinev6` — no `*.pyne`.
5. `initializationOptions` (`formattingEnabled` / …) are sent by the extension and **ignored** by the Python server.
6. `clients/emacs.el` / `neovim.lua` root/filetype globs omit `.pyne` (docs note the workaround).
7. Makefile help still points AXIS at `github.com/jango-blockchained/axis`.
8. No root `AGENTS.md` in this worktree (CRYPTO_KEY policy lives in `scripts/build/README.md` + workflows).
9. Hatch test matrix is 3.10–3.12; CI includes 3.13.

No new DevOps page for GHCR — covered on [Docker](/pyne/docs/devops/docker) and [CI](/pyne/docs/devops/ci). Parent should **not** add nav unless they want a dedicated page.

## Verdict

**updated** — exclusive LSP + DevOps pages now match 0.3.10 code. Did not commit.
