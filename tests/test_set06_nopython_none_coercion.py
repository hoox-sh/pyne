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

"""Object-mode None must not TypingError nested nopython scalar helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.numba_builtins import numba_abs
from pynescript.compiler.numba_builtins import numba_max
from pynescript.compiler.numba_builtins import numba_min
from pynescript.compiler.numba_builtins import numba_pine_eq
from pynescript.compiler.numba_builtins import numba_safe_div
from pynescript.compiler.numba_builtins import numba_safe_mod


pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")

_REPO = Path(__file__).resolve().parents[1]


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def test_numba_max_min_none_is_nan_not_typingerror() -> None:
    """Object-mode UDT None must coerce before the njit compare (no TypingError).

    Pine ``math.max``/``math.min`` skip na; both-na → nan.
    """
    mx_right = numba_max(1.0, None)
    mx_left = numba_max(None, 2.0)
    mn_both = numba_min(None, None)
    assert mx_right == 1.0
    assert mx_left == 2.0
    assert np.isnan(mn_both)


def test_numba_max_min_two_float64_still_jit() -> None:
    """Plain float64 pair keeps the nopython inner (not object-mode njit)."""
    assert numba_max(1.0, 2.0) == 2.0
    assert numba_min(1.0, 2.0) == 1.0
    assert numba_abs(-3.0) == 3.0


def test_other_scalar_helpers_none_not_typingerror() -> None:
    assert np.isnan(numba_abs(None))
    assert numba_pine_eq(None, None) is True
    assert numba_pine_eq(None, 1.0) is False
    assert np.isnan(numba_safe_div(None, 2.0))
    assert np.isnan(numba_safe_mod(1.0, None))


def test_nopython_math_max_two_float_series_runs() -> None:
    """Numeric math.max must still compile nopython (overload + jit inner)."""
    src = """//@version=5
indicator("nmax")
plot(math.max(close, open), title="m")
plot(math.min(high, low), title="n")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is False
    o, h, low, c, v = _ohlcv(10)
    out = compiled.run(o, h, low, c, v)
    assert abs(float(out["m"][-1]) - float(c[-1])) < 1e-12
    assert abs(float(out["n"][-1]) - float(low[-1])) < 1e-12


def test_udt_uninitialized_float_math_max_min_runs() -> None:
    src = """//@version=5
indicator("udt none max")
type Box
    float hi
    float lo
var b = Box.new()
plot(math.max(b.hi, close), title="mx")
plot(math.min(b.lo, close), title="mn")
plot(math.abs(b.hi), title="ab")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is True
    out = compiled.run(*_ohlcv(20))
    assert "mx" in out
    assert "mn" in out
    assert len(out["mx"]) == 20


def test_ict_macros_object_mode_run_no_typingerror() -> None:
    """set06 13645: already object_mode; nested numba_max must accept None."""
    path = _REPO / "tests/data/set06/indicators/13645_ind_ict_macros.pine"
    src = path.read_text(encoding="utf-8")
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is True
    out = compiled.run(*_ohlcv(24))
    # Overlay drawings-only script; run must not raise TypingError.
    assert isinstance(out, dict)
