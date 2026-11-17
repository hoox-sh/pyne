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

"""Numeric-mode plotshape synthesis: constant visual attrs, numeric condition.

The compile path used to force object mode for every ``plotshape`` call. This
slice keeps a numeric condition + constant visual metadata on the nopython path
and materializes the same True/None series + plot_meta that interpret exports.
Dynamic visual metadata stays object mode (the boundary).
"""

from __future__ import annotations

import math

import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime


pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")


def _bars(n: int = 6) -> list[dict]:
    """Alternating up/down candles so ``close > open`` is not constant."""
    out = []
    for i in range(n):
        c = 100 + 5 * math.sin(i / 3.0)
        up = i % 2 == 0
        o = c - 0.5 if up else c + 0.5
        out.append(
            {
                "time": 1_700_000_000_000 + i * 60_000,
                "open": o,
                "high": max(o, c) + 1,
                "low": min(o, c) - 1,
                "close": c,
                "volume": 10.0,
            }
        )
    return out


def _run(src: str) -> tuple[dict, dict]:
    bars = _bars()
    interp = Runtime(symbol="TEST").run(src, bars, mode="interpret")
    out = Runtime(symbol="TEST").run(src, bars, mode="compile")
    assert "error" not in interp, f"interpret error: {interp.get('error')}"
    assert "error" not in out, f"compile error: {out.get('error')}"
    return interp, out


def test_plotshape_numeric_condition_stays_numeric() -> None:
    """``plotshape(close > open, style=, color=)`` stays nopython + parity."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title="bull", style=shape.triangleup, location=location.belowbar, color=color.green)
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "numeric plotshape must stay numeric"
    code = transpile(src)
    assert "@numba.njit" in code, "numeric plotshape must keep the njit entry point"
    assert "__drawings" not in code, "numeric plotshape must not emit drawing events"

    interp, out = _run(src)
    assert set(out["series"]) == set(interp["series"]), "series keys must match interpret"
    assert list(out["series"]["bull"]) == list(interp["series"]["bull"]), "series values must match interpret"
    assert out["series"]["bull"] == [True, None, True, None, True, None], "off bars must be None, not False"
    meta = out["plot_meta"]["bull"]
    assert meta["kind"] == "plotshape", "plot_meta kind must be plotshape"
    assert meta["style"] == "triangleup", "plot_meta style must match interpret"
    assert meta["location"] == "belowbar", "plot_meta location must match interpret"
    assert meta["color"] == interp["plot_meta"]["bull"]["color"], "plot_meta color must match interpret"


def test_plotshape_constant_true_stays_numeric() -> None:
    """A constant ``true`` condition emits an all-True numeric series."""
    src = """//@version=5
indicator("x")
plotshape(true, title="mark")
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "constant-true plotshape must stay numeric"
    interp, out = _run(src)
    assert list(out["series"]["mark"]) == list(interp["series"]["mark"]), "constant-true parity"
    assert out["series"]["mark"] == [True] * 6, "every bar must show the marker"


def test_plotshape_series_keyword_stays_numeric() -> None:
    """``plotshape(series=...)`` resolves the keyword condition on the numeric path."""
    src = """//@version=5
indicator("x")
longSignal = close > open
plotshape(series=longSignal, title="buy", style=shape.labelup, location=location.belowbar, color=color.green)
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "series= plotshape must stay numeric"
    interp, out = _run(src)
    assert list(out["series"]["buy"]) == list(interp["series"]["buy"]), "series= parity"


def test_plotshape_constant_color_new_stays_numeric() -> None:
    """A constant ``color.new`` folds to an rgba literal, matching interpret."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title="bull", color=color.new(color.green, 0))
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "constant color.new plotshape must stay numeric"
    code = transpile(src)
    assert "pine_color_new(" not in code, "constant color.new must fold, not call the runtime helper"
    interp, out = _run(src)
    assert list(out["series"]["bull"]) == list(interp["series"]["bull"]), "color.new series parity"
    assert out["plot_meta"]["bull"]["color"] == interp["plot_meta"]["bull"]["color"], "color.new meta parity"
    assert out["plot_meta"]["bull"]["color"] == "rgba(34, 171, 148, 1.0)", "folded rgba must match interpret"


def test_plotshape_ternary_numeric_condition_stays_numeric() -> None:
    """``cond ? price : na`` is truthy only when the price is non-NaN."""
    src = """//@version=5
indicator("x")
plotshape(close > open ? close : na, title="bull", location=location.belowbar, color=color.green)
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "ternary numeric plotshape must stay numeric"
    interp, out = _run(src)
    assert list(out["series"]["bull"]) == list(interp["series"]["bull"]), "ternary numeric parity"
    assert out["series"]["bull"] == [True, None, True, None, True, None], "na branch must map to None"


def test_plotshape_text_size_meta_matches_interpret() -> None:
    """``text=`` / ``size=`` are constant metadata, not object-mode triggers."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title="bull", style=shape.labelup, location=location.belowbar, color=color.green, text="BUY", size=size.small)
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "text/size plotshape must stay numeric"
    interp, out = _run(src)
    assert list(out["series"]["bull"]) == list(interp["series"]["bull"]), "text/size series parity"
    for key in ("text", "size", "text_size"):
        assert out["plot_meta"]["bull"].get(key) == interp["plot_meta"]["bull"].get(key), f"{key} meta parity"


def test_plotshape_positional_attrs_stay_numeric() -> None:
    """Positional title/style/location/color slots stay numeric + parity."""
    src = """//@version=5
indicator("x")
plotshape(close > open, "bull", shape.triangleup, location.belowbar, color.green)
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, "positional plotshape must stay numeric"
    interp, out = _run(src)
    assert set(out["series"]) == set(interp["series"]), "positional series keys parity"
    assert list(out["series"]["bull"]) == list(interp["series"]["bull"]), "positional series values parity"


def test_plotshape_dynamic_color_stays_object() -> None:
    """A per-bar dynamic color keeps object mode."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title="bull", color=color.from_gradient(close, 100.0, 105.0, color.red, color.green))
plot(close, "c")
"""
    assert compile_script(src, use_cache=False).object_mode is True, "dynamic gradient color must stay object"


def test_plotshape_dynamic_color_ternary_stays_object() -> None:
    """A per-bar color ternary keeps object mode."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title="bull", color=close > open ? color.green : color.red)
plot(close, "c")
"""
    assert compile_script(src, use_cache=False).object_mode is True, "dynamic color ternary must stay object"


def test_plotshape_dynamic_style_stays_object() -> None:
    """A per-bar style expression keeps object mode."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title="bull", style=close > open ? shape.triangleup : shape.triangledown)
plot(close, "c")
"""
    assert compile_script(src, use_cache=False).object_mode is True, "dynamic style must stay object"


def test_plotshape_dynamic_title_stays_object() -> None:
    """A non-literal title cannot become a stable series key; stay object."""
    src = """//@version=5
indicator("x")
plotshape(close > open, title=str.tostring(close))
plot(close, "c")
"""
    assert compile_script(src, use_cache=False).object_mode is True, "dynamic title must stay object"


def test_plotshape_assigned_handle_stays_object() -> None:
    """An assigned plotshape handle is outside the statement-form slice."""
    src = """//@version=5
indicator("x")
p = plotshape(close > open, title="bull")
plot(close, "c")
"""
    assert compile_script(src, use_cache=False).object_mode is True, "assigned plotshape handle must stay object"
