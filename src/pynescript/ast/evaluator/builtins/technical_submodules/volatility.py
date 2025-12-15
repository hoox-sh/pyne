# Copyright 2024-2025 jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Volatility indicators module - ATR, Bollinger Bands, Keltner, StochRSI, etc."""

from __future__ import annotations

import math
import statistics
from typing import Any

from .core import (
    BINARY,
    QUATERNARY,
    QUINARY,
    TERNARY,
    TechnicalHelpers,
)


class VolatilityIndicators(TechnicalHelpers):
    """Volatility and price action indicators."""

    def _builtin_ta_stdev(self, args: list[Any]) -> float | None:
        """Standard Deviation."""
        series, period = self._expect_series(args, length=BINARY)
        return self._stdev(series, period)

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

    def _builtin_ta_tr(self, args: list[Any]) -> list[float]:
        """True Range."""
        msg = "ta.tr expects high, low, and close"
        if len(args) != TERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        return self._tr(highs, lows, closes)

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

    def _builtin_ta_kc(self, args: list[Any]) -> tuple[float, float, float]:
        """Keltner Channels."""
        if len(args) not in {TERNARY, QUATERNARY}:
            self._error("ta.kc takes high, low, close series, length, and optional offset_percent")

        highs = self._expect_list(args[0], "ta.kc takes high, low, close series, length")
        lows = self._expect_list(args[1], "ta.kc takes high, low, close series, length")
        closes = self._expect_list(args[2], "ta.kc takes high, low, close series, length")
        length = self._expect_int(args[3], "ta.kc length must be integer") if len(args) > TERNARY else 0
        offset_percent = 1.0 if len(args) < QUINARY else (args[4] if isinstance(args[4], (int, float)) else 1.0)

        if length < 1:
            self._error("ta.kc length must be positive")

        # Middle line = EMA of closes
        ema_vals = self._ema(closes, length)
        middle = ema_vals[-1] if ema_vals else math.nan

        # ATR for channel width
        atr_series = self._atr(highs, lows, closes, length)
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

    def _builtin_ta_linreg(self, args: list[Any]) -> float:
        """Linear Regression value."""
        series, length = self._expect_series(args, length=BINARY)

        if length < BINARY:
            self._error("ta.linreg length must be at least 2")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [v for v in window if v is not None]

        if len(valid_values) < BINARY:
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

        if length < BINARY:
            self._error("ta.rci length must be at least 2")
        if len(series) < length:
            return math.nan

        window = series[-length:]
        valid_values = [(i, v) for i, v in enumerate(window) if v is not None]

        if len(valid_values) < BINARY:
            return math.nan

        ranks_idx = sorted(range(len(valid_values)), key=lambda i: i)
        ranks_val = sorted(range(len(valid_values)), key=lambda i: valid_values[i][1])

        rank_dict_idx = {idx: rank for rank, idx in enumerate(ranks_idx)}
        rank_dict_val = {idx: rank for rank, idx in enumerate(ranks_val)}

        d_squared = sum((rank_dict_idx[i] - rank_dict_val[i]) ** 2 for i in range(len(valid_values)))
        n = len(valid_values)
        return 1 - (6 * d_squared) / (n * (n * n - 1)) if n > 1 else math.nan

    def _builtin_ta_dpo(self, args: list[Any]) -> float | None:
        """Detrended Price Oscillator."""
        if len(args) < 1:
            msg = "ta.dpo() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < 1:
            msg = "DPO length must be >= 1"
            self._error(msg)

        closes = self.current_series.get("close", [])
        if not closes or len(closes) < length:
            return None

        sma_val = sum(closes[-length:]) / length
        displacement = length // 2 + 1

        if len(closes) < displacement:
            return None

        dpo_val = closes[-displacement] - sma_val
        return dpo_val

    def _builtin_ta_bb_pct(self, args: list[Any]) -> float | None:
        """Bollinger Band Percentage.

        ta.bb_pct(length, std_dev)
        Position between upper and lower bands (0-100).
        """
        if len(args) < BINARY:
            msg = "ta.bb_pct() requires 2 arguments: length, std_dev"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")
        std_dev = float(args[1]) if isinstance(args[1], (int, float)) else 2.0

        closes = self.current_series.get("close", [])
        if not closes or len(closes) < length:
            return None

        sma_val = sum(closes[-length:]) / length
        variance = sum((v - sma_val) ** 2 for v in closes[-length:]) / length
        std_val = variance ** 0.5

        upper = sma_val + (std_val * std_dev)
        lower = sma_val - (std_val * std_dev)

        if upper == lower:
            return 50.0

        bb_pct = ((closes[-1] - lower) / (upper - lower)) * 100.0
        return max(0.0, min(100.0, bb_pct))

    def _builtin_ta_beta(self, args: list[Any]) -> float | None:
        """Beta Coefficient.

        ta.beta(series1, series2, length)
        Correlation measure between two series.
        """
        if len(args) < TERNARY:
            msg = "ta.beta() requires 3 arguments: series1, series2, length"
            self._error(msg)

        series1 = args[0] if isinstance(args[0], list) else [args[0]]
        series2 = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series1) < length or len(series2) < length:
            return None

        s1 = series1[-length:]
        s2 = series2[-length:]

        mean1 = sum(s1) / length
        mean2 = sum(s2) / length

        covariance = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(length)) / length
        variance2 = sum((v - mean2) ** 2 for v in s2) / length

        if variance2 == 0:
            return 0.0

        beta_val = covariance / variance2
        return beta_val

    def _builtin_ta_r_squared(self, args: list[Any]) -> float | None:
        """R-Squared (Coefficient of Determination).

        ta.r_squared(series1, series2, length)
        Measures fit quality (0-1).
        """
        if len(args) < TERNARY:
            msg = "ta.r_squared() requires 3 arguments: series1, series2, length"
            self._error(msg)

        series1 = args[0] if isinstance(args[0], list) else [args[0]]
        series2 = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series1) < length or len(series2) < length:
            return None

        s1 = series1[-length:]
        s2 = series2[-length:]

        mean1 = sum(s1) / length
        mean2 = sum(s2) / length

        covariance = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(length)) / length
        var1 = sum((v - mean1) ** 2 for v in s1) / length
        var2 = sum((v - mean2) ** 2 for v in s2) / length

        if var1 == 0 or var2 == 0:
            return 0.0

        correlation = covariance / ((var1 * var2) ** 0.5)
        r_squared = correlation ** 2

        return max(0.0, min(1.0, r_squared))

    def _builtin_ta_comovement(self, args: list[Any]) -> float | None:
        """Comovement Index.

        ta.comovement(series1, series2, length)
        Synchronicity between two series.
        """
        if len(args) < TERNARY:
            msg = "ta.comovement() requires 3 arguments: series1, series2, length"
            self._error(msg)

        series1 = args[0] if isinstance(args[0], list) else [args[0]]
        series2 = args[1] if isinstance(args[1], list) else [args[1]]
        length = self._expect_int(args[2], "length must be integer")

        if len(series1) < length or len(series2) < length:
            return None

        s1 = series1[-length:]
        s2 = series2[-length:]

        same_direction = sum(1 for i in range(1, length) if (s1[i] - s1[i - 1]) * (s2[i] - s2[i - 1]) > 0)

        comovement = (same_direction / (length - 1)) * 100.0 if length > 1 else 0.0
        return comovement

    def _builtin_ta_atr_stop(self, args: list[Any]) -> dict[str, float | None]:
        """ATR-based Stop Loss.

        ta.atr_stop(atr_value, multiplier)
        Calculate stop levels based on ATR.
        """
        if len(args) < BINARY:
            msg = "ta.atr_stop() requires 2 arguments: atr_value, multiplier"
            self._error(msg)

        atr_val = float(args[0]) if isinstance(args[0], (int, float)) else None
        multiplier = float(args[1]) if isinstance(args[1], (int, float)) else 2.0

        if atr_val is None or atr_val <= 0:
            return {"long_stop": None, "short_stop": None}

        closes = self.current_series.get("close", [])
        if not closes:
            return {"long_stop": None, "short_stop": None}

        current_close = closes[-1]
        long_stop = current_close - (atr_val * multiplier)
        short_stop = current_close + (atr_val * multiplier)

        return {"long_stop": long_stop, "short_stop": short_stop}

    def _builtin_ta_stochrsi(self, args: list[Any]) -> dict[str, float | None]:
        """Stochastic RSI."""
        if len(args) < BINARY:
            msg = "ta.stochrsi() requires 2 arguments: rsi_length, stoch_length"
            self._error(msg)

        rsi_length = self._expect_int(args[0], "rsi_length must be integer")
        stoch_length = self._expect_int(args[1], "stoch_length must be integer")

        closes = self.current_series.get("close", [])
        if not closes or len(closes) < rsi_length:
            return {"stochrsi": None, "signal": None}

        # Calculate RSI series
        rsi_series = []
        for i in range(len(closes)):
            if i < rsi_length:
                rsi_series.append(None)
            else:
                segment = closes[i - rsi_length + 1 : i + 1]
                gains = sum(max(0, segment[j] - segment[j - 1]) for j in range(1, len(segment)))
                losses = sum(max(0, segment[j - 1] - segment[j]) for j in range(1, len(segment)))
                avg_gain = gains / rsi_length
                avg_loss = losses / rsi_length
                rs = avg_gain / avg_loss if avg_loss != 0 else 100.0
                rsi_val = 100.0 - (100.0 / (1.0 + rs))
                rsi_series.append(rsi_val)

        # Calculate StochRSI from RSI series
        valid_rsi = [v for v in rsi_series if v is not None]
        if len(valid_rsi) < stoch_length:
            return {"stochrsi": None, "signal": None}

        rsi_high = max(valid_rsi[-stoch_length:])
        rsi_low = min(valid_rsi[-stoch_length:])
        rsi_range = rsi_high - rsi_low

        if rsi_range == 0:
            stochrsi_val = 0.0
        else:
            stochrsi_val = (valid_rsi[-1] - rsi_low) / rsi_range * 100.0

        # Signal is EMA of StochRSI
        signal = stochrsi_val * 0.33 + (getattr(self, "_last_stochrsi_signal", stochrsi_val) * 0.67)
        self._last_stochrsi_signal = signal

        return {"stochrsi": stochrsi_val, "signal": signal}

    def _builtin_ta_atr_normalized(self, args: list[Any]) -> float | None:
        """Normalized ATR - ATR as percentage of current price.

        ta.atr_normalized(high, low, close, period)
        Returns ATR as a percentage of price for comparable analysis.
        """
        if len(args) < QUATERNARY:
            msg = "ta.atr_normalized() requires 4 arguments: high, low, close, period"
            self._error(msg)

        highs = args[0] if isinstance(args[0], list) else [args[0]]
        lows = args[1] if isinstance(args[1], list) else [args[1]]
        closes = args[2] if isinstance(args[2], list) else [args[2]]
        period = self._expect_int(args[3], "period must be integer")

        if len(closes) == 0 or not isinstance(closes[-1], (int, float)):
            return None

        current_close = closes[-1]
        if current_close == 0:
            return None

        # Calculate ATR
        atr_list = self._atr(highs, lows, closes, period)
        if not atr_list or atr_list[-1] is None:
            return None

        atr_current = atr_list[-1]
        # Normalized ATR as percentage
        normalized_atr = (atr_current / current_close) * 100
        return normalized_atr

    # Helper implementations

    def _atr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> list[float | None]:
        """ATR calculation."""
        if period <= 0:
            return []
        tr_values: list[float] = []
        for idx in range(1, len(closes)):
            high = highs[idx]
            low = lows[idx]
            prev_close = closes[idx - 1]
            tr_values.append(
                max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close),
                )
            )
        if not tr_values:
            return []
        if len(tr_values) < period:
            average = statistics.mean(tr_values)
            return [average]
        return self._ema(tr_values, period)

    def _bollinger_bands(
        self,
        series: list[float],
        period: int,
        multiplier: float,
    ) -> tuple[float | None, float | None, float | None]:
        """Bollinger Bands calculation."""
        sma_values = self._sma(series, period)
        middle = sma_values[-1] if sma_values else None
        deviation = self._stdev(series, period)
        if middle is None or deviation is None:
            return None, None, None
        upper = middle + deviation * multiplier
        lower = middle - deviation * multiplier
        return upper, middle, lower
