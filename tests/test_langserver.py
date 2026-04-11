# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Tests for the LSP workspace and diagnostics."""

from __future__ import annotations

import pytest

from pynescript.langserver.workspace import Workspace, TextDocumentState
from pynescript.langserver.features.diagnostics import lint_warnings_to_diagnostics


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
        from lsprotocol import types as lsp

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
        from pynescript.langserver.features.diagnostics import (
            lint_warnings_to_diagnostics,
        )

        source = "indicator('Test')\n"
        warnings = lint_script(source)
        diagnostics = lint_warnings_to_diagnostics(warnings, source)

        assert len(diagnostics) > 0
        from lsprotocol import types as lsp

        assert diagnostics[0].severity == lsp.DiagnosticSeverity.Warning
