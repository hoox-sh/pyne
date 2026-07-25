# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Basic technical indicators module - MA, Crossover, Volatility, etc."""

from __future__ import annotations

import math
import statistics

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import QUINARY
from .core import TERNARY
from .core import UNARY
from .core import TechnicalHelpers


class BasicIndicators(TechnicalHelpers):
    """Basic technical indicators and moving averages."""

    # -- Public API (builtin_ta_ prefix) ------------------------------------

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
        """Rolling Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._rma(series, period)

    def _builtin_ta_vwma(self, args: list[Any]) -> list[float | None]:
        """Volume Weighted Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._vwma(series, period)

    def _builtin_ta_hma(self, args: list[Any]) -> float | None:
        """Hull Moving Average."""
        series, period = self._expect_series(args, length=BINARY)
        return self._hma(series, period)

    def _builtin_ta_vwap(self, args: list[Any]) -> float:
        """Volume Weighted Average Price."""
        msg = "ta.vwap expects price-volume values"
        if len(args) != UNARY:
            self._error(msg)
        sequence = self._expect_list(args[0], msg)
        return self._vwap(sequence)

    def _builtin_ta_crossover(self, args: list[Any]) -> bool:
        """Crossover check."""
        series1, series2 = self._expect_two_series(args)
        return self._crossover(series1, series2)

    def _builtin_ta_crossunder(self, args: list[Any]) -> bool:
        """Crossunder check."""
        series1, series2 = self._expect_two_series(args)
        return self._crossunder(series1, series2)

    def _builtin_ta_cross(self, args: list[Any]) -> bool:
        """Cross check."""
        series1, series2 = self._expect_two_series(args)
        return self._cross(series1, series2)

    def _builtin_ta_falling(self, args: list[Any]) -> bool:
        """Falling check."""
        series, period = self._expect_series(args, length=BINARY)
        return self._falling(series, period)

    def _builtin_ta_rising(self, args: list[Any]) -> bool:
        """Rising check."""
        series, period = self._expect_series(args, length=BINARY)
        return self._rising(series, period)

    def _builtin_ta_highest(self, args: list[Any]) -> Any:
        """Highest value."""
        series, period = self._expect_series(args, length=BINARY)
        return self._highest(series, period)

    def _builtin_ta_lowest(self, args: list[Any]) -> Any:
        """Lowest value."""
        series, period = self._expect_series(args, length=BINARY)
        return self._lowest(series, period)

    def _builtin_ta_highestbars(self, args: list[Any]) -> int:
        """Offset to highest value."""
        series, period = self._expect_series(args, length=BINARY)
        return self._highestbars(series, period)

    def _builtin_ta_lowestbars(self, args: list[Any]) -> int:
        """Offset to lowest value."""
        series, period = self._expect_series(args, length=BINARY)
        return self._lowestbars(series, period)

    def _builtin_ta_change(self, args: list[Any]) -> float | None:
        """Change over period (1 or 2 args; period defaults to 1)."""
        if len(args) < 1 or len(args) > 2:
            self._error("ta.change() requires 1 or 2 arguments: source, (period)")
        source = self._as_series(args[0])
        period = self._expect_int(args[1], "Second argument must be an integer") if len(args) > 1 else 1
        if isinstance(period, float) and period == int(period):
            period = int(period)
        return self._change(source, period)

    def _builtin_ta_mom(self, args: list[Any]) -> float:
        """Momentum."""
        series, period = self._expect_series(args, length=BINARY)
        return self._mom(series, period)

    def _builtin_ta_stdev(self, args: list[Any]) -> float | None:
        """Standard Deviation."""
        series, period = self._expect_series(args, length=BINARY)
        return self._stdev(series, period)

    def _builtin_ta_tr(self, args: list[Any]) -> list[float]:
        """True Range."""
        msg = "ta.tr expects high, low, and close"
        if len(args) != TERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        return self._tr(highs, lows, closes)

    def _builtin_ta_sar(self, args: list[Any]) -> list[float]:
        """Parabolic SAR."""
        msg = "ta.sar expects high, low, start, increment, max"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        start = self._expect_number(args[2], msg)
        increment = self._expect_number(args[3], msg)
        maximum = self._expect_number(args[4], msg)
        return self._sar(highs, lows, start, increment, maximum)

    def _builtin_ta_bb(
        self,
        args: list[Any],
    ) -> tuple[float | None, float | None, float | None]:
        """Bollinger Bands."""
        msg = "ta.bb expects series, length, and multiplier"
        if len(args) != TERNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        length = self._expect_int(args[1], msg)
        multiplier = args[2]
        if not isinstance(multiplier, int | float):
            self._error("ta.bb expects numeric multiplier")
        return self._bollinger_bands(series, length, multiplier)

    def _builtin_ta_atr(self, args: list[Any]) -> list[float | None]:
        """Average True Range."""
        msg = "ta.atr expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._atr(highs, lows, closes, length)

    def _builtin_ta_kc(self, args: list[Any]) -> tuple[float, float, float]:
        """Keltner Channels (returns middle, upper, lower)."""
        if len(args) not in {TERNARY, QUATERNARY}:
            self._error("ta.kc takes high, low, close series, length, and optional offset_percent")

        highs = self._expect_list(args[0], "ta.kc takes high, low, close series, length")
        lows = self._expect_list(args[1], "ta.kc takes high, low, close series, length")
        closes = self._expect_list(args[2], "ta.kc takes high, low, close series, length")
        length = self._expect_int(args[3], "ta.kc length must be integer") if len(args) > 3 else 0
        offset_percent = 1.0 if len(args) < 5 else (args[4] if isinstance(args[4], (int, float)) else 1.0)

        if length < 1:
            self._error("ta.kc length must be positive")

        # Middle line = EMA of closes
        ema_vals = self._ema(closes, length)
        middle = ema_vals[-1] if ema_vals else math.nan

        # ATR for channel width
        atr_series = self._builtin_ta_atr([highs, lows, closes, length])
        atr_val = atr_series[-1] if atr_series else 0

        channel_width = atr_val * offset_percent
        upper = middle + channel_width if middle is not None else math.nan
        lower = middle - channel_width if middle is not None else math.nan

        return middle, upper, lower

    def _builtin_ta_kcw(self, args: list[Any]) -> float:
        """Keltner Channels Width."""
        if len(args) not in {TERNARY, QUATERNARY}:
            self._error("ta.kcw takes high, low, close series, length, and optional offset_percent")

        _, upper, lower = self._builtin_ta_kc(args)
        if math.isnan(upper) or math.isnan(lower):
            return math.nan
        return upper - lower

    def _builtin_ta_dmi(self, args: list[Any]) -> tuple[float, float]:
        """Directional Movement Index (returns +DI, -DI)."""
        if len(args) != QUATERNARY:
            self._error("ta.dmi takes high, low, close series and length")

        highs = self._expect_list(args[0], "ta.dmi takes high, low, close series and length")
        lows = self._expect_list(args[1], "ta.dmi takes high, low, close series and length")
        closes = self._expect_list(args[2], "ta.dmi takes high, low, close series and length")
        length = self._expect_int(args[3], "ta.dmi takes high, low, close series and length")

        if length < 1:
            self._error("ta.dmi length must be positive")
        if not (len(highs) == len(lows) == len(closes)):
            self._error("ta.dmi series must have equal length")

        plus_dm = []
        minus_dm = []

        for i in range(len(highs)):
            if i == 0:
                plus_dm.append(0.0)
                minus_dm.append(0.0)
            else:
                high_diff = (highs[i] if highs[i] is not None else 0) - (
                    highs[i - 1] if highs[i - 1] is not None else 0
                )
                low_diff = (lows[i - 1] if lows[i - 1] is not None else 0) - (lows[i] if lows[i] is not None else 0)
                plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
                minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)

        atr_series = self._builtin_ta_atr([highs, lows, closes, length])
        atr_val = atr_series[-1] if atr_series else 1

        plus_di = 100 * (sum(plus_dm[-length:]) / length) / atr_val if atr_val else 0
        minus_di = 100 * (sum(minus_dm[-length:]) / length) / atr_val if atr_val else 0

        return plus_di, minus_di

    def _builtin_ta_supertrend(self, args: list[Any]) -> tuple[float, float, int]:
        """Supertrend indicator (returns final_lowerband, final_upperband, direction)."""
        if len(args) < TERNARY:
            self._error("ta.supertrend takes high, low series and length, multiplier")

        highs = self._expect_list(args[0], "ta.supertrend takes high, low, length, multiplier")
        lows = self._expect_list(args[1], "ta.supertrend takes high, low, length, multiplier")
        length = self._expect_int(args[2], "ta.supertrend takes high, low, length, multiplier")
        multiplier = args[3] if (len(args) > 3 and isinstance(args[3], (int, float))) else 1.0

        if length < 1:
            self._error("ta.supertrend length must be positive")

        # This is a simplified implementation as full Supertrend requires state
        # For now we return basic bands based on ATR
        atr_series = self._builtin_ta_atr([highs, lows, [0] * len(highs), length])
        atr_val = atr_series[-1] if atr_series and isinstance(atr_series[-1], (int, float)) else 0.0

        current_high = highs[-1] if highs and isinstance(highs[-1], (int, float)) else 0.0
        current_low = lows[-1] if lows and isinstance(lows[-1], (int, float)) else 0.0
        mid = (current_high + current_low) / 2.0

        final_lowerband = mid - (multiplier * atr_val)
        final_upperband = mid + (multiplier * atr_val)

        # Full Supertrend direction requires state; return 1 as a stable default.
        return final_lowerband, final_upperband, 1

    def _builtin_ta_linreg(self, args: list[Any]) -> float:
        """Linear Regression value."""
        series, length = self._expect_series(args, length=BINARY)

        if length < 2:
            self._error("ta.linreg length must be at least 2")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [v for v in window if v is not None]

        if len(valid_values) < 2:
            return math.nan

        x = list(range(len(valid_values)))
        mean_x = sum(x) / len(x)
        mean_y = sum(valid_values) / len(valid_values)

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, valid_values, strict=True))
        denominator = sum((xi - mean_x) ** 2 for xi in x)

        if denominator == 0:
            return mean_y

        slope = numerator / denominator
        return slope * (len(valid_values) - 1) + mean_y

    def _builtin_ta_rci(self, args: list[Any]) -> float:
        """Rank Correlation Index (Spearman's correlation)."""
        if len(args) != BINARY:
            self._error("ta.rci takes source series and length")

        series = self._expect_list(args[0], "ta.rci takes source series and length")
        length = self._expect_int(args[1], "ta.rci takes source series and length")

        if length < 2:
            self._error("ta.rci length must be at least 2")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [(i, v) for i, v in enumerate(window) if v is not None]

        if len(valid_values) < 2:
            return math.nan

        ranks_idx = sorted(range(len(valid_values)), key=lambda i: i)
        ranks_val = sorted(range(len(valid_values)), key=lambda i: valid_values[i][1])

        rank_dict_idx = {idx: rank for rank, idx in enumerate(ranks_idx)}
        rank_dict_val = {idx: rank for rank, idx in enumerate(ranks_val)}

        d_squared = sum((rank_dict_idx[i] - rank_dict_val[i]) ** 2 for i in range(len(valid_values)))
        n = len(valid_values)
        return 1 - (6 * d_squared) / (n * (n * n - 1)) if n > 1 else math.nan

    def _builtin_ta_cog(self, args: list[Any]) -> float:
        """Center of Gravity oscillator."""
        series, length = self._expect_series(args, length=BINARY)

        if length < 1:
            self._error("ta.cog length must be positive")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        num_sum = sum((i + 1) * val for i, val in enumerate(reversed(window)) if val is not None)
        den_sum = sum(val for val in window if val is not None)

        if den_sum == 0:
            return math.nan
        return -num_sum / den_sum

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

    def _builtin_ta_zigzag(self, args: list[Any]) -> tuple[float, float, int]:
        """Zigzag pattern detector (returns high, low, direction)."""
        if len(args) != BINARY:
            self._error("ta.zigzag takes source series and percent threshold")

        series = self._expect_list(args[0], "ta.zigzag takes source series and percent threshold")
        threshold = args[1] if isinstance(args[1], (int, float)) else 5.0

        if len(series) < 2:
            return math.nan, math.nan, 0

        # Find peaks and troughs
        highs = [v for v in series if v is not None]
        if len(highs) < 2:
            return math.nan, math.nan, 0

        recent_high = max(highs[-2:])
        recent_low = min(highs[-2:])

        percent_change = (recent_high - recent_low) / recent_low * 100 if recent_low else 0

        direction = 1 if recent_high == highs[-1] else -1

        return recent_high, recent_low, 1 if percent_change > threshold else direction

    def _builtin_ta_range(self, args: list[Any]) -> float | None:
        """Range = highest - lowest over a period."""
        series, period = self._expect_series(args, length=2)
        return self._range(series, period)

    def _builtin_ta_max(self, args: list[Any]) -> float | None:
        """Maximum value over a period (alias for ta.highest)."""
        series, period = self._expect_series(args, length=2)
        return self._highest(series, period)

    def _builtin_ta_min(self, args: list[Any]) -> float | None:
        """Minimum value over a period (alias for ta.lowest)."""
        series, period = self._expect_series(args, length=2)
        return self._lowest(series, period)

    def _builtin_ta_cum(self, args: list[Any]) -> float:
        """Cumulative sum of values in series."""
        msg = "ta.cum expects a series"
        if len(args) != UNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        return self._cumsum(series)

    def _builtin_ta_dev(self, args: list[Any]) -> float | None:
        """Deviation from mean (standard deviation)."""
        series, period = self._expect_series(args, length=2)
        return self._dev(series, period)

    def _builtin_ta_median(self, args: list[Any]) -> float | None:
        """Median value over a period."""
        series, period = self._expect_series(args, length=2)
        return self._median(series, period)

    def _builtin_ta_mode(self, args: list[Any]) -> float | None:
        """Mode (most frequent value) over a period."""
        series, period = self._expect_series(args, length=2)
        return self._mode(series, period)

    def _builtin_ta_percentrank(self, args: list[Any]) -> float | None:
        """Percentile rank of current value in period."""
        series, period = self._expect_series(args, length=2)
        return self._percentrank(series, period)

    def _builtin_ta_percentile_linear_interpolation(self, args: list[Any]) -> float | None:
        """ta.percentile_linear_interpolation(source, length, percentage)."""
        if len(args) < 3:
            self._error("ta.percentile_linear_interpolation requires series, length, percentage")
        series = self._as_series(args[0]) if hasattr(self, "_as_series") else (
            args[0] if isinstance(args[0], list) else [args[0]]
        )
        period = self._expect_int(args[1], "length must be int")
        percentage = args[2]
        if not isinstance(percentage, (int, float)):
            self._error("percentage must be number")
        if len(series) < period or period <= 0:
            return None
        window = [v for v in series[-period:] if v is not None]
        if not window:
            return None
        sorted_w = sorted(window)
        n = len(sorted_w)
        if n == 1:
            return float(sorted_w[0])
        rank = (float(percentage) / 100.0) * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return float(sorted_w[lo]) * (1 - frac) + float(sorted_w[hi]) * frac

    def _builtin_ta_percentile_nearest_rank(self, args: list[Any]) -> float | None:
        """ta.percentile_nearest_rank(source, length, percentage)."""
        if len(args) < 3:
            self._error("ta.percentile_nearest_rank requires series, length, percentage")
        series = self._as_series(args[0]) if hasattr(self, "_as_series") else (
            args[0] if isinstance(args[0], list) else [args[0]]
        )
        period = self._expect_int(args[1], "length must be int")
        percentage = args[2]
        if not isinstance(percentage, (int, float)):
            self._error("percentage must be number")
        if len(series) < period or period <= 0:
            return None
        window = [v for v in series[-period:] if v is not None]
        if not window:
            return None
        sorted_w = sorted(window)
        n = len(sorted_w)
        # Nearest rank: ceil(p/100 * n), 1-indexed, clamped
        rank = max(1, int((float(percentage) / 100.0) * n + 0.999999))
        rank = min(rank, n)
        return float(sorted_w[rank - 1])

    def _builtin_ta_variance(self, args: list[Any]) -> float | None:
        """Variance over a period."""
        series, period = self._expect_series(args, length=2)
        return self._variance(series, period)

    def _builtin_ta_barssince(self, args: list[Any]) -> int | None:
        """Bars since condition was last true."""
        if len(args) != 1:
            msg = "ta.barssince() takes exactly one argument"
            self._error(msg)
        condition = args[0]
        # If condition is a list (series), check from the end backwards
        if isinstance(condition, list):
            for i in range(len(condition) - 1, -1, -1):
                is_true = condition[i] is True or (condition[i] is not None and condition[i] is not False)
                if is_true:
                    return len(condition) - 1 - i
            return len(condition) - 1
        # If condition is boolean, return 0 if true, 1 if false
        is_true = condition is True or (condition is not None and condition is not False)
        if is_true:
            return 0
        return 1

    def _builtin_ta_pivothigh(self, args: list[Any]) -> float | None:
        """Find the highest point (pivot high) in a window.

        ta.pivothigh(source, leftbars, rightbars)
        Finds a pivot high - a point where left_bars bars to the left are lower
        and right_bars bars to the right are lower.
        """
        if len(args) < 3:
            msg = "ta.pivothigh() requires 3 arguments: source, leftbars, rightbars"
            self._error(msg)

        source = args[0]
        left_bars = self._expect_int(args[1], "leftbars must be integer")
        right_bars = self._expect_int(args[2], "rightbars must be integer")

        # If source is a list (series), check if current value is a pivot high
        if isinstance(source, list):
            if len(source) <= left_bars + right_bars:
                return None

            # Get current value (last in series)
            current_idx = len(source) - 1
            current = source[current_idx]

            if current is None:
                return None

            # Check left bars
            for i in range(1, left_bars + 1):
                if current_idx - i < 0:
                    return None
                left_val = source[current_idx - i]
                if left_val is not None and left_val >= current:
                    return None

            # Check right bars - would need future bars
            # For now, only check left bars
            return float(current)

        return float(source) if source is not None else None

    def _builtin_ta_pivotlow(self, args: list[Any]) -> float | None:
        """Find the lowest point (pivot low) in a window.

        ta.pivotlow(source, leftbars, rightbars)
        Finds a pivot low - a point where left_bars bars to the left are higher
        and right_bars bars to the right are higher.
        """
        if len(args) < 3:
            msg = "ta.pivotlow() requires 3 arguments: source, leftbars, rightbars"
            self._error(msg)

        source = args[0]
        left_bars = self._expect_int(args[1], "leftbars must be integer")
        right_bars = self._expect_int(args[2], "rightbars must be integer")

        # If source is a list (series), check if current value is a pivot low
        if isinstance(source, list):
            if len(source) <= left_bars + right_bars:
                return None

            # Get current value (last in series)
            current_idx = len(source) - 1
            current = source[current_idx]

            if current is None:
                return None

            # Check left bars
            for i in range(1, left_bars + 1):
                if current_idx - i < 0:
                    return None
                left_val = source[current_idx - i]
                if left_val is not None and left_val <= current:
                    return None

            # Check right bars - would need future bars
            # For now, only check left bars
            return float(current)

        return float(source) if source is not None else None

    def _builtin_ta_pivot_point_levels(self, args: list[Any]) -> dict[str, float] | None:
        """Calculate pivot point levels.

        ta.pivot_point_levels(high, low, close, is_traditional)
        Returns a dictionary with pivot point levels.
        """
        if len(args) < 3:
            msg = "ta.pivot_point_levels() requires at least 3 arguments: high, low, close"
            self._error(msg)

        high = self._expect_number(args[0], "high must be numeric")
        low = self._expect_number(args[1], "low must be numeric")
        close = self._expect_number(args[2], "close must be numeric")
        is_traditional = args[3] if len(args) > 3 else True

        if high is None or low is None or close is None:
            return None

        # Calculate pivot point levels (traditional pivot points)
        pivot = (high + low + close) / 3.0

        if is_traditional:
            # Traditional pivot points
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + (high - low)
            s2 = pivot - (high - low)
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
        else:
            # Fibonacci pivot points
            diff = high - low
            r1 = pivot + 0.382 * diff
            s1 = pivot - 0.382 * diff
            r2 = pivot + 0.618 * diff
            s2 = pivot - 0.618 * diff
            r3 = pivot + diff
            s3 = pivot - diff

        return {
            "pivot": pivot,
            "r1": r1,
            "s1": s1,
            "r2": r2,
            "s2": s2,
            "r3": r3,
            "s3": s3,
        }

    # Helper implementations

    def _range(self, series: list[float], period: int) -> float | None:
        """Range = highest - lowest over a period."""
        highest = self._highest(series, period)
        lowest = self._lowest(series, period)
        if highest is None or lowest is None:
            return None
        return highest - lowest

    def _cumsum(self, series: list[Any]) -> float:
        """Cumulative sum of all values in series."""
        total = 0.0
        for value in series:
            if value is not None and isinstance(value, (int, float)):
                total += value
        return total

    def _dev(self, series: list[float], period: int) -> float | None:
        """Deviation = average absolute deviation from mean."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if not valid_values:
            return None
        mean = sum(valid_values) / len(valid_values)
        dev = sum(abs(v - mean) for v in valid_values) / len(valid_values)
        return dev

    def _median(self, series: list[float], period: int) -> float | None:
        """Median value over a period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = sorted([v for v in window if v is not None])
        if not valid_values:
            return None
        return statistics.median(valid_values)

    def _mode(self, series: list[float], period: int) -> float | None:
        """Mode (most frequent value) over a period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if not valid_values:
            return None
        try:
            return statistics.mode(valid_values)
        except statistics.StatisticsError:
            # No unique mode, return the first value
            return valid_values[0] if valid_values else None

    def _percentrank(self, series: list[float], period: int) -> float | None:
        """Percentile rank of current value in period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = sorted([v for v in window if v is not None])
        if not valid_values or len(valid_values) < 2:
            return 50.0
        current = series[-1]
        if current is None:
            return None
        count_below = sum(1 for v in valid_values if v < current)
        return (count_below / len(valid_values)) * 100

    def _variance(self, series: list[float], period: int) -> float | None:
        """Variance over a period."""
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if len(valid_values) < 2:
            return None
        return statistics.variance(valid_values)
