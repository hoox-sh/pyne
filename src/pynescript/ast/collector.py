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

"""Collect statement nodes for annotation attachment.

Used by :func:`pynescript.ast.helper.parse` (``exec`` mode) to pair
``//@…`` comments with the statements that follow them. Not part of the
package star-export; import as ``from pynescript.ast.collector import
StatementCollector``.
"""

from __future__ import annotations

from collections.abc import Iterator

from pynescript.ast import node as ast
from pynescript.ast.visitor import NodeVisitor


# Statement types that can have nested scopes
Structure = (
    ast.ForTo,
    ast.ForIn,
    ast.While,
    ast.If,
    ast.Switch,
    ast.Once,
)


class StatementCollector(NodeVisitor):
    """Yield statement nodes in source order for annotation processing.

    Call :meth:`~pynescript.ast.visitor.NodeVisitor.visit` on a
    :class:`~pynescript.ast.node.Script` (or nested body). Yields definitions
    (``FunctionDef``, ``TypeDef``, ``EnumDef``), assignments, imports, bare
    expressions, ``Break``/``Continue``, and descends into control structures
    so nested statements are included.

    Return type of each ``visit_*`` is an iterator of AST nodes (generator).
    """

    # ruff: noqa: N802

    def visit_Script(self, node: ast.Script) -> Iterator[ast.AST]:
        """Yield every statement under the script body."""
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Iterator[ast.AST]:
        """Yield the function, then statements in its body."""
        yield node
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_TypeDef(self, node: ast.TypeDef) -> Iterator[ast.AST]:
        """Yield the type def, then statements in its body."""
        yield node
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_EnumDef(self, node: ast.EnumDef) -> Iterator[ast.AST]:
        """Yield the enum def, then members/statements in its body."""
        yield node
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_Assign(self, node: ast.Assign) -> Iterator[ast.AST]:
        """Yield the assign; descend if the value is a control structure."""
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_ReAssign(self, node: ast.ReAssign) -> Iterator[ast.AST]:
        """Yield the reassignment; descend into structured values."""
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> Iterator[ast.AST]:
        """Yield the augmented assign; descend into structured values."""
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_Import(self, node: ast.Import) -> Iterator[ast.AST]:
        """Yield the import statement."""
        yield node

    def visit_Expr(self, node: ast.Expr) -> Iterator[ast.AST]:
        """Yield the expression statement; descend into structured values."""
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_Break(self, node: ast.Break) -> Iterator[ast.AST]:
        """Yield ``break``."""
        yield node

    def visit_Continue(self, node: ast.Continue) -> Iterator[ast.AST]:
        """Yield ``continue``."""
        yield node

    def visit_ForTo(self, node: ast.ForTo) -> Iterator[ast.AST]:
        """Yield statements inside a for-to loop body."""
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_ForIn(self, node: ast.ForIn) -> Iterator[ast.AST]:
        """Yield statements inside a for-in loop body."""
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_While(self, node: ast.While) -> Iterator[ast.AST]:
        """Yield statements inside a while body."""
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_If(self, node: ast.If) -> Iterator[ast.AST]:
        """Yield statements in then and else branches."""
        for stmt in node.body:
            yield from self.visit(stmt)
        for stmt in node.orelse:
            yield from self.visit(stmt)

    def visit_Switch(self, node: ast.Switch) -> Iterator[ast.AST]:
        """Yield statements from each switch case."""
        for case in node.cases:
            yield from self.visit(case)

    def visit_Once(self, node: ast.Once) -> Iterator[ast.AST]:
        """Yield statements inside a ``once`` body."""
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_Case(self, node: ast.Case) -> Iterator[ast.AST]:
        """Yield statements in a switch case body."""
        for stmt in node.body:
            yield from self.visit(stmt)
