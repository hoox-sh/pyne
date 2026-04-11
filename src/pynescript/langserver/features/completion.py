# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Completion feature — textDocument/completion handler.

Provides autocompletion for Pine Script builtins and user-defined symbols.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.langserver.providers.completion_items import (
    build_completion_list,
    build_completion_item,
    build_module_completion,
)
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.protocol.utils import get_trigger_char, get_word_at_position


def handle_completion(params: lsp.CompletionParams, source: str | None) -> lsp.CompletionList:
    """Handle textDocument/completion request.

    Args:
        params: The completion params from the LSP client.
        source: The source text of the document (for position context).

    Returns:
        CompletionList with completion items.
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
