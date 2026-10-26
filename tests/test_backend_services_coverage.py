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

"""Coverage for backend.services.backtest and chart_renderer."""

from __future__ import annotations

import base64
import random

import pytest

from backend.services.backtest import BacktestResult
from backend.services.backtest import Trade
from backend.services.backtest import generate_mock_ohlcv
from backend.services.backtest import run_backtest
from backend.services.backtest import run_quick_backtest
from backend.services.chart_renderer import render_equity_curve
from backend.services.chart_renderer import render_line_chart
from backend.services.chart_renderer import render_ohlcv_chart


_PINE = """
//@version=6
strategy("cov")
plot(close)
"""


def _is_png_b64(s: str) -> bool:
    assert isinstance(s, str) and len(s) > 32
    raw = base64.b64decode(s, validate=True)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    return True


def _trending_ohlcv(n: int = 80, *, seed: int = 42) -> dict[str, list]:
    """Enough bars for the MVP MA crossover (needs i >= 20)."""
    rng = random.Random(seed)
    close: list[float] = []
    price = 100.0
    for i in range(n):
        # Alternating regimes so MA crosses fire.
        drift = 0.35 if (i // 15) % 2 == 0 else -0.3
        price = max(5.0, price + drift + rng.uniform(-0.2, 0.2))
        close.append(round(price, 2))
    opens = [close[0], *close[:-1]]
    highs = [max(o, c) + 0.2 for o, c in zip(opens, close, strict=False)]
    lows = [min(o, c) - 0.2 for o, c in zip(opens, close, strict=False)]
    volumes = [1000 + i * 10 for i in range(n)]
    return {
        "open": [round(x, 2) for x in opens],
        "high": [round(x, 2) for x in highs],
        "low": [round(x, 2) for x in lows],
        "close": close,
        "volume": volumes,
    }


class TestTradeAndBacktestResult:
    def test_trade_fields(self) -> None:
        t = Trade(
            entry_time=1,
            entry_price=10.0,
            exit_time=5,
            exit_price=12.0,
            direction="long",
            pnl=2.0,
            pnl_pct=20.0,
            size=1.5,
        )
        assert t.size == 1.5
        assert t.direction == "long"

    def test_to_dict_shape(self) -> None:
        t = Trade(0, 10.0, 3, 11.0, "short", -1.0, -10.0, size=2.0)
        result = BacktestResult(
            equity_curve=[10000.0, 9999.0],
            trades=[t],
            total_pnl=-1.0,
            total_pnl_pct=-0.01,
            sharpe_ratio=0.1,
            max_drawdown=1.0,
            max_drawdown_pct=0.01,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=1,
            winning_trades=0,
            losing_trades=1,
            avg_win=0.0,
            avg_loss=-1.0,
            avg_bars_in_trade=3.0,
            equity_chart_b64="abc",
        )
        d = result.to_dict()
        assert set(d) == {"equity_curve", "trades", "summary", "equity_chart"}
        assert d["equity_chart"] == "abc"
        assert d["trades"][0]["direction"] == "short"
        assert d["trades"][0]["size"] == 2.0
        assert "total_pnl" in d["summary"]
        assert "avg_bars_in_trade" not in d["summary"]


class TestRunBacktest:
    def test_empty_ohlcv(self) -> None:
        result = run_backtest(_PINE, {"close": []}, plot_chart=False)
        assert result.total_trades == 0
        assert result.equity_curve == [10000.0]
        assert result.equity_chart_b64 == ""
        assert result.total_pnl == 0.0

    def test_short_series_no_signals(self) -> None:
        # Loop that builds signals starts at i=20; 10 bars → no entries.
        ohlcv = {"close": [100.0 + i * 0.1 for i in range(10)]}
        result = run_backtest(_PINE, ohlcv, plot_chart=False)
        assert len(result.equity_curve) == 10
        assert result.total_trades == 0
        assert all(e == 10000.0 for e in result.equity_curve)

    def test_missing_close_key(self) -> None:
        result = run_backtest(_PINE, {}, plot_chart=False)
        assert result.total_trades == 0
        assert result.equity_curve == [10000.0]

    def test_synthetic_enough_bars(self) -> None:
        ohlcv = _trending_ohlcv(90)
        result = run_backtest(_PINE, ohlcv, initial_capital=10_000.0, plot_chart=False)
        assert len(result.equity_curve) == 90
        assert result.total_trades >= 0
        d = result.to_dict()
        assert d["summary"]["total_trades"] == result.total_trades
        assert isinstance(d["summary"]["profit_factor"], float)

    def test_commission_and_slippage(self) -> None:
        ohlcv = _trending_ohlcv(100, seed=7)
        base = run_backtest(_PINE, ohlcv, commission=0.0, slippage=0.0, plot_chart=False)
        taxed = run_backtest(_PINE, ohlcv, commission=5.0, slippage=0.01, plot_chart=False)
        assert len(base.equity_curve) == len(taxed.equity_curve) == 100
        assert base.total_trades == taxed.total_trades
        for t in taxed.trades:
            assert t.entry_price > 0
            assert t.exit_price > 0
            assert isinstance(t.pnl, float)
        # Slippage moves fills off the raw bar close (MVP long entry uses 1+slip).
        if taxed.trades:
            first = taxed.trades[0]
            raw = ohlcv["close"][first.entry_time]
            assert first.entry_price != pytest.approx(raw)

    def test_plot_chart_false_skips_image(self) -> None:
        ohlcv = _trending_ohlcv(60)
        result = run_backtest(_PINE, ohlcv, plot_chart=False)
        assert result.equity_chart_b64 == ""

    def test_plot_chart_true_renders(self) -> None:
        ohlcv = _trending_ohlcv(50)
        result = run_backtest(_PINE, ohlcv, plot_chart=True)
        assert _is_png_b64(result.equity_chart_b64)

    def test_invalid_script_still_runs(self) -> None:
        ohlcv = _trending_ohlcv(40)
        result = run_backtest("not valid pine {{{", ohlcv, plot_chart=False)
        assert len(result.equity_curve) == 40

    def test_run_quick_backtest_dict(self) -> None:
        ohlcv = _trending_ohlcv(45)
        d = run_quick_backtest(_PINE, ohlcv, initial_capital=5000.0)
        assert "summary" in d and "equity_chart" in d
        assert _is_png_b64(d["equity_chart"])

    def test_generate_mock_ohlcv_shape(self) -> None:
        random.seed(0)
        data = generate_mock_ohlcv(n_bars=30, base_price=50.0)
        assert set(data) == {"open", "high", "low", "close", "volume"}
        assert len(data["close"]) == 30
        assert data["close"][0] == 50.0
        assert all(isinstance(v, int) for v in data["volume"])


class TestChartRenderer:
    def test_line_empty_list(self) -> None:
        assert _is_png_b64(render_line_chart([], height=40, width=80))

    def test_line_all_none(self) -> None:
        assert _is_png_b64(render_line_chart([None, None], height=40, width=80))

    def test_line_normal(self) -> None:
        b64 = render_line_chart([1.0, 2.5, 2.0, 3.0], title="T", height=40, width=80)
        assert _is_png_b64(b64)

    def test_line_with_dates(self) -> None:
        vals = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        dates = [f"d{i}" for i in range(6)]
        assert _is_png_b64(render_line_chart(vals, dates=dates, height=40, width=100))

    def test_line_with_nones_interleaved(self) -> None:
        assert _is_png_b64(render_line_chart([1.0, None, 2.0], height=40, width=80))

    def test_line_volume_and_ohlcv(self) -> None:
        vals = [10.0, 10.5, 11.0, 10.8]
        ohlcv = {
            "open": [10, 10.2, 10.5, 11],
            "high": [10.5, 10.8, 11.2, 11.1],
            "low": [9.8, 10, 10.4, 10.5],
            "close": vals,
            "volume": [100, 120, 90, 110],
        }
        b64 = render_line_chart(
            vals,
            show_volume=True,
            ohlcv=ohlcv,
            height=50,
            width=100,
        )
        assert _is_png_b64(b64)

    def test_line_show_volume_without_ohlcv(self) -> None:
        # Twin axis only when ohlcv has volume; still returns PNG.
        assert _is_png_b64(render_line_chart([1.0, 2.0], show_volume=True, height=40, width=80))

    def test_equity_empty(self) -> None:
        assert _is_png_b64(render_equity_curve([], height=40, width=80))

    def test_equity_normal(self) -> None:
        curve = [10000.0, 10050.0, 9950.0, 10100.0]
        assert _is_png_b64(render_equity_curve(curve, height=40, width=80))

    def test_equity_with_dates(self) -> None:
        curve = [1.0, 1.1, 0.9, 1.2]
        dates = ["a", "b", "c", "d"]
        assert _is_png_b64(render_equity_curve(curve, dates=dates, height=40, width=80))

    def test_ohlcv_empty_dict(self) -> None:
        assert _is_png_b64(render_ohlcv_chart({}, height=40, width=80))

    def test_ohlcv_empty_close(self) -> None:
        assert _is_png_b64(render_ohlcv_chart({"close": []}, height=40, width=80))

    def test_ohlcv_candles(self) -> None:
        n = 8
        ohlcv = {
            "open": [10.0 + i * 0.1 for i in range(n)],
            "high": [10.5 + i * 0.1 for i in range(n)],
            "low": [9.5 + i * 0.1 for i in range(n)],
            "close": [10.2 + i * 0.1 for i in range(n)],
            "volume": [100 + i for i in range(n)],
        }
        # Force a down candle for red branch.
        ohlcv["close"][2] = ohlcv["open"][2] - 0.3
        assert _is_png_b64(render_ohlcv_chart(ohlcv, title="PX", height=50, width=100))
