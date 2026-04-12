# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Economics Module: Market Microstructure & Advanced Economics Indicators."""

from __future__ import annotations

from typing import Any

from .core import TechnicalHelpers


class EconomicsIndicators(TechnicalHelpers):
    """Economics indicators: Market microstructure, advanced economics."""

    # -- Group A: Market Microstructure ------------------------------------

    def _builtin_ta_order_flow_imbalance(self, args: list[Any]) -> float:
        """Order Flow Imbalance - Detect buy/sell pressure through volume distribution.

        ta.order_flow_imbalance(high, low, close, volume, period)

        Returns:
            float: Imbalance ratio (-1.0 to 1.0)
        """
        msg = "ta.order_flow_imbalance() requires 5 arguments"
        if len(args) != 5:
            self._error(msg)

        high = self._expect_list(args[0], msg)
        low = self._expect_list(args[1], msg)
        close = self._expect_list(args[2], msg)
        volume = self._expect_list(args[3], msg)
        period = self._expect_int(args[4], msg)

        if len(close) < period or period <= 0:
            return 0.0

        buy_vol = 0.0
        sell_vol = 0.0

        for i in range(-period, 0):
            h = high[i] if isinstance(high[i], (int, float)) else 0
            l = low[i] if isinstance(low[i], (int, float)) else 0
            c = close[i] if isinstance(close[i], (int, float)) else 0
            v = volume[i] if isinstance(volume[i], (int, float)) else 0

            mid = (h + l) / 2
            if c > mid:
                buy_vol += v
            else:
                sell_vol += v

        total_vol = buy_vol + sell_vol
        if total_vol == 0:
            return 0.0

        return (buy_vol - sell_vol) / total_vol

    def _builtin_ta_volume_profile_high(self, args: list[Any]) -> float:
        """Volume Profile High - Find price level with highest volume.

        ta.volume_profile_high(close, volume, period, levels)
        """
        msg = "ta.volume_profile_high() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)
        levels = self._expect_int(args[3], msg)

        if len(close) < period or period <= 0 or levels <= 0:
            return 0.0

        # Simple implementation: find price with max volume in period
        # A real implementation would bin prices, but for now let's follow the guide's intent
        # "Bin prices into (levels) buckets"

        subset_close = close[-period:]
        subset_vol = volume[-period:]

        min_price = min(c for c in subset_close if isinstance(c, (int, float)))
        max_price = max(c for c in subset_close if isinstance(c, (int, float)))

        if min_price == max_price:
            return min_price

        price_range = max_price - min_price
        bucket_size = price_range / levels

        buckets = [0.0] * levels

        for c, v in zip(subset_close, subset_vol, strict=False):
            if not isinstance(c, (int, float)) or not isinstance(v, (int, float)):
                continue

            bucket_idx = int((c - min_price) / bucket_size)
            if bucket_idx >= levels:
                bucket_idx = levels - 1
            buckets[bucket_idx] += v

        max_vol_idx = buckets.index(max(buckets))
        return min_price + (max_vol_idx * bucket_size) + (bucket_size / 2)

    def _builtin_ta_volume_profile_low(self, args: list[Any]) -> float:
        """Volume Profile Low - Find price level with lowest volume.

        ta.volume_profile_low(close, volume, period, levels)
        """
        msg = "ta.volume_profile_low() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)
        levels = self._expect_int(args[3], msg)

        if len(close) < period or period <= 0 or levels <= 0:
            return 0.0

        subset_close = close[-period:]
        subset_vol = volume[-period:]

        valid_closes = [c for c in subset_close if isinstance(c, (int, float))]
        if not valid_closes:
            return 0.0

        min_price = min(valid_closes)
        max_price = max(valid_closes)

        if min_price == max_price:
            return min_price

        price_range = max_price - min_price
        bucket_size = price_range / levels

        buckets = [0.0] * levels

        for c, v in zip(subset_close, subset_vol, strict=False):
            if not isinstance(c, (int, float)) or not isinstance(v, (int, float)):
                continue

            bucket_idx = int((c - min_price) / bucket_size)
            if bucket_idx >= levels:
                bucket_idx = levels - 1
            buckets[bucket_idx] += v

        min_vol_idx = buckets.index(min(buckets))
        return min_price + (min_vol_idx * bucket_size) + (bucket_size / 2)

    def _builtin_ta_spread_analysis(self, args: list[Any]) -> dict[str, Any]:
        """Spread Analysis - Bid-ask spread tracking.

        ta.spread_analysis(bid, ask, period)
        """
        msg = "ta.spread_analysis() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        bid = self._expect_list(args[0], msg)
        ask = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)

        if len(bid) < period or len(ask) < period or period <= 0:
            return {"avg_spread": 0.0, "spread_percent": 0.0, "spread_trend": "stable"}

        spreads = []
        for i in range(-period, 0):
            b = bid[i] if isinstance(bid[i], (int, float)) else 0
            a = ask[i] if isinstance(ask[i], (int, float)) else 0
            if a > b > 0:
                spreads.append(a - b)

        if not spreads:
            return {"avg_spread": 0.0, "spread_percent": 0.0, "spread_trend": "stable"}

        avg_spread = sum(spreads) / len(spreads)
        mid_price = (
            (ask[-1] + bid[-1]) / 2
            if isinstance(ask[-1], (int, float)) and isinstance(bid[-1], (int, float))
            else 100.0
        )
        spread_percent = (avg_spread / mid_price * 100) if mid_price > 0 else 0.0

        if len(spreads) >= 2:
            if spreads[-1] > spreads[0] * 1.1:
                trend = "increasing"
            elif spreads[-1] < spreads[0] * 0.9:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {"avg_spread": avg_spread, "spread_percent": spread_percent, "spread_trend": trend}

    # -- Group B: Advanced Momentum ----------------------------------------

    def _builtin_ta_momentum_divergence(self, args: list[Any]) -> dict[str, Any]:
        """Momentum Divergence - Detect divergences across timeframes.

        ta.momentum_divergence(price, momentum_fast, momentum_slow)
        """
        msg = "ta.momentum_divergence() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        price = self._expect_list(args[0], msg)
        mom_fast = self._expect_list(args[1], msg)
        mom_slow = self._expect_list(args[2], msg)

        if not price or not mom_fast or not mom_slow:
            return {"divergence_type": "none", "strength": 0.0, "bars_since": 0}

        # Simplified logic for divergence
        p_curr = price[-1] if isinstance(price[-1], (int, float)) else 0
        p_prev = price[-2] if len(price) > 1 and isinstance(price[-2], (int, float)) else p_curr

        m_curr = mom_fast[-1] if isinstance(mom_fast[-1], (int, float)) else 0
        m_prev = mom_fast[-2] if len(mom_fast) > 1 and isinstance(mom_fast[-2], (int, float)) else m_curr

        div_type = "none"
        strength = 0.0

        if p_curr > p_prev and m_curr < m_prev:
            div_type = "bearish"
            strength = abs(m_curr - m_prev)
        elif p_curr < p_prev and m_curr > m_prev:
            div_type = "bullish"
            strength = abs(m_curr - m_prev)

        return {"divergence_type": div_type, "strength": strength, "bars_since": 0}

    def _builtin_ta_acceleration_factor(self, args: list[Any]) -> float:
        """Acceleration Factor - Measure momentum acceleration/deceleration.

        ta.acceleration_factor(momentum_list, period)
        """
        msg = "ta.acceleration_factor() requires 2 arguments"
        if len(args) != 2:
            self._error(msg)

        momentum = self._expect_list(args[0], msg)
        period = self._expect_int(args[1], msg)

        if len(momentum) < period + 1 or period <= 0:
            return 0.0

        curr_mom = momentum[-1] if isinstance(momentum[-1], (int, float)) else 0
        prev_mom = momentum[-period - 1] if isinstance(momentum[-period - 1], (int, float)) else 0

        acc = (curr_mom - prev_mom) / period
        return max(-2.0, min(2.0, acc))

    def _builtin_ta_mean_reversion_score(self, args: list[Any]) -> float:
        """Mean Reversion Score - Probability of price reverting to mean.

        ta.mean_reversion_score(close, sma, stdev, period)
        """
        msg = "ta.mean_reversion_score() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        sma = self._expect_list(args[1], msg)
        stdev = self._expect_list(args[2], msg)
        period = self._expect_int(args[3], msg)

        if not close or not sma or not stdev:
            return 50.0

        c = close[-1] if isinstance(close[-1], (int, float)) else 0
        s = sma[-1] if isinstance(sma[-1], (int, float)) else 0
        d = stdev[-1] if isinstance(stdev[-1], (int, float)) else 1.0

        if d == 0:
            return 50.0

        z_score = (c - s) / d
        # Map z-score to 0-100. z=0 -> 50. z=2 -> 95, z=-2 -> 5
        score = 50 + (z_score * 25)
        return max(0.0, min(100.0, score))

    def _builtin_ta_momentum_filter(self, args: list[Any]) -> float:
        """Momentum Filter - Filter noise from momentum.

        ta.momentum_filter(momentum_raw, volume, period)
        """
        msg = "ta.momentum_filter() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        mom = self._expect_list(args[0], msg)
        vol = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)

        if len(mom) < period or len(vol) < period:
            return 0.0

        # Volume weighted momentum
        weighted_sum = 0.0
        vol_sum = 0.0

        for i in range(-period, 0):
            m = mom[i] if isinstance(mom[i], (int, float)) else 0
            v = vol[i] if isinstance(vol[i], (int, float)) else 0
            weighted_sum += m * v
            vol_sum += v

        if vol_sum == 0:
            return 0.0

        return weighted_sum / vol_sum

    # -- Group C: Economic Integration -------------------------------------

    def _builtin_ta_economic_impact_score(self, args: list[Any]) -> float:
        """Economic Impact Score.

        ta.economic_impact_score(price_change, volatility, volume_change)
        """
        msg = "ta.economic_impact_score() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        pc = self._expect_number(args[0], msg)
        vol = self._expect_number(args[1], msg)
        vc = self._expect_number(args[2], msg)

        # Simple weighted score
        score = (abs(pc) * 0.4) + (vol * 0.3) + (abs(vc) * 0.3)
        return max(0.0, min(100.0, score * 10))  # Scale up

    def _builtin_ta_inflation_proxy_indicator(self, args: list[Any]) -> float:
        """Inflation Proxy Indicator.

        ta.inflation_proxy_indicator(usd_index, commodity_prices, bond_yields)
        """
        msg = "ta.inflation_proxy_indicator() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        usd = self._expect_number(args[0], msg)
        comm = self._expect_number(args[1], msg)
        bond = self._expect_number(args[2], msg)

        # Heuristic: High commodities + High yields - High USD = Inflation
        # Normalize inputs roughly around 100 or 0

        val = (comm * 0.5) + (bond * 10) - (usd * 0.5)
        return max(-100.0, min(100.0, val))

    def _builtin_ta_employment_cycle_indicator(self, args: list[Any]) -> str:
        """Employment Cycle Indicator.

        ta.employment_cycle_indicator(cyclical_stocks, defensive_stocks, unemployment_proxy)
        """
        msg = "ta.employment_cycle_indicator() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        cyc = self._expect_number(args[0], msg)
        def_ = self._expect_number(args[1], msg)
        unemp = self._expect_number(args[2], msg)

        ratio = cyc / def_ if def_ != 0 else 1.0

        if unemp > 6.0:
            return "recession"
        elif ratio > 1.2:
            return "early_cycle"
        elif ratio < 0.8:
            return "late_cycle"
        else:
            return "mid_cycle"

    def _builtin_ta_gdp_growth_proxy(self, args: list[Any]) -> float:
        """GDP Growth Proxy.

        ta.gdp_growth_proxy(market_breadth, market_volume, price_momentum)
        """
        msg = "ta.gdp_growth_proxy() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        breadth = self._expect_number(args[0], msg)
        volume = self._expect_number(args[1], msg)
        mom = self._expect_number(args[2], msg)

        # Combine signals
        growth = (breadth * 0.01) + (volume * 0.001) + (mom * 0.1)
        return max(-2.0, min(4.0, growth))

    # -- Group D: Behavioral Finance ---------------------------------------

    def _builtin_ta_fear_greed_index(self, args: list[Any]) -> float:
        """Fear & Greed Index.

        ta.fear_greed_index(rsi, vix_proxy, put_call_ratio, breadth)
        """
        msg = "ta.fear_greed_index() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        rsi = self._expect_number(args[0], msg)
        vix = self._expect_number(args[1], msg)
        pcr = self._expect_number(args[2], msg)
        breadth = self._expect_number(args[3], msg)

        # RSI contribution (0-100 -> -50 to 50)
        rsi_comp = rsi - 50

        # VIX contribution (Low VIX = Greed, High VIX = Fear)
        vix_comp = (20 - vix) * 2

        # PCR contribution (Low PCR = Greed, High PCR = Fear)
        pcr_comp = (1.0 - pcr) * 20

        # Breadth contribution
        breadth_comp = (breadth - 50) * 0.5

        total = rsi_comp + vix_comp + pcr_comp + breadth_comp
        return max(-100.0, min(100.0, total))

    def _builtin_ta_crowd_sentiment(self, args: list[Any]) -> float:
        """Crowd Sentiment.

        ta.crowd_sentiment(price_agreement, volume_agreement, time_agreement)
        """
        msg = "ta.crowd_sentiment() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        pa = self._expect_number(args[0], msg)
        va = self._expect_number(args[1], msg)
        ta = self._expect_number(args[2], msg)

        return (pa + va + ta) / 3.0

    def _builtin_ta_contrarian_signal(self, args: list[Any]) -> dict[str, Any]:
        """Contrarian Signal.

        ta.contrarian_signal(sentiment, volatility, time_since_extreme)
        """
        msg = "ta.contrarian_signal() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        sent = self._expect_number(args[0], msg)
        vol = self._expect_number(args[1], msg)
        time = self._expect_int(args[2], msg)

        signal = "neutral"
        strength = 0.0
        confidence = 0.0

        if sent > 80:
            signal = "sell"
            strength = (sent - 80) * 5
            confidence = min(100.0, vol * 2)
        elif sent < 20:
            signal = "buy"
            strength = (20 - sent) * 5
            confidence = min(100.0, vol * 2)

        return {"signal": signal, "strength": strength, "confidence": confidence}

    # -- Group E: Volume & Flow Analysis -----------------------------------

    def _builtin_ta_cumulative_delta(self, args: list[Any]) -> float:
        """Cumulative Delta.

        ta.cumulative_delta(close, volume, period)
        """
        msg = "ta.cumulative_delta() requires 3 arguments"
        if len(args) != 3:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        period = self._expect_int(args[2], msg)

        if len(close) < period or period <= 0:
            return 0.0

        delta = 0.0
        for i in range(-period, 0):
            c = close[i] if isinstance(close[i], (int, float)) else 0
            c_prev = close[i - 1] if i > -len(close) and isinstance(close[i - 1], (int, float)) else c
            v = volume[i] if isinstance(volume[i], (int, float)) else 0

            if c > c_prev:
                delta += v
            elif c < c_prev:
                delta -= v

        return delta

    def _builtin_ta_volume_momentum(self, args: list[Any]) -> float:
        """Volume Momentum.

        ta.volume_momentum(volume, period)
        """
        msg = "ta.volume_momentum() requires 2 arguments"
        if len(args) != 2:
            self._error(msg)

        volume = self._expect_list(args[0], msg)
        period = self._expect_int(args[1], msg)

        if len(volume) < period + 1 or period <= 0:
            return 0.0

        volume = [v for v in volume if isinstance(v, (int, float))]
        if len(volume) < period + 1:
            return 0.0

        old_vol = sum(volume[-period - 1 : -1]) / period if len(volume) > period else 1.0
        new_vol = sum(volume[-period:]) / period

        if old_vol == 0:
            return 0.0

        momentum = ((new_vol - old_vol) / old_vol) * 100.0
        return max(-100.0, min(100.0, momentum))

    def _builtin_ta_smart_money_flow(self, args: list[Any]) -> float:
        """Smart Money Flow.

        ta.smart_money_flow(price_change, volume, time_since_high, time_since_low)
        """
        msg = "ta.smart_money_flow() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        pc = self._expect_number(args[0], msg)
        vol = self._expect_number(args[1], msg)
        t_high = self._expect_int(args[2], msg)
        t_low = self._expect_int(args[3], msg)

        # Heuristic: High volume on small price change near highs/lows

        flow = 0.0
        if abs(pc) < 0.5 and vol > 1000:
            if t_high < 10:
                flow = -0.8  # Distribution
            elif t_low < 10:
                flow = 0.8  # Accumulation

        return flow

    def _builtin_ta_liquidity_score(self, args: list[Any]) -> float:
        """Liquidity Score.

        ta.liquidity_score(volume, volatility, bid_ask_spread, period)
        """
        msg = "ta.liquidity_score() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        vol = self._expect_list(args[0], msg)
        vola = self._expect_list(args[1], msg)
        spread = self._expect_list(args[2], msg)
        period = self._expect_int(args[3], msg)

        if not vol or not vola or not spread:
            return 50.0

        v = vol[-1] if isinstance(vol[-1], (int, float)) else 0
        vl = vola[-1] if isinstance(vola[-1], (int, float)) else 1.0
        s = spread[-1] if isinstance(spread[-1], (int, float)) else 1.0

        # High volume, low volatility, low spread = High Liquidity

        score = (v * 0.01) / (vl * s + 0.001)
        return max(0.0, min(100.0, score))

    # -- Group F: Advanced Patterns ----------------------------------------

    def _builtin_ta_volume_thrust(self, args: list[Any]) -> bool:
        """Volume Thrust.

        ta.volume_thrust(close, volume, volume_sma, sensitivity)
        """
        msg = "ta.volume_thrust() requires 4 arguments"
        if len(args) != 4:
            self._error(msg)

        close = self._expect_list(args[0], msg)
        volume = self._expect_list(args[1], msg)
        vol_sma = self._expect_list(args[2], msg)
        sens = self._expect_number(args[3], msg)

        if not close or not volume or not vol_sma:
            return False

        c = close[-1] if isinstance(close[-1], (int, float)) else 0
        c_prev = close[-2] if len(close) > 1 and isinstance(close[-2], (int, float)) else c
        v = volume[-1] if isinstance(volume[-1], (int, float)) else 0
        vs = vol_sma[-1] if isinstance(vol_sma[-1], (int, float)) else 0

        if vs == 0:
            return False

        return v > (vs * (1 + sens)) and abs(c - c_prev) > 0
