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

"""Intratick order inside one OHLC print (D-01 / D-03 residuals).

The OHLC print is the finest path Pyne models. Pine does not specify
intratick order, so both hosts pin one convention, applied per tick and per
print alike (see docs/known_divergences.md):

    favorable extreme first (ratchet the trail / accumulate MFE),
    then the adverse extreme (fill test / MAE attribution).

Consequences pinned here:

* a short-side trail on one print ratchets from the low, then tests the high;
  a print whose open sits above the ratcheted stop fills at the open (the
  mirror of the pinned long case);
* MAE/MFE is order-invariant per leg (both extremes are applied before the
  closed trade record is written), so the closed leg sees the whole print;
* on a partial close the *leftover* leg keeps the leg's accumulated extremes
  (interpret historically dropped them; the compile broker keeps them);
* ``InterpretSession.update_last_bar`` re-applies the forming print's envelope
  in the same two phases as the feed tick path (before fills / after fills),
  so a re-tick that fills keeps the print's envelope on the closed and the
  newly opened leg. ``append_bars([])`` confirmation applies the same
  two-phase re-apply when it re-commits the forming bar.
"""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.runtime import Runtime


_TS0 = 1_704_067_200_000
_DAY = 86_400_000


def _bar(i: int, o: float, h: float, low: float, c: float) -> dict[str, float | int]:
    return {
        "time": _TS0 + i * _DAY,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": 1000.0,
    }


def _series(out: dict[str, Any], name: str) -> list[float]:
    assert "error" not in out, out.get("error")
    return [float(v) for v in out["series"][name]]


def _trail_fill_stop(out: dict[str, Any]) -> float:
    fills = [
        ev
        for ev in (out.get("events") or [])
        if ev.get("kind") == "order" and ev.get("id") == "XT" and str(ev.get("comment") or "").startswith("fill")
    ]
    assert len(fills) == 1, fills
    return float(fills[0]["stop"])


_SRC_SHORT_TRAIL = """//@version=5
strategy("trail short print", commission_value=0)
if bar_index == 0
    strategy.entry("S", strategy.short, qty=1)
if bar_index == 1
    strategy.exit("XT", trail_offset=100)
plot(strategy.position_size, "ps")
plot(strategy.closedtrades, "ct")
plot(strategy.closedtrades.exit_price(0), "xp")
plot(strategy.closedtrades.profit(0), "pnl")
plot(high, "h")
plot(low, "l")
"""


def test_short_trail_print_favorable_first_dual_host() -> None:
    """Short mirror of the pinned long print.

    Print: open 95, high 99.5, low 90.0, close 94.0. Favorable-first applies
    the low first (stop 101 -> 91), then the high tests the stop: 99.5 >= 91
    fills at the open 95 (open is through the ratcheted stop). Ordering the
    high first (adverse-first) would test 99.5 against the pre-print stop of
    101.0 and leave the position open — not the chosen convention.
    """
    bars = [
        _bar(0, 100.0, 100.0, 100.0, 100.0),
        _bar(1, 100.0, 100.0, 100.0, 100.0),
        _bar(2, 95.0, 99.5, 90.0, 94.0),
    ]
    interp = Runtime(symbol="INTRATICK").run(_SRC_SHORT_TRAIL, [dict(b) for b in bars], mode="interpret")
    compiled = Runtime(symbol="INTRATICK").run(_SRC_SHORT_TRAIL, [dict(b) for b in bars], mode="compile")
    for name, out in (("interpret", interp), ("compile", compiled)):
        assert "error" not in out, (name, out.get("error"))
    # mintick 0.01, trail_offset 100 ticks = 1.0 → stop after bar 1 print is 99.0;
    # after this print's low (90.0): 91.0. Both hosts agree on the fill.
    assert _series(interp, "ps") == pytest.approx(_series(compiled, "ps"))
    assert _series(interp, "ps") == pytest.approx([0.0, -1.0, 0.0])
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 1.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 95.0])
    assert _series(interp, "pnl") == pytest.approx([0.0, 0.0, 5.0])
    assert _trail_fill_stop(interp) == pytest.approx(91.0)
    assert _trail_fill_stop(compiled) == pytest.approx(91.0)


def test_closed_leg_keeps_both_extremes_from_one_print_dual_host() -> None:
    """A leg opened and closed across two prints attributes both extremes.

    Order of high vs low inside a print never changes the result: both
    extremes are folded into the leg before the closed record is copied.
    """
    src = """//@version=5
strategy("mfe one print", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
if bar_index == 1
    strategy.exit("X", from_entry="L", limit=110.0, qty=2)
plot(strategy.closedtrades.max_runup(0), "ru")
plot(strategy.closedtrades.max_drawdown(0), "dd")
"""
    bars = [
        _bar(0, 100.0, 105.0, 95.0, 100.0),  # entry fills at bar 1 open (100.0)
        _bar(1, 100.0, 104.0, 97.0, 101.0),  # exit placed; cannot fill same bar
        _bar(2, 101.0, 130.0, 70.0, 108.0),  # limit 110 fills here; one print spans both extremes
    ]
    outs = {}
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="INTRATICK").run(src, [dict(b) for b in bars], mode=mode)
        assert "error" not in out, (mode, out.get("error"))
        outs[mode] = out
    for mode, out in outs.items():
        # Closed leg saw high 130 (ru 30 * 2 = 60) and low 70 (dd 30 * 2 = 60).
        assert _series(out, "ru")[-1] == pytest.approx(60.0), mode
        assert _series(out, "dd")[-1] == pytest.approx(60.0), mode


_PARTIAL_SRC = """//@version=5
strategy("partial keep extremes", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=3)
if bar_index == 1
    strategy.exit("X", from_entry="L", limit=110.0, qty=1)
plot(strategy.opentrades.max_runup(0), "ru")
plot(strategy.opentrades.max_drawdown(0), "dd")
plot(strategy.closedtrades.max_runup(0), "cru")
"""

_PARTIAL_BARS = [
    _bar(0, 100.0, 120.0, 90.0, 100.0),
    _bar(1, 100.0, 121.0, 95.0, 101.0),  # exit placed; fills from bar 2
    _bar(2, 101.0, 112.0, 100.0, 108.0),  # 1 of 3 exits at 110.0
]


def test_partial_close_leftover_leg_keeps_extremes_interpret() -> None:
    """Leftover leg after a partial close keeps the leg's accumulated MAE/MFE."""
    out = Runtime(symbol="INTRATICK").run(_PARTIAL_SRC, [dict(b) for b in _PARTIAL_BARS], mode="interpret")
    assert "error" not in out, out.get("error")
    # Leg: entry 100, high 121 => runup 21 * 3 = 63; the partial exit closes 1 of 3.
    assert _series(out, "ru")[2] == pytest.approx(63.0)
    assert _series(out, "dd")[2] == pytest.approx(15.0)  # (100 - 95) * 3 = 15
    # The closed record carries the same leg extremes.
    assert _series(out, "cru")[2] == pytest.approx(63.0)


def test_partial_close_leftover_leg_keeps_extremes_compile() -> None:
    out = Runtime(symbol="INTRATICK").run(_PARTIAL_SRC, [dict(b) for b in _PARTIAL_BARS], mode="compile")
    assert "error" not in out, out.get("error")
    assert _series(out, "ru")[2] == pytest.approx(63.0)
    assert _series(out, "dd")[2] == pytest.approx(15.0)
    assert _series(out, "cru")[2] == pytest.approx(63.0)


def _session(bars: list[dict[str, Any]]):
    return Runtime(symbol="INTRASES").create_session(
        _RETICK_SRC,
        [dict(b) for b in bars],
        mode="interpret",
    )


_RETICK_SRC = """//@version=5
strategy("retick mae", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 1
    strategy.exit("X", from_entry="L", limit=110.0)
plot(strategy.position_size, "ps")
plot(strategy.closedtrades.max_runup(0), "ru")
plot(strategy.closedtrades.max_drawdown(0), "dd")
plot(strategy.opentrades.max_runup(0), "oru")
plot(strategy.opentrades.max_drawdown(0), "odd")
"""


def _retick_bars() -> list[dict[str, float | int]]:
    return [
        _bar(0, 100.0, 105.0, 95.0, 100.0),
        _bar(1, 100.0, 104.0, 98.0, 102.0),
        _bar(2, 102.0, 104.0, 101.0, 103.0),
    ]


def test_update_last_bar_closing_fill_keeps_retick_envelope() -> None:
    """A re-tick that fills the exit keeps that print's envelope on the closed leg.

    Two re-ticks of the same forming bar: the second extends the low. The
    closed trade must see the *cumulative* envelope after the restore +
    re-apply (mirror of the feed path's two-phase apply).
    """
    bars = _retick_bars()
    sess = _session(bars)
    ts = bars[-1]["time"]

    tick1 = dict(bars[-1])
    tick1.update({"high": 115.0, "low": 111.0, "close": 112.0})
    out1 = sess.update_last_bar(tick1)
    assert "error" not in out1, out1.get("error")
    closed = list(sess.evaluator._strategy_state.closed_trades)
    assert len(closed) == 1
    assert closed[0].entry_price == pytest.approx(100.0)
    assert closed[0].exit_price == pytest.approx(110.0)
    assert closed[0].max_runup == pytest.approx(15.0)  # 115 - 100
    assert closed[0].max_drawdown == pytest.approx(2.0)  # bar 1 low 98

    tick2 = dict(bars[-1])
    tick2.update({"high": 115.0, "low": 90.0, "close": 111.0})
    out2 = sess.update_last_bar(tick2)
    assert "error" not in out2, out2.get("error")
    closed = list(sess.evaluator._strategy_state.closed_trades)
    assert len(closed) == 1
    assert closed[0].max_runup == pytest.approx(15.0)
    assert closed[0].max_drawdown == pytest.approx(10.0)  # 100 - 90


_ENTRY_SRC = """//@version=5
strategy("retick entry envelope", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
plot(strategy.position_size, "ps")
plot(strategy.opentrades.max_runup(0), "ru")
plot(strategy.opentrades.max_drawdown(0), "dd")
"""


def test_update_last_bar_opening_fill_keeps_retick_envelope() -> None:
    """A limit entry filled by a re-tick sees that print's envelope."""
    bars = _retick_bars()
    sess = Runtime(symbol="INTRASES2").create_session(_ENTRY_SRC, [dict(b) for b in bars], mode="interpret")
    tick = dict(bars[-1])
    tick.update({"open": 97.0, "high": 102.0, "low": 90.0, "close": 94.0})  # low crosses 95 limit
    out = sess.update_last_bar(tick)
    assert "error" not in out, out.get("error")
    trades = list(sess.evaluator._strategy_state.open_trades)
    assert len(trades) == 1
    assert trades[0].entry_price == pytest.approx(95.0)
    # New leg sees the full print: runup 102-95 = 7, drawdown 95-90 = 5.
    assert trades[0].max_runup == pytest.approx(7.0)
    assert trades[0].max_drawdown == pytest.approx(5.0)


_SAME_TICK_SRC = """//@version=6
strategy("retick same-tick open close", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
    strategy.order("S", strategy.short, qty=1, limit=110.0)
plot(strategy.closedtrades.max_runup(0), "ru")
plot(strategy.closedtrades.max_drawdown(0), "dd")
plot(strategy.closedtrades, "ct")
plot(strategy.position_size, "ps")
"""


def test_update_last_bar_same_print_open_and_close_keeps_envelope() -> None:
    """Entry and exit filled by one re-tick keep that print's envelope."""
    bars = [
        _bar(0, 100.0, 101.0, 99.0, 100.0),
        _bar(1, 100.0, 100.5, 99.5, 100.0),
    ]
    sess = Runtime(symbol="INTRASES3").create_session(_SAME_TICK_SRC, [dict(b) for b in bars], mode="interpret")
    tick = dict(bars[-1])
    tick.update({"open": 100.0, "high": 120.0, "low": 80.0, "close": 100.0})
    out = sess.update_last_bar(tick)
    assert "error" not in out, out.get("error")
    closed = list(sess.evaluator._strategy_state.closed_trades)
    assert len(closed) == 1, [vars(t) for t in closed]
    # Long leg entered at 95 (limit), closed at 110 (limit). Print spans 80..120.
    assert closed[0].entry_price == pytest.approx(95.0)
    assert closed[0].exit_price == pytest.approx(110.0)
    assert closed[0].max_runup == pytest.approx(25.0)  # 120 - 95
    assert closed[0].max_drawdown == pytest.approx(15.0)  # 95 - 80


# ---------------------------------------------------------------------------
# Confirmation path (append_bars -> _confirm_forming_last_bar)
#
# Confirming the forming bar must re-apply the same two-phase envelope as
# ``update_last_bar``: phase 1 after the broker restore (closed leg keeps the
# print), phase 2 after the confirmation fills (opened leg keeps the print).
# ---------------------------------------------------------------------------


def _entry_session(symbol: str, bars: list[dict[str, Any]]):
    return Runtime(symbol=symbol).create_session(_ENTRY_SRC, [dict(b) for b in bars], mode="interpret")


def test_confirm_closing_fill_matches_update_last_bar() -> None:
    """Confirmation keeps the same envelope on the closed leg as update_last_bar."""
    bars = _retick_bars()
    tick = dict(bars[-1])
    tick.update({"high": 115.0, "low": 90.0, "close": 111.0})

    # Path A: re-tick only (no confirmation).
    sess_a = Runtime(symbol="INTRACONFA").create_session(_RETICK_SRC, [dict(b) for b in bars], mode="interpret")
    out_a = sess_a.update_last_bar(dict(tick))
    assert "error" not in out_a, out_a.get("error")
    closed_a = list(sess_a.evaluator._strategy_state.closed_trades)
    assert len(closed_a) == 1

    # Path B: re-tick, then confirm in place via an empty append.
    sess_b = Runtime(symbol="INTRACONFB").create_session(_RETICK_SRC, [dict(b) for b in bars], mode="interpret")
    out_b = sess_b.update_last_bar(dict(tick))
    assert "error" not in out_b, out_b.get("error")
    confirmed = sess_b.append_bars([])
    assert "error" not in confirmed, confirmed.get("error")
    closed_b = list(sess_b.evaluator._strategy_state.closed_trades)
    assert len(closed_b) == 1
    assert closed_b[0].entry_price == pytest.approx(closed_a[0].entry_price)
    assert closed_b[0].exit_price == pytest.approx(closed_a[0].exit_price)
    assert closed_b[0].max_runup == pytest.approx(closed_a[0].max_runup)
    assert closed_b[0].max_drawdown == pytest.approx(closed_a[0].max_drawdown)
    # Absolute pins: print spans 90..115, entry at 100.
    assert closed_b[0].max_runup == pytest.approx(15.0)
    assert closed_b[0].max_drawdown == pytest.approx(10.0)


def test_confirm_opening_fill_matches_update_last_bar() -> None:
    """A leg opened by the re-tick keeps the print's envelope after confirmation."""
    bars = _retick_bars()
    tick = dict(bars[-1])
    tick.update({"open": 97.0, "high": 102.0, "low": 90.0, "close": 94.0})

    sess_a = _entry_session("INTRACONFC", bars)
    out_a = sess_a.update_last_bar(dict(tick))
    assert "error" not in out_a, out_a.get("error")
    open_a = list(sess_a.evaluator._strategy_state.open_trades)
    assert len(open_a) == 1

    sess_b = _entry_session("INTRACONFD", bars)
    out_b = sess_b.update_last_bar(dict(tick))
    assert "error" not in out_b, out_b.get("error")
    confirmed = sess_b.append_bars([])
    assert "error" not in confirmed, confirmed.get("error")
    open_b = list(sess_b.evaluator._strategy_state.open_trades)
    assert len(open_b) == 1
    assert open_b[0].entry_price == pytest.approx(open_a[0].entry_price)
    assert open_b[0].max_runup == pytest.approx(open_a[0].max_runup)
    assert open_b[0].max_drawdown == pytest.approx(open_a[0].max_drawdown)
    # Absolute pins: print spans 90..102, entry limited at 95.
    assert open_b[0].entry_price == pytest.approx(95.0)
    assert open_b[0].max_runup == pytest.approx(7.0)
    assert open_b[0].max_drawdown == pytest.approx(5.0)


def test_confirm_same_print_open_and_close_matches_update_last_bar() -> None:
    """A same-print open+close re-tick keeps the print's envelope after confirmation."""
    bars = [
        _bar(0, 100.0, 101.0, 99.0, 100.0),
        _bar(1, 100.0, 100.5, 99.5, 100.0),
    ]
    tick = dict(bars[-1])
    tick.update({"open": 100.0, "high": 120.0, "low": 80.0, "close": 100.0})

    sess_a = Runtime(symbol="INTRACONFE").create_session(_SAME_TICK_SRC, [dict(b) for b in bars], mode="interpret")
    out_a = sess_a.update_last_bar(dict(tick))
    assert "error" not in out_a, out_a.get("error")
    closed_a = list(sess_a.evaluator._strategy_state.closed_trades)
    assert len(closed_a) == 1

    sess_b = Runtime(symbol="INTRACONFF").create_session(_SAME_TICK_SRC, [dict(b) for b in bars], mode="interpret")
    out_b = sess_b.update_last_bar(dict(tick))
    assert "error" not in out_b, out_b.get("error")
    confirmed = sess_b.append_bars([])
    assert "error" not in confirmed, confirmed.get("error")
    closed_b = list(sess_b.evaluator._strategy_state.closed_trades)
    assert len(closed_b) == 1
    assert closed_b[0].entry_price == pytest.approx(closed_a[0].entry_price)
    assert closed_b[0].exit_price == pytest.approx(closed_a[0].exit_price)
    assert closed_b[0].max_runup == pytest.approx(closed_a[0].max_runup)
    assert closed_b[0].max_drawdown == pytest.approx(closed_a[0].max_drawdown)
    # Absolute pins: entry 95, closed at 110, print spans 80..120.
    assert closed_b[0].max_runup == pytest.approx(25.0)
    assert closed_b[0].max_drawdown == pytest.approx(15.0)


def test_confirm_applies_envelope_after_fills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirmation re-applies the print's envelope *after* its fills run.

    White-box pin for the phase-2 half of the two-phase contract: without a
    post-fill application, a leg opened by the confirmation's fills relies
    solely on the broker's internal per-fill apply and the path diverges
    from update_last_bar's explicit phase 2.
    """
    bars = _retick_bars()
    sess = _session(bars)
    ev = sess.evaluator
    orig_ppo = ev.process_pending_orders
    orig_extremes = ev.update_open_trade_extremes
    events: list[str] = []

    def ppo_spy(**kwargs: Any):
        result = orig_ppo(**kwargs)
        events.append("ppo-done")
        return result

    def extremes_spy(high, low):
        events.append("extremes")
        return orig_extremes(high, low)

    monkeypatch.setattr(ev, "process_pending_orders", ppo_spy)
    monkeypatch.setattr(ev, "update_open_trade_extremes", extremes_spy)

    out = sess.update_last_bar(dict(bars[-1], high=115.0, low=90.0, close=111.0))
    assert "error" not in out, out.get("error")
    events.clear()
    confirmed = sess.append_bars([])
    assert "error" not in confirmed, confirmed.get("error")
    assert "ppo-done" in events, events
    last_ppo = max(i for i, e in enumerate(events) if e == "ppo-done")
    assert any(e == "extremes" for e in events[last_ppo + 1 :]), events
