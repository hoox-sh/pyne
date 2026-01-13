# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from typing import Any
from typing import NoReturn
from typing import Protocol

from pynescript.ast.node import AST


class EvaluatorProtocol(Protocol):
    """Protocol defining the interface for AST node evaluators.

    All evaluator mixins must implement this protocol to provide consistent
    traversal and evaluation of AST nodes. Enables duck-typing of evaluator
    components without requiring explicit inheritance.

    This is a typing helper for static analysis and IDE support.
    """

    # Shared context dict for storing variables, functions, and types
    context: dict[str, Any]

    def visit(self, node: AST) -> Any:  # pragma: no cover - typing helper
        """Visit an AST node and return its evaluated value.

        Dispatches to visit_<NodeType> methods based on node type.
        """
        ...

    def _error(self, msg: str) -> NoReturn:  # pragma: no cover - typing helper
        """Raise a ValueError with the given message.

        Helper for consistent error reporting across evaluators.
        """
        ...

    def _call_builtin(self, name: str, args: list[Any]) -> Any:  # pragma: no cover - typing helper
        """Call a built-in function with the given name and arguments.

        Resolves Pine Script built-in functions (plot, ta.sma, etc.).
        """
        ...

    def _invoke_method(
        self, obj: Any, method_name: str, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:  # pragma: no cover - typing helper
        """Invoke a method on an object with arguments.

        Handles method calls on UDT instances and built-in types.
        """
        ...

    def _handle_udt_new(
        self, type_obj: Any, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:  # pragma: no cover - typing helper
        """Handle instantiation of a user-defined type (UDT).

        Creates ObjectInstance and calls constructor if defined.
        """
        ...
