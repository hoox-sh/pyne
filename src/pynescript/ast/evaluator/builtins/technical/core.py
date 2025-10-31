"""Core technical analysis helpers and validation utilities."""

from __future__ import annotations

import math
import statistics
from typing import Any

# Constants
UNARY = 1
BINARY = 2
TERNARY = 3
QUATERNARY = 4
QUINARY = 5

MIN_SERIES_LENGTH = 2


class TechnicalHelpers:
    """Shared technical analysis helpers and validation methods."""

    def _expect_series(
        self,
        args: list[Any],
        length: int,
    ) -> tuple[list[Any], int]:
        """Validate and extract series and period arguments."""
        if len(args) != length:
            self._error("Invalid argument count for series-based function")
        series = self._expect_list(args[0], "First argument must be a series")
        period = self._expect_int(
            args[1],
            "Second argument must be an integer length",
        )
        return series, period

    def _expect_two_series(
        self,
        args: list[Any],
    ) -> tuple[list[Any], list[Any]]:
        """Validate and extract two series arguments."""
        if len(args) != BINARY:
            self._error("Function takes two series arguments")
        return (
            self._expect_list(args[0], "Function takes two series arguments"),
            self._expect_list(args[1], "Function takes two series arguments"),
        )

    def _expect_list(self, value: Any, message: str) -> list[Any]:
        """Validate that value is a list."""
        if not isinstance(value, list):
            self._error(message)
        return value

    def _expect_int(self, value: Any, message: str) -> int:
        """Validate that value is an integer."""
        if not isinstance(value, int):
            self._error(message)
        return value

    def _expect_number(self, value: Any, message: str) -> float:
        """Validate that value is numeric and return as float."""
        if not isinstance(value, int | float):
            self._error(message)
        return float(value)

    # Helper methods used across multiple indicators

    def _min_series(
        self,
        series: list[Any],
        period: int,
    ) -> list[float | None]:
        """Calculate minimum value over rolling period."""
        result: list[float | None] = []
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = series[index - period + 1 : index + 1]
            valid = [value for value in window if value is not None]
            result.append(min(valid) if valid else None)
        return result

    def _max_series(
        self,
        series: list[Any],
        period: int,
    ) -> list[float | None]:
        """Calculate maximum value over rolling period."""
        result: list[float | None] = []
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = series[index - period + 1 : index + 1]
            valid = [value for value in window if value is not None]
            result.append(max(valid) if valid else None)
        return result

    def _format_series(self, series: list[Any]) -> list[float]:
        """Convert series to float list, replacing None with NaN."""
        return [float(value) if value is not None else math.nan for value in series]

    def _sma(self, series: list[Any], period: int) -> list[float | None]:
        """Simple Moving Average."""
        result: list[float | None] = []
        if not series or period <= 0:
            return result
        for index in range(len(series)):
            if index < period - 1:
                result.append(None)
                continue
            window = [value for value in series[index - period + 1 : index + 1] if value is not None]
            if not window:
                result.append(None)
                continue
            result.append(sum(window) / len(window))
        return result

    def _ema(self, series: list[Any], period: int) -> list[float | None]:
        """Exponential Moving Average."""
        if not series or period <= 0:
            return [None] * len(series)
        alpha = 2 / (period + 1)
        ema_values: list[float | None] = []
        first_valid = next(
            (i for i, value in enumerate(series) if value is not None),
            -1,
        )
        if first_valid == -1:
            return [None] * len(series)
        ema_values.extend([None] * first_valid)
        ema_values.append(series[first_valid])
        for idx in range(first_valid + 1, len(series)):
            value = series[idx]
            if value is None:
                ema_values.append(ema_values[-1])
                continue
            previous = ema_values[-1]
            if previous is None:
                self._error("EMA requires a previous value")
            ema_values.append(alpha * value + (1 - alpha) * previous)
        return ema_values

    def _rma(self, series: list[Any], period: int) -> list[float]:
        """Recursive Moving Average (Wilder's Smoothing)."""
        formatted = self._format_series(series)
        if not formatted or period <= 0:
            return [math.nan] * len(formatted)
        alpha = 1.0 / period
        rma_values: list[float] = []
        first_valid = next(
            (idx for idx, value in enumerate(formatted) if not math.isnan(value)),
            -1,
        )
        if first_valid == -1:
            return [math.nan] * len(formatted)
        rma_values.extend([math.nan] * first_valid)
        initial_window = [value for value in formatted[first_valid : first_valid + period] if not math.isnan(value)]
        if not initial_window:
            return [math.nan] * len(formatted)
        current = sum(initial_window) / len(initial_window)
        rma_values.extend([math.nan] * (period - 1))
        rma_values.append(current)
        for idx in range(first_valid + period, len(formatted)):
            value = formatted[idx]
            if math.isnan(value):
                rma_values.append(current)
                continue
            current = alpha * value + (1 - alpha) * current
            rma_values.append(current)
        while len(rma_values) < len(formatted):
            rma_values.append(rma_values[-1])
        return rma_values[: len(formatted)]

    def _wma(self, series: list[float], period: int) -> float | None:
        """Weighted Moving Average."""
        if len(series) < period:
            return None
        weights = list(range(1, period + 1))
        total = sum(weights)
        return sum(series[-idx] * (period - idx + 1) for idx in range(1, period + 1)) / total

    def _highest(self, series: list[float], period: int) -> float | None:
        """Get highest value in period."""
        if len(series) < period:
            return None
        return max(series[-period:])

    def _lowest(self, series: list[float], period: int) -> float | None:
        """Get lowest value in period."""
        if len(series) < period:
            return None
        return min(series[-period:])

    def _stdev(self, series: list[float], period: int) -> float | None:
        """Standard deviation over period."""
        if len(series) < period:
            return None
        return statistics.stdev(series[-period:])

    def _tr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> list[float]:
        """True Range calculation."""
        result = [math.nan]
        for idx in range(1, len(closes)):
            result.append(
                max(
                    highs[idx] - lows[idx],
                    abs(highs[idx] - closes[idx - 1]),
                    abs(lows[idx] - closes[idx - 1]),
                )
            )
        return result

    def _crossover(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses above series2."""
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        return series1[-2] < series2[-2] and series1[-1] > series2[-1]

    def _crossunder(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses below series2."""
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        return series1[-2] > series2[-2] and series1[-1] < series2[-1]

    def _cross(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses series2 (either direction)."""
        return bool(self._crossover(series1, series2) or self._crossunder(series1, series2))
