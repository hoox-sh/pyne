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
