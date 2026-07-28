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

"""
TA Indicators - Tier 8: Final Capstone Indicator - Intelligent Strategy Synthesizer

Comprehensive test suite for ta.intelligent_strategy_synthesizer - the final indicator
synthesizing all 146 previous indicators into adaptive, context-aware trading signals.

Total: 24 comprehensive tests across 6 test classes
"""

from __future__ import annotations

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


@pytest.fixture
def evaluator():
    """Create evaluator for builtin tests."""
    return NodeLiteralEvaluator()


# ============================================================================
# Test Group 1: Signal Aggregation (4 tests)
# ============================================================================

class TestSignalAggregation:
    """Tests for signal aggregation logic."""

    def test_strong_bullish_aggregation(self, evaluator):
        """Test strong bullish signal aggregation."""
        trend = [0.9, 0.8, 0.85]
        momentum = [0.8, 0.85, 0.9]
        volatility = [0.5, 0.5, 0.5]
        volume = [0.7, 0.75, 0.8]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "balanced"]
        )
        assert isinstance(result, dict)
        assert result["composite_signal"] > 0.6
        assert result["confidence_level"] > 0.7

    def test_strong_bearish_aggregation(self, evaluator):
        """Test strong bearish signal aggregation."""
        trend = [-0.9, -0.8, -0.85]
        momentum = [-0.8, -0.85, -0.9]
        volatility = [0.5, 0.5, 0.5]
        volume = [-0.7, -0.75, -0.8]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_down", "balanced"]
        )
        assert isinstance(result["composite_signal"], float)
        assert result["composite_signal"] < -0.6

    def test_mixed_signals_partial_agreement(self, evaluator):
        """Test mixed signals with partial agreement."""
        trend = [0.5, 0.6, 0.55]
        momentum = [-0.3, -0.2, -0.25]
        volatility = [0.4, 0.45, 0.42]
        volume = [0.1, 0.15, 0.12]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "ranging", "balanced"]
        )
        assert -1.0 <= result["composite_signal"] <= 1.0
        assert 0 <= result["confidence_level"] <= 1.0

    def test_extreme_signal_values(self, evaluator):
        """Test extreme signal values."""
        trend = [1.0, 1.0, 1.0]
        momentum = [1.0, 1.0, 1.0]
        volatility = [1.0, 1.0, 1.0]
        volume = [1.0, 1.0, 1.0]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "aggressive"]
        )
        assert -1.0 <= result["composite_signal"] <= 1.0
        assert 0 <= result["confidence_level"] <= 1.0


# ============================================================================
# Test Group 2: Market Context Analysis (4 tests)
# ============================================================================

class TestMarketContextAnalysis:
    """Tests for market context analysis."""

    def test_trending_market_condition(self, evaluator):
        """Test trending market condition."""
        trend = [0.8, 0.85, 0.9]
        momentum = [0.7, 0.75, 0.8]
        volatility = [0.3, 0.3, 0.3]
        volume = [0.6, 0.65, 0.7]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "balanced"]
        )
        assert result["regime_alignment"] >= 75.0

    def test_ranging_market_condition(self, evaluator):
        """Test ranging market condition."""
        trend = [0.2, -0.1, 0.15]
        momentum = [0.3, -0.2, 0.25]
        volatility = [0.6, 0.65, 0.6]
        volume = [0.1, 0.0, 0.05]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "ranging", "conservative"]
        )
        assert isinstance(result["regime_alignment"], float)
        assert 0 <= result["regime_alignment"] <= 100.0

    def test_volatile_market_condition(self, evaluator):
        """Test volatile market condition."""
        trend = [0.5, -0.4, 0.6]
        momentum = [0.4, -0.5, 0.7]
        volatility = [0.9, 0.95, 0.92]
        volume = [0.8, -0.7, 0.75]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "volatile", "conservative"]
        )
        assert result["risk_level"] > 15.0

    def test_dead_market_condition(self, evaluator):
        """Test dead/sideways market condition."""
        trend = [0.0, 0.05, -0.02]
        momentum = [0.0, 0.0, 0.0]
        volatility = [0.1, 0.12, 0.11]
        volume = [0.0, 0.02, -0.01]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "dead", "balanced"]
        )
        assert result["strategy_recommendation"] in [
            "hold",
            "conservative_long",
            "conservative_short",
        ]


# ============================================================================
# Test Group 3: Risk Profile Adaptation (4 tests)
# ============================================================================

class TestRiskProfileAdaptation:
    """Tests for risk profile adaptation."""

    def test_conservative_risk_profile(self, evaluator):
        """Test conservative risk profile adaptation."""
        trend = [0.7, 0.75, 0.8]
        momentum = [0.6, 0.65, 0.7]
        volatility = [0.4, 0.4, 0.4]
        volume = [0.5, 0.55, 0.6]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "conservative"]
        )
        assert result["risk_level"] < 30.0
        assert result["stop_loss_priority"] <= -0.2

    def test_balanced_risk_profile(self, evaluator):
        """Test balanced risk profile adaptation."""
        trend = [0.7, 0.75, 0.8]
        momentum = [0.6, 0.65, 0.7]
        volatility = [0.4, 0.4, 0.4]
        volume = [0.5, 0.55, 0.6]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "balanced"]
        )
        assert 20.0 < result["risk_level"] < 50.0
        assert result["take_profit_priority"] > 0.5

    def test_aggressive_risk_profile(self, evaluator):
        """Test aggressive risk profile adaptation."""
        trend = [0.7, 0.75, 0.8]
        momentum = [0.6, 0.65, 0.7]
        volatility = [0.4, 0.4, 0.4]
        volume = [0.5, 0.55, 0.6]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "aggressive"]
        )
        assert result["risk_level"] > 15.0
        assert result["take_profit_priority"] > 1.0

    def test_extreme_risk_inputs(self, evaluator):
        """Test extreme risk profile inputs."""
        trend = [1.0, 1.0, 1.0]
        momentum = [1.0, 1.0, 1.0]
        volatility = [0.0, 0.0, 0.0]
        volume = [1.0, 1.0, 1.0]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "aggressive"]
        )
        assert 0 <= result["risk_level"] <= 100.0
        assert 0 <= result["confidence_level"] <= 1.0


# ============================================================================
# Test Group 4: Confidence Scoring (4 tests)
# ============================================================================

class TestConfidenceScoring:
    """Tests for confidence scoring logic."""

    def test_high_confidence_aligned_signals(self, evaluator):
        """Test high confidence with aligned signals."""
        trend = [0.9, 0.85, 0.9]
        momentum = [0.85, 0.9, 0.85]
        volatility = [0.5, 0.5, 0.5]
        volume = [0.8, 0.85, 0.8]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "balanced"]
        )
        assert result["confidence_level"] > 0.75

    def test_low_confidence_divergent_signals(self, evaluator):
        """Test low confidence with divergent signals."""
        trend = [0.8, -0.7, 0.6]
        momentum = [-0.6, 0.7, -0.5]
        volatility = [0.9, 0.85, 0.95]
        volume = [0.5, -0.6, 0.4]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "volatile", "balanced"]
        )
        assert result["confidence_level"] < 0.65

    def test_partial_confidence_mixed_alignment(self, evaluator):
        """Test partial confidence with mixed alignment."""
        trend = [0.6, 0.55, 0.58]
        momentum = [0.4, 0.35, 0.38]
        volatility = [0.5, 0.52, 0.48]
        volume = [0.2, 0.15, 0.18]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "ranging", "balanced"]
        )
        assert 0.3 < result["confidence_level"] < 0.7

    def test_confidence_with_extreme_volatility(self, evaluator):
        """Test confidence scoring with extreme volatility."""
        trend = [0.5, 0.5, 0.5]
        momentum = [0.5, 0.5, 0.5]
        volatility = [0.95, 0.98, 0.96]
        volume = [0.5, 0.5, 0.5]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "volatile", "aggressive"]
        )
        assert 0 <= result["confidence_level"] <= 1.0


# ============================================================================
# Test Group 5: Edge Cases (4 tests)
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_indicator_lists(self, evaluator):
        """Test handling of empty indicator lists."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[], [], [], [], "ranging", "balanced"]
        )
        assert isinstance(result, dict)
        assert "composite_signal" in result

    def test_single_indicator_per_category(self, evaluator):
        """Test single value per category."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[0.5], [0.6], [0.4], [0.5], "trending_up", "balanced"]
        )
        assert isinstance(result, dict)
        assert -1.0 <= result["composite_signal"] <= 1.0

    def test_extreme_values_zero(self, evaluator):
        """Test with all zero values."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
             [0.0, 0.0, 0.0], "ranging", "balanced"]
        )
        assert result["composite_signal"] == 0.0
        assert result["strategy_recommendation"] == "hold"

    def test_extreme_values_boundaries(self, evaluator):
        """Test with boundary values (-1, 0, 1)."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[1.0, 0.0, -1.0], [1.0, 0.0, -1.0],
             [1.0, 0.0, -1.0], [1.0, 0.0, -1.0],
             "volatile", "conservative"]
        )
        assert -1.0 <= result["composite_signal"] <= 1.0
        assert isinstance(result["strategy_recommendation"], str)


# ============================================================================
# Test Group 6: Integration (4 tests)
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_bullish_trading_workflow(self, evaluator):
        """Test complete bullish trading workflow."""
        trend = [0.75, 0.8, 0.85]
        momentum = [0.7, 0.75, 0.8]
        volatility = [0.3, 0.3, 0.35]
        volume = [0.65, 0.7, 0.75]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_up", "balanced"]
        )

        assert result["composite_signal"] > 0.5
        assert result["confidence_level"] > 0.6
        assert "long" in result["strategy_recommendation"]
        assert result["stop_loss_priority"] < 0
        assert result["take_profit_priority"] > 0.5

    def test_complete_bearish_trading_workflow(self, evaluator):
        """Test complete bearish trading workflow."""
        trend = [-0.75, -0.8, -0.85]
        momentum = [-0.7, -0.75, -0.8]
        volatility = [0.3, 0.3, 0.35]
        volume = [-0.65, -0.7, -0.75]
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "trending_down", "balanced"]
        )

        assert result["composite_signal"] < -0.5
        assert result["confidence_level"] > 0.6
        assert "short" in result["strategy_recommendation"]

    def test_risk_management_integration(self, evaluator):
        """Test risk management across all profiles."""
        trend = [0.5, 0.55, 0.6]
        momentum = [0.4, 0.45, 0.5]
        volatility = [0.6, 0.65, 0.6]
        volume = [0.3, 0.35, 0.3]

        conservative = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "ranging", "conservative"]
        )
        aggressive = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "ranging", "aggressive"]
        )

        assert conservative["risk_level"] < aggressive["risk_level"]

    def test_multi_condition_scenario(self, evaluator):
        """Test multi-condition complex scenario."""
        trend = [0.6, -0.3, 0.5]
        momentum = [0.5, -0.4, 0.45]
        volatility = [0.8, 0.85, 0.82]
        volume = [0.4, -0.2, 0.35]

        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [trend, momentum, volatility, volume, "volatile", "conservative"]
        )

        assert isinstance(result, dict)
        assert all(
            key in result for key in [
                "composite_signal",
                "confidence_level",
                "strategy_recommendation",
                "risk_level",
                "expected_return",
                "holding_period",
                "stop_loss_priority",
                "take_profit_priority",
                "regime_alignment",
            ]
        )


# ============================================================================
# Comprehensive Validation
# ============================================================================

class TestOutputFormat:
    """Validate output format and all required fields."""

    def test_complete_output_dict_structure(self, evaluator):
        """Test that complete dict structure is returned."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[0.5], [0.5], [0.5], [0.5], "ranging", "balanced"]
        )

        required_fields = [
            "composite_signal",
            "confidence_level",
            "strategy_recommendation",
            "risk_level",
            "expected_return",
            "holding_period",
            "stop_loss_priority",
            "take_profit_priority",
            "regime_alignment",
        ]

        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_output_value_ranges(self, evaluator):
        """Test that all output values are within expected ranges."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[0.7], [0.6], [0.5], [0.65], "trending_up", "balanced"]
        )

        assert -1.0 <= result["composite_signal"] <= 1.0
        assert 0 <= result["confidence_level"] <= 1.0
        assert 0 <= result["risk_level"] <= 100.0
        assert -1.0 <= result["stop_loss_priority"] <= 0
        assert 0.5 <= result["take_profit_priority"] <= 2.0
        assert 0 <= result["regime_alignment"] <= 100.0

    def test_strategy_recommendation_values(self, evaluator):
        """Test valid strategy recommendation values."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[0.5], [0.5], [0.5], [0.5], "ranging", "balanced"]
        )

        valid_recommendations = [
            "aggressive_long",
            "conservative_long",
            "hold",
            "conservative_short",
            "aggressive_short",
        ]

        assert result["strategy_recommendation"] in valid_recommendations

    def test_holding_period_values(self, evaluator):
        """Test valid holding period values."""
        result = evaluator._builtin_ta_intelligent_strategy_synthesizer(
            [[0.5], [0.5], [0.5], [0.5], "ranging", "balanced"]
        )

        valid_periods = ["scalp", "day_trade", "swing", "position"]

        assert result["holding_period"] in valid_periods
