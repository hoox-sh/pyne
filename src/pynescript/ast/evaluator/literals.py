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

from pynescript.ast import node as ast


class LiteralEvaluator:
    """Evaluates literal value nodes (constants and tuples).

    Handles direct value evaluation for constant expressions in the AST,
    including numeric literals, string literals, boolean literals, and tuple literals.
    """

    def visit_Constant(self, node: ast.Constant):
        """Evaluate a constant literal node.

        Args:
            node: The Constant AST node containing the literal value and optional kind

        Returns:
            The literal value contained in the node

        Raises:
            ValueError: If the constant has an unexpected kind modifier
        """
        # Allow color literals (kind="#")
        if node.kind and node.kind != "#":
            msg = f"unexpected constant kind: {node.kind!s}"
            raise ValueError(msg)
        # Return the literal value directly
        return node.value

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        """Evaluate a tuple literal node.

        Recursively evaluates each element of the tuple.

        Args:
            node: The Tuple AST node containing element nodes

        Returns:
            A list representing the evaluated tuple elements
            (Note: Lists are used instead of tuples for mutability in PineScript context)
        """
        # Evaluate each element in the tuple and return as a list
        # (PineScript uses lists for dynamic sequences)
        return [self.visit(elt) for elt in node.elts]  # type: ignore[attr-defined]
