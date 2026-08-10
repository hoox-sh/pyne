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

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse
from pynescript.util.datafeed import MockDataFeed


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


def _bars(n: int = 80, start: float = 100.0) -> list[dict]:
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
                "time": 1_700_000_000_000 + i * 60_000,
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
    """Same-symbol simple OHLCV may passthrough; complex HTF → na without re-eval."""

    def test_same_symbol_htf_close_passthrough(self) -> None:
        from backend.runtime import Runtime

        bars = _bars(40)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", close), title="sec")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert out["series"]["sec"][-1] == out["series"]["c"][-1] == bars[-1]["close"]

    def test_same_symbol_htf_high1_passthrough(self) -> None:
        from backend.runtime import Runtime

        bars = _bars(40)
        src = """//@version=6
indicator("t")
plot(request.security(syminfo.tickerid, "60", high[1]), title="h")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        assert abs(float(out["series"]["h"][-1]) - float(bars[-2]["high"])) < 1e-9

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
        out = Runtime(symbol="AAPL").run(src, _bars(80), mode="interpret")
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


class TestRequestSecurityHonestyMeta:
    """Runtime metadata + documented no-crash behavior for limited security surface."""

    def test_gaps_lookahead_accepted_unused_and_meta(self) -> None:
        """barmerge.gaps_* / lookahead_* must not crash; values still chart-stub."""
        from backend.runtime import Runtime

        bars = _bars(40)
        src = """//@version=6
indicator("t")
v = request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on)
plot(v, title="sec")
plot(close, title="c")
"""
        out = Runtime(symbol="AAPL").run(src, bars, mode="interpret")
        assert not out.get("error"), out.get("error")
        # No crash + chart passthrough stub (not invented HTF)
        assert out["series"]["sec"][-1] == out["series"]["c"][-1] == bars[-1]["close"]
        pol = (out.get("meta") or {}).get("request_security") or {}
        assert pol.get("htf_reeval") is False
        assert pol.get("gaps_supported") is False
        assert pol.get("lookahead_supported") is False
        policies = pol.get("policies") or {}
        assert "gaps_lookahead_unused" in policies
        assert "chart_passthrough_htf_stub" in policies
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

        bars = _bars(30)
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
        """barmerge.* constants are wired (True/False) even though unused by security."""
        assert _eval(NodeLiteralEvaluator(), "barmerge.lookahead_on") is True
        assert _eval(NodeLiteralEvaluator(), "barmerge.lookahead_off") is False
        assert _eval(NodeLiteralEvaluator(), "barmerge.gaps_on") is True
        assert _eval(NodeLiteralEvaluator(), "barmerge.gaps_off") is False
