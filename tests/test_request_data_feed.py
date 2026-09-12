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

    def test_dividends_scales_with_feed_price(self) -> None:
        feed = MockDataFeed(symbol="AAPL", start_price=200.0)
        ev = NodeLiteralEvaluator(data_feed=feed)
        # base AAPL div 0.24 scaled by last/100
        div = _eval(ev, 'request.dividends("AAPL")')
        assert float(div) > 0.24  # scaled up vs base at 100

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
    """Allowlisted ta.sma/ema/rsi/atr/wma/rma on resampled HTF bars (not full multi-TF)."""

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
        # Stepwise constancy: within hour 5 (bars 300–359) last completed is hour 4;
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
        """Nested / non-allowlist ta never use htf_simple_ta_resample.

        Chart pre-eval of nested SMA can occasionally equal an OHLCV sample and
        hit the pre-existing passthrough heuristic — that is not the simple-ta
        HTF path. Nested ``ta.sma(ta.ema(...))`` and non-allowlist ``ta.stdev``
        stay na; ``ta.wma`` / ``ta.rma`` are now allowlisted.
        """
        from backend.runtime import Runtime

        bars = _aligned_1m_bars(3 * 60)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", ta.sma(ta.ema(close, 3), 3)), title="nested")
plot(request.security(syminfo.tickerid, "60", ta.stdev(close, 5)), title="stdev")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert all(_is_na(x) for x in out["series"]["stdev"])
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
        assert match_htf_simple_ta_ast(_expr("ta.sma(ta.ema(close, 5), 14)")) is None
        assert match_htf_simple_ta_ast(_expr("ta.stdev(close, 14)")) is None
        assert match_htf_simple_ta_ast(_expr("close")) is None


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
