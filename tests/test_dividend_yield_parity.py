# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Focused interpret/compile parity for dividend_yield.pine.

Root causes covered:
- compile must not lower ``request.security(..., year_sum(close))`` as chart
  close cumsum (fake dividends)
- interpret must not invent chart-evaluated UDF results for foreign tickers
- ``last := time`` must not alias/corrupt the host ``time`` series
"""

from __future__ import annotations

from pathlib import Path

import math

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PINE = _ROOT / "tests" / "data" / "builtin_scripts" / "dividend_yield.pine"


def _bars(n: int = 200) -> list[dict]:
    bars: list[dict] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        lo = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "time": 1_700_000_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _is_na(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        return bool(math.isnan(float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


@pytest.mark.skipif(not _PINE.is_file(), reason="dividend_yield.pine missing")
def test_dividend_yield_interp_compile_all_na() -> None:
    """Without fundamental data both backends plot na (not close-as-dividend)."""
    from backend.runtime import Runtime

    src = _PINE.read_text(encoding="utf-8")
    bars = _bars(1000)
    rt = Runtime()
    si = rt.run(src, bars, mode="interpret")
    sc = rt.run(src, bars, mode="compile")
    assert not si.get("error"), si.get("error")
    assert not sc.get("error"), sc.get("error")
    pi = si["series"]["plot_0"]
    pc = sc["series"]["plot_0"]
    assert len(pi) == len(pc) == 1000
    assert all(_is_na(x) for x in pi)
    assert all(_is_na(x) for x in pc)


def test_foreign_security_udf_expression_is_na() -> None:
    """request.security on ESD_FACTSET with UDF expr → na on interpret."""
    from backend.runtime import Runtime

    src = """//@version=6
indicator("t")
year_sum(src) =>
	ta.cum(src)
div_ticker = ticker.new("ESD_FACTSET", "X;Y;DIVIDENDS")
div_ttm = request.security(div_ticker, "D", year_sum(close), barmerge.gaps_on, lookahead=barmerge.lookahead_on)
plot(div_ttm)
plot(close)
"""
    bars = _bars(20)
    si = Runtime().run(src, bars, mode="interpret")
    assert not si.get("error"), si.get("error")
    div = si["series"]["plot_0"]
    close = si["series"]["plot_1"]
    assert all(_is_na(x) for x in div)
    # close still real (not all na)
    assert any(not _is_na(x) for x in close)


def test_foreign_security_string_close_is_na_both_modes() -> None:
    """Foreign OHLCV string expr must not invent mock prices under host chart."""
    from backend.runtime import Runtime

    src = """//@version=6
indicator("t")
plot(request.security("UPVOL.NY", "D", "close"), title="up")
plot(request.security("DNVOL.NY", "D", close), title="dn")
"""
    bars = _bars(30)
    rt = Runtime(symbol="AAPL")
    si = rt.run(src, bars, mode="interpret")
    sc = rt.run(src, bars, mode="compile")
    assert not si.get("error"), si.get("error")
    assert not sc.get("error"), sc.get("error")
    for key in ("up", "dn"):
        assert all(_is_na(x) for x in si["series"][key]), key
        assert all(_is_na(x) for x in sc["series"][key]), key


def test_time_assign_does_not_alias_host_series() -> None:
    """``last := time`` must copy scalar; later updates must not corrupt time[1]."""
    from backend.runtime import Runtime

    src = """//@version=6
indicator("t")
float last_t = na
last_t := na(close) ? last_t[1] : time
plot(nz(time[1]), title="t1")
plot(time, title="t")
plot(last_t, title="lt")
"""
    bars = _bars(10)
    si = Runtime().run(src, bars, mode="interpret")
    assert not si.get("error"), si.get("error")
    t1 = si["series"]["t1"]
    t = si["series"]["t"]
    lt = si["series"]["lt"]
    assert t1[1] == bars[0]["time"]
    assert t1[2] == bars[1]["time"]
    assert t[2] == bars[2]["time"]
    assert lt[2] == bars[2]["time"]
    # After several bars, time[1] still tracks previous bar (not zeroed)
    assert t1[5] == bars[4]["time"]
