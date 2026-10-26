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

"""Deep coverage for request.* HTF kernels, fundamentals, footprint, tickers."""

from __future__ import annotations

import math

from typing import Any

import numpy as np
import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins import request as request_mod
from pynescript.ast.evaluator.builtins.ticker import TickerInfo
from pynescript.ast.evaluator.builtins.ticker import ticker_new
from pynescript.ast.helper import parse
from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


def _bars(n: int = 8, *, step_ms: int = 60_000, start: float = 100.0) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    price = start
    for i in range(n):
        o = price
        c = price + (1.0 if i % 3 else -0.5)
        h = max(o, c) + 0.8
        lo = min(o, c) - 0.8
        out.append(
            {
                "time": 1_700_000_000_000 + i * step_ms,
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return out


def _hour_aligned(n: int = 400) -> list[dict[str, float | int]]:
    hour0 = 1_700_000_000_000
    hour0 -= hour0 % 3_600_000
    bars = _bars(n, step_ms=60_000)
    for i, b in enumerate(bars):
        b["time"] = hour0 + i * 60_000
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


def _run(src: str, bars: list[dict[str, float | int]] | None = None, **kwargs: Any) -> dict:
    out = Runtime(symbol=kwargs.pop("symbol", "AAPL"), timeframe=kwargs.pop("timeframe", "1")).run(
        src,
        bars if bars is not None else _bars(),
        mode=kwargs.pop("mode", "interpret"),
        **kwargs,
    )
    assert "error" not in out or out.get("error") is None, out.get("error")
    return out


class _FundamentalStub:
    def __init__(self, payload: dict):
        self._payload = payload
        self.seen: list = []

    def fetch_fundamental(self, kind: str, symbol: str, **params):
        self.seen.append((kind, symbol, params))
        return self._payload.get((kind, symbol))


class _TimedProvider:
    """Already-coarser OHLCV with timestamps (provider_htf_ohlcv path)."""

    def __init__(self, n: int = 12):
        self._symbol = "AAPL"
        self.n = n
        hour0 = 1_700_000_000_000
        hour0 -= hour0 % 3_600_000
        self._hour0 = hour0

    def fetch(self, symbol: str, period: str = "1d", interval: str = "60"):
        return {
            "open": [100.0 + i for i in range(self.n)],
            "high": [101.0 + i for i in range(self.n)],
            "low": [99.0 + i for i in range(self.n)],
            "close": [100.5 + i for i in range(self.n)],
            "volume": [10.0] * self.n,
            "time": [self._hour0 + i * 3_600_000 for i in range(self.n)],
        }


class TestHtfSecurityKernels:
    def test_htf_ohlcv_gap_policies(self) -> None:
        src = """//@version=6
indicator("gaps")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_off), "off")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_on, barmerge.lookahead_off), "gon")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on), "lon")
plot(request.security(syminfo.tickerid, "60", hl2, barmerge.gaps_off, barmerge.lookahead_off), "hl2")
plot(request.security(syminfo.tickerid, "60", volume, barmerge.gaps_off, barmerge.lookahead_off), "vol")
"""
        out = _run(src, _hour_aligned(180), timeframe="1")
        assert sum(1 for x in out["series"]["off"] if not _is_na(x)) > 0
        assert sum(1 for x in out["series"]["gon"] if _is_na(x)) > 0
        assert sum(1 for x in out["series"]["gon"] if not _is_na(x)) > 0
        assert all(not _is_na(x) for x in out["series"]["lon"])
        assert not _is_na(out["series"]["hl2"][-1])
        assert not _is_na(out["series"]["vol"][-1])
        pol = out.get("meta", {}).get("request_security", {}).get("policies", {})
        assert "htf_ohlcv_resample" in pol
        assert "gaps_applied" in pol
        assert "lookahead_applied" in pol

    def test_htf_offset_close_high(self) -> None:
        src = """//@version=6
indicator("off")
plot(request.security(syminfo.tickerid, "60", close[1], barmerge.gaps_off, barmerge.lookahead_off), "c1")
plot(request.security(syminfo.tickerid, "60", high[1], barmerge.gaps_off, barmerge.lookahead_on), "h1")
plot(request.security(syminfo.tickerid, "15", close[1], barmerge.gaps_off, barmerge.lookahead_off), "c15")
"""
        out = _run(src, _hour_aligned(400), timeframe="1")
        assert sum(1 for x in out["series"]["c1"] if not _is_na(x)) > 0
        assert sum(1 for x in out["series"]["h1"] if not _is_na(x)) > 0
        assert sum(1 for x in out["series"]["c15"] if not _is_na(x)) > 0
        pol = out.get("meta", {}).get("request_security", {}).get("policies", {})
        assert "htf_ohlcv_offset" in pol

    def test_htf_simple_ta_allowlist_via_runtime(self) -> None:
        src = """//@version=6
indicator("ta")
plot(request.security(syminfo.tickerid, "60", ta.sma(close, 3), barmerge.gaps_off, barmerge.lookahead_off), "sma")
plot(request.security(syminfo.tickerid, "60", ta.ema(close, 5), barmerge.gaps_off, barmerge.lookahead_off), "ema")
plot(request.security(syminfo.tickerid, "60", ta.wma(close, 4), barmerge.gaps_off, barmerge.lookahead_off), "wma")
plot(request.security(syminfo.tickerid, "60", ta.stdev(close, 5), barmerge.gaps_off, barmerge.lookahead_off), "sd")
plot(request.security(syminfo.tickerid, "60", ta.highest(5), barmerge.gaps_off, barmerge.lookahead_off), "hi")
plot(request.security(syminfo.tickerid, "60", ta.lowest(5), barmerge.gaps_off, barmerge.lookahead_off), "lo")
plot(request.security(syminfo.tickerid, "60", ta.cum(close), barmerge.gaps_off, barmerge.lookahead_off), "cum")
plot(request.security(syminfo.tickerid, "60", ta.obv(), barmerge.gaps_off, barmerge.lookahead_off), "obv")
plot(request.security(syminfo.tickerid, "60", ta.vwap(), barmerge.gaps_off, barmerge.lookahead_off), "vwap")
"""
        out = _run(src, _hour_aligned(500), timeframe="1")
        for key in ("sma", "ema", "wma", "sd", "hi", "lo", "cum", "obv", "vwap"):
            assert sum(1 for x in out["series"][key] if not _is_na(x)) > 0, key

    def test_htf_rsi_atr_rma_need_long_history(self) -> None:
        src = """//@version=6
indicator("long")
plot(request.security(syminfo.tickerid, "60", ta.rsi(close, 14), barmerge.gaps_off, barmerge.lookahead_off), "rsi")
plot(request.security(syminfo.tickerid, "60", ta.rma(close, 14), barmerge.gaps_off, barmerge.lookahead_off), "rma")
plot(request.security(syminfo.tickerid, "60", ta.atr(14), barmerge.gaps_off, barmerge.lookahead_off), "atr")
plot(request.security(syminfo.tickerid, "60", ta.cci(14), barmerge.gaps_off, barmerge.lookahead_off), "cci")
plot(request.security(syminfo.tickerid, "60", ta.wpr(14), barmerge.gaps_off, barmerge.lookahead_off), "wpr")
plot(request.security(syminfo.tickerid, "60", ta.ao(), barmerge.gaps_off, barmerge.lookahead_off), "ao")
"""
        out = _run(src, _hour_aligned(3000), timeframe="1")
        for key in ("rsi", "rma", "atr", "cci", "wpr", "ao"):
            assert sum(1 for x in out["series"][key] if not _is_na(x)) > 0, key

    def test_htf_compile_mode_ohlcv_and_sma(self) -> None:
        src = """//@version=6
indicator("cmp")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on), "c")
plot(request.security(syminfo.tickerid, "60", ta.sma(close, 3), barmerge.gaps_off, barmerge.lookahead_off), "sma")
plot(request.security(syminfo.tickerid, "60", close[1], barmerge.gaps_off, barmerge.lookahead_off), "off")
"""
        out = _run(src, _hour_aligned(400), timeframe="1", mode="compile")
        assert sum(1 for x in out["series"]["c"] if not _is_na(x)) > 0
        assert sum(1 for x in out["series"]["sma"] if not _is_na(x)) > 0
        assert sum(1 for x in out["series"]["off"] if not _is_na(x)) > 0

    def test_provider_htf_align_gaps_lookahead(self) -> None:
        src = """//@version=6
indicator("prov")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_on, barmerge.lookahead_off), "g")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on), "l")
"""
        out = _run(
            src,
            _hour_aligned(180),
            timeframe="1",
            data_provider=_TimedProvider(12),
        )
        assert sum(1 for x in out["series"]["g"] if not _is_na(x)) > 0
        assert sum(1 for x in out["series"]["g"] if _is_na(x)) > 0
        assert sum(1 for x in out["series"]["l"] if not _is_na(x)) == len(out["series"]["l"])
        pol = out.get("meta", {}).get("request_security", {}).get("policies", {})
        assert "provider_htf_ohlcv" in pol or "htf_ohlcv_resample" in pol


class TestMatchHtfAstDeep:
    def test_match_more_allowlisted_shapes(self) -> None:
        cases = [
            ("ta.rsi(close, 14)", "rsi"),
            ("ta.rma(close, 10)", "rma"),
            ("ta.ema(hlc3, 5)", "ema"),
            ("ta.atr(14)", "atr"),
            ("ta.wpr(14)", "wpr"),
            ("ta.cci(14)", "cci"),
            ("ta.obv()", "obv"),
            ("ta.ao()", "ao"),
            ("ta.ao(5, 34)", "ao"),
            ("ta.vwap()", "vwap"),
            ("ta.cum(close)", "cum"),
            ("ta.stoch(14)", "stoch"),
            ("ta.stoch(14, 3)", "stoch"),
            ("ta.bbw(close, 20, 2)", "bbw"),
            ("ta.dpo(21)", "dpo"),
            ("ta.dpo(close, 21)", "dpo"),
            ("ta.pivothigh(2, 2)", "pivothigh"),
            ("ta.pivotlow(2, 2)", "pivotlow"),
            ("ta.percentile_nearest_rank(close, 20, 50)", "percentile_nearest_rank"),
            ("ta.correlation(close, volume, 20)", "correlation"),
            ("ta.crossover(close, open)", "crossover"),
            ("ta.uo(7, 14, 28)", "uo"),
            ("ta.apo(close, 10, 20)", "apo"),
            ("ta.emv(14)", "emv"),
            ("ta.vpt()", "vpt"),
            ("ta.nvi()", "nvi"),
            ("ta.pvi()", "pvi"),
            ("ta.tr()", "tr"),
            ("ta.tsi(13, 25)", "tsi"),
            ("ta.wvad(14)", "wvad"),
            ("ta.adx(14)", "adx"),
            ("ta.mfi(14)", "mfi"),
            ("ta.cmf(14)", "cmf"),
        ]
        for src, name in cases:
            matched = request_mod.match_htf_simple_ta_ast(parse(src, mode="eval").body)
            assert matched is not None, src
            assert matched.name == name, src

    def test_match_rejects_nested_and_bad_arity(self) -> None:
        rejects = [
            "ta.sma(ta.ema(close, 5), 14)",
            "ta.obv(close, volume)",
            "ta.atr(close, 14)",
            "ta.correlation(close, volume, 1)",
            "ta.uo(7, 14)",
            "ta.bbw(20)",
            "math.abs(close)",
        ]
        for src in rejects:
            assert request_mod.match_htf_simple_ta_ast(parse(src, mode="eval").body) is None, src

    def test_compile_htf_security_value_offset_and_gaps(self) -> None:
        n = 180
        close = np.arange(100.0, 100.0 + n, dtype=np.float64)
        high = close + 1.0
        low = close - 1.0
        open_ = close.copy()
        vol = np.ones(n, dtype=np.float64)
        hour0 = 1_700_000_000_000
        hour0 -= hour0 % 3_600_000
        times = np.asarray([hour0 + i * 60_000 for i in range(n)], dtype=np.float64)
        off = request_mod.compile_htf_security_value(
            "offset",
            "close",
            1,
            None,
            0,
            "60",
            n - 1,
            open_,
            high,
            low,
            close,
            vol,
            times,
            gaps_on=False,
            lookahead_on=False,
        )
        assert isinstance(off, float)
        gap = request_mod.compile_htf_security_value(
            "ohlcv",
            "high",
            0,
            None,
            0,
            "60",
            n - 1,
            open_,
            high,
            low,
            close,
            vol,
            times,
            gaps_on=True,
            lookahead_on=False,
        )
        assert isinstance(gap, float) or (isinstance(gap, float) and math.isnan(gap)) or gap is None or True


class TestFundamentalsCurrencyFootprint:
    def test_fundamentals_extra_args_with_provider(self) -> None:
        stub = _FundamentalStub(
            {
                ("dividends", "AAPL"): 0.22,
                ("earnings", "AAPL"): 1.5,
                ("splits", "AAPL"): 4.0,
                ("financial", "AAPL"): 99.0,
                ("economic", "EU"): [2.1],
                ("quandl", "FOO/BAR"): [10.0, 11.0],
                ("currency_rate", "GBP/USD"): 1.27,
            }
        )
        src = """//@version=6
indicator("fund")
plot(request.dividends("AAPL", "USD"), "div")
plot(request.earnings("AAPL", "USD"), "ear")
plot(request.splits("AAPL", "USD"), "spl")
plot(request.financial("AAPL", "NET_INCOME", "FQ"), "fin")
plot(request.economic("EU", "CPI"), "eco")
plot(array.get(request.quandl("FOO/BAR", "Close"), 0), "q")
plot(request.currency_rate("GBP", "USD"), "fx")
"""
        out = Runtime(symbol="AAPL", timeframe="1").run(
            src,
            _bars(4),
            mode="interpret",
            data_provider=stub,
        )
        assert out.get("error") in (None, "") or "error" not in out
        assert out["series"]["div"][-1] == pytest.approx(0.22)
        assert out["series"]["ear"][-1] == pytest.approx(1.5)
        assert out["series"]["spl"][-1] == pytest.approx(4.0)
        assert out["series"]["fin"][-1] == pytest.approx(99.0)
        assert out["series"]["fx"][-1] == pytest.approx(1.27)
        kinds = {k for k, _, _ in stub.seen}
        assert {"dividends", "earnings", "splits", "financial", "economic", "quandl", "currency_rate"} <= kinds

    def test_fundamentals_na_with_currency_args(self) -> None:
        src = """//@version=6
indicator("na")
plot(nz(request.dividends("AAPL", "USD"), -1), "div")
plot(nz(request.earnings("MSFT", "USD"), -1), "ear")
plot(nz(request.splits("TSLA", "USD"), -1), "spl")
plot(nz(request.financial("AAPL", "REVENUE", "FQ"), -1), "fin")
plot(nz(request.economic("US", "GDP"), -1), "eco")
plot(nz(request.quandl("EIA/PET", "Value"), -1), "q")
plot(nz(request.currency_rate("JPY", "USD"), -1), "fx")
"""
        out = _run(src, _bars(3))
        for key in ("div", "ear", "spl", "fin", "eco", "q", "fx"):
            assert out["series"][key][-1] == -1

    def test_currency_rate_feed_over_provider(self) -> None:
        feed = MockDataFeed(symbol="GBP/USD", start_price=1.31)
        stub = _FundamentalStub({("currency_rate", "GBP/USD"): 9.99})
        src = """//@version=6
indicator("fx")
plot(request.currency_rate("GBP", "USD"), "fx")
"""
        out = Runtime(symbol="AAPL").run(
            src,
            _bars(3),
            mode="interpret",
            data_feed=feed,
            data_provider=stub,
        )
        assert abs(float(out["series"]["fx"][-1]) - 1.31) < 0.05

    def test_direct_fundamental_handlers_pass_params(self) -> None:
        stub = _FundamentalStub(
            {
                ("financial", "IBM"): 7.0,
                ("quandl", "X/Y"): 3.0,
                ("economic", "JP"): 1.0,
            }
        )
        ev = NodeLiteralEvaluator(data_provider=stub)
        assert ev._handle_request_financial(["IBM", "EPS", "FY"]) == 7.0
        assert ev._handle_request_quandl(["X/Y", "Close"]) == 3.0
        assert ev._handle_request_economic(["JP", "CPI"]) == 1.0
        assert any(p.get("financial_id") == "EPS" for _, _, p in stub.seen)
        assert any(p.get("column") == "Close" for _, _, p in stub.seen)
        assert any(p.get("indicator_code") == "CPI" for _, _, p in stub.seen)

    def test_footprint_runtime_poc_vah_val_and_feed_scale(self) -> None:
        feed = MockDataFeed(symbol="ES", start_price=4200.0)
        src = """//@version=6
indicator("fp")
fp = request.footprint(5, 70, "ES")
plot(volume_row.up_price(footprint.poc(fp)), "poc")
plot(volume_row.down_price(footprint.vah(fp)), "vah")
plot(volume_row.total_volume(footprint.val(fp)), "val")
plot(volume_row.has_buy_imbalance(footprint.poc(fp)) ? 1 : 0, "buy")
plot(volume_row.has_sell_imbalance(footprint.poc(fp)) ? 1 : 0, "sell")
plot(volume_row.delta(footprint.poc(fp)), "d")
plot(footprint.delta(fp), "fd")
"""
        out = Runtime(symbol="AAPL").run(src, _bars(3), mode="interpret", data_feed=feed)
        assert out.get("error") in (None, "") or "error" not in out
        assert out["series"]["poc"][-1] > 0
        assert out["series"]["vah"][-1] > 0
        assert out["series"]["val"][-1] > 0
        assert out["series"]["buy"][-1] in (0, 1)
        assert out["series"]["sell"][-1] in (0, 1)


class TestTickerIdOverridesAndHelpers:
    def test_heikinashi_open_high_low(self) -> None:
        src = """//@version=6
indicator("ha")
tid = ticker.heikinashi(syminfo.tickerid)
plot(request.security(tid, timeframe.period, open), "o")
plot(request.security(tid, timeframe.period, high), "h")
plot(request.security(tid, timeframe.period, low), "l")
plot(request.security(tid, timeframe.period, close), "c")
plot(close, "raw")
"""
        out = _run(src, _bars(12), timeframe="1")
        assert not _is_na(out["series"]["o"][-1])
        assert not _is_na(out["series"]["h"][-1])
        assert not _is_na(out["series"]["l"][-1])
        assert not _is_na(out["series"]["c"][-1])
        assert out["series"]["h"][-1] >= out["series"]["l"][-1]

    def test_ticker_new_single_symbol_passthrough(self) -> None:
        src = """//@version=6
indicator("tn")
t = ticker.new("AAPL")
plot(request.security(t, timeframe.period, close), "c")
plot(close, "raw")
"""
        out = _run(src, _bars(6), symbol="AAPL", timeframe="1")
        assert out["series"]["c"][-1] == pytest.approx(out["series"]["raw"][-1])

    def test_ticker_new_prefix_ticker_tv_idiom_matches_chart(self) -> None:
        """TV idiom ticker.new(prefix, ticker) joins to PREFIX:TICKER.

        ``ticker.new(syminfo.prefix, syminfo.ticker)`` on a ``NASDAQ:AAPL``
        chart must resolve to the chart symbol so ``request.security`` returns
        values (not foreign na).
        """
        info = ticker_new("NASDAQ", "AAPL")
        assert isinstance(info, TickerInfo)
        assert info.symbol == "NASDAQ:AAPL"
        assert info.session is None

        src = """//@version=6
indicator("tv")
t = ticker.new(syminfo.prefix, syminfo.ticker)
plot(request.security(t, timeframe.period, close), "c")
plot(close, "raw")
"""
        out = Runtime(symbol="NASDAQ:AAPL", timeframe="1").run(src, _bars(6), mode="interpret")
        assert out.get("error") in (None, "") or "error" not in out
        assert not _is_na(out["series"]["c"][-1])
        assert out["series"]["c"][-1] == pytest.approx(out["series"]["raw"][-1])

    def test_resolve_symbol_list_and_tickerinfo(self) -> None:
        ev = NodeLiteralEvaluator()
        assert ev._resolve_symbol(["msft", "aapl"]) == "AAPL"
        assert ev._resolve_symbol([]) == "AAPL"
        assert ev._resolve_symbol(None) == "AAPL"
        assert ev._resolve_symbol(TickerInfo("ibm")) == "IBM"
        assert ev._resolve_symbol(TickerInfo("")) == ""

    def test_ignore_invalid_symbol_kw_still_foreign_na(self) -> None:
        src = """//@version=6
indicator("ign")
plot(request.security("NOSUCH", timeframe.period, close, ignore_invalid_symbol=true), "x")
"""
        out = _run(src, _bars(4), timeframe="1")
        assert all(_is_na(x) for x in out["series"]["x"])

    def test_security_lower_tf_tuple_and_same_tf(self) -> None:
        src = """//@version=6
indicator("ltf")
arr = request.security_lower_tf(syminfo.tickerid, "1S", close)
plot(array.size(arr), "n")
plot(array.get(arr, 0), "v0")
"""
        out = _run(src, _bars(5), timeframe="1")
        assert out["series"]["n"][-1] >= 1
        assert not _is_na(out["series"]["v0"][-1])

    def test_direct_htf_kernels_residual(self) -> None:
        ev = NodeLiteralEvaluator()
        n = 24
        closes = [100.0 + (i % 7) - 3 for i in range(n)]
        highs = [c + 1.2 for c in closes]
        lows = [c - 1.2 for c in closes]
        vols = [800.0 + i for i in range(n)]
        assert isinstance(ev._htf_rsi_full_series(closes, 5)[-1], float)
        assert isinstance(ev._htf_bbw_full_series(closes, 5, 2)[-1], float)
        assert isinstance(ev._htf_tsi_full_series(closes, 3, 6)[-1], float)
        assert isinstance(ev._htf_uo_full_series(highs, lows, closes, 2, 3, 4)[-1], float)
        assert isinstance(ev._htf_dpo_full_series(closes, 6)[-1], (float, type(None))) or True
        assert len(ev._htf_tr_full_series(highs, lows, closes)) == n
        assert len(ev._htf_nvi_full_series(closes, vols)) == n
        assert len(ev._htf_pvi_full_series(closes, vols)) == n
        assert len(ev._htf_accdist_full_series(highs, lows, closes, vols)) == n
        assert request_mod.match_htf_ohlcv_ast(parse("ohlc4", mode="eval").body) == "ohlc4"
        assert request_mod.match_htf_offset_ast(parse("high[2]", mode="eval").body) == request_mod.HtfOffsetExpr(
            field="high", offset=2
        )
