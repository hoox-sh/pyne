# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for the numeric realtime contract slice.

Run from the pynescript repo root:

    PYTHONPATH=src .venv/bin/python \
        .oo/plans/pyne-realtime-varip-2026-11-14.proof.py
"""

# ruff: noqa: S101, T201

from __future__ import annotations

import math

from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime


_ISREALTIME_SRC = """
//@version=5
indicator("isrealtime")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(barstate.isconfirmed ? 1 : 0, "cf")
plot(barstate.ishistory ? 1 : 0, "hist")
"""

_VAR_VARIP_SRC = """
//@version=5
indicator("var varip rt")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""


def _bars(n: int = 8) -> list[dict[str, float | int]]:
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


def _arrays(bars: list[dict[str, float | int]]) -> tuple[list[float], ...]:
    return (
        [float(b["open"]) for b in bars],
        [float(b["high"]) for b in bars],
        [float(b["low"]) for b in bars],
        [float(b["close"]) for b in bars],
        [float(b["volume"]) for b in bars],
        [float(b["time"]) for b in bars],
    )


def _num(value: object) -> float:
    if value is None:
        return math.nan
    return float(value)  # type: ignore[arg-type]


def main() -> None:
    n = 8
    bars = _bars(n)
    opens, highs, lows, closes, vols, times = _arrays(bars)

    # 1) Numeric CompiledScript.run must honor an active realtime window.
    flags = compile_script(_ISREALTIME_SRC, use_cache=False)
    assert flags.object_mode is False
    rt = flags.run(opens, highs, lows, closes, vols, time=times, rt_first=n - 1, rt_ticks=2)
    assert list(rt["rt"][:-1]) == [0.0] * (n - 1)
    assert rt["rt"][-1] == 1.0
    assert rt["cf"][-1] == 1.0
    assert rt["hist"][-1] == 0.0
    assert flags.object_mode is False

    # 2) Historical run after the realtime run stays numeric/historical.
    hist = flags.run(opens, highs, lows, closes, vols, time=times)
    assert list(hist["rt"]) == [0.0] * n
    assert list(hist["hist"]) == [1.0] * n
    assert flags.object_mode is False

    # 3) Numeric varip under a realtime window matches interpret.
    ticks = 3
    interp = Runtime(symbol="TEST").run(
        _VAR_VARIP_SRC,
        bars,
        mode="interpret",
        realtime_ticks=ticks,
    )
    assert "error" not in interp, interp.get("error")
    interp_v = [_num(v) for v in interp["series"]["v"]]
    interp_vip = [_num(v) for v in interp["series"]["vip"]]

    varip = compile_script(_VAR_VARIP_SRC, use_cache=False)
    assert varip.object_mode is False
    out = varip.run(opens, highs, lows, closes, vols, time=times, rt_first=n - 1, rt_ticks=ticks)
    assert [float(v) for v in out["v"]] == interp_v
    assert [float(v) for v in out["vip"]] == interp_vip
    assert out["v"][-1] == n
    assert out["vip"][-1] == 1.0
    assert varip.object_mode is False

    hist2 = varip.run(opens, highs, lows, closes, vols, time=times)
    assert hist2["v"][-1] == n
    assert hist2["vip"][-1] == n
    assert varip.object_mode is False

    print("REALTIME_SLICE_OK numeric_rt=1 varip=1 historical=1")


if __name__ == "__main__":
    main()
