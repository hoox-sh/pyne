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

"""Pin September 2026 square-bracket wrapping, and the older parentheses rule.

Older Pine rejected a wrap inside ``[]`` when the next line's indent was a
multiple of four, unless those brackets sat inside parentheses. Parentheses
already accepted any indent. Square brackets now do too.

The lexer already hides newlines while either delimiter is open. These tests
only pin that parse. They do not change the grammar.
"""

from __future__ import annotations

from pynescript.ast.helper import parse


def _script(body: str) -> str:
    return f'//@version=6\nindicator("t")\n{body}\nplot(x)\n'


def _assert_same_tree(wrapped: str, flat: str) -> None:
    assert repr(parse(wrapped)) == repr(parse(flat))


def test_multiple_of_four_indent_inside_square_brackets() -> None:
    """A 4-space and an 8-space wrap inside ``[]`` parse as the flat form.

    Four and eight are the widths the old rule treated as a block indent.
    History references and tuples are the two forms the release note names.
    """
    history = _script("x = close[1]")
    _assert_same_tree(_script("x = close[\n    1]"), history)
    _assert_same_tree(_script("x = close[\n        1]"), history)
    _assert_same_tree(_script("x = close[1 +\n    2]"), _script("x = close[1 + 2]"))

    header = '//@version=6\nindicator("t")\n'
    flat_tuple = header + "[a, b] = [close, open]\nplot(a)\n"
    wrapped_tuple = header + "[a, b] = [\n    close,\n    open]\nplot(a)\n"
    _assert_same_tree(wrapped_tuple, flat_tuple)


def test_multiple_of_four_indent_inside_parentheses() -> None:
    """Parentheses already had to accept a multiple-of-four indent.

    That includes a square bracket nested inside the parentheses, which was
    the only square-bracket wrap the old rule allowed at this indent.
    """
    added = _script("x = (close + open)")
    _assert_same_tree(_script("x = (\n    close + open)"), added)
    _assert_same_tree(_script("x = (\n        close +\n        open)"), added)
    _assert_same_tree(_script("x = (close[\n    1])"), _script("x = close[1]"))
