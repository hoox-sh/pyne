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

"""Interpreter holes from the 2026-11-22 pipeline audit.

Runtime.run only. Compile is not the oracle for these rows.
"""

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


def _bars(n: int = 4, start: float = 10.0) -> list[dict[str, float | int]]:
    return [
        {
            "open": start + i,
            "high": start + i,
            "low": start + i,
            "close": start + i,
            "volume": 1.0,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def _run(src: str, n: int = 4, **kwargs: Any) -> dict[str, Any]:
    return Runtime(symbol="AUDIT").run(src, _bars(n), mode="interpret", **kwargs)


def _series(out: dict[str, Any], name: str) -> list[Any]:
    assert out.get("error_kind") in (None, ""), out.get("error")
    assert "error" not in out, out.get("error")
    return list(out["series"][name])


def _is_na(value: object) -> bool:
    return value is None or (isinstance(value, float) and value != value)


def test_audit_interpreter_realtime_var_history_rolls_back() -> None:
    """Confirmed tick that is not ``isnew`` keeps the previous bar's history.

    ``var float x = 1`` then ``x := x + 10`` only when ``barstate.isnew``.
    Four bars, last bar realtime, three ticks. Historical bars are one tick
    (11, 21, 31). The last bar's ``+10`` is unconfirmed and must not stick.
    """
    src = """
//@version=6
indicator("rt var hist")
var float x = 1.0
if barstate.isnew
    x := x + 10
plot(x, "x")
plot(x[0], "x0")
plot(x[1], "x1")
"""
    out = _run(src, realtime_last_bar=True, realtime_ticks=3)
    assert _series(out, "x") == [11.0, 21.0, 31.0, 31.0]
    assert _series(out, "x0") == [11.0, 21.0, 31.0, 31.0]
    x1 = _series(out, "x1")
    assert _is_na(x1[0])
    assert x1[1:] == [11.0, 21.0, 21.0]


def test_audit_interpreter_map_for_in_sums_values() -> None:
    """``for [k, v] in map`` sums the values. Map is not a dict."""
    src = """
//@version=6
indicator("map for")
var m = map.new<string, float>()
if bar_index == 0
    map.put(m, "a", 10.0)
    map.put(m, "b", 20.0)
total = 0.0
for [k, v] in m
    total += v
plot(total, "total")
plot(map.size(m), "sz")
"""
    out = _run(src)
    assert _series(out, "total") == [30.0, 30.0, 30.0, 30.0]
    assert _series(out, "sz") == [2.0, 2.0, 2.0, 2.0]


def test_audit_interpreter_matrix_for_in_sums_column() -> None:
    """``for row in matrix`` yields rows. Column 0 is 4 + 5."""
    src = """
//@version=6
indicator("matrix for")
var m = matrix.new<float>(2, 2, 0.0)
if bar_index == 0
    matrix.set(m, 0, 0, 4.0)
    matrix.set(m, 1, 0, 5.0)
total = 0.0
for row in m
    total += array.get(row, 0)
plot(total, "total")
"""
    out = _run(src)
    assert _series(out, "total") == [9.0, 9.0, 9.0, 9.0]


def test_audit_interpreter_for_in_snapshots_array() -> None:
    """Pushing during ``for-in`` does not add iterations. Three elements stay three."""
    src = """
//@version=6
indicator("for snap")
a = array.from(1.0, 2.0, 3.0)
total = 0.0
n = 0
for v in a
    if array.size(a) < 6
        array.push(a, 10.0)
    total += v
    n += 1
plot(total, "total")
plot(n, "n")
plot(array.size(a), "sz")
"""
    out = _run(src)
    assert _series(out, "total") == [6.0, 6.0, 6.0, 6.0]
    assert _series(out, "n") == [3.0, 3.0, 3.0, 3.0]
    assert _series(out, "sz") == [6.0, 6.0, 6.0, 6.0]


def test_audit_interpreter_for_in_string_does_not_iterate() -> None:
    """A string is not a collection. ``for-in`` must not walk characters."""
    src = """
//@version=6
indicator("for str")
int n = 0
for ch in "ab"
    n += 1
plot(n, "n")
"""
    out = _run(src)
    assert _series(out, "n") == [0.0, 0.0, 0.0, 0.0]


def test_audit_interpreter_ta_cog_nan_is_na() -> None:
    """``ta.cog`` warmup NaN is ``na``: ``na`` true, ``nz`` is 0, ``!= 0`` false."""
    src = """
//@version=6
indicator("cog na")
c = ta.cog(close, 10)
plot(c, "c")
plot(na(c) ? 1.0 : 0.0, "isna")
plot(nz(c), "z")
plot(c != 0 ? 1.0 : 0.0, "ne")
"""
    out = _run(src)
    assert all(_is_na(v) for v in _series(out, "c"))
    assert _series(out, "isna") == [1.0, 1.0, 1.0, 1.0]
    assert _series(out, "z") == [0.0, 0.0, 0.0, 0.0]
    assert _series(out, "ne") == [0.0, 0.0, 0.0, 0.0]


def test_audit_interpreter_ta_sma_warmup_stays_na() -> None:
    """``ta.sma`` warmup already returns ``na`` (None), not a float NaN and not 0."""
    src = """
//@version=6
indicator("sma na")
s = ta.sma(close, 10)
plot(s, "s")
plot(na(s) ? 1.0 : 0.0, "isna")
"""
    out = _run(src)
    assert _series(out, "s") == [None, None, None, None]
    assert _series(out, "isna") == [1.0, 1.0, 1.0, 1.0]


def test_audit_interpreter_udf_missing_required_raises() -> None:
    """A plain UDF with a missing required arg raises. It must not concat the name."""
    src = """
//@version=6
indicator("udf miss")
f(x) =>
    x + 1.0
plot(f(), "y")
"""
    out = _run(src)
    assert out.get("error_kind") == "runtime", out
    assert out.get("error_type") == "TypeError", out
    assert "missing 1 required positional argument: 'x'" in str(out.get("error") or "")
    assert "series" not in out


def test_audit_interpreter_udf_missing_required_ignores_caller_binding() -> None:
    """The same short call must not read the caller's ``x`` (that would plot 8)."""
    src = """
//@version=6
indicator("udf miss caller")
x = 7.0
f(x) =>
    x + 1.0
plot(f(), "y")
"""
    out = _run(src)
    assert out.get("error_kind") == "runtime", out
    assert out.get("error_type") == "TypeError", out
    assert "missing 1 required positional argument: 'x'" in str(out.get("error") or "")
    assert "series" not in out
    assert "8.0" not in str(out.get("error") or "")


def test_audit_interpreter_udf_trailing_default_still_binds() -> None:
    """A trailing default still fills when the required prefix is present."""
    src = """
//@version=6
indicator("udf def")
f(x, y = 1.0) =>
    x + y
plot(f(close), "y")
"""
    out = _run(src)
    assert _series(out, "y") == [11.0, 12.0, 13.0, 14.0]


def test_audit_interpreter_array_subscript_is_history_not_element() -> None:
    """``[]`` on an array is history of the array value, not an element.

    Choice (names.py scalar rule, no array-series history): ``a[0]`` is the
    current array, ``a[1]`` is ``na``. ``a[0]`` is not ``3.0`` and not ``na``.
    ``a[1]`` is not element ``2.0``. ``array.get(a, 0)`` stays ``1.0``.
    ``close[1]`` stays the previous close.
    """
    src = """
//@version=6
indicator("arr hist")
a = array.from(1.0, 2.0, 3.0)
plot(array.get(a, 0), "get0")
plot(array.size(a[0]), "sz0")
plot(array.get(a[0], 0), "elem0")
plot(array.get(a[0], 2), "elem2")
plot(na(a[1]) ? 1.0 : 0.0, "na1")
plot(a[1] == 2.0 ? 1.0 : 0.0, "el2")
plot(close[1], "c1")
"""
    out = _run(src)
    assert _series(out, "get0") == [1.0, 1.0, 1.0, 1.0]
    # a[0] is the array (size 3, first element 1, last element 3), not na.
    assert _series(out, "sz0") == [3.0, 3.0, 3.0, 3.0]
    assert _series(out, "elem0") == [1.0, 1.0, 1.0, 1.0]
    assert _series(out, "elem2") == [3.0, 3.0, 3.0, 3.0]
    assert _series(out, "na1") == [1.0, 1.0, 1.0, 1.0]
    assert _series(out, "el2") == [0.0, 0.0, 0.0, 0.0]
    c1 = _series(out, "c1")
    assert _is_na(c1[0])
    assert c1[1:] == [10.0, 11.0, 12.0]
