# Copyright 2024-2025 jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
