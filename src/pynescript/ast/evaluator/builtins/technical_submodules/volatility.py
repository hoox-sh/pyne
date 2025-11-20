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
from typing import Any

from .core import (
    BINARY,
    QUATERNARY,
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
        length = self._expect_int(args[3], "ta.kc length must be integer") if len(args) > 3 else 0
        offset_percent = 1.0 if len(args) < 5 else (args[4] if isinstance(args[4], (int, float)) else 1.0)

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
            import statistics
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
