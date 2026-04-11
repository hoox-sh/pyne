# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Diagnostics feature — lint warnings to LSP diagnostics conversion.

This module handles textDocument/publishDiagnostics and pull diagnostics.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.ast.linter import LintWarning


def lint_warnings_to_diagnostics(warnings: list[LintWarning], source: str) -> list[lsp.Diagnostic]:
    """Convert LintWarning objects to LSP Diagnostic objects.

    Args:
        warnings: List of lint warnings from PineLinter.
        source: The source text for line-based conversions.

    Returns:
        List of LSP Diagnostic objects.
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
    severity = _severity_to_lsp(warning.severity)
    line_index = max(0, (warning.line or 1) - 1) if warning.line else 0
    column = warning.column if warning.column is not None else 0

    line_text = _get_line_text(source, line_index)
    end_column = min(column + len(line_text) if line_text else column + 10, 2000)

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
            title="Add @version=5 declaration",
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
                                new_text="//@version=5\n",
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
