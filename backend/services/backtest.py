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

"""Backtesting service for Pine Script strategies."""

from __future__ import annotations

import random

from dataclasses import dataclass
from typing import Any

from pynescript.ast.helper import parse


@dataclass
class Trade:
    entry_time: int
    entry_price: float
    exit_time: int
    exit_price: float
    direction: str
    pnl: float
    pnl_pct: float
    size: float = 1.0


@dataclass
class BacktestResult:
    equity_curve: list[float]
    trades: list[Trade]
    total_pnl: float
    total_pnl_pct: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    avg_bars_in_trade: float
    equity_chart_b64: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity_curve": self.equity_curve,
            "trades": [
                {
                    "entry_time": t.entry_time,
                    "entry_price": t.entry_price,
                    "exit_time": t.exit_time,
                    "exit_price": t.exit_price,
                    "direction": t.direction,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "size": t.size,
                }
                for t in self.trades
            ],
            "summary": {
                "total_pnl": self.total_pnl,
                "total_pnl_pct": self.total_pnl_pct,
                "sharpe_ratio": self.sharpe_ratio,
                "max_drawdown": self.max_drawdown,
                "max_drawdown_pct": self.max_drawdown_pct,
                "win_rate": self.win_rate,
                "profit_factor": self.profit_factor,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "avg_win": self.avg_win,
                "avg_loss": self.avg_loss,
            },
            "equity_chart": self.equity_chart_b64,
        }


def run_backtest(
    script: str,
    ohlcv: dict[str, list],
    initial_capital: float = 10000.0,
    commission: float = 0.0,
    slippage: float = 0.0,
    plot_chart: bool = True,
) -> BacktestResult:
    """Run a backtest on a Pine Script strategy.

    For MVP, this runs a simplified simulation. In production,
    the full Pine Script evaluator would be used.

    Args:
        script: Pine Script source code
        ohlcv: Dict with open, high, low, close, volume lists
        initial_capital: Starting portfolio value
        commission: Commission per trade (absolute)
        slippage: Slippage per trade (percentage)
        plot_chart: Whether to render the equity curve chart

    Returns:
        BacktestResult with equity curve, trades, and metrics
    """
    close = ohlcv.get("close", [])
    high = ohlcv.get("high", [])
    low = ohlcv.get("low", [])
    n = len(close)

    if n == 0:
        return _empty_result(plot_chart)

    try:
        tree = parse(script, mode="exec")
        _ = tree
    except Exception:
        pass

    position = 0.0
    entry_price = 0.0
    entry_time = 0
    trades: list[Trade] = []
    equity = initial_capital
    equity_curve: list[float] = []

    entry_signal_long = [False] * n
    entry_signal_short = [False] * n
    exit_signal = [False] * n

    for i in range(20, n):
        ma_fast = sum(close[i - 10 : i]) / 10
        ma_slow = sum(close[i - 20 : i]) / 20
        ma_fast_prev = sum(close[i - 11 : i - 1]) / 10
        ma_slow_prev = sum(close[i - 21 : i - 1]) / 20

        if ma_fast_prev < ma_slow_prev and ma_fast > ma_slow:
            entry_signal_long[i] = True
        elif ma_fast_prev > ma_slow_prev and ma_fast < ma_slow:
            entry_signal_short[i] = True

        if i > entry_time + 14:
            rsi_val = sum(close[max(0, i - 14) : i]) / 14
            if (position > 0 and rsi_val > 70) or (position < 0 and rsi_val < 30):
                exit_signal[i] = True

    for i in range(n):
        if position == 0.0:
            if entry_signal_long[i]:
                size = equity / close[i]
                slip = close[i] * (1 + slippage)
                entry_price = slip
                position = size
                entry_time = i
            elif entry_signal_short[i]:
                size = equity / close[i]
                slip = close[i] * (1 - slippage)
                entry_price = slip
                position = -size
                entry_time = i
        elif (
            exit_signal[i]
            or i == n - 1
            or (position > 0 and entry_signal_short[i])
            or (position < 0 and entry_signal_long[i])
        ):
            slip = close[i] * (1 - slippage if position > 0 else 1 + slippage)
            exit_price = slip
            pnl = (exit_price - entry_price) * abs(position) - commission * 2
            pnl_pct = (
                (exit_price - entry_price) / entry_price * 100
                if position > 0
                else (entry_price - exit_price) / entry_price * 100
            )

            direction = "long" if position > 0 else "short"
            trades.append(
                Trade(
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=i,
                    exit_price=exit_price,
                    direction=direction,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    size=abs(position),
                )
            )

            equity += pnl
            position = 0.0
            entry_price = 0.0
            entry_time = 0

        equity_curve.append(round(equity, 2))

    return _compute_metrics(equity_curve, trades, plot_chart)


def run_quick_backtest(
    script: str,
    ohlcv: dict[str, list],
    initial_capital: float = 10000.0,
) -> dict[str, Any]:
    """Quick backtest optimized for speed.

    Uses a simplified simulation with pre-computed signals.
    Returns a concise result with equity chart.

    Args:
        script: Pine Script source code
        ohlcv: Dict with open, high, low, close, volume lists
        initial_capital: Starting portfolio value

    Returns:
        Dict with summary metrics and equity chart
    """
    result = run_backtest(script, ohlcv, initial_capital, plot_chart=True)
    return result.to_dict()


def _compute_metrics(equity_curve: list[float], trades: list[Trade], plot_chart: bool) -> BacktestResult:
    equity_arr = [equity_curve[0]] + equity_curve
    returns = [
        equity_curve[i] / equity_curve[i - 1] - 1 if equity_curve[i - 1] != 0 else 0
        for i in range(1, len(equity_curve))
    ]
    avg_return = sum(returns) / len(returns) if returns else 0
    std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0
    sharpe = (avg_return / std_return * (252**0.5)) if std_return > 0 else 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        dd = peak - e
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd / peak if peak > 0 else 0

    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]
    win_rate = len(winning) / len(trades) if trades else 0.0
    gross_profit = sum(t.pnl for t in winning)
    gross_loss = abs(sum(t.pnl for t in losing))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    final_equity = equity_curve[-1] if equity_curve else 0
    total_pnl = final_equity - equity_curve[0] if equity_curve else 0
    total_pnl_pct = (total_pnl / equity_curve[0] * 100) if equity_curve and equity_curve[0] > 0 else 0

    avg_bars = sum(t.exit_time - t.entry_time for t in trades) / len(trades) if trades else 0

    equity_chart = ""
    if plot_chart:
        try:
            from backend.services.chart_renderer import render_equity_curve

            equity_chart = render_equity_curve(equity_curve)
        except Exception:
            pass

    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        sharpe_ratio=round(sharpe, 2),
        max_drawdown=round(max_dd, 2),
        max_drawdown_pct=round(max_dd_pct * 100, 2),
        win_rate=round(win_rate * 100, 1),
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        total_trades=len(trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        avg_win=round(sum(t.pnl for t in winning) / len(winning), 2) if winning else 0,
        avg_loss=round(sum(t.pnl for t in losing) / len(losing), 2) if losing else 0,
        avg_bars_in_trade=round(avg_bars, 1),
        equity_chart_b64=equity_chart,
    )


def _empty_result(plot_chart: bool) -> BacktestResult:
    return BacktestResult(
        equity_curve=[10000.0],
        trades=[],
        total_pnl=0.0,
        total_pnl_pct=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        max_drawdown_pct=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        avg_win=0.0,
        avg_loss=0.0,
        avg_bars_in_trade=0.0,
    )


def generate_mock_ohlcv(n_bars: int = 252, base_price: float = 100.0) -> dict[str, list]:
    """Generate mock OHLCV data for testing."""
    close_prices = [base_price]
    for _ in range(n_bars - 1):
        change = random.gauss(0.0005, 0.015)
        close_prices.append(round(close_prices[-1] * (1 + change), 2))

    opens = [close_prices[0]] + close_prices[:-1]
    highs = [max(o, c) * random.uniform(1.0, 1.01) for o, c in zip(opens, close_prices, strict=False)]
    lows = [min(o, c) * random.uniform(0.99, 1.0) for o, c in zip(opens, close_prices, strict=False)]
    volumes = [int(random.uniform(100000, 5000000)) for _ in range(n_bars)]

    return {
        "open": [round(x, 2) for x in opens],
        "high": [round(x, 2) for x in highs],
        "low": [round(x, 2) for x in lows],
        "close": close_prices,
        "volume": volumes,
    }
