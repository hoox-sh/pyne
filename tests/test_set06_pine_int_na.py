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

"""Pine ``int(na)`` / ``float(None)`` casts and sanitize chrome that RAW-parses."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pynescript.ast.helper import parse
from pynescript.compiler.engine import compile_script
from pynescript.compiler.numba_builtins import pine_bool
from pynescript.compiler.numba_builtins import pine_int
from pynescript.compiler.numba_builtins import pine_string
from pynescript.compiler.numba_builtins import safe_int
from pynescript.util.corpus_sanitize import sanitize_corpus_source


_REPO = Path(__file__).resolve().parents[1]
_SET06_IND = _REPO / "tests/data/set06/indicators"
_SET06_LIB = _REPO / "tests/data/set06/libraries"


def _ohlcv(n: int = 30, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def _compile_run(src: str, n: int = 20) -> dict:
    compiled = compile_script(src, use_cache=False)
    return compiled.run(*_ohlcv(n))


def test_pine_int_helper_na_is_nan_not_zero() -> None:
    """``safe_int`` stays NaN→0; Pine ``int(na)`` is na."""
    assert safe_int(np.nan) == 0
    assert np.isnan(pine_int(np.nan))
    assert np.isnan(pine_int(None))
    assert pine_int(5.7) == 5.0
    assert pine_int(-2.7) == -2.0
    assert pine_int(-0.5) == 0.0
    assert pine_int(x=True) == 1.0


def test_pine_bool_na_is_false() -> None:
    assert pine_bool(None) is False
    assert pine_bool(np.nan) is False
    assert pine_bool(0.0) is False
    assert pine_bool(3.2) is True


def test_pine_string_na_does_not_raise() -> None:
    assert pine_string(None) == "na"
    assert pine_string(np.nan) == "na"
    assert pine_string(x=True) == "true"


def test_int_na_plot_is_nan_int_float_truncates() -> None:
    src = """//@version=5
indicator("t")
plot(int(5.7), title="ip")
plot(int(-2.7), title="in")
plot(int(na), title="ina")
plot(float(na), title="fna")
plot(bool(na) ? 1.0 : 0.0, title="bna")
"""
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(10))
    assert float(out["ip"][-1]) == 5.0
    assert float(out["in"][-1]) == -2.0
    assert np.isnan(float(out["ina"][-1]))
    assert np.isnan(float(out["fna"][-1]))
    assert float(out["bna"][-1]) == 0.0


def test_3950_type_cast_basic_int_na_does_not_raise() -> None:
    """set06 3950: ``int(naFloat)`` must not ``ValueError: cannot convert float NaN``."""
    src = (_SET06_IND / "3950_ind_type_cast_basic.pine").read_text(encoding="utf-8")
    compiled = compile_script(src, use_cache=False)
    out = compiled.run(*_ohlcv(8))
    assert compiled.execute is not None
    assert isinstance(out, dict)


def test_12242_sanitize_keeps_block_comment_and_parses() -> None:
    raw = (_SET06_IND / "12242_ind_test_86.pine").read_text(encoding="utf-8")
    parse(raw)
    cleaned = sanitize_corpus_source(raw)
    assert "/*" in cleaned
    assert "*/" in cleaned
    assert "Still a comment" in cleaned
    assert "z = 5" in cleaned
    parse(cleaned)


def test_2492_markdown_planning_sanitized_parses() -> None:
    raw = (_SET06_IND / "2492_ind_pdf_01_reversal_radar_v2.pine").read_text(encoding="utf-8")
    cleaned = sanitize_corpus_source(raw)
    assert 'indicator("x")' in cleaned
    assert "Reversal Radar" not in cleaned
    parse(cleaned)
    compiled = compile_script(raw, use_cache=False)
    out = compiled.run(*_ohlcv(6))
    assert "plot_0" in out or "close" in out or len(out) >= 1


def test_14508_jinja_template_sanitized_parses() -> None:
    raw = (_SET06_IND / "14508_ind_indicator_2.pine").read_text(encoding="utf-8")
    cleaned = sanitize_corpus_source(raw)
    assert "{%" not in cleaned
    assert "{{" not in cleaned
    assert 'indicator("x")' in cleaned
    parse(cleaned)


def test_0018_library_sanitize_still_parses() -> None:
    raw = (_SET06_LIB / "0018_lib_16.pine").read_text(encoding="utf-8")
    parse(raw)
    cleaned = sanitize_corpus_source(raw)
    assert "DistMethod distMethod" in cleaned
    assert "export method unit_price" in cleaned
    assert "switch distMethod" in cleaned
    parse(cleaned)
