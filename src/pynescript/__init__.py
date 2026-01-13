# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""PyneScript: Pine Script AST Parser and Code Generator.

A comprehensive Python library for parsing, analyzing, and manipulating
TradingView Pine Script code. Provides ANTLR-based parsing, AST manipulation,
evaluation, and code generation capabilities.

Main Entry Points:
  >>> from pynescript import parse, dump, unparse
  >>> ast = parse("plot(close)")  # Parse Pine Script
  >>> print(dump(ast))  # View AST structure
  >>> print(unparse(ast))  # Generate source code

Submodules:
- ast: Core AST parsing and manipulation
- ext: Extensions (Pygments lexer, Nautilus Trader integration)
- util: Utility functions
"""

from __future__ import annotations
