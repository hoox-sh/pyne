# API Overview

This page provides an overview of the PyneScript API organized by functionality.

## Core API

### Parsing and Unparsing

The primary entry points for working with Pine Script™ code:

```{eval-rst}
.. autofunction:: pynescript.ast.helper.parse
.. autofunction:: pynescript.ast.helper.unparse
.. autofunction:: pynescript.ast.helper.dump
```

### Evaluation

Execute and evaluate Pine Script™ expressions:

```{eval-rst}
.. autofunction:: pynescript.ast.helper.literal_eval
```

## AST Components

### AST Builder

```{eval-rst}
.. autoclass:: pynescript.ast.builder.PinescriptASTBuilder
   :members:
   :undoc-members:
   :show-inheritance:
```

### Node Transformer

```{eval-rst}
.. autoclass:: pynescript.ast.transformer.NodeTransformer
   :members:
   :undoc-members:
   :show-inheritance:
```

### Node Unparser

```{eval-rst}
.. autoclass:: pynescript.ast.unparser.NodeUnparser
   :members:
   :undoc-members:
   :show-inheritance:
```

### Evaluator

```{eval-rst}
.. autoclass:: pynescript.ast.evaluator.NodeLiteralEvaluator
   :members:
   :undoc-members:
   :show-inheritance:
```

## Built-in Functions

PyneScript implements 149+ Pine Script™ built-in functions organized by category:

### Technical Analysis

```{eval-rst}
.. automodule:: pynescript.ast.evaluator.builtins.technical
   :members:
   :undoc-members:
```

#### Technical Submodules

- **Core Indicators**: `pynescript.ast.evaluator.builtins.technical_submodules.core`
- **Moving Averages**: `pynescript.ast.evaluator.builtins.technical_submodules.moving_averages`
- **Oscillators**: `pynescript.ast.evaluator.builtins.technical_submodules.oscillators`
- **Volatility**: `pynescript.ast.evaluator.builtins.technical_submodules.volatility`
- **Volume**: `pynescript.ast.evaluator.builtins.technical_submodules.volume`
- **Patterns**: `pynescript.ast.evaluator.builtins.technical_submodules.patterns`
- **Advanced**: `pynescript.ast.evaluator.builtins.technical_submodules.advanced`

### Arrays and Collections

```{eval-rst}
.. automodule:: pynescript.ast.evaluator.builtins.arrays
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.matrix
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.map
   :members:
   :undoc-members:
```

### Strings and Numeric

```{eval-rst}
.. automodule:: pynescript.ast.evaluator.builtins.strings
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.numeric
   :members:
   :undoc-members:
```

### Plotting and Drawing

```{eval-rst}
.. automodule:: pynescript.ast.evaluator.builtins.plotting
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.drawing
   :members:
   :undoc-members:
```

### Strategy and Trading

```{eval-rst}
.. automodule:: pynescript.ast.evaluator.builtins.strategy
   :members:
   :undoc-members:
```

### Utility Functions

```{eval-rst}
.. automodule:: pynescript.ast.evaluator.builtins.utility
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.input
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.color
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.timeframe
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.ticker
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.request
   :members:
   :undoc-members:

.. automodule:: pynescript.ast.evaluator.builtins.logging
   :members:
   :undoc-members:
```

## Extensions

### Pygments Lexer

Syntax highlighting support for Pine Script™:

```{eval-rst}
.. autoclass:: pynescript.ext.pygments.lexers.PinescriptLexer
   :members:
   :undoc-members:
   :show-inheritance:
```

### Nautilus Trader Integration

```{eval-rst}
.. automodule:: pynescript.ext.nautilus_trader
   :members:
   :undoc-members:
```

## Utilities

### Pine Facade

```{eval-rst}
.. automodule:: pynescript.util.pine_facade
   :members:
   :undoc-members:
```

## Command-Line Interface

```{eval-rst}
.. click:: pynescript.__main__:cli
   :prog: pynescript
   :nested: full
```
