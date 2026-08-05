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

"""Runtime helpers star-imported by :class:`CompilerVisitor` prologs.

There is no central dict registry: generated modules do
``from pynescript.compiler.numba_builtins import *``. Names must therefore be
public (no leading underscore) when the emitter references them.

Layers (what this module “registers” for the compile path)
----------------------------------------------------------
1. **njit TA / series kernels** (``@numba.njit(cache=True)``):
   ``numba_sma``, ``numba_ema``, ``numba_rsi``, ``numba_macd``, … plus
   expression helpers ``numba_nz``, ``numba_store``, ``numba_store_src``,
   crossover/math scalars. Signature convention is usually
   ``(series…, params…, bar_index i)``; warm-up bars return ``np.nan``.

2. **Incremental ``*_inc`` kernels** (amortized O(1) per bar):
   ``numba_sma_inc``, ``numba_ema_inc``, ``numba_atr_inc``, … take a small
   float state vector ``st`` allocated by the visitor (``__ema0_st``, …).
   Used when the emitter can prove fixed-size TA state.

3. **Object-mode coercion / safety** (pure Python, never under njit):
   ``safe_float``, ``safe_int``, ``safe_period``, ``safe_len``, ``safe_iter``,
   ``safe_sum`` / ``safe_max`` / ``safe_min``, ``na_num`` (None→nan for
   arithmetic), ``nz_py`` (unicode-safe nz), ``store_src_py``, ``udt_index``,
   ``pine_raise``, list/matrix mutators (``safe_list_*``, ``matrix_*``),
   array stats (``array_mode``, ``array_range``, …).

Numba constraints
-----------------
- nopython kernels use only float64 series + scalars; no dicts/lists/str.
- Object mode reuses the same import * and may call both njit and Python
  helpers (Numba dispatches Python callables when not nested inside njit).
- Prefer matching interpret-path seeding (EMA/ATR notes on individual kernels).

Matrix / na
-----------
Matrices are list-of-lists handles. ``na_num`` / ``safe_float`` map Pine
``na``/handles to float NaN so bar-loop arithmetic and plot stores never raise.
"""

from __future__ import annotations

import numpy as np
import numba


@numba.njit(cache=True)
def numba_sma(arr, period, i):
    """Simple moving average of last ``period`` bars ending at ``i``; else na."""
    period = int(period)
    if period <= 0 or i < period - 1:
        return np.nan
    sum_val = 0.0
    for j in range(period):
        val = arr[i - j]
        if np.isnan(val):
            return np.nan
        sum_val += val
    return sum_val / period


@numba.njit(cache=True)
def numba_ema(arr, period, i):
    """EMA with SMA seed, then recursive to ``i``.

    Seeds on the earliest window of ``period`` consecutive non-NaN samples
    ending at index ``s`` where ``period-1 <= s <= i``. Leading NaNs (e.g.
    nested EMA of a warm-up series, TR with bar-0 na) no longer poison the
    seed forever. Once seeded, NaN inputs propagate NaN through the recursion.

    Dual-host note: Runtime bar-mode interpret uses ``_ema_inc_update`` with the
    same SMA seed (na until ``period`` samples). Full-list ``_ema`` still seeds
    with the first valid sample for non-incremental callers; prefer the SMA-seed
    path when comparing interpret vs compile plots.
    """
    period = int(period)
    if period <= 0 or i < period - 1:
        return np.nan
    alpha = 2.0 / (period + 1.0)
    seed_end = -1
    ema = np.nan
    for s in range(period - 1, i + 1):
        sum_val = 0.0
        ok = True
        start = s - period + 1
        for k in range(period):
            v = arr[start + k]
            if np.isnan(v):
                ok = False
                break
            sum_val += v
        if ok:
            seed_end = s
            ema = sum_val / period
            break
    if seed_end < 0:
        return np.nan
    for j in range(seed_end + 1, i + 1):
        ema = alpha * arr[j] + (1.0 - alpha) * ema
    return ema


@numba.njit(cache=True)
def numba_rma(arr, period, i):
    """Wilder RMA: SMA seed on first all-finite window, then recursive.

    Same NaN-window-safe seed as ``numba_ema`` (leading NaNs shift the seed).
    Required for expanded ADX/DMI scripts (``ta.rma(plusDM)`` / ``ta.rma(ta.tr)``)
    where bar-0 is na — the old seed at ``period-1`` summed NaN forever and
    left compile ADX stuck at ~0 after warmup.
    After seed, NaN inputs hold the previous RMA (interpret ``_rma`` parity).
    """
    period = int(period)
    if period <= 0 or i < period - 1:
        return np.nan
    alpha = 1.0 / period
    seed_end = -1
    rma = np.nan
    for s in range(period - 1, i + 1):
        ssum = 0.0
        ok = True
        start = s - period + 1
        for k in range(period):
            v = arr[start + k]
            if np.isnan(v):
                ok = False
                break
            ssum += v
        if ok:
            seed_end = s
            rma = ssum / period
            break
    if seed_end < 0:
        return np.nan
    for j in range(seed_end + 1, i + 1):
        v = arr[j]
        if not np.isnan(v):
            rma = alpha * v + (1.0 - alpha) * rma
    return rma


@numba.njit(cache=True)
def numba_rsi(arr, period, i):
    """Wilder RSI: SMA seed of first ``period`` deltas, then RMA of gain/loss.

    Matches interpret ``_rsi`` / ``_rsi_inc_update`` and TradingView ``ta.rsi``.
    First valid bar is ``i == period`` (``period`` deltas need ``period+1`` prices).
    """
    period = int(period)
    if period <= 0 or i < period:
        return np.nan
    # Seed: simple average of first ``period`` deltas (bars 1..period)
    avg_gain = 0.0
    avg_loss = 0.0
    for j in range(1, period + 1):
        delta = arr[j] - arr[j - 1]
        if delta >= 0.0:
            avg_gain += delta
        else:
            avg_loss -= delta
    avg_gain /= period
    avg_loss /= period
    alpha = 1.0 / period
    for j in range(period + 1, i + 1):
        delta = arr[j] - arr[j - 1]
        gain = delta if delta >= 0.0 else 0.0
        loss = -delta if delta < 0.0 else 0.0
        avg_gain = alpha * gain + (1.0 - alpha) * avg_gain
        avg_loss = alpha * loss + (1.0 - alpha) * avg_loss
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@numba.njit(cache=True)
def numba_highest(arr, period, i):
    """Highest over the last ``period`` bars ending at ``i``.

    Matches interpret ``_highest`` / ``_highest_inc_update``: requires a full
    window (``i >= period - 1``); partial history returns NaN. NaN samples in
    the window are skipped (max of finite values; all-NaN → NaN).
    """
    period = int(period)
    if period <= 0 or i < 0 or i < period - 1:
        return np.nan
    start = i - period + 1
    m = np.nan
    for j in range(start, i + 1):
        v = arr[j]
        if np.isnan(v):
            continue
        if np.isnan(m) or v > m:
            m = v
    return m


@numba.njit(cache=True)
def numba_lowest(arr, period, i):
    """Lowest over the last ``period`` bars ending at ``i``.

    Matches interpret ``_lowest`` / ``_lowest_inc_update``: full window required
    (``i >= period - 1``); partial history → NaN. NaN samples skipped.
    """
    period = int(period)
    if period <= 0 or i < 0 or i < period - 1:
        return np.nan
    start = i - period + 1
    m = np.nan
    for j in range(start, i + 1):
        v = arr[j]
        if np.isnan(v):
            continue
        if np.isnan(m) or v < m:
            m = v
    return m


@numba.njit(cache=True)
def numba_stdev(arr, period, i):
    """Sample standard deviation (n-1) over last ``period`` bars ending at ``i``."""
    period = int(period)
    if period <= 1 or i < period - 1:
        return np.nan
    mean = 0.0
    for j in range(period):
        mean += arr[i - j]
    mean /= period
    var = 0.0
    for j in range(period):
        d = arr[i - j] - mean
        var += d * d
    var /= period - 1
    return np.sqrt(var)


@numba.njit(cache=True)
def numba_atr(high, low, close, period, i):
    """ATR matching interpret path: mean(TR) while warming; else EMA-of-TR.

    EMA seeds with the first TR value (same as interpret ``_ema``), not SMA.
    """
    period = int(period)
    if period <= 0 or i < 1:
        return np.nan
    n_tr = i  # TR samples for bars 1..i
    if n_tr < period:
        s = 0.0
        for j in range(1, i + 1):
            tr = max(
                high[j] - low[j],
                abs(high[j] - close[j - 1]),
                abs(low[j] - close[j - 1]),
            )
            s += tr
        return s / n_tr
    # EMA of TR from bar 1..i, seed = first TR
    tr0 = max(high[1] - low[1], abs(high[1] - close[0]), abs(low[1] - close[0]))
    ema = tr0
    alpha = 2.0 / (period + 1.0)
    for j in range(2, i + 1):
        tr = max(
            high[j] - low[j],
            abs(high[j] - close[j - 1]),
            abs(low[j] - close[j - 1]),
        )
        ema = alpha * tr + (1.0 - alpha) * ema
    return ema


@numba.njit(cache=True)
def numba_change(arr, length, i):
    length = int(length)
    if length <= 0 or i < length:
        return np.nan
    return arr[i] - arr[i - length]


@numba.njit(cache=True)
def numba_pvt_inc(close, vol, i, st):
    """Price Volume Trend (incremental): cum((c-c1)/c1 * volume).

    ``st[0]`` holds previous PVT, ``st[1]`` previous bar index for catch-up.
    """
    if i <= 0:
        st[0] = 0.0
        st[1] = float(i)
        return 0.0
    prev_i = int(st[1]) if not np.isnan(st[1]) else -1
    if prev_i == i:
        return st[0]
    if prev_i != i - 1:
        pvt = 0.0
        for j in range(1, i + 1):
            c0 = close[j - 1]
            if c0 == 0.0 or np.isnan(c0) or np.isnan(close[j]) or np.isnan(vol[j]):
                continue
            pvt = pvt + ((close[j] - c0) / c0) * vol[j]
        st[0] = pvt
        st[1] = float(i)
        return pvt
    c0 = close[i - 1]
    if c0 == 0.0 or np.isnan(c0) or np.isnan(close[i]) or np.isnan(vol[i]):
        st[1] = float(i)
        return st[0]
    pvt = st[0] + ((close[i] - c0) / c0) * vol[i]
    st[0] = pvt
    st[1] = float(i)
    return pvt


def safe_tonumber(x):
    """Parse Pine str.tonumber — non-numeric / empty → NaN."""
    try:
        if x is None:
            return np.nan
        s = str(x).strip()
        if s == "" or s.lower() in ("nan", "none", "na"):
            return np.nan
        return float(s)
    except (TypeError, ValueError):
        return np.nan


@numba.njit(cache=True)
def numba_bb(arr, period, mult, i):
    """Return (upper, middle, lower) Bollinger bands."""
    period = int(period)
    mid = numba_sma(arr, period, i)
    sd = numba_stdev(arr, period, i)
    if np.isnan(mid) or np.isnan(sd):
        return np.nan, np.nan, np.nan
    return mid + mult * sd, mid, mid - mult * sd


@numba.njit(cache=True)
def numba_macd(arr, fast, slow, signal, i):
    """Return (macd, signal, hist) at bar ``i`` in a single O(i) pass.

    Fast/slow EMAs use SMA seed (same as ``numba_ema``). Signal uses
    first-value seed on the MACD line. Must not nest per-bar EMA rebuilds
    (that was O(n³) and hung multi-thousand-bar compiles).
    """
    fast = int(fast)
    slow = int(slow)
    signal = int(signal)
    if fast <= 0 or slow <= 0 or signal <= 0 or i < slow - 1:
        return np.nan, np.nan, np.nan

    alpha_f = 2.0 / (fast + 1.0)
    alpha_s = 2.0 / (slow + 1.0)
    alpha_sig = 2.0 / (signal + 1.0)

    sum_f = 0.0
    for j in range(fast):
        sum_f += arr[j]
    ema_f = sum_f / fast

    sum_s = 0.0
    for j in range(slow):
        sum_s += arr[j]
    ema_s = sum_s / slow

    # Advance fast EMA from index ``fast`` through ``slow-1`` so both sit at slow-1
    for j in range(fast, slow):
        ema_f = alpha_f * arr[j] + (1.0 - alpha_f) * ema_f

    macd_val = ema_f - ema_s
    sig = macd_val  # first-value seed at first valid MACD bar

    for j in range(slow, i + 1):
        ema_f = alpha_f * arr[j] + (1.0 - alpha_f) * ema_f
        ema_s = alpha_s * arr[j] + (1.0 - alpha_s) * ema_s
        macd_val = ema_f - ema_s
        sig = alpha_sig * macd_val + (1.0 - alpha_sig) * sig

    return macd_val, sig, macd_val - sig


@numba.njit(cache=True)
def numba_nz(val, replacement):
    """nopython ``nz`` / ``fixnan``: replace float NaN only (not unicode-safe)."""
    if np.isnan(val):
        return replacement
    return val


@numba.njit(cache=True)
def numba_safe_div(a, b):
    """Pine division: zero / non-finite divisor → na. Single-eval of both args."""
    if b == 0.0 or np.isnan(b):
        return np.nan
    return a / b


@numba.njit(cache=True)
def numba_safe_mod(a, b):
    """Pine modulo: zero / non-finite divisor → na. Single-eval of both args."""
    if b == 0.0 or np.isnan(b):
        return np.nan
    return np.fmod(a, b)


@numba.njit(cache=True)
def numba_accdist_inc(high, low, close, vol, i, st):
    """Cumulative Chaikin Accumulation/Distribution. ``st``: [sum, last_i].

    Matches interpret ``_accdist`` / TV ``ta.accdist``: CLV * volume accumulated.
    """
    if i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = 0.0
    s = 0.0 if np.isnan(st[0]) or last < 0 else st[0]
    for j in range(last + 1, i + 1):
        h = high[j]
        l_ = low[j]
        c = close[j]
        v = vol[j]
        if np.isnan(h) or np.isnan(l_) or np.isnan(c):
            continue
        vv = 0.0 if np.isnan(v) else v
        rng = h - l_
        if rng == 0.0:
            clv = 0.0
        else:
            clv = ((c - l_) - (h - c)) / rng
        s += clv * vv
    st[0] = s
    st[1] = float(i)
    return s


def nz_py(val, replacement=0.0):
    """Object-mode ``nz`` / ``fixnan`` stub — never calls ``isnan`` on unicode.

    Used when the compiler has already forced object mode or the value may be
    a color/string/UDT handle. Numba's ``numba_nz`` rejects ``unicode_type``.
    """
    if val is None:
        return replacement
    # Fast path: Python float NaN
    if isinstance(val, float) and val != val:
        return replacement
    # Strings, colors, dicts, lists — pass through (never isnan)
    if isinstance(val, (str, bytes, dict, list, tuple, set)):
        return val
    try:
        if isinstance(val, (int, np.integer, bool, np.bool_)):
            return val
        if isinstance(val, (np.floating,)):
            f = float(val)
            if f != f:
                return replacement
            return f
        # Avoid np.isnan on object/unicode (raises / TypingError under njit paths)
        if isinstance(val, (np.ndarray,)) and getattr(val, "dtype", None) is not None:
            return replacement if val.size == 0 else nz_py(val.reshape(-1)[0], replacement)
    except Exception:
        return replacement
    return val

@numba.njit(cache=True)
def numba_store(arr, i, value):
    """Write ``value`` into ``arr[i]`` and return it.

    Expression-safe substitute for ``arr[i] = value`` so ``plot()`` can appear
    inside dict/call arguments (e.g. ``fill(plot(a), plot(b))``).
    """
    arr[i] = value
    return value


@numba.njit(cache=True)
def numba_store_src(dst, val, i):
    """Write scalar ``val`` into ``dst[i]`` and return ``dst`` for TA consumers.

    Materializes expression sources (e.g. ``math.abs(mom)``, ``close * 2``)
    into a synthetic series so ``numba_ema`` / ``numba_sma`` can index history.
    Uses ``val + 0.0`` so bool/int promote under nopython.
    """
    v = val + 0.0
    if v != v:  # NaN
        dst[i] = np.nan
    else:
        dst[i] = v
    return dst


@numba.njit(cache=True)
def numba_abs(val):
    if val < 0.0:
        return -val
    return val


@numba.njit(cache=True)
def numba_max(a, b):
    if a > b:
        return a
    return b


@numba.njit(cache=True)
def numba_min(a, b):
    if a < b:
        return a
    return b


@numba.njit(cache=True)
def numba_crossover(a, b, i):
    """True when series ``a`` crosses over series ``b`` on bar ``i``."""
    if i < 1:
        return False
    return a[i] > b[i] and a[i - 1] <= b[i - 1]


@numba.njit(cache=True)
def numba_crossunder(a, b, i):
    """True when series ``a`` crosses under series ``b`` on bar ``i``."""
    if i < 1:
        return False
    return a[i] < b[i] and a[i - 1] >= b[i - 1]


@numba.njit(cache=True)
def numba_crossover_scalar(a, level, i):
    """True when series ``a`` crosses over constant ``level``."""
    if i < 1:
        return False
    return a[i] > level and a[i - 1] <= level


@numba.njit(cache=True)
def numba_crossunder_scalar(a, level, i):
    """True when series ``a`` crosses under constant ``level``."""
    if i < 1:
        return False
    return a[i] < level and a[i - 1] >= level


@numba.njit(cache=True)
def numba_tr(high, low, close, i):
    """True range at bar ``i`` (NaN on first bar)."""
    if i < 1:
        return np.nan
    return max(
        high[i] - low[i],
        abs(high[i] - close[i - 1]),
        abs(low[i] - close[i - 1]),
    )


@numba.njit(cache=True)
def numba_cum(arr, i):
    """Running sum of ``arr[0..i]`` (NaNs treated as 0)."""
    s = 0.0
    for j in range(i + 1):
        v = arr[j]
        if not np.isnan(v):
            s += v
    return s


@numba.njit(cache=True)
def numba_cum_expr(state_arr, val, i):
    """Running sum of a per-bar scalar expression (NaNs treated as 0).

    Used when ``cum(expr)`` cannot pass a pure series array (e.g. ternaries).
    ``state_arr`` is a synthetic series allocated by the compiler; this bar's
    value is written then returned so the assign target gets the cumulative.
    """
    v = 0.0 if np.isnan(val) else val
    if i <= 0:
        state_arr[0] = v
        return v
    prev = state_arr[i - 1]
    if np.isnan(prev):
        prev = 0.0
    s = prev + v
    state_arr[i] = s
    return s


@numba.njit(cache=True)
def numba_valuewhen(cond_arr, src_arr, occ, i):
    occ = int(occ)
    """Return source at the ``occ``-th most recent true condition (0 = latest)."""
    if occ < 0:
        return np.nan
    left = occ
    for j in range(i, -1, -1):
        c = cond_arr[j]
        if np.isnan(c) or c == 0.0:
            continue
        if left == 0:
            return src_arr[j]
        left -= 1
    return np.nan


@numba.njit(cache=True)
def numba_pivothigh(arr, left, right, i):
    left = int(left)
    right = int(right)
    """Pivot high confirmed at bar ``i`` (center = i - right)."""
    if left < 0 or right < 0:
        return np.nan
    c = i - right
    if c < left or i < left + right:
        return np.nan
    val = arr[c]
    if np.isnan(val):
        return np.nan
    for j in range(c - left, c + right + 1):
        if j == c:
            continue
        if arr[j] >= val:
            return np.nan
    return val


@numba.njit(cache=True)
def numba_pivotlow(arr, left, right, i):
    left = int(left)
    right = int(right)
    """Pivot low confirmed at bar ``i`` (center = i - right)."""
    if left < 0 or right < 0:
        return np.nan
    c = i - right
    if c < left or i < left + right:
        return np.nan
    val = arr[c]
    if np.isnan(val):
        return np.nan
    for j in range(c - left, c + right + 1):
        if j == c:
            continue
        if arr[j] <= val:
            return np.nan
    return val


@numba.njit(cache=True)
def numba_stoch(source, high, low, length, i):
    length = int(length)
    """Stochastic %K: (src - lowest(low)) / (highest(high) - lowest(low)) * 100."""
    if length <= 0 or i < length - 1:
        return np.nan
    hh = high[i]
    ll = low[i]
    for j in range(1, length):
        h = high[i - j]
        l = low[i - j]
        if h > hh or np.isnan(hh):
            hh = h
        if l < ll or np.isnan(ll):
            ll = l
    if np.isnan(hh) or np.isnan(ll) or np.isnan(source[i]):
        return np.nan
    if hh == ll:
        return 50.0
    return 100.0 * (source[i] - ll) / (hh - ll)


@numba.njit(cache=True)
def numba_cci(arr, length, i):
    length = int(length)
    """CCI on a single source series (typical price or explicit source)."""
    if length <= 0 or i < length - 1:
        return np.nan
    mean = 0.0
    for j in range(length):
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        mean += v
    mean /= length
    md = 0.0
    for j in range(length):
        md += abs(arr[i - j] - mean)
    md /= length
    if md == 0.0:
        return 0.0
    return (arr[i] - mean) / (0.015 * md)


@numba.njit(cache=True)
def numba_vwap(src, vol, i):
    """Cumulative VWAP: sum(src*vol) / sum(vol) from bar 0..i."""
    cum_pv = 0.0
    cum_v = 0.0
    for j in range(i + 1):
        p = src[j]
        v = vol[j]
        if np.isnan(p) or np.isnan(v):
            continue
        cum_pv += p * v
        cum_v += v
    if cum_v == 0.0:
        return np.nan
    return cum_pv / cum_v


@numba.njit(cache=True)
def numba_sar(high, low, start, increment, maximum, i):
    """Simple Parabolic SAR rebuilt from bar 0..i (O(i))."""
    if i < 0 or len(high) == 0:
        return np.nan
    n = i + 1
    if n < 1:
        return np.nan
    # Seed: long trend, SAR = first low, EP = first high
    sar = low[0]
    ep = high[0]
    af = start
    trend = 1  # 1 = long, -1 = short
    if n == 1:
        return sar
    for idx in range(1, n):
        hi = high[idx]
        lo = low[idx]
        prev = sar
        if trend == 1:
            sar = prev + af * (ep - prev)
            if hi > ep:
                ep = hi
                af = af + increment
                if af > maximum:
                    af = maximum
            if sar > lo:
                trend = -1
                sar = ep
                ep = lo
                af = start
        else:
            sar = prev - af * (prev - ep)
            if lo < ep:
                ep = lo
                af = af + increment
                if af > maximum:
                    af = maximum
            if sar < hi:
                trend = 1
                sar = ep
                ep = hi
                af = start
    return sar


@numba.njit(cache=True)
def numba_percentile_nearest_rank(arr, length, percentage, i):
    length = int(length)
    """Nearest-rank percentile over last ``length`` bars ending at ``i``."""
    if length <= 0 or i < length - 1:
        return np.nan
    # Copy window and insertion-sort (numba-friendly)
    window = np.empty(length, dtype=np.float64)
    count = 0
    for j in range(length):
        v = arr[i - j]
        if not np.isnan(v):
            window[count] = v
            count += 1
    if count == 0:
        return np.nan
    # insertion sort first count elements
    for a in range(1, count):
        key = window[a]
        b = a - 1
        while b >= 0 and window[b] > key:
            window[b + 1] = window[b]
            b -= 1
        window[b + 1] = key
    # Nearest rank: ceil(p/100 * n), 1-indexed
    rank = int((percentage / 100.0) * count + 0.999999)
    if rank < 1:
        rank = 1
    if rank > count:
        rank = count
    return window[rank - 1]


@numba.njit(cache=True)
def numba_barssince(cond_arr, i):
    """Bars since ``cond_arr`` was last true (non-zero / non-nan)."""
    for j in range(i, -1, -1):
        c = cond_arr[j]
        if np.isnan(c) or c == 0.0:
            continue
        return float(i - j)
    return np.nan


@numba.njit(cache=True)
def numba_linreg(arr, length, offset, i):
    length = int(length)
    offset = int(offset)
    """Least-squares linear regression of ``arr`` over ``length``, value at offset.

    x runs 0..length-1 (oldest->newest). Result is the fitted value at
    ``x = length - 1 - offset`` (offset=0 -> current bar on the regression line).
    """
    if length < 2 or i < length - 1:
        return np.nan
    n = float(length)
    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_xx = 0.0
    for j in range(length):
        x = float(j)
        y = arr[i - length + 1 + j]
        if np.isnan(y):
            return np.nan
        sum_x += x
        sum_y += y
        sum_xy += x * y
        sum_xx += x * x
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0.0:
        return sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return intercept + slope * (n - 1.0 - float(offset))


@numba.njit(cache=True)
def numba_vwma(src, vol, length, i):
    length = int(length)
    """Volume-weighted MA: sum(src*vol) / sum(vol) over last ``length`` bars."""
    if length <= 0 or i < length - 1:
        return np.nan
    sum_pv = 0.0
    sum_v = 0.0
    for j in range(length):
        p = src[i - j]
        v = vol[i - j]
        if np.isnan(p) or np.isnan(v):
            return np.nan
        sum_pv += p * v
        sum_v += v
    if sum_v == 0.0:
        return np.nan
    return sum_pv / sum_v


@numba.njit(cache=True)
def numba_mfi(high, low, close, vol, length, i):
    length = int(length)
    """Money Flow Index over ``length`` money-flow samples ending at ``i``.

    Needs ``length + 1`` typical-price samples (direction vs previous bar).
    """
    if length <= 0 or i < length:
        return np.nan
    pos = 0.0
    neg = 0.0
    for j in range(length):
        k = i - j
        tp = (high[k] + low[k] + close[k]) / 3.0
        tp_prev = (high[k - 1] + low[k - 1] + close[k - 1]) / 3.0
        if np.isnan(tp) or np.isnan(tp_prev) or np.isnan(vol[k]):
            return np.nan
        mf = tp * vol[k]
        if tp > tp_prev:
            pos += mf
        elif tp < tp_prev:
            neg += mf
        # tp == tp_prev -> neither (TV convention)
    if neg == 0.0:
        if pos == 0.0:
            return 50.0
        return 100.0
    ratio = pos / neg
    return 100.0 - (100.0 / (1.0 + ratio))


@numba.njit(cache=True)
def numba_rci(arr, length, i):
    """Rank Correlation Index (Spearman rho of time vs value ranks).

    Matches interpret ``ta.rci``: window oldest→newest, time ranks 0..n-1,
    value ranks via stable ascending sort (ties keep earlier index lower rank).
    Returns rho in ``[-1, 1]`` (not *100).
    """
    length = int(length)
    if length < 2 or i < length - 1:
        return np.nan
    n = length
    base = i - length + 1
    d2 = 0.0
    for a in range(n):
        va = arr[base + a]
        if np.isnan(va):
            return np.nan
        rank = 0
        for b in range(n):
            vb = arr[base + b]
            if np.isnan(vb):
                return np.nan
            # Stable order: lower value first; equal values keep lower index first
            if vb < va or (vb == va and b < a):
                rank += 1
        d = float(a - rank)
        d2 += d * d
    denom = float(n) * (float(n) * float(n) - 1.0)
    if denom == 0.0:
        return np.nan
    return 1.0 - (6.0 * d2) / denom


@numba.njit(cache=True)
def numba_rising(arr, length, i):
    length = int(length)
    """True if ``arr`` rose strictly for ``length`` consecutive bars."""
    if length <= 0 or i < length:
        return False
    for j in range(length):
        a = arr[i - j]
        b = arr[i - j - 1]
        if np.isnan(a) or np.isnan(b) or a <= b:
            return False
    return True


@numba.njit(cache=True)
def numba_falling(arr, length, i):
    length = int(length)
    """True if ``arr`` fell strictly for ``length`` consecutive bars."""
    if length <= 0 or i < length:
        return False
    for j in range(length):
        a = arr[i - j]
        b = arr[i - j - 1]
        if np.isnan(a) or np.isnan(b) or a >= b:
            return False
    return True


@numba.njit(cache=True)
def numba_highestbars(arr, length, i):
    """Offset to highest value in window (TradingView / interpret parity).

    Returns ``0`` if the current bar is highest, ``-1`` if one bar ago, …,
    down to ``-(length-1)``.  Short history (``i+1 < length``), invalid
    length, or all-NaN window → ``-1.0`` (same sentinel as interpret).

    On ties prefers the **oldest** extreme in the window (leftmost; matches
    interpret ``_highestbars``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return -1.0
    if i + 1 < length:
        return -1.0
    start = i - length + 1
    best = np.nan
    best_idx = -1
    for k in range(start, i + 1):
        v = arr[k]
        if np.isnan(v):
            continue
        # strict > → first (oldest) wins ties
        if np.isnan(best) or v > best:
            best = v
            best_idx = k
    if best_idx < 0:
        return -1.0
    return float(-(i - best_idx))


@numba.njit(cache=True)
def numba_lowestbars(arr, length, i):
    """Offset to lowest value in window (TradingView / interpret parity).

    Same contract as :func:`numba_highestbars`: negative bars-back offset,
    ``-1.0`` when short / invalid / all-NaN; oldest extreme on ties.
    """
    length = int(length)
    if length <= 0 or i < 0:
        return -1.0
    if i + 1 < length:
        return -1.0
    start = i - length + 1
    best = np.nan
    best_idx = -1
    for k in range(start, i + 1):
        v = arr[k]
        if np.isnan(v):
            continue
        if np.isnan(best) or v < best:
            best = v
            best_idx = k
    if best_idx < 0:
        return -1.0
    return float(-(i - best_idx))

@numba.njit(cache=True)
def numba_percentrank(arr, length, i):
    """Percentrank matching interpret ``_percentrank`` (strict ``<`` / valid-only).

    Window is the last ``length`` bars ending at ``i``. Among non-nan samples,
    returns ``100 * count(v < arr[i]) / n_valid``. Fewer than 2 valid samples
    → 50.0 (same as interpret). Warm-up / current nan → nan.
    """
    length = int(length)
    if length <= 0 or i < length - 1:
        return np.nan
    v = arr[i]
    if np.isnan(v):
        return np.nan
    n_valid = 0
    n_below = 0
    for j in range(length):
        x = arr[i - j]
        if np.isnan(x):
            continue
        n_valid += 1
        if x < v:
            n_below += 1
    if n_valid < 2:
        return 50.0
    return 100.0 * n_below / n_valid


@numba.njit(cache=True)
def numba_obv(close, vol, i):
    """On-Balance Volume rebuilt as a running sum from bar 0..i."""
    if i < 0:
        return np.nan
    obv = 0.0
    for j in range(1, i + 1):
        if close[j] > close[j - 1]:
            obv += vol[j]
        elif close[j] < close[j - 1]:
            obv -= vol[j]
    return obv


@numba.njit(cache=True)
def numba_wma(arr, length, i):
    length = int(length)
    """Linear weighted MA: newest bar weight = length, oldest weight = 1."""
    if length <= 0 or i < length - 1:
        return np.nan
    weighted = 0.0
    total_w = 0.0
    for j in range(length):
        w = float(length - j)
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        weighted += v * w
        total_w += w
    if total_w == 0.0:
        return np.nan
    return weighted / total_w


@numba.njit(cache=True)
def numba_roc(arr, length, i):
    length = int(length)
    """Rate of Change: 100 * (arr[i] - arr[i-length]) / arr[i-length]."""
    if length <= 0 or i < length:
        return np.nan
    baseline = arr[i - length]
    if np.isnan(baseline) or baseline == 0.0 or np.isnan(arr[i]):
        return np.nan
    return 100.0 * (arr[i] - baseline) / baseline


@numba.njit(cache=True)
def numba_sum(arr, period, i):
    period = int(period)
    """Rolling sum of last ``period`` bars ending at ``i``."""
    if period <= 0 or i < period - 1:
        return np.nan
    s = 0.0
    for j in range(period):
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        s += v
    return s


@numba.njit(cache=True)
def numba_variance(arr, period, i):
    period = int(period)
    """Sample variance (n-1) over last ``period`` bars — ``stdev**2``."""
    if period <= 1 or i < period - 1:
        return np.nan
    mean = 0.0
    for j in range(period):
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        mean += v
    mean /= period
    var = 0.0
    for j in range(period):
        d = arr[i - j] - mean
        var += d * d
    return var / (period - 1)


@numba.njit(cache=True)
def numba_dev(arr, period, i):
    period = int(period)
    """Mean absolute deviation from SMA over last ``period`` bars."""
    if period <= 0 or i < period - 1:
        return np.nan
    mean = 0.0
    for j in range(period):
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        mean += v
    mean /= period
    md = 0.0
    for j in range(period):
        md += abs(arr[i - j] - mean)
    return md / period


@numba.njit(cache=True)
def numba_correlation(a, b, period, i):
    period = int(period)
    """Pearson correlation of series ``a`` and ``b`` over last ``period`` bars."""
    if period < 2 or i < period - 1:
        return np.nan
    mean_a = 0.0
    mean_b = 0.0
    for j in range(period):
        va = a[i - j]
        vb = b[i - j]
        if np.isnan(va) or np.isnan(vb):
            return np.nan
        mean_a += va
        mean_b += vb
    mean_a /= period
    mean_b /= period
    num = 0.0
    den_a = 0.0
    den_b = 0.0
    for j in range(period):
        da = a[i - j] - mean_a
        db = b[i - j] - mean_b
        num += da * db
        den_a += da * da
        den_b += db * db
    if den_a == 0.0 or den_b == 0.0:
        return np.nan
    return num / np.sqrt(den_a * den_b)


@numba.njit(cache=True)
def numba_alma(arr, length, offset, sigma, i):
    length = int(length)
    """Arnaud Legoux Moving Average over last ``length`` bars ending at ``i``.

    Weights: Gaussian centered at ``m = offset * (length - 1)`` with
    ``s = length / sigma`` (TV defaults offset=0.85, sigma=6).
    Index 0 in the weight loop is the oldest bar in the window.
    """
    if length <= 0 or i < length - 1:
        return np.nan
    if sigma == 0.0:
        return np.nan
    m = offset * (length - 1)
    s = length / sigma
    s2 = 2.0 * s * s
    wsum = 0.0
    total = 0.0
    for k in range(length):
        # k=0 oldest … k=length-1 newest
        v = arr[i - length + 1 + k]
        if np.isnan(v):
            return np.nan
        d = float(k) - m
        w = np.exp(-(d * d) / s2)
        total += v * w
        wsum += w
    if wsum == 0.0:
        return np.nan
    return total / wsum


@numba.njit(cache=True)
def _numba_wma_at(arr, end_idx, period):
    """WMA ending at ``end_idx`` with length ``period`` (newest weight = period)."""
    period = int(period)
    if period <= 0 or end_idx < period - 1:
        return np.nan
    weighted = 0.0
    total_w = 0.0
    for j in range(period):
        w = float(period - j)
        v = arr[end_idx - j]
        if np.isnan(v):
            return np.nan
        weighted += v * w
        total_w += w
    if total_w == 0.0:
        return np.nan
    return weighted / total_w


@numba.njit(cache=True)
def numba_hma(arr, length, i):
    length = int(length)
    """Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n)) at bar ``i``."""
    if length <= 0 or i < length - 1:
        return np.nan
    half = length // 2
    if half < 1:
        half = 1
    sqrt_n = int(np.sqrt(float(length)))
    if sqrt_n < 1:
        sqrt_n = 1
    # Full WMA needs ``length`` bars at each of last sqrt_n ends
    if i < length + sqrt_n - 2:
        return np.nan

    diffs = np.empty(sqrt_n, dtype=np.float64)
    for t in range(sqrt_n):
        end = i - t
        wh = _numba_wma_at(arr, end, half)
        wf = _numba_wma_at(arr, end, length)
        if np.isnan(wh) or np.isnan(wf):
            return np.nan
        diffs[t] = 2.0 * wh - wf
    weighted = 0.0
    total_w = 0.0
    for j in range(sqrt_n):
        w = float(sqrt_n - j)
        weighted += diffs[j] * w
        total_w += w
    if total_w == 0.0:
        return np.nan
    return weighted / total_w


@numba.njit(cache=True)
def _wma_window_sums(arr, end_idx, period):
    """Return (sum, weighted_sum) for WMA window ending at ``end_idx``, or (nan,nan)."""
    period = int(period)
    s = 0.0
    ws = 0.0
    start = end_idx - period + 1
    for k in range(period):
        v = arr[start + k]
        if np.isnan(v):
            return np.nan, np.nan
        s += v
        ws += v * (k + 1)
    return s, ws


@numba.njit(cache=True)
def numba_hma_inc(arr, length, i, st, raw):
    """Amortized-O(1) HMA via multi-stage incremental WMA.

    ``st``: [half_s, half_ws, full_s, full_ws, outer_s, outer_ws, last_i]
    ``raw``: intermediate series buffer (same length as ``arr``); filled with
    ``2*WMA(half) - WMA(full)`` for each bar as we advance.

    Half/full/outer sliding sums reseed from the window every ``length`` bars to
    bound float drift (parity vs ``numba_hma`` ≤ 1e-10). Catch-up / rewind safe.
    """
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    half = length // 2
    if half < 1:
        half = 1
    sqrt_n = int(np.sqrt(float(length)))
    if sqrt_n < 1:
        sqrt_n = 1
    half_tw = half * (half + 1) / 2.0
    full_tw = length * (length + 1) / 2.0
    outer_tw = sqrt_n * (sqrt_n + 1) / 2.0
    need = length + sqrt_n - 2
    # Reseed cadence: at least every `length` bars (amortized O(1))
    reseed_every = length if length > 0 else 1

    if np.isnan(st[6]):
        last = -1
    else:
        last = int(st[6])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan
        st[3] = np.nan
        st[4] = np.nan
        st[5] = np.nan

    hs = st[0]
    hws = st[1]
    fs = st[2]
    fws = st[3]
    os_ = st[4]
    ows = st[5]

    for j in range(last + 1, i + 1):
        # --- half WMA ---
        if j < half - 1:
            hs = np.nan
            hws = np.nan
        elif j == half - 1 or np.isnan(hs) or (j % reseed_every == 0):
            hs, hws = _wma_window_sums(arr, j, half)
        else:
            old = arr[j - half]
            new = arr[j]
            if np.isnan(old) or np.isnan(new):
                hs = np.nan
                hws = np.nan
            else:
                hws = hws - hs + new * half
                hs = hs - old + new

        # --- full WMA ---
        if j < length - 1:
            fs = np.nan
            fws = np.nan
        elif j == length - 1 or np.isnan(fs) or (j % reseed_every == 0):
            fs, fws = _wma_window_sums(arr, j, length)
        else:
            old = arr[j - length]
            new = arr[j]
            if np.isnan(old) or np.isnan(new):
                fs = np.nan
                fws = np.nan
            else:
                fws = fws - fs + new * length
                fs = fs - old + new

        # intermediate raw = 2*half - full (both must be valid)
        if np.isnan(hws) or np.isnan(fws) or j < length - 1:
            raw[j] = np.nan
        else:
            raw[j] = 2.0 * (hws / half_tw) - (fws / full_tw)

        # --- outer WMA of raw over sqrt_n ---
        if j < need:
            os_ = np.nan
            ows = np.nan
        elif j == need or np.isnan(os_) or (j % reseed_every == 0):
            os_, ows = _wma_window_sums(raw, j, sqrt_n)
        else:
            old = raw[j - sqrt_n]
            new = raw[j]
            if np.isnan(old) or np.isnan(new):
                os_ = np.nan
                ows = np.nan
            else:
                ows = ows - os_ + new * sqrt_n
                os_ = os_ - old + new

    st[0] = hs
    st[1] = hws
    st[2] = fs
    st[3] = fws
    st[4] = os_
    st[5] = ows
    st[6] = float(i)
    if i < need or np.isnan(ows):
        return np.nan
    return ows / outer_tw


@numba.njit(cache=True)
def numba_tsi(arr, short_len, long_len, i):
    short_len = int(short_len)
    long_len = int(long_len)
    """True Strength Index: double-smoothed momentum / double-smoothed |mom|.

    TV: ``ta.tsi(source, short_length, long_length)`` —
    ``100 * EMA(EMA(mom, long), short) / EMA(EMA(|mom|, long), short)``.
    EMAs use SMA seed (same as ``numba_ema``).
    """
    if short_len <= 0 or long_len <= 0:
        return np.nan
    need = long_len + short_len - 1
    if i < need:
        return np.nan

    alpha_l = 2.0 / (long_len + 1.0)
    alpha_s = 2.0 / (short_len + 1.0)

    sum_m = 0.0
    sum_a = 0.0
    for j in range(1, long_len + 1):
        mom = arr[j] - arr[j - 1]
        sum_m += mom
        sum_a += abs(mom)
    ema_m = sum_m / long_len
    ema_a = sum_a / long_len

    seed_sm = ema_m
    seed_sa = ema_a
    seed_count = 1
    short_m = 0.0
    short_a = 0.0
    short_ready = False

    for j in range(long_len + 1, i + 1):
        mom = arr[j] - arr[j - 1]
        ema_m = alpha_l * mom + (1.0 - alpha_l) * ema_m
        ema_a = alpha_l * abs(mom) + (1.0 - alpha_l) * ema_a
        if not short_ready:
            seed_sm += ema_m
            seed_sa += ema_a
            seed_count += 1
            if seed_count == short_len:
                short_m = seed_sm / short_len
                short_a = seed_sa / short_len
                short_ready = True
        else:
            short_m = alpha_s * ema_m + (1.0 - alpha_s) * short_m
            short_a = alpha_s * ema_a + (1.0 - alpha_s) * short_a

    if not short_ready:
        return np.nan
    if short_a == 0.0:
        return 0.0
    return 100.0 * (short_m / short_a)


# ---------------------------------------------------------------------------
# Object-mode coercion helpers (pure Python; never called under njit)
# ---------------------------------------------------------------------------

def safe_float(x):
    """Best-effort float cast for plot/series stores in object mode.

    UDT dicts, hline/label/table handles, callables, version strings, ndarrays,
    and sequences must not raise — return NaN (or first element when useful).
    """
    try:
        if x is None:
            return np.nan
        # bool and numpy.bool_ (not a subclass of bool on recent NumPy)
        if isinstance(x, (bool, np.bool_)):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float, np.integer, np.floating)):
            return float(x)
        # Drawing / UDT / map handles
        if isinstance(x, (dict, set)):
            return np.nan
        # Full series buffers or multi-d arrays must not hit bare float()
        if isinstance(x, np.ndarray):
            if x.size == 0:
                return np.nan
            return safe_float(x.reshape(-1)[0])
        if isinstance(x, (list, tuple)):
            if len(x) == 0:
                return np.nan
            # "setting an array element with a sequence" — take first element
            return safe_float(x[0])
        if callable(x) and not isinstance(x, type):
            return np.nan
        if isinstance(x, str):
            # version strings / colors / labels / size enums are not floats
            s = x.strip()
            if not s or s.startswith("#"):
                return np.nan
            # Reject pure words (Round, Neutral, small, tiny, …)
            if any(c.isalpha() for c in s) and not any(c.isdigit() for c in s):
                return np.nan
            if s.count(".") > 1 or not (
                s[0].isdigit() or s[0] in "+-" or s[0] == "."
            ):
                return np.nan
            return float(s)
        # array-like with shape (e.g. some matrix stubs)
        shape = getattr(x, "shape", None)
        if shape is not None:
            try:
                flat = np.asarray(x).reshape(-1)
                if flat.size == 0:
                    return np.nan
                return safe_float(flat[0])
            except Exception:
                return np.nan
        return float(x)
    except Exception:
        return np.nan


def na_num(x):
    """Fast None→nan coercion for object-mode arithmetic / comparisons.

    Hot path: ``None`` → ``nan``; bare ``float``/``int`` identity (no alloc).
    Everything else falls through to :func:`safe_float` (handles bool, str,
    UDT dicts, sequences, …). Never raises — used in generated bar loops.
    """
    if x is None:
        return np.nan
    # CPython exact types (Pine scalars are usually these)
    t = type(x)
    if t is float or t is int:
        return x
    if t is bool:
        return 1.0 if x else 0.0
    if t is np.float64 or t is np.int64:
        return float(x)
    return safe_float(x)

def safe_int(x):
    """Best-effort int cast; NaN/invalid → 0 (Pine-ish fallback)."""
    try:
        f = safe_float(x)
        if f != f:  # NaN
            return 0
        return int(f)
    except Exception:
        return 0

def safe_period(x, default: int = 0) -> int:
    """Coerce a TA length / for-loop bound to a plain int.

    Handles float NaN (``int(nan)`` raises), multi-d ndarrays
    (``only 0-dimensional arrays…``), None, and non-numeric junk.
    Returns *default* (0) on failure so callers can treat ``period <= 0``
    as “not ready” without crashing the bar loop.
    """
    try:
        f = safe_float(x)
        if f != f:  # NaN
            return int(default)
        return int(f)
    except Exception:
        return int(default)


def safe_len(x) -> int:
    """Pine-friendly length: arrays/lists/strings ok; scalar → 0 (not TypeError)."""
    if x is None:
        return 0
    if isinstance(x, (list, tuple, str, dict, set)):
        return len(x)
    if isinstance(x, np.ndarray):
        return int(x.size) if x.ndim == 0 else int(x.shape[0])
    # float/int series values are not collections
    return 0


def safe_iter(x):
    """Iterate only real collections; scalars/NaN → empty (no TypeError)."""
    if x is None:
        return ()
    if isinstance(x, (list, tuple, str, dict, set)):
        return x
    if isinstance(x, np.ndarray):
        if x.ndim == 0:
            return ()
        return x
    if isinstance(x, (float, int, bool, complex, np.floating, np.integer)):
        return ()
    try:
        iter(x)
        return x
    except TypeError:
        return ()

def safe_sum(x):
    """Sum numeric elements of a collection; skip str/dict/None (no TypeError)."""
    if x is None:
        return 0.0
    if isinstance(x, (float, int, np.floating, np.integer, bool)):
        f = safe_float(x)
        return 0.0 if f != f else f
    total = 0.0
    n = 0
    try:
        items = safe_iter(x)
    except Exception:
        return 0.0
    for e in items:
        if isinstance(e, (list, tuple, np.ndarray)):
            total += safe_sum(e)
            n += 1
            continue
        f = safe_float(e)
        if f == f:  # not NaN
            total += f
            n += 1
    return total


def safe_max(x):
    """Max of numeric elements; empty / non-numeric → NaN."""
    if x is None:
        return np.nan
    if isinstance(x, (float, int, np.floating, np.integer, bool)):
        return safe_float(x)
    best = np.nan
    for e in safe_iter(x):
        if isinstance(e, (list, tuple, np.ndarray)):
            # matrix row/col: use first numeric leaf or flatten
            f = safe_max(e)
        else:
            f = safe_float(e)
        if f != f:
            continue
        if best != best or f > best:
            best = f
    return best


def safe_min(x):
    """Min of numeric elements; empty / non-numeric → NaN."""
    if x is None:
        return np.nan
    if isinstance(x, (float, int, np.floating, np.integer, bool)):
        return safe_float(x)
    best = np.nan
    for e in safe_iter(x):
        if isinstance(e, (list, tuple, np.ndarray)):
            f = safe_min(e)
        else:
            f = safe_float(e)
        if f != f:
            continue
        if best != best or f < best:
            best = f
    return best


def udt_index(obj, idx):
    """Index a Pine UDT dict or list/array: dict uses ordered values, list uses int."""
    try:
        i = int(idx)
    except (TypeError, ValueError):
        i = 0
    if isinstance(obj, dict):
        vals = list(obj.values())
        if 0 <= i < len(vals):
            return vals[i]
        return np.nan
    if isinstance(obj, (list, tuple)):
        if 0 <= i < len(obj):
            return obj[i]
        return np.nan
    if isinstance(obj, np.ndarray) and obj.ndim >= 1:
        if 0 <= i < len(obj):
            return obj[i]
        return np.nan
    return np.nan


def udt_set_field(obj, key, val):
    """Assign ``obj[key] = val`` when *obj* is a UDT dict; no-op for na/scalars.

    Nested field writes like ``this.__timer.offset := x`` emit
    ``udt_set_field(this['__timer'], 'offset', x)``. When ``__timer`` is still
    ``na`` (``np.nan``), a raw ``nan['offset'] = x`` would raise
    ``'float' object does not support item assignment`` (motion library).
    """
    if isinstance(obj, dict):
        obj[key] = val
    return val


def pine_raise(msg) -> None:
    """Expression-safe ``runtime.error`` for generated code.

    Pine ``runtime.error(...)`` appears in statement and expression contexts
    (ternary/switch arms, ``return runtime.error(...)``). Python ``raise`` is
    only a statement, so emitted code calls this helper instead.

    Named without a leading underscore so ``from numba_builtins import *``
    (used by compiled prologs) exports it.
    """
    raise RuntimeError(str(msg))


def str_split(value, sep=None):
    """Pine ``str.split(source, separator?)``.

    Python forbids ``str.split("")`` (empty separator). Pine uses empty
    separator to mean "split into characters" — return ``list(s)``.
    """
    s = "" if value is None else str(value)
    if sep is None:
        return s.split()
    sep_s = str(sep)
    if sep_s == "":
        return list(s)
    return s.split(sep_s)


def store_src_py(dst, val, i):
    """Object-mode series materialize: coerce non-numeric (list/str/…) to NaN.

    Avoids ``list + 0.0`` / TypeError when a Pine array handle is fed to TA.
    """
    dst[i] = safe_float(val)
    return dst


def _pine_is_descending(order) -> bool:
    """True when *order* is descending (``order.descending`` / -1 / True / …)."""
    if order is None:
        return False
    if order is True or order == -1:
        return True
    if isinstance(order, str):
        return order.lower() in ("descending", "desc")
    return False


def safe_list_set(arr, index, value):
    """Pine ``array.set(id, index, value)`` with soft OOB recovery.

    Matches the interpret-path ``_builtin_array_set`` policy used by corpus
    Runtime: grow undersized lists up to a sanity cap, no-op on negative /
    non-int index or non-list handles. Avoids ``list assignment index out of
    range`` from raw ``__setitem__`` in object-mode compile.
    """
    if not isinstance(arr, list):
        return arr
    if index is None:
        return arr
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return arr
    if idx < 0:
        return arr
    if idx >= len(arr):
        if idx >= 1_000_000:
            return arr
        arr.extend([None] * (idx + 1 - len(arr)))
    if idx < len(arr):
        arr[idx] = value
    return arr

def safe_list_append(arr, value):
    """Append to a real list; no-op when *arr* is float/None (misclassified series)."""
    if isinstance(arr, list):
        arr.append(value)
        return arr
    return arr


def safe_list_clear(arr):
    """Clear a real list; no-op for scalars (avoids float64.clear AttributeError)."""
    if isinstance(arr, list):
        arr.clear()
    return None


def safe_list_pop(arr, index=None):
    """Pop from a real list; return na when not a list / empty / OOB."""
    if not isinstance(arr, list) or not arr:
        return np.nan
    try:
        if index is None:
            return arr.pop()
        idx = int(index)
        if idx < 0 or idx >= len(arr):
            return np.nan
        return arr.pop(idx)
    except Exception:
        return np.nan


def safe_list_insert(arr, index, value):
    """Insert into a real list; no-op when *arr* is not a list / bad index."""
    if not isinstance(arr, list):
        return arr
    if index is None:
        return arr
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return arr
    if idx < 0:
        return arr
    try:
        arr.insert(idx, value)
    except Exception:
        pass
    return arr


def _udt_sort_key(elem, sort_field):
    """Extract sort key from UDT dict / ObjectInstance-like for object-mode sorts."""
    if sort_field is None:
        if isinstance(elem, dict):
            # Prefer first non-meta field; skip compiler ``__type__`` marker
            for k, v in elem.items():
                if k != "__type__":
                    return v
            return next(iter(elem.values()), np.nan) if elem else np.nan
        return elem
    if isinstance(elem, dict):
        if isinstance(sort_field, str):
            return elem.get(sort_field, np.nan)
        try:
            idx = int(sort_field)
        except (TypeError, ValueError):
            return elem
        # Prefer field order without ``__type__``
        keys = [k for k in elem.keys() if k != "__type__"]
        if 0 <= idx < len(keys):
            return elem[keys[idx]]
        vals = list(elem.values())
        if 0 <= idx < len(vals):
            return vals[idx]
        return np.nan
    get_field = getattr(elem, "get_field", None)
    if callable(get_field) and isinstance(sort_field, str):
        try:
            return get_field(sort_field)
        except Exception:
            return np.nan
    return elem


def _is_sort_na(v) -> bool:
    if v is None:
        return True
    try:
        return v != v  # NaN
    except Exception:
        return False


def array_sort(arr, order="ascending", sort_field=None):
    """Pine ``array.sort(id, order?, sort_field?)`` — in-place, na last.

    Object-mode helper. Supports UDT dict cells keyed by field name/index.
    """
    if not isinstance(arr, list):
        return arr
    reverse = _pine_is_descending(order)
    non_na = [x for x in arr if not _is_sort_na(x)]
    na_vals = [x for x in arr if _is_sort_na(x)]

    def _key(x):
        return _udt_sort_key(x, sort_field)

    try:
        non_na.sort(key=_key, reverse=reverse)
    except TypeError:
        non_na.sort(
            key=lambda x: (str(type(_key(x))), str(_key(x))),
            reverse=reverse,
        )
    arr[:] = non_na + na_vals
    return arr


def array_fill(arr, value, index_from=None, index_to=None):
    """Pine ``array.fill(id, value, index_from?, index_to?)`` half-open range.

    Also fills list-of-lists matrices cell-wise when *arr* is a matrix handle
    and no range is given.
    """
    if not isinstance(arr, list):
        return arr
    # Matrix (list-of-lists) full fill when no range
    if (
        arr
        and isinstance(arr[0], list)
        and index_from is None
        and index_to is None
    ):
        for row in arr:
            if isinstance(row, list):
                for c in range(len(row)):
                    row[c] = value
        return arr
    n = len(arr)
    if index_from is None:
        start = 0
    else:
        try:
            start = int(index_from)
        except (TypeError, ValueError):
            start = 0
    if index_to is None:
        end = n
    else:
        try:
            end = int(index_to)
        except (TypeError, ValueError):
            end = n
    if start < 0:
        start = 0
    if end > n:
        end = n
    if end < start:
        return arr
    for i in range(start, end):
        arr[i] = value
    return arr


def array_mode(arr):
    """Pine ``array.mode(id)`` — most frequent value; na if empty or all unique.

    Matches TV-ish behaviour used by corpus tests (mode of multimodal → first
    max-frequency element; all-distinct → na).
    """
    if arr is None:
        return np.nan
    try:
        seq = list(arr)
    except TypeError:
        return np.nan
    if not seq:
        return np.nan
    from collections import Counter

    counts = Counter(seq)
    best_n = max(counts.values())
    if best_n <= 1 and len(counts) == len(seq):
        # All values unique → na (TV returns na when no mode)
        return np.nan
    # First element among those with max frequency (stable)
    for v in seq:
        if counts[v] == best_n:
            return v
    return np.nan


def array_standardize(arr):
    """Pine ``array.standardize(id)`` — z-score list; empty → []."""
    if arr is None:
        return []
    try:
        seq = [safe_float(x) for x in arr]
    except TypeError:
        return []
    if not seq:
        return []
    mu = float(np.nanmean(seq)) if seq else np.nan
    sd = float(np.nanstd(seq)) if seq else np.nan
    if not (sd == sd) or sd == 0.0:
        return [0.0 if (x == x) else np.nan for x in seq]
    return [((x - mu) / sd) if (x == x) else np.nan for x in seq]


def array_normalized(arr):
    """Pine ``array.normalized(id)`` — min-max to [0,1]; empty → []."""
    if arr is None:
        return []
    try:
        seq = [safe_float(x) for x in arr]
    except TypeError:
        return []
    if not seq:
        return []
    lo = float(np.nanmin(seq)) if seq else np.nan
    hi = float(np.nanmax(seq)) if seq else np.nan
    span = hi - lo if (hi == hi and lo == lo) else np.nan
    if not (span == span) or span == 0.0:
        return [0.0 if (x == x) else np.nan for x in seq]
    return [((x - lo) / span) if (x == x) else np.nan for x in seq]


def array_sort_indices(arr, order="ascending", sort_field=None):
    """Pine ``array.sort_indices(id, order?, sort_field?)`` → indices (na last).

    Object-mode helper used by the Numba compiler emit path. Optional
    *sort_field* keys UDT/dict elements (field name or field index).
    """
    if arr is None:
        return []
    try:
        seq = list(arr)
    except TypeError:
        return []
    if not seq:
        return []
    reverse = _pine_is_descending(order)

    non_na = [(val, idx) for idx, val in enumerate(seq) if not _is_sort_na(val)]
    na_idx = [idx for idx, val in enumerate(seq) if _is_sort_na(val)]

    def _key_pair(pair):
        return _udt_sort_key(pair[0], sort_field)

    try:
        non_na.sort(key=_key_pair, reverse=reverse)
    except TypeError:
        non_na.sort(
            key=lambda x: (str(type(_key_pair(x))), str(_key_pair(x))),
            reverse=reverse,
        )
    return [idx for _, idx in non_na] + na_idx


def _matrix_ncols(m) -> int:
    if not m:
        return 0
    try:
        return len(m[0]) if m[0] is not None else 0
    except (TypeError, IndexError):
        return 0


def _matrix_ensure(m):
    """Coerce *m* to a mutable list-of-lists matrix handle."""
    if m is None:
        return []
    if isinstance(m, list):
        return m
    try:
        return [list(row) for row in m]
    except TypeError:
        return []


def matrix_add_row(m, *rest):
    """Pine ``matrix.add_row(id)`` / ``(id, array)`` / ``(id, row, array)``.

    Mutates list-of-lists *m* in place and returns it.
    """
    m = _matrix_ensure(m)
    row_idx = None
    row_data = None
    if len(rest) == 1:
        if isinstance(rest[0], (list, tuple)):
            row_data = list(rest[0])
        else:
            try:
                row_idx = int(rest[0])
            except (TypeError, ValueError):
                row_idx = None
    elif len(rest) >= 2:
        try:
            row_idx = int(rest[0]) if rest[0] is not None else None
        except (TypeError, ValueError):
            row_idx = None
        if isinstance(rest[1], (list, tuple)):
            row_data = list(rest[1])
        elif rest[1] is not None:
            try:
                row_data = list(rest[1])
            except TypeError:
                row_data = None

    cols = _matrix_ncols(m)
    if row_data is None:
        row_data = [np.nan] * cols
    elif cols > 0:
        if len(row_data) < cols:
            row_data = list(row_data) + [np.nan] * (cols - len(row_data))
        elif len(row_data) > cols:
            row_data = list(row_data[:cols])
    else:
        row_data = list(row_data)

    if row_idx is None or row_idx >= len(m):
        m.append(row_data)
    else:
        m.insert(max(0, int(row_idx)), row_data)
    return m


def matrix_add_col(m, *rest):
    """Pine ``matrix.add_col(id)`` / ``(id, array)`` / ``(id, column, array)``.

    Mutates list-of-lists *m* in place and returns it.
    """
    m = _matrix_ensure(m)
    col_idx = None
    col_data = None
    if len(rest) == 1:
        if isinstance(rest[0], (list, tuple)):
            col_data = list(rest[0])
        else:
            try:
                col_idx = int(rest[0])
            except (TypeError, ValueError):
                col_idx = None
    elif len(rest) >= 2:
        try:
            col_idx = int(rest[0]) if rest[0] is not None else None
        except (TypeError, ValueError):
            col_idx = None
        if isinstance(rest[1], (list, tuple)):
            col_data = list(rest[1])
        elif rest[1] is not None:
            try:
                col_data = list(rest[1])
            except TypeError:
                col_data = None

    nrows = len(m)
    if col_data is None:
        col_data = [np.nan] * nrows
    else:
        col_data = list(col_data)

    # Empty matrix: column data defines row count (one element per new row).
    if nrows == 0:
        for v in col_data:
            m.append([v])
        return m

    if len(col_data) < nrows:
        col_data = col_data + [np.nan] * (nrows - len(col_data))
    elif len(col_data) > nrows:
        col_data = col_data[:nrows]

    ncols = _matrix_ncols(m)
    insert_at = ncols if col_idx is None else max(0, min(int(col_idx), ncols))
    for i, row in enumerate(m):
        if not isinstance(row, list):
            row = list(row)
            m[i] = row
        row.insert(insert_at, col_data[i])
    return m


def matrix_remove_row(m, index=0):
    """Pine ``matrix.remove_row(id, row)`` → removed row as list; mutates *m*."""
    m = _matrix_ensure(m)
    try:
        i = int(index)
    except (TypeError, ValueError):
        i = 0
    if not m or not (0 <= i < len(m)):
        return []
    return list(m.pop(i))


def matrix_remove_col(m, index=0):
    """Pine ``matrix.remove_col(id, column)`` → removed col as list; mutates *m*."""
    m = _matrix_ensure(m)
    try:
        i = int(index)
    except (TypeError, ValueError):
        i = 0
    ncols = _matrix_ncols(m)
    if not m or not (0 <= i < ncols):
        return []
    removed = []
    for row in m:
        if isinstance(row, list) and 0 <= i < len(row):
            removed.append(row.pop(i))
        else:
            removed.append(np.nan)
    # Drop empty rows if matrix becomes 0-col (keep row shells for handle stability)
    return removed


def matrix_reshape(m, rows, cols):
    """Pine ``matrix.reshape(id, rows, columns)`` — in-place reshape; returns *m*."""
    m = _matrix_ensure(m)
    try:
        rows_i = int(rows)
        cols_i = int(cols)
    except (TypeError, ValueError):
        return m
    if rows_i < 0 or cols_i < 0:
        return m
    flat = [elem for row in m for elem in (row if isinstance(row, (list, tuple)) else [row])]
    need = rows_i * cols_i
    if len(flat) < need:
        flat = flat + [np.nan] * (need - len(flat))
    else:
        flat = flat[:need]
    new_data = [
        [flat[r * cols_i + c] for c in range(cols_i)] for r in range(rows_i)
    ]
    m.clear()
    m.extend(new_data)
    return m


def matrix_swap_rows(m, row1, row2):
    """Pine ``matrix.swap_rows(id, row1, row2)`` — in-place; returns *m*."""
    m = _matrix_ensure(m)
    try:
        r1 = int(row1)
        r2 = int(row2)
    except (TypeError, ValueError):
        return m
    n = len(m)
    if 0 <= r1 < n and 0 <= r2 < n:
        m[r1], m[r2] = m[r2], m[r1]
    return m


def matrix_swap_columns(m, col1, col2):
    """Pine ``matrix.swap_columns(id, col1, col2)`` — in-place; returns *m*."""
    m = _matrix_ensure(m)
    try:
        c1 = int(col1)
        c2 = int(col2)
    except (TypeError, ValueError):
        return m
    ncols = _matrix_ncols(m)
    if not (0 <= c1 < ncols and 0 <= c2 < ncols):
        return m
    for row in m:
        if isinstance(row, list) and c1 < len(row) and c2 < len(row):
            row[c1], row[c2] = row[c2], row[c1]
    return m


def sequence_from_series(src, length=None, shift=0, direction_forward=True, i=None):
    """Best-effort ``*.sequence_from_series`` stub → list of recent values.

    ``src`` may be a full float series array or a scalar. Used by library
    helpers that sample a window; length defaults to available history.
    """
    try:
        length_i = int(length) if length is not None else 0
    except (TypeError, ValueError):
        length_i = 0
    try:
        shift_i = int(shift) if shift is not None else 0
    except (TypeError, ValueError):
        shift_i = 0
    if isinstance(src, (list, tuple)):
        data = list(src)
    elif isinstance(src, np.ndarray):
        data = src.tolist()
    else:
        return [safe_float(src)]
    n = len(data)
    if n == 0:
        return []
    end = n - 1 - shift_i if i is None else int(i) - shift_i
    if end < 0:
        return []
    if length_i <= 0:
        length_i = end + 1
    start = max(0, end - length_i + 1)
    window = [safe_float(data[j]) for j in range(start, end + 1)]
    if not direction_forward:
        window.reverse()
    return window


# ---------------------------------------------------------------------------
# Incremental TA (``*_inc``) — fixed-size ``st`` vectors from CompilerVisitor
# ---------------------------------------------------------------------------

@numba.njit(cache=True)
def numba_ema_inc(arr, period, i, st):
    """Incremental EMA. ``st`` is length-2: [ema, last_i]; last_i nan → none.

    Sequential bar calls are O(1) amortized; gaps catch up from last_i+1.

    Seeding is NaN-window-safe: while the accumulator is still NaN and
    ``j >= period-1``, try SMA over ``arr[j-period+1 : j+1]`` only when every
    sample is finite. Nested EMAs (DEMA via ``ema(ema(...))``) and RMA-of-TR
    style inputs with leading NaNs eventually produce values instead of
    poisoning the seed forever.

    Same SMA-seed contract as :func:`numba_ema` / interpret ``_ema_inc_update``.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    alpha = 2.0 / (period + 1.0)
    ema = st[0]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            ema = np.nan
        elif np.isnan(ema):
            sum_val = 0.0
            ok = True
            start = j - period + 1
            for k in range(period):
                v = arr[start + k]
                if np.isnan(v):
                    ok = False
                    break
                sum_val += v
            ema = sum_val / period if ok else np.nan
        else:
            ema = alpha * arr[j] + (1.0 - alpha) * ema
    st[0] = ema
    st[1] = float(i)
    if i < period - 1:
        return np.nan
    return ema


@numba.njit(cache=True)
def numba_rma_inc(arr, period, i, st):
    """Incremental Wilder RMA. ``st``: [rma, last_i].

    NaN-window-safe SMA seed (same policy as ``numba_ema_inc``). Critical for
    ATR-via-``rma(tr)`` and expanded ADX/DMI (``rma(plusDM)``) where the
    source is NaN on bar 0 — without a sliding all-finite seed, compile ADX
    stayed ~0 after warmup while interpret rose.
    After seed, NaN inputs hold the previous RMA (interpret ``_rma_inc_update``).
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    alpha = 1.0 / period
    rma = st[0]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            rma = np.nan
        elif np.isnan(rma):
            ssum = 0.0
            ok = True
            start = j - period + 1
            for k in range(period):
                v = arr[start + k]
                if np.isnan(v):
                    ok = False
                    break
                ssum += v
            rma = ssum / period if ok else np.nan
        else:
            v = arr[j]
            if not np.isnan(v):
                rma = alpha * v + (1.0 - alpha) * rma
    st[0] = rma
    st[1] = float(i)
    if i < period - 1:
        return np.nan
    return rma


@numba.njit(cache=True)
def numba_atr_inc(high, low, close, period, i, st):
    """Incremental ATR. ``st``: [acc, last_i] (warm sum or EMA).

    Matches ``numba_atr``: mean(TR) while ``i < period``, else EMA-of-TR
    seeded with the first TR value.
    """
    period = int(period)
    if period <= 0 or i < 1:
        return np.nan
    if np.isnan(st[1]):
        last = 0
    else:
        last = int(st[1])
    if i < last:
        last = 0
        st[0] = np.nan

    alpha = 2.0 / (period + 1.0)
    acc = st[0]
    start = 1 if last < 1 else last + 1

    for j in range(start, i + 1):
        tr = max(
            high[j] - low[j],
            abs(high[j] - close[j - 1]),
            abs(low[j] - close[j - 1]),
        )
        if j < period:
            if j == 1 or np.isnan(acc) or last < 1:
                s = 0.0
                for k in range(1, j + 1):
                    s += max(
                        high[k] - low[k],
                        abs(high[k] - close[k - 1]),
                        abs(low[k] - close[k - 1]),
                    )
                acc = s
            else:
                acc = acc + tr
        elif j == period:
            # Switch to EMA seeded with first TR (not the warm mean).
            acc = max(high[1] - low[1], abs(high[1] - close[0]), abs(low[1] - close[0]))
            for k in range(2, j + 1):
                trk = max(
                    high[k] - low[k],
                    abs(high[k] - close[k - 1]),
                    abs(low[k] - close[k - 1]),
                )
                acc = alpha * trk + (1.0 - alpha) * acc
        else:
            if np.isnan(acc) or last < period:
                acc = max(high[1] - low[1], abs(high[1] - close[0]), abs(low[1] - close[0]))
                for k in range(2, j + 1):
                    trk = max(
                        high[k] - low[k],
                        abs(high[k] - close[k - 1]),
                        abs(low[k] - close[k - 1]),
                    )
                    acc = alpha * trk + (1.0 - alpha) * acc
            else:
                acc = alpha * tr + (1.0 - alpha) * acc

    st[0] = acc
    st[1] = float(i)
    if i < period:
        return acc / i
    return acc
@numba.njit(cache=True)
def numba_macd_inc(arr, fast, slow, signal, i, st):
    """Incremental MACD. ``st``: [ema_f, ema_s, sig, last_i].

    Amortized O(1) per sequential bar; matches ``numba_macd`` values.
    """
    fast = int(fast)
    slow = int(slow)
    signal = int(signal)
    if fast <= 0 or slow <= 0 or signal <= 0 or i < 0:
        return np.nan, np.nan, np.nan

    if np.isnan(st[3]):
        last = -1
    else:
        last = int(st[3])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan

    alpha_f = 2.0 / (fast + 1.0)
    alpha_s = 2.0 / (slow + 1.0)
    alpha_sig = 2.0 / (signal + 1.0)

    ema_f = st[0]
    ema_s = st[1]
    sig = st[2]

    for j in range(last + 1, i + 1):
        # Fast EMA: seed at fast-1, advance on later bars (including through slow-1)
        if j == fast - 1:
            sum_f = 0.0
            for k in range(fast):
                sum_f += arr[k]
            ema_f = sum_f / fast
        elif j >= fast:
            ema_f = alpha_f * arr[j] + (1.0 - alpha_f) * ema_f

        # Slow EMA + signal: seed at slow-1, then joint advance
        if j == slow - 1:
            sum_s = 0.0
            for k in range(slow):
                sum_s += arr[k]
            ema_s = sum_s / slow
            macd_val = ema_f - ema_s
            sig = macd_val
        elif j >= slow:
            # ema_f already advanced above for this j
            ema_s = alpha_s * arr[j] + (1.0 - alpha_s) * ema_s
            macd_val = ema_f - ema_s
            sig = alpha_sig * macd_val + (1.0 - alpha_sig) * sig

    st[0] = ema_f
    st[1] = ema_s
    st[2] = sig
    st[3] = float(i)

    if i < slow - 1:
        return np.nan, np.nan, np.nan
    macd_val = ema_f - ema_s
    return macd_val, sig, macd_val - sig
@numba.njit(cache=True)
def numba_cum_inc(arr, i, st):
    """Incremental cum. ``st``: [sum, last_i]."""
    if i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = 0.0
    s = 0.0 if np.isnan(st[0]) or last < 0 else st[0]
    for j in range(last + 1, i + 1):
        v = arr[j]
        if not np.isnan(v):
            s += v
    st[0] = s
    st[1] = float(i)
    return s
@numba.njit(cache=True)
def numba_vwap_inc(src, vol, i, st):
    """Incremental VWAP. ``st``: [cum_pv, cum_v, last_i]."""
    if i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = 0.0
        st[1] = 0.0
    cum_pv = 0.0 if last < 0 or np.isnan(st[0]) else st[0]
    cum_v = 0.0 if last < 0 or np.isnan(st[1]) else st[1]
    for j in range(last + 1, i + 1):
        p = src[j]
        v = vol[j]
        if np.isnan(p) or np.isnan(v):
            continue
        cum_pv += p * v
        cum_v += v
    st[0] = cum_pv
    st[1] = cum_v
    st[2] = float(i)
    if cum_v == 0.0:
        return np.nan
    return cum_pv / cum_v


@numba.njit(cache=True)
def numba_vwap_anchor_inc(src, vol, anchor, i, st):
    """Incremental VWAP with anchor reset. ``st``: [cum_pv, cum_v, last_i].

    When ``anchor[j]`` is non-zero / true, the cumulative window restarts at
    bar ``j`` (includes bar ``j`` in the new window) — TV ``ta.vwap(src, anchor)``.
    """
    if i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = 0.0
        st[1] = 0.0
    cum_pv = 0.0 if last < 0 or np.isnan(st[0]) else st[0]
    cum_v = 0.0 if last < 0 or np.isnan(st[1]) else st[1]
    for j in range(last + 1, i + 1):
        a = anchor[j]
        if not np.isnan(a) and a != 0.0:
            cum_pv = 0.0
            cum_v = 0.0
        p = src[j]
        v = vol[j]
        if np.isnan(p) or np.isnan(v):
            continue
        cum_pv += p * v
        cum_v += v
    st[0] = cum_pv
    st[1] = cum_v
    st[2] = float(i)
    if cum_v == 0.0:
        return np.nan
    return cum_pv / cum_v


@numba.njit(cache=True)
def numba_obv_inc(close, vol, i, st):
    """Incremental OBV. ``st``: [obv, last_i]."""
    if i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = 0
    else:
        last = int(st[1])
    if i < last:
        last = 0
        st[0] = 0.0
    obv = 0.0 if last <= 0 or np.isnan(st[0]) else st[0]
    start = 1 if last < 1 else last + 1
    for j in range(start, i + 1):
        if close[j] > close[j - 1]:
            obv += vol[j]
        elif close[j] < close[j - 1]:
            obv -= vol[j]
    st[0] = obv
    st[1] = float(i)
    return obv


@numba.njit(cache=True)
def numba_sma_inc(arr, period, i, st):
    """O(1) rolling SMA. ``st``: [sum, last_i]. Matches ``numba_sma``."""
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    s = st[0]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            s = np.nan
        elif j == period - 1:
            s = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
            if not ok:
                s = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                ok = True
                for k in range(period):
                    v = arr[j - k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                if not ok:
                    s = np.nan
            else:
                old = arr[j - period]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                else:
                    s = s - old + new
    st[0] = s
    st[1] = float(i)
    if i < period - 1 or np.isnan(s):
        return np.nan
    return s / period


@numba.njit(cache=True)
def numba_sum_inc(arr, period, i, st):
    """O(1) rolling sum. ``st``: [sum, last_i]. Matches ``numba_sum``."""
    # Same window sum as SMA without divide
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    s = st[0]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            s = np.nan
        elif j == period - 1:
            s = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
            if not ok:
                s = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                ok = True
                for k in range(period):
                    v = arr[j - k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                if not ok:
                    s = np.nan
            else:
                old = arr[j - period]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                else:
                    s = s - old + new
    st[0] = s
    st[1] = float(i)
    if i < period - 1 or np.isnan(s):
        return np.nan
    return s


@numba.njit(cache=True)
def numba_stdev_inc(arr, period, i, st):
    """O(1) sample stdev. ``st``: [sum, sumsq, last_i]. Matches ``numba_stdev``."""
    period = int(period)
    if period <= 1 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    s = st[0]
    sq = st[1]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            s = np.nan
            sq = np.nan
        elif j == period - 1:
            s = 0.0
            sq = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
                sq += v * v
            if not ok:
                s = np.nan
                sq = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                sq = 0.0
                ok = True
                for k in range(period):
                    v = arr[j - k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                    sq += v * v
                if not ok:
                    s = np.nan
                    sq = np.nan
            else:
                old = arr[j - period]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                    sq = np.nan
                else:
                    s = s - old + new
                    sq = sq - old * old + new * new
    st[0] = s
    st[1] = sq
    st[2] = float(i)
    if i < period - 1 or np.isnan(s):
        return np.nan
    mean = s / period
    var = (sq - s * mean) / (period - 1)
    if var < 0.0:
        # floating cancellation
        var = 0.0
    return np.sqrt(var)


@numba.njit(cache=True)
def numba_variance_inc(arr, period, i, st):
    """O(1) sample variance. ``st``: [sum, sumsq, last_i]. Matches ``numba_variance``."""
    period = int(period)
    if period <= 1 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    s = st[0]
    sq = st[1]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            s = np.nan
            sq = np.nan
        elif j == period - 1:
            s = 0.0
            sq = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
                sq += v * v
            if not ok:
                s = np.nan
                sq = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                sq = 0.0
                ok = True
                for k in range(period):
                    v = arr[j - k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                    sq += v * v
                if not ok:
                    s = np.nan
                    sq = np.nan
            else:
                old = arr[j - period]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                    sq = np.nan
                else:
                    s = s - old + new
                    sq = sq - old * old + new * new
    st[0] = s
    st[1] = sq
    st[2] = float(i)
    if i < period - 1 or np.isnan(s):
        return np.nan
    mean = s / period
    var = (sq - s * mean) / (period - 1)
    if var < 0.0:
        var = 0.0
    return var


@numba.njit(cache=True)
def numba_bb_inc(arr, period, mult, i, st):
    """Incremental Bollinger. ``st``: [sum, sumsq, last_i]. Matches ``numba_bb``."""
    period = int(period)
    sd = numba_stdev_inc(arr, period, i, st)
    if np.isnan(sd):
        return np.nan, np.nan, np.nan
    # st[0] is sum after stdev_inc
    mid = st[0] / period
    return mid + mult * sd, mid, mid - mult * sd


@numba.njit(cache=True)
def numba_rsi_inc(arr, period, i, st):
    """O(1) Wilder RSI. ``st``: [avg_gain, avg_loss, last_i]. Matches ``numba_rsi``.

    Seed at ``i == period`` with SMA of first ``period`` deltas; later bars use
    RMA (``alpha = 1/period``) on gain/loss — same as interpret ``_rsi_inc_update``.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    avg_gain = st[0]
    avg_loss = st[1]
    alpha = 1.0 / period
    for j in range(last + 1, i + 1):
        if j < period:
            avg_gain = np.nan
            avg_loss = np.nan
        elif j == period:
            g = 0.0
            l = 0.0
            for k in range(1, period + 1):
                delta = arr[k] - arr[k - 1]
                if delta >= 0.0:
                    g += delta
                else:
                    l -= delta
            avg_gain = g / period
            avg_loss = l / period
        else:
            if np.isnan(avg_gain):
                # Catch-up seed if state was lost
                g = 0.0
                l = 0.0
                for k in range(1, period + 1):
                    delta = arr[k] - arr[k - 1]
                    if delta >= 0.0:
                        g += delta
                    else:
                        l -= delta
                avg_gain = g / period
                avg_loss = l / period
                for k in range(period + 1, j + 1):
                    delta = arr[k] - arr[k - 1]
                    gain = delta if delta >= 0.0 else 0.0
                    loss = -delta if delta < 0.0 else 0.0
                    avg_gain = alpha * gain + (1.0 - alpha) * avg_gain
                    avg_loss = alpha * loss + (1.0 - alpha) * avg_loss
            else:
                delta = arr[j] - arr[j - 1]
                gain = delta if delta >= 0.0 else 0.0
                loss = -delta if delta < 0.0 else 0.0
                avg_gain = alpha * gain + (1.0 - alpha) * avg_gain
                avg_loss = alpha * loss + (1.0 - alpha) * avg_loss
    st[0] = avg_gain
    st[1] = avg_loss
    st[2] = float(i)
    if i < period or np.isnan(avg_gain):
        return np.nan
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@numba.njit(cache=True)
def numba_tsi_inc(arr, short_len, long_len, i, st):
    """Incremental TSI. ``st``: [ema_m, ema_a, short_m, short_a, phase, last_i].

    ``phase`` is the short-seed sample count (0..short_len). When equal to
    ``short_len``, short_* hold EMA values; while 0 < phase < short_len they
    hold the running sum for the short SMA seed (matching ``numba_tsi``).
    """
    short_len = int(short_len)
    long_len = int(long_len)
    if short_len <= 0 or long_len <= 0 or i < 0:
        return np.nan
    need = long_len + short_len - 1
    if np.isnan(st[5]):
        last = 0
    else:
        last = int(st[5])
    if i < last:
        last = 0
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan
        st[3] = np.nan
        st[4] = 0.0

    alpha_l = 2.0 / (long_len + 1.0)
    alpha_s = 2.0 / (short_len + 1.0)
    ema_m = st[0]
    ema_a = st[1]
    short_m = st[2]
    short_a = st[3]
    phase = 0 if np.isnan(st[4]) else int(st[4])

    # Replay from last+1, but long seed needs bars 1..long_len first
    start = last + 1 if last > 0 else 1
    for j in range(start, i + 1):
        if j < long_len:
            continue
        if j == long_len:
            sum_m = 0.0
            sum_a = 0.0
            for k in range(1, long_len + 1):
                mom = arr[k] - arr[k - 1]
                sum_m += mom
                sum_a += abs(mom)
            ema_m = sum_m / long_len
            ema_a = sum_a / long_len
            # Begin short SMA seed with this first long-EMA sample
            short_m = ema_m
            short_a = ema_a
            phase = 1
            if phase == short_len:
                # short_len == 1: already final short EMA seed
                pass
            continue
        # j > long_len
        mom = arr[j] - arr[j - 1]
        ema_m = alpha_l * mom + (1.0 - alpha_l) * ema_m
        ema_a = alpha_l * abs(mom) + (1.0 - alpha_l) * ema_a
        if phase < short_len:
            short_m = short_m + ema_m
            short_a = short_a + ema_a
            phase += 1
            if phase == short_len:
                short_m = short_m / short_len
                short_a = short_a / short_len
        else:
            short_m = alpha_s * ema_m + (1.0 - alpha_s) * short_m
            short_a = alpha_s * ema_a + (1.0 - alpha_s) * short_a

    st[0] = ema_m
    st[1] = ema_a
    st[2] = short_m
    st[3] = short_a
    st[4] = float(phase)
    st[5] = float(i)

    if i < need or phase < short_len:
        return np.nan
    if short_a == 0.0:
        return 0.0
    return 100.0 * (short_m / short_a)


@numba.njit(cache=True)
def numba_highest_inc(arr, period, i, st):
    """Amortized sliding-window max. ``st``: [max_val, max_idx, last_i].

    Matches :func:`numba_highest` / interpret: NaN until full ``period`` bars
    (``i < period - 1``). State still advances for catch-up / rewind.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    m = st[0]
    mi = -1 if np.isnan(st[1]) else int(st[1])
    for j in range(last + 1, i + 1):
        # Full-window only (interpret parity); skip partial history.
        if j < period - 1:
            m = np.nan
            mi = -1
            continue
        start = j - period + 1
        if np.isnan(m) or mi < start:
            m = np.nan
            mi = -1
            for k in range(start, j + 1):
                v = arr[k]
                if np.isnan(v):
                    continue
                if np.isnan(m) or v > m:
                    m = v
                    mi = k
        else:
            v = arr[j]
            if np.isnan(m):
                if not np.isnan(v):
                    m = v
                    mi = j
            elif (not np.isnan(v)) and v > m:
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi) if mi >= 0 else np.nan
    st[2] = float(i)
    if i < period - 1:
        return np.nan
    return m


@numba.njit(cache=True)
def numba_lowest_inc(arr, period, i, st):
    """Amortized sliding-window min. ``st``: [min_val, min_idx, last_i].

    Matches :func:`numba_lowest` / interpret: NaN until full ``period`` bars.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    m = st[0]
    mi = -1 if np.isnan(st[1]) else int(st[1])
    for j in range(last + 1, i + 1):
        if j < period - 1:
            m = np.nan
            mi = -1
            continue
        start = j - period + 1
        if np.isnan(m) or mi < start:
            m = np.nan
            mi = -1
            for k in range(start, j + 1):
                v = arr[k]
                if np.isnan(v):
                    continue
                if np.isnan(m) or v < m:
                    m = v
                    mi = k
        else:
            v = arr[j]
            if np.isnan(m):
                if not np.isnan(v):
                    m = v
                    mi = j
            elif (not np.isnan(v)) and v < m:
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi) if mi >= 0 else np.nan
    st[2] = float(i)
    if i < period - 1:
        return np.nan
    return m


@numba.njit(cache=True)
def numba_vwma_inc(src, vol, length, i, st):
    """O(1) rolling VWMA. ``st``: [sum_pv, sum_v, last_i]. Matches ``numba_vwma``."""
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    sp = st[0]
    sv = st[1]
    for j in range(last + 1, i + 1):
        if j < length - 1:
            sp = np.nan
            sv = np.nan
        elif j == length - 1:
            sp = 0.0
            sv = 0.0
            ok = True
            for k in range(length):
                p = src[k]
                v = vol[k]
                if np.isnan(p) or np.isnan(v):
                    ok = False
                    break
                sp += p * v
                sv += v
            if not ok:
                sp = np.nan
                sv = np.nan
        else:
            if np.isnan(sp):
                sp = 0.0
                sv = 0.0
                ok = True
                for k in range(length):
                    p = src[j - k]
                    v = vol[j - k]
                    if np.isnan(p) or np.isnan(v):
                        ok = False
                        break
                    sp += p * v
                    sv += v
                if not ok:
                    sp = np.nan
                    sv = np.nan
            else:
                po = src[j - length]
                vo = vol[j - length]
                pn = src[j]
                vn = vol[j]
                if np.isnan(po) or np.isnan(vo) or np.isnan(pn) or np.isnan(vn):
                    sp = np.nan
                    sv = np.nan
                else:
                    sp = sp - po * vo + pn * vn
                    sv = sv - vo + vn
    st[0] = sp
    st[1] = sv
    st[2] = float(i)
    if i < length - 1 or np.isnan(sp) or sv == 0.0:
        return np.nan
    return sp / sv


@numba.njit(cache=True)
def numba_stoch_inc(source, high, low, length, i, st):
    """Incremental stochastic %K. ``st``: [hh, hi, ll, li, last_i]."""
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    if np.isnan(st[4]):
        last = -1
    else:
        last = int(st[4])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan
        st[3] = np.nan
    hh = st[0]
    hi = -1 if np.isnan(st[1]) else int(st[1])
    ll = st[2]
    li = -1 if np.isnan(st[3]) else int(st[3])
    for j in range(last + 1, i + 1):
        start = j - length + 1
        if start < 0:
            start = 0
        # high max
        if j == 0 or np.isnan(hh) or hi < start:
            hh = high[start]
            hi = start
            for k in range(start + 1, j + 1):
                v = high[k]
                if v > hh or np.isnan(hh):
                    hh = v
                    hi = k
        else:
            v = high[j]
            if v > hh or np.isnan(hh):
                hh = v
                hi = j
        # low min
        if j == 0 or np.isnan(ll) or li < start:
            ll = low[start]
            li = start
            for k in range(start + 1, j + 1):
                v = low[k]
                if v < ll or np.isnan(ll):
                    ll = v
                    li = k
        else:
            v = low[j]
            if v < ll or np.isnan(ll):
                ll = v
                li = j
    st[0] = hh
    st[1] = float(hi)
    st[2] = ll
    st[3] = float(li)
    st[4] = float(i)
    if i < length - 1:
        return np.nan
    if np.isnan(hh) or np.isnan(ll) or np.isnan(source[i]):
        return np.nan
    if hh == ll:
        return 50.0
    return 100.0 * (source[i] - ll) / (hh - ll)


@numba.njit(cache=True)
def numba_wma_inc(arr, length, i, st):
    """O(1) WMA via running sum + weighted sum. ``st``: [sum, wsum, last_i].

    Weights: oldest=1 … newest=length (matches ``numba_wma``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    s = st[0]
    ws = st[1]
    total_w = length * (length + 1) / 2.0
    for j in range(last + 1, i + 1):
        if j < length - 1:
            s = np.nan
            ws = np.nan
        elif j == length - 1:
            s = 0.0
            ws = 0.0
            ok = True
            for k in range(length):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
                ws += v * (k + 1)
            if not ok:
                s = np.nan
                ws = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                ws = 0.0
                ok = True
                for k in range(length):
                    v = arr[j - length + 1 + k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                    ws += v * (k + 1)
                if not ok:
                    s = np.nan
                    ws = np.nan
            else:
                old = arr[j - length]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                    ws = np.nan
                else:
                    # Drop oldest (weight 1), demote remaining weights by 1, add new at length
                    # ws_new = ws - old*1 - (s - old) + new*length
                    # = ws - old - s + old + new*length = ws - s + new*length
                    ws = ws - s + new * length
                    s = s - old + new
    st[0] = s
    st[1] = ws
    st[2] = float(i)
    if i < length - 1 or np.isnan(ws):
        return np.nan
    return ws / total_w


@numba.njit(cache=True)
def numba_barssince_inc(cond_arr, i, st):
    """O(1) bars-since. ``st``: [last_true_i, last_proc_i]."""
    if i < 0:
        return np.nan
    if np.isnan(st[1]):
        lp = -1
    else:
        lp = int(st[1])
    if i < lp:
        st[0] = np.nan
        lp = -1
    lt = -1 if np.isnan(st[0]) else int(st[0])
    for j in range(lp + 1, i + 1):
        c = cond_arr[j]
        if not (np.isnan(c) or c == 0.0):
            lt = j
    st[0] = float(lt) if lt >= 0 else np.nan
    st[1] = float(i)
    if lt < 0:
        return np.nan
    return float(i - lt)


@numba.njit(cache=True)
def numba_linreg_inc(arr, length, offset, i, st):
    """O(1) rolling linreg. ``st``: [sum_y, sum_xy, last_i]."""
    length = int(length)
    offset = int(offset)
    if length < 2 or i < 0:
        return np.nan
    n = float(length)
    sum_x = n * (n - 1.0) / 2.0
    sum_xx = (n - 1.0) * n * (2.0 * n - 1.0) / 6.0
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    sy = st[0]
    sxy = st[1]
    for j in range(last + 1, i + 1):
        if j < length - 1:
            sy = np.nan
            sxy = np.nan
        elif j == length - 1:
            sy = 0.0
            sxy = 0.0
            ok = True
            for k in range(length):
                y = arr[k]
                if np.isnan(y):
                    ok = False
                    break
                sy += y
                sxy += float(k) * y
            if not ok:
                sy = np.nan
                sxy = np.nan
        else:
            if np.isnan(sy):
                sy = 0.0
                sxy = 0.0
                ok = True
                base = j - length + 1
                for k in range(length):
                    y = arr[base + k]
                    if np.isnan(y):
                        ok = False
                        break
                    sy += y
                    sxy += float(k) * y
                if not ok:
                    sy = np.nan
                    sxy = np.nan
            else:
                y0 = arr[j - length]
                yn = arr[j]
                if np.isnan(y0) or np.isnan(yn):
                    sy = np.nan
                    sxy = np.nan
                else:
                    sxy = sxy - sy + y0 + yn * (n - 1.0)
                    sy = sy - y0 + yn
    st[0] = sy
    st[1] = sxy
    st[2] = float(i)
    if i < length - 1 or np.isnan(sy):
        return np.nan
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0.0:
        return sy / n
    slope = (n * sxy - sum_x * sy) / denom
    intercept = (sy - slope * sum_x) / n
    return intercept + slope * (n - 1.0 - float(offset))


@numba.njit(cache=True)
def numba_sar_inc(high, low, start, increment, maximum, i, st):
    """Incremental Parabolic SAR. ``st``: [sar, ep, af, trend, last_i]."""
    if i < 0 or len(high) == 0:
        return np.nan
    if np.isnan(st[4]):
        last = -1
    else:
        last = int(st[4])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan
        st[3] = np.nan

    if last < 0:
        sar = low[0]
        ep = high[0]
        af = start
        trend = 1.0
        last = 0
        st[0] = sar
        st[1] = ep
        st[2] = af
        st[3] = trend
        st[4] = 0.0
        if i == 0:
            return sar
    else:
        sar = st[0]
        ep = st[1]
        af = st[2]
        trend = st[3]

    for idx in range(last + 1, i + 1):
        hi = high[idx]
        lo = low[idx]
        prev = sar
        if trend > 0.0:
            sar = prev + af * (ep - prev)
            if hi > ep:
                ep = hi
                af = af + increment
                if af > maximum:
                    af = maximum
            if sar > lo:
                trend = -1.0
                sar = ep
                ep = lo
                af = start
        else:
            sar = prev - af * (prev - ep)
            if lo < ep:
                ep = lo
                af = af + increment
                if af > maximum:
                    af = maximum
            if sar < hi:
                trend = 1.0
                sar = ep
                ep = hi
                af = start

    st[0] = sar
    st[1] = ep
    st[2] = af
    st[3] = trend
    st[4] = float(i)
    return sar


@numba.njit(cache=True)
def numba_cci_inc(arr, length, i, st):
    """Incremental CCI. ``st``: [sum, last_i].

    Rolling mean is O(1); mean absolute deviation rescans the window (O(length)).
    Matches ``numba_cci``.
    """
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    s = st[0]
    for j in range(last + 1, i + 1):
        if j < length - 1:
            s = np.nan
        elif j == length - 1:
            s = 0.0
            ok = True
            for k in range(length):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
            if not ok:
                s = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                ok = True
                for k in range(length):
                    v = arr[j - k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                if not ok:
                    s = np.nan
            else:
                old = arr[j - length]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                else:
                    s = s - old + new
    st[0] = s
    st[1] = float(i)
    if i < length - 1 or np.isnan(s):
        return np.nan
    mean = s / length
    md = 0.0
    for j in range(length):
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        md += abs(v - mean)
    md /= length
    if md == 0.0:
        return 0.0
    return (arr[i] - mean) / (0.015 * md)


@numba.njit(cache=True)
def numba_dev_inc(arr, period, i, st):
    """Incremental mean abs dev from SMA. ``st``: [sum, last_i]. Matches ``numba_dev``."""
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    s = st[0]
    for j in range(last + 1, i + 1):
        if j < period - 1:
            s = np.nan
        elif j == period - 1:
            s = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
            if not ok:
                s = np.nan
        else:
            if np.isnan(s):
                s = 0.0
                ok = True
                for k in range(period):
                    v = arr[j - k]
                    if np.isnan(v):
                        ok = False
                        break
                    s += v
                if not ok:
                    s = np.nan
            else:
                old = arr[j - period]
                new = arr[j]
                if np.isnan(old) or np.isnan(new):
                    s = np.nan
                else:
                    s = s - old + new
    st[0] = s
    st[1] = float(i)
    if i < period - 1 or np.isnan(s):
        return np.nan
    mean = s / period
    md = 0.0
    for j in range(period):
        v = arr[i - j]
        if np.isnan(v):
            return np.nan
        md += abs(v - mean)
    return md / period


@numba.njit(cache=True)
def numba_mfi_inc(high, low, close, vol, length, i, st):
    """O(1) sliding Money Flow Index. ``st``: [pos, neg, last_i]. Matches ``numba_mfi``."""
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    pos = st[0]
    neg = st[1]

    for j in range(last + 1, i + 1):
        if j < length:
            pos = np.nan
            neg = np.nan
        elif j == length:
            pos = 0.0
            neg = 0.0
            ok = True
            for k in range(j - length + 1, j + 1):
                tp = (high[k] + low[k] + close[k]) / 3.0
                tp_prev = (high[k - 1] + low[k - 1] + close[k - 1]) / 3.0
                vv = vol[k]
                if np.isnan(tp) or np.isnan(tp_prev) or np.isnan(vv):
                    ok = False
                    break
                mf = tp * vv
                if tp > tp_prev:
                    pos += mf
                elif tp < tp_prev:
                    neg += mf
            if not ok:
                pos = np.nan
                neg = np.nan
        else:
            if np.isnan(pos):
                pos = 0.0
                neg = 0.0
                ok = True
                for k in range(j - length + 1, j + 1):
                    tp = (high[k] + low[k] + close[k]) / 3.0
                    tp_prev = (high[k - 1] + low[k - 1] + close[k - 1]) / 3.0
                    vv = vol[k]
                    if np.isnan(tp) or np.isnan(tp_prev) or np.isnan(vv):
                        ok = False
                        break
                    mf = tp * vv
                    if tp > tp_prev:
                        pos += mf
                    elif tp < tp_prev:
                        neg += mf
                if not ok:
                    pos = np.nan
                    neg = np.nan
            else:
                k_old = j - length
                tp = (high[k_old] + low[k_old] + close[k_old]) / 3.0
                tp_prev = (high[k_old - 1] + low[k_old - 1] + close[k_old - 1]) / 3.0
                vv = vol[k_old]
                if np.isnan(tp) or np.isnan(tp_prev) or np.isnan(vv):
                    pos = np.nan
                    neg = np.nan
                else:
                    mf = tp * vv
                    if tp > tp_prev:
                        pos -= mf
                    elif tp < tp_prev:
                        neg -= mf
                    k = j
                    tp = (high[k] + low[k] + close[k]) / 3.0
                    tp_prev = (high[k - 1] + low[k - 1] + close[k - 1]) / 3.0
                    vv = vol[k]
                    if np.isnan(tp) or np.isnan(tp_prev) or np.isnan(vv):
                        pos = np.nan
                        neg = np.nan
                    else:
                        mf = tp * vv
                        if tp > tp_prev:
                            pos += mf
                        elif tp < tp_prev:
                            neg += mf

    st[0] = pos
    st[1] = neg
    st[2] = float(i)
    if i < length or np.isnan(pos):
        return np.nan
    if neg == 0.0:
        if pos == 0.0:
            return 50.0
        return 100.0
    ratio = pos / neg
    return 100.0 - (100.0 / (1.0 + ratio))


@numba.njit(cache=True)
def numba_highestbars_inc(arr, length, i, st):
    """Amortized highestbars. ``st``: [max_val, max_idx, last_i].

    Matches :func:`numba_highestbars` / interpret: negative offset, ``-1.0``
    while ``i+1 < length`` or all-NaN; oldest extreme on ties (strict ``>``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return -1.0
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    m = st[0]
    mi = -1 if np.isnan(st[1]) else int(st[1])
    for j in range(last + 1, i + 1):
        start = j - length + 1
        if start < 0:
            start = 0
        if j == 0 or np.isnan(m) or mi < start:
            m = np.nan
            mi = -1
            for k in range(start, j + 1):
                v = arr[k]
                if np.isnan(v):
                    continue
                # strict > → oldest wins ties
                if np.isnan(m) or v > m:
                    m = v
                    mi = k
        else:
            v = arr[j]
            if np.isnan(m):
                if not np.isnan(v):
                    m = v
                    mi = j
            elif (not np.isnan(v)) and v > m:
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi) if mi >= 0 else np.nan
    st[2] = float(i)
    if i + 1 < length:
        return -1.0
    if np.isnan(m) or mi < 0:
        return -1.0
    return float(-(i - mi))


@numba.njit(cache=True)
def numba_lowestbars_inc(arr, length, i, st):
    """Amortized lowestbars. ``st``: [min_val, min_idx, last_i].

    Matches :func:`numba_lowestbars` / interpret: negative offset, ``-1.0``
    while ``i+1 < length`` or all-NaN; oldest extreme on ties (strict ``<``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return -1.0
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    m = st[0]
    mi = -1 if np.isnan(st[1]) else int(st[1])
    for j in range(last + 1, i + 1):
        start = j - length + 1
        if start < 0:
            start = 0
        if j == 0 or np.isnan(m) or mi < start:
            m = np.nan
            mi = -1
            for k in range(start, j + 1):
                v = arr[k]
                if np.isnan(v):
                    continue
                if np.isnan(m) or v < m:
                    m = v
                    mi = k
        else:
            v = arr[j]
            if np.isnan(m):
                if not np.isnan(v):
                    m = v
                    mi = j
            elif (not np.isnan(v)) and v < m:
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi) if mi >= 0 else np.nan
    st[2] = float(i)
    if i + 1 < length:
        return -1.0
    if np.isnan(m) or mi < 0:
        return -1.0
    return float(-(i - mi))


@numba.njit(cache=True)
def numba_correlation_inc(a, b, period, i, st):
    """O(1) sliding Pearson correlation. ``st``: [sa, sb, saa, sbb, sab, last_i]."""
    period = int(period)
    if period < 2 or i < 0:
        return np.nan
    if np.isnan(st[5]):
        last = -1
    else:
        last = int(st[5])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan
        st[3] = np.nan
        st[4] = np.nan
    sa = st[0]
    sb = st[1]
    saa = st[2]
    sbb = st[3]
    sab = st[4]
    n = float(period)
    for j in range(last + 1, i + 1):
        if j < period - 1:
            sa = np.nan
            sb = np.nan
            saa = np.nan
            sbb = np.nan
            sab = np.nan
        elif j == period - 1:
            sa = 0.0
            sb = 0.0
            saa = 0.0
            sbb = 0.0
            sab = 0.0
            ok = True
            for k in range(period):
                va = a[k]
                vb = b[k]
                if np.isnan(va) or np.isnan(vb):
                    ok = False
                    break
                sa += va
                sb += vb
                saa += va * va
                sbb += vb * vb
                sab += va * vb
            if not ok:
                sa = np.nan
                sb = np.nan
                saa = np.nan
                sbb = np.nan
                sab = np.nan
        else:
            if np.isnan(sa):
                sa = 0.0
                sb = 0.0
                saa = 0.0
                sbb = 0.0
                sab = 0.0
                ok = True
                for k in range(period):
                    va = a[j - k]
                    vb = b[j - k]
                    if np.isnan(va) or np.isnan(vb):
                        ok = False
                        break
                    sa += va
                    sb += vb
                    saa += va * va
                    sbb += vb * vb
                    sab += va * vb
                if not ok:
                    sa = np.nan
                    sb = np.nan
                    saa = np.nan
                    sbb = np.nan
                    sab = np.nan
            else:
                oa = a[j - period]
                ob = b[j - period]
                na_ = a[j]
                nb_ = b[j]
                if np.isnan(oa) or np.isnan(ob) or np.isnan(na_) or np.isnan(nb_):
                    sa = np.nan
                    sb = np.nan
                    saa = np.nan
                    sbb = np.nan
                    sab = np.nan
                else:
                    sa = sa - oa + na_
                    sb = sb - ob + nb_
                    saa = saa - oa * oa + na_ * na_
                    sbb = sbb - ob * ob + nb_ * nb_
                    sab = sab - oa * ob + na_ * nb_
    st[0] = sa
    st[1] = sb
    st[2] = saa
    st[3] = sbb
    st[4] = sab
    st[5] = float(i)
    if i < period - 1 or np.isnan(sa):
        return np.nan
    # Centered sums: match two-pass numba_correlation
    num = sab - sa * sb / n
    den_a = saa - sa * sa / n
    den_b = sbb - sb * sb / n
    if den_a <= 0.0 or den_b <= 0.0:
        return np.nan
    return num / np.sqrt(den_a * den_b)


@numba.njit(cache=True)
def numba_rising_inc(arr, length, i, st):
    """O(1) consecutive-rise streak. ``st``: [streak, last_i].

    Matches ``numba_rising``: True iff ``arr`` rose strictly for ``length``
    consecutive steps ending at ``i`` (needs ``i >= length``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return False
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = 0.0
    streak = 0.0 if np.isnan(st[0]) else st[0]
    for j in range(last + 1, i + 1):
        if j <= 0:
            streak = 0.0
            continue
        a = arr[j]
        b = arr[j - 1]
        if np.isnan(a) or np.isnan(b) or a <= b:
            streak = 0.0
        else:
            streak = streak + 1.0
    st[0] = streak
    st[1] = float(i)
    return i >= length and streak >= float(length)


@numba.njit(cache=True)
def numba_falling_inc(arr, length, i, st):
    """O(1) consecutive-fall streak. ``st``: [streak, last_i].

    Matches ``numba_falling``.
    """
    length = int(length)
    if length <= 0 or i < 0:
        return False
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = 0.0
    streak = 0.0 if np.isnan(st[0]) else st[0]
    for j in range(last + 1, i + 1):
        if j <= 0:
            streak = 0.0
            continue
        a = arr[j]
        b = arr[j - 1]
        if np.isnan(a) or np.isnan(b) or a >= b:
            streak = 0.0
        else:
            streak = streak + 1.0
    st[0] = streak
    st[1] = float(i)
    return i >= length and streak >= float(length)


@numba.njit(cache=True)
def numba_valuewhen_inc(cond_arr, src_arr, occ, i, st):
    """Amortized-O(1) valuewhen via ring of recent true bar indices.

    ``st`` layout (size >= 3 + occ + 1):
      [n_found, head, last_i, hist_0, ..., hist_occ]
    ``hist`` is a ring of bar indices (write at ``head % cap``).
    Matches ``numba_valuewhen`` for sequential / gap / rewind bars.
    """
    occ = int(occ)
    if occ < 0 or i < 0:
        return np.nan
    cap = occ + 1
    # Require packed hist after the 3 control slots
    if len(st) < 3 + cap:
        return numba_valuewhen(cond_arr, src_arr, occ, i)

    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = 0.0
        st[1] = 0.0

    n_found = 0 if np.isnan(st[0]) else int(st[0])
    head = 0 if np.isnan(st[1]) else int(st[1])

    for j in range(last + 1, i + 1):
        c = cond_arr[j]
        if np.isnan(c) or c == 0.0:
            continue
        st[3 + (head % cap)] = float(j)
        head += 1
        if n_found < cap:
            n_found += 1

    st[0] = float(n_found)
    st[1] = float(head)
    st[2] = float(i)

    if n_found <= occ:
        return np.nan
    # occ-th most recent true: head-1-occ
    bar_i = int(st[3 + ((head - 1 - occ) % cap)])
    return src_arr[bar_i]


@numba.njit(cache=True)
def numba_running_max_inc(arr, i, st):
    """O(1) all-time max of ``arr[0..i]``. ``st``: [max_val, last_i].

    Matches ``numba_highest(arr, i+1, i)`` (NaN ignored when a finite exists).
    """
    if i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    m = st[0]
    for j in range(last + 1, i + 1):
        v = arr[j]
        if np.isnan(m) or (not np.isnan(v) and v > m):
            m = v
    st[0] = m
    st[1] = float(i)
    return m


@numba.njit(cache=True)
def numba_running_min_inc(arr, i, st):
    """O(1) all-time min of ``arr[0..i]``. ``st``: [min_val, last_i].

    Matches ``numba_lowest(arr, i+1, i)``.
    """
    if i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1
        st[0] = np.nan
    m = st[0]
    for j in range(last + 1, i + 1):
        v = arr[j]
        if np.isnan(m) or (not np.isnan(v) and v < m):
            m = v
    st[0] = m
    st[1] = float(i)
    return m


@numba.njit(cache=True)
def numba_swma(arr, i):
    """Symmetric 4-period WMA: weights 1, 2, 2, 1 over 6 (TV ``ta.swma``).

    O(1) per bar — no sliding state required. Needs ``i >= 3``.
    """
    if i < 3:
        return np.nan
    a = arr[i - 3]
    b = arr[i - 2]
    c = arr[i - 1]
    d = arr[i]
    if np.isnan(a) or np.isnan(b) or np.isnan(c) or np.isnan(d):
        return np.nan
    return (a + 2.0 * b + 2.0 * c + d) / 6.0


@numba.njit(cache=True)
def numba_dema(arr, period, i):
    """Double EMA: ``2*EMA(src) - EMA(EMA(src))`` with SMA seed (matches ``numba_ema``).

    First valid bar is ``i >= 2*period - 2``.
    """
    period = int(period)
    if period <= 0 or i < 2 * period - 2:
        return np.nan
    alpha = 2.0 / (period + 1.0)
    e1 = np.empty(i + 1, dtype=np.float64)
    s = 0.0
    for k in range(period):
        v = arr[k]
        if np.isnan(v):
            return np.nan
        s += v
    e1[period - 1] = s / period
    for j in range(period, i + 1):
        v = arr[j]
        if np.isnan(v):
            return np.nan
        e1[j] = alpha * v + (1.0 - alpha) * e1[j - 1]
    s2 = 0.0
    for k in range(period):
        s2 += e1[period - 1 + k]
    e2 = s2 / period
    for j in range(2 * period - 1, i + 1):
        e2 = alpha * e1[j] + (1.0 - alpha) * e2
    return 2.0 * e1[i] - e2


@numba.njit(cache=True)
def numba_dema_inc(arr, period, i, st, e1_raw):
    """Amortized O(1) DEMA. ``st``: [e1, e2, last_i]; ``e1_raw`` intermediate EMA series.

    Matches ``numba_dema`` (SMA-seed nested EMAs). Catch-up / rewind safe.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[2]):
        last = -1
    else:
        last = int(st[2])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
    alpha = 2.0 / (period + 1.0)
    e1 = st[0]
    e2 = st[1]
    seed2 = 2 * period - 2
    for j in range(last + 1, i + 1):
        if j == period - 1:
            s = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
            e1 = s / period if ok else np.nan
        elif j >= period:
            v = arr[j]
            if np.isnan(v) or np.isnan(e1):
                e1 = np.nan
            else:
                e1 = alpha * v + (1.0 - alpha) * e1
        else:
            e1 = np.nan
        e1_raw[j] = e1

        if j == seed2:
            s2 = 0.0
            ok2 = True
            for k in range(period):
                v = e1_raw[period - 1 + k]
                if np.isnan(v):
                    ok2 = False
                    break
                s2 += v
            e2 = s2 / period if ok2 else np.nan
        elif j > seed2:
            if np.isnan(e1) or np.isnan(e2):
                e2 = np.nan
            else:
                e2 = alpha * e1 + (1.0 - alpha) * e2
        else:
            e2 = np.nan
    st[0] = e1
    st[1] = e2
    st[2] = float(i)
    if i < seed2 or np.isnan(e1) or np.isnan(e2):
        return np.nan
    return 2.0 * e1 - e2


@numba.njit(cache=True)
def numba_tema(arr, period, i):
    """Triple EMA: ``3*e1 - 3*e2 + e3`` with SMA seed (matches ``numba_ema``).

    First valid bar is ``i >= 3*period - 3``.
    """
    period = int(period)
    if period <= 0 or i < 3 * period - 3:
        return np.nan
    alpha = 2.0 / (period + 1.0)
    n = i + 1
    e1 = np.empty(n, dtype=np.float64)
    e2 = np.empty(n, dtype=np.float64)
    s = 0.0
    for k in range(period):
        v = arr[k]
        if np.isnan(v):
            return np.nan
        s += v
    e1[period - 1] = s / period
    for j in range(period, n):
        v = arr[j]
        if np.isnan(v):
            return np.nan
        e1[j] = alpha * v + (1.0 - alpha) * e1[j - 1]
    s2 = 0.0
    for k in range(period):
        s2 += e1[period - 1 + k]
    e2[2 * period - 2] = s2 / period
    for j in range(2 * period - 1, n):
        e2[j] = alpha * e1[j] + (1.0 - alpha) * e2[j - 1]
    s3 = 0.0
    for k in range(period):
        s3 += e2[2 * period - 2 + k]
    e3 = s3 / period
    for j in range(3 * period - 2, n):
        e3 = alpha * e2[j] + (1.0 - alpha) * e3
    return 3.0 * e1[i] - 3.0 * e2[i] + e3


@numba.njit(cache=True)
def numba_tema_inc(arr, period, i, st, e1_raw, e2_raw):
    """Amortized O(1) TEMA. ``st``: [e1, e2, e3, last_i]; two intermediate series.

    Matches ``numba_tema``. Catch-up / rewind safe.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return np.nan
    if np.isnan(st[3]):
        last = -1
    else:
        last = int(st[3])
    if i < last:
        last = -1
        st[0] = np.nan
        st[1] = np.nan
        st[2] = np.nan
    alpha = 2.0 / (period + 1.0)
    e1 = st[0]
    e2 = st[1]
    e3 = st[2]
    seed2 = 2 * period - 2
    seed3 = 3 * period - 3
    for j in range(last + 1, i + 1):
        if j == period - 1:
            s = 0.0
            ok = True
            for k in range(period):
                v = arr[k]
                if np.isnan(v):
                    ok = False
                    break
                s += v
            e1 = s / period if ok else np.nan
        elif j >= period:
            v = arr[j]
            if np.isnan(v) or np.isnan(e1):
                e1 = np.nan
            else:
                e1 = alpha * v + (1.0 - alpha) * e1
        else:
            e1 = np.nan
        e1_raw[j] = e1

        if j == seed2:
            s2 = 0.0
            ok2 = True
            for k in range(period):
                v = e1_raw[period - 1 + k]
                if np.isnan(v):
                    ok2 = False
                    break
                s2 += v
            e2 = s2 / period if ok2 else np.nan
        elif j > seed2:
            if np.isnan(e1) or np.isnan(e2):
                e2 = np.nan
            else:
                e2 = alpha * e1 + (1.0 - alpha) * e2
        else:
            e2 = np.nan
        e2_raw[j] = e2

        if j == seed3:
            s3 = 0.0
            ok3 = True
            for k in range(period):
                v = e2_raw[seed2 + k]
                if np.isnan(v):
                    ok3 = False
                    break
                s3 += v
            e3 = s3 / period if ok3 else np.nan
        elif j > seed3:
            if np.isnan(e2) or np.isnan(e3):
                e3 = np.nan
            else:
                e3 = alpha * e2 + (1.0 - alpha) * e3
        else:
            e3 = np.nan
    st[0] = e1
    st[1] = e2
    st[2] = e3
    st[3] = float(i)
    if i < seed3 or np.isnan(e1) or np.isnan(e2) or np.isnan(e3):
        return np.nan
    return 3.0 * e1 - 3.0 * e2 + e3


# ---------------------------------------------------------------------------
# Round 6: ADX / DMI / Supertrend / ALMA_inc (match current interpret oracle)
# ---------------------------------------------------------------------------

@numba.njit(cache=True)
def _rma_step4(st, base, x, period):
    """One Wilder RMA sample; ``st[base:base+4]`` = [rma, seed_sum, seed_count, phase].

    phase: 0 = not started, 1 = seeding, 2 = seeded.
    Matches interpret ``_rma_state_step`` (skip nan until started; hold on nan).
    """
    period = int(period)
    rma = st[base + 0]
    seed_sum = st[base + 1]
    seed_count = st[base + 2]
    phase = st[base + 3]
    alpha = 1.0 / float(period)

    if phase < 1.5:
        if np.isnan(x):
            st[base + 0] = np.nan
            return np.nan
        if phase < 0.5:
            phase = 1.0
            seed_sum = 0.0
            seed_count = 0.0
        seed_sum = seed_sum + x
        seed_count = seed_count + 1.0
        if seed_count < float(period):
            st[base + 0] = np.nan
            st[base + 1] = seed_sum
            st[base + 2] = seed_count
            st[base + 3] = phase
            return np.nan
        rma = seed_sum / seed_count
        st[base + 0] = rma
        st[base + 1] = 0.0
        st[base + 2] = 0.0
        st[base + 3] = 2.0
        return rma

    if np.isnan(x):
        return rma
    rma = alpha * x + (1.0 - alpha) * rma
    st[base + 0] = rma
    return rma


@numba.njit(cache=True)
def _rma_reset4(st, base):
    st[base + 0] = np.nan
    st[base + 1] = 0.0
    st[base + 2] = 0.0
    st[base + 3] = 0.0


@numba.njit(cache=True)
def _rma_series_full(src, period, n):
    """Full-series Wilder RMA matching interpret ``_rma`` (nan-aware seed)."""
    out = np.empty(n, dtype=np.float64)
    period = int(period)
    if period <= 0 or n <= 0:
        for i in range(n):
            out[i] = np.nan
        return out
    alpha = 1.0 / float(period)
    first_valid = -1
    for i in range(n):
        if not np.isnan(src[i]):
            first_valid = i
            break
    if first_valid < 0:
        for i in range(n):
            out[i] = np.nan
        return out
    for i in range(first_valid):
        out[i] = np.nan
    # seed window [first_valid, first_valid+period); filter nans like full path
    s = 0.0
    cnt = 0
    end = first_valid + period
    if end > n:
        for i in range(first_valid, n):
            out[i] = np.nan
        return out
    for i in range(first_valid, end):
        v = src[i]
        if not np.isnan(v):
            s += v
            cnt += 1
    if cnt == 0:
        for i in range(n):
            out[i] = np.nan
        return out
    current = s / float(cnt)
    for i in range(first_valid, first_valid + period - 1):
        out[i] = np.nan
    seed_idx = first_valid + period - 1
    out[seed_idx] = current
    for i in range(first_valid + period, n):
        v = src[i]
        if np.isnan(v):
            out[i] = current
        else:
            current = alpha * v + (1.0 - alpha) * current
            out[i] = current
    return out


@numba.njit(cache=True)
def numba_adx(high, low, close, period, i):
    """ADX at bar ``i`` matching interpret ``_adx`` / ``_adx_inc_update``.

    nan-first DM; Wilder RMA of TR/+DM/-DM and of DX. Returns 0.0 while
    ``i+1 < period`` or ADX has not seeded yet (not nan).
    """
    period = int(period)
    if period <= 0 or i < 0:
        return 0.0
    n = i + 1
    if n < period:
        return 0.0

    tr = np.empty(n, dtype=np.float64)
    plus_dm = np.empty(n, dtype=np.float64)
    minus_dm = np.empty(n, dtype=np.float64)
    tr[0] = np.nan
    plus_dm[0] = np.nan
    minus_dm[0] = np.nan
    for j in range(1, n):
        hj = high[j]
        lj = low[j]
        pc = close[j - 1]
        tr[j] = max(hj - lj, abs(hj - pc), abs(lj - pc))
        high_diff = hj - high[j - 1]
        low_diff = low[j - 1] - lj
        if high_diff > low_diff and high_diff > 0.0:
            plus_dm[j] = high_diff
        else:
            plus_dm[j] = 0.0
        if low_diff > high_diff and low_diff > 0.0:
            minus_dm[j] = low_diff
        else:
            minus_dm[j] = 0.0

    atr = _rma_series_full(tr, period, n)
    pd = _rma_series_full(plus_dm, period, n)
    md = _rma_series_full(minus_dm, period, n)

    # ATR all-nan → 0.0
    any_atr = False
    for j in range(n):
        if not np.isnan(atr[j]) and atr[j] != 0.0:
            any_atr = True
            break
        if not np.isnan(atr[j]):
            any_atr = True
            break
    if not any_atr:
        return 0.0

    dx = np.empty(n, dtype=np.float64)
    for j in range(n):
        a = atr[j]
        p = pd[j]
        m = md[j]
        if np.isnan(a) or np.isnan(p) or np.isnan(m):
            dx[j] = np.nan
        else:
            plus_di = 100.0 * p / a if a != 0.0 else 0.0
            minus_di = 100.0 * m / a if a != 0.0 else 0.0
            denom = plus_di + minus_di
            if denom == 0.0:
                dx[j] = 0.0
            else:
                dx[j] = 100.0 * abs(plus_di - minus_di) / denom

    adx_s = _rma_series_full(dx, period, n)
    for j in range(n - 1, -1, -1):
        if not np.isnan(adx_s[j]):
            return adx_s[j]
    return 0.0


@numba.njit(cache=True)
def numba_adx_inc(high, low, close, period, i, st):
    """Amortized O(1) ADX. ``st`` length 22:

    [0:4] rma_tr, [4:8] rma_pdm, [8:12] rma_mdm, [12:16] rma_dx,
    [16] prev_h, [17] prev_l, [18] prev_c, [19] n_seen, [20] last_i, [21] value.
    """
    period = int(period)
    if period <= 0 or i < 0:
        return 0.0

    if np.isnan(st[20]):
        last = -1
    else:
        last = int(st[20])
    if i < last:
        last = -1
    if last < 0:
        for b in (0, 4, 8, 12):
            _rma_reset4(st, b)
        st[16] = np.nan
        st[17] = np.nan
        st[18] = np.nan
        st[19] = 0.0
        st[21] = 0.0

    for j in range(last + 1, i + 1):
        hj = high[j]
        lj = low[j]
        cj = close[j]
        prev_h = st[16]
        prev_l = st[17]
        prev_c = st[18]
        st[16] = hj
        st[17] = lj
        st[18] = cj
        st[19] = st[19] + 1.0
        n = int(st[19])

        if np.isnan(prev_c) or np.isnan(prev_h) or np.isnan(prev_l):
            tr = np.nan
            plus_dm = np.nan
            minus_dm = np.nan
        else:
            tr = max(hj - lj, abs(hj - prev_c), abs(lj - prev_c))
            high_diff = hj - prev_h
            low_diff = prev_l - lj
            if high_diff > low_diff and high_diff > 0.0:
                plus_dm = high_diff
            else:
                plus_dm = 0.0
            if low_diff > high_diff and low_diff > 0.0:
                minus_dm = low_diff
            else:
                minus_dm = 0.0

        atr_v = _rma_step4(st, 0, tr, period)
        pd = _rma_step4(st, 4, plus_dm, period)
        md = _rma_step4(st, 8, minus_dm, period)

        if n < period:
            st[21] = 0.0
            continue

        # ATR not seeded yet
        if st[3] < 1.5:
            st[21] = 0.0
            continue

        if np.isnan(atr_v) or np.isnan(pd) or np.isnan(md):
            dx_in = np.nan
        else:
            plus_di = 100.0 * pd / atr_v if atr_v != 0.0 else 0.0
            minus_di = 100.0 * md / atr_v if atr_v != 0.0 else 0.0
            denom = plus_di + minus_di
            if denom == 0.0:
                dx_in = 0.0
            else:
                dx_in = 100.0 * abs(plus_di - minus_di) / denom

        adx_v = _rma_step4(st, 12, dx_in, period)
        if np.isnan(adx_v):
            st[21] = 0.0
        else:
            st[21] = adx_v

    st[20] = float(i)
    return st[21]


@numba.njit(cache=True)
def numba_dmi(high, low, close, di_len, adx_smooth, i):
    """DMI at bar ``i`` → (+DI, -DI, ADX) matching interpret BasicIndicators.

    +DI/-DI use **0-first** DM + RMA(di_len); ADX uses nan-first ``numba_adx``.
    """
    di_len = int(di_len)
    adx_smooth = int(adx_smooth)
    if di_len < 1 or i < 0:
        return np.nan, np.nan, 0.0

    n = i + 1
    tr = np.empty(n, dtype=np.float64)
    plus_dm = np.empty(n, dtype=np.float64)
    minus_dm = np.empty(n, dtype=np.float64)
    tr[0] = np.nan
    plus_dm[0] = 0.0
    minus_dm[0] = 0.0
    for j in range(1, n):
        hj = high[j]
        lj = low[j]
        pc = close[j - 1]
        tr[j] = max(hj - lj, abs(hj - pc), abs(lj - pc))
        high_diff = hj - high[j - 1]
        low_diff = low[j - 1] - lj
        if high_diff > low_diff and high_diff > 0.0:
            plus_dm[j] = high_diff
        else:
            plus_dm[j] = 0.0
        if low_diff > high_diff and low_diff > 0.0:
            minus_dm[j] = low_diff
        else:
            minus_dm[j] = 0.0

    atr = _rma_series_full(tr, di_len, n)
    pd = _rma_series_full(plus_dm, di_len, n)
    md = _rma_series_full(minus_dm, di_len, n)
    a = atr[i]
    p = pd[i]
    m = md[i]
    if np.isnan(a) or np.isnan(p) or np.isnan(m):
        plus_di = np.nan
        minus_di = np.nan
    elif a == 0.0:
        plus_di = 0.0
        minus_di = 0.0
    else:
        plus_di = 100.0 * p / a
        minus_di = 100.0 * m / a

    adx = numba_adx(high, low, close, adx_smooth, i)
    return plus_di, minus_di, adx


@numba.njit(cache=True)
def numba_dmi_inc(high, low, close, di_len, adx_smooth, i, st):
    """Amortized DMI. ``st`` length 40:

    [0:22] ADX sub-state (same layout as ``numba_adx_inc``),
    [22:26] DI rma_tr, [26:30] DI rma_pdm, [30:34] DI rma_mdm,
    [34] DI prev_h, [35] DI prev_l, [36] DI prev_c,
    [37] last_i, [38] plus_di, [39] minus_di.
    """
    di_len = int(di_len)
    adx_smooth = int(adx_smooth)
    if di_len < 1 or i < 0:
        return np.nan, np.nan, 0.0

    if np.isnan(st[37]):
        last = -1
    else:
        last = int(st[37])
    if i < last:
        last = -1
    if last < 0:
        for b in (0, 4, 8, 12, 22, 26, 30):
            _rma_reset4(st, b)
        st[16] = np.nan
        st[17] = np.nan
        st[18] = np.nan
        st[19] = 0.0
        st[20] = np.nan
        st[21] = 0.0
        st[34] = np.nan
        st[35] = np.nan
        st[36] = np.nan
        st[38] = np.nan
        st[39] = np.nan

    for j in range(last + 1, i + 1):
        hj = high[j]
        lj = low[j]
        cj = close[j]

        # --- DI path (0-first DM) ---
        prev_h = st[34]
        prev_l = st[35]
        prev_c = st[36]
        st[34] = hj
        st[35] = lj
        st[36] = cj
        if np.isnan(prev_h) or np.isnan(prev_l) or np.isnan(prev_c):
            tr = np.nan
            plus_dm = 0.0
            minus_dm = 0.0
        else:
            tr = max(hj - lj, abs(hj - prev_c), abs(lj - prev_c))
            high_diff = hj - prev_h
            low_diff = prev_l - lj
            if high_diff > low_diff and high_diff > 0.0:
                plus_dm = high_diff
            else:
                plus_dm = 0.0
            if low_diff > high_diff and low_diff > 0.0:
                minus_dm = low_diff
            else:
                minus_dm = 0.0

        atr_v = _rma_step4(st, 22, tr, di_len)
        pd = _rma_step4(st, 26, plus_dm, di_len)
        md = _rma_step4(st, 30, minus_dm, di_len)

        if np.isnan(atr_v) or np.isnan(pd) or np.isnan(md):
            if np.isnan(atr_v):
                plus_di = np.nan
                minus_di = np.nan
            elif atr_v == 0.0:
                plus_di = 0.0
                minus_di = 0.0
            else:
                pd_f = 0.0 if np.isnan(pd) else pd
                md_f = 0.0 if np.isnan(md) else md
                plus_di = 100.0 * pd_f / atr_v
                minus_di = 100.0 * md_f / atr_v
        else:
            if atr_v == 0.0:
                plus_di = 0.0
                minus_di = 0.0
            else:
                plus_di = 100.0 * pd / atr_v
                minus_di = 100.0 * md / atr_v

        st[38] = plus_di
        st[39] = minus_di

        # --- ADX path (nan-first) — mirror numba_adx_inc one bar ---
        prev_h2 = st[16]
        prev_l2 = st[17]
        prev_c2 = st[18]
        st[16] = hj
        st[17] = lj
        st[18] = cj
        st[19] = st[19] + 1.0
        n = int(st[19])

        if np.isnan(prev_c2) or np.isnan(prev_h2) or np.isnan(prev_l2):
            tr2 = np.nan
            pdm2 = np.nan
            mdm2 = np.nan
        else:
            tr2 = max(hj - lj, abs(hj - prev_c2), abs(lj - prev_c2))
            high_diff2 = hj - prev_h2
            low_diff2 = prev_l2 - lj
            if high_diff2 > low_diff2 and high_diff2 > 0.0:
                pdm2 = high_diff2
            else:
                pdm2 = 0.0
            if low_diff2 > high_diff2 and low_diff2 > 0.0:
                mdm2 = low_diff2
            else:
                mdm2 = 0.0

        atr2 = _rma_step4(st, 0, tr2, adx_smooth)
        pd2 = _rma_step4(st, 4, pdm2, adx_smooth)
        md2 = _rma_step4(st, 8, mdm2, adx_smooth)

        if n < adx_smooth:
            st[21] = 0.0
        elif st[3] < 1.5:
            st[21] = 0.0
        else:
            if np.isnan(atr2) or np.isnan(pd2) or np.isnan(md2):
                dx_in = np.nan
            else:
                pdi = 100.0 * pd2 / atr2 if atr2 != 0.0 else 0.0
                mdi = 100.0 * md2 / atr2 if atr2 != 0.0 else 0.0
                denom = pdi + mdi
                if denom == 0.0:
                    dx_in = 0.0
                else:
                    dx_in = 100.0 * abs(pdi - mdi) / denom
            adx_v = _rma_step4(st, 12, dx_in, adx_smooth)
            if np.isnan(adx_v):
                st[21] = 0.0
            else:
                st[21] = adx_v

    st[20] = float(i)
    st[37] = float(i)
    return st[38], st[39], st[21]


@numba.njit(cache=True)
def numba_supertrend(high, low, close, factor, atr_period, i):
    """Simplified Supertrend matching interpret BasicIndicators (not TV ratchet).

    Returns ``(supertrend, direction)`` with direction -1 (up) / +1 (down).
    ATR via ``numba_atr``; nan ATR treated as 0.0.
    """
    atr_period = int(atr_period)
    atr_v = numba_atr(high, low, close, atr_period, i)
    if np.isnan(atr_v):
        atr_v = 0.0
    mid = (high[i] + low[i]) * 0.5
    upper = mid + factor * atr_v
    lower = mid - factor * atr_v
    if close[i] >= mid:
        direction = -1.0
        return lower, direction
    direction = 1.0
    return upper, direction


@numba.njit(cache=True)
def numba_supertrend_inc(high, low, close, factor, atr_period, i, st):
    """Incremental Supertrend. ``st`` length 2 — shared with ``numba_atr_inc``."""
    atr_period = int(atr_period)
    atr_v = numba_atr_inc(high, low, close, atr_period, i, st)
    if np.isnan(atr_v):
        atr_v = 0.0
    mid = (high[i] + low[i]) * 0.5
    upper = mid + factor * atr_v
    lower = mid - factor * atr_v
    if close[i] >= mid:
        return lower, -1.0
    return upper, 1.0


@numba.njit(cache=True)
def numba_alma_inc(arr, length, offset, sigma, i, st):
    """ALMA with one-time Gaussian weight precompute in ``st``.

    ``st`` layout (length L = int(length)):
    [0] wsum, [1] last_i, [2 .. 1+L] weights for k=0..L-1 (oldest→newest).
    Requires ``len(st) >= 2 + L``. Matches ``numba_alma`` / interpret ALMA.
    """
    length = int(length)
    if length <= 0 or i < 0:
        return np.nan
    if np.isnan(st[1]):
        last = -1
    else:
        last = int(st[1])
    if i < last:
        last = -1

    # (re)build weights when uninitialized (wsum nan) or after rewind
    if np.isnan(st[0]) or last < 0:
        if sigma == 0.0:
            st[0] = np.nan
            st[1] = float(i)
            return np.nan
        m = offset * (length - 1)
        s = length / sigma
        s2 = 2.0 * s * s
        wsum = 0.0
        for k in range(length):
            d = float(k) - m
            w = np.exp(-(d * d) / s2)
            st[2 + k] = w
            wsum += w
        st[0] = wsum

    if i < length - 1:
        st[1] = float(i)
        return np.nan

    wsum = st[0]
    if wsum == 0.0 or np.isnan(wsum):
        st[1] = float(i)
        return np.nan

    total = 0.0
    for k in range(length):
        v = arr[i - length + 1 + k]
        if np.isnan(v):
            st[1] = float(i)
            return np.nan
        total += v * st[2 + k]
    st[1] = float(i)
    return total / wsum


@numba.njit(cache=True)
def numba_median(arr, length, i):
    """Rolling median of last ``length`` bars ending at ``i``.

    Matches interpret ``_median`` / ``statistics.median`` on non-nan window
    samples: odd count → middle; even → mean of two middle. Warm-up /
    empty valid set → nan.
    """
    length = int(length)
    if length <= 0 or i < length - 1:
        return np.nan
    window = np.empty(length, dtype=np.float64)
    count = 0
    for j in range(length):
        v = arr[i - j]
        if not np.isnan(v):
            window[count] = v
            count += 1
    if count == 0:
        return np.nan
    # insertion sort first ``count`` elements
    for a in range(1, count):
        key = window[a]
        b = a - 1
        while b >= 0 and window[b] > key:
            window[b + 1] = window[b]
            b -= 1
        window[b + 1] = key
    if count % 2 == 1:
        return window[count // 2]
    mid = count // 2
    return 0.5 * (window[mid - 1] + window[mid])


@numba.njit(cache=True)
def numba_wpr(high, low, close, period, i):
    """Williams %R at bar ``i`` (TV ``ta.wpr``).

    Matches interpret ``_wpr``: warm-up / non-positive period → 0.0;
    flat high/low range → 0.0; else ``-100 * (HH - close) / (HH - LL)``.
    """
    period = int(period)
    if period <= 0 or i < period - 1:
        return 0.0
    hh = high[i]
    ll = low[i]
    for j in range(1, period):
        h = high[i - j]
        l_ = low[i - j]
        if h > hh:
            hh = h
        if l_ < ll:
            ll = l_
    c = close[i]
    if hh == ll:
        return 0.0
    return -100.0 * (hh - c) / (hh - ll)


@numba.njit(cache=True)
def numba_cmo(arr, length, i):
    """Chande Momentum Oscillator over ``length`` changes ending at ``i``.

    Matches interpret ``_builtin_ta_cmo``: needs ``length+1`` samples
    (``i >= length``); sums up/down moves; zero denom → 0.0.
    """
    length = int(length)
    if length <= 0 or i < length:
        return np.nan
    up = 0.0
    down = 0.0
    # length diffs over window arr[i-length] .. arr[i]
    for j in range(i - length + 1, i + 1):
        a = arr[j - 1]
        b = arr[j]
        if np.isnan(a) or np.isnan(b):
            continue
        diff = b - a
        if diff > 0.0:
            up += diff
        else:
            down += -diff
    denom = up + down
    if denom == 0.0:
        return 0.0
    return 100.0 * (up - down) / denom


@numba.njit(cache=True)
def numba_bbw(arr, period, mult, i):
    """Bollinger Band Width: ``(upper - lower) / middle``.

    Matches interpret ``_builtin_ta_bbw`` (zero / nan middle → nan).
    ``numba_bb`` returns ``(upper, middle, lower)``.
    """
    upper, mid, lower = numba_bb(arr, period, mult, i)
    if np.isnan(mid) or mid == 0.0:
        return np.nan
    return (upper - lower) / mid


@numba.njit(cache=True)
def numba_bbw_inc(arr, period, mult, i, st):
    """Incremental BBW. ``st`` shared with ``numba_bb_inc`` (sum/sumsq/last_i)."""
    upper, mid, lower = numba_bb_inc(arr, period, mult, i, st)
    if np.isnan(mid) or mid == 0.0:
        return np.nan
    return (upper - lower) / mid


def array_range(arr):
    """Pine ``array.range(id)`` — max − min of numeric elements; empty → na.

    Not Python ``range`` / ``list(range(...))``. Used by compile object-mode
    so ``float_range / n`` never becomes ``list / int``.
    """
    if arr is None:
        return np.nan
    if not isinstance(arr, (list, tuple, np.ndarray)) and not hasattr(arr, "__iter__"):
        return np.nan
    if isinstance(arr, (float, int, np.floating, np.integer, bool)):
        return np.nan
    lo = safe_min(arr)
    hi = safe_max(arr)
    if lo != lo or hi != hi:  # NaN
        return np.nan
    return hi - lo



# ---------------------------------------------------------------------------
# Calendar / timestamp (njit-safe; matches util.time_parts + TV overflow style)
# ---------------------------------------------------------------------------


@numba.njit(cache=True)
def numba_days_from_civil(y, m, d):
    """Days since Unix epoch for civil y-m-d (Howard Hinnant algorithm)."""
    y = y - (1 if m <= 2 else 0)
    era = y // 400 if y >= 0 else (y - 399) // 400
    yoe = y - era * 400
    mp = m - 3 if m > 2 else m + 9
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


@numba.njit(cache=True)
def numba_timestamp(y, m, d, h=0.0, mi=0.0, s=0.0):
    """Unix epoch ms from calendar components with month/day overflow.

    Matches TradingView ``timestamp(year, month, day, hour, minute, second)``
    enough for TTM windows (``dayofmonth + 27``, ``month=0``, …). Timezone is UTC.
    """
    yi = int(y) if y == y else 1970  # NaN → epoch
    mo = int(m) if m == m else 1
    di = int(d) if d == d else 1
    hi = int(h) if h == h else 0
    mni = int(mi) if mi == mi else 0
    si = int(s) if s == s else 0
    # Normalize month into 1..12 with year carry (month=0 → Dec prior year)
    while mo > 12:
        mo -= 12
        yi += 1
    while mo < 1:
        mo += 12
        yi -= 1
    if yi < 1:
        yi = 1
    if yi > 9999:
        yi = 9999
    # day/hour/min/sec may overflow; fold into epoch days + rem seconds
    total_sec = (di - 1) * 86400 + hi * 3600 + mni * 60 + si
    add_days = total_sec // 86400
    rem = total_sec - add_days * 86400
    if rem < 0:
        add_days -= 1
        rem += 86400
    base_days = numba_days_from_civil(yi, mo, 1)
    epoch_days = base_days + add_days
    return float(epoch_days * 86400000 + rem * 1000)


@numba.njit(cache=True)
def numba_utc_parts(ms):
    """Return (year, month, dayofmonth, hour, minute, second, dayofweek).

    dayofweek is Pine-style: 1=Sunday … 7=Saturday.
    """
    # NaN / non-finite → epoch
    if ms != ms:
        t = 0
    else:
        t = int(ms) // 1000
    if t < -62167219200:
        t = -62167219200
    elif t > 253402300799:
        t = 253402300799

    days = t // 86400
    rem = t - days * 86400
    if rem < 0:
        days -= 1
        rem += 86400
    hour = rem // 3600
    rem = rem - hour * 3600
    minute = rem // 60
    second = rem - minute * 60

    # Epoch day 0 (1970-01-01) was Thursday. Python weekday: Mon=0 … Sun=6.
    weekday = (days + 3) % 7  # 0=Mon … 6=Sun
    dayofweek = ((weekday + 1) % 7) + 1  # Pine: 1=Sun … 7=Sat

    z = days + 719468
    era = z // 146097 if z >= 0 else (z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + 3 if mp < 10 else mp - 9
    year = y + (1 if month <= 2 else 0)

    return (
        float(year),
        float(month),
        float(day),
        float(hour),
        float(minute),
        float(second),
        float(dayofweek),
    )


@numba.njit(cache=True)
def numba_synthetic_time(n_bars):
    """Default bar-open times when host does not pass a time array (ms).

    ``bar_index * 60_000`` — keeps unit tests / pure compile callers stable.
    Runtime hosts should pass real OHLCV timestamps instead.
    """
    out = np.empty(n_bars, dtype=np.float64)
    for i in range(n_bars):
        out[i] = float(i) * 60000.0
    return out
