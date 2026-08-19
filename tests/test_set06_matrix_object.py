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

"""Set06 residual locks: matrix object handles + kron on misclassified scalars."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.compiler.numba_builtins import matrix_get
from pynescript.compiler.numba_builtins import matrix_kron


def _ohlcv(n: int = 20, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _last(out: dict, name: str = "plot_0") -> float:
    return float(np.asarray(out[name], dtype=np.float64)[-1])


def test_udf_returning_matrix_is_scalar_handle() -> None:
    """UDF that returns ``matrix.new`` must not store into a float64 series."""
    src = """//@version=5
indicator("udf-matrix")
makeM() =>
    matrix.new<float>(2, 2, 1.0)
var m = makeM()
plot(matrix.get(m, 0, 0))
"""
    code = transpile(src)
    assert "m_arr[__bar_idx] =" not in code
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(10))
    assert _last(out) == 1.0


def test_matrix_kron_1x2_is_object_handle() -> None:
    """``matrix.kron`` result is a matrix handle, not ``safe_float`` into float64."""
    src = """//@version=5
indicator("kron")
maA = matrix.new<float>(1, 2, 2.0)
mbA = matrix.new<float>(1, 2, 3.0)
raA = matrix.kron(maA, mbA)
plot(matrix.get(raA, 0, 0))
"""
    code = transpile(src)
    assert "raA_arr[__bar_idx] =" not in code
    assert "safe_float(matrix_kron" not in code
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(10))
    assert _last(out) == 6.0


def test_matrix_kron_float64_inputs_do_not_raise() -> None:
    """Misclassified series (numpy scalar) must yield empty matrix, not TypeError."""
    assert matrix_kron(1.0, 1.0) == []
    assert matrix_kron(np.float64(1.0), np.float64(2.0)) == []
    got = matrix_get(1.0, 0, 0)
    assert np.isnan(got)


def test_corpus_2738_udf_matrix_from_input_area() -> None:
    src = Path("tests/data/set06/indicators/2738_ind_matrix_new_type_example_3.pine").read_text()
    compiled = compile_script(src, use_cache=False)
    compiled.run(*_ohlcv(8))


def test_corpus_3712_matrix_kron() -> None:
    src = Path("tests/data/set06/indicators/3712_ind_matrix_kron.pine").read_text()
    code = transpile(src)
    assert "raA_arr[__bar_idx] =" not in code
    compiled = compile_script(src, use_cache=False)
    compiled.run(*_ohlcv(20))
