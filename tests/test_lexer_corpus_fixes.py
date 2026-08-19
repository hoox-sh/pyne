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

"""Lexer fixes found while sweeping set01–set05 corpus failures."""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


def _roundtrip(source: str) -> None:
    tree = parse(source)
    again = parse(unparse(tree))
    assert repr(tree) == repr(again)


def test_multiline_ternary_after_question_with_trailing_spaces():
    """Trailing spaces after ``?`` must not break operator-line-join."""
    _roundtrip(
        """//@version=5
indicator("t")
momentum = 1.0
momentumColor = momentum > 0 ?\u0020
                color.green :
                color.blue
plot(1)
"""
    )


def test_hash_line_comment_not_color():
    _roundtrip(
        """//@version=5
indicator("t")
# this is a hash comment (corpus scrape noise)
plot(close)
"""
    )


def test_color_literal_still_parses_after_hash_comment_rule():
    _roundtrip(
        """//@version=5
indicator("t")
plot(close, color=#2962FF)
c = #F23745
plot(1, color=c)
"""
    )


def test_markdown_backticks_ignored():
    _roundtrip(
        """//@version=5
indicator("t")
```
plot(close)
```
"""
    )


def test_unicode_identifier():
    _roundtrip(
        """//@version=5
indicator("t")
基于RSI = close
plot(基于RSI)
"""
    )


def test_soft_keyword_as_identifier():
    """`as` is a keyword (import alias) but valid as a variable name."""
    _roundtrip(
        """//@version=5
indicator("t")
as = 10
plot(as)
"""
    )


def test_soft_keywords_type_method_to_by_as_identifiers():
    """Soft keywords ``type`` / ``method`` / ``to`` / ``by`` are valid identifiers."""
    _roundtrip(
        """//@version=5
indicator("t")
type = 1
method = 2
to = 3
by = 4
plot(type + method + to + by)
"""
    )


def test_nested_ternary_type_soft_keyword_ma_selector():
    """set05 pattern: nested ternary arms headed by soft-keyword ``type``."""
    _roundtrip(
        """//@version=5
indicator("t")
ma(source, length, type) =>
    type == "SMA" ? ta.sma(source, length) :
     type == "EMA" ? ta.ema(source, length) :
     type == "WMA" ? ta.wma(source, length) :
     na
plot(ma(close, 14, "SMA"))
"""
    )


def test_soft_keyword_fields_on_udt():
    """UDT fields may use soft-keyword names."""
    _roundtrip(
        """//@version=6
indicator("t")
type Box
    float as
    int method
    string type
b = Box.new(1.0, 2, "x")
plot(b.as)
"""
    )


def test_reassignment_equals_and_colon_equals():
    """Both ``=`` re-bind and ``:=`` reassignment parse."""
    _roundtrip(
        """//@version=5
indicator("t")
x = 1
x = 2
y = 0
y := y + 1
plot(x + y)
"""
    )


def test_multiline_triple_quoted_string_roundtrip():
    _roundtrip(
        '''//@version=6
indicator("t")
s = """line one
We do not break mid-string
line three"""
plot(1)
'''
    )


def test_bitwise_ops_shift_and_or():
    tree = parse(
        """//@version=5
indicator("t")
r = 0
x = 3
r := (r << 1) | (x & 1)
x := x >> 1
y = ~x ^ 1
plot(r)
"""
    )
    unparse(tree)


def test_typed_function_return_and_params():
    """Pine v5+ UDFs may declare return and parameter types."""
    src = """//@version=5
indicator("t")
int ilog2(int n) =>
    int p = 0
    p
void noop(float[] re, int N) =>
    0
plot(ilog2(8))
"""
    tree = parse(src)
    funcs = [s for s in tree.body if type(s).__name__ == "FunctionDef"]
    by_name = {f.name: f for f in funcs}
    assert by_name["ilog2"].returns is not None
    assert by_name["ilog2"].returns.id == "int"
    assert by_name["noop"].returns is not None
    out = unparse(tree)
    assert "int ilog2(" in out
    assert "void noop(" in out
    again = parse(out)
    again_fn = {f.name: f for f in again.body if type(f).__name__ == "FunctionDef"}
    assert again_fn["ilog2"].returns.id == "int"


def test_bare_name_equal_is_assign_not_reassign():
    """``x = 1`` is initialization; ``x := 1`` / ``obj.f = 1`` are reassignment."""
    from pynescript.ast import node as ast

    tree = parse(
        """//@version=5
indicator("eq")
x = 1
x := 2
strategy.initial_capital = 50000
plot(x)
"""
    )
    stmts = [s for s in tree.body if type(s).__name__ in {"Assign", "ReAssign"}]
    assert any(isinstance(s, ast.Assign) and isinstance(s.target, ast.Name) and s.target.id == "x" for s in stmts)
    assert any(isinstance(s, ast.ReAssign) and isinstance(s.target, ast.Name) and s.target.id == "x" for s in stmts)
    assert any(
        isinstance(s, ast.ReAssign)
        and isinstance(s.target, ast.Attribute)
        and s.target.attr == "initial_capital"
        for s in stmts
    )


def test_c_style_block_comment():
    _roundtrip(
        """//@version=5
indicator("t")
/* This is a block comment
   spanning multiple lines */
a = close
plot(a)
"""
    )


def test_inline_block_comment():
    _roundtrip(
        """//@version=5
indicator("t")
a = close /* inline */
plot(a)
"""
    )
