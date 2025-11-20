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

"""Oscillator indicators module - RSI, STOCH, MACD, CCI, ROC, WPR, TSI."""

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


class OscillatorIndicators(TechnicalHelpers):
    """Momentum and oscillator indicators."""

    def _builtin_ta_rsi(self, args: list[Any]) -> float | None:
        """Relative Strength Index."""
        series, period = self._expect_series(args, length=BINARY)
        return self._rsi(series, period)

    def _builtin_ta_stoch(self, args: list[Any]) -> tuple[float, float]:
        """Stochastic Oscillator."""
        msg = "ta.stoch expects high, low, close, length, smooth"
        if len(args) != QUINARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        smooth_k = self._expect_int(args[4], msg)
        return self._stoch(highs, lows, closes, length, smooth_k)

    def _builtin_ta_macd(self, args: list[Any]) -> tuple[float, float, float]:
        """MACD (Moving Average Convergence Divergence)."""
        msg = "ta.macd expects series and three lengths"
        if len(args) != QUATERNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        fast = self._expect_int(args[1], msg)
        slow = self._expect_int(args[2], msg)
        signal = self._expect_int(args[3], msg)
        return self._macd(series, fast, slow, signal)

    def _builtin_ta_cci(self, args: list[Any]) -> float:
        """Commodity Channel Index."""
        msg = "ta.cci expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._cci(highs, lows, closes, length)

    def _builtin_ta_roc(self, args: list[Any]) -> float:
        """Rate of Change."""
        series, period = self._expect_series(args, length=BINARY)
        return self._roc(series, period)

    def _builtin_ta_wpr(self, args: list[Any]) -> float:
        """Williams %R."""
        msg = "ta.wpr expects high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        return self._wpr(highs, lows, closes, length)

    def _builtin_ta_tsi(self, args: list[Any]) -> float | None:
        """True Strength Index."""
        msg = "ta.tsi expects series and two lengths"
        if len(args) != TERNARY:
            self._error(msg)
        series = self._expect_list(args[0], msg)
        long_period = self._expect_int(args[1], msg)
        short_period = self._expect_int(args[2], msg)
        return self._tsi(series, long_period, short_period)

    def _builtin_ta_valuewhen(self, args: list[Any]) -> Any:
        """Get value when condition was true."""
        msg = "ta.valuewhen expects condition, source, and optional occurrence"
        if len(args) not in {BINARY, TERNARY}:
            self._error(msg)
        condition = self._expect_list(args[0], msg)
        source = self._expect_list(args[1], msg)
        occurrence = self._expect_int(args[2], msg) if len(args) == TERNARY else 0
        return self._valuewhen(condition, source, occurrence)

    def _builtin_ta_rsi_divergence(self, args: list[Any]) -> list[float | None]:
        """RSI Divergence Detector."""
        if len(args) < BINARY:
            msg = "ta.rsi_divergence() requires 2 arguments: rsi_series, period"
            self._error(msg)

        rsi_series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "ta.rsi_divergence period must be integer")

        divergence_values = []
        for i in range(len(rsi_series)):
            if i < period:
                divergence_values.append(0.0)
                continue

            start_idx = max(0, i - period)
            rsi_values = [rsi_series[j] for j in range(start_idx, i + 1) if rsi_series[j] is not None]

            if len(rsi_values) < 2:
                divergence_values.append(0.0)
                continue

            rsi_min = min(rsi_values)
            rsi_max = max(rsi_values)
            rsi_range = rsi_max - rsi_min

            if rsi_range > 0:
                divergence = (rsi_series[i] - rsi_min) / rsi_range * 2 - 1
            else:
                divergence = 0.0

            divergence_values.append(divergence)

        return divergence_values

    def _builtin_ta_macd_signal(self, args: list[Any]) -> float | None:
        """MACD Signal Strength."""
        if len(args) < BINARY:
            msg = "ta.macd_signal() requires 2 arguments: macd_line, signal_line"
            self._error(msg)

        macd_line = args[0]
        signal_line = args[1]

        if macd_line is None or signal_line is None:
            return None

        strength = float(macd_line) - float(signal_line)
        return strength

    def _builtin_ta_stoch_smooth(self, args: list[Any]) -> list[float | None]:
        """Smoothed Stochastic Oscillator."""
        if len(args) < 6:
            msg = "ta.stoch_smooth() requires 6 arguments: high, low, close, period, smooth_k, smooth_d"
            self._error(msg)

        high_series = args[0] if isinstance(args[0], list) else [args[0]]
        low_series = args[1] if isinstance(args[1], list) else [args[1]]
        close_series = args[2] if isinstance(args[2], list) else [args[2]]
        period = self._expect_int(args[3], "ta.stoch_smooth period must be integer")
        smooth_k = self._expect_int(args[4], "ta.stoch_smooth smooth_k must be integer")
        smooth_d = self._expect_int(args[5], "ta.stoch_smooth smooth_d must be integer")

        # Calculate raw stochastic
        stoch_values = []
        for i in range(len(close_series)):
            start_idx = max(0, i - period + 1)
            high_max = max(high_series[j] for j in range(start_idx, i + 1) if j < len(high_series))
            low_min = min(low_series[j] for j in range(start_idx, i + 1) if j < len(low_series))
            c = close_series[i] if i < len(close_series) else 0

            hl_range = high_max - low_min
            if hl_range != 0:
                stoch = 100 * (c - low_min) / hl_range
            else:
                stoch = 50.0

            stoch_values.append(stoch)

        # Smooth stochastic
        smooth_k_ema = self._ema(stoch_values, smooth_k)
        smooth_d_ema = self._ema(smooth_k_ema, smooth_d)

        return smooth_d_ema

    # Helper implementations

    def _rsi(self, series: list[float], period: int) -> float | None:
        """RSI calculation."""
        if len(series) < period + 1:
            return None
        gains: list[float] = []
        losses: list[float] = []
        for idx in range(1, len(series)):
            change = series[idx] - series[idx - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        avg_gain = self._rma(gains, period)[-1]
        avg_loss = self._rma(losses, period)[-1]
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _stoch(
        self,
        highs: list[Any],
        lows: list[Any],
        closes: list[Any],
        period: int,
        smooth_k: int,
    ) -> tuple[float, float]:
        """Stochastic calculation."""
        low_n = self._min_series(lows, period)
        high_n = self._max_series(highs, period)
        raw_values: list[float | None] = []
        for idx, close in enumerate(closes):
            high_value = high_n[idx]
            low_value = low_n[idx]
            if high_value is not None and low_value is not None and high_value != low_value:
                raw_values.append(100 * (close - low_value) / (high_value - low_value))
            else:
                raw_values.append(None)
        valid_values = [value for value in raw_values if value is not None]
        if not valid_values:
            return 0.0, 0.0
        last_k = valid_values[-1]
        if len(valid_values) <= smooth_k + 1:
            return last_k, 0.0
        smoothed_k = self._ema(valid_values, smooth_k)
        if not smoothed_k:
            return last_k, 0.0
        last_d = smoothed_k[-1]
        if last_d is None:
            last_d = 0.0
        return last_k, last_d

    def _macd(
        self,
        series: list[float],
        fast: int,
        slow: int,
        signal: int,
    ) -> tuple[float, float, float]:
        """MACD calculation."""
        ema_fast = self._ema(series, fast)
        ema_slow = self._ema(series, slow)
        macd_line = [
            fast_val - slow_val if fast_val is not None and slow_val is not None else None
            for fast_val, slow_val in zip(ema_fast, ema_slow, strict=True)
        ]
        signal_line = self._ema(macd_line, signal)
        histogram = [
            macd_val - sig_val if macd_val is not None and sig_val is not None else None
            for macd_val, sig_val in zip(macd_line, signal_line, strict=True)
        ]
        last_macd = next(
            (value for value in reversed(macd_line) if value is not None),
            0.0,
        )
        last_signal = next(
            (value for value in reversed(signal_line) if value is not None),
            0.0,
        )
        last_hist = next(
            (value for value in reversed(histogram) if value is not None),
            0.0,
        )
        return last_macd, last_signal, last_hist

    def _cci(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        """CCI calculation."""
        if period <= 0 or len(closes) < period:
            return 0.0
        typical_prices = [(high + low + close) / 3 for high, low, close in zip(highs, lows, closes, strict=True)]
        sma_values = self._sma(typical_prices, period)
        mean_devs: list[float | None] = []
        for idx in range(len(typical_prices)):
            if idx < period - 1:
                mean_devs.append(None)
                continue
            window = typical_prices[idx - period + 1 : idx + 1]
            sma_value = sma_values[idx]
            if sma_value is None:
                mean_devs.append(None)
                continue
            mean_devs.append(statistics.mean(abs(value - sma_value) for value in window))
        last_mean_dev = next(
            (value for value in reversed(mean_devs) if value not in {None, 0}),
            None,
        )
        if last_mean_dev is None:
            return 0.0
        last_tp = next(
            (value for value in reversed(typical_prices) if value is not None),
            0,
        )
        last_sma = next(
            (value for value in reversed(sma_values) if value is not None),
            0,
        )
        return (last_tp - last_sma) / (0.015 * last_mean_dev)

    def _roc(self, series: list[float], period: int) -> float:
        """Rate of Change calculation."""
        if period <= 0 or len(series) <= period:
            return 0.0
        previous_index = len(series) - period - 1
        if previous_index < 0:
            return 0.0
        baseline = series[previous_index]
        if baseline in {None, 0}:
            return 0.0
        earlier_index = previous_index - 1
        denominator = baseline
        if earlier_index >= 0:
            earlier = series[earlier_index]
            if earlier not in {None, 0}:
                denominator = earlier
        change = series[-1] - baseline
        return 100 * change / denominator

    def _wpr(
        self,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        """Williams %R calculation."""
        if len(closes) < period or period <= 0:
            return 0.0
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        if highest_high == lowest_low:
            return 0.0
        return -100 * (highest_high - closes[-1]) / (highest_high - lowest_low)

    def _tsi(
        self,
        series: list[float],
        long_period: int,
        short_period: int,
    ) -> float | None:
        """True Strength Index calculation."""
        if len(series) < long_period + short_period:
            return None
        momentum = [series[idx] - series[idx - 1] for idx in range(1, len(series))]
        abs_momentum = [abs(value) for value in momentum]
        ema_mom = self._ema(momentum, long_period)
        ema_ema_mom = self._ema(ema_mom, short_period)
        ema_abs = self._ema(abs_momentum, long_period)
        ema_ema_abs = self._ema(ema_abs, short_period)
        if ema_ema_abs[-1] == 0:
            return 0
        return 100 * (ema_ema_mom[-1] / ema_ema_abs[-1])

    def _valuewhen(
        self,
        condition: list[bool],
        source: list[Any],
        occurrence: int,
    ) -> Any:
        """Valuewhen calculation."""
        indices = [index for index, flag in enumerate(condition) if flag]
        if not indices or occurrence >= len(indices):
            return None
        return source[indices[-(occurrence + 1)]]
