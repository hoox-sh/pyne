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

"""Interpret must match compile for nested ``var`` EMA state (TTM Wave).

``ema_calc`` keeps ``var result`` and is called from several ``macd_hist``
sites. One shared binding aliases those EMAs. Compile clones the state per
call path; Wave A1[1] on the shared synthetic bars is 0.1556462585033874.
"""

from __future__ import annotations

import math

from typing import Any

import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import has_numba
from pynescript.runtime import Runtime


_RTOL = 1e-5
_ATOL = 1e-6
# compile oracle on make_bars() / the same close path (bar index 1)
_WAVE_A1_BAR1 = 0.1556462585033874
_WAVE_A2_BAR1 = 0.17984693877551042

_SRC = """
//@version=6
indicator("TTM Wave reduced")
ema_calc(series float src, simple int length) =>
    float alpha = 2.0 / (length + 1)
    var float result = 0.0
    result := bar_index == 0 ? src : alpha * src + (1 - alpha) * result
    result
macd_hist(series float src, simple int fast, simple int slow, simple int signal) =>
    float fast_ema = ema_calc(src, fast)
    float slow_ema = ema_calc(src, slow)
    float macd_line = fast_ema - slow_ema
    float signal_line = ema_calc(macd_line, signal)
    macd_line - signal_line
plot(macd_hist(close, 8, 34, 34), "Wave A1")
plot(macd_hist(close, 8, 55, 55), "Wave A2")
"""


def _bars(n: int = 8) -> list[dict[str, float | int]]:
    """Same synthetic OHLCV as scripts/compare_interp_compile.make_bars."""
    bars: list[dict[str, float | int]] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        lo = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _is_na(v: object) -> bool:
    if v is None:
        return True
    try:
        return v != v
    except Exception:
        return False


def _run(mode: str, bars: list[dict[str, float | int]]) -> dict[str, Any]:
    clear_parse_cache()
    out = Runtime(symbol="PARITY").run(_SRC, bars, mode=mode)
    assert "error" not in out, out.get("error")
    return out


def test_ttm_wave_udf_var_matches_compile() -> None:
    """Wave A1/A2 histograms match compile, including the pinned bar-1 values."""
    if not has_numba():
        pytest.skip("numba compile path unavailable")
    bars = _bars(8)
    interp = _run("interpret", bars)
    compiled = _run("compile", bars)
    for key, pinned in (("Wave A1", _WAVE_A1_BAR1), ("Wave A2", _WAVE_A2_BAR1)):
        iv = interp["series"][key]
        cv = compiled["series"][key]
        assert len(iv) == len(cv) == len(bars)
        assert not _is_na(cv[1])
        assert math.isclose(float(cv[1]), pinned, rel_tol=0.0, abs_tol=1e-12), cv[1]
        assert math.isclose(float(iv[1]), pinned, rel_tol=0.0, abs_tol=1e-12), iv[1]
        for i, (a, b) in enumerate(zip(iv, cv, strict=True)):
            assert not _is_na(a) and not _is_na(b), (key, i, a, b)
            assert math.isclose(float(a), float(b), rel_tol=_RTOL, abs_tol=_ATOL), (key, i, a, b)
