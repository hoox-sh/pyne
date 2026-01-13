# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""ANTLR4 Lexer, Parser, and Infrastructure.

Components:
- lexer: PinescriptLexer - tokenizes Pine Script source code
- parser: PinescriptParser - builds parse trees from tokens
- visitor: PinescriptParserVisitor - traverses parse trees
- listener: PinescriptParserListener - event-based parse tree traversal
- error_listener: PinescriptErrorListener - custom error handling
- generated: Auto-generated ANTLR files (do not edit manually)
"""

from __future__ import annotations
