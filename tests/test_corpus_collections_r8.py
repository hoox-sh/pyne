# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Round 8 Agent 09 — C1 collection/string soft-na + real semantics goldens.

Prefer this file over editing ``test_corpus_runtime_residuals.py`` (Agent 12).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.runtime import Runtime


def _bars(n: int = 20) -> list[dict]:
    out: list[dict] = []
    price = 100.0
    for i in range(n):
        o = price
        c = price + (0.5 if i % 2 == 0 else -0.3)
        out.append(
            {
                "open": o,
                "high": max(o, c) + 0.5,
                "low": min(o, c) - 0.5,
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0,
            }
        )
        price = c
    return out


class TestArrayNegativeIndexRuntime:
    def test_get_set_remove_negative(self) -> None:
        src = """//@version=6
indicator("t")
a = array.from(1.0, 2.0, 3.0)
array.set(a, -1, 9.0)
plot(array.get(a, -1))
plot(array.remove(a, -2))
plot(array.size(a))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        assert abs(float(p0[-1]) - 9.0) < 1e-9


class TestStrMatchAndPosRuntime:
    def test_str_match_substring(self) -> None:
        src = """//@version=6
indicator("t")
s = "It's time to sell some NASDAQ:AAPL!"
t = str.match(s, "[\\\\w]+:[\\\\w]+")
plot(str.length(t))
plot(str.startswith(t, "NASDAQ") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        assert int(p0[-1]) == len("NASDAQ:AAPL")
        p1 = series.get("plot_1")
        if p1 is not None:
            assert int(p1[-1]) == 1

    def test_str_pos_source_first(self) -> None:
        src = """//@version=6
indicator("t")
plot(str.pos("abc", "b"))
plot(na(str.pos(na, "x")) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        assert int(p0[-1]) == 1

    def test_str_upper_na_soft(self) -> None:
        src = """//@version=6
indicator("t")
plot(na(str.upper(na)) ? 1 : 0)
plot(str.length(str.lower("AB")))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        assert int(p0[-1]) == 1


class TestMapMatrixSoftNaRuntime:
    def test_map_na_and_remove_return(self) -> None:
        src = """//@version=6
indicator("t")
m = map.new<string,float>()
map.put(m, "a", 1.5)
plot(map.remove(m, "a"))
plot(na(map.size(na)) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        assert abs(float(p0[-1]) - 1.5) < 1e-9

    def test_matrix_na_index_soft(self) -> None:
        src = """//@version=6
indicator("t")
m = matrix.new<float>(2, 2, 3.0)
matrix.set(m, na, 0, 9.0)
plot(nz(matrix.get(m, na, 0), -1))
plot(matrix.get(m, 0, 0))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p1 = series.get("plot_1")
        if p1 is not None:
            assert abs(float(p1[-1]) - 3.0) < 1e-9


class TestArraySoftNaRuntime:
    def test_array_stats_na_id(self) -> None:
        src = """//@version=6
indicator("t")
plot(na(array.avg(na)) ? 1 : 0)
plot(na(array.sum(na)) ? 1 : 0)
a = array.from(1.0, 2.0, 3.0)
plot(array.get(a, -1))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p2 = series.get("plot_2")
        if p2 is not None:
            assert abs(float(p2[-1]) - 3.0) < 1e-9


class TestIntentionalRuntimeErrorStillFails:
    """Do not soft-suppress library ``runtime.error`` validation demos."""

    @pytest.mark.parametrize(
        "rel",
        [
            "set02/libraries/019_lib_functionnnetwork.pine",
            "set02/libraries/021_lib_analysisinterpolationloess.pine",
            "set02/libraries/026_lib_mathcomplexoperator.pine",
            "set02/libraries/036_lib_mathcomplextrigonometry.pine",
        ],
    )
    def test_library_runtime_error_still_fails(self, rel: str) -> None:
        path = Path(__file__).resolve().parent / "data" / rel
        if not path.is_file():
            pytest.skip(f"missing {rel}")
        src = path.read_text(encoding="utf-8", errors="replace")
        r = Runtime().run(src, _bars(12), mode="interpret")
        err = r.get("error")
        assert err, f"expected RuntimeError for {rel}, got success"
        assert "RuntimeError" in str(err) or "runtime" in str(err).lower() or "error" in str(err).lower()
