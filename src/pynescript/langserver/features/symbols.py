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

"""Symbols — ``textDocument/documentSymbol`` (document outline).

Public handler: :func:`handle_document_symbols`. Hierarchical outline via
:class:`DocumentSymbolCollector` (functions, types, assignments). Workspace-wide
search is handled separately in :mod:`pynescript.langserver.server`
(``workspace/symbol``).
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast

from ._ranges import node_to_range


def handle_document_symbols(
    params: lsp.DocumentSymbolParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
) -> list[lsp.DocumentSymbol]:
    """Build a hierarchical symbol tree for the document outline view.

    Args:
        params: Client document-symbol params.
        source: Document text, or ``None``.
        uri: Document URI (used for context; symbols are position-based).
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse (skips a redundant re-parse).
            Omit (default ``...``) to parse from *source*.

    Returns:
        Top-level :class:`~lsprotocol.types.DocumentSymbol` list (possibly empty).
    """
    if tree is ...:
        if not source:
            return []
        try:
            from pynescript.ast.helper import parse

            tree = parse(source, filename=uri)
        except Exception:
            return []
    if tree is None:
        return []

    collector = DocumentSymbolCollector(uri, source or "")
    collector.visit(tree)

    return collector.symbols


class DocumentSymbolCollector(NodeVisitor):
    """AST visitor that builds a hierarchical document outline.

    Collects functions, user-defined types (with fields), enums, and assignments into
    :attr:`symbols`. Nested assignments under a function become children of that
    function symbol.
    """

    def __init__(self, uri: str, source: str = "") -> None:
        """Collect outline symbols for document *uri*."""
        super().__init__()
        self.uri = uri
        self.source = source
        self._lines = source.split("\n") if source else []
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
        """Handle function and method definitions."""
        # Flush previous function
        self._flush_function()

        # Create function symbol
        func_symbol = lsp.DocumentSymbol(
            name=node.name or "<anonymous>",
            kind=lsp.SymbolKind.Method if node.method else lsp.SymbolKind.Function,
            range=self._node_to_range(node),
            selection_range=self._name_to_range(node, getattr(node, "name", None)),
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
            selection_range=self._name_to_range(node, getattr(node, "name", None)),
            children=[],
            detail="User-defined type",
        )

        for stmt in node.body:
            self.visit_type_member(stmt, type_symbol)

        self.symbols.append(type_symbol)

    def visit_EnumDef(self, node: ast.EnumDef) -> Any:
        """Handle enum definitions (members must not appear as top-level vars)."""
        enum_symbol = lsp.DocumentSymbol(
            name=node.name or "<anonymous>",
            kind=lsp.SymbolKind.Enum,
            range=self._node_to_range(node),
            selection_range=self._name_to_range(node, getattr(node, "name", None)),
            children=[],
            detail="User-defined enum",
        )
        children: list[lsp.DocumentSymbol] = []
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                children.append(
                    lsp.DocumentSymbol(
                        name=stmt.target.id,
                        kind=lsp.SymbolKind.EnumMember,
                        range=self._node_to_range(stmt),
                        selection_range=self._name_to_range(stmt.target),
                        children=[],
                        detail="Enum member",
                    )
                )
        enum_symbol.children = children
        self.symbols.append(enum_symbol)

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
                    parent.children = [*list(parent.children), field]
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
                            parent.children = [*list(parent.children), field]

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

    def visit_Import(self, node: ast.Import) -> Any:
        """Add library imports to the outline."""
        alias = node.alias or node.name or ""
        if not alias:
            return
        self.symbols.append(
            lsp.DocumentSymbol(
                name=alias,
                kind=lsp.SymbolKind.Module,
                range=self._node_to_range(node),
                selection_range=self._name_to_range(node, alias),
                children=[],
                detail=f"import {node.namespace}/{node.name}/{node.version}",
            )
        )

    def _flush_function(self) -> None:
        """Flush the current function's symbols.

        Clears ``_current_function`` so a subsequent flush (e.g. end of
        :meth:`visit_Script`) does not re-append the same function, and so
        top-level assignments after a function are not nested under it.
        """
        if self._current_function:
            self._current_function.children = self._function_vars
            self.symbols.append(self._current_function)
            self._function_vars = []
            self._current_function = None

    def _node_to_range(self, node: Any) -> lsp.Range:
        """Convert AST node to a Range covering its full source span.

        The end position must not precede the ``selection_range`` produced by
        :meth:`_name_to_range`; clients (VS Code) reject symbols whose
        selection range is not contained in the full range.
        """
        span = node_to_range(node)
        if span is not None:
            return span
        # Defensive fallback for nodes lacking span info: keep the range
        # wide enough to contain any name-based selection range.
        return lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=0, character=1),
        )

    def _name_to_range(self, node: Any, name: str | None = None) -> lsp.Range:
        """Convert a declaration name to a Range (works for Import/FunctionDef)."""
        lineno = getattr(node, "lineno", 1) or 1
        col_offset = getattr(node, "col_offset", 0) or 0
        token = name or getattr(node, "id", None) or getattr(node, "name", None) or "x"
        line_text = self._source_line(lineno)
        if isinstance(node, ast.Name):
            if line_text[col_offset : col_offset + len(token)] == token:
                return lsp.Range(
                    start=lsp.Position(line=max(0, lineno - 1), character=col_offset),
                    end=lsp.Position(line=max(0, lineno - 1), character=col_offset + len(token)),
                )
        if isinstance(node, (ast.FunctionDef, ast.TypeDef, ast.EnumDef, ast.Import)):
            if isinstance(node, ast.FunctionDef):
                paren = line_text.find("(", col_offset)
                end = paren if paren >= 0 else len(line_text)
                idx = line_text.rfind(token, col_offset, end)
            elif isinstance(node, ast.Import):
                idx = line_text.rfind(token, col_offset)
            else:
                idx = line_text.find(token, col_offset)
            if idx >= 0:
                col_offset = idx
        end_col = col_offset + len(token)
        return lsp.Range(
            start=lsp.Position(line=max(0, lineno - 1), character=col_offset),
            end=lsp.Position(line=max(0, lineno - 1), character=end_col),
        )

    def _source_line(self, lineno: int) -> str:
        index = max(0, int(lineno or 1) - 1)
        return self._lines[index] if 0 <= index < len(self._lines) else ""


def collect_workspace_symbols(doc: Any, uri: str) -> list[lsp.SymbolInformation]:
    """Flatten a document outline into ``workspace/symbol`` entries."""
    tree = getattr(doc, "valid_ast", None) or getattr(doc, "ast", None)
    source = getattr(doc, "source", "") or ""
    if tree is None:
        return []
    collector = DocumentSymbolCollector(uri, source)
    collector.visit(tree)
    results: list[lsp.SymbolInformation] = []

    def add(symbol: lsp.DocumentSymbol, container: str | None = None) -> None:
        results.append(
            lsp.SymbolInformation(
                name=symbol.name,
                kind=symbol.kind,
                location=lsp.Location(uri=uri, range=symbol.range),
                container_name=container,
            )
        )
        for child in symbol.children or []:
            add(child, symbol.name)

    for symbol in collector.symbols:
        add(symbol)
    return results


def _get_function_signature(node: ast.FunctionDef) -> str:
    """Get a signature string for a function or method."""
    if not node.name:
        return "function"
    params = []
    for param in node.args or []:
        name = getattr(param, "name", None)
        if name:
            params.append(str(name))
    prefix = "method " if node.method else "function "
    result = f"{prefix}{node.name}({', '.join(params)})"
    returns = _type_name(node.returns)
    if returns:
        result += f" → {returns}"
    return result


def _type_name(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id or ""
    if isinstance(node, ast.Attribute):
        base = _type_name(node.value)
        return f"{base}.{node.attr}" if base and node.attr else (node.attr or "")
    if isinstance(node, ast.Qualify):
        inner = _type_name(node.value)
        qualifier = type(node.qualifier).__name__.lower() if node.qualifier is not None else ""
        return f"{qualifier} {inner}".strip() if inner else qualifier
    if isinstance(node, ast.Specialize):
        base = _type_name(node.value)
        args = ", ".join(filter(None, (_type_name(arg) for arg in (node.args or []))))
        return f"{base}<{args}>" if base and args else base
    return ""


def _get_assign_detail(node: ast.Assign) -> str:
    """Get a detail string for an assignment (type annotation or call)."""
    type_name = _type_name(node.type)
    if type_name:
        return type_name
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
