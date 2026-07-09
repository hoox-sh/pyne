<!-- Context: project-intelligence/navigation | Priority: critical | Version: 1.0 | Updated: 2026-07-05 -->

# Project Intelligence

Internal context for the **pynescript** repository. Use this for orientation, exact
commands, repo-specific conventions, and gotchas an agent would miss.

## Concepts (what things are)

- [`architecture.md`](./concepts/architecture.md) — Component map and execution flow.
- [`pine-script-language.md`](./concepts/pine-script-language.md) — The Pine Script language itself (v5/v6 syntax, types, control flow).
- [`parser-ast.md`](./concepts/parser-ast.md) — ANTLR grammar → AST → unparser pipeline.
- [`langserver.md`](./concepts/langserver.md) — pygls LSP server, providers, metadata.
- [`backend-api.md`](./concepts/backend-api.md) — Flask Pro API, endpoints, gunicorn.
- [`build-pipeline.md`](./concepts/build-pipeline.md) — Nuitka, Fernet metadata, VSIX.

## Examples (working code)

- [`parse-and-unparse.md`](./examples/parse-and-unparse.md) — Round-trip via Python API.
- [`cli-usage.md`](./examples/cli-usage.md) — `pynescript` and `pynescript-lsp` CLIs.
- [`lsp-testing.md`](./examples/lsp-testing.md) — pytest-lsp test pattern.

## Guides (how to)

- [`dev-setup.md`](./guides/dev-setup.md) — Install, hatch envs, dev install.
- [`testing.md`](./guides/testing.md) — Test commands, fixtures, parametrize.
- [`grammar-changes.md`](./guides/grammar-changes.md) — Editing `.g4` and regenerating.
- [`adding-builtin.md`](./guides/adding-builtin.md) — Adding a new builtin function.

## Lookup (quick reference)

- [`commands.md`](./lookup/commands.md) — Make, hatch, CLI, npm.
- [`directory-map.md`](./lookup/directory-map.md) — Filesystem layout with role.
- [`entry-points.md`](./lookup/entry-points.md) — Console scripts, modules to invoke.

## Errors (known pitfalls)

- [`build-issues.md`](./errors/build-issues.md) — Nuitka, Fernet, .metadata.key.
- [`test-gotchas.md`](./errors/test-gotchas.md) — Builtin-script parametrize, antivirus.
