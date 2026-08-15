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

"""Tests for the LSP workspace and diagnostics."""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.ast.linter import LintWarning
from pynescript.langserver.features.diagnostics import lint_warnings_to_diagnostics
from pynescript.langserver.workspace import Workspace
from pynescript.langserver.workspace import _apply_text_edit
from pynescript.langserver.workspace import _lint_warning_to_diagnostic


class TestWorkspace:
    """Test workspace document management."""

    def test_put_document(self) -> None:
        """Test adding a document to the workspace."""
        ws = Workspace()
        source = "//@version=5\nindicator('Test')\n"
        doc = ws.put_document("test://test.pine", source)

        assert doc.uri == "test://test.pine"
        assert doc.source == source
        assert doc.version == 1
        assert doc.ast is not None
        assert doc.parse_error is None

    def test_update_document(self) -> None:
        """Test updating a document with changes."""
        ws = Workspace()
        original = "//@version=5\nindicator('Test')\n"
        doc = ws.put_document("test://test.pine", original)

        updated = "//@version=5\nindicator('Updated')\n"

        updated_doc = ws.update_document(
            "test://test.pine",
            [lsp.TextDocumentContentChangeWholeDocument(text=updated)],
            version=2,
        )

        assert updated_doc.version == 2
        assert "indicator('Updated')" in updated_doc.source

    def test_remove_document(self) -> None:
        """Test removing a document from the workspace."""
        ws = Workspace()
        ws.put_document("test://test.pine", "//@version=5\n")
        assert "test://test.pine" in ws.documents

        ws.remove_document("test://test.pine")
        assert "test://test.pine" not in ws.documents

    def test_lint_warnings(self) -> None:
        """Test that lint warnings are generated."""
        ws = Workspace()
        source = "indicator('Test')"  # Missing @version
        doc = ws.put_document("test://test.pine", source)

        assert len(doc.diagnostics) > 0
        assert any(d.code == "W001" for d in doc.diagnostics)

    def test_parse_error(self) -> None:
        """Test that parse errors are captured."""
        ws = Workspace()
        source = "this is not valid pine script @#$"
        doc = ws.put_document("test://test.pine", source)

        assert doc.parse_error is not None
        assert doc.ast is None

    def test_diagnostics_clear_after_fix(self) -> None:
        """Parse error diagnostics must not linger after a successful edit."""
        ws = Workspace()
        uri = "test://stale.pine"
        ws.put_document(uri, "indicator('T')\nplot(ta.", version=1)
        doc = ws.get_document(uri)
        assert doc is not None
        assert doc.parse_error is not None
        broken_diags = ws._lint_warnings_to_diagnostics(doc)
        assert any(d.code == "E001" for d in broken_diags)

        fixed = "//@version=5\nindicator('T')\n"
        ws.update_document(
            uri,
            [lsp.TextDocumentContentChangeWholeDocument(text=fixed)],
            version=2,
        )
        doc = ws.get_document(uri)
        assert doc is not None
        assert doc.parse_error is None
        assert doc.ast is not None
        recovered = ws._lint_warnings_to_diagnostics(doc)
        assert not any(d.code == "E001" for d in recovered)

    def test_skip_reparse_when_source_unchanged(self) -> None:
        """No-op content change must not drop the cached AST."""
        ws = Workspace()
        uri = "test://noop.pine"
        source = "//@version=5\nindicator('T')\n"
        doc = ws.put_document(uri, source, version=1)
        cached_ast = doc.ast
        assert cached_ast is not None

        updated = ws.update_document(
            uri,
            [lsp.TextDocumentContentChangeWholeDocument(text=source)],
            version=2,
        )
        assert updated.version == 2
        assert updated.ast is cached_ast  # identity: re-parse was skipped

    def test_incomplete_input_does_not_crash(self) -> None:
        """Mid-edit fragments must yield diagnostics, not exceptions."""
        ws = Workspace()
        fragments = [
            "",
            "//@version=5\nindi",
            "//@version=5\nindicator('T')\nplot(ta.",
            "//@version=5\nindicator('T')\nx = ",
        ]
        for i, fragment in enumerate(fragments):
            doc = ws.put_document(f"test://inc{i}.pine", fragment, version=1)
            # Must always produce a document state; features tolerate None AST.
            assert doc is not None
            _ = ws._lint_warnings_to_diagnostics(doc)


class TestApplyTextEdit:
    """Incremental textDocument/didChange application."""

    def test_partial_replace(self) -> None:
        source = "length = 14\n"
        r = lsp.Range(
            start=lsp.Position(line=0, character=9),
            end=lsp.Position(line=0, character=11),
        )
        assert _apply_text_edit(source, r, "20") == "length = 20\n"

    def test_append_past_last_line_without_trailing_newline(self) -> None:
        """EOF range past last line must apply (previously left stale buffer)."""
        source = "a"
        r = lsp.Range(
            start=lsp.Position(line=1, character=0),
            end=lsp.Position(line=1, character=0),
        )
        assert _apply_text_edit(source, r, "b") == "a\nb"

    def test_multiline_insert(self) -> None:
        source = "a\nc\n"
        r = lsp.Range(
            start=lsp.Position(line=1, character=0),
            end=lsp.Position(line=1, character=0),
        )
        assert _apply_text_edit(source, r, "b\n") == "a\nb\nc\n"


class TestDiagnostics:
    """Test diagnostics conversion."""

    def test_lint_warnings_to_diagnostics(self) -> None:
        """Test converting lint warnings to LSP diagnostics."""
        source = "//@version=5\nindicator('Test')\n"
        warnings = lint_warnings_to_diagnostics([], source)
        assert warnings == []

    def test_warning_severity(self) -> None:
        """Test warning severity mapping."""
        from pynescript.ast.linter import lint_script
        from pynescript.langserver.features.diagnostics import lint_warnings_to_diagnostics

        source = "indicator('Test')\n"
        warnings = lint_script(source)
        diagnostics = lint_warnings_to_diagnostics(warnings, source)

        assert len(diagnostics) > 0
        assert diagnostics[0].severity == lsp.DiagnosticSeverity.Warning

    def test_end_column_does_not_overshoot_line(self) -> None:
        """Diagnostic end character must stay within the line length."""
        source = "0123456789abcdef\n"
        warning = LintWarning(
            code="E999",
            message="boom",
            severity="error",
            line=1,
            column=5,
        )
        diag = _lint_warning_to_diagnostic(warning, source)
        assert diag is not None
        line_len = len(source.split("\n")[0])
        assert diag.range.start.character == 5
        assert diag.range.end.character <= line_len
        assert diag.range.end.character > diag.range.start.character

    def test_warning_without_line_skipped(self) -> None:
        warning = LintWarning(
            code="C004",
            message="File should end with a newline",
            severity="info",
            line=None,
            column=None,
        )
        assert _lint_warning_to_diagnostic(warning, "x\n") is None
        assert lint_warnings_to_diagnostics([warning], "x\n") == []

    def test_c001_skipped_when_already_camel_case(self) -> None:
        """C001 is a false positive for names that are already camelCase."""
        ws = Workspace()
        source = "//@version=6\nindicator('T')\nfastMA = ta.sma(close, 14)\n"
        doc = ws.put_document("test://c001.pine", source)
        diags = ws._lint_warnings_to_diagnostics(doc)
        assert not any(d.code == "C001" for d in diags)

    def test_c001_kept_for_snake_case(self) -> None:
        """C001 still publishes for snake_case ``ta.*`` assignments."""
        ws = Workspace()
        source = "//@version=6\nindicator('T')\nfast_ma = ta.sma(close, 14)\n"
        doc = ws.put_document("test://c001s.pine", source)
        diags = ws._lint_warnings_to_diagnostics(doc)
        assert any(d.code == "C001" for d in diags)

    def test_c003_skipped_for_block_if(self) -> None:
        """Indented multi-line ``if`` is not a single-line-if warning."""
        ws = Workspace()
        source = """//@version=6
indicator('T')
if barstate.isfirst
    if close > open
        x = 1
"""
        doc = ws.put_document("test://c003.pine", source)
        diags = ws._lint_warnings_to_diagnostics(doc)
        assert not any(d.code == "C003" for d in diags)
