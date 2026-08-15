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

"""Completion — ``textDocument/completion`` and ``completionItem/resolve``.

Public handlers:

- :func:`handle_completion` — prefix / ``.``-triggered builtins, keywords, user enums
- :func:`handle_completion_resolve` — fill documentation for a completion item

Uses :mod:`pynescript.langserver.providers.builtin_metadata` and
:mod:`pynescript.langserver.providers.completion_items`. Wired from
:mod:`pynescript.langserver.server` with trigger character ``.`` and
``resolve_provider=True``.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.langserver.protocol.utils import get_trigger_char
from pynescript.langserver.protocol.utils import trailing_ident
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.providers.completion_items import build_completion_item
from pynescript.langserver.providers.completion_items import build_completion_list
from pynescript.langserver.providers.completion_items import build_enum_member_completion
from pynescript.langserver.providers.completion_items import build_enum_name_items
from pynescript.langserver.providers.completion_items import build_keyword_items
from pynescript.langserver.providers.completion_items import build_module_completion
from pynescript.langserver.providers.completion_items import collect_user_enums


def handle_completion(
    params: lsp.CompletionParams,
    source: str | None,
    tree: Any | None = ...,
) -> lsp.CompletionList:
    """Return a completion list for the cursor position in *source*.

    Dot-prefix paths (e.g. ``ta.`` / ``Side.``) complete module or user-enum
    members; otherwise returns keywords, user enums, and filtered builtins.

    Args:
        params: Client ``CompletionParams`` (position / context).
        source: Document text, or ``None`` if unknown.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source*.

    Returns:
        Always a :class:`~lsprotocol.types.CompletionList` (may be empty).
    """
    position = params.position
    line = position.line
    character = position.character

    if source:
        lines = source.split("\n")
        if line < len(lines):
            text_before_cursor = lines[line][:character]
        else:
            text_before_cursor = ""
    else:
        text_before_cursor = ""

    trigger_char = get_trigger_char(source or "", line, character)
    prefix = trailing_ident(text_before_cursor)

    enums = collect_user_enums(_resolve_tree(source, tree), source)

    if "." in prefix or trigger_char == ".":
        module, sep, rest = prefix.rpartition(".")
        if not sep and trigger_char == ".":
            module = prefix
            rest = ""
        if module:
            enum_info = enums.get(module)
            if enum_info is not None:
                return build_enum_member_completion(enum_info, member_prefix=rest)
            return build_module_completion(module, member_prefix=rest)

    extras = build_keyword_items(prefix) + build_enum_name_items(enums, prefix)
    builtin = build_completion_list(prefix=prefix)
    return lsp.CompletionList(is_incomplete=False, items=extras + builtin.items)


def _resolve_tree(source: str | None, tree: Any | None) -> Any | None:
    """Use *tree* when provided; otherwise parse *source* (best-effort)."""
    if tree is not ...:
        return tree
    if not source:
        return None
    try:
        from pynescript.ast.helper import parse

        return parse(source)
    except Exception:
        return None


def handle_completion_resolve(
    params: lsp.CompletionItem,
) -> lsp.CompletionItem:
    """Handle completionItem/resolve request.

    Enriches a completion item with full documentation.

    Args:
        params: The completion item to resolve.

    Returns:
        The resolved completion item with full documentation.
    """
    # Check if it's a builtin
    builtin_info = get_builtin(params.label)
    if builtin_info:
        return build_completion_item(builtin_info)

    # Return as-is if not a builtin
    return params
