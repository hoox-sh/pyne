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

"""In-memory workspace for open Pine Script documents.

The Language Server keeps one :class:`Workspace` on
:attr:`~pynescript.langserver.server.PynescriptLanguageServer.pine_workspace`.
On open/change it parses with :func:`pynescript.ast.parse` and lints with
:func:`pynescript.ast.linter.lint_script`, storing results on
:class:`TextDocumentState`.

Feature handlers typically call :meth:`Workspace.get_source` and re-parse if
needed; diagnostics are converted to LSP via :meth:`Workspace.get_all_diagnostics`
/ internal ``_lint_warnings_to_diagnostics`` (publish + pull paths in
:mod:`pynescript.langserver.server`).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import parse
from pynescript.ast.linter import LintWarning
from pynescript.ast.linter import lint_script


@dataclass
class TextDocumentState:
    """Cached parse/lint state for a single open document URI.

    Attributes:
        uri: Document URI (usually ``file://…``).
        source: Current buffer text.
        version: LSP textDocument version.
        ast: Parsed AST, or ``None`` if the last parse failed.
        diagnostics: :class:`~pynescript.ast.linter.LintWarning` list (not LSP types).
        parse_error: Human-readable parse failure message when ``ast`` is ``None``.
        parse_error_line: 1-based line from the error string, if detected.
    """

    uri: str
    source: str
    version: int = 1
    ast: Any | None = None
    diagnostics: list[LintWarning] = field(default_factory=list)
    parse_error: str | None = None
    parse_error_line: int | None = None

    @property
    def path(self) -> Path | None:
        """Filesystem path for ``file://`` URIs; otherwise ``None``."""
        if self.uri.startswith("file://"):
            return Path(self.uri[7:])
        return None


class Workspace:
    """URI-keyed store of open documents with parse/lint cache.

    Public surface used by the server:

    - :meth:`get_document` / :meth:`get_source` / :attr:`documents`
    - :meth:`put_document` / :meth:`update_document` / :meth:`remove_document`
    - :meth:`get_all_diagnostics` — LSP diagnostics for every open URI
    """

    def __init__(self) -> None:
        """Create an empty document store."""
        self._documents: dict[str, TextDocumentState] = {}
        self._parse_errors: set[str] = set()

    def get_document(self, uri: str) -> TextDocumentState | None:
        """Return state for *uri*, or ``None`` if not open."""
        return self._documents.get(uri)

    def get_source(self, uri: str) -> str | None:
        """Return buffer text for *uri*, or ``None`` if not open."""
        doc = self._documents.get(uri)
        return doc.source if doc else None

    def put_document(self, uri: str, source: str, version: int = 1) -> TextDocumentState:
        """Insert or replace a document, then parse and lint."""
        doc = TextDocumentState(
            uri=uri,
            source=source,
            version=version,
        )
        self._documents[uri] = doc
        self._parse_and_lint(doc)
        return doc

    def remove_document(self, uri: str) -> None:
        """Drop *uri* from the workspace (no-op if missing)."""
        self._documents.pop(uri, None)

    def update_document(
        self, uri: str, changes: list[lsp.TextDocumentContentChangeEvent], version: int
    ) -> TextDocumentState:
        """Apply full-document or incremental LSP content changes, then re-lint.

        Skips re-parse/lint when the buffer text is unchanged (version-only
        bumps or no-op edits) so large docs are not re-parsed for free.

        Raises:
            ValueError: If *uri* is not in the workspace.
        """
        doc = self._documents.get(uri)
        if not doc:
            raise ValueError(f"Document {uri} not found in workspace")

        previous_source = doc.source
        for change in changes:
            if isinstance(change, lsp.TextDocumentContentChangeWholeDocument):
                doc.source = change.text
            elif hasattr(change, "range") and change.range is None:
                doc.source = change.text
            else:
                doc.source = _apply_text_edit(doc.source, change.range, change.text)

        doc.version = version
        # Correctness: only skip when text is identical. Version is still updated.
        if doc.source != previous_source:
            self._parse_and_lint(doc)
        return doc

    def _parse_and_lint(self, doc: TextDocumentState) -> None:
        """Parse the document and run the linter."""
        try:
            doc.ast = parse(doc.source, filename=doc.uri)
            doc.parse_error = None
            doc.parse_error_line = None
            doc.diagnostics = lint_script(doc.source, filename=doc.uri)
        except Exception as e:
            doc.ast = None
            doc.parse_error = str(e)
            doc.parse_error_line = self._extract_error_line(str(e))
            doc.diagnostics = []
            self._parse_errors.add(doc.uri)
        else:
            self._parse_errors.discard(doc.uri)

    def _extract_error_line(self, error_msg: str) -> int | None:
        """Extract line number from a parse error message."""
        import re

        match = re.search(r"line[:\s]+(\d+)", error_msg, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    @property
    def documents(self) -> dict[str, TextDocumentState]:
        """Live mapping of URI → :class:`TextDocumentState` (do not replace wholesale)."""
        return self._documents

    def get_all_diagnostics(self) -> dict[str, list[lsp.Diagnostic]]:
        """Map each open URI to LSP diagnostics (lint + parse error)."""
        result = {}
        for uri, doc in self._documents.items():
            result[uri] = self._lint_warnings_to_diagnostics(doc)
        return result

    def _lint_warnings_to_diagnostics(self, doc: TextDocumentState) -> list[lsp.Diagnostic]:
        """Convert LintWarning objects to LSP Diagnostic objects."""
        diagnostics = []

        for warning in doc.diagnostics:
            diag = _lint_warning_to_diagnostic(warning, doc.source)
            if diag:
                diagnostics.append(diag)

        if doc.parse_error:
            diag = lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(
                        line=max(0, (doc.parse_error_line or 1) - 1),
                        character=0,
                    ),
                    end=lsp.Position(
                        line=max(0, (doc.parse_error_line or 1) - 1),
                        character=0,
                    ),
                ),
                severity=lsp.DiagnosticSeverity.Error,
                message=doc.parse_error,
                source="PineScript",
                code="E001",
            )
            diagnostics.append(diag)

        return diagnostics


def _lint_warning_to_diagnostic(warning: LintWarning, source: str) -> lsp.Diagnostic | None:
    """Convert a LintWarning to an LSP Diagnostic."""
    if warning.line is None:
        return None

    line_index = max(0, warning.line - 1)
    line_text = ""
    if source:
        lines = source.split("\n")
        if line_index < len(lines):
            line_text = lines[line_index]

    severity_map = {
        "error": lsp.DiagnosticSeverity.Error,
        "warning": lsp.DiagnosticSeverity.Warning,
        "info": lsp.DiagnosticSeverity.Information,
        "hint": lsp.DiagnosticSeverity.Hint,
    }
    severity = severity_map.get(warning.severity, lsp.DiagnosticSeverity.Warning)

    column = warning.column if warning.column is not None else 0
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
    )


def _apply_text_edit(source: str, range: lsp.Range, text: str) -> str:
    """Apply an incremental LSP text edit to *source*.

    Pads the line list when the client range sits at/past the current end of
    the buffer (common for appends on files without a trailing newline). Silent
    no-op on out-of-range positions previously left **stale** buffers after
    ``didChange`` — that is a diagnostics correctness bug.
    """
    lines = source.split("\n")

    start_line = max(0, range.start.line)
    start_col = max(0, range.start.character)
    end_line = max(0, range.end.line)
    end_col = max(0, range.end.character)

    # Ensure line list covers the edit range (EOF append / past-last-line).
    max_line = max(start_line, end_line)
    while len(lines) <= max_line:
        lines.append("")

    # Clamp columns so partial edits never raise; clients may send stale cols.
    start_col = min(start_col, len(lines[start_line]))
    end_col = min(end_col, len(lines[end_line]))

    start_str = lines[start_line][:start_col]
    end_str = lines[end_line][end_col:]
    lines[start_line] = start_str + text + end_str

    if end_line > start_line:
        del lines[start_line + 1 : end_line + 1]

    return "\n".join(lines)
