# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for interpret drawing rollback on unconfirmed ticks."""

# ruff: noqa: S101, T201

from __future__ import annotations

from typing import Any

from pynescript.runtime import Runtime


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


def _run(src: str, *, mode: str = "interpret") -> dict[str, Any]:
    out = Runtime(symbol="TEST").run(src, _bars(), mode=mode, realtime_ticks=3)
    assert "error" not in out, out.get("error")
    return out


_LINE_XY = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.set_xy1(l, 5, 999.0)
plot(close)
"""

_LABEL_TEXT = """//@version=6
indicator("draw rt")
var label l = na
if barstate.isfirst
    l := label.new(0, close, "orig")
if barstate.isrealtime and not barstate.isconfirmed
    label.set_text(l, "LEAK")
plot(close)
"""

_CONFIRMED_XY = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and barstate.isconfirmed
    line.set_xy1(l, 5, 999.0)
plot(close)
"""

_NEW_ON_TICK = """//@version=6
indicator("draw rt")
var line base = na
if barstate.isfirst
    base := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.new(2, close, 3, close)
plot(close)
"""

_LINE_XY2 = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.set_xy2(l, 5, 999.0)
plot(close)
"""

_LINE_DELETE = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.delete(l)
plot(close)
"""


def main() -> None:
    xy = next(d for d in _run(_LINE_XY)["drawings"] if d.get("type") == "line")
    assert xy["p1"] == 100.5, xy

    xy2 = next(d for d in _run(_LINE_XY2)["drawings"] if d.get("type") == "line")
    assert xy2["p2"] == 100.5, xy2
    assert xy2["t2"] == 1_700_000_060_000, xy2

    text = next(d for d in _run(_LABEL_TEXT)["drawings"] if d.get("type") == "label")
    assert text["text"] == "orig", text

    confirmed = next(d for d in _run(_CONFIRMED_XY)["drawings"] if d.get("type") == "line")
    assert confirmed["p1"] == 999.0, confirmed

    new_lines = [d for d in _run(_NEW_ON_TICK)["drawings"] if d.get("type") == "line"]
    assert len(new_lines) == 1, new_lines

    deleted = [d for d in _run(_LINE_DELETE)["drawings"] if d.get("type") == "line"]
    assert len(deleted) == 1, deleted
    assert deleted[0]["p1"] == 100.5, deleted

    compiled = next(d for d in _run(_LINE_XY, mode="compile")["drawings"] if d.get("type") == "line")
    assert compiled["p1"] == 100.5, compiled

    print("DRAWING_ROLLBACK_OK xy1=100.5 xy2=100.5 text=orig new=1 confirmed=999 deleted=1")


if __name__ == "__main__":
    main()
