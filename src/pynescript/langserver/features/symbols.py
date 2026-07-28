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

"""Symbols feature — textDocument/documentSymbol handler.

Provides document outline (symbols tree) for Pine Script.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast


def handle_document_symbols(params: lsp.DocumentSymbolParams, source: str | None, uri: str) -> list[lsp.DocumentSymbol]:
    """Handle textDocument/documentSymbol request.

    Builds a hierarchical symbol tree for the document outline.

    Args:
        params: The document symbol params.
        source: The source text of the document.
        uri: The document URI.

    Returns:
        List of top-level document symbols.
    """
    if not source:
        return []

    try:
        from pynescript.ast.helper import parse

        tree = parse(source, filename=uri)
    except Exception:
        return []

    collector = DocumentSymbolCollector(uri)
    collector.visit(tree)

    return collector.symbols


class DocumentSymbolCollector(NodeVisitor):
    """Collects document symbols for outline view."""

    def __init__(self, uri: str) -> None:
        super().__init__()
        self.uri = uri
        self.symbols: list[lsp.DocumentSymbol] = []
        self._current_function: lsp.DocumentSymbol | None = None
        self._function_vars: list[lsp.DocumentSymbol] = []

    def visit_Script(self, node: ast.Script) -> Any:
        """Visit the root script node."""
        for stmt in node.body:
            self.visit(stmt)

        # Flush any remaining function symbols
        self._flush_function()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        """Handle function definitions."""
        # Flush previous function
        self._flush_function()

        # Create function symbol
        func_symbol = lsp.DocumentSymbol(
            name=node.name or "<anonymous>",
            kind=lsp.SymbolKind.Function,
            range=self._node_to_range(node),
            selection_range=self._name_to_range(node),
            children=[],
            detail=_get_function_signature(node),
        )

        self._current_function = func_symbol

        for stmt in node.body:
            self.visit(stmt)

        # Flush the function with its children
        self._flush_function()

    def visit_TypeDef(self, node: ast.TypeDef) -> Any:
        """Handle type (UDT) definitions."""
        # Create type symbol
        type_symbol = lsp.DocumentSymbol(
            name=node.name or "<anonymous>",
            kind=lsp.SymbolKind.Class,
            range=self._node_to_range(node),
            selection_range=self._name_to_range(node),
            children=[],
            detail="User-defined type",
        )

        for stmt in node.body:
            self.visit_type_member(stmt, type_symbol)

        self.symbols.append(type_symbol)

    def visit_type_member(self, node: Any, parent: lsp.DocumentSymbol) -> None:
        """Visit type members."""
        if isinstance(node, ast.Assign):
            if isinstance(node.target, ast.Name):
                field = lsp.DocumentSymbol(
                    name=node.target.id,
                    kind=lsp.SymbolKind.Field,
                    range=self._node_to_range(node),
                    selection_range=self._name_to_range(node.target),
                    children=[],
                    detail="Field",
                )
                if parent.children is None:
                    parent.children = [field]
                else:
                    parent.children = list(parent.children) + [field]
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        field = lsp.DocumentSymbol(
                            name=elt.id,
                            kind=lsp.SymbolKind.Field,
                            range=self._node_to_range(node),
                            selection_range=self._name_to_range(elt),
                            children=[],
                            detail="Field",
                        )
                        if parent.children is None:
                            parent.children = [field]
                        else:
                            parent.children = list(parent.children) + [field]

    def visit_Assign(self, node: ast.Assign) -> Any:
        """Handle variable assignments."""
        if isinstance(node.target, ast.Name):
            var_symbol = lsp.DocumentSymbol(
                name=node.target.id,
                kind=lsp.SymbolKind.Variable,
                range=self._node_to_range(node),
                selection_range=self._name_to_range(node.target),
                children=[],
                detail=_get_assign_detail(node),
            )

            if self._current_function:
                self._function_vars.append(var_symbol)
            else:
                self.symbols.append(var_symbol)

        elif isinstance(node.target, ast.Tuple):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    var_symbol = lsp.DocumentSymbol(
                        name=elt.id,
                        kind=lsp.SymbolKind.Variable,
                        range=self._node_to_range(node),
                        selection_range=self._name_to_range(elt),
                        children=[],
                    )
                    if self._current_function:
                        self._function_vars.append(var_symbol)
                    else:
                        self.symbols.append(var_symbol)

        if node.value is not None:
            self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> Any:
        """Handle function calls (don't add to outline)."""
        for arg in node.args:
            self.visit(arg)

    def _flush_function(self) -> None:
        """Flush the current function's symbols."""
        if self._current_function:
            self._current_function.children = self._function_vars
            self.symbols.append(self._current_function)
            self._function_vars = []

    def _node_to_range(self, node: Any) -> lsp.Range:
        """Convert AST node to Range."""
        lineno = getattr(node, "lineno", 1) or 1
        end_lineno = getattr(node, "end_lineno", lineno) or lineno
        return lsp.Range(
            start=lsp.Position(line=max(0, lineno - 1), character=0),
            end=lsp.Position(line=max(0, end_lineno - 1), character=0),
        )

    def _name_to_range(self, node: Any) -> lsp.Range:
        """Convert name node to Range."""
        lineno = getattr(node, "lineno", 1) or 1
        col_offset = getattr(node, "col_offset", 0) or 0
        end_col = col_offset + len(getattr(node, "id", "x") or "x")
        return lsp.Range(
            start=lsp.Position(line=max(0, lineno - 1), character=col_offset),
            end=lsp.Position(line=max(0, lineno - 1), character=end_col),
        )


def _get_function_signature(node: ast.FunctionDef) -> str:
    """Get a signature string for a function."""
    if not node.name:
        return "function"
    return f"function {node.name}()"


def _get_assign_detail(node: ast.Assign) -> str:
    """Get a detail string for an assignment."""
    if isinstance(node.value, ast.Call):
        if isinstance(node.value.func, ast.Attribute):
            module = node.value.func.value
            attr = node.value.func.attr
            if isinstance(module, ast.Name):
                return f"{module.id}.{attr}"
            return attr
        elif isinstance(node.value.func, ast.Name):
            return node.value.func.id
    return ""
