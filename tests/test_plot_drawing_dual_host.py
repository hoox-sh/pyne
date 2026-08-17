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

"""Interpret ↔ compile identity for every plot kind and drawing kind.

Series keys/values and AXIS geometry drawings must match across hosts.
Visuals (hline/fill/bgcolor/plotshape/…) live in ``series`` + ``plot_meta.kind``;
``drawings`` is geometry-only (line/label/box/polyline/table/linefill).
"""

from __future__ import annotations

import math

from typing import Any

import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import clear_disk_compile_cache
from pynescript.compiler.engine import has_numba
from pynescript.runtime import Runtime
from pynescript.runtime import host as runtime_host

clear_disk_compile_cache()

_RTOL = 1e-5
_ATOL = 1e-6
_GEOM = frozenset({"line", "label", "box", "polyline", "table", "linefill"})


def _bars(n: int = 12) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for i in range(n):
        c = 100.0 + i
        up = i % 2 == 0
        o = c - 0.5 if up else c + 0.5
        out.append(
            {
                "time": 1_700_000_000_000 + i * 86_400_000,
                "open": o,
                "high": max(o, c) + 1.0,
                "low": min(o, c) - 1.0,
                "close": c,
                "volume": 1000.0 + i,
            }
        )
    return out


def _is_na(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in {"", "nan", "none"}:
        return True
    try:
        return v != v
    except Exception:
        return False


def _run_dual(src: str, bars: list[dict[str, float | int]]):
    clear_parse_cache()
    clear_compile_cache()
    runtime_host._HOST_COMPILE_CACHE.clear()
    interp = Runtime(symbol="PLOTDR").run(src, bars, mode="interpret")
    assert "error" not in interp, interp.get("error")
    if not has_numba():
        pytest.skip("numba required for compile-mode plot/drawing identity")
    clear_parse_cache()
    compiled = Runtime(symbol="PLOTDR").run(src, bars, mode="compile")
    assert "error" not in compiled, compiled.get("error")
    return interp, compiled


def _assert_series_equal(
    interp: dict[str, Any],
    compiled: dict[str, Any],
    *,
    extra_ok: set[str] | None = None,
) -> None:
    si = interp.get("series") or {}
    sc = compiled.get("series") or {}
    extra_ok = extra_ok or set()
    only_i = sorted(set(si) - set(sc) - extra_ok)
    only_c = sorted(set(sc) - set(si) - extra_ok)
    assert not only_i and not only_c, (only_i, only_c, sorted(si), sorted(sc))
    for key in sorted(set(si) & set(sc)):
        a, b = si[key], sc[key]
        assert len(a) == len(b), (key, len(a), len(b))
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            if _is_na(x) and _is_na(y):
                continue
            if type(x) is bool or type(y) is bool:
                assert type(x) is type(y) and x == y, (key, i, x, y)
                continue
            if isinstance(x, str) or isinstance(y, str):
                assert (None if _is_na(x) else x) == (None if _is_na(y) else y), (key, i, x, y)
                continue
            try:
                fx, fy = float(x), float(y)
            except (TypeError, ValueError):
                assert x == y, (key, i, x, y)
                continue
            if math.isnan(fx) and math.isnan(fy):
                continue
            assert abs(fx - fy) <= _ATOL + _RTOL * abs(fy), (key, i, x, y)


def _assert_kinds(interp: dict[str, Any], compiled: dict[str, Any], expected: dict[str, str]) -> None:
    mi = interp.get("plot_meta") or {}
    mc = compiled.get("plot_meta") or {}
    for key, kind in expected.items():
        assert key in mi, (key, sorted(mi))
        assert key in mc, (key, sorted(mc))
        assert mi[key].get("kind") == kind, (key, mi[key])
        assert mc[key].get("kind") == kind, (key, mc[key])


def _geom_kind(d: dict[str, Any]) -> str:
    return str(d.get("type") or d.get("kind") or "").lower()


def _num(v: Any) -> Any:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _canon_geom(d: dict[str, Any]) -> tuple[Any, ...]:
    kind = _geom_kind(d)
    text = str(d.get("text") or "")
    color = str(d.get("color") or "").strip().lower()
    if kind == "line":
        width = _num(d.get("width"))
        style = str(d.get("style") or "solid").replace("line.style_", "")
        return (
            "line",
            _num(d.get("t1")),
            _num(d.get("p1")),
            _num(d.get("t2")),
            _num(d.get("p2")),
            text,
            color,
            style,
            int(width) if isinstance(width, (int, float)) else 1,
        )
    if kind == "label":
        return ("label", _num(d.get("t1")), _num(d.get("p1")), text, color)
    if kind == "box":
        return ("box", _num(d.get("t1")), _num(d.get("p1")), _num(d.get("t2")), _num(d.get("p2")), text, color)
    if kind == "polyline":
        pts = tuple(
            (p.get("time"), p.get("price")) for p in (d.get("points") or []) if isinstance(p, dict)
        )
        return ("polyline", pts)
    if kind == "linefill":
        return (
            "linefill",
            d.get("t1"),
            d.get("p1"),
            d.get("t2"),
            d.get("p2"),
            d.get("t3"),
            d.get("p3"),
            d.get("t4"),
            d.get("p4"),
        )
    if kind == "table":
        cells = tuple(
            sorted(
                (
                    int(c.get("row") or 0),
                    int(c.get("col", c.get("column")) or 0),
                    str(c.get("text") or ""),
                    str(c.get("text_color") or "").strip().lower(),
                    str(c.get("bgcolor") or "").strip().lower(),
                )
                for c in (d.get("cells") or [])
                if isinstance(c, dict)
            )
        )
        return (
            "table",
            str(d.get("position") or ""),
            int(d.get("rows") or 0),
            int(d.get("columns") or 0),
            str(d.get("frame_color") or d.get("color") or "").strip().lower(),
            str(d.get("bgcolor") or "").strip().lower(),
            cells,
        )
    return (kind,)


def _assert_drawings_equal(interp: dict[str, Any], compiled: dict[str, Any]) -> None:
    di = [d for d in (interp.get("drawings") or []) if isinstance(d, dict) and _geom_kind(d) in _GEOM]
    dc = [d for d in (compiled.get("drawings") or []) if isinstance(d, dict) and _geom_kind(d) in _GEOM]
    leftover_c = [
        _geom_kind(d)
        for d in (compiled.get("drawings") or [])
        if isinstance(d, dict) and _geom_kind(d) not in _GEOM
    ]
    leftover_i = [
        _geom_kind(d)
        for d in (interp.get("drawings") or [])
        if isinstance(d, dict) and _geom_kind(d) not in _GEOM
    ]
    assert leftover_c == [], leftover_c
    assert leftover_i == [], leftover_i
    ci = sorted(_canon_geom(d) for d in di)
    cc = sorted(_canon_geom(d) for d in dc)
    assert ci == cc, (ci, cc)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def test_plot_and_hline_fill_identity() -> None:
    src = """
//@version=6
indicator("vis", overlay=true)
hline(50, "mid")
hline(70)
p1 = plot(high, "Upper")
p2 = plot(low, "Lower")
fill(p1, p2, title="Background", color=color.blue)
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_kinds(
        ri,
        rc,
        {
            "c": "plot",
            "Upper": "plot",
            "Lower": "plot",
            "mid": "hline",
            "hline": "hline",
            "Background": "fill",
        },
    )
    _assert_drawings_equal(ri, rc)


def test_bgcolor_barcolor_plotshape_plotchar_plotarrow_identity() -> None:
    src = """
//@version=6
indicator("marks", overlay=true)
bgcolor(close > open ? color.green : na, title="up_bg")
barcolor(close > open ? color.green : color.red)
plotshape(close > open, title="Buy")
plotchar(close < open, title="X", char="X")
plotarrow(close > open ? 1 : -1, title="Arr")
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_kinds(
        ri,
        rc,
        {
            "c": "plot",
            "up_bg": "bgcolor",
            "barcolor": "barcolor",
            "Buy": "plotshape",
            "X": "plotchar",
            "Arr": "plotarrow",
        },
    )
    _assert_drawings_equal(ri, rc)


def test_plotbar_plotcandle_identity() -> None:
    src = """
//@version=6
indicator("ohlc")
plotbar(open, high, low, close, "bars", color.olive)
plotcandle(open, high, low, close, "candles", color.teal)
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(8))
    _assert_series_equal(ri, rc)
    _assert_kinds(ri, rc, {"c": "plot", "bars": "plotbar", "candles": "plotcandle"})
    _assert_drawings_equal(ri, rc)


# ---------------------------------------------------------------------------
# Drawings
# ---------------------------------------------------------------------------


def test_line_label_box_last_bar_identity() -> None:
    src = """
//@version=6
indicator("geom", overlay=true)
if barstate.islast
    line.new(bar_index - 2, low, bar_index + 1, high, color=color.red, width=2)
    label.new(bar_index, high, "hi", color=color.blue, textcolor=color.white)
    box.new(bar_index - 3, high, bar_index, low, bgcolor=color.new(color.teal, 80), border_color=color.teal)
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_drawings_equal(ri, rc)
    kinds = {_geom_kind(d) for d in ri["drawings"]}
    assert kinds == {"line", "label", "box"}


def test_line_created_on_bar_zero_snapshots_identity() -> None:
    """line.new on bar 0 must keep bar-0 prices, not last-bar series.current."""
    src = """
//@version=6
indicator("snap", overlay=true)
var line ln = na
if bar_index == 0
    ln := line.new(bar_index, high, bar_index + 5, low)
plot(close, "c")
"""
    bars = _bars(10)
    ri, rc = _run_dual(src, bars)
    _assert_series_equal(ri, rc)
    _assert_drawings_equal(ri, rc)
    lines = [d for d in ri["drawings"] if _geom_kind(d) == "line"]
    assert len(lines) == 1
    assert lines[0]["p1"] == pytest.approx(float(bars[0]["high"]))
    assert lines[0]["p2"] == pytest.approx(float(bars[0]["low"]))
    assert lines[0]["t1"] == bars[0]["time"]


def test_polyline_table_linefill_identity() -> None:
    src = """
//@version=6
indicator("more", overlay=true)
var line l1 = na
var line l2 = na
if bar_index == 0
    l1 := line.new(bar_index, high, bar_index + 5, high)
    l2 := line.new(bar_index, low, bar_index + 5, low)
    linefill.new(l1, l2, color=color.new(color.blue, 80))
if barstate.islast
    polyline.new(array.from(chart.point.from_index(bar_index - 2, low), chart.point.from_index(bar_index, high)), false)
    t = table.new(position.top_right, 3, 2)
    table.cell(t, 0, 0, "A")
    table.cell(t, 1, 1, "B")
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_drawings_equal(ri, rc)
    kinds = {_geom_kind(d) for d in ri["drawings"]}
    assert {"line", "linefill", "polyline", "table"} <= kinds
    tables = [d for d in ri["drawings"] if _geom_kind(d) == "table"]
    assert len(tables) == 1
    assert tables[0]["rows"] == 3
    assert tables[0]["columns"] == 2
    texts = sorted(str(c.get("text") or "") for c in (tables[0].get("cells") or []) if isinstance(c, dict))
    assert texts == ["A", "B"]
    fills = [d for d in ri["drawings"] if _geom_kind(d) == "linefill"]
    assert len(fills) == 1
    assert fills[0].get("t4") is not None
    assert fills[0].get("p4") is not None


def test_mutate_and_delete_identity() -> None:
    src = """
//@version=6
indicator("mut", overlay=true)
var line ln = na
var label lb = na
if bar_index == 0
    ln := line.new(bar_index, low, bar_index + 1, high)
    lb := label.new(bar_index, high, "old")
if bar_index == 3
    line.set_xy2(ln, bar_index, close)
    label.set_text(lb, "new")
if bar_index == 5
    line.delete(ln)
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_drawings_equal(ri, rc)
    kinds = {_geom_kind(d) for d in ri["drawings"]}
    assert kinds == {"label"}
    assert ri["drawings"][0]["text"] == "new"
    assert rc["drawings"][0]["text"] == "new"


def test_linefill_dropped_when_line_deleted() -> None:
    """Both hosts drop linefill when either endpoint Line is deleted."""
    src = """
//@version=6
indicator("lfdel", overlay=true)
var line l1 = na
var line l2 = na
if bar_index == 0
    l1 := line.new(bar_index, high, bar_index + 5, high)
    l2 := line.new(bar_index, low, bar_index + 5, low)
    linefill.new(l1, l2, color=color.new(color.blue, 80))
if barstate.islast
    line.delete(l1)
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_drawings_equal(ri, rc)
    kinds_i = {_geom_kind(d) for d in ri["drawings"]}
    kinds_c = {_geom_kind(d) for d in rc["drawings"]}
    assert "linefill" not in kinds_i
    assert "linefill" not in kinds_c
    assert kinds_i == {"line"}
    assert kinds_c == {"line"}


def test_combined_plots_and_drawings_identity() -> None:
    src = """
//@version=6
indicator("all", overlay=true)
hline(50, "mid")
p1 = plot(high, "Upper")
p2 = plot(low, "Lower")
fill(p1, p2, title="Band", color=color.blue)
bgcolor(close > open ? color.green : na, title="up_bg")
plotshape(close > open, title="Buy")
plotarrow(close > open ? 1 : -1, title="Arr")
if barstate.islast
    line.new(bar_index - 1, low, bar_index + 1, high, color=color.red)
    label.new(bar_index, high, "L")
plot(close, "c")
"""
    ri, rc = _run_dual(src, _bars(10))
    _assert_series_equal(ri, rc)
    _assert_kinds(
        ri,
        rc,
        {
            "c": "plot",
            "Upper": "plot",
            "Lower": "plot",
            "mid": "hline",
            "Band": "fill",
            "up_bg": "bgcolor",
            "Buy": "plotshape",
            "Arr": "plotarrow",
        },
    )
    _assert_drawings_equal(ri, rc)
