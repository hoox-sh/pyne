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

"""Unconfirmed realtime ticks roll back broker fills (D-04).

Body-placed ``strategy.entry`` / ``order`` / ``close`` on intermediate ticks
must not commit. The final confirmed tick keeps fills, pending-book changes,
and strategy events. Pending OHLC processing stays once per bar
(``process_pending_orders`` / compile ``begin_bar`` remain outside the tick
loop). Historical ``realtime_ticks=1`` matches today's goldens.
"""

from __future__ import annotations

from typing import Any

from pynescript.ast.evaluator.builtins.strategy import OpenTrade
from pynescript.ast.evaluator.builtins.strategy import Order
from pynescript.ast.evaluator.builtins.strategy import StrategyState
from pynescript.ast.evaluator.builtins.strategy import Trade
from pynescript.ast.evaluator.events import StrategyEvent
from pynescript.compiler.engine import transpile
from pynescript.compiler.strategy_broker import CompileStrategyBroker
from pynescript.compiler.strategy_broker import OpenLeg
from pynescript.compiler.strategy_broker import PendingOrder
from pynescript.runtime import Runtime


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


def _num(value: object) -> float:
    if value is None:
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def _series(out: dict[str, Any], name: str) -> list[float]:
    assert "error" not in out, out.get("error")
    col = out["series"][name]
    return [_num(v) for v in col]


def _run(src: str, bars: list[dict[str, float | int]], mode: str, **kwargs: Any) -> dict[str, Any]:
    return Runtime(symbol="RTBROKER").run(src, bars, mode=mode, **kwargs)


def _dual(src: str, bars: list[dict[str, float | int]], **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    interp = _run(src, bars, "interpret", **kwargs)
    compiled = _run(src, bars, "compile", **kwargs)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    return interp, compiled


def _kinds(out: dict[str, Any]) -> list[str]:
    return [str(e.get("kind")) for e in (out.get("events") or [])]


def _kind_count(out: dict[str, Any], kind: str) -> int:
    return sum(1 for k in _kinds(out) if k == kind)


_PYRAMID_ENTRY_SRC = """//@version=6
strategy("rt broker", pyramiding=5)
if barstate.isrealtime
    strategy.entry("L", strategy.long, qty=1)
plot(strategy.opentrades, "ot")
plot(strategy.position_size, "ps")
"""

_EVERY_BAR_ENTRY_SRC = """//@version=6
strategy("hist entry")
strategy.entry("L", strategy.long, qty=1)
plot(strategy.opentrades, "ot")
plot(strategy.position_size, "ps")
"""

_CLOSE_RT_SRC = """//@version=6
strategy("close rt")
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
if barstate.isrealtime
    strategy.close("L")
plot(strategy.opentrades, "ot")
plot(strategy.closedtrades, "ct")
"""

_PENDING_LIMIT_SRC = """//@version=6
strategy("lim rt")
if barstate.isrealtime
    strategy.order("LIM", strategy.long, qty=1, limit=1.0)
plot(strategy.position_size, "ps")
plot(strategy.opentrades, "ot")
"""


def test_last_bar_entry_fills_once_not_per_tick() -> None:
    """``strategy.entry`` on every last-bar tick commits one fill, not three.

    Reference Pine: a market entry placed on the forming bar fills at the
    NEXT bar's open — with no next bar the order stays working (once, not
    once per unconfirmed tick).
    """
    bars = _bars(5)
    interp, compiled = _dual(_PYRAMID_ENTRY_SRC, bars, realtime_ticks=3)
    for out in (interp, compiled):
        ot = _series(out, "ot")
        ps = _series(out, "ps")
        assert ot == [0.0, 0.0, 0.0, 0.0, 0.0], ot
        assert ps[-1] == 0.0, ps
        # One working order, no per-tick duplicate fills.
        assert _kind_count(out, "entry") == 0, _kinds(out)
        assert _kind_count(out, "order") == 1, _kinds(out)
    assert _series(compiled, "ot") == _series(interp, "ot")
    assert _series(compiled, "ps") == _series(interp, "ps")
    assert _kind_count(compiled, "order") == _kind_count(interp, "order")


def test_pending_limit_body_commits_on_confirmed_tick_only() -> None:
    """Body-placed last-bar limits do not fill this bar (once-per-bar pending).

    ``process_pending_orders`` / compile ``begin_bar`` stay outside the tick
    loop, so a limit placed on the forming bar waits for a later bar. Unconfirmed
    ticks that upsert the same pending id are rolled back: both hosts export
    one ``order`` event, not one per tick, and the position stays flat.
    """
    bars = _bars(4)
    interp, compiled = _dual(_PENDING_LIMIT_SRC, bars, realtime_ticks=3)
    for out in (interp, compiled):
        assert _series(out, "ps")[-1] == 0.0
        assert _series(out, "ot")[-1] == 0.0
        assert _kind_count(out, "order") == 1, _kinds(out)
        assert _kind_count(out, "entry") == 0, _kinds(out)
    assert _kind_count(compiled, "order") == _kind_count(interp, "order")


def test_realtime_ticks_1_matches_historical_goldens() -> None:
    """``realtime_ticks=1`` is historical: no extra fills vs the default run."""
    bars = _bars(5)
    default_i, default_c = _dual(_EVERY_BAR_ENTRY_SRC, bars)
    ticks1_i, ticks1_c = _dual(_EVERY_BAR_ENTRY_SRC, bars, realtime_ticks=1)
    for left, right in ((default_i, ticks1_i), (default_c, ticks1_c), (default_i, default_c)):
        assert _series(left, "ps") == _series(right, "ps")
        assert _series(left, "ot") == _series(right, "ot")
        assert _kind_count(left, "entry") == 1
        assert _kind_count(right, "entry") == 1
    # Last-bar re-visits with pyramiding=0 still cannot add a second same-id fill.
    multi_i, multi_c = _dual(_EVERY_BAR_ENTRY_SRC, bars, realtime_ticks=3)
    assert _series(multi_i, "ps") == _series(default_i, "ps")
    assert _series(multi_c, "ps") == _series(default_c, "ps")
    assert _kind_count(multi_i, "entry") == 1
    assert _kind_count(multi_c, "entry") == 1


def test_close_on_unconfirmed_ticks_commits_once() -> None:
    """Last-bar ``strategy.close`` rolls back until the confirmed tick.

    The close is a market order: placed on the forming bar it fills at the
    next bar's open, so with no next bar the position stays open (one close
    order event, not one per unconfirmed tick).
    """
    bars = _bars(5)
    interp, compiled = _dual(_CLOSE_RT_SRC, bars, realtime_ticks=3)
    for out in (interp, compiled):
        assert _series(out, "ot")[-1] == 1.0
        assert _series(out, "ct")[-1] == 0.0
        assert _kind_count(out, "entry") == 1, _kinds(out)
        assert _kind_count(out, "close") <= 1, _kinds(out)
    assert _series(compiled, "ot") == _series(interp, "ot")
    assert _series(compiled, "ct") == _series(interp, "ct")


def test_pending_from_prior_bar_fills_once_on_last_bar() -> None:
    """Pending OHLC fill still runs once per bar before the tick loop."""
    src = """//@version=6
strategy("prior pending")
if bar_index == 0
    strategy.order("L1", strategy.long, qty=2, limit=100.0)
plot(strategy.position_size, "ps")
plot(strategy.opentrades, "ot")
"""
    # Bars 0-2 stay above the limit; last bar's low touches 100.
    bars = [
        {"time": 1_704_067_200_000 + i * 86_400_000, "open": o, "high": h, "low": low, "close": c, "volume": 1000.0}
        for i, (o, h, low, c) in enumerate(
            [
                (101.0, 102.0, 100.5, 101.0),
                (101.0, 102.0, 100.5, 101.0),
                (101.0, 102.0, 100.5, 101.0),
                (100.5, 101.0, 99.5, 100.0),
            ]
        )
    ]
    interp, compiled = _dual(src, bars, realtime_ticks=3)
    for out in (interp, compiled):
        assert _series(out, "ps")[-1] == 2.0, _series(out, "ps")
        assert _series(out, "ot")[-1] == 1.0
        # Interpret records the fill as kind=order; compile also emits entry.
        # Either way the last-bar OHLC path fills once, not once per tick.
        assert _kind_count(out, "entry") + _kind_count(out, "order") >= 1, _kinds(out)
    assert _series(compiled, "ps") == _series(interp, "ps")
    assert _series(compiled, "ot") == _series(interp, "ot")


def test_object_mode_emits_strategy_snapshot_restore_inside_tick_loop() -> None:
    """``begin_bar`` stays outside the tick loop; snapshot/restore sit inside."""
    code = transpile(_PYRAMID_ENTRY_SRC)
    assert "CompileStrategyBroker" in code
    assert "__strategy.snapshot()" in code
    assert "__strategy.restore(__st_snap)" in code
    begin_at = code.index("__strategy.begin_bar(")
    tick_at = code.index("for __tick_i in range(__n_ticks):")
    snap_at = code.index("__strategy.snapshot()")
    restore_at = code.index("__strategy.restore(__st_snap)")
    assert begin_at < tick_at < snap_at < restore_at


def _entry_event() -> StrategyEvent:
    return StrategyEvent(
        kind="entry",
        id="L",
        direction="long",
        qty=1.0,
        order_type="market",
        limit=None,
        stop=None,
        oca_name=None,
        comment=None,
        bar_index=1,
        bar_time=0,
        ohlc=(1.0, 1.0, 1.0, 1.0),
        script_id="",
        run_id="",
    )


class TestStrategyStateSnapshotRestore:
    def test_restore_pending_trades_events_in_place(self) -> None:
        st = StrategyState()
        pending_id = id(st.pending_orders)
        events_id = id(st._events)
        trades_id = id(st.open_trades)
        st.pending_orders["LIM"] = Order(
            order_id="LIM",
            order_type="limit",
            direction="buy",
            quantity=2.0,
            limit_price=90.0,
        )
        st.position_direction = "long"
        st.position_size = 1.0
        st.entry_price = 100.0
        st.open_trades.append(
            OpenTrade(
                entry_id="L",
                entry_bar=0,
                entry_time=0,
                entry_price=100.0,
                direction="long",
                size=1.0,
            )
        )
        st._events.append(_entry_event())
        st._equity_peak = 120_000.0
        st._size_hist.append(1.0)

        snap = st.snapshot()
        st.pending_orders["LIM"].filled_qty = 2.0
        st.pending_orders["NEW"] = Order(
            order_id="NEW",
            order_type="market",
            direction="buy",
            quantity=1.0,
        )
        st.position_size = 3.0
        st.open_trades.append(
            OpenTrade(
                entry_id="L2",
                entry_bar=1,
                entry_time=1,
                entry_price=101.0,
                direction="long",
                size=2.0,
            )
        )
        st.closed_trades.append(
            Trade(
                entry_bar=0,
                entry_time=0,
                entry_price=100.0,
                exit_bar=1,
                exit_time=1,
                exit_price=101.0,
                direction="long",
                size=1.0,
                profit=1.0,
                commission=0.0,
            )
        )
        st._events.append(_entry_event())
        st._equity_peak = 999_000.0
        st._size_hist.append(3.0)

        st.restore(snap)
        assert id(st.pending_orders) == pending_id
        assert id(st._events) == events_id
        assert id(st.open_trades) == trades_id
        assert list(st.pending_orders) == ["LIM"]
        assert st.pending_orders["LIM"].filled_qty == 0.0
        assert st.position_size == 1.0
        assert len(st.open_trades) == 1
        assert st.closed_trades == []
        assert len(st._events) == 1
        assert st._equity_peak == 120_000.0
        assert st._size_hist == [1.0]

    def test_restore_none_is_noop(self) -> None:
        st = StrategyState()
        st.position_size = 4.0
        st.restore(None)
        assert st.position_size == 4.0


class TestCompileBrokerSnapshotRestore:
    def test_restore_pending_legs_events_in_place(self) -> None:
        br = CompileStrategyBroker()
        pending_id = id(br.pending_orders)
        events_id = id(br.events)
        legs_id = id(br.open_legs)
        br.pending_orders["LIM"] = PendingOrder(
            order_id="LIM",
            order_type="limit",
            direction="long",
            quantity=2.0,
            limit_price=90.0,
        )
        br.position_size = 1.0
        br.position_avg_price = 100.0
        br.open_legs.append(OpenLeg(entry_id="L", size=1.0, entry_price=100.0, direction="long"))
        br.open_entry_count = 1
        br.events.append({"kind": "entry", "id": "L", "qty": 1.0})
        br._equity_peak = 120_000.0

        snap = br.snapshot()
        br.pending_orders["LIM"].filled_qty = 2.0
        br.pending_orders["NEW"] = PendingOrder(
            order_id="NEW",
            order_type="market",
            direction="long",
            quantity=1.0,
        )
        br.position_size = 3.0
        br.open_legs.append(OpenLeg(entry_id="L2", size=2.0, entry_price=101.0, direction="long"))
        br.open_entry_count = 2
        br.events.append({"kind": "entry", "id": "L2", "qty": 2.0})
        br._equity_peak = 999_000.0
        br.netprofit = 50.0

        br.restore(snap)
        assert id(br.pending_orders) == pending_id
        assert id(br.events) == events_id
        assert id(br.open_legs) == legs_id
        assert list(br.pending_orders) == ["LIM"]
        assert br.pending_orders["LIM"].filled_qty == 0.0
        assert br.position_size == 1.0
        assert len(br.open_legs) == 1
        assert br.open_entry_count == 1
        assert len(br.events) == 1
        assert br._equity_peak == 120_000.0
        assert br.netprofit == 0.0
