<!-- Context: project-intelligence/lookup/entry-points | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Entry Points

All public entry points an agent might invoke, with the exact import path or
console script name. `pyproject.toml` is the source of truth.

## Console Scripts (`[project.scripts]`)

| Name | Target | Module |
| --- | --- | --- |
| `pynescript` | `pynescript.__main__:cli` | `src/pynescript/__main__.py` |
| `pynescript-lsp` | `pynescript.langserver.__main__:main` | `src/pynescript/langserver/__main__.py` |

## Pygments Plugin (`[project.entry-points."pygments.lexers"]`)

- `pinescript` → `pynescript.ext.pygments.lexers:PinescriptLexer`

## Python Module Entry Points (`python -m ...`)

| Command | Module |
| --- | --- |
| `python -m pynescript` | `src/pynescript/__main__.py` |
| `python -m pynescript.langserver` | `src/pynescript/langserver/__main__.py` |
| `python -m backend.app` | `backend/app.py` (gunicorn target) |
| `python -m pynescript.ast` | `src/pynescript/ast/__main__.py` (grammar tooling) |
| `python -m nuitka ...` | (from `scripts/build/compile.py`) |

## Public Python API (re-exported from `pynescript.ast`)

```python
from pynescript.ast import (
    parse,                  # parse Pine source to AST
    unparse,                # AST → Pine source
    dump,                   # AST → string
    literal_eval,           # safe expression eval
    walk,                   # depth-first traversal
    copy_location,          # copy lineno/col_offset
    NodeVisitor,            # base visitor
    NodeTransformer,        # base transformer
    Script, Expression,     # AST node classes
    AST,                    # base node
    ERROR, ERROR_TOKEN,     # error nodes
)
from pynescript.ast.linter import PineLinter, lint_script, LintWarning
from pynescript.ast.type_system import ...  # type predicates
```

## Backend HTTP Routes

| Method | Path | Blueprint |
| --- | --- | --- |
| POST | `/run` | `backend.api.preview.run_bp` (if present) |
| POST | `/preview/chart` | `backend.api.preview.preview_bp` |
| POST | `/preview/indicator` | `backend.api.preview.preview_bp` |
| POST | `/backtest/quick` | `backend.api.preview.backtest_bp` |

## LSP Methods Advertised

`textDocument/publishDiagnostics`, `textDocument/completion`,
`textDocument/hover`, `textDocument/definition`, `textDocument/references`,
`textDocument/documentSymbol`, `textDocument/workspaceSymbol`,
`textDocument/formatting`, `textDocument/rangeFormatting`,
`textDocument/semanticTokens`.

## 📂 Codebase References

- **Reference**: `pyproject.toml` — `[project.scripts]`, `[project.entry-points]`.
- **Implementation**: `src/pynescript/__main__.py` — `cli` Click group.
- **Implementation**: `src/pynescript/langserver/__main__.py` — `main()`.
- **Implementation**: `backend/app.py` — Flask app routes.
