# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

import numpy as np
import numba


@numba.njit
def numba_sma(arr, period, i):
    if i < period - 1:
        return np.nan
    sum_val = 0.0
    for j in range(period):
        val = arr[i - j]
        if np.isnan(val):
            return np.nan
        sum_val += val
    return sum_val / period


@numba.njit
def numba_ema(arr, period, i):
    if i < period - 1:
        return np.nan
    alpha = 2.0 / (period + 1.0)

    # Needs history array for EMA but we can compute simple EMA just by scanning back
    # Or assuming we have an ema_arr. Since we don't have state here,
    # computing EMA without state requires calculating it from index 0 every time, which is slow.
    # For a proper compiler, we'd allocate state arrays.
    # For MVP, we'll just scan back `period * 3` bars for approximation or fallback to sma.
    # Let's approximate by scanning back period * 3 bars
    lookback = min(i, period * 3)
    if lookback < period:
        return np.nan

    # Start with SMA
    sum_val = 0.0
    for j in range(period):
        sum_val += arr[i - lookback + j]
    ema = sum_val / period

    # Apply EMA formula forward
    for j in range(i - lookback + period, i + 1):
        ema = alpha * arr[j] + (1 - alpha) * ema

    return ema
