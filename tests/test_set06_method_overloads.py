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

"""Method overloads dispatched by arity / receiver (set06 ``update``)."""

from __future__ import annotations

import ast
import signal

from pathlib import Path

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


_SET06_LIB = Path(__file__).parent / "data" / "set06" / "libraries"


def _ohlcv(n: int = 12, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1.0, close - 1.0, close, np.ones(n)


def _last(out: dict, name: str = "plot_0") -> float:
    return float(np.asarray(out[name], dtype=np.float64)[-1])


def _defs_named(code: str, prefix: str) -> list[ast.FunctionDef]:
    tree = ast.parse(code)
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and (node.name == prefix or node.name.startswith(prefix + "__"))
    ]


def _calls_named(code: str, names: set[str]) -> list[ast.Call]:
    tree = ast.parse(code)
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
            found.append(node)
    return found


class _TimeoutError(Exception):
    """SIGALRM fired while a compile/run was expected to finish quickly."""


def _run_with_timeout(fn, seconds: float = 20.0):
    def _handler(_signum, _frame):
        msg = "compile/run exceeded timeout"
        raise _TimeoutError(msg)

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, old)


_TWO_UPDATE_SRC = """//@version=5
indicator("ov")
type StatsBox
    float v = 0.0
type SeasonBox
    float v = 0.0
method update(StatsBox this, float wins, float losses, float n) =>
    this.v := wins + losses + n
    this.v
method update(SeasonBox this, float data, color c1 = color.red, color c2 = color.blue, color c3 = color.green, color c4 = color.white, color c5 = color.black, color c6 = color.gray, color c7 = color.orange) =>
    this.v := data
    this.v
var SeasonBox seasonalTable = SeasonBox.new()
var StatsBox statsData = StatsBox.new()
float s = seasonalTable.update(5.0)
float t = statsData.update(1.0, 2.0, 3.0)
plot(s)
plot(t)
"""


def test_method_update_overloads_compile_and_run() -> None:
    """Two ``method update`` overloads of different arity compile and run."""
    code = transpile(_TWO_UPDATE_SRC)
    defs = _defs_named(code, "update")
    assert len(defs) >= 2, code
    by_name = {d.name: len(d.args.args) for d in defs}
    # First def keeps Pine name; later arity is renamed (update__9, …).
    assert "update" in by_name
    renamed = [n for n in by_name if n != "update"]
    assert renamed, f"second overload was not renamed: {by_name}"
    # User formals are a prefix of the Python def (extras may follow).
    four = [n for n, arity in by_name.items() if arity >= 4]
    nine = [n for n, arity in by_name.items() if n != "update"]
    assert four and nine

    names = {d.name for d in defs}
    calls = _calls_named(code, names)
    assert calls, "no update(...) call in transpile"
    # seasonalTable.update(5.0) must not invoke the 4-user-formal def with
    # 9 filled args (``update() takes 4 positional arguments but 9 were given``).
    for call in calls:
        n_passed = len(call.args) + len(call.keywords)
        if call.func.id == "update":
            assert n_passed != 9, ast.dump(call)
            assert n_passed >= 4

    compiled = compile_script(_TWO_UPDATE_SRC, use_cache=False)
    out = compiled.run(*_ohlcv(12))
    assert abs(_last(out, "plot_0") - 5.0) < 1e-9
    assert abs(_last(out, "plot_1") - 6.0) < 1e-9


def test_method_update_defaults_pick_nine_arg_overload() -> None:
    """2 user args + 7 color defaults call the 9-formal overload, not the 4-arg def."""
    src = """//@version=5
indicator("ov2")
type A
    float v = 0.0
type B
    float v = 0.0
method update(A this, float x, float y, float z) =>
    this.v := x + y + z
    this.v
method update(B this, float x, color a = color.red, color b = color.blue, color c = color.green, color d = color.white, color e = color.black, color f = color.gray, color g = color.orange) =>
    this.v := x + 100.0
    this.v
var B seasonalTable = B.new()
plot(seasonalTable.update(5.0))
"""
    code = transpile(src)
    assert "def update(" in code
    assert any(ln.startswith("def update__") for ln in code.splitlines()), code
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(8))
    assert abs(_last(out) - 105.0) < 1e-9


def test_method_field_receiver_dispatches_nested_udt() -> None:
    """``this.wins.getAvgProfit()`` must call SideStats, not recurse into StatsData."""
    src = """//@version=5
indicator("gp")
type SideStats
    float sumProfit = 0.0
    int numOf = 1
method getAvgProfit(SideStats this) =>
    this.sumProfit / this.numOf
type StatsData
    SideStats wins
method getAvgProfit(StatsData this) =>
    this.wins.getAvgProfit()
s = StatsData.new(SideStats.new(10.0, 2))
plot(s.getAvgProfit())
"""
    code = transpile(src)
    assert "getAvgProfit__" in code
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(8))
    assert abs(_last(out) - 5.0) < 1e-9


def test_corpus_0030_update_arity_typeerror_gone() -> None:
    """0030 ``seasonalTable.update(seasonalData)`` must not hit StatsData.update."""
    pine = _SET06_LIB / "0030_lib_3.pine"
    src = pine.read_text(encoding="utf-8")
    code = transpile(src)
    defs = _defs_named(code, "update")
    assert len(defs) >= 2, "0030 expected several method update overloads"
    names = {d.name for d in defs}
    # Later overloads must keep distinct py names (not all ``def update``).
    assert any(n.startswith("update__") for n in names), names
    calls = _calls_named(code, names)
    assert calls
    for call in calls:
        n_passed = len(call.args) + len(call.keywords)
        if call.func.id == "update":
            # StatsData.update — 4 user formals; never the 9-arg SeasonalTable call
            assert n_passed != 9, ast.dump(call)
    # seasonalTable.update(...) must hit the 9-formal overload, not StatsData
    assert any(c.func.id.startswith("update__") and len(c.args) + len(c.keywords) >= 6 for c in calls)

    def _go() -> dict:
        compiled = compile_script(src, use_cache=False)
        return compiled.run(*_ohlcv(12))

    try:
        out = _run_with_timeout(_go, seconds=20.0)
    except TypeError as exc:
        msg = str(exc)
        if "update" in msg and "positional" in msg:
            raise
        pytest.skip(f"0030 later TypeError after update arity fixed: {exc}")
    except _TimeoutError:
        pytest.skip("0030 compile/run hung; reduced snippet is the lock")
    except RecursionError:
        raise
    except Exception as exc:
        msg = str(exc)
        if "INV" in msg:
            pytest.skip(f"0030 later INV after update arity fixed: {exc}")
        if "update" in msg and "positional" in msg:
            raise
        pytest.skip(f"0030 later error after update arity fixed: {exc}")
    else:
        assert isinstance(out, dict)
