# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
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

"""AST Visitor Pattern Implementation.

Base class for traversing and processing AST nodes using the visitor pattern.
Subclasses implement visit_<NodeType> methods to handle specific node types.

The visitor dispatches to specialized methods based on node class name,
with caching for performance optimization.
"""

from __future__ import annotations

from typing import Any
from typing import Callable

from pynescript.ast.helper import iter_fields
from pynescript.ast.node import AST


class NodeVisitor:
    """Base visitor for traversing AST nodes.

    Implements the visitor pattern with method dispatch and caching.
    Subclasses should override visit_<NodeType> methods for custom behavior.
    """

    def __init__(self):
        """Initialize the visitor with empty method cache."""
        # Optimize: cache visitor methods to avoid repeated getattr calls
        self._visitor_cache: dict[str, Callable[[AST], Any]] = {}

    def visit(self, node: AST) -> Any:
        """Visit an AST node and dispatch to appropriate handler.

        Looks up and caches visit_<NodeType> methods for performance.

        Args:
            node: The AST node to visit

        Returns:
            Result from the visit_<NodeType> method (implementation-dependent)
        """
        node_class = node.__class__.__name__
        # Try cache first
        visitor = self._visitor_cache.get(node_class)
        if visitor is None:
            # Cache miss, look up and cache the method
            method = "visit_" + node_class
            visitor = getattr(self, method, self.generic_visit)
            self._visitor_cache[node_class] = visitor
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
