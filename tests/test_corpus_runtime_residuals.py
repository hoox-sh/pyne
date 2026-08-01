# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit goldens for high-frequency corpus Runtime residual themes (C1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.runtime import Runtime
from pynescript.util.corpus_sanitize import sanitize_corpus_source

DATA = Path(__file__).resolve().parent / "data"


def _bars(n: int = 30) -> list[dict]:
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


class TestKwargNoneNotTrimmed:
    def test_array_push_value_na(self) -> None:
        src = """//@version=5
indicator("t")
a = array.new_float()
array.push(id=a, value=na)
plot(array.size(a))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_array_push_value_number(self) -> None:
        src = """//@version=5
indicator("t")
a = array.new_float()
array.push(id=a, value=1.5)
plot(array.get(a, 0))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 1.5) < 1e-9


class TestV4Tonumber:
    def test_bare_tonumber(self) -> None:
        src = """//@version=5
indicator("t")
plot(tonumber("12.5"))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 12.5) < 1e-9


class TestMathIsfinite:
    def test_isfinite(self) -> None:
        src = """//@version=5
indicator("t")
plot(math.isfinite(close) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1


class TestStrategyTradeFields:
    def test_entry_comment_registered(self) -> None:
        src = """//@version=5
strategy("t")
strategy.entry("L", strategy.long, comment="c1")
if bar_index > 3
    strategy.close("L")
c = strategy.closedtrades.entry_comment(0)
plot(str.length(c))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_opentrades_entry_id(self) -> None:
        src = """//@version=5
strategy("t")
strategy.entry("Long", strategy.long)
id = strategy.opentrades.entry_id(0)
plot(str.length(id))
"""
        r = Runtime().run(src, _bars(10), mode="interpret")
        assert "error" not in r, r.get("error")


class TestCorpusScripts:
    @pytest.mark.parametrize(
        "rel",
        [
            "set01/indicators/119_ind_session_input_parser.pine",
            "set01/libraries/005_lib_withglobalpass.pine",
            "set04/indicators/0739_ind_non_ascii_case_demo.pine",
            "set04/strategies/0140_str_strategy_closedtrades_entry_comment_example.pine",
            "set03/strategies/0267_str_strategy_opentrades_max_drawdown_example_1.pine",
        ],
    )
    def test_residual_scripts_ok(self, rel: str) -> None:
        path = DATA / rel
        if not path.exists():
            pytest.skip(f"missing {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(50), mode="interpret")
        assert "error" not in r, f"{rel}: {r.get('error')}"
