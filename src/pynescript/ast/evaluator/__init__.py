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

from pynescript.ast.evaluator.builtins.strategy import StrategyState
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.helper import parse

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

    def __init__(self, context=None, data_feed=None, data_provider=None):
        super().__init__(context=context, data_feed=data_feed, data_provider=data_provider)
        # Support for strategy events (from plan branch integration)
        if not hasattr(self, "_strategy_state"):
            self._strategy_state = StrategyState()

        if not hasattr(self, "_var_declarations"):
            self._var_declarations = set()

        # Wire realtime/historical data for request.* builtins (v6 live data)
        # (base already injects; these ensure presence even if context pre-populated)
        if data_feed is not None:
            self.context["data_feed"] = data_feed
        if data_provider is not None:
            self.context["data_provider"] = data_provider

    def reset_events(self):
        """Reset events for per-bar testing (strategy events integration)."""
        if hasattr(self, "_strategy_state"):
            self._strategy_state._events = []  # type: ignore[attr-defined]

    def evaluate_script(self, source: str) -> Any:
        """Parse and evaluate a script string.

        Args:
            source: Pine Script source code

        Returns:
            The result of evaluating the script (value of last expression)
        """
        tree = parse(source, mode="exec")
        return self.visit(tree)

    def register_library_source(self, namespace: str, name: str, version: int, source: str) -> None:
        """Register Pine source for ``import namespace/name/version`` resolution."""
        self._library_registry.register_source(namespace, name, version, source)

    def lookup_library(
        self,
        *,
        namespace: str | None = None,
        name: str,
        version: int | None = None,
    ) -> LibraryModule | None:
        """Look up a previously evaluated or registered library."""
        return self._library_registry.lookup(namespace=namespace, name=name, version=version)
