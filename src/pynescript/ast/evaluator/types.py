# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

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
