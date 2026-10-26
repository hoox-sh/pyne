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

"""Runtime.interpret coverage for array.* edge cases."""

from __future__ import annotations

from pynescript.runtime import Runtime


def _bars(n: int = 4) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


def _run(src: str, bars: list[dict[str, float | int]] | None = None) -> dict:
    out = Runtime(symbol="ARR").run(src, bars if bars is not None else _bars(), mode="interpret")
    assert "error" not in out, out.get("error")
    return out


def _last(series: dict, name: str):
    return series[name][-1]


class TestArrayFromJoinFill:
    def test_from_empty_join_fill_range(self) -> None:
        src = """//@version=5
indicator("from_join_fill")
empty = array.from()
plot(array.size(empty), "esz")
a = array.from(1, 2, 3)
plot(str.length(array.join(a, "-")), "jn")
b = array.new_float(4, 0.0)
array.fill(b, 9.0, 1, 3)
plot(array.get(b, 0), "f0")
plot(array.get(b, 1), "f1")
plot(array.get(b, 2), "f2")
plot(array.get(b, 3), "f3")
array.fill(b, 1.0)
plot(array.sum(b), "full")
"""
        s = _run(src)["series"]
        assert _last(s, "esz") == 0
        assert _last(s, "jn") == 5  # "1-2-3"
        assert _last(s, "f0") == 0.0
        assert _last(s, "f1") == 9.0
        assert _last(s, "f2") == 9.0
        assert _last(s, "f3") == 0.0
        assert _last(s, "full") == 4.0


class TestArraySortBinarySearch:
    def test_sort_and_searches(self) -> None:
        src = """//@version=5
indicator("sort_bs")
a = array.from(3.0, 1.0, 2.0, 1.0, 4.0)
array.sort(a)
plot(array.get(a, 0), "s0")
plot(array.get(a, 4), "s4")
plot(array.binary_search(a, 2.0), "bs")
plot(array.binary_search(a, 9.0), "miss")
plot(array.binary_search_leftmost(a, 1.0), "bl")
plot(array.binary_search_rightmost(a, 1.0), "br")
idx = array.sort_indices(array.from(3.0, 1.0, 2.0))
plot(array.get(idx, 0), "si0")
b = array.from(1.0, 3.0, 2.0)
array.sort(b, order.descending)
plot(array.get(b, 0), "desc0")
"""
        s = _run(src)["series"]
        assert _last(s, "s0") == 1.0
        assert _last(s, "s4") == 4.0
        assert _last(s, "bs") == 2
        assert _last(s, "miss") == -1
        assert _last(s, "bl") == 0
        assert _last(s, "br") == 1
        assert _last(s, "si0") == 1
        assert _last(s, "desc0") == 3.0


class TestArrayEmptyNaOutOfRange:
    def test_na_size_get_includes_indexof(self) -> None:
        src = """//@version=5
indicator("na_oor")
a = array.new_float(3, na)
plot(array.size(a), "sz")
plot(na(array.get(a, 0)) ? 1 : 0, "gna")
plot(na(array.get(a, 99)) ? 1 : 0, "goor")
plot(na(array.get(a, -99)) ? 1 : 0, "gneg")
array.set(a, 1, 5.0)
plot(array.includes(a, 5.0) ? 1 : 0, "inc")
plot(array.indexof(a, 5.0), "ixo")
plot(array.lastindexof(a, 5.0), "lix")
plot(array.includes(a, 7.0) ? 1 : 0, "miss")
"""
        s = _run(src)["series"]
        assert _last(s, "sz") == 3
        assert _last(s, "gna") == 1
        assert _last(s, "goor") == 1
        assert _last(s, "gneg") == 1
        assert _last(s, "inc") == 1
        assert _last(s, "ixo") == 1
        assert _last(s, "lix") == 1
        assert _last(s, "miss") == 0


class TestArrayMutationsStats:
    def test_push_pop_shift_unshift_reverse_slice(self) -> None:
        src = """//@version=5
indicator("mut")
a = array.from(1.0, 2.0, 3.0)
array.push(a, 4.0)
plot(array.pop(a), "pop")
array.unshift(a, 0.0)
plot(array.shift(a), "sh")
array.reverse(a)
plot(array.first(a), "first")
plot(array.last(a), "last")
sl = array.slice(a, 0, 2)
plot(array.size(sl), "slsz")
plot(array.avg(a), "avg")
plot(array.min(a), "mn")
plot(array.max(a), "mx")
plot(array.range(a), "rng")
plot(array.sum(a), "sum")
"""
        s = _run(src)["series"]
        assert _last(s, "pop") == 4.0
        assert _last(s, "sh") == 0.0
        assert _last(s, "first") == 3.0
        assert _last(s, "last") == 1.0
        assert _last(s, "slsz") == 2
        assert _last(s, "mn") == 1.0
        assert _last(s, "mx") == 3.0
        assert _last(s, "rng") == 2.0
        assert _last(s, "sum") == 6.0

    def test_some_every_clear_copy_concat_abs(self) -> None:
        src = """//@version=5
indicator("boolstats")
a = array.from(1.0, 2.0, 3.0)
plot(array.some(a) ? 1 : 0, "some")
plot(array.every(a) ? 1 : 0, "every")
z = array.from(0.0, 1.0)
plot(array.every(z) ? 1 : 0, "zevery")
c = array.copy(a)
array.clear(a)
plot(array.size(a), "cleared")
plot(array.size(c), "copied")
cat = array.concat(c, array.from(4.0))
plot(array.size(cat), "cat")
n = array.abs(array.from(-2.0, 3.0))
plot(array.get(n, 0), "ab0")
plot(array.median(array.from(1.0, 2.0, 3.0)), "med")
plot(array.stdev(array.from(1.0, 2.0, 3.0)), "sd")
plot(array.variance(array.from(1.0, 2.0, 3.0)), "var")
"""
        s = _run(src)["series"]
        assert _last(s, "some") == 1
        assert _last(s, "every") == 1
        assert _last(s, "zevery") == 0
        assert _last(s, "cleared") == 0
        assert _last(s, "copied") == 3
        assert _last(s, "cat") == 4
        assert _last(s, "ab0") == 2.0
        assert _last(s, "med") == 2.0


class TestArrayPercentileModeStandardize:
    def test_percentile_mode_standardize_percentrank(self) -> None:
        src = """//@version=5
indicator("pct")
a = array.from(1.0, 2.0, 3.0, 4.0, 5.0)
plot(array.percentile_linear_interpolation(a, 50), "pli")
plot(array.percentile_nearest_rank(a, 50), "pnr")
plot(array.percentrank(a, 3.0), "pr")
b = array.from(1.0, 2.0, 2.0, 3.0)
plot(array.mode(b), "mode")
st = array.standardize(a)
plot(array.size(st), "stsz")
plot(array.covariance(array.from(1.0, 2.0, 3.0), array.from(1.0, 2.0, 3.0)), "cov")
"""
        s = _run(src)["series"]
        assert _last(s, "pli") == 3.0
        assert _last(s, "pnr") == 3.0
        assert _last(s, "mode") == 2.0
        assert _last(s, "stsz") == 5


class TestArrayRemoveInsertNewAliases:
    def test_remove_insert_and_typed_new(self) -> None:
        src = """//@version=5
indicator("rmins")
a = array.from(10.0, 20.0, 30.0)
plot(array.remove(a, 1), "rm")
plot(array.size(a), "sz1")
array.insert(a, 1, 15.0)
plot(array.get(a, 1), "ins")
i = array.new_int(2, 7)
plot(array.get(i, 0), "i0")
s = array.new_string(1, "x")
plot(str.length(array.get(s, 0)), "slen")
bf = array.new_bool(1, true)
plot(array.get(bf, 0) ? 1 : 0, "b0")
f = array.new<float>(2, 1.5)
plot(array.sum(f), "fsum")
"""
        s = _run(src)["series"]
        assert _last(s, "rm") == 20.0
        assert _last(s, "sz1") == 2
        assert _last(s, "ins") == 15.0
        assert _last(s, "i0") == 7
        assert _last(s, "slen") == 1
        assert _last(s, "b0") == 1
        assert _last(s, "fsum") == 3.0
