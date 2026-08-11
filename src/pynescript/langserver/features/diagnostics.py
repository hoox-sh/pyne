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

from lsprotocol import types as lsp

from pynescript.ast.linter import LintWarning


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

    for warning in warnings:
        diag = _lint_warning_to_diagnostic(warning, source)
        if diag:
            diagnostics.append(diag)

    return diagnostics


def _lint_warning_to_diagnostic(warning: LintWarning, source: str) -> lsp.Diagnostic | None:
    """Convert a single LintWarning to an LSP Diagnostic.

    Args:
        warning: The lint warning to convert.
        source: The source text for determining line text.

    Returns:
        LSP Diagnostic object or None if the warning can't be converted.
    """
    if warning.line is None:
        return None

    severity = _severity_to_lsp(warning.severity)
    line_index = max(0, warning.line - 1)
    column = warning.column if warning.column is not None else 0

    line_text = _get_line_text(source, line_index)
    # Highlight from column to end of line (not column + line_len, which overshoots).
    if line_text:
        end_column = max(column + 1, len(line_text))
    else:
        end_column = column + 1
    end_column = min(end_column, 2000)

    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(line=line_index, character=column),
            end=lsp.Position(line=line_index, character=end_column),
        ),
        severity=severity,
        message=warning.message,
        source="PineScript",
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
    if code.startswith("E"):
        return lsp.CodeDescription(href="https://docs.pynescript.ai/errors")
    if code.startswith("W"):
        return lsp.CodeDescription(href="https://docs.pynescript.ai/warnings")
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

    if code == "W001":
        return [lsp.DiagnosticTag.Unnecessary]

    return None


def create_quick_fix(warning: LintWarning, uri: str, source: str) -> lsp.CodeAction | None:
    """Create a CodeAction for a lint warning.

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

    if warning.code == "C002":
        line_index = max(0, (warning.line or 1) - 1)
        line_text = _get_line_text(source, line_index)

        if len(line_text) > 120:
            return lsp.CodeAction(
                title="Split long line",
                kind=lsp.CodeActionKind.Refactor,
                command=lsp.Command(
                    title="Format document",
                    command="editor.action.formatDocument",
                ),
            )

    return None


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
