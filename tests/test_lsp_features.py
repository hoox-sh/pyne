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

"""Tests for LSP features."""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.langserver.features.completion import handle_completion
from pynescript.langserver.features.definitions import handle_definition
from pynescript.langserver.features.formatting import handle_formatting
from pynescript.langserver.features.formatting import handle_range_formatting
from pynescript.langserver.features.hover import handle_hover
from pynescript.langserver.features.references import handle_references
from pynescript.langserver.features.symbols import handle_document_symbols
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.providers.builtin_metadata import get_metadata
from pynescript.langserver.providers.completion_items import build_completion_item
from pynescript.langserver.providers.completion_items import build_completion_list
from pynescript.langserver.providers.completion_items import build_module_completion


class TestBuiltinMetadata:
    """Test builtin metadata loading."""

    def test_metadata_loaded(self) -> None:
        """Test that metadata is loaded."""
        metadata = get_metadata()
        assert len(metadata) > 400, "Should have 400+ builtins"

    def test_ta_sma_metadata(self) -> None:
        """Test ta.sma metadata exists."""
        info = get_builtin("ta.sma")
        assert info is not None
        assert info["label"] == "ta.sma"
        assert "detail" in info
        assert "snippet" in info

    def test_category_inference(self) -> None:
        """Test that categories are inferred correctly."""
        info = get_builtin("ta.sma")
        assert info is not None
        assert info["category"] == "ta.technical_analysis"

        info2 = get_builtin("strategy.entry")
        assert info2 is not None
        assert info2["category"] == "strategy"


class TestCompletionList:
    """Test completion list building."""

    def test_full_completion_list(self) -> None:
        """Test building full completion list."""
        cl = build_completion_list()
        assert cl.is_incomplete is False
        assert len(cl.items) > 400

    def test_module_completion(self) -> None:
        """Test module-specific completion (counts track regenerated metadata)."""
        ta_cl = build_module_completion("ta")
        assert len(ta_cl.items) >= 150

        strategy_cl = build_module_completion("strategy")
        assert len(strategy_cl.items) >= 27

    def test_completion_item_structure(self) -> None:
        """Test completion item has correct structure."""
        info = get_builtin("ta.sma")
        assert info is not None
        item = build_completion_item(info)

        assert item.label == "ta.sma"
        assert item.kind == lsp.CompletionItemKind.Function
        assert hasattr(item, "detail")


class TestCompletionHandler:
    """Test completion request handling."""

    def test_handle_completion_no_prefix(self) -> None:
        """Test completion with no prefix."""
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),
            context=lsp.CompletionContext(trigger_kind=lsp.CompletionTriggerKind.Invoked),
        )

        result = handle_completion(params, "//@version=5\n")
        assert isinstance(result, lsp.CompletionList)
        assert len(result.items) > 100

    def test_handle_completion_with_ta_prefix(self) -> None:
        """Test completion filtering by prefix."""
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=3),  # After "ta."
            context=lsp.CompletionContext(trigger_kind=lsp.CompletionTriggerKind.Invoked),
        )

        # Source with "ta." at cursor
        result = handle_completion(params, "//@version=5\nta.")
        assert isinstance(result, lsp.CompletionList)

    def test_handle_completion_after_call_open_paren(self) -> None:
        """``plot(ta.`` must complete ``ta`` members, not an empty list."""
        source = "//@version=6\nindicator('T')\nplot(ta."
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=8),
            context=lsp.CompletionContext(
                trigger_kind=lsp.CompletionTriggerKind.TriggerCharacter,
                trigger_character=".",
            ),
        )
        result = handle_completion(params, source)
        labels = [i.label for i in result.items]
        assert "ta.sma" in labels
        sma = next(i for i in result.items if i.label == "ta.sma")
        assert sma.insert_text is not None
        assert not str(sma.insert_text).startswith("ta.")

    def test_handle_completion_keywords(self) -> None:
        """Soft keywords missing from builtin metadata still complete."""
        source = "//@version=6\nindicator('T')\nenu"
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=3),
            context=lsp.CompletionContext(trigger_kind=lsp.CompletionTriggerKind.Invoked),
        )
        result = handle_completion(params, source)
        keywords = [i for i in result.items if i.kind == lsp.CompletionItemKind.Keyword]
        labels = [i.label for i in keywords]
        assert "enum" in labels

    def test_handle_completion_user_enum_members(self) -> None:
        """``Side.`` completes user-enum members with leaf insert text."""
        source = """//@version=6
indicator("T")
enum Side
    buy = "B"
    sell = "S"
s = Side.
"""
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=5, character=9),
            context=lsp.CompletionContext(
                trigger_kind=lsp.CompletionTriggerKind.TriggerCharacter,
                trigger_character=".",
            ),
        )
        result = handle_completion(params, source)
        labels = [i.label for i in result.items]
        assert "Side.buy" in labels
        assert "Side.sell" in labels
        buy = next(i for i in result.items if i.label == "Side.buy")
        assert buy.kind == lsp.CompletionItemKind.EnumMember
        assert buy.insert_text == "buy"

    def test_handle_completion_user_enum_name(self) -> None:
        """Bare prefix offers the user enum type name."""
        source = """//@version=6
indicator("T")
enum Side
    buy
    sell
x = Si
"""
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=5, character=6),
            context=lsp.CompletionContext(trigger_kind=lsp.CompletionTriggerKind.Invoked),
        )
        result = handle_completion(params, source)
        enums = [i for i in result.items if i.kind == lsp.CompletionItemKind.Enum]
        assert any(i.label == "Side" for i in enums)


class TestHoverHandler:
    """Test hover request handling."""

    def test_handle_hover_ta_sma(self) -> None:
        """Test hover over ta.sma."""
        source = "//@version=5\nindicator('Test')\nplot(ta.sma(close, 14))\n"

        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=10),  # On "sma"
        )

        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result, lsp.Hover)
        assert isinstance(result.contents, lsp.MarkupContent)

    def test_handle_hover_no_symbol(self) -> None:
        """Test hover where there's no symbol."""
        source = "//@version=5\nindicator('Test')\n"

        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),  # On comment
        )

        result = handle_hover(params, source)
        # May return None if cursor isn't on a symbol

    def test_handle_hover_outside_document(self) -> None:
        """Test hover outside document bounds."""
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=100, character=0),
        )

        result = handle_hover(params, "//@version=5\n")
        assert result is None

    def test_handle_hover_user_enum(self) -> None:
        """Hover on a user enum type and ``Enum.member`` path."""
        source = """//@version=6
indicator("T")
enum Side
    buy = "B"
    sell = "S"
s = Side.buy
"""
        type_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=6),  # on "Side" in decl
        )
        type_hover = handle_hover(type_params, source)
        assert type_hover is not None
        assert isinstance(type_hover.contents, lsp.MarkupContent)
        assert "enum Side" in type_hover.contents.value
        assert "buy" in type_hover.contents.value

        member_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=5, character=10),  # on "buy" in Side.buy
        )
        member_hover = handle_hover(member_params, source)
        assert member_hover is not None
        assert isinstance(member_hover.contents, lsp.MarkupContent)
        assert "Side.buy" in member_hover.contents.value or "Member of user enum" in member_hover.contents.value

    def test_handle_hover_keyword(self) -> None:
        """Hover on a soft keyword shows a short description."""
        source = "//@version=6\nenum Side\n    buy\n"
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=1, character=1),  # on "enum"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        assert "enum" in result.contents.value
        assert "user-defined enum" in result.contents.value.lower()

    def test_handle_hover_if_keyword(self) -> None:
        """Hover on ``if`` shows a sentence, not a one-word stub."""
        source = "//@version=6\nindicator('T')\nif close > open\n    x = 1\n"
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=1),  # on "if"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value.lower()
        assert "if" in text
        assert "condition" in text or "branch" in text

    def test_handle_hover_var_keyword(self) -> None:
        """Hover on ``var`` documents the persistent declaration mode."""
        source = "//@version=6\nindicator('T')\nvar float x = close\n"
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=1),  # on "var"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value.lower()
        assert "var" in text
        assert "persist" in text or "across bars" in text

    def test_handle_hover_series_qualifier(self) -> None:
        """Hover on ``series`` documents the type qualifier."""
        source = "//@version=6\nindicator('T')\nseries float x = close\n"
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=2),  # on "series"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value.lower()
        assert "series" in text
        assert "qualifier" in text or "bar" in text

    def test_handle_hover_float_type(self) -> None:
        """Hover on ``float`` in a typed decl is the type, not ``float(...)``."""
        source = "//@version=6\nindicator('T')\nfloat len = close\n"
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=2),  # on "float"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value.lower()
        assert "float" in text
        assert "type" in text
        assert "float(...)" not in result.contents.value

    def test_handle_hover_ta_module(self) -> None:
        """Hover on ``ta`` in ``ta.sma`` documents the namespace."""
        source = "//@version=6\nindicator('T')\nplot(ta.sma(close, 14))\n"
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=5),  # on "ta"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value.lower()
        assert "ta" in text
        assert "namespace" in text or "technical" in text

    def test_handle_hover_user_function(self) -> None:
        """Hover on a user function shows kind plus the source signature."""
        source = "//@version=6\nindicator('T')\nfoo(a) => a\nplot(foo(1))\n"
        decl_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=1),  # on "foo" in decl
        )
        result = handle_hover(decl_params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value
        assert "foo" in text
        assert "function" in text.lower()
        assert "foo(a)" in text

        use_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=3, character=6),  # on "foo" in plot(foo(1))
        )
        use_hover = handle_hover(use_params, source)
        assert use_hover is not None
        assert isinstance(use_hover.contents, lsp.MarkupContent)
        assert "foo(a)" in use_hover.contents.value


class TestDefinitionHandler:
    """Test go-to-definition request handling."""

    def test_handle_definition_function(self) -> None:
        """Test go-to-definition for a function."""
        source = """//@version=5
indicator("Test")

myFunction() =>
    ta.sma(close, 14)

plot(myFunction())
"""
        # Line 6 (0-indexed) is "plot(myFunction())", position 6 is after "plot("
        params = lsp.DefinitionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=6, character=6),
        )

        result = handle_definition(params, source, "file:///test.pine")
        # Should find the function definition at line 4 (0-indexed)
        assert result is not None
        assert len(result) >= 1

    def test_handle_definition_variable(self) -> None:
        """Test go-to-definition for a variable."""
        source = """//@version=5
indicator("Test")

length = 14
plot(ta.sma(close, length))
"""
        # Line 4 (0-indexed) is "plot(ta.sma(close, length))"
        params = lsp.DefinitionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=4, character=25),
        )

        result = handle_definition(params, source, "file:///test.pine")
        # Should find the variable definition at line 3 (0-indexed)
        assert result is not None
        assert len(result) >= 1

    def test_handle_definition_no_symbol(self) -> None:
        """Test go-to-definition when cursor is not on a symbol."""
        source = "//@version=5\nindicator('Test')\n"
        params = lsp.DefinitionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),  # On comment
        )

        result = handle_definition(params, source, "file:///test.pine")
        assert result is None or len(result) == 0

    def test_handle_definition_user_enum_member(self) -> None:
        """Go-to-definition on ``Side.buy`` lands on the member declaration."""
        source = """//@version=6
indicator("T")
enum Side
    buy = "B"
    sell = "S"
s = Side.buy
"""
        params = lsp.DefinitionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=5, character=10),  # on "buy"
        )
        result = handle_definition(params, source, "file:///test.pine")
        assert result is not None
        assert any(loc.range.start.line == 3 for loc in result)


class TestReferencesHandler:
    """Test find-references request handling."""

    def test_handle_references(self) -> None:
        """Test find references for a variable."""
        source = """//@version=5
indicator("Test")

length = 14
plot(ta.sma(close, length))
plot(ta.ema(close, length))
"""
        # Line 4 is plot(... length) — character 25 lands on "length"
        params = lsp.ReferenceParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=4, character=25),
            context=lsp.ReferenceContext(include_declaration=True),
        )

        result = handle_references(params, source, "file:///test.pine")
        # definition (line 3) + two uses (lines 4 and 5)
        assert len(result) == 3
        lines = sorted(r.range.start.line for r in result)
        assert lines == [3, 4, 5]

    def test_handle_references_no_include_declaration(self) -> None:
        """Test find references without including declaration."""
        source = """//@version=5
indicator("Test")

length = 14
plot(ta.sma(close, length))
"""
        params = lsp.ReferenceParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=4, character=25),  # On "length" use
            context=lsp.ReferenceContext(include_declaration=False),
        )

        result = handle_references(params, source, "file:///test.pine")
        assert len(result) >= 1
        # Declaration line must be excluded
        assert all(r.range.start.line != 3 for r in result)

    def test_handle_references_inside_function_body(self) -> None:
        """Recursive / in-body references must not be skipped when name matches."""
        source = """//@version=5
indicator("T")

myFunc(x) =>
    myFunc(x - 1)

plot(myFunc(1))
"""
        params = lsp.ReferenceParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=3, character=0),  # On "myFunc" def
            context=lsp.ReferenceContext(include_declaration=True),
        )
        result = handle_references(params, source, "file:///test.pine")
        # def, recursive call inside body, outer plot call
        assert len(result) >= 3
        lines = sorted({r.range.start.line for r in result})
        assert 3 in lines  # definition
        assert 4 in lines  # recursive body call
        assert 6 in lines  # plot(myFunc(1))


class TestDocumentSymbolsHandler:
    """Test document symbols request handling."""

    def test_handle_document_symbols(self) -> None:
        """Test document symbols for a script."""
        source = """//@version=5
indicator("Test")

length = 14
fastMA = ta.sma(close, length)
slowMA = ta.ema(close, length)

myFunction() =>
    ta.sma(close, 14)

plot(myFunction())
"""
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )

        result = handle_document_symbols(params, source, "file:///test.pine")
        assert len(result) >= 1

        # Check for function symbol — exactly once (no double-flush)
        func_symbols = [s for s in result if s.kind == lsp.SymbolKind.Function]
        assert len(func_symbols) == 1
        assert func_symbols[0].name == "myFunction"

        # Check for variable symbols
        var_symbols = [s for s in result if s.kind == lsp.SymbolKind.Variable]
        assert len(var_symbols) >= 2

    def test_handle_document_symbols_no_double_flush(self) -> None:
        """Functions must appear once; top-level vars after a function must not nest."""
        source = """//@version=5
indicator("T")

f1() =>
    1

f2() =>
    2

x = 3
"""
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        result = handle_document_symbols(params, source, "file:///test.pine")
        func_names = [s.name for s in result if s.kind == lsp.SymbolKind.Function]
        assert func_names == ["f1", "f2"]
        var_names = [s.name for s in result if s.kind == lsp.SymbolKind.Variable]
        assert "x" in var_names

    def test_handle_document_symbols_empty(self) -> None:
        """Test document symbols for empty source."""
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )

        result = handle_document_symbols(params, "", "file:///test.pine")
        assert len(result) == 0

    def test_handle_document_symbols_selection_contained_in_full_range(self) -> None:
        """Every symbol's selectionRange must be contained in its fullRange.

        VS Code raises ``selectionRange must be contained in fullRange`` and
        drops the whole outline otherwise. Single-line statements previously
        produced zero-width full ranges ending at character 0.
        """

        def _contains(full: lsp.Range, sel: lsp.Range) -> bool:
            return (full.start.line, full.start.character) <= (
                sel.start.line,
                sel.start.character,
            ) and (sel.end.line, sel.end.character) <= (full.end.line, full.end.character)

        def _walk(symbols: list[lsp.DocumentSymbol]) -> list[lsp.DocumentSymbol]:
            out: list[lsp.DocumentSymbol] = []
            for s in symbols:
                out.append(s)
                out.extend(_walk(list(s.children or [])))
            return out

        source = """//@version=5
indicator("Test")

length = 14
fastMA = ta.sma(close, length)

myFunction() =>
    inner = 1
    inner

type MySettings
    int size = 10

settings = MySettings.new()
"""
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        result = handle_document_symbols(params, source, "file:///test.pine")
        assert len(result) >= 1

        for sym in _walk(result):
            assert sym.range is not None and sym.selection_range is not None
            assert _contains(sym.range, sym.selection_range), (
                f"{sym.name}: selection {sym.selection_range} not in full {sym.range}"
            )

    def test_handle_document_symbols_with_type(self) -> None:
        """Test document symbols with user-defined type."""
        source = """//@version=5
indicator("Test")

type MySettings
    int length = 14
    bool enabled = true

settings = MySettings.new()
"""
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )

        result = handle_document_symbols(params, source, "file:///test.pine")
        # Should find the type definition
        type_symbols = [s for s in result if s.kind == lsp.SymbolKind.Class]
        assert len(type_symbols) >= 1
        assert type_symbols[0].name == "MySettings"

    def test_handle_document_symbols_reuses_tree(self) -> None:
        """Passing a pre-parsed tree must not require re-parse of source."""
        from pynescript.ast.helper import parse

        source = """//@version=5
indicator("T")
length = 14
"""
        tree = parse(source, filename="file:///test.pine")
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        # Empty source would fail if tree were ignored and re-parsed from source.
        result = handle_document_symbols(params, source=None, uri="file:///test.pine", tree=tree)
        var_names = [s.name for s in result if s.kind == lsp.SymbolKind.Variable]
        assert "length" in var_names

    def test_handle_document_symbols_enum(self) -> None:
        """EnumDef is an outline enum; members are not top-level variables."""
        source = """//@version=6
indicator("T")
enum Side
    buy = "B"
    sell = "S"
s = Side.buy
"""
        params = lsp.DocumentSymbolParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        result = handle_document_symbols(params, source, "file:///test.pine")
        enums = [s for s in result if s.kind == lsp.SymbolKind.Enum]
        assert len(enums) == 1
        assert enums[0].name == "Side"
        members = list(enums[0].children or [])
        assert [m.name for m in members] == ["buy", "sell"]
        assert all(m.kind == lsp.SymbolKind.EnumMember for m in members)
        var_names = [s.name for s in result if s.kind == lsp.SymbolKind.Variable]
        assert "buy" not in var_names
        assert "sell" not in var_names
        assert "s" in var_names


class TestFormattingHandler:
    """Test formatting request handling."""

    def test_handle_formatting(self) -> None:
        """Test document formatting."""
        source = """//@version=5
indicator("Test")

length=14
plot(ta.sma(close,length))
"""
        params = lsp.DocumentFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )

        result = handle_formatting(params, source)
        assert result is not None
        assert len(result) >= 1

    def test_handle_formatting_empty(self) -> None:
        """Test formatting empty source."""
        params = lsp.DocumentFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )

        result = handle_formatting(params, "")
        assert result == []

    def test_handle_range_formatting(self) -> None:
        """Test range formatting."""
        source = """//@version=5
indicator("Test")
length=14
plot(ta.sma(close,length))
"""
        params = lsp.DocumentRangeFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=2, character=0),
                end=lsp.Position(line=2, character=20),
            ),
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )

        result = handle_range_formatting(params, source)
        assert result is not None


class TestSemanticTokensHandler:
    """Semantic tokens + workspace AST reuse."""

    def test_handle_semantic_tokens_basic(self) -> None:
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens

        source = """//@version=5
indicator("T")
length = 14
plot(ta.sma(close, length))
"""
        params = lsp.SemanticTokensParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        result = handle_semantic_tokens(params, source)
        assert result is not None
        assert len(result.data) > 0
        assert len(result.data) % 5 == 0

    def test_handle_semantic_tokens_reuses_tree(self) -> None:
        from pynescript.ast.helper import parse
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens

        source = """//@version=5
indicator("T")
x = 1
"""
        tree = parse(source)
        params = lsp.SemanticTokensParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        with_tree = handle_semantic_tokens(params, source=None, tree=tree)
        without = handle_semantic_tokens(params, source)
        assert with_tree is not None and without is not None
        assert with_tree.data == without.data

    def test_handle_semantic_tokens_incomplete_source(self) -> None:
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens

        params = lsp.SemanticTokensParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        result = handle_semantic_tokens(params, "//@version=5\nplot(ta.")
        assert result is not None
        assert result.data == []


class TestCapabilities:
    """Advertised capabilities must match implemented handlers only."""

    def test_no_unimplemented_signature_help_or_code_action(self) -> None:
        from pynescript.langserver.config import get_server_capabilities

        caps = get_server_capabilities()
        assert caps.signature_help_provider is None
        assert caps.code_action_provider is None or caps.code_action_provider is False
        assert caps.hover_provider is True
        assert caps.definition_provider is True
        assert caps.semantic_tokens_provider is not None
        assert caps.semantic_tokens_provider.full is True
        assert caps.semantic_tokens_provider.range is False
