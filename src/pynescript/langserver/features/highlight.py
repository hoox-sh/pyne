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

"""Document highlight — ``textDocument/documentHighlight``.

Public handler: :func:`handle_document_highlight`. Collects same-document
occurrences of the identifier under the cursor (character-precise ranges)
via an AST walk. Shared with :mod:`.rename`.
"""

from __future__ import annotations

import re

from typing import Any
from typing import NamedTuple

from lsprotocol import types as lsp

from pynescript.ast import NodeVisitor
from pynescript.ast import node as ast
from pynescript.ast.helper import parse
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.protocol.utils import get_identifier_segment_at_position
from pynescript.langserver.protocol.utils import in_comment_or_string
from pynescript.langserver.providers.completion_items import PINE_KEYWORDS


_IDENT_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PINE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

KEYWORDS: frozenset[str] = frozenset(name for name, _brief in PINE_KEYWORDS)

# Builtin namespaces (and a few top-level drawing/plot builtins) that must not
# be renamed. Matches the wave-5 list plus extra library namespaces.
BUILTIN_NAMESPACES: frozenset[str] = frozenset(
    {
        "ta",
        "strategy",
        "math",
        "input",
        "request",
        "str",
        "array",
        "matrix",
        "map",
        "barstate",
        "syminfo",
        "timeframe",
        "ticker",
        "color",
        "line",
        "label",
        "box",
        "table",
        "polyline",
        "alert",
        "plot",
        "hline",
        "log",
        "chart",
        "runtime",
        "session",
        "time",
    }
)


class IdentHit(NamedTuple):
    """One same-document occurrence of an identifier."""

    range: lsp.Range
    write: bool


def cursor_ident(source: str, line: int, character: int) -> tuple[str, int, int, str]:
    """Return ``(segment, start, end, full_word)`` at *line*/*character*."""
    return get_identifier_segment_at_position(source, line, character)


def is_valid_pine_ident(name: str) -> bool:
    """True when *name* is a single Pine identifier token."""
    return bool(name) and _PINE_IDENT.fullmatch(name) is not None


def is_renamable_ident(segment: str, full_word: str = "") -> bool:
    """False for empty/invalid tokens, keywords, and builtin namespaces."""
    if not is_valid_pine_ident(segment):
        return False
    if segment in KEYWORDS or segment in BUILTIN_NAMESPACES:
        return False
    word = full_word or segment
    head = word.split(".", 1)[0]
    if head in BUILTIN_NAMESPACES:
        return False
    return True


def resolve_tree(source: str | None, tree: Any | None) -> Any | None:
    """Return *tree*, or parse *source* when *tree* is the omit-sentinel."""
    if tree is not ...:
        return tree
    if not source:
        return None
    try:
        return parse(source)
    except Exception:
        return None


def collect_ident_hits(
    source: str,
    tree: Any,
    name: str,
    *,
    include_builtin_attrs: bool = True,
) -> list[IdentHit]:
    """Collect character-precise occurrences of *name* in *tree*."""
    if not name or tree is None:
        return []
    finder = _IdentFinder(source, name, include_builtin_attrs=include_builtin_attrs)
    finder.visit(tree)
    hits = list(finder.hits.values())
    hits.sort(key=lambda h: (h.range.start.line, h.range.start.character))
    return hits


def handle_document_highlight(
    params: lsp.DocumentHighlightParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> list[lsp.DocumentHighlight]:
    """Highlight same-document occurrences of the ident under the cursor.

    Scope-aware when an analysis index is available: shadowed locals and
    unrelated same-named fields are not highlighted.

    Args:
        params: Client highlight params (position).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source*.
        analysis: Pre-built symbol index for *tree*.

    Returns:
        List of :class:`~lsprotocol.types.DocumentHighlight` (empty if none).
    """
    if not source:
        return []
    line = params.position.line
    character = params.position.character
    if in_comment_or_string(source, line, character):
        return []

    index = ensure_symbol_index(source, tree, analysis)
    if index is not None:
        symbol = index.symbol_at(line, character)
        if symbol is not None:
            occurrences = index.occurrences_for(symbol, include_declaration=True)
            return [
                lsp.DocumentHighlight(
                    range=lsp.Range(
                        start=lsp.Position(line=occ.line, character=occ.column),
                        end=lsp.Position(line=occ.end_line, character=occ.end_column),
                    ),
                    kind=lsp.DocumentHighlightKind.Write if occ.write else lsp.DocumentHighlightKind.Read,
                )
                for occ in occurrences
            ]
        member = index.member_at(line, character)
        if member is not None and member.builtin_name:
            # Highlight other uses of the same builtin member (e.g. ta.sma).
            return [
                lsp.DocumentHighlight(
                    range=lsp.Range(
                        start=lsp.Position(line=other.line, character=other.column),
                        end=lsp.Position(line=other.end_line, character=other.end_column),
                    ),
                    kind=lsp.DocumentHighlightKind.Read,
                )
                for other in index.member_refs
                if other.builtin_name == member.builtin_name
            ]

    segment, _start, _end, _full = cursor_ident(source, line, character)
    if not segment:
        return []

    resolved = resolve_tree(source, tree)
    if resolved is None:
        return []

    hits = collect_ident_hits(source, resolved, segment, include_builtin_attrs=True)
    highlights: list[lsp.DocumentHighlight] = []
    for hit in hits:
        kind = lsp.DocumentHighlightKind.Write if hit.write else lsp.DocumentHighlightKind.Read
        highlights.append(lsp.DocumentHighlight(range=hit.range, kind=kind))
    return highlights


class _IdentFinder(NodeVisitor):
    """AST visitor that records every occurrence of *target* with a Range."""

    def __init__(self, source: str, target: str, *, include_builtin_attrs: bool) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.include_builtin_attrs = include_builtin_attrs
        self.hits: dict[tuple[int, int, int], IdentHit] = {}

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id == self.target:
            ctx_name = node.ctx.__class__.__name__ if node.ctx is not None else ""
            self._add_node(node, node.id, write=ctx_name == "Store")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if node.name == self.target:
            self._add_node(node, node.name, write=True)
        self.generic_visit(node)

    def visit_TypeDef(self, node: ast.TypeDef) -> Any:
        if node.name == self.target:
            self._add_node(node, node.name, write=True)
        self.generic_visit(node)

    def visit_EnumDef(self, node: ast.EnumDef) -> Any:
        if node.name == self.target:
            self._add_node(node, node.name, write=True)
        self.generic_visit(node)

    def visit_Param(self, node: ast.Param) -> Any:
        if node.name == self.target:
            self._add_node(node, node.name, write=True)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        if node.alias == self.target:
            self._add_node(node, node.alias, write=True)
        self.generic_visit(node)

    def visit_Arg(self, node: ast.Arg) -> Any:
        if node.name == self.target:
            self._add_node(node, node.name, write=False)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr == self.target and (self.include_builtin_attrs or not _is_builtin_attr(node)):
            end_col = getattr(node, "end_col_offset", None)
            col: int | None
            if isinstance(end_col, int) and end_col >= len(node.attr):
                col = end_col - len(node.attr)
            else:
                col = getattr(node, "col_offset", None)
            self._add_at(getattr(node, "lineno", None), col, node.attr, write=False)
        self.generic_visit(node)

    def _add_node(self, node: Any, name: str, *, write: bool) -> None:
        self._add_at(getattr(node, "lineno", None), getattr(node, "col_offset", None), name, write=write)

    def _add_at(self, lineno: int | None, col: int | None, name: str, *, write: bool) -> None:
        rng = _range_for_ident(self.source, lineno, col, name)
        if rng is None:
            return
        key = (rng.start.line, rng.start.character, rng.end.character)
        existing = self.hits.get(key)
        if existing is None or (write and not existing.write):
            self.hits[key] = IdentHit(range=rng, write=write)


def _is_builtin_attr(node: ast.Attribute) -> bool:
    value = getattr(node, "value", None)
    return isinstance(value, ast.Name) and value.id in BUILTIN_NAMESPACES


def _bounded(line: str, start: int, end: int) -> bool:
    before = line[start - 1] if start > 0 else ""
    after = line[end] if end < len(line) else ""
    return not _is_ident_char(before) and not _is_ident_char(after)


def _is_ident_char(ch: str) -> bool:
    return bool(ch) and (ch.isalnum() or ch == "_")


def _make_range(line: int, start: int, end: int) -> lsp.Range:
    return lsp.Range(
        start=lsp.Position(line=line, character=start),
        end=lsp.Position(line=line, character=end),
    )


def _range_for_ident(source: str, lineno: int | None, col: int | None, name: str) -> lsp.Range | None:
    """Map *name* on *lineno* to a Range, preferring *col* when it matches."""
    if not name:
        return None
    lines = source.split("\n")
    line_idx = max(0, (lineno or 1) - 1)
    if line_idx >= len(lines):
        return None
    line = lines[line_idx]
    start_at = 0 if col is None else max(0, col)
    end_at = start_at + len(name)
    if end_at <= len(line) and line[start_at:end_at] == name and _bounded(line, start_at, end_at):
        return _make_range(line_idx, start_at, end_at)
    fallback: lsp.Range | None = None
    for match in _IDENT_TOKEN.finditer(line):
        if match.group() != name:
            continue
        rng = _make_range(line_idx, match.start(), match.end())
        if match.start() >= start_at:
            return rng
        if fallback is None:
            fallback = rng
    return fallback
