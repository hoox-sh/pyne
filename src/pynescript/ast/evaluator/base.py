# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
    # Additional v6 syminfo / timeframe constants (simple defaults)
    "syminfo.isin": "",
    "syminfo.current_contract": None,
    "syminfo.main_tickerid": "UNKNOWN",
    "timeframe.main_period": "D",
    # v6 text formatting constants
    "text.formatting.none": "",
    "text.formatting.bold": "bold",
    "text.formatting.italic": "italic",
    "text.formatting.bold_italic": "bold italic",
    # v6 text size constants (can be used as int or str; int for points in v6)
    "size.auto": "auto",
    "size.tiny": 8,
    "size.small": 10,
    "size.normal": 12,
    "size.large": 16,
    "size.huge": 20,
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
