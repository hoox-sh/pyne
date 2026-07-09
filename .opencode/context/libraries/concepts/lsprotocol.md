<!-- Context: libraries/concepts/lsprotocol | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# lsprotocol

`lsprotocol` is the official Python stub package for the Language Server Protocol
types. Every `params` and every return value from a pygls handler is an
`lsprotocol.types.*` instance.

**context7 source**: (used in combination with `/openlawlibrary/pygls`).
Cross-verified against `lsprotocol>=2024.0.0` in `pyproject.toml`.

## Import Convention

```python
from lsprotocol import types as lsp
```

Never `from lsprotocol.types import *` — keep the namespace.

## Common Types You'll Touch

| Type | Used For |
| --- | --- |
| `lsp.Position(line, character)` | cursor position (0-indexed both) |
| `lsp.Range(start, end)` | text range (start and end are `Position`s) |
| `lsp.Location(uri, range)` | a `Range` inside a document |
| `lsp.TextDocumentIdentifier(uri)` | reference to a doc by URI |
| `lsp.TextEdit(range, new_text)` | a single edit |
| `lsp.WorkspaceEdit(changes={uri: [TextEdit, ...]})` | multi-doc edit |
| `lsp.CompletionItem(label, kind, detail, documentation, ...)` | one completion |
| `lsp.CompletionList(is_incomplete, items)` | full completion result |
| `lsp.Hover(contents=MarkupContent(...), range=...)` | hover payload |
| `lsp.MarkupContent(kind=MarkupKind.Markdown, value=...)` | rich hover body |
| `lsp.Diagnostic(range, message, severity, code, source)` | one lint finding |
| `lsp.SymbolKind.Function`, `lsp.SymbolKind.Variable`, ... | document-symbol kind |
| `lsp.DocumentSymbol(name, kind, range, selection_range, children)` | tree node |

## LSP Method Constants

```python
lsp.TEXT_DOCUMENT_COMPLETION
lsp.TEXT_DOCUMENT_HOVER
lsp.TEXT_DOCUMENT_DEFINITION
lsp.TEXT_DOCUMENT_REFERENCES
lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL
lsp.TEXT_DOCUMENT_FORMATTING
lsp.TEXT_DOCUMENT_RANGE_FORMATTING
lsp.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS
lsp.TEXT_DOCUMENT_DID_OPEN
lsp.TEXT_DOCUMENT_DID_CHANGE
lsp.TEXT_DOCUMENT_DID_SAVE
lsp.TEXT_DOCUMENT_DID_CLOSE
lsp.WORKSPACE_SYMBOL
lsp.INITIALIZE
lsp.SHUTDOWN
```

Full list: `dir(lsp)` filtered to `TEXT_DOCUMENT_*` / `WORKSPACE_*`.

## Pitfalls

- `Position` is **0-indexed** on both `line` and `character`. The character
  offset is in UTF-16 code units (LSP spec); pygls' `PositionCodec` handles the
  conversion against Python's actual codepoint index. Don't roll your own.
- `Range` end is **inclusive of the last character**, not exclusive of the
  line after. Re-check when generating from parser positions.
- `MarkupKind` values are strings: `"plaintext"`, `"markdown"`.

## 📂 Codebase References

- **Implementation**: `src/pynescript/langserver/features/*.py` — handler
  signatures use these types.
- **Implementation**: `src/pynescript/langserver/protocol/constants.py` — re-exports.
- **Reference**: `pyproject.toml` — `lsprotocol>=2024.0.0`.
