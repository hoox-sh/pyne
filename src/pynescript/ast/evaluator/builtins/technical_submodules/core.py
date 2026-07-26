# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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

    current_series: dict[str, list[Any]]

    def _error(self, message: str) -> Any:
        """Raise a runtime error.

        This method should be overridden by the host class (Evaluator).
        """
        msg = "Must be implemented by host class"
        raise NotImplementedError(msg)

    _SERIES_MAX = 256

    def _bar_mode(self) -> bool:
        """True when evaluating bar-by-bar (Runtime / CustomEvaluator).

        Unit tests pass explicit list histories and expect full-series
        returns; bar mode returns the current (last) scalar so Pine
        expressions like ``ta.ema(close,12) - ta.ema(close,26)`` stay
        numeric per bar without relying only on plot unwrap.
        """
        return bool(getattr(self, "_pine_bar_mode", False))

    def _finalize_series(self, values: list[Any]) -> Any:
        """Return full series list, or current scalar in bar mode."""
        if not self._bar_mode():
            return values
        if not values:
            return None
        return values[-1]

    def _as_series(self, value: Any) -> list[Any]:
        """Convert a Pine-series-like object to a list.

        Accepts:
        - ``list`` — returned as-is.
        - Any object with a ``history`` attribute (e.g. ``PineSeries``) —
          its history is converted to a reversed list (chronological order),
          truncated to the most recent ``_SERIES_MAX`` elements to avoid
          O(n²) recomputation of full history at every bar.
        - Falls back to ``self.current_series`` lookup by name when the
          value is a string matching a known key.
        - Otherwise wraps the value in a single-element list.
        """
        if isinstance(value, list):
            return value
        # Duck-type PineSeries: has a deque/iterable history
        if hasattr(value, "history"):
            raw = list(reversed(value.history))
            if len(raw) > self._SERIES_MAX:
                raw = raw[-self._SERIES_MAX :]
            return raw
        # Named series reference — look up from the pre-loaded dict
        if isinstance(value, str) and value in self.current_series:
            return self.current_series[value]
        # Unknown — wrap as single-element
        return [value]

    def _context_series(self, name: str) -> list[Any]:
        """Return a named OHLCV series from the bar runtime context.

        Used when Pine calls omit the source series, e.g. ``ta.highest(20)``
        (defaults to high) or ``ta.atr(14)`` (uses high/low/close).
        """
        series_map = getattr(self, "current_series", None) or {}
        if name in series_map and series_map[name]:
            return list(series_map[name])
        # Fall back to empty — callers treat short series as na
        return []

    def _is_period_like(self, value: Any) -> bool:
        """True if *value* looks like a length/period (int or whole float)."""
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, float) and value == int(value):
            return True
        return False

    def _expect_series(
        self,
        args: list[Any],
        length: int,
        *,
        default_source: str | None = "close",
        allow_period_only: bool = False,
    ) -> tuple[list[Any], int]:
        """Validate and extract series and period arguments.

        TradingView allows ``ta.sma(close, 14)`` and, for some functions,
        ``ta.highest(14)`` (period-only, source defaults to high/low/close).

        When ``allow_period_only`` is True and a single period-like arg is
        passed, the series is taken from ``current_series[default_source]``.
        """
        if allow_period_only and len(args) == 1 and self._is_period_like(args[0]):
            if not default_source:
                self._error(f"ta.* function requires {length} argument(s), got 1. Expected: (series, period)")
            series = self._context_series(default_source)
            period = self._expect_int(args[0], "Period must be an integer")
            return series, period
        if len(args) != length:
            self._error(f"ta.* function requires {length} argument(s), got {len(args)}. Expected: (series, period)")
        series = self._as_series(args[0])
        # If caller passed a scalar as "series" (e.g. intermediate expression),
        # wrap and continue — period must still resolve.
        period = self._expect_int(
            args[1],
            "Second argument must be an integer (period)",
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
            self._as_series(args[0]),
            self._as_series(args[1]),
        )

    def _expect_int(self, value: Any, message: str) -> int:
        """Validate that value is an integer (accepts floats via floor for periods)."""
        # Unwrap series wrappers / input dict defaults / single-element lists / na
        if isinstance(value, dict) and "default" in value:
            value = value["default"]
        if hasattr(value, "current") and not isinstance(value, (list, tuple, str, bytes)):
            # PineSeries / _SeriesResult / _NaValue-like
            cur = value.current
            # _NaValue is callable and has no numeric current
            if type(value).__name__ == "_NaValue":
                self._error(f"{message}. Got: na")
            value = cur
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if value is None:
            self._error(f"{message}. Got: na")
        if isinstance(value, float):
            # TV floors fractional periods (e.g. length/2 → 4 for length=9)
            value = int(math.floor(value))
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, int):
            self._error(f"{message}. Got: {type(value).__name__}")
        return value

    def _expect_number(self, value: Any, message: str) -> float:
        """Validate that value is numeric and return as float."""
        if not isinstance(value, int | float):
            self._error(f"{message}. Got: {type(value).__name__}")
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
        """Weighted Moving Average (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = series[-period:]
        if any(v is None for v in window):
            valid = [(i + 1, v) for i, v in enumerate(window) if v is not None]
            if not valid:
                return None
            # weight by position among full period (TV drops na bars from sum only)
            total_w = sum(w for w, _ in valid)
            return sum(w * float(v) for w, v in valid) / total_w
        weights = list(range(1, period + 1))
        total = sum(weights)
        return sum(float(series[-idx]) * (period - idx + 1) for idx in range(1, period + 1)) / total

    def _highest(self, series: list[float], period: int) -> float | None:
        """Get highest value in period (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = [v for v in series[-period:] if v is not None]
        return max(window) if window else None

    def _lowest(self, series: list[float], period: int) -> float | None:
        """Get lowest value in period (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = [v for v in series[-period:] if v is not None]
        return min(window) if window else None

    def _stdev(self, series: list[float], period: int) -> float | None:
        """Standard deviation over period (na-safe)."""
        if period <= 0 or len(series) < period:
            return None
        window = [float(v) for v in series[-period:] if v is not None]
        if len(window) < 2:
            return None
        return statistics.stdev(window)

    def _tr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> list[float | None]:
        """True Range calculation (na-safe)."""
        if not closes:
            return []
        result: list[float | None] = [None]
        for idx in range(1, len(closes)):
            h, l, c_prev = highs[idx] if idx < len(highs) else None, lows[idx] if idx < len(lows) else None, closes[idx - 1]
            if h is None or l is None or c_prev is None:
                result.append(None)
                continue
            try:
                result.append(
                    max(
                        float(h) - float(l),
                        abs(float(h) - float(c_prev)),
                        abs(float(l) - float(c_prev)),
                    )
                )
            except (TypeError, ValueError):
                result.append(None)
        return result

    @staticmethod
    def _cmp_lt(a: Any, b: Any) -> bool | None:
        if a is None or b is None:
            return None
        try:
            return float(a) < float(b)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _cmp_gt(a: Any, b: Any) -> bool | None:
        if a is None or b is None:
            return None
        try:
            return float(a) > float(b)
        except (TypeError, ValueError):
            return None

    def _crossover(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses above series2 (na-safe)."""
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        prev = self._cmp_lt(series1[-2], series2[-2])
        curr = self._cmp_gt(series1[-1], series2[-1])
        return bool(prev and curr)

    def _crossunder(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses below series2 (na-safe)."""
        if len(series1) < MIN_SERIES_LENGTH or len(series2) < MIN_SERIES_LENGTH:
            return False
        prev = self._cmp_gt(series1[-2], series2[-2])
        curr = self._cmp_lt(series1[-1], series2[-1])
        return bool(prev and curr)

    def _cross(self, series1: list[float], series2: list[float]) -> bool:
        """Check if series1 crosses series2 (either direction)."""
        return bool(self._crossover(series1, series2) or self._crossunder(series1, series2))

    def _falling(self, series: list[float], period: int) -> bool:
        """Check if series is falling for period (na-safe)."""
        if len(series) < period or period < 1:
            return False
        for idx in range(1, period):
            cmp = self._cmp_lt(series[-idx], series[-idx - 1])  # current < previous? falling means lower
            # falling: series[-idx] < series[-idx-1] is wrong; falling means each is lower than previous
            # i.e. series[-1] < series[-2] < ... 
            a, b = series[-idx], series[-idx - 1]
            if a is None or b is None:
                return False
            try:
                if float(a) >= float(b):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _rising(self, series: list[float], period: int) -> bool:
        """Check if series is rising for period (na-safe)."""
        if len(series) < period or period < 1:
            return False
        for idx in range(1, period):
            a, b = series[-idx], series[-idx - 1]
            if a is None or b is None:
                return False
            try:
                if float(a) <= float(b):
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _highestbars(self, series: list[float], period: int) -> int:
        """Get offset to highest value in period."""
        if len(series) < period:
            return -1
        window = series[-period:]
        valid = [(i, v) for i, v in enumerate(window) if v is not None]
        if not valid:
            return -1
        max_i, _ = max(valid, key=lambda iv: iv[1])
        return -(period - 1 - max_i)

    def _lowestbars(self, series: list[float], period: int) -> int:
        """Get offset to lowest value in period."""
        if len(series) < period:
            return -1
        window = series[-period:]
        valid = [(i, v) for i, v in enumerate(window) if v is not None]
        if not valid:
            return -1
        min_i, _ = min(valid, key=lambda iv: iv[1])
        return -(period - 1 - min_i)

    def _swma(self, series: list[Any]) -> float | None:
        """Symmetrically Weighted Moving Average (4-period: 1/6, 2/6, 2/6, 1/6)."""
        if len(series) < 4:
            return None
        w = series[-4:]
        if any(v is None for v in w):
            return None
        try:
            return (float(w[0]) + 2 * float(w[1]) + 2 * float(w[2]) + float(w[3])) / 6.0
        except (TypeError, ValueError):
            return None

    def _change(self, source: list[float], length: int = 1) -> float | None:
        """Calculate change over length (na-safe)."""
        if len(source) <= length:
            return None
        a, b = source[-1], source[-1 - length]
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None

    def _mom(self, series: list[float], period: int) -> float | None:
        """Calculate momentum (na-safe)."""
        if len(series) <= period:
            return None
        a, b = series[-1], series[-period - 1]
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None
