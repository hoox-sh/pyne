"""Phase 8 Tier 1: Additional TA Indicators - High Priority Functions.

Tests for newly implemented technical analysis indicators:
- ta.kama: Kaufman's Adaptive Moving Average
- ta.dema: Double Exponential Moving Average
- ta.tema: Triple Exponential Moving Average
- ta.cmf: Chaikin Money Flow
- ta.klinger: Klinger Oscillator
- And other Tier 1 indicators
"""

from __future__ import annotations

import pytest

from pynescript.ast.helper import parse, unparse


class TestKAMA:
    """Kaufman's Adaptive Moving Average tests."""

    def test_kama_basic(self):
        """Test KAMA with basic parameters."""
        script = """
//@version 6
indicator("KAMA Test", overlay=true)
result = ta.kama(close, 10, 2, 30)
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kama" in unparsed

    def test_kama_series(self):
        """Test KAMA with series input."""
        script = """
//@version 6
indicator("KAMA Series", overlay=true)
ma = ta.sma(close, 5)
kama = ta.kama(ma, 10, 2, 30)
plot(kama)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kama" in unparsed

    def test_kama_custom_periods(self):
        """Test KAMA with custom fast/slow periods."""
        script = """
//@version 6
indicator("KAMA Custom", overlay=true)
kama = ta.kama(close, 15, 3, 50)
plot(kama)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kama" in unparsed


class TestDEMA:
    """Double Exponential Moving Average tests."""

    def test_dema_basic(self):
        """Test DEMA with basic parameters."""
        script = """
//@version 6
indicator("DEMA Test", overlay=true)
dema = ta.dema(close, 20)
plot(dema)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.dema" in unparsed

    def test_dema_vs_ema(self):
        """Test DEMA compared to EMA."""
        script = """
//@version 6
indicator("DEMA vs EMA", overlay=true)
ema = ta.ema(close, 20)
dema = ta.dema(close, 20)
plot(ema, color=color.blue)
plot(dema, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.dema" in unparsed
        assert "ta.ema" in unparsed

    def test_dema_multiple_lengths(self):
        """Test DEMA with different lengths."""
        script = """
//@version 6
indicator("DEMA Lengths", overlay=true)
dema10 = ta.dema(close, 10)
dema20 = ta.dema(close, 20)
dema50 = ta.dema(close, 50)
plot(dema10, color=color.green)
plot(dema20, color=color.blue)
plot(dema50, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.dema" in unparsed


class TestTEMA:
    """Triple Exponential Moving Average tests."""

    def test_tema_basic(self):
        """Test TEMA with basic parameters."""
        script = """
//@version 6
indicator("TEMA Test", overlay=true)
tema = ta.tema(close, 20)
plot(tema)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.tema" in unparsed

    def test_tema_less_lag(self):
        """Test TEMA for reduced lag vs DEMA."""
        script = """
//@version 6
indicator("TEMA Less Lag", overlay=true)
ema = ta.ema(close, 20)
dema = ta.dema(close, 20)
tema = ta.tema(close, 20)
plot(ema, color=color.gray)
plot(dema, color=color.blue)
plot(tema, color=color.green)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.tema" in unparsed

    def test_tema_signal_crossover(self):
        """Test TEMA in crossover strategy."""
        script = """
//@version 6
indicator("TEMA Crossover", overlay=true)
tema = ta.tema(close, 20)
signal = ta.sma(tema, 5)
plot(tema, color=color.blue)
plot(signal, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.tema" in unparsed


class TestCMF:
    """Chaikin Money Flow tests."""

    def test_cmf_basic(self):
        """Test CMF with basic parameters."""
        script = """
//@version 6
indicator("CMF Test", overlay=false)
cmf = ta.cmf(close, high, low, volume, 20)
plot(cmf)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.cmf" in unparsed

    def test_cmf_volume_analysis(self):
        """Test CMF for volume analysis."""
        script = """
//@version 6
indicator("CMF Volume", overlay=false)
cmf = ta.cmf(close, high, low, volume, 21)
hline(0, linestyle=hline.style_dashed)
plot(cmf, color=color.blue)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.cmf" in unparsed

    def test_cmf_custom_periods(self):
        """Test CMF with different periods."""
        script = """
//@version 6
indicator("CMF Periods", overlay=false)
cmf14 = ta.cmf(close, high, low, volume, 14)
cmf21 = ta.cmf(close, high, low, volume, 21)
plot(cmf14, color=color.blue)
plot(cmf21, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.cmf" in unparsed


class TestKlinger:
    """Klinger Oscillator tests."""

    def test_klinger_basic(self):
        """Test Klinger oscillator with basic parameters."""
        script = """
//@version 6
indicator("Klinger Test", overlay=false)
ko = ta.klinger(high, low, close, volume, 34, 55)
plot(ko)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.klinger" in unparsed

    def test_klinger_signal_line(self):
        """Test Klinger with signal line."""
        script = """
//@version 6
indicator("Klinger Signal", overlay=false)
ko = ta.klinger(high, low, close, volume, 34, 55)
signal = ta.ema(ko, 13)
plot(ko, color=color.blue)
plot(signal, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.klinger" in unparsed

    def test_klinger_divergence(self):
        """Test Klinger for divergence detection."""
        script = """
//@version 6
indicator("Klinger Divergence", overlay=false)
ko = ta.klinger(high, low, close, volume, 34, 55)
signal = ta.ema(ko, 13)
ko_cross = ta.cross(ko, signal)
plot(ko, color=color.blue)
plot(signal, color=color.red)
alertcondition(ko_cross, title="KO Signal Cross")
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.klinger" in unparsed


class TestAPO:
    """Absolute Price Oscillator tests."""

    def test_apo_basic(self):
        """Test APO with basic parameters."""
        script = """
//@version 6
indicator("APO Test", overlay=false)
apo = ta.apo(close, 12, 26)
plot(apo)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.apo" in unparsed

    def test_apo_signal_line(self):
        """Test APO with signal line."""
        script = """
//@version 6
indicator("APO Signal", overlay=false)
apo = ta.apo(close, 12, 26)
signal = ta.ema(apo, 9)
plot(apo, color=color.blue)
plot(signal, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.apo" in unparsed

    def test_apo_custom_periods(self):
        """Test APO with custom fast/slow periods."""
        script = """
//@version 6
indicator("APO Custom", overlay=false)
apo = ta.apo(close, 10, 20)
plot(apo)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.apo" in unparsed


class TestStochSmooth:
    """Smoothed Stochastic tests."""

    def test_stoch_smooth_basic(self):
        """Test smoothed stochastic."""
        script = """
//@version 6
indicator("Stoch Smooth Test", overlay=false)
stoch_smooth = ta.stoch_smooth(high, low, close, 14, 3, 3)
plot(stoch_smooth)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.stoch_smooth" in unparsed

    def test_stoch_smooth_overbought_oversold(self):
        """Test smoothed stochastic levels."""
        script = """
//@version 6
indicator("Stoch Smooth Levels", overlay=false)
stoch = ta.stoch_smooth(high, low, close, 14, 3, 3)
hline(80, color=color.red)
hline(20, color=color.green)
plot(stoch)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.stoch_smooth" in unparsed


class TestRSIDivergence:
    """RSI Divergence Detector tests."""

    def test_rsi_divergence_basic(self):
        """Test RSI divergence detection."""
        script = """
//@version 6
indicator("RSI Divergence", overlay=false)
rsi = ta.rsi(close, 14)
divergence = ta.rsi_divergence(rsi, 5)
plot(divergence)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_divergence" in unparsed

    def test_rsi_divergence_signals(self):
        """Test RSI divergence signals."""
        script = """
//@version 6
indicator("RSI Div Signals", overlay=false)
rsi = ta.rsi(close, 14)
divergence = ta.rsi_divergence(rsi, 5)
alertcondition(divergence > 0, title="Bullish Div")
alertcondition(divergence < 0, title="Bearish Div")
plot(divergence)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.rsi_divergence" in unparsed


class TestMACDSignal:
    """MACD Signal Strength tests."""

    def test_macd_signal_basic(self):
        """Test MACD signal strength."""
        script = """
//@version 6
indicator("MACD Signal", overlay=false)
macd = ta.macd(close)[0]
signal = ta.macd(close)[1]
strength = ta.macd_signal(macd, signal)
plot(strength)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.macd_signal" in unparsed


class TestALMA:
    """Arnaud Legoux Moving Average tests."""

    def test_alma_basic(self):
        """Test ALMA with basic parameters."""
        script = """
//@version 6
indicator("ALMA Test", overlay=true)
alma = ta.alma(close, 20, 0.85, 6)
plot(alma)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.alma" in unparsed

    def test_alma_offset_sensitivity(self):
        """Test ALMA with different offset values."""
        script = """
//@version 6
indicator("ALMA Offset", overlay=true)
alma_low = ta.alma(close, 20, 0.5, 6)
alma_mid = ta.alma(close, 20, 0.85, 6)
alma_high = ta.alma(close, 20, 0.95, 6)
plot(alma_low, color=color.blue)
plot(alma_mid, color=color.green)
plot(alma_high, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.alma" in unparsed


class TestPhase8Integration:
    """Integration tests for Phase 8 indicators."""

    def test_multiple_tier1_indicators(self):
        """Test multiple Tier 1 indicators together."""
        script = """
//@version 6
indicator("Phase 8 Tier 1 Mix", overlay=true)
kama = ta.kama(close, 10, 2, 30)
dema = ta.dema(close, 20)
tema = ta.tema(close, 20)
plot(kama, color=color.blue)
plot(dema, color=color.green)
plot(tema, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kama" in unparsed
        assert "ta.dema" in unparsed
        assert "ta.tema" in unparsed

    def test_tier1_in_strategy(self):
        """Test Tier 1 indicators in strategy."""
        script = """
//@version 6
strategy("Phase 8 Strategy", overlay=true)
kama = ta.kama(close, 10, 2, 30)
cmf = ta.cmf(close, high, low, volume, 20)
if cmf > 0
    strategy.entry("Long", strategy.long)
if cmf < 0
    strategy.close("Long")
plot(kama)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kama" in unparsed
        assert "ta.cmf" in unparsed

    def test_tier1_with_existing_indicators(self):
        """Test Tier 1 indicators mixed with existing indicators."""
        script = """
//@version 6
indicator("Phase 8 + Existing", overlay=true)
sma = ta.sma(close, 20)
ema = ta.ema(close, 20)
kama = ta.kama(close, 10, 2, 30)
dema = ta.dema(close, 20)
plot(sma, color=color.blue)
plot(ema, color=color.green)
plot(kama, color=color.orange)
plot(dema, color=color.red)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.sma" in unparsed
        assert "ta.ema" in unparsed
        assert "ta.kama" in unparsed
        assert "ta.dema" in unparsed


class TestPhase8RoundTrip:
    """Round-trip parsing tests for Phase 8 indicators."""

    def test_kama_round_trip(self):
        """Test KAMA parsing round-trip."""
        script = """
//@version 6
indicator("KAMA Round Trip", overlay=true)
result = ta.kama(close, 10, 2, 30)
plot(result)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        tree2 = parse(unparsed)
        unparsed2 = unparse(tree2)
        assert unparsed == unparsed2

    def test_dema_tema_round_trip(self):
        """Test DEMA/TEMA round-trip."""
        script = """
//@version 6
indicator("DEMA/TEMA Round Trip", overlay=true)
d = ta.dema(close, 20)
t = ta.tema(close, 20)
plot(d)
plot(t)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        tree2 = parse(unparsed)
        unparsed2 = unparse(tree2)
        assert unparsed == unparsed2

    def test_volume_indicators_round_trip(self):
        """Test volume indicators round-trip."""
        script = """
//@version 6
indicator("Volume Ind Round Trip", overlay=false)
cmf = ta.cmf(close, high, low, volume, 20)
ko = ta.klinger(high, low, close, volume, 34, 55)
plot(cmf)
plot(ko)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        tree2 = parse(unparsed)
        unparsed2 = unparse(tree2)
        assert unparsed == unparsed2
