<!-- Context: project-intelligence/concepts/langserver | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Language Server (LSP)

`pynescript-lsp` is a pygls-based language server exposing completion, hover,
diagnostics, formatting, definition, references, and document symbols for Pine
Script. It is distributed as a Nuitka-compiled onefile binary plus a VS Code
extension.

## Layout

- `src/pynescript/langserver/server.py` — `PynescriptLanguageServer(LanguageServer)`.
- `src/pynescript/langserver/__main__.py` — `main()` → `server.start_io()`.
- `src/pynescript/langserver/config.py` — Server config / capabilities.
- `src/pynescript/langserver/workspace.py` — Project workspace.
- `src/pynescript/langserver/features/` — One module per LSP capability:
  `completion.py`, `hover.py`, `diagnostics.py`, `formatting.py`, `definitions.py`,
  `references.py`, `symbols.py`.
- `src/pynescript/langserver/protocol/` — Protocol constants and helpers.
- `src/pynescript/langserver/providers/` — Builtin metadata + completion builders.

## Providers

- `providers/builtin_metadata.json` — Plaintext metadata for 482+ builtins
  (categories, signatures, docs, examples). Used at dev time.
- `providers/builtin_metadata.json.enc` — Fernet-encrypted copy bundled into the
  compiled binary.
- `providers/builtin_metadata.json.sha256` — Integrity hash.
- `providers/builtin_metadata.py` — Loader (`get_builtin`, `get_metadata`).
- `providers/completion_items.py` — `CompletionItem` builder.
- `providers/metadata_decrypt.py` — Runtime decrypt path for the encrypted bundle.

## Console Entry Point

```toml
[project.scripts]
pynescript-lsp = "pynescript.langserver.__main__:main"
```

Run with: `pynescript-lsp` (STDIO) or `python -m pynescript.langserver`.

## Capabilities (advertised)

- `textDocument/publishDiagnostics` (linter → 9 rules)
- `textDocument/completion` (482 builtins, trigger chars `[".", ","]`)
- `textDocument/hover` (signature + docstring + see-also)
- `textDocument/definition` / `textDocument/references`
- `textDocument/documentSymbol` / `textDocument/workspaceSymbol`
- `textDocument/formatting` / `textDocument/rangeFormatting`
- `textDocument/semanticTokens`

## 📂 Codebase References

- **Implementation**: `src/pynescript/langserver/server.py` — class
  `PynescriptLanguageServer`.
- **Implementation**: `src/pynescript/langserver/features/` — per-feature handlers.
- **Implementation**: `src/pynescript/langserver/providers/builtin_metadata.py`.
- **Reference**: `pyproject.toml` — `[project.scripts]` defines `pynescript-lsp`.
- **Reference**: `.opencode/plans/pynescript-lsp-implementation.md` — full design doc.
