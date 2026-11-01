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

"""Linked editing ranges — ``textDocument/linkedEditingRange``.

Public handler: :func:`handle_linked_editing_range`. Returns same-document
ranges for the user identifier under the cursor so the client can drive
live multi-cursor edits. Keywords and builtin namespaces are unlinked
(same set as :mod:`.rename`).
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.features.highlight import cursor_ident
from pynescript.langserver.features.highlight import is_renamable_ident
from pynescript.langserver.protocol.utils import in_comment_or_string


WORD_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"


def handle_linked_editing_range(
    params: lsp.LinkedEditingRangeParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> lsp.LinkedEditingRanges | None:
    """Return scope-aware same-document ranges for the symbol under the cursor.

    Args:
        params: Client linked-editing params (position).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source*.
        analysis: Pre-built symbol index for *tree*.

    Returns:
        :class:`~lsprotocol.types.LinkedEditingRanges` with a Pine ident
        ``word_pattern``, or ``None`` when there is no renamable symbol.
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
    symbol = index.symbol_at(line, character)
    if symbol is None:
        return None
    occurrences = index.occurrences_for(symbol, include_declaration=True)
    if not occurrences:
        return None
    return lsp.LinkedEditingRanges(
        ranges=[
            lsp.Range(
                start=lsp.Position(line=occ.line, character=occ.column),
                end=lsp.Position(line=occ.end_line, character=occ.end_column),
            )
            for occ in occurrences
        ],
        word_pattern=WORD_PATTERN,
    )
