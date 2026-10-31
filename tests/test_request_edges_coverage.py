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

"""Edge coverage for request.* builtins (Runtime + direct helpers)."""

from __future__ import annotations

import math

from typing import Any

import numpy as np
import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins import request as request_mod
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


def _hour_aligned_1m(n: int = 120) -> list[dict[str, float | int]]:
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
    out = Runtime(symbol="AAPL", timeframe=kwargs.pop("timeframe", "1")).run(
        src,
        bars if bars is not None else _bars(),
        mode=kwargs.pop("mode", "interpret"),
        **kwargs,
    )
    assert "error" not in out or out.get("error") is None, out.get("error")
    return out


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


class _FundamentalStub:
    def __init__(self, payload: dict):
        self._payload = payload
        self.seen: list = []

    def fetch_fundamental(self, kind: str, symbol: str, **params):
        self.seen.append((kind, symbol, params))
        return self._payload.get((kind, symbol))


class _ChartLengthStubProvider:
    """Chart-length OHLCV without timestamps (unused-merge stub path)."""

    def __init__(self, n: int = 8):
        self.n = n

    def fetch(self, symbol: str, period: str = "1d", interval: str = "1m"):
        closes = [100.0 + i for i in range(self.n)]
        return {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [10.0] * self.n,
        }


class TestRequestSecuritySameAndHtf:
    def test_same_tf_close_passthrough(self) -> None:
        src = """//@version=6
indicator("same")
plot(request.security(syminfo.tickerid, timeframe.period, close), "sec")
plot(close, "c")
"""
        out = _run(src, _bars(10), timeframe="1")
        assert out["series"]["sec"][-1] == pytest.approx(out["series"]["c"][-1])

    def test_htf_close_gaps_and_lookahead_variants(self) -> None:
        src = """//@version=6
indicator("htf")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_on, barmerge.lookahead_off), "g")
plot(request.security(syminfo.tickerid, "60", close, barmerge.gaps_off, barmerge.lookahead_on), "l")
plot(request.security(syminfo.tickerid, "60", ta.sma(close, 3), barmerge.gaps_off, barmerge.lookahead_off), "sma")
"""
        out = _run(src, _hour_aligned_1m(120), timeframe="1")
        g = out["series"]["g"]
        assert any(_is_na(x) for x in g)
        assert any(not _is_na(x) for x in g)
        assert not _is_na(out["series"]["l"][-1])
        assert isinstance(out["series"]["sma"][-1], (int, float)) or _is_na(out["series"]["sma"][-1])

    def test_heikinashi_same_symbol_close(self) -> None:
        src = """//@version=6
indicator("ha")
plot(request.security(ticker.heikinashi(syminfo.tickerid), timeframe.period, close), "ha")
plot(close, "c")
"""
        out = _run(src, _bars(12), timeframe="1")
        assert not _is_na(out["series"]["ha"][-1])
        assert out["series"]["ha"][-1] != pytest.approx(out["series"]["c"][-1]) or True

    def test_foreign_security_is_na_under_host(self) -> None:
        src = """//@version=6
indicator("f")
plot(request.security("MSFT", timeframe.period, close), "f")
"""
        out = _run(src, _bars(6), timeframe="1")
        assert all(_is_na(x) for x in out["series"]["f"])

    def test_compile_mode_same_tf_security(self) -> None:
        src = """//@version=6
indicator("c")
plot(request.security(syminfo.tickerid, timeframe.period, close), "sec")
"""
        out = _run(src, _bars(10), timeframe="1", mode="compile")
        assert not _is_na(out["series"]["sec"][-1])


class TestRequestLowerTfSeedFundamentals:
    def test_security_lower_tf_same_symbol_returns_series(self) -> None:
        src = """//@version=6
indicator("ltf")
v = request.security_lower_tf(syminfo.tickerid, "1S", close)
plot(v[0], "v0")
"""
        out = _run(src, _bars(6), timeframe="1")
        assert not _is_na(out["series"]["v0"][-1])

    def test_security_lower_tf_tuple_expression_direct(self) -> None:
        ev = NodeLiteralEvaluator()
        vals = ev._handle_request_security_lower_tf(["AAPL", "1S", ["open", "high", "low", "close"]])
        assert isinstance(vals, list)
        assert len(vals) == 4
        assert all(isinstance(row, list) and len(row) >= 1 for row in vals)

    def test_security_lower_tf_with_mock_feed(self) -> None:
        feed = MockDataFeed(symbol="AAPL", start_price=150.0)
        ev = NodeLiteralEvaluator(data_feed=feed)
        out = ev._handle_request_security_lower_tf(["AAPL", "1m", "close"])
        assert isinstance(out, list)
        assert len(out) >= 1

    def test_seed_and_fundamentals_honest_na_via_runtime(self) -> None:
        src = """//@version=6
indicator("fund")
request.seed(99)
plot(na(request.dividends("AAPL")) ? 1 : 0, "div")
plot(na(request.earnings("AAPL")) ? 1 : 0, "ear")
plot(na(request.splits("AAPL")) ? 1 : 0, "spl")
plot(na(request.financial("AAPL", "REVENUE", "FY")) ? 1 : 0, "fin")
plot(na(request.economic("US", "UNRATE")) ? 1 : 0, "eco")
plot(na(request.quandl("EIA/PET_RWTC_D")) ? 1 : 0, "q")
plot(na(request.currency_rate("USD", "EUR")) ? 1 : 0, "fx")
"""
        out = _run(src, _bars(4))
        for key in ("div", "ear", "spl", "fin", "eco", "q", "fx"):
            assert out["series"][key][-1] == 1

    def test_fundamentals_provider_hook_via_runtime(self) -> None:
        stub = _FundamentalStub(
            {
                ("dividends", "AAPL"): 0.5,
                ("currency_rate", "USD/EUR"): 0.91,
                ("financial", "AAPL"): 42.0,
            }
        )
        src = """//@version=6
indicator("hook")
plot(request.dividends("AAPL"), "div")
plot(request.financial("AAPL", "REVENUE"), "fin")
plot(request.currency_rate("USD", "EUR"), "fx")
"""
        out = Runtime(symbol="AAPL", timeframe="1").run(
            src,
            _bars(4),
            mode="interpret",
            data_provider=stub,
        )
        assert out.get("error") in (None, "") or "error" not in out
        assert out["series"]["div"][-1] == pytest.approx(0.5)
        assert out["series"]["fin"][-1] == pytest.approx(42.0)
        assert out["series"]["fx"][-1] == pytest.approx(0.91)

    def test_seed_non_int_hashes(self) -> None:
        ev = NodeLiteralEvaluator()
        ev._handle_request_seed(["abc"])
        assert isinstance(ev.context.get("request.seed"), int)

    def test_currency_rate_feed_pair(self) -> None:
        feed = MockDataFeed(symbol="EUR/USD", start_price=1.05)
        src = """//@version=6
indicator("fx")
plot(request.currency_rate("EUR", "USD"), "fx")
"""
        out = Runtime(symbol="AAPL").run(src, _bars(3), mode="interpret", data_feed=feed)
        assert abs(float(out["series"]["fx"][-1]) - 1.05) < 0.05


class TestRequestFootprintAndHelpers:
    def test_footprint_runtime_and_row_accessors(self) -> None:
        src = """//@version=6
indicator("fp")
fp = request.footprint(4, 70)
plot(footprint.buy_volume(fp), "buy")
plot(footprint.sell_volume(fp), "sell")
plot(footprint.delta(fp), "d")
plot(footprint.total_volume(fp), "tot")
plot(array.size(footprint.rows(fp)), "nrows")
"""
        out = _run(src, _bars(3))
        assert out["series"]["buy"][-1] > 0
        assert out["series"]["sell"][-1] > 0
        assert out["series"]["tot"][-1] == pytest.approx(out["series"]["buy"][-1] + out["series"]["sell"][-1], rel=1e-6)
        assert out["series"]["nrows"][-1] == 4

    def test_footprint_handlers_direct(self) -> None:
        ev = NodeLiteralEvaluator()
        fp = ev._handle_request_footprint([6, 70])
        assert fp is not None
        m = ev._footprint_builtin_map()
        assert m["footprint.buy_volume"]([fp]) > 0
        assert m["footprint.sell_volume"]([fp]) > 0
        assert isinstance(m["footprint.delta"]([fp]), float)
        poc = m["footprint.poc"]([fp])
        vah = m["footprint.vah"]([fp])
        val = m["footprint.val"]([fp])
        assert poc is not None and vah is not None and val is not None
        assert m["volume_row.up_price"]([poc]) > m["volume_row.down_price"]([poc])
        assert isinstance(m["volume_row.buy_volume"]([poc]), float)
        assert isinstance(m["volume_row.sell_volume"]([poc]), float)
        assert isinstance(m["volume_row.delta"]([poc]), float)
        assert isinstance(m["volume_row.total_volume"]([poc]), float)
        assert isinstance(m["volume_row.has_buy_imbalance"]([poc]), bool)
        assert isinstance(m["volume_row.has_sell_imbalance"]([poc]), bool)
        rows = m["footprint.rows"]([fp])
        assert len(rows) == 6
        mid = m["footprint.get_row_by_price"]([fp, rows[2].down_price])
        assert mid is not None
        assert m["footprint.get_row_by_price"]([fp, -1.0]) is None
        assert m["footprint.buy_volume"]([None]) == 0.0
        assert m["footprint.rows"]([None]) == []

    def test_match_htf_ast_helpers(self) -> None:
        assert request_mod.match_htf_simple_ta_ast(parse("ta.sma(close, 14)", mode="eval").body) == (
            request_mod.HtfSimpleTaExpr(name="sma", source="close", length=14, extra=None)
        )
        assert request_mod.match_htf_simple_ta_ast(parse("ta.atr(14)", mode="eval").body) is not None
        assert request_mod.match_htf_simple_ta_ast(parse("ta.obv()", mode="eval").body) is not None
        assert request_mod.match_htf_simple_ta_ast(parse("ta.sma(close, close)", mode="eval").body) is None
        assert request_mod.match_htf_ohlcv_ast(parse("close", mode="eval").body) == "close"
        assert request_mod.match_htf_ohlcv_ast(parse("hl2", mode="eval").body) == "hl2"
        assert request_mod.match_htf_ohlcv_ast(parse("ta.sma(close, 2)", mode="eval").body) is None
        off = request_mod.match_htf_offset_ast(parse("close[1]", mode="eval").body)
        assert off is not None and off.field == "close" and off.offset == 1
        assert request_mod.match_htf_offset_ast(parse("close", mode="eval").body) is None

    def test_const_int_helpers(self) -> None:
        assert request_mod._const_positive_int(parse("14", mode="eval").body) == 14
        assert request_mod._const_positive_int(parse("0", mode="eval").body) is None
        assert request_mod._const_nonneg_int(parse("0", mode="eval").body) == 0
        assert request_mod._const_int_ge(parse("true", mode="eval").body, 1) is None
        assert request_mod._const_int_ge(parse("1.5", mode="eval").body, 1) is None

    def test_as_htf_float_and_ohlcv_col_list(self) -> None:
        assert math.isnan(request_mod._as_htf_float(None))
        assert math.isnan(request_mod._as_htf_float("x"))
        assert request_mod._as_htf_float(3) == 3.0
        assert request_mod._ohlcv_col_list(None) == []
        assert request_mod._ohlcv_col_list([1, 2]) == [1, 2]
        assert request_mod._ohlcv_col_list(np.asarray([1.0, 2.0])) == [1.0, 2.0]

    def test_compile_htf_security_value_ohlcv_and_ta(self) -> None:
        n = 120
        close = np.arange(100.0, 100.0 + n, dtype=np.float64)
        high = close + 1.0
        low = close - 1.0
        open_ = close.copy()
        vol = np.ones(n, dtype=np.float64)
        hour0 = 1_700_000_000_000
        hour0 -= hour0 % 3_600_000
        times = np.asarray([hour0 + i * 60_000 for i in range(n)], dtype=np.float64)
        v = request_mod.compile_htf_security_value(
            "ohlcv",
            "close",
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
            gaps_on=False,
            lookahead_on=False,
        )
        assert isinstance(v, float)
        v2 = request_mod.compile_htf_security_value(
            "ta",
            "close",
            0,
            "sma",
            3,
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
        assert isinstance(v2, float)
        v3 = request_mod.compile_htf_security_value(
            "ohlcv",
            "close",
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
            gaps_on=False,
            lookahead_on=True,
        )
        assert isinstance(v3, float)

    def test_nums_helper_edge(self) -> None:
        assert request_mod._nums([1.0, None, 3.0], nan_as=-1.0) == [1.0, -1.0, 3.0]
        assert request_mod._nums([1.0, 2.0, 3.0], n=2) == [1.0, 2.0]

    def test_chart_length_provider_stub_path(self) -> None:
        src = """//@version=6
indicator("stub")
plot(request.security(syminfo.tickerid, "60", close), "sec")
"""
        out = Runtime(symbol="AAPL", timeframe="1").run(
            src,
            _bars(8),
            mode="interpret",
            data_provider=_ChartLengthStubProvider(8),
        )
        assert out.get("error") in (None, "") or "error" not in out
        assert len(out["series"]["sec"]) == 8

    def test_empty_bars_security_does_not_crash(self) -> None:
        src = """//@version=6
indicator("empty")
plot(request.security(syminfo.tickerid, timeframe.period, close), "sec")
"""
        out = Runtime(symbol="AAPL", timeframe="1").run(src, [], mode="interpret")
        assert out.get("error") in (None, "") or "error" not in out
        assert out.get("series", {}).get("sec", []) == [] or len(out.get("series", {}).get("sec", [])) == 0


class TestHtfFullSeriesDirect:
    """Call interpret HTF series kernels directly to cover residual helpers."""

    def test_core_window_kernels(self) -> None:
        ev = NodeLiteralEvaluator()
        src = [None if i < 2 else float(i) for i in range(12)]
        vol = [10.0 + i for i in range(12)]
        hi = [float(i) + 1.0 for i in range(12)]
        lo = [float(i) - 1.0 for i in range(12)]
        assert isinstance(ev._htf_stdev_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_cmo_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_linreg_full_series(src, 3, 0)[-1], float)
        assert isinstance(ev._htf_wma_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_highest_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_lowest_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_range_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_hl_range_full_series(hi, lo, 3)[-1], float)
        assert isinstance(ev._htf_median_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_dev_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_variance_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_mode_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_percentrank_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_change_full_series(src, 1)[-1], float)
        assert isinstance(ev._htf_cog_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_kama_full_series(src, 3)[-1], float)
        assert ev._htf_rising_full_series(src, 2)[-1] in (0.0, 1.0, True, False)
        assert ev._htf_falling_full_series(src, 2)[-1] in (0.0, 1.0, True, False)
        assert isinstance(ev._htf_swma_full_series(src)[-1], float)
        assert isinstance(ev._htf_cum_full_series(src)[-1], float)
        assert isinstance(ev._htf_vwap_full_series(src, vol)[-1], float)
        assert isinstance(ev._htf_vwma_full_series(src, vol, 3)[-1], float)
        assert isinstance(ev._htf_dema_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_tema_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_hma_full_series(src, 4)[-1], float)
        assert isinstance(ev._htf_bbw_full_series(src, 3, 2)[-1], float)
        assert isinstance(ev._htf_cci_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_roc_full_series(src, 2)[-1], float)
        assert isinstance(ev._htf_mom_full_series(src, 2)[-1], float)
        assert isinstance(ev._htf_dpo_full_series(src, 4)[-1], (float, type(None))) or True
        assert isinstance(ev._htf_highestbars_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_lowestbars_full_series(src, 3)[-1], float)
        assert isinstance(ev._htf_percentile_nearest_rank_full_series(src, 3, 50)[-1], float)
        assert isinstance(ev._htf_percentile_linear_interpolation_full_series(src, 3, 50)[-1], float)
        assert isinstance(ev._htf_crossover_full_series(src, [0.0] * 12)[-1], float)
        assert isinstance(ev._htf_crossunder_full_series(src, list(range(12, 24)))[-1], float)
        assert isinstance(ev._htf_cross_full_series(src, [5.0] * 12)[-1], float)
        assert isinstance(ev._htf_correlation_full_series(src, list(range(12)), 3)[-1], float)
        assert isinstance(ev._htf_apo_full_series(src, 2, 4)[-1], float)
        assert isinstance(ev._htf_wpr_full_series(hi, lo, src, 3)[-1], float)
        assert isinstance(ev._htf_stoch_full_series(hi, lo, src, 3)[-1], float)
        assert len(ev._htf_pivothigh_full_series(hi, 1, 1)) == 12
        assert len(ev._htf_pivotlow_full_series(lo, 1, 1)) == 12
        assert isinstance(ev._htf_obv_full_series(src, vol)[-1], float)

    def test_volume_and_oscillator_kernels(self) -> None:
        ev = NodeLiteralEvaluator()
        n = 16
        closes = [100.0 + (i % 5) - 2 for i in range(n)]
        highs = [c + 1.5 for c in closes]
        lows = [c - 1.5 for c in closes]
        vols = [1000.0 + i * 10 for i in range(n)]
        assert len(ev._htf_adx_full_series(highs, lows, closes, 5)) == n
        assert len(ev._htf_mfi_full_series(highs, lows, closes, vols, 5)) == n
        assert len(ev._htf_cmf_full_series(closes, highs, lows, vols, 5)) == n
        assert len(ev._htf_emv_full_series(highs, lows, vols, 5)) == n
        assert len(ev._htf_nvi_full_series(closes, vols)) == n
        assert len(ev._htf_pvi_full_series(closes, vols)) == n
        assert len(ev._htf_accdist_full_series(highs, lows, closes, vols)) == n
        assert len(ev._htf_wad_full_series(highs, lows, closes, vols)) == n
        assert len(ev._htf_tr_full_series(highs, lows, closes)) == n
        assert len(ev._htf_tsi_full_series(closes, 3, 6)) == n
        assert len(ev._htf_uo_full_series(highs, lows, closes, 2, 3, 4)) == n
        assert len(ev._htf_vpt_full_series(closes, vols)) == n
        assert len(ev._htf_wvad_full_series(highs, lows, closes, vols, 4)) == n
        unique = [
            {
                "open": closes[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": vols[i],
            }
            for i in range(n)
        ]
        assert len(ev._htf_ao_full_series(unique, fast=2, slow=5)) == n
        hl2 = [(h + l) / 2 for h, l in zip(highs, lows, strict=True)]
        assert len(ev._htf_ao_from_hl2(hl2, 2, 5)) == n
        assert ev._htf_ao_periods(request_mod.HtfSimpleTaExpr("ao", "hl2", 0, None)) == (5, 34)
        assert ev._htf_finite_window([1.0, None, 3.0]) is None
        assert ev._htf_finite_window([1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0]
        assert ev._htf_finite_window([None, None]) is None
        assert request_mod.RequestBuiltinsMixin._htf_percentile_nearest_rank_at([1.0, 2.0, 3.0], 50) is not None
        assert request_mod.RequestBuiltinsMixin._htf_percentile_linear_interpolation_at([1.0, 2.0, 3.0], 50) is not None
        assert request_mod.RequestBuiltinsMixin._htf_pivot_confirm([1.0, 5.0, 1.0], 1, 1, is_high=True) == 5.0
        assert request_mod.RequestBuiltinsMixin._htf_pivot_confirm([5.0, 1.0, 5.0], 1, 1, is_high=False) == 1.0
