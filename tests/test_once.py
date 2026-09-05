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

"""``once`` conditional structure (TradingView August 2026)."""

from __future__ import annotations

import pytest

from pynescript.ast import node as ast
from pynescript.ast.error import SyntaxError as PineSyntaxError
from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse
from pynescript.ast.helper import walk
from pynescript.runtime import Runtime


def _bars(n: int = 20) -> list[dict[str, float | int]]:
    return [
        {
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0 + i,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def _roundtrip(source: str) -> ast.Script:
    tree = parse(source)
    again = parse(unparse(tree))
    assert repr(tree) == repr(again)
    return tree


def _first_once(tree: ast.AST) -> ast.Once:
    for node in walk(tree):
        if isinstance(node, ast.Once):
            return node
    msg = "no Once node"
    raise AssertionError(msg)


class TestOnceParse:
    def test_once_with_condition_roundtrip(self) -> None:
        tree = _roundtrip(
            """//@version=6
indicator("once cond")
var int n = 0
once close > 102
    n := 1
plot(n)
"""
        )
        node = _first_once(tree)
        assert node.test is not None
        assert unparse(tree).splitlines()[3].startswith("once ")

    def test_once_without_condition_roundtrip(self) -> None:
        tree = _roundtrip(
            """//@version=6
indicator("once bare")
var int n = 0
once
    n := 1
plot(n)
"""
        )
        node = _first_once(tree)
        assert node.test is None
        assert "once" in unparse(tree)

    def test_once_as_identifier_still_parses(self) -> None:
        tree = _roundtrip(
            """//@version=6
indicator("once id")
once = 3
plot(once)
"""
        )
        names = [n.id for n in walk(tree) if isinstance(n, ast.Name)]
        assert "once" in names

    def test_once_cannot_be_assigned(self) -> None:
        src = """//@version=6
indicator("once rhs")
x = once close > open
    1
plot(x)
"""
        with pytest.raises(PineSyntaxError):
            parse(src)


class TestOnceRuntime:
    def test_fires_once_on_historical_bars(self) -> None:
        src = """//@version=6
indicator("once hist")
var int n = 0
once close > 102
    n := n + 1
plot(n, "n")
"""
        n = 10
        out = Runtime(symbol="TEST").run(src, _bars(n), mode="interpret")
        assert "error" not in out, out.get("error")
        series = out["series"]["n"]
        # close = 100.5 + i; first fire at i=2 (close=102.5), then sticky 1
        assert series[0] == 0
        assert series[1] == 0
        assert series[2:] == [1] * (n - 2)

    def test_bare_once_fires_on_first_bar(self) -> None:
        src = """//@version=6
indicator("once first")
var int n = 0
once
    n := 7
plot(n, "n")
"""
        out = Runtime(symbol="TEST").run(src, _bars(8), mode="interpret")
        assert "error" not in out, out.get("error")
        assert out["series"]["n"] == [7] * 8

    def test_nested_once_inside_if(self) -> None:
        src = """//@version=6
indicator("once nested")
var int n = 0
if close > 101
    once
        n := 4
plot(n, "n")
"""
        out = Runtime(symbol="TEST").run(src, _bars(6), mode="interpret")
        assert "error" not in out, out.get("error")
        series = out["series"]["n"]
        # close > 101 first at i=1 (101.5); once fires that bar only
        assert series[0] == 0
        assert series[1:] == [4] * 5

    def test_realtime_unconfirmed_ticks_can_refire(self) -> None:
        """Unconfirmed realtime ticks do not commit ``once`` (rollback)."""
        src = """//@version=6
indicator("once rt")
var int n = 0
if barstate.isrealtime
    once
        n := n + 1
plot(n, "n")
"""
        bars = 6
        ticks = 4
        out = Runtime(symbol="TEST").run(
            src,
            _bars(bars),
            mode="interpret",
            realtime_last_bar=True,
            realtime_ticks=ticks,
        )
        assert "error" not in out, out.get("error")
        series = out["series"]["n"]
        assert series[:-1] == [0] * (bars - 1)
        assert series[-1] == ticks


class TestOnceCompile:
    def test_interpret_compile_parity(self) -> None:
        src = """//@version=6
indicator("once cmp")
var int n = 0
once close > 102
    n := 1
plot(n, "n")
"""
        bars = _bars(12)
        rt = Runtime(symbol="TEST")
        interp = rt.run(src, bars, mode="interpret")
        compiled = rt.run(src, bars, mode="compile")
        assert "error" not in interp, interp.get("error")
        assert "error" not in compiled, compiled.get("error")
        assert interp["series"]["n"] == compiled["series"]["n"]
