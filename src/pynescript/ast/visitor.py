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

"""AST Visitor Pattern Implementation.

Base class for traversing and processing AST nodes using the visitor pattern.
Subclasses implement visit_<NodeType> methods to handle specific node types.

The visitor dispatches to specialized methods based on node class name,
with caching for performance optimization.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pynescript.ast.helper import iter_fields
from pynescript.ast.node import AST


class NodeVisitor:
    """Base visitor for traversing AST nodes.

    Implements the visitor pattern with method dispatch and caching.
    Subclasses should override visit_<NodeType> methods for custom behavior.
    """

    def __init__(self):
        """Initialize the visitor with empty method cache."""
        super().__init__()
        # Type-object keyed cache (faster than class-name strings; matches unparser).
        self._visitor_cache: dict[type, Callable[[AST], Any]] = {}

    def visit(self, node: AST) -> Any:
        """Visit an AST node and dispatch to appropriate handler.

        Looks up and caches visit_<NodeType> methods for performance.
        Cache is keyed by ``type(node)`` to avoid per-call ``__name__`` strings.

        Args:
            node: The AST node to visit

        Returns:
            Result from the visit_<NodeType> method (implementation-dependent)
        """
        cache = self._visitor_cache
        cls = node.__class__
        visitor = cache.get(cls)
        if visitor is None:
            visitor = getattr(self, "visit_" + cls.__name__, self.generic_visit)
            cache[cls] = visitor
        return visitor(node)

    def generic_visit(self, node: AST) -> Any:
        """Called if no specific visit method exists for a node type.

        Default implementation recursively visits all child AST nodes.

        Args:
            node: The AST node being visited
        """
        for _field, value in iter_fields(node):
            # Handle list of nodes
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, AST):
                        self.visit(item)
            # Handle single node
            elif isinstance(value, AST):
                self.visit(value)
