<!-- Context: project-intelligence/concepts/architecture | Priority: critical | Version: 1.0 | Updated: 2026-07-05 -->

# Architecture

Pynescript is a multi-component toolchain centered on a Pine Script v5/v6 parser.
Source code lives in `src/pynescript/`, with a separate Flask backend, a TypeScript
VS Code extension, and an ANTLR/ASDL grammar pipeline.

## Component Map

| Component | Path | Entry Point | Purpose |
| --- | --- | --- | --- |
| Core library | `src/pynescript/` | `pynescript.ast` | parse / dump / unparse / eval / lint |
| CLI | `src/pynescript/__main__.py` | console `pynescript` | click group |
| LSP server | `src/pynescript/langserver/` | `pynescript-lsp` | pygls + lsprotocol |
| Pro API | `backend/` | `backend.app:app` (gunicorn) | Flask, chart preview, backtest |
| VS Code ext | `vscode-extension/` | `vscode-extension/src/extension.ts` | Bundles LSP binary |
| Grammar | `src/pynescript/ast/grammar/antlr4/resource/*.g4` | `antlr4` CLI | Pine v5/v6 grammar |
| ASDL | `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl` | `pyasdl` | AST node schema |
| Build script | `scripts/build/compile.py` | `python -m nuitka` | Compile LSP binary |

## Execution Flow (parse-and-unparse)

```
Pine Script source (.pine)
    └─> pynescript.ast.helper.parse(source, filename)
          ├─> antlr4.FileStream
          ├─> PinescriptLexer  (generated, grammar/antlr4/generated/)
          ├─> CommonTokenStream
          ├─> PinescriptParser (generated)
          ├─> PinescriptASTBuilder.visit_*  (ast/builder.py)
          └─> ast.node.* Script AST (ASDL-generated classes)
    └─> pynescript.ast.helper.unparse(tree)
          └─> AST unparser (ast/unparser.py)
```

## Execution Flow (LSP server)

```
IDE (VS Code, Neovim, ...)
    └─> STDIO / TCP ──> pynescript-lsp
          └─> pygls.lsp.server.LanguageServer
                ├─> features/diagnostics.py   (linter → Range)
                ├─> features/completion.py    (builtin_metadata.json)
                ├─> features/hover.py         (metadata lookup)
                ├─> features/definitions.py   (AST walk)
                ├─> features/references.py    (collect Name nodes)
                ├─> features/symbols.py       (documentSymbol)
                └─> features/formatting.py    (unparse)
```

## Public API Surface (core)

```python
from pynescript.ast import parse, unparse, dump, literal_eval, walk
from pynescript.ast.linter import PineLinter, lint_script
from pynescript.ast.visitor import NodeVisitor
from pynescript.ast.transformer import NodeTransformer
```

## 📂 Codebase References

- **Implementation**: `src/pynescript/__init__.py` (top-level)
- **Implementation**: `src/pynescript/ast/__init__.py` (public AST API re-exports)
- **Implementation**: `src/pynescript/langserver/server.py` (LSP server class)
- **Reference**: `pyproject.toml` (entry points, optional deps, hatch envs)
