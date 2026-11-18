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

"""Interpret / compile parity for expression bugs found in the 0.7.0 review.

Covers ``iff(na)``, ``math.round`` precision, ``math.log`` base, ``math.pow``
na propagation, operator ``na == na``, a loop counter that shadows a series
of the same name, and v6 ``for`` loops that re-read ``to`` each iteration.
"""

from __future__ import annotations

import math

import pytest

from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime


def _bars(n: int = 4) -> list[dict]:
    return [
        {
            "open": 1.0 + i,
            "high": 2.0 + i,
            "low": 0.5,
            "close": 1.5 + i * 0.25,
            "volume": 10.0,
            "time": 1_700_000_000 + i * 86_400,
        }
        for i in range(n)
    ]


def _series(src: str, mode: str, n: int = 4) -> dict:
    out = Runtime().run(src, _bars(n), mode=mode)
    assert not out.get("error"), out.get("error")
    return out["series"]


def _same(src: str, n: int = 4) -> tuple[dict, dict]:
    interp = _series(src, "interpret", n)
    comp = _series(src, "compile", n)
    assert set(interp) == set(comp)
    for key in interp:
        left = interp[key]
        right = comp[key]
        assert len(left) == len(right)
        for a, b in zip(left, right, strict=True):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na or b_na:
                assert a_na and b_na
            else:
                assert b == pytest.approx(float(a))
    return interp, comp


_EXPR = {
    "iff_na": "iff(na, 1, 0)",
    "iff_true": "iff(true, 1, 0)",
    "iff_false": "iff(false, 1, 0)",
    "round_half": "math.round(2.5)",
    "round_neg_half": "math.round(-2.5)",
    "round_prec": "math.round(1.234, 2)",
    "round_tenth": "math.round(1.55, 1)",
    "round_tens": "math.round(123.45, -1)",
    "log10": "math.log(100, 10)",
    "log2": "math.log(8, 2)",
    "log_base1": "na(math.log(10, 1)) ? 1 : 0",
    "pow_na": "na(math.pow(na, 0)) ? 1 : 0",
    "eq_na": "na == na ? 1 : 0",
    "ne_na": "na != 1 ? 1 : 0",
    "cmp": "close > open ? 1 : 0",
}


@pytest.mark.parametrize("name", list(_EXPR))
def test_expr_interpret_matches_compile(name: str) -> None:
    src = f"""//@version=6
indicator("t")
plot({_EXPR[name]}, "v")
"""
    _same(src)


def test_iff_numeric_stays_nopython() -> None:
    src = """//@version=6
indicator("t")
plot(iff(close > open, 1, 0), "v")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False
    assert compiled.nopython_fallback_reason is None
    got, _ = _same(src)
    # First bar: close 1.5 > open 1.
    assert got["v"][0] == pytest.approx(1.0)


def test_iff_na_is_na_on_compile() -> None:
    src = """//@version=6
indicator("t")
plot(iff(na, 1, 0), "v")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False
    got, _ = _same(src)
    assert got["v"][0] is None


def test_switch_na_still_matches() -> None:
    """Operator ``na == na`` is false. Switch still matches an na arm."""
    src = """//@version=6
indicator("t")
x = switch float(na)
    na => 1
    => 3
plot(x, "x")
"""
    got, _ = _same(src)
    assert got["x"][0] == pytest.approx(1.0)


def test_for_counter_shadows_preexisting_series() -> None:
    src = """//@version=6
indicator("t")
i = 5
s = 0.0
for i = 0 to i
    s := s + 1
plot(s, "s")
"""
    got, _ = _same(src)
    assert got["s"][0] == pytest.approx(1.0)


def test_for_counter_negative_preexisting() -> None:
    src = """//@version=6
indicator("t")
i = -3
s = 0.0
for i = 0 to i
    s := s + 1
plot(s, "s")
"""
    got, _ = _same(src)
    assert got["s"][0] == pytest.approx(1.0)


def test_dynamic_for_limit_still_one_iteration() -> None:
    src = """//@version=6
indicator("t")
limit = 2
s = 0.0
for i = 0 to limit
    s := s + 1
    limit := 0
plot(s, "s")
"""
    got, _ = _same(src)
    assert got["s"][0] == pytest.approx(1.0)


def test_for_end_bound_grows_and_is_visited() -> None:
    """v6 reads ``to`` before every iteration. A frozen end of 1 stops at 1."""
    src = """//@version=6
indicator("t")
end = 1
last = -1.0
count = 0.0
for i = 0 to end
    last := i
    count := count + 1
    end := 4
plot(last, "last")
plot(count, "count")
"""
    got, _ = _same(src, n=2)
    # Inclusive 0..4. Frozen v5 would plot last=1, count=2.
    assert got["last"] == pytest.approx([4.0, 4.0])
    assert got["count"] == pytest.approx([5.0, 5.0])


def test_for_end_expression_rereads_each_iteration() -> None:
    """``to`` is an expression, not a captured number. Growing ``extra`` extends it."""
    src = """//@version=6
indicator("t")
extra = 0
last = -1.0
for i = 0 to 1 + extra
    last := i
    extra := 3
plot(last, "last")
"""
    got, _ = _same(src, n=2)
    # First check is 1+0. Later checks are 1+3, so the counter reaches 4.
    assert got["last"] == pytest.approx([4.0, 4.0])


def test_for_end_follows_array_size_grown_in_body() -> None:
    """``array.size`` in ``to`` is re-evaluated, so a push inside the body is reachable."""
    src = """//@version=6
indicator("t")
arr = array.new_float()
array.push(arr, 1.0)
last = -1.0
for i = 0 to array.size(arr) - 1
    last := i
    if i == 0
        array.push(arr, 2.0)
        array.push(arr, 3.0)
plot(last, "last")
plot(array.size(arr), "sz")
"""
    got, _ = _same(src, n=2)
    # Size starts at 1 (to=0). The i==0 body grows it to 3, so i reaches 2.
    assert got["last"] == pytest.approx([2.0, 2.0])
    assert got["sz"] == pytest.approx([3.0, 3.0])


def test_compile_reports_literal_inputs() -> None:
    src = """//@version=6
indicator("inputs")
length = input.int(14, "RSI Length", minval=2, maxval=100)
oversold = input.float(30, "Oversold", minval=1, maxval=50)
plot(close)
"""
    interp = Runtime().run(src, _bars(3), mode="interpret")
    comp = Runtime().run(src, _bars(3), mode="compile")
    assert not interp.get("error") and not comp.get("error")
    assert interp["inputs"] == comp["inputs"]
    assert [item["title"] for item in comp["inputs"]] == ["RSI Length", "Oversold"]
    assert comp["inputs"][0]["default"] == 14
    assert comp["inputs"][0]["min"] == 2
    assert comp["inputs"][1]["value"] == pytest.approx(30.0)


def test_symbol_index_failure_is_a_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("lsprotocol")
    from pynescript.langserver.workspace import Workspace

    def _boom(*_args, **_kwargs):
        raise RuntimeError("index exploded")

    monkeypatch.setattr("pynescript.langserver.workspace.build_symbol_index", _boom)
    ws = Workspace()
    uri = "file:///t.pine"
    ws.put_document(uri, '//@version=6\nindicator("t")\nplot(close)\n')
    codes = [diag.code for diag in ws.get_all_diagnostics()[uri]]
    assert "E002" in codes
    assert ws.get_document(uri).valid_analysis is None
    assert ws.get_document(uri).valid_ast is not None
