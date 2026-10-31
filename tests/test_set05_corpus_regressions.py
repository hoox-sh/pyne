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

"""Regression tests for genuine compiler bugs found via the set05 corpus.

Each class isolates one root cause that made valid third-party Pine scripts
fail in the compiled runtime while running fine under ``mode="interpret"``.
"""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile


def _clear_caches() -> None:
    clear_parse_cache()
    clear_compile_cache()


pytestmark = pytest.mark.skipif(not has_numba(), reason="numba not installed")


def _ohlcv(n: int = 100, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


class TestSelectorUDFSingleImplStaysNumeric:
    """``ma(type, src, len)`` selector UDF with ONE impl must return a float.

    Regression: a single UDF whose first param merely selects by string was
    misclassified as string-returning (``_call_returns_string`` overload
    branch fired for any UDF whose first arg inferred as string/color). The
    result series became a string buffer, so ``close > upperk`` compared
    Float64 vs Str → ``UFuncTypeError: ufunc 'greater'``. Only a genuine
    multi-impl overload set now qualifies for the string branch.
    """

    def test_selector_udf_returns_float_series(self) -> None:
        _clear_caches()
        src = """//@version=6
indicator("ma")
ma(type, src, len) =>
    result = 0.0
    if type == "SMA"
        result := ta.sma(src, len)
    result
m = ma("SMA", close, 5)
plot(m, title="m")
"""
        code = transpile(src)
        # Single impl → not string-returning → the plot series stays numeric.
        assert "m_arr = np.full(n_bars, np.nan)" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")
        arr = out["m"]
        # SMA(close, 5) at bar 10 = mean(c[6..10]) = mean(106..110) = 108.
        assert abs(float(arr[10]) - float(np.mean(c[6:11]))) < 1e-9

    def test_multi_impl_color_overload_still_string(self) -> None:
        """A genuine multi-impl overload must still trip the string branch."""
        _clear_caches()
        src = """//@version=6
indicator("neg")
negate(float v) =>
    -v
negate(bool v) =>
    not v
negate(color v) =>
    v
bool b = negate(close > open)
plot(b ? 1.0 : 0.0, title="b")
"""
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")


class TestTupleBuiltinSingleStoreSafeFloat:
    """``macdValue = ta.macd(...)`` (single store) must not land a tuple in float64.

    Regression: a tuple-returning numba builtin stored to one var was treated
    as a float64 scalar → ``ValueError: setting an array element with a
    sequence``. ``_is_safe_numeric_expr`` now rejects tuple-returning builtins
    unless the expr is explicitly indexed ``(...)``[k]``.
    """

    def test_macd_single_store_wraps_safe_float(self) -> None:
        _clear_caches()
        src = """//@version=6
indicator("macd")
macdValue = ta.macd(close, 12, 26, 9)
plot(macdValue, title="macd")
"""
        code = transpile(src)
        assert "safe_float(numba_macd" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(60)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")
        arr = out["macd"]
        # After warmup the MACD line is finite (safe_float picked element 0).
        assert np.isfinite(arr[-1])

    def test_supertrend_single_store_wraps_safe_float(self) -> None:
        """The frozenset covers supertrend/kc/stochrsi/aroon too, not just macd."""
        _clear_caches()
        src = """//@version=6
indicator("st")
stValue = ta.supertrend(3, 10)
plot(stValue, title="st")
"""
        code = transpile(src)
        assert "safe_float(numba_supertrend" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(40)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")
        assert np.isfinite(out["st"][-1])


class TestUDFDeclaredAfterSameNamedInput:
    """``maType = input.string(...)`` before ``maType(...) =>`` def.

    Regression: the script-level input store rebound the Python def, so every
    ``maType(...)`` call raised ``'str' object is not callable``. Top-level UDF
    names are now hoisted (``_pre_func_names``) before the body walk so the
    input renames to ``maType__loc`` while calls still resolve to the function.
    """

    def test_input_then_same_named_udf_runs(self) -> None:
        _clear_caches()
        src = """//@version=6
indicator("c")
maType = input.string("SMA", title="Type")
maType(src, len, type) =>
    result = 0.0
    if type == "SMA"
        result := ta.sma(src, len)
    result
m = maType(close, 5, "SMA")
plot(m, title="m")
"""
        code = transpile(src)
        # The input store is renamed; the function def keeps its name.
        assert "maType__loc" in code
        assert "def maType(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")
        arr = out["m"]
        assert abs(float(arr[10]) - float(np.mean(c[6:11]))) < 1e-9


class TestDrawingHandleSkipsUDTSeriesBranch:
    """``var table t = table.new(...)`` must be a scalar handle, not a series.

    Regression: a drawing/table handle lowers to a ``{'kind': …}`` dict that
    tripped ``_looks_like_object_handle_expr``, sending it through the UDT
    *series* branch (``t_arr[__bar_idx]``) before the drawing branch could make
    it a scalar. The UDT branch now skips drawing RHS so the handle becomes a
    scalar (``NameError: plt_arr is not defined`` when a UDF read the phantom
    series buffer).
    """

    def test_table_handle_is_scalar(self) -> None:
        _clear_caches()
        src = """//@version=6
indicator("t")
var plt = table.new(position.top_left, 1, 1)
if barstate.islast
    table.cell(plt, 0, 0, "hi")
plot(close, title="c")
"""
        code = transpile(src)
        # Table handle is a scalar (``plt = …``), never ``plt_arr[__bar_idx]``.
        assert "plt_arr[__bar_idx]" not in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")


class TestCrossWithNoneLevelGuardsFloat:
    """``ta.cross(close, NoneLevel)`` must guard ``float(None)``.

    Regression: a security-tuple stub level of ``None`` crashed
    ``TypeError: float() ... not 'NoneType'`` in ``_cross_pair``. Object mode
    now emits ``na_num(level)`` (None → nan); njit numeric levels are never
    None so the bare ``float()`` cast stays nopython-safe.
    """

    def test_cross_scalar_level_in_object_mode_uses_na_num(self) -> None:
        """In object mode the crossover level is na-guarded (None-safe)."""
        _clear_caches()
        src = """//@version=6
indicator("d")
s = "force-object-mode"
y = ta.cross(close, 0.0)
plot(y ? 1.0 : 0.0, title="y")
"""
        code = transpile(src)
        # Object-mode scalar level is na-guarded, never a bare ``float()``.
        assert "na_num(" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(20)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")
        assert len(out["y"]) == 20


class TestUserArrayNamedArrCollision:
    """``var float[] ph_arr`` + ``bool ph`` must not collide on ``ph_arr``.

    Regression: the user array ``ph_arr`` and the series buffer for ``bool ph``
    (also ``ph_arr``) lowered to the same Python identifier, so the per-bar
    ``ph_arr[__bar_idx] = …`` write hit ``IndexError: list assignment index out
    of range`` on the user's 2-element list. The user handle is renamed to
    ``ph_arr__hdl``; reads resolve via ``ident_map``.
    """

    def test_arr_named_handle_does_not_collide(self) -> None:
        _clear_caches()
        src = """//@version=6
indicator("i")
var float[] ph_arr = array.new_float(2)
bool ph = false
ph := close > open
v0 = array.get(ph_arr, 0)
plot(ph ? 1.0 : 0.0, title="ph")
"""
        code = transpile(src)
        # User handle renamed; bool series keeps the bare ``ph_arr`` buffer.
        assert "ph_arr__hdl" in code
        assert "ph_arr[__bar_idx]" in code
        compiled = compile_script(src)
        o, h, l, c, v = _ohlcv(30)
        out = compiled.run(o, h, l, c, v)
        assert "error" not in out, out.get("error")
        # ``_ohlcv`` yields o == c so ``close > open`` is always False → 0.0.
        arr = out["ph"]
        assert len(arr) == 30
        assert np.allclose(arr, 0.0)
