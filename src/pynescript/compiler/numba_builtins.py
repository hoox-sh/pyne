# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Numba-compatible builtins used by CompilerVisitor-generated code."""

from __future__ import annotations

import numpy as np
import numba


@numba.njit(cache=True)
def numba_sma(arr, period, i):
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
def numba_rsi(arr, period, i):
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
