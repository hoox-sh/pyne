# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Definitions feature — textDocument/definition handler.

Provides go-to-definition for Pine Script symbols.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast
from pynescript.langserver.protocol.utils import get_word_at_position


def handle_definition(params: lsp.DefinitionParams, source: str | None, uri: str) -> list[lsp.Location] | None:
    """Handle textDocument/definition request.

    Finds the definition of a symbol at the cursor position.

    Args:
        params: The definition params from the LSP client.
        source: The source text of the document.
        uri: The document URI.

    Returns:
        List of Locations (definitions found) or None.
    """
    if not source:
        return None

    position = params.position
    line = position.line
    character = position.character

    # Get the word at cursor
    word, word_start, word_end = get_word_at_position(source, line, character)
    if not word:
        return None

    # Parse the source to get AST
    try:
        from pynescript.ast.helper import parse

        tree = parse(source, filename=uri)
    except Exception:
        return None

    # Find the definition
    finder = DefinitionFinder(word, uri)
    finder.visit(tree)

    if finder.locations:
        return finder.locations

    return None


class DefinitionFinder(NodeVisitor):
    """Finds definitions of symbols in Pine Script."""

    def __init__(self, target_name: str, uri: str) -> None:
        super().__init__()
        self.target_name = target_name
        self.uri = uri
        self.locations: list[lsp.Location] = []
        self.in_user_function: str | None = None
        self.in_user_type: str | None = None

    def visit_Script(self, node: ast.Script) -> Any:
        """Visit the root script node."""
        for stmt in node.body:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Handle function definitions."""
        old_in_function = self.in_user_function
        if node.name == self.target_name:
            self._add_location(node.name, node.lineno)
        self.in_user_function = node.name
        for stmt in node.body:
            self.visit(stmt)
        self.in_user_function = old_in_function

    def visit_TypeDef(self, node: ast.TypeDef) -> Any:
        """Handle type (UDT) definitions."""
        old_in_type = self.in_user_type
        if node.name == self.target_name:
            self._add_location(node.name, node.lineno)
        self.in_user_type = node.name
        for stmt in node.body:
            self.visit(stmt)
        self.in_user_type = old_in_type

    def visit_Name(self, node: ast.Name) -> Any:
        """Handle variable references."""
        if node.id == self.target_name and node.ctx.__class__.__name__ == "Load":
            if self.in_user_function and self.in_user_function == self.target_name:
                return
            if self.in_user_type and self.in_user_type == self.target_name:
                return

            # Check if this is a definition (Store context)
            if hasattr(node, "_ctx") and node._ctx.__class__.__name__ == "Store":
                self._add_location(node.id, getattr(node, "lineno", None) or 0)
                return

    def visit_Assign(self, node: ast.Assign) -> Any:
        """Handle variable assignments."""
        # Check if the target matches
        if isinstance(node.target, ast.Name):
            if node.target.id == self.target_name:
                self._add_location(node.target.id, node.target.lineno)
                return

        for child in node.target._fields if hasattr(node.target, "_fields") else []:
            child_node = getattr(node.target, child, None)
            if isinstance(child_node, ast.Name) and child_node.id == self.target_name:
                self._add_location(child_node.id, child_node.lineno)

        if node.value is not None:
            self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> Any:
        """Handle function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id == self.target_name:
                # This is a call, not a definition
                return
        for arg in node.args:
            self.visit(arg)

    def _add_location(self, name: str, lineno: int | None) -> None:
        """Add a definition location."""
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
