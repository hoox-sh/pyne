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

"""Same-tick entry and exit keep the fill print's MAE/MFE (D-03 residual).

Both orders are already pending. One polled OHLC print fills the entry and
the exit. The closed leg uses that print's high/low, not the pre-tick bar
``begin_bar`` stored. High-versus-low order inside the print is not modeled.
"""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


_LIMIT_SRC = """//@version=6
strategy("same tick limit oc", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
    strategy.order("S", strategy.short, qty=1, limit=110.0)
plot(strategy.closedtrades.max_runup(0), "cru")
plot(strategy.closedtrades.max_drawdown(0), "cdd")
plot(strategy.closedtrades.entry_price(0), "ep")
plot(strategy.closedtrades.exit_price(0), "xp")
plot(strategy.closedtrades, "ct")
plot(strategy.position_size, "ps")
"""

_STOP_SRC = """//@version=6
strategy("same tick stop oc", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, stop=105.0)
    strategy.order("S", strategy.short, qty=1, limit=130.0)
plot(strategy.closedtrades.max_runup(0), "cru")
plot(strategy.closedtrades.max_drawdown(0), "cdd")
plot(strategy.closedtrades.entry_price(0), "ep")
plot(strategy.closedtrades.exit_price(0), "xp")
plot(strategy.closedtrades, "ct")
plot(strategy.position_size, "ps")
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


def _limit_bars() -> list[dict[str, float | int]]:
    # Pre-tick last bar is 103 / 97. Limits 95 and 110 stay pending until the
    # fill print. That bar alone would be runup 8 / drawdown 0.
    return [
        _bar(100.0, 101.0, 99.0, 100.0, i=0),
        _bar(100.0, 102.0, 98.0, 100.0, i=1),
        _bar(100.0, 103.0, 97.0, 100.0, i=2),
    ]


def _limit_ticks() -> list[list[float | int]]:
    ts = _limit_bars()[-1]["time"]
    return [
        [ts, 100.0, 104.0, 96.0, 100.0, 10.0],
        [ts, 100.0, 104.0, 96.0, 100.0, 11.0],
        [ts, 100.0, 120.0, 80.0, 100.0, 12.0],
    ]


def _stop_bars() -> list[dict[str, float | int]]:
    # Low 50 never reaches the 105 stop, so it must not become drawdown.
    # High stays under 105 and under the 130 limit until the fill print.
    return [
        _bar(100.0, 101.0, 99.0, 100.0, i=0),
        _bar(100.0, 102.0, 50.0, 100.0, i=1),
        _bar(100.0, 104.0, 50.0, 100.0, i=2),
    ]


def _stop_ticks() -> list[list[float | int]]:
    ts = _stop_bars()[-1]["time"]
    return [
        [ts, 100.0, 104.0, 90.0, 100.0, 10.0],
        [ts, 100.0, 104.0, 90.0, 100.0, 11.0],
        [ts, 100.0, 140.0, 100.0, 120.0, 12.0],
    ]


def _copy_bars(bars: list[dict[str, float | int]]) -> list[dict[str, float | int]]:
    # The tick path overwrites the forming bar. A shared list would let
    # interpret's last print become compile's pre-tick bar.
    return [dict(bar) for bar in bars]


def _run(
    source: str,
    bars: list[dict[str, float | int]],
    ticks: list[list[float | int]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    feeds = [MockDataFeed(scripted=[list(t) for t in ticks]) for _ in range(2)]
    interp = Runtime(symbol="STOC").run(
        source,
        _copy_bars(bars),
        mode="interpret",
        realtime_ticks=3,
        data_feed=feeds[0],
    )
    compiled = Runtime(symbol="STOC").run(
        source,
        _copy_bars(bars),
        mode="compile",
        realtime_ticks=3,
        data_feed=feeds[1],
    )
    return interp, compiled


def _series(out: dict[str, Any], name: str) -> list[float]:
    assert "error" not in out, out.get("error")
    return [float(v) for v in out["series"][name]]


def _assert_hosts(interp: dict[str, Any], compiled: dict[str, Any]) -> None:
    assert interp.get("mode") == "interpret", interp.get("mode")
    assert compiled.get("mode") == "compile", compiled.get("mode")
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    for key in ("cru", "cdd", "ep", "xp", "ct", "ps"):
        left = _series(interp, key)
        right = _series(compiled, key)
        assert left == pytest.approx(right), (key, left, right)


def test_same_tick_limit_open_close_keeps_fill_tick_extremes() -> None:
    """Entry 95 and exit 110 in the 120 / 80 print: runup 25, drawdown 15.

    The pre-tick bar (103 / 97) would be runup 8 / drawdown 0.
    """
    interp, compiled = _run(_LIMIT_SRC, _limit_bars(), _limit_ticks())
    _assert_hosts(interp, compiled)
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 1.0])
    assert _series(interp, "ps") == pytest.approx([0.0, 0.0, 0.0])
    assert _series(interp, "ep") == pytest.approx([0.0, 0.0, 95.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 110.0])
    assert _series(interp, "cru") == pytest.approx([0.0, 0.0, 25.0])
    assert _series(interp, "cdd") == pytest.approx([0.0, 0.0, 15.0])


def test_same_tick_stop_open_close_ignores_pre_tick_low() -> None:
    """Stop entry 105 filled on 140 / 100: runup 35, drawdown 5.

    The pre-tick low 50 would be drawdown 55 if the stored bar leaked in.
    """
    interp, compiled = _run(_STOP_SRC, _stop_bars(), _stop_ticks())
    _assert_hosts(interp, compiled)
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 1.0])
    assert _series(interp, "ps") == pytest.approx([0.0, 0.0, 0.0])
    assert _series(interp, "ep") == pytest.approx([0.0, 0.0, 105.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 130.0])
    assert _series(interp, "cru") == pytest.approx([0.0, 0.0, 35.0])
    assert _series(interp, "cdd") == pytest.approx([0.0, 0.0, 5.0])


def test_same_tick_limit_open_close_session() -> None:
    """Session twin: the closed trade stores the fill print, not the pre-tick bar."""
    sess = Runtime(symbol="STOC").create_session(
        _LIMIT_SRC,
        _limit_bars(),
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=_limit_ticks()),
    )
    trade = sess.evaluator._strategy_state.closed_trades[0]
    assert trade.entry_price == pytest.approx(95.0)
    assert trade.exit_price == pytest.approx(110.0)
    assert trade.max_runup == pytest.approx(25.0)
    assert trade.max_drawdown == pytest.approx(15.0)
