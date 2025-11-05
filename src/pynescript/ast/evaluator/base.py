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
    def __init__(self, context: dict[str, Any] | None = None):
        self.context = context or {}
        # Optimize: use pre-computed constants
        self.context.update(_MATH_CONSTANTS)
        self.type_registry = TypeRegistry()

    def generic_visit(self, node: ast.AST):
        msg = f"unexpected type of node: {type(node)}"
        raise ValueError(msg)

    def _error(self, msg: str):
        raise ValueError(msg)
