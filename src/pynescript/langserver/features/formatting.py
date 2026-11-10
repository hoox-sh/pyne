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

Prose comments are not on the ASDL tree. After the canonical unparse, comments
are spliced back onto the matching tokens so formatting stays lossless and
idempotent (line comments, trailing comments, and block comments).

Parse failures yield an empty edit list (no throw to the client).
"""

from __future__ import annotations

from dataclasses import dataclass
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


def _multiline_string_lines(source: str) -> list[bool]:
    """Mark lines whose trailing whitespace lives inside a multi-line string."""
    lines = source.split("\n")
    flags = [False] * len(lines)
    i = 0
    n = len(source)
    line = 0
    triple: str | None = None
    while i < n:
        ch = source[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if triple is not None:
            flags[line] = True
            if source.startswith(triple, i):
                triple = None
                i += 3
            else:
                i += 1
            continue
        if ch in "\"'":
            marker = source[i : i + 3]
            if marker in ('"""', "'''"):
                triple = marker
                flags[line] = True
                i += 3
                continue
            quote = ch
            i += 1
            while i < n:
                c = source[i]
                if c == "\\":
                    i += 2
                    continue
                if c in (quote, "\n"):
                    i += 1
                    break
                i += 1
            continue
        i += 1
    return flags


def _safe_whitespace_format(source: str) -> str:
    """Trim trailing whitespace and normalize the final newline, keeping trivia.

    Used when prose/block comments are present: the canonical unparser would
    drop them, but a whitespace-only pass is always safe. Lines inside a
    multi-line string are left untouched so string content is preserved.
    """
    lines = source.split("\n")
    flags = _multiline_string_lines(source)
    cleaned = [
        line if (index < len(flags) and flags[index]) else line.rstrip(" \t") for index, line in enumerate(lines)
    ]
    text = "\n".join(cleaned)
    if not text.strip():
        return source
    return text.rstrip("\n") + "\n"


def has_unpreserved_comments(source: str, tree: Any | None = None) -> bool:
    """True when formatting would drop a comment in *source*.

    Public wrapper for code actions. Comment-preserving format returns
    ``False`` so C002 can offer a real pretty-print. Parse failures and a
    splice that still loses trivia return ``True``.
    """
    if not source:
        return False
    if tree is None:
        try:
            from pynescript.ast.helper import parse

            tree = parse(source, filename="<format>")
        except Exception:
            return True
    try:
        formatted = _format_text(source, tree)
    except Exception:
        return True
    return not _comments_preserved(source, formatted)


def _format_text(source: str, tree: Any) -> str:
    """Canonical unparse, with comments spliced back in when present."""
    from pynescript.ast.unparser import NodeUnparser

    formatted = NodeUnparser().visit(tree)
    if not formatted:
        return _safe_whitespace_format(source) if _has_comments(source, tree) else formatted
    if not _has_comments(source, tree):
        return formatted
    try:
        return _splice_comments(source, formatted)
    except Exception:
        return _safe_whitespace_format(source)


@dataclass
class _Lexeme:
    text: str
    start: int
    end: int
    line: int
    comment: bool


@dataclass
class _SpanEdit:
    start: int
    end: int
    text: str


def _lexemes(source: str) -> list[_Lexeme]:
    """Lex *source*, keeping comments and significant tokens."""
    from antlr4 import CommonTokenStream
    from antlr4 import InputStream

    from pynescript.ast.grammar.antlr4.lexer import PinescriptLexer

    lexer = PinescriptLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    stream.fill()
    skip = {
        PinescriptLexer.WS,
        PinescriptLexer.NEWLINE,
        PinescriptLexer.INDENT,
        PinescriptLexer.DEDENT,
    }
    lexemes: list[_Lexeme] = []
    for token in stream.tokens:
        if token.type == -1 or token.type in skip:
            continue
        text = token.text or ""
        start = int(token.start)
        lexemes.append(
            _Lexeme(
                text=text,
                start=start,
                end=start + len(text),
                line=max(0, int(token.line) - 1),
                comment=token.type == PinescriptLexer.COMMENT,
            )
        )
    return lexemes


def _is_own_line(source: str, start: int) -> bool:
    line_start = source.rfind("\n", 0, start) + 1
    return source[line_start:start].strip() == ""


def _find_comment(text: str, needle: str, start: int) -> int | None:
    """Return the index after a whole-comment match of *needle*, or ``None``."""
    if not needle:
        return None
    idx = start
    while True:
        found = text.find(needle, idx)
        if found < 0:
            return None
        after = found + len(needle)
        before_ok = found == 0 or text[found - 1] in "\n\r \t"
        after_ok = after >= len(text) or text[after] in "\n\r \t"
        if before_ok and after_ok:
            return after
        idx = found + 1


def _count_comment(text: str, needle: str) -> int:
    count = 0
    cursor = 0
    while True:
        found = _find_comment(text, needle, cursor)
        if found is None:
            return count
        count += 1
        cursor = found


def _comments_preserved(source: str, formatted: str) -> bool:
    try:
        comments = [item.text.rstrip() for item in _lexemes(source) if item.comment]
    except Exception:
        return False
    return all(_count_comment(formatted, comment) >= _count_comment(source, comment) for comment in comments)


def _splice_comments(source: str, formatted: str) -> str:
    """Insert comments from *source* into canonical *formatted* text.

    Significant tokens are aligned (the unparser may drop redundant
    parentheses or respell a literal). Line comments stay on their own line
    ahead of the next token, trailing ``//`` / ``#`` comments stay at the end
    of the line that owns them, and inline block comments stay between the
    surrounding tokens. A comment that cannot be placed is appended so the
    format is lossless.
    """
    original = _lexemes(source)
    formatted_lex = _lexemes(formatted)
    orig_sig = [item for item in original if not item.comment]
    fmt_sig = [item for item in formatted_lex if not item.comment]
    orig_to_fmt = _align_tokens(orig_sig, fmt_sig)

    own_before: dict[int, list[str]] = {}
    inline_before: dict[int, list[str]] = {}
    trailing_on_line: dict[int, list[str]] = {}
    end_own: list[str] = []

    def line_of(token: _Lexeme) -> int:
        return formatted.count("\n", 0, token.start)

    for comment in original:
        if not comment.comment:
            continue
        text = comment.text.rstrip()
        if not text:
            continue
        prev_i, next_i = _comment_neighbors(comment, orig_sig)
        kind = _comment_kind(source, comment)
        next_fmt = _mapped(orig_to_fmt, next_i, forward=True)
        prev_fmt = _mapped(orig_to_fmt, prev_i, forward=False)
        if kind == "inline":
            if next_fmt is None:
                end_own.append(text)
            else:
                inline_before.setdefault(next_fmt, []).append(text)
            continue
        if kind == "own":
            if next_fmt is None:
                end_own.append(text)
            else:
                own_before.setdefault(next_fmt, []).append(text)
            continue
        if prev_fmt is not None and next_fmt is not None and line_of(fmt_sig[prev_fmt]) == line_of(fmt_sig[next_fmt]):
            target = line_of(fmt_sig[next_fmt])
        elif prev_fmt is not None:
            target = line_of(fmt_sig[prev_fmt])
        elif next_fmt is not None:
            target = line_of(fmt_sig[next_fmt])
        else:
            end_own.append(text)
            continue
        trailing_on_line.setdefault(target, []).append(text)

    for index, comments in list(own_before.items()):
        own_before[index] = _subtract_present(comments, _gap_before(formatted, fmt_sig, index))
    for index, comments in list(inline_before.items()):
        inline_before[index] = _subtract_present(comments, _gap_before(formatted, fmt_sig, index))

    edits: list[_SpanEdit] = []
    for index, token in enumerate(fmt_sig):
        own = own_before.get(index) or []
        inline = inline_before.get(index) or []
        if own:
            edits.append(_own_line_edit(formatted, token.start, own, inline))
        elif inline:
            edits.append(_inline_edit(formatted, token.start, inline))
    for line_index, comments in trailing_on_line.items():
        edit = _trailing_edit(formatted, line_index, comments)
        if edit is not None:
            edits.append(edit)

    result = _apply_edits(formatted, edits)
    if end_own:
        suffix = "\n".join(end_own)
        result = result + ("" if result.endswith("\n") else "\n") + suffix + "\n"
    result = _append_missing(source, result)
    return result


def _align_tokens(orig_sig: list[_Lexeme], fmt_sig: list[_Lexeme]) -> list[int | None]:
    from difflib import SequenceMatcher

    mapping: list[int | None] = [None] * len(orig_sig)
    matcher = SequenceMatcher(
        a=[item.text for item in orig_sig],
        b=[item.text for item in fmt_sig],
        autojunk=False,
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                mapping[i1 + offset] = j1 + offset
        elif tag == "replace":
            for offset in range(min(i2 - i1, j2 - j1)):
                mapping[i1 + offset] = j1 + offset
    return mapping


def _comment_neighbors(comment: _Lexeme, sigs: list[_Lexeme]) -> tuple[int | None, int | None]:
    prev_i: int | None = None
    next_i: int | None = None
    for index, token in enumerate(sigs):
        if token.end <= comment.start:
            prev_i = index
        elif token.start >= comment.end and next_i is None:
            next_i = index
            break
    return prev_i, next_i


def _mapped(mapping: list[int | None], index: int | None, *, forward: bool) -> int | None:
    if index is None:
        return None
    if forward:
        for cursor in range(index, len(mapping)):
            if mapping[cursor] is not None:
                return mapping[cursor]
        return None
    for cursor in range(index, -1, -1):
        if mapping[cursor] is not None:
            return mapping[cursor]
    return None


def _comment_kind(source: str, comment: _Lexeme) -> str:
    if _is_own_line(source, comment.start):
        return "own"
    if comment.text.startswith("/*"):
        return "inline"
    return "trailing"


def _gap_before(formatted: str, fmt_sig: list[_Lexeme], index: int) -> str:
    start = 0 if index == 0 else fmt_sig[index - 1].end
    return formatted[start : fmt_sig[index].start]


def _subtract_present(comments: list[str], gap: str) -> list[str]:
    kept: list[str] = []
    cursor = 0
    for comment in comments:
        found = _find_comment(gap, comment, cursor)
        if found is None:
            kept.append(comment)
        else:
            cursor = found
    return kept


def _own_line_edit(formatted: str, token_start: int, comments: list[str], inline: list[str]) -> _SpanEdit:
    line_start = formatted.rfind("\n", 0, token_start) + 1
    cursor = line_start
    while cursor < len(formatted) and formatted[cursor] in " \t":
        cursor += 1
    indent = formatted[line_start:cursor]
    if token_start <= cursor:
        block = "".join(f"{indent}{comment}\n" for comment in comments)
        return _SpanEdit(line_start, line_start, block)
    cont = indent + "    "
    gap = token_start
    while gap > line_start and formatted[gap - 1] in " \t":
        gap -= 1
    body = "\n".join(f"{cont}{comment}" for comment in comments)
    prefix = cont
    if inline:
        prefix = f"{cont}{' '.join(inline)} "
    return _SpanEdit(gap, token_start, f"\n{body}\n{prefix}")


def _inline_edit(formatted: str, token_start: int, comments: list[str]) -> _SpanEdit:
    line_start = formatted.rfind("\n", 0, token_start) + 1
    gap = token_start
    while gap > line_start and formatted[gap - 1] in " \t":
        gap -= 1
    return _SpanEdit(gap, token_start, f" {' '.join(comments)} ")


def _trailing_edit(formatted: str, line_index: int, comments: list[str]) -> _SpanEdit | None:
    lines = formatted.split("\n")
    if line_index < 0 or line_index >= len(lines):
        return None
    start = sum(len(lines[i]) + 1 for i in range(line_index))
    content = lines[line_index]
    trimmed = content.rstrip(" \t")
    suffix = "".join(f"  {comment}" for comment in comments)
    if not suffix or trimmed.endswith(suffix):
        return None
    return _SpanEdit(start + len(trimmed), start + len(content), suffix)


def _apply_edits(formatted: str, edits: list[_SpanEdit]) -> str:
    ordered = sorted(edits, key=lambda edit: (edit.start, edit.end), reverse=True)
    result = formatted
    for edit in ordered:
        result = result[: edit.start] + edit.text + result[edit.end :]
    return result


def _append_missing(source: str, formatted: str) -> str:
    """Append any comment the splice failed to place (lossless fallback)."""
    try:
        comments = [item.text.rstrip() for item in _lexemes(source) if item.comment and item.text.rstrip()]
    except Exception:
        return formatted
    missing: list[str] = []
    for comment in comments:
        if _count_comment(formatted, comment) < _count_comment(source, comment):
            missing.append(comment)
            formatted = formatted + "\n" + comment
    if missing and not formatted.endswith("\n"):
        formatted += "\n"
    return formatted


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


def _whole_document_edit(source: str, formatted: str) -> lsp.TextEdit:
    """One replace-edit covering the entire document."""
    lines = source.split("\n")
    end_line = len(lines) - 1
    end_col = len(lines[-1]) if lines else 0
    return lsp.TextEdit(
        range=lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=end_line, character=end_col),
        ),
        new_text=formatted,
    )


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

        if tree is None:
            tree = parse(source, filename="<format>")
        formatted = _format_text(source, tree)

        if formatted == source:
            return []

        return [_whole_document_edit(source, formatted)]

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

        if tree is None:
            tree = parse(source, filename="<format>")
        formatted = _format_text(source, tree)

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

        if tree is ...:
            tree = parse(source, filename="<format>")
        formatted = _format_text(source, tree)

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
