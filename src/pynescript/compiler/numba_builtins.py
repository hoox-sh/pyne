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

"""Numba-compatible builtins used by CompilerVisitor-generated code."""

from __future__ import annotations

import numpy as np
import numba


@numba.njit(cache=True)
def numba_sma(arr, period, i):
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
    period = int(period)
    if period <= 0 or i < period - 1:
        return np.nan
    alpha = 2.0 / (period + 1.0)
    # Seed with SMA over first `period` bars, then EMA forward to i
    sum_val = 0.0
    for j in range(period):
        sum_val += arr[j]
    ema = sum_val / period
    for j in range(period, i + 1):
        ema = alpha * arr[j] + (1.0 - alpha) * ema
    return ema


@numba.njit(cache=True)
def numba_rma(arr, period, i):
    period = int(period)
    """Wilder RMA: seed = mean of first ``period`` samples, then recursive."""
    if period <= 0 or i < period - 1:
        return np.nan
    s = 0.0
    for j in range(period):
        s += arr[j]
    rma = s / period
    alpha = 1.0 / period
    for j in range(period, i + 1):
        rma = alpha * arr[j] + (1.0 - alpha) * rma
    return rma


@numba.njit(cache=True)
def numba_rsi(arr, period, i):
    period = int(period)
    if period <= 0 or i < period:
        return np.nan
    gain = 0.0
    loss = 0.0
    for j in range(i - period + 1, i + 1):
        delta = arr[j] - arr[j - 1]
        if delta >= 0.0:
            gain += delta
        else:
            loss -= delta
    avg_gain = gain / period
    avg_loss = loss / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@numba.njit(cache=True)
def numba_highest(arr, period, i):
    period = int(period)
    if period <= 0:
        return np.nan
    start = i - period + 1
    if start < 0:
        start = 0
    m = arr[start]
    for j in range(start + 1, i + 1):
        if arr[j] > m or np.isnan(m):
            m = arr[j]
    return m


@numba.njit(cache=True)
def numba_lowest(arr, period, i):
    period = int(period)
    if period <= 0:
        return np.nan
    start = i - period + 1
    if start < 0:
        start = 0
    m = arr[start]
    for j in range(start + 1, i + 1):
        if arr[j] < m or np.isnan(m):
            m = arr[j]
    return m


@numba.njit(cache=True)
def numba_stdev(arr, period, i):
    period = int(period)
    """Sample standard deviation (n-1) over last ``period`` bars ending at ``i``."""
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
    period = int(period)
    """ATR matching interpret path: mean(TR) while warming; else EMA-of-TR.

    EMA seeds with the first TR value (same as interpret ``_ema``), not SMA.
    """
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
def numba_bb(arr, period, mult, i):
    period = int(period)
    """Return (upper, middle, lower) Bollinger bands."""
    mid = numba_sma(arr, period, i)
    sd = numba_stdev(arr, period, i)
    if np.isnan(mid) or np.isnan(sd):
        return np.nan, np.nan, np.nan
    return mid + mult * sd, mid, mid - mult * sd


@numba.njit(cache=True)
def numba_macd(arr, fast, slow, signal, i):
    fast = int(fast)
    slow = int(slow)
    signal = int(signal)
    """Return (macd, signal, hist) at bar ``i`` in a single O(i) pass.

    Fast/slow EMAs use SMA seed (same as ``numba_ema``). Signal uses
    first-value seed on the MACD line. Must not nest per-bar EMA rebuilds
    (that was O(n³) and hung multi-thousand-bar compiles).
    """
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
    if np.isnan(val):
        return replacement
    return val


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
    length = int(length)
    """Bars since highest value in window (0 = current is highest).

    On ties, prefers the most recent bar (smallest offset).
    """
    if length <= 0:
        return np.nan
    start = i - length + 1
    if start < 0:
        start = 0
    best = arr[i]
    best_off = 0
    for j in range(1, i - start + 1):
        v = arr[i - j]
        if np.isnan(best) or (not np.isnan(v) and v > best):
            best = v
            best_off = j
    if np.isnan(best):
        return np.nan
    return float(best_off)


@numba.njit(cache=True)
def numba_lowestbars(arr, length, i):
    length = int(length)
    """Bars since lowest value in window (0 = current is lowest).

    On ties, prefers the most recent bar (smallest offset).
    """
    if length <= 0:
        return np.nan
    start = i - length + 1
    if start < 0:
        start = 0
    best = arr[i]
    best_off = 0
    for j in range(1, i - start + 1):
        v = arr[i - j]
        if np.isnan(best) or (not np.isnan(v) and v < best):
            best = v
            best_off = j
    if np.isnan(best):
        return np.nan
    return float(best_off)
