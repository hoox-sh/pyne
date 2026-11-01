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

"""request.* uses injected data_feed (MockDataFeed sync helpers).

Also covers foreign-na policy under a host chart and same-symbol simple
OHLCV vs complex HTF UDF (MTF structure residual).
"""

from __future__ import annotations

import itertools
import math

from datetime import datetime
from datetime import timezone

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse
from pynescript.util.datafeed import MockDataFeed


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


def _bars(n: int = 80, start: float = 100.0, step_ms: int = 60_000) -> list[dict]:
    """Synthetic OHLCV. Default *step_ms* is 1 minute (Runtime bar times)."""
    bars: list[dict] = []
    price = start
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
                "time": 1_700_000_000_000 + i * int(step_ms),
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _hourly_bars(n: int = 72, start: float = 100.0) -> list[dict]:
    """Hourly synthetic bars (for daily HTF resample tests)."""
    return _bars(n, start=start, step_ms=3_600_000)


def _daily_bars(n: int = 40, start: float = 100.0) -> list[dict]:
    """Daily synthetic bars (matches Runtime default timeframe.period ``D``)."""
    return _bars(n, start=start, step_ms=86_400_000)


def _expect_pivot_confirm(src: list[float], left: int, right: int, *, is_high: bool) -> float | None:
    """Last-sample ``ta.pivothigh`` / ``ta.pivotlow`` on a chronological unique series."""
    need = left + right + 1
    if len(src) < need:
        return None
    center_i = len(src) - 1 - right
    val = src[center_i]
    lo = center_i - left
    hi = center_i + right
    for j in range(lo, hi + 1):
        if j == center_i:
            continue
        other = src[j]
        left_side = j < center_i
        if is_high:
            if (other > val) if left_side else (other >= val):
                return None
        elif (other < val) if left_side else (other <= val):
            return None
    return val


def _is_na(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        return bool(math.isnan(float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


class TestRequestDataFeed:
    def test_security_uses_mock_feed_ohlcv(self) -> None:
        feed = MockDataFeed(symbol="BTC/USDT", start_price=30_000.0)
        ev = NodeLiteralEvaluator(data_feed=feed)
        result = _eval(ev, 'request.security("BTC/USDT", "1m", "close")')
        # Returns a price-like series or value derived from feed closes (~30000)
        if isinstance(result, list):
            assert all(abs(float(x) - 30_000.0) < 500 for x in result)
        else:
            assert abs(float(result) - 30_000.0) < 500

    def test_currency_rate_prefers_feed_pair(self) -> None:
        feed = MockDataFeed(symbol="EUR/USD", start_price=1.12)
        ev = NodeLiteralEvaluator(data_feed=feed)
        rate = _eval(ev, 'request.currency_rate("EUR", "USD")')
        assert abs(float(rate) - 1.12) < 0.01

    def test_dividends_is_na_without_fundamentals_hook(self) -> None:
        feed = MockDataFeed(symbol="AAPL", start_price=200.0)
        ev = NodeLiteralEvaluator(data_feed=feed)
        # No fetch_fundamental hook on the feed → honest na, not a mock value
        assert _eval(ev, 'request.dividends("AAPL")') is None

    def test_request_seed_stored_in_context(self) -> None:
        ev = NodeLiteralEvaluator()
        _eval(ev, "request.seed(42)")
        assert ev.context.get("request.seed") == 42


class TestForeignSecurityNaPolicy:
    """Under a host chart, foreign tickers without multi-symbol data → na."""

    def test_foreign_string_close_is_na_with_host_chart(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=6
indicator("t")
plot(request.security("UPVOL.NY", "D", "close"), title="up")
plot(request.security("MSFT", "D", close), title="ms")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, _bars(40), mode="interpret")
        assert not out.get("error"), out.get("error")
        assert all(_is_na(x) for x in out["series"]["up"])
        assert all(_is_na(x) for x in out["series"]["ms"])
        assert any(not _is_na(x) for x in out["series"]["c"])

    def test_standalone_eval_still_mocks_bare_equity_string(self) -> None:
        """No host chart identity → legacy mock prices for offline demos."""
        ev = NodeLiteralEvaluator()
        result = _eval(ev, 'request.security("AAPL", "D", "close")')
        assert isinstance(result, list)
        assert all(not _is_na(x) for x in result)


class TestSameSymbolSecurityPolicy:
    """Same-symbol simple OHLCV may passthrough/resample; complex HTF → na."""

    def test_same_symbol_htf_close_resamples_60m_on_1m_bars(self) -> None:
        """1m chart bars + request ``\"60\"`` → last completed 60m close (not chart close)."""
        from backend.runtime import Runtime

        # Align open times to 60m buckets so each hour is exactly 60 bars.
        hour0 = 1_700_000_000_000
        hour0 -= hour0 % 3_600_000
        bars: list[dict] = []
        price = 100.0
        for i in range(180):  # 3 full hours
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
                    "time": hour0 + i * 60_000,
                    "volume": 1000.0 + i,
                }
            )
            price = c

        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", close), title="sec")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        # First hour has no completed HTF bar → na (bar 0 may still be stub
        # before bar spacing is inferable; allow either na or chart on bar 0).
        assert all(_is_na(x) for x in sec[1:60])
        # After first hour completes, security is constant within the next hour
        # (lookahead_off / last completed only).
        hour0_close = float(bars[59]["close"])
        for v in sec[60:120]:
            assert not _is_na(v)
            assert abs(float(v) - hour0_close) < 1e-9
        hour1_close = float(bars[119]["close"])
        for v in sec[120:180]:
            assert not _is_na(v)
            assert abs(float(v) - hour1_close) < 1e-9
        # Not chart passthrough on the last bar (inside forming hour 3)
        assert abs(float(sec[-1]) - float(bars[-1]["close"])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_ohlcv_resample" in (pol.get("policies") or {})

    def test_same_symbol_hourly_to_daily_close_steps(self) -> None:
        """Hourly bars → daily close is constant within each day (last completed day)."""
        from backend.runtime import Runtime

        # Align to UTC day boundary so bucket math is stable.
        day0 = 1_700_000_000_000
        day0 -= day0 % 86_400_000
        bars: list[dict] = []
        price = 100.0
        # 3 full days * 24 hours + 6 hours into day 4
        for i in range(24 * 3 + 6):
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
                    "time": day0 + i * 3_600_000,
                    "volume": 1000.0 + i,
                }
            )
            price = c

        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", close), title="dclose")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        dclose = out["series"]["dclose"]
        # Day 0 incomplete for security → na on first 24 hours (bar 0 may stub).
        assert all(_is_na(x) for x in dclose[1:24])
        day0_close = float(bars[23]["close"])
        for v in dclose[24:48]:
            assert abs(float(v) - day0_close) < 1e-9
        day1_close = float(bars[47]["close"])
        for v in dclose[48:72]:
            assert abs(float(v) - day1_close) < 1e-9
        day2_close = float(bars[71]["close"])
        for v in dclose[72:]:
            assert abs(float(v) - day2_close) < 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_ohlcv_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_same_symbol_htf_high1_passthrough(self) -> None:
        """``high[1]`` resamples the previous HTF bar, not the previous LTF high."""
        from backend.runtime import Runtime

        bars = _hour_bars()
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", high[1]), title="h")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hour0_high = max(float(b["high"]) for b in bars[0:60])
        assert abs(float(out["series"]["h"][-1]) - hour0_high) < 1e-9

    def test_same_symbol_complex_htf_udf_is_na(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=6
indicator("t")
f_struct(len) =>
    hh = ta.highest(high, len)
    ll = ta.lowest(low, len)
    hhUp = hh > hh[len]
    llUp = ll > ll[len]
    hhUp and llUp ? 1 : not hhUp and not llUp ? -1 : 0
s_htf = request.security(syminfo.tickerid, "60", f_struct(20))
s_same = request.security(syminfo.tickerid, "D", f_struct(20))
plot(s_htf, title="htf")
plot(s_same, title="same")
plot(f_struct(20), title="chart")
"""
        # Daily-spaced bars so request "D" is same-TF for the UDF allow path.
        out = Runtime(symbol="AAPL").run(src, _daily_bars(80), mode="interpret")
        assert not out.get("error"), out.get("error")
        # Different TF + UDF without multi-TF engine → honest na
        assert all(_is_na(x) for x in out["series"]["htf"])
        # Same TF as default chart period ("D") → chart eval allowed
        assert out["series"]["same"][-1] == out["series"]["chart"][-1]

    def test_empty_symbol_ohlcvt_tuple_different_tf_passthrough(self) -> None:
        """``request.security('', input.timeframe('1'), [o,h,l,c,v,time])`` keeps list shape.

        Perceptron corpus: empty symbol = chart; TF may differ from chart period.
        Including ``time`` must not mark the tuple "complex" and collapse to a
        single ``na`` (which poisons High/Low/Close and custom dmi).
        """
        from backend.runtime import Runtime

        # 1m request on 1m bars → not coarser HTF; chart field passthrough.
        bars = _bars(40)
        src = """//@version=5
indicator("t")
Timeframe = input.timeframe("1", "Time Frame")
[Open, High, Low, Close, Volume, Time] = request.security("", Timeframe, [open, high, low, close, volume, time])
plot(High, title="High")
plot(Low, title="Low")
plot(Close, title="Close")
plot(Time, title="Time")
plot(Volume, title="Volume")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert abs(float(out["series"]["High"][-1]) - float(bars[-1]["high"])) < 1e-9
        assert abs(float(out["series"]["Low"][-1]) - float(bars[-1]["low"])) < 1e-9
        assert abs(float(out["series"]["Close"][-1]) - float(bars[-1]["close"])) < 1e-9
        assert abs(float(out["series"]["Volume"][-1]) - float(bars[-1]["volume"])) < 1e-9
        assert abs(float(out["series"]["Time"][-1]) - float(bars[-1]["time"])) < 1e-9
        # Not all-na
        assert any(not _is_na(x) for x in out["series"]["High"])

    def test_mtf_structure_bias_interp_compile_score_parity(self) -> None:
        from pathlib import Path

        from backend.runtime import Runtime

        pine = (
            Path(__file__).resolve().parents[1]
            / "tests"
            / "data"
            / "set02"
            / "indicators"
            / "156_ind_mtf_structure_bias.pine"
        )
        if not pine.is_file():
            import pytest

            pytest.skip("MTF corpus script missing")
        src = pine.read_text(encoding="utf-8")
        bars = _bars(200)
        rt = Runtime(symbol="AAPL")
        si = rt.run(src, bars, mode="interpret")
        sc = rt.run(src, bars, mode="compile")
        assert not si.get("error"), si.get("error")
        assert not sc.get("error"), sc.get("error")
        pi = si["series"]["Structure Score"]
        pc = sc["series"]["Structure Score"]
        assert len(pi) == len(pc) == 200
        # Without multi-TF data both backends leave HTF terms na → all-na score
        assert all(_is_na(x) for x in pi)
        assert all(_is_na(x) for x in pc)


def _aligned_1m_bars(n: int = 600, start: float = 100.0) -> list[dict]:
    """1m bars aligned to 60m buckets (for HTF simple-ta tests)."""
    hour0 = 1_700_000_000_000
    hour0 -= hour0 % 3_600_000
    bars: list[dict] = []
    price = start
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
                "time": hour0 + i * 60_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


class TestHtfSimpleTaResample:
    """Allowlisted ta.sma/ema/rsi/atr/wma/rma/cmo/stdev/linreg/cci/roc/mom/hma/vwma/dema/tema/highest/lowest/range/median/dev/variance/mode/percentrank/change/cog/highestbars/lowestbars/kama/rising/falling + 1-arg wpr/highest/lowest/highestbars/lowestbars on HTF."""

    def test_htf_sma_finite_after_warmup_and_stepwise_constant(self) -> None:
        """1m chart + request 60m sma(close, 3) → finite after 3 HTF bars; flat in bucket."""
        from backend.runtime import Runtime

        # 10 hours of 1m bars → 9 completed hours available late in the series.
        bars = _aligned_1m_bars(10 * 60)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", ta.sma(close, 3)), title="hsma")
plot(ta.sma(close, 3), title="csma")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hsma = out["series"]["hsma"]
        csma = out["series"]["csma"]
        # First hour incomplete → na (bar 0 may stub); need 3 completed HTF bars
        # for SMA(3) → finite from the start of the 4th hour (bar index 180).
        assert all(_is_na(x) for x in hsma[1:60])
        # After warmup: finite and constant within each hour bucket.
        warm = 3 * 60  # 3 completed HTF bars available from chart bar 180
        assert warm < len(hsma)
        finite_tail = [x for x in hsma[warm:] if not _is_na(x)]
        assert len(finite_tail) > 60
        for v in finite_tail:
            assert math.isfinite(float(v))
        # Stepwise constancy: within hour 5 (bars 300-359) last completed is hour 4;
        # value should not change mid-hour.
        hour5 = hsma[5 * 60 : 6 * 60]
        assert all(not _is_na(x) for x in hour5)
        ref = float(hour5[0])
        for v in hour5:
            assert abs(float(v) - ref) < 1e-9
        # Not chart-TF SMA passthrough (different series after HTF aggregation).
        assert abs(float(hsma[-1]) - float(csma[-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_ema_and_rsi_finite_policy(self) -> None:
        from backend.runtime import Runtime

        bars = _aligned_1m_bars(12 * 60)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", ta.ema(close, 5)), title="hema")
plot(request.security(syminfo.tickerid, "60", ta.rsi(close, 5)), title="hrsi")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hema = out["series"]["hema"]
        hrsi = out["series"]["hrsi"]
        # Warmup: 5 HTF bars for EMA seed → finite later in series.
        assert any(not _is_na(x) for x in hema[5 * 60 :])
        assert any(not _is_na(x) for x in hrsi[6 * 60 :])
        assert math.isfinite(float([x for x in hema if not _is_na(x)][-1]))
        rsi_last = float([x for x in hrsi if not _is_na(x)][-1])
        assert math.isfinite(rsi_last)
        assert 0.0 <= rsi_last <= 100.0
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})

    def test_htf_atr_finite_after_warmup(self) -> None:
        from backend.runtime import Runtime

        bars = _aligned_1m_bars(12 * 60)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", ta.atr(3)), title="hatr")
plot(ta.atr(3), title="catr")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hatr = out["series"]["hatr"]
        catr = out["series"]["catr"]
        finite = [x for x in hatr[4 * 60 :] if not _is_na(x)]
        assert len(finite) > 0
        assert math.isfinite(float(finite[-1]))
        assert float(finite[-1]) > 0.0
        # Differ from chart ATR once HTF bars exist.
        if not _is_na(hatr[-1]) and not _is_na(catr[-1]):
            assert abs(float(hatr[-1]) - float(catr[-1])) > 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})

    def test_nested_ta_still_complex_htf_na(self) -> None:
        """Nested / 4-arg cci never use htf_simple_ta_resample.

        Chart pre-eval of nested SMA can occasionally equal an OHLCV sample and
        hit the pre-existing passthrough heuristic — that is not the simple-ta
        HTF path. Nested ``ta.sma(ta.ema(...))``, 4-arg ``ta.cci``, and 4-arg
        ``ta.wpr`` stay na; 2-arg ``ta.cci(close, n)`` / 1-arg ``ta.cci(n)`` /
        ``ta.hma`` / ``ta.vwma`` / ``ta.dema`` / ``ta.tema`` / 1-arg ``ta.wpr(n)`` /
        ``ta.highest`` / ``ta.lowest`` (2-arg and 1-arg) / ``ta.range``
        (2-arg and 1-arg high-low) / ``ta.median`` / ``ta.dev`` / ``ta.variance`` /
        ``ta.mode`` / ``ta.percentrank`` / ``ta.change`` / ``ta.cog`` /
        ``ta.highestbars`` / ``ta.lowestbars`` (2-arg and 1-arg) / 2-arg
        ``ta.kama`` / ``ta.rising`` / ``ta.falling`` / ``ta.swma`` / ``ta.ao()`` /
        1-arg ``ta.ao(fast)`` / 2-arg ``ta.ao(fast, slow)`` /
        3-arg ``ta.linreg(source, n, offset)`` /
        0-arg ``ta.vwap()`` / 1-arg ``ta.vwap(source)`` / 1-arg ``ta.cum(source)`` /
        1-arg ``ta.change(source)`` (length 1) / 1-arg ``ta.adx(n)`` /
        1-arg ``ta.mfi(n)`` / 0-arg ``ta.obv()`` / 1-arg ``ta.cmf(n)`` /
        0-arg ``ta.nvi()`` / 0-arg ``ta.pvi()`` / 0-arg ``ta.accdist()`` /
        0-arg ``ta.wad()`` / 0-arg ``ta.tr()`` / 2-arg ``ta.tsi(short, long)`` /
        2-arg ``ta.bbw(n, mult)`` / 3-arg ``ta.bbw(source, n, mult)`` /
        1-arg ``ta.stoch(n)`` / 2-arg ``ta.stoch(k, d)`` (%K) /
        2-arg ``ta.pivothigh(left, right)`` / ``ta.pivotlow(left, right)`` /
        3-arg ``ta.percentile_nearest_rank(source, n, percentage)`` /
        3-arg ``ta.percentile_linear_interpolation(source, n, percentage)`` /
        1-arg ``ta.dpo(n)`` / 2-arg ``ta.dpo(source, n)`` / 2-arg
        ``ta.crossover`` / ``ta.crossunder`` / ``ta.cross`` of
        OHLCV names / 3-arg ``ta.correlation`` of two OHLCV names /
        0-arg ``ta.vpt()`` / ``ta.pvt()`` / 1-arg ``ta.wvad(n)`` /
        3-arg ``ta.uo(n1, n2, n3)`` / 3-arg ``ta.apo(source, fast, slow)`` /
        1-arg ``ta.emv(n)``
        are allowlisted. 2-arg / 3-arg ``ta.vwap``, 2-arg ``ta.adx``, 2-arg
        ``ta.obv``, 2-arg ``ta.nvi`` / ``ta.pvi``, 5-arg ``ta.cmf``, 4-arg
        ``ta.accdist`` / ``ta.wad``, 3-arg ``ta.tr(high, low, close)`` /
        3-arg ``ta.tsi(source, short, long)``, nested ``ta.bbw``, 1-arg
        ``ta.bbw``, 4-arg ``ta.stoch(source, high, low, length)``, nested
        ``ta.pivothigh`` / ``ta.pivotlow``, nested
        ``ta.percentile_nearest_rank`` / ``ta.percentile_linear_interpolation``,
        nested ``ta.dpo``, nested ``ta.crossover`` /
        ``ta.crossunder`` / ``ta.cross``, nested ``ta.correlation``,
        nested ``ta.vpt``, 4-arg ``ta.wvad``, nested ``ta.uo``, nested
        ``ta.apo``, nested ``ta.emv``, and nested ``ta.adx`` / ``ta.mfi`` stay na.
        """
        from backend.runtime import Runtime

        bars = _aligned_1m_bars(3 * 60)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", ta.sma(ta.ema(close, 3), 3)), title="nested")
plot(request.security(syminfo.tickerid, "60", ta.cci(high, low, close, 5)), title="cci4")
plot(request.security(syminfo.tickerid, "60", ta.wpr(high, low, close, 5)), title="wpr4")
plot(request.security(syminfo.tickerid, "60", ta.kama(close, 5, 2, 30)), title="kama4")
plot(request.security(syminfo.tickerid, "60", ta.kama(close, 5, 2)), title="kama3")
plot(request.security(syminfo.tickerid, "60", ta.vwap(ta.sma(close, 5))), title="vwapn")
plot(request.security(syminfo.tickerid, "60", ta.cum(ta.sma(close, 5))), title="cumn")
plot(request.security(syminfo.tickerid, "60", ta.change(ta.sma(close, 5))), title="chgn")
plot(request.security(syminfo.tickerid, "60", ta.adx(5, 5)), title="adx2")
plot(request.security(syminfo.tickerid, "60", ta.adx(high, low, close, 5)), title="adx4")
plot(request.security(syminfo.tickerid, "60", ta.mfi(ta.sma(close, 5), 5)), title="mfin")
plot(request.security(syminfo.tickerid, "60", ta.obv(close, volume)), title="obv2")
plot(request.security(syminfo.tickerid, "60", ta.nvi(close, volume)), title="nvi2")
plot(request.security(syminfo.tickerid, "60", ta.pvi(close, volume)), title="pvi2")
plot(request.security(syminfo.tickerid, "60", ta.cmf(close, high, low, volume, 5)), title="cmf5")
plot(request.security(syminfo.tickerid, "60", ta.cmf(ta.sma(close, 5), high, low, volume, 5)), title="cmfn")
plot(request.security(syminfo.tickerid, "60", ta.accdist(high, low, close, volume)), title="ad4")
plot(request.security(syminfo.tickerid, "60", ta.wad(high, low, close, volume)), title="wad4")
plot(request.security(syminfo.tickerid, "60", ta.tr(high, low, close)), title="tr3")
plot(request.security(syminfo.tickerid, "60", ta.tsi(close, 13, 25)), title="tsi3")
plot(request.security(syminfo.tickerid, "60", ta.bbw(ta.sma(close, 5), 5, 2)), title="bbwn")
plot(request.security(syminfo.tickerid, "60", ta.stoch(close, high, low, 5)), title="stoch4")
plot(request.security(syminfo.tickerid, "60", ta.pivothigh(ta.sma(close, 5), 2, 2)), title="phn")
plot(request.security(syminfo.tickerid, "60", ta.pivotlow(ta.ema(close, 5), 2, 2)), title="pln")
plot(request.security(syminfo.tickerid, "60", ta.percentile_nearest_rank(ta.sma(close, 5), 20, 50)), title="pnrn")
plot(request.security(syminfo.tickerid, "60", ta.percentile_linear_interpolation(ta.ema(close, 5), 20, 50)), title="plin")
plot(request.security(syminfo.tickerid, "60", ta.crossover(ta.sma(close, 5), open)), title="xon")
plot(request.security(syminfo.tickerid, "60", ta.crossunder(close, ta.ema(open, 5))), title="xun")
plot(request.security(syminfo.tickerid, "60", ta.cross(ta.sma(close, 5), open)), title="xn")
plot(request.security(syminfo.tickerid, "60", ta.cross(close, ta.ema(open, 5))), title="xn2")
plot(request.security(syminfo.tickerid, "60", ta.correlation(ta.sma(close, 5), volume, 20)), title="corrn")
plot(request.security(syminfo.tickerid, "60", ta.correlation(close, ta.ema(volume, 5), 20)), title="corrn2")
plot(request.security(syminfo.tickerid, "60", ta.vpt(ta.sma(close, 5))), title="vptn")
plot(request.security(syminfo.tickerid, "60", ta.wvad(high, low, close, volume)), title="wvad4")
plot(request.security(syminfo.tickerid, "60", ta.wvad(high, low, close, volume, 5)), title="wvad5")
plot(request.security(syminfo.tickerid, "60", ta.apo(ta.sma(close, 5), 10, 20)), title="apon")
plot(request.security(syminfo.tickerid, "60", ta.emv(close)), title="emvn")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert all(_is_na(x) for x in out["series"]["cci4"])
        assert all(_is_na(x) for x in out["series"]["wpr4"])
        assert all(_is_na(x) for x in out["series"]["kama4"])
        assert all(_is_na(x) for x in out["series"]["kama3"])
        assert all(_is_na(x) for x in out["series"]["adx4"])
        assert all(_is_na(x) for x in out["series"]["tr3"])
        assert all(_is_na(x) for x in out["series"]["tsi3"])
        assert all(_is_na(x) for x in out["series"]["bbwn"])
        assert all(_is_na(x) for x in out["series"]["stoch4"])
        assert all(_is_na(x) for x in out["series"]["phn"])
        assert all(_is_na(x) for x in out["series"]["pln"])
        # Nested percentile can coincidentally equal an OHLCV sample and hit the
        # chart pre-eval heuristic (same as nested sma); matcher stays unmatched.
        pol = (out.get("meta") or {}).get("request_security") or {}
        policies = pol.get("policies") or {}
        assert "complex_htf_na" in policies
        assert "htf_simple_ta_resample" not in policies

    def test_htf_wma_and_rma_finite_after_warmup(self) -> None:
        from backend.runtime import Runtime

        bars = _aligned_1m_bars(12 * 60)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", ta.wma(close, 3)), title="hwma")
plot(request.security(syminfo.tickerid, "60", ta.rma(close, 3)), title="hrma")
plot(ta.wma(close, 3), title="cwma")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hwma = out["series"]["hwma"]
        hrma = out["series"]["hrma"]
        cwma = out["series"]["cwma"]
        finite_w = [x for x in hwma[4 * 60 :] if not _is_na(x)]
        finite_r = [x for x in hrma[4 * 60 :] if not _is_na(x)]
        assert len(finite_w) > 0 and math.isfinite(float(finite_w[-1]))
        assert len(finite_r) > 0 and math.isfinite(float(finite_r[-1]))
        if not _is_na(hwma[-1]) and not _is_na(cwma[-1]):
            assert abs(float(hwma[-1]) - float(cwma[-1])) > 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})

    def test_match_htf_simple_ta_ast_allowlist(self) -> None:
        from pynescript.ast.evaluator.builtins.request import match_htf_simple_ta_ast
        from pynescript.ast.helper import parse

        def _expr(src: str):
            return parse(src, mode="eval").body

        m = match_htf_simple_ta_ast(_expr("ta.sma(close, 14)"))
        assert m is not None and m.name == "sma" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.atr(14)"))
        assert m is not None and m.name == "atr" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.wma(close, 14)"))
        assert m is not None and m.name == "wma" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.rma(hlc3, 10)"))
        assert m is not None and m.name == "rma" and m.source == "hlc3" and m.length == 10
        m = match_htf_simple_ta_ast(_expr("ta.cmo(close, 9)"))
        assert m is not None and m.name == "cmo" and m.source == "close" and m.length == 9
        m = match_htf_simple_ta_ast(_expr("ta.stdev(close, 14)"))
        assert m is not None and m.name == "stdev" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.linreg(hl2, 20)"))
        assert m is not None and m.name == "linreg" and m.source == "hl2" and m.length == 20
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.linreg(close, 14, 1)"))
        assert m is not None and m.name == "linreg" and m.source == "close" and m.length == 14
        assert m.extra == 1
        m = match_htf_simple_ta_ast(_expr("ta.cci(close, 14)"))
        assert m is not None and m.name == "cci" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.roc(close, 9)"))
        assert m is not None and m.name == "roc" and m.source == "close" and m.length == 9
        m = match_htf_simple_ta_ast(_expr("ta.mom(hl2, 10)"))
        assert m is not None and m.name == "mom" and m.source == "hl2" and m.length == 10
        m = match_htf_simple_ta_ast(_expr("ta.hma(close, 14)"))
        assert m is not None and m.name == "hma" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.vwma(close, 14)"))
        assert m is not None and m.name == "vwma" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.cci(14)"))
        assert m is not None and m.name == "cci" and m.source == "hlc3" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.dema(close, 14)"))
        assert m is not None and m.name == "dema" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.tema(hl2, 9)"))
        assert m is not None and m.name == "tema" and m.source == "hl2" and m.length == 9
        m = match_htf_simple_ta_ast(_expr("ta.wpr(14)"))
        assert m is not None and m.name == "wpr" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.highest(close, 14)"))
        assert m is not None and m.name == "highest" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.lowest(close, 14)"))
        assert m is not None and m.name == "lowest" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.highest(14)"))
        assert m is not None and m.name == "highest" and m.source == "high" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.lowest(14)"))
        assert m is not None and m.name == "lowest" and m.source == "low" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.range(close, 14)"))
        assert m is not None and m.name == "range" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.median(close, 14)"))
        assert m is not None and m.name == "median" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.dev(hlc3, 10)"))
        assert m is not None and m.name == "dev" and m.source == "hlc3" and m.length == 10
        m = match_htf_simple_ta_ast(_expr("ta.variance(hl2, 20)"))
        assert m is not None and m.name == "variance" and m.source == "hl2" and m.length == 20
        m = match_htf_simple_ta_ast(_expr("ta.mode(close, 14)"))
        assert m is not None and m.name == "mode" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.percentrank(hlc3, 10)"))
        assert m is not None and m.name == "percentrank" and m.source == "hlc3" and m.length == 10
        m = match_htf_simple_ta_ast(_expr("ta.change(hl2, 20)"))
        assert m is not None and m.name == "change" and m.source == "hl2" and m.length == 20
        m = match_htf_simple_ta_ast(_expr("ta.change(close)"))
        assert m is not None and m.name == "change" and m.source == "close" and m.length == 1
        m = match_htf_simple_ta_ast(_expr("ta.change(hl2)"))
        assert m is not None and m.name == "change" and m.source == "hl2" and m.length == 1
        m = match_htf_simple_ta_ast(_expr("ta.cog(close, 14)"))
        assert m is not None and m.name == "cog" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.highestbars(close, 14)"))
        assert m is not None and m.name == "highestbars" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.lowestbars(close, 14)"))
        assert m is not None and m.name == "lowestbars" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.highestbars(14)"))
        assert m is not None and m.name == "highestbars" and m.source == "high" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.lowestbars(14)"))
        assert m is not None and m.name == "lowestbars" and m.source == "low" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.kama(close, 14)"))
        assert m is not None and m.name == "kama" and m.source == "close" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.rising(close, 3)"))
        assert m is not None and m.name == "rising" and m.source == "close" and m.length == 3
        m = match_htf_simple_ta_ast(_expr("ta.falling(hl2, 5)"))
        assert m is not None and m.name == "falling" and m.source == "hl2" and m.length == 5
        m = match_htf_simple_ta_ast(_expr("ta.swma(close)"))
        assert m is not None and m.name == "swma" and m.source == "close" and m.length == 4
        m = match_htf_simple_ta_ast(_expr("ta.swma(hl2)"))
        assert m is not None and m.name == "swma" and m.source == "hl2" and m.length == 4
        m = match_htf_simple_ta_ast(_expr("ta.ao()"))
        assert m is not None and m.name == "ao" and m.source == "hl2" and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.ao(5)"))
        assert m is not None and m.name == "ao" and m.source == "hl2" and m.length == 34
        assert m.extra == 5
        m = match_htf_simple_ta_ast(_expr("ta.ao(5, 34)"))
        assert m is not None and m.name == "ao" and m.source == "hl2" and m.length == 34
        assert m.extra == 5
        m = match_htf_simple_ta_ast(_expr("ta.cum(close)"))
        assert m is not None and m.name == "cum" and m.source == "close" and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.cum(hl2)"))
        assert m is not None and m.name == "cum" and m.source == "hl2" and m.length == 0
        m = match_htf_simple_ta_ast(_expr("ta.range(14)"))
        assert m is not None and m.name == "range" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.vwap()"))
        assert m is not None and m.name == "vwap" and m.source == "hlc3" and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.vwap(close)"))
        assert m is not None and m.name == "vwap" and m.source == "close" and m.length == 0
        m = match_htf_simple_ta_ast(_expr("ta.vwap(hlc3)"))
        assert m is not None and m.name == "vwap" and m.source == "hlc3" and m.length == 0
        m = match_htf_simple_ta_ast(_expr("ta.adx(14)"))
        assert m is not None and m.name == "adx" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.mfi(14)"))
        assert m is not None and m.name == "mfi" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.obv()"))
        assert m is not None and m.name == "obv" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.nvi()"))
        assert m is not None and m.name == "nvi" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.pvi()"))
        assert m is not None and m.name == "pvi" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.accdist()"))
        assert m is not None and m.name == "accdist" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.wad()"))
        assert m is not None and m.name == "wad" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.tr()"))
        assert m is not None and m.name == "tr" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.tr(true)"))
        assert m is not None and m.name == "tr" and m.source is None and m.length == 0
        m = match_htf_simple_ta_ast(_expr("ta.tr(false)"))
        assert m is not None and m.name == "tr" and m.source is None and m.length == 0
        m = match_htf_simple_ta_ast(_expr("ta.tsi(13, 25)"))
        assert m is not None and m.name == "tsi" and m.source == "close" and m.length == 25
        assert m.extra == 13
        m = match_htf_simple_ta_ast(_expr("ta.bbw(close, 20, 2)"))
        assert m is not None and m.name == "bbw" and m.source == "close" and m.length == 20
        assert m.extra == 2
        m = match_htf_simple_ta_ast(_expr("ta.bbw(hl2, 20, 2.0)"))
        assert m is not None and m.name == "bbw" and m.source == "hl2" and m.length == 20
        assert m.extra == 2
        m = match_htf_simple_ta_ast(_expr("ta.bbw(20, 2)"))
        assert m is not None and m.name == "bbw" and m.source == "close" and m.length == 20
        assert m.extra == 2
        m = match_htf_simple_ta_ast(_expr("ta.stoch(14)"))
        assert m is not None and m.name == "stoch" and m.source is None and m.length == 14
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.stoch(14, 3)"))
        assert m is not None and m.name == "stoch" and m.source is None and m.length == 14
        assert m.extra == 3
        m = match_htf_simple_ta_ast(_expr("ta.pivothigh(2, 2)"))
        assert m is not None and m.name == "pivothigh" and m.source == "high" and m.length == 2
        assert m.extra == 2
        m = match_htf_simple_ta_ast(_expr("ta.pivotlow(2, 2)"))
        assert m is not None and m.name == "pivotlow" and m.source == "low" and m.length == 2
        assert m.extra == 2
        m = match_htf_simple_ta_ast(_expr("ta.pivothigh(close, 2, 2)"))
        assert m is not None and m.name == "pivothigh" and m.source == "close" and m.length == 2
        assert m.extra == 2
        m = match_htf_simple_ta_ast(_expr("ta.pivotlow(hl2, 3, 1)"))
        assert m is not None and m.name == "pivotlow" and m.source == "hl2" and m.length == 3
        assert m.extra == 1
        m = match_htf_simple_ta_ast(_expr("ta.percentile_nearest_rank(close, 20, 50)"))
        assert m is not None and m.name == "percentile_nearest_rank" and m.source == "close"
        assert m.length == 20 and m.extra == 50
        m = match_htf_simple_ta_ast(_expr("ta.percentile_linear_interpolation(hl2, 14, 0)"))
        assert m is not None and m.name == "percentile_linear_interpolation" and m.source == "hl2"
        assert m.length == 14 and m.extra == 0
        m = match_htf_simple_ta_ast(_expr("ta.percentile_nearest_rank(hlc3, 10, 50.0)"))
        assert m is not None and m.name == "percentile_nearest_rank" and m.source == "hlc3"
        assert m.length == 10 and m.extra == 50
        m = match_htf_simple_ta_ast(_expr("ta.dpo(21)"))
        assert m is not None and m.name == "dpo" and m.source == "close" and m.length == 21
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.dpo(3)"))
        assert m is not None and m.name == "dpo" and m.source == "close" and m.length == 3
        m = match_htf_simple_ta_ast(_expr("ta.dpo(close, 21)"))
        assert m is not None and m.name == "dpo" and m.source == "close" and m.length == 21
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.dpo(hl2, 3)"))
        assert m is not None and m.name == "dpo" and m.source == "hl2" and m.length == 3
        m = match_htf_simple_ta_ast(_expr("ta.dpo(open, 14)"))
        assert m is not None and m.name == "dpo" and m.source == "open" and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.crossover(close, open)"))
        assert m is not None and m.name == "crossover" and m.source == "close" and m.length == 0
        assert m.extra == 1
        m = match_htf_simple_ta_ast(_expr("ta.crossunder(high, low)"))
        assert m is not None and m.name == "crossunder" and m.source == "high" and m.length == 0
        assert m.extra == 3
        m = match_htf_simple_ta_ast(_expr("ta.crossover(hl2, hlc3)"))
        assert m is not None and m.name == "crossover" and m.source == "hl2" and m.length == 0
        assert m.extra == 6
        m = match_htf_simple_ta_ast(_expr("ta.crossunder(ohlc4, volume)"))
        assert m is not None and m.name == "crossunder" and m.source == "ohlc4" and m.length == 0
        assert m.extra == 4
        m = match_htf_simple_ta_ast(_expr("ta.crossover(close, hlcc4)"))
        assert m is not None and m.name == "crossover" and m.source == "close" and m.length == 0
        assert m.extra == 8
        m = match_htf_simple_ta_ast(_expr("ta.cross(close, open)"))
        assert m is not None and m.name == "cross" and m.source == "close" and m.length == 0
        assert m.extra == 1
        m = match_htf_simple_ta_ast(_expr("ta.cross(high, low)"))
        assert m is not None and m.name == "cross" and m.source == "high" and m.length == 0
        assert m.extra == 3
        m = match_htf_simple_ta_ast(_expr("ta.cross(hl2, hlc3)"))
        assert m is not None and m.name == "cross" and m.source == "hl2" and m.length == 0
        assert m.extra == 6
        m = match_htf_simple_ta_ast(_expr("ta.cross(ohlc4, volume)"))
        assert m is not None and m.name == "cross" and m.source == "ohlc4" and m.length == 0
        assert m.extra == 4
        m = match_htf_simple_ta_ast(_expr("ta.cross(close, hlcc4)"))
        assert m is not None and m.name == "cross" and m.source == "close" and m.length == 0
        assert m.extra == 8
        m = match_htf_simple_ta_ast(_expr("ta.correlation(close, volume, 20)"))
        assert m is not None and m.name == "correlation" and m.source == "close" and m.length == 20
        assert m.extra == 4
        m = match_htf_simple_ta_ast(_expr("ta.correlation(hl2, hlc3, 2)"))
        assert m is not None and m.name == "correlation" and m.source == "hl2" and m.length == 2
        assert m.extra == 6
        m = match_htf_simple_ta_ast(_expr("ta.correlation(close, hlcc4, 3)"))
        assert m is not None and m.name == "correlation" and m.source == "close" and m.length == 3
        assert m.extra == 8
        m = match_htf_simple_ta_ast(_expr("ta.cmf(14)"))
        assert m is not None and m.name == "cmf" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.vpt()"))
        assert m is not None and m.name == "vpt" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.pvt()"))
        assert m is not None and m.name == "vpt" and m.source is None and m.length == 0
        assert m.extra is None
        m = match_htf_simple_ta_ast(_expr("ta.vpt(close)"))
        assert m is not None and m.name == "vpt" and m.source is None and m.length == 0
        m = match_htf_simple_ta_ast(_expr("ta.wvad(14)"))
        assert m is not None and m.name == "wvad" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.wvad()"))
        assert m is not None and m.name == "wvad" and m.source is None and m.length == 20
        m = match_htf_simple_ta_ast(_expr("ta.wvad(3)"))
        assert m is not None and m.name == "wvad" and m.source is None and m.length == 3
        m = match_htf_simple_ta_ast(_expr("ta.uo(7, 14, 28)"))
        assert m is not None and m.name == "uo" and m.source is None and m.length == 7
        assert m.extra == 14 * 1000 + 28
        m = match_htf_simple_ta_ast(_expr("ta.uo(2, 3, 4)"))
        assert m is not None and m.name == "uo" and m.source is None and m.length == 2
        assert m.extra == 3 * 1000 + 4
        m = match_htf_simple_ta_ast(_expr("ta.apo(close, 10, 20)"))
        assert m is not None and m.name == "apo" and m.source == "close" and m.length == 20
        assert m.extra == 10
        m = match_htf_simple_ta_ast(_expr("ta.apo(hl2, 3, 5)"))
        assert m is not None and m.name == "apo" and m.source == "hl2" and m.length == 5
        assert m.extra == 3
        m = match_htf_simple_ta_ast(_expr("ta.emv(14)"))
        assert m is not None and m.name == "emv" and m.source is None and m.length == 14
        m = match_htf_simple_ta_ast(_expr("ta.emv(3)"))
        assert m is not None and m.name == "emv" and m.source is None and m.length == 3
        assert match_htf_simple_ta_ast(_expr("ta.adx(14, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.adx(high, low, close, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.adx(ta.sma(close, 14), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.mfi(close, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.mfi(ta.sma(close, 14), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.obv(close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.nvi(close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.pvi(close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.accdist(high, low, close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.wad(high, low, close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.accdist(ta.sma(high, 5), low, close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.wad(ta.sma(high, 5), low, close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.tr(high, low, close)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.tsi(close, 13, 25)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.tsi(ta.sma(close, 5), 13, 25)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.bbw(ta.sma(close, 5), 20, 2)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.bbw(20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.bbw(close, 20, 2.5)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.stoch(close, high, low, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.stoch(ta.sma(close, 5), high, low, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.pivothigh(ta.sma(close, 5), 2, 2)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.pivotlow(ta.ema(close, 5), 2, 2)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.pivothigh(2)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.pivotlow()")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentile_nearest_rank(ta.sma(close, 5), 20, 50)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentile_linear_interpolation(ta.ema(close, 5), 20, 50)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentile_nearest_rank(close, 20, 50.5)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentile_linear_interpolation(close, 20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentile_nearest_rank(close, 20, -1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.dpo(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.dpo(ta.sma(close, 5), 21)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.dpo()")) is None
        assert match_htf_simple_ta_ast(_expr("ta.dpo(close, 21, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.crossover(ta.sma(close, 5), open)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.crossunder(close, ta.ema(open, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.crossover(close)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.crossover(close, 50)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.crossunder(close, open, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cross(ta.sma(close, 5), open)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cross(close, ta.ema(open, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cross(close)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cross(close, 50)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cross(close, open, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.correlation(ta.sma(close, 5), volume, 20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.correlation(close, ta.ema(volume, 5), 20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.correlation(close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.correlation(close, volume, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.correlation(close, 20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cmf(close, high, low, volume, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cmf(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.vpt(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.wvad(high, low, close, volume)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.wvad(high, low, close, volume, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.wvad(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.uo(ta.sma(close, 5), 14, 28)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.uo(7, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.uo(7, 1000, 28)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.uo(7, 14, 1000)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.apo(ta.sma(close, 5), 10, 20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.apo(close, 10)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.apo(10, 20)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.emv()")) is None
        assert match_htf_simple_ta_ast(_expr("ta.emv(close)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.emv(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.sma(ta.ema(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cci(high, low, close, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.wpr(high, low, close, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.linreg(ta.sma(close, 5), 14, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.kama(close, 14, 2, 30)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.kama(close, 14, 2)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.highest(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.lowest(ta.ema(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.swma(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.swma(close, 4)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cum(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cum(close, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.ao(close)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.median(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.dev(ta.ema(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.variance(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.median(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.mode(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentrank(ta.ema(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.change(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.change(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.mode(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.percentrank(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.change(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cog(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.highestbars(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.lowestbars(ta.ema(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.cog(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.kama(ta.sma(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.rising(ta.sma(close, 5), 3)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.falling(ta.ema(close, 5), 3)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.rising(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.falling(14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.vwap(ta.sma(close, 5))")) is None
        assert match_htf_simple_ta_ast(_expr("ta.vwap(close, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.vwap(hlc3, 1, 1)")) is None
        assert match_htf_simple_ta_ast(_expr("close")) is None

    def test_htf_cmo_stdev_linreg_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily bucket, not forming day."""
        import statistics

        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.cmo(close, 3)), title="hcmo")
plot(request.security(syminfo.tickerid, "D", ta.stdev(close, 3)), title="hstdev")
plot(request.security(syminfo.tickerid, "D", ta.linreg(close, 3)), title="hlin")
plot(ta.cmo(close, 3), title="ccmo")
plot(ta.stdev(close, 3), title="cstdev")
plot(ta.linreg(close, 3), title="clin")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hcmo = out["series"]["hcmo"]
        hstdev = out["series"]["hstdev"]
        hlin = out["series"]["hlin"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # cmo(3) needs 4 HTF samples; stdev/linreg(3) need 3.
        assert all(_is_na(x) for x in hcmo[1:96])
        assert all(_is_na(x) for x in hstdev[1:72])
        assert all(_is_na(x) for x in hlin[1:72])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hstdev[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win3 = daily_closes[-3:]
        expect_stdev = statistics.pstdev(win3)
        assert abs(float(hstdev[-1]) - expect_stdev) < 1e-9
        # linreg(length=3, offset=0) skip-na OLS endpoint on last 3 completed days.
        n = 3
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(win3) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, win3, strict=True))
        den = sum((xi - mean_x) ** 2 for xi in xs)
        expect_lin = mean_y if den == 0 else mean_y + (num / den) * ((n - 1) - mean_x)
        assert abs(float(hlin[-1]) - expect_lin) < 1e-9
        win4 = daily_closes[-4:]
        up = down = 0.0
        for a, b in itertools.pairwise(win4):
            diff = b - a
            if diff > 0:
                up += diff
            else:
                down += -diff
        denom = up + down
        expect_cmo = 0.0 if denom == 0 else 100.0 * (up - down) / denom
        assert abs(float(hcmo[-1]) - expect_cmo) < 1e-9
        # Not chart-TF passthrough.
        assert abs(float(hstdev[-1]) - float(out["series"]["cstdev"][-1])) > 1e-6
        assert abs(float(hcmo[-1]) - float(out["series"]["ccmo"][-1])) > 1e-6
        assert abs(float(hlin[-1]) - float(out["series"]["clin"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_cci_roc_mom_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily bucket for cci/roc/mom."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.cci(close, 3)), title="hcci")
plot(request.security(syminfo.tickerid, "D", ta.roc(close, 3)), title="hroc")
plot(request.security(syminfo.tickerid, "D", ta.mom(close, 3)), title="hmom")
plot(ta.cci(close, 3), title="ccci")
plot(ta.roc(close, 3), title="croc")
plot(ta.mom(close, 3), title="cmom")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hcci = out["series"]["hcci"]
        hroc = out["series"]["hroc"]
        hmom = out["series"]["hmom"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # cci(3) needs 3 HTF samples; roc/mom(3) need 4.
        assert all(_is_na(x) for x in hcci[1:72])
        assert all(_is_na(x) for x in hroc[1:96])
        assert all(_is_na(x) for x in hmom[1:96])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hcci[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win3 = daily_closes[-3:]
        mean = sum(win3) / 3.0
        mean_dev = sum(abs(v - mean) for v in win3) / 3.0
        expect_cci = 0.0 if mean_dev == 0.0 else (win3[-1] - mean) / (0.015 * mean_dev)
        assert abs(float(hcci[-1]) - expect_cci) < 1e-9
        base = daily_closes[-4]
        expect_roc = 100.0 * (daily_closes[-1] - base) / base
        expect_mom = daily_closes[-1] - base
        assert abs(float(hroc[-1]) - expect_roc) < 1e-9
        assert abs(float(hmom[-1]) - expect_mom) < 1e-9
        # Not chart-TF passthrough. Daily CCI of this arithmetic walk is 100
        # (same as a 3-bar chart CCI of a near-linear tail), so compare roc/mom
        # last samples and intra-day chart CCI variation vs HTF stepwise.
        assert abs(float(hroc[-1]) - float(out["series"]["croc"][-1])) > 1e-6
        assert abs(float(hmom[-1]) - float(out["series"]["cmom"][-1])) > 1e-6
        ccci_day5 = out["series"]["ccci"][5 * 24 : 6 * 24]
        assert any(not _is_na(v) and abs(float(v) - float(ccci_day5[0])) > 1e-6 for v in ccci_day5)
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_hma_vwma_cci1_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily hma/vwma/1-arg cci."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.hma(close, 3)), title="hhma")
plot(request.security(syminfo.tickerid, "D", ta.vwma(close, 3)), title="hvwma")
plot(request.security(syminfo.tickerid, "D", ta.cci(3)), title="hcci1")
plot(ta.hma(close, 3), title="chma")
plot(ta.vwma(close, 3), title="cvwma")
plot(ta.cci(3), title="ccci1")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hhma = out["series"]["hhma"]
        hvwma = out["series"]["hvwma"]
        hcci1 = out["series"]["hcci1"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        daily_tp: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
            hi = max(float(b["high"]) for b in chunk)
            lo = min(float(b["low"]) for b in chunk)
            cl = float(chunk[-1]["close"])
            daily_tp.append((hi + lo + cl) / 3.0)
        # hma(3)/vwma(3)/cci(3) need 3 HTF samples (hma sqrt(3)=1).
        assert all(_is_na(x) for x in hhma[1:72])
        assert all(_is_na(x) for x in hvwma[1:72])
        assert all(_is_na(x) for x in hcci1[1:72])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hhma[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win3 = daily_closes[-3:]
        wma3 = (win3[0] * 1.0 + win3[1] * 2.0 + win3[2] * 3.0) / 6.0
        expect_hma = 2.0 * win3[-1] - wma3
        assert abs(float(hhma[-1]) - expect_hma) < 1e-9
        win3_v = daily_vols[-3:]
        sv = sum(win3_v)
        expect_vwma = sum(c * v for c, v in zip(win3, win3_v, strict=True)) / sv
        assert abs(float(hvwma[-1]) - expect_vwma) < 1e-9
        tp3 = daily_tp[-3:]
        mean = sum(tp3) / 3.0
        mean_dev = sum(abs(v - mean) for v in tp3) / 3.0
        expect_cci = 0.0 if mean_dev == 0.0 else (tp3[-1] - mean) / (0.015 * mean_dev)
        assert abs(float(hcci1[-1]) - expect_cci) < 1e-9
        # Not chart-TF passthrough.
        assert abs(float(hhma[-1]) - float(out["series"]["chma"][-1])) > 1e-6
        assert abs(float(hvwma[-1]) - float(out["series"]["cvwma"][-1])) > 1e-6
        ccci_day5 = out["series"]["ccci1"][5 * 24 : 6 * 24]
        assert any(not _is_na(v) and abs(float(v) - float(ccci_day5[0])) > 1e-6 for v in ccci_day5)
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_dema_tema_wpr_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily dema/tema/1-arg wpr."""
        from backend.runtime import Runtime

        def _ema_full(src: list[float | None], period: int) -> list[float | None]:
            """Match interpret ``_ema`` (SMA seed, skip None until seeded)."""
            alpha = 2.0 / (period + 1)
            out: list[float | None] = []
            seed: list[float] = []
            seeded = False
            ema: float | None = None
            for raw in src:
                x: float | None
                if raw is None:
                    x = None
                else:
                    try:
                        fv = float(raw)
                    except (TypeError, ValueError):
                        fv = float("nan")
                    x = None if fv != fv else fv
                if not seeded:
                    if x is None:
                        out.append(None)
                        continue
                    seed.append(x)
                    if len(seed) < period:
                        out.append(None)
                        continue
                    ema = sum(seed) / period
                    seeded = True
                    out.append(ema)
                    continue
                if x is None:
                    out.append(ema)
                    continue
                ema = alpha * x + (1.0 - alpha) * float(ema)
                out.append(ema)
            return out

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.dema(close, 3)), title="hdema")
plot(request.security(syminfo.tickerid, "D", ta.tema(close, 3)), title="htema")
plot(request.security(syminfo.tickerid, "D", ta.wpr(3)), title="hwpr")
plot(ta.dema(close, 3), title="cdema")
plot(ta.tema(close, 3), title="ctema")
plot(ta.wpr(3), title="cwpr")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hdema = out["series"]["hdema"]
        htema = out["series"]["htema"]
        hwpr = out["series"]["hwpr"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes: list[float] = []
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
        # dema(3) seeds at unique index 4; tema(3) at 6; wpr(3) at 2.
        assert all(_is_na(x) for x in hdema[1:120])
        assert all(_is_na(x) for x in htema[1:168])
        assert all(_is_na(x) for x in hwpr[1:72])
        # Stepwise constant inside day 6 (last completed = day 5).
        day6 = hdema[6 * 24 : 7 * 24]
        assert all(not _is_na(x) for x in day6)
        ref = float(day6[0])
        for v in day6:
            assert abs(float(v) - ref) < 1e-9
        e1 = _ema_full(daily_closes, 3)
        e2 = _ema_full(e1, 3)
        e3 = _ema_full(e2, 3)
        expect_dema = 2.0 * float(e1[-1]) - float(e2[-1])
        assert abs(float(hdema[-1]) - expect_dema) < 1e-9
        expect_tema = 3.0 * float(e1[-1]) - 3.0 * float(e2[-1]) + float(e3[-1])
        assert abs(float(htema[-1]) - expect_tema) < 1e-9
        win_h = daily_highs[-3:]
        win_l = daily_lows[-3:]
        hh = max(win_h)
        ll = min(win_l)
        expect_wpr = 0.0 if hh == ll else -100.0 * (hh - daily_closes[-1]) / (hh - ll)
        assert abs(float(hwpr[-1]) - expect_wpr) < 1e-9
        # Not chart-TF passthrough.
        assert abs(float(hdema[-1]) - float(out["series"]["cdema"][-1])) > 1e-6
        assert abs(float(htema[-1]) - float(out["series"]["ctema"][-1])) > 1e-6
        assert abs(float(hwpr[-1]) - float(out["series"]["cwpr"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_highest_lowest_range_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily highest/lowest/range."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.highest(close, 3)), title="hhi")
plot(request.security(syminfo.tickerid, "D", ta.lowest(close, 3)), title="hlo")
plot(request.security(syminfo.tickerid, "D", ta.highest(3)), title="hhi1")
plot(request.security(syminfo.tickerid, "D", ta.lowest(3)), title="hlo1")
plot(request.security(syminfo.tickerid, "D", ta.range(close, 3)), title="hrng")
plot(request.security(syminfo.tickerid, "D", ta.range(3)), title="hrng1")
plot(ta.highest(close, 3), title="chi")
plot(ta.lowest(close, 3), title="clo")
plot(ta.range(close, 3), title="crng")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hhi = out["series"]["hhi"]
        hlo = out["series"]["hlo"]
        hhi1 = out["series"]["hhi1"]
        hlo1 = out["series"]["hlo1"]
        hrng = out["series"]["hrng"]
        hrng1 = out["series"]["hrng1"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes: list[float] = []
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
        # highest/lowest/range(3) need 3 HTF samples.
        assert all(_is_na(x) for x in hhi[1:72])
        assert all(_is_na(x) for x in hlo[1:72])
        assert all(_is_na(x) for x in hhi1[1:72])
        assert all(_is_na(x) for x in hlo1[1:72])
        assert all(_is_na(x) for x in hrng[1:72])
        assert all(_is_na(x) for x in hrng1[1:72])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hhi[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win_c = daily_closes[-3:]
        expect_hi = max(win_c)
        expect_lo = min(win_c)
        expect_rng = expect_hi - expect_lo
        assert abs(float(hhi[-1]) - expect_hi) < 1e-9
        assert abs(float(hlo[-1]) - expect_lo) < 1e-9
        assert abs(float(hrng[-1]) - expect_rng) < 1e-9
        expect_hi1 = max(daily_highs[-3:])
        expect_lo1 = min(daily_lows[-3:])
        expect_rng1 = expect_hi1 - expect_lo1
        assert abs(float(hhi1[-1]) - expect_hi1) < 1e-9
        assert abs(float(hlo1[-1]) - expect_lo1) < 1e-9
        assert abs(float(hrng1[-1]) - expect_rng1) < 1e-9
        # Not chart-TF passthrough.
        assert abs(float(hhi[-1]) - float(out["series"]["chi"][-1])) > 1e-6
        assert abs(float(hlo[-1]) - float(out["series"]["clo"][-1])) > 1e-6
        assert abs(float(hrng[-1]) - float(out["series"]["crng"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_median_dev_variance_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily median/dev/variance."""
        import statistics

        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.median(close, 3)), title="hmed")
plot(request.security(syminfo.tickerid, "D", ta.dev(close, 3)), title="hdev")
plot(request.security(syminfo.tickerid, "D", ta.variance(close, 3)), title="hvar")
plot(ta.median(close, 3), title="cmed")
plot(ta.dev(close, 3), title="cdev")
plot(ta.variance(close, 3), title="cvar")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hmed = out["series"]["hmed"]
        hdev = out["series"]["hdev"]
        hvar = out["series"]["hvar"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # median/dev/variance(3) need 3 HTF samples.
        assert all(_is_na(x) for x in hmed[1:72])
        assert all(_is_na(x) for x in hdev[1:72])
        assert all(_is_na(x) for x in hvar[1:72])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hmed[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win3 = daily_closes[-3:]
        expect_med = statistics.median(win3)
        mean = sum(win3) / 3
        expect_dev = sum(abs(v - mean) for v in win3) / 3
        expect_var = statistics.pvariance(win3)
        assert abs(float(hmed[-1]) - expect_med) < 1e-9
        assert abs(float(hdev[-1]) - expect_dev) < 1e-9
        assert abs(float(hvar[-1]) - expect_var) < 1e-9
        # Not chart-TF passthrough.
        assert abs(float(hmed[-1]) - float(out["series"]["cmed"][-1])) > 1e-6
        assert abs(float(hdev[-1]) - float(out["series"]["cdev"][-1])) > 1e-6
        assert abs(float(hvar[-1]) - float(out["series"]["cvar"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_mode_percentrank_change_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily mode/percentrank/change."""
        import statistics

        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.mode(close, 3)), title="hmode")
plot(request.security(syminfo.tickerid, "D", ta.percentrank(close, 3)), title="hpr")
plot(request.security(syminfo.tickerid, "D", ta.change(close, 3)), title="hchg")
plot(ta.mode(close, 3), title="cmode")
plot(ta.percentrank(close, 3), title="cpr")
plot(ta.change(close, 3), title="cchg")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hmode = out["series"]["hmode"]
        hpr = out["series"]["hpr"]
        hchg = out["series"]["hchg"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # mode/percentrank(3) need 3 HTF samples; change(3) needs 4.
        assert all(_is_na(x) for x in hmode[1:72])
        assert all(_is_na(x) for x in hpr[1:72])
        assert all(_is_na(x) for x in hchg[1:96])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hmode[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win3 = daily_closes[-3:]
        try:
            expect_mode = statistics.mode(win3)
        except statistics.StatisticsError:
            expect_mode = win3[0]
        current = win3[-1]
        prev3 = daily_closes[-4:-1]
        count_below = sum(1 for v in prev3 if v <= current)
        expect_pr = (count_below / len(prev3)) * 100.0
        expect_chg = daily_closes[-1] - daily_closes[-4]
        assert abs(float(hmode[-1]) - expect_mode) < 1e-9
        assert abs(float(hpr[-1]) - expect_pr) < 1e-9
        assert abs(float(hchg[-1]) - expect_chg) < 1e-9
        # Not chart-TF passthrough. Last-sample percentrank of this walk can
        # match a 3-bar chart window (both 2/3 below current); HTF is stepwise.
        assert abs(float(hmode[-1]) - float(out["series"]["cmode"][-1])) > 1e-6
        assert abs(float(hchg[-1]) - float(out["series"]["cchg"][-1])) > 1e-6
        cpr_day5 = out["series"]["cpr"][5 * 24 : 6 * 24]
        assert any(not _is_na(v) and abs(float(v) - float(cpr_day5[0])) > 1e-6 for v in cpr_day5)
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_cog_highestbars_lowestbars_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily cog/highestbars/lowestbars."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.cog(close, 3)), title="hcog")
plot(request.security(syminfo.tickerid, "D", ta.highestbars(close, 3)), title="hhb")
plot(request.security(syminfo.tickerid, "D", ta.lowestbars(close, 3)), title="hlb")
plot(request.security(syminfo.tickerid, "D", ta.highestbars(3)), title="hhb1")
plot(request.security(syminfo.tickerid, "D", ta.lowestbars(3)), title="hlb1")
plot(ta.cog(close, 3), title="ccog")
plot(ta.highestbars(close, 3), title="chb")
plot(ta.lowestbars(close, 3), title="clb")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hcog = out["series"]["hcog"]
        hhb = out["series"]["hhb"]
        hlb = out["series"]["hlb"]
        hhb1 = out["series"]["hhb1"]
        hlb1 = out["series"]["hlb1"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes: list[float] = []
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))

        def _bars_offset(window: list[float], *, highest: bool) -> int:
            best_i = 0
            best_v = window[0]
            for i, v in enumerate(window):
                if (highest and v > best_v) or (not highest and v < best_v):
                    best_v = v
                    best_i = i
            return -(len(window) - 1 - best_i)

        # cog/highestbars/lowestbars(3) need 3 HTF samples.
        assert all(_is_na(x) for x in hcog[1:72])
        assert all(_is_na(x) for x in hhb[1:72])
        assert all(_is_na(x) for x in hlb[1:72])
        assert all(_is_na(x) for x in hhb1[1:72])
        assert all(_is_na(x) for x in hlb1[1:72])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hcog[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win3 = daily_closes[-3:]
        num = sum((i + 1) * val for i, val in enumerate(reversed(win3)))
        den = sum(win3)
        expect_cog = -num / den
        expect_hb = _bars_offset(win3, highest=True)
        expect_lb = _bars_offset(win3, highest=False)
        expect_hb1 = _bars_offset(daily_highs[-3:], highest=True)
        expect_lb1 = _bars_offset(daily_lows[-3:], highest=False)
        assert abs(float(hcog[-1]) - expect_cog) < 1e-9
        assert abs(float(hhb[-1]) - expect_hb) < 1e-9
        assert abs(float(hlb[-1]) - expect_lb) < 1e-9
        assert abs(float(hhb1[-1]) - expect_hb1) < 1e-9
        assert abs(float(hlb1[-1]) - expect_lb1) < 1e-9
        # Not chart-TF passthrough. Last-sample highestbars of this walk can
        # match a 3-bar chart window (both 0 on a rising tail); HTF is stepwise.
        assert abs(float(hcog[-1]) - float(out["series"]["ccog"][-1])) > 1e-6
        chb_day5 = out["series"]["chb"][5 * 24 : 6 * 24]
        assert any(not _is_na(v) and abs(float(v) - float(chb_day5[0])) > 1e-6 for v in chb_day5)
        clb_day5 = out["series"]["clb"][5 * 24 : 6 * 24]
        assert any(not _is_na(v) and abs(float(v) - float(clb_day5[0])) > 1e-6 for v in clb_day5)
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_kama_rising_falling_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily kama/rising/falling."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.kama(close, 3)), title="hkama")
plot(request.security(syminfo.tickerid, "D", ta.rising(close, 3)), title="hris")
plot(request.security(syminfo.tickerid, "D", ta.falling(close, 3)), title="hfal")
plot(ta.kama(close, 3), title="ckama")
plot(ta.rising(close, 3), title="cris")
plot(ta.falling(close, 3), title="cfal")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hkama = out["series"]["hkama"]
        hris = out["series"]["hris"]
        hfal = out["series"]["hfal"]
        # 8 UTC days of hourly bars; last-completed is day 6 while day 7 is forming.
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]

        def _kama_last(series: list[float], length: int, fast: int = 2, slow: int = 30) -> float:
            kama = series[length - 1]
            for i in range(length, len(series)):
                change = abs(series[i] - series[i - length])
                volatility = sum(abs(series[i - j] - series[i - j - 1]) for j in range(length))
                if volatility != 0:
                    efficiency = change / volatility
                    fastest = 2.0 / (fast + 1.0)
                    slowest = 2.0 / (slow + 1.0)
                    smoothing = efficiency * (fastest - slowest) + slowest
                    sc = smoothing * smoothing
                else:
                    sc = (2.0 / (slow + 1.0)) ** 2
                kama = kama + sc * (series[i] - kama)
            return kama

        def _steps(series: list[float], period: int, *, rising: bool) -> float:
            if period < 1 or len(series) < period + 1:
                return 0.0
            for idx in range(1, period + 1):
                a, b = series[-idx], series[-idx - 1]
                if rising and a <= b:
                    return 0.0
                if not rising and a >= b:
                    return 0.0
            return 1.0

        # kama(3)/rising(3)/falling(3) need 4 HTF samples (first output at index 3).
        assert all(_is_na(x) for x in hkama[1:96])
        assert all(_is_na(x) for x in hris[1:96])
        assert all(_is_na(x) for x in hfal[1:96])
        # Stepwise constant inside day 5 (last completed = day 4).
        day5 = hkama[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        expect_kama = _kama_last(daily_closes, 3)
        expect_ris = _steps(daily_closes, 3, rising=True)
        expect_fal = _steps(daily_closes, 3, rising=False)
        assert abs(float(hkama[-1]) - expect_kama) < 1e-9
        assert abs(float(hris[-1]) - expect_ris) < 1e-9
        assert abs(float(hfal[-1]) - expect_fal) < 1e-9
        # Not chart-TF passthrough (hourly rising(3) never holds; daily closes do).
        # Falling is 0 on both (uptrend); HTF is still stepwise in the bucket.
        assert abs(float(hkama[-1]) - float(out["series"]["ckama"][-1])) > 1e-6
        assert abs(float(hris[-1]) - float(out["series"]["cris"][-1])) > 1e-6
        day5_fal = hfal[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_fal)
        fal_ref = float(day5_fal[0])
        for v in day5_fal:
            assert abs(float(v) - fal_ref) < 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_swma_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 4-period swma."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.swma(close)), title="hswma")
plot(ta.swma(close), title="cswma")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hswma = out["series"]["hswma"]
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # swma is 4-period; first output at unique index 3 (during day 4).
        assert all(_is_na(x) for x in hswma[1:96])
        day5 = hswma[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        w = daily_closes[-4:]
        expect = (w[0] + 2.0 * w[1] + 2.0 * w[2] + w[3]) / 6.0
        assert abs(float(hswma[-1]) - expect) < 1e-9
        assert abs(float(hswma[-1]) - float(out["series"]["cswma"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_ao_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily ta.ao() (SMA 5 - 34)."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 40)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.ao()), title="hao")
plot(ta.ao(), title="cao")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hao = out["series"]["hao"]
        daily_hl2: list[float] = []
        for d in range(39):
            chunk = bars[24 * d : 24 * (d + 1)]
            hi = max(float(b["high"]) for b in chunk)
            lo = min(float(b["low"]) for b in chunk)
            daily_hl2.append((hi + lo) * 0.5)
        # SMA(34) first output at unique index 33 (during day 34).
        assert all(_is_na(x) for x in hao[1 : 34 * 24])
        day36 = hao[36 * 24 : 37 * 24]
        assert all(not _is_na(x) for x in day36)
        ref = float(day36[0])
        for v in day36:
            assert abs(float(v) - ref) < 1e-9
        expect_fast = sum(daily_hl2[-5:]) / 5.0
        expect_slow = sum(daily_hl2[-34:]) / 34.0
        assert abs(float(hao[-1]) - (expect_fast - expect_slow)) < 1e-9
        assert abs(float(hao[-1]) - float(out["series"]["cao"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_ao2_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily ta.ao(3, 8)."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 12)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.ao(3, 8)), title="hao")
plot(ta.ao(3, 8), title="cao")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hao = out["series"]["hao"]
        daily_hl2: list[float] = []
        for d in range(11):
            chunk = bars[24 * d : 24 * (d + 1)]
            hi = max(float(b["high"]) for b in chunk)
            lo = min(float(b["low"]) for b in chunk)
            daily_hl2.append((hi + lo) * 0.5)
        # SMA(8) first output at unique index 7 (during day 8).
        assert all(_is_na(x) for x in hao[1 : 8 * 24])
        day9 = hao[9 * 24 : 10 * 24]
        assert all(not _is_na(x) for x in day9)
        ref = float(day9[0])
        for v in day9:
            assert abs(float(v) - ref) < 1e-9
        expect_fast = sum(daily_hl2[-3:]) / 3.0
        expect_slow = sum(daily_hl2[-8:]) / 8.0
        assert abs(float(hao[-1]) - (expect_fast - expect_slow)) < 1e-9
        assert abs(float(hao[-1]) - float(out["series"]["cao"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_linreg3_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily ta.linreg(close, 4, 1)."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.linreg(close, 4, 1)), title="hlin")
plot(ta.linreg(close, 4, 1), title="clin")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hlin = out["series"]["hlin"]
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # linreg(4) needs 4 HTF samples; first output during day 4.
        assert all(_is_na(x) for x in hlin[1:96])
        day5 = hlin[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        win = daily_closes[-4:]
        n = 4
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(win) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, win, strict=True))
        den = sum((xi - mean_x) ** 2 for xi in xs)
        # offset=1 → fitted x = n - 1 - 1 = n - 2
        expect_lin = mean_y if den == 0 else mean_y + (num / den) * ((n - 2) - mean_x)
        assert abs(float(hlin[-1]) - expect_lin) < 1e-9
        assert abs(float(hlin[-1]) - float(out["series"]["clin"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_vwap_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily cumulative ta.vwap."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.vwap()), title="hv0")
plot(request.security(syminfo.tickerid, "D", ta.vwap(close)), title="hv1")
plot(ta.vwap(), title="cv0")
plot(ta.vwap(close), title="cv1")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hv0 = out["series"]["hv0"]
        hv1 = out["series"]["hv1"]
        daily_hlc3: list[float] = []
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            hi = max(float(b["high"]) for b in chunk)
            lo = min(float(b["low"]) for b in chunk)
            cl = float(chunk[-1]["close"])
            daily_hlc3.append((hi + lo + cl) / 3.0)
            daily_closes.append(cl)
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # Cumulative from unique bar 0; first completed HTF close at chart 24.
        assert all(_is_na(x) for x in hv0[1:24])
        assert all(_is_na(x) for x in hv1[1:24])
        day5 = hv0[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        sv = sum(daily_vols)
        expect0 = sum(p * v for p, v in zip(daily_hlc3, daily_vols, strict=True)) / sv
        expect1 = sum(c * v for c, v in zip(daily_closes, daily_vols, strict=True)) / sv
        assert abs(float(hv0[-1]) - expect0) < 1e-9
        assert abs(float(hv1[-1]) - expect1) < 1e-9
        assert abs(float(hv0[-1]) - float(hv1[-1])) > 1e-6
        assert abs(float(hv0[-1]) - float(out["series"]["cv0"][-1])) > 1e-6
        assert abs(float(hv1[-1]) - float(out["series"]["cv1"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_cum_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily running ta.cum(close)."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.cum(close)), title="hcum")
plot(ta.cum(close), title="ccum")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hcum = out["series"]["hcum"]
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # Cumulative from unique bar 0; first completed HTF close at chart 24.
        assert all(_is_na(x) for x in hcum[1:24])
        day5 = hcum[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        expect = sum(daily_closes)
        assert abs(float(hcum[-1]) - expect) < 1e-9
        assert abs(float(hcum[-1]) - float(out["series"]["ccum"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_ao1_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily ta.ao(3) (fast=3, slow=34)."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 40)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.ao(3)), title="hao")
plot(ta.ao(3), title="cao")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hao = out["series"]["hao"]
        daily_hl2: list[float] = []
        for d in range(39):
            chunk = bars[24 * d : 24 * (d + 1)]
            hi = max(float(b["high"]) for b in chunk)
            lo = min(float(b["low"]) for b in chunk)
            daily_hl2.append((hi + lo) * 0.5)
        # SMA(34) first output at unique index 33 (during day 34).
        assert all(_is_na(x) for x in hao[1 : 34 * 24])
        day36 = hao[36 * 24 : 37 * 24]
        assert all(not _is_na(x) for x in day36)
        ref = float(day36[0])
        for v in day36:
            assert abs(float(v) - ref) < 1e-9
        expect_fast = sum(daily_hl2[-3:]) / 3.0
        expect_slow = sum(daily_hl2[-34:]) / 34.0
        assert abs(float(hao[-1]) - (expect_fast - expect_slow)) < 1e-9
        assert abs(float(hao[-1]) - float(out["series"]["cao"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_change1_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 1-arg ta.change(close)."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.change(close)), title="hchg")
plot(ta.change(close), title="cchg")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hchg = out["series"]["hchg"]
        daily_closes = [float(bars[24 * (d + 1) - 1]["close"]) for d in range(7)]
        # change(1) needs 2 HTF samples; first output at unique index 1 (during day 2).
        assert all(_is_na(x) for x in hchg[1:48])
        day5 = hchg[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5)
        ref = float(day5[0])
        for v in day5:
            assert abs(float(v) - ref) < 1e-9
        expect = daily_closes[-1] - daily_closes[-2]
        assert abs(float(hchg[-1]) - expect) < 1e-9
        assert abs(float(hchg[-1]) - float(out["series"]["cchg"][-1])) > 1e-6
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_adx_mfi_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 1-arg ta.adx / ta.mfi."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.common import CommonIndicators
        from pynescript.ast.evaluator.builtins.technical_submodules.volume import VolumeIndicators

        # Oscillating 5-day cycle so daily ADX/MFI differ from hourly (plain
        # `_day_aligned_hourly` is a strong uptrend and saturates ADX at 100).
        day0 = _utc_day0_ms()
        bars: list[dict] = []
        for i in range(24 * 12):
            base = 100.0 + 8.0 * math.sin(2.0 * math.pi * i / (24 * 5))
            o = round(base, 2)
            c = round(base + (1.2 if i % 4 else -0.8), 2)
            h = round(max(o, c) + 0.9, 2)
            lo = round(min(o, c) - 0.9, 2)
            bars.append(
                {
                    "open": o,
                    "high": h,
                    "low": max(lo, 0.01),
                    "close": c,
                    "time": day0 + i * 3_600_000,
                    "volume": 800.0 + (i % 24) * 40.0,
                }
            )
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.adx(3)), title="hadx")
plot(request.security(syminfo.tickerid, "D", ta.mfi(3)), title="hmfi")
plot(ta.adx(3), title="cadx")
plot(ta.mfi(3), title="cmfi")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hadx = out["series"]["hadx"]
        hmfi = out["series"]["hmfi"]
        # 12 UTC days of hourly bars; last-completed is day 10 while day 11 is forming.
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(11):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # mfi(3) first value at unique index 2 (during day 3); full 3 pairs from day 4.
        assert all(_is_na(x) for x in hmfi[1:48])
        assert any(not _is_na(x) for x in hmfi[48:96])
        day8_adx = hadx[8 * 24 : 9 * 24]
        day8_mfi = hmfi[8 * 24 : 9 * 24]
        assert all(not _is_na(x) for x in day8_adx)
        assert all(not _is_na(x) for x in day8_mfi)
        adx_ref = float(day8_adx[0])
        mfi_ref = float(day8_mfi[0])
        for v in day8_adx:
            assert abs(float(v) - adx_ref) < 1e-9
        for v in day8_mfi:
            assert abs(float(v) - mfi_ref) < 1e-9
        expect_adx = float(CommonIndicators()._adx(daily_highs, daily_lows, daily_closes, 3))
        expect_mfi = float(VolumeIndicators()._mfi(daily_highs, daily_lows, daily_closes, daily_vols, 3))
        assert math.isfinite(expect_adx) and math.isfinite(expect_mfi)
        assert abs(float(hadx[-1]) - expect_adx) < 1e-9
        assert abs(float(hmfi[-1]) - expect_mfi) < 1e-9
        cadx_day8 = out["series"]["cadx"][8 * 24 : 9 * 24]
        cmfi_day8 = out["series"]["cmfi"][8 * 24 : 9 * 24]
        assert any(
            abs(float(hadx[8 * 24 + i]) - float(cadx_day8[i])) > 1e-6 for i in range(24) if not _is_na(cadx_day8[i])
        )
        assert any(
            abs(float(hmfi[8 * 24 + i]) - float(cmfi_day8[i])) > 1e-6 for i in range(24) if not _is_na(cmfi_day8[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_obv_cmf_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 0-arg ta.obv / 1-arg ta.cmf."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.volume import VolumeIndicators

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.obv()), title="hobv")
plot(request.security(syminfo.tickerid, "D", ta.cmf(3)), title="hcmf")
plot(ta.obv(), title="cobv")
plot(ta.cmf(3), title="ccmf")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hobv = out["series"]["hobv"]
        hcmf = out["series"]["hcmf"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # First completed HTF bar at chart 24; obv is 0 until 3 unique samples.
        assert all(_is_na(x) for x in hobv[1:24])
        assert all(_is_na(x) for x in hcmf[1:24])
        day5_obv = hobv[5 * 24 : 6 * 24]
        day5_cmf = hcmf[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_obv)
        assert all(not _is_na(x) for x in day5_cmf)
        obv_ref = float(day5_obv[0])
        cmf_ref = float(day5_cmf[0])
        for v in day5_obv:
            assert abs(float(v) - obv_ref) < 1e-9
        for v in day5_cmf:
            assert abs(float(v) - cmf_ref) < 1e-9
        expect_obv = float(VolumeIndicators()._obv(daily_closes, daily_vols))
        expect_cmf = float(VolumeIndicators()._cmf(daily_closes, daily_highs, daily_lows, daily_vols, 3)[-1])
        assert math.isfinite(expect_obv) and math.isfinite(expect_cmf)
        assert abs(float(hobv[-1]) - expect_obv) < 1e-9
        assert abs(float(hcmf[-1]) - expect_cmf) < 1e-9
        cobv_day5 = out["series"]["cobv"][5 * 24 : 6 * 24]
        ccmf_day5 = out["series"]["ccmf"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hobv[5 * 24 + i]) - float(cobv_day5[i])) > 1e-6 for i in range(24) if not _is_na(cobv_day5[i])
        )
        assert any(
            abs(float(hcmf[5 * 24 + i]) - float(ccmf_day5[i])) > 1e-6 for i in range(24) if not _is_na(ccmf_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_nvi_pvi_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 0-arg ta.nvi / ta.pvi."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        # Oscillate daily volume so nvi (decrease) and pvi (increase) both fire
        # on unique HTF bars; chart-TF still differs (hourly path).
        for i, b in enumerate(bars):
            day = i // 24
            hour = i % 24
            base = 2000.0 if day % 2 == 0 else 800.0
            b["volume"] = base + hour
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.nvi()), title="hnvi")
plot(request.security(syminfo.tickerid, "D", ta.pvi()), title="hpvi")
plot(ta.nvi(), title="cnvi")
plot(ta.pvi(), title="cpvi")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hnvi = out["series"]["hnvi"]
        hpvi = out["series"]["hpvi"]
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # First completed HTF bar at chart 24; nvi/pvi seed 1000 on unique bar 0.
        assert all(_is_na(x) for x in hnvi[1:24])
        assert all(_is_na(x) for x in hpvi[1:24])
        assert abs(float(hnvi[24]) - 1000.0) < 1e-9
        assert abs(float(hpvi[24]) - 1000.0) < 1e-9
        day5_nvi = hnvi[5 * 24 : 6 * 24]
        day5_pvi = hpvi[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_nvi)
        assert all(not _is_na(x) for x in day5_pvi)
        nvi_ref = float(day5_nvi[0])
        pvi_ref = float(day5_pvi[0])
        for v in day5_nvi:
            assert abs(float(v) - nvi_ref) < 1e-9
        for v in day5_pvi:
            assert abs(float(v) - pvi_ref) < 1e-9
        expect_nvi = _nvi_last(daily_closes, daily_vols)
        expect_pvi = _pvi_last(daily_closes, daily_vols)
        assert math.isfinite(expect_nvi) and math.isfinite(expect_pvi)
        assert abs(float(hnvi[-1]) - expect_nvi) < 1e-9
        assert abs(float(hpvi[-1]) - expect_pvi) < 1e-9
        cnvi_day5 = out["series"]["cnvi"][5 * 24 : 6 * 24]
        cpvi_day5 = out["series"]["cpvi"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hnvi[5 * 24 + i]) - float(cnvi_day5[i])) > 1e-6 for i in range(24) if not _is_na(cnvi_day5[i])
        )
        assert any(
            abs(float(hpvi[5 * 24 + i]) - float(cpvi_day5[i])) > 1e-6 for i in range(24) if not _is_na(cpvi_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_accdist_wad_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 0-arg ta.accdist / ta.wad."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.volume import VolumeIndicators

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.accdist()), title="had")
plot(request.security(syminfo.tickerid, "D", ta.wad()), title="hwad")
plot(ta.accdist(), title="cad")
plot(ta.wad(), title="cwad")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        had = out["series"]["had"]
        hwad = out["series"]["hwad"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # First completed HTF bar at chart 24; wad is 0 on unique bar 0.
        assert all(_is_na(x) for x in had[1:24])
        assert all(_is_na(x) for x in hwad[1:24])
        assert abs(float(hwad[24]) - 0.0) < 1e-9
        day5_ad = had[5 * 24 : 6 * 24]
        day5_wad = hwad[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_ad)
        assert all(not _is_na(x) for x in day5_wad)
        ad_ref = float(day5_ad[0])
        wad_ref = float(day5_wad[0])
        for v in day5_ad:
            assert abs(float(v) - ad_ref) < 1e-9
        for v in day5_wad:
            assert abs(float(v) - wad_ref) < 1e-9
        expect_ad = float(VolumeIndicators()._accdist(daily_highs, daily_lows, daily_closes, daily_vols)[-1])
        expect_wad = float(VolumeIndicators()._wad(daily_highs, daily_lows, daily_closes, daily_vols)[-1])
        assert math.isfinite(expect_ad) and math.isfinite(expect_wad)
        assert abs(float(had[-1]) - expect_ad) < 1e-9
        assert abs(float(hwad[-1]) - expect_wad) < 1e-9
        cad_day5 = out["series"]["cad"][5 * 24 : 6 * 24]
        cwad_day5 = out["series"]["cwad"][5 * 24 : 6 * 24]
        assert any(
            abs(float(had[5 * 24 + i]) - float(cad_day5[i])) > 1e-6 for i in range(24) if not _is_na(cad_day5[i])
        )
        assert any(
            abs(float(hwad[5 * 24 + i]) - float(cwad_day5[i])) > 1e-6 for i in range(24) if not _is_na(cwad_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_tr_tsi_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 0-arg ta.tr / 2-arg ta.tsi."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers
        from pynescript.ast.evaluator.builtins.technical_submodules.oscillators import OscillatorIndicators

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.tr()), title="htr")
plot(request.security(syminfo.tickerid, "D", ta.tsi(2, 3)), title="htsi")
plot(ta.tr(), title="ctr")
plot(ta.tsi(2, 3), title="ctsi")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        htr = out["series"]["htr"]
        htsi = out["series"]["htsi"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_closes: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_closes.append(float(chunk[-1]["close"]))
        # First unique HTF bar TR is na; first completed unique at chart 24.
        assert all(_is_na(x) for x in htr[1:24])
        assert _is_na(htr[24])
        # TSI(2, 3) needs 5 unique HTF closes (long+short); unique 4 completes at 120.
        assert all(_is_na(x) for x in htsi[1:120])
        day5_tr = htr[5 * 24 : 6 * 24]
        day5_tsi = htsi[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_tr)
        assert all(not _is_na(x) for x in day5_tsi)
        tr_ref = float(day5_tr[0])
        tsi_ref = float(day5_tsi[0])
        for v in day5_tr:
            assert abs(float(v) - tr_ref) < 1e-9
        for v in day5_tsi:
            assert abs(float(v) - tsi_ref) < 1e-9
        expect_tr = TechnicalHelpers()._tr(daily_highs, daily_lows, daily_closes)[-1]
        expect_tsi = OscillatorIndicators()._tsi(daily_closes, 3, 2)
        assert expect_tr is not None and math.isfinite(float(expect_tr))
        assert expect_tsi is not None and math.isfinite(float(expect_tsi))
        assert abs(float(htr[-1]) - float(expect_tr)) < 1e-9
        assert abs(float(htsi[-1]) - float(expect_tsi)) < 1e-9
        ctr_day5 = out["series"]["ctr"][5 * 24 : 6 * 24]
        ctsi_day5 = out["series"]["ctsi"][5 * 24 : 6 * 24]
        assert any(
            abs(float(htr[5 * 24 + i]) - float(ctr_day5[i])) > 1e-6 for i in range(24) if not _is_na(ctr_day5[i])
        )
        assert any(
            abs(float(htsi[5 * 24 + i]) - float(ctsi_day5[i])) > 1e-6 for i in range(24) if not _is_na(ctsi_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_bbw_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 2-arg / 3-arg ta.bbw."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.bbw(close, 3, 2)), title="hbbw")
plot(request.security(syminfo.tickerid, "D", ta.bbw(3, 2)), title="hbbw2")
plot(ta.bbw(close, 3, 2), title="cbbw")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hbbw = out["series"]["hbbw"]
        hbbw2 = out["series"]["hbbw2"]
        daily_closes: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
        # SMA/stdev(3) defined at unique 2; unique 2 completes at chart 72.
        assert all(_is_na(x) for x in hbbw[1:72])
        assert all(_is_na(x) for x in hbbw2[1:72])
        day5_bbw = hbbw[5 * 24 : 6 * 24]
        day5_bbw2 = hbbw2[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_bbw)
        assert all(not _is_na(x) for x in day5_bbw2)
        bbw_ref = float(day5_bbw[0])
        for v in day5_bbw:
            assert abs(float(v) - bbw_ref) < 1e-9
        for v in day5_bbw2:
            assert abs(float(v) - bbw_ref) < 1e-9
        helpers = TechnicalHelpers()
        mid = helpers._sma(daily_closes, 3)[-1]
        sd = helpers._stdev(daily_closes, 3)
        assert mid is not None and sd is not None and float(mid) != 0.0
        expect_bbw = 2.0 * 2.0 * float(sd) / float(mid)
        assert math.isfinite(expect_bbw)
        assert abs(float(hbbw[-1]) - expect_bbw) < 1e-9
        assert abs(float(hbbw2[-1]) - expect_bbw) < 1e-9
        cbbw_day5 = out["series"]["cbbw"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hbbw[5 * 24 + i]) - float(cbbw_day5[i])) > 1e-6 for i in range(24) if not _is_na(cbbw_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_stoch_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 1-arg / 2-arg ta.stoch %K."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.stoch(3)), title="hstoch")
plot(request.security(syminfo.tickerid, "D", ta.stoch(3, 2)), title="hstoch2")
plot(ta.stoch(3), title="cstoch")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hstoch = out["series"]["hstoch"]
        hstoch2 = out["series"]["hstoch2"]
        daily_closes: list[float] = []
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
        # stoch(3) defined at unique 2; unique 2 completes at chart 72.
        assert all(_is_na(x) for x in hstoch[1:72])
        assert all(_is_na(x) for x in hstoch2[1:72])
        day5_stoch = hstoch[5 * 24 : 6 * 24]
        day5_stoch2 = hstoch2[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_stoch)
        assert all(not _is_na(x) for x in day5_stoch2)
        stoch_ref = float(day5_stoch[0])
        for v in day5_stoch:
            assert abs(float(v) - stoch_ref) < 1e-9
        for v in day5_stoch2:
            assert abs(float(v) - stoch_ref) < 1e-9
        win_h = daily_highs[-3:]
        win_l = daily_lows[-3:]
        hh = max(win_h)
        ll = min(win_l)
        expect_stoch = 50.0 if hh == ll else 100.0 * (daily_closes[-1] - ll) / (hh - ll)
        assert math.isfinite(expect_stoch)
        assert abs(float(hstoch[-1]) - expect_stoch) < 1e-9
        assert abs(float(hstoch2[-1]) - expect_stoch) < 1e-9
        cstoch_day5 = out["series"]["cstoch"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hstoch[5 * 24 + i]) - float(cstoch_day5[i])) > 1e-6
            for i in range(24)
            if not _is_na(cstoch_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_pivot_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 2-arg pivothigh / pivotlow."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        # Force a daily pivot at unique[4] (day 4) so left=2, right=2 confirms
        # once unique[6] completes (chart bar 168 = start of forming day 7).
        for b in bars[4 * 24 : 5 * 24]:
            b["high"] = float(b["high"]) + 200.0
            b["low"] = max(float(b["low"]) - 200.0, 0.01)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.pivothigh(2, 2)), title="hph")
plot(request.security(syminfo.tickerid, "D", ta.pivotlow(2, 2)), title="hpl")
plot(ta.pivothigh(2, 2), title="cph")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hph = out["series"]["hph"]
        hpl = out["series"]["hpl"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
        # pivot(2,2) needs 5 unique HTF bars; unique 4 completes at chart 120,
        # but the day-4 extreme confirms only after unique 6 (chart 168).
        assert all(_is_na(x) for x in hph[1:168])
        assert all(_is_na(x) for x in hpl[1:168])
        day7_ph = hph[7 * 24 :]
        day7_pl = hpl[7 * 24 :]
        assert all(not _is_na(x) for x in day7_ph)
        assert all(not _is_na(x) for x in day7_pl)
        ph_ref = float(day7_ph[0])
        pl_ref = float(day7_pl[0])
        for v in day7_ph:
            assert abs(float(v) - ph_ref) < 1e-9
        for v in day7_pl:
            assert abs(float(v) - pl_ref) < 1e-9
        expect_ph = _expect_pivot_confirm(daily_highs, 2, 2, is_high=True)
        expect_pl = _expect_pivot_confirm(daily_lows, 2, 2, is_high=False)
        assert expect_ph is not None and math.isfinite(expect_ph)
        assert expect_pl is not None and math.isfinite(expect_pl)
        assert abs(float(hph[-1]) - expect_ph) < 1e-9
        assert abs(float(hpl[-1]) - expect_pl) < 1e-9
        cph_day7 = out["series"]["cph"][7 * 24 :]
        assert any(
            abs(float(hph[7 * 24 + i]) - float(cph_day7[i])) > 1e-6
            for i in range(len(day7_ph))
            if not _is_na(cph_day7[i])
        ) or all(_is_na(x) for x in cph_day7)
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_percentile_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 3-arg percentile TA."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.percentile_nearest_rank(close, 3, 50)), title="hpnr")
plot(request.security(syminfo.tickerid, "D", ta.percentile_linear_interpolation(close, 3, 25)), title="hpli")
plot(ta.percentile_nearest_rank(close, 3, 50), title="cpnr")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hpnr = out["series"]["hpnr"]
        hpli = out["series"]["hpli"]
        daily_closes: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
        # period=3 defined at unique 2; unique 2 completes at chart 72.
        assert all(_is_na(x) for x in hpnr[1:72])
        assert all(_is_na(x) for x in hpli[1:72])
        day5_pnr = hpnr[5 * 24 : 6 * 24]
        day5_pli = hpli[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_pnr)
        assert all(not _is_na(x) for x in day5_pli)
        pnr_ref = float(day5_pnr[0])
        pli_ref = float(day5_pli[0])
        for v in day5_pnr:
            assert abs(float(v) - pnr_ref) < 1e-9
        for v in day5_pli:
            assert abs(float(v) - pli_ref) < 1e-9
        win = daily_closes[-3:]
        sorted_w = sorted(win)
        n = len(sorted_w)
        rank_nr = max(1, int((50.0 / 100.0) * n + 0.999999))
        rank_nr = min(rank_nr, n)
        expect_pnr = float(sorted_w[rank_nr - 1])
        rank_lin = (25.0 / 100.0) * (n - 1)
        lo = int(rank_lin)
        hi = min(lo + 1, n - 1)
        frac = rank_lin - lo
        expect_pli = float(sorted_w[lo]) * (1.0 - frac) + float(sorted_w[hi]) * frac
        assert math.isfinite(expect_pnr)
        assert math.isfinite(expect_pli)
        assert abs(float(hpnr[-1]) - expect_pnr) < 1e-9
        assert abs(float(hpli[-1]) - expect_pli) < 1e-9
        cpnr_day5 = out["series"]["cpnr"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hpnr[5 * 24 + i]) - float(cpnr_day5[i])) > 1e-6 for i in range(24) if not _is_na(cpnr_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_dpo_crossover_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 1-arg dpo / OHLCV cross."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.dpo(3)), title="hdpo")
plot(request.security(syminfo.tickerid, "D", ta.crossover(close, open)), title="hxo")
plot(request.security(syminfo.tickerid, "D", ta.crossunder(close, open)), title="hxu")
plot(ta.dpo(3), title="cdpo")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hdpo = out["series"]["hdpo"]
        hxo = out["series"]["hxo"]
        hxu = out["series"]["hxu"]
        daily_opens: list[float] = []
        daily_closes: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_opens.append(float(chunk[0]["open"]))
            daily_closes.append(float(chunk[-1]["close"]))
        # dpo(3) needs 3 unique HTF samples; unique 2 completes at chart 72.
        # crossover needs 2 unique samples; unique 1 completes at chart 48.
        assert all(_is_na(x) for x in hdpo[1:72])
        assert all(_is_na(x) for x in hxo[1:48])
        assert all(_is_na(x) for x in hxu[1:48])
        day5_dpo = hdpo[5 * 24 : 6 * 24]
        day5_xo = hxo[5 * 24 : 6 * 24]
        day5_xu = hxu[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_dpo)
        assert all(not _is_na(x) for x in day5_xo)
        assert all(not _is_na(x) for x in day5_xu)
        dpo_ref = float(day5_dpo[0])
        xo_ref = float(day5_xo[0])
        xu_ref = float(day5_xu[0])
        for v in day5_dpo:
            assert abs(float(v) - dpo_ref) < 1e-9
        for v in day5_xo:
            assert abs(float(v) - xo_ref) < 1e-9
        for v in day5_xu:
            assert abs(float(v) - xu_ref) < 1e-9
        win = daily_closes[-3:]
        sma = sum(win) / 3.0
        disp = 3 // 2 + 1
        expect_dpo = daily_closes[-disp] - sma
        assert math.isfinite(expect_dpo)
        assert abs(float(hdpo[-1]) - expect_dpo) < 1e-9
        pa, pb = daily_closes[-2], daily_opens[-2]
        ca, cb = daily_closes[-1], daily_opens[-1]
        expect_xo = 1.0 if (pa <= pb and ca > cb) else 0.0
        expect_xu = 1.0 if (pa >= pb and ca < cb) else 0.0
        assert abs(float(hxo[-1]) - expect_xo) < 1e-9
        assert abs(float(hxu[-1]) - expect_xu) < 1e-9
        cdpo_day5 = out["series"]["cdpo"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hdpo[5 * 24 + i]) - float(cdpo_day5[i])) > 1e-6 for i in range(24) if not _is_na(cdpo_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_correlation_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 3-arg OHLCV correlation."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.correlation(close, volume, 3)), title="hcorr")
plot(ta.correlation(close, volume, 3), title="ccorr")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hcorr = out["series"]["hcorr"]
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # correlation(3) needs 3 unique HTF samples; unique 2 completes at chart 72.
        assert all(_is_na(x) for x in hcorr[1:72])
        day5_corr = hcorr[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_corr)
        corr_ref = float(day5_corr[0])
        for v in day5_corr:
            assert abs(float(v) - corr_ref) < 1e-9
        xs = daily_closes[-3:]
        ys = daily_vols[-3:]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        denx = sum((x - mx) ** 2 for x in xs) ** 0.5
        deny = sum((y - my) ** 2 for y in ys) ** 0.5
        expect_corr = num / (denx * deny)
        assert math.isfinite(expect_corr)
        assert abs(float(hcorr[-1]) - expect_corr) < 1e-9
        ccorr_day5 = out["series"]["ccorr"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hcorr[5 * 24 + i]) - float(ccorr_day5[i])) > 1e-6 for i in range(24) if not _is_na(ccorr_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_dpo2_cross_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 2-arg dpo / OHLCV ta.cross."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.dpo(close, 3)), title="hdpo")
plot(request.security(syminfo.tickerid, "D", ta.dpo(open, 3)), title="hdpoo")
plot(request.security(syminfo.tickerid, "D", ta.cross(close, open)), title="hx")
plot(ta.dpo(3), title="cdpo")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hdpo = out["series"]["hdpo"]
        hdpoo = out["series"]["hdpoo"]
        hx = out["series"]["hx"]
        daily_opens: list[float] = []
        daily_closes: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_opens.append(float(chunk[0]["open"]))
            daily_closes.append(float(chunk[-1]["close"]))
        # dpo(3) needs 3 unique HTF samples; unique 2 completes at chart 72.
        # ta.cross needs 2 unique samples; unique 1 completes at chart 48.
        assert all(_is_na(x) for x in [*hdpo[1:72], *hdpoo[1:72], *hx[1:48]])
        day5_dpo = hdpo[5 * 24 : 6 * 24]
        day5_dpoo = hdpoo[5 * 24 : 6 * 24]
        day5_x = hx[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in [*day5_dpo, *day5_dpoo, *day5_x])
        dpo_ref, dpoo_ref, x_ref = float(day5_dpo[0]), float(day5_dpoo[0]), float(day5_x[0])
        for series, ref in ((day5_dpo, dpo_ref), (day5_dpoo, dpoo_ref), (day5_x, x_ref)):
            for v in series:
                assert abs(float(v) - ref) < 1e-9
        disp = 3 // 2 + 1
        expect_dpo = daily_closes[-disp] - sum(daily_closes[-3:]) / 3.0
        expect_dpoo = daily_opens[-disp] - sum(daily_opens[-3:]) / 3.0
        assert math.isfinite(expect_dpo) and math.isfinite(expect_dpoo)
        assert abs(float(hdpo[-1]) - expect_dpo) < 1e-9
        assert abs(float(hdpoo[-1]) - expect_dpoo) < 1e-9
        pa, pb = daily_closes[-2], daily_opens[-2]
        ca, cb = daily_closes[-1], daily_opens[-1]
        expect_x = 1.0 if ((pa <= pb and ca > cb) or (pa >= pb and ca < cb)) else 0.0
        assert abs(float(hx[-1]) - expect_x) < 1e-9
        cdpo_day5 = out["series"]["cdpo"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hdpo[5 * 24 + i]) - float(cdpo_day5[i])) > 1e-6 for i in range(24) if not _is_na(cdpo_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_vpt_wvad_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 0-arg ta.vpt / 1-arg ta.wvad."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.volume import VolumeIndicators

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.vpt()), title="hvpt")
plot(request.security(syminfo.tickerid, "D", ta.pvt()), title="hpvt")
plot(request.security(syminfo.tickerid, "D", ta.wvad(3)), title="hwvad")
plot(ta.vpt(), title="cvpt")
plot(ta.wvad(3), title="cwvad")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hvpt = out["series"]["hvpt"]
        hpvt = out["series"]["hpvt"]
        hwvad = out["series"]["hwvad"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_closes: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_closes.append(float(chunk[-1]["close"]))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # First completed HTF bar at chart 24; vpt seeds 0.0 on unique bar 0.
        assert all(_is_na(x) for x in hvpt[1:24])
        assert all(_is_na(x) for x in hwvad[1:24])
        assert abs(float(hvpt[24]) - 0.0) < 1e-9
        assert abs(float(hpvt[24]) - 0.0) < 1e-9
        day5_vpt = hvpt[5 * 24 : 6 * 24]
        day5_pvt = hpvt[5 * 24 : 6 * 24]
        day5_wvad = hwvad[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_vpt)
        assert all(not _is_na(x) for x in day5_pvt)
        assert all(not _is_na(x) for x in day5_wvad)
        vpt_ref = float(day5_vpt[0])
        wvad_ref = float(day5_wvad[0])
        for v in day5_vpt:
            assert abs(float(v) - vpt_ref) < 1e-9
        for v in day5_pvt:
            assert abs(float(v) - vpt_ref) < 1e-9
        for v in day5_wvad:
            assert abs(float(v) - wvad_ref) < 1e-9
        expect_vpt = float(VolumeIndicators()._vpt(daily_closes, daily_vols))
        expect_wvad = float(VolumeIndicators()._wvad(daily_highs, daily_lows, daily_closes, daily_vols, 3)[-1])
        assert math.isfinite(expect_vpt) and math.isfinite(expect_wvad)
        assert abs(float(hvpt[-1]) - expect_vpt) < 1e-9
        assert abs(float(hpvt[-1]) - expect_vpt) < 1e-9
        assert abs(float(hwvad[-1]) - expect_wvad) < 1e-9
        cvpt_day5 = out["series"]["cvpt"][5 * 24 : 6 * 24]
        cwvad_day5 = out["series"]["cwvad"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hvpt[5 * 24 + i]) - float(cvpt_day5[i])) > 1e-6 for i in range(24) if not _is_na(cvpt_day5[i])
        )
        assert any(
            abs(float(hwvad[5 * 24 + i]) - float(cwvad_day5[i])) > 1e-6 for i in range(24) if not _is_na(cwvad_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_uo_apo_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 3-arg ta.uo / 3-arg ta.apo."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers
        from pynescript.ast.evaluator.builtins.technical_submodules.volume import VolumeIndicators

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.uo(2, 3, 4)), title="huo")
plot(request.security(syminfo.tickerid, "D", ta.apo(close, 2, 3)), title="hapo")
plot(ta.uo(2, 3, 4), title="cuo")
plot(ta.apo(close, 2, 3), title="capo")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        huo = out["series"]["huo"]
        hapo = out["series"]["hapo"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_closes: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_closes.append(float(chunk[-1]["close"]))
        # uo(2,3,4) needs n > 4 unique HTF bars; unique 4 completes at chart 120.
        # apo EMA(slow=3) seeds at unique index 2; unique 2 completes at chart 72.
        assert all(_is_na(x) for x in huo[1:120])
        assert all(_is_na(x) for x in hapo[1:72])
        day5_uo = huo[5 * 24 : 6 * 24]
        day5_apo = hapo[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_uo)
        assert all(not _is_na(x) for x in day5_apo)
        uo_ref = float(day5_uo[0])
        apo_ref = float(day5_apo[0])
        for v in day5_uo:
            assert abs(float(v) - uo_ref) < 1e-9
        for v in day5_apo:
            assert abs(float(v) - apo_ref) < 1e-9
        expect_uo = TechnicalHelpers()._uo_last(daily_highs, daily_lows, daily_closes, 2, 3, 4)
        expect_apo = VolumeIndicators()._apo(daily_closes, 2, 3)[-1]
        assert expect_uo is not None and expect_apo is not None
        assert math.isfinite(float(expect_uo)) and math.isfinite(float(expect_apo))
        assert abs(float(huo[-1]) - float(expect_uo)) < 1e-9
        assert abs(float(hapo[-1]) - float(expect_apo)) < 1e-9
        cuo_day5 = out["series"]["cuo"][5 * 24 : 6 * 24]
        capo_day5 = out["series"]["capo"][5 * 24 : 6 * 24]
        assert any(
            abs(float(huo[5 * 24 + i]) - float(cuo_day5[i])) > 1e-6 for i in range(24) if not _is_na(cuo_day5[i])
        )
        assert any(
            abs(float(hapo[5 * 24 + i]) - float(capo_day5[i])) > 1e-6 for i in range(24) if not _is_na(capo_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False

    def test_htf_emv_hourly_to_daily_last_completed(self) -> None:
        """Hourly chart + request D: last-completed daily 1-arg ta.emv."""
        from backend.runtime import Runtime
        from pynescript.ast.evaluator.builtins.technical_submodules.volume import VolumeIndicators

        bars = _day_aligned_hourly(24 * 8)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "D", ta.emv(3)), title="hemv")
plot(ta.emv(3), title="cemv")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        hemv = out["series"]["hemv"]
        daily_highs: list[float] = []
        daily_lows: list[float] = []
        daily_vols: list[float] = []
        for d in range(7):
            chunk = bars[24 * d : 24 * (d + 1)]
            daily_highs.append(max(float(b["high"]) for b in chunk))
            daily_lows.append(min(float(b["low"]) for b in chunk))
            daily_vols.append(sum(float(b["volume"]) for b in chunk))
        # emv(3) needs 3 valid unique HTF samples; bar 0 is na so unique 3
        # completes at chart 96.
        assert all(_is_na(x) for x in hemv[1:96])
        day5_emv = hemv[5 * 24 : 6 * 24]
        assert all(not _is_na(x) for x in day5_emv)
        emv_ref = float(day5_emv[0])
        for v in day5_emv:
            assert abs(float(v) - emv_ref) < 1e-9
        expect_emv = VolumeIndicators()._emv(daily_highs, daily_lows, daily_vols, 3)
        assert expect_emv is not None
        assert math.isfinite(float(expect_emv))
        assert abs(float(hemv[-1]) - float(expect_emv)) < 1e-9
        cemv_day5 = out["series"]["cemv"][5 * 24 : 6 * 24]
        assert any(
            abs(float(hemv[5 * 24 + i]) - float(cemv_day5[i])) > 1e-6 for i in range(24) if not _is_na(cemv_day5[i])
        )
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})
        assert pol.get("htf_reeval") is False


class TestRequestSecurityHonestyMeta:
    """Runtime metadata + documented no-crash behavior for limited security surface."""

    def test_gaps_lookahead_accepted_unused_and_meta(self) -> None:
        """barmerge.gaps_* / lookahead_* must not crash; lookahead_on is honored."""
        from backend.runtime import Runtime

        # Aligned 1m bars for 60m HTF resample.
        hour0 = 1_700_000_000_000
        hour0 -= hour0 % 3_600_000
        bars: list[dict] = []
        price = 100.0
        for i in range(120):
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
                    "time": hour0 + i * 60_000,
                    "volume": 1000.0 + i,
                }
            )
            price = c
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on)
plot(v, title="sec")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        # lookahead_on reads the forming HTF bucket: last bar → last chart close.
        assert abs(float(out["series"]["sec"][-1]) - float(bars[-1]["close"])) < 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("htf_reeval") is False
        assert pol.get("gaps_supported") is False
        assert pol.get("lookahead_supported") is True
        policies = pol.get("policies") or {}
        assert "gaps_lookahead_provided" in policies
        assert "lookahead_applied" in policies
        assert "htf_ohlcv_resample" in policies
        notes = pol.get("notes") or []
        assert any("lookahead" in str(n).lower() for n in notes)
        assert any("gaps" in str(n).lower() for n in notes)

    def test_complex_htf_na_recorded_in_meta(self) -> None:
        from backend.runtime import Runtime

        # UDF returns structure flags (-1/0/1), not OHLCV-like prices — must
        # not be mistaken for simple chart passthrough by the OHLCV heuristic.
        src = """//@version=6
indicator("t")
f_struct(len) =>
    hh = ta.highest(high, len)
    ll = ta.lowest(low, len)
    hhUp = hh > hh[len]
    llUp = ll > ll[len]
    hhUp and llUp ? 1 : not hhUp and not llUp ? -1 : 0
plot(request.security(syminfo.tickerid, "60", f_struct(10)), title="htf")
"""
        out = Runtime(symbol="AAPL").run(src, _bars(40), mode="interpret")
        assert not out.get("error"), out.get("error")
        assert all(_is_na(x) for x in out["series"]["htf"])
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("htf_reeval") is False
        assert "complex_htf_na" in (pol.get("policies") or {})
        assert int(pol.get("calls") or 0) >= 1

    def test_foreign_na_recorded_in_meta(self) -> None:
        from backend.runtime import Runtime

        src = """//@version=6
indicator("t")
plot(request.security("MSFT", "D", close), title="ms")
"""
        out = Runtime(symbol="AAPL").run(src, _bars(20), mode="interpret")
        assert not out.get("error"), out.get("error")
        assert all(_is_na(x) for x in out["series"]["ms"])
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "foreign_na" in (pol.get("policies") or {})

    def test_same_tf_security_allows_chart_eval_meta(self) -> None:
        from backend.runtime import Runtime

        # Daily-spaced bars match default Runtime timeframe.period "D".
        bars = _daily_bars(30)
        src = """//@version=6
indicator("t")
// Default Runtime chart period is "D" — same TF as request
plot(request.security(syminfo.tickerid, "D", close), title="sec")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert out["series"]["sec"][-1] == out["series"]["c"][-1]
        pol = (out.get("meta") or {}).get("request_security") or {}
        policies = pol.get("policies") or {}
        assert "same_tf_chart_eval" in policies
        assert "complex_htf_na" not in policies
        assert "htf_ohlcv_resample" not in policies

    def test_standalone_handler_policy_state(self) -> None:
        """Direct handler path also records policy (unit-eval demos)."""
        ev = NodeLiteralEvaluator()
        result = ev._handle_request_security(["AAPL", "D", "close"])
        assert isinstance(result, list)
        state = getattr(ev, "_request_security_policy", None)
        assert isinstance(state, dict)
        assert state.get("htf_reeval") is False
        assert "legacy_mock_ohlcv" in (state.get("policies") or {})

    def test_barmerge_constants_resolve(self) -> None:
        """barmerge.* constants are wired (True/False) for gaps/lookahead merge args."""
        assert _eval(NodeLiteralEvaluator(), "barmerge.lookahead_on") is True
        assert _eval(NodeLiteralEvaluator(), "barmerge.lookahead_off") is False
        assert _eval(NodeLiteralEvaluator(), "barmerge.gaps_on") is True
        assert _eval(NodeLiteralEvaluator(), "barmerge.gaps_off") is False


def _hour_bars(n: int = 180) -> list[dict]:
    """Aligned 1m bars starting on an hour boundary (3 full hours)."""
    hour0 = 1_700_000_000_000
    hour0 -= hour0 % 3_600_000
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
                "time": hour0 + i * 60_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _is_na(v: object) -> bool:
    """Series layer stores na as None or float nan."""
    return v is None or (isinstance(v, float) and v != v)


class TestRequestSecurityBarmerge:
    """gaps_on / lookahead_on on the HTF resample paths (reference barmerge)."""

    def test_gaps_on_ohlcv_only_bucket_starts(self) -> None:
        """gaps_on close: previous hour close on hour-open bars, na elsewhere."""
        from backend.runtime import Runtime

        bars = _hour_bars()
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", close, barmerge.gaps_on, barmerge.lookahead_off)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert len(sec) == len(bars)
        # First hour: no completed bucket yet → all na (bar 0 excepted: with a
        # single bar the HTF-vs-chart inference falls back to chart period and
        # takes the passthrough stub — pre-existing edge, same as gaps_off).
        assert all(_is_na(v) for v in sec[1:60])
        # Hour opens (bars 60, 120) carry the previous hour's final close.
        assert abs(float(sec[60]) - float(bars[59]["close"])) < 1e-9
        assert abs(float(sec[120]) - float(bars[119]["close"])) < 1e-9
        # Mid-hour bars are na.
        assert all(_is_na(v) for v in sec[61:120])
        assert all(_is_na(v) for v in sec[121:])
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("gaps_supported") is True
        assert pol.get("lookahead_supported") is False
        assert "gaps_applied" in (pol.get("policies") or {})

    def test_lookahead_on_ohlcv_forming_bucket(self) -> None:
        """lookahead_on: each hour's final close/high is visible from the hour start."""
        from backend.runtime import Runtime

        bars = _hour_bars()
        src = """//@version=6
indicator("t")
c = request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on)
h = request.security(syminfo.tickerid, "60", high, barmerge.gaps_off, barmerge.lookahead_on)
plot(c, title="sec_c")
plot(h, title="sec_h")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec_c = out["series"]["sec_c"]
        sec_h = out["series"]["sec_h"]
        for i in (0, 30, 59):
            assert abs(float(sec_c[i]) - float(bars[59]["close"])) < 1e-9
        for i in (60, 90, 119):
            assert abs(float(sec_c[i]) - float(bars[119]["close"])) < 1e-9
        hour0_high = max(float(b["high"]) for b in bars[0:60])
        hour1_high = max(float(b["high"]) for b in bars[60:120])
        for i in (0, 30, 59):
            assert abs(float(sec_h[i]) - hour0_high) < 1e-9
        for i in (60, 61, 119):
            assert abs(float(sec_h[i]) - hour1_high) < 1e-9

    def test_gaps_and_lookahead_combined(self) -> None:
        """gaps_on + lookahead_on: final bucket value on period starts, including bar 0."""
        from backend.runtime import Runtime

        bars = _hour_bars()
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", close, barmerge.gaps_on, barmerge.lookahead_on)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert abs(float(sec[0]) - float(bars[59]["close"])) < 1e-9
        assert abs(float(sec[60]) - float(bars[119]["close"])) < 1e-9
        assert abs(float(sec[120]) - float(bars[179]["close"])) < 1e-9
        assert all(_is_na(v) for v in sec[1:60])
        assert all(_is_na(v) for v in sec[61:120])

    def test_gaps_on_simple_ta(self) -> None:
        """gaps_on ta.sma: HTF SMA on bucket starts, na elsewhere."""
        from backend.runtime import Runtime

        bars = _hour_bars(300)  # 5 hours → completed HTF bars for sma(3)
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", ta.sma(close, 3), barmerge.gaps_on, barmerge.lookahead_off)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        # sma(3) needs 3 completed hours → first value at hour-3 open (bar 180).
        # (sec[0] excepted: single-bar HTF inference takes the passthrough stub.)
        assert all(_is_na(v) for v in sec[1:180])
        h2 = float(bars[119]["close"])
        h3 = float(bars[179]["close"])
        h4 = float(bars[239]["close"])
        expect_180 = (float(bars[59]["close"]) + h2 + h3) / 3.0
        expect_240 = (h2 + h3 + h4) / 3.0
        assert abs(float(sec[180]) - expect_180) < 1e-9
        assert abs(float(sec[240]) - expect_240) < 1e-9
        assert all(_is_na(v) for v in sec[181:240])
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "htf_simple_ta_resample" in (pol.get("policies") or {})

    def test_lookahead_on_simple_ta_developing(self) -> None:
        """lookahead_on ta.sma: current period's final HTF SMA from the period start."""
        from backend.runtime import Runtime

        bars = _hour_bars(300)
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", ta.sma(close, 3), barmerge.gaps_off, barmerge.lookahead_on)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        expect_120 = (float(bars[59]["close"]) + float(bars[119]["close"]) + float(bars[179]["close"])) / 3.0
        assert abs(float(sec[120]) - expect_120) < 1e-9
        assert abs(float(sec[130]) - expect_120) < 1e-9

    def test_gaps_unused_on_passthrough_paths(self) -> None:
        """gaps_on with same-TF passthrough: provided but not applied."""
        from backend.runtime import Runtime

        bars = _hour_bars(60)
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "1", close, barmerge.gaps_on, barmerge.lookahead_off)
plot(v, title="sec")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert out["series"]["sec"][-1] == out["series"]["c"][-1]
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("gaps_supported") is False
        policies = pol.get("policies") or {}
        assert "gaps_lookahead_provided" in policies
        assert "gaps_applied" not in policies

    def test_same_tf_close_offset_is_chart_history(self) -> None:
        """Same-TF ``close[1]`` is the previous chart close, not na."""
        from backend.runtime import Runtime

        bars = _hour_bars(60)
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "1", close[1])
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert abs(float(sec[-1]) - float(bars[-2]["close"])) < 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        policies = pol.get("policies") or {}
        assert "same_tf_chart_eval" in policies or "chart_passthrough_htf_stub" in policies

    def test_lookahead_on_close_offset_is_previous_htf_bar(self) -> None:
        """``close[1]`` + lookahead_on is the previous HTF bar (non-repaint pattern)."""
        from backend.runtime import Runtime

        bars = _hour_bars()
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", close[1], barmerge.gaps_off, barmerge.lookahead_on)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert all(_is_na(v) for v in sec[0:60])
        for i in (60, 90, 119):
            assert abs(float(sec[i]) - float(bars[59]["close"])) < 1e-9
        for i in (120, 150, 179):
            assert abs(float(sec[i]) - float(bars[119]["close"])) < 1e-9

    def test_session_update_last_bar_refreshes_lookahead_high(self) -> None:
        """In-place last-bar ticks must invalidate the HTF cache."""
        from pynescript.runtime import Runtime as HostRuntime

        bars = _hour_bars(30)
        src = """//@version=6
indicator("t")
h = request.security(syminfo.tickerid, "60", high, barmerge.gaps_off, barmerge.lookahead_on)
plot(h, title="sec_h")
"""
        rt = HostRuntime(symbol="AAPL")
        sess = rt.create_session(src, bars, mode="interpret")
        out0 = sess.result()
        assert not out0.get("error"), out0.get("error")
        base = float(out0["series"]["sec_h"][-1])
        tick = dict(bars[-1])
        tick["high"] = base + 50.0
        out1 = sess.update_last_bar(tick)
        assert not out1.get("error"), out1.get("error")
        assert float(out1["series"]["sec_h"][-1]) == tick["high"]

    def test_weekly_htf_follows_monday_calendar(self) -> None:
        """Bare W security buckets ISO Monday weeks, not Thursday-epoch widths."""
        from backend.runtime import Runtime

        # Thu 2024-01-04, Fri 01-05, Mon 01-08, Tue 01-09 (daily bars at noon UTC).
        days = [
            (2024, 1, 4, 10.0),
            (2024, 1, 5, 20.0),
            (2024, 1, 8, 30.0),
            (2024, 1, 9, 40.0),
        ]
        bars = []
        for y, m, d, c in days:
            ts = int(datetime(y, m, d, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)
            bars.append({"time": ts, "open": c, "high": c, "low": c, "close": c, "volume": 1000.0})
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "W", close)
plot(v, title="sec")
plot(timeframe.change("W") ? 1 : 0, "chg")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        chg = out["series"]["chg"]
        sec = out["series"]["sec"]
        assert float(chg[2]) == 1.0  # Monday
        assert float(chg[3]) == 0.0
        # Monday opens a new week: last completed weekly close is Friday's 20.
        assert abs(float(sec[2]) - 20.0) < 1e-9
        assert abs(float(sec[3]) - 20.0) < 1e-9


def _nvi_last(closes: list[float], volumes: list[float]) -> float:
    """Oracle matching ``_nvi_inc_update`` last sample on unique bars."""
    nvi = 1000.0
    prev_c: float | None = None
    prev_v: float | None = None
    started = False
    for close, vol in zip(closes, volumes, strict=True):
        cf = float(close)
        vv = 0.0 if vol is None else float(vol)
        if not started:
            started = True
            prev_c = cf
            prev_v = vv
            continue
        if prev_c is not None:
            close_change = 0.0 if prev_c == 0.0 else (cf - prev_c) / prev_c
            pv = 0.0 if prev_v is None else float(prev_v)
            if vv < pv:
                nvi = nvi * (1.0 + close_change)
        prev_c = cf
        prev_v = vv
    return nvi


def _pvi_last(closes: list[float], volumes: list[float]) -> float:
    """Oracle matching ``_pvi_inc_update`` last sample on unique bars."""
    pvi = 1000.0
    prev_c: float | None = None
    prev_v: float | None = None
    started = False
    for close, vol in zip(closes, volumes, strict=True):
        cf = float(close)
        vv = 0.0 if vol is None else float(vol)
        if not started:
            started = True
            prev_c = cf
            prev_v = vv
            continue
        if prev_c is not None:
            close_change = 0.0 if prev_c == 0.0 else (cf - prev_c) / prev_c
            pv = 0.0 if prev_v is None else float(prev_v)
            if vv > pv:
                pvi = pvi * (1.0 + close_change)
        prev_c = cf
        prev_v = vv
    return pvi


def _utc_day0_ms() -> int:
    day0 = 1_700_000_000_000
    return day0 - day0 % 86_400_000


def _day_aligned_hourly(n: int = 72, start: float = 100.0) -> list[dict]:
    """Hourly bars starting on a UTC day boundary (3 days when n=72)."""
    day0 = _utc_day0_ms()
    bars: list[dict] = []
    price = start
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
                "time": day0 + i * 3_600_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


class _DailyHtfProvider:
    """Honors interval: daily OHLCV with timestamps (unlike ChartOHLCVProvider)."""

    def __init__(self, daily_bars: list[dict], symbol: str = "AAPL"):
        self._bars = list(daily_bars)
        self._symbol = str(symbol).upper()

    def fetch(self, symbol: str, period: str = "1d", interval: str = "1d") -> dict:
        _ = period, interval, symbol
        bars = self._bars
        return {
            "open": [float(b["open"]) for b in bars],
            "high": [float(b["high"]) for b in bars],
            "low": [float(b["low"]) for b in bars],
            "close": [float(b["close"]) for b in bars],
            "volume": [float(b.get("volume", 0.0)) for b in bars],
            "time": [b["time"] for b in bars],
            "symbol": self._symbol,
        }


class _ChartLengthStubProvider:
    """ChartOHLCVProvider-like: ignores interval, returns the chart bars."""

    def __init__(self, bars: list[dict], symbol: str = "AAPL"):
        self._bars = list(bars)
        self._symbol = str(symbol).upper()

    def fetch(self, symbol: str, period: str = "1d", interval: str = "1d") -> dict:
        _ = period, interval, symbol
        bars = self._bars
        return {
            "open": [float(b["open"]) for b in bars],
            "high": [float(b["high"]) for b in bars],
            "low": [float(b["low"]) for b in bars],
            "close": [float(b["close"]) for b in bars],
            "volume": [float(b.get("volume", 0.0)) for b in bars],
            "time": [b.get("time", 0) for b in bars],
            "symbol": self._symbol,
        }


def _daily_provider_bars(closes: tuple[float, ...] = (111.0, 222.0, 333.0)) -> list[dict]:
    day0 = _utc_day0_ms()
    out: list[dict] = []
    for i, c in enumerate(closes):
        out.append(
            {
                "open": float(c),
                "high": float(c),
                "low": float(c),
                "close": float(c),
                "volume": 1.0,
                "time": day0 + i * 86_400_000,
            }
        )
    return out


class TestProviderHtfBarmerge:
    """gaps_on / lookahead_on on provider-backed coarser OHLCV (D-06 residual)."""

    def test_gaps_on_daily_provider_only_bucket_starts(self) -> None:
        """Daily provider on a 1h chart: gaps_on close only on HTF day-open bars."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(72)
        prov = _DailyHtfProvider(_daily_provider_bars())
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "D", "close", barmerge.gaps_on, barmerge.lookahead_off)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret", data_provider=prov)
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert len(sec) == len(bars)
        # Day 0: no completed daily bar yet.
        assert all(_is_na(v) for v in sec[0:24])
        # Day-open bars carry the previous day's provider close.
        assert abs(float(sec[24]) - 111.0) < 1e-9
        assert abs(float(sec[48]) - 222.0) < 1e-9
        assert all(_is_na(v) for v in sec[25:48])
        assert all(_is_na(v) for v in sec[49:])
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("gaps_supported") is True
        policies = pol.get("policies") or {}
        assert "gaps_applied" in policies
        assert "gaps_lookahead_provided" in policies

    def test_lookahead_on_daily_provider_leaks_from_period_start(self) -> None:
        """lookahead_on leaks each daily close from the UTC day start on 1h bars."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(72)
        prov = _DailyHtfProvider(_daily_provider_bars())
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "D", "close", barmerge.gaps_off, barmerge.lookahead_on)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret", data_provider=prov)
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        for i in (0, 12, 23):
            assert abs(float(sec[i]) - 111.0) < 1e-9
        for i in (24, 36, 47):
            assert abs(float(sec[i]) - 222.0) < 1e-9
        for i in (48, 60, 71):
            assert abs(float(sec[i]) - 333.0) < 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("lookahead_supported") is True
        assert "lookahead_applied" in (pol.get("policies") or {})

    def test_gaps_and_lookahead_combined_daily_provider(self) -> None:
        """gaps_on + lookahead_on: leaked daily close on day-open hours only."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(72)
        prov = _DailyHtfProvider(_daily_provider_bars())
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "D", "close", barmerge.gaps_on, barmerge.lookahead_on)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret", data_provider=prov)
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert abs(float(sec[0]) - 111.0) < 1e-9
        assert abs(float(sec[24]) - 222.0) < 1e-9
        assert abs(float(sec[48]) - 333.0) < 1e-9
        assert all(_is_na(v) for v in sec[1:24])
        assert all(_is_na(v) for v in sec[25:48])
        assert all(_is_na(v) for v in sec[49:])

    def test_daily_feed_ohlcv_lookahead_on(self) -> None:
        """Feed ``fetch_latest_ohlcv`` daily rows align like a provider payload."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(72)
        day0 = _utc_day0_ms()
        rows = []
        for i, c in enumerate((111.0, 222.0, 333.0)):
            ts = day0 + i * 86_400_000
            rows.append([ts, c, c, c, c, 1.0])

        class _DailyHtfFeed:
            def fetch_latest_ohlcv(self, symbol, timeframe="D", limit=5):
                _ = symbol, timeframe
                n = int(limit) if limit is not None else len(rows)
                return rows[-max(1, n) :] if n < len(rows) else list(rows)

        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "D", "close", barmerge.gaps_off, barmerge.lookahead_on)
plot(v, title="sec")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret", data_feed=_DailyHtfFeed())
        assert not out.get("error"), out.get("error")
        sec = out["series"]["sec"]
        assert abs(float(sec[0]) - 111.0) < 1e-9
        assert abs(float(sec[24]) - 222.0) < 1e-9
        assert abs(float(sec[48]) - 333.0) < 1e-9
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert "lookahead_applied" in (pol.get("policies") or {})

    def test_chart_length_provider_gaps_unused(self) -> None:
        """ChartOHLCVProvider-like (ignores interval) + gaps_on stays unused-merge."""
        from backend.runtime import Runtime

        bars = _day_aligned_hourly(48)
        stub = _ChartLengthStubProvider(bars, symbol="AAPL")
        src_on = """//@version=6
indicator("t")
v = request.security("MSFT", "D", "close", barmerge.gaps_on, barmerge.lookahead_off)
plot(v, title="sec")
"""
        src_off = """//@version=6
indicator("t")
v = request.security("MSFT", "D", "close", barmerge.gaps_off, barmerge.lookahead_off)
plot(v, title="sec")
"""
        rt = Runtime(symbol="AAPL")
        on = rt.run(src_on, bars, mode="interpret", data_provider=stub)
        off = rt.run(src_off, bars, mode="interpret", data_provider=stub)
        assert not on.get("error"), on.get("error")
        assert not off.get("error"), off.get("error")
        sec_on = on["series"]["sec"]
        sec_off = off["series"]["sec"]
        assert len(sec_on) == len(sec_off) == len(bars)
        for a, b in zip(sec_on, sec_off, strict=True):
            na_a, na_b = _is_na(a), _is_na(b)
            assert na_a == na_b
            if not na_a:
                assert abs(float(a) - float(b)) < 1e-9
        pol = (on.get("meta") or {}).get("request_security") or {}
        assert pol.get("gaps_supported") is False
        policies = pol.get("policies") or {}
        assert "gaps_lookahead_provided" in policies
        assert "gaps_applied" not in policies
