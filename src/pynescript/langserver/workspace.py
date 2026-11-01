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
from urllib.parse import unquote
from urllib.parse import urlparse

from lsprotocol import types as lsp

from pynescript.ast import parse
from pynescript.ast.linter import LintWarning
from pynescript.ast.linter import lint_script
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import build_symbol_index
from pynescript.langserver.features import semantic_diagnostics
from pynescript.langserver.features.diagnostics import lint_warnings_to_diagnostics
from pynescript.langserver.protocol.utils import codepoint_column_to_utf16
from pynescript.langserver.protocol.utils import utf16_column_to_codepoint


# Style-only rules. The language server can hide these by default; the linter
# still emits them for CLI users and for editors that opt in.
_STYLE_CODES = frozenset({"C001", "C002", "C004"})


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
        parse_error_details: Structured ``SyntaxErrorDetails`` when available.
        ast_version: Document version that produced ``ast``. ``valid_ast``
            returns ``None`` when this differs from :attr:`version`, which
            prevents features from mixing new text with old positions while a
            debounced parse is in flight.
        analysis: Static symbol/scope index for ``ast`` (see
            :mod:`pynescript.langserver.analysis`).
    """

    uri: str
    source: str
    version: int = 1
    ast: Any | None = None
    diagnostics: list[LintWarning] = field(default_factory=list)
    parse_error: str | None = None
    parse_error_line: int | None = None
    parse_error_details: Any | None = None
    ast_version: int = 0
    analysis: SymbolIndex | None = None
    # Feature-level memo (semantic tokens, inlay hints, hover decl maps…).
    # Cleared whenever source/AST changes; keys are feature-defined strings.
    feature_cache: dict[str, Any] = field(default_factory=dict)

    @property
    def valid_ast(self) -> Any | None:
        """AST only when it matches the current document version."""
        return self.ast if self.ast_version == self.version else None

    @property
    def valid_analysis(self) -> SymbolIndex | None:
        """Symbol index only when it matches the current document version."""
        return self.analysis if self.ast_version == self.version else None

    @property
    def has_astral(self) -> bool:
        """True when the buffer contains non-BMP characters (UTF-16 differs)."""
        cached = self.feature_cache.get("has_astral")
        if cached is None:
            cached = any(ord(char) > 0xFFFF for char in self.source)
            self.feature_cache["has_astral"] = cached
        return bool(cached)

    @property
    def path(self) -> Path | None:
        """Filesystem path for ``file://`` URIs; otherwise ``None``.

        Handles percent-encoding (``%20``) and Windows drive letters.
        """
        parsed = urlparse(self.uri)
        if parsed.scheme != "file":
            return None
        path = unquote(parsed.path)
        if parsed.netloc and parsed.netloc not in ("", "localhost"):
            # UNC path: file://server/share/file
            path = f"//{parsed.netloc}{path}"
        if len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return Path(path)


class Workspace:
    """URI-keyed store of open documents with parse/lint cache.

    Public surface used by the server:

    - :meth:`get_document` / :meth:`get_source` / :attr:`documents`
    - :meth:`list_open_documents` — snapshot of currently open states
    - :meth:`put_document` / :meth:`update_document` / :meth:`remove_document`
    - :meth:`get_all_diagnostics` — LSP diagnostics for every open URI
    """

    def __init__(self, *, style_diagnostics: bool = True, semantic_diagnostics: bool = False) -> None:
        """Create an empty document store.

        Args:
            style_diagnostics: Publish C001/C002/C004 findings. The VS Code
                extension defaults this off to keep the Problems panel focused
                on correctness.
            semantic_diagnostics: Publish opt-in S001/S002 checks (unknown
                user-type/enum members and user-function arity). Off by
                default: under-report rather than guess.
        """
        self._documents: dict[str, TextDocumentState] = {}
        self._parse_errors: set[str] = set()
        self.style_diagnostics = style_diagnostics
        self.semantic_diagnostics = semantic_diagnostics

    def get_document(self, uri: str) -> TextDocumentState | None:
        """Return state for *uri*, or ``None`` if not open."""
        return self._documents.get(uri)

    def get_source(self, uri: str) -> str | None:
        """Return buffer text for *uri*, or ``None`` if not open."""
        doc = self._documents.get(uri)
        return doc.source if doc else None

    def list_open_documents(self) -> list[TextDocumentState]:
        """Return a snapshot of currently open document states."""
        return list(self._documents.values())

    def put_document(self, uri: str, source: str, version: int = 1, *, parse: bool = True) -> TextDocumentState:
        """Insert or replace a document, then parse and lint.

        Pass ``parse=False`` for very large buffers; the caller can run
        :meth:`_parse_and_lint` on a worker thread so the event loop stays
        responsive. ``valid_ast``/``valid_analysis`` stay ``None`` until then.
        """
        doc = TextDocumentState(
            uri=uri,
            source=source,
            version=version,
        )
        self._documents[uri] = doc
        if parse:
            self._parse_and_lint(doc)
        return doc

    def _invalidate_feature_cache(self, doc: TextDocumentState) -> None:
        """Drop per-version feature results after a source/AST change."""
        doc.feature_cache.clear()

    def remove_document(self, uri: str) -> None:
        """Drop *uri* from the workspace (no-op if missing)."""
        self._documents.pop(uri, None)
        self._parse_errors.discard(uri)

    def update_document(
        self,
        uri: str,
        changes: list[lsp.TextDocumentContentChangeEvent],
        version: int,
        relint: bool = True,
    ) -> TextDocumentState:
        """Apply full-document or incremental LSP content changes, then re-lint.

        Skips re-parse/lint when the buffer text is unchanged (version-only
        bumps or no-op edits) so large docs are not re-parsed for free.
        With ``relint=False`` only the text/version are applied — the caller
        schedules the parse+lint itself (e.g. debounced and off-loop).

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
            self._invalidate_feature_cache(doc)
            if relint:
                self._parse_and_lint(doc)
        else:
            # Version-only bump: the cached AST/index still describes this text.
            doc.ast_version = version
        return doc

    def _parse_and_lint(self, doc: TextDocumentState) -> None:
        """Parse the document and run the linter.

        Captures ``source``/``version`` before parsing and commits results only
        if the document is still at that version. This closes the race where a
        cancelled debounce task (or a slow executor job) writes an AST for an
        older buffer after the user has typed again.
        """
        source = doc.source
        version = doc.version
        self._invalidate_feature_cache(doc)
        try:
            tree = parse(source, filename=doc.uri)
            diagnostics = lint_script(source, filename=doc.uri, tree=tree)
        except Exception as e:
            if doc.version != version or doc.source != source:
                return
            doc.ast = None
            doc.ast_version = version
            doc.analysis = None
            doc.parse_error = _short_parse_error(e)
            doc.parse_error_details = getattr(e, "details", None)
            doc.parse_error_line = self._extract_error_line(str(e))
            doc.diagnostics = []
            self._parse_errors.add(doc.uri)
            return

        if doc.version != version or doc.source != source:
            # A newer edit won; leave the newer document state untouched.
            return
        doc.ast = tree
        doc.ast_version = version
        doc.analysis = build_symbol_index(tree, source, doc.uri)
        doc.parse_error = None
        doc.parse_error_line = None
        doc.parse_error_details = None
        # Reuse the fresh tree; lint_script would otherwise re-parse.
        doc.diagnostics = diagnostics
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
        """Convert LintWarning objects to LSP Diagnostic objects.

        Style-only findings are filtered when ``style_diagnostics`` is off.
        Parse errors use the structured ANTLR location when available and are
        clamped to a non-empty range so editors can underline the right token.
        """
        warnings = doc.diagnostics
        if not self.style_diagnostics:
            warnings = [warning for warning in warnings if warning.code not in _STYLE_CODES]
        diagnostics = lint_warnings_to_diagnostics(warnings, doc.source)

        if self.semantic_diagnostics:
            diagnostics.extend(semantic_diagnostics.collect(doc.valid_analysis))

        if doc.parse_error:
            rng = _parse_error_range(doc.source, doc.parse_error_details, doc.parse_error_line)
            diag = lsp.Diagnostic(
                range=rng,
                severity=lsp.DiagnosticSeverity.Error,
                message=doc.parse_error,
                source="pyne",
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
    end_line_index = max(0, (warning.end_line or warning.line) - 1)
    if warning.end_column is not None and end_line_index == line_index:
        end_column = warning.end_column
    elif line_text:
        end_column = len(line_text)
    else:
        end_column = column + 1
    # Never emit an inverted or zero-width range unless the token is at EOL.
    if end_line_index == line_index and end_column <= column:
        end_column = min(max(column + 1, 1), max(len(line_text), 1))
    end_column = min(end_column, 2000)

    content = line_text[:-1] if line_text.endswith("\r") else line_text
    if content:
        column = min(max(0, column), len(content))
        end_column = min(max(column, end_column), len(content))
        column = codepoint_column_to_utf16(content, column)
        end_column = codepoint_column_to_utf16(content, end_column)
    else:
        column = 0
        end_column = max(1, end_column)

    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(line=line_index, character=column),
            end=lsp.Position(line=end_line_index, character=end_column),
        ),
        severity=severity,
        message=warning.message,
        source="pyne",
        code=warning.code,
    )


def _short_parse_error(error: Exception) -> str:
    """Return the parser's short message without the caret dump."""
    message = getattr(error, "message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()
    return str(error).split("\n", 1)[0].strip() or str(error)


def _parse_error_range(
    source: str,
    details: Any | None,
    fallback_line: int | None,
) -> lsp.Range:
    """Build a non-empty LSP range from structured parse-error details.

    ANTLR reports EOF errors on the line *after* the last source line with an
    empty text. Clamp those to the last non-empty line and highlight its end so
    the editor does not place a zero-width error in blank space.
    """
    lines = source.split("\n") if source else [""]
    lineno = getattr(details, "lineno", None) or fallback_line or 1
    column = getattr(details, "offset", None)
    end_lineno = getattr(details, "end_lineno", None)
    end_column = getattr(details, "end_offset", None)

    line_index = max(0, int(lineno) - 1)
    if line_index >= len(lines) or not lines[line_index].strip():
        # EOF / blank line: prefer the last line that has content.
        for candidate in range(min(line_index, len(lines) - 1), -1, -1):
            if lines[candidate].strip():
                line_index = candidate
                column = len(lines[candidate].rstrip("\r"))
                end_lineno = None
                end_column = None
                break
        else:
            line_index = 0
            column = 0

    start_col = max(0, int(column or 0))
    line_text = lines[line_index] if 0 <= line_index < len(lines) else ""
    start_col = min(start_col, len(line_text))

    end_index = max(0, int(end_lineno or (line_index + 1)) - 1)
    end_col = int(end_column or 0)
    if end_index != line_index:
        end_index = line_index
        end_col = len(line_text)
    end_col = min(end_col, len(line_text))
    if end_col <= start_col:
        end_col = min(len(line_text), start_col + 1)
    if end_col <= start_col and line_text:
        # EOF errors point at the end of the last non-empty line. Highlight the
        # final character instead of emitting a zero-width diagnostic.
        start_col = max(0, len(line_text.rstrip("\r")) - 1)
        end_col = len(line_text.rstrip("\r"))
    # Empty line at EOF: keep a one-character range within the line.
    end_col = max(start_col, end_col)

    content = line_text[:-1] if line_text.endswith("\r") else line_text
    if content:
        start_col = codepoint_column_to_utf16(content, min(start_col, len(content)))
        end_col = codepoint_column_to_utf16(content, min(end_col, len(content)))
    else:
        start_col = 0
        end_col = max(1, end_col)

    return lsp.Range(
        start=lsp.Position(line=line_index, character=start_col),
        end=lsp.Position(line=end_index, character=end_col),
    )


def _utf16_column_to_index(line: str, column: int) -> int:
    """Convert an LSP UTF-16 column to a Python index (CR excluded)."""
    content = line[:-1] if line.endswith("\r") else line
    return utf16_column_to_codepoint(content, column)


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
    # LSP columns exclude the line terminator, so a trailing ``\r`` must not
    # consume a column when clamping (otherwise CRLF edits land after the CR).
    # LSP counts UTF-16 code units; convert to Python code points so an emoji
    # earlier on the line cannot shift the edit into the wrong character.
    start_col = _utf16_column_to_index(lines[start_line], start_col)
    end_col = _utf16_column_to_index(lines[end_line], end_col)

    start_str = lines[start_line][:start_col]
    end_str = lines[end_line][end_col:]
    lines[start_line] = start_str + text + end_str

    if end_line > start_line:
        del lines[start_line + 1 : end_line + 1]

    return "\n".join(lines)
