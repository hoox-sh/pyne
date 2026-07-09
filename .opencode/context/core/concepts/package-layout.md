# Package Layout

Source layout (Hatchling build) — `src/pynescript/` is the core library.

```
src/pynescript/
├── __init__.py
├── __main__.py              # CLI (click)
├── __about__.py             # Version (read by hatch)
├── py.typed                 # PEP 561 marker
├── ast/                     # Parser, AST, evaluator, linter
│   ├── helper.py            # parse(), unparse(), literal_eval()
│   ├── node.py              # ASDL-generated AST node classes
│   ├── builder.py           # AST construction helpers
│   ├── visitor.py           # NodeVisitor (read-only)
│   ├── transformer.py       # NodeTransformer (mutation)
│   ├── unparser.py          # AST → formatted source
│   ├── linter.py            # PineLinter — 9 rules
│   ├── collector.py         # Symbol collection
│   ├── error.py             # Parse/lint error types
│   ├── type_system.py       # Pine Script type system
│   ├── evaluator/           # Expression/statement evaluation
│   │   ├── base.py          # Evaluator base class
│   │   ├── literals.py / expressions.py / statements.py
│   │   ├── names.py / types.py
│   │   └── builtins/        # 482 builtin implementations
│   │       ├── technical.py + technical_submodules/
│   │       ├── strategy.py / arrays.py / matrix.py
│   │       └── map.py / strings.py / numeric.py ...
│   └── grammar/             # ANTLR4 + ASDL grammars
│       ├── antlr4/          # .g4 → generated/ (⚠️ auto-gen)
│       └── asdl/            # .asdl → generated/ (⚠️ auto-gen)
├── langserver/              # LSP (pygls)
│   ├── server.py            # Entry point
│   ├── config.py / workspace.py
│   ├── features/            # diagnostics, completion, hover, etc.
│   ├── providers/           # builtin_metadata, completion_items
│   └── protocol/            # constants, utils
├── compiler/                # Numba-compiled execution
│   ├── compiler.py
│   └── numba_builtins.py
├── util/                    # Data providers
│   ├── data.py              # Yahoo Finance, CCXT
│   ├── pine_facade.py
│   └── itertools.py
└── ext/                     # Extensions
    ├── pygments/            # Pine Script lexer
    ├── jupyter.py           # Jupyter magic
    └── nautilus_trader/     # NautilusTrader integration

backend/                     # Pro API (Flask, separate from core)
vscode-extension/            # VS Code extension (TypeScript)
clients/                     # Editor configs (Neovim, Zed, etc.)
scripts/                     # Build, metadata, copyright
tests/                       # Test suite
```

## Key Entry Points

| Entry Point | Command | Module |
|-------------|---------|--------|
| CLI | `pynescript` | `pynescript.__main__:cli` |
| LSP server | `pynescript-lsp` | `pynescript.langserver.__main__:main` |
| Backend API | `python -m backend.app` | `backend.app` |

## Core API

```python
from pynescript.ast.helper import parse, unparse, literal_eval

tree = parse(source_code)          # Pine Script → AST
code = unparse(tree)              # AST → formatted Pine Script
result = literal_eval("1 + 2")    # Evaluate expressions

from pynescript.ast.linter import lint_script
warnings = lint_script(source)     # Lint Pine Script

from pynescript.ast.transformer import NodeTransformer
from pynescript.ast.visitor import NodeVisitor
```
