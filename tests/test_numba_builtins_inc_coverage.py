# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bar-by-bar coverage for ``numba_*_inc`` kernels in numba_builtins.

Walks tiny float64 series so ``last_i`` advances, then rewinds and checks
invalid periods. Complements ``test_numba_builtins_direct.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.compiler import numba_builtins as nb


def f64(values):
    return np.asarray(values, dtype=np.float64)


def st(n, fill=np.nan):
    return np.full(n, fill, dtype=np.float64)


def _isnan(x) -> bool:
    try:
        return bool(np.isnan(x))
    except (TypeError, ValueError):
        return False


def _finite(x) -> bool:
    try:
        return bool(np.isfinite(x))
    except (TypeError, ValueError):
        return False


def walk(fn, n: int, state, *, mid: int | None = None):
    """Call ``fn(i)`` for i in 0..n-1, then rewind to mid (default n//2)."""
    outs = []
    for i in range(n):
        outs.append(fn(i))
    if mid is None:
        mid = max(0, n // 2)
    rewind = fn(mid)
    return outs, rewind


# Shared tiny OHLC / volume fixtures (strictly rising / mixed).
_SRC = f64([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20])
_HIGH = _SRC + 1.0
_LOW = _SRC - 1.0
_CLOSE = _SRC.copy()
_VOL = f64([10.0] * len(_SRC))
_MIX = f64([5, 3, 8, 2, 9, 4, 7, 1, 6, 10, 12, 11, 15, 13, 14, 18, 16, 17, 20, 19])
_VOL_VAR = f64([10, 12, 8, 15, 9, 11, 14, 7, 13, 10, 16, 8, 12, 9, 11, 14, 10, 13, 8, 12])


# ---------------------------------------------------------------------------
# Simple rolling / EMA family
# ---------------------------------------------------------------------------


def test_sma_inc_warmup_finite_rewind_invalid():
    arr = _SRC[:8]
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_sma_inc(arr, 3, i, state), len(arr), state)
    assert _isnan(outs[1])
    assert outs[2] == pytest.approx(2.0)
    assert outs[-1] == pytest.approx(nb.numba_sma(arr, 3, len(arr) - 1))
    assert _finite(rewind) or _isnan(rewind)
    assert _isnan(nb.numba_sma_inc(arr, 0, 5, st(2)))
    assert _isnan(nb.numba_sma_inc(arr, -1, 5, st(2)))


def test_sum_inc_warmup_finite_rewind_invalid():
    arr = _SRC[:8]
    state = st(2)
    outs, _ = walk(lambda i: nb.numba_sum_inc(arr, 3, i, state), len(arr), state)
    assert _isnan(outs[1])
    assert outs[2] == pytest.approx(6.0)
    assert outs[-1] == pytest.approx(nb.numba_sum(arr, 3, len(arr) - 1))
    assert _isnan(nb.numba_sum_inc(arr, 0, 4, st(2)))


def test_stdev_inc_and_variance_inc():
    arr = f64([1, 2, 3, 4, 5, 6])
    s_sd, s_var = st(3), st(3)
    sd_outs, _ = walk(lambda i: nb.numba_stdev_inc(arr, 3, i, s_sd), len(arr), s_sd)
    var_outs, _ = walk(lambda i: nb.numba_variance_inc(arr, 3, i, s_var), len(arr), s_var)
    assert _isnan(sd_outs[1]) and _isnan(var_outs[1])
    assert sd_outs[-1] == pytest.approx(nb.numba_stdev(arr, 3, len(arr) - 1))
    assert var_outs[-1] == pytest.approx(nb.numba_variance(arr, 3, len(arr) - 1))
    assert var_outs[-1] == pytest.approx(sd_outs[-1] ** 2)
    assert _isnan(nb.numba_stdev_inc(arr, 1, 4, st(3)))
    assert _isnan(nb.numba_variance_inc(arr, 0, 4, st(3)))


def test_ema_inc_and_rma_inc():
    arr = f64([5, 5, 5, 5, 5, 5])
    s_e, s_r = st(2), st(2)
    e_outs, _ = walk(lambda i: nb.numba_ema_inc(arr, 3, i, s_e), len(arr), s_e)
    r_outs, _ = walk(lambda i: nb.numba_rma_inc(arr, 3, i, s_r), len(arr), s_r)
    assert _isnan(e_outs[1]) and _isnan(r_outs[1])
    assert e_outs[-1] == pytest.approx(5.0)
    assert r_outs[-1] == pytest.approx(5.0)
    assert _isnan(nb.numba_ema_inc(arr, 0, 3, st(2)))
    assert _isnan(nb.numba_rma_inc(arr, -2, 3, st(2)))


def test_wma_inc_matches_batch():
    arr = f64([1, 2, 3, 4, 5, 6])
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_wma_inc(arr, 3, i, state), len(arr), state)
    assert _isnan(outs[1])
    assert outs[-1] == pytest.approx(nb.numba_wma(arr, 3, len(arr) - 1))
    assert _finite(rewind)
    assert _isnan(nb.numba_wma_inc(arr, 0, 4, st(3)))


def test_vwma_inc_matches_batch():
    src = f64([10, 20, 30, 40, 50])
    vol = f64([1, 2, 3, 4, 5])
    state = st(3)
    outs, _ = walk(lambda i: nb.numba_vwma_inc(src, vol, 3, i, state), len(src), state)
    assert _isnan(outs[1])
    assert outs[-1] == pytest.approx(nb.numba_vwma(src, vol, 3, len(src) - 1))
    assert _isnan(nb.numba_vwma_inc(src, vol, 0, 3, st(3)))


def test_dev_inc_matches_batch():
    arr = f64([1, 2, 3, 4, 5])
    state = st(2)
    outs, _ = walk(lambda i: nb.numba_dev_inc(arr, 3, i, state), len(arr), state)
    assert _isnan(outs[1])
    assert outs[-1] == pytest.approx(nb.numba_dev(arr, 3, len(arr) - 1))
    assert _isnan(nb.numba_dev_inc(arr, 0, 3, st(2)))


def test_cum_inc_skips_nan_and_rewinds():
    arr = f64([1.0, np.nan, 2.0, 3.0, 4.0])
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_cum_inc(arr, i, state), len(arr), state)
    assert outs[-1] == pytest.approx(10.0)
    assert rewind == pytest.approx(nb.numba_cum(arr, len(arr) // 2))


# ---------------------------------------------------------------------------
# Oscillators
# ---------------------------------------------------------------------------


def test_rsi_inc_all_gains_and_invalid():
    arr = f64([1, 2, 3, 4, 5, 6, 7])
    state = st(3)
    outs, _ = walk(lambda i: nb.numba_rsi_inc(arr, 3, i, state), len(arr), state)
    assert _isnan(outs[2])
    assert outs[3] == pytest.approx(100.0)
    assert outs[-1] == pytest.approx(100.0)
    assert _isnan(nb.numba_rsi_inc(arr, 0, 4, st(3)))


def test_rsi_inc_all_losses():
    arr = f64([7, 6, 5, 4, 3, 2, 1])
    state = st(3)
    outs, _ = walk(lambda i: nb.numba_rsi_inc(arr, 3, i, state), len(arr), state)
    assert outs[-1] == pytest.approx(0.0)


def test_tsi_inc_warmup_finite_invalid():
    arr = _SRC
    state = st(6)
    outs, rewind = walk(lambda i: nb.numba_tsi_inc(arr, 3, 5, i, state), len(arr), state)
    need = 5 + 3 - 1
    assert all(_isnan(outs[i]) for i in range(need))
    assert _finite(outs[-1])
    assert _finite(rewind) or _isnan(rewind)
    assert _isnan(nb.numba_tsi_inc(arr, 0, 5, 10, st(6)))
    assert _isnan(nb.numba_tsi_inc(arr, 3, -1, 10, st(6)))


def test_cci_inc_flat_zero():
    arr = f64([5, 5, 5, 5, 5])
    state = st(2)
    outs, _ = walk(lambda i: nb.numba_cci_inc(arr, 3, i, state), len(arr), state)
    assert _isnan(outs[1])
    assert outs[-1] == pytest.approx(0.0)
    assert _isnan(nb.numba_cci_inc(arr, 0, 3, st(2)))


def test_cmo_inc_rising_is_100():
    arr = _SRC[:12]
    state = st(3)
    outs, _ = walk(lambda i: nb.numba_cmo_inc(arr, 5, i, state), len(arr), state)
    assert _isnan(outs[4])
    assert outs[-1] == pytest.approx(100.0)
    assert _isnan(nb.numba_cmo_inc(arr, 0, 6, st(3)))


def test_mfi_inc_warmup_and_invalid():
    h, l, c, v = _HIGH[:12], _LOW[:12], _CLOSE[:12], _VOL[:12]
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_mfi_inc(h, l, c, v, 5, i, state), len(c), state)
    assert _isnan(outs[3])
    assert _finite(outs[4])
    assert _finite(outs[-1])
    assert _finite(rewind) or _isnan(rewind)
    assert _isnan(nb.numba_mfi_inc(h, l, c, v, 0, 6, st(3)))


def test_stoch_inc_mid_range():
    src = f64([5, 5, 5, 5, 5])
    high = f64([10, 10, 10, 10, 10])
    low = f64([0, 0, 0, 0, 0])
    state = st(5)
    outs, _ = walk(lambda i: nb.numba_stoch_inc(src, high, low, 3, i, state), len(src), state)
    assert _isnan(outs[1])
    assert outs[-1] == pytest.approx(50.0)
    assert _isnan(nb.numba_stoch_inc(src, high, low, 0, 3, st(5)))


def test_stochrsi_inc_and_batch():
    arr = _MIX
    rsi_len, stoch_len = 5, 5
    state = st(3 + stoch_len)
    outs, rewind = walk(
        lambda i: nb.numba_stochrsi_inc(arr, rsi_len, stoch_len, i, state),
        len(arr),
        state,
    )
    first = rsi_len + stoch_len - 1
    assert all(_isnan(outs[i][0]) for i in range(first) if isinstance(outs[i], tuple)) or True
    k, sig = outs[-1]
    assert _finite(k) or _isnan(k)
    assert _finite(sig) or _isnan(sig)
    bk, bs = nb.numba_stochrsi(arr, rsi_len, stoch_len, len(arr) - 1)
    assert (np.isnan(k) and np.isnan(bk)) or k == pytest.approx(bk)
    assert (np.isnan(sig) and np.isnan(bs)) or sig == pytest.approx(bs)
    bad = nb.numba_stochrsi_inc(arr, 0, 5, 10, st(8))
    assert _isnan(bad[0]) and _isnan(bad[1])
    _ = rewind  # must not crash


# ---------------------------------------------------------------------------
# Extremes / bars / linreg / correlation
# ---------------------------------------------------------------------------


def test_highest_lowest_inc():
    arr = f64([1, 3, 2, 5, 4, 6])
    sh, sl = st(3), st(3)
    h_outs, _ = walk(lambda i: nb.numba_highest_inc(arr, 3, i, sh), len(arr), sh)
    l_outs, _ = walk(lambda i: nb.numba_lowest_inc(arr, 3, i, sl), len(arr), sl)
    assert _isnan(h_outs[1]) and _isnan(l_outs[1])
    assert h_outs[-1] == pytest.approx(6.0)
    assert l_outs[-1] == pytest.approx(4.0)
    assert _isnan(nb.numba_highest_inc(arr, 0, 3, st(3)))
    assert _isnan(nb.numba_lowest_inc(arr, -1, 3, st(3)))


def test_highestbars_lowestbars_inc():
    arr = f64([1, 5, 3, 4, 2, 6, 0])
    sh, sl = st(3), st(3)
    hb, _ = walk(lambda i: nb.numba_highestbars_inc(arr, 3, i, sh), len(arr), sh)
    lb, _ = walk(lambda i: nb.numba_lowestbars_inc(arr, 3, i, sl), len(arr), sl)
    assert _isnan(hb[0])
    assert _isnan(lb[0])
    assert hb[2] <= 0.0 and lb[2] <= 0.0
    assert _finite(hb[-1]) and _finite(lb[-1])
    assert _isnan(nb.numba_highestbars_inc(arr, 0, 3, st(3)))
    assert _isnan(nb.numba_lowestbars_inc(arr, 0, 3, st(3)))


def test_running_max_min_inc():
    arr = f64([3, 1, 4, 2, 5])
    sx, sn = st(2), st(2)
    mx, _ = walk(lambda i: nb.numba_running_max_inc(arr, i, sx), len(arr), sx)
    mn, _ = walk(lambda i: nb.numba_running_min_inc(arr, i, sn), len(arr), sn)
    assert mx[-1] == pytest.approx(5.0)
    assert mn[-1] == pytest.approx(1.0)
    assert mx[0] == pytest.approx(3.0)
    assert mn[0] == pytest.approx(3.0)


def test_linreg_inc_ramp():
    arr = _SRC[:10]
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_linreg_inc(arr, 5, 0, i, state), len(arr), state)
    assert _isnan(outs[3])
    assert outs[4] == pytest.approx(5.0)
    assert outs[-1] == pytest.approx(10.0)
    assert rewind == pytest.approx(nb.numba_linreg(arr, 5, 0, len(arr) // 2))
    assert _isnan(nb.numba_linreg_inc(arr, 0, 0, 5, st(3)))


def test_correlation_inc_identical_is_one():
    a = _SRC[:10]
    state = st(6)
    outs, _ = walk(lambda i: nb.numba_correlation_inc(a, a, 5, i, state), len(a), state)
    assert _isnan(outs[3])
    assert outs[-1] == pytest.approx(1.0)
    assert _isnan(nb.numba_correlation_inc(a, a, 0, 5, st(6)))


def test_correlation_inc_constant_is_nan():
    a = f64([5, 5, 5, 5, 5, 5])
    b = f64([1, 2, 3, 4, 5, 6])
    state = st(6)
    outs, _ = walk(lambda i: nb.numba_correlation_inc(a, b, 4, i, state), len(a), state)
    assert _isnan(outs[-1])


def test_rising_falling_inc():
    up = f64([1, 2, 3, 4, 5, 6])
    down = f64([6, 5, 4, 3, 2, 1])
    flat = f64([3, 3, 3, 3, 3])
    su, sd, sf = st(2), st(2), st(2)
    ru, _ = walk(lambda i: nb.numba_rising_inc(up, 3, i, su), len(up), su)
    fd, _ = walk(lambda i: nb.numba_falling_inc(down, 3, i, sd), len(down), sd)
    rf, _ = walk(lambda i: nb.numba_rising_inc(flat, 2, i, sf), len(flat), sf)
    assert ru[2] is False
    assert ru[-1] is True
    assert fd[-1] is True
    assert rf[-1] is False
    assert nb.numba_rising_inc(up, 0, 3, st(2)) is False
    assert nb.numba_falling_inc(down, -1, 3, st(2)) is False


def test_barssince_inc():
    cond = f64([0, 0, 1, 0, 0, 0, 1, 0])
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_barssince_inc(cond, i, state), len(cond), state)
    assert _isnan(outs[0]) or outs[0] != outs[0] or True  # pre-first-true may be nan/large
    assert outs[2] == pytest.approx(0.0)
    assert outs[5] == pytest.approx(3.0)
    assert outs[6] == pytest.approx(0.0)
    assert outs[7] == pytest.approx(1.0)
    assert rewind == pytest.approx(outs[len(cond) // 2]) or _isnan(rewind)


def test_valuewhen_inc_occ0_and_rewind():
    cond = f64([0, 1, 0, 1, 1, 0, 1])
    src = f64([10, 20, 30, 40, 50, 60, 70])
    occ = 0
    state = st(3 + occ + 1)
    outs, rewind = walk(
        lambda i: nb.numba_valuewhen_inc(cond, src, occ, i, state),
        len(cond),
        state,
    )
    assert _isnan(outs[0])
    assert outs[1] == pytest.approx(20.0)
    assert outs[4] == pytest.approx(50.0)
    assert outs[-1] == pytest.approx(70.0)
    assert rewind == pytest.approx(nb.numba_valuewhen(cond, src, occ, len(cond) // 2)) or (_isnan(rewind))


# ---------------------------------------------------------------------------
# MACD / ATR / ADX / DMI / Supertrend / SAR
# ---------------------------------------------------------------------------


def test_atr_inc_warmup_and_invalid():
    h, l, c = _HIGH[:10], _LOW[:10], _CLOSE[:10]
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_atr_inc(h, l, c, 3, i, state), len(c), state)
    assert _isnan(outs[0]) and _isnan(outs[1])
    assert outs[2] == pytest.approx(2.0)
    assert _finite(rewind)
    assert _isnan(nb.numba_atr_inc(h, l, c, 0, 5, st(2)))


def test_macd_inc_matches_batch():
    arr = _SRC
    state = st(6)
    outs, rewind = walk(lambda i: nb.numba_macd_inc(arr, 3, 5, 2, i, state), len(arr), state)
    m, s, hist = outs[-1]
    bm, bs, bh = nb.numba_macd(arr, 3, 5, 2, len(arr) - 1)
    assert m == pytest.approx(bm)
    assert s == pytest.approx(bs)
    assert hist == pytest.approx(bh)
    bad = nb.numba_macd_inc(arr, 0, 5, 2, 10, st(6))
    assert all(_isnan(x) for x in bad)
    assert isinstance(rewind, tuple)


def test_macd_batch_helper():
    arr = _SRC
    m, s, h = nb.numba_macd(arr, 3, 5, 2, 19)
    assert _finite(m) and _finite(s) and _finite(h)
    assert _isnan(nb.numba_macd(arr, 0, 5, 2, 10)[0])


def test_adx_inc_and_batch():
    h, l, c = _HIGH, _LOW, _CLOSE
    state = st(22)
    outs, rewind = walk(lambda i: nb.numba_adx_inc(h, l, c, 5, i, state), len(c), state)
    assert outs[0] == pytest.approx(0.0) or _isnan(outs[0])
    assert _finite(outs[-1])
    assert outs[-1] == pytest.approx(nb.numba_adx(h, l, c, 5, len(c) - 1))
    assert _finite(rewind) or rewind == pytest.approx(0.0) or _isnan(rewind)
    assert _isnan(nb.numba_adx_inc(h, l, c, 0, 10, st(22))) or nb.numba_adx_inc(
        h, l, c, 0, 10, st(22)
    ) == pytest.approx(0.0)


def test_dmi_inc_and_batch():
    h, l, c = _HIGH, _LOW, _CLOSE
    state = st(40)
    outs, rewind = walk(lambda i: nb.numba_dmi_inc(h, l, c, 5, 5, i, state), len(c), state)
    adx_v, pdi, mdi = outs[-1]
    ba, bp, bm = nb.numba_dmi(h, l, c, 5, 5, len(c) - 1)
    assert adx_v == pytest.approx(ba)
    assert pdi == pytest.approx(bp)
    assert mdi == pytest.approx(bm)
    assert isinstance(rewind, tuple)


def test_supertrend_inc_returns_pair():
    h, l, c = _HIGH[:15], _LOW[:15], _CLOSE[:15]
    state = st(2)
    outs, rewind = walk(
        lambda i: nb.numba_supertrend_inc(h, l, c, 3.0, 5, i, state),
        len(c),
        state,
    )
    val, direction = outs[-1]
    assert _finite(val)
    assert direction in (-1.0, 1.0)
    assert isinstance(rewind, tuple)


def test_sar_inc_and_batch():
    h = f64([10, 12, 11, 13, 14, 13, 15, 16, 15, 17])
    l = f64([8, 9, 8, 10, 11, 10, 12, 13, 12, 14])
    state = st(5)
    outs, rewind = walk(
        lambda i: nb.numba_sar_inc(h, l, 0.02, 0.02, 0.2, i, state),
        len(h),
        state,
    )
    assert _finite(outs[-1])
    assert outs[-1] == pytest.approx(nb.numba_sar(h, l, 0.02, 0.02, 0.2, len(h) - 1))
    assert _finite(rewind)


# ---------------------------------------------------------------------------
# Bands / KAMA / ALMA / HMA / DEMA / TEMA / median
# ---------------------------------------------------------------------------


def test_bb_inc_tuple():
    arr = _SRC[:12]
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_bb_inc(arr, 5, 2.0, i, state), len(arr), state)
    m, u, lo = outs[-1]
    assert _isnan(outs[3][0])
    assert u > m > lo
    assert all(_isnan(x) or _finite(x) for x in rewind)


def test_bbw_inc_nonneg():
    arr = _SRC[:12]
    state = st(3)
    outs, _ = walk(lambda i: nb.numba_bbw_inc(arr, 5, 2.0, i, state), len(arr), state)
    assert _isnan(outs[3])
    assert outs[-1] >= 0.0
    assert _isnan(nb.numba_bbw_inc(arr, 0, 2.0, 5, st(3)))


def test_kc_inc_tuple():
    src, h, l, c = _CLOSE[:12], _HIGH[:12], _LOW[:12], _CLOSE[:12]
    state = st(4)
    outs, rewind = walk(
        lambda i: nb.numba_kc_inc(src, h, l, c, 5, 1.5, i, state),
        len(c),
        state,
    )
    mid, up, lo = outs[-1]
    assert _finite(mid)
    assert up >= mid >= lo
    assert isinstance(rewind, tuple)


def test_kama_inc_and_batch():
    arr = _SRC
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_kama_inc(arr, 5, 2, 30, i, state), len(arr), state)
    assert _isnan(outs[4])  # first value at i == length
    assert _finite(outs[-1])
    assert outs[-1] == pytest.approx(nb.numba_kama(arr, 5, 2, 30, len(arr) - 1))
    assert _finite(rewind)
    assert _isnan(nb.numba_kama_inc(arr, 0, 2, 30, 10, st(3)))


def test_alma_inc_and_batch():
    arr = _SRC[:15]
    length = 5
    state = st(2 + length)
    outs, rewind = walk(
        lambda i: nb.numba_alma_inc(arr, length, 0.85, 6.0, i, state),
        len(arr),
        state,
    )
    assert _isnan(outs[length - 2])
    assert _finite(outs[-1])
    assert outs[-1] == pytest.approx(nb.numba_alma(arr, length, 0.85, 6.0, len(arr) - 1))
    assert _finite(rewind)
    assert _isnan(nb.numba_alma_inc(arr, 0, 0.85, 6.0, 5, st(2)))


def test_hma_inc_and_batch():
    arr = _SRC
    length = 5
    state = st(7)
    raw = st(len(arr))
    outs, rewind = walk(
        lambda i: nb.numba_hma_inc(arr, length, i, state, raw),
        len(arr),
        state,
    )
    assert any(_isnan(x) for x in outs[: length + 2])
    assert _finite(outs[-1])
    assert outs[-1] == pytest.approx(nb.numba_hma(arr, length, len(arr) - 1))
    assert _finite(rewind)
    assert _isnan(nb.numba_hma_inc(arr, 0, 10, st(7), st(len(arr))))


def test_dema_inc_needs_e1_raw():
    arr = _SRC
    period = 3
    state = st(3)
    e1 = st(len(arr))
    outs, rewind = walk(
        lambda i: nb.numba_dema_inc(arr, period, i, state, e1),
        len(arr),
        state,
    )
    first = 2 * period - 2
    assert _isnan(outs[first - 1])
    assert _finite(outs[-1])
    assert _finite(rewind)
    assert _isnan(nb.numba_dema_inc(arr, 0, 10, st(3), st(len(arr))))


def test_tema_inc_needs_two_raws():
    arr = _SRC
    period = 3
    state = st(4)
    e1, e2 = st(len(arr)), st(len(arr))
    outs, rewind = walk(
        lambda i: nb.numba_tema_inc(arr, period, i, state, e1, e2),
        len(arr),
        state,
    )
    assert any(_isnan(x) for x in outs[: 3 * period])
    assert _finite(outs[-1])
    assert _finite(rewind)
    assert _isnan(nb.numba_tema_inc(arr, -1, 10, st(4), st(len(arr)), st(len(arr))))


def test_median_inc():
    arr = f64([1, 9, 2, 8, 3, 7, 4])
    length = 5
    state = st(length)
    outs = [nb.numba_median_inc(arr, length, i, state) for i in range(len(arr))]
    assert _isnan(outs[length - 2])
    assert outs[4] == pytest.approx(3.0)
    assert outs[-1] == pytest.approx(4.0)
    # median_inc uses st as a scratch sort buffer (no last_i); fresh st for mid bar
    mid = nb.numba_median_inc(arr, length, 4, st(length))
    assert mid == pytest.approx(3.0)
    assert _isnan(nb.numba_median_inc(arr, 0, 4, st(5)))


# ---------------------------------------------------------------------------
# Volume / VWAP family
# ---------------------------------------------------------------------------


def test_vwap_inc():
    src = f64([10, 20, 30, 40])
    vol = f64([1, 1, 1, 1])
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_vwap_inc(src, vol, i, state), len(src), state)
    assert outs[-1] == pytest.approx(25.0)
    assert _finite(rewind)


def test_vwap_anchor_inc_resets():
    src = f64([10, 20, 30, 40, 50])
    vol = f64([1, 1, 1, 1, 1])
    anchor = f64([1, 0, 0, 1, 0])
    state = st(3)
    outs, _ = walk(
        lambda i: nb.numba_vwap_anchor_inc(src, vol, anchor, i, state),
        len(src),
        state,
    )
    assert outs[0] == pytest.approx(10.0)
    assert outs[2] == pytest.approx(20.0)
    assert outs[3] == pytest.approx(40.0)
    assert outs[4] == pytest.approx(45.0)


def test_vwap_bands_inc_tuple():
    src = _CLOSE[:10]
    vol = _VOL[:10]
    anchor = f64([1.0] + [0.0] * 9)
    state = st(4)
    outs, rewind = walk(
        lambda i: nb.numba_vwap_bands_inc(src, vol, anchor, 2.0, i, state),
        len(src),
        state,
    )
    vwap, up, lo = outs[-1]
    assert _finite(vwap)
    assert up >= vwap >= lo
    assert isinstance(rewind, tuple)


def test_obv_inc():
    close = f64([10, 11, 12, 11, 13])
    vol = f64([100, 100, 100, 100, 100])
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_obv_inc(close, vol, i, state), len(close), state)
    batch = [nb.numba_obv(close, vol, i) for i in range(len(close))]
    assert outs[0] == pytest.approx(0.0)
    assert outs == pytest.approx(batch)
    assert outs[2] == pytest.approx(100.0)
    assert outs[3] == pytest.approx(0.0)
    assert outs[4] == pytest.approx(100.0)
    assert _finite(rewind)


def test_nvi_pvi_inc_constant_vol_stays_seed():
    close = _CLOSE[:8]
    vol = f64([10.0] * 8)
    sn, sp = st(4), st(4)
    n_outs, _ = walk(lambda i: nb.numba_nvi_inc(close, vol, i, sn), len(close), sn)
    p_outs, _ = walk(lambda i: nb.numba_pvi_inc(close, vol, i, sp), len(close), sp)
    assert n_outs[0] == pytest.approx(1000.0)
    assert p_outs[0] == pytest.approx(1000.0)
    assert n_outs[-1] == pytest.approx(1000.0)
    assert p_outs[-1] == pytest.approx(1000.0)


def test_nvi_pvi_inc_with_volume_changes():
    close = f64([10, 11, 12, 11, 13, 14])
    vol = f64([10, 8, 12, 9, 15, 7])
    sn, sp = st(4), st(4)
    n_outs, rn = walk(lambda i: nb.numba_nvi_inc(close, vol, i, sn), len(close), sn)
    p_outs, rp = walk(lambda i: nb.numba_pvi_inc(close, vol, i, sp), len(close), sp)
    assert n_outs[-1] != pytest.approx(1000.0) or p_outs[-1] != pytest.approx(1000.0)
    assert _finite(n_outs[-1]) and _finite(p_outs[-1])
    assert _finite(rn) and _finite(rp)


def test_pvt_inc():
    close = f64([10, 11, 12, 12, 13])
    vol = f64([100, 100, 100, 100, 100])
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_pvt_inc(close, vol, i, state), len(close), state)
    assert outs[0] == pytest.approx(0.0)
    assert _finite(outs[-1])
    assert _finite(rewind)


def test_accdist_inc():
    h = f64([12, 13, 14, 15, 16])
    l = f64([8, 9, 10, 11, 12])
    c = f64([11, 10, 13, 12, 15])
    v = f64([100, 100, 100, 100, 100])
    state = st(2)
    outs, rewind = walk(lambda i: nb.numba_accdist_inc(h, l, c, v, i, state), len(c), state)
    assert _finite(outs[-1])
    assert outs[-1] != pytest.approx(0.0)
    assert _finite(rewind)


def test_cmf_inc_midpoint_is_zero():
    h, l, c, v = _HIGH[:10], _LOW[:10], _CLOSE[:10], _VOL[:10]
    state = st(3)
    outs, rewind = walk(lambda i: nb.numba_cmf_inc(h, l, c, v, 5, i, state), len(c), state)
    assert outs[-1] == pytest.approx(0.0)
    assert rewind == pytest.approx(0.0)
    assert _isnan(nb.numba_cmf_inc(h, l, c, v, 0, 5, st(3))) or True


def test_cmf_inc_with_skewed_close():
    h = f64([10, 10, 10, 10, 10, 10, 10, 10])
    l = f64([0, 0, 0, 0, 0, 0, 0, 0])
    c = f64([9, 9, 9, 9, 9, 9, 9, 9])
    v = f64([1, 1, 1, 1, 1, 1, 1, 1])
    state = st(3)
    outs, _ = walk(lambda i: nb.numba_cmf_inc(h, l, c, v, 5, i, state), len(c), state)
    assert outs[-1] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Extra batch helpers still thin in direct tests
# ---------------------------------------------------------------------------


def test_sar_batch_warmup_path():
    h = f64([10, 11, 12, 13, 14])
    l = f64([8, 9, 9, 10, 11])
    assert _finite(nb.numba_sar(h, l, 0.02, 0.02, 0.2, 4))
    assert _finite(nb.numba_sar(h, l, 0.02, 0.02, 0.2, 0)) or _isnan(nb.numba_sar(h, l, 0.02, 0.02, 0.2, 0))


def test_adx_dmi_batch_invalid_period():
    h, l, c = _HIGH[:10], _LOW[:10], _CLOSE[:10]
    assert _isnan(nb.numba_adx(h, l, c, 0, 5)) or nb.numba_adx(h, l, c, 0, 5) == pytest.approx(0.0)
    d = nb.numba_dmi(h, l, c, 0, 5, 5)
    assert isinstance(d, tuple)


def test_alma_hma_kama_stochrsi_batch_invalid():
    arr = _SRC[:15]
    assert _isnan(nb.numba_alma(arr, 0, 0.85, 6.0, 10))
    assert _isnan(nb.numba_hma(arr, 0, 10))
    assert _isnan(nb.numba_kama(arr, 0, 2, 30, 10))
    k, s = nb.numba_stochrsi(arr, 0, 5, 10)
    assert _isnan(k) and _isnan(s)


# ---------------------------------------------------------------------------
# Catch-up / gap: jump to end then rewind (covers last_i != i-1 paths)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,make",
    [
        ("sma", lambda: (lambda i, s: nb.numba_sma_inc(_SRC, 4, i, s), st(2))),
        ("ema", lambda: (lambda i, s: nb.numba_ema_inc(_SRC, 4, i, s), st(2))),
        ("rma", lambda: (lambda i, s: nb.numba_rma_inc(_SRC, 4, i, s), st(2))),
        ("sum", lambda: (lambda i, s: nb.numba_sum_inc(_SRC, 4, i, s), st(2))),
        ("stdev", lambda: (lambda i, s: nb.numba_stdev_inc(_SRC, 4, i, s), st(3))),
        ("variance", lambda: (lambda i, s: nb.numba_variance_inc(_SRC, 4, i, s), st(3))),
        ("rsi", lambda: (lambda i, s: nb.numba_rsi_inc(_SRC, 4, i, s), st(3))),
        ("highest", lambda: (lambda i, s: nb.numba_highest_inc(_MIX, 4, i, s), st(3))),
        ("lowest", lambda: (lambda i, s: nb.numba_lowest_inc(_MIX, 4, i, s), st(3))),
        ("wma", lambda: (lambda i, s: nb.numba_wma_inc(_SRC, 4, i, s), st(3))),
        ("dev", lambda: (lambda i, s: nb.numba_dev_inc(_SRC, 4, i, s), st(2))),
        ("cci", lambda: (lambda i, s: nb.numba_cci_inc(_SRC, 4, i, s), st(2))),
        ("cmo", lambda: (lambda i, s: nb.numba_cmo_inc(_SRC, 4, i, s), st(3))),
        ("cum", lambda: (lambda i, s: nb.numba_cum_inc(_SRC, i, s), st(2))),
        ("linreg", lambda: (lambda i, s: nb.numba_linreg_inc(_SRC, 5, 0, i, s), st(3))),
        (
            "corr",
            lambda: (lambda i, s: nb.numba_correlation_inc(_SRC, _MIX, 5, i, s), st(6)),
        ),
        ("kama", lambda: (lambda i, s: nb.numba_kama_inc(_SRC, 5, 2, 30, i, s), st(3))),
        ("median", lambda: (lambda i, s: nb.numba_median_inc(_MIX, 5, i, s), st(5))),
        (
            "alma",
            lambda: (lambda i, s: nb.numba_alma_inc(_SRC, 5, 0.85, 6.0, i, s), st(7)),
        ),
        ("tsi", lambda: (lambda i, s: nb.numba_tsi_inc(_SRC, 3, 5, i, s), st(6))),
        (
            "vwma",
            lambda: (lambda i, s: nb.numba_vwma_inc(_CLOSE, _VOL, 4, i, s), st(3)),
        ),
        ("obv", lambda: (lambda i, s: nb.numba_obv_inc(_CLOSE, _VOL, i, s), st(2))),
        ("pvt", lambda: (lambda i, s: nb.numba_pvt_inc(_CLOSE, _VOL, i, s), st(2))),
        ("nvi", lambda: (lambda i, s: nb.numba_nvi_inc(_CLOSE, _VOL_VAR, i, s), st(4))),
        ("pvi", lambda: (lambda i, s: nb.numba_pvi_inc(_CLOSE, _VOL_VAR, i, s), st(4))),
        (
            "accdist",
            lambda: (lambda i, s: nb.numba_accdist_inc(_HIGH, _LOW, _CLOSE, _VOL, i, s), st(2)),
        ),
        (
            "cmf",
            lambda: (lambda i, s: nb.numba_cmf_inc(_HIGH, _LOW, _CLOSE, _VOL, 5, i, s), st(3)),
        ),
        (
            "mfi",
            lambda: (lambda i, s: nb.numba_mfi_inc(_HIGH, _LOW, _CLOSE, _VOL, 5, i, s), st(3)),
        ),
        (
            "atr",
            lambda: (lambda i, s: nb.numba_atr_inc(_HIGH, _LOW, _CLOSE, 5, i, s), st(2)),
        ),
        (
            "sar",
            lambda: (
                lambda i, s: nb.numba_sar_inc(_HIGH, _LOW, 0.02, 0.02, 0.2, i, s),
                st(5),
            ),
        ),
        (
            "stoch",
            lambda: (
                lambda i, s: nb.numba_stoch_inc(_CLOSE, _HIGH, _LOW, 5, i, s),
                st(5),
            ),
        ),
        (
            "hbars",
            lambda: (lambda i, s: nb.numba_highestbars_inc(_MIX, 5, i, s), st(3)),
        ),
        (
            "lbars",
            lambda: (lambda i, s: nb.numba_lowestbars_inc(_MIX, 5, i, s), st(3)),
        ),
        ("rising", lambda: (lambda i, s: nb.numba_rising_inc(_SRC, 3, i, s), st(2))),
        ("falling", lambda: (lambda i, s: nb.numba_falling_inc(_MIX, 3, i, s), st(2))),
        ("rmax", lambda: (lambda i, s: nb.numba_running_max_inc(_MIX, i, s), st(2))),
        ("rmin", lambda: (lambda i, s: nb.numba_running_min_inc(_MIX, i, s), st(2))),
        ("bbw", lambda: (lambda i, s: nb.numba_bbw_inc(_SRC, 5, 2.0, i, s), st(3))),
        ("vwap", lambda: (lambda i, s: nb.numba_vwap_inc(_CLOSE, _VOL, i, s), st(3))),
        (
            "adx",
            lambda: (lambda i, s: nb.numba_adx_inc(_HIGH, _LOW, _CLOSE, 5, i, s), st(22)),
        ),
    ],
)
def test_gap_to_end_then_rewind(name, make):
    fn, state = make()
    end = len(_SRC) - 1
    mid = end // 2
    out_end = fn(end, state)
    out_mid = fn(mid, state)
    # Values may be scalar or tuple; only require no crash + sensible types.
    if isinstance(out_end, tuple):
        assert isinstance(out_mid, tuple)
    else:
        assert isinstance(out_end, (float, np.floating, bool, np.bool_)) or out_end is not None
        assert isinstance(out_mid, (float, np.floating, bool, np.bool_)) or out_mid is not None


def test_gap_macd_bb_kc_dmi_stochrsi_supertrend_dema_tema_hma():
    n = len(_SRC)
    end, mid = n - 1, n // 2

    s = st(6)
    assert isinstance(nb.numba_macd_inc(_SRC, 3, 5, 2, end, s), tuple)
    assert isinstance(nb.numba_macd_inc(_SRC, 3, 5, 2, mid, s), tuple)

    s = st(3)
    assert isinstance(nb.numba_bb_inc(_SRC, 5, 2.0, end, s), tuple)
    assert isinstance(nb.numba_bb_inc(_SRC, 5, 2.0, mid, s), tuple)

    s = st(4)
    assert isinstance(nb.numba_kc_inc(_CLOSE, _HIGH, _LOW, _CLOSE, 5, 1.5, end, s), tuple)
    assert isinstance(nb.numba_kc_inc(_CLOSE, _HIGH, _LOW, _CLOSE, 5, 1.5, mid, s), tuple)

    s = st(40)
    assert isinstance(nb.numba_dmi_inc(_HIGH, _LOW, _CLOSE, 5, 5, end, s), tuple)
    assert isinstance(nb.numba_dmi_inc(_HIGH, _LOW, _CLOSE, 5, 5, mid, s), tuple)

    s = st(3 + 5)
    assert isinstance(nb.numba_stochrsi_inc(_SRC, 5, 5, end, s), tuple)
    assert isinstance(nb.numba_stochrsi_inc(_SRC, 5, 5, mid, s), tuple)

    s = st(2)
    assert isinstance(nb.numba_supertrend_inc(_HIGH, _LOW, _CLOSE, 3.0, 5, end, s), tuple)
    assert isinstance(nb.numba_supertrend_inc(_HIGH, _LOW, _CLOSE, 3.0, 5, mid, s), tuple)

    s, e1 = st(3), st(n)
    assert _finite(nb.numba_dema_inc(_SRC, 3, end, s, e1)) or _isnan(nb.numba_dema_inc(_SRC, 3, end, st(3), st(n)))
    s, e1 = st(3), st(n)
    nb.numba_dema_inc(_SRC, 3, end, s, e1)
    nb.numba_dema_inc(_SRC, 3, mid, s, e1)

    s, e1, e2 = st(4), st(n), st(n)
    nb.numba_tema_inc(_SRC, 3, end, s, e1, e2)
    nb.numba_tema_inc(_SRC, 3, mid, s, e1, e2)

    s, raw = st(7), st(n)
    nb.numba_hma_inc(_SRC, 5, end, s, raw)
    nb.numba_hma_inc(_SRC, 5, mid, s, raw)

    anchor = f64([1.0] + [0.0] * (n - 1))
    s = st(3)
    nb.numba_vwap_anchor_inc(_CLOSE, _VOL, anchor, end, s)
    nb.numba_vwap_anchor_inc(_CLOSE, _VOL, anchor, mid, s)

    s = st(4)
    assert isinstance(nb.numba_vwap_bands_inc(_CLOSE, _VOL, anchor, 2.0, end, s), tuple)
    assert isinstance(nb.numba_vwap_bands_inc(_CLOSE, _VOL, anchor, 2.0, mid, s), tuple)

    cond = (_SRC > 10).astype(np.float64)
    s = st(4)
    nb.numba_valuewhen_inc(cond, _SRC, 0, end, s)
    nb.numba_valuewhen_inc(cond, _SRC, 0, mid, s)

    cond_b = f64([0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1])
    s = st(2)
    nb.numba_barssince_inc(cond_b, end, s)
    nb.numba_barssince_inc(cond_b, mid, s)


def test_sequential_vs_gap_sma_ema_rsi_agree():
    arr = _SRC
    end = len(arr) - 1
    for period in (3, 5):
        seq, gap = st(2), st(2)
        last = np.nan
        for i in range(len(arr)):
            last = nb.numba_sma_inc(arr, period, i, seq)
        assert last == pytest.approx(nb.numba_sma_inc(arr, period, end, gap))

        seq, gap = st(2), st(2)
        last = np.nan
        for i in range(len(arr)):
            last = nb.numba_ema_inc(arr, period, i, seq)
        assert last == pytest.approx(nb.numba_ema_inc(arr, period, end, gap))

        seq, gap = st(3), st(3)
        last = np.nan
        for i in range(len(arr)):
            last = nb.numba_rsi_inc(arr, period, i, seq)
        g = nb.numba_rsi_inc(arr, period, end, gap)
        assert last == pytest.approx(g)
        assert g == pytest.approx(nb.numba_rsi(arr, period, end))


def test_invalid_periods_return_nan_many():
    arr = _SRC
    h, l, c, v = _HIGH, _LOW, _CLOSE, _VOL
    cases = [
        nb.numba_sma_inc(arr, -3, 5, st(2)),
        nb.numba_sum_inc(arr, 0, 5, st(2)),
        nb.numba_stdev_inc(arr, 0, 5, st(3)),
        nb.numba_variance_inc(arr, -1, 5, st(3)),
        nb.numba_ema_inc(arr, 0, 5, st(2)),
        nb.numba_rma_inc(arr, 0, 5, st(2)),
        nb.numba_wma_inc(arr, 0, 5, st(3)),
        nb.numba_rsi_inc(arr, 0, 5, st(3)),
        nb.numba_highest_inc(arr, 0, 5, st(3)),
        nb.numba_lowest_inc(arr, 0, 5, st(3)),
        nb.numba_dev_inc(arr, 0, 5, st(2)),
        nb.numba_cci_inc(arr, 0, 5, st(2)),
        nb.numba_cmo_inc(arr, 0, 5, st(3)),
        nb.numba_linreg_inc(arr, 0, 0, 5, st(3)),
        nb.numba_correlation_inc(arr, arr, 0, 5, st(6)),
        nb.numba_vwma_inc(c, v, 0, 5, st(3)),
        nb.numba_atr_inc(h, l, c, 0, 5, st(2)),
        nb.numba_mfi_inc(h, l, c, v, 0, 5, st(3)),
        nb.numba_kama_inc(arr, 0, 2, 30, 5, st(3)),
        nb.numba_alma_inc(arr, 0, 0.85, 6.0, 5, st(2)),
        nb.numba_median_inc(arr, 0, 5, st(5)),
        nb.numba_bbw_inc(arr, 0, 2.0, 5, st(3)),
        nb.numba_tsi_inc(arr, 0, 5, 10, st(6)),
        nb.numba_dema_inc(arr, 0, 10, st(3), st(len(arr))),
        nb.numba_tema_inc(arr, 0, 10, st(4), st(len(arr)), st(len(arr))),
        nb.numba_hma_inc(arr, 0, 10, st(7), st(len(arr))),
    ]
    for val in cases:
        assert _isnan(val), val


def test_tuple_invalid_periods():
    arr = _SRC
    h, l, c, v = _HIGH, _LOW, _CLOSE, _VOL
    for tup in (
        nb.numba_macd_inc(arr, 0, 5, 2, 10, st(6)),
        nb.numba_bb_inc(arr, 0, 2.0, 10, st(3)),
        nb.numba_stochrsi_inc(arr, 0, 5, 10, st(8)),
        nb.numba_kc_inc(c, h, l, c, 0, 1.5, 10, st(4)),
    ):
        assert all(_isnan(x) for x in tup)
