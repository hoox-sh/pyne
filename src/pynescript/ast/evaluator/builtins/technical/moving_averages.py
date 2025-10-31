"""Moving Average indicators module."""

from __future__ import annotations

import math
from typing import Any

from .core import (
    BINARY,
    TechnicalHelpers,
)


class MovingAverageIndicators(TechnicalHelpers):
    """Moving average and trend-following indicators."""

    def _builtin_ta_sma(self, args: list[Any]) -> list[float | None]:
        """Simple Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._sma(series, period)

    def _builtin_ta_ema(self, args: list[Any]) -> list[float | None]:
        """Exponential Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._ema(series, period)

    def _builtin_ta_wma(self, args: list[Any]) -> float | None:
        """Weighted Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._wma(series, period)

    def _builtin_ta_rma(self, args: list[Any]) -> list[float]:
        """Recursive Moving Average (Wilder's smoothing)."""
        series, period = self._expect_series(args, length=BINARY)
        return self._rma(series, period)

    def _builtin_ta_hma(self, args: list[Any]) -> float | None:
        """Hull Moving Average - reduces lag."""
        series, period = self._expect_series(args, length=BINARY)
        return self._hma(series, period)

    def _builtin_ta_vwma(self, args: list[Any]) -> list[float | None]:
        """Volume Weighted Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._vwma(series, period)

    def _builtin_ta_kama(self, args: list[Any]) -> list[float | None]:
        """Kaufman's Adaptive Moving Average."""
        if len(args) < 4:
            msg = "ta.kama() requires 4 arguments: series, length, fast_period, slow_period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        length = self._expect_int(args[1], "ta.kama length must be integer")
        fast = self._expect_int(args[2], "ta.kama fast_period must be integer")
        slow = self._expect_int(args[3], "ta.kama slow_period must be integer")

        if length < 1:
            return [None] * len(series)

        kama_values = [None] * length
        kama = series[length - 1] if length <= len(series) else 0.0

        for i in range(length, len(series)):
            change = abs(series[i] - series[i - length])
            volatility = sum(abs(series[i - j] - series[i - j - 1]) for j in range(length))

            if volatility != 0:
                efficiency = change / volatility
                fastest = 2.0 / (fast + 1.0)
                slowest = 2.0 / (slow + 1.0)
                smoothing = efficiency * (fastest - slowest) + slowest
                sc = smoothing * smoothing
            else:
                sc = (2.0 / (slow + 1.0)) ** 2

            kama = kama + sc * (series[i] - kama)
            kama_values.append(kama)

        return kama_values

    def _builtin_ta_dema(self, args: list[Any]) -> list[float | None]:
        """Double Exponential Moving Average - reduces lag."""
        if len(args) < 2:
            msg = "ta.dema() requires 2 arguments: series, length"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        length = self._expect_int(args[1], "ta.dema length must be integer")

        ema1 = self._ema(series, length)
        ema2 = self._ema(ema1, length)

        dema_values = []
        for i in range(len(series)):
            if ema1[i] is None or ema2[i] is None:
                dema_values.append(None)
            else:
                dema_values.append(2 * ema1[i] - ema2[i])

        return dema_values

    def _builtin_ta_tema(self, args: list[Any]) -> list[float | None]:
        """Triple Exponential Moving Average - even less lag than DEMA."""
        if len(args) < 2:
            msg = "ta.tema() requires 2 arguments: series, length"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        length = self._expect_int(args[1], "ta.tema length must be integer")

        ema1 = self._ema(series, length)
        ema2 = self._ema(ema1, length)
        ema3 = self._ema(ema2, length)

        tema_values = []
        for i in range(len(series)):
            if ema1[i] is None or ema2[i] is None or ema3[i] is None:
                tema_values.append(None)
            else:
                tema_values.append(3 * ema1[i] - 3 * ema2[i] + ema3[i])

        return tema_values

    def _builtin_ta_swma(self, args: list[Any]) -> float:
        """Symmetric Weighted Moving Average."""
        series, length = self._expect_series(args, length=BINARY)

        if length < 1:
            self._error("ta.swma length must be positive")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [v for v in window if v is not None]

        if not valid_values:
            return math.nan

        # Symmetric weights: [1, 2, 3, ..., n, ..., 3, 2, 1]
        n = len(valid_values)
        if n == 1:
            return valid_values[0]

        weights = []
        for i in range(n):
            if i < n // 2:
                weights.append(i + 1)
            elif i > (n - 1) // 2:
                weights.append(n - i)
            else:
                weights.append(n // 2 + 1)

        weighted_sum = sum(v * w for v, w in zip(valid_values, weights, strict=True))
        return weighted_sum / sum(weights)

    def _builtin_ta_sma_weighted(self, args: list[Any]) -> float | None:
        """Weighted SMA with custom weighting scheme."""
        if len(args) < 2:
            msg = "ta.sma_weighted() requires at least 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")
        weight_type = args[2] if len(args) > 2 else "linear"

        if not isinstance(weight_type, str):
            weight_type = "linear"

        if len(series) < period:
            return None

        data = series[-period:]
        valid_data = [x for x in data if isinstance(x, (int, float))]

        if len(valid_data) < period:
            return None

        # Calculate weights based on type
        weights = []
        for i in range(len(valid_data)):
            if weight_type == "quadratic":
                weight = (i + 1) ** 2
            elif weight_type == "sqrt":
                weight = (i + 1) ** 0.5
            else:  # linear (default)
                weight = i + 1
            weights.append(weight)

        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(v * w for v, w in zip(valid_data, weights, strict=True))
        return weighted_sum / total_weight if total_weight > 0 else None

    # Helper implementations

    def _hma(self, series: list[float], period: int) -> float | None:
        """Hull Moving Average calculation."""
        half_period = period // 2
        sqrt_period = int(math.sqrt(period))
        wma_half = self._wma(series, half_period)
        wma_full = self._wma(series, period)
        if wma_half is None or wma_full is None:
            return None
        diff = [2 * wma_half[i] - wma_full[i] for i in range(min(len(wma_half), len(wma_full)))]
        return self._wma(diff, sqrt_period)

    def _vwma(self, series: list[float], period: int) -> list[float]:
        """Volume Weighted Moving Average."""
        return self._sma(series, period)
