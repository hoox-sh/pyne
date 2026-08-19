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

"""Object-mode timestamp timezone/strings and valuewhen object series."""

from __future__ import annotations

import signal

from pathlib import Path

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.numba_builtins import numba_timestamp
from pynescript.compiler.numba_builtins import numba_valuewhen
from pynescript.compiler.numba_builtins import numba_valuewhen_inc


pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")

_REPO = Path(__file__).resolve().parents[1]


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


class _TimeoutError(Exception):
    """SIGALRM fired while a compile/run was expected to finish quickly."""


def _run_with_timeout(fn, seconds: float = 30.0):
    def _handler(_signum, _frame):
        msg = "compile/run exceeded timeout"
        raise _TimeoutError(msg)

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, old)


def test_numba_timestamp_string_year_and_floats() -> None:
    """``int(unicode_type)`` must not TypingError; ``\"2021\"`` is a year."""
    a = numba_timestamp("2021", 7, 20)
    b = numba_timestamp(2021.0, 7.0, 20.0)
    assert a == b
    # 2021-07-20 00:00:00 UTC
    assert abs(float(b) - 1_626_739_200_000.0) < 1e-3


def test_numba_timestamp_timezone_lead_skipped() -> None:
    """Pine ``timestamp(timezone, year, month, day, …)`` skips the tz string."""
    numeric = numba_timestamp(2021.0, 7.0, 20.0)
    assert numba_timestamp("GMT+3", 2021.0, 7.0, 20.0) == numeric
    assert numba_timestamp("America/Chicago", 2021, 7, 20) == numeric
    assert numba_timestamp("+0300", 2021.0, 7.0, 20.0, 0.0, 0.0) == numeric
    none_year = numba_timestamp(None, 1, 1)
    assert np.isfinite(none_year)


def test_timestamp_numeric_pine_stays_nopython() -> None:
    """Literal ``timestamp(year, month, day, …)`` stays on the nopython path."""
    src = """//@version=5
indicator("ts")
plot(timestamp(2021, 7, 20, 0, 0, 0), title="t")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False
    out = compiled.run(*_ohlcv(8))
    assert abs(float(out["t"][-1]) - float(numba_timestamp(2021.0, 7.0, 20.0))) < 1e-3


def test_valuewhen_object_src_helpers() -> None:
    """Object-dtype cond/src must not TypingError; occ-th true still matches."""
    cond = np.array([0.0, 1.0, 0.0, 1.0], dtype=object)
    src = np.array(["a", "up", "b", "up2"], dtype=object)
    assert numba_valuewhen(cond, src, 0, 3) == "up2"
    assert numba_valuewhen(cond, src, 1, 3) == "up"
    st = np.full(4, np.nan)
    assert numba_valuewhen_inc(cond, src, 0, 3, st) == "up2"
    assert numba_valuewhen_inc(cond, src, 1, 3, st) == "up"

    fcond = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float64)
    fsrc = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    fst = np.full(4, np.nan)
    assert numba_valuewhen(fcond, fsrc, 0, 3) == 40.0
    assert numba_valuewhen_inc(fcond, fsrc, 0, 3, fst) == 40.0


def test_valuewhen_string_src_pine_object_mode() -> None:
    """``ta.valuewhen`` with a string source compiles and runs in object mode."""
    src = """//@version=5
indicator("vwstr")
cond = high > low
txt = high > low ? "up" : "down"
v = ta.valuewhen(cond, txt, 0)
plot(v == "up" ? 1.0 : 0.0, title="v")
plot(ta.valuewhen(cond, close, 0), title="n")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is True
    o, h, low, c, vol = _ohlcv(20)
    out = compiled.run(o, h, low, c, vol)
    assert "v" in out
    assert "n" in out
    assert len(out["n"]) == 20
    assert abs(float(out["n"][-1]) - float(c[-1])) < 1e-12


@pytest.mark.parametrize(
    "rel",
    [
        "tests/data/set06/indicators/13676_ind_triexdev_superbuyselltrend_plus_plus.pine",
        "tests/data/set06/indicators/13937_ind_tma_overlay.pine",
    ],
)
def test_set06_timestamp_timezone_corpus_runs(rel: str) -> None:
    """Timezone-first ``timestamp(...)`` must not TypingError on 20-30 bars."""
    path = _REPO / rel
    pine = path.read_text(encoding="utf-8")

    def _go() -> dict:
        compiled = compile_script(pine, use_cache=False)
        return compiled.run(*_ohlcv(24))

    out = _run_with_timeout(_go, seconds=30.0)
    assert isinstance(out, dict)


def test_valuewhen_string_src_reduced_snippet() -> None:
    """Reduced lock for object-src valuewhen (1610 hits a different njit kernel)."""
    src = """//@version=5
indicator("vw-obj")
cond = high > low
col = high > low ? color.green : color.red
v = ta.valuewhen(cond, col, 0)
plot(na(v) ? 0.0 : 1.0, title="c")
"""
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(20))
    assert isinstance(out, dict)
    assert len(out["c"]) == 20


def test_running_max_object_array_no_typingerror() -> None:
    """Object ``array.new<int>`` buffers must not njit ``array(pyobject)``."""
    from pynescript.compiler.numba_builtins import numba_running_max_inc

    arr = np.empty(8, dtype=object)
    arr[:] = [1, 3, 2, 5, 4, 0, 9, 1]
    st = np.array([np.nan, np.nan], dtype=np.float64)
    m = numba_running_max_inc(arr, 3, st)
    assert m == 5.0
    src = """//@version=5
indicator("rm")
var bins = array.new<int>()
if bar_index == 0
    array.push(bins, 1)
    array.push(bins, 3)
plot(array.max(bins), title="m")
"""
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(12))
    assert abs(float(out["m"][-1]) - 3.0) < 1e-9


def test_corpus_1610_running_max_object_runs() -> None:
    path = _REPO / "tests/data/set06/indicators/1610_ind_deviation_trend_profile.pine"
    pine = path.read_text(encoding="utf-8")

    def _go() -> dict:
        compiled = compile_script(pine, use_cache=False)
        return compiled.run(*_ohlcv(24))

    out = _run_with_timeout(_go, seconds=30.0)
    assert isinstance(out, dict)
