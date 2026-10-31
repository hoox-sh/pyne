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
from pynescript.langserver.features.completion import handle_completion_resolve
from pynescript.langserver.features.convert import handle_code_action
from pynescript.langserver.features.convert import handle_convert_to_v6
from pynescript.langserver.features.definitions import handle_definition
from pynescript.langserver.features.document_color import handle_color_presentation
from pynescript.langserver.features.document_color import handle_document_color
from pynescript.langserver.features.document_link import handle_document_link
from pynescript.langserver.features.document_link import handle_document_link_resolve
from pynescript.langserver.features.folding import handle_folding_range
from pynescript.langserver.features.formatting import handle_formatting
from pynescript.langserver.features.formatting import handle_on_type_formatting
from pynescript.langserver.features.formatting import handle_range_formatting
from pynescript.langserver.features.highlight import handle_document_highlight
from pynescript.langserver.features.hover import handle_hover
from pynescript.langserver.features.inlay_hints import handle_inlay_hint_resolve
from pynescript.langserver.features.inlay_hints import handle_inlay_hints
from pynescript.langserver.features.linked_editing import handle_linked_editing_range
from pynescript.langserver.features.references import handle_references
from pynescript.langserver.features.rename import handle_prepare_rename
from pynescript.langserver.features.rename import handle_rename
from pynescript.langserver.features.selection_range import handle_selection_range
from pynescript.langserver.features.signature_help import handle_signature_help
from pynescript.langserver.features.symbols import handle_document_symbols
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.providers.builtin_metadata import get_metadata
from pynescript.langserver.providers.completion_items import build_completion_item
from pynescript.langserver.providers.completion_items import build_completion_list
from pynescript.langserver.providers.completion_items import build_module_completion
from pynescript.langserver.workspace import Workspace


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

    def test_line_fill_alias_in_metadata(self) -> None:
        """``line.fill`` is a runtime alias of ``linefill.new`` and must be in LSP catalog."""
        info = get_builtin("line.fill")
        assert info is not None
        assert info["label"] == "line.fill"
        assert info["category"] == "line"
        assert "line1" in info["snippet"]
        assert "color" in info["documentation"]

    def test_metadata_covers_dispatch_names(self) -> None:
        """Every BuiltinEvaluator dispatch key must appear in LSP metadata.

        AXIS pre-eval flags unknown ``module.member`` paths against this catalog
        (e.g. ``line.fill`` → ``line.all`` when the alias is missing).
        """
        from pynescript.ast.evaluator.builtins import BuiltinEvaluator

        dispatch = BuiltinEvaluator()._build_builtin_map()
        metadata = get_metadata()
        missing = sorted(set(dispatch) - set(metadata))
        assert missing == [], f"LSP metadata missing dispatch names: {missing}"


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

    def test_handle_completion_line_fill(self) -> None:
        """``line.`` completes ``line.fill`` (alias of linefill.new)."""
        source = "//@version=6\nindicator('T')\nline."
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=5),
            context=lsp.CompletionContext(
                trigger_kind=lsp.CompletionTriggerKind.TriggerCharacter,
                trigger_character=".",
            ),
        )
        result = handle_completion(params, source)
        labels = [i.label for i in result.items]
        assert "line.fill" in labels

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

    def test_handle_completion_strategy_risk_keeps_nested_path(self) -> None:
        """``strategy.`` insert text must keep ``risk.`` for nested members."""
        source = "//@version=6\nindicator('T')\nstrategy."
        params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=9),
            context=lsp.CompletionContext(
                trigger_kind=lsp.CompletionTriggerKind.TriggerCharacter,
                trigger_character=".",
            ),
        )
        result = handle_completion(params, source)
        item = next(i for i in result.items if i.label == "strategy.risk.max_drawdown")
        insert = str(item.insert_text)
        assert insert.startswith("risk.max_drawdown")
        assert not insert.startswith("max_drawdown")
        assert not insert.startswith("strategy.")

        nested_source = "//@version=6\nindicator('T')\nstrategy.risk."
        nested_params = lsp.CompletionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=14),
            context=lsp.CompletionContext(
                trigger_kind=lsp.CompletionTriggerKind.TriggerCharacter,
                trigger_character=".",
            ),
        )
        nested = handle_completion(nested_params, nested_source)
        nested_item = next(i for i in nested.items if i.label == "strategy.risk.max_drawdown")
        nested_insert = str(nested_item.insert_text)
        assert nested_insert.startswith("max_drawdown")
        assert "risk.max_drawdown" not in nested_insert

    def test_completion_resolve_preserves_leaf_insert_text(self) -> None:
        """Resolve must not restore the fully-qualified snippet after ``ta.``."""
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
        sma = next(i for i in result.items if i.label == "ta.sma")
        resolved = handle_completion_resolve(sma)
        assert resolved.insert_text == sma.insert_text
        assert not str(resolved.insert_text).startswith("ta.")

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
        assert "https://www.tradingview.com/pine-script-reference/v6/#fun_ta.sma" in result.contents.value

    def test_handle_hover_line_fill(self) -> None:
        """Hover over ``line.fill`` (alias of linefill.new)."""
        source = (
            "//@version=6\nindicator('T')\n"
            "line.fill(line.new(0, high, 1, low), line.new(0, low, 1, high), color.blue)\n"
        )
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=6),  # On "fill"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        assert "line.fill" in result.contents.value
        assert "https://www.tradingview.com/pine-script-reference/v6/#fun_line.fill" in result.contents.value

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
        assert "pine-script-reference" not in result.contents.value

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
        assert "pine-script-reference" not in result.contents.value

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
        assert "pine-script-reference" not in result.contents.value

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
        assert "pine-script-reference" not in result.contents.value

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
        assert "pine-script-reference" not in result.contents.value

    def test_handle_hover_line_namespace_and_type(self) -> None:
        """``line.fill`` module prefix is the namespace; bare ``line`` is the type."""
        dotted = (
            "//@version=6\nindicator('T')\n"
            "line.fill(line.new(0, high, 1, low), line.new(0, low, 1, high), color.blue)\n"
        )
        ns_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=1),  # on "line" in line.fill
        )
        ns_hover = handle_hover(ns_params, dotted)
        assert ns_hover is not None
        assert isinstance(ns_hover.contents, lsp.MarkupContent)
        ns_text = ns_hover.contents.value.lower()
        assert "namespace" in ns_text
        assert "line.fill" in ns_text or "line.new" in ns_text

        typed = "//@version=6\nindicator('T')\nline l = line.new(0, high, 1, low)\n"
        type_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=1),  # on type ``line``
        )
        type_hover = handle_hover(type_params, typed)
        assert type_hover is not None
        assert isinstance(type_hover.contents, lsp.MarkupContent)
        type_text = type_hover.contents.value.lower()
        assert "type" in type_text
        assert "namespace" not in type_text

    def test_handle_hover_log_namespace(self) -> None:
        """Hover on ``log`` in ``log.info`` documents the namespace."""
        source = '//@version=6\nindicator("T")\nlog.info("hi")\n'
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=1),  # on "log"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        text = result.contents.value.lower()
        assert "namespace" in text
        assert "log.info" in text or "log" in text

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
        assert "https://www.tradingview.com/pine-script-reference/v6/" not in text

        use_params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=3, character=6),  # on "foo" in plot(foo(1))
        )
        use_hover = handle_hover(use_params, source)
        assert use_hover is not None
        assert isinstance(use_hover.contents, lsp.MarkupContent)
        assert "foo(a)" in use_hover.contents.value
        assert "https://www.tradingview.com/pine-script-reference/v6/" not in use_hover.contents.value

    def test_handle_hover_library_annotations_markdown(self) -> None:
        """Library ``// @function`` annotations render multi-line Markdown."""
        source = """//@version=6
library("Lib")

// @function **Bold** heading
// #### Usage
// ```
// x = foo(1)
// ```
// @param a The first.
// @returns The result.
export foo(a) => a

plot(foo(1))
"""
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=12, character=6),  # on "foo" in plot(foo(1))
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        value = result.contents.value
        assert "**Bold** heading" in value
        assert "#### Usage" in value
        assert "```" in value
        assert "`a`: The first." in value
        assert "**Returns:** The result." in value

    def test_handle_hover_library_description(self) -> None:
        """``// @description`` on a library renders when hovering ``library``."""
        source = """//@version=6
// @description A **markdown** library.
// second line.
library("Lib")
"""
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=3, character=2),  # on "library"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        value = result.contents.value
        assert "**markdown** library." in value
        assert "second line." in value

    def test_handle_hover_type_annotations(self) -> None:
        """``// @type`` + ``// @field`` render a type hover card."""
        source = """//@version=6
indicator("T")

// @type A point.
// @field x The x coordinate.
// @field y The y coordinate.
export type Point
    float x
    float y
"""
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=6, character=13),  # on "Point"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        value = result.contents.value
        assert "A point." in value
        assert "`x`: The x coordinate." in value
        assert "`y`: The y coordinate." in value

    def test_handle_hover_variable_annotation(self) -> None:
        """``// @variable`` renders as a variable hover card."""
        source = """//@version=6
indicator("T")

// @variable An array of averages.
export myVar = array.new<float>()
"""
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=4, character=9),  # on "myVar"
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        assert "An array of averages." in result.contents.value

    def test_handle_hover_user_function_shadows_builtin(self) -> None:
        """A user function named like a builtin alias shows its annotation card."""
        source = """//@version=6
library("Lib")

// @function Custom bands.
// @param src Source series.
// @returns Bands.
export bb(series float src) => src

plot(bb(close))
"""
        params = lsp.HoverParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=8, character=6),  # on "bb" in plot(bb(close))
        )
        result = handle_hover(params, source)
        assert result is not None
        assert isinstance(result.contents, lsp.MarkupContent)
        value = result.contents.value
        assert "Custom bands." in value
        assert "`src`: Source series." in value
        assert "**Returns:** Bands." in value

    def test_build_docs_link_only_dotted_labels(self) -> None:
        """Docs links are dotted-namespace builtins only; empty / undotted stay blank."""
        from pynescript.langserver.features.hover import _build_docs_link

        sma = _build_docs_link("ta.sma")
        assert sma == ("[Pine v6: ta.sma](https://www.tradingview.com/pine-script-reference/v6/#fun_ta.sma)\n")
        entry = _build_docs_link("strategy.entry")
        assert "fun_strategy.entry" in entry
        assert entry.endswith("\n")
        fill = _build_docs_link("line.fill")
        assert "fun_line.fill" in fill
        assert _build_docs_link("") == ""
        assert _build_docs_link("sma") == ""
        assert _build_docs_link("   ") == ""


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

    def test_handle_on_type_formatting(self) -> None:
        """After newline, format the just-completed compact assignment line."""
        source = """//@version=5
indicator("Test")
length=14
plot(ta.sma(close,length))
"""
        params = lsp.DocumentOnTypeFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=3, character=0),
            ch="\n",
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )

        result = handle_on_type_formatting(params, source)
        assert result is not None
        assert len(result) == 1
        edit = result[0]
        assert edit.range.start.line == 2
        assert edit.range.start.character == 0
        assert edit.range.end.line == 2
        assert edit.range.end.character == len("length=14")
        assert edit.new_text == "length = 14"

    def test_handle_on_type_formatting_empty(self) -> None:
        """Empty source yields no on-type edits."""
        params = lsp.DocumentOnTypeFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),
            ch="\n",
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )
        assert handle_on_type_formatting(params, "") == []
        assert handle_on_type_formatting(params, None) == []

    def test_handle_on_type_formatting_unknown_ch(self) -> None:
        """Triggers other than newline are ignored."""
        source = """//@version=5
indicator("Test")
length=14
"""
        params = lsp.DocumentOnTypeFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=2, character=9),
            ch=";",
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )
        assert handle_on_type_formatting(params, source) == []

    def test_handle_on_type_formatting_unparsed(self) -> None:
        """Explicit tree=None (workspace parse failure) yields no edits."""
        source = """//@version=5
indicator("Test")
length=14
"""
        params = lsp.DocumentOnTypeFormattingParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=3, character=0),
            ch="\n",
            options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
        )
        assert handle_on_type_formatting(params, source, tree=None) == []


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

    def test_handle_semantic_tokens_range_sma_line(self) -> None:
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens_range

        source = """//@version=5
indicator("T")
length = 14
plot(ta.sma(close, length))
"""
        params = lsp.SemanticTokensRangeParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=3, character=0),
                end=lsp.Position(line=4, character=0),
            ),
        )
        result = handle_semantic_tokens_range(params, source)
        assert result is not None
        assert len(result.data) > 0
        assert len(result.data) % 5 == 0

    def test_handle_semantic_tokens_range_pragma_excludes_ta(self) -> None:
        from pynescript.langserver.config import semantic_token_types
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens_range

        source = """//@version=5
indicator("T")
length = 14
plot(ta.sma(close, length))
"""
        params = lsp.SemanticTokensRangeParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=1, character=0),
            ),
        )
        result = handle_semantic_tokens_range(params, source)
        assert result is not None
        assert len(result.data) % 5 == 0
        ns_index = semantic_token_types().index("namespace")
        decoded = _decode_semantic_tokens(result.data)
        assert all(ttype != ns_index for _, _, _, ttype, _ in decoded)

    def test_handle_semantic_tokens_range_empty_unparsed(self) -> None:
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens_range

        params = lsp.SemanticTokensRangeParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=1, character=0),
            ),
        )
        empty = handle_semantic_tokens_range(params, "")
        missing = handle_semantic_tokens_range(params, None)
        unparsed = handle_semantic_tokens_range(params, "//@version=5\nplot(ta.")
        tree_none = handle_semantic_tokens_range(params, "x = 1", tree=None)
        assert empty is not None and empty.data == []
        assert missing is not None and missing.data == []
        assert unparsed is not None and unparsed.data == []
        assert tree_none is not None and tree_none.data == []

    def test_handle_semantic_tokens_range_is_subsequence_of_full(self) -> None:
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens
        from pynescript.langserver.features.semantic_tokens import handle_semantic_tokens_range

        source = """//@version=5
indicator("T")
length = 14
plot(ta.sma(close, length))
"""
        full_params = lsp.SemanticTokensParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        )
        range_params = lsp.SemanticTokensRangeParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=3, character=0),
                end=lsp.Position(line=4, character=0),
            ),
        )
        full = handle_semantic_tokens(full_params, source)
        clipped = handle_semantic_tokens_range(range_params, source)
        assert full is not None and clipped is not None
        full_abs = _decode_semantic_tokens(full.data)
        range_abs = _decode_semantic_tokens(clipped.data)
        full_iter = iter(full_abs)
        for token in range_abs:
            for candidate in full_iter:
                if candidate == token:
                    break
            else:
                raise AssertionError(f"range token {token} not a subsequence of full")

    def test_semantic_tokens_range_capability(self) -> None:
        from pynescript.langserver.config import get_server_capabilities

        caps = get_server_capabilities()
        assert caps.semantic_tokens_provider is not None
        assert caps.semantic_tokens_provider.range


class TestConvertToV6:
    """Source-level Convert-to-v6 command + code action."""

    def test_handle_convert_rewrites_v4(self) -> None:
        src = '//@version=4\nstudy("t")\nplot(sma(close, 14))\n'
        payload = handle_convert_to_v6(src)
        assert payload["from_version"] == 4
        assert payload["to_version"] == 6
        assert payload["changed"] is True
        assert "ta.sma(" in payload["source"]
        assert "indicator(" in payload["source"]

    def test_code_action_offered_for_old_version(self) -> None:
        src = '//@version=5\nindicator("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src)
        assert len(actions) == 1
        assert "v5" in actions[0].title
        assert actions[0].edit is not None

    def test_code_action_hidden_for_v6(self) -> None:
        src = '//@version=6\nindicator("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        assert handle_code_action(params, src) == []

    def test_w001_quickfix_inserts_version_pragma(self) -> None:
        src = 'indicator("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src)
        quick = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick) == 1
        action = quick[0]
        edit = _first_text_edit(action)
        assert edit.new_text == "//@version=6\n"
        assert edit.range.start == lsp.Position(line=0, character=0)
        assert edit.range.end == lsp.Position(line=0, character=0)

    def test_w001_quickfix_hidden_when_version_present(self) -> None:
        src = '//@version=6\nindicator("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src)
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions)

    def test_v5_still_offers_convert_not_w001(self) -> None:
        src = '//@version=5\nindicator("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src)
        assert any(a.kind == lsp.CodeActionKind.RefactorRewrite for a in actions)
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions)

    def test_w002_quickfix_replaces_old_pragma(self) -> None:
        src = '//@version=4\nstudy("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src)
        assert any(a.kind == lsp.CodeActionKind.RefactorRewrite for a in actions)
        quick = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick) == 1
        edit = _first_text_edit(quick[0])
        assert edit.new_text == "//@version=6"
        from pynescript.langserver.workspace import _apply_text_edit

        fixed = _apply_text_edit(src, edit.range, edit.new_text)
        assert fixed.startswith("//@version=6\n")
        assert "//@version=4" not in fixed
        assert fixed.count("//@version=") == 1

    def test_w002_quickfix_from_lint_warnings(self) -> None:
        from pynescript.ast.linter import lint_script

        src = '// license\n//@version=3\nindicator("t")\nplot(close)\n'
        warnings = lint_script(src)
        assert any(w.code == "W002" for w in warnings)
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=1, character=0),
                end=lsp.Position(line=1, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src, warnings)
        quick = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick) == 1
        edit = _first_text_edit(quick[0])
        from pynescript.langserver.workspace import _apply_text_edit

        fixed = _apply_text_edit(src, edit.range, edit.new_text)
        assert fixed.startswith("// license\n//@version=6\n")
        assert "//@version=3" not in fixed
        assert fixed.count("//@version=") == 1

    def test_w002_quickfix_hidden_for_v6(self) -> None:
        src = '//@version=6\nindicator("t")\nplot(close)\n'
        params = lsp.CodeActionParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///t.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=0, character=1),
            ),
            context=lsp.CodeActionContext(diagnostics=[]),
        )
        actions = handle_code_action(params, src)
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions)


_C002_LONG_TITLE = (
    "This is a very very very very very very very very very very very "
    "very very very very very very very very very very long line"
)
_C002_SRC = f'//@version=6\nindicator(  "t"  )\nplot(  ta.sma( close,14 ), title="{_C002_LONG_TITLE}"  )\n'


def _code_action_params(uri: str = "file:///t.pine") -> lsp.CodeActionParams:
    return lsp.CodeActionParams(
        text_document=lsp.TextDocumentIdentifier(uri=uri),
        range=lsp.Range(
            start=lsp.Position(line=2, character=0),
            end=lsp.Position(line=2, character=1),
        ),
        context=lsp.CodeActionContext(diagnostics=[]),
    )


def _format_params(uri: str = "file:///t.pine") -> lsp.DocumentFormattingParams:
    return lsp.DocumentFormattingParams(
        text_document=lsp.TextDocumentIdentifier(uri=uri),
        options=lsp.FormattingOptions(tab_size=4, insert_spaces=True),
    )


class TestC002QuickFix:
    """C002 long-line QuickFix applies the same edit as format-document."""

    def test_c002_quickfix_formats_document(self) -> None:
        from pynescript.ast.linter import lint_script

        src = _C002_SRC
        warnings = lint_script(src)
        assert any(w.code == "C002" for w in warnings)
        expected = handle_formatting(_format_params(), src)
        assert expected

        actions = handle_code_action(_code_action_params(), src, warnings)
        quick = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick) == 1
        action = quick[0]
        assert action.command is None
        assert action.kind == lsp.CodeActionKind.QuickFix
        edit = _first_text_edit(action)
        assert edit.new_text == expected[0].new_text
        assert edit.range == expected[0].range

    def test_c002_quickfix_not_invented_without_warning(self) -> None:
        actions = handle_code_action(_code_action_params(), _C002_SRC)
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions)
        actions_empty = handle_code_action(_code_action_params(), _C002_SRC, [])
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions_empty)

    def test_c002_quickfix_hidden_when_unchanged(self) -> None:
        from pynescript.ast.linter import lint_script

        formatted = handle_formatting(_format_params(), _C002_SRC)
        assert formatted
        src = formatted[0].new_text
        assert handle_formatting(_format_params(), src) == []
        warnings = lint_script(src)
        assert any(w.code == "C002" for w in warnings)
        actions = handle_code_action(_code_action_params(), src, warnings)
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions)

    def test_c002_quickfix_hidden_when_unparsed(self) -> None:
        from pynescript.ast.linter import lint_script

        src = f'//@version=6\nindicator("t"\nplot(ta.sma(close, 14), title="{_C002_LONG_TITLE}")\n'
        warnings = lint_script(src)
        assert any(w.code == "C002" for w in warnings)
        assert handle_formatting(_format_params(), src) == []
        actions = handle_code_action(_code_action_params(), src, warnings)
        assert not any(a.kind == lsp.CodeActionKind.QuickFix for a in actions)

    def test_c002_one_fix_for_multiple_long_lines(self) -> None:
        from pynescript.ast.linter import lint_script

        src = _C002_SRC + f'plot(close, title="{_C002_LONG_TITLE}")\n'
        warnings = lint_script(src)
        assert sum(1 for w in warnings if w.code == "C002") >= 2
        actions = handle_code_action(_code_action_params(), src, warnings)
        quick = [a for a in actions if a.kind == lsp.CodeActionKind.QuickFix]
        assert len(quick) == 1

    def test_c002_does_not_replace_w001_or_convert(self) -> None:
        from pynescript.ast.linter import lint_script

        src = f'indicator(  "t"  )\nplot(  close, title="{_C002_LONG_TITLE}"  )\n'
        warnings = lint_script(src)
        assert any(w.code == "C002" for w in warnings)
        actions = handle_code_action(_code_action_params(), src, warnings)
        assert any(a.kind == lsp.CodeActionKind.RefactorRewrite for a in actions)
        titles = {a.title for a in actions if a.kind == lsp.CodeActionKind.QuickFix}
        assert "Add @version=6 declaration" in titles
        assert any("format" in t.lower() for t in titles)


def _first_text_edit(action: lsp.CodeAction) -> lsp.TextEdit:
    """Return the first TextEdit on a code action workspace edit."""
    edit = action.edit
    assert edit is not None
    if edit.document_changes:
        change = edit.document_changes[0]
        assert isinstance(change, lsp.TextDocumentEdit)
        first = change.edits[0]
        assert isinstance(first, lsp.TextEdit)
        return first
    if edit.changes:
        uri_edits = next(iter(edit.changes.values()))
        first = uri_edits[0]
        assert isinstance(first, lsp.TextEdit)
        return first
    missing = "code action has no text edit"
    raise AssertionError(missing)


def _position_after(source: str, prefix: str) -> lsp.Position:
    """LSP position immediately after the first occurrence of *prefix*."""
    idx = source.index(prefix) + len(prefix)
    line = source.count("\n", 0, idx)
    col = idx - (source.rfind("\n", 0, idx) + 1)
    return lsp.Position(line=line, character=col)


def _signature_params(source: str, prefix: str) -> lsp.SignatureHelpParams:
    return lsp.SignatureHelpParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        position=_position_after(source, prefix),
    )


def _param_label(param: lsp.ParameterInformation) -> str:
    label = param.label
    return label if isinstance(label, str) else ""


class TestSignatureHelpHandler:
    """textDocument/signatureHelp for builtins and user FunctionDef."""

    def test_builtin_plot_after_paren(self) -> None:
        source = "//@version=6\nindicator('T')\nplot(close)\n"
        result = handle_signature_help(_signature_params(source, "plot("), source)
        assert result is not None
        assert result.active_signature == 0
        assert result.active_parameter == 0
        assert result.signatures
        assert "plot" in result.signatures[0].label

    def test_builtin_ta_sma_after_comma(self) -> None:
        source = "//@version=6\nindicator('T')\nta.sma(close, 14)\n"
        result = handle_signature_help(_signature_params(source, "ta.sma(close,"), source)
        assert result is not None
        assert result.active_signature == 0
        assert result.active_parameter == 1
        labels = [_param_label(p) for p in (result.signatures[0].parameters or [])]
        assert len(labels) >= 2

    def test_nested_parens_innermost_callee(self) -> None:
        source = "//@version=6\nindicator('T')\nplot(math.max(close, open))\n"
        result = handle_signature_help(_signature_params(source, "math.max(close,"), source)
        assert result is not None
        label = result.signatures[0].label
        assert "max" in label
        assert not label.startswith("plot")

    def test_user_function_active_parameter(self) -> None:
        source = "//@version=6\nindicator('T')\nf(int x, int y) => x + y\nplot(f(1, 2))\n"
        result = handle_signature_help(_signature_params(source, "plot(f(1,"), source)
        assert result is not None
        assert result.active_parameter == 1
        labels = [_param_label(p) for p in (result.signatures[0].parameters or [])]
        assert any("y" in lab for lab in labels)

    def test_outside_call_returns_none(self) -> None:
        source = "//@version=6\nindicator('T')\nlength = 14\n"
        params = lsp.SignatureHelpParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=_position_after(source, "len"),
        )
        assert handle_signature_help(params, source) is None

    def test_unknown_callee_returns_none(self) -> None:
        source = "//@version=6\nindicator('T')\nzzz_unknown(1, 2)\n"
        assert handle_signature_help(_signature_params(source, "zzz_unknown("), source) is None

    def test_empty_source_returns_none(self) -> None:
        params = lsp.SignatureHelpParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),
        )
        assert handle_signature_help(params, "") is None
        assert handle_signature_help(params, None) is None


_FOLD_SOURCE = """//@version=6
indicator("T")

if close > 0
    x = 1
    y = 2
else if close < 0
    x = 3
else
    x = 4

for i = 0 to 10
    s = i

for v in array.from(1, 2)
    t = v

while bar_index < 3
    n = 1

switch close
    0 => 0
    => 1

once bar_index == 0
    z = 1

f() =>
    a = 1
    a

g() => 1

type Point
    float x
    float y

enum Side
    buy
    sell

//#region foo
plot(close)
//#endregion

# region hash
plot(1)
# endregion
"""


def _folding_params() -> lsp.FoldingRangeParams:
    return lsp.FoldingRangeParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
    )


def _line_of(source: str, needle: str) -> int:
    for i, line in enumerate(source.splitlines()):
        if needle in line:
            return i
    msg = f"needle not found: {needle!r}"
    raise AssertionError(msg)


def _fold_starting(ranges: list[lsp.FoldingRange], start_line: int) -> lsp.FoldingRange:
    matches = [r for r in ranges if r.start_line == start_line]
    assert matches, f"no fold starting at line {start_line}"
    return max(matches, key=lambda r: r.end_line)


def _assert_block_fold(
    ranges: list[lsp.FoldingRange],
    source: str,
    start_needle: str,
    last_body_needle: str,
    next_needle: str | None = None,
) -> lsp.FoldingRange:
    start = _line_of(source, start_needle)
    last_body = _line_of(source, last_body_needle)
    rng = _fold_starting(ranges, start)
    assert rng.end_line >= last_body, (start_needle, rng, last_body)
    if next_needle is not None:
        nxt = _line_of(source, next_needle)
        assert rng.end_line < nxt, (start_needle, rng, nxt)
    return rng


class TestFoldingRangeHandler:
    """Test textDocument/foldingRange for blocks and region comments."""

    def test_handle_folding_range_blocks_and_regions(self) -> None:
        """if/for/while/switch/once/type/enum/function and //#region folds."""
        result = handle_folding_range(_folding_params(), _FOLD_SOURCE)
        assert result
        src = _FOLD_SOURCE

        _assert_block_fold(result, src, "if close > 0", "x = 4", "for i = 0 to 10")
        _assert_block_fold(result, src, "else if close < 0", "x = 4", "for i = 0 to 10")
        _assert_block_fold(result, src, "for i = 0 to 10", "s = i", "for v in")
        _assert_block_fold(result, src, "for v in", "t = v", "while bar_index")
        _assert_block_fold(result, src, "while bar_index", "n = 1", "switch close")
        _assert_block_fold(result, src, "switch close", "=> 1", "once bar_index")
        _assert_block_fold(result, src, "once bar_index", "z = 1", "f() =>")
        _assert_block_fold(result, src, "f() =>", "    a", "g() =>")
        _assert_block_fold(result, src, "type Point", "float y", "enum Side")
        _assert_block_fold(result, src, "enum Side", "sell", "//#region foo")

        # One-line function is not a fold.
        g_line = _line_of(src, "g() => 1")
        assert all(r.start_line != g_line for r in result)

        regions = [r for r in result if r.kind == lsp.FoldingRangeKind.Region]
        assert len(regions) == 2
        slash = next(r for r in regions if r.start_line == _line_of(src, "//#region foo"))
        assert slash.end_line == _line_of(src, "//#endregion")
        hashed = next(r for r in regions if r.start_line == _line_of(src, "# region hash"))
        assert hashed.end_line == _line_of(src, "# endregion")

    def test_handle_folding_range_empty_and_unparsed(self) -> None:
        """Empty source and parse failure return an empty list."""
        params = _folding_params()
        assert handle_folding_range(params, "") == []
        assert handle_folding_range(params, None) == []
        assert handle_folding_range(params, "this is not valid pine @#$") == []
        assert handle_folding_range(params, "x = 1", tree=None) == []

    def test_handle_folding_range_reuses_tree(self) -> None:
        """Passing a pre-parsed tree must not require re-parse of source."""
        from pynescript.ast.helper import parse

        tree = parse(_FOLD_SOURCE, filename="file:///test.pine")
        result = handle_folding_range(_folding_params(), source=None, tree=tree)
        if_fold = _fold_starting(result, _line_of(_FOLD_SOURCE, "if close > 0"))
        assert if_fold.end_line > if_fold.start_line
        # Regions come from source lines; omitted when source is None.
        assert all(r.kind != lsp.FoldingRangeKind.Region for r in result)


_SEL_SOURCE = """//@version=6
indicator("T")
foo = close
if bar_index > 0
    plot(foo)
    if close > 0
        x = foo + 1
for i = 0 to 10
    s = i
while bar_index < 3
    n = 1
switch close
    0 => 0
    => 1
once bar_index == 0
    z = 1
f() =>
    a = 1
    a
type Point
    float px
enum Side
    buy
"""


def _sel_params(source: str, *prefixes: str) -> lsp.SelectionRangeParams:
    return lsp.SelectionRangeParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        positions=[_position_after(source, p) for p in prefixes],
    )


def _flatten_sel(sr: lsp.SelectionRange) -> list[lsp.Range]:
    out: list[lsp.Range] = []
    cur: lsp.SelectionRange | None = sr
    while cur is not None:
        out.append(cur.range)
        cur = cur.parent
    return out


def _slice_range(source: str, rng: lsp.Range) -> str:
    lines = source.split("\n")
    if rng.start.line == rng.end.line:
        return lines[rng.start.line][rng.start.character : rng.end.character]
    parts = [lines[rng.start.line][rng.start.character :]]
    for i in range(rng.start.line + 1, rng.end.line):
        parts.append(lines[i])
    if rng.end.line < len(lines):
        parts.append(lines[rng.end.line][: rng.end.character])
    return "\n".join(parts)


def _assert_sel_nested(ranges: list[lsp.Range]) -> None:
    assert ranges
    for i in range(len(ranges) - 1):
        inner, outer = ranges[i], ranges[i + 1]
        assert (outer.start.line, outer.start.character) <= (inner.start.line, inner.start.character)
        assert (inner.end.line, inner.end.character) <= (outer.end.line, outer.end.character)


class TestSelectionRangeHandler:
    """Test textDocument/selectionRange for idents, statements, and blocks."""

    def test_handle_selection_range_empty_and_unparsed(self) -> None:
        """Empty source, parse failure, and no node under the cursor return []."""
        params = _sel_params(_SEL_SOURCE, "foo")
        assert handle_selection_range(params, "") == []
        assert handle_selection_range(params, None) == []
        assert handle_selection_range(params, "this is not valid pine @#$") == []
        assert handle_selection_range(params, "x = 1", tree=None) == []
        pragma = _sel_params(_SEL_SOURCE)
        pragma.positions = [lsp.Position(line=0, character=0)]
        assert handle_selection_range(pragma, _SEL_SOURCE) == []

    def test_handle_selection_range_ident_then_statement(self) -> None:
        """Top-level ident expands to the enclosing assignment."""
        result = handle_selection_range(_sel_params(_SEL_SOURCE, "foo"), _SEL_SOURCE)
        assert len(result) == 1
        chain = _flatten_sel(result[0])
        _assert_sel_nested(chain)
        assert _slice_range(_SEL_SOURCE, chain[0]) == "foo"
        assert any("foo = close" in _slice_range(_SEL_SOURCE, r) for r in chain)

    def test_handle_selection_range_nested_if_blocks(self) -> None:
        """Ident inside nested if: ident → statement → inner If → outer If."""
        result = handle_selection_range(_sel_params(_SEL_SOURCE, "x = "), _SEL_SOURCE)
        assert len(result) == 1
        chain = _flatten_sel(result[0])
        _assert_sel_nested(chain)
        assert _slice_range(_SEL_SOURCE, chain[0]) == "foo"
        texts = [_slice_range(_SEL_SOURCE, r) for r in chain]
        assert any("x = foo + 1" in t for t in texts)
        assert any("if close > 0" in t for t in texts)
        assert any("if bar_index > 0" in t for t in texts)
        assert texts[-1].startswith("if bar_index") or "if bar_index > 0" in texts[-1]

    def test_handle_selection_range_for_while_switch_once(self) -> None:
        """Idents in for/while/switch/once expand through the enclosing block."""
        cases = (
            ("    s", "s", "for i = 0 to 10"),
            ("    n", "n", "while bar_index < 3"),
            ("switch ", "close", "switch close"),
            ("    z", "z", "once bar_index == 0"),
        )
        for prefix, ident, header in cases:
            result = handle_selection_range(_sel_params(_SEL_SOURCE, prefix), _SEL_SOURCE)
            assert len(result) == 1, header
            chain = _flatten_sel(result[0])
            _assert_sel_nested(chain)
            assert _slice_range(_SEL_SOURCE, chain[0]) == ident
            texts = [_slice_range(_SEL_SOURCE, r) for r in chain]
            assert any(header in t for t in texts), (header, texts)

    def test_handle_selection_range_function_type_enum(self) -> None:
        """Idents in FunctionDef / TypeDef / EnumDef expand to that block."""
        cases = (
            ("    a", "a", "f() =>"),
            ("float ", "px", "type Point"),
            ("    buy", "buy", "enum Side"),
        )
        for prefix, ident, header in cases:
            result = handle_selection_range(_sel_params(_SEL_SOURCE, prefix), _SEL_SOURCE)
            assert len(result) == 1, header
            chain = _flatten_sel(result[0])
            _assert_sel_nested(chain)
            assert _slice_range(_SEL_SOURCE, chain[0]) == ident
            texts = [_slice_range(_SEL_SOURCE, r) for r in chain]
            assert any(header in t for t in texts), (header, texts)

    def test_handle_selection_range_smallest_node_without_ident(self) -> None:
        """Cursor on a literal still expands from the smallest AST node."""
        result = handle_selection_range(_sel_params(_SEL_SOURCE, "foo + "), _SEL_SOURCE)
        assert len(result) == 1
        chain = _flatten_sel(result[0])
        _assert_sel_nested(chain)
        assert _slice_range(_SEL_SOURCE, chain[0]) == "1"
        texts = [_slice_range(_SEL_SOURCE, r) for r in chain]
        assert any("x = foo + 1" in t for t in texts)
        assert any("if close > 0" in t for t in texts)

    def test_handle_selection_range_multiple_positions(self) -> None:
        """One SelectionRange per requested position."""
        result = handle_selection_range(_sel_params(_SEL_SOURCE, "foo", "    a"), _SEL_SOURCE)
        assert len(result) == 2
        assert _slice_range(_SEL_SOURCE, _flatten_sel(result[0])[0]) == "foo"
        assert _slice_range(_SEL_SOURCE, _flatten_sel(result[1])[0]) == "a"

    def test_handle_selection_range_reuses_tree(self) -> None:
        """Passing a pre-parsed tree must not require re-parse of source."""
        from pynescript.ast.helper import parse

        tree = parse(_SEL_SOURCE, filename="file:///test.pine")
        result = handle_selection_range(_sel_params(_SEL_SOURCE, "x = "), source=None, tree=tree)
        assert len(result) == 1
        chain = _flatten_sel(result[0])
        _assert_sel_nested(chain)
        assert chain[0].start.line == _line_of(_SEL_SOURCE, "x = foo + 1")


_COLOR_SOURCE = """//@version=6
indicator("T")
c1 = #ff0000
c2 = #00ff00aa
plot(close, color=#2962FF)
bgcolor(#22AB94)
plot(close, title="#ff00ff")
col = color.red
"""


def _color_params() -> lsp.DocumentColorParams:
    return lsp.DocumentColorParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
    )


def _range_of_hex(source: str, needle: str) -> lsp.Range:
    idx = source.index(needle)
    line = source.count("\n", 0, idx)
    col = idx - (source.rfind("\n", 0, idx) + 1)
    return lsp.Range(
        start=lsp.Position(line=line, character=col),
        end=lsp.Position(line=line, character=col + len(needle)),
    )


def _color_at(infos: list[lsp.ColorInformation], source: str, needle: str) -> lsp.Color:
    rng = _range_of_hex(source, needle)
    matches = [info for info in infos if info.range == rng]
    assert matches, f"no ColorInformation for {needle!r}"
    return matches[0].color


def _assert_rgba(color: lsp.Color, r: int, g: int, b: int, a: int = 255) -> None:
    assert color.red == r / 255.0
    assert color.green == g / 255.0
    assert color.blue == b / 255.0
    assert color.alpha == a / 255.0


_COLOR_NAMED_SOURCE = """//@version=6
indicator("T")
col = color.red
plot(close, color=color.green)
bgcolor(color.gray)
fill(p1, p2, color=color.fuchsia)
"""

_COLOR_RGB_SOURCE = """//@version=6
indicator("T")
c = color.rgb(255, 0, 0)
d = color.rgb(33, 150, 243, 95)
e = color.rgb(10, 20, 30, transp=50)
f = color.rgb(red=1, green=2, blue=3)
x = 255
skip = color.rgb(x, 0, 0)
nested = color.rgb(color.r(color.blue), 0, 0)
n = color.new(color.white, 50)
unk = color.foo
ch = color.r
title = "#00ff00"
"""

_COLOR_QUOTED_SOURCE = """//@version=6
indicator("T")
a = "#ff0000"
b = "#00ff00aa"
c = "#2962FF"
skip = "not-a-color"
bare = "ff0000"
"""

_COLOR_NEW_SOURCE = """//@version=6
indicator("T")
n = color.new(color.white, 50)
n2 = color.new(#ff0000, 25)
n3 = color.new("#00ff00", 0)
n4 = color.new(color.red, transp=75)
n5 = color.new(color=#2962FF, transp=10)
kw = color.new(transp=50, color=color.blue)
one = color.new(color.white)
skip = color.new(x, 50)
skip2 = color.new(color.white, t)
skip3 = color.new(color.rgb(1, 2, 3), 50)
extra = color.new(color.white, 50, 1)
"""

_COLOR_ALIAS_SOURCE = """//@version=6
indicator("T")
n = color(color.white, 50)
n2 = color(#ff0000, 25)
n3 = color("#00ff00", 0)
n4 = color(color.red, transp=75)
n5 = color(color=#2962FF, transp=10)
kw = color(transp=50, color=color.blue)
one = color(color.white)
skip = color(x, 50)
skip2 = color(color.white, t)
skip3 = color(color.rgb(1, 2, 3), 50)
extra = color(color.white, 50, 1)
"""

_COLOR_GRAD_SOURCE = """//@version=6
indicator("T")
g = color.from_gradient(5, 0, 10, #000000, #ffffff)
g2 = color.from_gradient(50, 0, 100, color.red, color.green)
g3 = color.from_gradient(0, 0, 100, "#ff0000", #00ff00aa)
g4 = color.from_gradient(value=99, bottom_value=0, top_value=10, bottom_color=#000000, top_color=#ffffff)
g5 = color.from_gradient(5, 5, 5, color.black, color.white)
g6 = color.from_gradient(-5, -10, 10, #ff0000, #00ff00)
kw = color.from_gradient(bottom_color=color.blue, top_color=color.yellow, value=25, bottom_value=0, top_value=100)
py = color.from_gradient(value=5, min_val=0, max_val=10, color1=#111111, color2=#eeeeee)
skip = color.from_gradient(close, 0, 100, color.red, color.green)
skip2 = color.from_gradient(50, lo, 100, color.red, color.green)
skip3 = color.from_gradient(50, 0, 100, color.rgb(1, 2, 3), color.green)
skip4 = color.from_gradient(50, 0, 100, color.red)
skip5 = color.from_gradient(50, 0, 100, color.red, color.green, 1)
one = color.from_gradient(50, 0, 100, x, color.green)
"""


class TestDocumentColorHandler:
    """Test documentColor / colorPresentation for #hex, color.*, rgb, new, color(), from_gradient."""

    def test_handle_document_color_empty_and_unparsed(self) -> None:
        """Empty source and parse failure return an empty list."""
        params = _color_params()
        assert handle_document_color(params, "") == []
        assert handle_document_color(params, None) == []
        assert handle_document_color(params, "this is not valid pine @#$") == []
        assert handle_document_color(params, "x = 1", tree=None) == []

    def test_handle_document_color_hex_literals(self) -> None:
        """#rrggbb / #rrggbbaa literals become 0-1 RGBA ColorInformation."""
        result = handle_document_color(_color_params(), _COLOR_SOURCE)
        src = _COLOR_SOURCE
        hexes = ("#ff0000", "#00ff00aa", "#2962FF", "#22AB94")
        found = {_slice_range(src, info.range) for info in result}
        assert set(hexes) <= found
        _assert_rgba(_color_at(result, src, "#ff0000"), 0xFF, 0, 0)
        _assert_rgba(_color_at(result, src, "#00ff00aa"), 0, 0xFF, 0, 0xAA)
        _assert_rgba(_color_at(result, src, "#2962FF"), 0x29, 0x62, 0xFF)
        _assert_rgba(_color_at(result, src, "#22AB94"), 0x22, 0xAB, 0x94)

    def test_handle_document_color_quoted_hex_strings(self) -> None:
        """Quoted \"#rrggbb\" / \"#rrggbbaa\" Constants are document colors (range includes quotes)."""
        src = _COLOR_QUOTED_SOURCE
        result = handle_document_color(_color_params(), src)
        found = {_slice_range(src, info.range) for info in result}
        assert found == {'"#ff0000"', '"#00ff00aa"', '"#2962FF"'}
        _assert_rgba(_color_at(result, src, '"#ff0000"'), 0xFF, 0, 0)
        _assert_rgba(_color_at(result, src, '"#00ff00aa"'), 0, 0xFF, 0, 0xAA)
        _assert_rgba(_color_at(result, src, '"#2962FF"'), 0x29, 0x62, 0xFF)
        texts = list(found)
        assert "not-a-color" not in texts
        assert '"not-a-color"' not in texts
        assert "ff0000" not in texts
        assert '"ff0000"' not in texts

    def test_handle_document_color_named_constants(self) -> None:
        """color.red / color.green / … Attributes become palette RGBA swatches."""
        src = _COLOR_NAMED_SOURCE
        result = handle_document_color(_color_params(), src)
        found = {_slice_range(src, info.range) for info in result}
        assert found == {"color.red", "color.green", "color.gray", "color.fuchsia"}
        _assert_rgba(_color_at(result, src, "color.red"), 0xF2, 0x36, 0x45)
        _assert_rgba(_color_at(result, src, "color.green"), 0x22, 0xAB, 0x94)
        _assert_rgba(_color_at(result, src, "color.gray"), 0x78, 0x7B, 0x86)
        _assert_rgba(_color_at(result, src, "color.fuchsia"), 0xE0, 0x40, 0xFB)

    def test_handle_document_color_hex_source_includes_named(self) -> None:
        """Mixed hex + color.red + quoted title hex are all reported."""
        result = handle_document_color(_color_params(), _COLOR_SOURCE)
        found = {_slice_range(_COLOR_SOURCE, info.range) for info in result}
        assert "color.red" in found
        assert '"#ff00ff"' in found
        _assert_rgba(_color_at(result, _COLOR_SOURCE, "color.red"), 0xF2, 0x36, 0x45)
        _assert_rgba(_color_at(result, _COLOR_SOURCE, '"#ff00ff"'), 0xFF, 0, 0xFF)

    def test_handle_document_color_rgb_literals(self) -> None:
        """color.rgb with numeric literals (optional transp 0-100) is a swatch."""
        src = _COLOR_RGB_SOURCE
        result = handle_document_color(_color_params(), src)
        _assert_rgba(_color_at(result, src, "color.rgb(255, 0, 0)"), 255, 0, 0)
        # transp 95 → alpha = round(255 * (1 - 0.95)) = 13
        _assert_rgba(_color_at(result, src, "color.rgb(33, 150, 243, 95)"), 33, 150, 243, 13)
        # transp 50 → alpha = round(255 * 0.5) = 128
        _assert_rgba(_color_at(result, src, "color.rgb(10, 20, 30, transp=50)"), 10, 20, 30, 128)
        _assert_rgba(_color_at(result, src, "color.rgb(red=1, green=2, blue=3)"), 1, 2, 3)

    def test_handle_document_color_rgb_skips_non_literals(self) -> None:
        """Non-literal rgb args, unknown color.foo, and color.r are skipped."""
        src = _COLOR_RGB_SOURCE
        result = handle_document_color(_color_params(), src)
        texts = [_slice_range(src, info.range) for info in result]
        assert "color.rgb(x, 0, 0)" not in texts
        assert "color.rgb(color.r(color.blue), 0, 0)" not in texts
        assert "color.foo" not in texts
        assert "color.r" not in texts
        # nested named constant inside the skipped rgb call is still a swatch
        assert "color.blue" in texts
        assert "color.white" in texts
        # leftover quoted hex / color.new in this source are now swatches
        assert '"#00ff00"' in texts
        assert "color.new(color.white, 50)" in texts

    def test_handle_document_color_color_new_literals(self) -> None:
        """color.new with literal color + transp (0-100) applies Pine transparency."""
        src = _COLOR_NEW_SOURCE
        result = handle_document_color(_color_params(), src)
        # transp 50 → alpha = round(255 * 0.5) = 128
        _assert_rgba(_color_at(result, src, "color.new(color.white, 50)"), 0xFF, 0xFF, 0xFF, 128)
        # transp 25 → alpha = round(255 * 0.75) = 191
        _assert_rgba(_color_at(result, src, "color.new(#ff0000, 25)"), 0xFF, 0, 0, 191)
        _assert_rgba(_color_at(result, src, 'color.new("#00ff00", 0)'), 0, 0xFF, 0)
        # transp 75 → alpha = round(255 * 0.25) = 64
        _assert_rgba(_color_at(result, src, "color.new(color.red, transp=75)"), 0xF2, 0x36, 0x45, 64)
        # transp 10 → alpha = round(255 * 0.9) = 230
        _assert_rgba(_color_at(result, src, "color.new(color=#2962FF, transp=10)"), 0x29, 0x62, 0xFF, 230)
        _assert_rgba(_color_at(result, src, "color.new(transp=50, color=color.blue)"), 0x29, 0x62, 0xFF, 128)
        # inner literals remain swatches
        found = {_slice_range(src, info.range) for info in result}
        assert "color.white" in found
        assert "#ff0000" in found
        assert '"#00ff00"' in found
        assert "color.red" in found
        assert "color.blue" in found
        assert "color.rgb(1, 2, 3)" in found

    def test_handle_document_color_color_new_skips_non_literals(self) -> None:
        """color.new needs both args as literals; extra/non-literal args skip the call."""
        src = _COLOR_NEW_SOURCE
        result = handle_document_color(_color_params(), src)
        texts = [_slice_range(src, info.range) for info in result]
        assert "color.new(color.white)" not in texts
        assert "color.new(x, 50)" not in texts
        assert "color.new(color.white, t)" not in texts
        assert "color.new(color.rgb(1, 2, 3), 50)" not in texts
        assert "color.new(color.white, 50, 1)" not in texts

    def test_handle_document_color_color_alias_literals(self) -> None:
        """color() is Pine's alias of color.new; same literal args yield the same swatch."""
        src = _COLOR_ALIAS_SOURCE
        result = handle_document_color(_color_params(), src)
        # transp 50 → alpha = round(255 * 0.5) = 128
        _assert_rgba(_color_at(result, src, "color(color.white, 50)"), 0xFF, 0xFF, 0xFF, 128)
        # transp 25 → alpha = round(255 * 0.75) = 191
        _assert_rgba(_color_at(result, src, "color(#ff0000, 25)"), 0xFF, 0, 0, 191)
        _assert_rgba(_color_at(result, src, 'color("#00ff00", 0)'), 0, 0xFF, 0)
        # transp 75 → alpha = round(255 * 0.25) = 64
        _assert_rgba(_color_at(result, src, "color(color.red, transp=75)"), 0xF2, 0x36, 0x45, 64)
        # transp 10 → alpha = round(255 * 0.9) = 230
        _assert_rgba(_color_at(result, src, "color(color=#2962FF, transp=10)"), 0x29, 0x62, 0xFF, 230)
        _assert_rgba(_color_at(result, src, "color(transp=50, color=color.blue)"), 0x29, 0x62, 0xFF, 128)
        found = {_slice_range(src, info.range) for info in result}
        assert "color.white" in found
        assert "#ff0000" in found
        assert '"#00ff00"' in found
        assert "color.red" in found
        assert "color.blue" in found
        assert "color.rgb(1, 2, 3)" in found

    def test_handle_document_color_color_alias_skips_non_literals(self) -> None:
        """color() needs both args as literals, same as color.new."""
        src = _COLOR_ALIAS_SOURCE
        result = handle_document_color(_color_params(), src)
        texts = [_slice_range(src, info.range) for info in result]
        assert "color(color.white)" not in texts
        assert "color(x, 50)" not in texts
        assert "color(color.white, t)" not in texts
        assert "color(color.rgb(1, 2, 3), 50)" not in texts
        assert "color(color.white, 50, 1)" not in texts

    def test_handle_document_color_from_gradient_literals(self) -> None:
        """color.from_gradient interpolates RGBA when all five args are literals."""
        src = _COLOR_GRAD_SOURCE
        result = handle_document_color(_color_params(), src)
        # 5 in [0, 10] black→white: int(255 * 0.5) = 127
        _assert_rgba(
            _color_at(result, src, "color.from_gradient(5, 0, 10, #000000, #ffffff)"),
            127,
            127,
            127,
        )
        # 50 in [0, 100] color.red (#F23645) → color.green (#22AB94)
        _assert_rgba(
            _color_at(result, src, "color.from_gradient(50, 0, 100, color.red, color.green)"),
            138,
            112,
            108,
        )
        # value == min → color1; quoted hex + #rrggbbaa token
        _assert_rgba(
            _color_at(result, src, 'color.from_gradient(0, 0, 100, "#ff0000", #00ff00aa)'),
            0xFF,
            0,
            0,
        )
        # value above max clamps to color2 (white)
        _assert_rgba(
            _color_at(
                result,
                src,
                "color.from_gradient(value=99, bottom_value=0, top_value=10, bottom_color=#000000, top_color=#ffffff)",
            ),
            0xFF,
            0xFF,
            0xFF,
        )
        # min == max → color1 (black)
        _assert_rgba(
            _color_at(result, src, "color.from_gradient(5, 5, 5, color.black, color.white)"),
            0,
            0,
            0,
        )
        # unary-minus numeric literals: -5 in [-10, 10] red→lime
        _assert_rgba(
            _color_at(result, src, "color.from_gradient(-5, -10, 10, #ff0000, #00ff00)"),
            191,
            63,
            0,
        )
        # keyword order + named palette
        kw_call = (
            "color.from_gradient(bottom_color=color.blue, top_color=color.yellow,"
            " value=25, bottom_value=0, top_value=100)"
        )
        _assert_rgba(_color_at(result, src, kw_call), 94, 127, 204)
        # evaluator aliases min_val/max_val/color1/color2
        _assert_rgba(
            _color_at(
                result,
                src,
                "color.from_gradient(value=5, min_val=0, max_val=10, color1=#111111, color2=#eeeeee)",
            ),
            127,
            127,
            127,
        )
        found = {_slice_range(src, info.range) for info in result}
        assert "#000000" in found
        assert "#ffffff" in found
        assert "color.red" in found
        assert "color.green" in found
        assert '"#ff0000"' in found
        assert "#00ff00aa" in found
        assert "color.black" in found
        assert "color.white" in found
        assert "#ff0000" in found
        assert "#00ff00" in found
        assert "color.blue" in found
        assert "color.yellow" in found
        assert "color.rgb(1, 2, 3)" in found

    def test_handle_document_color_from_gradient_skips_non_literals(self) -> None:
        """from_gradient needs all five args as literals; nested rgb / names skip the call."""
        src = _COLOR_GRAD_SOURCE
        result = handle_document_color(_color_params(), src)
        texts = [_slice_range(src, info.range) for info in result]
        assert "color.from_gradient(close, 0, 100, color.red, color.green)" not in texts
        assert "color.from_gradient(50, lo, 100, color.red, color.green)" not in texts
        assert "color.from_gradient(50, 0, 100, color.rgb(1, 2, 3), color.green)" not in texts
        assert "color.from_gradient(50, 0, 100, color.red)" not in texts
        assert "color.from_gradient(50, 0, 100, color.red, color.green, 1)" not in texts
        assert "color.from_gradient(50, 0, 100, x, color.green)" not in texts

    def test_handle_document_color_reuses_tree(self) -> None:
        """Passing a pre-parsed tree must not require re-parse of source."""
        from pynescript.ast.helper import parse

        tree = parse(_COLOR_SOURCE, filename="file:///test.pine")
        result = handle_document_color(_color_params(), source=None, tree=tree)
        found = {_slice_range(_COLOR_SOURCE, info.range) for info in result}
        assert found == {"#ff0000", "#00ff00aa", "#2962FF", "#22AB94", "color.red", '"#ff00ff"'}
        _assert_rgba(_color_at(result, _COLOR_SOURCE, "#ff0000"), 0xFF, 0, 0)
        _assert_rgba(_color_at(result, _COLOR_SOURCE, '"#ff00ff"'), 0xFF, 0, 0xFF)

    def test_handle_document_color_rgb_shorthand_on_tree(self) -> None:
        """#rgb Constants (kind='#') expand each nibble when present on the tree."""
        from pynescript.ast import node as ast

        lit = ast.Constant(value="#f0a", kind="#")
        lit.lineno = 1
        lit.col_offset = 5
        lit.end_lineno = 1
        lit.end_col_offset = 9
        tree = ast.Script(body=[ast.Expr(value=lit)])
        result = handle_document_color(_color_params(), source=None, tree=tree)
        assert len(result) == 1
        _assert_rgba(result[0].color, 0xFF, 0x00, 0xAA)
        assert result[0].range == lsp.Range(
            start=lsp.Position(line=0, character=5),
            end=lsp.Position(line=0, character=9),
        )

    def test_handle_color_presentation_opaque_hex(self) -> None:
        """Opaque colors rewrite as #rrggbb at the given range."""
        rng = _range_of_hex(_COLOR_SOURCE, "#ff0000")
        params = lsp.ColorPresentationParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            color=lsp.Color(red=1.0, green=0.0, blue=0.0, alpha=1.0),
            range=rng,
        )
        result = handle_color_presentation(params, _COLOR_SOURCE)
        assert len(result) == 1
        pres = result[0]
        assert pres.label == "#ff0000"
        assert pres.text_edit is not None
        assert pres.text_edit.range == rng
        assert pres.text_edit.new_text == "#ff0000"

    def test_handle_color_presentation_alpha_hex(self) -> None:
        """Alpha ≠ 1 rewrites as #rrggbbaa."""
        rng = _range_of_hex(_COLOR_SOURCE, "#00ff00aa")
        params = lsp.ColorPresentationParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            color=lsp.Color(red=0.0, green=1.0, blue=0.0, alpha=0xAA / 255.0),
            range=rng,
        )
        result = handle_color_presentation(params, _COLOR_SOURCE)
        assert len(result) == 1
        pres = result[0]
        assert pres.label == "#00ff00aa"
        assert pres.text_edit is not None
        assert pres.text_edit.range == rng
        assert pres.text_edit.new_text == "#00ff00aa"

    def test_handle_color_presentation_no_document(self) -> None:
        """Presentation still rewrites hex when the document is missing."""
        rng = lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=0, character=7),
        )
        params = lsp.ColorPresentationParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///missing.pine"),
            color=lsp.Color(red=0.2, green=0.4, blue=0.6, alpha=0.5),
            range=rng,
        )
        result = handle_color_presentation(params, None)
        assert len(result) == 1
        assert result[0].label.startswith("#")
        assert len(result[0].label) == 9
        assert result[0].text_edit is not None
        assert result[0].text_edit.new_text == result[0].label

    def test_handle_color_presentation_named_rewrites_hex(self) -> None:
        """Picking a color on a color.* name rewrites the range to #rrggbb."""
        rng = _range_of_hex(_COLOR_NAMED_SOURCE, "color.red")
        params = lsp.ColorPresentationParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            color=lsp.Color(red=0xF2 / 255.0, green=0x36 / 255.0, blue=0x45 / 255.0, alpha=1.0),
            range=rng,
        )
        result = handle_color_presentation(params, _COLOR_NAMED_SOURCE)
        assert len(result) == 1
        pres = result[0]
        assert pres.label == "#f23645"
        assert pres.text_edit is not None
        assert pres.text_edit.range == rng
        assert pres.text_edit.new_text == "#f23645"


_LINK_SOURCE = """//@version=6
indicator("T")
// docs: https://example.com/pine
url = "https://tradingview.com/pine-script-docs"
also = 'http://example.org/path'
plot(close)
"""

_LINK_COMMENT_VARIANTS = """//@version=6
indicator("T")
/* block https://example.com/block and https://example.com/two */
# hash https://example.com/hash
// trailing https://example.com/end.
plot(close)
"""

_LINK_NO_URLS = """//@version=6
indicator("T")
// no link here, nor ftp://example.com, nor www.example.com
plot(close)
"""


def _link_params() -> lsp.DocumentLinkParams:
    return lsp.DocumentLinkParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
    )


def _link_at(links: list[lsp.DocumentLink], source: str, needle: str) -> lsp.DocumentLink:
    rng = _range_of_hex(source, needle)
    matches = [link for link in links if link.range == rng]
    assert matches, f"no DocumentLink for {needle!r}"
    return matches[0]


class TestDocumentLinkHandler:
    """Test textDocument/documentLink for http(s) URLs in comments and strings."""

    def test_handle_document_link_empty_and_unparsed(self) -> None:
        """Empty source and parse failure return an empty list."""
        params = _link_params()
        assert handle_document_link(params, "") == []
        assert handle_document_link(params, None) == []
        assert handle_document_link(params, "this is not valid pine @#$") == []
        assert handle_document_link(params, "x = 1", tree=None) == []

    def test_handle_document_link_comment_and_string_urls(self) -> None:
        """// comments and quoted strings yield DocumentLink ranges on the URL."""
        src = _LINK_SOURCE
        result = handle_document_link(_link_params(), src)
        urls = (
            "https://example.com/pine",
            "https://tradingview.com/pine-script-docs",
            "http://example.org/path",
        )
        found = {_slice_range(src, link.range) for link in result}
        assert found == set(urls)
        for url in urls:
            link = _link_at(result, src, url)
            assert link.target == url
        ordered = [_slice_range(src, link.range) for link in result]
        assert ordered == list(urls)

    def test_handle_document_link_block_and_hash_comments(self) -> None:
        """Block comments, hash comments, and trailing punctuation are handled."""
        src = _LINK_COMMENT_VARIANTS
        result = handle_document_link(_link_params(), src)
        found = {_slice_range(src, link.range) for link in result}
        assert found == {
            "https://example.com/block",
            "https://example.com/two",
            "https://example.com/hash",
            "https://example.com/end",
        }
        for url in found:
            assert _link_at(result, src, url).target == url
        # Trailing period is not part of the range.
        end_link = _link_at(result, src, "https://example.com/end")
        assert _slice_range(src, end_link.range) == "https://example.com/end"
        assert end_link.target == "https://example.com/end"

    def test_handle_document_link_skips_non_http(self) -> None:
        """ftp:// and scheme-less www hosts are not document links."""
        result = handle_document_link(_link_params(), _LINK_NO_URLS)
        assert result == []

    def test_handle_document_link_reuses_tree(self) -> None:
        """Passing a pre-parsed tree must not require re-parse of source."""
        from pynescript.ast.helper import parse

        tree = parse(_LINK_SOURCE, filename="file:///test.pine")
        result = handle_document_link(_link_params(), source=None, tree=tree)
        found = {link.target for link in result}
        # Comments need source; string Constants are on the tree.
        assert found == {
            "https://tradingview.com/pine-script-docs",
            "http://example.org/path",
        }
        src = _LINK_SOURCE
        for url in found:
            assert _link_at(result, src, url).target == url

    def test_comment_url_has_target_and_resolve_fills_tooltip(self) -> None:
        """// https://example.com still has target; resolve sets tooltip to it."""
        src = '//@version=6\nindicator("T")\n// https://example.com\nplot(close)\n'
        result = handle_document_link(_link_params(), src)
        link = _link_at(result, src, "https://example.com")
        assert link.target == "https://example.com"
        assert link.tooltip is None
        resolved = handle_document_link_resolve(link)
        assert resolved.tooltip == "https://example.com"
        assert resolved.target == "https://example.com"

    def test_handle_document_link_resolve_keeps_existing_tooltip(self) -> None:
        """Already-resolved tooltip is not overwritten."""
        rng = lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=0, character=19),
        )
        link = lsp.DocumentLink(
            range=rng,
            target="https://example.com",
            tooltip="keep me",
        )
        resolved = handle_document_link_resolve(link)
        assert resolved is link
        assert resolved.tooltip == "keep me"

    def test_handle_document_link_resolve_empty_and_malformed(self) -> None:
        """Empty / malformed links are returned unchanged and never raise."""
        from types import SimpleNamespace

        rng = lsp.Range(
            start=lsp.Position(line=0, character=0),
            end=lsp.Position(line=0, character=1),
        )
        empty = lsp.DocumentLink(range=rng)
        assert handle_document_link_resolve(empty) is empty
        assert empty.tooltip is None
        bogus = SimpleNamespace(tooltip=None, target=None)
        assert handle_document_link_resolve(bogus) is bogus  # type: ignore[arg-type]


class TestInlayHintParameters:
    """Builtin calls get Parameter inlay hints from metadata / well-known names."""

    SRC = '//@version=5\nindicator("T")\nlength = 14\nplot(ta.sma(close, 14))\n'
    KWARGS_SRC = '//@version=5\nindicator("T")\nplot(ta.sma(close, length=14))\n'

    def _params(self) -> lsp.InlayHintParams:
        return lsp.InlayHintParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=10, character=0),
            ),
        )

    def test_empty_source(self) -> None:
        assert handle_inlay_hints(self._params(), "") == []
        assert handle_inlay_hints(self._params(), None) == []

    def test_sma_parameter_names_and_assignment_type(self) -> None:
        hints = handle_inlay_hints(self._params(), self.SRC)
        assert hints is not None
        param_hints = [h for h in hints if h.kind == lsp.InlayHintKind.Parameter]
        labels = [h.label if isinstance(h.label, str) else "" for h in param_hints]
        assert len(param_hints) >= 2
        assert any("source" in label for label in labels)
        assert any("length" in label for label in labels)
        for hint in param_hints:
            assert hint.data is None
            assert isinstance(hint.label, str)
            assert hint.label.endswith(" ")
        type_labels = [h.label for h in hints if h.kind == lsp.InlayHintKind.Type]
        assert ": const int" in type_labels

    def test_named_kwargs_skipped(self) -> None:
        hints = handle_inlay_hints(self._params(), self.KWARGS_SRC)
        assert hints is not None
        param_hints = [h for h in hints if h.kind == lsp.InlayHintKind.Parameter]
        labels = [h.label if isinstance(h.label, str) else "" for h in param_hints]
        assert any("source" in label for label in labels)
        assert not any("length" in label for label in labels)

    def test_resolve_type_hint_fills_edits_parameter_does_not(self) -> None:
        hints = handle_inlay_hints(self._params(), self.SRC)
        assert hints is not None
        type_hints = [h for h in hints if h.kind == lsp.InlayHintKind.Type]
        param_hints = [h for h in hints if h.kind == lsp.InlayHintKind.Parameter]
        assert type_hints
        assert param_hints
        resolved_type = handle_inlay_hint_resolve(type_hints[0])
        assert resolved_type.text_edits is not None
        assert resolved_type.text_edits[0].new_text == ": const int"
        resolved_param = handle_inlay_hint_resolve(param_hints[0])
        assert not resolved_param.text_edits
        # Parameter labels are "name: ", not insertable type annotations (": type").
        assert isinstance(resolved_param.label, str)
        assert not resolved_param.label.startswith(": ")

    def _param_labels(self, source: str) -> list[str]:
        hints = handle_inlay_hints(self._params(), source)
        assert hints is not None
        return [h.label if isinstance(h.label, str) else "" for h in hints if h.kind == lsp.InlayHintKind.Parameter]

    def test_atr_length_parameter(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.atr(14))\n')
        assert any("length" in label for label in labels)

    def test_correlation_parameter_names(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.correlation(close, volume, 20))\n')
        assert any("source1" in label for label in labels)
        assert any("source2" in label for label in labels)
        assert any("length" in label for label in labels)

    def test_roc_and_crossover_well_known_names(self) -> None:
        roc = self._param_labels('//@version=6\nindicator("T")\nplot(ta.roc(close, 9))\n')
        assert any("source" in label for label in roc)
        assert any("length" in label for label in roc)
        cross = self._param_labels('//@version=6\nindicator("T")\nplot(ta.crossover(close, open))\n')
        assert any("source1" in label for label in cross)
        assert any("source2" in label for label in cross)

    def test_strategy_entry_and_input_int_names(self) -> None:
        entry = self._param_labels('//@version=6\nstrategy("T")\nstrategy.entry("L", strategy.long)\n')
        assert any("id" in label for label in entry)
        assert any("direction" in label for label in entry)
        inp = self._param_labels('//@version=6\nindicator("T")\nn = input.int(5, "n")\n')
        assert any("defval" in label for label in inp)
        assert any("title" in label for label in inp)

    def test_cci_one_arg_is_length_not_source(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.cci(14))\n')
        assert any("length" in label for label in labels)
        assert not any("source" in label for label in labels)

    def test_cci_two_arg_source_length(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.cci(close, 14))\n')
        assert any("source" in label for label in labels)
        assert any("length" in label for label in labels)

    def test_adx_one_arg_is_length_not_dilength(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.adx(14))\n')
        assert any("length" in label for label in labels)
        assert not any("diLength" in label for label in labels)

    def test_adx_two_arg_dilength_adxsmoothing(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.adx(14, 14))\n')
        assert any("diLength" in label for label in labels)
        assert any("adxSmoothing" in label for label in labels)

    def test_mfi_and_bbw_one_arg_is_length(self) -> None:
        mfi = self._param_labels('//@version=6\nindicator("T")\nplot(ta.mfi(14))\n')
        assert any("length" in label for label in mfi)
        assert not any("source" in label for label in mfi)
        bbw = self._param_labels('//@version=6\nindicator("T")\nplot(ta.bbw(20))\n')
        assert any("length" in label for label in bbw)
        assert not any("source" in label for label in bbw)

    def test_bbw_two_arg_is_length_mult_not_source(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.bbw(20, 2))\n')
        assert any("length" in label for label in labels)
        assert any("mult" in label for label in labels)
        assert labels and "source" not in labels[0]
        assert not any("source" in label for label in labels)

    def test_bbw_three_arg_source_length_mult(self) -> None:
        labels = self._param_labels('//@version=6\nindicator("T")\nplot(ta.bbw(close, 20, 2))\n')
        assert any("source" in label for label in labels)
        assert any("length" in label for label in labels)
        assert any("mult" in label for label in labels)


class TestInlayHintResolve:
    """inlayHint/resolve fills textEdits that insert the inferred type annotation."""

    SRC = '//@version=5\nindicator("T")\nlength = 14\n'

    def _params(self) -> lsp.InlayHintParams:
        return lsp.InlayHintParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=10, character=0),
            ),
        )

    def test_initial_hint_label_and_tooltip(self) -> None:
        hints = handle_inlay_hints(self._params(), self.SRC)
        assert hints is not None and len(hints) == 1
        hint = hints[0]
        assert hint.label == ": const int"
        assert hint.tooltip == "Inferred type: const int"
        assert hint.kind == lsp.InlayHintKind.Type

    def test_resolve_fills_text_edits(self) -> None:
        hints = handle_inlay_hints(self._params(), self.SRC)
        assert hints is not None
        resolved = handle_inlay_hint_resolve(hints[0])
        assert resolved.text_edits is not None
        assert len(resolved.text_edits) == 1
        edit = resolved.text_edits[0]
        assert edit.new_text == ": const int"
        assert edit.range.start == hints[0].position
        assert edit.range.end == hints[0].position
        assert edit.range.start.line == 2
        assert edit.range.start.character == len("length")

    def test_already_resolved_returned_as_is(self) -> None:
        pos = lsp.Position(line=0, character=3)
        existing = [
            lsp.TextEdit(
                range=lsp.Range(start=pos, end=pos),
                new_text=": already",
            )
        ]
        hint = lsp.InlayHint(position=pos, label=": const int", text_edits=existing)
        resolved = handle_inlay_hint_resolve(hint)
        assert resolved is hint
        assert resolved.text_edits is existing

    def test_empty_label_no_throw(self) -> None:
        hint = lsp.InlayHint(position=lsp.Position(line=0, character=0), label="")
        resolved = handle_inlay_hint_resolve(hint)
        assert resolved is hint
        assert not resolved.text_edits

    def test_label_parts_joined(self) -> None:
        pos = lsp.Position(line=2, character=6)
        hint = lsp.InlayHint(
            position=pos,
            label=[
                lsp.InlayHintLabelPart(value=": "),
                lsp.InlayHintLabelPart(value="const int"),
            ],
        )
        resolved = handle_inlay_hint_resolve(hint)
        assert resolved.text_edits is not None
        assert len(resolved.text_edits) == 1
        assert resolved.text_edits[0].new_text == ": const int"
        assert resolved.text_edits[0].range.start == pos
        assert resolved.text_edits[0].range.end == pos

    def test_malformed_hint_no_throw(self) -> None:
        from types import SimpleNamespace

        bogus = SimpleNamespace(text_edits=None, label=None, position=None, data=None)
        assert handle_inlay_hint_resolve(bogus) is bogus  # type: ignore[arg-type]


class TestCapabilities:
    """Advertised capabilities must match implemented handlers only."""

    def test_signature_help_provider(self) -> None:
        from pynescript.langserver.config import get_server_capabilities

        caps = get_server_capabilities()
        assert caps.signature_help_provider is not None
        triggers = list(caps.signature_help_provider.trigger_characters or [])
        assert "(" in triggers
        assert "," in triggers
        assert caps.code_action_provider is not None
        kinds = list(caps.code_action_provider.code_action_kinds or [])
        assert lsp.CodeActionKind.QuickFix in kinds
        assert lsp.CodeActionKind.RefactorRewrite in kinds
        assert caps.execute_command_provider is not None
        assert "pynescript.convertToV6" in (caps.execute_command_provider.commands or [])
        assert caps.hover_provider is True
        assert caps.definition_provider is True
        assert caps.document_highlight_provider is True
        assert caps.rename_provider is not None
        assert caps.rename_provider.prepare_provider is True
        assert caps.semantic_tokens_provider is not None
        assert caps.semantic_tokens_provider.full is True
        assert caps.semantic_tokens_provider.range
        assert caps.folding_range_provider is True
        assert caps.selection_range_provider is True
        assert caps.color_provider is True
        assert caps.document_link_provider is not None
        assert caps.document_link_provider.resolve_provider is True
        assert caps.linked_editing_range_provider
        assert caps.document_on_type_formatting_provider is not None
        assert caps.document_on_type_formatting_provider.first_trigger_character == "\n"
        assert caps.inlay_hint_provider is not None
        assert caps.inlay_hint_provider.resolve_provider is True


def _decode_semantic_tokens(data: list[int]) -> list[tuple[int, int, int, int, int]]:
    """Undo LSP delta encoding into absolute (line, col, length, type, mods)."""
    tokens: list[tuple[int, int, int, int, int]] = []
    prev_line = 0
    prev_col = 0
    for i in range(0, len(data), 5):
        d_line, d_col, length, ttype, mods = data[i : i + 5]
        line = prev_line + d_line
        col = d_col if d_line != 0 else prev_col + d_col
        tokens.append((line, col, length, ttype, mods))
        prev_line = line
        prev_col = col
    return tokens


_FOO_SOURCE = """//@version=6
indicator("T")
foo = close
plot(foo)
"""

_FOO_IF_SOURCE = """//@version=6
indicator("T")
foo = close
if bar_index > 0
    plot(foo)
"""

_FOO_TA_SOURCE = """//@version=6
indicator("T")
foo = close
plot(ta.sma(foo, 14))
"""


def _highlight_params(source: str, prefix: str) -> lsp.DocumentHighlightParams:
    return lsp.DocumentHighlightParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        position=_position_after(source, prefix),
    )


def _prepare_rename_params(source: str, prefix: str) -> lsp.PrepareRenameParams:
    return lsp.PrepareRenameParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        position=_position_after(source, prefix),
    )


def _rename_params(source: str, prefix: str, new_name: str) -> lsp.RenameParams:
    return lsp.RenameParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        position=_position_after(source, prefix),
        new_name=new_name,
    )


def _apply_text_edits(source: str, edits: list[lsp.TextEdit]) -> str:
    """Apply LSP text edits (same-line only) from last to first."""
    ordered = sorted(
        edits,
        key=lambda e: (e.range.start.line, e.range.start.character),
        reverse=True,
    )
    lines = source.split("\n")
    for edit in ordered:
        start = edit.range.start
        end = edit.range.end
        assert start.line == end.line
        line = lines[start.line]
        lines[start.line] = line[: start.character] + edit.new_text + line[end.character :]
    return "\n".join(lines)


class TestDocumentHighlightHandler:
    """textDocument/documentHighlight for same-document ident occurrences."""

    def test_highlight_declaration_and_use(self) -> None:
        result = handle_document_highlight(_highlight_params(_FOO_SOURCE, "foo"), _FOO_SOURCE)
        assert result is not None
        assert len(result) >= 2
        texts = [_range_text(_FOO_SOURCE, h.range) for h in result]
        assert texts.count("foo") >= 2

    def test_highlight_same_line_twice(self) -> None:
        source = '//@version=6\nindicator("T")\nfoo = close\nplot(foo + foo)\n'
        result = handle_document_highlight(_highlight_params(source, "foo"), source)
        assert result is not None
        assert len(result) >= 3
        texts = [_range_text(source, h.range) for h in result]
        assert texts.count("foo") >= 3

    def test_highlight_empty_source(self) -> None:
        params = lsp.DocumentHighlightParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),
        )
        assert handle_document_highlight(params, "") == []
        assert handle_document_highlight(params, None) == []


class TestRenameHandler:
    """textDocument/prepareRename and textDocument/rename (open workspace docs)."""

    def test_prepare_rename_user_ident(self) -> None:
        result = handle_prepare_rename(_prepare_rename_params(_FOO_SOURCE, "foo"), _FOO_SOURCE)
        assert result is not None
        rng = result if isinstance(result, lsp.Range) else result.range
        assert _range_text(_FOO_SOURCE, rng) == "foo"

    def test_prepare_rename_keyword_null(self) -> None:
        result = handle_prepare_rename(_prepare_rename_params(_FOO_IF_SOURCE, "if"), _FOO_IF_SOURCE)
        assert result is None

    def test_prepare_rename_builtin_namespace_null(self) -> None:
        result = handle_prepare_rename(_prepare_rename_params(_FOO_TA_SOURCE, "ta"), _FOO_TA_SOURCE)
        assert result is None

    def test_rename_declaration_and_uses(self) -> None:
        params = _rename_params(_FOO_SOURCE, "foo", "bar")
        result = handle_rename(params, _FOO_SOURCE, params.text_document.uri)
        assert result is not None
        edits = list((result.changes or {}).get(params.text_document.uri, []))
        assert len(edits) >= 2
        rewritten = _apply_text_edits(_FOO_SOURCE, edits)
        assert "bar = close" in rewritten
        assert "plot(bar)" in rewritten
        assert "foo" not in rewritten.split("indicator", 1)[-1]

    def test_rename_leaves_keywords_and_other_idents(self) -> None:
        source = """//@version=6
indicator("T")
foo = close
foobar = 1
if bar_index > 0
    plot(foo)
"""
        params = _rename_params(source, "foo", "bar")
        result = handle_rename(params, source, params.text_document.uri)
        assert result is not None
        edits = list((result.changes or {}).get(params.text_document.uri, []))
        rewritten = _apply_text_edits(source, edits)
        assert "bar = close" in rewritten
        assert "foobar = 1" in rewritten
        assert "if bar_index > 0" in rewritten
        assert "plot(bar)" in rewritten

    def test_rename_rejects_invalid_new_name(self) -> None:
        uri = "file:///test.pine"
        assert handle_rename(_rename_params(_FOO_SOURCE, "foo", "if"), _FOO_SOURCE, uri) is None
        assert handle_rename(_rename_params(_FOO_SOURCE, "foo", "ta"), _FOO_SOURCE, uri) is None
        assert handle_rename(_rename_params(_FOO_SOURCE, "foo", "1bar"), _FOO_SOURCE, uri) is None

    def test_rename_keyword_is_noop(self) -> None:
        assert handle_rename(_rename_params(_FOO_IF_SOURCE, "if", "iff"), _FOO_IF_SOURCE, "file:///test.pine") is None

    def test_rename_updates_other_open_documents(self) -> None:
        src_a = _FOO_SOURCE
        src_b = """//@version=6
indicator("B")
foo = close
plot(foo)
"""
        uri_a = "file:///a.pine"
        uri_b = "file:///b.pine"
        ws = Workspace()
        doc_a = ws.put_document(uri_a, src_a)
        ws.put_document(uri_b, src_b)
        params = lsp.RenameParams(
            text_document=lsp.TextDocumentIdentifier(uri=uri_a),
            position=_position_after(src_a, "foo"),
            new_name="bar",
        )
        result = handle_rename(params, src_a, uri_a, tree=doc_a.ast, workspace=ws)
        assert result is not None
        changes = result.changes or {}
        assert uri_a in changes
        assert uri_b in changes
        rewritten_a = _apply_text_edits(src_a, list(changes[uri_a]))
        rewritten_b = _apply_text_edits(src_b, list(changes[uri_b]))
        assert "bar = close" in rewritten_a
        assert "plot(bar)" in rewritten_a
        assert "bar = close" in rewritten_b
        assert "plot(bar)" in rewritten_b

    def test_rename_skips_documents_that_are_not_open(self) -> None:
        src_a = _FOO_SOURCE
        src_b = """//@version=6
indicator("B")
foo = close
plot(foo)
"""
        src_closed = """//@version=6
indicator("C")
foo = close
plot(foo)
"""
        uri_a = "file:///a.pine"
        uri_b = "file:///b.pine"
        uri_closed = "file:///closed.pine"
        ws = Workspace()
        doc_a = ws.put_document(uri_a, src_a)
        ws.put_document(uri_b, src_b)
        params = lsp.RenameParams(
            text_document=lsp.TextDocumentIdentifier(uri=uri_a),
            position=_position_after(src_a, "foo"),
            new_name="bar",
        )
        result = handle_rename(params, src_a, uri_a, tree=doc_a.ast, workspace=ws)
        assert result is not None
        changes = result.changes or {}
        assert uri_a in changes
        assert uri_b in changes
        assert uri_closed not in changes
        assert "foo" in src_closed

    def test_prepare_rename_stays_cursor_document(self) -> None:
        ws = Workspace()
        ws.put_document("file:///a.pine", _FOO_SOURCE)
        ws.put_document("file:///b.pine", _FOO_SOURCE)
        result = handle_prepare_rename(_prepare_rename_params(_FOO_SOURCE, "foo"), _FOO_SOURCE)
        assert result is not None
        rng = result if isinstance(result, lsp.Range) else result.range
        assert _range_text(_FOO_SOURCE, rng) == "foo"


def _range_text(source: str, rng: lsp.Range) -> str:
    lines = source.split("\n")
    assert rng.start.line == rng.end.line
    return lines[rng.start.line][rng.start.character : rng.end.character]


_LENGTH_SOURCE = """//@version=6
indicator("t")
length = 14
plot(ta.sma(close, length))
"""

_IF_SOURCE = """//@version=6
indicator("t")
if bar_index > 0
    plot(close)
"""


def _linked_editing_params(source: str, prefix: str) -> lsp.LinkedEditingRangeParams:
    return lsp.LinkedEditingRangeParams(
        text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
        position=_position_after(source, prefix),
    )


class TestLinkedEditingRangeHandler:
    """textDocument/linkedEditingRange for same-document user ident occurrences."""

    def test_user_ident_links_all_occurrences(self) -> None:
        result = handle_linked_editing_range(_linked_editing_params(_LENGTH_SOURCE, "length"), _LENGTH_SOURCE)
        assert result is not None
        texts = [_range_text(_LENGTH_SOURCE, rng) for rng in result.ranges]
        assert texts == ["length", "length"]
        assert result.word_pattern == r"[A-Za-z_][A-Za-z0-9_]*"
        starts = {(rng.start.line, rng.start.character) for rng in result.ranges}
        assert len(starts) == 2

    def test_builtin_namespace_and_keyword_unlinked(self) -> None:
        assert handle_linked_editing_range(_linked_editing_params(_LENGTH_SOURCE, "ta"), _LENGTH_SOURCE) is None
        assert handle_linked_editing_range(_linked_editing_params(_LENGTH_SOURCE, "plot"), _LENGTH_SOURCE) is None
        assert handle_linked_editing_range(_linked_editing_params(_IF_SOURCE, "if"), _IF_SOURCE) is None

    def test_empty_source(self) -> None:
        params = lsp.LinkedEditingRangeParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///test.pine"),
            position=lsp.Position(line=0, character=0),
        )
        assert handle_linked_editing_range(params, "") is None
        assert handle_linked_editing_range(params, None) is None

    def test_unparsed_tree_none(self) -> None:
        result = handle_linked_editing_range(
            _linked_editing_params(_LENGTH_SOURCE, "length"),
            _LENGTH_SOURCE,
            tree=None,
        )
        assert result is None or (result.ranges == [])
