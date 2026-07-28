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

    UDT dicts, hline handles, callables, version strings, and sequences
    must not raise — return NaN (or first element for length-1+ sequences).
    """
    try:
        if x is None:
            return np.nan
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        if isinstance(x, (int, float, np.integer, np.floating)):
            return float(x)
        if isinstance(x, (dict, set)):
            return np.nan
        if isinstance(x, (list, tuple)):
            if len(x) == 0:
                return np.nan
            # "setting an array element with a sequence" — take first element
            return safe_float(x[0])
        if callable(x) and not isinstance(x, type):
            return np.nan
        if isinstance(x, str):
            # version strings / colors / labels are not floats
            s = x.strip()
            if not s or s.count(".") > 1 or s.startswith("#") or not (
                s[0].isdigit() or s[0] in "+-" or s[0] == "."
            ):
                return np.nan
            return float(s)
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
