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

from collections.abc import Callable
from typing import Any

import attrs

from lsprotocol import types as lsp


def convert_positions(
    value: Any,
    lines: list[str],
    *,
    to_codepoint: bool,
    lines_for_uri: Callable[[str], list[str] | None] | None = None,
) -> Any:
    """Recursively convert LSP UTF-16 positions to/from Python code points.

    LSP positions count UTF-16 code units; Python strings count code points.
    The two differ only when a line contains a non-BMP character (emoji, some
    CJK extensions). Feature handlers operate on Python strings, so server
    handlers convert params on the way in and results on the way out.

    ``lines_for_uri`` lets URI-bearing containers (``Location``,
    ``TextDocumentEdit``, ``WorkspaceEdit.changes``) use the right document's
    lines when a result spans several open files.
    """
    if isinstance(value, lsp.Position):
        return _convert_position(value, lines, to_codepoint)
    if isinstance(value, lsp.Location):
        target = lines_for_uri(value.uri) if lines_for_uri is not None else None
        converted = convert_positions(
            value.range,
            target or lines,
            to_codepoint=to_codepoint,
            lines_for_uri=lines_for_uri,
        )
        return value if converted is value.range else attrs.evolve(value, range=converted)
    if isinstance(value, lsp.TextDocumentEdit):
        target = lines_for_uri(value.text_document.uri) if lines_for_uri is not None else None
        converted = convert_positions(
            value.edits,
            target or lines,
            to_codepoint=to_codepoint,
            lines_for_uri=lines_for_uri,
        )
        return value if converted is value.edits else attrs.evolve(value, edits=converted)
    if isinstance(value, lsp.WorkspaceEdit):
        return _convert_workspace_edit(value, lines, to_codepoint=to_codepoint, lines_for_uri=lines_for_uri)
    if isinstance(value, lsp.FoldingRange):
        return _convert_folding_range(value, lines, to_codepoint)
    if isinstance(value, list):
        converted_items = [
            convert_positions(item, lines, to_codepoint=to_codepoint, lines_for_uri=lines_for_uri)
            for item in value
        ]
        if all(new is old for new, old in zip(converted_items, value, strict=True)):
            return value
        return converted_items
    if isinstance(value, tuple):
        return tuple(
            convert_positions(item, lines, to_codepoint=to_codepoint, lines_for_uri=lines_for_uri)
            for item in value
        )
    if isinstance(value, dict):
        converted_values = {
            key: convert_positions(item, lines, to_codepoint=to_codepoint, lines_for_uri=lines_for_uri)
            for key, item in value.items()
        }
        if all(new is value[key] for key, new in converted_values.items()):
            return value
        return converted_values
    if attrs.has(type(value)):
        updates = {}
        for field in attrs.fields(type(value)):
            if not field.init:
                continue
            old = getattr(value, field.name)
            new = convert_positions(
                old,
                lines,
                to_codepoint=to_codepoint,
                lines_for_uri=lines_for_uri,
            )
            if new is not old:
                updates[field.name] = new
        return attrs.evolve(value, **updates) if updates else value
    return value


def _convert_position(position: lsp.Position, lines: list[str], to_codepoint: bool) -> lsp.Position:
    if not (0 <= position.line < len(lines)):
        return position
    content = _line_content(lines[position.line])
    character = (
        utf16_column_to_codepoint(content, position.character)
        if to_codepoint
        else codepoint_column_to_utf16(content, position.character)
    )
    if character == position.character:
        return position
    return lsp.Position(line=position.line, character=character)


def _convert_workspace_edit(
    edit: lsp.WorkspaceEdit,
    lines: list[str],
    *,
    to_codepoint: bool,
    lines_for_uri: Callable[[str], list[str] | None] | None,
) -> lsp.WorkspaceEdit:
    updates: dict[str, Any] = {}
    if edit.changes:
        changes = {}
        for uri, edits in edit.changes.items():
            target = lines_for_uri(uri) if lines_for_uri is not None else None
            changes[uri] = convert_positions(
                edits,
                target or lines,
                to_codepoint=to_codepoint,
                lines_for_uri=lines_for_uri,
            )
        updates["changes"] = changes
    if edit.document_changes:
        updates["document_changes"] = [
            convert_positions(
                item,
                lines,
                to_codepoint=to_codepoint,
                lines_for_uri=lines_for_uri,
            )
            for item in edit.document_changes
        ]
    return attrs.evolve(edit, **updates) if updates else edit


def _convert_folding_range(
    value: lsp.FoldingRange,
    lines: list[str],
    to_codepoint: bool,
) -> lsp.FoldingRange:
    updates: dict[str, Any] = {}
    for prefix in ("start", "end"):
        line = getattr(value, f"{prefix}_line", None)
        character = getattr(value, f"{prefix}_character", None)
        if line is None or character is None or not (0 <= line < len(lines)):
            continue
        content = _line_content(lines[line])
        updates[f"{prefix}_character"] = (
            utf16_column_to_codepoint(content, character)
            if to_codepoint
            else codepoint_column_to_utf16(content, character)
        )
    return attrs.evolve(value, **updates) if updates else value


def _line_content(line: str) -> str:
    """Line text without the CR of a CRLF terminator."""
    return line[:-1] if line.endswith("\r") else line


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


def in_comment_or_string(text: str, line: int, column: int) -> bool:
    """True when LSP position (*line*, *column*) is inside a comment or string.

    Completion/hover should stay quiet there: suggesting `ta.sma` inside a
    comment or a plotted label string is noise. The scanner mirrors the
    grammar's `//`, `/* */`, `#` comments and single/triple-quoted strings.
    """
    if not text:
        return False
    offset = offset_from_position(text, line, column)
    i = 0
    n = min(offset, len(text))
    while i < n:
        ch = text[i]
        if ch in "\"'":
            triple = text[i : i + 3]
            if triple in ('"""', "'''"):
                end = text.find(triple, i + 3)
                if end < 0 or end + 3 > offset:
                    return True
                i = end + 3
                continue
            quote = ch
            j = i + 1
            while j < n:
                c = text[j]
                if c == "\\":
                    j += 2
                    continue
                if c == quote:
                    j += 1
                    break
                if c == "\n":
                    break
                j += 1
            if j > offset:
                return True
            i = j
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                end = text.find("\n", i)
                end = n if end < 0 else end
                if offset <= end:
                    return True
                i = end
                continue
            if nxt == "*":
                end = text.find("*/", i + 2)
                end = n if end < 0 else end + 2
                if offset <= end:
                    return True
                i = end
                continue
        if ch == "#":
            nxt = text[i + 1] if i + 1 < n else ""
            if not nxt or nxt in " \t\f\r\n" or not (nxt.isdigit() or ("a" <= nxt.lower() <= "f")):
                end = text.find("\n", i)
                end = n if end < 0 else end
                if offset <= end:
                    return True
                i = end
                continue
        i += 1
    return False


def utf16_column_to_codepoint(line: str, column: int) -> int:
    """Convert an LSP UTF-16 column to a Python codepoint index.

    LSP positions count UTF-16 code units; Python strings count code points.
    They differ only for non-BMP characters (emoji, some CJK extensions).
    Columns past the end clamp to ``len(line)``.
    """
    if column <= 0 or not line:
        return 0
    units = 0
    for index, char in enumerate(line):
        if units >= column:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
    return len(line)


def codepoint_column_to_utf16(line: str, column: int) -> int:
    """Convert a Python codepoint index to an LSP UTF-16 column."""
    if column <= 0 or not line:
        return 0
    return sum(2 if ord(char) > 0xFFFF else 1 for char in line[:column])


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


def _is_ascii_ident_start(ch: str) -> bool:
    return ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch == "_"


def _is_ascii_ident_cont(ch: str) -> bool:
    return _is_ascii_ident_start(ch) or ("0" <= ch <= "9")


def trailing_ident(text_before_cursor: str) -> str:
    """Return the trailing identifier or dotted path (optional trailing ``.``).

    Ignores surrounding punctuation so ``plot(ta.`` yields ``ta.`` and
    ``s = Side.b`` yields ``Side.b``.
    """
    if not text_before_cursor:
        return ""
    end = len(text_before_cursor)
    trailing_dot = False
    if text_before_cursor[-1] == ".":
        trailing_dot = True
        end -= 1
        if end == 0:
            return ""
    i = end
    while i > 0:
        ch = text_before_cursor[i - 1]
        if _is_ascii_ident_cont(ch) or ch == ".":
            i -= 1
            continue
        break
    parts = text_before_cursor[i:end].split(".")
    kept: list[str] = []
    for seg in reversed(parts):
        if seg and _is_ascii_ident_start(seg[0]) and all(_is_ascii_ident_cont(c) for c in seg):
            kept.append(seg)
        else:
            break
    kept.reverse()
    if not kept:
        return ""
    result = ".".join(kept)
    if trailing_dot:
        result += "."
    return result


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
