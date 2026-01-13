# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
