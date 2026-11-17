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

"""Live DataFeed.poll_ohlcv drives interpret and compile realtime ticks (D-04).

Without a feed, last-bar ticks re-visit the same historical OHLC.
With a feed, each last-bar tick evaluates the next polled forming candle.
"""

from __future__ import annotations

from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


def _bars(n: int = 5) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for i in range(n):
        c = 100.0 + i
        out.append(
            {
                "time": 1_704_067_200_000 + i * 86_400_000,
                "open": c,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1000.0,
            }
        )
    return out


_PLOT_CLOSE = """//@version=6
indicator("rt feed")
plot(close, "c")
"""


def _scripted_closes(*closes: float, ts: int = 1_704_067_200_000 + 4 * 86_400_000) -> list[list[float | int]]:
    candles: list[list[float | int]] = []
    for i, close in enumerate(closes):
        o = float(closes[0])
        candles.append([ts, o, close + 1.0, o - 1.0, float(close), 10.0 + i])
    return candles


def test_feed_ticks_use_third_polled_close() -> None:
    """``realtime_ticks=3`` + feed → last plotted close is the third poll."""
    candles = _scripted_closes(210.0, 220.0, 230.0)
    feed = MockDataFeed(scripted=candles)
    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="interpret",
        realtime_ticks=3,
        data_feed=feed,
    )
    assert "error" not in out, out.get("error")
    plotted = [float(v) for v in out["series"]["c"]]
    assert plotted[-1] == 230.0, plotted
    assert plotted[-1] != hist_close
    assert plotted[:-1] == [float(b["close"]) for b in bars[:-1]]


_PENDING_LIMIT = """//@version=6
strategy("rt pending", overlay=true)
if barstate.isfirst
    strategy.entry("L", strategy.long, limit=95.0)
plot(strategy.position_size, "pos")
"""


def test_feed_tick_fills_pending_limit_intrabar() -> None:
    """A pending limit fills on the tick whose forming low crosses it."""
    ts = 1_704_067_200_000 + 4 * 86_400_000
    candles = [
        [ts, 104.0, 105.0, 96.0, 104.0, 10.0],
        [ts, 104.0, 105.0, 94.0, 104.0, 20.0],
        [ts, 104.0, 105.0, 94.0, 104.0, 30.0],
    ]
    out = Runtime(symbol="RT").run(
        _PENDING_LIMIT,
        _bars(5),
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=candles),
    )
    assert "error" not in out, out.get("error")
    pos = [float(v) for v in out["series"]["pos"]]
    assert pos[-1] == 1.0, pos
    assert pos[:-1] == [0.0, 0.0, 0.0, 0.0], pos


def test_no_feed_pending_limit_does_not_fill_intrabar() -> None:
    """Without a crossing forming bar, the limit stays pending."""
    out = Runtime(symbol="RT").run(_PENDING_LIMIT, _bars(5), mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert [float(v) for v in out["series"]["pos"]] == [0.0, 0.0, 0.0, 0.0, 0.0]


_PARTIAL_FILL = """//@version=6
strategy("rt partial", overlay=true)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=10, limit=95.0, max_fill_per_bar=3)
plot(strategy.position_size, "pos")
"""


def test_partial_fill_budget_consumed_once_per_bar_no_feed() -> None:
    """``max_fill_per_bar`` fills once per bar across bar-start and tick paths."""
    bars = _bars(5)
    bars[-1]["low"] = 94.0
    for ticks in (1, 3):
        out = Runtime(symbol="RT").run(_PARTIAL_FILL, bars, mode="interpret", realtime_ticks=ticks)
        assert "error" not in out, out.get("error")
        assert out["series"]["pos"][-1] == 3.0, (ticks, out["series"]["pos"])


def test_partial_fill_budget_consumed_once_per_bar_with_feed() -> None:
    """A feed tick that crosses fills the bar budget once, not once per tick."""
    ts = 1_704_067_200_000 + 4 * 86_400_000
    feed = MockDataFeed(
        scripted=[
            [ts, 104.0, 105.0, 94.0, 104.0, 10.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 20.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 30.0],
        ]
    )
    bars = _bars(5)
    bars[-1]["low"] = 94.0
    out = Runtime(symbol="RT").run(_PARTIAL_FILL, bars, mode="interpret", realtime_ticks=3, data_feed=feed)
    assert "error" not in out, out.get("error")
    assert out["series"]["pos"][-1] == 3.0, out["series"]["pos"]


def test_tick_order_fill_error_returns_order_kind(monkeypatch) -> None:
    """An exception in the tick fill path returns ERROR_KIND_ORDER, not a crash."""
    from pynescript.ast.evaluator.builtins.strategy import StrategyBuiltinsMixin

    real = StrategyBuiltinsMixin.process_pending_orders

    def boom(self, *, open_=None, high=None, low=None, close=None):
        if low is not None and float(low) <= 94.0:
            raise RuntimeError("tick fill boom")
        return real(self, open_=open_, high=high, low=low, close=close)

    monkeypatch.setattr(StrategyBuiltinsMixin, "process_pending_orders", boom)
    ts = 1_704_067_200_000 + 4 * 86_400_000
    feed = MockDataFeed(
        scripted=[
            [ts, 104.0, 105.0, 96.0, 104.0, 10.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 20.0],
            [ts, 104.0, 105.0, 94.0, 104.0, 30.0],
        ]
    )
    out = Runtime(symbol="RT").run(_PENDING_LIMIT, _bars(5), mode="interpret", realtime_ticks=3, data_feed=feed)
    assert out.get("error_kind") == "order", out
    assert "tick fill boom" in str(out.get("error") or "")


_COMPILE_TICK_CANDLES = [
    [1_704_067_200_000 + 4 * 86_400_000, 104.0, 105.0, 96.0, 104.0, 10.0],
    [1_704_067_200_000 + 4 * 86_400_000, 104.0, 105.0, 94.0, 104.0, 20.0],
    [1_704_067_200_000 + 4 * 86_400_000, 104.0, 105.0, 94.0, 104.0, 30.0],
]


def _compile_tick_feed() -> MockDataFeed:
    """Fresh scripted feed: a feed instance advances its own candle list."""
    return MockDataFeed(scripted=[list(candle) for candle in _COMPILE_TICK_CANDLES])


def test_compile_feed_tick_fills_pending_limit_intrabar() -> None:
    """Compile object mode must fill a pending limit on the crossing tick."""
    interp = Runtime(symbol="RT").run(
        _PENDING_LIMIT,
        _bars(5),
        mode="interpret",
        realtime_ticks=3,
        data_feed=_compile_tick_feed(),
    )
    compiled = Runtime(symbol="RT").run(
        _PENDING_LIMIT,
        _bars(5),
        mode="compile",
        realtime_ticks=3,
        data_feed=_compile_tick_feed(),
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    pos_i = [float(v) for v in interp["series"]["pos"]]
    pos_c = [float(v) for v in compiled["series"]["pos"]]
    assert pos_i[-1] == 1.0, pos_i
    assert pos_c[-1] == 1.0, pos_c
    assert pos_c == pos_i


def test_compile_partial_fill_budget_consumed_once_per_bar_with_feed() -> None:
    """Compile tick fills share the per-bar ``max_fill_per_bar`` budget."""
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="RT").run(
            _PARTIAL_FILL,
            _bars(5),
            mode=mode,
            realtime_ticks=3,
            data_feed=_compile_tick_feed(),
        )
        assert "error" not in out, (mode, out.get("error"))
        assert out["series"]["pos"][-1] == 3.0, (mode, out["series"]["pos"])


def test_compile_tick_order_fill_error_returns_order_kind(monkeypatch) -> None:
    """An exception in the compile tick fill path returns ERROR_KIND_ORDER."""
    from pynescript.compiler.strategy_broker import CompileStrategyBroker

    real = CompileStrategyBroker.process_pending_orders

    def boom(self, open_=None, high=None, low=None, close=None):
        if low is not None and float(low) <= 94.0:
            raise RuntimeError("compile tick fill boom")
        return real(self, open_=open_, high=high, low=low, close=close)

    monkeypatch.setattr(CompileStrategyBroker, "process_pending_orders", boom)
    out = Runtime(symbol="RT").run(
        _PENDING_LIMIT,
        _bars(5),
        mode="compile",
        realtime_ticks=3,
        data_feed=_compile_tick_feed(),
    )
    assert out.get("error_kind") == "order", out
    assert "compile tick fill boom" in str(out.get("error") or "")


def test_no_feed_keeps_historical_close() -> None:
    """Without ``data_feed``, ticks re-visit the same last-bar OHLC."""
    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(_PLOT_CLOSE, bars, mode="interpret", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert [float(v) for v in out["series"]["c"]] == [float(b["close"]) for b in bars]
    assert float(out["series"]["c"][-1]) == hist_close


def test_poll_none_is_noop() -> None:
    """``poll_ohlcv`` returning None leaves the historical last bar in place."""

    class _NonePoll:
        def poll_ohlcv(self, symbol: str, timeframe: str = "1m"):
            return None

    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="interpret",
        realtime_ticks=3,
        data_feed=_NonePoll(),
    )
    assert "error" not in out, out.get("error")
    assert float(out["series"]["c"][-1]) == hist_close


def test_historical_ticks_one_ignores_feed() -> None:
    """``realtime_ticks=1`` (no window) does not consume the feed."""
    candles = _scripted_closes(999.0)
    feed = MockDataFeed(scripted=candles)
    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="interpret",
        realtime_ticks=1,
        data_feed=feed,
    )
    assert "error" not in out, out.get("error")
    assert float(out["series"]["c"][-1]) == hist_close
    assert feed.poll_ohlcv("RT") == candles[0]


def test_compile_feed_ticks_use_third_polled_close() -> None:
    """Compile object-mode last-bar ticks poll the same forming OHLC as interpret."""
    candles = _scripted_closes(210.0, 220.0, 230.0)
    feed = MockDataFeed(scripted=candles)
    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="compile",
        realtime_ticks=3,
        data_feed=feed,
    )
    assert "error" not in out, out.get("error")
    plotted = [float(v) for v in out["series"]["c"]]
    assert plotted[-1] == 230.0, plotted
    assert plotted[-1] != hist_close
    assert plotted[:-1] == [float(b["close"]) for b in bars[:-1]]


def test_compile_matches_interpret_feed_ticks() -> None:
    """Dual-host: last plotted close is the third polled candle on both backends."""
    candles = _scripted_closes(210.0, 220.0, 230.0)
    bars = _bars(5)
    interp = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )
    compiled = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="compile",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    assert float(interp["series"]["c"][-1]) == 230.0
    assert float(compiled["series"]["c"][-1]) == 230.0
    assert [float(v) for v in compiled["series"]["c"]] == [float(v) for v in interp["series"]["c"]]


def test_compile_no_feed_keeps_historical_close() -> None:
    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(_PLOT_CLOSE, bars, mode="compile", realtime_ticks=3)
    assert "error" not in out, out.get("error")
    assert float(out["series"]["c"][-1]) == hist_close


def test_compile_poll_none_is_noop() -> None:
    class _NonePoll:
        def poll_ohlcv(self, symbol: str, timeframe: str = "1m"):
            return None

    bars = _bars(5)
    hist_close = float(bars[-1]["close"])
    out = Runtime(symbol="RT").run(
        _PLOT_CLOSE,
        bars,
        mode="compile",
        realtime_ticks=3,
        data_feed=_NonePoll(),
    )
    assert "error" not in out, out.get("error")
    assert float(out["series"]["c"][-1]) == hist_close
