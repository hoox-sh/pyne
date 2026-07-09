<!-- Context: libraries/concepts/pygls | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# pygls

`pygls` (Python Language Server) is the framework this repo's LSP server
(`src/pynescript/langserver/`) is built on. Subclass `LanguageServer` and
register feature handlers with the `@server.feature` decorator.

**context7 source**: `/openlawlibrary/pygls` — `llms.txt`,
`servers/howto/work-with-text-documents.md`,
`pygls/api-reference/workspace.md`. Verify against the pygls version pinned in
`pyproject.toml` (`pygls>=2.0.0`).

## Minimum Server

```python
from pygls.lsp.server import LanguageServer
from lsprotocol import types as lsp

server = LanguageServer("pynescript", "v1")

@server.feature(lsp.TEXT_DOCUMENT_COMPLETION,
                lsp.CompletionOptions(trigger_characters=[".", ","]))
def completions(params: lsp.CompletionParams) -> lsp.CompletionList:
    return lsp.CompletionList(is_incomplete=False, items=[])

if __name__ == "__main__":
    server.start_io()
```

## Workspace Access

The server keeps every opened document in `server.workspace`. Get a document:

```python
doc = ls.workspace.get_text_document(params.text_document.uri)
doc.source        # full text
doc.lines         # list[str] (line by line)
doc.path          # path on disk (if applicable)
doc.word_at_position(params.position)
```

The PositionCodec handles UTF-16 ↔ Python codepoint conversions automatically.

## Registering a Feature

```python
@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def hover(ls, params: lsp.HoverParams):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    return lsp.Hover(contents=lsp.MarkupContent(
        kind=lsp.MarkupKind.Markdown,
        value="**docs**",
    ))
```

Options (e.g. `CompletionOptions(trigger_characters=...)`) are advertised to the
client during capability negotiation. Handlers can take `(ls, params)` or just
`(params)`.

## This Repo

- Class: `PynescriptLanguageServer(LanguageServer)` in
  `src/pynescript/langserver/server.py`.
- Features split across `src/pynescript/langserver/features/`.
- One module per LSP method: `completion.py`, `hover.py`, `diagnostics.py`,
  `formatting.py`, `definitions.py`, `references.py`, `symbols.py`.

## Transports

- STDIO: `server.start_io()` (default; what editors use).
- TCP/WebSocket: `pygls.cli.start_server` (used for debugging).

## Gotchas

- Don't block the event loop — if a feature is expensive, use `asyncio.create_task`
  and return a placeholder.
- Async handlers: `async def feature(ls, params)` is supported; pygls awaits them.
- `ls.workspace.get_text_document(uri)` will create a `TextDocument` on disk
  if one isn't in memory yet (see pygls API ref caveat about disk fallback).

## 📂 Codebase References

- **Implementation**: `src/pynescript/langserver/server.py` — server class.
- **Implementation**: `src/pynescript/langserver/features/completion.py`.
- **Implementation**: `src/pynescript/langserver/features/hover.py`.
- **Reference**: `pyproject.toml` — `pygls>=2.0.0`, `lsprotocol>=2024.0.0`.
- **Reference**: `pyproject.toml` — `[project.optional-dependencies] dev-lsp`
  adds `pytest-lsp`.
