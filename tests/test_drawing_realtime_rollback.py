# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Interpret drawing mutations roll back on unconfirmed realtime ticks."""

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


def _run(src: str, *, mode: str = "interpret", ticks: int = 3) -> dict[str, Any]:
    out = Runtime(symbol="TEST").run(src, _bars(), mode=mode, realtime_ticks=ticks)
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


def test_interpret_line_set_xy_rolls_back_on_unconfirmed_tick() -> None:
    out = _run(_LINE_XY)
    line = next(d for d in out["drawings"] if d.get("type") == "line")
    assert line["p1"] == 100.5
    assert line["t1"] == 1_700_000_000_000


_LABEL_TEXT = """//@version=6
indicator("draw rt")
var label l = na
if barstate.isfirst
    l := label.new(0, close, "orig")
if barstate.isrealtime and not barstate.isconfirmed
    label.set_text(l, "LEAK")
plot(close)
"""


def test_interpret_label_set_text_rolls_back_on_unconfirmed_tick() -> None:
    out = _run(_LABEL_TEXT)
    label = next(d for d in out["drawings"] if d.get("type") == "label")
    assert label["text"] == "orig"


_CONFIRMED_XY = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and barstate.isconfirmed
    line.set_xy1(l, 5, 999.0)
plot(close)
"""


def test_interpret_line_set_xy_commits_on_confirmed_tick() -> None:
    out = _run(_CONFIRMED_XY)
    line = next(d for d in out["drawings"] if d.get("type") == "line")
    assert line["p1"] == 999.0


_NEW_ON_TICK = """//@version=6
indicator("draw rt")
var line base = na
if barstate.isfirst
    base := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.new(2, close, 3, close)
plot(close)
"""


def test_interpret_new_drawing_on_unconfirmed_tick_is_truncated() -> None:
    out = _run(_NEW_ON_TICK)
    lines = [d for d in out["drawings"] if d.get("type") == "line"]
    assert len(lines) == 1


_LINE_XY2 = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.set_xy2(l, 5, 999.0)
plot(close)
"""


def test_interpret_line_set_xy2_rolls_back_on_unconfirmed_tick() -> None:
    out = _run(_LINE_XY2)
    line = next(d for d in out["drawings"] if d.get("type") == "line")
    assert line["p2"] == 100.5
    assert line["t2"] == 1_700_000_060_000


_LINE_DELETE = """//@version=6
indicator("draw rt")
var line l = na
if barstate.isfirst
    l := line.new(0, close, 1, close)
if barstate.isrealtime and not barstate.isconfirmed
    line.delete(l)
plot(close)
"""


def test_interpret_line_delete_rolls_back_on_unconfirmed_tick() -> None:
    out = _run(_LINE_DELETE)
    lines = [d for d in out["drawings"] if d.get("type") == "line"]
    assert len(lines) == 1
    assert lines[0]["p1"] == 100.5
