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

"""LSP protocol utilities (positions, words, completion triggers).

Public helpers used by feature handlers:

- :func:`position_from_offset` / :func:`offset_from_position` — coordinate conversion
- :func:`get_word_at_position` — identifier (including ``module.member``) under cursor
- :func:`get_identifier_segment_at_position` — dotted-path segment under cursor
- :func:`get_trigger_char` — character immediately before the cursor
- :func:`trailing_ident` — identifier / dotted path at the end of a line prefix
- :func:`extract_module_prefix` / :func:`build_filter_text` — completion helpers
"""

from __future__ import annotations

import re


def position_from_offset(text: str, offset: int) -> tuple[int, int]:
    """Convert a character offset to line/column position.

    Args:
        text: The source text.
        offset: Character offset (0-indexed).

    Returns:
        Tuple of (line, column), both 0-indexed.
    """
    if offset < 0:
        return (0, 0)

    lines = text.split("\n")
    current_offset = 0

    for line_num, line in enumerate(lines):
        line_length = len(line) + 1  # +1 for newline
        if current_offset + line_length > offset:
            col = offset - current_offset
            return (line_num, col)
        current_offset += line_length

    return (len(lines) - 1, len(lines[-1]) if lines else 0)


def offset_from_position(text: str, line: int, column: int) -> int:
    """Convert line/column position to character offset.

    Args:
        text: The source text.
        line: Line number (0-indexed).
        column: Column number (0-indexed).

    Returns:
        Character offset (0-indexed).
    """
    lines = text.split("\n")

    if line < 0:
        return 0
    if line >= len(lines):
        line = len(lines) - 1

    offset = sum(len(l) + 1 for l in lines[:line])
    offset += min(column, len(lines[line]))

    return offset


def get_word_at_position(text: str, line: int, column: int) -> tuple[str, int, int]:
    """Get the word at a given position.

    Args:
        text: The source text.
        line: Line number (0-indexed).
        column: Column number (0-indexed).

    Returns:
        Tuple of (word, start_col, end_col) or ("", column, column) if no word.
    """
    lines = text.split("\n")

    if line < 0 or line >= len(lines):
        return ("", column, column)

    line_text = lines[line]

    if column < 0 or column > len(line_text):
        return ("", column, column)

    # Pine Script identifiers: letter/underscore followed by alphanumerics/underscores
    # Also include dots for module access (e.g., ta.sma, request.security)
    pattern = r"[a-zA-Z_][a-zA-Z0-9_.]*"

    for match in re.finditer(pattern, line_text):
        start, end = match.start(), match.end()
        if start <= column <= end:
            return (match.group(), start, end)

    return ("", column, column)


def get_identifier_segment_at_position(text: str, line: int, column: int) -> tuple[str, int, int, str]:
    """Split a dotted word so the segment under the cursor is distinct.

    ``ta.sma`` with the cursor on ``ta`` yields ``("ta", start, start+2, "ta.sma")``.
    A non-dotted identifier returns the same string for segment and full word.

    Returns:
        ``(segment, seg_start, seg_end, full_word)``. Empty segment when there
        is no identifier at *column*.
    """
    word, start, end = get_word_at_position(text, line, column)
    if not word:
        return ("", start, end, "")
    if "." not in word:
        return (word, start, end, word)

    rel = max(0, min(column - start, len(word)))
    offset = 0
    last = word
    last_start = start
    last_end = end
    for part in word.split("."):
        part_start = offset
        part_end = offset + len(part)
        last = part
        last_start = start + part_start
        last_end = start + part_end
        if part_start <= rel <= part_end:
            return (part, last_start, last_end, word)
        offset = part_end + 1
    return (last, last_start, last_end, word)


def get_trigger_char(text: str, line: int, column: int) -> str | None:
    """Get the trigger character before the cursor.

    Args:
        text: The source text.
        line: Line number (0-indexed).
        column: Column number (0-indexed).

    Returns:
        The trigger character (e.g., "." for module completion) or None.
    """
    lines = text.split("\n")

    if line < 0 or line >= len(lines):
        return None

    line_text = lines[line]

    if column <= 0 or column > len(line_text):
        return None

    char = line_text[column - 1]
    if char in (".", "(", ",", " "):
        return char

    return None


def trailing_ident(text_before_cursor: str) -> str:
    """Return the trailing identifier or dotted path (optional trailing ``.``).

    Ignores surrounding punctuation so ``plot(ta.`` yields ``ta.`` and
    ``s = Side.b`` yields ``Side.b``.
    """
    if not text_before_cursor:
        return ""
    match = re.search(
        r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(\.?)$",
        text_before_cursor,
    )
    return (match.group(1) + match.group(2)) if match else ""


def extract_module_prefix(word: str) -> str | None:
    """Extract the module prefix from a partial completion.

    E.g., "ta." -> "ta", "request.se" -> "request.se"

    Args:
        word: The partial word being typed.

    Returns:
        The module prefix (e.g., "ta") or None.
    """
    if "." not in word:
        return None

    parts = word.rsplit(".", 1)
    return parts[0] if parts else None


def build_filter_text(name: str, prefix: str | None = None) -> str:
    """Build filter text for completion items.

    Args:
        name: The full name (e.g., "ta.sma").
        prefix: Optional partial prefix being typed.

    Returns:
        Filter text for fuzzy matching.
    """
    parts = name.split(".")
    words = []
    for part in parts:
        for i in range(1, len(part) + 1):
            words.append(" ".join(parts[: parts.index(part)]) + " " + part[:i])
    return " ".join(words)
