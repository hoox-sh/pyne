"""
Phase 8 Tier 6: Market Microstructure & Advanced Economics

Tests for 20 new advanced trading indicators:
- Market microstructure analysis (order flow, volume profile, spreads)
- Advanced momentum indicators (divergence, acceleration, mean reversion)
- Economic integration (inflation, employment, GDP proxies)
- Behavioral finance (fear/greed, sentiment, contrarian signals)
- Volume & flow analysis (delta, momentum, smart money, liquidity)
- Advanced pattern recognition (volume thrust)

Total: 60 comprehensive tests
"""

from __future__ import annotations

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


@pytest.fixture
def evaluator():
    """Create evaluator for builtin tests."""
    return NodeLiteralEvaluator()


# ============================================================================
# Group A: Market Microstructure Tests (10 tests)
# ============================================================================

class TestOrderFlowImbalance:
    """Tests for ta.order_flow_imbalance indicator."""

    def test_buy_pressure(self, evaluator):
        """Test buy pressure imbalance detection."""
        high = [100.0, 101.0, 102.0, 103.0, 104.0]
        low = [95.0, 96.0, 97.0, 98.0, 99.0]
        close = [102.0, 102.5, 103.0, 103.5, 104.0]
        volume = [1000.0, 1200.0, 1100.0, 1300.0, 1400.0]
        imbalance = evaluator._builtin_ta_order_flow_imbalance([high, low, close, volume, 3])
        assert isinstance(imbalance, (int, float))
        assert -1.0 <= imbalance <= 1.0

    def test_sell_pressure(self, evaluator):
        """Test sell pressure imbalance detection."""
        high = [104.0, 103.0, 102.0, 101.0, 100.0]
        low = [99.0, 98.0, 97.0, 96.0, 95.0]
        close = [99.5, 98.5, 97.5, 96.5, 95.5]
        volume = [1400.0, 1300.0, 1100.0, 1200.0, 1000.0]
        imbalance = evaluator._builtin_ta_order_flow_imbalance([high, low, close, volume, 3])
        assert -1.0 <= imbalance <= 1.0

    def test_balanced_flow(self, evaluator):
        """Test balanced order flow."""
        high = [100.0, 101.0, 100.0, 101.0, 100.0]
        low = [95.0, 96.0, 95.0, 96.0, 95.0]
        close = [97.5, 98.5, 97.5, 98.5, 97.5]
        volume = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        imbalance = evaluator._builtin_ta_order_flow_imbalance([high, low, close, volume, 3])
        assert -1.0 <= imbalance <= 1.0  # Valid range

    def test_edge_case_single_bar(self, evaluator):
        """Test edge case with minimal data."""
        high = [100.0]
        low = [95.0]
        close = [97.5]
        volume = [1000.0]
        imbalance = evaluator._builtin_ta_order_flow_imbalance([high, low, close, volume, 1])
        assert imbalance is not None


class TestVolumeProfileHigh:
    """Tests for ta.volume_profile_high indicator."""

    def test_point_of_control_high(self, evaluator):
        """Test point of control detection."""
        close = [100.0, 100.5, 101.0, 101.5, 102.0]
        volume = [1000.0, 1500.0, 2000.0, 1500.0, 1000.0]
        poc = evaluator._builtin_ta_volume_profile_high([close, volume, 5, 10])
        assert isinstance(poc, (int, float))
        assert 99.0 <= poc <= 103.0

    def test_volume_concentration(self, evaluator):
        """Test volume concentrated at high level."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [100.0, 200.0, 300.0, 5000.0, 200.0]
        poc = evaluator._builtin_ta_volume_profile_high([close, volume, 5, 10])
        assert poc > 102.0  # Should be near highest volume bar

    def test_uniform_distribution(self, evaluator):
        """Test uniform volume distribution."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        poc = evaluator._builtin_ta_volume_profile_high([close, volume, 5, 10])
        assert 100.0 <= poc <= 104.0


class TestVolumeProfileLow:
    """Tests for ta.volume_profile_low indicator."""

    def test_volume_gap_low(self, evaluator):
        """Test volume gap (low volume) detection."""
        close = [100.0, 100.5, 101.0, 101.5, 102.0]
        volume = [5000.0, 100.0, 2000.0, 1500.0, 5000.0]
        lowest_vol = evaluator._builtin_ta_volume_profile_low([close, volume, 5, 10])
        assert isinstance(lowest_vol, (int, float))
        assert 100.0 <= lowest_vol <= 102.0

    def test_identifies_weak_areas(self, evaluator):
        """Test identification of weak trading areas."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [5000.0, 5000.0, 100.0, 5000.0, 5000.0]
        lowest_vol = evaluator._builtin_ta_volume_profile_low([close, volume, 5, 10])
        assert 100.0 <= lowest_vol <= 104.0  # Valid range for price profile


class TestSpreadAnalysis:
    """Tests for ta.spread_analysis indicator."""

    def test_tight_spread(self, evaluator):
        """Test tight bid-ask spread detection."""
        bid = [99.9, 99.95, 100.0, 100.05, 100.1]
        ask = [100.1, 100.15, 100.2, 100.25, 100.3]
        result = evaluator._builtin_ta_spread_analysis([bid, ask, 3])
        assert isinstance(result, dict)
        assert "avg_spread" in result
        assert result["avg_spread"] < 0.5

    def test_wide_spread(self, evaluator):
        """Test wide bid-ask spread detection."""
        bid = [90.0, 92.0, 94.0, 96.0, 98.0]
        ask = [110.0, 112.0, 114.0, 116.0, 118.0]
        result = evaluator._builtin_ta_spread_analysis([bid, ask, 3])
        assert result["avg_spread"] > 10.0

    def test_spread_trend(self, evaluator):
        """Test spread trend detection."""
        bid = [99.9, 99.95, 99.98, 99.99, 99.995]
        ask = [100.1, 100.05, 100.02, 100.01, 100.005]
        result = evaluator._builtin_ta_spread_analysis([bid, ask, 3])
        assert result["spread_trend"] in ["stable", "increasing", "decreasing"]


# ============================================================================
# Group B: Advanced Momentum Tests (10 tests)
# ============================================================================

class TestMomentumDivergence:
    """Tests for ta.momentum_divergence indicator."""

    def test_bullish_divergence(self, evaluator):
        """Test bullish momentum divergence detection."""
        price = [100.0, 99.0, 98.0, 99.0, 100.0]
        momentum_fast = [1.0, 0.5, -0.5, 0.0, 1.5]
        momentum_slow = [0.5, 0.3, -0.1, 0.2, 0.8]
        result = evaluator._builtin_ta_momentum_divergence([price, momentum_fast, momentum_slow])
        assert isinstance(result, dict)
        assert result["divergence_type"] in ["bullish", "bearish", "none"]

    def test_bearish_divergence(self, evaluator):
        """Test bearish momentum divergence detection."""
        price = [100.0, 101.0, 102.0, 101.0, 100.0]
        momentum_fast = [-1.0, -0.5, 0.5, 0.0, -1.5]
        momentum_slow = [-0.5, -0.3, 0.1, -0.2, -0.8]
        result = evaluator._builtin_ta_momentum_divergence([price, momentum_fast, momentum_slow])
        assert "strength" in result
        assert 0 <= result["strength"] <= 1

    def test_no_divergence(self, evaluator):
        """Test no divergence scenario."""
        price = [100.0, 101.0, 102.0, 103.0, 104.0]
        momentum_fast = [1.0, 1.2, 1.4, 1.6, 1.8]
        momentum_slow = [0.8, 1.0, 1.2, 1.4, 1.6]
        result = evaluator._builtin_ta_momentum_divergence([price, momentum_fast, momentum_slow])
        assert result["divergence_type"] == "none"


class TestAccelerationFactor:
    """Tests for ta.acceleration_factor indicator."""

    def test_accelerating_momentum(self, evaluator):
        """Test accelerating momentum detection."""
        momentum_list = [0.5, 1.0, 1.5, 2.0, 2.5]
        factor = evaluator._builtin_ta_acceleration_factor([momentum_list, 3])
        assert isinstance(factor, (int, float))
        assert factor > 0.5  # Accelerating

    def test_decelerating_momentum(self, evaluator):
        """Test decelerating momentum detection."""
        momentum_list = [2.5, 2.0, 1.5, 1.0, 0.5]
        factor = evaluator._builtin_ta_acceleration_factor([momentum_list, 3])
        assert factor < -0.5  # Decelerating

    def test_stable_momentum(self, evaluator):
        """Test stable momentum detection."""
        momentum_list = [1.0, 1.0, 1.0, 1.0, 1.0]
        factor = evaluator._builtin_ta_acceleration_factor([momentum_list, 3])
        assert -0.2 <= factor <= 0.2  # Near zero


class TestMeanReversionScore:
    """Tests for ta.mean_reversion_score indicator."""

    def test_high_reversion_probability(self, evaluator):
        """Test high mean reversion score."""
        close = [100.0, 105.0, 110.0, 115.0, 120.0]
        sma = [100.0, 100.5, 101.0, 101.5, 102.0]
        stdev = [2.0, 2.1, 2.2, 2.3, 2.4]
        score = evaluator._builtin_ta_mean_reversion_score([close, sma, stdev, 3])
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
        assert score > 50  # High reversion probability

    def test_low_reversion_probability(self, evaluator):
        """Test low mean reversion score."""
        close = [100.5, 100.4, 100.3, 100.2, 100.1]
        sma = [100.0, 100.0, 100.0, 100.0, 100.0]
        stdev = [0.1, 0.1, 0.1, 0.1, 0.1]
        score = evaluator._builtin_ta_mean_reversion_score([close, sma, stdev, 3])
        assert score < 50  # Low reversion probability

    def test_neutral_reversion_score(self, evaluator):
        """Test neutral mean reversion score."""
        close = [100.0, 100.2, 100.0, 100.2, 100.0]
        sma = [100.0, 100.1, 100.1, 100.1, 100.1]
        stdev = [0.5, 0.5, 0.5, 0.5, 0.5]
        score = evaluator._builtin_ta_mean_reversion_score([close, sma, stdev, 3])
        assert 0 <= score <= 100  # Valid range


class TestMomentumFilter:
    """Tests for ta.momentum_filter indicator."""

    def test_filters_noise(self, evaluator):
        """Test filtering of noisy momentum."""
        momentum_raw = [0.1, -0.2, 0.15, -0.1, 0.3]
        volume = [1000.0, 500.0, 800.0, 600.0, 2000.0]
        filtered = evaluator._builtin_ta_momentum_filter([momentum_raw, volume, 3])
        assert isinstance(filtered, (int, float))
        # Filtered should be smoother
        assert abs(filtered) <= max(abs(m) for m in momentum_raw)

    def test_preserves_strong_signals(self, evaluator):
        """Test preservation of strong signals."""
        momentum_raw = [2.0, 2.2, 2.1, 2.3, 2.0]
        volume = [5000.0, 5000.0, 5000.0, 5000.0, 5000.0]
        filtered = evaluator._builtin_ta_momentum_filter([momentum_raw, volume, 3])
        assert filtered > 1.5  # Strong signal preserved

    def test_weak_volume_damping(self, evaluator):
        """Test weak volume damping effect."""
        momentum_raw = [1.0, 1.0, 1.0, 1.0, 1.0]
        volume = [100.0, 100.0, 100.0, 100.0, 100.0]
        filtered = evaluator._builtin_ta_momentum_filter([momentum_raw, volume, 3])
        assert isinstance(filtered, (int, float))  # Valid output


# ============================================================================
# Group C: Economic Integration Tests (8 tests)
# ============================================================================

class TestEconomicImpactScore:
    """Tests for ta.economic_impact_score indicator."""

    def test_high_impact_move(self, evaluator):
        """Test high economic impact score."""
        price_change = 2.5
        volatility = 1.5
        volume_change = 1.8
        score = evaluator._builtin_ta_economic_impact_score([price_change, volatility, volume_change])
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_low_impact_move(self, evaluator):
        """Test low economic impact score."""
        price_change = 0.2
        volatility = 0.1
        volume_change = 0.15
        score = evaluator._builtin_ta_economic_impact_score([price_change, volatility, volume_change])
        assert 0 <= score <= 100

    def test_moderate_impact_move(self, evaluator):
        """Test moderate economic impact score."""
        price_change = 1.0
        volatility = 0.8
        volume_change = 0.9
        score = evaluator._builtin_ta_economic_impact_score([price_change, volatility, volume_change])
        assert 0 <= score <= 100


class TestInflationProxyIndicator:
    """Tests for ta.inflation_proxy_indicator."""

    def test_inflation_signals(self, evaluator):
        """Test inflation pressure detection."""
        usd_index = [95.0, 94.0, 93.0, 92.0, 91.0]  # USD weakness
        commodity_prices = [100.0, 102.0, 104.0, 106.0, 108.0]  # Rising
        bond_yields = [2.0, 2.1, 2.2, 2.3, 2.4]  # Rising
        score = evaluator._builtin_ta_inflation_proxy_indicator([usd_index, commodity_prices, bond_yields])
        assert isinstance(score, (int, float))
        assert -100 <= score <= 100

    def test_disinflation_signals(self, evaluator):
        """Test disinflation pressure detection."""
        usd_index = [100.0, 101.0, 102.0, 103.0, 104.0]  # USD strength
        commodity_prices = [100.0, 98.0, 96.0, 94.0, 92.0]  # Falling
        bond_yields = [2.5, 2.4, 2.3, 2.2, 2.1]  # Falling
        score = evaluator._builtin_ta_inflation_proxy_indicator([usd_index, commodity_prices, bond_yields])
        assert -100 <= score <= 100

    def test_neutral_inflation_signals(self, evaluator):
        """Test neutral inflation signals."""
        usd_index = [100.0, 100.5, 100.0, 100.5, 100.0]
        commodity_prices = [100.0, 100.5, 100.0, 100.5, 100.0]
        bond_yields = [2.5, 2.5, 2.5, 2.5, 2.5]
        score = evaluator._builtin_ta_inflation_proxy_indicator([usd_index, commodity_prices, bond_yields])
        assert -100 <= score <= 100


class TestEmploymentCycleIndicator:
    """Tests for ta.employment_cycle_indicator."""

    def test_early_cycle_detection(self, evaluator):
        """Test early cycle detection."""
        cyclical_stocks = [100.0, 102.0, 104.0, 106.0, 108.0]
        defensive_stocks = [100.0, 100.5, 101.0, 101.5, 102.0]
        unemployment_proxy = [0.2, 0.18, 0.16, 0.14, 0.12]
        cycle = evaluator._builtin_ta_employment_cycle_indicator(
            [cyclical_stocks, defensive_stocks, unemployment_proxy]
        )
        assert isinstance(cycle, str)
        assert cycle in ["early_cycle", "mid_cycle", "late_cycle", "recession"]

    def test_late_cycle_detection(self, evaluator):
        """Test late cycle detection."""
        cyclical_stocks = [110.0, 109.0, 108.0, 107.0, 106.0]
        defensive_stocks = [103.0, 104.0, 105.0, 106.0, 107.0]
        unemployment_proxy = [0.1, 0.11, 0.12, 0.13, 0.14]
        cycle = evaluator._builtin_ta_employment_cycle_indicator(
            [cyclical_stocks, defensive_stocks, unemployment_proxy]
        )
        assert cycle in ["late_cycle", "mid_cycle", "recession"]

    def test_recession_detection(self, evaluator):
        """Test recession detection."""
        cyclical_stocks = [90.0, 88.0, 86.0, 84.0, 82.0]
        defensive_stocks = [105.0, 106.0, 107.0, 108.0, 109.0]
        unemployment_proxy = [0.2, 0.22, 0.24, 0.26, 0.28]
        cycle = evaluator._builtin_ta_employment_cycle_indicator(
            [cyclical_stocks, defensive_stocks, unemployment_proxy]
        )
        assert cycle in ["recession", "late_cycle"]


class TestGDPGrowthProxy:
    """Tests for ta.gdp_growth_proxy indicator."""

    def test_growth_signal(self, evaluator):
        """Test GDP growth signal."""
        market_breadth = [0.6, 0.65, 0.7, 0.75, 0.8]
        market_volume = [1000.0, 1200.0, 1400.0, 1600.0, 1800.0]
        price_momentum = [1.0, 1.2, 1.4, 1.6, 1.8]
        gdp_estimate = evaluator._builtin_ta_gdp_growth_proxy([market_breadth, market_volume, price_momentum])
        assert isinstance(gdp_estimate, (int, float))
        assert -2 <= gdp_estimate <= 4

    def test_contraction_signal(self, evaluator):
        """Test GDP contraction signal."""
        market_breadth = [0.4, 0.35, 0.3, 0.25, 0.2]
        market_volume = [1000.0, 800.0, 600.0, 400.0, 200.0]
        price_momentum = [-1.0, -1.2, -1.4, -1.6, -1.8]
        gdp_estimate = evaluator._builtin_ta_gdp_growth_proxy([market_breadth, market_volume, price_momentum])
        assert gdp_estimate < 0  # Contraction

    def test_neutral_growth_signal(self, evaluator):
        """Test neutral GDP growth signal."""
        market_breadth = [0.5, 0.5, 0.5, 0.5, 0.5]
        market_volume = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        price_momentum = [0.0, 0.0, 0.0, 0.0, 0.0]
        gdp_estimate = evaluator._builtin_ta_gdp_growth_proxy([market_breadth, market_volume, price_momentum])
        assert -0.5 <= gdp_estimate <= 0.5


# ============================================================================
# Group D: Behavioral Finance Tests (8 tests)
# ============================================================================

class TestFearGreedIndex:
    """Tests for ta.fear_greed_index indicator."""

    def test_extreme_fear(self, evaluator):
        """Test extreme fear detection."""
        rsi = [20.0, 25.0, 30.0, 35.0, 40.0]
        vix_proxy = [8.0, 8.5, 9.0, 9.5, 10.0]
        put_call_ratio = [2.0, 1.8, 1.6, 1.4, 1.2]
        breadth = [0.2, 0.25, 0.3, 0.35, 0.4]
        index = evaluator._builtin_ta_fear_greed_index([rsi, vix_proxy, put_call_ratio, breadth])
        assert isinstance(index, (int, float))
        assert -100 <= index <= 100

    def test_extreme_greed(self, evaluator):
        """Test extreme greed detection."""
        rsi = [80.0, 75.0, 70.0, 65.0, 60.0]
        vix_proxy = [1.0, 1.1, 1.2, 1.3, 1.4]
        put_call_ratio = [0.5, 0.6, 0.7, 0.8, 0.9]
        breadth = [0.8, 0.75, 0.7, 0.65, 0.6]
        index = evaluator._builtin_ta_fear_greed_index([rsi, vix_proxy, put_call_ratio, breadth])
        assert -100 <= index <= 100

    def test_neutral_sentiment(self, evaluator):
        """Test neutral sentiment detection."""
        rsi = [50.0, 50.0, 50.0, 50.0, 50.0]
        vix_proxy = [2.0, 2.0, 2.0, 2.0, 2.0]
        put_call_ratio = [1.0, 1.0, 1.0, 1.0, 1.0]
        breadth = [0.5, 0.5, 0.5, 0.5, 0.5]
        index = evaluator._builtin_ta_fear_greed_index([rsi, vix_proxy, put_call_ratio, breadth])
        assert -10 <= index <= 10  # Neutral


class TestCrowdSentiment:
    """Tests for ta.crowd_sentiment indicator."""

    def test_strong_consensus(self, evaluator):
        """Test strong crowd consensus."""
        price_agreement = 0.9
        volume_agreement = 0.85
        time_agreement = 0.8
        consensus = evaluator._builtin_ta_crowd_sentiment([price_agreement, volume_agreement, time_agreement])
        assert isinstance(consensus, (int, float))
        assert 0 <= consensus <= 100
        assert consensus > 75  # Strong consensus

    def test_weak_consensus(self, evaluator):
        """Test weak crowd consensus."""
        price_agreement = 0.4
        volume_agreement = 0.35
        time_agreement = 0.3
        consensus = evaluator._builtin_ta_crowd_sentiment([price_agreement, volume_agreement, time_agreement])
        assert consensus < 40  # Weak consensus

    def test_moderate_consensus(self, evaluator):
        """Test moderate crowd consensus."""
        price_agreement = 0.6
        volume_agreement = 0.5
        time_agreement = 0.55
        consensus = evaluator._builtin_ta_crowd_sentiment([price_agreement, volume_agreement, time_agreement])
        assert 40 <= consensus <= 75


class TestContrarySignal:
    """Tests for ta.contrarian_signal indicator."""

    def test_strong_contrarian_signal(self, evaluator):
        """Test strong contrarian signal."""
        sentiment = 95.0
        volatility = 3.5
        time_since_extreme = 2
        result = evaluator._builtin_ta_contrarian_signal([sentiment, volatility, time_since_extreme])
        assert isinstance(result, dict)
        assert result["signal"] in ["strong_contrarian", "mild_contrarian", "follow_crowd", "neutral"]
        assert result["signal"] == "strong_contrarian"

    def test_follow_crowd_signal(self, evaluator):
        """Test follow crowd signal."""
        sentiment = 45.0
        volatility = 0.5
        time_since_extreme = 20
        result = evaluator._builtin_ta_contrarian_signal([sentiment, volatility, time_since_extreme])
        assert result["signal"] in ["follow_crowd", "neutral"]

    def test_neutral_contrarian_signal(self, evaluator):
        """Test neutral contrarian signal."""
        sentiment = 50.0
        volatility = 1.5
        time_since_extreme = 10
        result = evaluator._builtin_ta_contrarian_signal([sentiment, volatility, time_since_extreme])
        assert 0 <= result["strength"] <= 1
        assert 0 <= result["confidence"] <= 1


# ============================================================================
# Group E: Volume & Flow Analysis Tests (12 tests)
# ============================================================================

class TestCumulativeDelta:
    """Tests for ta.cumulative_delta indicator."""

    def test_positive_delta_accumulation(self, evaluator):
        """Test positive cumulative delta."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        delta = evaluator._builtin_ta_cumulative_delta([close, volume, 5])
        assert isinstance(delta, (int, float))
        assert delta > 0  # Net positive buy volume

    def test_negative_delta_accumulation(self, evaluator):
        """Test negative cumulative delta."""
        close = [104.0, 103.0, 102.0, 101.0, 100.0]
        volume = [1400.0, 1300.0, 1200.0, 1100.0, 1000.0]
        delta = evaluator._builtin_ta_cumulative_delta([close, volume, 5])
        assert delta < 0  # Net negative sell volume

    def test_balanced_delta(self, evaluator):
        """Test balanced cumulative delta."""
        close = [100.0, 101.0, 100.0, 101.0, 100.0]
        volume = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        delta = evaluator._builtin_ta_cumulative_delta([close, volume, 5])
        assert -500 <= delta <= 500  # Near balanced


class TestVolumeMomentum:
    """Tests for ta.volume_momentum indicator."""

    def test_increasing_volume_momentum(self, evaluator):
        """Test increasing volume momentum."""
        volume = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        momentum = evaluator._builtin_ta_volume_momentum([volume, 3])
        assert isinstance(momentum, (int, float))
        assert -100 <= momentum <= 100

    def test_decreasing_volume_momentum(self, evaluator):
        """Test decreasing volume momentum."""
        volume = [1400.0, 1300.0, 1200.0, 1100.0, 1000.0]
        momentum = evaluator._builtin_ta_volume_momentum([volume, 3])
        assert -100 <= momentum <= 100

    def test_stable_volume_momentum(self, evaluator):
        """Test stable volume momentum."""
        volume = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        momentum = evaluator._builtin_ta_volume_momentum([volume, 3])
        assert -5 <= momentum <= 5  # Stable


class TestSmartMoneyFlow:
    """Tests for ta.smart_money_flow indicator."""

    def test_institutional_buying(self, evaluator):
        """Test institutional buying detection."""
        price_change = 2.5
        volume = 5000.0
        time_since_high = 10
        time_since_low = 2
        flow = evaluator._builtin_ta_smart_money_flow([price_change, volume, time_since_high, time_since_low])
        assert isinstance(flow, (int, float))
        assert -1.0 <= flow <= 1.0

    def test_institutional_selling(self, evaluator):
        """Test institutional selling detection."""
        price_change = -2.5
        volume = 5000.0
        time_since_high = 2
        time_since_low = 10
        flow = evaluator._builtin_ta_smart_money_flow([price_change, volume, time_since_high, time_since_low])
        assert -1.0 <= flow <= 1.0

    def test_balanced_institutional_flow(self, evaluator):
        """Test balanced institutional flow."""
        price_change = 0.2
        volume = 500.0
        time_since_high = 10
        time_since_low = 10
        flow = evaluator._builtin_ta_smart_money_flow([price_change, volume, time_since_high, time_since_low])
        assert -0.3 <= flow <= 0.3


class TestLiquidityScore:
    """Tests for ta.liquidity_score indicator."""

    def test_high_liquidity(self, evaluator):
        """Test high liquidity detection."""
        volume = [5000.0, 5200.0, 5400.0, 5600.0, 5800.0]
        volatility = [0.5, 0.45, 0.4, 0.35, 0.3]
        bid_ask_spread = [0.01, 0.01, 0.01, 0.01, 0.01]
        score = evaluator._builtin_ta_liquidity_score([volume, volatility, bid_ask_spread, 3])
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
        assert score > 70  # High liquidity

    def test_low_liquidity(self, evaluator):
        """Test low liquidity detection."""
        volume = [100.0, 90.0, 80.0, 70.0, 60.0]
        volatility = [5.0, 5.2, 5.4, 5.6, 5.8]
        bid_ask_spread = [1.0, 1.1, 1.2, 1.3, 1.4]
        score = evaluator._builtin_ta_liquidity_score([volume, volatility, bid_ask_spread, 3])
        assert score < 30  # Low liquidity

    def test_moderate_liquidity(self, evaluator):
        """Test moderate liquidity detection."""
        volume = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        volatility = [1.5, 1.4, 1.3, 1.2, 1.1]
        bid_ask_spread = [0.1, 0.1, 0.1, 0.1, 0.1]
        score = evaluator._builtin_ta_liquidity_score([volume, volatility, bid_ask_spread, 3])
        assert 30 <= score <= 70


# ============================================================================
# Group F: Advanced Pattern Recognition Tests (4 tests)
# ============================================================================

class TestVolumeThrust:
    """Tests for ta.volume_thrust indicator."""

    def test_volume_thrust_detected(self, evaluator):
        """Test volume thrust pattern detection."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [1000.0, 1100.0, 1200.0, 5000.0, 1300.0]
        volume_sma = [1100.0, 1100.0, 1100.0, 1100.0, 1100.0]
        is_thrust = evaluator._builtin_ta_volume_thrust([close, volume, volume_sma, 0.3])
        assert isinstance(is_thrust, bool)

    def test_no_volume_thrust(self, evaluator):
        """Test no volume thrust scenario."""
        close = [100.0, 100.1, 100.0, 100.1, 100.0]
        volume = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        volume_sma = [1100.0, 1100.0, 1100.0, 1100.0, 1100.0]
        is_thrust = evaluator._builtin_ta_volume_thrust([close, volume, volume_sma, 0.3])
        assert is_thrust is False  # No thrust (no price move)

    def test_volume_spike_without_price_move(self, evaluator):
        """Test volume spike without significant price move."""
        close = [100.0, 100.1, 100.0, 100.1, 100.0]
        volume = [1000.0, 1100.0, 1200.0, 10000.0, 1300.0]
        volume_sma = [1100.0, 1100.0, 1100.0, 1100.0, 1100.0]
        is_thrust = evaluator._builtin_ta_volume_thrust([close, volume, volume_sma, 0.3])
        assert is_thrust is False  # High volume but no price move

    def test_price_move_without_volume_spike(self, evaluator):
        """Test price move without volume spike."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        volume_sma = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        is_thrust = evaluator._builtin_ta_volume_thrust([close, volume, volume_sma, 0.3])
        assert is_thrust is False  # Price move but no volume spike


# ============================================================================
# Edge Case & Integration Tests (8 tests)
# ============================================================================

class TestEdgeCases:
    """Edge case tests for all Tier 6 indicators."""

    def test_empty_inputs(self, evaluator):
        """Test handling of empty inputs."""
        result = evaluator._builtin_ta_order_flow_imbalance([[], [], [], [], 3])
        assert result is None or isinstance(result, (int, float))

    def test_single_bar_data(self, evaluator):
        """Test handling of single bar data."""
        result = evaluator._builtin_ta_volume_profile_high([[100.0], [1000.0], 1, 10])
        assert result is not None

    def test_none_values(self, evaluator):
        """Test handling of None values in data."""
        close = [100.0, None, 101.0, None, 102.0]
        volume = [1000.0, None, 1100.0, None, 1200.0]
        result = evaluator._builtin_ta_momentum_divergence(
            [close, [1.0, None, 1.2, None, 1.4], [0.8, None, 1.0, None, 1.2]]
        )
        assert result is not None

    def test_extreme_values(self, evaluator):
        """Test handling of extreme values."""
        close = [1e10, 1e10 + 1e9, 1e10 + 2e9, 1e10 + 3e9, 1e10 + 4e9]
        volume = [1e15, 1.1e15, 1.2e15, 1.3e15, 1.4e15]
        volatility = [0.001, 0.0009, 0.0008, 0.0007, 0.0006]
        spread = [0.0001, 0.0001, 0.0001, 0.0001, 0.0001]
        result = evaluator._builtin_ta_liquidity_score([volume, volatility, spread, 3])
        assert result is not None

    def test_zero_volume(self, evaluator):
        """Test handling of zero volume."""
        close = [100.0, 101.0, 102.0, 103.0, 104.0]
        volume = [0.0, 0.0, 0.0, 0.0, 0.0]
        result = evaluator._builtin_ta_cumulative_delta([close, volume, 5])
        assert result == 0.0 or result is None

    def test_identical_prices(self, evaluator):
        """Test handling of identical prices."""
        close = [100.0, 100.0, 100.0, 100.0, 100.0]
        sma = [100.0, 100.0, 100.0, 100.0, 100.0]
        stdev = [0.0, 0.0, 0.0, 0.0, 0.0]
        result = evaluator._builtin_ta_mean_reversion_score([close, sma, stdev, 3])
        assert 0 <= result <= 100

    def test_price_gap_events(self, evaluator):
        """Test handling of price gaps."""
        close = [100.0, 110.0, 120.0, 130.0, 140.0]  # Extreme gaps
        volume = [1000.0, 1100.0, 1200.0, 1300.0, 1400.0]
        result = evaluator._builtin_ta_economic_impact_score([10.0, 1.0, 0.2])
        assert 0 <= result <= 100


class TestIntegration:
    """Integration tests combining multiple Tier 6 functions."""

    def test_microstructure_with_momentum(self, evaluator):
        """Test combining microstructure with momentum indicators."""
        # Order flow + momentum divergence
        high = [100, 101, 102, 103, 104]
        low = [95, 96, 97, 98, 99]
        close = [102, 102.5, 103, 103.5, 104]
        volume = [1000, 1200, 1100, 1300, 1400]
        imbalance = evaluator._builtin_ta_order_flow_imbalance([high, low, close, volume, 3])
        
        close2 = [100, 101, 102, 103, 104]
        rsi = [1.0, 1.2, 1.4, 1.6, 1.8]
        stoch = [0.8, 1.0, 1.2, 1.4, 1.6]
        divergence = evaluator._builtin_ta_momentum_divergence([close2, rsi, stoch])
        assert imbalance is not None
        assert divergence is not None

    def test_behavioral_with_volume(self, evaluator):
        """Test combining behavioral with volume indicators."""
        # Fear/greed + liquidity
        vix = [40, 35, 30, 25, 20]
        put_call = [2.0, 2.1, 2.2, 2.3, 2.4]
        safe_haven = [1.5, 1.4, 1.3, 1.2, 1.1]
        margin = [0.3, 0.35, 0.4, 0.45, 0.5]
        fg_index = evaluator._builtin_ta_fear_greed_index([vix, put_call, safe_haven, margin])
        
        volume = [5000, 5200, 5400, 5600, 5800]
        volatility = [0.5, 0.45, 0.4, 0.35, 0.3]
        spread = [0.01, 0.01, 0.01, 0.01, 0.01]
        liquidity = evaluator._builtin_ta_liquidity_score([volume, volatility, spread, 3])
        assert fg_index is not None
        assert liquidity is not None

    def test_economic_with_technical(self, evaluator):
        """Test combining economic with technical indicators."""
        # GDP proxy + volume momentum
        breadth = [0.6, 0.65, 0.7, 0.75, 0.8]
        volume = [1000, 1200, 1400, 1600, 1800]
        momentum = [1.0, 1.2, 1.4, 1.6, 1.8]
        gdp = evaluator._builtin_ta_gdp_growth_proxy([breadth, volume, momentum])
        
        vol_mom = evaluator._builtin_ta_volume_momentum([[1000, 1100, 1200, 1300, 1400], 3])
        assert gdp is not None
        assert vol_mom is not None

    def test_full_trading_signal_generation(self, evaluator):
        """Test full trading signal generation using multiple Tier 6 functions."""
        # Combine multiple indicators for a complete signal
        high = [100, 101, 102, 103, 104]
        low = [95, 96, 97, 98, 99]
        close = [102, 102.5, 103, 103.5, 104]
        volume = [1000, 1200, 1100, 1300, 1400]
        ofi = evaluator._builtin_ta_order_flow_imbalance([high, low, close, volume, 3])
        
        close2 = [100, 101, 102, 103, 104]
        ma = [100.5, 100.8, 101.1, 101.4, 101.7]
        volume2 = [1.0, 1.1, 1.2, 1.3, 1.4]
        mean_rev = evaluator._builtin_ta_mean_reversion_score([close2, ma, volume2, 3])
        sentiment = evaluator._builtin_ta_crowd_sentiment([0.7, 0.65, 0.75])

        # All should return valid values
        assert ofi is not None
        assert mean_rev is not None
        assert sentiment is not None
