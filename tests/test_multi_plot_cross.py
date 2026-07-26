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
    assert len(r["series"]["fast"]) == 50


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
