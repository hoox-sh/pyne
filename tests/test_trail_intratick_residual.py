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

"""Pin trail ratchet parity: tick path vs one OHLC print (D-01 residual).

Interpret and compile already agree, so this file does not change the broker
and does not invent an open→high→low path inside one print.

* Across feed ticks the stop follows prices the tick path has already seen.
  An earlier peak (or trough) stays in the stop after unconfirmed fills roll
  back. A later print can fill against that stop even when its own high/low
  would not arm it, and even when the stored bar no longer contains the peak.
* Inside one OHLC print the intratick convention is now pinned on both hosts
  (2026-11-19): the favorable extreme is applied first (trail ratchet / MFE),
  then the adverse extreme is tested against the stop (MAE). Pine does not
  model intra-print order; this is a pinned convention, not modeled truth,
  pinned by ``tests/test_intratick_order.py`` (including the short-side
  mirror and dual-host asserts). The same print fills at the open when that
  open is through the new stop, rather than at the stop (high then low) or
  not at all (low then high). MAE/MFE extremes are order-invariant max-of-
  leg-excursions, except the interpret leftover-leg partial-close path,
  which now carries the leg's accumulated extremes too (2026-11-19).
"""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.runtime import Runtime
from pynescript.util.datafeed import MockDataFeed


_SRC_LONG = """//@version=5
strategy("trail tick long", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 1
    strategy.exit("XT", trail_offset=100)
plot(strategy.position_size, "ps")
plot(strategy.closedtrades, "ct")
plot(strategy.closedtrades.exit_price(0), "xp")
plot(strategy.closedtrades.profit(0), "pnl")
plot(high, "h")
plot(low, "l")
"""

_SRC_SHORT = """//@version=5
strategy("trail tick short", commission_value=0)
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


def _hist_long() -> list[dict[str, float | int]]:
    # Bar 2 arms at high 101 → stop 100 and does not fill. Ticks move it.
    return [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(100.0, 100.0, 100.0, 100.0, i=1),
        _bar(100.5, 101.0, 100.2, 100.8, i=2),
    ]


def _hist_short() -> list[dict[str, float | int]]:
    # Bar 2 arms at low 99 → stop 100 and does not fill. Ticks move it.
    return [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(100.0, 100.0, 100.0, 100.0, i=1),
        _bar(99.5, 99.8, 99.0, 99.2, i=2),
    ]


def _run(
    source: str,
    bars: list[dict[str, float | int]],
    ticks: list[list[float | int]] | None,
    *,
    realtime_ticks: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if ticks is None:
        feeds: list[Any] = [None, None]
    else:
        feeds = [MockDataFeed(scripted=[list(t) for t in ticks]) for _ in range(2)]
    interp = Runtime(symbol="RTTRAIL").run(
        source,
        bars,
        mode="interpret",
        realtime_ticks=realtime_ticks,
        data_feed=feeds[0],
    )
    compiled = Runtime(symbol="RTTRAIL").run(
        source,
        bars,
        mode="compile",
        realtime_ticks=realtime_ticks,
        data_feed=feeds[1],
    )
    return interp, compiled


def _series(out: dict[str, Any], name: str) -> list[float]:
    assert "error" not in out, out.get("error")
    return [float(v) for v in out["series"][name]]


def _assert_hosts(interp: dict[str, Any], compiled: dict[str, Any], keys: tuple[str, ...]) -> None:
    assert interp.get("mode") == "interpret", interp.get("mode")
    assert compiled.get("mode") == "compile", compiled.get("mode")
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    for key in keys:
        left = _series(interp, key)
        right = _series(compiled, key)
        assert left == pytest.approx(right), (key, left, right)


def _trail_fill_stop(out: dict[str, Any]) -> float:
    fills = [
        ev
        for ev in (out.get("events") or [])
        if ev.get("kind") == "order" and ev.get("id") == "XT" and str(ev.get("comment") or "").startswith("fill")
    ]
    assert len(fills) == 1, fills
    return float(fills[0]["stop"])


def test_tick_peak_fills_later_print_dual_host() -> None:
    """Earlier high 120 keeps stop 119; the confirmed print does not contain it.

    Confirmed OHLC is 118 / 118.2 / 118. A stop taken only from that print is
    117.2 and the low 118 would not fill. Both hosts fill at the open (118)
    against the remembered stop (119).
    """
    ts = _hist_long()[-1]["time"]
    ticks = [
        [ts, 101.0, 120.0, 119.2, 119.5, 10.0],
        [ts, 116.0, 116.5, 115.5, 116.0, 11.0],
        [ts, 118.0, 118.2, 118.0, 118.1, 12.0],
    ]
    interp, compiled = _run(_SRC_LONG, _hist_long(), ticks, realtime_ticks=3)
    _assert_hosts(interp, compiled, ("ps", "ct", "xp", "pnl", "h", "l"))
    assert _series(interp, "ps") == pytest.approx([0.0, 1.0, 0.0])
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 1.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 118.0])
    assert _series(interp, "pnl") == pytest.approx([0.0, 0.0, 18.0])
    assert _series(interp, "h")[-1] == pytest.approx(118.2)
    assert _series(interp, "h")[-1] != pytest.approx(120.0)
    assert _series(interp, "l")[-1] == pytest.approx(118.0)
    assert _trail_fill_stop(interp) == pytest.approx(119.0)
    assert _trail_fill_stop(compiled) == pytest.approx(119.0)


def test_tick_trough_fills_later_print_dual_host() -> None:
    """Short mirror: low 80 keeps stop 81; confirmed low 81.8 would not.

    A stop taken only from the confirmed print is 82.8, and high 82.2 would
    not fill. Both hosts fill at the open (82) against stop 81.
    """
    ts = _hist_short()[-1]["time"]
    ticks = [
        [ts, 99.0, 80.8, 80.0, 80.4, 10.0],
        [ts, 84.0, 84.5, 83.5, 84.0, 11.0],
        [ts, 82.0, 82.2, 81.8, 82.0, 12.0],
    ]
    interp, compiled = _run(_SRC_SHORT, _hist_short(), ticks, realtime_ticks=3)
    _assert_hosts(interp, compiled, ("ps", "ct", "xp", "pnl", "h", "l"))
    assert _series(interp, "ps") == pytest.approx([0.0, -1.0, 0.0])
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 1.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 82.0])
    assert _series(interp, "pnl") == pytest.approx([0.0, 0.0, 18.0])
    assert _series(interp, "l")[-1] == pytest.approx(81.8)
    assert _series(interp, "l")[-1] != pytest.approx(80.0)
    assert _trail_fill_stop(interp) == pytest.approx(81.0)
    assert _trail_fill_stop(compiled) == pytest.approx(81.0)


def test_unconfirmed_pierce_rolls_back_and_stop_holds_dual_host() -> None:
    """A middle tick trades through the remembered stop; only the last tick commits.

    Confirmed low 119.2 stays above stop 119, so the position remains long.
    The interpret book still shows that stop after the run.
    """
    bars = _hist_long()
    ts = bars[-1]["time"]
    ticks = [
        [ts, 101.0, 120.0, 119.2, 119.5, 10.0],
        [ts, 116.0, 116.5, 115.5, 116.0, 11.0],
        [ts, 119.4, 119.5, 119.2, 119.3, 12.0],
    ]
    interp, compiled = _run(_SRC_LONG, bars, ticks, realtime_ticks=3)
    _assert_hosts(interp, compiled, ("ps", "ct", "xp", "pnl"))
    assert _series(interp, "ps") == pytest.approx([0.0, 1.0, 1.0])
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 0.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 0.0])

    sess = Runtime(symbol="RTTRAIL").create_session(
        _SRC_LONG,
        bars,
        mode="interpret",
        realtime_ticks=3,
        data_feed=MockDataFeed(scripted=[list(t) for t in ticks]),
    )
    pending = sess.evaluator._strategy_state.pending_orders
    assert pending["XT"].stop_price == pytest.approx(119.0)
    assert pending["XT"].trail_active is True
    assert sess.evaluator._strategy_state.position_size == pytest.approx(1.0)


def test_one_ohlc_print_does_not_order_high_and_low_dual_host() -> None:
    """One print ratchets to 109 and fills at the open (105), on both hosts.

    The print is open 105, high 110, low 100.5. Ordering high before low would
    fill at the stop (109). Ordering low before high would leave the trade
    open. Neither path is modeled.
    """
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(100.0, 100.0, 100.0, 100.0, i=1),
        _bar(105.0, 110.0, 100.5, 106.0, i=2),
    ]
    interp, compiled = _run(_SRC_LONG, bars, None)
    _assert_hosts(interp, compiled, ("ps", "ct", "xp", "pnl", "h", "l"))
    assert _series(interp, "ps") == pytest.approx([0.0, 1.0, 0.0])
    assert _series(interp, "ct") == pytest.approx([0.0, 0.0, 1.0])
    assert _series(interp, "xp") == pytest.approx([0.0, 0.0, 105.0])
    assert _series(interp, "xp")[-1] != pytest.approx(109.0)
    assert _series(interp, "pnl") == pytest.approx([0.0, 0.0, 5.0])
    assert _trail_fill_stop(interp) == pytest.approx(109.0)
    assert _trail_fill_stop(compiled) == pytest.approx(109.0)
