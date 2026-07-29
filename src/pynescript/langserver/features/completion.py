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

- :func:`handle_completion` — prefix / ``.``-triggered builtins and modules
- :func:`handle_completion_resolve` — fill documentation for a completion item

Uses :mod:`pynescript.langserver.providers.builtin_metadata` and
:mod:`pynescript.langserver.providers.completion_items`. Wired from
:mod:`pynescript.langserver.server` with trigger character ``.`` and
``resolve_provider=True``.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.langserver.protocol.utils import get_trigger_char
from pynescript.langserver.protocol.utils import get_word_at_position
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.providers.completion_items import build_completion_item
from pynescript.langserver.providers.completion_items import build_completion_list
from pynescript.langserver.providers.completion_items import build_module_completion


def handle_completion(params: lsp.CompletionParams, source: str | None) -> lsp.CompletionList:
    """Return a completion list for the cursor position in *source*.

    Dot-prefix paths (e.g. ``ta.``) complete module members; otherwise returns
    filtered builtins for the typed prefix.

    Args:
        params: Client ``CompletionParams`` (position / context).
        source: Document text, or ``None`` if unknown.

    Returns:
        Always a :class:`~lsprotocol.types.CompletionList` (may be empty).
    """
    # Get context
    position = params.position
    line = position.line
    character = position.character

    # Get the text before cursor
    if source:
        lines = source.split("\n")
        if line < len(lines):
            text_before_cursor = lines[line][:character]
        else:
            text_before_cursor = ""
    else:
        text_before_cursor = ""

    # Check for trigger character
    trigger_char = get_trigger_char(source or "", line, character)

    # Get the current word being typed
    word, word_start, word_end = get_word_at_position(source or "", line, character)

    # Determine what to complete
    prefix = text_before_cursor.split()[-1] if text_before_cursor else ""

    # If we have a dot, check for module completion
    if "." in prefix:
        module = prefix.rsplit(".", 1)[0]
        return build_module_completion(module)

    # If triggered by dot, complete module members
    if trigger_char == ".":
        # Find the module name before the dot
        words = text_before_cursor.rstrip().split()
        if words:
            last_word = words[-1]
            if last_word.endswith("."):
                module = last_word.rstrip(".")
                return build_module_completion(module)

    # Otherwise, complete all builtins
    return build_completion_list(prefix=prefix)


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
