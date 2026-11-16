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

"""Proof: interpret historical bars update per-trade MAE/MFE per bar (D-03)."""

from __future__ import annotations

# ruff: noqa: S101, T201
from pynescript.runtime import Runtime


_TS0 = 1_704_067_200_000
_DAY = 86_400_000

_SRC = """//@version=6
strategy("hist held mae", commission_value=0)
if bar_index == 0
    strategy.entry("L", strategy.long, qty=1)
plot(strategy.opentrades.max_runup(0), "ru")
plot(strategy.opentrades.max_drawdown(0), "dd")
plot(strategy.position_size, "ps")
"""

_SAME_BAR_FULL_SRC = """//@version=6
strategy("same bar oc", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=1, limit=95.0)
    strategy.order("S", strategy.short, qty=1, limit=105.0)
plot(strategy.closedtrades.max_runup(0), "cru")
plot(strategy.closedtrades.max_drawdown(0), "cdd")
plot(strategy.closedtrades, "ct")
"""

_SAME_BAR_PARTIAL_SRC = """//@version=6
strategy("same bar oc partial", commission_value=0)
if barstate.isfirst
    strategy.entry("L", strategy.long, qty=2, limit=95.0)
    strategy.order("S", strategy.short, qty=1, limit=105.0)
plot(strategy.closedtrades.max_runup(0), "cru")
plot(strategy.closedtrades.max_drawdown(0), "cdd")
plot(strategy.closedtrades, "ct")
"""


def _bar(o: float, h: float, low: float, c: float, i: int) -> dict[str, float | int]:
    return {
        "time": _TS0 + i * _DAY,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": 1000.0,
    }


def _bars() -> list[dict[str, float | int]]:
    return [
        _bar(100.0, 101.0, 99.0, 100.0, 0),
        _bar(100.0, 102.0, 98.0, 100.0, 1),
        _bar(100.0, 103.0, 97.0, 100.0, 2),
        _bar(100.0, 104.0, 96.0, 100.0, 3),
        _bar(100.0, 105.0, 95.0, 100.0, 4),
    ]


def _same_bar_bars() -> list[dict[str, float | int]]:
    return [
        _bar(100.0, 101.0, 99.0, 100.0, 0),
        _bar(100.0, 106.0, 94.0, 100.0, 1),
        _bar(100.0, 101.0, 99.0, 100.0, 2),
    ]


def _series(out: dict[str, object], name: str) -> list[float]:
    return [float(v) for v in out["series"][name]]  # type: ignore[index]


def _run(src: str, bars: list[dict[str, float | int]], mode: str) -> dict[str, object]:
    out = Runtime(symbol="HIST").run(src, bars, mode=mode)
    assert "error" not in out, (mode, out.get("error"))
    return out


def main() -> None:
    interp = _run(_SRC, _bars(), "interpret")
    compiled = _run(_SRC, _bars(), "compile")
    expected = [0.0, 2.0, 3.0, 4.0, 5.0]
    for label, out in (("interpret", interp), ("compile", compiled)):
        assert _series(out, "ru") == expected, (label, _series(out, "ru"))
        assert _series(out, "dd") == expected, (label, _series(out, "dd"))
        assert _series(out, "ps")[-1] == 1.0, (label, _series(out, "ps"))

    sess = Runtime(symbol="HIST").create_session(_SRC, _bars(), mode="interpret")
    sout = sess.result()
    assert "error" not in sout, sout.get("error")
    assert _series(sout, "ru") == expected, _series(sout, "ru")
    assert _series(sout, "dd") == expected, _series(sout, "dd")

    for label, out in (
        ("interpret", _run(_SAME_BAR_FULL_SRC, _same_bar_bars(), "interpret")),
        ("compile", _run(_SAME_BAR_FULL_SRC, _same_bar_bars(), "compile")),
    ):
        assert _series(out, "ct")[-1] == 1.0, (label, _series(out, "ct"))
        assert _series(out, "cru")[-1] == 11.0, (label, _series(out, "cru"))
        assert _series(out, "cdd")[-1] == 1.0, (label, _series(out, "cdd"))

    for label, out in (
        ("interpret", _run(_SAME_BAR_PARTIAL_SRC, _same_bar_bars(), "interpret")),
        ("compile", _run(_SAME_BAR_PARTIAL_SRC, _same_bar_bars(), "compile")),
    ):
        assert _series(out, "ct")[-1] == 1.0, (label, _series(out, "ct"))
        assert _series(out, "cru")[-1] == 22.0, (label, _series(out, "cru"))
        assert _series(out, "cdd")[-1] == 2.0, (label, _series(out, "cdd"))

    print(
        f"HIST_EXTREMES_OK interp={_series(interp, 'ru')[-1]:.1f}/"
        f"{_series(interp, 'dd')[-1]:.1f} compile={_series(compiled, 'ru')[-1]:.1f}/"
        f"{_series(compiled, 'dd')[-1]:.1f} session={_series(sout, 'ru')[-1]:.1f}/"
        f"{_series(sout, 'dd')[-1]:.1f} samebar=11.0/1.0 partial=22.0/2.0 series=0,2,3,4,5"
    )


if __name__ == "__main__":
    main()
