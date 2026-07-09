# Entry Points (Quick Reference)

## CLI Commands

| Command | Description |
|---------|-------------|
| `pynescript parse-and-dump <file>` | Parse and print AST |
| `pynescript parse-and-unparse <file>` | Normalize formatting |
| `pynescript lint <file>` | Check for issues |
| `pynescript lint --fail-on warnings` | Fail on warnings |
| `pynescript data <symbol>` | Fetch market data |
| `pynescript-lsp` | Start LSP server (STDIO) |

## Make Targets

| Command | Action |
|---------|--------|
| `make test` | All tests |
| `make test-lsp` | LSP tests only |
| `make test-backend` | Backend tests only |
| `make lint` | ruff check |
| `make fmt` | ruff format |
| `make run-lsp` | Start LSP server |
| `make run` | Start backend API |
| `make build` | Nuitka LSP binary |
| `make build-check` | Verify imports (fast) |

## Hatch Environments

| Command | Action |
|---------|--------|
| `hatch run test:test` | Run tests via hatch |
| `hatch run lint:style` | ruff via hatch |
| `hatch run lint:typing` | mypy via hatch |
| `hatch run lint:format` | ruff format via hatch |
| `hatch run docs:build` | Sphinx docs |

## Core Python API

```python
from pynescript.ast.helper import parse, unparse, literal_eval
from pynescript.ast.linter import lint_script
from pynescript.ast.transformer import NodeTransformer
from pynescript.ast.visitor import NodeVisitor
```
