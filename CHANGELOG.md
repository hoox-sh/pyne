# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Stable `CRYPTO_KEY` / `METADATA_KEY` resolution for Fernet metadata encryption (GitHub secrets wired).
- Multi-target Docker image (`api` / `api-dev` / `lsp`), `docker-bake.hcl`, prod compose overlay, Makefile docker helpers.
- Key-store backends selectable via `STORE_BACKEND` (`json` | `sqlite` | `redis`) for multi-worker / multi-replica deploys.
- PyPI publish workflow (Trusted Publishing on `v*` tags) and package build job in CI.
- Strategy events system: StrategyEvent dataclass, full emission from strategy.* builtins, parity test corpus.
- pine-worker/ as colocated extra tool: TypeScript evaluator port + Python to TS converter script (convert-python-to-ts.py).
- var / varip declaration modes and ReAssign support.
- Consolidation of main with recent plan branch work (2026-07-09).

### Changed
- **PyPI distribution name is `hoox-pyne`** (import package and CLIs remain `pynescript` / `pynescript-lsp`). Avoids collision with upstream elbakramer `pynescript` on PyPI. Install: `pip install "hoox-pyne[lsp]"`.
- Version **0.3.0** prepared as first `hoox-pyne` release candidate (tag when ready).
- VS Code extension rebrand: **PYNE — Pine Script™ for VS Code** (`pyne` 0.2.2), HOOX logo icon, marketplace description as part of the HOOX open trading stack, TradingView® / Pine Script™ trademark disclaimer, and richer TextMate syntax highlighting (namespaces, annotations, colors, UDT/enum, multiline strings).
- VS Code extension packaging: esbuild-bundle `vscode-languageclient` into the VSIX (fixes palette “command not found” when `node_modules` was omitted), explicit `onCommand` activation, resilient command handlers, and shared output channel.
- CI rewritten for the post-AXIS-extract repo: Python lint/test matrix, package build, Docker smoke; removed dead `frontend/` jobs.
- `require_admin_token` enforces `ADMIN_TOKEN` + `X-Admin-Token` (fail-closed); prod compose drops host source mounts via `volumes: !override`.
- `pyproject.toml` project URLs, Alpha classifier, Python 3.13, `pro` extra includes `redis`.
- Updated documentation (ROADMAP, missing_features, implementation status, LSP plan, devops Docker) to reflect current state.
- Backend test collection fixes post-integration.

### Fixed
- Interpreter: `ta.rising` / `ta.falling` / `ta.highestbars` / `ta.lowestbars` no longer raise
  `TypeError: '>=' not supported between instances of 'NoneType' and 'NoneType'` when the
  series contains Pine `na` (e.g. VIDYA warmup on MA-STER). Unsafe `CommonIndicators`
  overrides were removed so na-safe `TechnicalHelpers` implementations are used.

### Removed
- Stale `Dockerfile.api` (folded into multi-target `Dockerfile`).
- Dead `technical_refactored.py` and internal refactoring notes from the published package tree.
- Broken AXIS-only GitHub workflows (`axis-nightly`, PWA/e2e jobs) — AXIS CI lives in [jango-blockchained/axis](https://github.com/jango-blockchained/axis).
