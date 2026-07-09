<!-- Context: project-intelligence/examples/lsp-testing | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# LSP Testing

Two layers of LSP tests live in `tests/`:

1. **Direct handler tests** — `tests/test_lsp_features.py` calls
   `handle_completion`, `handle_hover`, etc. directly and checks the returned
   `lsprotocol.types.*` structures.
2. **End-to-end pygls tests** — `tests/test_langserver.py` boots an actual
   `LanguageServer` over an in-memory pipe (pytest-lsp).

## Direct Handler Test (unit)

```python
from lsprotocol import types as lsp
from pynescript.langserver.features.completion import handle_completion
from pynescript.langserver.providers.builtin_metadata import get_builtin

def test_completion_returns_ta_functions():
    params = lsp.CompletionParams(
        text_document=lsp.TextDocumentIdentifier(uri="file://x.pine"),
        position=lsp.Position(line=0, character=0),
    )
    result = handle_completion(None, params)
    labels = {item.label for item in result.items}
    assert "ta.sma" in labels
```

## End-to-end Test (pytest-lsp)

`pytest-lsp` is in the `dev-lsp` extra (`pip install -e ".[dev-lsp]"`). It provides
`client_server` fixture that wires a real `pygls` server to a client over an
asyncio transport.

```python
import pytest
from lsprotocol import types as lsp

@pytest.mark.asyncio
async def test_hover(client_server):
    client, server = client_server
    # open doc, position cursor, send textDocument/hover, assert MarkupContent
    ...
```

## Running

```bash
make test-lsp         # tests/test_langserver.py + tests/test_lsp_features.py
pytest tests/test_lsp_features.py -v
pytest tests/test_langserver.py -v
```

## Gotchas

- `pytest-asyncio` is required for `async def` tests in the pygls e2e suite.
  CI installs it explicitly: see `.github/workflows/ci.yml`.
- LSP handlers receive `params: lsprotocol.types.*Params` — type imports use
  `from lsprotocol import types as lsp`.
- Server instances in unit tests are `None` for the `ls` argument; handler functions
  must not depend on `ls.workspace` unless given a real `LanguageServer`.

## 📂 Codebase References

- **Implementation**: `tests/test_lsp_features.py` — direct handler tests.
- **Implementation**: `tests/test_langserver.py` — end-to-end pygls tests.
- **Implementation**: `src/pynescript/langserver/features/` — handlers under test.
- **Reference**: `pyproject.toml` — `[project.optional-dependencies] dev-lsp`
  adds `pytest-lsp`.
