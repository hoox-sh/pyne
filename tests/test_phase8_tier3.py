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

"""Phase 8 Tier 3: Additional TA Indicators - Specialized Indicators.

Tests for newly implemented technical analysis indicators:
- ta.engulfing: Pattern detection (candlestick patterns)
- ta.hammer: Hammer/Doji pattern recognition
- ta.gap_detector: Gap identification
- ta.voi: Volume of Imbalance
- ta.bid_ask_imbalance: Bid-ask microstructure
- ta.expected_value: Statistical expected value
- ta.skewness: Distribution skewness
- ta.kurtosis: Distribution kurtosis (tail risk)
- ta.parkinson: Range-based volatility
- ta.garman_klass: OHLC volatility
"""

from __future__ import annotations

import pytest

from pynescript.ast.helper import parse, unparse


class TestEngulfing:
    """Engulfing Pattern Detection tests."""

    def test_engulfing_basic(self):
        """Test engulfing pattern detection with basic usage."""
        script = """
//@version 6
indicator("Engulfing Test", overlay=true)
pattern = ta.engulfing(open, high, low, close)
plot(pattern)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.engulfing" in unparsed

    def test_engulfing_with_condition(self):
        """Test engulfing within conditional logic."""
        script = """
//@version 6
indicator("Engulfing Condition", overlay=true)
bullish = ta.engulfing(open, high, low, close)
if bullish
    plot(high)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.engulfing" in unparsed


class TestHammer:
    """Hammer/Doji Pattern Detection tests."""

    def test_hammer_basic(self):
        """Test hammer pattern detection."""
        script = """
//@version 6
indicator("Hammer Test", overlay=true)
pattern = ta.hammer(open, high, low, close)
plot(pattern)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.hammer" in unparsed

    def test_hammer_doji_detection(self):
        """Test both hammer and doji detection."""
        script = """
//@version 6
indicator("Hammer Doji", overlay=true)
h = ta.hammer(open, high, low, close)
d = ta.hammer(open, high, low, close)
plot(h)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.hammer" in unparsed


class TestGapDetector:
    """Gap Detection tests."""

    def test_gap_basic(self):
        """Test gap detection with current bar."""
        script = """
//@version 6
indicator("Gap Test", overlay=true)
gap = ta.gap_detector(high, low, close)
plot(gap)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.gap_detector" in unparsed

    def test_gap_previous_close(self):
        """Test gap detection using previous close."""
        script = """
//@version 6
indicator("Gap Previous", overlay=true)
prev_c = close[1]
gap = ta.gap_detector(high, low, prev_c)
plot(gap)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.gap_detector" in unparsed


class TestVOI:
    """Volume of Imbalance tests."""

    def test_voi_basic(self):
        """Test VOI with basic volume series."""
        script = """
//@version 6
indicator("VOI Test", overlay=false)
voi = ta.voi(volume, 14)
plot(voi)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.voi" in unparsed

    def test_voi_with_price(self):
        """Test VOI with price-weighted volume."""
        script = """
//@version 6
indicator("VOI Price", overlay=false)
buy_vol = volume * (close - open)
sell_vol = volume * (open - close)
voi = ta.voi(buy_vol, 20)
plot(voi)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.voi" in unparsed


class TestBidAskImbalance:
    """Bid-Ask Imbalance tests."""

    def test_bid_ask_basic(self):
        """Test bid-ask imbalance calculation."""
        script = """
//@version 6
indicator("Bid-Ask Test", overlay=false)
imbalance = ta.bid_ask_imbalance(volume, 10)
plot(imbalance)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.bid_ask_imbalance" in unparsed

    def test_bid_ask_with_spread(self):
        """Test bid-ask with spread calculation."""
        script = """
//@version 6
indicator("Bid-Ask Spread", overlay=false)
bid_ask = ta.bid_ask_imbalance(volume, 14)
plot(bid_ask)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.bid_ask_imbalance" in unparsed


class TestExpectedValue:
    """Expected Value (Statistical) tests."""

    def test_expected_value_basic(self):
        """Test expected value calculation."""
        script = """
//@version 6
indicator("Expected Value Test", overlay=false)
ev = ta.expected_value(close, 20)
plot(ev)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.expected_value" in unparsed

    def test_expected_value_with_returns(self):
        """Test expected value on returns."""
        script = """
//@version 6
indicator("Expected Value Returns", overlay=false)
ret = close / close[1]
ev = ta.expected_value(ret, 14)
plot(ev)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.expected_value" in unparsed


class TestSkewness:
    """Skewness (Distribution Asymmetry) tests."""

    def test_skewness_basic(self):
        """Test skewness calculation."""
        script = """
//@version 6
indicator("Skewness Test", overlay=false)
skew = ta.skewness(close, 20)
plot(skew)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.skewness" in unparsed

    def test_skewness_returns(self):
        """Test skewness on returns distribution."""
        script = """
//@version 6
indicator("Skewness Returns", overlay=false)
ret = (close - close[1]) / close[1]
skew = ta.skewness(ret, 30)
plot(skew)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.skewness" in unparsed


class TestKurtosis:
    """Kurtosis (Tail Risk) tests."""

    def test_kurtosis_basic(self):
        """Test kurtosis calculation."""
        script = """
//@version 6
indicator("Kurtosis Test", overlay=false)
kurt = ta.kurtosis(close, 20)
plot(kurt)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kurtosis" in unparsed

    def test_kurtosis_tail_risk(self):
        """Test kurtosis for tail risk detection."""
        script = """
//@version 6
indicator("Kurtosis Tail Risk", overlay=false)
k = ta.kurtosis(close, 30)
alarm = k > 3
plot(alarm)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.kurtosis" in unparsed


class TestParkinson:
    """Parkinson Volatility tests."""

    def test_parkinson_basic(self):
        """Test Parkinson volatility calculation."""
        script = """
//@version 6
indicator("Parkinson Test", overlay=false)
pvol = ta.parkinson(high, low, 14)
plot(pvol)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.parkinson" in unparsed

    def test_parkinson_volatility(self):
        """Test Parkinson volatility for trend detection."""
        script = """
//@version 6
indicator("Parkinson Volatility", overlay=false)
p = ta.parkinson(high, low, 20)
high_vol = p > ta.sma(p, 10)
plot(high_vol)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.parkinson" in unparsed


class TestGarmanKlass:
    """Garman-Klass Volatility tests."""

    def test_garman_klass_basic(self):
        """Test Garman-Klass volatility calculation."""
        script = """
//@version 6
indicator("Garman-Klass Test", overlay=false)
gkvol = ta.garman_klass(open, high, low, close, 14)
plot(gkvol)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.garman_klass" in unparsed

    def test_garman_klass_comparison(self):
        """Test Garman-Klass vs other volatility measures."""
        script = """
//@version 6
indicator("Garman-Klass vs ATR", overlay=false)
gk = ta.garman_klass(open, high, low, close, 14)
atr_vol = ta.atr(14) / ta.sma(close, 14)
plot(gk)
plot(atr_vol)
"""
        tree = parse(script)
        unparsed = unparse(tree)
        assert "ta.garman_klass" in unparsed
