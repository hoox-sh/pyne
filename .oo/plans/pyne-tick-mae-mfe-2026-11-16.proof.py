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

"""Proof: tick-accurate MAE/MFE on the interpret feed tick path (D-03).

Entry ticks: a pending limit/stop filled on a tick counts that tick's envelope
after the fill; pre-entry ticks must not inflate the trade's extremes.
Exit ticks: a trade closed by a tick fill keeps the exit tick's envelope
(pre-fill apply) while the entry fill still sees its own tick (post-fill).
"""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


_TS0 = 1_704_067_200_000
_DAY = 86_400_000

_ENTRY_LIMIT_SRC = """//@version=6
strategy("tick mae fill", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
plot(strategy.opentrades.max_runup(0), "ru")
plot(strategy.opentrades.max_drawdown(0), "dd")
plot(strategy.position_size, "ps")
"""

_ENTRY_STOP_SRC = """//@version=6
strategy("tick mae stop", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, stop=105.0)
plot(strategy.opentrades.max_runup(0), "ru")
plot(strategy.opentrades.max_drawdown(0), "dd")
plot(strategy.position_size, "ps")
"""

_EXIT_LIMIT_SRC = """//@version=6
strategy("tick exit limit", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 1
    strategy.exit("X", "L", limit=110.0)
plot(strategy.closedtrades.max_runup(0), "cru")
plot(strategy.closedtrades.max_drawdown(0), "cdd")
plot(strategy.closedtrades, "ct")
"""

_EXIT_STOP_SRC = """//@version=6
strategy("tick exit stop", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 1
    strategy.exit("X", "L", stop=90.0)
plot(strategy.closedtrades.max_runup(0), "cru")
plot(strategy.closedtrades.max_drawdown(0), "cdd")
plot(strategy.closedtrades, "ct")
"""


def _bars() -> list[dict[str, float | int]]:
    return [
        {
            "time": _TS0 + i * _DAY,
            "open": 100.0,
            "high": 101.0,
            "low": 100.2,
            "close": 100.8,
            "volume": 1000.0,
        }
        for i in range(5)
    ]


def _entry_limit_candles() -> list[list[float | int]]:
    ts = _TS0 + 4 * _DAY
    return [
        [ts, 100.5, 120.0, 119.5, 119.8, 10.0],
        [ts, 100.5, 118.0, 117.0, 117.5, 11.0],
        [ts, 100.5, 100.0, 94.0, 96.0, 12.0],
    ]


def _entry_stop_candles() -> list[list[float | int]]:
    ts = _TS0 + 4 * _DAY
    return [
        [ts, 100.5, 100.0, 80.0, 100.0, 10.0],
        [ts, 100.5, 110.0, 90.0, 108.0, 11.0],
        [ts, 100.5, 110.0, 90.0, 108.0, 12.0],
    ]


def _exit_limit_candles() -> list[list[float | int]]:
    ts = _TS0 + 4 * _DAY
    return [
        [ts, 100.0, 115.0, 95.0, 100.0, 10.0],
        [ts, 100.0, 118.0, 92.0, 100.0, 11.0],
        [ts, 100.0, 120.0, 90.0, 100.0, 12.0],
    ]


def _exit_stop_candles() -> list[list[float | int]]:
    ts = _TS0 + 4 * _DAY
    return [
        [ts, 100.0, 115.0, 95.0, 100.0, 10.0],
        [ts, 100.0, 118.0, 92.0, 100.0, 11.0],
        [ts, 100.0, 120.0, 80.0, 100.0, 12.0],
    ]


def _run(src: str, candles: list[list[float | int]]) -> dict[str, Any]:
    out = Runtime(symbol="RTMAE").run(
        src,
        _bars(),
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )
    assert "error" not in out, out.get("error")
    return out


def _last(out: dict[str, Any], name: str) -> float:
    return float(out["series"][name][-1])


def _session(src: str, candles: list[list[float | int]]) -> Any:
    return Runtime(symbol="RTMAE").create_session(
        src,
        _bars(),
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=list(candles)),
    )


def main() -> None:
    entry = _run(_ENTRY_LIMIT_SRC, _entry_limit_candles())
    ru = _last(entry, "ru")
    dd = _last(entry, "dd")
    ps = _last(entry, "ps")
    assert ps == 1.0, ps
    assert ru == 5.0, ru
    assert dd == 1.0, dd
    assert ru != 25.0, ru  # bar envelope would count the pre-entry high 120

    entry_stop = _run(_ENTRY_STOP_SRC, _entry_stop_candles())
    sru = _last(entry_stop, "ru")
    sdd = _last(entry_stop, "dd")
    sps = _last(entry_stop, "ps")
    assert sps == 1.0, sps
    assert sru == 5.0, sru
    assert sdd == 15.0, sdd
    assert sdd != 25.0, sdd  # bar envelope would count the pre-entry low 80

    exit_limit = _run(_EXIT_LIMIT_SRC, _exit_limit_candles())
    cru = _last(exit_limit, "cru")
    cdd = _last(exit_limit, "cdd")
    ct = _last(exit_limit, "ct")
    assert ct == 1.0, ct
    assert cru == 20.0, cru
    assert cdd == 10.0, cdd

    exit_stop = _run(_EXIT_STOP_SRC, _exit_stop_candles())
    xru = _last(exit_stop, "cru")
    xdd = _last(exit_stop, "cdd")
    xct = _last(exit_stop, "ct")
    assert xct == 1.0, xct
    assert xru == 20.0, xru
    assert xdd == 20.0, xdd

    sess_entry = _session(_ENTRY_LIMIT_SRC, _entry_limit_candles())
    trade = sess_entry.evaluator._strategy_state.open_trades[0]
    assert trade.max_runup == 5.0, trade.max_runup
    assert trade.max_drawdown == 1.0, trade.max_drawdown

    sess_limit = _session(_EXIT_LIMIT_SRC, _exit_limit_candles())
    limit_trade = sess_limit.evaluator._strategy_state.closed_trades[0]
    assert limit_trade.max_runup == 20.0, limit_trade.max_runup
    assert limit_trade.max_drawdown == 10.0, limit_trade.max_drawdown

    sess_stop = _session(_EXIT_STOP_SRC, _exit_stop_candles())
    stop_trade = sess_stop.evaluator._strategy_state.closed_trades[0]
    assert stop_trade.max_runup == 20.0, stop_trade.max_runup
    assert stop_trade.max_drawdown == 20.0, stop_trade.max_drawdown

    print(
        f"TICK_MAE_OK tick={ru:.1f} dd={dd:.1f} stop_dd={sdd:.1f} "
        f"exit={cru:.1f}/{cdd:.1f} stop_exit={xru:.1f}/{xdd:.1f} "
        f"session={trade.max_runup:.1f} pos={ps:.1f}"
    )


if __name__ == "__main__":
    main()
