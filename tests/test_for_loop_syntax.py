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

"""Parse/unparse coverage for typed for-iterators and comma-chained for structures.

These patterns appear in real library scripts (e.g. ``for int i = 0 to n`` and
``Ex = 0.0, Ey = 0.0, for i=0 to n``).
"""

from __future__ import annotations

from pynescript.ast import node as ast
from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse
from pynescript.ast.helper import walk


def _roundtrip(source: str) -> ast.Script:
    tree = parse(source)
    again = parse(unparse(tree))
    assert repr(tree) == repr(again)
    return tree


def test_typed_for_to_iterator():
    tree = _roundtrip(
        """//@version=5
indicator("typed for")
sum = 0.0
for int i = 0 to 10
    sum := sum + i
plot(sum)
"""
    )
    # Find ForTo target is Name "i"
    forto = next(n for n in walk(tree) if isinstance(n, ast.ForTo))
    assert isinstance(forto.target, ast.Name)
    assert forto.target.id == "i"


def test_typed_for_in_iterator():
    tree = _roundtrip(
        """//@version=5
indicator("typed for-in")
arr = array.from(1, 2, 3)
total = 0
for int v in arr
    total := total + v
plot(total)
"""
    )
    forin = next(n for n in walk(tree) if isinstance(n, ast.ForIn))
    assert isinstance(forin.target, ast.Name)
    assert forin.target.id == "v"


def test_series_typed_for_iterator():
    _roundtrip(
        """//@version=5
indicator("series typed for")
for series int i = 0 to 3
    x = i
plot(x)
"""
    )


def test_comma_chained_for_structure():
    """Old-style multi-statement lines may end with a for structure."""
    tree = _roundtrip(
        """//@version=4
study("comma for")
Ex = 0.0, Ey = 0.0, for i=0 to 5
    Ex := Ex + i
plot(Ex)
"""
    )
    assert any(isinstance(n, ast.ForTo) for n in walk(tree))


def test_orderbook_style_typed_for():
    """Snippet from tests/data/library/orderbook.lib.pine."""
    _roundtrip(
        """//@version=5
library("Orderbook")
export avgGrossProfit() =>
    float subresult = 0.
    for int i = 0 to strategy.closedtrades - 1
        subresult += strategy.closedtrades.profit(i)
    strategy.closedtrades > 0 ? subresult / strategy.closedtrades : na
"""
    )


def test_switch_multi_value_arm():
    tree = _roundtrip(
        """//@version=5
indicator("Switch Multi")
x = 2
val = switch x
    1, 2 => 100
    3, 4 => 200
    => 0
plot(val)
"""
    )
    switch = next(n for n in walk(tree) if isinstance(n, ast.Switch))
    pattern = switch.cases[0].pattern
    assert isinstance(pattern, ast.Tuple) or getattr(pattern, "elts", None)
    assert len(pattern.elts) == 2


def test_switch_default_only_arm():
    tree = _roundtrip(
        """//@version=5
indicator("UDF Switch Default")
f_always() =>
    switch
        => 42.0
plot(f_always())
"""
    )
    switch = next(n for n in walk(tree) if isinstance(n, ast.Switch))
    assert len(switch.cases) == 1
    assert isinstance(switch.cases[0], ast.Case)
    assert switch.cases[0].pattern is None
