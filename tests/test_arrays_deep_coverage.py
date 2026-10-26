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

"""Deep Runtime + direct-dispatch coverage for array.* soft-fail and edge paths."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.runtime import Runtime


def _bars(n: int = 3) -> list[dict[str, float | int]]:
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
    out = Runtime(symbol="ARR_DEEP").run(src, bars if bars is not None else _bars(), mode="interpret")
    assert "error" not in out, out.get("error")
    return out


def _last(series: dict, name: str):
    return series[name][-1]


def _map() -> dict:
    return NodeLiteralEvaluator()._build_builtin_map()


# ---------------------------------------------------------------------------
# Runtime scripts — mutation / query edges beyond test_arrays_edges_coverage
# ---------------------------------------------------------------------------


class TestArraySliceUnshiftShiftIndex:
    def test_slice_bounds_and_mutations(self) -> None:
        src = """//@version=5
indicator("slice_mut")
a = array.from(10.0, 20.0, 30.0, 40.0)
sl = array.slice(a, 1, 3)
plot(array.size(sl), "slsz")
plot(array.get(sl, 0), "sl0")
plot(array.size(array.slice(a, 3, 1)), "empty")
array.unshift(a, 5.0)
plot(array.first(a), "u0")
plot(array.shift(a), "sh")
plot(array.indexof(a, 30.0), "ixo")
plot(array.lastindexof(a, 30.0), "lix")
plot(array.includes(a, 99.0) ? 0 : 1, "miss")
b = array.copy(a)
array.reverse(b)
plot(array.first(b), "rev0")
cat = array.concat(a, array.from(50.0))
plot(array.size(cat), "cat")
"""
        s = _run(src)["series"]
        assert _last(s, "slsz") == 2
        assert _last(s, "sl0") == 20.0
        assert _last(s, "empty") == 0
        assert _last(s, "u0") == 5.0
        assert _last(s, "sh") == 5.0
        assert _last(s, "ixo") == 2
        assert _last(s, "lix") == 2
        assert _last(s, "miss") == 1
        assert _last(s, "rev0") == 40.0
        assert _last(s, "cat") == 5

    def test_negative_get_set_and_fill_range(self) -> None:
        src = """//@version=5
indicator("neg_idx")
a = array.from(1.0, 2.0, 3.0)
plot(array.get(a, -1), "neg1")
array.set(a, -2, 9.0)
plot(array.get(a, 1), "setneg")
array.fill(a, 0.0, 0, 2)
plot(array.get(a, 0), "f0")
plot(array.get(a, 2), "f2")
"""
        s = _run(src)["series"]
        assert _last(s, "neg1") == 3.0
        assert _last(s, "setneg") == 9.0
        assert _last(s, "f0") == 0.0
        assert _last(s, "f2") == 3.0


class TestArrayEverySomePercentrank:
    def test_every_some_bool_arrays(self) -> None:
        src = """//@version=5
indicator("bool_ops")
t = array.from(true, true, true)
f = array.from(true, false)
z = array.from(0.0, 0.0)
plot(array.every(t) ? 1 : 0, "et")
plot(array.every(f) ? 1 : 0, "ef")
plot(array.some(f) ? 1 : 0, "sf")
plot(array.some(z) ? 1 : 0, "sz")
"""
        s = _run(src)["series"]
        assert _last(s, "et") == 1
        assert _last(s, "ef") == 0
        assert _last(s, "sf") == 1
        assert _last(s, "sz") == 0

    def test_percentrank_and_biased_stats(self) -> None:
        src = """//@version=5
indicator("pr_stats")
a = array.from(1.0, 2.0, 3.0, 4.0, 5.0)
plot(array.percentrank(a, 3.0), "pr")
plot(array.percentrank(a, 1.0), "pr1")
plot(array.stdev(a, true), "sdp")
plot(array.stdev(a, false), "sds")
plot(array.variance(a, true), "vp")
plot(array.variance(a, false), "vs")
plot(array.percentile_linear_interpolation(a, 0), "pli0")
plot(array.percentile_nearest_rank(a, 100), "pnr100")
"""
        s = _run(src)["series"]
        assert _last(s, "pr") == pytest.approx(50.0)
        assert _last(s, "pr1") == pytest.approx(0.0)
        assert _last(s, "sdp") == pytest.approx(1.41421356237, abs=1e-6)
        assert _last(s, "sds") == pytest.approx(1.58113883008, abs=1e-6)
        assert _last(s, "pli0") == 1.0
        assert _last(s, "pnr100") == 5.0

    def test_min_max_nth_and_na_slots(self) -> None:
        src = """//@version=5
indicator("nth")
a = array.from(5.0, 1.0, 3.0, na, 2.0)
plot(array.min(a), "mn")
plot(array.max(a), "mx")
plot(array.min(a, 1), "mn1")
plot(array.max(a, 1), "mx1")
plot(na(array.avg(array.from(na, na))) ? 1 : 0, "avgna")
plot(na(array.sum(array.from(na))) ? 1 : 0, "sumna")
"""
        s = _run(src)["series"]
        assert _last(s, "mn") == 1.0
        assert _last(s, "mx") == 5.0
        assert _last(s, "mn1") == 2.0
        assert _last(s, "mx1") == 3.0
        assert _last(s, "avgna") == 1


class TestArrayJoinSortNaUdtDict:
    def test_join_default_sep_and_sort_na_last(self) -> None:
        src = """//@version=5
indicator("join_sort")
a = array.from(3.0, na, 1.0, 2.0)
plot(str.length(array.join(a)), "j0")
plot(str.length(array.join(a, ",")), "j1")
array.sort(a)
plot(na(array.get(a, 3)) ? 1 : 0, "na_last")
plot(array.get(a, 0), "s0")
idx = array.sort_indices(array.from(3.0, 1.0, na, 2.0))
plot(array.get(idx, 0), "si0")
plot(array.get(idx, 3), "sina")
"""
        s = _run(src)["series"]
        assert _last(s, "na_last") == 1
        assert _last(s, "s0") == 1.0
        assert _last(s, "si0") == 1
        assert _last(s, "sina") == 2

    def test_new_aliases_and_pop_empty(self) -> None:
        src = """//@version=5
indicator("new_pop")
c = array.new_color(1, color.red)
plot(array.size(c), "csz")
e = array.new_float(0)
plot(na(array.pop(e)) ? 1 : 0, "popna")
plot(na(array.shift(e)) ? 1 : 0, "shna")
f = array.newfloat(2, 1.0)
plot(array.sum(f), "fs")
"""
        s = _run(src)["series"]
        assert _last(s, "csz") == 1
        assert _last(s, "popna") == 1
        assert _last(s, "shna") == 1
        assert _last(s, "fs") == 2.0


# ---------------------------------------------------------------------------
# Direct builtin map — soft-na, wrappers, type-error soft paths
# ---------------------------------------------------------------------------


class TestArraySoftNaDirect:
    def test_size_get_push_pop_on_na(self) -> None:
        m = _map()
        assert m["array.size"]([None]) is None
        assert m["array.get"]([None, 0]) is None
        assert m["array.push"]([None, 1]) is None
        assert m["array.push"]([]) is None
        assert m["array.pop"]([None]) is None
        assert m["array.clear"]([None]) is None
        assert m["array.copy"]([None]) is None
        assert m["array.reverse"]([None]) is None
        assert m["array.unshift"]([None, 1]) is None
        assert m["array.shift"]([None]) is None
        assert m["array.first"]([None]) is None
        assert m["array.last"]([None]) is None
        assert m["array.includes"]([None, 1]) is None
        assert m["array.indexof"]([None, 1]) is None
        assert m["array.lastindexof"]([None, 1]) is None
        assert m["array.remove"]([None, 0]) is None
        assert m["array.abs"]([None]) is None
        assert m["array.avg"]([None]) is None
        assert m["array.sum"]([None]) is None
        assert m["array.median"]([None]) is None
        assert m["array.range"]([None]) is None
        assert m["array.mode"]([None]) is None
        assert m["array.standardize"]([None]) is None
        assert m["array.stdev"]([None]) is None
        assert m["array.variance"]([None]) is None
        assert m["array.sort"]([None]) is None
        assert m["array.sort_indices"]([None]) is None
        assert m["array.slice"]([None, 0, 1]) == []
        assert m["array.concat"]([None, [1]]) is None
        assert m["array.concat"]([[1], None]) is None
        assert m["array.every"]([None]) is None
        assert m["array.some"]([None]) is None
        assert m["array.join"]([None]) is None
        assert m["array.covariance"]([None, [1.0, 2.0]]) is None

    def test_slice_na_bounds_and_set_soft_index(self) -> None:
        m = _map()
        assert m["array.slice"]([[1, 2, 3], None, 2]) == []
        assert m["array.slice"]([[1, 2, 3], 0, None]) == []
        a = [1.0, 2.0]
        assert m["array.set"]([a, None, 9.0]) is a
        assert a == [1.0, 2.0]
        stub = SimpleNamespace(__pine_import_stub__=True)
        assert m["array.set"]([a, stub, 9.0]) is a

    def test_history_and_tuple_coercion(self) -> None:
        m = _map()
        hist_list = SimpleNamespace(history=[1, 2, 3])
        assert m["array.size"]([hist_list]) == 3
        hist_deq = SimpleNamespace(history=deque([3, 2, 1]))
        assert m["array.size"]([hist_deq]) == 3
        cur = SimpleNamespace(current=[9, 8])
        assert m["array.size"]([cur]) == 2
        assert m["array.size"]([(1, 2)]) == 2
        assert m["array.size"]([object()]) is None

    def test_index_soft_series_and_string(self) -> None:
        m = _map()
        series_idx = SimpleNamespace(current=1)
        assert m["array.get"]([[10, 20, 30], series_idx]) == 20
        assert m["array.get"]([[10, 20], "1"]) == 20
        assert m["array.get"]([[10], float("nan")]) is None
        with pytest.raises(ValueError):
            m["array.get"]([[10], [0]])

    def test_covariance_biased_and_length(self) -> None:
        m = _map()
        a = [1.0, 2.0, 3.0, 4.0]
        b = [2.0, 4.0, 6.0, 8.0]
        assert m["array.covariance"]([a, b, False]) == pytest.approx(3.333333, abs=1e-5)
        assert m["array.covariance"]([a, b, True]) == pytest.approx(2.5)
        assert m["array.covariance"]([a, b, 2]) == pytest.approx(0.5)
        assert m["array.covariance"]([a, b, 1]) is None
        assert m["array.covariance"]([[1.0], [1.0]]) is None

    def test_every_some_predicate_forms(self) -> None:
        m = _map()
        assert m["array.every"]([[1, 2, 3], lambda x: x > 0]) is True
        assert m["array.every"]([[1, 0, 3], lambda x: x > 0]) is False
        assert m["array.every"]([[1, 2], "not-callable"]) is True
        assert m["array.some"]([[0, 0, 1], lambda x: x > 0]) is True
        with pytest.raises(ValueError):
            m["array.some"]([[1], "not-callable"])

    def test_abs_na_slots_and_type_error(self) -> None:
        m = _map()
        assert m["array.abs"]([[-2.0, None, 3.0]]) == [2.0, None, 3.0]
        with pytest.raises(ValueError):
            m["array.abs"]([["x"]])

    def test_min_max_nth_edges(self) -> None:
        m = _map()
        assert m["array.min"]([[5.0, 1.0, 3.0], 0]) == 1.0
        assert m["array.min"]([[5.0, 1.0, 3.0], 2]) == 5.0
        assert m["array.min"]([[5.0], 5]) is None
        assert m["array.min"]([[5.0], -1]) is None
        assert m["array.max"]([[5.0, 1.0, 3.0], SimpleNamespace(current=1)]) == 3.0
        with pytest.raises(ValueError):
            m["array.max"]([[1.0], "bad"])

    def test_set_grow_and_negative_oob(self) -> None:
        m = _map()
        a: list = [1.0]
        m["array.set"]([a, 3, 9.0])
        assert a == [1.0, None, None, 9.0]
        b = [1.0, 2.0]
        m["array.set"]([b, -9, 0.0])
        assert b == [1.0, 2.0]
        series_val = SimpleNamespace(current=7.0, history=deque([7.0]))
        m["array.set"]([b, 0, series_val])
        assert b[0] == 7.0

    def test_sort_field_dict_udt_and_mixed(self) -> None:
        m = _map()
        rows = [
            {"__type__": "Pt", "v": 3.0},
            {"__type__": "Pt", "v": 1.0},
            None,
            {"__type__": "Pt", "v": 2.0},
        ]
        m["array.sort"]([rows, "ascending", "v"])
        assert [r["v"] if r else None for r in rows] == [1.0, 2.0, 3.0, None]
        idx = m["array.sort_indices"]([[{"__type__": "Pt", "v": 3}, {"__type__": "Pt", "v": 1}], None, "v"])
        assert idx == [1, 0]
        mixed = [1.0, "a", 2.0]
        m["array.sort"]([mixed])
        assert set(mixed[:2]) == {1.0, 2.0}

    def test_binary_search_with_na_and_field(self) -> None:
        m = _map()
        assert m["array.binary_search_leftmost"]([[1.0, None, 1.0, 2.0], 1.0]) == 0
        assert m["array.binary_search_rightmost"]([[1.0, None, 1.0, 2.0], 1.0]) == 2
        assert m["array.binary_search_leftmost"]([[1.0, None], None]) == 1
        rows = [
            {"__type__": "Pt", "v": 1.0},
            {"__type__": "Pt", "v": 2.0},
            {"__type__": "Pt", "v": 3.0},
        ]
        assert m["array.binary_search"]([rows, 2.0, "v"]) == 1
        assert m["array.binary_search"]([rows, 9.0, "v"]) == -1

    def test_percentrank_na_value_and_standardize(self) -> None:
        m = _map()
        assert m["array.percentrank"]([[1.0, 2.0], None]) is None
        assert m["array.percentrank"]([[1.0], 1.0]) == 0.0
        assert m["array.standardize"]([[1.0]]) is None
        assert m["array.standardize"]([[5.0, 5.0]]) is None
        st = m["array.standardize"]([[1.0, 2.0, 3.0, None]])
        assert st is not None and st[3] is None
        assert st[1] == pytest.approx(0.0)

    def test_join_non_string_sep_and_new_size_float(self) -> None:
        m = _map()
        assert m["array.join"]([[1, None, 2], 0]) == "1002"  # sep str(0)
        assert m["array.new_float"]([2.0, 1.5]) == [1.5, 1.5]
        assert m["array.new_float"](["bad"]) == []
        assert m["array.new"]([]) == []

    def test_percentile_all_na_soft(self) -> None:
        m = _map()
        assert m["array.percentile_linear_interpolation"]([[None, None], 50]) is None
        assert m["array.percentile_nearest_rank"]([[None], 50]) is None
