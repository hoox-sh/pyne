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

"""Exhaustive unit tests for langserver protocol constants/utils and workspace helpers."""

from __future__ import annotations

import pytest

from lsprotocol import types as lsp

from pynescript.ast.linter import LintWarning
from pynescript.langserver.protocol import constants as proto_constants
from pynescript.langserver.protocol.constants import COMPLETION_ITEM_KINDS
from pynescript.langserver.protocol.constants import DIAGNOSTIC_SEVERITY_MAP
from pynescript.langserver.protocol.constants import SYMBOL_KINDS
from pynescript.langserver.protocol.utils import _is_ascii_ident_cont
from pynescript.langserver.protocol.utils import _is_ascii_ident_start
from pynescript.langserver.protocol.utils import build_filter_text
from pynescript.langserver.protocol.utils import extract_module_prefix
from pynescript.langserver.protocol.utils import get_identifier_segment_at_position
from pynescript.langserver.protocol.utils import get_trigger_char
from pynescript.langserver.protocol.utils import get_word_at_position
from pynescript.langserver.protocol.utils import offset_from_position
from pynescript.langserver.protocol.utils import position_from_offset
from pynescript.langserver.protocol.utils import trailing_ident
from pynescript.langserver.workspace import TextDocumentState
from pynescript.langserver.workspace import Workspace
from pynescript.langserver.workspace import _apply_text_edit
from pynescript.langserver.workspace import _lint_warning_to_diagnostic


# ---------------------------------------------------------------------------
# constants.py
# ---------------------------------------------------------------------------


class TestProtocolConstants:
    def test_diagnostic_severity_map_complete(self) -> None:
        assert DIAGNOSTIC_SEVERITY_MAP["E"] == lsp.DiagnosticSeverity.Error
        assert DIAGNOSTIC_SEVERITY_MAP["W"] == lsp.DiagnosticSeverity.Warning
        assert DIAGNOSTIC_SEVERITY_MAP["C"] == lsp.DiagnosticSeverity.Information
        assert DIAGNOSTIC_SEVERITY_MAP["I"] == lsp.DiagnosticSeverity.Hint
        assert set(DIAGNOSTIC_SEVERITY_MAP) == {"E", "W", "C", "I"}
        assert DIAGNOSTIC_SEVERITY_MAP is proto_constants.DIAGNOSTIC_SEVERITY_MAP

    def test_completion_item_kinds_values(self) -> None:
        expected = {
            "function": lsp.CompletionItemKind.Function,
            "method": lsp.CompletionItemKind.Method,
            "variable": lsp.CompletionItemKind.Variable,
            "type": lsp.CompletionItemKind.TypeParameter,
            "keyword": lsp.CompletionItemKind.Keyword,
            "constant": lsp.CompletionItemKind.Constant,
            "class": lsp.CompletionItemKind.Class,
            "module": lsp.CompletionItemKind.Module,
            "property": lsp.CompletionItemKind.Property,
            "snippet": lsp.CompletionItemKind.Snippet,
        }
        assert COMPLETION_ITEM_KINDS == expected
        assert len(COMPLETION_ITEM_KINDS) == 10

    def test_symbol_kinds_values(self) -> None:
        assert SYMBOL_KINDS["script"] == lsp.SymbolKind.File
        assert SYMBOL_KINDS["function"] == lsp.SymbolKind.Function
        assert SYMBOL_KINDS["type"] == lsp.SymbolKind.Class
        assert SYMBOL_KINDS["variable"] == lsp.SymbolKind.Variable
        assert SYMBOL_KINDS["parameter"] == lsp.SymbolKind.Variable
        assert SYMBOL_KINDS["annotation"] == lsp.SymbolKind.Namespace
        assert set(SYMBOL_KINDS) == {"script", "function", "type", "variable", "parameter", "annotation"}


# ---------------------------------------------------------------------------
# utils.py — positions / offsets
# ---------------------------------------------------------------------------


class TestPositionOffset:
    def test_position_from_offset_basic(self) -> None:
        text = "abc\ndef\nghi"
        assert position_from_offset(text, 0) == (0, 0)
        assert position_from_offset(text, 3) == (0, 3)
        assert position_from_offset(text, 4) == (1, 0)
        assert position_from_offset(text, 5) == (1, 1)
        assert position_from_offset(text, 10) == (2, 2)
        assert position_from_offset(text, 11) == (2, 3)  # past EOF → last line end

    def test_position_from_offset_edges(self) -> None:
        assert position_from_offset("", 0) == (0, 0)
        assert position_from_offset("x", -5) == (0, 0)
        assert position_from_offset("a\nb", 99) == (1, 1)
        assert position_from_offset("only", 4) == (0, 4)

    def test_offset_from_position_roundtrip(self) -> None:
        text = "hello\nworld\n!"
        for off in range(len(text) + 1):
            line, col = position_from_offset(text, off)
            assert offset_from_position(text, line, col) == off

    def test_offset_from_position_clamp(self) -> None:
        text = "ab\ncd"
        assert offset_from_position(text, -1, 0) == 0
        assert offset_from_position(text, 99, 0) == offset_from_position(text, 1, 0)
        assert offset_from_position(text, 0, 99) == 2  # clamped to len(line)
        assert offset_from_position("", 0, 0) == 0


# ---------------------------------------------------------------------------
# utils.py — word / segment / trigger
# ---------------------------------------------------------------------------


class TestWordAndSegment:
    def test_get_word_at_position(self) -> None:
        text = "plot(ta.sma(close, 14))"
        word, start, end = get_word_at_position(text, 0, 7)
        assert word == "ta.sma"
        assert text[start:end] == "ta.sma"
        assert get_word_at_position(text, 0, 0)[0] == "plot"
        assert get_word_at_position(text, 5, 0) == ("", 0, 0)
        assert get_word_at_position(text, -1, 0) == ("", 0, 0)
        assert get_word_at_position("   ", 0, 1) == ("", 1, 1)
        assert get_word_at_position("x", 0, 99) == ("", 99, 99)

    def test_identifier_segment_at_position(self) -> None:
        text = "x = ta.sma(close, 14)"
        # cursor on "ta"
        seg, s, e, full = get_identifier_segment_at_position(text, 0, 5)
        assert seg == "ta" and full == "ta.sma"
        assert text[s:e] == "ta"
        # cursor on "sma"
        seg2, s2, e2, full2 = get_identifier_segment_at_position(text, 0, 8)
        assert seg2 == "sma" and full2 == "ta.sma"
        assert text[s2:e2] == "sma"
        # non-dotted
        seg3, _, _, full3 = get_identifier_segment_at_position("length = 14", 0, 2)
        assert seg3 == full3 == "length"
        # empty
        assert get_identifier_segment_at_position("   ", 0, 1)[0] == ""
        # past last segment boundary still returns last
        text2 = "a.b.c"
        seg4, _, _, full4 = get_identifier_segment_at_position(text2, 0, len(text2))
        assert full4 == "a.b.c"
        assert seg4 == "c"

    def test_get_trigger_char(self) -> None:
        text = "plot(ta."
        assert get_trigger_char(text, 0, len(text)) == "."
        assert get_trigger_char("f(", 0, 2) == "("
        assert get_trigger_char("a,b", 0, 2) == ","
        assert get_trigger_char("a b", 0, 2) == " "
        assert get_trigger_char("ab", 0, 2) is None
        assert get_trigger_char("ab", 0, 0) is None
        assert get_trigger_char("ab", 0, 99) is None
        assert get_trigger_char("ab", -1, 1) is None


class TestTrailingIdentAndFilter:
    def test_trailing_ident_extra_cases(self) -> None:
        assert trailing_ident("request.security") == "request.security"
        assert trailing_ident("(ta.") == "ta."
        assert trailing_ident("1+foo") == "foo"
        assert trailing_ident("foo.bar.baz") == "foo.bar.baz"
        assert trailing_ident("_x") == "_x"
        assert trailing_ident("A1.B2.") == "A1.B2."
        assert trailing_ident("...ta.") == "ta." or trailing_ident("...ta.") == ""

    def test_ascii_ident_helpers(self) -> None:
        assert _is_ascii_ident_start("a")
        assert _is_ascii_ident_start("Z")
        assert _is_ascii_ident_start("_")
        assert not _is_ascii_ident_start("1")
        assert not _is_ascii_ident_start(".")
        assert _is_ascii_ident_cont("9")
        assert _is_ascii_ident_cont("a")
        assert not _is_ascii_ident_cont(".")

    def test_extract_module_prefix(self) -> None:
        assert extract_module_prefix("ta.") == "ta"
        assert extract_module_prefix("request.se") == "request"
        assert extract_module_prefix("a.b.c") == "a.b"
        assert extract_module_prefix("sma") is None
        assert extract_module_prefix("") is None

    def test_build_filter_text(self) -> None:
        ft = build_filter_text("ta.sma")
        assert isinstance(ft, str) and len(ft) > 0
        assert "t" in ft and "s" in ft
        ft2 = build_filter_text("plot")
        assert "p" in ft2
        assert build_filter_text("a.b", prefix="a")  # prefix ignored but accepted


# ---------------------------------------------------------------------------
# workspace.py thin helpers
# ---------------------------------------------------------------------------


class TestWorkspaceThinHelpers:
    def test_text_document_path(self) -> None:
        doc = TextDocumentState(uri="file:///tmp/demo.pine", source="x")
        assert doc.path is not None
        assert str(doc.path).endswith("demo.pine")
        untitled = TextDocumentState(uri="untitled:1", source="x")
        assert untitled.path is None

    def test_extract_error_line(self) -> None:
        ws = Workspace()
        assert ws._extract_error_line("Parse error at line: 12") == 12
        assert ws._extract_error_line("LINE 3: boom") == 3
        assert ws._extract_error_line("no line here") is None

    def test_lint_warning_to_diagnostic_edges(self) -> None:
        src = "length = 14\nplot(close)\n"
        w = LintWarning(code="W001", message="warn", severity="warning", line=1, column=0)
        diag = _lint_warning_to_diagnostic(w, src)
        assert diag is not None
        assert diag.code == "W001"
        assert diag.severity == lsp.DiagnosticSeverity.Warning
        assert diag.range.start.line == 0

        w2 = LintWarning(code="E002", message="err", severity="error", line=2, column=1)
        diag2 = _lint_warning_to_diagnostic(w2, src)
        assert diag2 is not None
        assert diag2.severity == lsp.DiagnosticSeverity.Error
        assert diag2.range.start.character == 1

        w3 = LintWarning(code="I1", message="info", severity="info", line=1, column=0)
        assert _lint_warning_to_diagnostic(w3, src).severity == lsp.DiagnosticSeverity.Information  # type: ignore[union-attr]
        w4 = LintWarning(code="H1", message="hint", severity="hint", line=1, column=0)
        assert _lint_warning_to_diagnostic(w4, "").severity == lsp.DiagnosticSeverity.Hint  # type: ignore[union-attr]
        w5 = LintWarning(code="X", message="x", severity="weird", line=1, column=0)
        assert _lint_warning_to_diagnostic(w5, "").severity == lsp.DiagnosticSeverity.Warning  # type: ignore[union-attr]
        assert _lint_warning_to_diagnostic(LintWarning(code="Z", message="z", severity="warning", line=None), src) is None

    def test_apply_text_edit_pad_and_multiline(self) -> None:
        # append past EOF
        r = lsp.Range(
            start=lsp.Position(line=5, character=0),
            end=lsp.Position(line=5, character=0),
        )
        out = _apply_text_edit("a", r, "z")
        assert "z" in out
        # replace across lines
        src = "one\ntwo\nthree"
        r2 = lsp.Range(
            start=lsp.Position(line=0, character=1),
            end=lsp.Position(line=2, character=2),
        )
        assert _apply_text_edit(src, r2, "X") == "oXree"
        # clamp stale columns
        r3 = lsp.Range(
            start=lsp.Position(line=0, character=100),
            end=lsp.Position(line=0, character=200),
        )
        assert _apply_text_edit("hi", r3, "!") == "hi!"

    def test_workspace_put_update_diagnostics(self) -> None:
        ws = Workspace()
        uri = "file:///proto-cov.pine"
        src = '//@version=5\nindicator("t")\nplot(close)\n'
        doc = ws.put_document(uri, src, version=1)
        assert doc.ast is not None
        assert ws.get_source(uri) == src
        assert ws.get_document(uri) is doc
        assert len(ws.list_open_documents()) == 1

        # version-only bump, identical text → skip reparse path still returns doc
        whole = lsp.TextDocumentContentChangeWholeDocument(text=src)
        doc2 = ws.update_document(uri, [whole], version=2)
        assert doc2.version == 2

        # incremental edit
        change = lsp.TextDocumentContentChangePartial(
            range=lsp.Range(start=lsp.Position(line=2, character=0), end=lsp.Position(line=2, character=11)),
            text="plot(open)\n",
        )
        doc3 = ws.update_document(uri, [change], version=3)
        assert "plot(open)" in doc3.source
        diags = ws.get_all_diagnostics()
        assert uri in diags

        # parse error path
        bad = ws.put_document("file:///bad.pine", "@@@", version=1)
        assert bad.ast is None
        assert bad.parse_error
        bad_diags = ws._lint_warnings_to_diagnostics(bad)
        assert any(d.code == "E001" for d in bad_diags)

        ws.remove_document(uri)
        assert ws.get_document(uri) is None

    def test_update_missing_raises(self) -> None:
        ws = Workspace()
        with pytest.raises(ValueError):
            ws.update_document("file:///missing.pine", [], 1)

    def test_feature_cache_invalidated_on_change(self) -> None:
        ws = Workspace()
        uri = "file:///cache.pine"
        doc = ws.put_document(uri, '//@version=5\nindicator("t")\nplot(close)\n')
        doc.feature_cache["tokens"] = [1, 2, 3]
        change = lsp.TextDocumentContentChangeWholeDocument(text='//@version=5\nindicator("t")\nplot(open)\n')
        ws.update_document(uri, [change], version=2)
        assert ws.get_document(uri).feature_cache == {}  # type: ignore[union-attr]
