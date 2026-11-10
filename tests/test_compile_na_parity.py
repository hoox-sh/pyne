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

"""Interpret / compile parity for na conditions, switch, for-to, and modulo.

These used to disagree because the compiler lowered ``na`` to ``np.nan`` and
then used Python truthiness (``bool(nan)`` is true) and IEEE ``==``.
"""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.ast.error import SyntaxError as PineSyntaxError
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse
from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime


def _bars(n: int = 3) -> list[dict]:
    return [
        {
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 10.0,
            "time": 1_700_000_000 + i * 86_400,
        }
        for i in range(n)
    ]


def _series(src: str, mode: str) -> dict:
    out = Runtime().run(src, _bars(), mode=mode)
    assert not out.get("error"), out.get("error")
    return out["series"]


def _eval(expr: str):
    return NodeLiteralEvaluator().visit(parse(expr, mode="eval").body)


CASES = {
    "boolops": """//@version=6
indicator("t")
plot(na and true ? 1 : 0, "a")
plot(na or false ? 1 : 0, "b")
plot(false or na ? 1 : 0, "c")
plot(true or na ? 1 : 0, "d")
plot(na ? 1 : 0, "e")
""",
    "notna": """//@version=6
indicator("t")
x = not na
plot(na(x) ? 1 : 0, "isna")
plot(x ? 1 : 0, "truth")
""",
    "ifna": """//@version=6
indicator("t")
x = na
y = 0.0
if x
    y := 1.0
plot(y, "y")
z = 0.0
if not na
    z := 1.0
plot(z, "z")
""",
    "switchna": """//@version=6
indicator("t")
x = switch float(na)
    na => 1
    => 3
plot(x, "x")
s = "bb"
w = switch s
    "aa" => 1
    "bb" => 2
    => 3
plot(w, "w")
""",
    "forto": """//@version=6
indicator("t")
limit = 2
s = 0.0
for i = 0 to limit
    s := s + 1
    limit := 0
plot(s, "s")
t = 0.0
for i = 0 to 3
    t := t + 1
plot(t, "t")
""",
    "mod": """//@version=6
indicator("t")
plot(-7 % 3, "i")
plot(-7.0 % 3.0, "f")
plot(7 % -3, "j")
plot(7 % 3, "k")
""",
    "cmp": """//@version=6
indicator("t")
plot(close > open ? 1 : 0, "up")
""",
}


@pytest.mark.parametrize("name", list(CASES))
def test_interpret_matches_compile(name: str) -> None:
    src = CASES[name]
    interp = _series(src, "interpret")
    comp = _series(src, "compile")
    assert set(interp) == set(comp)
    for key in interp:
        left = interp[key]
        right = comp[key]
        assert len(left) == len(right)
        for a, b in zip(left, right, strict=True):
            if a is None or (isinstance(a, float) and a != a):
                assert b is None or (isinstance(b, float) and b != b)
            else:
                assert b == pytest.approx(float(a))


def test_numeric_if_stays_nopython() -> None:
    compiled = compile_script(CASES["cmp"], use_cache=False)
    assert compiled.object_mode is False
    assert compiled.nopython_fallback_reason is None


def test_expected_values() -> None:
    got = _series(CASES["boolops"], "compile")
    assert got["a"][0] == pytest.approx(0.0)
    assert got["b"][0] == pytest.approx(0.0)
    assert got["c"][0] == pytest.approx(0.0)
    assert got["d"][0] == pytest.approx(1.0)
    assert got["e"][0] == pytest.approx(0.0)

    got = _series(CASES["notna"], "compile")
    assert got["isna"][0] == pytest.approx(1.0)
    assert got["truth"][0] == pytest.approx(0.0)

    got = _series(CASES["ifna"], "compile")
    assert got["y"][0] == pytest.approx(0.0)
    # ``not na`` is na, and na is a false condition.
    assert got["z"][0] == pytest.approx(0.0)

    got = _series(CASES["switchna"], "compile")
    assert got["x"][0] == pytest.approx(1.0)
    assert got["w"][0] == pytest.approx(2.0)

    got = _series(CASES["forto"], "compile")
    assert got["s"][0] == pytest.approx(1.0)
    assert got["t"][0] == pytest.approx(4.0)

    got = _series(CASES["mod"], "compile")
    assert got["i"][0] == pytest.approx(-1.0)
    assert got["f"][0] == pytest.approx(-1.0)
    assert got["j"][0] == pytest.approx(1.0)
    assert got["k"][0] == pytest.approx(1.0)


def test_interpret_nan_is_false_and_mod_sign() -> None:
    assert _eval("na and true") is False
    assert _eval("not na") is None
    assert _pine_not_float_nan() is None
    assert _eval("-7 % 3") == -1
    assert _eval("7 % -3") == 1
    assert _eval("7 % 3") == 1
    assert _eval("-7.0 % 3.0") == pytest.approx(-1.0)
    assert _eval("1 % 0") is None


def _pine_not_float_nan():
    from pynescript.ast.evaluator.expressions import _pine_is_true

    assert _pine_is_true(float("nan")) is False
    node = parse("not x", mode="eval").body
    ev = NodeLiteralEvaluator()
    ev.context["x"] = float("nan")
    return ev.visit(node)


def test_integer_mod_under_njit() -> None:
    import numba

    from pynescript.compiler.numba_builtins import numba_safe_mod

    @numba.njit
    def call(a, b):
        return numba_safe_mod(a, b)

    assert call(-7, 3) == pytest.approx(-1.0)
    assert call(7, -3) == pytest.approx(1.0)
    assert np.isnan(call(1, 0))


def test_syntax_error_without_details_is_message() -> None:
    err = PineSyntaxError("boom")
    assert str(err) == "boom"
