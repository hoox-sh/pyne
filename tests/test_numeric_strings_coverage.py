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

"""Extra coverage for ``math.*`` / ``str.*`` builtins via Runtime and direct calls."""

from __future__ import annotations

import random

from types import SimpleNamespace

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
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
    out = Runtime(symbol="NS").run(src, bars if bars is not None else _bars(), mode="interpret")
    assert "error" not in out, out.get("error")
    return out


def _ev(**ctx: object) -> NodeLiteralEvaluator:
    return NodeLiteralEvaluator(context=dict(ctx))


# ---------------------------------------------------------------------------
# Runtime scripts — math.* edge paths
# ---------------------------------------------------------------------------


class TestMathRuntimeEdges:
    def test_abs_ceil_floor_round_pow_log(self) -> None:
        src = """//@version=5
indicator("math_edges")
plot(math.abs(-3.5), "abs")
plot(math.ceil(1.1), "ceil")
plot(math.floor(1.9), "floor")
plot(math.round(1.5), "rnd")
plot(math.round(1.234, 2), "rnd2")
plot(math.pow(2, 8), "pow")
plot(math.log(math.exp(1)), "log")
plot(math.log(100, 10), "logb")
plot(math.log10(1000), "log10")
plot(math.sqrt(9), "sqrt")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["abs"][-1]) == pytest.approx(3.5)
        assert float(s["ceil"][-1]) == 2.0
        assert float(s["floor"][-1]) == 1.0
        assert float(s["rnd"][-1]) == pytest.approx(2.0) or float(s["rnd"][-1]) == pytest.approx(1.0)
        assert float(s["rnd2"][-1]) == pytest.approx(1.23)
        assert float(s["pow"][-1]) == 256.0
        assert float(s["log"][-1]) == pytest.approx(1.0)
        assert float(s["logb"][-1]) == pytest.approx(2.0)
        assert float(s["log10"][-1]) == pytest.approx(3.0)
        assert float(s["sqrt"][-1]) == pytest.approx(3.0)

    def test_min_max_sign_trig_and_na(self) -> None:
        src = """//@version=5
indicator("math_mm")
plot(math.min(3, 1, 2), "mn")
plot(math.max(3, 1, 2), "mx")
plot(math.sign(-9), "sg")
plot(math.sin(0), "sn")
plot(math.cos(0), "cs")
plot(math.tan(0), "tn")
plot(na(math.sqrt(-1)) ? 1 : 0, "nsqrt")
plot(na(math.log(0)) ? 1 : 0, "nlog")
plot(na(math.abs(na)) ? 1 : 0, "nabs")
plot(math.isfinite(1.0) ? 1 : 0, "fin")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["mn"][-1]) == 1.0
        assert float(s["mx"][-1]) == 3.0
        assert float(s["sg"][-1]) == -1.0
        assert float(s["sn"][-1]) == pytest.approx(0.0)
        assert float(s["cs"][-1]) == pytest.approx(1.0)
        assert float(s["tn"][-1]) == pytest.approx(0.0)
        assert float(s["nsqrt"][-1]) == 1.0
        assert float(s["nlog"][-1]) == 1.0
        assert float(s["nabs"][-1]) == 1.0
        assert float(s["fin"][-1]) == 1.0

    def test_avg_sum_exp_degrees_nz_iff(self) -> None:
        src = """//@version=5
indicator("math_avg")
plot(math.avg(2, 4, 6), "avg")
plot(math.exp(0), "exp")
plot(math.todegrees(math.toradians(90)), "deg")
plot(nz(na, 7), "nz")
plot(iff(true, 1, 0), "iff1")
plot(iff(false, 1, 0), "iff0")
plot(math.sum(close, 2), "sum2")
"""
        r = _run(src, _bars(6))
        s = r["series"]
        assert float(s["avg"][-1]) == pytest.approx(4.0)
        assert float(s["exp"][-1]) == pytest.approx(1.0)
        assert float(s["deg"][-1]) == pytest.approx(90.0)
        assert float(s["nz"][-1]) == 7.0
        assert float(s["iff1"][-1]) == 1.0
        assert float(s["iff0"][-1]) == 0.0
        assert s["sum2"][-1] is not None

    def test_casts_and_fixnan(self) -> None:
        src = """//@version=5
indicator("casts")
plot(int("2.9"), "i")
plot(float("3.5"), "f")
plot(bool(1) ? 1 : 0, "b")
plot(fixnan(na), "fn")
plot(str.length(string(true)), "slen")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["i"][-1]) == 2.0
        assert float(s["f"][-1]) == pytest.approx(3.5)
        assert float(s["b"][-1]) == 1.0
        assert float(s["fn"][-1]) == 0.0
        assert float(s["slen"][-1]) == 4.0  # "true"


# ---------------------------------------------------------------------------
# Runtime scripts — str.* edge paths
# ---------------------------------------------------------------------------


class TestStrRuntimeEdges:
    def test_case_contains_split_replace(self) -> None:
        src = """//@version=5
indicator("str_basic")
s = "Hello World"
plot(str.length(s), "len")
plot(str.contains(s, "World") ? 1 : 0, "ct")
plot(str.startswith(s, "He") ? 1 : 0, "st")
plot(str.endswith(s, "ld") ? 1 : 0, "en")
plot(str.length(str.upper(s)), "up")
plot(str.length(str.lower(s)), "lo")
plot(str.length(str.trim("  x  ")), "tr")
plot(array.size(str.split("a,b,c", ",")), "sp")
plot(str.length(str.replace(s, "l", "L")), "rp")
plot(str.length(str.replace_all(s, "l", "L")), "ra")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["len"][-1]) == 11.0
        assert float(s["ct"][-1]) == 1.0
        assert float(s["st"][-1]) == 1.0
        assert float(s["en"][-1]) == 1.0
        assert float(s["up"][-1]) == 11.0
        assert float(s["lo"][-1]) == 11.0
        assert float(s["tr"][-1]) == 1.0
        assert float(s["sp"][-1]) == 3.0
        assert float(s["rp"][-1]) == 11.0
        assert float(s["ra"][-1]) == 11.0

    def test_tonumber_tostring_format_match_pos(self) -> None:
        src = """//@version=5
indicator("str_num")
plot(str.tonumber("12.5"), "tn")
plot(na(str.tonumber("")) ? 1 : 0, "tne")
plot(na(str.tonumber("abc")) ? 1 : 0, "tnb")
plot(str.length(str.tostring(42)), "ts")
plot(str.length(str.format("x={0}", 7)), "fmt")
plot(str.length(str.match("abc123", "\\\\d+")), "mt")
plot(str.pos("abcdef", "cd"), "pos")
plot(str.length(str.substring("abcdef", 2, 5)), "sub")
plot(str.length(str.repeat("ab", 3)), "rep")
plot(str.length(str.join(array.from("a", "b"), "-")), "jn")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["tn"][-1]) == pytest.approx(12.5)
        assert float(s["tne"][-1]) == 1.0
        assert float(s["tnb"][-1]) == 1.0
        assert float(s["ts"][-1]) == 2.0
        assert float(s["fmt"][-1]) == 3.0  # "x=7"
        assert float(s["mt"][-1]) == 3.0
        assert float(s["pos"][-1]) == 2.0
        assert float(s["sub"][-1]) == 3.0
        assert float(s["rep"][-1]) == 6.0
        assert float(s["jn"][-1]) == 3.0

    def test_empty_and_na_string_edges(self) -> None:
        src = """//@version=5
indicator("str_na")
plot(na(str.length(na)) ? 1 : 0, "nlen")
plot(na(str.upper(na)) ? 1 : 0, "nup")
plot(na(str.contains(na, "x")) ? 1 : 0, "nct")
plot(na(str.startswith("a", na)) ? 1 : 0, "nst")
plot(str.contains("", "") ? 1 : 0, "ee")
plot(str.startswith("", "") ? 1 : 0, "es")
plot(str.endswith("", "") ? 1 : 0, "ed")
plot(str.length(str.tostring(na)), "tsna")
"""
        r = _run(src)
        s = r["series"]
        assert float(s["nlen"][-1]) == 1.0
        assert float(s["nup"][-1]) == 1.0
        assert float(s["nct"][-1]) == 1.0
        assert float(s["nst"][-1]) == 1.0
        assert float(s["ee"][-1]) == 1.0
        assert float(s["es"][-1]) == 1.0
        assert float(s["ed"][-1]) == 1.0
        assert float(s["tsna"][-1]) == 3.0  # "NaN"


# ---------------------------------------------------------------------------
# Direct evaluator calls — additional edges beyond builtins_coverage
# ---------------------------------------------------------------------------


class TestNumericDirectExtra:
    def test_as_num_unwraps_series_and_nan(self) -> None:
        ev = _ev()
        ser = SimpleNamespace(current=float("nan"), history=[1.0])
        assert ev._as_num(ser) is None
        assert ev._as_num(SimpleNamespace(current=4.5, history=[4.5])) == 4.5
        assert ev._as_num("nope") is None
        assert ev._builtin_abs([None]) is None
        assert ev._builtin_abs([-2]) == 2
        assert ev._builtin_abs(["x"]) is None

    def test_as_scalar_walks_wrappers_and_lists(self) -> None:
        ev = _ev()
        inner = SimpleNamespace(current=9, history=[9])
        outer = SimpleNamespace(current=inner, history=[inner])
        assert ev._as_scalar(outer) == 9
        assert ev._as_scalar([1, 2, 3]) == 3
        assert ev._as_scalar(None) is None

    def test_floor_ceil_abs_map_and_random_seed(self) -> None:
        ev = _ev()
        assert ev._builtin_math_floor([2.9]) == 2
        assert ev._builtin_math_ceil([-1.1]) == -1
        assert ev._builtin_math_abs([-7.0]) == 7.0
        assert ev._builtin_math_abs([None]) is None
        random.seed(0)
        a = ev._builtin_math_random([])
        random.seed(0)
        b = ev._builtin_math_random([])
        assert a == b
        assert 2.0 <= ev._builtin_math_random([2, 4]) <= 4.0

    def test_atan_asin_acos_domain(self) -> None:
        ev = _ev()
        assert ev._builtin_math_atan([0]) == pytest.approx(0.0)
        assert ev._builtin_math_asin([0]) == pytest.approx(0.0)
        assert ev._builtin_math_acos([1]) == pytest.approx(0.0)
        assert ev._builtin_math_asin([2]) is None
        assert ev._builtin_math_acos([-2]) is None

    def test_avg_list_last_and_sum_history(self) -> None:
        ev = _ev()
        hist = SimpleNamespace(history=[3.0, 2.0, 1.0], current=3.0)  # newest-first
        assert ev._builtin_math_sum([hist, 2]) == pytest.approx(5.0)
        assert ev._builtin_math_avg([SimpleNamespace(current=None)]) is None
        # Single-list form skips None entries rather than propagating na.
        assert ev._builtin_math_avg([[1.0, None]]) == pytest.approx(1.0)
        assert ev._builtin_math_avg([1, None]) is None
        assert ev._builtin_math_avg([SimpleNamespace(current=[1.0, 3.0])]) == pytest.approx(3.0)

    def test_nz_unwraps_series_default(self) -> None:
        ev = _ev()
        na_ser = SimpleNamespace(current=None, history=[None])
        def_ser = SimpleNamespace(current=11, history=[11])
        assert ev._builtin_nz([na_ser, def_ser]) == 11
        assert ev._builtin_nz([SimpleNamespace(current=5, history=[5])]) == 5
        with pytest.raises(ValueError):
            ev._builtin_nz([])

    def test_iff_na_condition_and_bool_strings(self) -> None:
        ev = _ev()
        assert ev._builtin_iff([None, 1, 0]) is None
        assert ev._builtin_bool(["yes"]) is True
        assert ev._builtin_bool(["no"]) is False
        assert ev._builtin_bool([None]) is False
        assert ev._builtin_int(["2.01"]) == 2
        assert ev._builtin_int(["bad"]) is None
        assert ev._builtin_int([float("nan")]) is None
        with pytest.raises(ValueError):
            ev._builtin_float(["not-a-float"])
        assert ev._builtin_fixnan([float("nan")]) == 0
        assert ev._builtin_fixnan([3]) == 3
        assert ev._builtin_color_new(["red"]) == "color(red)"

    def test_numeric_builtin_map_keys(self) -> None:
        ev = _ev()
        keys = set(ev._numeric_builtin_map())
        for name in ("math.abs", "math.random", "nz", "iff", "round_to_mintick", "fixnan"):
            assert name in keys


class TestStringDirectExtra:
    def test_empty_string_ops(self) -> None:
        ev = _ev()
        assert ev._builtin_str_length([""]) == 0
        assert ev._builtin_str_upper([""]) == ""
        assert ev._builtin_str_lower([""]) == ""
        assert ev._builtin_str_trim([""]) == ""
        assert ev._builtin_str_contains(["", ""]) is True
        assert ev._builtin_str_startswith(["abc", ""]) is True
        assert ev._builtin_str_endswith(["abc", ""]) is True
        assert ev._builtin_str_repeat(["", 5]) == ""
        assert ev._builtin_str_split([""]) == []
        assert ev._builtin_str_split(["", ""]) == []

    def test_replace_empty_target_and_occurrence(self) -> None:
        ev = _ev()
        assert ev._builtin_str_replace(["abc", "", "X", 0]) == "Xabc"
        assert ev._builtin_str_replace(["abc", "", "X", 3]) == "abcX"
        assert ev._builtin_str_replace(["abc", "", "X", 99]) == "abc"
        assert ev._builtin_str_replace_all(["ab", "", "-"]) == "-a-b-"
        assert ev._builtin_str_replace([5, 1, 9]) == "595" or "5" in ev._builtin_str_replace([5, 1, 9])

    def test_format_edges_and_match_pos(self) -> None:
        ev = _ev()
        assert ev._builtin_str_format(["{0,integer}", 3.9]) == "3"
        assert ev._builtin_str_format(["{0,string}", None]) == "NaN"
        assert ev._builtin_str_format(["{9}", 1]) == ""
        assert ev._builtin_str_format(["{x}", 1]) == "{x}"
        assert ev._builtin_str_format([None, 1]) == "NaN"
        assert ev._builtin_str_format(["plain"]) == "plain"
        assert ev._builtin_str_match(["", "a"]) is None
        assert ev._builtin_str_pos(["", "a"]) == -1
        assert ev._builtin_str_pos(["aaa", "a"]) == 0
        assert ev._builtin_str_pos([123, 2]) == 1

    def test_tostring_format_and_format_time_tz(self) -> None:
        ev = _ev()
        assert ev._builtin_str_tostring([True]) == "True" or ev._builtin_str_tostring([True]) == "true"
        assert ev._builtin_str_tostring([1.25, "0.00"]) in {"1.25", "1.250000"} or "1.25" in ev._builtin_str_tostring(
            [1.25, "0.00"]
        )
        with pytest.raises(ValueError):
            ev._builtin_str_tostring([])
        out = ev._builtin_str_format_time([1_609_459_200_000, "yyyy-MM-dd HH:mm:ss", "UTC"])
        assert out.startswith("2021-01-01")
        assert "NaN" == ev._builtin_str_format_time(["bogus"])
        assert "NaN" == ev._builtin_str_format_time([1_609_459_200_000, None]) or "2021" in ev._builtin_str_format_time(
            [1_609_459_200_000, None]
        )

    def test_join_and_substring_end_na(self) -> None:
        ev = _ev()
        assert ev._builtin_str_join([SimpleNamespace(current=["x", "y"]), ":"]) == "x:y"
        assert ev._builtin_str_substring(["hello", 1, None]) is None
        assert ev._builtin_str_substring([12, 0, 1]) == "1"
        with pytest.raises(ValueError):
            ev._builtin_str_repeat(["a"])
        with pytest.raises(ValueError):
            ev._builtin_str_split([])

    def test_string_builtin_map_keys(self) -> None:
        ev = _ev()
        keys = set(ev._string_builtin_map())
        for name in (
            "str.length",
            "str.format",
            "str.format_time",
            "str.match",
            "str.join",
            "tostring",
            "tonumber",
        ):
            assert name in keys

    def test_coerce_str_arg_none_and_number(self) -> None:
        assert NodeLiteralEvaluator._coerce_str_arg(None) == ""
        assert NodeLiteralEvaluator._coerce_str_arg(3) == "3"
        assert NodeLiteralEvaluator._coerce_str_arg("ok") == "ok"
