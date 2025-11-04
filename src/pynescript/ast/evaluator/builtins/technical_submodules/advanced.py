"""Advanced Technical Indicators - Tier 5-8 (Complex Analysis & Strategy Synthesis)."""

from __future__ import annotations

import math
import statistics
from typing import Any

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
        expected_args = 2
        if len(args) < expected_args:
            msg = "ta.ichimoku() requires 2 arguments: fast_period, slow_period"
            self._error(msg)

        fast_period = self._expect_int(args[0], "fast_period must be integer")
        slow_period = self._expect_int(args[1], "slow_period must be integer")

        min_period = 1
        if fast_period < min_period or slow_period < min_period:
            msg = "Ichimoku periods must be >= 1"
            self._error(msg)

        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

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
        expected_args = 1
        if len(args) < expected_args:
            msg = "ta.donchian() requires 1 argument: length"
            self._error(msg)

        length = self._expect_int(args[0], "length must be integer")

        if length < DONCHIAN_MIN_LENGTH:
            msg = "Donchian length must be >= 1"
            self._error(msg)

        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

        if not highs or not lows or len(highs) < length:
            return {"high": None, "low": None, "mid": None}

        high_val = max(highs[-length:])
        low_val = min(lows[-length:])
        mid_val = (high_val + low_val) / 2.0

        return {"high": high_val, "low": low_val, "mid": mid_val}

    def _builtin_ta_market_condition(self, args: list[Any]) -> str:
        """Market Condition Detection."""
        if len(args) < 4:
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
        if len(args) < 2:
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
        if len(args) < 3:
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
        if len(args) < 2:
            msg = "ta.inside_bar_pattern() requires 2 arguments"
            self._error(msg)

        high_list = args[0] if isinstance(args[0], list) else [args[0]]
        low_list = args[1] if isinstance(args[1], list) else [args[1]]

        if len(high_list) < 2 or len(low_list) < 2:
            return False

        prev_high = high_list[-2] if isinstance(high_list[-2], (int, float)) else 0.0
        prev_low = low_list[-2] if isinstance(low_list[-2], (int, float)) else 0.0
        curr_high = high_list[-1] if isinstance(high_list[-1], (int, float)) else 0.0
        curr_low = low_list[-1] if isinstance(low_list[-1], (int, float)) else 0.0

        return curr_high < prev_high and curr_low > prev_low

    # -- Tier 5: Position Sizing & Risk Management --------------------------

    def _builtin_ta_position_sizing(self, args: list[Any]) -> float:
        """Position Sizing."""
        if len(args) < 4:
            msg = "ta.position_sizing() requires 4 arguments"
            self._error(msg)

        account = args[0] if isinstance(args[0], (int, float)) else 10000.0
        risk_pct = args[1] if isinstance(args[1], (int, float)) else 0.01
        entry = args[2] if isinstance(args[2], (int, float)) else 100.0
        stop = args[3] if isinstance(args[3], (int, float)) else 95.0

        risk_amount = account * (risk_pct / 100.0)
        stop_distance = entry - stop

        if abs(stop_distance) < 1e-10:
            return 0.0

        size = risk_amount / abs(stop_distance)
        return max(0.0, size)

    def _builtin_ta_kelly_criterion(self, args: list[Any]) -> float:
        """Kelly Criterion."""
        if len(args) < 3:
            msg = "ta.kelly_criterion() requires 3 arguments"
            self._error(msg)

        win_rate = args[0] if isinstance(args[0], (int, float)) else 0.5
        avg_win = args[1] if isinstance(args[1], (int, float)) else 1.0
        avg_loss = args[2] if isinstance(args[2], (int, float)) else 1.0

        win_rate = max(0.0, min(1.0, win_rate))

        if abs(avg_win) < 1e-10:
            return 0.0

        kelly = (win_rate * avg_win - (1.0 - win_rate) * avg_loss) / avg_win
        return max(0.0, kelly)

    def _builtin_ta_risk_reward_ratio(self, args: list[Any]) -> float | None:
        """Risk/Reward Ratio."""
        if len(args) < 3:
            msg = "ta.risk_reward_ratio() requires 3 arguments"
            self._error(msg)

        entry = args[0] if isinstance(args[0], (int, float)) else 0.0
        stop = args[1] if isinstance(args[1], (int, float)) else 0.0
        target = args[2] if isinstance(args[2], (int, float)) else 0.0

        risk = entry - stop
        if abs(risk) < 1e-10:
            return None

        reward = target - entry
        ratio = reward / risk if risk != 0 else None
        return ratio

    # -- Tier 6: Signal Confluence & Scoring --------------------------------

    def _builtin_ta_strategy_score(self, args: list[Any]) -> float:
        """Strategy Score."""
        if len(args) < 4:
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
        if len(args) < 1:
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
        if len(args) < 3:
            msg = "ta.divergence_detector() requires 3 arguments"
            self._error(msg)

        price_list = args[0] if isinstance(args[0], list) else [args[0]]
        indicator_list = args[1] if isinstance(args[1], list) else [args[1]]
        lookback = self._expect_int(args[2], "lookback must be integer")

        if len(price_list) < lookback or len(indicator_list) < lookback:
            return {"is_bullish": False, "is_bearish": False, "strength": 0.0}

        price_recent = [p for p in price_list[-lookback:] if isinstance(p, (int, float))]
        ind_recent = [i for i in indicator_list[-lookback:] if isinstance(i, (int, float))]

        if len(price_recent) < 2 or len(ind_recent) < 2:
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
        if len(args) < 5:
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
        if len(args) < 2:
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

    # -- Tier 7: Advanced Economics & Probability ---------------------------

    def _builtin_ta_probability_of_movement(self, args: list[Any]) -> float:
        """Probability of Movement."""
        if len(args) < 4:
            msg = "ta.probability_of_movement() requires 4 arguments"
            self._error(msg)

        current = args[0] if isinstance(args[0], (int, float)) else 100.0
        target = args[1] if isinstance(args[1], (int, float)) else 100.0
        atr = args[2] if isinstance(args[2], (int, float)) else 1.0
        period = self._expect_int(args[3], "period must be integer")

        if abs(current) < 1e-10 or abs(atr) < 1e-10:
            return 0.5

        distance = abs(target - current)
        expected_move = atr * math.sqrt(period)

        if expected_move == 0:
            return 0.5

        probability = min(1.0, distance / expected_move) * 0.8 + 0.1
        return max(0.0, min(1.0, probability))

    def _builtin_ta_gamma_levels(self, args: list[Any]) -> list[float]:
        """Gamma Levels."""
        if len(args) < 3:
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
        expected_args = 3
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
        if len(args) < 2:
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
        signal = stochrsi_val * 0.33 + (
            getattr(self, "_last_stochrsi_signal", stochrsi_val) * 0.67
        )
        self._last_stochrsi_signal = signal

        return {"stochrsi": stochrsi_val, "signal": signal}

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

    def _builtin_ta_kst(self, args: list[Any]) -> float | None:
        """Know Sure Thing Oscillator."""
        if len(args) < 4:
            msg = "ta.kst() requires 4 arguments: length1, length2, length3, length4"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")
        length4 = self._expect_int(args[3], "length4 must be integer")

        closes = self.current_series.get("close", [])
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
        if len(args) < 3:
            msg = "ta.uo() requires 3 arguments: length1, length2, length3"
            self._error(msg)

        length1 = self._expect_int(args[0], "length1 must be integer")
        length2 = self._expect_int(args[1], "length2 must be integer")
        length3 = self._expect_int(args[2], "length3 must be integer")

        closes = self.current_series.get("close", [])
        highs = self.current_series.get("high", [])
        lows = self.current_series.get("low", [])

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
        expected_args = 2
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
