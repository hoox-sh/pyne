# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""References feature — textDocument/references handler.

Provides find-references for Pine Script symbols.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast
from pynescript.langserver.protocol.utils import get_word_at_position


def handle_references(params: lsp.ReferenceParams, source: str | None, uri: str) -> list[lsp.Location]:
    """Handle textDocument/references request.

    Finds all references to a symbol at the cursor position.

    Args:
        params: The references params from the LSP client.
        source: The source text of the document.
        uri: The document URI.

    Returns:
        List of Locations (all references found).
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

    # Parse the source to get AST
    try:
        from pynescript.ast.helper import parse

        tree = parse(source, filename=uri)
    except Exception:
        return []

    # Find all references
    include_declaration = params.context.include_declaration
    finder = ReferencesFinder(word, uri, include_declaration)
    finder.visit(tree)

    return finder.locations


class ReferencesFinder(NodeVisitor):
    """Finds all references to symbols in Pine Script."""

    def __init__(self, target_name: str, uri: str, include_declaration: bool = True) -> None:
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
        """Handle function definitions."""
        # Check if this is the target function
        if node.name == self.target_name:
            if self.include_declaration:
                self._add_location(node.name, node.lineno)
                self.declaration_found = True
        else:
            # Check function body for references
            for stmt in node.body:
                self.visit(stmt)

    def visit_TypeDef(self, node: ast.TypeDef) -> Any:
        """Handle type definitions."""
        # Check if this is the target type
        if node.name == self.target_name:
            if self.include_declaration:
                self._add_location(node.name, node.lineno)
                self.declaration_found = True
        else:
            # Check type body for references
            for stmt in node.body:
                self.visit(stmt)

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
