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

"""Advanced Technical Indicators - Tier 5-8 (Complex Analysis & Strategy Synthesis)."""

from __future__ import annotations

import math
import statistics

from typing import Any

from .core import BINARY
from .core import QUATERNARY
from .core import QUINARY
from .core import TERNARY
from .core import TechnicalHelpers


# Constants for technical indicator calculations
MIN_PRICE_EPSILON = 1e-10
ATR_MULTIPLIER_HIGH = 1.5
ATR_MULTIPLIER_EXTREME = 2.0
ATR_THRESHOLD = 0.5
RSI_PERCENTILE = 50.0
DONCHIAN_MIN_LENGTH = 1
ICHIMOKU_KIJUN_PERIOD = 26
ICHIMOKU_SENKOU_B_PERIOD = 52
KELLY_MIN_VALUE = 0.0
KELLY_MAX_VALUE = 1.0
PROBABILITY_MAX = 1.0
PROBABILITY_MIN = 0.0
PROBABILITY_BIAS = 0.1
PROBABILITY_COEFFICIENT = 0.8
STOCHRSI_MULTIPLIER = 0.33
STOCHRSI_EMA_WEIGHT = 0.67
TREND_STRENGTH_ADX_WEIGHT = 0.6
TREND_STRENGTH_RSI_WEIGHT = 40.0
UD_SIGNAL_WEIGHT = 0.6
VOLUME_PROFILE_FACTOR = 1.0
KIJUN_OPTIMAL = 26
TENKAN_OPTIMAL = 9
MIN_ARG_COUNT_1 = 1
MIN_ARG_COUNT_2 = 2
MIN_ARG_COUNT_3 = 3
MIN_ARG_COUNT_4 = 4
MIN_ARG_COUNT_5 = 5
MINIMUM_CANDLES = 2
MAX_PRICE_VALUE = 100.0
ADX_MAX_VALUE = 100
KELLY_RISK_PERCENTAGE = 100.0
DEFAULT_ACCOUNT_SIZE = 10000.0
DEFAULT_RISK_PERCENT = 0.01
DEFAULT_RSI_MIDPOINT = 50.0
NEAR_ZERO_THRESHOLD = 0.0


class AdvancedIndicators(TechnicalHelpers):
    """Advanced Tier 5-8 indicators: Market regimes, strategy synthesis, microstructure."""

    # -- Tier 5: Market Structure & Advanced Patterns ----------------------

    def _builtin_ta_ichimoku(self, args: list[Any]) -> dict[str, float | None]:
        """Ichimoku Cloud Components."""
        if len(args) < BINARY:
            msg = "ta.ichimoku() requires 2 arguments: fast_period, slow_period"
            self._error(msg)

        fast_period = self._expect_int(args[0], "fast_period must be integer")
        slow_period = self._expect_int(args[1], "slow_period must be integer")

        min_period = 1
        if fast_period < min_period or slow_period < min_period:
            msg = "Ichimoku periods must be >= 1"
            self._error(msg)

        highs = (getattr(self, "current_series", None) or {}).get("high", [])
        lows = (getattr(self, "current_series", None) or {}).get("low", [])

        if not highs or not lows:
            return {"tenkan_sen": None, "kijun_sen": None, "senkou_span_a": None, "senkou_span_b": None}

        # Tenkan-sen: 9-period high-low midpoint
        tenkan = None
        if len(highs) >= fast_period:
            fast_high = max(highs[-fast_period:])
            fast_low = min(lows[-fast_period:])
            tenkan = (fast_high + fast_low) / 2.0

        # Kijun-sen: 26-period high-low midpoint
        kijun = None
        if len(highs) >= slow_period:
            slow_high = max(highs[-slow_period:])
            slow_low = min(lows[-slow_period:])
            kijun = (slow_high + slow_low) / 2.0

        # Senkou Span A: midpoint of tenkan and kijun
        senkou_a = None
        if tenkan is not None and kijun is not None:
            senkou_a = (tenkan + kijun) / 2.0

        # Senkou Span B: 52-period high-low midpoint
        senkou_b = None
        if len(highs) >= ICHIMOKU_SENKOU_B_PERIOD:
            high_52 = max(highs[-ICHIMOKU_SENKOU_B_PERIOD:])
            low_52 = min(lows[-ICHIMOKU_SENKOU_B_PERIOD:])
            senkou_b = (high_52 + low_52) / 2.0

        return {"tenkan_sen": tenkan, "kijun_sen": kijun, "senkou_span_a": senkou_a, "senkou_span_b": senkou_b}

    def _builtin_ta_donchian(self, args: list[Any]) -> dict[str, float | None]:
        """Donchian Channels."""
        unary = 1
        if len(args) < unary:
            msg = "ta.donchian() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < DONCHIAN_MIN_LENGTH:
            msg = "Donchian length must be >= 1"
            self._error(msg)

        highs = (getattr(self, "current_series", None) or {}).get("high", [])
        lows = (getattr(self, "current_series", None) or {}).get("low", [])

        if not highs or not lows or len(highs) < length:
            return {"high": None, "low": None, "mid": None}

        high_val = max(highs[-length:])
        low_val = min(lows[-length:])
        mid_val = (high_val + low_val) / 2.0

        return {"high": high_val, "low": low_val, "mid": mid_val}

    def _builtin_ta_market_condition(self, args: list[Any]) -> str:
        """Market Condition Detection."""
        if len(args) < QUATERNARY:
            msg = "ta.market_condition() requires 4 arguments"
            self._error(msg)

        close_list = args[0] if isinstance(args[0], list) else [args[0]]
        atr_list = args[1] if isinstance(args[1], list) else [args[1]]
        sma_period = self._expect_int(args[2], "sma_period must be integer")
        stdev_period = self._expect_int(args[3], "stdev_period must be integer")

        if len(close_list) < max(sma_period, stdev_period):
            return "ranging"

        current_close = close_list[-1] if isinstance(close_list[-1], (int, float)) else 0
        current_atr = atr_list[-1] if isinstance(atr_list[-1], (int, float)) else 1.0

        sma_list = self._sma(close_list, sma_period)
        current_sma = sma_list[-1] if sma_list and sma_list[-1] is not None else current_close
        stdev_val = self._stdev(close_list, stdev_period)

        if stdev_val and stdev_val > (current_atr * 1.5):
            return "volatile"
        if current_close > current_sma and current_atr > 0.5:
            return "trending_up"
        if current_close < current_sma and current_atr > 0.5:
            return "trending_down"
        return "ranging"

    def _builtin_ta_volatility_regime(self, args: list[Any]) -> str:
        """Volatility Regime Classification."""
        if len(args) < BINARY:
            msg = "ta.volatility_regime() requires 2 arguments"
            self._error(msg)

        atr_list = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")

        if len(atr_list) < period:
            return "medium"

        recent = [x for x in atr_list[-period:] if isinstance(x, (int, float))]
        if not recent:
            return "medium"

        current_atr = recent[-1]
        avg_atr = sum(recent) / len(recent) if recent else 1.0

        if current_atr < avg_atr * 0.5:
            return "low"
        if current_atr > avg_atr * 2.0:
            return "extreme"
        if current_atr > avg_atr * 1.3:
            return "high"
        return "medium"

    def _builtin_ta_breakout_detection(self, args: list[Any]) -> dict[str, Any]:
        """Breakout Detection."""
        if len(args) < TERNARY:
            msg = "ta.breakout_detection() requires 3 arguments"
            self._error(msg)

        close_val = args[0] if isinstance(args[0], (int, float)) else 0.0
        resistance = args[1] if isinstance(args[1], (int, float)) else 0.0
        support = args[2] if isinstance(args[2], (int, float)) else 0.0

        if close_val > resistance:
            strength = (close_val - resistance) / resistance * 100 if resistance > 0 else 0.0
            return {"is_breakout": True, "breakout_type": "resistance", "breakout_strength": strength}
        if close_val < support:
            strength = (support - close_val) / support * 100 if support > 0 else 0.0
            return {"is_breakout": True, "breakout_type": "support", "breakout_strength": strength}

        return {"is_breakout": False, "breakout_type": "none", "breakout_strength": 0.0}

    def _builtin_ta_inside_bar_pattern(self, args: list[Any]) -> bool:
        """Inside Bar Pattern."""
        if len(args) < BINARY:
            msg = "ta.inside_bar_pattern() requires 2 arguments"
            self._error(msg)

        high_list = args[0] if isinstance(args[0], list) else [args[0]]
        low_list = args[1] if isinstance(args[1], list) else [args[1]]

        if len(high_list) < BINARY or len(low_list) < BINARY:
            return False

        prev_high = high_list[-2] if isinstance(high_list[-2], (int, float)) else 0.0
        prev_low = low_list[-2] if isinstance(low_list[-2], (int, float)) else 0.0
        curr_high = high_list[-1] if isinstance(high_list[-1], (int, float)) else 0.0
        curr_low = low_list[-1] if isinstance(low_list[-1], (int, float)) else 0.0

        return curr_high < prev_high and curr_low > prev_low

    # -- Tier 5: Position Sizing & Risk Management --------------------------

    def _builtin_ta_position_sizing(self, args: list[Any]) -> float:
        """Position Sizing."""
        if len(args) < QUATERNARY:
            msg = "ta.position_sizing() requires 4 arguments"
            self._error(msg)

        account = args[0] if isinstance(args[0], (int, float)) else 10000.0
        risk_pct = args[1] if isinstance(args[1], (int, float)) else 0.01
        entry = args[2] if isinstance(args[2], (int, float)) else 100.0
        stop = args[3] if isinstance(args[3], (int, float)) else 95.0

        risk_amount = account * (risk_pct / 100.0)
        stop_distance = entry - stop

        if abs(stop_distance) < MIN_PRICE_EPSILON:
            return 0.0

        size = risk_amount / abs(stop_distance)
        return max(0.0, size)

    def _builtin_ta_kelly_criterion(self, args: list[Any]) -> float:
        """Kelly Criterion."""
        if len(args) < TERNARY:
            msg = "ta.kelly_criterion() requires 3 arguments"
            self._error(msg)

        win_rate = args[0] if isinstance(args[0], (int, float)) else 0.5
        avg_win = args[1] if isinstance(args[1], (int, float)) else 1.0
        avg_loss = args[2] if isinstance(args[2], (int, float)) else 1.0

        win_rate = max(0.0, min(1.0, win_rate))

        if abs(avg_win) < MIN_PRICE_EPSILON:
            return 0.0

        kelly = (win_rate * avg_win - (1.0 - win_rate) * avg_loss) / avg_win
        return max(0.0, kelly)

    def _builtin_ta_risk_reward_ratio(self, args: list[Any]) -> float | None:
        """Risk/Reward Ratio."""
        if len(args) < TERNARY:
            msg = "ta.risk_reward_ratio() requires 3 arguments"
            self._error(msg)

        entry = args[0] if isinstance(args[0], (int, float)) else 0.0
        stop = args[1] if isinstance(args[1], (int, float)) else 0.0
        target = args[2] if isinstance(args[2], (int, float)) else 0.0

        risk = entry - stop
        if abs(risk) < MIN_PRICE_EPSILON:
            return None

        reward = target - entry
        ratio = reward / risk if risk != 0 else None
        return ratio

    # -- Tier 6: Signal Confluence & Scoring --------------------------------

    def _builtin_ta_strategy_score(self, args: list[Any]) -> float:
        """Strategy Score."""
        if len(args) < QUATERNARY:
            msg = "ta.strategy_score() requires 4 arguments"
            self._error(msg)

        rsi = args[0] if isinstance(args[0], (int, float)) else 50.0
        macd = args[1] if isinstance(args[1], (int, float)) else 0.0
        ema_cross = args[2] if isinstance(args[2], bool) else False
        trend = args[3] if isinstance(args[3], (int, float)) else 50.0

        rsi_normalized = (rsi - 50.0) / 50.0 * 25.0
        macd_normalized = max(-25.0, min(25.0, macd * 50.0))
        ema_bonus = 25.0 if ema_cross else -25.0
        trend_normalized = (trend - 50.0) / 50.0 * 25.0

        score = rsi_normalized + macd_normalized + ema_bonus + trend_normalized
        return max(-100.0, min(100.0, score))

    def _builtin_ta_signal_confluence(self, args: list[Any]) -> dict[str, Any]:
        """Signal Confluence."""
        unary = 1
        if len(args) < unary:
            msg = "ta.signal_confluence() requires 1 argument"
            self._error(msg)

        signals = args[0]
        if not isinstance(signals, dict):
            signals = {}

        signal_count = 0
        bullish_signals = 0
        bearish_signals = 0

        for val in signals.values():
            if isinstance(val, (int, float)):
                if val > 0:
                    bullish_signals += 1
                    signal_count += 1
                elif val < 0:
                    bearish_signals += 1
                    signal_count += 1

        total = len(signals) if signals else 1
        confluence_level = signal_count / total if total > 0 else 0.0

        if bullish_signals > bearish_signals:
            primary = "buy"
        elif bearish_signals > bullish_signals:
            primary = "sell"
        else:
            primary = "neutral"

        return {"signal_count": signal_count, "confluence_level": confluence_level, "primary_signal": primary}

    def _builtin_ta_divergence_detector(self, args: list[Any]) -> dict[str, Any]:
        """Divergence Detector."""
        if len(args) < TERNARY:
            msg = "ta.divergence_detector() requires 3 arguments"
            self._error(msg)

        price_list = args[0] if isinstance(args[0], list) else [args[0]]
        indicator_list = args[1] if isinstance(args[1], list) else [args[1]]
        lookback = self._expect_int(args[2], "lookback must be integer")

        if len(price_list) < lookback or len(indicator_list) < lookback:
            return {"is_bullish": False, "is_bearish": False, "strength": 0.0}

        price_recent = [p for p in price_list[-lookback:] if isinstance(p, (int, float))]
        ind_recent = [i for i in indicator_list[-lookback:] if isinstance(i, (int, float))]

        if len(price_recent) < BINARY or len(ind_recent) < BINARY:
            return {"is_bullish": False, "is_bearish": False, "strength": 0.0}

        price_lower = price_recent[-1] < price_recent[0]
        ind_higher = ind_recent[-1] > ind_recent[0]
        bullish_div = price_lower and ind_higher

        price_higher = price_recent[-1] > price_recent[0]
        ind_lower = ind_recent[-1] < ind_recent[0]
        bearish_div = price_higher and ind_lower

        strength = min(1.0, abs(ind_recent[-1] - ind_recent[0]) / 100.0) if ind_recent else 0.0

        return {"is_bullish": bullish_div, "is_bearish": bearish_div, "strength": strength}

    # -- Tier 6: Market Microstructure ---------------------------------------

    def _builtin_ta_order_flow_imbalance(self, args: list[Any]) -> float:
        """Order Flow Imbalance."""
        msg = "ta.order_flow_imbalance() requires 5 arguments"
        if len(args) < QUINARY:
            self._error(msg)

        high = self._expect_list(args[0], msg)
        low = self._expect_list(args[1], msg)
        close = self._expect_list(args[2], msg)
        volume = self._expect_list(args[3], msg)
        period = self._expect_int(args[4], msg)

        if len(high) < period or len(low) < period or period <= 0:
            return 0.0

        buy_vol = 0.0
        sell_vol = 0.0

        for idx in range(-period, 0):
            h_val = high[idx] if isinstance(high[idx], (int, float)) else 0
            low_val = low[idx] if isinstance(low[idx], (int, float)) else 0
            c_val = close[idx] if isinstance(close[idx], (int, float)) else 0
            v_val = volume[idx] if isinstance(volume[idx], (int, float)) else 0

            if h_val > low_val:
                midpoint = (h_val + low_val) / 2
                if c_val > midpoint:
                    buy_vol += v_val
                else:
                    sell_vol += v_val

        total = buy_vol + sell_vol
        if total == 0:
            return 0.0

        return (buy_vol - sell_vol) / total

    def _builtin_ta_volume_profile_high(self, args: list[Any]) -> float:
        """Volume Profile High."""
        if len(args) < BINARY:
            msg = "ta.volume_profile_high() requires 2 arguments"
            self._error(msg)

        price_list = args[0] if isinstance(args[0], list) else [args[0]]
        volume_list = args[1] if isinstance(args[1], list) else [args[1]]

        if not price_list or not volume_list or len(price_list) != len(volume_list):
            return 0.0

        max_vol = 0.0
        max_price = 0.0

        for p, v in zip(price_list, volume_list, strict=False):
            if isinstance(v, (int, float)) and v > max_vol:
                max_vol = v
                max_price = p if isinstance(p, (int, float)) else 0.0

        return max_price

    def _builtin_ta_volume_profile_low(self, args: list[Any]) -> float:
        """Volume Profile Low - Lowest volume price level.

        ta.volume_profile_low(close, volume, period, levels)
        Returns: Price level with lowest volume
        """
        msg = "ta.volume_profile_low() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)
        levels = self._expect_int(args[3], msg) if len(args) > TERNARY else 10

        if len(close) < period or period <= 0 or levels <= 0:
            return close[-1] if close else 100.0

        data = [(close[i], volume[i]) for i in range(-period, 0)
                if isinstance(close[i], (int, float)) and isinstance(volume[i], (int, float))]

        if not data:
            return close[-1] if close else 100.0

        prices = [p for p, v in data]
        min_price = min(prices)
        max_price = max(prices)

        if min_price == max_price:
            return min_price

        bucket_size = (max_price - min_price) / levels
        buckets = [0.0] * levels
        bucket_prices = [min_price + i * bucket_size for i in range(levels)]

        for price, vol in data:
            bucket_idx = min(int((price - min_price) / bucket_size), levels - 1)
            buckets[bucket_idx] += vol

        min_idx = buckets.index(min(buckets))
        return bucket_prices[min_idx]

    # -- Tier 7: Advanced Economics & Probability ---------------------------

    def _builtin_ta_probability_of_movement(self, args: list[Any]) -> float:
        """Probability of Movement."""
        if len(args) < QUATERNARY:
            msg = "ta.probability_of_movement() requires 4 arguments"
            self._error(msg)

        current = args[0] if isinstance(args[0], (int, float)) else 100.0
        target = args[1] if isinstance(args[1], (int, float)) else 100.0
        atr = args[2] if isinstance(args[2], (int, float)) else 1.0
        period = self._expect_int(args[3], "period must be integer")

        if abs(current) < MIN_PRICE_EPSILON or abs(atr) < MIN_PRICE_EPSILON:
            return 0.5

        distance = abs(target - current)
        expected_move = atr * math.sqrt(period)

        if expected_move == 0:
            return 0.5

        probability = min(1.0, distance / expected_move) * 0.8 + 0.1
        return max(0.0, min(1.0, probability))

    def _builtin_ta_gamma_levels(self, args: list[Any]) -> list[float]:
        """Gamma Levels."""
        if len(args) < TERNARY:
            msg = "ta.gamma_levels() requires 3 arguments"
            self._error(msg)

        volatility = args[0] if isinstance(args[0], (int, float)) else 0.02
        current_price = args[1] if isinstance(args[1], (int, float)) else 100.0
        period = self._expect_int(args[2], "period must be integer")

        vol_adjusted = volatility * math.sqrt(period)
        gamma_distance = current_price * vol_adjusted

        high_level = current_price + gamma_distance
        low_level = current_price - gamma_distance

        return [high_level, low_level]

    def _builtin_ta_trend_strength(self, args: list[Any]) -> float:
        """Trend Strength."""
        expected_args = TERNARY
        if len(args) < expected_args:
            msg = "ta.trend_strength() requires 3 arguments"
            self._error(msg)

        adx_val = args[1] if isinstance(args[1], (int, float)) else 20.0
        rsi_val = args[2] if isinstance(args[2], (int, float)) else 50.0

        adx_normalized = min(100, max(0, adx_val))
        rsi_extremeness = abs(rsi_val - RSI_PERCENTILE) / RSI_PERCENTILE

        strength = (adx_normalized * TREND_STRENGTH_ADX_WEIGHT) + (rsi_extremeness * TREND_STRENGTH_RSI_WEIGHT)
        return min(100.0, max(0.0, strength))

    # -- Tier 8: Capstone & Meta Indicators ---------------------------------

    def _builtin_ta_stochrsi(self, args: list[Any]) -> dict[str, float | None]:
        """Stochastic RSI."""
        if len(args) < BINARY:
            msg = "ta.stochrsi() requires 2 arguments: rsi_length, stoch_length"
            self._error(msg)

        rsi_length = self._expect_int(args[0], "rsi_length must be integer")
        stoch_length = self._expect_int(args[1], "stoch_length must be integer")

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
        signal = stochrsi_val * 0.33 + (
            getattr(self, "_last_stochrsi_signal", stochrsi_val) * 0.67
        )
        self._last_stochrsi_signal = signal

        return {"stochrsi": stochrsi_val, "signal": signal}

    def _builtin_ta_dpo(self, args: list[Any]) -> float | None:
        """Detrended Price Oscillator."""
        unary = 1
        if len(args) < unary:
            msg = "ta.dpo() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < unary:
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

    def _builtin_ta_kst(self, args: list[Any]) -> float | None:
        """Know Sure Thing Oscillator."""
        if len(args) < QUATERNARY:
            msg = "ta.kst() requires 4 arguments: length1, length2, length3, length4"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")
        length4 = self._expect_int(args[3], "length4 must be integer")

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
        if not closes:
            return None

        max_len = max(length1, length2, length3, length4)
        if len(closes) < max_len:
            return None

        # Calculate ROCs (Rate of Change)
        roc1 = (
            (closes[-1] - closes[-length1]) / closes[-length1] * 100
            if len(closes) >= length1
            else 0
        )
        roc2 = (
            (closes[-1] - closes[-length2]) / closes[-length2] * 100
            if len(closes) >= length2
            else 0
        )
        roc3 = (
            (closes[-1] - closes[-length3]) / closes[-length3] * 100
            if len(closes) >= length3
            else 0
        )
        roc4 = (
            (closes[-1] - closes[-length4]) / closes[-length4] * 100
            if len(closes) >= length4
            else 0
        )

        # Weighted sum
        kst_val = roc1 * 1.0 + roc2 * 2.0 + roc3 * 3.0 + roc4 * 4.0
        return kst_val / 10.0

    def _builtin_ta_uo(self, args: list[Any]) -> float | None:
        """Ultimate Oscillator."""
        if len(args) < TERNARY:
            msg = "ta.uo() requires 3 arguments: length1, length2, length3"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")

        closes = (getattr(self, "current_series", None) or {}).get("close", [])
        highs = (getattr(self, "current_series", None) or {}).get("high", [])
        lows = (getattr(self, "current_series", None) or {}).get("low", [])

        if not closes or not highs or not lows or len(closes) < length3:
            return None

        max_len = max(length1, length2, length3)

        # True Range and Buying Pressure
        tr_sum = 0.0
        bp_sum = 0.0
        for i in range(len(closes) - max_len, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i - 1]) if i > 0 else high_low
            low_close = abs(lows[i] - closes[i - 1]) if i > 0 else 0
            tr = max(high_low, high_close, low_close)

            bp = closes[i] - min(lows[i], closes[i - 1]) if i > 0 else 0
            tr_sum += tr
            bp_sum += bp

        if tr_sum == 0:
            return 0.0

        avg1 = bp_sum / tr_sum
        avg2 = bp_sum / tr_sum
        avg3 = bp_sum / tr_sum

        uo_val = 100.0 * ((avg1 * 4.0 + avg2 * 2.0 + avg3) / 7.0)
        return uo_val

    def _builtin_ta_stdev(self, args: list[Any]) -> float | None:
        """Standard Deviation."""
        expected_args = BINARY
        if len(args) < expected_args:
            msg = "ta.stdev() requires 2 arguments: series, period"
            self._error(msg)

        series = args[0] if isinstance(args[0], list) else [args[0]]
        period = self._expect_int(args[1], "period must be integer")

        if len(series) < period:
            return None

        try:
            return statistics.stdev(series[-period:])
        except (ValueError, statistics.StatisticsError):
            return None

    def _builtin_ta_momentum_divergence(self, args: list[Any]) -> dict[str, Any]:
        """Momentum Divergence - Multi-timeframe momentum divergence.

        ta.momentum_divergence(price, momentum_fast, momentum_slow)
        Returns: dict with divergence_type, strength, bars_since
        """
        msg = "ta.momentum_divergence() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        price = self._expect_list(args[0], msg)
        mom_fast = self._expect_list(args[1], msg)
        mom_slow = self._expect_list(args[2], msg)

        if len(price) < BINARY or len(mom_fast) < BINARY or len(mom_slow) < BINARY:
            return {"divergence_type": "none", "strength": 0.0, "bars_since": 0}

        price_val = [p for p in price[-2:] if isinstance(p, (int, float))]
        mf_val = [m for m in mom_fast[-2:] if isinstance(m, (int, float))]
        ms_val = [m for m in mom_slow[-2:] if isinstance(m, (int, float))]

        if len(price_val) < BINARY or len(mf_val) < BINARY or len(ms_val) < BINARY:
            return {"divergence_type": "none", "strength": 0.0, "bars_since": 0}

        price_lower = price_val[1] < price_val[0]
        mf_higher = mf_val[1] > mf_val[0]
        ms_higher = ms_val[1] > ms_val[0]

        bullish = price_lower and mf_higher and ms_higher
        bearish = not price_lower and not mf_higher and not ms_higher

        div_type = "bullish" if bullish else ("bearish" if bearish else "none")
        strength = min(1.0, abs(mf_val[1] - mf_val[0]) / 100.0) if mf_val else 0.0

        return {"divergence_type": div_type, "strength": strength, "bars_since": 1}

    def _builtin_ta_acceleration_factor(self, args: list[Any]) -> float:
        """Acceleration Factor - Momentum acceleration/deceleration.

        ta.acceleration_factor(momentum_list, period)
        Returns: Factor (-2.0 to 2.0)
        """
        msg = "ta.acceleration_factor() requires 2 arguments"
        if len(args) < BINARY:
            self._error(msg)

        momentum = self._expect_list(args[0], msg)
        period = self._expect_int(args[1], msg)

        if len(momentum) < period + 1 or period <= 0:
            return 0.0

        momentum_clean = [m for m in momentum[-period - 1 :] if isinstance(m, (int, float))]
        if len(momentum_clean) < BINARY:
            return 0.0

        old_mom = sum(momentum_clean[:-1]) / len(momentum_clean[:-1])
        new_mom = sum(momentum_clean[-1:])

        if abs(old_mom) < MIN_PRICE_EPSILON:
            return 0.0

        acceleration = (new_mom - old_mom) / old_mom
        return max(-2.0, min(2.0, acceleration))

    def _builtin_ta_mean_reversion_score(self, args: list[Any]) -> float:
        """Mean Reversion Score - Probability of price reverting to mean.

        ta.mean_reversion_score(close, sma, stdev, period)
        Returns: Score (0-100)
        """
        msg = "ta.mean_reversion_score() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        sma = self._expect_list(args[1], msg)
        stdev = self._expect_list(args[2], msg)
        period = self._expect_int(args[3], msg)

        if len(close) < period or len(sma) < period or period <= 0:
            return 50.0

        c = close[-1] if isinstance(close[-1], (int, float)) else 100.0
        s = sma[-1] if isinstance(sma[-1], (int, float)) else 100.0
        sd = stdev[-1] if isinstance(stdev[-1], (int, float)) else 1.0

        if sd == 0:
            return 50.0

        distance = abs(c - s) / sd
        score = min(100.0, distance * 20)

        return max(0.0, min(100.0, score))

    def _builtin_ta_momentum_filter(self, args: list[Any]) -> float:
        """Momentum Filter - Adaptive momentum filtering.

        ta.momentum_filter(momentum_raw, volume, period)
        Returns: Filtered momentum value
        """
        msg = "ta.momentum_filter() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        momentum = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)

        if len(momentum) < period or len(volume) < period or period <= 0:
            return 0.0

        vol_sum = sum([v for v in volume[-period:] if isinstance(v, (int, float))])
        mom_data = [(momentum[i], volume[i]) for i in range(-period, 0)
                    if isinstance(momentum[i], (int, float)) and isinstance(volume[i], (int, float))]

        if not mom_data or vol_sum == 0:
            return 0.0

        weighted_mom = sum(m * v for m, v in mom_data) / vol_sum
        return weighted_mom

    def _builtin_ta_economic_impact_score(self, args: list[Any]) -> float:
        """Economic Impact Score - Economic data impact on price.

        ta.economic_impact_score(price_change, volatility, volume_change)
        Returns: Score (0-100)
        """
        msg = "ta.economic_impact_score() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        price_change = args[0] if isinstance(args[0], (int, float)) else 0.0
        volatility = args[1] if isinstance(args[1], (int, float)) else 0.0
        volume_change = args[2] if isinstance(args[2], (int, float)) else 0.0

        pc_score = min(100.0, abs(price_change) * 20)
        vol_score = min(100.0, volatility * 30)
        vc_score = min(100.0, volume_change * 25)

        impact = (pc_score + vol_score + vc_score) / 3
        return max(0.0, min(100.0, impact))

    def _builtin_ta_inflation_proxy_indicator(self, args: list[Any]) -> float:
        """Inflation Proxy Indicator - Inflation estimation from technicals.

        ta.inflation_proxy_indicator(usd_index, commodity_prices, bond_yields)
        Returns: Score (-100 to 100)
        """
        msg = "ta.inflation_proxy_indicator() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        usd_idx = self._expect_list(args[0], msg)
        commodities = self._expect_list(args[1], msg)
        yields = self._expect_list(args[2], msg)

        if not usd_idx or not commodities or not yields:
            return 0.0

        # Calculate USD change
        usd_valid = isinstance(usd_idx[0], (int, float)) and isinstance(usd_idx[-1], (int, float))
        usd_change = -((usd_idx[-1] - usd_idx[0]) / usd_idx[0] * 100) if usd_valid and usd_idx[0] != 0 else 0.0
        # Calculate commodity change
        comm_valid = isinstance(commodities[0], (int, float)) and isinstance(commodities[-1], (int, float))
        if comm_valid and commodities[0] != 0:
            comm_change = ((commodities[-1] - commodities[0]) / commodities[0] * 100)
        else:
            comm_change = 0.0
        # Calculate yields change
        yields_valid = isinstance(yields[-1], (int, float)) and isinstance(yields[0], (int, float))
        yields_change = yields[-1] - yields[0] if yields_valid else 0.0

        inflation_pressure = (usd_change * 0.3 + comm_change * 0.4 + yields_change * 0.3)
        return max(-100.0, min(100.0, inflation_pressure * 10))

    def _builtin_ta_employment_cycle_indicator(self, args: list[Any]) -> str:
        """Employment Cycle Indicator - Employment cycle detection.

        ta.employment_cycle_indicator(cyclical_stocks, defensive_stocks, unemployment_proxy)
        Returns: "early_cycle" | "mid_cycle" | "late_cycle" | "recession"
        """
        msg = "ta.employment_cycle_indicator() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        cyclical = self._expect_list(args[0], msg)
        defensive = self._expect_list(args[1], msg)
        unemployment = self._expect_list(args[2], msg)

        if not cyclical or not defensive or not unemployment:
            return "mid_cycle"

        # Calculate cyclical performance
        cyc_valid = isinstance(cyclical[0], (int, float)) and isinstance(cyclical[-1], (int, float))
        cyc_perf = (cyclical[-1] - cyclical[0]) / cyclical[0] if cyc_valid and cyclical[0] != 0 else 0.0
        # Calculate defensive performance
        def_valid = isinstance(defensive[0], (int, float)) and isinstance(defensive[-1], (int, float))
        def_perf = (defensive[-1] - defensive[0]) / defensive[0] if def_valid and defensive[0] != 0 else 0.0
        unemp = unemployment[-1] if isinstance(unemployment[-1], (int, float)) else 0.05

        if cyc_perf > def_perf and unemp < 0.04:
            return "early_cycle"
        elif cyc_perf > def_perf and unemp < 0.06:
            return "mid_cycle"
        elif cyc_perf < def_perf and unemp > 0.05:
            return "late_cycle"
        else:
            return "recession"

    def _builtin_ta_gdp_growth_proxy(self, args: list[Any]) -> float:
        """GDP Growth Proxy - GDP growth estimation from market signals.

        ta.gdp_growth_proxy(market_breadth, market_volume, price_momentum)
        Returns: Growth estimate (-2 to 4)
        """
        msg = "ta.gdp_growth_proxy() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        breadth = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        momentum = self._expect_list(args[2], msg)

        if not breadth or not volume or not momentum:
            return 0.0

        b_score = (breadth[-1] if isinstance(breadth[-1], (int, float)) else 0.5) * 2 - 1
        # Calculate volume change
        v_valid = isinstance(volume[0], (int, float)) and isinstance(volume[-1], (int, float))
        v_change = ((volume[-1] - volume[0]) / volume[0] * 100) if v_valid and volume[0] != 0 else 0.0
        m_score = (momentum[-1] if isinstance(momentum[-1], (int, float)) else 0.0) / 100.0

        gdp_est = b_score * 1.5 + (v_change / 100.0) + m_score
        return max(-2.0, min(4.0, gdp_est))

    def _builtin_ta_fear_greed_index(self, args: list[Any]) -> float:
        """Fear Greed Index - Market psychology measurement.

        ta.fear_greed_index(rsi, vix_proxy, put_call_ratio, breadth)
        Returns: Score (-100 to 100)
        """
        msg = "ta.fear_greed_index() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        rsi = self._expect_list(args[0], msg)
        vix = self._expect_list(args[1], msg)
        put_call = self._expect_list(args[2], msg)
        breadth = self._expect_list(args[3], msg)

        rsi_val = rsi[-1] if isinstance(rsi[-1], (int, float)) else 50.0
        vix_val = vix[-1] if isinstance(vix[-1], (int, float)) else 2.0
        pc_val = put_call[-1] if isinstance(put_call[-1], (int, float)) else 1.0
        b_val = breadth[-1] if isinstance(breadth[-1], (int, float)) else 0.5

        rsi_fear = (rsi_val - 50) * 1.0
        vix_fear = (vix_val - 2.0) * 10.0
        pc_fear = (1.0 - pc_val) * 50.0
        b_fear = (b_val - 0.5) * 100.0

        fear_index = (rsi_fear + vix_fear + pc_fear + b_fear) / 4
        return max(-100.0, min(100.0, fear_index))

    def _builtin_ta_crowd_sentiment(self, args: list[Any]) -> float:
        """Crowd Sentiment - Crowd consensus strength.

        ta.crowd_sentiment(price_agreement, volume_agreement, time_agreement)
        Returns: Score (0-100)
        """
        msg = "ta.crowd_sentiment() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        price_agr = args[0] if isinstance(args[0], (int, float)) else 0.5
        vol_agr = args[1] if isinstance(args[1], (int, float)) else 0.5
        time_agr = args[2] if isinstance(args[2], (int, float)) else 0.5

        consensus = ((price_agr + vol_agr + time_agr) / 3) * 100
        return max(0.0, min(100.0, consensus))

    def _builtin_ta_contrarian_signal(self, args: list[Any]) -> dict[str, Any]:
        """Contrarian Signal - Contrarian trading opportunity detection.

        ta.contrarian_signal(sentiment, volatility, time_since_extreme)
        Returns: dict with signal, strength, confidence
        """
        msg = "ta.contrarian_signal() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        sentiment = args[0] if isinstance(args[0], (int, float)) else 50.0
        volatility = args[1] if isinstance(args[1], (int, float)) else 1.0
        time_extreme = args[2] if isinstance(args[2], (int, float)) else 10

        if sentiment > 80 and volatility > 2.0 and time_extreme < 5:
            signal = "strong_contrarian"
            strength = 0.9
            confidence = 0.8
        elif sentiment < 20 and volatility > 2.0 and time_extreme < 5:
            signal = "strong_contrarian"
            strength = 0.9
            confidence = 0.8
        elif sentiment > 65 or sentiment < 35:
            signal = "mild_contrarian"
            strength = 0.6
            confidence = 0.6
        elif 45 < sentiment < 55:
            signal = "follow_crowd"
            strength = 0.3
            confidence = 0.4
        else:
            signal = "neutral"
            strength = 0.5
            confidence = 0.5

        return {"signal": signal, "strength": strength, "confidence": confidence}

    def _builtin_ta_cumulative_delta(self, args: list[Any]) -> float:
        """Cumulative Delta - Buy-sell volume delta.

        ta.cumulative_delta(close, volume, period)
        Returns: Cumulative signed volume
        """
        msg = "ta.cumulative_delta() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)

        if len(close) < period or len(volume) < period or period <= 0:
            return 0.0

        delta = 0.0
        for i in range(-period, 0):
            c = close[i] if isinstance(close[i], (int, float)) else 0
            v = volume[i] if isinstance(volume[i], (int, float)) else 0
            if i > -period:
                prev_c = close[i-1] if isinstance(close[i-1], (int, float)) else c
                if c > prev_c:
                    delta += v
                elif c < prev_c:
                    delta -= v

        return delta

    def _builtin_ta_volume_momentum(self, args: list[Any]) -> float:
        """Volume Momentum - Rate of change of volume.

        ta.volume_momentum(volume, period)
        Returns: Momentum (-100 to 100)
        """
        msg = "ta.volume_momentum() requires 2 arguments"
        if len(args) < BINARY:
            self._error(msg)

        volume = self._expect_list(args[0], msg)
        period = self._expect_int(args[1], msg)

        if len(volume) < period + 1 or period <= 0:
            return 0.0

        vol_clean = [v for v in volume[-period - 1 :] if isinstance(v, (int, float))]
        if len(vol_clean) < BINARY:
            return 0.0

        old_vol = sum(vol_clean[:-1]) / len(vol_clean[:-1])
        new_vol = sum(vol_clean[-1:])

        if old_vol == 0:
            return 0.0

        momentum = ((new_vol - old_vol) / old_vol) * 100.0
        return max(-100.0, min(100.0, momentum))

    def _builtin_ta_smart_money_flow(self, args: list[Any]) -> float:
        """Smart Money Flow - Institutional money flow estimation.

        ta.smart_money_flow(price_change, volume, time_since_high, time_since_low)
        Returns: Flow intensity (-1.0 to 1.0)
        """
        msg = "ta.smart_money_flow() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        price_change = args[0] if isinstance(args[0], (int, float)) else 0.0
        volume = args[1] if isinstance(args[1], (int, float)) else 1000.0
        time_high = args[2] if isinstance(args[2], (int, float)) else 10
        time_low = args[3] if isinstance(args[3], (int, float)) else 10

        vol_factor = min(1.0, volume / 5000.0)

        if price_change > 0 and time_high < time_low:
            flow = vol_factor * 0.8
        elif price_change < 0 and time_low < time_high:
            flow = -vol_factor * 0.8
        else:
            flow = 0.0

        return max(-1.0, min(1.0, flow))

    def _builtin_ta_liquidity_score(self, args: list[Any]) -> float:
        """Liquidity Score - Market liquidity measurement.

        ta.liquidity_score(volume, volatility, bid_ask_spread, period)
        Returns: Score (0-100)
        """
        msg = "ta.liquidity_score() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        volume = self._expect_list(args[0], msg)
        volatility = self._expect_list(args[1], msg)
        spread = self._expect_list(args[2], msg)
        period = self._expect_int(args[3], msg)

        if len(volume) < period or len(volatility) < period or len(spread) < period or period <= 0:
            return 50.0

        vol_avg = sum([v for v in volume[-period:] if isinstance(v, (int, float))]) / period if volume else 1000.0
        vol_score = min(100.0, vol_avg / 100.0)

        # Calculate average volatility
        valid_volatility = [v for v in volatility[-period:] if isinstance(v, (int, float))]
        vol_avg_volatility = sum(valid_volatility) / period if volatility else 1.0
        volatility_score = max(0.0, 100.0 - vol_avg_volatility * 50.0)

        spread_avg = sum([s for s in spread[-period:] if isinstance(s, (int, float))]) / period if spread else 0.1
        spread_score = max(0.0, 100.0 - spread_avg * 100.0)

        liquidity = (vol_score * 0.4 + volatility_score * 0.3 + spread_score * 0.3)
        return max(0.0, min(100.0, liquidity))

    def _builtin_ta_volume_thrust(self, args: list[Any]) -> bool:
        """Volume Thrust - Volume surge pattern detection.

        ta.volume_thrust(close, volume, volume_sma, sensitivity)
        Returns: bool
        """
        msg = "ta.volume_thrust() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        vol_sma = self._expect_list(args[2], msg)
        sensitivity = args[3] if isinstance(args[3], (int, float)) else 0.3

        if not close or not volume or not vol_sma:
            return False

        c_val = close[-1] if isinstance(close[-1], (int, float)) else 100.0
        c_prev = close[-2] if len(close) > 1 and isinstance(close[-2], (int, float)) else 100.0
        v_val = volume[-1] if isinstance(volume[-1], (int, float)) else 1000.0
        vs_val = vol_sma[-1] if isinstance(vol_sma[-1], (int, float)) else 1000.0

        volume_spike = v_val > vs_val * (1 + sensitivity)
        price_move = abs(c_val - c_prev) / c_prev > 0.01 if c_prev != 0 else False

        return volume_spike and price_move

    def _builtin_ta_trend_confirmation_score(self, args: list[Any]) -> float:
        """Trend Confirmation Score - Multi-signal trend strength.

        ta.trend_confirmation_score(momentum, trend_alignment, strength, rsi,
                                     rsi_alignment, support_distance)
        Returns: float (0-100)
        """
        senary = 6
        msg = "ta.trend_confirmation_score() requires 6 arguments"
        if len(args) < senary:
            self._error(msg)

        momentum = args[0] if isinstance(args[0], (int, float)) else 0.0
        trend_alignment = args[1] if isinstance(args[1], (int, float)) else 0.0
        strength = args[2] if isinstance(args[2], (int, float)) else 1.0
        rsi = args[3] if isinstance(args[3], (int, float)) else 50.0
        rsi_alignment = args[4] if isinstance(args[4], (int, float)) else 0.0

        momentum_score = min(100.0, abs(momentum) * 20.0)
        trend_score = max(0.0, (trend_alignment + 1.0) / 2.0 * 100.0)
        strength_score = min(100.0, strength * 50.0)
        rsi_score = min(100.0, abs(rsi - 50.0) * 2.0) if abs(rsi - 50.0) > 10.0 else 40.0
        alignment_bonus = 20.0 if abs(rsi_alignment) > 0.5 else 0.0

        total = (momentum_score * 0.25 + trend_score * 0.3 + strength_score * 0.25
                 + rsi_score * 0.15 + alignment_bonus)
        return max(0.0, min(100.0, total))

    def _builtin_ta_market_structure_pivot(self, args: list[Any]) -> dict:
        """Market Structure Pivot - Fractal/Swing/Block detection.

        ta.market_structure_pivot(high_list, low_list, close_list, period, mode)
        Returns: dict with pivot_price, strength, structure
        """
        msg = "ta.market_structure_pivot() requires 5 arguments"
        if len(args) < QUINARY:
            self._error(msg)

        high_list = self._expect_list(args[0], msg)
        low_list = self._expect_list(args[1], msg)
        close_list = self._expect_list(args[2], msg)
        period = self._expect_int(args[3], msg)
        mode = self._expect_int(args[4], msg)

        if (not high_list or not low_list or not close_list
                or len(high_list) < period or period <= 0):
            return {"pivot_price": 100.0, "strength": 50.0, "structure": "neutral"}

        h_vals = [h for h in high_list[-period:] if isinstance(h, (int, float))]
        l_vals = [low_val for low_val in low_list[-period:] if isinstance(low_val, (int, float))]

        if not h_vals or not l_vals:
            return {"pivot_price": 100.0, "strength": 50.0, "structure": "neutral"}

        pivot_high = max(h_vals)
        pivot_low = min(l_vals)
        pivot_price = (pivot_high + pivot_low) / 2.0
        pivot_range = pivot_high - pivot_low

        if mode == 0:  # Fractal
            structure = "fractal"
            strength = min(100.0, pivot_range * 2.0)
        elif mode == 1:  # Swing
            structure = "swing"
            strength = min(100.0, pivot_range * 1.5)
        else:  # Block
            structure = "block"
            strength = min(100.0, pivot_range * 0.5)

        return {
            "pivot_price": pivot_price,
            "structure": structure,
            "strength": strength,
        }

    def _builtin_ta_volatility_regime_score(self, args: list[Any]) -> dict:
        """Volatility Regime Score - Regime classification.

        ta.volatility_regime_score(atr_list, volatility_list, vix_list, threshold)
        Returns: dict with regime, volatility_score, momentum
        """
        msg = "ta.volatility_regime_score() requires 4 arguments"
        if len(args) < QUATERNARY:
            self._error(msg)

        atr_list = self._expect_list(args[0], msg)
        vol_list = self._expect_list(args[1], msg)
        vix_list = self._expect_list(args[2], msg)
        threshold = args[3] if isinstance(args[3], (int, float)) else 50.0

        if not atr_list or not vol_list or not vix_list:
            return {"regime": "normal", "volatility_score": 50.0, "momentum": "stable"}

        atr_val = atr_list[-1] if isinstance(atr_list[-1], (int, float)) else 2.0
        vol_val = vol_list[-1] if isinstance(vol_list[-1], (int, float)) else 0.02
        vix_val = vix_list[-1] if isinstance(vix_list[-1], (int, float)) else 15.0

        atr_score = min(100.0, atr_val * 20.0)
        vol_score = min(100.0, vol_val * 100.0)
        vix_score = min(100.0, vix_val * 2.0)

        volatility_score = (atr_score * 0.4 + vol_score * 0.3 + vix_score * 0.3)

        if volatility_score < threshold * 0.5:
            regime = "low"
        elif volatility_score < threshold:
            regime = "normal"
        elif volatility_score < threshold * 1.5:
            regime = "high"
        else:
            regime = "extreme"

        # Momentum detection
        if len(atr_list) > 1 and isinstance(atr_list[-2], (int, float)):
            prev_atr = atr_list[-2]
            if atr_val > prev_atr * 1.05:
                momentum = "accelerating"
            elif atr_val < prev_atr * 0.95:
                momentum = "decelerating"
            else:
                momentum = "stable"
        else:
            momentum = "stable"

        return {
            "regime": regime,
            "volatility_score": volatility_score,
            "momentum": momentum,
        }

    def _builtin_ta_correlation_filter(self, args: list[Any]) -> dict:
        """Correlation Filter - Multi-signal agreement.

        ta.correlation_filter(signal1_list, signal2_list, signal3_list,
                              num_signals, threshold)
        Returns: dict with is_correlated, signal_agreement, divergence_count
        """
        msg = "ta.correlation_filter() requires 5 arguments"
        if len(args) < QUINARY:
            self._error(msg)

        sig1 = self._expect_list(args[0], msg)
        sig2 = self._expect_list(args[1], msg)
        sig3 = self._expect_list(args[2], msg)
        _ = self._expect_int(args[3], msg)
        threshold = args[4] if isinstance(args[4], (int, float)) else 0.7

        signals = [sig1, sig2, sig3]
        valid_signals = [s for s in signals if s and len(s) > 0]

        if len(valid_signals) < BINARY:
            return {
                "is_correlated": False,
                "signal_agreement": 0,
                "divergence_count": 0,
            }

        last_vals = []
        for sig in valid_signals:
            if sig and isinstance(sig[-1], (int, float)):
                last_vals.append(sig[-1])

        if not last_vals:
            return {
                "is_correlated": False,
                "signal_agreement": 0,
                "divergence_count": 0,
            }

        agreement_count = 0
        divergence_count = 0

        for i in range(len(last_vals) - 1):
            for j in range(i + 1, len(last_vals)):
                product = last_vals[i] * last_vals[j]
                if product > 0:
                    agreement_count += 1
                else:
                    divergence_count += 1

        total_pairs = len(last_vals) * (len(last_vals) - 1) / 2.0
        signal_agreement = (agreement_count / total_pairs * 100.0) if total_pairs > 0 else 0
        is_correlated = signal_agreement / 100.0 >= threshold

        return {
            "is_correlated": is_correlated,
            "signal_agreement": signal_agreement,
            "divergence_count": divergence_count,
        }

    def _builtin_ta_advanced_breakout_detector(self, args: list[Any]) -> dict:
        """Advanced Breakout Detector - Multiple breakout types.

        ta.advanced_breakout_detector(price_list, volume_list, level, lookback,
                                      volume_multiplier)
        Returns: dict with breakout_detected, breakout_type, pullback_probability
        """
        msg = "ta.advanced_breakout_detector() requires 5 arguments"
        if len(args) < QUINARY:
            self._error(msg)

        price = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        level = args[2] if isinstance(args[2], (int, float)) else 100.0
        lookback = self._expect_int(args[3], msg)
        vol_mult = args[4] if isinstance(args[4], (int, float)) else 0.5

        if not price or not volume or len(price) < BINARY or lookback <= 0:
            return {
                "breakout_detected": False,
                "breakout_type": "none",
                "pullback_probability": 0.5,
            }

        current_price = price[-1] if isinstance(price[-1], (int, float)) else 100.0
        prev_price = price[-2] if isinstance(price[-2], (int, float)) else 100.0
        current_vol = volume[-1] if isinstance(volume[-1], (int, float)) else 1000.0

        recent_vol = [v for v in volume[-lookback:] if isinstance(v, (int, float))]
        avg_vol = sum(recent_vol) / len(recent_vol) if recent_vol else 1000.0

        gap_breakout = current_price > level and prev_price <= level
        close_breakout = current_price > level and abs(current_price - level) < 0.5
        volume_break = current_vol > avg_vol * (1.0 + vol_mult)

        breakout_detected = gap_breakout or close_breakout or volume_break

        if gap_breakout:
            breakout_type = "gap"
        elif close_breakout and volume_break:
            breakout_type = "volume_break"
        elif close_breakout:
            breakout_type = "close_above"
        else:
            breakout_type = "none"

        # Pullback probability (higher volume suggests less pullback)
        pullback_prob = max(0.1, 0.8 - (current_vol / avg_vol - 1.0) * 0.3)

        return {
            "breakout_detected": breakout_detected,
            "breakout_type": breakout_type,
            "pullback_probability": pullback_prob,
        }

    def _builtin_ta_pullback_bounce_level(self, args: list[Any]) -> dict:
        """Pullback/Bounce Level - Fibonacci support/resistance.

        ta.pullback_bounce_level(high_list, low_list, close_list, trend_direction,
                                 lookback)
        Returns: dict with primary_level, bounce_probability, support_strength
        """
        msg = "ta.pullback_bounce_level() requires 5 arguments"
        if len(args) < QUINARY:
            self._error(msg)

        high = self._expect_list(args[0], msg)
        low = self._expect_list(args[1], msg)
        _ = self._expect_list(args[2], msg)
        trend_dir = self._expect_int(args[3], msg)
        lookback = self._expect_int(args[4], msg)

        if not high or not low or lookback <= 0:
            return {
                "primary_level": 100.0,
                "bounce_probability": 0.5,
                "support_strength": 50.0,
            }

        h_vals = [h for h in high[-lookback:] if isinstance(h, (int, float))]
        l_vals = [low_val for low_val in low[-lookback:] if isinstance(low_val, (int, float))]

        if not h_vals or not l_vals:
            return {
                "primary_level": 100.0,
                "bounce_probability": 0.5,
                "support_strength": 50.0,
            }

        swing_high = max(h_vals)
        swing_low = min(l_vals)
        swing_range = swing_high - swing_low

        if trend_dir > 0:  # Uptrend - look for support (Fibonacci retracement)
            fib_level = swing_low + swing_range * 0.382
        else:  # Downtrend - look for resistance
            fib_level = swing_high - swing_range * 0.382

        primary_level = fib_level

        # Bounce probability based on volatility
        bounce_prob = min(0.95, 0.5 + (swing_range / swing_high) * 1.0)
        support_strength = min(100.0, (swing_range / swing_high) * 100.0)

        return {
            "primary_level": primary_level,
            "bounce_probability": bounce_prob,
            "support_strength": support_strength,
        }

    def _builtin_ta_multi_timeframe_signal(self, args: list[Any]) -> dict:
        """Multi-Timeframe Signal - Alignment across timeframes.

        ta.multi_timeframe_signal(signal_short, signal_mid, signal_long,
                                  weight_short, weight_mid, weight_long)
        Returns: dict with combined_signal, signal_agreement, alignment_quality
        """
        senary = 6
        msg = "ta.multi_timeframe_signal() requires 6 arguments"
        if len(args) < senary:
            self._error(msg)

        sig_short = args[0] if isinstance(args[0], (int, float)) else 0.0
        sig_mid = args[1] if isinstance(args[1], (int, float)) else 0.0
        sig_long = args[2] if isinstance(args[2], (int, float)) else 0.0
        w_short = args[3] if isinstance(args[3], (int, float)) else 0.33
        w_mid = args[4] if isinstance(args[4], (int, float)) else 0.33
        w_long = args[5] if isinstance(args[5], (int, float)) else 0.34

        combined = sig_short * w_short + sig_mid * w_mid + sig_long * w_long
        combined_signal = max(-1.0, min(1.0, combined))

        # Signal agreement counting
        agreement = 0
        if sig_short > 0 and sig_mid > 0 and sig_long > 0:
            agreement = 3
        elif sig_short > 0 and sig_mid > 0:
            agreement = 2
        elif sig_mid > 0 and sig_long > 0:
            agreement = 2
        elif sig_short > 0 and sig_long > 0:
            agreement = 2
        elif sig_short < 0 and sig_mid < 0 and sig_long < 0:
            agreement = 3
        elif sig_short < 0 and sig_mid < 0:
            agreement = 2
        elif sig_mid < 0 and sig_long < 0:
            agreement = 2
        elif sig_short < 0 and sig_long < 0:
            agreement = 2

        alignment_quality = agreement / 3.0 * 100.0

        return {
            "combined_signal": combined_signal,
            "signal_agreement": agreement,
            "alignment_quality": alignment_quality,
        }

    def _builtin_ta_max_loss_level(self, args: list[Any]) -> float:
        """Maximum Loss Stop - Calculates stop for max loss.

        ta.max_loss_level(entry, account, max_loss_pct)
        Returns: Stop price.
        """
        msg = "ta.max_loss_level() requires 3 arguments"
        if len(args) < TERNARY:
            self._error(msg)

        entry = args[0] if isinstance(args[0], (int, float)) else 100.0
        account = args[1] if isinstance(args[1], (int, float)) else 10000.0
        max_loss_pct = args[2] if isinstance(args[2], (int, float)) else 1.0

        max_loss_amount = account * (max_loss_pct / 100.0)

        if entry > 0:
            shares = account / entry
            stop_price = entry - (max_loss_amount / shares) if shares > 0 else 0.0
            return max(0.0, stop_price)

        return 0.0

    def _builtin_ta_profit_lock_level(self, args: list[Any]) -> float:
        """Profit Lock Level - Dynamic trailing stop.

        ta.profit_lock_level(entry, current, trail_pct, direction)
        Direction: 1 for long, -1 for short.
        Returns: Stop price that trails behind price.
        """
        if len(args) < QUATERNARY:
            msg = "ta.profit_lock_level() requires 4 arguments"
            self._error(msg)

        entry = args[0] if isinstance(args[0], (int, float)) else 100.0
        current = args[1] if isinstance(args[1], (int, float)) else 100.0
        trail_pct = args[2] if isinstance(args[2], (int, float)) else 0.05
        direction = args[3] if isinstance(args[3], (int, float)) else 1.0

        trail_pct = max(0.0, min(1.0, trail_pct))

        if direction > 0:
            trail_distance = current * trail_pct
            stop = current - trail_distance
            return max(entry * 0.9, stop)
        else:
            trail_distance = current * trail_pct
            stop = current + trail_distance
            return min(entry * 1.1, stop)

    # ========================================================================
    # Phase 8 Tier 8: Final Capstone Indicator (1 function)
    # ========================================================================

    def _builtin_ta_intelligent_strategy_synthesizer(self, args: list[Any]) -> dict:
        """Intelligent Trading Strategy Synthesizer - Meta-indicator synthesis.

        Combines all technical indicator categories into adaptive,
        context-aware trading signals.

        ta.intelligent_strategy_synthesizer(
            trend_indicators, momentum_indicators, volatility_indicators,
            volume_indicators, market_condition, risk_profile
        )

        Returns: dict with composite signal, confidence, and trading recommendation
        """
        msg = "ta.intelligent_strategy_synthesizer() requires 6 arguments"
        if len(args) < 6:
            self._error(msg)

        trend_list = self._expect_list(args[0], msg)
        momentum_list = self._expect_list(args[1], msg)
        volatility_list = self._expect_list(args[2], msg)
        volume_list = self._expect_list(args[3], msg)
        market_condition = (
            args[4]
            if isinstance(args[4], str)
            else "ranging"
        )
        risk_profile = (
            args[5]
            if isinstance(args[5], str)
            else "balanced"
        )

        # Extract numeric values from each category
        trend_vals = [
            t for t in trend_list
            if isinstance(t, (int, float))
        ]
        momentum_vals = [
            m for m in momentum_list
            if isinstance(m, (int, float))
        ]
        volatility_vals = [
            v for v in volatility_list
            if isinstance(v, (int, float))
        ]
        volume_vals = [
            vol for vol in volume_list
            if isinstance(vol, (int, float))
        ]

        # Calculate average signals from each category
        trend_avg = (
            sum(trend_vals) / len(trend_vals)
            if trend_vals
            else 0.0
        )
        momentum_avg = (
            sum(momentum_vals) / len(momentum_vals)
            if momentum_vals
            else 0.0
        )
        volatility_avg = (
            sum(volatility_vals) / len(volatility_vals)
            if volatility_vals
            else 0.5
        )
        volume_avg = (
            sum(volume_vals) / len(volume_vals)
            if volume_vals
            else 0.0
        )

        # Normalize volatility to 0-1 range
        volatility_normalized = max(0.0, min(1.0, volatility_avg))

        # Composite signal calculation
        # Trend: 40%, Momentum: 35%, Volume: 25%
        composite = (
            trend_avg * 0.4 +
            momentum_avg * 0.35 +
            volume_avg * 0.25
        )
        composite_signal = max(-1.0, min(1.0, composite))

        # Confidence scoring based on signal agreement
        agreement_count = 0
        if abs(trend_avg) > 0.3:
            agreement_count += 1
        if abs(momentum_avg) > 0.3:
            agreement_count += 1
        if abs(volume_avg) > 0.3:
            agreement_count += 1

        base_confidence = agreement_count / 3.0
        volatility_penalty = volatility_normalized * 0.3
        confidence_level = max(
            0.1,
            min(0.99, base_confidence - volatility_penalty)
        )

        # Strategy recommendation based on composite signal
        if composite_signal > 0.6:
            if risk_profile == "aggressive":
                recommendation = "aggressive_long"
            else:
                recommendation = "conservative_long"
        elif composite_signal > 0.2:
            recommendation = "conservative_long"
        elif composite_signal < -0.6:
            if risk_profile == "aggressive":
                recommendation = "aggressive_short"
            else:
                recommendation = "conservative_short"
        elif composite_signal < -0.2:
            recommendation = "conservative_short"
        else:
            recommendation = "hold"

        # Risk level based on volatility and risk profile
        if risk_profile == "conservative":
            risk_mult = 0.5
        elif risk_profile == "aggressive":
            risk_mult = 1.5
        else:
            risk_mult = 1.0

        risk_level = volatility_normalized * 50.0 * risk_mult

        # Expected return estimation
        abs_signal = abs(composite_signal)
        expected_return = abs_signal * 3.0

        # Holding period based on volatility
        if volatility_normalized > 0.7:
            holding_period = "scalp"
        elif volatility_normalized > 0.5:
            holding_period = "day_trade"
        elif abs_signal > 0.5:
            holding_period = "swing"
        else:
            holding_period = "position"

        # Stop loss priority (-1 to 0)
        if recommendation in ["aggressive_short", "conservative_short"]:
            stop_loss_priority = -0.7
        elif recommendation in ["aggressive_long", "conservative_long"]:
            stop_loss_priority = -0.2
        else:
            stop_loss_priority = -0.15

        # Take profit priority (0.5 to 2.0)
        if recommendation in ["aggressive_long", "aggressive_short"]:
            take_profit_priority = 1.5
        elif recommendation in ["conservative_long", "conservative_short"]:
            take_profit_priority = 1.0
        else:
            take_profit_priority = 0.5

        # Regime alignment scoring
        regime_alignment = 50.0

        if market_condition == "trending_up":
            if composite_signal > 0:
                regime_alignment = 90.0
            elif composite_signal > -0.3:
                regime_alignment = 60.0
            else:
                regime_alignment = 30.0
        elif market_condition == "trending_down":
            if composite_signal < 0:
                regime_alignment = 90.0
            elif composite_signal < 0.3:
                regime_alignment = 60.0
            else:
                regime_alignment = 30.0
        elif market_condition == "ranging":
            regime_alignment = 50.0 + (1.0 - abs_signal) * 30.0
        elif market_condition == "volatile":
            regime_alignment = 30.0 + abs_signal * 40.0
        else:  # dead
            regime_alignment = 40.0

        return {
            "composite_signal": composite_signal,
            "confidence_level": confidence_level,
            "strategy_recommendation": recommendation,
            "risk_level": max(0.0, min(100.0, risk_level)),
            "expected_return": expected_return,
            "holding_period": holding_period,
            "stop_loss_priority": stop_loss_priority,
            "take_profit_priority": take_profit_priority,
            "regime_alignment": max(0.0, min(100.0, regime_alignment)),
        }
