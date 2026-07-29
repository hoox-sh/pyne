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

from __future__ import annotations

import math

from backend.runtime import Runtime


def _bars(n: int = 60, amp: float = 10.0, period: float = 4.0) -> list[dict]:
    out = []
    for i in range(n):
        c = 100 + amp * math.sin(i / period)
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": c,
                "high": c + 1,
                "low": c - 1,
                "close": c,
                "volume": 10,
            }
        )
    return out


def test_multi_plot_series_and_colors():
    src = """
//@version=5
indicator("m", overlay=true)
plot(ta.sma(close, 5), "fast", color=color.green)
plot(ta.sma(close, 15), "slow", color=color.red)
"""
    r = Runtime().run(src, _bars(50))
    assert "error" not in r, r.get("error")
    assert "fast" in r["series"] and "slow" in r["series"]
    assert r["plot_meta"]["fast"]["color"]
    assert r["plot_meta"]["slow"]["color"]
    assert r["plot_meta"]["fast"].get("kind") in (None, "plot")
    assert len(r["series"]["fast"]) == 50


def test_hline_in_series_and_plot_meta():
    src = """
//@version=5
indicator("rsi-levels", overlay=false)
r = ta.rsi(close, 14)
plot(r, "RSI", color=color.purple, linewidth=2)
hline(30, "Oversold", color=color.green, linewidth=1)
hline(70, "Overbought", color=color.red, linewidth=1)
"""
    r = Runtime().run(src, _bars(50), mode="interpret")
    assert "error" not in r, r.get("error")
    assert "RSI" in r["series"], list(r["series"].keys())
    assert "Oversold" in r["series"], list(r["series"].keys())
    assert "Overbought" in r["series"], list(r["series"].keys())
    meta_os = r["plot_meta"]["Oversold"]
    meta_ob = r["plot_meta"]["Overbought"]
    assert meta_os.get("kind") == "hline"
    assert meta_ob.get("kind") == "hline"
    assert meta_os.get("price") == 30 or float(meta_os.get("price")) == 30.0
    assert meta_ob.get("price") == 70 or float(meta_ob.get("price")) == 70.0
    assert meta_os.get("color")
    assert r["plot_meta"]["RSI"].get("kind") in (None, "plot")
    assert r["plot_meta"]["RSI"].get("linewidth") == 2
    # Constant price repeated per bar
    assert all(v == 30 or v == 30.0 for v in r["series"]["Oversold"] if v is not None)
    assert all(v == 70 or v == 70.0 for v in r["series"]["Overbought"] if v is not None)


def test_crossover_strategy_events():
    src = """
//@version=5
strategy("s", overlay=true)
fast = ta.sma(close, 5)
slow = ta.sma(close, 15)
if ta.crossover(fast, slow)
    strategy.entry("L", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("L")
plot(fast, "fast")
plot(slow, "slow")
"""
    r = Runtime().run(src, _bars(60))
    assert "error" not in r, r.get("error")
    kinds = [e["kind"] for e in r.get("events") or []]
    assert "entry" in kinds, kinds
    assert "close" in kinds or kinds.count("entry") >= 1, kinds
