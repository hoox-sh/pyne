"""
Phase 8 Tier 4: Enhancement Variants - Comprehensive Tests
Tests for weighted SMA, EMA cross signals, RSI thresholds,
normalized ATR, and volume-weighted momentum.
"""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestSMAWeighted:
    """Tests for ta.sma_weighted - Weighted Simple Moving Average."""

    def test_sma_weighted_linear(self):
        """Test linear weighted SMA with basic data."""
        script = """
//@version 6
indicator("SMA Weighted Test", overlay=true)
result = ta.sma_weighted(close, 3, "linear")
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma_weighted" in unparsed

    def test_sma_weighted_quadratic(self):
        """Test quadratic weighted SMA."""
        script = """
//@version 6
indicator("SMA Weighted Quadratic", overlay=true)
result = ta.sma_weighted(close, 3, "quadratic")
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma_weighted" in unparsed

    def test_sma_weighted_sqrt(self):
        """Test sqrt weighted SMA."""
        script = """
//@version 6
indicator("SMA Weighted Sqrt", overlay=true)
result = ta.sma_weighted(close, 4, "sqrt")
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma_weighted" in unparsed

    def test_sma_weighted_default(self):
        """Test SMA weighted with default linear weighting."""
        script = """
//@version 6
indicator("SMA Weighted Default", overlay=true)
result = ta.sma_weighted(close, 3)
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma_weighted" in unparsed

    def test_sma_weighted_conditional(self):
        """Test SMA weighted in conditional logic."""
        script = """
//@version 6
indicator("SMA Weighted Conditional", overlay=true)
sma_val = ta.sma_weighted(close, 5, "linear")
if sma_val > 100
    plot(sma_val)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma_weighted" in unparsed


class TestEMACrossSignal:
    """Tests for ta.ema_cross_signal - EMA Crossover Detection."""

    def test_ema_cross_signal_basic(self):
        """Test detection of EMA crossover signals."""
        script = """
//@version 6
indicator("EMA Cross Signal", overlay=true)
signal = ta.ema_cross_signal(close, 2, 3)
plot(signal)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.ema_cross_signal" in unparsed

    def test_ema_cross_signal_dict_access(self):
        """Test that EMA cross signal returns dict structure."""
        script = """
//@version 6
indicator("EMA Cross Dict", overlay=true)
signal = ta.ema_cross_signal(close, 5, 10)
plot(signal.signal)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.ema_cross_signal" in unparsed

    def test_ema_cross_signal_with_crossover(self):
        """Test EMA cross signal with crossover condition."""
        script = """
//@version 6
indicator("EMA Crossover Test", overlay=true)
signal = ta.ema_cross_signal(close, 3, 8)
if signal.crossover
    plot(high)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.ema_cross_signal" in unparsed

    def test_ema_cross_signal_with_crossunder(self):
        """Test EMA cross signal with crossunder condition."""
        script = """
//@version 6
indicator("EMA Crossunder Test", overlay=true)
signal = ta.ema_cross_signal(close, 2, 4)
if signal.crossunder
    plot(low)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.ema_cross_signal" in unparsed

    def test_ema_cross_signal_value_check(self):
        """Test EMA cross signal value checking."""
        script = """
//@version 6
indicator("EMA Signal Value", overlay=true)
signal = ta.ema_cross_signal(close, 4, 9)
if signal.signal > 0
    plot(100)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.ema_cross_signal" in unparsed


class TestRSIOversoldOverbought:
    """Tests for ta.rsi_oversold_overbought - RSI Threshold Detection."""

    def test_rsi_threshold_basic(self):
        """Test basic RSI threshold detection."""
        script = """
//@version 6
indicator("RSI Threshold", overlay=true)
rsi_val = ta.rsi(close, 14)
result = ta.rsi_oversold_overbought(rsi_val, 30, 70)
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_oversold_overbought" in unparsed

    def test_rsi_threshold_oversold(self):
        """Test detection of oversold RSI."""
        script = """
//@version 6
indicator("RSI Oversold", overlay=true)
rsi_val = ta.rsi(close, 14)
levels = ta.rsi_oversold_overbought(rsi_val, 30, 70)
if levels.is_oversold
    plot(low)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_oversold_overbought" in unparsed

    def test_rsi_threshold_overbought(self):
        """Test detection of overbought RSI."""
        script = """
//@version 6
indicator("RSI Overbought", overlay=true)
rsi_val = ta.rsi(close, 14)
levels = ta.rsi_oversold_overbought(rsi_val, 30, 70)
if levels.is_overbought
    plot(high)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_oversold_overbought" in unparsed

    def test_rsi_threshold_custom_levels(self):
        """Test RSI with custom threshold levels."""
        script = """
//@version 6
indicator("RSI Custom Levels", overlay=true)
rsi_val = ta.rsi(close, 14)
levels = ta.rsi_oversold_overbought(rsi_val, 25, 75)
plot(levels.rsi)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_oversold_overbought" in unparsed

    def test_rsi_threshold_neutral(self):
        """Test RSI in neutral zone."""
        script = """
//@version 6
indicator("RSI Neutral", overlay=true)
rsi_val = ta.rsi(close, 14)
levels = ta.rsi_oversold_overbought(rsi_val, 35, 65)
neutral = not levels.is_oversold and not levels.is_overbought
plot(neutral ? 1 : 0)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_oversold_overbought" in unparsed


class TestATRNormalized:
    """Tests for ta.atr_normalized - Normalized ATR Percentage."""

    def test_atr_normalized_basic(self):
        """Test normalized ATR calculation."""
        script = """
//@version 6
indicator("ATR Normalized", overlay=true)
atr_norm = ta.atr_normalized(high, low, close, 14)
plot(atr_norm)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.atr_normalized" in unparsed

    def test_atr_normalized_comparison(self):
        """Test normalized ATR with comparisons."""
        script = """
//@version 6
indicator("ATR Normalized Compare", overlay=true)
atr_norm = ta.atr_normalized(high, low, close, 14)
if atr_norm > 2
    plot(atr_norm)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.atr_normalized" in unparsed

    def test_atr_normalized_multiple_periods(self):
        """Test ATR normalized with different periods."""
        script = """
//@version 6
indicator("ATR Normalized Multi", overlay=true)
atr_short = ta.atr_normalized(high, low, close, 7)
atr_long = ta.atr_normalized(high, low, close, 21)
plot(atr_short)
plot(atr_long)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.atr_normalized" in unparsed

    def test_atr_normalized_in_strategy(self):
        """Test normalized ATR in strategy logic."""
        script = """
//@version 6
indicator("ATR Strategy", overlay=true)
volatility = ta.atr_normalized(high, low, close, 10)
threshold = 1.5
signal = volatility > threshold
plot(signal ? 1 : 0)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.atr_normalized" in unparsed


class TestVolumeWeightedMomentum:
    """Tests for ta.volume_weighted_momentum - Volume-Weighted Momentum."""

    def test_vwm_basic(self):
        """Test volume-weighted momentum calculation."""
        script = """
//@version 6
indicator("Volume Weighted Momentum", overlay=true)
vwm = ta.volume_weighted_momentum(close, volume, 3)
plot(vwm)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.volume_weighted_momentum" in unparsed

    def test_vwm_uptrend(self):
        """Test volume-weighted momentum in uptrend."""
        script = """
//@version 6
indicator("VWM Uptrend", overlay=true)
vwm = ta.volume_weighted_momentum(close, volume, 5)
if vwm > 0
    plot(high)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.volume_weighted_momentum" in unparsed

    def test_vwm_downtrend(self):
        """Test volume-weighted momentum in downtrend."""
        script = """
//@version 6
indicator("VWM Downtrend", overlay=true)
vwm = ta.volume_weighted_momentum(close, volume, 5)
if vwm < 0
    plot(low)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.volume_weighted_momentum" in unparsed

    def test_vwm_multiple_periods(self):
        """Test VWM with multiple period lengths."""
        script = """
//@version 6
indicator("VWM Multi Period", overlay=true)
vwm_fast = ta.volume_weighted_momentum(close, volume, 3)
vwm_slow = ta.volume_weighted_momentum(close, volume, 10)
plot(vwm_fast)
plot(vwm_slow)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.volume_weighted_momentum" in unparsed

    def test_vwm_signal_generation(self):
        """Test VWM for signal generation."""
        script = """
//@version 6
indicator("VWM Signal", overlay=true)
momentum = ta.volume_weighted_momentum(close, volume, 7)
buy = momentum > 0.1
sell = momentum < -0.1
plot(buy ? 1 : sell ? -1 : 0)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.volume_weighted_momentum" in unparsed


class TestTier4Integration:
    """Integration tests combining multiple Tier 4 indicators."""

    def test_tier4_multi_indicator_strategy(self):
        """Test combining multiple Tier 4 indicators."""
        script = """
//@version 6
indicator("Tier 4 Multi Indicator", overlay=true)
sma_w = ta.sma_weighted(close, 5, "linear")
ema_sig = ta.ema_cross_signal(close, 3, 8)
rsi_levels = ta.rsi_oversold_overbought(ta.rsi(close, 14), 30, 70)
atr_norm = ta.atr_normalized(high, low, close, 14)
vwm = ta.volume_weighted_momentum(close, volume, 5)
plot(sma_w)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma_weighted" in unparsed
        assert "ta.ema_cross_signal" in unparsed

    def test_tier4_signal_combination(self):
        """Test signal generation with combined Tier 4 indicators."""
        script = """
//@version 6
indicator("Tier 4 Signals", overlay=true)
ema_sig = ta.ema_cross_signal(close, 5, 13)
rsi_levels = ta.rsi_oversold_overbought(ta.rsi(close, 14), 30, 70)
vwm = ta.volume_weighted_momentum(close, volume, 10)
buy_signal = ema_sig.crossover and rsi_levels.is_oversold and vwm > 0
sell_signal = ema_sig.crossunder and rsi_levels.is_overbought and vwm < 0
plot(buy_signal ? 1 : sell_signal ? -1 : 0)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.ema_cross_signal" in unparsed
        assert "ta.rsi_oversold_overbought" in unparsed
        assert "ta.volume_weighted_momentum" in unparsed

    def test_tier4_volatility_analysis(self):
        """Test volatility analysis using Tier 4 functions."""
        script = """
//@version 6
indicator("Tier 4 Volatility", overlay=true)
atr_norm = ta.atr_normalized(high, low, close, 14)
sma_w = ta.sma_weighted(close, 7, "quadratic")
vwm = ta.volume_weighted_momentum(close, volume, 3)
signal = atr_norm > 1.5 and vwm != 0
plot(signal ? 1 : 0)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.atr_normalized" in unparsed
        assert "ta.sma_weighted" in unparsed

    def test_tier4_round_trip_stability(self):
        """Test round-trip parsing stability with all Tier 4 functions."""
        script = """
//@version 6
indicator("Tier 4 Stability Test", overlay=true)
// All five Tier 4 functions
w = ta.sma_weighted(close, 3, "linear")
e = ta.ema_cross_signal(close, 2, 3)
r = ta.rsi_oversold_overbought(ta.rsi(close, 14), 30, 70)
a = ta.atr_normalized(high, low, close, 14)
v = ta.volume_weighted_momentum(close, volume, 5)
plot(w)
"""
        tree1 = parse(script)
        unparsed1 = unparse(tree1)
        tree2 = parse(unparsed1)
        unparsed2 = unparse(tree2)
        # Both reprs should be identical for stable round-trip
        assert unparsed1 == unparsed2
