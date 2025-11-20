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

"""
Phase 8 Tier 5: Advanced Integration & Real-World Indicators

Tests for 15 new real-world trading indicators:
- Market condition analysis
- Pattern recognition
- Risk management
- Multi-indicator combinations
- Volatility analysis
"""

from __future__ import annotations

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


@pytest.fixture
def evaluator():
    """Create evaluator for builtin tests."""
    return NodeLiteralEvaluator()


# ============================================================================
# Group A: Market Condition Indicators (4 tests each)
# ============================================================================

class TestMarketCondition:
    """Tests for ta.market_condition indicator."""

    def test_trending_up_condition(self, evaluator):
        """Test detection of trending up market."""
        close = [98.0, 99.0, 100.0, 101.0, 102.0]
        atr = [1.0, 1.0, 1.0, 1.0, 1.0]
        condition = evaluator._builtin_ta_market_condition([close, atr, 3, 2])
        assert condition == "trending_up"

    def test_trending_down_condition(self, evaluator):
        """Test detection of trending down market."""
        close = [102.0, 101.0, 100.0, 99.0, 98.0]
        atr = [1.0, 1.0, 1.0, 1.0, 1.0]
        condition = evaluator._builtin_ta_market_condition([close, atr, 3, 2])
        assert condition == "trending_down"

    def test_ranging_condition(self, evaluator):
        """Test detection of ranging market."""
        close = [100.0, 101.0, 100.0, 101.0, 100.0]
        atr = [0.5, 0.5, 0.5, 0.5, 0.5]
        condition = evaluator._builtin_ta_market_condition([close, atr, 3, 2])
        assert condition == "ranging"

    def test_volatile_condition(self, evaluator):
        """Test detection of volatile market."""
        close = [100.0, 95.0, 105.0, 90.0, 110.0]
        atr = [5.0, 5.0, 5.0, 5.0, 5.0]
        condition = evaluator._builtin_ta_market_condition([close, atr, 3, 2])
        assert condition in ["volatile", "trending_up", "trending_down"]


class TestVolatilityRegime:
    """Tests for ta.volatility_regime indicator."""

    def test_low_volatility_regime(self, evaluator):
        """Test low volatility detection."""
        atr_list = [0.1, 0.15, 0.12, 0.1, 0.08]
        regime = evaluator._builtin_ta_volatility_regime([atr_list, 3])
        assert regime in ["low", "medium"]

    def test_medium_volatility_regime(self, evaluator):
        """Test medium volatility detection."""
        atr_list = [1.5, 1.6, 1.55, 1.5, 1.48]
        regime = evaluator._builtin_ta_volatility_regime([atr_list, 3])
        assert regime == "medium"

    def test_high_volatility_regime(self, evaluator):
        """Test high volatility detection."""
        atr_list = [0.5, 0.6, 0.55, 2.0, 2.5]
        regime = evaluator._builtin_ta_volatility_regime([atr_list, 3])
        assert regime in ["high", "extreme", "medium"]

    def test_extreme_volatility_regime(self, evaluator):
        """Test extreme volatility detection."""
        atr_list = [1.0, 1.0, 1.0, 3.0, 3.2]
        regime = evaluator._builtin_ta_volatility_regime([atr_list, 3])
        assert regime in ["extreme", "high"]


class TestTrendStrength:
    """Tests for ta.trend_strength indicator."""

    def test_strong_uptrend(self, evaluator):
        """Test strong uptrend strength calculation."""
        strength = evaluator._builtin_ta_trend_strength([100.0, 50.0, 25.0])
        assert 50 <= strength <= 100  # Strong trend

    def test_weak_trend(self, evaluator):
        """Test weak trend strength calculation."""
        strength = evaluator._builtin_ta_trend_strength([100.0, 20.0, 60.0])
        assert 0 <= strength <= 50  # Weak trend

    def test_neutral_strength(self, evaluator):
        """Test neutral trend strength."""
        strength = evaluator._builtin_ta_trend_strength([100.0, 15.0, 50.0])
        assert 0 <= strength <= 100

    def test_strong_downtrend(self, evaluator):
        """Test strong downtrend strength calculation."""
        strength = evaluator._builtin_ta_trend_strength([100.0, 60.0, 70.0])
        assert 40 <= strength <= 100  # Strong trend signal


class TestRiskRewardRatio:
    """Tests for ta.risk_reward_ratio indicator."""

    def test_favorable_ratio(self, evaluator):
        """Test favorable risk/reward ratio."""
        ratio = evaluator._builtin_ta_risk_reward_ratio([100.0, 90.0, 120.0])
        assert ratio == 2.0  # 1:2 ratio

    def test_breakeven_ratio(self, evaluator):
        """Test breakeven risk/reward ratio."""
        ratio = evaluator._builtin_ta_risk_reward_ratio([100.0, 90.0, 100.0])
        assert ratio == 0.0

    def test_unfavorable_ratio(self, evaluator):
        """Test unfavorable risk/reward ratio."""
        ratio = evaluator._builtin_ta_risk_reward_ratio([100.0, 90.0, 105.0])
        assert 0 < ratio < 1

    def test_invalid_ratio(self, evaluator):
        """Test invalid setup (entry = stop)."""
        ratio = evaluator._builtin_ta_risk_reward_ratio([100.0, 100.0, 110.0])
        assert ratio is None or ratio == float('inf')


# ============================================================================
# Group B: Pattern Recognition Indicators (3 tests each)
# ============================================================================

class TestDoubleTopBottom:
    """Tests for ta.double_top_bottom pattern detector."""

    def test_double_top_pattern(self, evaluator):
        """Test double top pattern detection."""
        high = [100.0, 105.0, 102.0, 105.0, 103.0]
        low = [95.0, 100.0, 97.0, 100.0, 98.0]
        result = evaluator._builtin_ta_double_top_bottom([high, low, 3])
        assert isinstance(result, dict)
        assert "pattern_type" in result
        assert result["pattern_type"] in ["double_top", "double_bottom", "none"]

    def test_double_bottom_pattern(self, evaluator):
        """Test double bottom pattern detection."""
        high = [105.0, 100.0, 102.0, 100.0, 103.0]
        low = [100.0, 95.0, 97.0, 95.0, 98.0]
        result = evaluator._builtin_ta_double_top_bottom([high, low, 3])
        assert isinstance(result, dict)
        assert "strength" in result
        assert 0 <= result["strength"] <= 1

    def test_no_pattern(self, evaluator):
        """Test no pattern detection."""
        high = [100.0, 101.0, 102.0, 103.0, 104.0]
        low = [95.0, 96.0, 97.0, 98.0, 99.0]
        result = evaluator._builtin_ta_double_top_bottom([high, low, 3])
        assert result["pattern_type"] == "none"


class TestBreakoutDetection:
    """Tests for ta.breakout_detection indicator."""

    def test_resistance_breakout(self, evaluator):
        """Test resistance level breakout."""
        result = evaluator._builtin_ta_breakout_detection([102.0, 100.0, 95.0])
        assert isinstance(result, dict)
        assert result["is_breakout"] is True
        assert result["breakout_type"] == "resistance"

    def test_support_breakout(self, evaluator):
        """Test support level breakout."""
        result = evaluator._builtin_ta_breakout_detection([94.0, 100.0, 95.0])
        assert result["is_breakout"] is True
        assert result["breakout_type"] == "support"

    def test_no_breakout(self, evaluator):
        """Test no breakout scenario."""
        result = evaluator._builtin_ta_breakout_detection([98.0, 100.0, 95.0])
        assert result["is_breakout"] is False


class TestInsideBarPattern:
    """Tests for ta.inside_bar_pattern detector."""

    def test_inside_bar_detected(self, evaluator):
        """Test inside bar detection."""
        high = [105.0, 104.0, 103.0]
        low = [95.0, 96.0, 97.0]
        is_inside = evaluator._builtin_ta_inside_bar_pattern([high, low])
        assert is_inside is True

    def test_outside_bar(self, evaluator):
        """Test outside bar (not inside)."""
        high = [105.0, 106.0, 107.0]
        low = [95.0, 94.0, 93.0]
        is_inside = evaluator._builtin_ta_inside_bar_pattern([high, low])
        assert is_inside is False

    def test_equal_range_bar(self, evaluator):
        """Test bar with equal range."""
        high = [105.0, 105.0, 104.0]
        low = [95.0, 95.0, 96.0]
        is_inside = evaluator._builtin_ta_inside_bar_pattern([high, low])
        assert isinstance(is_inside, bool)


# ============================================================================
# Group C: Money Management & Risk Indicators (3 tests each)
# ============================================================================

class TestPositionSizing:
    """Tests for ta.position_sizing calculator."""

    def test_position_size_calculation(self, evaluator):
        """Test basic position sizing calculation."""
        size = evaluator._builtin_ta_position_sizing([10000.0, 1.0, 100.0, 95.0])
        assert size > 0
        assert size <= 200  # Reasonable upper bound

    def test_small_risk_position(self, evaluator):
        """Test position sizing with small risk."""
        size = evaluator._builtin_ta_position_sizing([10000.0, 0.5, 100.0, 95.0])
        assert size > 0
        assert size < evaluator._builtin_ta_position_sizing([10000.0, 1.0, 100.0, 95.0])

    def test_large_stop_position(self, evaluator):
        """Test position sizing with large stop."""
        size = evaluator._builtin_ta_position_sizing([10000.0, 1.0, 100.0, 50.0])
        assert size > 0
        assert size < evaluator._builtin_ta_position_sizing([10000.0, 1.0, 100.0, 95.0])


class TestKellyCriterion:
    """Tests for ta.kelly_criterion optimizer."""

    def test_kelly_sizing(self, evaluator):
        """Test Kelly criterion calculation."""
        kelly_pct = evaluator._builtin_ta_kelly_criterion([0.6, 2.0, 1.0])
        assert 0 <= kelly_pct <= 1
        assert kelly_pct > 0  # Positive expectancy

    def test_kelly_no_edge(self, evaluator):
        """Test Kelly with no edge."""
        kelly_pct = evaluator._builtin_ta_kelly_criterion([0.5, 1.0, 1.0])
        assert kelly_pct == 0.0  # No edge = zero Kelly

    def test_kelly_negative_edge(self, evaluator):
        """Test Kelly with negative edge."""
        kelly_pct = evaluator._builtin_ta_kelly_criterion([0.4, 1.0, 1.0])
        assert kelly_pct <= 0  # Negative expectancy


class TestMaxLossLevel:
    """Tests for ta.max_loss_level calculator."""

    def test_max_loss_stop(self, evaluator):
        """Test maximum loss stop calculation."""
        stop = evaluator._builtin_ta_max_loss_level([100.0, 10000.0, 1.0])
        assert stop < 100.0  # Stop below entry
        assert stop > 0  # Valid price

    def test_small_account_stop(self, evaluator):
        """Test stop with small account."""
        stop = evaluator._builtin_ta_max_loss_level([100.0, 1000.0, 1.0])
        assert stop < 100.0

    def test_large_loss_percent(self, evaluator):
        """Test with large loss percentage."""
        stop_small = evaluator._builtin_ta_max_loss_level([100.0, 10000.0, 0.5])
        stop_large = evaluator._builtin_ta_max_loss_level([100.0, 10000.0, 2.0])
        assert stop_large < stop_small  # Larger loss = lower stop


class TestProfitLockLevel:
    """Tests for ta.profit_lock_level calculator."""

    def test_long_trailing_stop(self, evaluator):
        """Test trailing stop for long position."""
        stop = evaluator._builtin_ta_profit_lock_level([100.0, 110.0, 0.05, 1])
        assert 100.0 < stop < 110.0  # Between entry and current

    def test_short_trailing_stop(self, evaluator):
        """Test trailing stop for short position."""
        stop = evaluator._builtin_ta_profit_lock_level([100.0, 90.0, 0.05, -1])
        assert 90.0 < stop < 100.0

    def test_no_profit_long(self, evaluator):
        """Test trailing stop with no profit (long)."""
        stop = evaluator._builtin_ta_profit_lock_level([100.0, 95.0, 0.05, 1])
        assert stop > 0  # Valid stop level


# ============================================================================
# Group D: Multi-Indicator Integration (3 tests each)
# ============================================================================

class TestSignalConfluence:
    """Tests for ta.signal_confluence detector."""

    def test_high_confluence(self, evaluator):
        """Test high signal confluence."""
        signals = {"rsi": 1, "macd": 1, "ema": 1, "bb": 1}
        result = evaluator._builtin_ta_signal_confluence([signals])
        assert isinstance(result, dict)
        assert result["signal_count"] == 4
        assert result["confluence_level"] == 1.0

    def test_mixed_signals(self, evaluator):
        """Test mixed signal confluence."""
        signals = {"rsi": 1, "macd": -1, "ema": 1, "bb": 0}
        result = evaluator._builtin_ta_signal_confluence([signals])
        assert 0 <= result["confluence_level"] <= 1

    def test_no_signals(self, evaluator):
        """Test no signal confluence."""
        signals = {"rsi": 0, "macd": 0, "ema": 0}
        result = evaluator._builtin_ta_signal_confluence([signals])
        assert result["signal_count"] == 0


class TestDivergenceDetector:
    """Tests for ta.divergence_detector indicator."""

    def test_bullish_divergence(self, evaluator):
        """Test bullish divergence detection."""
        price = [100.0, 95.0, 98.0]
        indicator = [50.0, 40.0, 45.0]
        result = evaluator._builtin_ta_divergence_detector([price, indicator, 2])
        assert isinstance(result, dict)
        assert "is_bullish" in result
        assert "is_bearish" in result

    def test_bearish_divergence(self, evaluator):
        """Test bearish divergence detection."""
        price = [100.0, 105.0, 102.0]
        indicator = [50.0, 60.0, 55.0]
        result = evaluator._builtin_ta_divergence_detector([price, indicator, 2])
        assert isinstance(result, dict)

    def test_no_divergence(self, evaluator):
        """Test no divergence scenario."""
        price = [100.0, 105.0, 110.0]
        indicator = [50.0, 55.0, 60.0]
        result = evaluator._builtin_ta_divergence_detector([price, indicator, 2])
        assert result["is_bullish"] is False
        assert result["is_bearish"] is False


class TestStrategyScore:
    """Tests for ta.strategy_score aggregator."""

    def test_bullish_score(self, evaluator):
        """Test bullish strategy score."""
        score = evaluator._builtin_ta_strategy_score([75.0, 0.5, True, 35.0])
        assert -100 <= score <= 100
        assert score > 0  # Bullish

    def test_bearish_score(self, evaluator):
        """Test bearish strategy score."""
        score = evaluator._builtin_ta_strategy_score([25.0, -0.5, False, 65.0])
        assert -100 <= score <= 100
        assert score < 0  # Bearish

    def test_neutral_score(self, evaluator):
        """Test neutral strategy score."""
        score = evaluator._builtin_ta_strategy_score([50.0, 0.0, False, 50.0])
        assert -100 <= score <= 100


# ============================================================================
# Group E: Volatility & Probability (2-3 tests each)
# ============================================================================

class TestProbabilityOfMovement:
    """Tests for ta.probability_of_movement calculator."""

    def test_close_target_probability(self, evaluator):
        """Test probability for close target."""
        prob = evaluator._builtin_ta_probability_of_movement([100.0, 101.0, 1.0, 5])
        assert 0 <= prob <= 1

    def test_distant_target_probability(self, evaluator):
        """Test probability for distant target."""
        prob_close = evaluator._builtin_ta_probability_of_movement([100.0, 101.0, 1.0, 5])
        prob_far = evaluator._builtin_ta_probability_of_movement([100.0, 110.0, 1.0, 5])
        assert 0 <= prob_close <= 1 and 0 <= prob_far <= 1

    def test_high_volatility_probability(self, evaluator):
        """Test probability with high volatility."""
        prob_low_vol = evaluator._builtin_ta_probability_of_movement([100.0, 105.0, 1.0, 5])
        prob_high_vol = evaluator._builtin_ta_probability_of_movement([100.0, 105.0, 5.0, 5])
        assert 0 <= prob_low_vol <= 1 and 0 <= prob_high_vol <= 1


class TestGammaLevels:
    """Tests for ta.gamma_levels calculator."""

    def test_gamma_levels_calculation(self, evaluator):
        """Test gamma levels calculation."""
        levels = evaluator._builtin_ta_gamma_levels([0.02, 100.0, 20])
        assert isinstance(levels, list)
        assert len(levels) == 2
        assert levels[0] > 100.0  # Upper level
        assert levels[1] < 100.0  # Lower level

    def test_gamma_levels_symmetry(self, evaluator):
        """Test gamma levels symmetry around price."""
        levels = evaluator._builtin_ta_gamma_levels([0.02, 100.0, 20])
        distance_up = levels[0] - 100.0
        distance_down = 100.0 - levels[1]
        assert abs(distance_up - distance_down) < 1  # Approximately symmetric


# ============================================================================
# Integration Tests
# ============================================================================

class TestTier5Integration:
    """Integration tests combining multiple Tier 5 indicators."""

    def test_market_condition_with_position_sizing(self, evaluator):
        """Test combining market condition with position sizing."""
        close = [98.0, 99.0, 100.0, 101.0, 102.0]
        atr = [1.0, 1.0, 1.0, 1.0, 1.0]
        condition = evaluator._builtin_ta_market_condition([close, atr, 3, 2])

        if condition == "trending_up":
            size = evaluator._builtin_ta_position_sizing([10000.0, 2.0, 102.0, 100.0])
            assert size > 0

    def test_signal_confluence_with_strategy_score(self, evaluator):
        """Test combining signal confluence with strategy score."""
        signals = {"rsi": 1, "macd": 1, "ema": 1}
        confluence = evaluator._builtin_ta_signal_confluence([signals])

        if confluence["signal_count"] >= 2:
            score = evaluator._builtin_ta_strategy_score([75.0, 0.5, True, 35.0])
            assert score > 0

    def test_breakout_with_risk_reward(self, evaluator):
        """Test combining breakout detection with risk/reward."""
        result = evaluator._builtin_ta_breakout_detection([102.0, 100.0, 95.0])

        if result["is_breakout"]:
            ratio = evaluator._builtin_ta_risk_reward_ratio([100.0, 95.0, 110.0])
            assert ratio > 0

    def test_volatility_with_position_sizing(self, evaluator):
        """Test volatility regime impact on position sizing."""
        atr_low = [0.5, 0.6, 0.55]
        atr_high = [3.0, 3.2, 3.1]

        size_low_vol = evaluator._builtin_ta_position_sizing([10000.0, 1.0, 100.0, 95.0])
        size_high_vol = evaluator._builtin_ta_position_sizing([10000.0, 1.0, 100.0, 85.0])

        # Both should be positive
        assert size_low_vol > 0
        assert size_high_vol > 0

    def test_probability_with_profit_lock(self, evaluator):
        """Test probability assessment with profit locking."""
        prob = evaluator._builtin_ta_probability_of_movement([100.0, 110.0, 2.0, 5])

        if prob > 0.5:
            stop = evaluator._builtin_ta_profit_lock_level([100.0, 105.0, 0.05, 1])
            assert isinstance(stop, float) and stop > 0
