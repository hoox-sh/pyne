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

"""Runtime dual-host goldens for ``strategy.exit(..., trail_offset=...)``.

Locks interpret vs compile on synthetic OHLCV: same position path, closed-trade
fill prices, and placement events (entry + exit). Trail math is the OHLC
approximation (bar high/low ratchet in ``process_pending_orders``) — tick-path
trail is out of scope.

Interpret Runtime drains the event buffer after start-of-bar pending fills, so
next-bar fill ``order``/``close`` events may appear only on compile. Fill prices
are asserted via ``strategy.closedtrades.exit_price`` (and same-bar fill events
when both hosts keep them).
"""

from __future__ import annotations

import math

from typing import Any

import pytest

from backend.runtime import Runtime


# Default Runtime / Syminfo mintick is 0.01 → 100 ticks = $1.00.
_SRC_LONG = """//@version=5
strategy("trail ohlc long", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
if bar_index == 1
    strategy.exit("XT", trail_offset=100)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.exit_price(0), title="xp")
plot(strategy.closedtrades.profit(0), title="pnl")
"""

_SRC_SHORT = """//@version=5
strategy("trail ohlc short", commission_value=0)
if bar_index == 0
    strategy.entry("S", strategy.short, qty=2)
if bar_index == 1
    strategy.exit("XT", trail_offset=100)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.exit_price(0), title="xp")
plot(strategy.closedtrades.profit(0), title="pnl")
"""

_SRC_ACTIVATION = """//@version=5
strategy("trail price act", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
if bar_index == 1
    strategy.exit("XT", trail_price=110, trail_offset=200)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.exit_price(0), title="xp")
plot(strategy.closedtrades.profit(0), title="pnl")
"""

_SRC_POINTS = """//@version=5
strategy("trail points wins", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
if bar_index == 1
    strategy.exit("XT", trail_points=100, trail_offset=500)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.exit_price(0), title="xp")
plot(strategy.closedtrades.profit(0), title="pnl")
"""

_SRC_POINTS_FALLBACK = """//@version=5
strategy("trail points fallback", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=2)
if bar_index == 1
    strategy.exit("XT", trail_points=0, trail_offset=100)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.exit_price(0), title="xp")
plot(strategy.closedtrades.profit(0), title="pnl")
"""

_SRC_FROM_ENTRY = """//@version=5
strategy("trail from_entry", pyramiding=1, commission_value=0)
if bar_index == 0
    strategy.entry("A", strategy.long, qty=2)
if bar_index == 1
    strategy.entry("B", strategy.long, qty=4)
if bar_index == 2
    strategy.exit("XA", from_entry="A", trail_offset=100)
plot(strategy.position_size, title="ps")
plot(strategy.closedtrades, title="ct")
plot(strategy.closedtrades.exit_price(0), title="xp")
plot(strategy.opentrades, title="ot")
"""


def _bar(
    open_: float,
    high: float,
    low: float,
    close: float,
    *,
    i: int,
    volume: float = 1.0,
) -> dict[str, float | int]:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "time": i * 60_000,
    }


def _run_dual(
    source: str,
    bars: list[dict[str, float | int]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    rt = Runtime()
    interp = rt.run(source, bars, mode="interpret")
    compiled = rt.run(source, bars, mode="compile")
    return interp, compiled


def _assert_ok(result: dict[str, Any], mode: str) -> None:
    assert "error" not in result, (mode, result.get("error"))
    assert result.get("mode") == mode, (mode, result.get("mode"))


def _is_na(v: object) -> bool:
    if v is None:
        return True
    try:
        return bool(math.isnan(float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _assert_series_match(
    interp: dict[str, Any],
    compiled: dict[str, Any],
    keys: tuple[str, ...],
    *,
    golden: dict[str, list[float]] | None = None,
) -> None:
    si = interp.get("series") or {}
    sc = compiled.get("series") or {}
    for key in keys:
        assert key in si, f"interpret missing {key!r}; have {list(si)}"
        assert key in sc, f"compile missing {key!r}; have {list(sc)}"
        ia, ca = list(si[key]), list(sc[key])
        assert len(ia) == len(ca), f"{key}: len interp={len(ia)} compile={len(ca)}"
        for i, (a, b) in enumerate(zip(ia, ca, strict=True)):
            if _is_na(a) and _is_na(b):
                continue
            assert a == pytest.approx(float(b)), f"{key}[{i}] interp={a!r} compile={b!r}"
        if golden is not None and key in golden:
            g = golden[key]
            assert len(ia) == len(g), f"{key}: len {len(ia)} != golden {len(g)}"
            for i, (a, gval) in enumerate(zip(ia, g, strict=True)):
                if _is_na(a) and _is_na(gval):
                    continue
                assert a == pytest.approx(gval), f"{key}[{i}] got={a!r} golden={gval!r}"


def _event_id(ev: dict[str, Any]) -> str | None:
    ev_id = ev.get("id")
    if ev_id is not None and str(ev_id) != "":
        return str(ev_id)
    cmt = ev.get("comment")
    if cmt is not None and str(cmt) != "" and not str(cmt).startswith("fill"):
        return str(cmt)
    return None


def _placement_fingerprint(events: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """Comparable entry/exit placement rows (host-envelope fill extras dropped)."""
    out: list[tuple[Any, ...]] = []
    for ev in events:
        kind = ev.get("kind")
        if kind not in {"entry", "exit"}:
            continue
        stop = ev.get("stop")
        out.append(
            (
                kind,
                _event_id(ev),
                ev.get("direction"),
                ev.get("qty"),
                ev.get("bar_index"),
                None if stop is None else float(stop),
            )
        )
    return out


def _assert_placement_events_match(
    interp: dict[str, Any],
    compiled: dict[str, Any],
    *,
    expected: list[tuple[Any, ...]] | None = None,
) -> None:
    fi = _placement_fingerprint(list(interp.get("events") or []))
    fc = _placement_fingerprint(list(compiled.get("events") or []))
    assert fi == fc, f"placement events diverge\n interpret={fi}\n compile={fc}"
    if expected is not None:
        assert fi == expected, f"placement events != golden\n got={fi}\n want={expected}"


def _same_bar_fill_orders(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        ev
        for ev in (result.get("events") or [])
        if ev.get("kind") == "order" and str(ev.get("comment") or "").startswith("fill")
    ]


def test_trail_offset_long_ratchet_dual_host() -> None:
    """100-tick trail arms immediately; stop ratchets with high then fills at 109."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(109.5, 110.0, 109.2, 109.8, i=1),  # high 110 → stop 109; low holds
        _bar(109.5, 109.6, 109.1, 109.2, i=2),  # no fill; trail does not lower
        _bar(109.2, 109.3, 108.0, 108.5, i=3),  # break stop → fill 109
    ]
    interp, compiled = _run_dual(_SRC_LONG, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "pnl"),
        golden={
            "ps": [2.0, 2.0, 2.0, 0.0],
            "ct": [0.0, 0.0, 0.0, 1.0],
            "xp": [0.0, 0.0, 0.0, 109.0],
            "pnl": [0.0, 0.0, 0.0, 18.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "L", "long", 2.0, 0, None),
            ("exit", "XT", None, 2.0, 1, None),
        ],
    )


def test_trail_offset_short_ratchet_dual_host() -> None:
    """Short trail: buy-stop ratchets with low then fills at 91."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(90.5, 90.8, 90.0, 90.2, i=1),  # low 90 → stop 91
        _bar(90.5, 90.9, 90.4, 90.8, i=2),  # bounce holds below stop
        _bar(90.8, 92.0, 90.7, 91.5, i=3),  # break stop → fill 91
    ]
    interp, compiled = _run_dual(_SRC_SHORT, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "pnl"),
        golden={
            "ps": [-2.0, -2.0, -2.0, 0.0],
            "ct": [0.0, 0.0, 0.0, 1.0],
            "xp": [0.0, 0.0, 0.0, 91.0],
            "pnl": [0.0, 0.0, 0.0, 18.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "S", "short", 2.0, 0, None),
            ("exit", "XT", None, 2.0, 1, None),
        ],
    )


def test_trail_offset_same_bar_fill_dual_host() -> None:
    """Place+ratchet+fill on the same bar: both hosts emit fill order at 109."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(109.5, 110.0, 108.0, 108.5, i=1),  # stop 109, low 108 → fill 109
    ]
    interp, compiled = _run_dual(_SRC_LONG, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "pnl"),
        golden={
            "ps": [2.0, 0.0],
            "ct": [0.0, 1.0],
            "xp": [0.0, 109.0],
            "pnl": [0.0, 18.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "L", "long", 2.0, 0, None),
            ("exit", "XT", None, 2.0, 1, None),
        ],
    )
    oi = _same_bar_fill_orders(interp)
    oc = _same_bar_fill_orders(compiled)
    assert len(oi) == 1 and len(oc) == 1
    assert oi[0].get("id") == "XT"
    assert oc[0].get("id") == "XT"
    assert oi[0].get("qty") == pytest.approx(2.0)
    assert oc[0].get("qty") == pytest.approx(2.0)
    assert oi[0].get("stop") == pytest.approx(109.0)
    assert oc[0].get("stop") == pytest.approx(109.0)
    assert oi[0].get("bar_index") == 1
    assert oc[0].get("bar_index") == 1


def test_trail_price_activation_dual_host() -> None:
    """trail_price delays arming; after high 112 stop is 110; fill at 110."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(100.0, 100.0, 100.0, 100.0, i=1),  # place; below activation
        _bar(105.0, 108.0, 104.0, 107.0, i=2),  # still below 110
        _bar(109.0, 112.0, 111.0, 111.5, i=3),  # arm; stop 110; low holds
        _bar(111.0, 111.0, 109.0, 109.5, i=4),  # pullback through 110
    ]
    interp, compiled = _run_dual(_SRC_ACTIVATION, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "pnl"),
        golden={
            "ps": [1.0, 1.0, 1.0, 1.0, 0.0],
            "ct": [0.0, 0.0, 0.0, 0.0, 1.0],
            "xp": [0.0, 0.0, 0.0, 0.0, 110.0],
            "pnl": [0.0, 0.0, 0.0, 0.0, 10.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "L", "long", 1.0, 0, None),
            ("exit", "XT", None, 1.0, 1, 110.0),
        ],
    )


def test_trail_points_wins_over_offset_dual_host() -> None:
    """trail_points=100 wins over wider trail_offset=500 → $1 trail, fill 109."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(109.5, 110.0, 109.2, 109.8, i=1),
        _bar(109.2, 109.3, 108.0, 108.5, i=2),
    ]
    interp, compiled = _run_dual(_SRC_POINTS, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "pnl"),
        golden={
            "ps": [2.0, 2.0, 0.0],
            "ct": [0.0, 0.0, 1.0],
            "xp": [0.0, 0.0, 109.0],
            "pnl": [0.0, 0.0, 18.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "L", "long", 2.0, 0, None),
            ("exit", "XT", None, 2.0, 1, None),
        ],
    )


def test_trail_nonpositive_points_falls_back_to_offset_dual_host() -> None:
    """trail_points=0 is ignored so trail_offset=100 still trails and fills at 109."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(109.5, 110.0, 109.2, 109.8, i=1),
        _bar(109.2, 109.3, 108.0, 108.5, i=2),
    ]
    interp, compiled = _run_dual(_SRC_POINTS_FALLBACK, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "pnl"),
        golden={
            "ps": [2.0, 2.0, 0.0],
            "ct": [0.0, 0.0, 1.0],
            "xp": [0.0, 0.0, 109.0],
            "pnl": [0.0, 0.0, 18.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "L", "long", 2.0, 0, None),
            ("exit", "XT", None, 2.0, 1, None),
        ],
    )


def test_trail_offset_from_entry_dual_host() -> None:
    """from_entry trail closes only that pyramid leg at the OHLC stop."""
    bars = [
        _bar(100.0, 100.0, 100.0, 100.0, i=0),
        _bar(105.0, 105.0, 105.0, 105.0, i=1),
        _bar(109.5, 110.0, 109.2, 109.8, i=2),  # place + ratchet; A still open
        _bar(109.2, 109.3, 108.0, 108.5, i=3),  # fill A @ 109; B remains
    ]
    interp, compiled = _run_dual(_SRC_FROM_ENTRY, bars)
    _assert_ok(interp, "interpret")
    _assert_ok(compiled, "compile")
    _assert_series_match(
        interp,
        compiled,
        ("ps", "ct", "xp", "ot"),
        golden={
            "ps": [2.0, 6.0, 6.0, 4.0],
            "ct": [0.0, 0.0, 0.0, 1.0],
            "xp": [0.0, 0.0, 0.0, 109.0],
            "ot": [1.0, 2.0, 2.0, 1.0],
        },
    )
    _assert_placement_events_match(
        interp,
        compiled,
        expected=[
            ("entry", "A", "long", 2.0, 0, None),
            ("entry", "B", "long", 4.0, 1, None),
            ("exit", "XA", None, 2.0, 2, None),
        ],
    )
