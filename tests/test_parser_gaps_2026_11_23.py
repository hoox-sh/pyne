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

"""Parser gaps found by the 2026-11-23 set06 corpus audit."""

from __future__ import annotations

import pytest

from pynescript.ast.helper import parse
from pynescript.ast.helper import parse_with_errors
from pynescript.ast.helper import unparse


def test_wrapped_ternary_with_leading_question_and_colon() -> None:
    src = """//@version=6
indicator("t")
x = close > open
     ? 1
     : 0
plot(x)
"""
    tree = parse(src)
    assert "?" in unparse(tree)
    assert ":" in unparse(tree)


def test_multiple_of_four_leading_operator_is_still_an_error() -> None:
    """INV074: TV rejects a leading operator at a 4-space continuation."""
    from pynescript.ast.error import SyntaxError as PineSyntaxError

    src = """//@version=6
indicator("t")
x = close > open
    ? 1
    : 0
plot(x)
"""
    with pytest.raises(PineSyntaxError):
        parse(src)


def test_column1_ternary_operator_is_still_a_new_statement() -> None:
    from pynescript.ast.error import SyntaxError as PineSyntaxError

    src = """//@version=6
indicator("t")
x = close
? high : low
plot(x)
"""
    with pytest.raises(PineSyntaxError):
        parse(src)


def test_wrapped_ternary_after_question() -> None:
    src = """//@version=6
indicator("t")
x = close > open ?
     1
     : 0
plot(x)
"""
    assert parse(src).body


def test_switch_arm_leading_operator_at_non_multiple_indent() -> None:
    """INV073: a switch arm may continue with a leading operator at 5 spaces."""
    src = """//@version=6
indicator("t")
f = input.string("Defensive")
x = switch f
    "Defensive" => (close > open)
     and (high > low)
    => true
plot(x ? 1 : 0)
"""
    assert parse(src).body


@pytest.mark.parametrize(
    "header",
    [
        "for i =\n  1 to\n  5\n    x += i",
        "for i = 1 to 5\n  by 2\n    x += i",
        "for v in\n  array.from(1, 2)\n    x += v",
    ],
)
def test_wrapped_for_header_keywords(header: str) -> None:
    src = f"""//@version=6
indicator("t")
x = 0
{header}
plot(x)
"""
    assert parse(src).body


def test_for_body_indent_five_spaces_is_not_a_body() -> None:
    """INV034: a complete for header + 5-space wrap is not a body."""
    from pynescript.ast.error import SyntaxError as PineSyntaxError

    src = """//@version=6
indicator("t")
for i = 1 to 7
     s := s + close[i]
plot(close)
"""
    with pytest.raises(PineSyntaxError):
        parse(src)


def test_recovery_parses_mangled_prose_and_column1_ternary() -> None:
    """INV080: skip URL/domain prose, recover the bad ternary, keep the tree."""
    src = """//@version=6
indicator("INV080")
// This code is available at
algopoint.co
// Mozilla Public License
at https://mozilla.org/MPL/2.0/
x = close > open ? 1 : close < open ? 2 : close == open
? 3 : 4
plot(close)
"""
    node, errors = parse_with_errors(src)
    assert node.body
    assert len(errors) == 1
    assert "operator ?:" in errors[0][2]
    assert parse(src, recover=True).body

    from pynescript.ast.error import SyntaxError as PineSyntaxError

    with pytest.raises(PineSyntaxError):
        parse(src)


def test_triple_quoted_string_escaped_delimiter() -> None:
    src = '''//@version=6
indicator("t")
string escaped = """a \\""" b"""
string single = \'\'\'a \\\'\'\' b\'\'\'
plot(close)
'''
    tree = parse(src)
    text = unparse(tree)
    assert "a" in text
    assert "b" in text
