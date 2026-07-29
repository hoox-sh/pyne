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

"""Formatting — ``textDocument/formatting`` and ``rangeFormatting``.

Public handlers:

- :func:`handle_formatting` — full document via parse + :class:`~pynescript.ast.unparser.NodeUnparser`
- :func:`handle_range_formatting` — same unparser, edit limited to the requested range

Parse failures yield an empty edit list (no throw to the client).
"""

from __future__ import annotations

from lsprotocol import types as lsp


def handle_formatting(params: lsp.DocumentFormattingParams, source: str | None) -> list[lsp.TextEdit] | None:
    """Format the whole document; return one replace-edit or ``[]`` if unchanged/error.

    Args:
        params: Client formatting options (tab size unused; unparser-driven).
        source: Document text, or ``None``.

    Returns:
        List of :class:`~lsprotocol.types.TextEdit`, or empty list on failure.
    """
    if not source:
        return []

    try:
        from pynescript.ast.helper import parse
        from pynescript.ast.unparser import NodeUnparser

        tree = parse(source, filename="<format>")

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


def handle_range_formatting(params: lsp.DocumentRangeFormattingParams, source: str | None) -> list[lsp.TextEdit] | None:
    """Format the lines covering *params.range*; return a replace-edit or ``[]``.

    Args:
        params: Client range + formatting options.
        source: Document text, or ``None``.

    Returns:
        List of :class:`~lsprotocol.types.TextEdit`, or empty list on failure.
    """
    if not source:
        return []

    try:
        from pynescript.ast.helper import parse
        from pynescript.ast.unparser import NodeUnparser

        tree = parse(source, filename="<format>")

        unparser = NodeUnparser()
        formatted = unparser.visit(tree)

        formatted_lines = formatted.split("\n")
        source_lines = source.split("\n")

        range_start = params.range.start
        range_end = params.range.end

        before_range = "\n".join(source_lines[: range_start.line])
        in_range = "\n".join(source_lines[range_start.line : range_end.line + 1])
        after_range = "\n".join(source_lines[range_end.line + 1 :])

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
