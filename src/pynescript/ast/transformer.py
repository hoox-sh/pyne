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

"""In-place AST rewriting via the visitor pattern.

:class:`NodeTransformer` extends :class:`~pynescript.ast.visitor.NodeVisitor`.
Override ``visit_<NodeType>`` and return a replacement according to:

* ``None`` — remove the node (from a list field, or delete a scalar field)
* an :class:`~pynescript.ast.node.AST` — replace the visited node
* a non-AST iterable (e.g. ``list``) — splice in place of one list item
* the same node (or omit override) — leave unchanged

Child transformation is applied bottom-up via :meth:`NodeTransformer.generic_visit`.
"""

from __future__ import annotations

from pynescript.ast.helper import iter_fields
from pynescript.ast.node import AST
from pynescript.ast.visitor import NodeVisitor


class NodeTransformer(NodeVisitor):
    """Rewrite an AST by visiting nodes and returning replacements.

    Mutates list fields in place and replaces/deletes scalar child fields
    on the parent. Prefer this over :class:`~pynescript.ast.visitor.NodeVisitor`
    for optimization, desugaring, or normalization passes.
    """

    def generic_visit(self, node: AST) -> AST:
        """Transform all children of *node*, then return *node*.

        List fields are rewritten in place; scalar AST fields are replaced
        or deleted according to child ``visit_*`` return values.
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
