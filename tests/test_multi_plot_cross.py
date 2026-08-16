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

"""Multi-plot, hline, fill, and crossover series/meta export checks.

Verifies interpret and compile agree on plot keys, colors, and strategy
crossover events via ``backend.runtime.Runtime``.
"""

from __future__ import annotations

import math

from backend.runtime import Runtime


def _bars(n: int = 60, amp: float = 10.0, period: float = 4.0) -> list[dict]:
    out = []
    for i in range(n):
        c = 100 + amp * math.sin(i / period)
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": c,
                "high": c + 1,
                "low": c - 1,
                "close": c,
                "volume": 10,
            }
        )
    return out


def test_plot_na_exports_none_not_zero():
    """``plot(na)`` must stay JSON null — never silent-coerce to 0."""
    src = """
//@version=5
indicator("n")
plot(na, title="n")
plot(close, title="c")
"""
    r = Runtime().run(src, _bars(8), mode="interpret")
    assert "error" not in r, r.get("error")
    col = r["series"]["n"]
    assert len(col) == 8
    assert all(v is None for v in col)
    assert r["series"]["c"][-1] == _bars(8)[-1]["close"]


def test_multi_plot_series_and_colors():
    src = """
//@version=5
indicator("m", overlay=true)
plot(ta.sma(close, 5), "fast", color=color.green)
plot(ta.sma(close, 15), "slow", color=color.red)
"""
    r = Runtime().run(src, _bars(50))
    assert "error" not in r, r.get("error")
    assert "fast" in r["series"] and "slow" in r["series"]
    assert r["plot_meta"]["fast"]["color"]
    assert r["plot_meta"]["slow"]["color"]
    assert r["plot_meta"]["fast"].get("kind") in (None, "plot")
    assert len(r["series"]["fast"]) == 50


def test_hline_in_series_and_plot_meta():
    src = """
//@version=5
indicator("rsi-levels", overlay=false)
r = ta.rsi(close, 14)
plot(r, "RSI", color=color.purple, linewidth=2)
hline(30, "Oversold", color=color.green, linewidth=1)
hline(70, "Overbought", color=color.red, linewidth=1)
"""
    r = Runtime().run(src, _bars(50), mode="interpret")
    assert "error" not in r, r.get("error")
    assert "RSI" in r["series"], list(r["series"].keys())
    assert "Oversold" in r["series"], list(r["series"].keys())
    assert "Overbought" in r["series"], list(r["series"].keys())
    meta_os = r["plot_meta"]["Oversold"]
    meta_ob = r["plot_meta"]["Overbought"]
    assert meta_os.get("kind") == "hline"
    assert meta_ob.get("kind") == "hline"
    assert meta_os.get("price") == 30 or float(meta_os.get("price")) == 30.0
    assert meta_ob.get("price") == 70 or float(meta_ob.get("price")) == 70.0
    assert meta_os.get("color")
    assert r["plot_meta"]["RSI"].get("kind") in (None, "plot")
    assert r["plot_meta"]["RSI"].get("linewidth") == 2
    # Constant price repeated per bar
    assert all(v == 30 or v == 30.0 for v in r["series"]["Oversold"] if v is not None)
    assert all(v == 70 or v == 70.0 for v in r["series"]["Overbought"] if v is not None)


def test_hline_series_keys_compile_matches_interpret():
    """Compile mode exports hline titles as constant series (interpret parity)."""
    src = """
//@version=5
indicator("rsi-levels", overlay=false)
r = ta.rsi(close, 14)
plot(r, "RSI", color=color.purple, linewidth=2)
hline(30, "Oversold", color=color.green, linewidth=1)
hline(70, "Overbought", color=color.red, linewidth=1)
hline(0)
hline(50)
"""
    bars = _bars(40)
    ri = Runtime().run(src, bars, mode="interpret")
    rc = Runtime().run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    for key in ("Oversold", "Overbought", "hline", "hline_2"):
        assert key in ri["series"], list(ri["series"].keys())
        assert key in rc["series"], list(rc["series"].keys())
        assert len(rc["series"][key]) == len(bars)
    assert all(v == 30.0 or v == 30 for v in rc["series"]["Oversold"] if v is not None)
    assert all(v == 70.0 or v == 70 for v in rc["series"]["Overbought"] if v is not None)
    assert all(v == 0.0 or v == 0 for v in rc["series"]["hline"] if v is not None)
    assert all(v == 50.0 or v == 50 for v in rc["series"]["hline_2"] if v is not None)
    # Drawings export retained
    kinds = {d.get("kind") for d in (rc.get("drawings") or []) if isinstance(d, dict)}
    assert "hline" in kinds


def test_fill_background_series_keys_compile_matches_interpret():
    """Compile mode exports titled fill() as null series keys (interpret parity)."""
    src = """
//@version=5
indicator("bb", overlay=true)
basis = ta.sma(close, 20)
dev = 2.0 * ta.stdev(close, 20)
p1 = plot(basis + dev, "Upper")
p2 = plot(basis - dev, "Lower")
plot(basis, "Basis")
fill(p1, p2, title="Background", color=color.rgb(33, 150, 243, 95))
"""
    bars = _bars(40)
    ri = Runtime().run(src, bars, mode="interpret")
    rc = Runtime().run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    for key in ("Upper", "Lower", "Basis", "Background"):
        assert key in ri["series"], list(ri["series"].keys())
        assert key in rc["series"], list(rc["series"].keys())
        assert len(rc["series"][key]) == len(bars)
    # Interpret fill column is all-null after JSON packaging; compile uses nan→null
    assert all(v is None for v in ri["series"]["Background"])
    assert all(v is None for v in rc["series"]["Background"])
    kinds = {d.get("kind") for d in (rc.get("drawings") or []) if isinstance(d, dict)}
    assert "fill" in kinds


def test_dual_host_visual_series_keys():
    """Same series keys: two hlines, titled fill, titled bgcolor, empty plot, plot(open), plotshape.

    First-party scripts must not need ``--ignore-hline-keys`` / ``--ignore-fill-keys``.
    """
    src = """
//@version=5
indicator("keys", overlay=true)
hline(30)
hline(70)
p_empty = plot(close, title="")
p_open = plot(open)
fill(p_empty, p_open, title="Background", color=color.blue)
bgcolor(close > open ? color.green : na, title="up_bg")
plotshape(close > open, title="Buy Label")
"""
    bars = _bars(24)
    ri = Runtime().run(src, bars, mode="interpret")
    rc = Runtime().run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    expected = {"hline", "hline_2", "Background", "up_bg", "Buy Label"}
    # empty title="" and untitled plot(open) share interpret plot_N policy
    ikeys = set(ri["series"])
    ckeys = set(rc["series"])
    assert expected <= ikeys, sorted(ikeys)
    assert expected <= ckeys, sorted(ckeys)
    assert ikeys == ckeys, (sorted(ikeys - ckeys), sorted(ckeys - ikeys))
    # empty + untitled plots are plot_N, never "" or bare "plot"
    assert "" not in ckeys
    extra = ikeys - expected
    assert extra, "expected plot_N keys for empty/untitled plots"
    assert all(k.startswith("plot_") for k in extra), extra
    assert "plot" not in ikeys
    assert "plot" not in ckeys


def test_plotshape_bgcolor_keys_via_materialize_match_interpret():
    """Dual-mode key parity for plotshape + default bgcolor after drawings lift."""
    from pynescript.ast.evaluator.builtins.plotting import merge_visual_series_from_drawings

    src = """
//@version=5
indicator("vis", overlay=true)
bgcolor(color.red)
plotshape(close > open, title="Buy Label")
plotshape(close < open, title="Sell Label")
plot(close, "c")
"""
    bars = _bars(30)
    ri = Runtime().run(src, bars, mode="interpret")
    rc = Runtime().run(src, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    for key in ("Buy Label", "Sell Label", "bgcolor", "c"):
        assert key in ri["series"], list(ri["series"].keys())

    series = dict(rc.get("series") or {})
    merge_visual_series_from_drawings(series, rc.get("drawings") or [], len(bars))
    for key in ("Buy Label", "Sell Label", "bgcolor", "c"):
        assert key in series, list(series.keys())
        assert len(series[key]) == len(bars)
    # Shape bools align with interpret
    for k in ("Buy Label", "Sell Label"):
        for i in range(len(bars)):
            assert bool(ri["series"][k][i]) == bool(series[k][i]), (k, i)


def test_crossover_strategy_events():
    src = """
//@version=5
strategy("s", overlay=true)
fast = ta.sma(close, 5)
slow = ta.sma(close, 15)
if ta.crossover(fast, slow)
    strategy.entry("L", strategy.long)
if ta.crossunder(fast, slow)
    strategy.close("L")
plot(fast, "fast")
plot(slow, "slow")
"""
    r = Runtime().run(src, _bars(60))
    assert "error" not in r, r.get("error")
    kinds = [e["kind"] for e in r.get("events") or []]
    assert "entry" in kinds, kinds
    assert "close" in kinds or kinds.count("entry") >= 1, kinds


def test_kwargs_titled_plots_column_length_no_append_growth():
    """Pre-sized columns stay bar-length; titled kwargs path matches positional."""
    src = """
//@version=5
indicator("k")
plot(close, title="c")
plot(open, title="o", color=color.red)
plot(na, title="n")
"""
    bars = _bars(40)
    r = Runtime().run(src, bars, mode="interpret")
    assert "error" not in r, r.get("error")
    assert len(r["series"]["c"]) == 40
    assert len(r["series"]["o"]) == 40
    assert len(r["series"]["n"]) == 40
    assert all(v is None for v in r["series"]["n"])
    assert r["plot_meta"]["c"]["kind"] == "plot"
    assert r["plot_meta"]["o"]["kind"] == "plot"
    assert r["plot_meta"]["o"]["color"]
    assert r["series"]["c"][-1] == bars[-1]["close"]


def test_lazy_first_non_null_plot_color():
    """color=na on bar 0 then a real color later still lands in plot_meta."""
    src = """
//@version=5
indicator("lz")
plot(close, "c", color=bar_index == 0 ? na : color.blue)
"""
    r = Runtime().run(src, _bars(12), mode="interpret")
    assert "error" not in r, r.get("error")
    color = r["plot_meta"]["c"].get("color")
    assert color
    assert "blue" in str(color).lower() or str(color).startswith("#")
