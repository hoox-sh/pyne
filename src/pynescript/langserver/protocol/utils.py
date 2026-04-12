# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""LSP protocol utilities."""

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
