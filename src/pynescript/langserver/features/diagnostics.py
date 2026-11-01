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

"""Diagnostics helpers — convert linter output to LSP diagnostics.

Publish and pull diagnostic paths in :mod:`pynescript.langserver.server` use
:class:`~pynescript.langserver.workspace.Workspace` conversion primarily. This
module provides shared helpers and optional quick-fix construction:

- :func:`lint_warnings_to_diagnostics` — bulk :class:`~pynescript.ast.linter.LintWarning` → LSP
- :func:`create_quick_fix` — CodeAction when a fix is available
- :func:`create_diagnostic_related_info` — related locations for selected codes
"""

from __future__ import annotations

import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.ast.helper import parse
from pynescript.ast.helper import walk
from pynescript.ast.linter import LintWarning
from pynescript.langserver.features.formatting import handle_formatting


# Same pattern as ``PineLinter._check_version`` (flexible whitespace).
_VERSION_PRAGMA_RE = re.compile(r"//\s*@version\s*=\s*\d+")


def lint_warnings_to_diagnostics(warnings: list[LintWarning], source: str) -> list[lsp.Diagnostic]:
    """Map linter warnings to LSP :class:`~lsprotocol.types.Diagnostic` objects.

    Args:
        warnings: Output of :func:`pynescript.ast.linter.lint_script`.
        source: Document text (used for end-of-range column estimates).

    Returns:
        Diagnostics with ``source="PineScript"`` and severity mapped from the
        warning's severity string.
    """
    diagnostics = []
    # Split once: per-warning whole-document splits are O(warnings x doc-size).
    lines = source.split("\n") if source else []

    for warning in warnings:
        if _is_noisy_lint_warning(warning, source, lines):
            continue
        diag = _lint_warning_to_diagnostic(warning, source, lines)
        if diag:
            diagnostics.append(diag)

    return diagnostics


def _is_noisy_lint_warning(warning: LintWarning, source: str, lines: list[str] | None = None) -> bool:
    """True when a linter hit is a known false positive for the editor.

    C001 fires on any ``ta.*`` assignment whose name starts with a lowercase
    letter — including already-camelCase names (``fastMA``, ``length``).
    (Retired-rule filter for C003 was removed with the rule itself.)
    """
    if warning.code == "C001":
        match = re.search(r"Variable '(\w+)'", warning.message or "")
        return bool(match and "_" not in match.group(1))
    return False


def _lint_warning_to_diagnostic(
    warning: LintWarning, source: str, lines: list[str] | None = None
) -> lsp.Diagnostic | None:
    """Convert a single LintWarning to an LSP Diagnostic.

    Args:
        warning: The lint warning to convert.
        source: The source text for determining line text.
        lines: Pre-split source lines (avoids re-splitting per warning).

    Returns:
        LSP Diagnostic object or None if the warning can't be converted.
    """
    if warning.line is None:
        return None

    severity = _severity_to_lsp(warning.severity)
    line_index = max(0, warning.line - 1)
    column = warning.column if warning.column is not None else 0

    if lines is None:
        line_text = _get_line_text(source, line_index)
    elif 0 <= line_index < len(lines):
        line_text = lines[line_index]
    else:
        line_text = ""
    end_line_index = max(0, (warning.end_line or warning.line) - 1)
    if warning.end_column is not None and end_line_index == line_index:
        end_column = warning.end_column
    elif line_text:
        end_column = len(line_text)
    else:
        end_column = column + 1
    if end_line_index == line_index and end_column <= column:
        end_column = min(max(column + 1, 1), max(len(line_text), 1))
    end_column = min(end_column, 2000)

    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(line=line_index, character=column),
            end=lsp.Position(line=end_line_index, character=end_column),
        ),
        severity=severity,
        message=warning.message,
        source="pyne",
        code=warning.code,
        code_description=_build_code_description(warning.code),
        tags=_get_diagnostic_tags(warning.code),
    )


def _severity_to_lsp(severity: str) -> lsp.DiagnosticSeverity:
    """Map our severity string to LSP DiagnosticSeverity."""
    mapping = {
        "error": lsp.DiagnosticSeverity.Error,
        "warning": lsp.DiagnosticSeverity.Warning,
        "info": lsp.DiagnosticSeverity.Information,
        "information": lsp.DiagnosticSeverity.Information,
        "hint": lsp.DiagnosticSeverity.Hint,
    }
    return mapping.get(severity.lower(), lsp.DiagnosticSeverity.Warning)


def _get_line_text(source: str, line_index: int) -> str:
    """Get the text of a specific line from source."""
    if not source:
        return ""
    lines = source.split("\n")
    if 0 <= line_index < len(lines):
        return lines[line_index]
    return ""


def _build_code_description(code: str) -> lsp.CodeDescription | None:
    """Build a code description with a link to documentation.

    For now, returns None. In the future, this could link to docs.
    """
    if code.startswith(("E", "W", "C")):
        return lsp.CodeDescription(href="https://hoox.sh/pyne/docs/core/linter")
    return None


def _get_diagnostic_tags(code: str) -> list[lsp.DiagnosticTag] | None:
    """Get diagnostic tags based on code.

    Args:
        code: The lint warning code.

    Returns:
        List of DiagnosticTag or None.
    """
    if code == "W002":
        return [lsp.DiagnosticTag.Deprecated]

    return None


def create_quick_fix(
    warning: LintWarning,
    uri: str,
    source: str,
    *,
    tree: Any | None = None,
) -> lsp.CodeAction | None:
    """Create a CodeAction for a lint warning.

    W001 inserts ``//@version=6``. W002 replaces an old pragma. W104 removes
    the v6-removed ``transp=`` / ``when=`` argument. W105 compares the numeric
    condition with ``0``. C002 applies the same whole-document edit as
    :func:`~pynescript.langserver.features.formatting.handle_formatting`
    (or ``None`` when parse fails or the buffer is already canonical).

    Args:
        warning: The lint warning.
        uri: The document URI.
        source: The source text.
        tree: Parsed AST for the current buffer (W104/W105 need argument and
            literal positions). Text-only fixes work without it.

    Returns:
        A CodeAction or None if no fix is available.
    """
    if warning.code == "W001":
        return lsp.CodeAction(
            title="Add @version=6 declaration",
            kind=lsp.CodeActionKind.QuickFix,
            edit=lsp.WorkspaceEdit(
                document_changes=[
                    lsp.TextDocumentEdit(
                        text_document=lsp.OptionalVersionedTextDocumentIdentifier(uri=uri),
                        edits=[
                            lsp.TextEdit(
                                range=lsp.Range(
                                    start=lsp.Position(line=0, character=0),
                                    end=lsp.Position(line=0, character=0),
                                ),
                                new_text="//@version=6\n",
                            )
                        ],
                    )
                ]
            ),
            is_preferred=True,
        )

    if warning.code == "W002":
        edit = _w002_pragma_replace_edit(source, warning)
        if edit is None:
            return None
        return lsp.CodeAction(
            title="Replace @version with 6",
            kind=lsp.CodeActionKind.QuickFix,
            edit=lsp.WorkspaceEdit(
                document_changes=[
                    lsp.TextDocumentEdit(
                        text_document=lsp.OptionalVersionedTextDocumentIdentifier(uri=uri),
                        edits=[edit],
                    )
                ]
            ),
            is_preferred=True,
        )

    if warning.code == "W104":
        edit = _removed_kwarg_edit(source, warning, tree)
        if edit is None:
            return None
        return _single_edit_action("Remove removed v6 argument", uri, edit)

    if warning.code == "W105":
        edit = _numeric_condition_edit(source, warning, tree)
        if edit is None:
            return None
        return _single_edit_action("Compare numeric condition with 0", uri, edit)

    if warning.code == "C002":
        edits = handle_formatting(
            lsp.DocumentFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri=uri),
                options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
            ),
            source,
        )
        if not edits:
            return None
        return lsp.CodeAction(
            title="Format document",
            kind=lsp.CodeActionKind.QuickFix,
            edit=lsp.WorkspaceEdit(
                document_changes=[
                    lsp.TextDocumentEdit(
                        text_document=lsp.OptionalVersionedTextDocumentIdentifier(uri=uri),
                        edits=list(edits),
                    )
                ]
            ),
        )

    return None


def _w002_pragma_replace_edit(source: str, warning: LintWarning) -> lsp.TextEdit | None:
    """Replace the existing ``//@version=N`` line with ``//@version=6``.

    Prefers the warning's line when that line holds a pragma; otherwise the
    first pragma match in *source*. Returns None when no pragma is found so
    the fix never inserts a second declaration.
    """
    if not source:
        return None
    lines = source.split("\n")
    line_index: int | None = None
    if warning.line is not None:
        idx = max(0, warning.line - 1)
        if 0 <= idx < len(lines) and _VERSION_PRAGMA_RE.search(lines[idx]):
            line_index = idx
    if line_index is None:
        match = _VERSION_PRAGMA_RE.search(source)
        if not match:
            return None
        line_index = source[: match.start()].count("\n")
    if line_index >= len(lines):
        return None
    line_text = lines[line_index]
    return lsp.TextEdit(
        range=lsp.Range(
            start=lsp.Position(line=line_index, character=0),
            end=lsp.Position(line=line_index, character=len(line_text)),
        ),
        new_text="//@version=6",
    )


def _single_edit_action(title: str, uri: str, edit: lsp.TextEdit) -> lsp.CodeAction:
    """Wrap one text edit in a preferred QuickFix CodeAction."""
    return lsp.CodeAction(
        title=title,
        kind=lsp.CodeActionKind.QuickFix,
        edit=lsp.WorkspaceEdit(
            document_changes=[
                lsp.TextDocumentEdit(
                    text_document=lsp.OptionalVersionedTextDocumentIdentifier(uri=uri),
                    edits=[edit],
                )
            ]
        ),
        is_preferred=True,
    )


def _removed_kwarg_edit(source: str, warning: LintWarning, tree: Any | None) -> lsp.TextEdit | None:
    """Remove the v6-removed named argument described by a W104 warning."""
    if tree is None or warning.line is None:
        return None
    match = re.search(r"'([A-Za-z_]\w*)='", warning.message or "")
    if match is None:
        return None
    name = match.group(1)
    for call in walk(tree):
        if not isinstance(call, ast.Call) or getattr(call, "lineno", None) != warning.line:
            continue
        args = [arg for arg in (call.args or []) if getattr(arg, "value", None) is not None]
        for index, arg in enumerate(args):
            if getattr(arg, "name", None) != name:
                continue
            edit = _argument_removal_edit(source, args, index)
            if edit is not None and _edit_parses(source, edit):
                return edit
    return None


def _argument_removal_edit(source: str, args: list[Any], index: int) -> lsp.TextEdit | None:
    """Build an edit that deletes ``args[index]`` and one separating comma."""
    lines = source.split("\n")
    start = _arg_start(lines, args[index])
    end = _arg_end(args[index])
    if start is None or end is None:
        return None
    start_point = start
    if index + 1 < len(args):
        # Remove through the start of the next argument: the comma and any
        # whitespace/newline between them disappear with it.
        next_start = _arg_start(lines, args[index + 1])
        if next_start is None:
            return None
        end_point = next_start
    else:
        if index > 0:
            previous_end = _arg_end(args[index - 1])
            if previous_end is None:
                return None
            comma = _first_comma(lines, previous_end, start)
            if comma is None:
                return None
            start_point = _trim_left(lines, comma)
        end_point = end
    removed = _span_text(lines, start_point, end_point)
    if "//" in removed or "/*" in removed:
        # Never trade a lint fix for a deleted comment.
        return None
    return lsp.TextEdit(range=_range_between(start_point, end_point), new_text="")


def _arg_start(lines: list[str], arg: Any) -> tuple[int, int] | None:
    """Start of an argument, including its ``name=`` prefix when present."""
    value = getattr(arg, "value", None)
    line = getattr(value, "lineno", None)
    column = getattr(value, "col_offset", None)
    if line is None or column is None:
        return None
    line_index = int(line) - 1
    column = int(column)
    name = getattr(arg, "name", None)
    if name and 0 <= line_index < len(lines):
        text = lines[line_index]
        name_start = text.rfind(name, 0, column)
        if name_start >= 0 and text[name_start + len(name) : column].strip() == "=":
            return (line_index, name_start)
    return (line_index, column)


def _arg_end(arg: Any) -> tuple[int, int] | None:
    """End of an argument's value expression."""
    value = getattr(arg, "value", None)
    line = getattr(value, "end_lineno", None)
    column = getattr(value, "end_col_offset", None)
    if line is None or column is None:
        return None
    return (int(line) - 1, int(column))


def _first_comma(lines: list[str], start: tuple[int, int], end: tuple[int, int]) -> tuple[int, int] | None:
    """First comma between *start* and *end* (both 0-based positions)."""
    start_line, start_col = start
    end_line, end_col = end
    if start_line == end_line:
        index = lines[start_line].find(",", start_col, end_col)
        return (start_line, index) if index >= 0 else None
    index = lines[start_line].find(",", start_col)
    if index >= 0:
        return (start_line, index)
    for line_index in range(start_line + 1, end_line):
        index = lines[line_index].find(",")
        if index >= 0:
            return (line_index, index)
    index = lines[end_line].find(",", 0, end_col)
    return (end_line, index) if index >= 0 else None


def _span_text(lines: list[str], start: tuple[int, int], end: tuple[int, int]) -> str:
    """Text between two 0-based positions (newline-joined)."""
    start_line, start_col = start
    end_line, end_col = end
    if start_line == end_line:
        return lines[start_line][start_col:end_col]
    parts = [lines[start_line][start_col:]]
    parts.extend(lines[start_line + 1 : end_line])
    parts.append(lines[end_line][:end_col])
    return "\n".join(parts)


def _trim_left(lines: list[str], point: tuple[int, int]) -> tuple[int, int]:
    """Move *point* left over spaces/tabs so removal does not leave a gap."""
    line_index, column = point
    text = lines[line_index]
    while column > 0 and text[column - 1] in " \t":
        column -= 1
    return (line_index, column)


def _numeric_condition_edit(
    source: str,
    warning: LintWarning,
    tree: Any | None,
) -> lsp.TextEdit | None:
    """Rewrite a numeric boolean condition as ``literal != 0``."""
    if tree is None or warning.line is None:
        return None
    lines = source.split("\n")
    line_index = int(warning.line) - 1
    if not (0 <= line_index < len(lines)):
        return None
    for node in walk(tree):
        if not isinstance(node, (ast.If, ast.While, ast.Conditional)):
            continue
        test = getattr(node, "test", None)
        if not isinstance(test, ast.Constant):
            continue
        if isinstance(test.value, bool) or not isinstance(test.value, (int, float)):
            continue
        if getattr(test, "lineno", None) != warning.line:
            continue
        column = getattr(test, "col_offset", None)
        if column is None:
            continue
        column = int(column)
        if warning.column is not None and column != int(warning.column):
            continue
        end_column = getattr(test, "end_col_offset", None)
        end_column = int(end_column) if end_column is not None else column + 1
        literal = lines[line_index][column:end_column]
        if not re.fullmatch(r"\d[\d_]*(?:\.\d[\d_]*)?", literal):
            continue
        edit = lsp.TextEdit(
            range=_range_between((line_index, column), (line_index, end_column)),
            new_text=f"{literal} != 0",
        )
        if _edit_parses(source, edit):
            return edit
    return None


def _range_between(start: tuple[int, int], end: tuple[int, int]) -> lsp.Range:
    return lsp.Range(
        start=lsp.Position(line=start[0], character=start[1]),
        end=lsp.Position(line=end[0], character=end[1]),
    )


def _edit_parses(source: str, edit: lsp.TextEdit) -> bool:
    """True when applying *edit* still parses (never offer a broken fix)."""
    try:
        parse(_apply_text_edit(source, edit))
    except Exception:
        return False
    return True


def _apply_text_edit(source: str, edit: lsp.TextEdit) -> str:
    lines = source.split("\n")

    def offset(line: int, character: int) -> int:
        line = max(0, min(line, len(lines) - 1))
        return sum(len(text) + 1 for text in lines[:line]) + min(max(0, character), len(lines[line]))

    start = offset(edit.range.start.line, edit.range.start.character)
    end = offset(edit.range.end.line, edit.range.end.character)
    if end < start:
        start, end = end, start
    return source[:start] + edit.new_text + source[end:]


def create_diagnostic_related_info(
    warning: LintWarning,
) -> list[lsp.DiagnosticRelatedInformation]:
    """Create related information for a diagnostic.

    Args:
        warning: The lint warning.

    Returns:
        List of related information.
    """
    info = []

    if warning.code == "E001":
        info.append(
            lsp.DiagnosticRelatedInformation(
                location=lsp.Location(
                    uri="builtin://pinescript/docs",
                    range=lsp.Range(
                        start=lsp.Position(line=0, character=0),
                        end=lsp.Position(line=0, character=0),
                    ),
                ),
                message="Check the Pine Script language reference for correct syntax.",
            )
        )

    return info
