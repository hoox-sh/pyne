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

"""Forming-bar realtime ticks update open-trade MAE/MFE (D-03).

``process_pending_orders`` / compile ``begin_bar`` still run once per bar
before the tick loop. Unconfirmed ticks restore the broker book (fills roll
back) then re-apply ``update_open_trade_extremes(high, low)`` from the forming
OHLC after ``poll_ohlcv`` so per-trade ``max_runup`` / ``max_drawdown`` follow
the forming high/low, not the bar-open extremes. Historical ``realtime_ticks=1``
is unchanged. Still OHLC-path (no intra-bar tick path).
"""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.compiler.engine import transpile
from pynescript.compiler.strategy_broker import CompileStrategyBroker
from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


_SRC = """//@version=5
strategy("mae rt", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
plot(high, "h")
plot(low, "l")
plot(strategy.opentrades.max_runup(0), "ru")
plot(strategy.opentrades.max_drawdown(0), "dd")
plot(strategy.position_size, "ps")
plot(strategy.closedtrades, "ct")
"""

_TS0 = 1_704_067_200_000
_DAY = 86_400_000


def _bar(o: float, h: float, low: float, c: float, *, i: int) -> dict[str, float | int]:
    return {
        "time": _TS0 + i * _DAY,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": 1000.0,
    }


def _hist_bars() -> list[dict[str, float | int]]:
    # Bar 0: entry at 100. Bar 1: hold. Bar 2 last — historical high 101 / low 100.2.
    return [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(100.0, 100.0, 100.0, 100.0, i=1),
        _bar(100.5, 101.0, 100.2, 100.8, i=2),
    ]


def _forming_extremes() -> list[list[float | int]]:
    # Higher high, then lower low. Last poll keeps the envelope so the confirmed
    # tick's forming OHLC is high 120 / low 90 (not bar-open 101 / 100.2).
    ts = _TS0 + 2 * _DAY
    return [
        [ts, 100.5, 120.0, 119.5, 119.8, 10.0],
        [ts, 100.5, 120.0, 90.0, 95.0, 11.0],
        [ts, 100.5, 120.0, 90.0, 100.0, 12.0],
    ]


def _num(value: object) -> float:
    if value is None:
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def _series(out: dict[str, Any], name: str) -> list[float]:
    assert "error" not in out, out.get("error")
    return [_num(v) for v in out["series"][name]]


def _kind_count(out: dict[str, Any], kind: str) -> int:
    return sum(1 for e in (out.get("events") or []) if str(e.get("kind")) == kind)


def test_update_open_trade_extremes_survives_broker_restore_interpret() -> None:
    """Restore rolls back fills; re-applying extremes keeps the forming envelope."""
    e = NodeLiteralEvaluator()
    e.context = {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "bar_index": 0,
        "time": 0,
    }
    m = e._build_builtin_map()
    m["strategy.entry"](["L", "long", 1.0])
    # Market entry fills at bar 1's open (reference Pine).
    e.context["bar_index"] = 1
    e.process_pending_orders(open_=100.0, high=100.0, low=100.0, close=100.0)
    trade = e._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(0.0)
    assert trade.max_drawdown == pytest.approx(0.0)
    snap = e._strategy_state.snapshot()
    e.update_open_trade_extremes(120.0, 119.5)
    assert trade.max_runup == pytest.approx(20.0)
    assert trade.max_drawdown == pytest.approx(0.0)
    e._strategy_state.restore(snap)
    trade = e._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(0.0)
    e.update_open_trade_extremes(120.0, 119.5)
    e.update_open_trade_extremes(110.0, 90.0)
    e.update_open_trade_extremes(105.0, 95.0)
    trade = e._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(20.0)
    assert trade.max_drawdown == pytest.approx(10.0)
    assert e._strategy_state.position_direction == "long"


def test_update_open_trade_extremes_survives_broker_restore_compile() -> None:
    b = CompileStrategyBroker(initial_capital=10_000.0, commission_value=0.0)
    b.begin_bar(0, 100.0, 100.0, 100.0, 100.0)
    b.entry("L", "long", 1.0)
    b.begin_bar(1, 100.0, 100.0, 100.0, 100.0)
    assert b.opentrades_max_runup(0) == pytest.approx(0.0)
    assert b.opentrades_max_drawdown(0) == pytest.approx(0.0)
    snap = b.snapshot()
    b.update_open_trade_extremes(120.0, 119.5)
    assert b.opentrades_max_runup(0) == pytest.approx(20.0)
    b.restore(snap)
    assert b.opentrades_max_runup(0) == pytest.approx(0.0)
    b.update_open_trade_extremes(120.0, 119.5)
    b.update_open_trade_extremes(110.0, 90.0)
    b.update_open_trade_extremes(105.0, 95.0)
    assert b.opentrades_max_runup(0) == pytest.approx(20.0)
    assert b.opentrades_max_drawdown(0) == pytest.approx(10.0)
    assert b.position_size == pytest.approx(1.0)


def test_compile_emits_extremes_after_restore() -> None:
    code = transpile(_SRC)
    assert "__strategy.restore(__st_snap)" in code
    restore_at = code.index("__strategy.restore(__st_snap)")
    mae_after = code.find(
        "__strategy.update_open_trade_extremes(high_arr[__bar_idx], low_arr[__bar_idx])",
        restore_at,
    )
    assert mae_after > restore_at, code[restore_at : restore_at + 400]


def test_forming_high_low_update_mae_dual_host() -> None:
    """Last-bar ``realtime_ticks=3`` + higher high then lower low: MAE/MFE follow forming OHLC.

    Unconfirmed ticks still commit at most one fill. Historical last-bar high/low
    is 101 / 100.2 (runup 1, drawdown 0 without a forming update).
    """
    candles = _forming_extremes()
    interp = Runtime(symbol="RTMAE").run(
        _SRC,
        _hist_bars(),
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )
    compiled = Runtime(symbol="RTMAE").run(
        _SRC,
        _hist_bars(),
        mode="compile",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )
    for label, out in (("interpret", interp), ("compile", compiled)):
        assert "error" not in out, (label, out.get("error"))
        h = _series(out, "h")
        low = _series(out, "l")
        ru = _series(out, "ru")
        dd = _series(out, "dd")
        ps = _series(out, "ps")
        ct = _series(out, "ct")
        assert h[-1] == pytest.approx(120.0), (label, h)
        assert low[-1] == pytest.approx(90.0), (label, low)
        assert h[-1] != pytest.approx(101.0)
        assert ru[-1] == pytest.approx(20.0), (label, ru)
        assert dd[-1] == pytest.approx(10.0), (label, dd)
        assert ru[-1] != pytest.approx(1.0)
        assert ps[-1] == pytest.approx(1.0), (label, ps)
        assert ct[-1] == pytest.approx(0.0), (label, ct)
        assert _kind_count(out, "entry") == 1
        assert _kind_count(out, "close") == 0
    assert _series(compiled, "h") == _series(interp, "h")
    assert _series(compiled, "ru") == _series(interp, "ru")
    assert _series(compiled, "dd") == _series(interp, "dd")
    assert _series(compiled, "ps") == _series(interp, "ps")
    assert _series(compiled, "ct") == _series(interp, "ct")

    sess = Runtime(symbol="RTMAE").create_session(
        _SRC,
        _hist_bars(),
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )
    trade = sess.evaluator._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(20.0)
    assert trade.max_drawdown == pytest.approx(10.0)
    assert sess.evaluator._strategy_state.position_direction == "long"


def test_historical_ticks_one_keeps_bar_open_mae() -> None:
    """``realtime_ticks=1`` does not poll; MAE/MFE stay on historical last-bar OHLC."""
    bars = _hist_bars()
    feed = MockDataFeed(scripted=_forming_extremes())
    interp = Runtime(symbol="RTMAE").run(_SRC, bars, mode="interpret", realtime_ticks=1, data_feed=feed)
    compiled = Runtime(symbol="RTMAE").run(
        _SRC,
        bars,
        mode="compile",
        realtime_ticks=1,
        data_feed=MockDataFeed(scripted=_forming_extremes()),
    )
    for out in (interp, compiled):
        assert "error" not in out, out.get("error")
        assert _series(out, "h")[-1] == pytest.approx(101.0)
        assert _series(out, "l")[-1] == pytest.approx(100.2)
        assert _series(out, "ru")[-1] != pytest.approx(20.0)
        assert _series(out, "dd")[-1] != pytest.approx(10.0)
        assert _series(out, "ps")[-1] == pytest.approx(1.0)
        assert _series(out, "ct")[-1] == pytest.approx(0.0)
    assert feed.poll_ohlcv("RTMAE") == _forming_extremes()[0]


def test_update_last_bar_updates_forming_mae() -> None:
    """Session forming ticks restore fills then re-apply the current bar high/low."""
    bars = _hist_bars()
    rt = Runtime(symbol="RTMAE")
    sess = rt.create_session(_SRC, bars, mode="interpret")
    last = dict(bars[-1])
    trade = sess.evaluator._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(0.0)

    tick1 = dict(last)
    tick1.update({"high": 120.0, "low": 119.5, "close": 119.8})
    out1 = sess.update_last_bar(tick1)
    assert "error" not in out1, out1.get("error")
    trade = sess.evaluator._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(20.0)
    assert trade.max_drawdown == pytest.approx(0.0)
    assert out1["series"]["ru"][-1] == pytest.approx(20.0)
    assert out1["series"]["ps"][-1] == pytest.approx(1.0)
    assert out1["series"]["ct"][-1] == pytest.approx(0.0)

    tick2 = dict(last)
    tick2.update({"high": 120.0, "low": 90.0, "close": 100.0})
    out2 = sess.update_last_bar(tick2)
    assert "error" not in out2, out2.get("error")
    trade = sess.evaluator._strategy_state.open_trades[0]
    assert trade.max_runup == pytest.approx(20.0)
    assert trade.max_drawdown == pytest.approx(10.0)
    assert out2["series"]["ru"][-1] == pytest.approx(20.0)
    assert out2["series"]["dd"][-1] == pytest.approx(10.0)
    assert out2["series"]["ps"][-1] == pytest.approx(1.0)
    kinds = [str(e.get("kind")) for e in (out2.get("events") or [])]
    assert kinds.count("entry") == 1
    assert kinds.count("close") == 0
