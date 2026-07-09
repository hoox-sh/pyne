<!-- Context: libraries/lookup/lsp-methods | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# LSP Methods (Quick Lookup)

The `textDocument/*` and `workspace/*` methods this server uses, with the
matching `lsprotocol.types` constant and parameter/return type.

## Request Methods (client → server, expect response)

| Method | Constant | Params | Returns |
| --- | --- | --- | --- |
| Completion | `TEXT_DOCUMENT_COMPLETION` | `CompletionParams` | `CompletionList \| None` |
| Hover | `TEXT_DOCUMENT_HOVER` | `HoverParams` | `Hover \| None` |
| Definition | `TEXT_DOCUMENT_DEFINITION` | `DefinitionParams` | `Location \| Location[] \| None` |
| References | `TEXT_DOCUMENT_REFERENCES` | `ReferenceParams` | `Location[] \| None` |
| Document Symbol | `TEXT_DOCUMENT_DOCUMENT_SYMBOL` | `DocumentSymbolParams` | `DocumentSymbol[] \| None` |
| Formatting | `TEXT_DOCUMENT_FORMATTING` | `DocumentFormattingParams` | `TextEdit[] \| None` |
| Range Formatting | `TEXT_DOCUMENT_RANGE_FORMATTING` | `DocumentRangeFormattingParams` | `TextEdit[] \| None` |
| Semantic Tokens | `TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL` | `SemanticTokensParams` | `SemanticTokens` |
| Workspace Symbol | `WORKSPACE_SYMBOL` | `WorkspaceSymbolParams` | `SymbolInformation[] \| None` |

## Notification Methods (client → server, no response)

| Method | Constant | Params |
| --- | --- | --- |
| Did Open | `TEXT_DOCUMENT_DID_OPEN` | `DidOpenTextDocumentParams` |
| Did Change | `TEXT_DOCUMENT_DID_CHANGE` | `DidChangeTextDocumentParams` |
| Did Save | `TEXT_DOCUMENT_DID_SAVE` | `DidSaveTextDocumentParams` |
| Did Close | `TEXT_DOCUMENT_DID_CLOSE` | `DidCloseTextDocumentParams` |

## Server → Client (this repo publishes diagnostics)

| Method | Constant | Params |
| --- | --- | --- |
| Publish Diagnostics | `TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS` | `PublishDiagnosticsParams(uri, diagnostics: list[Diagnostic])` |

## Capability / Lifecycle

| Method | Constant |
| --- | --- |
| Initialize | `INITIALIZE` |
| Initialized | `INITIALIZED` |
| Shutdown | `SHUTDOWN` |
| Exit | `EXIT` |

These are handled by pygls automatically; you don't need to override them
unless you want custom server metadata.

## Capability Negotiation

To advertise a feature with options (e.g. trigger chars), pass an `Options`
object as the second arg to `@server.feature(...)`:

```python
@server.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(trigger_characters=[".", ","]),
)
def completions(params): ...
```

## Common Imports

```python
from lsprotocol import types as lsp

# Positions / ranges
lsp.Position(line=0, character=0)
lsp.Range(start=lsp.Position(0, 0), end=lsp.Position(0, 5))
lsp.Location(uri="file://...", range=...)

# Text edits
lsp.TextEdit(range=lsp.Range(...), new_text="...")
lsp.WorkspaceEdit(changes={uri: [text_edit, ...]})

# Completion
lsp.CompletionItem(label="x", kind=lsp.CompletionItemKind.Function)
lsp.CompletionList(is_incomplete=False, items=[...])

# Hover
lsp.Hover(contents=lsp.MarkupContent(kind=lsp.MarkupKind.Markdown, value="..."))

# Diagnostics
lsp.Diagnostic(
    range=lsp.Range(...),
    message="...",
    severity=lsp.DiagnosticSeverity.Warning,
    code="LINT001",
    source="pynescript",
)
```

## 📂 Codebase References

- **Reference**: `libraries/concepts/lsprotocol.md` — full type reference.
- **Reference**: `src/pynescript/langserver/features/*.py` — live usage.
