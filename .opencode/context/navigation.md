<!-- Context: navigation | Priority: critical | Version: 1.0 | Updated: 2026-07-05 -->

# Pynescript — OpenCode Context Root

Entry point for project-specific and external library context. Categories follow the
function-based layout (`concepts/`, `examples/`, `guides/`, `lookup/`, `errors/`).

## Categories

| Category | Purpose | Navigation |
| --- | --- | --- |
| `project-intelligence/` | This repo: architecture, commands, conventions, gotchas | [navigation](./project-intelligence/navigation.md) |
| `libraries/` | External libraries (context7-sourced): pygls, antlr4, click, Nuitka, etc. | [navigation](./libraries/navigation.md) |

## Repo at a Glance

- **Name:** pynescript — Python toolchain for TradingView Pine Script (parser, AST,
  evaluator, linter, LSP, Pro API, VS Code extension).
- **Stack:** Python 3.10+ (hatchling, antlr4-python3-runtime, pygls/lsprotocol, click,
  flask), TypeScript (VS Code ext), ANTLR4 `.g4` grammar, ASDL, Nuitka.
- **Layout:** src-layout package at `src/pynescript/`; `backend/` (Flask Pro API);
  `vscode-extension/` (TS); `scripts/`; `tests/`.
- **Top instructions:** [`../../AGENTS.md`](../../AGENTS.md) — repo agent guide.
- **Deep design doc:** [`../plans/pynescript-lsp-implementation.md`](../plans/pynescript-lsp-implementation.md)
  — 1000+ line LSP architecture plan (NOT agent rules).

## Loading Order (for an agent)

1. Read [`../../AGENTS.md`](../../AGENTS.md) for repo rules.
2. Read `project-intelligence/concepts/architecture.md` for component map.
3. Read `project-intelligence/lookup/commands.md` for build/test commands.
4. Load only the external library file relevant to your task
   (`libraries/concepts/pygls.md` for LSP work, `libraries/concepts/antlr4-python3.md`
   for grammar work, etc.).

## 📂 Codebase References

- **Implementation**: `src/pynescript/` — package source.
- **Implementation**: `backend/` — Pro API Flask server.
- **Implementation**: `vscode-extension/` — TypeScript VS Code extension.
- **Reference**: `pyproject.toml` — build, dependencies, hatch envs, console scripts.
- **Reference**: `Makefile` — developer command shortcuts.
- **Reference**: `scripts/build/compile.py` — Nuitka binary builder.
