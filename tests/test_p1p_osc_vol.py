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

"""P1p oscillator/volume slice: interpret ≡ compile on recovered kernels."""

from __future__ import annotations

import math

import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import has_numba
from pynescript.runtime import Runtime


_RTOL = 1e-5
_ATOL = 1e-6


def _is_na(v: object) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _ohlcv(n: int = 80) -> list[dict[str, float | int]]:
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


def _run_dual(src: str, bars: list[dict[str, float | int]]):
    clear_parse_cache()
    interp = Runtime(symbol="P1P").run(src, bars, mode="interpret")
    assert "error" not in interp, interp.get("error")
    compiled = None
    if has_numba():
        clear_parse_cache()
        compiled = Runtime(symbol="P1P").run(src, bars, mode="compile")
        assert "error" not in compiled, compiled.get("error")
    return interp, compiled


def _assert_finite_match(interp_vals: list, compile_vals: list, *, key: str) -> None:
    assert len(interp_vals) == len(compile_vals), f"{key}: length"
    n_both = 0
    for i, (a, b) in enumerate(zip(interp_vals, compile_vals, strict=True)):
        an, bn = _is_na(a), _is_na(b)
        if an and bn:
            continue
        assert not an and not bn, f"{key}[{i}]: interp={a!r} compile={b!r}"
        n_both += 1
        assert math.isclose(float(a), float(b), rel_tol=_RTOL, abs_tol=_ATOL), f"{key}[{i}]: interp={a!r} compile={b!r}"
    assert n_both >= 1, f"{key}: no overlapping finite cells"


def _first_finite(vals: list) -> int | None:
    return next((i for i, v in enumerate(vals) if not _is_na(v)), None)


def test_math_sum_without_ta_dot_interp_compile() -> None:
    """math.sum must reset TA slots even when the script has no ``ta.``."""
    src = """
//@version=6
indicator("msum_p1p")
plot(math.sum(volume, 20), "s")
"""
    interp, compiled = _run_dual(src, _ohlcv(40))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    iv, cv = interp["series"]["s"], compiled["series"]["s"]
    assert _first_finite(iv) == 19
    assert _first_finite(cv) == 19
    assert all(_is_na(v) for v in iv[:19])
    _assert_finite_match(iv, cv, key="s")


def test_cmf_ad_math_sum_interp_compile() -> None:
    """Chaikin Money Flow builtin: rolling CLV*vol / vol (full window, not all-na)."""
    src = """
//@version=6
indicator("cmf_p1p")
length = 20
ad = close==high and close==low or high==low ? 0 : ((2*close-low-high)/(high-low))*volume
plot(math.sum(ad, length) / math.sum(volume, length), "CMF")
"""
    interp, compiled = _run_dual(src, _ohlcv(50))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    iv, cv = interp["series"]["CMF"], compiled["series"]["CMF"]
    assert _first_finite(iv) == 19
    assert _first_finite(cv) == 19
    _assert_finite_match(iv, cv, key="CMF")


def test_stoch_of_rsi_full_finite_window_interp_compile() -> None:
    """ta.stoch(rsi, rsi, rsi, n) stays na while RSI warmup poisons the window."""
    src = """
//@version=6
indicator("stochrsi_p1p")
rsi1 = ta.rsi(close, 14)
k = ta.sma(ta.stoch(rsi1, rsi1, rsi1, 14), 3)
d = ta.sma(k, 3)
plot(k, "K")
plot(d, "D")
"""
    interp, compiled = _run_dual(src, _ohlcv(50))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    k_i, k_c = interp["series"]["K"], compiled["series"]["K"]
    d_i, d_c = interp["series"]["D"], compiled["series"]["D"]
    # RSI first finite at 14; stoch length 14 → 27; SMA(3) → 29; D SMA(3) → 31
    assert _first_finite(k_i) == 29
    assert _first_finite(k_c) == 29
    assert _first_finite(d_i) == 31
    assert _first_finite(d_c) == 31
    _assert_finite_match(k_i, k_c, key="K")
    _assert_finite_match(d_i, d_c, key="D")


def test_stoch_full_window_interp_compile() -> None:
    """ta.stoch is na until ``length`` bars (no partial-window %K)."""
    src = """
//@version=6
indicator("stoch_p1p")
k = ta.sma(ta.stoch(close, high, low, 14), 1)
d = ta.sma(k, 3)
plot(k, "%K")
plot(d, "%D")
"""
    interp, compiled = _run_dual(src, _ohlcv(40))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    k_i, k_c = interp["series"]["%K"], compiled["series"]["%K"]
    d_i, d_c = interp["series"]["%D"], compiled["series"]["%D"]
    assert _first_finite(k_i) == 13
    assert _first_finite(k_c) == 13
    assert _first_finite(d_i) == 15
    assert _first_finite(d_c) == 15
    assert all(_is_na(v) for v in k_i[:13])
    _assert_finite_match(k_i, k_c, key="%K")
    _assert_finite_match(d_i, d_c, key="%D")


def test_cci_warmup_na_not_zero_interp_compile() -> None:
    """ta.cci warmup is na (never silent 0)."""
    src = """
//@version=6
indicator("cci_p1p")
plot(ta.cci(close, 14), "cci")
plot(ta.cci(close, 6), "turbo")
"""
    interp, compiled = _run_dual(src, _ohlcv(30))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    for key, first in (("cci", 13), ("turbo", 5)):
        iv, cv = interp["series"][key], compiled["series"][key]
        assert _first_finite(iv) == first, f"{key} interp first={_first_finite(iv)}"
        assert _first_finite(cv) == first, f"{key} compile first={_first_finite(cv)}"
        assert all(_is_na(v) for v in iv[:first])
        assert all(_is_na(v) for v in cv[:first])
        _assert_finite_match(iv, cv, key=key)


def test_rci_sma_of_rci_interp_compile() -> None:
    """SMA of ta.rci must seed after rci warmup (IEEE nan must not poison SMA)."""
    src = """
//@version=6
indicator("rci_p1p")
r = ta.rci(close, 10)
plot(r, "RCI")
plot(ta.sma(r, 14), "MA")
"""
    interp, compiled = _run_dual(src, _ohlcv(50))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    r_i, r_c = interp["series"]["RCI"], compiled["series"]["RCI"]
    m_i, m_c = interp["series"]["MA"], compiled["series"]["MA"]
    assert _first_finite(r_i) == 9
    assert _first_finite(r_c) == 9
    # rci ready at 9; SMA(14) of that → first finite at 9+13=22
    assert _first_finite(m_i) == 22
    assert _first_finite(m_c) == 22
    _assert_finite_match(r_i, r_c, key="RCI")
    _assert_finite_match(m_i, m_c, key="MA")


def test_rci_input_source_interp_compile() -> None:
    """input.source last-sample must still feed ta.rci (rank_correlation_index)."""
    src = """
//@version=6
indicator("rci_src_p1p")
source = input.source(close, title = "Source")
plot(ta.rci(source, 10), "RCI")
plot(ta.sma(ta.rci(source, 10), 14), "MA")
"""
    interp, compiled = _run_dual(src, _ohlcv(50))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    r_i, r_c = interp["series"]["RCI"], compiled["series"]["RCI"]
    m_i, m_c = interp["series"]["MA"], compiled["series"]["MA"]
    assert _first_finite(r_i) == 9
    assert _first_finite(r_c) == 9
    assert _first_finite(m_i) == 22
    assert _first_finite(m_c) == 22
    _assert_finite_match(r_i, r_c, key="RCI")
    _assert_finite_match(m_i, m_c, key="MA")


def test_rvi_ema_consecutive_seed_interp_compile() -> None:
    """RVI EMA seed is a consecutive finite window (not first-N skipping na)."""
    src = """
//@version=6
indicator("rvi_p1p")
length = 10
len = 14
stddev = ta.stdev(close, length)
upper = ta.ema(ta.change(close) <= 0 ? 0 : stddev, len)
lower = ta.ema(ta.change(close) > 0 ? 0 : stddev, len)
plot(upper / (upper + lower) * 100, "RVI")
"""
    interp, compiled = _run_dual(src, _ohlcv(50))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    iv, cv = interp["series"]["RVI"], compiled["series"]["RVI"]
    assert _first_finite(iv) == _first_finite(cv)
    _assert_finite_match(iv, cv, key="RVI")


def test_ultimate_oscillator_math_min_skip_na_interp_compile() -> None:
    """UO true-range uses math.min(low, close[1]); na on bar 0 is skipped."""
    src = """
//@version=6
indicator("uo_p1p")
high_ = math.max(high, close[1])
low_ = math.min(low, close[1])
bp = close - low_
tr_ = high_ - low_
avg7 = math.sum(bp, 7) / math.sum(tr_, 7)
avg14 = math.sum(bp, 14) / math.sum(tr_, 14)
avg28 = math.sum(bp, 28) / math.sum(tr_, 28)
plot(100 * (4*avg7 + 2*avg14 + avg28)/7, "Oscillator")
"""
    interp, compiled = _run_dual(src, _ohlcv(50))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    iv, cv = interp["series"]["Oscillator"], compiled["series"]["Oscillator"]
    assert _first_finite(iv) == 27
    assert _first_finite(cv) == 27
    _assert_finite_match(iv, cv, key="Oscillator")


def test_pivothigh_right_confirmation_interp_compile() -> None:
    """ta.pivothigh waits for rightbars confirmation (center = i - right)."""
    src = """
//@version=6
indicator("pivot_p1p")
plot(ta.pivothigh(close, 2, 2), "ph")
plot(ta.pivotlow(close, 2, 2), "pl")
"""
    # Peak at bar 3 (10) confirmed at 5; troughs at 6 (1) and 9 (0) confirmed at 8 / 11.
    closes = [1.0, 2.0, 3.0, 10.0, 3.0, 2.0, 1.0, 2.0, 3.0, 0.0, 3.0, 2.0, 4.0, 5.0, 6.0]
    bars = []
    for i, c in enumerate(closes):
        bars.append(
            {
                "open": c,
                "high": c + 0.5,
                "low": max(c - 0.5, 0.01),
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0,
            }
        )
    interp, compiled = _run_dual(src, bars)
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    ph_i, ph_c = interp["series"]["ph"], compiled["series"]["ph"]
    pl_i, pl_c = interp["series"]["pl"], compiled["series"]["pl"]
    assert _first_finite(ph_i) == 5
    assert _first_finite(ph_c) == 5
    assert math.isclose(float(ph_i[5]), 10.0, abs_tol=_ATOL)
    assert math.isclose(float(ph_c[5]), 10.0, abs_tol=_ATOL)
    assert _first_finite(pl_i) == 8
    assert _first_finite(pl_c) == 8
    assert math.isclose(float(pl_i[8]), 1.0, abs_tol=_ATOL)
    assert math.isclose(float(pl_c[8]), 1.0, abs_tol=_ATOL)
    assert math.isclose(float(pl_i[11]), 0.0, abs_tol=_ATOL)
    assert math.isclose(float(pl_c[11]), 0.0, abs_tol=_ATOL)
    _assert_finite_match(ph_i, ph_c, key="ph")
    _assert_finite_match(pl_i, pl_c, key="pl")
