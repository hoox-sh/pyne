# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import math

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.type_system import TypeRegistry
from pynescript.ast.visitor import NodeVisitor


# Optimize: Pre-compute math constants at module level
_MATH_CONSTANTS = {
    "math.pi": math.pi,
    "math.e": math.e,
    "math.phi": (1 + math.sqrt(5)) / 2,
    "math.rphi": 2 / (1 + math.sqrt(5)),
    # v6 feature (February 2025): bid and ask variables on 1T timeframe
    "bid": 100.01,  # Mock bid price for 1T timeframe
    "ask": 100.02,  # Mock ask price for 1T timeframe
}


class BaseEvaluator(NodeVisitor):
    """Base class for AST node evaluation with context and type registry support.

    Provides common functionality for all evaluator subclasses:
    - Context (variable, function, class definitions) management
    - Math constants and built-in values
    - Type registry for UDT and type checking
    - Error handling with custom messages

    Subclasses should override visit_* methods to handle specific AST node types.
    """

    def __init__(self, context: dict[str, Any] | None = None):
        """Initialize the evaluator with an optional context.

        Args:
            context: Optional dictionary of pre-defined variables, functions, and classes
                    (merged with built-in math constants)
        """
        # Initialize visitor cache for tracking visited nodes
        super().__init__()
        # Set up context: use provided or create empty dict
        self.context = context or {}
        # Merge pre-computed math constants into context for optimization
        self.context.update(_MATH_CONSTANTS)
        # Initialize type registry for user-defined types
        self.type_registry = TypeRegistry()

    def generic_visit(self, node: ast.AST):
        """Handle unexpected node types not covered by visit_* methods.

        Args:
            node: An AST node that couldn't be handled by a specific visitor

        Raises:
            ValueError: Always raised with a message identifying the unexpected node type
        """
        msg = f"unexpected type of node: {type(node)}"
        raise ValueError(msg)

    def _error(self, msg: str):
        """Raise a ValueError with a custom message.

        Convenience method for consistent error handling in evaluators.

        Args:
            msg: The error message to raise

        Raises:
            ValueError: Always raised with the provided message
        """
        raise ValueError(msg)
