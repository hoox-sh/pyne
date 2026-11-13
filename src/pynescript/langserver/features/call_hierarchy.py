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

"""Call hierarchy — ``textDocument/prepareCallHierarchy`` and ``callHierarchy/*``.

Same-document, scope-aware calls for user-defined functions and methods. The
collector walks the AST once per request, binds each ``Call`` to a user symbol
through :class:`~pynescript.langserver.analysis.SymbolIndex`, and groups call
sites by caller (incoming) or callee (outgoing).

Builtin calls (``ta.sma``, ``strategy.entry``) and UDT constructors are not
part of the hierarchy: they have no Pine source body to navigate to.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast
from pynescript.langserver.analysis import Symbol
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.features._ranges import node_to_range
from pynescript.langserver.protocol.utils import in_comment_or_string


_SCRIPT_NAME = "<script>"
_USER_CALLABLE_KINDS = frozenset({"function", "method"})


@dataclass
class _CallSite:
    """One ``Call`` node bound to a user-defined callee."""

    callee: Symbol
    caller: ast.FunctionDef | None
    range: lsp.Range


@dataclass
class _CallGraph:
    """Calls collected from one document."""

    calls: list[_CallSite] = field(default_factory=list)


class _CallCollector(NodeVisitor):
    """Collect user-function calls and track the enclosing function."""

    def __init__(self, index: SymbolIndex) -> None:
        super().__init__()
        self.graph = _CallGraph()
        self._current: ast.FunctionDef | None = None
        # O(1) callee lookup: the symbol index already bound every Name and
        # member access to a node. Scanning occurrences per Call would make a
        # large script O(calls x occurrences).
        self._occurrence_symbols = {
            id(occurrence.node): occurrence.symbol for occurrence in index.occurrences if occurrence.symbol is not None
        }
        self._member_refs = {id(member.node): member for member in index.member_refs}

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track the enclosing function while walking its body."""
        previous = self._current
        self._current = node
        for param in node.args or []:
            default = getattr(param, "default", None)
            if default is not None:
                self.visit(default)
        for stmt in node.body:
            self.visit(stmt)
        self._current = previous

    def visit_Call(self, node: ast.Call) -> None:
        """Record a call to a user function/method."""
        symbol = self._callee_symbol(node.func)
        if symbol is not None:
            rng = node_to_range(node)
            if rng is not None:
                self.graph.calls.append(_CallSite(symbol, self._current, rng))
        self.generic_visit(node)

    def _callee_symbol(self, func: Any) -> Symbol | None:
        """Resolve a ``Call.func`` node to a user function/method symbol."""
        if isinstance(func, ast.Attribute):
            member = self._member_refs.get(id(func))
            if member is not None and member.kind == "method" and member.symbol is not None:
                return member.symbol
            return None
        symbol = self._occurrence_symbols.get(id(func))
        if symbol is not None and symbol.kind in _USER_CALLABLE_KINDS:
            return symbol
        return None


def handle_prepare_call_hierarchy(
    params: lsp.CallHierarchyPrepareParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> list[lsp.CallHierarchyItem] | None:
    """Return the function at the cursor (definition, call, or enclosing body)."""
    if not source:
        return None
    line = params.position.line
    character = params.position.character
    if in_comment_or_string(source, line, character):
        return None

    index = ensure_symbol_index(source, tree, analysis)
    if index is None:
        return None

    symbol = index.symbol_at(line, character)
    if symbol is not None and symbol.kind in _USER_CALLABLE_KINDS:
        return [_item_for_symbol(index, symbol, uri)]

    scope = index.scope_at(line, character)
    while scope is not None and not isinstance(scope.node, ast.FunctionDef):
        scope = scope.parent
    if scope is None:
        return None
    node = scope.node
    symbol = index.functions.get(node.name or "")
    if symbol is None:
        return None
    return [_item_for_symbol(index, symbol, uri)]


def handle_incoming_calls(
    params: lsp.CallHierarchyIncomingCallsParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> list[lsp.CallHierarchyIncomingCall]:
    """Return callers of the item's function (same document)."""
    if not source:
        return []
    index = ensure_symbol_index(source, tree, analysis)
    if index is None:
        return []
    target = index.functions.get(params.item.name)
    if target is None:
        return []

    graph = _collect(index)
    grouped: dict[int | None, tuple[Any, list[lsp.Range]]] = {}
    for site in graph.calls:
        if site.callee is not target:
            continue
        key = id(site.caller) if site.caller is not None else None
        caller_item = _caller_item(index, site.caller, source, uri)
        if caller_item is None:
            continue
        if key not in grouped:
            grouped[key] = (caller_item, [])
        grouped[key][1].append(site.range)

    return [
        lsp.CallHierarchyIncomingCall(from_=item, from_ranges=_dedupe_ranges(ranges))
        for item, ranges in sorted(grouped.values(), key=lambda pair: _range_key(pair[1][0]))
    ]


def handle_outgoing_calls(
    params: lsp.CallHierarchyOutgoingCallsParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> list[lsp.CallHierarchyOutgoingCall]:
    """Return user functions called by the item's function (same document)."""
    if not source:
        return []
    index = ensure_symbol_index(source, tree, analysis)
    if index is None:
        return []
    target = index.functions.get(params.item.name)
    if target is None:
        return []

    graph = _collect(index)
    grouped: dict[int, tuple[lsp.CallHierarchyItem, list[lsp.Range]]] = {}
    for site in graph.calls:
        if site.caller is not target.node:
            continue
        callee = site.callee
        key = id(callee)
        if key not in grouped:
            grouped[key] = (_item_for_symbol(index, callee, uri), [])
        grouped[key][1].append(site.range)

    return [
        lsp.CallHierarchyOutgoingCall(to=item, from_ranges=_dedupe_ranges(ranges))
        for item, ranges in sorted(grouped.values(), key=lambda pair: _range_key(pair[1][0]))
    ]


def _collect(index: SymbolIndex) -> _CallGraph:
    collector = _CallCollector(index)
    collector.visit(index.tree)
    return collector.graph


def _item_for_symbol(index: SymbolIndex, symbol: Symbol, uri: str) -> lsp.CallHierarchyItem:
    rng = node_to_range(symbol.node)
    if rng is None:
        rng = lsp.Range(start=lsp.Position(0, 0), end=lsp.Position(0, 0))
    selection = _name_range(index, symbol) or rng
    return lsp.CallHierarchyItem(
        name=symbol.name,
        kind=lsp.SymbolKind.Method if symbol.kind == "method" else lsp.SymbolKind.Function,
        uri=uri,
        range=rng,
        selection_range=selection,
        detail=symbol.signature or None,
    )


def _caller_item(
    index: SymbolIndex,
    caller: ast.FunctionDef | None,
    source: str,
    uri: str,
) -> lsp.CallHierarchyItem | None:
    if caller is None:
        return _script_item(source, uri)
    symbol = index.functions.get(caller.name or "")
    if symbol is None:
        return None
    return _item_for_symbol(index, symbol, uri)


def _script_item(source: str, uri: str) -> lsp.CallHierarchyItem:
    lines = source.split("\n") if source else [""]
    end = lsp.Position(line=max(0, len(lines) - 1), character=len(lines[-1]))
    rng = lsp.Range(start=lsp.Position(0, 0), end=end)
    return lsp.CallHierarchyItem(
        name=_SCRIPT_NAME,
        kind=lsp.SymbolKind.Module,
        uri=uri,
        range=rng,
        selection_range=rng,
    )


def _name_range(index: SymbolIndex, symbol: Symbol) -> lsp.Range | None:
    for occurrence in index.occurrences_for(symbol, include_declaration=True):
        if occurrence.node is symbol.name_node:
            return lsp.Range(
                start=lsp.Position(line=occurrence.line, character=occurrence.column),
                end=lsp.Position(line=occurrence.end_line, character=occurrence.end_column),
            )
    return None


def _range_key(rng: lsp.Range) -> tuple[int, int]:
    return (rng.start.line, rng.start.character)


def _dedupe_ranges(ranges: list[lsp.Range]) -> list[lsp.Range]:
    """Deduplicate call-site ranges, keeping source order."""
    seen: set[tuple[int, int, int, int]] = set()
    result: list[lsp.Range] = []
    for rng in sorted(ranges, key=_range_key):
        key = (rng.start.line, rng.start.character, rng.end.line, rng.end.character)
        if key in seen:
            continue
        seen.add(key)
        result.append(rng)
    return result
