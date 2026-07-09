<!-- Context: libraries/guides/lsp-feature | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Adding a New LSP Feature

How to wire a new `textDocument/*` (or `workspace/*`) handler into the
pynescript LSP server.

## 1. Pick the Method

Find the constant in `lsprotocol.types`:

```python
from lsprotocol import types as lsp
lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL   # e.g. for semantic highlighting
```

## 2. Add a Handler Function

In `src/pynescript/langserver/features/<name>.py`:

```python
from __future__ import annotations

from lsprotocol import types as lsp
from pygls.lsp.server import LanguageServer

from pynescript.ast import parse
from pynescript.langserver.workspace import Workspace


def handle_semantic_tokens(ls: LanguageServer,
                           params: lsp.SemanticTokensParams) -> lsp.SemanticTokens:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    tree = parse(doc.source, doc.path)
    data: list[int] = []
    # walk `tree`, collect (deltaLine, deltaStart, length, tokenType, tokenModifiers)
    return lsp.SemanticTokens(data=data)
```

## 3. Register the Handler in `server.py`

In `PynescriptLanguageServer.__init__` (or wherever features are bound):

```python
from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens

self.feature(lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL,
             lsp.SemanticTokensOptions(
                 legend=lsp.SemanticTokensLegend(
                     token_types=[lsp.SemanticTokenTypes.function,
                                  lsp.SemanticTokenTypes.variable],
                     token_modifiers=[lsp.SemanticTokenModifiers.declaration],
                 ),
             ))(handle_semantic_tokens)
```

`self.feature(...)` is a method on `pygls.LanguageServer` that both registers
the handler **and** returns a decorator, so `(handler)` applies it.

## 4. Capability Negotiation

If the client must opt in, advertise it in the server's `server_capabilities`
property (override `__init__` or implement a method that pygls calls during
`initialize`).

## 5. Test It

Add a unit test in `tests/test_lsp_features.py`:

```python
def test_semantic_tokens_returns_list():
    params = lsp.SemanticTokensParams(
        text_document=lsp.TextDocumentIdentifier(uri="file://x.pine"),
    )
    result = handle_semantic_tokens(None, params)
    assert isinstance(result.data, list)
```

For e2e, add a test in `tests/test_langserver.py` using the
`pytest-lsp` `client_server` fixture.

## Pitfalls

- `ls` may be `None` in unit tests — your handler must tolerate that or branch
  on `ls is not None` to fetch the document.
- Always return an instance of the expected return type. Returning `None` from
  a request handler is allowed; from a notification it isn't.
- Use `lsp.Position(line=N, character=M)` — both 0-indexed.
- Convert ANTLR positions (1-indexed line) when handing off to `lsprotocol`.

## 📂 Codebase References

- **Implementation**: `src/pynescript/langserver/server.py` — feature bindings.
- **Implementation**: `src/pynescript/langserver/features/completion.py` — example.
- **Implementation**: `src/pynescript/langserver/features/hover.py` — example.
- **Reference**: `libraries/concepts/pygls.md`, `libraries/concepts/lsprotocol.md`.
