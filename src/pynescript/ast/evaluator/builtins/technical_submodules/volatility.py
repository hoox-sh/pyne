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

"""Volatility indicators module - ATR, Bollinger Bands, Keltner, StochRSI, etc."""

from __future__ import annotations

import math
import statistics

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import TERNARY
from .core import TechnicalHelpers


class VolatilityIndicators(TechnicalHelpers):
    """Volatility and price action indicators."""

    def _builtin_ta_stdev(self, args: list[Any]) -> float | None:
        """Standard Deviation."""
        series, period = self._expect_series(args, length=BINARY)
        if self._use_incremental_ta():
            return self._stdev_inc_update(series, period)
        return self._stdev(series, period)

    def _builtin_ta_atr(self, args: list[Any]) -> Any:
        """Average True Range.

        TradingView: ``ta.atr(length)``. Also accepts legacy
        ``ta.atr(high, low, close, length)`` for unit tests.
        """
        if len(args) == 1 and self._is_period_like(args[0]):
            length = self._expect_int(args[0], "ta.atr length must be an integer")
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if self._use_incremental_ta():
                return self._atr_inc_update(highs, lows, closes, length)
            return self._finalize_series(self._atr(highs, lows, closes, length))
        msg = "ta.atr expects length, or high, low, close, and length"
        if len(args) != QUATERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        length = self._expect_int(args[3], msg)
        if self._use_incremental_ta():
            return self._atr_inc_update(highs, lows, closes, length)
        return self._finalize_series(self._atr(highs, lows, closes, length))

    def _builtin_ta_tr(self, args: list[Any]) -> Any:
        """True Range — TV form ``ta.tr(handle_na?)`` or legacy 3-arg."""
        if len(args) <= 1:
            highs = self._context_series("high")
            lows = self._context_series("low")
            closes = self._context_series("close")
            if self._use_incremental_ta():
                return self._tr_inc_update(highs, lows, closes)
            return self._finalize_series(self._tr(highs, lows, closes))
        msg = "ta.tr expects high, low, and close"
        if len(args) != TERNARY:
            self._error(msg)
        highs = self._expect_list(args[0], msg)
        lows = self._expect_list(args[1], msg)
        closes = self._expect_list(args[2], msg)
        if self._use_incremental_ta():
            return self._tr_inc_update(highs, lows, closes)
        return self._finalize_series(self._tr(highs, lows, closes))

    def _builtin_ta_bb(
        self,
        args: list[Any],
    ) -> tuple[float | None, float | None, float | None]:
        """Bollinger Bands.

        Forms:
        - ``ta.bb(length, mult)`` — source defaults to close
        - ``ta.bb(source, length, mult)``
        """
        msg = "ta.bb expects series, length, and multiplier"
        use_inc = self._use_incremental_ta()
        if len(args) == BINARY and self._is_period_like(args[0]):
            length = self._expect_int(args[0], msg)
            multiplier = args[1]
            series = self._context_source("close") if use_inc else self._context_series("close")
        elif len(args) == TERNARY:
            length = self._expect_int(args[1], msg)
            multiplier = args[2]
            series = self._as_series_or_raw(args[0], last_sample_ok=True)
        else:
            self._error(msg)
            return None, None, None
        # Unwrap series/wrappers for mult
        if hasattr(multiplier, "current") and not isinstance(multiplier, (list, tuple, str, bytes, int, float)):
            multiplier = multiplier.current
        if not isinstance(multiplier, int | float):
            self._error("ta.bb expects numeric multiplier")
        if use_inc:
            return self._bb_inc_update(series, length, float(multiplier))
        return self._bollinger_bands(series, length, multiplier)

    def _builtin_ta_bbw(self, args: list[Any]) -> float | None:
        """Bollinger Band Width: (upper - lower) / middle.

        Forms: ``ta.bbw(source, length, mult)`` or ``ta.bbw(length, mult)``.
        """
        msg = "ta.bbw expects series, length, and multiplier"
        if len(args) not in {BINARY, TERNARY}:
            self._error(msg)
        # ``_builtin_ta_bb`` MRO may resolve to BasicIndicators; both paths
        # honor PYNE_TA_INCREMENTAL. BB returns (upper, middle, lower).
        upper, middle, lower = self._builtin_ta_bb(args)
        if middle is None or upper is None or lower is None:
            return None
        if middle == 0:
            return None
        return (upper - lower) / middle

    def _builtin_ta_alma(self, args: list[Any]) -> float | None:
        """Arnaud Legoux Moving Average.

        ta.alma(series, length, offset=0.85, sigma=6)
        """
        if len(args) < BINARY:
            self._error("ta.alma requires series and length")
        length = self._expect_int(args[1], "length")
        offset = float(args[2]) if len(args) > 2 and isinstance(args[2], (int, float)) else 0.85
        sigma = float(args[3]) if len(args) > 3 and isinstance(args[3], (int, float)) else 6.0
        if self._use_incremental_ta():
            series = self._as_series_or_raw(args[0], last_sample_ok=True)
            return self._alma_inc_update(series, length, offset, sigma)
        series = self._as_series(args[0]) if hasattr(self, "_as_series") else self._expect_list(args[0], "series")
        if length <= 0 or len(series) < length:
            return None
        window = series[-length:]
        if any(v is None for v in window):
            valid = [v for v in window if v is not None]
            if len(valid) < length:
                return None
        # ALMA weights
        m = offset * (length - 1)
        s = length / sigma
        weights = []
        for i in range(length):
            w = math.exp(-((i - m) ** 2) / (2 * s * s))
            weights.append(w)
        wsum = sum(weights)
        if wsum == 0:
            return None
        total = 0.0
        for i, v in enumerate(window):
            if v is None:
                return None
            total += float(v) * weights[i]
        return total / wsum

    def _builtin_ta_cmo(self, args: list[Any]) -> float | None:
        """Chande Momentum Oscillator.

        ta.cmo(source, length)
        """
        series, length = self._expect_series(args, length=BINARY, last_sample_ok=True)
        if self._use_incremental_ta():
            return self._cmo_inc_update(series, length)
        if length <= 0 or len(series) < length + 1:
            return None
        window = series[-(length + 1) :]
        up = 0.0
        down = 0.0
        for i in range(1, len(window)):
            a, b = window[i - 1], window[i]
            if a is None or b is None:
                continue
            diff = float(b) - float(a)
            if diff > 0:
                up += diff
            else:
                down += -diff
        denom = up + down
        if denom == 0:
            return 0.0
        return 100.0 * (up - down) / denom

    def _builtin_ta_correlation(self, args: list[Any]) -> float | None:
        """Pearson correlation of two series over length.

        ta.correlation(source1, source2, length)
        """
        if len(args) != TERNARY:
            self._error("ta.correlation requires source1, source2, length")
        length = self._expect_int(args[2], "length")
        if self._use_incremental_ta():
            s1 = self._as_series_or_raw(args[0], last_sample_ok=True)
            s2 = self._as_series_or_raw(args[1], last_sample_ok=True)
            return self._correlation_inc_update(s1, s2, length)
        s1 = self._as_series(args[0]) if hasattr(self, "_as_series") else self._expect_list(args[0], "source1")
        s2 = self._as_series(args[1]) if hasattr(self, "_as_series") else self._expect_list(args[1], "source2")
        if length < 2:
            return None
        n = min(len(s1), len(s2), length)
        if n < 2 or len(s1) < length or len(s2) < length:
            return None
        a = s1[-length:]
        b = s2[-length:]
        pairs = [(float(x), float(y)) for x, y in zip(a, b) if x is not None and y is not None]
        if len(pairs) < 2:
            return None
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        denx = sum((x - mx) ** 2 for x in xs) ** 0.5
        deny = sum((y - my) ** 2 for y in ys) ** 0.5
        if denx == 0 or deny == 0:
            return None
        return num / (denx * deny)

    def _builtin_ta_kc(self, args: list[Any]) -> tuple[float, float, float]:
        """Keltner Channels.

        TradingView: ``ta.kc(series, length, mult) → [middle, upper, lower]``
        using ATR of chart H/L/C. Legacy 4-arg ``(high, low, close, length)``
        still accepted (mult defaults to 1).
        """
        mult = 1.0
        use_inc = self._use_incremental_ta()
        if len(args) == TERNARY and self._is_period_like(args[1]):
            # TV form: source, length, mult
            length = self._expect_int(args[1], "ta.kc length must be integer")
            m = args[2]
            current = getattr(m, "current", None)
            if current is not None and not isinstance(m, (list, tuple, str, bytes, int, float)):
                m = current
            if isinstance(m, (int, float)) and not isinstance(m, bool):
                mult = float(m)
            if use_inc:
                closes = self._as_series_or_raw(args[0], last_sample_ok=True)
                highs = self._context_source("high") or closes
                lows = self._context_source("low") or closes
                return self._kc_inc_update(highs, lows, closes, length, mult)
            closes = self._as_series(args[0])
            highs = self._context_series("high") or closes
            lows = self._context_series("low") or closes
        elif len(args) in {TERNARY, QUATERNARY} and not self._is_period_like(args[1]):
            # Legacy: high, low, close [, length]
            length = (
                self._expect_int(args[3], "ta.kc length must be integer")
                if len(args) > TERNARY
                else 20
            )
            if use_inc:
                return self._kc_inc_update(args[0], args[1], args[2], length, mult)
            highs = self._expect_list(args[0], "ta.kc takes high, low, close series, length")
            lows = self._expect_list(args[1], "ta.kc takes high, low, close series, length")
            closes = self._expect_list(args[2], "ta.kc takes high, low, close series, length")
        elif len(args) >= QUATERNARY:
            length = self._expect_int(args[3], "ta.kc length must be integer")
            if len(args) > QUATERNARY and isinstance(args[4], (int, float)):
                mult = float(args[4])
            if use_inc:
                return self._kc_inc_update(args[0], args[1], args[2], length, mult)
            highs = self._expect_list(args[0], "ta.kc takes high, low, close series, length")
            lows = self._expect_list(args[1], "ta.kc takes high, low, close series, length")
            closes = self._expect_list(args[2], "ta.kc takes high, low, close series, length")
        else:
            self._error("ta.kc takes (series, length, mult) or (high, low, close, length)")
            return math.nan, math.nan, math.nan

        if length < 1:
            self._error("ta.kc length must be positive")

        # Align series lengths on the trailing edge
        n = min(len(highs), len(lows), len(closes)) if highs and lows and closes else 0
        if n == 0:
            return math.nan, math.nan, math.nan
        highs, lows, closes = highs[-n:], lows[-n:], closes[-n:]

        ema_vals = self._ema(closes, length)
        middle = ema_vals[-1] if ema_vals else math.nan
        atr_series = self._atr(highs, lows, closes, length)
        atr_val = atr_series[-1] if atr_series else 0
        channel_width = (atr_val or 0) * mult
        upper = middle + channel_width if middle is not None and middle == middle else math.nan
        lower = middle - channel_width if middle is not None and middle == middle else math.nan
        return middle, upper, lower

    def _builtin_ta_kcw(self, args: list[Any]) -> float:
        """Keltner Channels Width."""
        _, upper, lower = self._builtin_ta_kc(args)
        if isinstance(upper, float) and math.isnan(upper):
            return math.nan
        if isinstance(lower, float) and math.isnan(lower):
            return math.nan
        try:
            return float(upper) - float(lower)
        except (TypeError, ValueError):
            return math.nan

    def _builtin_ta_linreg(self, args: list[Any]) -> float:
        """Linear Regression value.

        Length < 2 soft-returns na (matches TV / BasicIndicators path).
        """
        series, length = self._expect_series(args, length=BINARY)

        if length < BINARY:
            return math.nan
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

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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

        if self._use_incremental_ta():
            closes = self._context_source("close")
            return self._stochrsi_inc_update(closes, rsi_length, stoch_length)

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
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
        """Bollinger Bands calculation.

        In bar-mode incremental hosts, middle uses call-site SMA state (O(1)
        after warm-up) instead of full-history ``_sma`` each bar.
        """
        if self._use_incremental_ta():
            return self._bb_inc_update(series, period, float(multiplier))
        sma_values = self._sma(series, period)
        middle = sma_values[-1] if sma_values else None
        deviation = self._stdev(series, period)
        if middle is None or deviation is None:
            return None, None, None
        upper = middle + deviation * multiplier
        lower = middle - deviation * multiplier
        return upper, middle, lower
