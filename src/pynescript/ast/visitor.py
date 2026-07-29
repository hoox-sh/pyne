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

"""Visitor base for walking Pine Script ASTs.

Subclass :class:`NodeVisitor` and implement ``visit_<NodeType>`` methods
(e.g. ``visit_Assign``, ``visit_Call``). Dispatch is by concrete class name
with a type-keyed method cache.

Use :class:`~pynescript.ast.transformer.NodeTransformer` when you need to
replace or remove nodes; use :func:`pynescript.ast.helper.walk` for a simple
iterator over the tree without subclassing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pynescript.ast.helper import iter_fields
from pynescript.ast.node import AST


class NodeVisitor:
    """Base class for AST traversal via the visitor pattern.

    Override ``visit_<ClassName>`` for node types of interest. Unhandled
    types fall through to :meth:`generic_visit`, which recursively visits
    all child AST fields. Return values are whatever each ``visit_*``
    method returns (often ``None`` for pure analysis visitors).
    """

    def __init__(self) -> None:
        """Initialize an empty per-type visitor method cache."""
        super().__init__()
        # Type-object keyed cache (faster than class-name strings; matches unparser).
        self._visitor_cache: dict[type, Callable[[AST], Any]] = {}

    def visit(self, node: AST) -> Any:
        """Dispatch to ``visit_<type(node).__name__>`` or :meth:`generic_visit`.

        Returns:
            Whatever the matched handler returns.
        """
        # Local binds shave attribute lookups on the deepest recursive path.
        cache = self._visitor_cache
        cls = type(node)
        visitor = cache.get(cls)
        if visitor is None:
            visitor = getattr(self, "visit_" + cls.__name__, self.generic_visit)
            cache[cls] = visitor
        return visitor(node)

    def generic_visit(self, node: AST) -> Any:
        """Default handler: recursively :meth:`visit` every child AST field.

        Does not return aggregated child results (return value is ``None``).
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
