<!-- Context: libraries/navigation | Priority: critical | Version: 1.0 | Updated: 2026-07-05 -->

# External Libraries

External library reference docs, sourced via context7. Load only the file
relevant to your task — these are MVI summaries, not full API references.

## Concepts (what each library is)

- [`antlr4-python3.md`](./concepts/antlr4-python3.md) — ANTLR4 Python runtime.
- [`pygls.md`](./concepts/pygls.md) — pygls LSP server framework.
- [`lsprotocol.md`](./concepts/lsprotocol.md) — `lsprotocol` LSP type stubs.
- [`click.md`](./concepts/click.md) — Click CLI composition.
- [`nuitka.md`](./concepts/nuitka.md) — Nuitka Python compiler.
- [`cryptography-fernet.md`](./concepts/cryptography-fernet.md) — Fernet symmetric crypto.
- [`pyasdl.md`](./concepts/pyasdl.md) — pyasdl AST schema → code generator.

## Guides (how to)

- [`lsp-feature.md`](./guides/lsp-feature.md) — Wiring a new LSP feature in pygls.
- [`grammar-workflow.md`](./guides/grammar-workflow.md) — Adding rules to a `.g4` file.

## Lookup (quick reference)

- [`lsp-methods.md`](./lookup/lsp-methods.md) — Common `lsprotocol.types` methods.

## Errors (known pitfalls)

- [`antlr4-errors.md`](./errors/antlr4-errors.md) — Token/parse error patterns.
- [`nuitka-errors.md`](./errors/nuitka-errors.md) — Onefile / data-dir pitfalls.

## Source Provenance

Each file cites its context7 library ID and source URL. If a section says
"verified against this repo's usage", it was cross-checked against the imports
in `src/pynescript/`.
