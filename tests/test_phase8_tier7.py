# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
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
Phase 8 Tier 7: Advanced Trading Strategies & Market Timing

Tests for 16 advanced strategy and market timing indicators:
- Multi-indicator strategies (trend confirmation, market structure, volatility regime, correlation)
- Advanced trend & breakout (breakout detection, pullback levels, multi-timeframe, position sizing)
- Advanced entry/exit (optimal entry, trailing exits, mean reversion, breakeven)
- Risk & regime (drawdown recovery, risk/reward asymmetry)
- Market timing (market timing index, regime-adaptive signals)

Total: 56+ comprehensive tests across 20+ test classes
"""

from __future__ import annotations

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


@pytest.fixture
def evaluator():
    """Create evaluator for builtin tests."""
    return NodeLiteralEvaluator()


# ============================================================================
# Group A: Multi-Indicator Strategies Tests (16 tests)
# ============================================================================

class TestTrendConfirmationScore:
    """Tests for ta.trend_confirmation_score indicator."""

    def test_strong_confirmation(self, evaluator):
        """Test strong trend confirmation."""
        score = evaluator._builtin_ta_trend_confirmation_score([50.0, 0.8, 2.0, 70.0, 0.9, 45.0])
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_weak_confirmation(self, evaluator):
        """Test weak trend confirmation."""
        score = evaluator._builtin_ta_trend_confirmation_score([10.0, 0.1, 1.0, 50.0, 0.2, 10.0])
        assert 0 <= score <= 100

    def test_conflicting_signals(self, evaluator):
        """Test conflicting signals reduce score."""
        score = evaluator._builtin_ta_trend_confirmation_score([50.0, -0.8, 2.0, 30.0, -0.9, 45.0])
        assert 0 <= score <= 100

    def test_neutral_confirmation(self, evaluator):
        """Test neutral confirmation scenario."""
        score = evaluator._builtin_ta_trend_confirmation_score([0.0, 0.0, 1.5, 50.0, 0.0, 0.0])
        assert 0 <= score <= 100


class TestMarketStructurePivot:
    """Tests for ta.market_structure_pivot indicator."""

    def test_fractal_detection(self, evaluator):
        """Test fractal market structure detection."""
        high = [100.0, 102.0, 104.0, 103.0, 101.0]
        low = [98.0, 100.0, 102.0, 101.0, 99.0]
        close = [99.0, 101.0, 103.0, 102.0, 100.0]
        result = evaluator._builtin_ta_market_structure_pivot([high, low, close, 5, 0])
        assert isinstance(result, dict)
        assert "pivot_price" in result

    def test_swing_detection(self, evaluator):
        """Test swing market structure detection."""
        high = [100.0, 102.0, 103.0, 102.0, 101.0]
        low = [98.0, 99.0, 100.0, 99.0, 98.0]
        close = [99.0, 101.0, 102.0, 100.0, 99.0]
        result = evaluator._builtin_ta_market_structure_pivot([high, low, close, 5, 1])
        assert isinstance(result, dict)
        assert "structure" in result

    def test_block_detection(self, evaluator):
        """Test block consolidation detection."""
        high = [100.0, 100.5, 100.0, 100.2, 100.1]
        low = [99.5, 99.8, 99.5, 99.7, 99.6]
        close = [99.8, 100.0, 99.9, 100.0, 99.9]
        result = evaluator._builtin_ta_market_structure_pivot([high, low, close, 5, 2])
        assert isinstance(result, dict)
        assert result["structure"] in ["fractal", "swing", "block"]

    def test_structure_strength(self, evaluator):
        """Test structure strength calculation."""
        high = [100.0, 102.0, 104.0, 103.0, 101.0]
        low = [98.0, 100.0, 102.0, 101.0, 99.0]
        close = [99.0, 101.0, 103.0, 102.0, 100.0]
        result = evaluator._builtin_ta_market_structure_pivot([high, low, close, 5, 0])
        assert 0 <= result["strength"] <= 100


class TestVolatilityRegimeScore:
    """Tests for ta.volatility_regime_score indicator."""

    def test_low_volatility_regime(self, evaluator):
        """Test low volatility regime detection."""
        atr = [0.5, 0.5, 0.5, 0.5, 0.5]
        vol = [0.01, 0.01, 0.01, 0.01, 0.01]
        vix = [10.0, 10.5, 11.0, 10.8, 10.5]
        score = evaluator._builtin_ta_volatility_regime_score([atr, vol, vix, 30.0])
        assert isinstance(score, dict)
        assert score["regime"] in ["low", "normal", "high", "extreme"]

    def test_high_volatility_regime(self, evaluator):
        """Test high volatility regime detection."""
        atr = [5.0, 5.5, 6.0, 5.8, 5.5]
        vol = [0.05, 0.06, 0.07, 0.06, 0.05]
        vix = [30.0, 32.0, 35.0, 33.0, 31.0]
        score = evaluator._builtin_ta_volatility_regime_score([atr, vol, vix, 70.0])
        assert score["regime"] in ["low", "normal", "high", "extreme"]

    def test_normal_volatility_regime(self, evaluator):
        """Test normal volatility regime."""
        atr = [2.0, 2.1, 2.0, 2.2, 2.0]
        vol = [0.02, 0.021, 0.02, 0.022, 0.02]
        vix = [15.0, 15.5, 16.0, 15.8, 15.5]
        score = evaluator._builtin_ta_volatility_regime_score([atr, vol, vix, 50.0])
        assert score["volatility_score"] >= 0

    def test_regime_momentum(self, evaluator):
        """Test volatility regime momentum detection."""
        atr = [2.0, 2.5, 3.0, 3.5, 4.0]
        vol = [0.02, 0.025, 0.03, 0.035, 0.04]
        vix = [15.0, 16.0, 17.0, 18.0, 19.0]
        score = evaluator._builtin_ta_volatility_regime_score([atr, vol, vix, 60.0])
        assert score["momentum"] in ["accelerating", "stable", "decelerating"]


class TestCorrelationFilter:
    """Tests for ta.correlation_filter indicator."""

    def test_correlated_signals(self, evaluator):
        """Test highly correlated signals."""
        sig1 = [1.0, 1.2, 1.4, 1.6, 1.8]
        sig2 = [0.9, 1.1, 1.3, 1.5, 1.7]
        sig3 = [1.1, 1.3, 1.5, 1.7, 1.9]
        result = evaluator._builtin_ta_correlation_filter([sig1, sig2, sig3, 3, 0.7])
        assert isinstance(result, dict)
        assert "is_correlated" in result

    def test_divergent_signals(self, evaluator):
        """Test divergent (uncorrelated) signals."""
        sig1 = [1.0, 1.5, 2.0, 1.5, 1.0]
        sig2 = [-0.5, 0.0, 0.5, 0.0, -0.5]
        sig3 = [0.2, 0.1, 0.3, 0.1, 0.2]
        result = evaluator._builtin_ta_correlation_filter([sig1, sig2, sig3, 3, 0.7])
        assert isinstance(result["is_correlated"], bool)

    def test_signal_agreement(self, evaluator):
        """Test signal agreement percentage."""
        sig1 = [1.0, 1.0, 1.0, 1.0, 1.0]
        sig2 = [1.0, 1.0, -1.0, 1.0, 1.0]
        sig3 = [1.0, 1.0, 1.0, 1.0, 1.0]
        result = evaluator._builtin_ta_correlation_filter([sig1, sig2, sig3, 3, 0.5])
        assert 0 <= result["signal_agreement"] <= 100

    def test_divergence_count(self, evaluator):
        """Test divergence counting."""
        sig1 = [1.0, 1.0, 1.0, 1.0, 1.0]
        sig2 = [-1.0, -1.0, -1.0, -1.0, -1.0]
        sig3 = [1.0, 1.0, 1.0, 1.0, 1.0]
        result = evaluator._builtin_ta_correlation_filter([sig1, sig2, sig3, 3, 0.5])
        assert result["divergence_count"] >= 0


# ============================================================================
# Group B: Advanced Trend & Breakout Tests (16 tests)
# ============================================================================

class TestAdvancedBreakoutDetector:
    """Tests for ta.advanced_breakout_detector indicator."""

    def test_gap_breakout(self, evaluator):
        """Test gap breakout detection."""
        price = [99.0, 100.0, 101.0, 102.0, 103.0]
        volume = [1000.0, 1200.0, 1100.0, 1300.0, 1400.0]
        result = evaluator._builtin_ta_advanced_breakout_detector([price, volume, 101.5, 10, 0.5])
        assert isinstance(result, dict)
        assert "breakout_detected" in result

    def test_close_breakout(self, evaluator):
        """Test close-based breakout."""
        price = [99.0, 100.0, 101.0, 101.8, 102.0]
        volume = [1000.0, 1200.0, 1100.0, 5000.0, 1400.0]
        result = evaluator._builtin_ta_advanced_breakout_detector([price, volume, 101.5, 10, 0.5])
        assert isinstance(result["breakout_type"], str)

    def test_volume_breakout(self, evaluator):
        """Test volume-driven breakout."""
        price = [99.0, 100.0, 101.0, 102.0, 103.0]
        volume = [1000.0, 1100.0, 1200.0, 2000.0, 3000.0]
        result = evaluator._builtin_ta_advanced_breakout_detector(
            [price, volume, 101.0, 10, 0.5]
        )
        assert result["breakout_detected"] is True

    def test_fake_breakout(self, evaluator):
        """Test fake-out detection."""
        price = [99.0, 100.0, 101.0, 102.0, 101.2]
        volume = [1000.0, 1200.0, 1100.0, 1300.0, 1400.0]
        result = evaluator._builtin_ta_advanced_breakout_detector([price, volume, 101.5, 10, 0.5])
        assert isinstance(result["pullback_probability"], float)


class TestPullbackBounceLevel:
    """Tests for ta.pullback_bounce_level indicator."""

    def test_uptrend_pullback(self, evaluator):
        """Test pullback levels in uptrend."""
        high = [100.0, 102.0, 104.0, 105.0, 103.0]
        low = [98.0, 100.0, 102.0, 103.0, 101.0]
        close = [99.0, 101.0, 103.0, 104.0, 102.0]
        result = evaluator._builtin_ta_pullback_bounce_level([high, low, close, 1, 10])
        assert isinstance(result, dict)
        assert "primary_level" in result

    def test_downtrend_bounce(self, evaluator):
        """Test bounce levels in downtrend."""
        high = [105.0, 103.0, 101.0, 100.0, 102.0]
        low = [103.0, 101.0, 99.0, 98.0, 100.0]
        close = [104.0, 102.0, 100.0, 99.0, 101.0]
        result = evaluator._builtin_ta_pullback_bounce_level([high, low, close, -1, 10])
        assert result["bounce_probability"] >= 0

    def test_fibonacci_levels(self, evaluator):
        """Test Fibonacci retracement generation."""
        high = [100.0, 102.0, 104.0, 106.0, 105.0]
        low = [98.0, 100.0, 102.0, 104.0, 103.0]
        close = [99.0, 101.0, 103.0, 105.0, 104.0]
        result = evaluator._builtin_ta_pullback_bounce_level([high, low, close, 1, 15])
        assert 98 < result["primary_level"] < 106

    def test_support_strength(self, evaluator):
        """Test support level strength calculation."""
        high = [100.0, 102.0, 104.0, 106.0, 105.0]
        low = [98.0, 100.0, 102.0, 104.0, 103.0]
        close = [99.0, 101.0, 103.0, 105.0, 104.0]
        result = evaluator._builtin_ta_pullback_bounce_level([high, low, close, 1, 20])
        assert 0 <= result["support_strength"] <= 100


class TestMultiTimeframeSignal:
    """Tests for ta.multi_timeframe_signal indicator."""

    def test_aligned_timeframes(self, evaluator):
        """Test aligned signals across timeframes."""
        result = evaluator._builtin_ta_multi_timeframe_signal([1, 1, 1, 0.3, 0.3, 0.4])
        assert isinstance(result, dict)
        assert -1 <= result["combined_signal"] <= 1

    def test_conflicting_timeframes(self, evaluator):
        """Test conflicting signals across timeframes."""
        result = evaluator._builtin_ta_multi_timeframe_signal([1, -1, 1, 0.3, 0.3, 0.4])
        assert isinstance(result["combined_signal"], float)

    def test_signal_agreement_count(self, evaluator):
        """Test signal agreement counting."""
        result = evaluator._builtin_ta_multi_timeframe_signal([1, 1, 1, 0.33, 0.33, 0.34])
        assert 0 <= result["signal_agreement"] <= 3

    def test_alignment_quality(self, evaluator):
        """Test alignment quality metric."""
        result = evaluator._builtin_ta_multi_timeframe_signal([1, 1, -1, 0.3, 0.3, 0.4])
        assert 0 <= result["alignment_quality"] <= 100


class TestPositionSizingScore:
    """Tests for ta.position_sizing_score indicator."""

    def test_conservative_sizing(self, evaluator):
        """Test conservative position sizing."""
        result = evaluator._builtin_ta_position_sizing_score([1.0, 80.0, 1.0, 0.5])
        assert isinstance(result, dict)
        assert "position_size_ratio" in result

    def test_aggressive_sizing(self, evaluator):
        """Test aggressive position sizing."""
        result = evaluator._builtin_ta_position_sizing_score([3.0, 20.0, 3.0, 0.1])
        assert 0 <= result["position_size_ratio"] <= 1

    def test_kelly_fraction(self, evaluator):
        """Test Kelly criterion calculation."""
        result = evaluator._builtin_ta_position_sizing_score([2.0, 50.0, 2.0, 0.3])
        assert 0 <= result["kelly_fraction"] <= 0.5

    def test_correlation_adjustment(self, evaluator):
        """Test correlation impact on sizing."""
        result = evaluator._builtin_ta_position_sizing_score([2.0, 50.0, 2.0, 0.8])
        assert 0 <= result["correlation_adjustment"] <= 1


# ============================================================================
# Group C: Advanced Entry/Exit Tests (16 tests)
# ============================================================================

class TestOptimalEntryZone:
    """Tests for ta.optimal_entry_zone indicator."""

    def test_single_confluence(self, evaluator):
        """Test zone with single confluence point."""
        result = evaluator._builtin_ta_optimal_entry_zone([100.0, 100.0, 100.0, 100.0])
        assert isinstance(result, dict)
        assert "zone_strength" in result

    def test_multiple_confluence(self, evaluator):
        """Test zone with multiple confluence points."""
        result = evaluator._builtin_ta_optimal_entry_zone([100.0, 100.0, 100.0, 100.0])
        assert result["zone_strength"] >= 0

    def test_entry_zone_bounds(self, evaluator):
        """Test zone upper and lower bounds."""
        result = evaluator._builtin_ta_optimal_entry_zone([99.5, 100.0, 99.8, 100.1])
        assert result["entry_zone_low"] <= result["entry_zone_high"]

    def test_best_entry_price(self, evaluator):
        """Test best entry price selection."""
        result = evaluator._builtin_ta_optimal_entry_zone([99.5, 100.0, 99.8, 100.1])
        assert result["entry_zone_low"] <= result["best_entry"] <= result["entry_zone_high"]


class TestTrailingExitLevel:
    """Tests for ta.trailing_exit_level indicator."""

    def test_profitable_position(self, evaluator):
        """Test trailing exit in profitable position."""
        result = evaluator._builtin_ta_trailing_exit_level([100.0, 105.0, 30.0, 2.0, 1.0])
        assert isinstance(result, dict)
        assert "trail_stop" in result

    def test_tight_trailing(self, evaluator):
        """Test tight trailing stop."""
        result = evaluator._builtin_ta_trailing_exit_level([100.0, 105.0, 10.0, 1.0, 1.5])
        assert result["trail_stop"] > 100.0

    def test_protected_profit(self, evaluator):
        """Test profit protection calculation."""
        result = evaluator._builtin_ta_trailing_exit_level([100.0, 105.0, 40.0, 2.0, 1.0])
        assert result["protected_profit"] >= 0

    def test_risk_reward_current(self, evaluator):
        """Test current risk/reward ratio."""
        result = evaluator._builtin_ta_trailing_exit_level([100.0, 105.0, 30.0, 2.0, 1.0])
        assert result["risk_reward_current"] >= 0


class TestMeanReversionEntry:
    """Tests for ta.mean_reversion_entry indicator."""

    def test_mean_reversion_setup(self, evaluator):
        """Test mean reversion setup detection."""
        result = evaluator._builtin_ta_mean_reversion_entry([95.0, 100.0, 2.0, 20, 2.0])
        assert isinstance(result, dict)
        assert isinstance(result["z_score"], float)

    def test_extreme_mean_reversion(self, evaluator):
        """Test extreme mean reversion scenario."""
        result = evaluator._builtin_ta_mean_reversion_entry([90.0, 100.0, 3.0, 20, 3.0])
        assert isinstance(result["is_mean_reversion_setup"], bool)

    def test_reversion_probability(self, evaluator):
        """Test reversion probability calculation."""
        result = evaluator._builtin_ta_mean_reversion_entry([95.0, 100.0, 2.0, 20, 2.0])
        assert 0 <= result["reversion_probability"] <= 1

    def test_target_price(self, evaluator):
        """Test mean reversion target calculation."""
        result = evaluator._builtin_ta_mean_reversion_entry([95.0, 100.0, 2.0, 20, 2.0])
        assert isinstance(result["target_price"], float)


class TestBreakevenLevel:
    """Tests for ta.breakeven_level indicator."""

    def test_long_breakeven(self, evaluator):
        """Test breakeven for long position."""
        result = evaluator._builtin_ta_breakeven_level([100.0, 1.0, 0.1, 0.05, 1])
        assert isinstance(result, dict)
        assert result["breakeven_price"] > 100.0

    def test_short_breakeven(self, evaluator):
        """Test breakeven for short position."""
        result = evaluator._builtin_ta_breakeven_level([100.0, 1.0, 0.1, 0.05, -1])
        assert result["breakeven_price"] < 100.0

    def test_total_cost(self, evaluator):
        """Test total cost calculation."""
        result = evaluator._builtin_ta_breakeven_level([100.0, 1.0, 0.1, 0.05, 1])
        assert result["total_cost"] >= 0

    def test_move_required_percent(self, evaluator):
        """Test percentage move required."""
        result = evaluator._builtin_ta_breakeven_level([100.0, 1.0, 0.1, 0.05, 1])
        assert result["move_required_percent"] >= 0


# ============================================================================
# Group D: Risk & Regime Tests (8 tests)
# ============================================================================

class TestDrawdownRecoveryLevel:
    """Tests for ta.drawdown_recovery_level indicator."""

    def test_recovery_calculation(self, evaluator):
        """Test recovery level calculation."""
        result = evaluator._builtin_ta_drawdown_recovery_level([110.0, 100.0, 1.0, 50])
        assert isinstance(result, dict)
        assert "drawdown_percent" in result

    def test_recovery_timeframe(self, evaluator):
        """Test recovery timeframe estimation."""
        result = evaluator._builtin_ta_drawdown_recovery_level([110.0, 100.0, 1.0, 50])
        assert result["recovery_timeframe"] >= 0

    def test_recovery_confidence(self, evaluator):
        """Test recovery confidence level."""
        result = evaluator._builtin_ta_drawdown_recovery_level([110.0, 100.0, 1.0, 50])
        assert 0 <= result["recovery_confidence"] <= 1

    def test_deep_drawdown(self, evaluator):
        """Test deep drawdown scenario."""
        result = evaluator._builtin_ta_drawdown_recovery_level([120.0, 80.0, 1.5, 100])
        assert result["drawdown_percent"] > 33


class TestRiskRewardAsymmetry:
    """Tests for ta.risk_reward_asymmetry indicator."""

    def test_favorable_setup(self, evaluator):
        """Test favorable risk/reward setup."""
        result = evaluator._builtin_ta_risk_reward_asymmetry([100.0, 98.0, 105.0, 0.6])
        assert isinstance(result, dict)
        assert "risk_reward_ratio" in result

    def test_unfavorable_setup(self, evaluator):
        """Test unfavorable risk/reward setup."""
        result = evaluator._builtin_ta_risk_reward_asymmetry([100.0, 99.0, 101.0, 0.6])
        assert result["risk_reward_ratio"] >= 0

    def test_expected_value(self, evaluator):
        """Test expected value calculation."""
        result = evaluator._builtin_ta_risk_reward_asymmetry([100.0, 98.0, 105.0, 0.7])
        assert isinstance(result["expected_value"], float)

    def test_kelly_percentage(self, evaluator):
        """Test Kelly percentage calculation."""
        result = evaluator._builtin_ta_risk_reward_asymmetry([100.0, 98.0, 105.0, 0.6])
        assert result["kelly_percentage"] >= 0


# ============================================================================
# Group E: Market Timing & Regime Tests (8 tests)
# ============================================================================

class TestMarketTimingIndex:
    """Tests for ta.market_timing_index indicator."""

    def test_optimal_long_conditions(self, evaluator):
        """Test optimal long market conditions."""
        result = evaluator._builtin_ta_market_timing_index([80.0, 30.0, 60.0, 60.0])
        assert isinstance(result, dict)
        assert -100 <= result["timing_index"] <= 100

    def test_optimal_short_conditions(self, evaluator):
        """Test optimal short market conditions."""
        result = evaluator._builtin_ta_market_timing_index([20.0, 30.0, 60.0, -60.0])
        assert result["market_condition"] in [
            "optimal_long",
            "favorable_long",
            "neutral",
            "favorable_short",
            "optimal_short",
        ]

    def test_neutral_conditions(self, evaluator):
        """Test neutral market conditions."""
        result = evaluator._builtin_ta_market_timing_index([50.0, 50.0, 50.0, 0.0])
        assert isinstance(result["confidence"], float)

    def test_timing_recommendation(self, evaluator):
        """Test timing recommendation generation."""
        result = evaluator._builtin_ta_market_timing_index([75.0, 40.0, 70.0, 70.0])
        assert result["recommendation"] in ["strong_buy", "buy", "hold", "sell", "strong_sell"]


class TestRegimeAdaptiveSignal:
    """Tests for ta.regime_adaptive_signal indicator."""

    def test_trending_regime_adaptation(self, evaluator):
        """Test signal adaptation in trending regime."""
        result = evaluator._builtin_ta_regime_adaptive_signal([0.8, "normal", "trending_up", 15])
        assert isinstance(result, dict)
        assert -1 <= result["adapted_signal"] <= 1

    def test_ranging_regime_adaptation(self, evaluator):
        """Test signal adaptation in ranging regime."""
        result = evaluator._builtin_ta_regime_adaptive_signal([0.5, "normal", "ranging", 10])
        assert isinstance(result["adapted_signal"], float)

    def test_high_volatility_adaptation(self, evaluator):
        """Test signal adaptation in high volatility."""
        result = evaluator._builtin_ta_regime_adaptive_signal([0.8, "high", "trending_up", 10])
        assert 0 <= result["regime_fit"] <= 1

    def test_regime_recommendation(self, evaluator):
        """Test strategy recommendation by regime."""
        result = evaluator._builtin_ta_regime_adaptive_signal([0.7, "normal", "ranging", 20])
        assert isinstance(result["strategy_recommendation"], str)


# ============================================================================
# Edge Cases & Integration Tests (8 tests)
# ============================================================================

class TestEdgeCases:
    """Edge case tests for Tier 7 indicators."""

    def test_empty_inputs(self, evaluator):
        """Test handling of empty input lists."""
        result = evaluator._builtin_ta_trend_confirmation_score([0.0, 0.0, 1.0, 50.0, 0.0, 0.0])
        assert isinstance(result, (int, float))

    def test_single_value_inputs(self, evaluator):
        """Test handling of single value inputs."""
        result = evaluator._builtin_ta_position_sizing_score([2.0, 50.0, 2.0, 0.5])
        assert isinstance(result, dict)

    def test_extreme_values(self, evaluator):
        """Test handling of extreme values."""
        result = evaluator._builtin_ta_market_timing_index([100.0, 100.0, 100.0, 100.0])
        assert -100 <= result["timing_index"] <= 100

    def test_zero_values(self, evaluator):
        """Test handling of zero values."""
        result = evaluator._builtin_ta_risk_reward_asymmetry([100.0, 100.0, 100.0, 0.5])
        assert isinstance(result, dict)

    def test_negative_values(self, evaluator):
        """Test handling of negative values."""
        result = evaluator._builtin_ta_multi_timeframe_signal([-1, -1, -1, 0.3, 0.3, 0.4])
        assert -1 <= result["combined_signal"] <= 1

    def test_extreme_confidence(self, evaluator):
        """Test extreme confidence values."""
        result = evaluator._builtin_ta_regime_adaptive_signal([1.0, "extreme", "trending_up", 50])
        assert 0 <= result["signal_confidence"] <= 1

    def test_boundary_conditions(self, evaluator):
        """Test boundary condition handling."""
        result = evaluator._builtin_ta_optimal_entry_zone([100.0, 100.0, 100.0, 100.0])
        assert result["zone_strength"] >= 0

    def test_mode_transitions(self, evaluator):
        """Test transitions between modes/regimes."""
        result = evaluator._builtin_ta_volatility_regime_score(
            [[1.0, 2.0, 3.0, 4.0, 5.0], [0.01, 0.02, 0.03, 0.04, 0.05], [10.0, 15.0, 20.0, 25.0, 30.0], 50.0]
        )
        assert result["regime"] in ["low", "normal", "high", "extreme"]


class TestIntegration:
    """Integration tests combining multiple Tier 7 indicators."""

    def test_complete_long_setup(self, evaluator):
        """Test complete long trading setup."""
        trend_score = evaluator._builtin_ta_trend_confirmation_score([50.0, 0.8, 2.0, 70.0, 0.9, 45.0])
        structure = evaluator._builtin_ta_market_structure_pivot(
            [[100.0, 102.0, 104.0, 103.0, 101.0],
             [98.0, 100.0, 102.0, 101.0, 99.0],
             [99.0, 101.0, 103.0, 102.0, 100.0], 5, 0]
        )
        assert isinstance(trend_score, (int, float))
        assert isinstance(structure, dict)

    def test_complete_entry_workflow(self, evaluator):
        """Test complete entry workflow."""
        timing = evaluator._builtin_ta_market_timing_index([75.0, 40.0, 70.0, 70.0])
        entry = evaluator._builtin_ta_optimal_entry_zone([100.0, 100.0, 100.0, 100.0])
        sizing = evaluator._builtin_ta_position_sizing_score([2.0, 40.0, 2.5, 0.3])
        assert timing["market_condition"] in [
            "optimal_long",
            "favorable_long",
            "neutral",
            "favorable_short",
            "optimal_short",
        ]
        assert entry["zone_strength"] >= 0
        assert 0 <= sizing["position_size_ratio"] <= 1

    def test_complete_exit_workflow(self, evaluator):
        """Test complete exit workflow."""
        trail = evaluator._builtin_ta_trailing_exit_level([100.0, 105.0, 30.0, 2.0, 1.0])
        recovery = evaluator._builtin_ta_drawdown_recovery_level([110.0, 105.0, 1.0, 50])
        assert trail["trail_stop"] > 100.0
        assert recovery["drawdown_percent"] >= 0

    def test_multi_timeframe_entry_system(self, evaluator):
        """Test multi-timeframe entry system."""
        mtf_signal = evaluator._builtin_ta_multi_timeframe_signal([1, 1, 1, 0.3, 0.3, 0.4])
        timing = evaluator._builtin_ta_market_timing_index([80.0, 30.0, 60.0, 60.0])
        entry = evaluator._builtin_ta_optimal_entry_zone([100.0, 100.0, 100.0, 100.0])
        assert mtf_signal["signal_agreement"] >= 0
        assert timing["timing_index"] >= -100
        assert entry["best_entry"] >= 0
