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

"""Smoke tests for the public :mod:`pynescript.runtime` package surface.

Guards H1 package façade: import path, interpret bar-loop, and backend shim
identity so existing ``from backend.runtime import Runtime`` callers keep
working against the same implementation.
"""

from __future__ import annotations

from pynescript.runtime import Runtime
from pynescript.runtime import host as runtime_host


def _bars(n: int = 20) -> list[dict[str, float | int]]:
    return [
        {
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0 + i,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def test_import_runtime_from_package() -> None:
    assert Runtime is runtime_host.Runtime


def test_interpret_tiny_script() -> None:
    src = """
//@version=5
indicator("pkg facade")
plot(close, "c")
"""
    out = Runtime(symbol="TEST").run(src, _bars(15), mode="interpret")
    assert "error" not in out, out.get("error")
    assert "series" in out
    series = out["series"]
    assert "c" in series
    assert len(series["c"]) == 15
    # Last bar close matches synthetic OHLCV
    assert series["c"][-1] == 100.5 + 14


def test_backend_runtime_shim_is_host_module() -> None:
    import backend.runtime as backend_rt

    assert backend_rt is runtime_host
    assert backend_rt.Runtime is Runtime


def test_historical_default_isrealtime_false_var_varip_same() -> None:
    """Default historical host: var and varip both init-once (no multi-tick)."""
    src = """
//@version=5
indicator("var varip hist")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 10
    out = Runtime(symbol="TEST").run(src, _bars(n), mode="interpret")
    assert "error" not in out, out.get("error")
    series = out["series"]
    # One visit per bar → both accumulate to n
    assert series["v"][-1] == n
    assert series["vip"][-1] == n
    assert len(series["v"]) == n
    assert len(series["vip"]) == n


def test_varip_reinit_under_realtime_last_bar_multi_tick() -> None:
    """Multi-tick last bar: varip re-inits each tick; var keeps accumulating.

    Evaluator contract when barstate.isrealtime: varip RHS re-runs each visit;
    var stays init-once. With ``v := v + 1`` / ``vip := vip + 1`` after
    ``var/varip int x = 0``, after N realtime ticks on the last bar:
    - ``v`` ends at historical_bars + N (accumulates across ticks)
    - ``vip`` ends at 1 (reset to 0 then +1 on the final tick)
    """
    src = """
//@version=5
indicator("varip rt")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 8
    ticks = 5
    out = Runtime(symbol="TEST").run(
        src,
        _bars(n),
        mode="interpret",
        realtime_last_bar=True,
        realtime_ticks=ticks,
    )
    assert "error" not in out, out.get("error")
    series = out["series"]
    # Series length still one cell per OHLCV bar (intermediate ticks discarded)
    assert len(series["v"]) == n
    assert len(series["vip"]) == n
    # Historical bars 0..n-2: one visit each → n-1 increments, then last bar N ticks
    assert series["v"][-1] == (n - 1) + ticks
    # varip re-inits to 0 on each realtime tick, then +1 → final cell is 1
    assert series["vip"][-1] == 1


def test_realtime_ticks_implies_last_bar_realtime() -> None:
    """realtime_ticks>1 enables last-bar isrealtime even without the bool flag."""
    src = """
//@version=5
indicator("rt ticks only")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 6
    ticks = 3
    out = Runtime(symbol="TEST").run(
        src,
        _bars(n),
        mode="interpret",
        realtime_ticks=ticks,
    )
    assert "error" not in out, out.get("error")
    series = out["series"]
    assert series["v"][-1] == (n - 1) + ticks
    assert series["vip"][-1] == 1


def test_realtime_last_bar_single_tick_sets_isrealtime() -> None:
    """realtime_last_bar=True with default ticks=1 still sets isrealtime on last bar.

    On the last bar alone, varip re-runs ``= 0`` then ``:= +1`` → ends at 1,
    while var keeps its historical accumulation → ends at n.
    """
    src = """
//@version=5
indicator("rt single")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 12
    bars = _bars(n)
    hist = Runtime(symbol="TEST").run(src, bars, mode="interpret")
    rt = Runtime(symbol="TEST").run(
        src, bars, mode="interpret", realtime_last_bar=True
    )
    assert "error" not in hist, hist.get("error")
    assert "error" not in rt, rt.get("error")
    # Historical: both accumulate one increment per bar
    assert hist["series"]["v"][-1] == n
    assert hist["series"]["vip"][-1] == n
    # Realtime last bar (1 tick): var still accumulates; varip re-inits then +1
    assert rt["series"]["v"][-1] == n
    assert rt["series"]["vip"][-1] == 1
