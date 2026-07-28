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

"""Document workspace manager.

Tracks open documents, caches parsed ASTs, and manages document state.
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
    """Holds parsed state for a single document."""

    uri: str
    source: str
    version: int = 1
    ast: Any | None = None
    diagnostics: list[LintWarning] = field(default_factory=list)
    parse_error: str | None = None
    parse_error_line: int | None = None

    @property
    def path(self) -> Path | None:
        """Get the file path from the URI."""
        if self.uri.startswith("file://"):
            return Path(self.uri[7:])
        return None


class Workspace:
    """Manages the document workspace.

    Tracks open documents, caches ASTs, and handles document change events.
    """

    def __init__(self) -> None:
        self._documents: dict[str, TextDocumentState] = {}
        self._parse_errors: set[str] = set()

    def get_document(self, uri: str) -> TextDocumentState | None:
        """Get a document by URI."""
        return self._documents.get(uri)

    def get_source(self, uri: str) -> str | None:
        """Get the source text for a document."""
        doc = self._documents.get(uri)
        return doc.source if doc else None

    def put_document(self, uri: str, source: str, version: int = 1) -> TextDocumentState:
        """Add or update a document."""
        existing = self._documents.get(uri)
        doc = TextDocumentState(
            uri=uri,
            source=source,
            version=version,
        )
        self._documents[uri] = doc
        self._parse_and_lint(doc)
        return doc

    def remove_document(self, uri: str) -> None:
        """Remove a document from the workspace."""
        self._documents.pop(uri, None)

    def update_document(
        self, uri: str, changes: list[lsp.TextDocumentContentChangeEvent], version: int
    ) -> TextDocumentState:
        """Apply incremental changes to a document."""
        doc = self._documents.get(uri)
        if not doc:
            raise ValueError(f"Document {uri} not found in workspace")

        for change in changes:
            if isinstance(change, lsp.TextDocumentContentChangeWholeDocument):
                doc.source = change.text
            elif hasattr(change, "range") and change.range is None:
                doc.source = change.text
            else:
                doc.source = _apply_text_edit(doc.source, change.range, change.text)

        doc.version = version
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
        """Get all documents in the workspace."""
        return self._documents

    def get_all_diagnostics(self) -> dict[str, list[lsp.Diagnostic]]:
        """Get LSP diagnostics for all documents."""
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
    )


def _apply_text_edit(source: str, range: lsp.Range, text: str) -> str:
    """Apply a text edit to the source."""
    lines = source.split("\n")

    start_line = range.start.line
    start_col = range.start.character
    end_line = range.end.line
    end_col = range.end.character

    if start_line >= len(lines) or end_line >= len(lines):
        return source

    start_str = lines[start_line][:start_col]
    end_str = lines[end_line][end_col:]
    lines[start_line] = start_str + text + end_str

    if end_line > start_line:
        del lines[start_line + 1 : end_line + 1]

    return "\n".join(lines)
