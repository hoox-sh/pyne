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

"""Parser audit pins for 2026-11-22: block indent, Pine numbers, version comments."""

from __future__ import annotations

import pytest

from pynescript.ast import node as ast
from pynescript.ast.error import SyntaxError as PineSyntaxError
from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse
from pynescript.ast.helper import walk


def _first(tree: ast.AST, cls: type) -> ast.AST:
    return next(node for node in walk(tree) if isinstance(node, cls))


def _const(source: str):
    tree = parse(source, mode="eval")
    constants = [node for node in walk(tree) if isinstance(node, ast.Constant)]
    assert len(constants) == 1
    return constants[0].value


@pytest.mark.parametrize(
    "pad",
    [" ", "  ", "   ", " \t", "\t ", "     ", "      "],
)
def test_non_multiple_of_4_indent_is_not_an_if_body(pad: str) -> None:
    """One space (and any other non-multiple of 4) must not become the branch."""
    source = f"if close > open\n{pad}plot(close)\nplot(open)\n"
    with pytest.raises(PineSyntaxError):
        parse(source)


@pytest.mark.parametrize(
    "header",
    [
        "for i = 0 to 2",
        "for x in close",
        "while close > open",
        "once close > open",
        "once",
        "if close > open\n    plot(close)\nelse",
    ],
)
def test_non_multiple_of_4_indent_is_not_a_structure_body(header: str) -> None:
    source = f"{header}\n plot(close)\n"
    with pytest.raises(PineSyntaxError):
        parse(source)


def test_bad_indent_does_not_poison_the_next_parse() -> None:
    with pytest.raises(PineSyntaxError):
        parse("if close > open\n plot(close)\n")
    tree = parse("if close > open\n    plot(close)\n")
    assert _first(tree, ast.If).body


def test_four_space_and_tab_blocks_parse() -> None:
    four = parse("if close > open\n    plot(close)\nplot(open)\n")
    assert len(four.body) == 2
    assert _first(four, ast.If).body

    tab = parse("if close > open\n\tplot(close)\n")
    assert _first(tab, ast.If).body

    eight = parse("for i = 0 to 2\n        plot(i)\n")
    assert _first(eight, ast.ForTo).body

    while_tree = parse("while close > open\n    plot(close)\n")
    assert _first(while_tree, ast.While).body

    once_tree = parse("once\n    plot(close)\n")
    assert _first(once_tree, ast.Once).body

    once_cond = parse("once close > open\n\tplot(close)\n")
    assert _first(once_cond, ast.Once).body

    else_tree = parse("if close > open\n    plot(close)\nelse\n    plot(open)\n")
    iff = _first(else_tree, ast.If)
    assert iff.body and iff.orelse


def test_operator_eol_wraps_and_condition_wraps_still_parse() -> None:
    parse("x = close +\n    open\n")
    parse("x = close +\n open\n")
    parse("x = close\n + open\n")
    tree = parse("if close\n > open\n    plot(close)\n")
    assert len(tree.body) == 1
    assert _first(tree, ast.If).body


def test_paren_and_bracket_wrap_any_indent_still_parse() -> None:
    for n in (1, 2, 3, 4, 8):
        pad = " " * n
        parse(f"plot(\n{pad}close)\n")
        parse(f"x = close[\n{pad}1]\n")


def test_same_line_if_and_function_soft_wrap_still_parse() -> None:
    same = parse("if close > open plot(close)\n")
    assert _first(same, ast.If).body
    wrapped = parse("f() =>\n x + 1\nplot(f())\n")
    assert _first(wrapped, ast.FunctionDef).body


def test_switch_rejects_non_multiple_of_4_and_accepts_four() -> None:
    with pytest.raises(PineSyntaxError):
        parse("switch close\n   1 => 10\nplot(1)\n")
    tree = parse("switch close\n    1 => 10\n    => 0\nplot(1)\n")
    assert _first(tree, ast.Switch).cases


@pytest.mark.parametrize(
    "literal",
    [
        "0x10",
        "0X10",
        "0b10",
        "0B11",
        "0o10",
        "0O10",
        "1_000",
        "1_000.5",
        "1j",
        "1.0j",
        "1J",
    ],
)
def test_python_only_numbers_are_syntax_errors(literal: str) -> None:
    """``plot(0x10)`` must not become a constant 16."""
    with pytest.raises(PineSyntaxError):
        parse(f"plot({literal})\n")


@pytest.mark.parametrize(
    ("literal", "value"),
    [
        ("0", 0),
        ("10", 10),
        ("1.5", 1.5),
        (".5", 0.5),
        ("1.", 1.0),
        ("1e2", 100.0),
        ("0.0", 0.0),
        ("10.25", 10.25),
        ("1E-1", 0.1),
    ],
)
def test_decimal_integers_and_floats_stay(literal: str, value: float) -> None:
    assert _const(literal) == value


@pytest.mark.parametrize(
    ("literal", "value"),
    [
        ("0", 0),
        ("00", 0),
        ("000", 0),
        ("01", 1),
        ("007", 7),
        ("02", 2),
        ("08", 8),
        ("008", 8),
    ],
)
def test_zero_padded_decimals_are_decimal(literal: str, value: int) -> None:
    """Pine accepts zero-padded decimals (e.g. ``timestamp(..., 02, 23)``)."""
    parsed = _const(literal)
    assert type(parsed) is int
    assert parsed == value


def test_version_only_script_keeps_annotation_and_unparses() -> None:
    tree = parse("//@version=6\n")
    assert tree.annotations == ["//@version=6"]
    assert "//@version=6" in unparse(tree)


def test_version_after_last_statement_is_stored() -> None:
    tree = parse("plot(close)\n//@version=6\n")
    assert tree.annotations == ["//@version=6"]
    assert "//@version=6" in unparse(tree)


def test_leading_version_still_round_trips() -> None:
    tree = parse("//@version=6\nplot(close)\n")
    assert tree.annotations == ["//@version=6"]
    again = parse(unparse(tree))
    assert again.annotations == ["//@version=6"]
