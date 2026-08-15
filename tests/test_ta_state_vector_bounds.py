# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Compile incremental TA state-vector layout + dual-host last-value."""

from __future__ import annotations

import re

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime


pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")


SRC = """
//@version=5
indicator("st")
plot(ta.sma(close, 10), "s10")
plot(ta.sma(close, 50), "s50")
plot(ta.ema(close, 12), "e")
plot(ta.rsi(close, 14), "r")
plot(ta.hma(close, 9), "h")
plot(ta.tsi(close, 13, 25), "t")
"""


def _bars(n: int) -> list[dict[str, float | int]]:
    return [
        {
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.0 + i,
            "volume": 1000.0,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def test_alloc_fixed_state_covers_kernel_max_index() -> None:
    code = transpile(SRC)
    sma = re.findall(r"(__sma\d+_st) = np\.full\((\d+),", code)
    ema = re.findall(r"(__ema\d+_st) = np\.full\((\d+),", code)
    rsi = re.findall(r"(__rsi\d+_st) = np\.full\((\d+),", code)
    hma = re.findall(r"(__hma\d+_st) = np\.full\((\d+),", code)
    tsi = re.findall(r"(__tsi\d+_st) = np\.full\((\d+),", code)
    assert len(sma) == 2
    assert {n for n, _ in sma} == {"__sma0_st", "__sma1_st"} or len({n for n, _ in sma}) == 2
    assert all(int(sz) == 2 for _, sz in sma)
    assert ema and all(int(sz) == 2 for _, sz in ema)
    assert rsi and all(int(sz) == 3 for _, sz in rsi)
    assert hma and all(int(sz) == 7 for _, sz in hma)
    assert tsi and all(int(sz) == 6 for _, sz in tsi)

    compiled = compile_script(SRC, use_cache=False)
    assert compiled.object_mode is False
    n = 80
    bars = _bars(n)
    close = np.arange(100.0, 100.0 + n, dtype=np.float64)
    o = close
    h = close + 1.0
    l = close - 1.0
    v = np.ones(n)
    out = compiled.run(o, h, l, close, v)
    interp = Runtime(symbol="TEST").run(SRC, bars, mode="interpret")
    assert "error" not in interp, interp.get("error")

    s10, s50 = out["s10"], out["s50"]
    assert np.isnan(s10[8])
    assert np.isfinite(s10[9])
    assert np.isnan(s50[48])
    assert np.isfinite(s50[49])
    assert s10[49] != s50[49]
    # RSI Wilder: na until period
    assert np.isnan(out["r"][13])
    assert np.isfinite(out["r"][14])

    for key in ("s10", "s50", "e", "r", "h", "t"):
        left = interp["series"][key]
        right = out[key]
        assert len(left) == len(right) == n
        for i in range(n):
            a, b = left[i], right[i]
            a_na = a is None or (isinstance(a, float) and np.isnan(a))
            b_na = b is None or (isinstance(b, float) and np.isnan(b))
            if a_na or b_na:
                assert a_na and b_na, f"{key}[{i}] interp={a!r} compile={b!r}"
            else:
                assert abs(float(a) - float(b)) < 1e-9, f"{key}[{i}]"


def test_median_inc_state_too_short_falls_back() -> None:
    from pynescript.compiler.numba_builtins import numba_median
    from pynescript.compiler.numba_builtins import numba_median_inc

    arr = np.arange(10, dtype=np.float64)
    short = np.full(2, np.nan)
    # Fallback to full kernel when st is shorter than period
    assert abs(float(numba_median_inc(arr, 5, 9, short)) - float(numba_median(arr, 5, 9))) < 1e-12
