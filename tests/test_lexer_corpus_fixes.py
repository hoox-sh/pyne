# Copyright (C) 2025 jango-blockchained
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
    tree = parse(
        """//@version=5
indicator("t")
int ilog2(int n) =>
    int p = 0
    p
void noop(float[] re, int N) =>
    0
plot(ilog2(8))
"""
    )
    unparse(tree)
