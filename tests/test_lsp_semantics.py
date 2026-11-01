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

"""Regression tests for the scope-aware LSP semantic layer.

These cover the production-readiness fixes that are easy to regress:
version-gated lint rules, comment/string masking, stale-AST protection,
scope-aware navigation, and non-destructive formatting.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.ast.helper import parse
from pynescript.ast.linter import lint_script
from pynescript.langserver.analysis import build_symbol_index
from pynescript.langserver.features.completion import handle_completion
from pynescript.langserver.features.convert import handle_code_action
from pynescript.langserver.features.definitions import handle_definition
from pynescript.langserver.features.formatting import handle_formatting
from pynescript.langserver.features.highlight import handle_document_highlight
from pynescript.langserver.features.inlay_hints import handle_inlay_hints
from pynescript.langserver.features.references import handle_references
from pynescript.langserver.features.rename import handle_rename
from pynescript.langserver.features.signature_help import handle_signature_help
from pynescript.langserver.workspace import Workspace
from pynescript.langserver.workspace_index import WorkspaceIndex


def _completion(source: str, line: int, character: int) -> list[lsp.CompletionItem]:
    return list(
        handle_completion(
            lsp.CompletionParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///semantics.pine"),
                position=lsp.Position(line=line, character=character),
            ),
            source,
        ).items
    )


def _position_after(source: str, needle: str, occurrence: int = 1) -> lsp.Position:
    index = -1
    for _ in range(occurrence):
        index = source.find(needle, index + 1)
    assert index >= 0, needle
    line = source.count("\n", 0, index)
    start = source.rfind("\n", 0, index) + 1
    return lsp.Position(line=line, character=index - start + len(needle))


# ---------------------------------------------------------------------------
# Linter precision
# ---------------------------------------------------------------------------


class TestLinterPrecision:
    def test_v5_transp_is_not_w104(self) -> None:
        src = '//@version=5\nindicator("T")\nplot(close, transp=50)\n'
        assert "W104" not in [warning.code for warning in lint_script(src)]

    def test_v6_transp_is_w104(self) -> None:
        src = '//@version=6\nindicator("T")\nplot(close, transp=50)\n'
        warning = next(w for w in lint_script(src) if w.code == "W104")
        assert warning.column == 12
        assert warning.end_column == 19

    def test_v5_numeric_condition_is_not_w105(self) -> None:
        src = '//@version=5\nindicator("T")\nif 1\n    x = 2\n'
        assert "W105" not in [warning.code for warning in lint_script(src)]

    def test_comment_and_string_do_not_trigger_c001(self) -> None:
        src = """//@version=6
indicator("T")
// old_name = ta.sma(close, 14)
s = "old_name = ta.sma(close, 14)"
foo_bar = ta.sma(close, 14)
"""
        warnings = [w for w in lint_script(src) if w.code == "C001"]
        assert len(warnings) == 1
        assert warnings[0].line == 5

    def test_security_in_comment_or_string_is_not_w101(self) -> None:
        src = """//@version=5
indicator("T")
// security('NASDAQ:AAPL')
s = "security('NASDAQ:AAPL')"
x = security('NASDAQ:AAPL')
"""
        warnings = [w for w in lint_script(src) if w.code == "W101"]
        assert len(warnings) == 1
        assert warnings[0].line == 5


# ---------------------------------------------------------------------------
# Workspace freshness
# ---------------------------------------------------------------------------


class TestWorkspaceFreshness:
    def test_changed_source_invalidates_ast_until_reparse(self) -> None:
        workspace = Workspace()
        doc = workspace.put_document("file:///fresh.pine", '//@version=6\nindicator("T")\nx = 1\n')
        assert doc.valid_ast is not None

        workspace.update_document(
            "file:///fresh.pine",
            [lsp.TextDocumentContentChangeWholeDocument(text='//@version=6\nindicator("U")\n')],
            version=2,
            relint=False,
        )
        assert doc.valid_ast is None
        assert doc.valid_analysis is None
        # The old tree is retained for tests/debugging but never served.
        assert doc.ast is not None

    def test_parse_error_range_is_non_empty(self) -> None:
        workspace = Workspace()
        doc = workspace.put_document("file:///broken.pine", '//@version=6\nindicator("T")\nplot(ta.\n')
        diagnostics = workspace._lint_warnings_to_diagnostics(doc)
        error = next(d for d in diagnostics if d.code == "E001")
        assert error.range.end.character > error.range.start.character


class TestWorkspaceIndex:
    def test_search_closed_pine_files(self, tmp_path) -> None:
        (tmp_path / "a.pine").write_text(
            '//@version=6\nindicator("A")\nmyFunction() => 1\n',
            encoding="utf-8",
        )
        (tmp_path / "b.pyne").write_text(
            '//@version=6\nindicator("B")\nlength = 14\n',
            encoding="utf-8",
        )
        index = WorkspaceIndex([tmp_path])
        names = {symbol.name for symbol in index.search("my")}
        assert "myFunction" in names
        names = {symbol.name for symbol in index.search("length")}
        assert "length" in names

    def test_ignored_directories_are_not_scanned(self, tmp_path) -> None:
        ignored = tmp_path / "node_modules"
        ignored.mkdir()
        (ignored / "hidden.pine").write_text(
            '//@version=6\nindicator("H")\nsecretFunction() => 1\n',
            encoding="utf-8",
        )
        index = WorkspaceIndex([tmp_path])
        assert index.search("secret") == []


# ---------------------------------------------------------------------------
# Scope-aware completion / navigation
# ---------------------------------------------------------------------------


class TestCompletionSemantics:
    SOURCE = """//@version=6
indicator("T")
type Point
    float x
    float y
method dist(Point self, Point other) =>
    math.sqrt(self.x)
p = Point.new(1, 2)
q = Point.new(3, 4)
d = p.
"""

    def test_udt_member_completion(self) -> None:
        items = _completion(self.SOURCE, 9, 6)
        labels = {item.label for item in items}
        assert {"x", "y", "dist"}.issubset(labels)
        method = next(item for item in items if item.label == "dist")
        assert method.insert_text == "dist(${1:other})"

    def test_user_symbols_are_offered(self) -> None:
        items = _completion(self.SOURCE, 9, 4)
        labels = {item.label for item in items}
        assert {"Point", "p", "q", "dist"}.issubset(labels)

    def test_snippets_can_be_disabled(self) -> None:
        result = handle_completion(
            lsp.CompletionParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///semantics.pine"),
                position=lsp.Position(line=2, character=0),
            ),
            '//@version=6\nindicator("T")\nplot(ta.sma(close, 14))\n',
            snippets=False,
        )
        sma = next(item for item in result.items if item.label == "ta.sma")
        assert sma.insert_text_format == lsp.InsertTextFormat.PlainText
        assert "${" not in str(sma.insert_text)


class TestNavigationSemantics:
    SOURCE = """//@version=6
indicator("T")
x = 1
f() =>
    x = 2
    x
plot(x)
"""

    def test_definition_respects_shadowing_and_precise_range(self) -> None:
        result = handle_definition(
            lsp.DefinitionParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///nav.pine"),
                position=lsp.Position(line=5, character=4),
            ),
            self.SOURCE,
            "file:///nav.pine",
        )
        assert result
        location = result[0]
        assert location.range.start.line == 4
        assert location.range.start.character == 4
        assert location.range.end.character == 5

    def test_references_do_not_cross_scopes(self) -> None:
        result = handle_references(
            lsp.ReferenceParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///nav.pine"),
                position=lsp.Position(line=5, character=4),
                context=lsp.ReferenceContext(include_declaration=True),
            ),
            self.SOURCE,
            "file:///nav.pine",
        )
        assert [(loc.range.start.line, loc.range.start.character) for loc in result] == [(4, 4), (5, 4)]

    def test_highlight_does_not_cross_scopes(self) -> None:
        result = handle_document_highlight(
            lsp.DocumentHighlightParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///nav.pine"),
                position=lsp.Position(line=5, character=4),
            ),
            self.SOURCE,
        )
        assert len(result) == 2

    def test_rename_local_only(self) -> None:
        result = handle_rename(
            lsp.RenameParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///nav.pine"),
                position=lsp.Position(line=5, character=4),
                new_name="y",
            ),
            self.SOURCE,
            "file:///nav.pine",
        )
        assert result is not None
        edits = result.changes["file:///nav.pine"]
        assert [(edit.range.start.line, edit.new_text) for edit in edits] == [(4, "y"), (5, "y")]


# ---------------------------------------------------------------------------
# Formatting safety
# ---------------------------------------------------------------------------


class TestFormattingSafety:
    def test_prose_comment_blocks_formatting(self) -> None:
        source = '//@version=6\nindicator("T")\n// keep this comment\nx=1\n'
        edits = handle_formatting(
            lsp.DocumentFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///fmt.pine"),
                options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
            ),
            source,
        )
        assert edits == []

    def test_preserved_annotations_still_format(self) -> None:
        source = '//@version=6\nindicator("T")\n//@function docs\nf(x) => x\n'
        edits = handle_formatting(
            lsp.DocumentFormattingParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///fmt.pine"),
                options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
            ),
            source,
        )
        assert edits
        assert "//@function docs" in edits[0].new_text


# ---------------------------------------------------------------------------
# Signature / inlay / semantic details
# ---------------------------------------------------------------------------


class TestSignatureAndInlaySemantics:
    def test_unknown_receiver_does_not_fall_back_to_builtin(self) -> None:
        source = '//@version=6\nindicator("T")\nobj.sma(close, 14)\n'
        result = handle_signature_help(
            lsp.SignatureHelpParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///sig.pine"),
                position=_position_after(source, "obj.sma(close,"),
            ),
            source,
        )
        assert result is None

    def test_inlay_hints_are_range_filtered(self) -> None:
        source = '//@version=6\nindicator("T")\na = close\nb = 1\nc = "x"\n'
        hints = handle_inlay_hints(
            lsp.InlayHintParams(
                text_document=lsp.TextDocumentIdentifier(uri="file:///ih.pine"),
                range=lsp.Range(
                    start=lsp.Position(line=3, character=0),
                    end=lsp.Position(line=4, character=0),
                ),
            ),
            source,
        )
        assert hints is not None
        assert [hint.position.line for hint in hints] == [3]

    def test_symbol_index_infers_collection_element_type(self) -> None:
        source = """//@version=6
indicator("T")
a = array.new<float>(3, 0.0)
x = array.get(a, 0)
m = map.new<string, float>()
y = map.get(m, "a")
"""
        index = build_symbol_index(parse(source), source)
        assert index.resolve("a").type_label == "array<float>"
        assert index.resolve("x").type_label == "float"
        assert index.resolve("m").type_label == "map<string, float>"
        assert index.resolve("y").type_label == "float"

    def test_symbol_index_infers_udt_field_type(self) -> None:
        source = """//@version=6
indicator("T")
type Point
    float x
p = Point.new(1)
y = p.x
"""
        index = build_symbol_index(parse(source), source)
        symbol = index.resolve("y")
        assert symbol is not None
        assert symbol.type_label == "float"


# ---------------------------------------------------------------------------
# Opt-in semantic diagnostics
# ---------------------------------------------------------------------------


_SEMANTIC_SOURCE = """//@version=6
indicator("T")

type Point
    float x
    float y

enum Side
    Buy
    Sell

add(a, b) => a + b
addDefault(a, b = 2) => a + b

method describe(Point self) =>
    str.tostring(self.x)

p = Point.new(1.0, 2.0)
ok = p.x + p.y
badField = p.distnace
badEnum = Side.Selll
missing = add(1)
tooMany = add(1, 2, 3)
typoKwarg = add(1, lenght=2)
defaulted = addDefault(1)
builtin = ta.sma(close)
methodCall = p.describe(1)
plot(ok)
"""


def _semantic_diagnostics(*, enabled: bool) -> list[lsp.Diagnostic]:
    workspace = Workspace(style_diagnostics=False, semantic_diagnostics=enabled)
    workspace.put_document("file:///semantics.pine", _SEMANTIC_SOURCE)
    return workspace.get_all_diagnostics()["file:///semantics.pine"]


class TestSemanticDiagnostics:
    def test_off_by_default(self) -> None:
        assert not [diag for diag in _semantic_diagnostics(enabled=False) if str(diag.code).startswith("S")]

    def test_unknown_udt_member(self) -> None:
        diagnostic = next(diag for diag in _semantic_diagnostics(enabled=True) if diag.code == "S001")
        assert "distnace" in diagnostic.message
        assert "Point" in diagnostic.message
        assert diagnostic.range.start.line == 19
        assert diagnostic.range.start.character == _SEMANTIC_SOURCE.split("\n")[19].index("distnace")

    def test_unknown_enum_member(self) -> None:
        messages = [diag.message for diag in _semantic_diagnostics(enabled=True) if diag.code == "S001"]
        assert any("Selll" in message and "Side" in message for message in messages)

    def test_user_function_arity(self) -> None:
        messages = [diag.message for diag in _semantic_diagnostics(enabled=True) if diag.code == "S002"]
        assert any("missing required argument" in message and "'b'" in message for message in messages)
        assert any("expects at most 2" in message for message in messages)
        assert any("no parameter named 'lenght'" in message for message in messages)

    def test_valid_calls_and_builtins_are_quiet(self) -> None:
        diagnostics = [diag for diag in _semantic_diagnostics(enabled=True) if diag.code == "S002"]
        messages = " ".join(diag.message for diag in diagnostics)
        assert "addDefault" not in messages
        assert "ta.sma" not in messages
        assert "describe" not in messages

    def test_known_fields_and_enum_members_are_quiet(self) -> None:
        messages = " ".join(diag.message for diag in _semantic_diagnostics(enabled=True))
        assert "p.x" not in messages
        assert "'Buy'" not in messages


# ---------------------------------------------------------------------------
# W104 / W105 quick fixes
# ---------------------------------------------------------------------------


def _apply_action(source: str, action: lsp.CodeAction) -> str:
    document_changes = action.edit.document_changes or []
    edits = document_changes[0].edits
    assert isinstance(edits, list)
    lines = source.split("\n")

    def offset(position: lsp.Position) -> int:
        return sum(len(text) + 1 for text in lines[: position.line]) + position.character

    edit = edits[0]
    return source[: offset(edit.range.start)] + edit.new_text + source[offset(edit.range.end) :]


def _actions_for(source: str) -> list[lsp.CodeAction]:
    tree = parse(source)
    warnings = lint_script(source, tree=tree)
    params = lsp.CodeActionParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///fixes.pine"),
        range=lsp.Range(start=lsp.Position(line=0, character=0), end=lsp.Position(line=0, character=0)),
        context=lsp.CodeActionContext(diagnostics=[]),
    )
    return handle_code_action(params, source, warnings, tree=tree)


class TestQuickFixes:
    def test_w104_removes_middle_argument(self) -> None:
        source = '//@version=6\nindicator("T")\nplot(close, transp=20, color=color.red)\n'
        action = next(a for a in _actions_for(source) if a.title == "Remove removed v6 argument")
        fixed = _apply_action(source, action)
        assert fixed == '//@version=6\nindicator("T")\nplot(close, color=color.red)\n'

    def test_w104_removes_last_argument(self) -> None:
        source = '//@version=6\nindicator("T")\nplot(close, transp=20)\n'
        action = next(a for a in _actions_for(source) if a.title == "Remove removed v6 argument")
        assert _apply_action(source, action) == '//@version=6\nindicator("T")\nplot(close)\n'

    def test_w104_removes_strategy_when(self) -> None:
        source = '//@version=6\nstrategy("T")\nstrategy.entry("L", strategy.long, when = close > open)\n'
        action = next(a for a in _actions_for(source) if a.title == "Remove removed v6 argument")
        fixed = _apply_action(source, action)
        assert fixed == '//@version=6\nstrategy("T")\nstrategy.entry("L", strategy.long)\n'

    def test_w104_refuses_to_delete_a_comment(self) -> None:
        source = '//@version=6\nindicator("T")\nplot(close, transp=20, // keep\n     color=color.red)\n'
        titles = [action.title for action in _actions_for(source)]
        assert "Remove removed v6 argument" not in titles

    def test_w104_absent_on_v5(self) -> None:
        source = '//@version=5\nindicator("T")\nplot(close, transp=20)\n'
        assert "Remove removed v6 argument" not in [action.title for action in _actions_for(source)]

    def test_w105_compares_with_zero(self) -> None:
        source = '//@version=6\nindicator("T")\nif 1\n    x = 2\n'
        action = next(a for a in _actions_for(source) if a.title == "Compare numeric condition with 0")
        assert _apply_action(source, action) == '//@version=6\nindicator("T")\nif 1 != 0\n    x = 2\n'

    def test_w105_ternary_literal(self) -> None:
        source = '//@version=6\nindicator("T")\ny = 1 ? 2 : 3\n'
        action = next(a for a in _actions_for(source) if a.title == "Compare numeric condition with 0")
        assert _apply_action(source, action) == '//@version=6\nindicator("T")\ny = 1 != 0 ? 2 : 3\n'
