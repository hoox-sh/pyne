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

"""Missing library ``alias.method(...)`` stubs must be Pine na, never Python None."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


_REPO = Path(__file__).resolve().parents[1]
_SET06_IND = _REPO / "tests/data/set06/indicators"


def _ohlcv(n: int = 20, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _compile_run(src: str, n: int = 20) -> dict:
    compiled = compile_script(src, use_cache=False)
    return compiled.run(*_ohlcv(n))


def test_import_method_stub_is_nan_not_none() -> None:
    """``eta.ma`` is absent — plot na / crossover 0, never ``float(None)``."""
    src = """//@version=5
indicator("t")
import Foo/Bar/1 as eta
ma = eta.ma(close, "sma", 20)
plot(ma)
plot(ta.crossover(close, ma) ? 1 : 0)
"""
    code = transpile(src)
    assert "float(None)" not in code
    assert "safe_float(None)" not in code
    assert "eta.ma" not in code
    out = _compile_run(src, n=20)
    ma = np.asarray(out["plot_0"], dtype=np.float64)
    cross = np.asarray(out["plot_1"], dtype=np.float64)
    assert ma.size == 20
    assert np.isnan(ma).all()
    assert np.all(cross == 0.0)


def test_import_alias_shadowed_by_stub_not_float_none() -> None:
    """3725 shape: ``import … as ma`` then ``ma = eta.ma(...)`` then ``ta.cross*``."""
    src = """//@version=5
indicator("t")
import Foo/Mat/1 as ma
import Foo/Bar/1 as eta
ma = eta.ma(close, "sma", 20)
plot(ma)
plot(ta.crossover(close, ma) ? 1 : 0)
plot(ta.crossunder(close, ma) ? 1 : 0)
"""
    code = transpile(src)
    assert "float(None)" not in code
    out = _compile_run(src, n=20)
    ma = np.asarray(out["plot_0"], dtype=np.float64)
    assert np.isnan(ma).all()
    assert np.all(np.asarray(out["plot_1"], dtype=np.float64) == 0.0)
    assert np.all(np.asarray(out["plot_2"], dtype=np.float64) == 0.0)


def test_import_method_tuple_unpack_is_nan_not_none() -> None:
    """``[a,b,c] = lib.foo()`` fills nans, not Python Nones."""
    src = """//@version=5
indicator("t")
import Foo/Bar/1 as lib
[a, b, c] = lib.foo()
plot(a)
plot(b)
plot(c)
"""
    code = transpile(src)
    assert "float(None)" not in code
    out = _compile_run(src, n=20)
    for key in ("plot_0", "plot_1", "plot_2"):
        arr = np.asarray(out[key], dtype=np.float64)
        assert arr.size == 20
        assert np.isnan(arr).all()


def test_corpus_3725_import_stub_runs() -> None:
    """Absent enhanced_ta must not ``float(None)`` on crossover / plot(ma)."""
    pine = (_SET06_IND / "3725_ind_extreme_trend_reversal_points.pine").read_text()
    compiled = compile_script(pine, use_cache=False)
    out = compiled.run(*_ohlcv(20))
    ma = np.asarray(out["Moving Average"], dtype=np.float64)
    assert ma.size == 20
    assert np.isnan(ma).all()
    drawings = out.get("__drawings")
    assert drawings is not None
