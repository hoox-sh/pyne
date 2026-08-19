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


def test_udt_keyword_fields_var_switch():
    """UDT fields may be named ``var`` / ``switch`` (lexer keywords)."""
    _roundtrip(
        """//@version=5
indicator("Keyword Field Var")
type Settings
    float var = 1.0
    float switch = 2.0
Settings s = Settings.new()
var float result = 0.0
result := s.var + s.switch
plot(result)
"""
    )


def test_var_declaration_mode_still_parses():
    """``var float x = 1`` remains a declaration, not an identifier."""
    from pynescript.ast import node as ast

    tree = parse(
        """//@version=5
indicator("t")
var float x = 1
var y = 2
plot(x + y)
"""
    )
    assigns = [s for s in tree.body if isinstance(s, ast.Assign)]
    by_name = {s.target.id: s for s in assigns if isinstance(s.target, ast.Name)}
    assert isinstance(by_name["x"].mode, ast.Var)
    assert by_name["x"].type.id == "float"
    assert isinstance(by_name["y"].mode, ast.Var)


def test_switch_default_mid_roundtrip():
    """Default arm may sit between pattern arms (``=> 0`` then ``2 => 20``)."""
    _roundtrip(
        """//@version=5
indicator("Switch DefMid")
x = 2
var int r = 0
r := switch x
    1 => 10
    => 0
    2 => 20
plot(r)
"""
    )


def test_nested_generic_array_new():
    """``>>`` after a nested type arg is RSHIFT; 2-level ``array.new<array<float>>()``."""
    _roundtrip(
        """//@version=5
indicator("t")
a = array.new<array<float>>()
plot(1)
"""
    )


def test_nested_generic_map_field():
    """UDT field ``map<string, array<float>>`` (same RSHIFT closer)."""
    _roundtrip(
        """//@version=5
indicator("t")
type Basket
    map<string, array<float>> groups
plot(1)
"""
    )


def test_not_continuation():
    """Unary ``not`` must line-join so the operand can start on the next line."""
    _roundtrip(
        """//@version=5
indicator("Not Cont")
x = not
    (close < open)
plot(x ? 1 : 0)
"""
    )


def test_blank_lines_between_arrow_and_indented_method_body():
    """Blank lines after ``=>`` before an indented method/function body.

    set06 ``13730_ind_mxwll_suite.pine``: ``method tfDraw(...) =>`` then empty
    lines then an indented body. Same ``local_block`` production as if/else
    and switch arms.
    """
    _roundtrip(
        """//@version=5
indicator("t")
method tfDraw(int tfDiff, bool showLevels) =>




    x = tfDiff
    if showLevels


        x := x + 1
    x
f(n) =>

    n + 1
y = switch close > open
    true =>

        1
    =>

        0
plot(tfDraw(1, true) + f(1) + y)
"""
    )


def test_multiline_type_new_nested_map_new():
    """Multiline ``Type.new(...)`` args with nested ``map.new<K,V>()``.

    set06 ``13716_ind_depth_of_market_dom.pine``: commas are line-join ops
    and ``<K,V>`` must not confuse paren-depth / RSHIFT type-arg closing.
    """
    _roundtrip(
        """//@version=5
indicator("t")
type Dom
    map<float,float> a
    map<float,float> b
    map<float,string> c
newDom() => Dom.new(map.new<float,float>(),
                 map.new<float,float>(),
                 map.new<float,string>())
d = array.new<map<string, float>>()
plot(1)
"""
    )
