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

"""Common Technical Indicators - Trend, Statistics, and Utilities."""

from __future__ import annotations

import math
import statistics

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import TERNARY
from .core import UNARY
from .core import TechnicalHelpers


class CommonIndicators(TechnicalHelpers):
    """Common technical indicators and statistical functions."""

    # -- Cross functions ----------------------------------------------------

    def _builtin_ta_crossover(self, args: list[Any]) -> bool:
        """Check if series1 crosses over series2."""
        if self._use_incremental_ta():
            series1, series2 = self._expect_two_series(args, last_sample_ok=True)
            return self._cross_stateful(series1, series2, under=False)
        series1, series2 = self._expect_two_series(args)
        if len(series1) >= 2 and len(series2) >= 2:
            return self._crossover(series1, series2)
        return self._cross_stateful(series1, series2, under=False)

    def _builtin_ta_crossunder(self, args: list[Any]) -> bool:
        """Check if series1 crosses under series2."""
        if self._use_incremental_ta():
            series1, series2 = self._expect_two_series(args, last_sample_ok=True)
            return self._cross_stateful(series1, series2, under=True)
        series1, series2 = self._expect_two_series(args)
        if len(series1) >= 2 and len(series2) >= 2:
            return self._crossunder(series1, series2)
        return self._cross_stateful(series1, series2, under=True)

    def _builtin_ta_cross(self, args: list[Any]) -> bool:
        """Check if series1 crosses series2."""
        if self._use_incremental_ta():
            series1, series2 = self._expect_two_series(args, last_sample_ok=True)
            return self._cross_stateful(series1, series2, under=False, either=True)
        series1, series2 = self._expect_two_series(args)
        return self._cross(series1, series2)

    # -- Trend/Direction functions ------------------------------------------

    def _builtin_ta_falling(self, args: list[Any]) -> bool:
        """Check if series is falling for length bars."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._falling_inc_update(series, period)
        # Bar-mode locals resolve to last-sample scalars — need call-site window.
        if self._bar_mode() and len(series) < period:
            return self._falling_inc_update(series, period)
        return self._falling(series, period)

    def _builtin_ta_rising(self, args: list[Any]) -> bool:
        """Check if series is rising for length bars."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._rising_inc_update(series, period)
        if self._bar_mode() and len(series) < period:
            return self._rising_inc_update(series, period)
        return self._rising(series, period)

    # -- Extremes functions -------------------------------------------------

    def _builtin_ta_highestbars(self, args: list[Any]) -> int:
        """Offset to the highest value over length bars."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._highestbars_inc_update(series, period)
        if self._bar_mode() and len(series) < period:
            return self._highestbars_inc_update(series, period)
        return self._highestbars(series, period)

    def _builtin_ta_lowestbars(self, args: list[Any]) -> int:
        """Offset to the lowest value over length bars."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._lowestbars_inc_update(series, period)
        if self._bar_mode() and len(series) < period:
            return self._lowestbars_inc_update(series, period)
        return self._lowestbars(series, period)

    def _builtin_ta_range(self, args: list[Any]) -> float | None:
        """Range = highest - lowest over a period."""
        series, period = self._expect_series(args, length=BINARY)
        return self._range(series, period)

    def _builtin_ta_max(self, args: list[Any]) -> float | None:
        """Maximum value over a period (alias for ta.highest)."""
        if len(args) == UNARY:
            series = self._as_series(args[0])
            valid = [v for v in series if v is not None and isinstance(v, (int, float))]
            return max(valid) if valid else None
        series, period = self._expect_series(args, length=BINARY)
        return self._highest(series, period)

    def _builtin_ta_min(self, args: list[Any]) -> float | None:
        """Minimum value over a period (alias for ta.lowest)."""
        if len(args) == UNARY:
            series = self._as_series(args[0])
            valid = [v for v in series if v is not None and isinstance(v, (int, float))]
            return min(valid) if valid else None
        series, period = self._expect_series(args, length=BINARY)
        return self._lowest(series, period)

    # -- Statistical/Change functions ---------------------------------------

    def _builtin_ta_change(self, args: list[Any]) -> float | None:
        """Difference between current value and value length bars ago."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._change_inc_update(series, period)
        return self._change(series, period)

    def _builtin_ta_mom(self, args: list[Any]) -> float | None:
        """Momentum = current value - previous value at specified length."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._mom_inc_update(series, period)
        return self._momentum(series, period)

    def _builtin_ta_cum(self, args: list[Any]) -> float:
        """Cumulative sum of values in series."""
        msg = "ta.cum expects a series"
        if len(args) != UNARY:
            self._error(msg)
        if self._use_incremental_ta():
            return self._cum_inc_update(args[0])  # type: ignore[return-value]
        series = self._expect_list(args[0], msg)
        return self._cumsum(series)

    def _builtin_ta_dev(self, args: list[Any]) -> float | None:
        """Deviation from mean (standard deviation)."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta() and hasattr(self, "_dev_inc_update"):
            return self._dev_inc_update(series, period)
        return self._dev(series, period)

    def _builtin_ta_median(self, args: list[Any]) -> float | None:
        """Median value over a period."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._median_inc_update(series, period)
        return self._median(series, period)

    def _builtin_ta_mode(self, args: list[Any]) -> float | None:
        """Mode (most frequent value) over a period."""
        series, period = self._expect_series(args, length=BINARY)
        return self._mode(series, period)

    def _builtin_ta_percentrank(self, args: list[Any]) -> float | None:
        """Percentile rank of current value in period."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._percentrank_inc_update(series, period)
        return self._percentrank(series, period)

    def _builtin_ta_variance(self, args: list[Any]) -> float | None:
        """Variance over a period."""
        series, period = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta() and hasattr(self, "_variance_inc_update"):
            return self._variance_inc_update(series, period)
        return self._variance(series, period)

    def _builtin_ta_expected_value(self, args: list[Any]) -> float:
        """Expected Value.

        ta.expected_value(returns, probabilities)
        Calculates statistical expected value.
        """
        if len(args) < BINARY:
            msg = "ta.expected_value() requires 2 arguments: returns, probabilities"
            self._error(msg)

        returns = args[0] if isinstance(args[0], list) else [args[0]]
        probs = args[1] if isinstance(args[1], list) else [args[1]]

        if len(returns) != len(probs):
            msg = "Returns and probabilities must have same length"
            self._error(msg)

        total_prob = sum(p for p in probs if isinstance(p, (int, float)))
        if total_prob == 0:
            return 0.0

        ev = sum(
            (r if isinstance(r, (int, float)) else 0.0) * (p if isinstance(p, (int, float)) else 0.0)
            for r, p in zip(returns, probs, strict=False)
        )
        return ev / total_prob

    def _builtin_ta_skewness(self, args: list[Any]) -> float | None:
        """Skewness.

        ta.skewness(series, period)
        Measures asymmetry in distribution.
        """
        if len(args) < 2:
            msg = "ta.skewness() requires 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")

        if len(series) < period:
            return None

        data = series[-period:]
        valid_data = [x for x in data if isinstance(x, (int, float))]

        if len(valid_data) < period:
            return None

        mean = sum(valid_data) / len(valid_data)
        variance = sum((x - mean) ** 2 for x in valid_data) / len(valid_data)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Skewness = E[(x - mean)³] / std_dev³
        skewness_val = sum((x - mean) ** 3 for x in valid_data) / (len(valid_data) * (std_dev ** 3))
        return skewness_val

    def _builtin_ta_kurtosis(self, args: list[Any]) -> float | None:
        """Kurtosis.

        ta.kurtosis(series, period)
        Measures tail risk and peakedness.
        """
        if len(args) < 2:
            msg = "ta.kurtosis() requires 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")

        if len(series) < period:
            return None

        data = series[-period:]
        valid_data = [x for x in data if isinstance(x, (int, float))]

        if len(valid_data) < period:
            return None

        mean = sum(valid_data) / len(valid_data)
        variance = sum((x - mean) ** 2 for x in valid_data) / len(valid_data)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # Kurtosis = E[(x - mean)⁴] / std_dev⁴ - 3
        fourth_moment = sum((x - mean) ** 4 for x in valid_data) / len(valid_data)
        kurtosis_val = (fourth_moment / (std_dev ** 4)) - 3.0
        return kurtosis_val

    def _builtin_ta_parkinson(self, args: list[Any]) -> float | None:
        """Parkinson Volatility.

        ta.parkinson(high, low)
        Calculates volatility from high-low range.
        """
        if len(args) < 2:
            msg = "ta.parkinson() requires 2 arguments: high, low"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]

        if not highs or not lows or len(highs) == 0:
            return None

        current_high = highs[-1] if isinstance(highs[-1], (int, float)) else None
        current_low = lows[-1] if isinstance(lows[-1], (int, float)) else None

        if current_high is None or current_low is None or current_high <= current_low:
            return None

        ratio = current_high / current_low
        if ratio <= 0:
            return None

        # Parkinson volatility
        parkinson_vol = math.sqrt(math.log(ratio) ** 2 / (4 * math.log(2)))
        return parkinson_vol

    def _builtin_ta_garman_klass(self, args: list[Any]) -> float | None:
        """Garman-Klass Volatility.

        ta.garman_klass(high, low, close, open)
        Volatility using OHLC data.
        """
        if len(args) < 4:
            msg = "ta.garman_klass() requires 4 arguments: high, low, close, open"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]
        closes = args[2] if isinstance(args[2], list) else [args[2]]
        opens = args[3] if isinstance(args[3], list) else [args[3]]

        if not highs or not lows or not closes or not opens:
            return None

        high_val = highs[-1] if isinstance(highs[-1], (int, float)) else None
        low_val = lows[-1] if isinstance(lows[-1], (int, float)) else None
        c = closes[-1] if isinstance(closes[-1], (int, float)) else None
        o = opens[-1] if isinstance(opens[-1], (int, float)) else None

        if high_val is None or low_val is None or c is None or o is None:
            return None

        if high_val <= low_val or high_val <= 0 or c <= 0:
            return None

        # Garman-Klass volatility formula
        hl_ratio = high_val / low_val
        co_ratio = c / o

        term1 = 0.5 * (math.log(hl_ratio) ** 2)
        term2 = (2 * math.log(2) - 1) * (math.log(co_ratio) ** 2)

        gk_vol = math.sqrt(term1 - term2)
        return gk_vol

    # -- Other Utilities ----------------------------------------------------

    def _builtin_ta_vwap(self, args: list[Any]) -> float:
        """Volume Weighted Average Price."""
        msg = "ta.vwap expects price-volume values"
        if len(args) != UNARY:
            self._error(msg)
        sequence = self._expect_list(args[0], msg)
        return self._vwap(sequence)

    def _builtin_ta_barssince(self, args: list[Any]) -> int | None:
        """Bars since condition was last true."""
        if len(args) != 1:
            msg = "ta.barssince() takes exactly one argument"
            self._error(msg)
        condition = args[0]
        if self._use_incremental_ta():
            return self._barssince_inc_update(condition)
        # If condition is a list (series), check from the end backwards
        if isinstance(condition, list):
            for i in range(len(condition) - 1, -1, -1):
                is_true = condition[i] is True or (condition[i] is not None and condition[i] is not False)
                if is_true:
                    return len(condition) - 1 - i
            return len(condition) - 1
        # If condition is boolean without bar-mode state, return 0 if true, 1 if false
        is_true = condition is True or (condition is not None and condition is not False)
        if is_true:
            return 0
        return 1

    # -- Phase 7 Missing Indicators -----------------------------------------

    def _builtin_ta_pivothigh(self, args: list[Any]) -> float | None:
        """Find the highest point (pivot high) in a window.

        Fallback when BasicIndicators is not in the MRO. Accepts list or
        PineSeries-like sources (materialized via ``_as_series``).
        """
        if len(args) < 3:
            msg = "ta.pivothigh() requires 3 arguments: source, leftbars, rightbars"
            self._error(msg)

        source = self._as_series(args[0])
        left_bars = self._expect_int(args[1], "leftbars must be integer")
        right_bars = self._expect_int(args[2], "rightbars must be integer")

        if len(source) <= left_bars + right_bars:
            return None
        current_idx = len(source) - 1
        current = source[current_idx]
        if current is None:
            return None
        # Unwrap nested series wrappers if present
        cur_attr = getattr(current, "current", None)
        if cur_attr is not None and hasattr(current, "history"):
            current = cur_attr
            if current is None:
                return None
        for i in range(1, left_bars + 1):
            if current_idx - i < 0:
                return None
            left_val = source[current_idx - i]
            lv = getattr(left_val, "current", left_val) if left_val is not None and hasattr(left_val, "history") else left_val
            try:
                if lv is not None and float(lv) >= float(current):
                    return None
            except (TypeError, ValueError):
                return None
        try:
            return float(current)
        except (TypeError, ValueError):
            return None

    def _builtin_ta_pivotlow(self, args: list[Any]) -> float | None:
        """Find the lowest point (pivot low) in a window.

        Fallback when BasicIndicators is not in the MRO. Accepts list or
        PineSeries-like sources (materialized via ``_as_series``).
        """
        if len(args) < 3:
            msg = "ta.pivotlow() requires 3 arguments: source, leftbars, rightbars"
            self._error(msg)

        source = self._as_series(args[0])
        left_bars = self._expect_int(args[1], "leftbars must be integer")
        right_bars = self._expect_int(args[2], "rightbars must be integer")

        if len(source) <= left_bars + right_bars:
            return None
        current_idx = len(source) - 1
        current = source[current_idx]
        if current is None:
            return None
        cur_attr = getattr(current, "current", None)
        if cur_attr is not None and hasattr(current, "history"):
            current = cur_attr
            if current is None:
                return None
        for i in range(1, left_bars + 1):
            if current_idx - i < 0:
                return None
            left_val = source[current_idx - i]
            lv = getattr(left_val, "current", left_val) if left_val is not None and hasattr(left_val, "history") else left_val
            try:
                if lv is not None and float(lv) <= float(current):
                    return None
            except (TypeError, ValueError):
                return None
        try:
            return float(current)
        except (TypeError, ValueError):
            return None

    def _builtin_ta_pivot_point_levels(self, args: list[Any]) -> Any:
        """Calculate pivot point levels — delegates to BasicIndicators TV form."""
        # Prefer BasicIndicators implementation via MRO when available.
        # Keep a minimal local fallback for composition without BasicIndicators.
        if args and isinstance(args[0], str):
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if not highs or not lows or not closes:
                return []
            high = highs[-1]
            low = lows[-1]
            close = closes[-1]
            if high is None or low is None or close is None:
                return []
            high_f, low_f, close_f = float(high), float(low), float(close)
            pivot = (high_f + low_f + close_f) / 3.0
            diff = high_f - low_f
            r1 = 2 * pivot - low_f
            s1 = 2 * pivot - high_f
            r2 = pivot + diff
            s2 = pivot - diff
            r3 = high_f + 2 * (pivot - low_f)
            s3 = low_f - 2 * (high_f - pivot)
            return [pivot, r1, s1, r2, s2, r3, s3]
        if len(args) < 3:
            msg = "ta.pivot_point_levels() requires type+anchor or high, low, close"
            self._error(msg)

        high = self._expect_number(args[0], "high must be numeric")
        low = self._expect_number(args[1], "low must be numeric")
        close = self._expect_number(args[2], "close must be numeric")
        is_traditional = args[3] if len(args) > 3 else True

        if high is None or low is None or close is None:
            return None

        pivot = (high + low + close) / 3.0

        if is_traditional:
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + (high - low)
            s2 = pivot - (high - low)
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
        else:
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

    def _builtin_ta_dmi(self, args: list[Any]) -> tuple[float, float, float]:
        """Directional Movement Index — see BasicIndicators for TV 2-arg form.

        Returns ``(+DI, -DI, ADX)``.
        """
        import math

        if len(args) == BINARY:
            di_len = self._expect_int(args[0], "ta.dmi diLength must be int")
            adx_smooth = self._expect_int(args[1], "ta.dmi adxSmoothing must be int")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
        elif len(args) == QUATERNARY:
            highs = self._expect_list(args[0], "ta.dmi takes high, low, close series and length")
            lows = self._expect_list(args[1], "ta.dmi takes high, low, close series and length")
            closes = self._expect_list(args[2], "ta.dmi takes high, low, close series and length")
            di_len = self._expect_int(args[3], "ta.dmi takes high, low, close series and length")
            adx_smooth = di_len
        else:
            self._error("ta.dmi takes (diLength, adxSmoothing) or (high, low, close, length)")
            return math.nan, math.nan, math.nan

        if di_len < 1:
            self._error("ta.dmi length must be positive")
        if not highs or not (len(highs) == len(lows) == len(closes)):
            return math.nan, math.nan, math.nan

        plus_dm: list[float] = []
        minus_dm: list[float] = []
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

        tr_series = self._tr(highs, lows, closes)
        atr_series = self._rma(tr_series, di_len)
        atr_val = atr_series[-1] if atr_series else 1
        plus_rma = self._rma(plus_dm, di_len)
        minus_rma = self._rma(minus_dm, di_len)
        pd = plus_rma[-1] if plus_rma else 0.0
        md = minus_rma[-1] if minus_rma else 0.0
        plus_di = 100 * pd / atr_val if atr_val else 0.0
        minus_di = 100 * md / atr_val if atr_val else 0.0
        adx = float(self._adx(highs, lows, closes, adx_smooth) or 0)
        return float(plus_di), float(minus_di), adx

    def _builtin_ta_supertrend(self, args: list[Any]) -> tuple[float, float, int]:
        """Supertrend indicator (returns final_lowerband, final_upperband, direction)."""
        if len(args) != TERNARY:
            self._error("ta.supertrend takes high, low series and length, multiplier")

        highs = self._expect_list(args[0], "ta.supertrend takes high, low, length, multiplier")
        lows = self._expect_list(args[1], "ta.supertrend takes high, low, length, multiplier")
        length = self._expect_int(args[2], "ta.supertrend takes high, low, length, multiplier")
        multiplier = args[3] if len(args) > 3 else 1.0

        if length < 1:
            self._error("ta.supertrend length must be positive")

        tr_series = self._tr(highs, lows, [0.0] * len(highs))
        atr_series = self._rma(tr_series, length)

        highest_high = max((h for h in highs[-length:] if h is not None), default=0)
        lowest_low = min((ll for ll in lows[-length:] if ll is not None), default=0)

        atr_last = atr_series[-1] if atr_series else 0
        if atr_last is None or (isinstance(atr_last, float) and math.isnan(atr_last)):
            atr_last = 0.0
        basic_ub = (highest_high + lowest_low) / 2 + multiplier * float(atr_last)
        basic_lb = (highest_high + lowest_low) / 2 - multiplier * float(atr_last)

        # na-safe direction (do not compare None with bands — TypeError on warmup)
        h_last = highs[-1] if highs else None
        l_last = lows[-1] if lows else None
        direction = 1
        try:
            if h_last is not None and float(h_last) > float(basic_ub):
                direction = 1
            elif l_last is not None and float(l_last) < float(basic_lb):
                direction = -1
        except (TypeError, ValueError):
            direction = 1

        return basic_lb, basic_ub, direction

    def _builtin_ta_zigzag(self, args: list[Any]) -> tuple[float, float, int]:
        """Zigzag pattern detector (returns high, low, direction)."""
        if len(args) != BINARY:
            self._error("ta.zigzag takes source series and percent threshold")

        series = self._expect_list(args[0], "ta.zigzag takes source series and percent threshold")
        threshold = args[1] if isinstance(args[1], (int, float)) else 5.0

        if len(series) < 2:
            return math.nan, math.nan, 0

        highs = [v for v in series if v is not None]
        if len(highs) < 2:
            return math.nan, math.nan, 0

        recent_high = max(highs[-2:])
        recent_low = min(highs[-2:])

        percent_change = (recent_high - recent_low) / recent_low * 100 if recent_low else 0

        direction = 1 if recent_high == highs[-1] else -1

        return recent_high, recent_low, 1 if percent_change > threshold else direction

    def _builtin_ta_adx(self, args: list[Any]) -> float:
        """Average Directional Index.

        Forms:
        - ``ta.adx(length)`` / ``ta.adx(diLength, adxSmoothing)`` — chart OHLC
        - ``ta.adx(high, low, close, length)`` — legacy explicit series
        """
        msg = "ta.adx expects length, (diLength, adxSmoothing), or high/low/close/length"
        if len(args) == UNARY and self._is_period_like(args[0]):
            length = self._expect_int(args[0], msg)
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if self._use_incremental_ta():
                return self._adx_inc_update(highs, lows, closes, length)
            return self._adx(highs, lows, closes, length)
        if len(args) == BINARY and self._is_period_like(args[0]) and self._is_period_like(args[1]):
            # diLength + adxSmoothing — use adxSmoothing for the final ADX period
            adx_len = self._expect_int(args[1], msg)
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if self._use_incremental_ta():
                return self._adx_inc_update(highs, lows, closes, adx_len)
            return self._adx(highs, lows, closes, adx_len)
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        if self._use_incremental_ta():
            return self._adx_inc_update(highs, lows, closes, length)
        return self._adx(highs, lows, closes, length)

    def _adx(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        if period <= 0:
            return 0.0
        if min(len(highs), len(lows), len(closes)) < period:
            return 0.0
        true_ranges = self._tr(highs, lows, closes)
        plus_dm = [math.nan]
        minus_dm = [math.nan]
        for idx in range(1, len(highs)):
            high_diff = highs[idx] - highs[idx - 1]
            low_diff = lows[idx - 1] - lows[idx]
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)
        atr = self._rma(true_ranges, period)
        if not atr or all(value in {None, math.nan, 0} for value in atr):
            return 0.0
        plus_di = [100 * dm / tr if tr else 0 for dm, tr in zip(self._rma(plus_dm, period), atr, strict=True)]
        minus_di = [100 * dm / tr if tr else 0 for dm, tr in zip(self._rma(minus_dm, period), atr, strict=True)]
        dx = [100 * abs(p - m) / (p + m) if (p + m) else 0 for p, m in zip(plus_di, minus_di, strict=True)]
        adx_series = self._rma(dx, period)
        return next(
            (value for value in reversed(adx_series) if value not in {None, math.nan}),
            0.0,
        )

    # -- Implementation Helpers ---------------------------------------------
    # Note: ``_rising`` / ``_falling`` / ``_highestbars`` / ``_lowestbars`` live
    # on :class:`TechnicalHelpers` (core.py) with na-safe comparisons. Do not
    # reintroduce bare ``>=``/``max(window)`` here — they raise TypeError when
    # the series contains Pine ``na`` (None), e.g. early VIDYA warmup bars:
    # ``Runtime Error: '>=' not supported between instances of 'NoneType'...``.

    def _range(self, series: list[float], period: int) -> float | None:
        highest = self._highest(series, period)
        lowest = self._lowest(series, period)
        if highest is None or lowest is None:
            return None
        return highest - lowest

    def _change(self, source: list[float], length: int = 1) -> float | None:
        """Difference vs value `length` bars ago (na-safe)."""
        if len(source) <= length:
            return None
        a, b = source[-1], source[-1 - length]
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None

    def _momentum(self, series: list[float], period: int) -> float | None:
        if len(series) <= period:
            return None
        a, b = series[-1], series[-1 - period]
        if a is None or b is None:
            return None
        try:
            return float(a) - float(b)
        except (TypeError, ValueError):
            return None

    def _cumsum(self, series: list[Any]) -> float:
        total = 0.0
        for value in series:
            if value is not None and isinstance(value, (int, float)):
                total += value
        return total

    def _dev(self, series: list[float], period: int) -> float | None:
        """Mean absolute deviation (strict window; mirror BasicIndicators)."""
        if period <= 0 or len(series) < period:
            return None
        window = series[-period:]
        vals: list[float] = []
        for v in window:
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            if fv != fv:  # NaN
                return None
            vals.append(fv)
        mean = sum(vals) / period
        return sum(abs(v - mean) for v in vals) / period

    def _median(self, series: list[float], period: int) -> float | None:
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = sorted([v for v in window if v is not None])
        if not valid_values:
            return None
        return statistics.median(valid_values)

    def _mode(self, series: list[float], period: int) -> float | None:
        if len(series) < period:
            return None
        window = series[-period:]
        valid_values = [v for v in window if v is not None]
        if not valid_values:
            return None
        try:
            return statistics.mode(valid_values)
        except statistics.StatisticsError:
            return valid_values[0] if valid_values else None

    def _percentrank(self, series: list[float], period: int) -> float | None:
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
        """Sample variance (strict window; mirror BasicIndicators)."""
        if period <= 1 or len(series) < period:
            return None
        window = series[-period:]
        vals: list[float] = []
        for v in window:
            if v is None:
                return None
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None
            if fv != fv:  # NaN
                return None
            vals.append(fv)
        return statistics.variance(vals)

    def _vwap(self, hlc3_volume: list[float]) -> float:
        if not hlc3_volume:
            return 0
        return sum(hlc3_volume) / len(hlc3_volume)

