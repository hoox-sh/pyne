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

from lsprotocol import types as lsp

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


def create_quick_fix(warning: LintWarning, uri: str, source: str) -> lsp.CodeAction | None:
    """Create a CodeAction for a lint warning.

    W001 inserts ``//@version=6``. W002 replaces an old pragma. C002 applies
    the same whole-document edit as
    :func:`~pynescript.langserver.features.formatting.handle_formatting`
    (or ``None`` when parse fails or the buffer is already canonical).

    Args:
        warning: The lint warning.
        uri: The document URI.
        source: The source text.

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
