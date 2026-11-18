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

"""Pre-placed opposite ``strategy.order`` nets against the position.

Reference Pine: ``strategy.order`` "does not automatically reverse" — the
resulting position is the net sum of the open position and the filled order
quantity. Only ``strategy.entry`` reverses (close the whole opposite position,
then open the entry qty). These tests pin the netting shape on both hosts:
reduce (2 long, sell 1 -> 1 long), full close (1 long, sell 1 -> flat), and
excess (1 long, sell 2 -> 1 short).
"""

from __future__ import annotations

import pytest

from pynescript.runtime import Runtime


_TS0 = 1_704_067_200_000
_DAY = 86_400_000

_SRC = """//@version=6
strategy("reverse order", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty={qty_l}, limit=95.0)
    strategy.order("S", strategy.short, qty={qty_s}, limit=105.0)
plot(strategy.position_size, "ps")
plot(strategy.closedtrades, "ct")
plot(strategy.closedtrades.size(0), "cs")
"""


def _bars() -> list[dict[str, float | int]]:
    # Bar 1 fills both pre-placed orders: long 95 on the low 94, short 105 on
    # the high 106.
    return [
        {"time": _TS0, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000.0},
        {"time": _TS0 + _DAY, "open": 100.0, "high": 106.0, "low": 94.0, "close": 100.0, "volume": 1000.0},
        {"time": _TS0 + 2 * _DAY, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000.0},
    ]


def _series(out: dict[str, object], name: str) -> list[float]:
    return [float(v) for v in out["series"][name]]  # type: ignore[index]


@pytest.mark.parametrize(
    ("qty_l", "qty_s", "expected_pos"),
    [
        (2, 1, 1.0),  # reduce: long 2 - sell 1 = long 1
        (1, 1, 0.0),  # full close: flat
        (1, 2, -1.0),  # excess: close 1, open short 1
    ],
)
def test_preplaced_opposite_order_nets_both_hosts(qty_l: int, qty_s: int, expected_pos: float) -> None:
    src = _SRC.format(qty_l=qty_l, qty_s=qty_s)
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="RO").run(src, _bars(), mode=mode)
        assert "error" not in out, (mode, out.get("error"))
        ps = _series(out, "ps")
        assert ps[-1] == pytest.approx(expected_pos), (mode, ps)
        assert _series(out, "ct")[-1] == pytest.approx(1.0), (mode, out["series"]["ct"])
        assert _series(out, "cs")[-1] == pytest.approx(1.0), (mode, out["series"]["cs"])


_RISK_FLAT_SRC = """//@version=6
strategy("risk flat", commission_value=0)
strategy.risk.allow_entry_in(strategy.long)
if barstate.isfirst
    strategy.order("S", strategy.short, qty=1)
plot(strategy.position_size, "ps")
"""

_RISK_LEFTOVER_SRC = """//@version=6
strategy("risk leftover", commission_value=0)
strategy.risk.allow_entry_in(strategy.long)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
    strategy.order("S", strategy.short, qty=2, limit=105.0)
plot(strategy.position_size, "ps")
plot(strategy.closedtrades, "ct")
"""

_RISK_COVER_SRC = """//@version=6
strategy("risk cover", commission_value=0)
strategy.risk.allow_entry_in(strategy.long)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
    strategy.order("S", strategy.short, qty=1, limit=105.0)
plot(strategy.position_size, "ps")
"""


def _risk_blocked(out: dict[str, object]) -> bool:
    return any(str(e.get("comment")) == "risk_blocked" for e in (out.get("events") or []))


def test_raw_order_flat_open_blocked_by_allow_entry_in() -> None:
    """A flat raw short order is gated like an entry (both hosts)."""
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="RO").run(_RISK_FLAT_SRC, _bars(), mode=mode)
        assert "error" not in out, (mode, out.get("error"))
        assert _series(out, "ps")[-1] == pytest.approx(0.0), (mode, out["series"]["ps"])
        assert _risk_blocked(out), (mode, out.get("events"))


def test_raw_order_leftover_blocked_but_cover_allowed() -> None:
    """A cover proceeds ungated; the reverse excess is risk-gated (both hosts)."""
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="RO").run(_RISK_LEFTOVER_SRC, _bars(), mode=mode)
        assert "error" not in out, (mode, out.get("error"))
        assert _series(out, "ps")[-1] == pytest.approx(0.0), (mode, out["series"]["ps"])
        assert _series(out, "ct")[-1] == pytest.approx(1.0), (mode, out["series"]["ct"])
        assert _risk_blocked(out), (mode, out.get("events"))


def test_raw_order_pure_cover_ungated() -> None:
    """A pure cover must not be blocked by allow_entry_in (both hosts)."""
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="RO").run(_RISK_COVER_SRC, _bars(), mode=mode)
        assert "error" not in out, (mode, out.get("error"))
        assert _series(out, "ps")[-1] == pytest.approx(0.0), (mode, out["series"]["ps"])
        assert not _risk_blocked(out), (mode, out.get("events"))


@pytest.mark.parametrize(
    ("qty_l", "qty_s", "close_qty"),
    [
        (2, 1, 1.0),  # reduce: cover 1 of 2
        (1, 1, 1.0),  # full close
        (1, 2, 1.0),  # excess: cover 1, remainder opens short
    ],
)
def test_raw_order_cover_emits_close_event_both_hosts(qty_l: int, qty_s: int, close_qty: float) -> None:
    """A raw ``strategy.order`` fill that covers a position emits ``close``.

    Compile routes the cover through ``CompileStrategyBroker.close(...)`` —
    the same primitive used by ``strategy.close`` and entry reverses — so a
    ``close`` event is recorded for the realized exit alongside the trailing
    ``order`` fill event. The interpreter must match: entry-reversal fills
    already emit ``close`` in ``_fill_order``; the raw cover branch must too.
    """
    src = _SRC.format(qty_l=qty_l, qty_s=qty_s)
    streams: dict[str, list[dict]] = {}
    for mode in ("interpret", "compile"):
        out = Runtime(symbol="RO").run(src, _bars(), mode=mode)
        assert "error" not in out, (mode, out.get("error"))
        events = list(out.get("events") or [])
        kinds = [e.get("kind") for e in events]
        assert "close" in kinds, (mode, kinds)
        closes = [e for e in events if e.get("kind") == "close"]
        assert len(closes) == 1, (mode, [(e.get("kind"), e.get("id"), e.get("qty")) for e in events])
        ce = closes[0]
        assert ce.get("id") == "S"
        assert ce.get("direction") == "long"  # the closed side
        assert ce.get("qty") == pytest.approx(close_qty)
        assert ce.get("bar_index") == 1
        # The trailing order-fill event for S comes after the close
        # (excess qty also opens a leftover short, which emits its own entry).
        i_close = kinds.index("close")
        assert any(e.get("kind") == "order" and e.get("id") == "S" for e in events[i_close + 1 :])
        streams[mode] = [(e.get("kind"), e.get("id")) for e in events]
    # Dual-host lock-step: the full (kind, id) stream must match exactly.
    assert streams["interpret"] == streams["compile"]
