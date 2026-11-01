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

"""Rename — ``textDocument/prepareRename`` and ``textDocument/rename``.

Public handlers: :func:`handle_prepare_rename`, :func:`handle_rename`.
Rename updates the ident in every currently open workspace document.
``prepareRename`` stays the cursor document's ident range. Pine keywords
and builtin namespaces are not renamed. New names must be a single valid
Pine identifier token. Documents that are not open are not edited.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.langserver.analysis import Symbol
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.features.highlight import cursor_ident
from pynescript.langserver.features.highlight import is_renamable_ident
from pynescript.langserver.features.highlight import is_valid_pine_ident
from pynescript.langserver.protocol.utils import in_comment_or_string
from pynescript.langserver.workspace import Workspace


def handle_prepare_rename(
    params: lsp.PrepareRenameParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> lsp.Range | None:
    """Return the exact range of the symbol under the cursor, or ``None``.

    Keywords, builtin namespaces (``ta``, ``strategy``, …), members of those
    namespaces (``ta.sma``), and unresolved identifiers yield ``None``.
    """
    if not source:
        return None
    line = params.position.line
    character = params.position.character
    if in_comment_or_string(source, line, character):
        return None
    segment, _start, _end, full = cursor_ident(source, line, character)
    if not is_renamable_ident(segment, full):
        return None

    index = ensure_symbol_index(source, tree, analysis)
    if index is None:
        return None
    occurrence = index.occurrence_at(line, character)
    if occurrence is None or occurrence.symbol is None:
        return None
    return lsp.Range(
        start=lsp.Position(line=occurrence.line, character=occurrence.column),
        end=lsp.Position(line=occurrence.end_line, character=occurrence.end_column),
    )


def handle_rename(
    params: lsp.RenameParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
    workspace: Workspace | None = None,
    *,
    analysis: SymbolIndex | None = None,
) -> lsp.WorkspaceEdit | None:
    """Rename the symbol under the cursor in the current and open documents.

    Scope-aware: renaming a local variable does not touch a same-named global,
    and renaming a UDT field/method/enum member only edits that member. A
    script-level symbol is also renamed in other open scripts that declare the
    same script-level name (the common multi-file authoring workflow).

    Args:
        params: Client rename params (position + ``new_name``).
        source: Cursor document text, or ``None``.
        uri: Cursor document URI.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source*.
        workspace: Open-document store. Other open buffers that contain the
            symbol are included in the edit. ``None`` limits the edit to *uri*.
        analysis: Pre-built symbol index for *tree*.

    Returns:
        :class:`~lsprotocol.types.WorkspaceEdit`, or ``None`` when the symbol
        is not renamable / the new name is invalid / it conflicts with an
        existing declaration.
    """
    if not source:
        return None
    line = params.position.line
    character = params.position.character
    if in_comment_or_string(source, line, character):
        return None

    new_name = params.new_name
    if not is_valid_pine_ident(new_name) or not is_renamable_ident(new_name, new_name):
        return None

    segment, _start, _end, full = cursor_ident(source, line, character)
    if not is_renamable_ident(segment, full):
        return None

    index = ensure_symbol_index(source, tree, analysis)
    if index is None:
        return None
    symbol = index.symbol_at(line, character)
    if symbol is None:
        return None

    existing = symbol.scope.lookup(new_name)
    if existing is not None and existing is not symbol:
        return None

    changes: dict[str, list[lsp.TextEdit]] = {}
    current_edits = _edits_for_symbol(index, symbol, new_name)
    if current_edits:
        changes[uri] = current_edits

    if workspace is not None and symbol.scope is index.script_scope:
        for doc in workspace.list_open_documents():
            if doc.uri == uri or not doc.source:
                continue
            other_index = ensure_symbol_index(doc.source, doc.valid_ast, doc.valid_analysis)
            if other_index is None:
                continue
            other_symbol = other_index.script_scope.symbols.get(symbol.name)
            if other_symbol is None or other_symbol.kind != symbol.kind:
                continue
            edits = _edits_for_symbol(other_index, other_symbol, new_name)
            if edits:
                changes[doc.uri] = edits

    if not changes:
        return None
    return lsp.WorkspaceEdit(changes=changes)


def _edits_for_symbol(index: SymbolIndex, symbol: Symbol, new_name: str) -> list[lsp.TextEdit]:
    occurrences = index.occurrences_for(symbol, include_declaration=True)
    return [
        lsp.TextEdit(
            range=lsp.Range(
                start=lsp.Position(line=occ.line, character=occ.column),
                end=lsp.Position(line=occ.end_line, character=occ.end_column),
            ),
            new_text=new_name,
        )
        for occ in occurrences
    ]
