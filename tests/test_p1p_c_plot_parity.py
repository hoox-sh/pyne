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

"""P1p-C interpret/compile plot parity: strategy/request/pivot/plot collectors.

Covers:
- ``color.new`` transparency exported as interpret-style ``rgba(...)``
- ``time_close`` / ``time_close[1]`` vs interpret next-bar open
- ``syminfo.target_price_*`` is na (not compile 0.0)
- ``str.format('{0}', x)`` interpolates (open_interest runtime.error)
- HTF ``request.security`` UDF unpack is na (seasonality months-used)
- ``array.includes`` on a float/na handle does not TypeError
"""

from __future__ import annotations

import math

from pathlib import Path

from backend.runtime import Runtime
from pynescript.compiler.engine import transpile


_ROOT = Path(__file__).resolve().parents[1]
_BUILTIN = _ROOT / "tests" / "data" / "builtin_scripts"


def _bars(n: int = 40, *, t0: int = 1_000_000, step: int = 86_400_000) -> list[dict]:
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
                "time": t0 + i * step,
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


def _run_both(src: str, bars: list[dict], *, symbol: str = "PARITY") -> tuple[dict, dict]:
    rt = Runtime(symbol=symbol)
    si = rt.run(src, bars, mode="interpret")
    sc = rt.run(src, bars, mode="compile")
    assert not si.get("error"), si.get("error")
    assert not sc.get("error"), sc.get("error")
    return si, sc


def test_color_new_transp_bgcolor_rgba_both_hosts() -> None:
    """color.new(white, 95) must export interpret rgba alpha, not opaque #FFFFFF."""
    src = """//@version=6
indicator("bg")
bgcolor(color.new(color.white, 95))
plot(close, "c")
"""
    si, sc = _run_both(src, _bars(8))
    bi = si["series"]["bgcolor"][0]
    bc = sc["series"]["bgcolor"][0]
    assert isinstance(bi, str) and "rgba" in bi.lower(), bi
    assert bi == bc, (bi, bc)
    # 95% transp → a = int(255 * 0.05) = 12 → 12/255
    assert "0.047058823529411764" in bi


def test_time_close_matches_next_bar_open() -> None:
    """Compile time_close is next bar open; last bar is time + 86400000."""
    src = """//@version=6
indicator("tc")
plot(time_close, "tc")
plot(time_close[1], "tc1")
plot(time, "t")
"""
    bars = _bars(6)
    si, sc = _run_both(src, bars)
    for key in ("tc", "tc1", "t"):
        for i, (a, b) in enumerate(zip(si["series"][key], sc["series"][key], strict=True)):
            if _is_na(a) and _is_na(b):
                continue
            assert a == b, (key, i, a, b)
    # Non-last: time_close == next bar open
    assert si["series"]["tc"][0] == bars[1]["time"]
    assert si["series"]["tc"][-1] == bars[-1]["time"] + 86_400_000
    # History: time_close[1] at bar i is time_close of i-1 == time of bar i
    assert si["series"]["tc1"][2] == bars[2]["time"]


def test_target_price_syminfo_is_na_not_zero() -> None:
    """Missing analyst targets plot na on both hosts (never compile 0.0)."""
    src = """//@version=6
indicator("pt")
plot(syminfo.target_price_high, "Max")
plot(syminfo.target_price_average, "Avg")
plot(syminfo.target_price_low, "Min")
plot(syminfo.target_price_date, "Date")
"""
    si, sc = _run_both(src, _bars(12))
    for key in ("Max", "Avg", "Min", "Date"):
        assert all(_is_na(x) for x in si["series"][key]), key
        assert all(_is_na(x) for x in sc["series"][key]), (key, sc["series"][key][:3])


def test_str_format_interpolates_placeholder() -> None:
    src = """//@version=6
indicator("fmt")
s = str.format("No Open Interest data found for the `{0}` symbol.", syminfo.prefix + ":" + syminfo.ticker)
runtime.error(s)
plot(close)
"""
    bars = _bars(3)
    rt = Runtime(symbol="PARITY")
    si = rt.run(src, bars, mode="interpret")
    sc = rt.run(src, bars, mode="compile")
    assert si.get("error"), "interpret should runtime.error"
    assert sc.get("error"), "compile should runtime.error"
    ei = str(si["error"]).lower()
    ec = str(sc["error"]).lower()
    assert "{0}" not in ec
    assert ":parity" in ei
    assert ":parity" in ec


def test_htf_security_udf_unpack_is_na() -> None:
    """HTF request.security of a UDF tuple must not invent chart-eval 0s."""
    src = """//@version=6
indicator("sea")
calc() =>
    var matrix<float> m = matrix.new<float>(0, 13)
    [array.new<int>(), m]
[years, changes] = request.security(syminfo.tickerid, "1M", calc(), lookahead = barmerge.lookahead_on)
var float n = na
if timeframe.change("1M") and not na(changes)
    n := 0.0
plot(n, "No. of months used in the current average")
"""
    si, sc = _run_both(src, _bars(40))
    for host, out in (("interp", si), ("compile", sc)):
        vals = out["series"]["No. of months used in the current average"]
        assert all(_is_na(x) for x in vals), (host, vals[:5])


def test_array_includes_on_nan_handle_does_not_raise() -> None:
    src = """//@version=6
indicator("inc")
import TradingView/ValueAtTime/2 as VAT
var array<string> symbols = VAT.getArrayFromString("AAPL")
ok = not symbols.includes(syminfo.ticker)
plot(ok ? 1 : 0, "ok")
"""
    sc = Runtime(symbol="PARITY").run(src, _bars(5), mode="compile")
    assert not sc.get("error"), sc.get("error")


def test_transpile_time_close_uses_series_not_59999() -> None:
    code = transpile(
        """//@version=6
indicator("t")
plot(time_close)
"""
    )
    assert "59999" not in code
    assert "time_close_arr" in code
    assert "86400000" in code


def test_transpile_str_format_and_color_new() -> None:
    code = transpile(
        """//@version=6
indicator("t")
bgcolor(color.new(color.white, 95))
runtime.error(str.format("x {0}", syminfo.ticker))
plot(close)
"""
    )
    assert "pine_color_new" in code
    assert "pine_str_format" in code
    assert "chart_ticker()" in code


def test_ep_assign_high_does_not_alias_ohlcv_series() -> None:
    """``EP := high`` must snapshot the bar scalar (Parabolic SAR AF increment).

    Aliasing the live high series makes ``high > EP`` never true after the
    first assignment, so AF stays at 0.02 on interpret while compile steps.
    """
    src = """
//@version=6
indicator("sar_alias_p1p")
start = 0.02
increment = 0.02
maximum = 0.2
var bool uptrend = false
var float EP = na
var float SAR = na
var float AF = start
var float nextBarSAR = na
if bar_index > 0
    firstTrendBar = false
    SAR := nextBarSAR
    if bar_index == 1
        if close > close[1]
            uptrend := true
            EP := high
            prevSAR = low[1]
            prevEP = high
        else
            uptrend := false
            EP := low
            prevSAR = high[1]
            prevEP = low
        firstTrendBar := true
        SAR := prevSAR + start * (prevEP - prevSAR)
    if uptrend
        if SAR > low
            firstTrendBar := true
            uptrend := false
            SAR := math.max(EP, high)
            EP := low
            AF := start
    else
        if SAR < high
            firstTrendBar := true
            uptrend := true
            SAR := math.min(EP, low)
            EP := high
            AF := start
    if not firstTrendBar
        if uptrend
            if high > EP
                EP := high
                AF := math.min(AF + increment, maximum)
        else
            if low < EP
                EP := low
                AF := math.min(AF + increment, maximum)
    if uptrend
        SAR := math.min(SAR, low[1])
        if bar_index > 1
            SAR := math.min(SAR, low[2])
    else
        SAR := math.max(SAR, high[1])
        if bar_index > 1
            SAR := math.max(SAR, high[2])
    nextBarSAR := SAR + AF * (EP - SAR)
plot(SAR, "SAR")
plot(nextBarSAR, "N")
plot(AF, "AF")
"""
    si, sc = _run_both(src, _bars(12))
    for key in ("SAR", "N", "AF"):
        for i, (a, b) in enumerate(zip(si["series"][key], sc["series"][key], strict=True)):
            if _is_na(a) and _is_na(b):
                continue
            assert not _is_na(a) and not _is_na(b), (key, i, a, b)
            assert abs(float(a) - float(b)) < 1e-9, (key, i, a, b)
    # AF must step off 0.02 once high exceeds the stored EP
    assert any(abs(float(v) - 0.02) > 1e-12 for v in si["series"]["AF"] if not _is_na(v))
