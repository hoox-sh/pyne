# API Reference

This section provides comprehensive documentation for all PyneScript modules, classes, and functions. The documentation is automatically generated from the source code to ensure 100% coverage and accuracy.

## Core Modules

The following pages document the complete PyneScript API:

```{toctree}
---
maxdepth: 2
---

apidoc/modules
```

## Quick Navigation

### Main Entry Points

- `pynescript.ast.helper` - Core parsing, unparsing, and evaluation functions
- `pynescript.__main__` - Command-line interface

### AST Components

- `pynescript.ast.builder` - AST construction from parse trees
- `pynescript.ast.unparser` - Convert AST back to Pine Script™
- `pynescript.ast.transformer` - AST transformation utilities
- `pynescript.ast.evaluator` - Expression evaluation engine
- `pynescript.ast.collector` - Statement and comment collection

### Grammar and Parsing

- `pynescript.ast.grammar.antlr4` - ANTLR4 grammar definitions
- `pynescript.ast.grammar.asdl` - Abstract Syntax Definition Language

### Extensions

- `pynescript.ext.pygments` - Pygments lexer for syntax highlighting
- `pynescript.ext.nautilus_trader` - Nautilus Trader integration

### Utilities

- `pynescript.util.pine_facade` - TradingView® Pine Script™ API utilities
