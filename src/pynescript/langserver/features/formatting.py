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

"""Formatting — ``textDocument/formatting``, ``rangeFormatting``, ``onTypeFormatting``.

Public handlers:

- :func:`handle_formatting` — full document via parse + :class:`~pynescript.ast.unparser.NodeUnparser`
- :func:`handle_range_formatting` — same unparser, edit limited to the requested range
- :func:`handle_on_type_formatting` — same unparser, edit limited to the just-completed line

Parse failures yield an empty edit list (no throw to the client).
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp


_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _has_comments(source: str, tree: Any | None = None) -> bool:
    """True when *source* contains a comment the unparser would drop.

    The ASDL AST retains Pine annotations (``//@version``, ``//@function`` …)
    but not ordinary prose/block comments. Refusing to format buffers with
    non-annotation comments is the only non-destructive option until a
    comment-preserving formatter lands.
    """
    preserved = _preserved_annotations(tree)
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in "\"'":
            triple = source[i : i + 3]
            if triple in ('"""', "'''"):
                end = source.find(triple, i + 3)
                i = n if end < 0 else end + 3
                continue
            quote = ch
            j = i + 1
            while j < n:
                c = source[j]
                if c == "\\":
                    j += 2
                    continue
                if c == quote:
                    j += 1
                    break
                if c == "\n":
                    break
                j += 1
            i = j
            continue
        if ch == "/" and i + 1 < n:
            if source[i + 1] == "*":
                return True
            if source[i + 1] == "/":
                # Pine annotations (``//@version``, ``//@function`` …) are
                # retained by the AST/unparser. Plain prose comments are not.
                line_end = source.find("\n", i)
                line_end = n if line_end < 0 else line_end
                body = source[i + 2 : line_end].lstrip()
                line_start = source.rfind("\n", 0, i) + 1
                prefix = source[line_start:i].strip()
                annotation = source[line_start:line_end].strip()
                if body.startswith("@") and not prefix and annotation in preserved:
                    i = line_end
                    continue
                return True
        if ch == "#":
            nxt = source[i + 1] if i + 1 < n else ""
            if not nxt or nxt in " \t\f\r\n" or nxt not in _HEX_DIGITS:
                return True
        i += 1
    return False


def _preserved_annotations(tree: Any | None) -> set[str]:
    """Collect annotation comment lines the AST/unparser preserves."""
    if tree is None:
        return set()
    from pynescript.ast.helper import walk

    preserved: set[str] = set()
    for node in walk(tree):
        for annotation in getattr(node, "annotations", None) or []:
            if isinstance(annotation, str):
                preserved.add(annotation.strip())
    return preserved


def _aligned_lines(source: str, formatted: str) -> tuple[list[str], list[str]] | None:
    """Return line lists with matching counts, tolerating a trailing newline."""
    source_lines = source.split("\n")
    formatted_lines = formatted.split("\n")
    if len(formatted_lines) == len(source_lines) - 1 and source_lines[-1] == "":
        formatted_lines.append("")
    if len(formatted_lines) != len(source_lines):
        return None
    return source_lines, formatted_lines


def handle_formatting(
    params: lsp.DocumentFormattingParams, source: str | None, tree: Any | None = None
) -> list[lsp.TextEdit] | None:
    """Format the whole document; return one replace-edit or ``[]`` if unchanged/error.

    Args:
        params: Client formatting options (tab size unused; unparser-driven).
        source: Document text, or ``None``.
        tree: Pre-parsed AST to reuse instead of re-parsing *source*.

    Returns:
        List of :class:`~lsprotocol.types.TextEdit`, or empty list on failure.
    """
    if not source:
        return []

    try:
        from pynescript.ast.helper import parse
        from pynescript.ast.unparser import NodeUnparser

        if tree is None:
            tree = parse(source, filename="<format>")
        if _has_comments(source, tree):
            # Unparser output has no prose-comment trivia; formatting here
            # would delete user comments. Prefer no edit over data loss.
            return []

        unparser = NodeUnparser()
        formatted = unparser.visit(tree)

        if formatted == source:
            return []

        lines = source.split("\n")
        end_line = len(lines) - 1
        end_col = len(lines[-1]) if lines else 0

        return [
            lsp.TextEdit(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=end_line, character=end_col),
                ),
                new_text=formatted,
            )
        ]

    except Exception:
        return []


def handle_range_formatting(
    params: lsp.DocumentRangeFormattingParams, source: str | None, tree: Any | None = None
) -> list[lsp.TextEdit] | None:
    """Format the lines covering *params.range*; return a replace-edit or ``[]``.

    Args:
        params: Client range + formatting options.
        source: Document text, or ``None``.
        tree: Pre-parsed AST to reuse instead of re-parsing *source*.

    Returns:
        List of :class:`~lsprotocol.types.TextEdit`, or empty list on failure.
    """
    if not source:
        return []

    try:
        from pynescript.ast.helper import parse
        from pynescript.ast.unparser import NodeUnparser

        if tree is None:
            tree = parse(source, filename="<format>")
        if _has_comments(source, tree):
            return []

        unparser = NodeUnparser()
        formatted = unparser.visit(tree)

        aligned = _aligned_lines(source, formatted)
        if aligned is None:
            # Line-index mapping is unsafe when the canonical form adds or
            # removes lines; fall back to no range edit.
            return []
        source_lines, formatted_lines = aligned

        range_start = params.range.start
        range_end = params.range.end

        in_range = "\n".join(source_lines[range_start.line : range_end.line + 1])

        formatted_in_range = "\n".join(formatted_lines[range_start.line : range_end.line + 1])

        if formatted_in_range == in_range:
            return []

        return [
            lsp.TextEdit(
                range=params.range,
                new_text=formatted_in_range,
            )
        ]

    except Exception:
        return []


def handle_on_type_formatting(
    params: lsp.DocumentOnTypeFormattingParams,
    source: str | None,
    tree: Any | None = ...,
) -> list[lsp.TextEdit]:
    """Format the just-completed line after a trigger character.

    After ``\\n``, *params.position* is the cursor on the new line; the
    previous line (or line 0) is replaced with the corresponding
    :class:`~pynescript.ast.unparser.NodeUnparser` output when it differs.

    Args:
        params: Client on-type params (trigger ``ch``, cursor position).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse (skips a redundant re-parse).
            Omit (default ``...``) to parse from *source*.

    Returns:
        Zero or one :class:`~lsprotocol.types.TextEdit` covering only the
        target source line. Empty list on empty/unparsed source, unknown
        ``ch``, unchanged line, or error.
    """
    if not source or params.ch != "\n" or tree is None:
        return []

    try:
        from pynescript.ast.helper import parse
        from pynescript.ast.unparser import NodeUnparser

        if tree is ...:
            tree = parse(source, filename="<format>")
        if _has_comments(source, tree):
            return []

        unparser = NodeUnparser()
        formatted = unparser.visit(tree)

        aligned = _aligned_lines(source, formatted)
        if aligned is None:
            return []
        source_lines, formatted_lines = aligned

        target = max(0, params.position.line - 1)
        if target >= len(source_lines) or target >= len(formatted_lines):
            return []

        source_line = source_lines[target]
        formatted_line = formatted_lines[target]
        if formatted_line == source_line:
            return []

        return [
            lsp.TextEdit(
                range=lsp.Range(
                    start=lsp.Position(line=target, character=0),
                    end=lsp.Position(line=target, character=len(source_line)),
                ),
                new_text=formatted_line,
            )
        ]

    except Exception:
        return []
