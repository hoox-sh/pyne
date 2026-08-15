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

"""References — ``textDocument/references`` (find all references).

Public handler: :func:`handle_references`. Same-document AST walk via
:class:`ReferencesFinder`; respects ``context.include_declaration``.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast
from pynescript.langserver.protocol.utils import get_word_at_position


def handle_references(
    params: lsp.ReferenceParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
) -> list[lsp.Location]:
    """Collect references to the symbol under the cursor.

    Args:
        params: Client reference params (position + includeDeclaration).
        source: Document text, or ``None``.
        uri: Document URI for returned locations.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse (skips a redundant re-parse).
            Omit (default ``...``) to parse from *source*.

    Returns:
        List of :class:`~lsprotocol.types.Location` (empty if none / unparsable).
    """
    if not source:
        return []

    position = params.position
    line = position.line
    character = position.character

    # Get the word at cursor
    word, word_start, word_end = get_word_at_position(source, line, character)
    if not word:
        return []

    if tree is ...:
        try:
            from pynescript.ast.helper import parse

            tree = parse(source, filename=uri)
        except Exception:
            return []
    if tree is None:
        return []

    # Find all references
    include_declaration = params.context.include_declaration
    finder = ReferencesFinder(word, uri, include_declaration)
    finder.visit(tree)

    return finder.locations


class ReferencesFinder(NodeVisitor):
    """AST visitor that collects all references to a single name.

    Populates :attr:`locations` for loads, calls, and (optionally) declarations
    matching *target_name*. Same-document only (uses *uri* for each location).
    """

    def __init__(self, target_name: str, uri: str, include_declaration: bool = True) -> None:
        """Search for references to *target_name* in document *uri*."""
        super().__init__()
        self.target_name = target_name
        self.uri = uri
        self.include_declaration = include_declaration
        self.locations: list[lsp.Location] = []
        self.declaration_found = False

    def visit_Script(self, node: ast.Script) -> Any:
        """Visit the root script node."""
        for stmt in node.body:
            self.visit(stmt)

    def visit_Name(self, node: ast.Name) -> Any:
        """Handle variable references."""
        if node.id == self.target_name:
            is_load = node.ctx.__class__.__name__ == "Load"
            is_store = node.ctx.__class__.__name__ == "Store"

            if is_load:
                self._add_location(node.id, getattr(node, "lineno", None) or 1)
            elif is_store and self.include_declaration:
                self._add_location(node.id, getattr(node, "lineno", None) or 1)
                self.declaration_found = True

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Handle function definitions and always walk the body.

        Previously the body was skipped when ``node.name == target_name``, which
        missed recursive calls and same-named free variables inside the function.
        """
        if node.name == self.target_name and self.include_declaration:
            self._add_location(node.name, node.lineno)
            self.declaration_found = True
        for stmt in node.body:
            self.visit(stmt)

    def visit_TypeDef(self, node: ast.TypeDef) -> Any:
        """Handle type definitions and always walk the body (same as FunctionDef)."""
        if node.name == self.target_name and self.include_declaration:
            self._add_location(node.name, node.lineno)
            self.declaration_found = True
        for stmt in node.body:
            self.visit(stmt)

    def visit_EnumDef(self, node: ast.EnumDef) -> Any:
        """Handle enum type / member declarations and walk members."""
        if node.name == self.target_name and self.include_declaration:
            self._add_location(node.name, node.lineno)
            self.declaration_found = True
        member = None
        if node.name and self.target_name.startswith(f"{node.name}."):
            member = self.target_name[len(node.name) + 1 :]
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                if stmt.target.id == self.target_name or (member and stmt.target.id == member):
                    if self.include_declaration:
                        self._add_location(stmt.target.id, stmt.target.lineno)
                        self.declaration_found = True
            self.visit(stmt)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Handle ``Enum.member`` / ``module.member`` attribute uses."""
        value = getattr(node, "value", None)
        attr = getattr(node, "attr", None)
        if isinstance(value, ast.Name) and isinstance(attr, str):
            dotted = f"{value.id}.{attr}"
            if (
                dotted == self.target_name
                or attr == self.target_name
                or value.id == self.target_name
            ):
                self._add_location(dotted, getattr(node, "lineno", None) or 1)
        if value is not None:
            self.visit(value)

    def visit_Call(self, node: ast.Call) -> Any:
        """Handle function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id == self.target_name:
                self._add_location(node.func.id, getattr(node.func, "lineno", None) or 1)
        for arg in node.args:
            self.visit(arg)

    def _add_location(self, name: str, lineno: int | None) -> None:
        """Add a reference location."""
        if not lineno:
            lineno = 1

        location = lsp.Location(
            uri=self.uri,
            range=lsp.Range(
                start=lsp.Position(line=max(0, lineno - 1), character=0),
                end=lsp.Position(line=max(0, lineno - 1), character=0),
            ),
        )
        if location not in self.locations:
            self.locations.append(location)
