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
    """Bars since highest value in window (0 = current is highest).

    On ties, prefers the most recent bar (smallest offset).
    Returns float of a non-negative int so callers can ``int()`` for indexing;
    invalid length / all-NaN window -> 0.0 (index-friendly; not NaN).
    """
    length = int(length)
    if length <= 0:
        return 0.0
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
        return 0.0
    return float(best_off)


@numba.njit(cache=True)
def numba_lowestbars(arr, length, i):
    """Bars since lowest value in window (0 = current is lowest).

    On ties, prefers the most recent bar (smallest offset).
    Returns float of a non-negative int so callers can ``int()`` for indexing;
    invalid length / all-NaN window -> 0.0 (index-friendly; not NaN).
    """
    length = int(length)
    if length <= 0:
        return 0.0
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
        return 0.0
    return float(best_off)

@numba.njit(cache=True)
def numba_percentrank(arr, length, i):
    length = int(length)
    """Percent of values in the last ``length`` bars that are <= arr[i]."""
    if length <= 0 or i < length - 1:
        return np.nan
    v = arr[i]
    if np.isnan(v):
        return np.nan
    cnt = 0
    for j in range(length):
        if arr[i - j] <= v:
            cnt += 1
    return 100.0 * cnt / length


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


def array_sort_indices(arr, order="ascending"):
    """Pine ``array.sort_indices(id, order?)`` → list of indices (na last).

    Object-mode helper used by the Numba compiler emit path.
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

    def _is_na(v) -> bool:
        if v is None:
            return True
        try:
            return v != v  # NaN
        except Exception:
            return False

    non_na = [(val, idx) for idx, val in enumerate(seq) if not _is_na(val)]
    na_idx = [idx for idx, val in enumerate(seq) if _is_na(val)]
    try:
        non_na.sort(key=lambda x: x[0], reverse=reverse)
    except TypeError:
        non_na.sort(key=lambda x: (str(type(x[0])), str(x[0])), reverse=reverse)
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


@numba.njit(cache=True)
def numba_ema_inc(arr, period, i, st):
    """Incremental EMA. ``st`` is length-2: [ema, last_i]; last_i nan → none.

    Sequential bar calls are O(1) amortized; gaps catch up from last_i+1.
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
        if j == period - 1:
            sum_val = 0.0
            for k in range(period):
                sum_val += arr[k]
            ema = sum_val / period
        elif j >= period:
            ema = alpha * arr[j] + (1.0 - alpha) * ema
    st[0] = ema
    st[1] = float(i)
    if i < period - 1:
        return np.nan
    return ema
@numba.njit(cache=True)
def numba_rma_inc(arr, period, i, st):
    """Incremental Wilder RMA. ``st``: [rma, last_i]."""
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
        if j == period - 1:
            s = 0.0
            for k in range(period):
                s += arr[k]
            rma = s / period
        elif j >= period:
            rma = alpha * arr[j] + (1.0 - alpha) * rma
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
    """O(1) simple-window RSI. ``st``: [gain, loss, last_i]. Matches ``numba_rsi``."""
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
    gain = st[0]
    loss = st[1]
    for j in range(last + 1, i + 1):
        if j < period:
            gain = np.nan
            loss = np.nan
        elif j == period:
            gain = 0.0
            loss = 0.0
            for k in range(j - period + 1, j + 1):
                delta = arr[k] - arr[k - 1]
                if delta >= 0.0:
                    gain += delta
                else:
                    loss -= delta
        else:
            if np.isnan(gain):
                gain = 0.0
                loss = 0.0
                for k in range(j - period + 1, j + 1):
                    delta = arr[k] - arr[k - 1]
                    if delta >= 0.0:
                        gain += delta
                    else:
                        loss -= delta
            else:
                old_d = arr[j - period] - arr[j - period - 1]
                new_d = arr[j] - arr[j - 1]
                if old_d >= 0.0:
                    gain -= old_d
                else:
                    loss += old_d
                if new_d >= 0.0:
                    gain += new_d
                else:
                    loss -= new_d
    st[0] = gain
    st[1] = loss
    st[2] = float(i)
    if i < period or np.isnan(gain):
        return np.nan
    avg_gain = gain / period
    avg_loss = loss / period
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
    """Amortized sliding-window max. ``st``: [max_val, max_idx, last_i]."""
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
        start = j - period + 1
        if start < 0:
            start = 0
        if j == 0 or np.isnan(m) or mi < start:
            m = arr[start]
            mi = start
            for k in range(start + 1, j + 1):
                v = arr[k]
                if v > m or np.isnan(m):
                    m = v
                    mi = k
        else:
            v = arr[j]
            if v > m or np.isnan(m):
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi)
    st[2] = float(i)
    return m


@numba.njit(cache=True)
def numba_lowest_inc(arr, period, i, st):
    """Amortized sliding-window min. ``st``: [min_val, min_idx, last_i]."""
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
        start = j - period + 1
        if start < 0:
            start = 0
        if j == 0 or np.isnan(m) or mi < start:
            m = arr[start]
            mi = start
            for k in range(start + 1, j + 1):
                v = arr[k]
                if v < m or np.isnan(m):
                    m = v
                    mi = k
        else:
            v = arr[j]
            if v < m or np.isnan(m):
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi)
    st[2] = float(i)
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

    On ties prefers the most recent bar (matches ``numba_highestbars``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return 0.0
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
            m = arr[start]
            mi = start
            for k in range(start + 1, j + 1):
                v = arr[k]
                # >= prefers most recent on ties (non-nan); nan loses to real
                if np.isnan(m):
                    m = v
                    mi = k
                elif (not np.isnan(v)) and v >= m:
                    m = v
                    mi = k
        else:
            v = arr[j]
            if np.isnan(m):
                m = v
                mi = j
            elif (not np.isnan(v)) and v >= m:
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi)
    st[2] = float(i)
    if np.isnan(m):
        return 0.0
    return float(i - mi)


@numba.njit(cache=True)
def numba_lowestbars_inc(arr, length, i, st):
    """Amortized lowestbars. ``st``: [min_val, min_idx, last_i].

    On ties prefers the most recent bar (matches ``numba_lowestbars``).
    """
    length = int(length)
    if length <= 0 or i < 0:
        return 0.0
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
            m = arr[start]
            mi = start
            for k in range(start + 1, j + 1):
                v = arr[k]
                if np.isnan(m):
                    m = v
                    mi = k
                elif (not np.isnan(v)) and v <= m:
                    m = v
                    mi = k
        else:
            v = arr[j]
            if np.isnan(m):
                m = v
                mi = j
            elif (not np.isnan(v)) and v <= m:
                m = v
                mi = j
    st[0] = m
    st[1] = float(mi)
    st[2] = float(i)
    if np.isnan(m):
        return 0.0
    return float(i - mi)


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
