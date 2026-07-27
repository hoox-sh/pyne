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
