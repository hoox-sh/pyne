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

"""Inline completion — deterministic ghost text for common Pine calls.

LSP 3.18 ``textDocument/inlineCompletion``. Only a small curated set of
argument shapes is offered, and only when the cursor sits immediately after an
empty ``(``. The feature is off by default (``inlineCompletionEnabled``) so it
never competes with the normal completion list.

This is intentionally not model-backed: no network calls, no speculation about
user code. A suggestion is a complete, valid argument list for a builtin whose
shape is stable across Pine v5/v6.
"""

from __future__ import annotations

import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.langserver.protocol.utils import in_comment_or_string


_CALLEE_TAIL = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*$")

# Builtin name -> text inserted after the opening ``(`` (including the close).
_CURATED_ARGUMENTS: dict[str, str] = {
    "plot": "close)",
    "plotchar": 'close, title="", char="•")',
    "plotshape": "close > open, style=shape.triangleup, location=location.belowbar)",
    "ta.sma": "close, 14)",
    "ta.ema": "close, 20)",
    "ta.rsi": "close, 14)",
    "ta.atr": "14)",
    "ta.change": "close)",
    "ta.crossover": "close, ta.sma(close, 14))",
    "ta.crossunder": "close, ta.sma(close, 14))",
    "strategy.entry": '"Long", strategy.long)',
    "strategy.close": '"Long")',
    "strategy.exit": '"Exit", "Long", stop=close * 0.98, limit=close * 1.02)',
    "request.security": 'syminfo.tickerid, "D", close)',
    "array.new_float": "0, 0.0)",
    "array.new_int": "0, 0)",
    "table.new": "position.top_right, 1, 1)",
    "label.new": 'bar_index, close, "")',
    "line.new": "bar_index, close, bar_index, close)",
}


def handle_inline_completion(
    params: lsp.InlineCompletionParams,
    source: str | None,
    uri: str,
    tree: Any | None = ...,
    *,
    enabled: bool = False,
) -> lsp.InlineCompletionList | None:
    """Return one ghost-text suggestion for an empty builtin call.

    Args:
        params: Client inline-completion params (position already converted to
            code-point columns by the server wrapper).
        source: Current buffer text, or ``None``.
        uri: Document URI (unused; kept for handler symmetry).
        tree: Unused; inline completion works on the line prefix so it still
            responds while the buffer does not parse.
        enabled: Feature gate from ``inlineCompletionEnabled``.

    Returns:
        An :class:`~lsprotocol.types.InlineCompletionList` with at most one
        item, or ``None``.
    """
    del uri, tree  # line-prefix feature; no AST needed
    if not enabled or not source:
        return None

    lines = source.split("\n")
    line_index = params.position.line
    if not (0 <= line_index < len(lines)):
        return None
    line = lines[line_index]
    column = max(0, min(params.position.character, len(line)))
    prefix = line[:column]
    # The cursor sits after the `(`, so an unterminated string/comment may end
    # exactly at the cursor; the helper covers closed comments, the prefix scan
    # covers open ones.
    if in_comment_or_string(source, line_index, column) or _open_string_or_comment(prefix):
        return None

    open_index = _unclosed_paren(prefix)
    if open_index < 0:
        return None
    # Only complete an empty argument list; typed arguments are left alone.
    if prefix[open_index + 1 :].strip():
        return None
    # If the client already has the closing paren after the cursor, do nothing.
    if ")" in line[column:]:
        return None

    match = _CALLEE_TAIL.search(prefix[:open_index])
    if not match:
        return None
    insert_text = _CURATED_ARGUMENTS.get(match.group(1))
    if insert_text is None:
        return None

    position = lsp.Position(line=line_index, character=column)
    return lsp.InlineCompletionList(
        items=[
            lsp.InlineCompletionItem(
                insert_text=insert_text,
                range=lsp.Range(start=position, end=position),
            )
        ]
    )


def _unclosed_paren(prefix: str) -> int:
    """Index of the innermost unmatched ``(`` in *prefix*, or ``-1``."""
    depth = 0
    for index in range(len(prefix) - 1, -1, -1):
        char = prefix[index]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                return index
            depth -= 1
    return -1


def _open_string_or_comment(prefix: str) -> bool:
    """True when *prefix* ends inside a Pine string or ``//`` comment."""
    in_double = False
    in_single = False
    in_triple_double = False
    in_triple_single = False
    index = 0
    while index < len(prefix):
        if in_triple_double:
            if prefix.startswith('"""', index):
                in_triple_double = False
                index += 3
                continue
            index += 1
            continue
        if in_triple_single:
            if prefix.startswith("'''", index):
                in_triple_single = False
                index += 3
                continue
            index += 1
            continue
        if in_double:
            char = prefix[index]
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_double = False
            index += 1
            continue
        if in_single:
            char = prefix[index]
            if char == "\\":
                index += 2
                continue
            if char == "'":
                in_single = False
            index += 1
            continue
        if prefix.startswith("//", index):
            return True
        if prefix.startswith('"""', index):
            in_triple_double = True
            index += 3
            continue
        if prefix.startswith("'''", index):
            in_triple_single = True
            index += 3
            continue
        char = prefix[index]
        if char == '"':
            in_double = True
        elif char == "'":
            in_single = True
        index += 1
    return in_double or in_single or in_triple_double or in_triple_single
