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

"""Interpret path exports bgcolor / plotshape / plotchar into series + plot_meta.kind.

Also covers compile dual-mode via drawing-event materialization (plotting helper)
so titled visual keys are not interpret-only structural residuals.
"""

from __future__ import annotations

import math

from backend.runtime import Runtime
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.evaluator.builtins.plotting import materialize_visual_series_from_drawings
from pynescript.ast.evaluator.builtins.plotting import uniquify_series_title


def _bars(n: int = 40) -> list[dict]:
    """Bars with alternating up/down candles so close>open is not always true."""
    out = []
    for i in range(n):
        c = 100 + 5 * math.sin(i / 3.0)
        up = i % 2 == 0
        o = c - 0.5 if up else c + 0.5
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": o,
                "high": max(o, c) + 1,
                "low": min(o, c) - 1,
                "close": c,
                "volume": 10,
            }
        )
    return out


def test_bgcolor_export_kind_and_color_series():
    src = """
//@version=5
indicator("bg", overlay=true)
bgcolor(close > open ? color.green : na, title="up_bg")
plot(close, "c")
"""
    r = Runtime().run(src, _bars(30))
    assert "error" not in r, r.get("error")
    meta = r.get("plot_meta") or {}
    assert "up_bg" in meta, meta
    assert meta["up_bg"].get("kind") == "bgcolor"
    series = r["series"]["up_bg"]
    assert len(series) == 30
    # Some bars colored, some null
    assert any(v is not None for v in series)
    assert any(v is None for v in series)
    # Colored cells are JSON-safe strings
    for v in series:
        if v is not None:
            assert isinstance(v, str) and len(v) > 0


def test_plotshape_export_bool_series_and_style():
    src = """
//@version=5
indicator("sh", overlay=true)
plotshape(close > open, title="bull", style=shape.triangleup, location=location.belowbar, color=color.green)
"""
    r = Runtime().run(src, _bars(25))
    assert "error" not in r, r.get("error")
    meta = r.get("plot_meta") or {}
    assert "bull" in meta, meta
    assert meta["bull"].get("kind") == "plotshape"
    assert "triangleup" in str(meta["bull"].get("style") or "").lower() or meta["bull"].get("style")
    assert meta["bull"].get("location")
    series = r["series"]["bull"]
    assert len(series) == 25
    assert any(v is True or v == 1 for v in series)
    assert any(v is False or v == 0 or v is None for v in series)


def test_plotchar_export():
    src = """
//@version=5
indicator("ch", overlay=true)
plotchar(close > open, title="x", char="X", color=color.red)
"""
    r = Runtime().run(src, _bars(20))
    assert "error" not in r, r.get("error")
    meta = r.get("plot_meta") or {}
    assert "x" in meta, meta
    assert meta["x"].get("kind") == "plotchar"
    assert meta["x"].get("char") == "X" or meta["x"].get("text") == "X"


def test_plot_meta_kind_plot_compat():
    src = """
//@version=5
indicator("p", overlay=true)
plot(close, "c", color=color.blue)
"""
    r = Runtime().run(src, _bars(15))
    assert "error" not in r, r.get("error")
    assert r["plot_meta"]["c"].get("kind") == "plot"


def test_uniquify_series_title_matches_runtime():
    used: set[str] = set()
    assert uniquify_series_title("hline", used) == "hline"
    used.add("hline")
    assert uniquify_series_title("hline", used) == "hline_2"
    used.add("hline_2")
    assert uniquify_series_title("hline", used) == "hline_3"
    assert uniquify_series_title("", used) == "plot"


def test_materialize_plotshape_from_compile_drawings():
    """Compile drawings → series keys for titled plotshape / plotchar (interpret parity)."""
    src = """
//@version=5
indicator("sh", overlay=true)
plotshape(close > open, title="bull", style=shape.triangleup, location=location.belowbar)
plotshape(close < open)
plotchar(close > open, title="x", char="X")
plot(close, "c")
"""
    bars = _bars(20)
    ri = Runtime().run(src, bars, mode="interpret")
    rc = Runtime().run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    # Runtime compile path materializes visual series from __drawings (R8 A11/A07).
    series = rc.get("series") or {}
    assert "bull" in series, series.keys()
    assert "x" in series
    assert "shape" in series  # untitled plotshape default
    assert "c" in series
    n = len(bars)
    assert len(series["bull"]) == n
    # True when marker shows; None/falsey when not (interpret uses None, not False)
    for i in range(n):
        bi = ri["series"]["bull"][i]
        bc = series["bull"][i]
        assert bool(bi) == bool(bc), (i, bi, bc)


def test_materialize_bgcolor_default_titles_from_drawings():
    """Untitled bgcolors → bgcolor / bgcolor_2 series (title emit still missing on compile)."""
    src = """
//@version=5
indicator("bg")
bgcolor(color.red)
bgcolor(color.blue)
plot(close, "c")
"""
    bars = _bars(12)
    ri = Runtime().run(src, bars, mode="interpret")
    rc = Runtime().run(src, bars, mode="compile")
    assert "error" not in ri and "error" not in rc
    # Host already materializes; helper is still correct when keys not yet present.
    host = rc.get("series") or {}
    assert "bgcolor" in host and "bgcolor_2" in host, sorted(host.keys())
    series, meta = materialize_visual_series_from_drawings(
        rc.get("drawings") or [], len(bars), existing_keys=()
    )
    assert "bgcolor" in series and "bgcolor_2" in series
    assert meta["bgcolor"].get("kind") == "bgcolor"
    # Color strings present most bars
    assert all(isinstance(v, str) and v for v in series["bgcolor"] if v is not None)
    # Keys match interpret defaults
    assert "bgcolor" in ri["series"] and "bgcolor_2" in ri["series"]


def test_drawing_registry_merge_visual_series_wrapper():
    src = """
//@version=5
indicator("sh")
plotshape(true, title="mark")
plot(close, "c")
"""
    bars = _bars(8)
    rc = Runtime().run(src, bars, mode="compile")
    series = dict(rc.get("series") or {})
    DrawingRegistry.merge_visual_series_from_drawings(series, rc.get("drawings") or [], len(bars))
    assert "mark" in series
    assert len(series["mark"]) == len(bars)
    assert all(v is True or v == 1 for v in series["mark"])
