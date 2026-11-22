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

"""Unparser parentheses on non-atom bases, and LSP range-format edits.

``[]`` and ``<type>()`` bind to a primary. A non-atom base has to keep its
parentheses, the same way a call or attribute does. Range format has to
return an edit that, applied to the buffer, matches the formatted document
on the lines the range touches. A character-narrow range must not receive
full-line replacement text.
"""

from __future__ import annotations

import pytest

from lsprotocol import types as lsp

from pynescript.ast.helper import dump
from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse
from pynescript.langserver.features.formatting import handle_formatting
from pynescript.langserver.features.formatting import handle_on_type_formatting
from pynescript.langserver.features.formatting import handle_range_formatting
from pynescript.langserver.workspace import _apply_text_edit


_OPTIONS = lsp.FormattingOptions(tab_size=4, insert_spaces=True)
_URI = lsp.TextDocumentIdentifier(uri="file:///audit.pine")

# Audit sample. The trailing newline is the usual file ending.
_LENGTH_DOC = '//@version=6\nindicator("T")\nlength=14\nplot(close)\n'
_LENGTH_DOC_FIXED = '//@version=6\nindicator("T")\nlength = 14\nplot(close)\n'


def _round_trip(source: str) -> str:
    """Unparse once, require a stable second unparse and the same tree."""
    tree = parse(source)
    once = unparse(tree)
    assert unparse(parse(once)) == once
    assert dump(parse(once)) == dump(tree)
    return once


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = (close + open)[1]", "x = (close + open)[1]"),
        ("x = (close > open)[1]", "x = (close > open)[1]"),
        ("x = (a and b)[1]", "x = (a and b)[1]"),
        ("x = (a or b)[1]", "x = (a or b)[1]"),
        ("x = (a ? b : c)[1]", "x = (a ? b : c)[1]"),
        ("x = (not cond)[1]", "x = (not cond)[1]"),
        ("x = (-close)[1]", "x = (-close)[1]"),
        ("x = (a + b)<float>(1)", "x = (a + b)<float>(1)"),
        ("x = (close + open)[1] + (high + low)[1]", "x = (close + open)[1] + (high + low)[1]"),
    ],
    ids=["add", "compare", "and", "or", "ternary", "not", "usub", "specialize", "two-sums"],
)
def test_non_atom_history_base_keeps_parens(source: str, expected: str) -> None:
    """A subscript or specialization of a non-atom reparses as that base."""
    assert _round_trip(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "x = ta.sma(close, 14)[1]",
        "x = f(1)[2]",
        "x = close[1]",
        "x = f[1](2)",
        "x = array<float>(1)",
        "x = (a + b).c",
        "x = (a + b)(c)",
    ],
    ids=["sma", "call", "name", "subscript-call", "typed-call", "attribute", "call-of-sum"],
)
def test_atom_base_stays_unwrapped(source: str) -> None:
    """Names, calls, and attributes are already primaries and stay bare."""
    assert _round_trip(source) == source


def _range_params(start: tuple[int, int], end: tuple[int, int]) -> lsp.DocumentRangeFormattingParams:
    return lsp.DocumentRangeFormattingParams(
        text_document=_URI,
        range=lsp.Range(
            start=lsp.Position(line=start[0], character=start[1]),
            end=lsp.Position(line=end[0], character=end[1]),
        ),
        options=_OPTIONS,
    )


def _formatted_lines(source: str) -> list[str]:
    """Lines of the buffer after a full-document format edit is applied."""
    edits = handle_formatting(
        lsp.DocumentFormattingParams(text_document=_URI, options=_OPTIONS),
        source,
    )
    if not edits:
        return source.split("\n")
    assert len(edits) == 1
    applied = _apply_text_edit(source, edits[0].range, edits[0].new_text)
    return applied.split("\n")


def _applied_range(source: str, start: tuple[int, int], end: tuple[int, int]) -> tuple[str, lsp.TextEdit]:
    edits = handle_range_formatting(_range_params(start, end), source)
    assert edits is not None
    assert len(edits) == 1
    edit = edits[0]
    applied = _apply_text_edit(source, edit.range, edit.new_text)
    formatted = _formatted_lines(source)
    applied_lines = applied.split("\n")
    for line in range(edit.range.start.line, edit.range.end.line + 1):
        assert applied_lines[line] == formatted[line]
    return applied, edit


@pytest.mark.parametrize(
    ("start", "end", "end_line", "forbidden"),
    [
        ((2, 0), (2, 0), 2, "length = 14length=14"),
        ((2, 0), (2, 3), 2, "length = 14gth=14"),
        ((2, 3), (2, 3), 2, "lenlength = 14gth=14"),
        ((2, 0), (3, 0), 2, "plot(close)plot(close)"),
        ((2, 9), (3, 0), 2, "plot(close)plot(close)"),
        ((2, 0), (3, 4), 3, "plot(close)(close)"),
    ],
    ids=[
        "zero-width",
        "partial-token",
        "mid-caret",
        "end-at-next-col-0",
        "eol-to-next-col-0",
        "into-next-line",
    ],
)
def test_range_format_applies_over_touched_lines(
    start: tuple[int, int],
    end: tuple[int, int],
    end_line: int,
    forbidden: str,
) -> None:
    """Applying the edit yields the formatted lines, not a splice of both."""
    source = _LENGTH_DOC
    applied, edit = _applied_range(source, start, end)
    assert forbidden not in applied
    assert applied == _LENGTH_DOC_FIXED
    assert edit.range.start.line == 2
    assert edit.range.start.character == 0
    assert edit.range.end.line == end_line
    assert edit.range.end.character == len(source.split("\n")[end_line])
    assert "\n" not in edit.new_text or edit.range.start.line != edit.range.end.line


def test_range_ending_at_next_column_0_leaves_that_line() -> None:
    """A selection that stops at the next line's column 0 does not rewrite it."""
    source = '//@version=6\nindicator("T")\nlength=14\nplot( close )\n'
    applied, edit = _applied_range(source, (2, 0), (3, 0))
    assert edit.range.end.line == 2
    lines = applied.split("\n")
    assert lines[2] == "length = 14"
    assert lines[3] == "plot( close )"
    assert "plot(close)plot" not in applied


def test_range_entering_next_line_formats_that_line() -> None:
    """A selection that includes part of the next line formats that whole line."""
    source = '//@version=6\nindicator("T")\nlength=14\nplot( close )\n'
    applied, edit = _applied_range(source, (2, 0), (3, 4))
    assert edit.range.end.line == 3
    lines = applied.split("\n")
    assert lines[2] == "length = 14"
    assert lines[3] == "plot(close)"
    assert "plot( close )( close )" not in applied
    assert "plot(close)( close )" not in applied


def test_zero_width_range_on_formatted_line_is_empty() -> None:
    """No edit when the touched line is already in canonical form."""
    source = _LENGTH_DOC_FIXED
    edits = handle_range_formatting(_range_params((2, 0), (2, 0)), source)
    assert edits == []


def test_zero_width_comment_line_applies_without_duplicating() -> None:
    """Comment splice still trims the selected line, and the edit applies."""
    source = '//@version=6\nindicator("T")\n// note\nplot(close)   \nplot(open)   \n'
    applied, edit = _applied_range(source, (4, 0), (4, 0))
    assert edit.new_text == "plot(open)"
    assert edit.range.start.character == 0
    assert edit.range.end.character == len("plot(open)   ")
    lines = applied.split("\n")
    assert lines[2] == "// note"
    assert lines[4] == "plot(open)"
    assert "plot(open)plot(open)" not in applied


def test_full_document_format_replaces_the_whole_buffer() -> None:
    """Full format stays one edit covering the buffer, not a line splice."""
    source = _LENGTH_DOC
    edits = handle_formatting(
        lsp.DocumentFormattingParams(text_document=_URI, options=_OPTIONS),
        source,
    )
    assert edits is not None
    assert len(edits) == 1
    edit = edits[0]
    applied = _apply_text_edit(source, edit.range, edit.new_text)
    assert applied == '//@version=6\nindicator("T")\nlength = 14\nplot(close)'
    assert edit.range.start.line == 0
    assert edit.range.start.character == 0
    assert "length = 14length=14" not in applied


def test_on_type_format_replaces_the_whole_previous_line() -> None:
    """On-type stays a single whole-line edit of the line before the cursor."""
    source = _LENGTH_DOC
    edits = handle_on_type_formatting(
        lsp.DocumentOnTypeFormattingParams(
            text_document=_URI,
            position=lsp.Position(line=3, character=0),
            ch="\n",
            options=_OPTIONS,
        ),
        source,
    )
    assert edits is not None
    assert len(edits) == 1
    edit = edits[0]
    applied = _apply_text_edit(source, edit.range, edit.new_text)
    assert edit.range.start.line == edit.range.end.line == 2
    assert edit.range.start.character == 0
    assert edit.range.end.character == len("length=14")
    assert edit.new_text == "length = 14"
    assert "\n" not in edit.new_text
    assert applied.split("\n")[2] == "length = 14"
    assert applied.split("\n")[3] == "plot(close)"
