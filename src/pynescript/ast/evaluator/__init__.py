# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""AST Node Evaluators - Execute Pine Script AST Nodes.

Evaluators traverse and execute AST nodes to compute values. Composed of
mixin classes organized by AST node category:

- BaseEvaluator: Common visitor infrastructure, context, type registry
- LiteralEvaluator: Constants and literal values
- NameEvaluator: Variable names, attributes, subscript access
- ExpressionEvaluator: Operations (boolean, binary, unary, comparisons, calls)
- StatementEvaluator: Script, assignments, type/function definitions
- BuiltinEvaluator: Built-in functions (plot, ta.sma, etc.)

NodeLiteralEvaluator: Combined evaluator for safe literal evaluation
NodeEvaluator: Full evaluator with all features for complete script execution
"""

from __future__ import annotations

from typing import Any

from .base import BaseEvaluator
from .builtins import BuiltinEvaluator
from .expressions import ExpressionEvaluator
from .literals import LiteralEvaluator
from .names import NameEvaluator
from .statements import StatementEvaluator


class NodeLiteralEvaluator(
    BaseEvaluator,
    LiteralEvaluator,
    ExpressionEvaluator,
    BuiltinEvaluator,
    StatementEvaluator,
    NameEvaluator,
):
    """Safe evaluator for literal expressions and built-in functions.

    Combines all evaluator mixins for flexible AST node evaluation.
    """

    def evaluate_script(self, source: str) -> Any:
        """Parse and evaluate a script string.

        Args:
            source: Pine Script source code

        Returns:
            The result of evaluating the script (value of last expression)
        """
        from pynescript.ast.helper import parse

        tree = parse(source, mode="exec")
        return self.visit(tree)
