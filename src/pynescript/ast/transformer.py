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

"""AST Transformer for In-Place Tree Modification.

Extends the visitor pattern to enable transforming (modifying) AST nodes in place.
Subclasses implement visit_<NodeType> methods that return modified nodes.

Transformation rules:
- Return None to remove a node
- Return an AST node to replace the node
- Return a list to replace a single node with multiple nodes
- Return the same node or leave unchanged to keep as-is
"""

from __future__ import annotations

from pynescript.ast.helper import iter_fields
from pynescript.ast.node import AST
from pynescript.ast.visitor import NodeVisitor


class NodeTransformer(NodeVisitor):
    """Transforms an AST in place using the visitor pattern.

    Enables rewriting AST structures by visiting nodes and optionally
    replacing them. More powerful than visitors for AST optimization,
    simplification, and normalization.

    Subclasses should override visit_<NodeType> methods to return
    modified nodes (or None to remove).
    """

    def generic_visit(self, node: AST):
        """Visit and potentially transform all child nodes in place.

        Args:
            node: The parent AST node

        Returns:
            The modified node with transformed children
        """
        for field, old_value in iter_fields(node):
            # Handle list of nodes (e.g., function body statements)
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    # Visit child AST nodes
                    if isinstance(value, AST):
                        value = self.visit(value)  # noqa: PLW2901
                        if value is None:
                            # Remove node (filtered out)
                            continue
                        elif not isinstance(value, AST):
                            # Expand list (one node replaced with multiple)
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                # Replace the original list in-place
                old_value[:] = new_values
            # Handle single node child
            elif isinstance(old_value, AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    # Remove the child node
                    delattr(node, field)
                else:
                    # Replace the child node
                    setattr(node, field, new_node)
        return node
