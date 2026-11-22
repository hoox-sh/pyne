# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: statement-form plotshape with numeric condition + constant metadata.

Positive cases must stay numeric AND match interpret on both the series and
plot_meta; boundary cases must stay object. Prints ``PLOTSHAPE_NUMERIC_OK`` only
when every assertion passes.
"""

from __future__ import annotations

# ruff: noqa: S101, T201
import math

from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime

BARS = []
for _i in range(6):
    _c = 100 + 5 * math.sin(_i / 3.0)
    _up = _i % 2 == 0
    _o = _c - 0.5 if _up else _c + 0.5
    BARS.append(
        {
            "time": 1_700_000_000_000 + _i * 60_000,
            "open": _o,
            "high": max(_o, _c) + 1,
            "low": min(_o, _c) - 1,
            "close": _c,
            "volume": 10.0,
        }
    )

POSITIVE = {
    "numeric_condition": '''//@version=5
indicator("x")
plotshape(close > open, title="bull", style=shape.triangleup, location=location.belowbar, color=color.green)
plot(close, "c")
''',
    "constant_true": '''//@version=5
indicator("x")
plotshape(true, title="mark")
plot(close, "c")
''',
    "series_keyword": '''//@version=5
indicator("x")
longSignal = close > open
plotshape(series=longSignal, title="buy", style=shape.labelup, location=location.belowbar, color=color.green)
plot(close, "c")
''',
    "constant_color_new": '''//@version=5
indicator("x")
plotshape(close > open, title="bull", color=color.new(color.green, 0))
plot(close, "c")
''',
    "ternary_numeric": '''//@version=5
indicator("x")
plotshape(close > open ? close : na, title="bull", location=location.belowbar, color=color.green)
plot(close, "c")
''',
    "text_size": '''//@version=5
indicator("x")
plotshape(close > open, title="bull", style=shape.labelup, location=location.belowbar, color=color.green, text="BUY", size=size.small)
plot(close, "c")
''',
    "positional_attrs": '''//@version=5
indicator("x")
plotshape(close > open, "bull", shape.triangleup, location.belowbar, color.green)
plot(close, "c")
''',
}

BOUNDARY = {
    "dynamic_gradient_color": '''//@version=5
indicator("x")
plotshape(close > open, title="bull", color=color.from_gradient(close, 100.0, 105.0, color.red, color.green))
plot(close, "c")
''',
    "dynamic_color_ternary": '''//@version=5
indicator("x")
plotshape(close > open, title="bull", color=close > open ? color.green : color.red)
plot(close, "c")
''',
    "dynamic_style": '''//@version=5
indicator("x")
plotshape(close > open, title="bull", style=close > open ? shape.triangleup : shape.triangledown)
plot(close, "c")
''',
    "dynamic_title": '''//@version=5
indicator("x")
plotshape(close > open, title=str.tostring(close))
plot(close, "c")
''',
    "assigned_handle": '''//@version=5
indicator("x")
p = plotshape(close > open, title="bull")
plot(close, "c")
''',
}

META_KEYS = ("kind", "style", "location", "color", "text", "size", "text_size")

for name, src in POSITIVE.items():
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False, f"{name}: expected numeric, got object mode"
    interp = Runtime(symbol="TEST").run(src, BARS, mode="interpret")
    out = Runtime(symbol="TEST").run(src, BARS, mode="compile")
    assert "error" not in interp, f"{name}: interpret error {interp.get('error')}"
    assert "error" not in out, f"{name}: compile error {out.get('error')}"
    assert set(out["series"]) == set(interp["series"]), f"{name}: series key mismatch"
    for title, values in interp["series"].items():
        assert list(out["series"][title]) == list(values), f"{name}: series mismatch for {title}"
    for title, meta in interp["plot_meta"].items():
        for key in META_KEYS:
            assert out["plot_meta"][title].get(key) == meta.get(key), f"{name}: meta {title}.{key} mismatch"
    print(f"  PASS {name}")

for name, src in BOUNDARY.items():
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is True, f"{name}: expected object mode"
    print(f"  PASS {name} (object)")

print(f"PLOTSHAPE_NUMERIC_OK positives={len(POSITIVE)} boundaries={len(BOUNDARY)}")
