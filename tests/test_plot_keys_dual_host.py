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

"""Dual-host series key set: hline / fill / bgcolor / empty plot / plotshape."""

from __future__ import annotations

import math

import numpy as np

from backend.runtime import Runtime
from pynescript.compiler.engine import _normalize_result
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import compile_script


def _bars(n: int = 24) -> list[dict]:
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


_KEY_SCRIPT = """
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


def test_normalize_result_empty_key_is_plot_n() -> None:
    """Object-mode leftover ``""`` keys must become plot_N, not ``plot``."""
    out = _normalize_result(
        {
            "hline": np.full(2, 30.0),
            "": np.ones(2),
            "__drawings": [],
        }
    )
    assert "" not in out
    assert "plot" not in out
    assert "plot_1" in out
    assert "hline" in out
    assert np.allclose(out["plot_1"], 1.0)


def test_compiler_empty_plot_title_is_plot_n() -> None:
    """Visitor + transpile store plot_N (never empty / bare ``plot``)."""
    clear_compile_cache()
    compiled = compile_script(_KEY_SCRIPT, use_cache=False)
    titles = list(compiled.plot_titles)
    assert "" not in titles
    assert "plot" not in titles
    assert "hline" in titles
    assert "hline_2" in titles
    assert "Background" in titles
    assert any(t.startswith("plot_") for t in titles)


def test_dual_host_key_set_hline_fill_bgcolor_empty_plotshape() -> None:
    bars = _bars(20)
    ri = Runtime().run(_KEY_SCRIPT, bars, mode="interpret")
    rc = Runtime().run(_KEY_SCRIPT, bars, mode="compile")
    assert "error" not in ri, ri.get("error")
    assert "error" not in rc, rc.get("error")
    assert set(ri["series"]) == set(rc["series"]), (
        sorted(set(ri["series"]) - set(rc["series"])),
        sorted(set(rc["series"]) - set(ri["series"])),
    )
    keys = set(ri["series"])
    for k in ("hline", "hline_2", "Background", "up_bg", "Buy Label"):
        assert k in keys, sorted(keys)
    assert "" not in keys
    assert "plot" not in keys
    plot_ns = sorted(k for k in keys if k.startswith("plot_"))
    assert len(plot_ns) == 2, plot_ns
