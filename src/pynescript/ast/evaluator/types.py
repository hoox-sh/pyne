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

"""Typing protocol for evaluator mixins (static analysis only).

Mixins such as :class:`~.expressions.ExpressionEvaluator` and
:class:`~.names.NameEvaluator` annotate ``self`` as
:class:`EvaluatorProtocol` so they can call ``visit``, ``_call_builtin``,
and friends without importing the concrete
:class:`~pynescript.ast.evaluator.NodeLiteralEvaluator` (avoids cycles).
Runtime composition is pure multiple inheritance — this protocol is not
enforced at runtime.
"""

from __future__ import annotations

from typing import Any
from typing import NoReturn
from typing import Protocol

from pynescript.ast.node import AST


class EvaluatorProtocol(Protocol):
    """Structural type for composed evaluator instances.

    Documents the methods mixins expect from
    :class:`~.base.BaseEvaluator` + :class:`~.builtins.BuiltinEvaluator` +
    expression helpers. Used only for type checking / IDEs.
    """

    # Shared context dict for storing variables, functions, and types
    context: dict[str, Any]

    def visit(self, node: AST) -> Any:  # pragma: no cover - typing helper
        """Dispatch to ``visit_<NodeType>`` and return the evaluated value."""
        ...

    def _error(self, msg: str) -> NoReturn:  # pragma: no cover - typing helper
        """Raise ``ValueError`` with a consistent message format."""
        ...

    def _call_builtin(self, name: str, args: list[Any]) -> Any:  # pragma: no cover - typing helper
        """Invoke a registered Pine builtin (``plot``, ``ta.sma``, …)."""
        ...

    def _invoke_method(
        self, obj: Any, method_name: str, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:  # pragma: no cover - typing helper
        """Run a UDT method with in-place context param rebind."""
        ...

    def _handle_udt_new(
        self, type_obj: Any, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:  # pragma: no cover - typing helper
        """Construct a UDT instance (``Type.new(...)``)."""
        ...
