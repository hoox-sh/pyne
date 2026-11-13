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

"""Tests for declaration, type definition, call hierarchy, code lens, inline completion."""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.ast import parse
from pynescript.langserver.analysis import build_symbol_index
from pynescript.langserver.features import call_hierarchy
from pynescript.langserver.features import code_lens
from pynescript.langserver.features import definitions
from pynescript.langserver.features import inline_completion


URI = "file:///nav-extras.pine"

UDT_SOURCE = """//@version=6
indicator("Test")

type Point
    float x
    float y

f(float a) =>
    a + 1

g(float b) =>
    f(b) * 2

p = Point.new(1.0, 2.0)
plot(g(close))
"""

METHOD_SOURCE = """//@version=6
indicator("M")
type Point
    float x
method norm(Point self) =>
    math.abs(self.x)
p = Point.new(3.0)
v = p.norm()
plot(v)
"""


def _position(source: str, needle: str, occurrence: int = 1) -> lsp.Position:
    index = -1
    for _ in range(occurrence):
        index = source.find(needle, index + 1)
    assert index >= 0, needle
    line = source.count("\n", 0, index)
    start = source.rfind("\n", 0, index) + 1
    return lsp.Position(line=line, character=index - start)


def _index(source: str):
    tree = parse(source)
    return tree, build_symbol_index(tree, source, URI)


def _params(position: lsp.Position) -> lsp.TextDocumentIdentifier:
    return lsp.TextDocumentIdentifier(uri=URI)


class TestDeclaration:
    def test_declaration_matches_definition(self) -> None:
        tree, index = _index(UDT_SOURCE)
        position = _position(UDT_SOURCE, "p = Point")
        declaration = definitions.handle_declaration(
            lsp.DeclarationParams(text_document=_params(position), position=position),
            UDT_SOURCE,
            URI,
            tree=tree,
            analysis=index,
        )
        definition = definitions.handle_definition(
            lsp.DefinitionParams(text_document=_params(position), position=position),
            UDT_SOURCE,
            URI,
            tree=tree,
            analysis=index,
        )
        assert declaration is not None
        assert definition is not None
        assert declaration[0].range == definition[0].range


class TestTypeDefinition:
    def _type_definition(self, source: str, needle: str) -> list[lsp.Location] | None:
        tree, index = _index(source)
        position = _position(source, needle)
        return definitions.handle_type_definition(
            lsp.TypeDefinitionParams(text_document=_params(position), position=position),
            source,
            URI,
            tree=tree,
            analysis=index,
        )

    def test_inferred_udt_variable(self) -> None:
        result = self._type_definition(UDT_SOURCE, "p = Point")
        assert result is not None
        assert result[0].range.start.line == 3  # type Point

    def test_constructor_token(self) -> None:
        result = self._type_definition(UDT_SOURCE, "Point.new")
        assert result is not None
        assert result[0].range.start.line == 3

    def test_annotated_variable(self) -> None:
        source = '//@version=6\nindicator("A")\ntype Point\n    float x\nPoint p = Point.new(1.0)\nplot(p.x)\n'
        result = self._type_definition(source, "p = Point")
        assert result is not None
        assert result[0].range.start.line == 2

    def test_member_receiver_type(self) -> None:
        source = '//@version=6\nindicator("A")\ntype Point\n    float x\nPoint p = Point.new(1.0)\nplot(p.x)\n'
        result = self._type_definition(source, "p.x")
        assert result is not None
        assert result[0].range.start.line == 2

    def test_builtin_type_has_no_location(self) -> None:
        assert self._type_definition(UDT_SOURCE, "float x") is None


class TestCallHierarchy:
    def _prepare(self, source: str, needle: str) -> list[lsp.CallHierarchyItem] | None:
        tree, index = _index(source)
        position = _position(source, needle)
        return call_hierarchy.handle_prepare_call_hierarchy(
            lsp.CallHierarchyPrepareParams(text_document=_params(position), position=position),
            source,
            URI,
            tree=tree,
            analysis=index,
        )

    def test_prepare_on_definition_and_call(self) -> None:
        assert [item.name for item in self._prepare(UDT_SOURCE, "g(float b)") or []] == ["g"]
        assert [item.name for item in self._prepare(UDT_SOURCE, "g(close)") or []] == ["g"]

    def test_incoming_calls_from_script(self) -> None:
        tree, index = _index(UDT_SOURCE)
        item = self._prepare(UDT_SOURCE, "g(float b)")[0]
        calls = call_hierarchy.handle_incoming_calls(
            lsp.CallHierarchyIncomingCallsParams(item=item),
            UDT_SOURCE,
            URI,
            tree=tree,
            analysis=index,
        )
        assert [call.from_.name for call in calls] == ["<script>"]
        assert calls[0].from_ranges[0].start.line == 14

    def test_incoming_calls_from_function(self) -> None:
        tree, index = _index(UDT_SOURCE)
        item = self._prepare(UDT_SOURCE, "f(float a)")[0]
        calls = call_hierarchy.handle_incoming_calls(
            lsp.CallHierarchyIncomingCallsParams(item=item),
            UDT_SOURCE,
            URI,
            tree=tree,
            analysis=index,
        )
        assert [call.from_.name for call in calls] == ["g"]

    def test_outgoing_calls_include_user_functions_only(self) -> None:
        tree, index = _index(UDT_SOURCE)
        item = self._prepare(UDT_SOURCE, "g(float b)")[0]
        calls = call_hierarchy.handle_outgoing_calls(
            lsp.CallHierarchyOutgoingCallsParams(item=item),
            UDT_SOURCE,
            URI,
            tree=tree,
            analysis=index,
        )
        assert [call.to.name for call in calls] == ["f"]

    def test_method_call_hierarchy(self) -> None:
        item = self._prepare(METHOD_SOURCE, "norm(Point")[0]
        tree, index = _index(METHOD_SOURCE)
        calls = call_hierarchy.handle_incoming_calls(
            lsp.CallHierarchyIncomingCallsParams(item=item),
            METHOD_SOURCE,
            URI,
            tree=tree,
            analysis=index,
        )
        assert [call.from_.name for call in calls] == ["<script>"]
        assert calls[0].from_ranges[0].start.line == 7


class TestCodeLens:
    def _lenses(self, source: str, *, pro_enabled: bool = False) -> list[lsp.CodeLens]:
        tree, index = _index(source)
        return code_lens.handle_code_lens(
            lsp.CodeLensParams(text_document=lsp.TextDocumentIdentifier(uri=URI)),
            source,
            URI,
            tree=tree,
            analysis=index,
            pro_enabled=pro_enabled,
        )

    def test_v5_offers_convert(self) -> None:
        lenses = self._lenses('//@version=5\nstrategy("S")\nplot(close)\n')
        assert [lens.command.title for lens in lenses] == ["Convert to v6"]
        assert lenses[0].range.start.line == 1

    def test_v6_has_no_convert(self) -> None:
        assert self._lenses('//@version=6\nindicator("T")\nplot(close)\n') == []

    def test_survives_parse_error(self) -> None:
        source = '//@version=5\nstrategy("S")\nplot(ta.\n'
        lenses = code_lens.handle_code_lens(
            lsp.CodeLensParams(text_document=lsp.TextDocumentIdentifier(uri=URI)),
            source,
            URI,
            tree=None,
            analysis=None,
        )
        assert [lens.command.title for lens in lenses] == ["Convert to v6"]
        assert lenses[0].range.start.line == 1

    def test_pro_adds_smoke(self) -> None:
        lenses = self._lenses('//@version=6\nindicator("T")\nplot(close)\n', pro_enabled=True)
        assert [lens.command.title for lens in lenses] == ["Smoke /run"]
        assert lenses[0].command.command == "pynescript.runOnPro"


class TestInlineCompletion:
    def _complete(self, source: str, *, enabled: bool = True):
        line = source.split("\n", maxsplit=1)[0]
        return inline_completion.handle_inline_completion(
            lsp.InlineCompletionParams(
                text_document=lsp.TextDocumentIdentifier(uri=URI),
                position=lsp.Position(line=0, character=len(line)),
                context=lsp.InlineCompletionContext(trigger_kind=lsp.InlineCompletionTriggerKind.Invoked),
            ),
            source,
            URI,
            enabled=enabled,
        )

    def test_curated_builtin_arguments(self) -> None:
        result = self._complete("ta.sma(")
        assert result is not None
        assert [item.insert_text for item in result.items] == ["close, 14)"]

    def test_disabled_returns_none(self) -> None:
        assert self._complete("ta.sma(", enabled=False) is None

    def test_typed_arguments_are_left_alone(self) -> None:
        assert self._complete("ta.sma(close") is None

    def test_existing_close_paren_is_left_alone(self) -> None:
        assert self._complete("ta.sma()") is None

    def test_unknown_callee_returns_none(self) -> None:
        assert self._complete("myFunction(") is None

    def test_comment_is_left_alone(self) -> None:
        assert self._complete("// ta.sma(") is None

    def test_string_is_left_alone(self) -> None:
        assert self._complete('s = "ta.sma(') is None
