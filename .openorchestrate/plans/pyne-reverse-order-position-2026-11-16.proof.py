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

"""Proof: pre-placed opposite ``strategy.order`` nets on both hosts.

Also covers the risk gate: flat raw opens and opposite-fill leftovers are
blocked by ``strategy.risk.allow_entry_in``; a pure cover stays ungated.
"""

from __future__ import annotations

# ruff: noqa: S101, T201
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


def _bars() -> list[dict[str, float | int]]:
    return [
        {"time": _TS0, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000.0},
        {"time": _TS0 + _DAY, "open": 100.0, "high": 106.0, "low": 94.0, "close": 100.0, "volume": 1000.0},
        {"time": _TS0 + 2 * _DAY, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000.0},
    ]


def _last(out: dict[str, object], name: str) -> float:
    return float(out["series"][name][-1])  # type: ignore[index]


def _run(src: str, mode: str) -> dict[str, object]:
    out = Runtime(symbol="RO").run(src, _bars(), mode=mode)
    assert "error" not in out, (mode, out.get("error"))
    return out


def _risk_blocked(out: dict[str, object]) -> bool:
    return any(str(e.get("comment")) == "risk_blocked" for e in (out.get("events") or []))


def main() -> None:
    cases = [
        (2, 1, 1.0),  # reduce: long 2 - sell 1 = long 1
        (1, 1, 0.0),  # full close: flat
        (1, 2, -1.0),  # excess: close 1, open short 1
    ]
    results: dict[str, float] = {}
    for qty_l, qty_s, expected in cases:
        src = _SRC.format(qty_l=qty_l, qty_s=qty_s)
        for mode in ("interpret", "compile"):
            out = _run(src, mode)
            assert _last(out, "ps") == expected, (mode, qty_l, qty_s, out["series"]["ps"])
            assert _last(out, "ct") == 1.0, (mode, qty_l, qty_s, out["series"]["ct"])
            assert _last(out, "cs") == 1.0, (mode, qty_l, qty_s, out["series"]["cs"])
        results[f"{qty_l}-{qty_s}"] = expected

    for mode in ("interpret", "compile"):
        flat = _run(_RISK_FLAT_SRC, mode)
        assert _last(flat, "ps") == 0.0, (mode, flat["series"]["ps"])
        assert _risk_blocked(flat), (mode, flat.get("events"))

        leftover = _run(_RISK_LEFTOVER_SRC, mode)
        assert _last(leftover, "ps") == 0.0, (mode, leftover["series"]["ps"])
        assert _last(leftover, "ct") == 1.0, (mode, leftover["series"]["ct"])
        assert _risk_blocked(leftover), (mode, leftover.get("events"))

        cover = _run(_RISK_COVER_SRC, mode)
        assert _last(cover, "ps") == 0.0, (mode, cover["series"]["ps"])
        assert not _risk_blocked(cover), (mode, cover.get("events"))

    print(
        f"REVERSE_ORDER_OK reduce={results['2-1']:.1f} flat={results['1-1']:.1f} "
        f"excess={results['1-2']:.1f} closed=1.0 risk_flat=0.0 risk_leftover=0.0 cover=1"
    )


if __name__ == "__main__":
    main()
