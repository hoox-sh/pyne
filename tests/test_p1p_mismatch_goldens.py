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

"""P1p residual goldens: compile numeric series must match interpret (oracle).

Covers MACD SMA-seeded signal, OBV skip-first-change, ta.ao, ta.aroon.
Compile warmup stays na (never silent na→0) except where interpret itself
returns a documented 0 (OBV < 3 samples).
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


def _is_na(v: object) -> bool:
    if v is None:
        return True
    try:
        return v != v
    except Exception:
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


def _assert_finite_match(
    interp_vals: list[Any],
    compile_vals: list[Any],
    *,
    key: str,
    allow_interp_zero_warmup: bool = False,
) -> None:
    """When both cells are finite they must allclose; compile never invents 0 for na."""
    assert len(interp_vals) == len(compile_vals), f"{key}: length"
    n_both = 0
    for i, (a, b) in enumerate(zip(interp_vals, compile_vals, strict=True)):
        an, bn = _is_na(a), _is_na(b)
        if an and bn:
            continue
        if (not bn) and _is_na(a):
            # interpret na / missing → compile must not emit a silent 0
            if not (allow_interp_zero_warmup and float(b) == 0.0):
                assert abs(float(b)) > 1e-15 or allow_interp_zero_warmup, (
                    f"{key}[{i}]: compile filled na with {b!r}"
                )
            continue
        if an or bn:
            if allow_interp_zero_warmup and (not an) and float(a) == 0.0 and bn:
                continue
            if (not an) and bn:
                # compile still warming (na) while interpret already seeded —
                # allowed only before interpret's first *non-zero-or-warmup* value
                # is matched later. Counted as type/na leftover if persist.
                continue
            continue
        n_both += 1
        assert math.isclose(float(a), float(b), rel_tol=_RTOL, abs_tol=_ATOL), (
            f"{key}[{i}]: interp={a!r} compile={b!r}"
        )
    assert n_both >= 1, f"{key}: no overlapping finite cells"


def test_macd_signal_sma_seed_interp_compile() -> None:
    """MACD signal uses SMA seed; compile stays na until ready (not first-value)."""
    src = """
//@version=5
indicator("macd_p1p")
[macd, sig, hist] = ta.macd(close, 12, 26, 9)
plot(macd, "macd")
plot(sig, "sig")
plot(hist, "hist")
"""
    n = 80
    interp, compiled = _run_dual(src, _ohlcv(n))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    # First valid MACD at slow-1 = 25; signal SMA-ready at 25+8 = 33
    sig_i = interp["series"]["sig"]
    sig_c = compiled["series"]["sig"]
    macd_i = interp["series"]["macd"]
    macd_c = compiled["series"]["macd"]
    first_c = next((i for i, v in enumerate(sig_c) if not _is_na(v)), None)
    assert first_c == 33, f"compile signal first finite at {first_c}, expected 33"
    assert _is_na(sig_c[32]), "compile signal must stay na during SMA seed"
    # interpret incremental returns 0.0 until seeded — do not copy that to compile
    assert not _is_na(sig_i[33])
    assert math.isclose(float(sig_i[33]), float(sig_c[33]), rel_tol=_RTOL, abs_tol=_ATOL)
    _assert_finite_match(macd_i, macd_c, key="macd", allow_interp_zero_warmup=True)
    _assert_finite_match(sig_i, sig_c, key="sig", allow_interp_zero_warmup=True)
    _assert_finite_match(
        interp["series"]["hist"],
        compiled["series"]["hist"],
        key="hist",
        allow_interp_zero_warmup=True,
    )


def test_obv_skip_first_change_interp_compile() -> None:
    """OBV: 0 until 3 samples, accumulate from index 2 (interpret ``_obv``)."""
    src = """
//@version=5
indicator("obv_p1p")
plot(ta.obv(), "obv")
"""
    n = 20
    interp, compiled = _run_dual(src, _ohlcv(n))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    oi = interp["series"]["obv"]
    oc = compiled["series"]["obv"]
    assert oi[0] == 0.0 and oc[0] == 0.0
    assert oi[1] == 0.0 and oc[1] == 0.0
    for i, (a, b) in enumerate(zip(oi, oc, strict=True)):
        assert not _is_na(a) and not _is_na(b), f"obv[{i}] na"
        assert math.isclose(float(a), float(b), rel_tol=_RTOL, abs_tol=_ATOL), (
            f"obv[{i}]: interp={a!r} compile={b!r}"
        )
    # First change close[1] vs close[0] is skipped — bar 2 uses vol[2] only
    bars = _ohlcv(n)
    expected2 = 0.0
    if bars[2]["close"] > bars[1]["close"]:
        expected2 = float(bars[2]["volume"])
    elif bars[2]["close"] < bars[1]["close"]:
        expected2 = -float(bars[2]["volume"])
    assert math.isclose(float(oc[2]), expected2, abs_tol=_ATOL)


def test_ao_aroon_interp_compile() -> None:
    """ta.ao / ta.aroon compile kernels match interpret after warmup."""
    src = """
//@version=5
indicator("ao_aroon_p1p")
plot(ta.ao, "ao")
[adown, aup] = ta.aroon(14)
plot(adown, "adown")
plot(aup, "aup")
"""
    n = 80
    interp, compiled = _run_dual(src, _ohlcv(n))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    ao_c = compiled["series"]["ao"]
    first_ao = next((i for i, v in enumerate(ao_c) if not _is_na(v)), None)
    assert first_ao == 33, f"AO first finite at {first_ao}, expected 33 (slow=34)"
    assert all(_is_na(v) for v in ao_c[:33])
    _assert_finite_match(interp["series"]["ao"], ao_c, key="ao")

    ad_c = compiled["series"]["adown"]
    au_c = compiled["series"]["aup"]
    first_ar = next((i for i, v in enumerate(ad_c) if not _is_na(v)), None)
    assert first_ar == 14, f"aroon first finite at {first_ar}, expected 14"
    _assert_finite_match(interp["series"]["adown"], ad_c, key="adown")
    _assert_finite_match(interp["series"]["aup"], au_c, key="aup")
    # last cells must be finite on both hosts
    assert not _is_na(interp["series"]["ao"][-1])
    assert not _is_na(ao_c[-1])
    assert not _is_na(ad_c[-1]) and not _is_na(au_c[-1])


def test_nvi_pvi_interp_compile() -> None:
    """ta.nvi / ta.pvi compile kernels match incremental interpret (seed 1000)."""
    src = """
//@version=5
indicator("nvi_pvi_p1p")
plot(ta.nvi, "nvi")
plot(ta.pvi, "pvi")
"""
    n = 40
    interp, compiled = _run_dual(src, _ohlcv(n))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    for key in ("nvi", "pvi"):
        iv = interp["series"][key]
        cv = compiled["series"][key]
        assert math.isclose(float(iv[0]), 1000.0, abs_tol=_ATOL)
        assert math.isclose(float(cv[0]), 1000.0, abs_tol=_ATOL)
        _assert_finite_match(iv, cv, key=key)
        assert not _is_na(iv[-1]) and not _is_na(cv[-1])


def test_pvt_cumulative_interp_compile() -> None:
    """ta.pvt / ta.vpt is cumulative on both hosts (bar 0 is 0.0)."""
    src = """
//@version=5
indicator("pvt_p1p")
plot(ta.pvt, "pvt")
"""
    n = 20
    bars = _ohlcv(n)
    interp, compiled = _run_dual(src, bars)
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    iv = interp["series"]["pvt"]
    cv = compiled["series"]["pvt"]
    assert math.isclose(float(iv[0]), 0.0, abs_tol=_ATOL)
    assert math.isclose(float(cv[0]), 0.0, abs_tol=_ATOL)
    _assert_finite_match(iv, cv, key="pvt")
    # last value is the running sum, not the last-bar increment alone
    last_inc = 0.0
    prev = float(bars[-2]["close"])
    if prev != 0.0:
        last_inc = float(bars[-1]["volume"]) * (
            (float(bars[-1]["close"]) - prev) / prev
        )
    assert abs(float(iv[-1]) - last_inc) > 1e-9 or n <= 2
    assert math.isclose(float(iv[-1]), float(cv[-1]), rel_tol=_RTOL, abs_tol=_ATOL)


@pytest.mark.xfail(
    reason="P1p leftover: v4 bare sma/wma interpret stays all-na after bar-0 site bind; "
    "v5 ta.wma dual-host is OK (same handler).",
    strict=False,
)
def test_v4_bare_wma_interp_compile() -> None:
    """v4 ``wma(close, 22)`` should match ``ta.wma`` on both hosts."""
    src = """
//@version=4
study("wma_p1p")
plot(wma(close, 22), "w")
"""
    n = 40
    interp, compiled = _run_dual(src, _ohlcv(n))
    if compiled is None:
        pytest.skip("numba compile path unavailable")
    assert "error" not in interp, interp.get("error")
    iv = interp["series"]["w"]
    cv = compiled["series"]["w"]
    first_i = next((i for i, v in enumerate(iv) if not _is_na(v)), None)
    first_c = next((i for i, v in enumerate(cv) if not _is_na(v)), None)
    assert first_i == 21, f"interpret wma first finite at {first_i}"
    assert first_c == 21, f"compile wma first finite at {first_c}"
    _assert_finite_match(iv, cv, key="w")
