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

"""AST Statement Collector.

Traverses an AST and collects top-level statements for annotation processing.
Used to pair special comments (//@version, //@description, etc.) with their
corresponding statement nodes.
"""

from __future__ import annotations

from pynescript.ast import node as ast
from pynescript.ast.visitor import NodeVisitor


# Statement types that can have nested scopes
Structure = (
    ast.ForTo,
    ast.ForIn,
    ast.While,
    ast.If,
    ast.Switch,
)


class StatementCollector(NodeVisitor):
    """Collects all statements from an AST for annotation processing.

    Visits an AST tree and yields all top-level statement nodes
    (FunctionDef, TypeDef, EnumDef, Assign, etc.) in order,
    enabling annotation comments to be matched to statements.
    """
    # ruff: noqa: N802

    def visit_Script(self, node):
        """Visit script and yield all statements in order."""
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_FunctionDef(self, node):
        """Visit function definition and yield it plus inner statements."""
        yield node
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_TypeDef(self, node):
        """Visit type definition and yield it plus inner statements."""
        yield node
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_EnumDef(self, node):
        """Visit enum definition and yield it plus inner statements."""
        yield node
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_Assign(self, node):
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_ReAssign(self, node):
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_AugAssign(self, node):
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_Import(self, node):
        yield node

    def visit_Expr(self, node):
        yield node
        if isinstance(node.value, Structure):
            yield from self.visit(node.value)

    def visit_Break(self, node):
        yield node

    def visit_Continue(self, node):
        yield node

    def visit_ForTo(self, node):
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_ForIn(self, node):
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_While(self, node):
        for stmt in node.body:
            yield from self.visit(stmt)

    def visit_If(self, node):
        for stmt in node.body:
            yield from self.visit(stmt)
        for stmt in node.orelse:
            yield from self.visit(stmt)

    def visit_Switch(self, node):
        for case in node.cases:
            yield from self.visit(case)

    def visit_Case(self, node):
        for stmt in node.body:
            yield from self.visit(stmt)
