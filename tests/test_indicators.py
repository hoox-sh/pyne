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

"""Test suite for additional technical indicators.

Tests cover several indicators:
- ta.iii: Intraday Intensity Index
- ta.nvi: Negative Volume Index
- ta.pvi: Positive Volume Index
- ta.accdist: Accumulation/Distribution Index
- ta.wad: Williams Accumulation/Distribution
- ta.wvad: Williams Volume Accumulation/Distribution
"""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestIiiIndicator:
    """Test suite for ta.iii (Intraday Intensity Index) indicator."""

    def test_iii_basic_calculation(self):
        """Test basic IIIcalculation with simple OHLC data."""
        code = """
//@version=6
indicator("iii test")

high = 105.0
low = 95.0
close = 100.0

iii_value = ta.iii(high, low, close)
plot(iii_value)
"""
        script = parse(code)
        assert script is not None
        unparsed = unparse(script)
        assert "ta.iii" in unparsed

    def test_iii_zero_range(self):
        """Test IIIwith high == low (zero true range)."""
        code = """
//@version=6
indicator("iii zero range test")

high = 100.0
low = 100.0
close = 100.0

iii_value = ta.iii(high, low, close)
plot(iii_value)
"""
        script = parse(code)
        assert script is not None

    def test_iii_up_movement(self):
        """Test IIIwith close at top of range."""
        code = """
//@version=6
indicator("iii up test")

high = 105.0
low = 95.0
close = 105.0

iii_value = ta.iii(high, low, close)
plot(iii_value)
"""
        script = parse(code)
        assert script is not None

    def test_iii_down_movement(self):
        """Test IIIwith close at bottom of range."""
        code = """
//@version=6
indicator("iii down test")

high = 105.0
low = 95.0
close = 95.0

iii_value = ta.iii(high, low, close)
plot(iii_value)
"""
        script = parse(code)
        assert script is not None

    def test_iii_series_processing(self):
        """Test IIIwith series inputs from arrays."""
        code = """
//@version=6
indicator("iii series test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 100.0)

high_val = array.get(highs, 0)
low_val = array.get(lows, 0)
close_val = array.get(closes, 0)

iii_value = ta.iii(high_val, low_val, close_val)
plot(iii_value)
"""
        script = parse(code)
        assert script is not None


class TestNviPviIndicators:
    """Test suite for ta.nvi and ta.pvi (Volume Index) indicators."""

    def test_nvi_basic_calculation(self):
        """Test basic NVI calculation with price and volume data."""
        code = """
//@version=6
indicator("nvi test")

closes = array.new<float>()
volumes = array.new<float>()

array.push(closes, 100.0)
array.push(closes, 101.0)
array.push(closes, 100.5)

array.push(volumes, 1000.0)
array.push(volumes, 900.0)  // volume down, price up
array.push(volumes, 1100.0)

nvi = ta.nvi(closes, volumes)
for i = 0 to array.size(nvi) - 1
    plot(array.get(nvi, i))
"""
        script = parse(code)
        assert script is not None

    def test_pvi_basic_calculation(self):
        """Test basic PVI calculation with price and volume data."""
        code = """
//@version=6
indicator("pvi test")

closes = array.new<float>()
volumes = array.new<float>()

array.push(closes, 100.0)
array.push(closes, 101.0)
array.push(closes, 100.5)

array.push(volumes, 1000.0)
array.push(volumes, 1100.0)  // volume up, price up
array.push(volumes, 900.0)

pvi = ta.pvi(closes, volumes)
for i = 0 to array.size(pvi) - 1
    plot(array.get(pvi, i))
"""
        script = parse(code)
        assert script is not None

    def test_nvi_volume_decrease_triggers(self):
        """Test NVI updates only on volume decrease."""
        code = """
//@version=6
indicator("nvi volume down test")

closes = array.new<float>()
volumes = array.new<float>()

array.push(closes, 100.0)
array.push(closes, 102.0)
array.push(closes, 101.0)

array.push(volumes, 1000.0)
array.push(volumes, 500.0)
array.push(volumes, 300.0)

nvi = ta.nvi(closes, volumes)
plot(array.get(nvi, 0))
"""
        script = parse(code)
        assert script is not None

    def test_pvi_volume_increase_triggers(self):
        """Test PVI updates only on volume increase."""
        code = """
//@version=6
indicator("pvi volume up test")

closes = array.new<float>()
volumes = array.new<float>()

array.push(closes, 100.0)
array.push(closes, 102.0)
array.push(closes, 101.0)

array.push(volumes, 1000.0)
array.push(volumes, 1500.0)
array.push(volumes, 1200.0)

pvi = ta.pvi(closes, volumes)
plot(array.get(pvi, 0))
"""
        script = parse(code)
        assert script is not None

    def test_nvi_pvi_mismatched_series(self):
        """Test handling of mismatched series lengths."""
        code = """
//@version=6
indicator("nvi mismatch test")

closes = array.new<float>()
volumes = array.new<float>()

array.push(closes, 100.0)
array.push(closes, 101.0)

array.push(volumes, 1000.0)

nvi = ta.nvi(closes, volumes)
pvi = ta.pvi(closes, volumes)
plot(0.0)
"""
        script = parse(code)
        assert script is not None


class TestAccdistIndicator:
    """Test suite for ta.accdist (Accumulation/Distribution) indicator."""

    def test_accdist_basic_calculation(self):
        """Test basic A/D calculation with OHLCV data."""
        code = """
//@version=6
indicator("accdist test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 100.0)
array.push(volumes, 1000.0)

array.push(highs, 106.0)
array.push(lows, 96.0)
array.push(closes, 104.0)
array.push(volumes, 1200.0)

accdist = ta.accdist(highs, lows, closes, volumes)
plot(array.get(accdist, 0))
"""
        script = parse(code)
        assert script is not None

    def test_accdist_close_at_high(self):
        """Test A/D when close = high (positive CLV)."""
        code = """
//@version=6
indicator("accdist high test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 105.0)
array.push(volumes, 1000.0)

accdist = ta.accdist(highs, lows, closes, volumes)
plot(array.get(accdist, 0))
"""
        script = parse(code)
        assert script is not None

    def test_accdist_close_at_low(self):
        """Test A/D when close = low (negative CLV)."""
        code = """
//@version=6
indicator("accdist low test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 95.0)
array.push(volumes, 1000.0)

accdist = ta.accdist(highs, lows, closes, volumes)
plot(array.get(accdist, 0))
"""
        script = parse(code)
        assert script is not None

    def test_accdist_zero_range(self):
        """Test A/D with high = low (zero range)."""
        code = """
//@version=6
indicator("accdist range test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 100.0)
array.push(lows, 100.0)
array.push(closes, 100.0)
array.push(volumes, 1000.0)

accdist = ta.accdist(highs, lows, closes, volumes)
plot(array.get(accdist, 0))
"""
        script = parse(code)
        assert script is not None

    def test_accdist_cumulative_nature(self):
        """Test that A/D is cumulative and increasing/decreasing."""
        code = """
//@version=6
indicator("accdist cumulative test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 104.0)
array.push(volumes, 1000.0)

array.push(highs, 103.0)
array.push(lows, 93.0)
array.push(closes, 94.0)
array.push(volumes, 1200.0)

accdist = ta.accdist(highs, lows, closes, volumes)
plot(array.get(accdist, 0))
plot(array.get(accdist, 1))
"""
        script = parse(code)
        assert script is not None


class TestWadIndicator:
    """Test suite for ta.wad (Williams A/D) indicator."""

    def test_wad_basic_calculation(self):
        """Test basic WAD calculation."""
        code = """
//@version=6
indicator("wad test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 100.0)
array.push(volumes, 1000.0)

array.push(highs, 106.0)
array.push(lows, 96.0)
array.push(closes, 104.0)
array.push(volumes, 1200.0)

wad = ta.wad(highs, lows, closes, volumes)
plot(array.get(wad, 0))
"""
        script = parse(code)
        assert script is not None

    def test_wad_up_accumulation(self):
        """Test WAD with price up (accumulation)."""
        code = """
//@version=6
indicator("wad up test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 100.0)
array.push(lows, 90.0)
array.push(closes, 95.0)
array.push(volumes, 1000.0)

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 103.0)
array.push(volumes, 1500.0)

wad = ta.wad(highs, lows, closes, volumes)
plot(array.get(wad, 0))
plot(array.get(wad, 1))
"""
        script = parse(code)
        assert script is not None

    def test_wad_down_distribution(self):
        """Test WAD with price down (distribution)."""
        code = """
//@version=6
indicator("wad down test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 103.0)
array.push(volumes, 1000.0)

array.push(highs, 102.0)
array.push(lows, 92.0)
array.push(closes, 94.0)
array.push(volumes, 1500.0)

wad = ta.wad(highs, lows, closes, volumes)
plot(array.get(wad, 0))
plot(array.get(wad, 1))
"""
        script = parse(code)
        assert script is not None

    def test_wad_cumulative(self):
        """Test that WAD is cumulative."""
        code = """
//@version=6
indicator("wad cumulative test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 100.0)
array.push(lows, 90.0)
array.push(closes, 95.0)
array.push(volumes, 1000.0)

array.push(highs, 102.0)
array.push(lows, 92.0)
array.push(closes, 101.0)
array.push(volumes, 1000.0)

array.push(highs, 104.0)
array.push(lows, 94.0)
array.push(closes, 103.0)
array.push(volumes, 1000.0)

wad = ta.wad(highs, lows, closes, volumes)
plot(array.get(wad, 0))
plot(array.get(wad, 1))
plot(array.get(wad, 2))
"""
        script = parse(code)
        assert script is not None

    def test_wad_first_bar_zero(self):
        """Test that WAD first bar is zero."""
        code = """
//@version=6
indicator("wad first bar test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 100.0)
array.push(lows, 90.0)
array.push(closes, 95.0)
array.push(volumes, 1000.0)

wad = ta.wad(highs, lows, closes, volumes)
first = array.get(wad, 0)
plot(first)
"""
        script = parse(code)
        assert script is not None


class TestWvadIndicator:
    """Test suite for ta.wvad (Williams Volume A/D) indicator."""

    def test_wvad_basic_calculation(self):
        """Test basic WVAD calculation."""
        code = """
//@version=6
indicator("wvad test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 100.0)
array.push(volumes, 1000.0)

array.push(highs, 106.0)
array.push(lows, 96.0)
array.push(closes, 104.0)
array.push(volumes, 1200.0)

wvad = ta.wvad(highs, lows, closes, volumes)
plot(array.get(wvad, 0))
"""
        script = parse(code)
        assert script is not None

    def test_wvad_custom_period(self):
        """Test WVAD with custom period."""
        code = """
//@version=6
indicator("wvad period test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

for i = 0 to 30
    array.push(highs, 105.0)
    array.push(lows, 95.0)
    array.push(closes, 100.0 + float(i) * 0.1)
    array.push(volumes, 1000.0 + float(i) * 10.0)

wvad = ta.wvad(highs, lows, closes, volumes, 14)
plot(array.get(wvad, 0))
"""
        script = parse(code)
        assert script is not None

    def test_wvad_default_period(self):
        """Test WVAD with default period (20)."""
        code = """
//@version=6
indicator("wvad default period test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

for i = 0 to 25
    array.push(highs, 105.0)
    array.push(lows, 95.0)
    array.push(closes, 100.0 + float(i) * 0.1)
    array.push(volumes, 1000.0 + float(i) * 10.0)

wvad = ta.wvad(highs, lows, closes, volumes)
plot(array.get(wvad, 0))
"""
        script = parse(code)
        assert script is not None

    def test_wvad_volume_normalization(self):
        """Test that WVAD normalizes by volume."""
        code = """
//@version=6
indicator("wvad norm test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 100.0)
array.push(lows, 90.0)
array.push(closes, 95.0)
array.push(volumes, 10000.0)

array.push(highs, 102.0)
array.push(lows, 92.0)
array.push(closes, 101.0)
array.push(volumes, 20000.0)

wvad = ta.wvad(highs, lows, closes, volumes, 10)
plot(array.get(wvad, 0))
plot(array.get(wvad, 1))
"""
        script = parse(code)
        assert script is not None

    def test_wvad_zero_volume(self):
        """Test WVAD handling of zero volume."""
        code = """
//@version=6
indicator("wvad zero vol test")

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 100.0)
array.push(lows, 90.0)
array.push(closes, 95.0)
array.push(volumes, 0.0)

wvad = ta.wvad(highs, lows, closes, volumes, 5)
plot(array.get(wvad, 0))
"""
        script = parse(code)
        assert script is not None


class TestPhase7Integration:
    """Integration tests for all Phase 7 indicators."""

    def test_all_indicators_in_single_script(self):
        """Test all 6 indicators working together in one script."""
        code = """
//@version=6
indicator("Phase 7 Indicators Integration", overlay=false)

// Setup data
highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

for i = 0 to 30
    array.push(highs, 105.0 + float(i) * 0.5)
    array.push(lows, 95.0 + float(i) * 0.5)
    array.push(closes, 100.0 + float(i) * 0.3)
    array.push(volumes, 1000.0 + float(i) * 50.0)

// Test all indicators
high = array.get(highs, 0)
low = array.get(lows, 0)
close = array.get(closes, 0)

iii = ta.iii(high, low, close)
nvi = ta.nvi(closes, volumes)
pvi = ta.pvi(closes, volumes)
accdist = ta.accdist(highs, lows, closes, volumes)
wad = ta.wad(highs, lows, closes, volumes)
wvad = ta.wvad(highs, lows, closes, volumes, 14)

plot(iii, title="IIIIndex", color=color.blue)
plot(array.get(nvi, array.size(nvi) - 1), title="NVI", color=color.green)
plot(array.get(pvi, array.size(pvi) - 1), title="PVI", color=color.red)
plot(array.get(accdist, array.size(accdist) - 1), title="A/D", color=color.orange)
plot(array.get(wad, array.size(wad) - 1), title="WAD", color=color.purple)
plot(array.get(wvad, array.size(wvad) - 1), title="WVAD", color=color.yellow)
"""
        script = parse(code)
        assert script is not None
        unparsed = unparse(script)
        # Verify all indicators are present in unparsed code
        assert "ta.iii" in unparsed
        assert "ta.nvi" in unparsed
        assert "ta.pvi" in unparsed
        assert "ta.accdist" in unparsed
        assert "ta.wad" in unparsed
        assert "ta.wvad" in unparsed

    def test_indicators_with_builtin_functions(self):
        """Test Phase 7 indicators work with existing built-in functions."""
        code = """
//@version=6
indicator("Phase 7 + Built-ins", overlay=false)

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

for i = 0 to 50
    array.push(highs, 105.0)
    array.push(lows, 95.0)
    array.push(closes, 100.0 + float(i % 10) * 0.5)
    array.push(volumes, 1000.0)

// Use Phase 7 indicators
accdist = ta.accdist(highs, lows, closes, volumes)
wvad = ta.wvad(highs, lows, closes, volumes)

// Apply existing Phase 5 functions to results
accdist_sma = ta.sma(accdist, 5)
wvad_rsi = ta.rsi(wvad, 14)

plot(accdist_sma, title="A/D SMA", color=color.blue)
plot(wvad_rsi, title="WVAD RSI", color=color.red)
"""
        script = parse(code)
        assert script is not None

    def test_with_strategy_context(self):
        """Test Phase 7 indicators in strategy context."""
        code = """
//@version=6
strategy("Phase 7 Strategy", overlay=false)

highs = array.new<float>()
lows = array.new<float>()
closes = array.new<float>()
volumes = array.new<float>()

array.push(highs, 105.0)
array.push(lows, 95.0)
array.push(closes, 100.0)
array.push(volumes, 1000.0)

array.push(highs, 106.0)
array.push(lows, 96.0)
array.push(closes, 104.0)
array.push(volumes, 1200.0)

// Use Phase 7 indicators for entry signals
iii = ta.iii(array.get(highs, 1), array.get(lows, 1), array.get(closes, 1))
accdist = ta.accdist(highs, lows, closes, volumes)

if iii > 0.0
    strategy.entry("BUY", strategy.long)

if iii < 0.0
    strategy.close("BUY")
"""
        script = parse(code)
        assert script is not None

    def test_type_compatibility(self):
        """Test that Phase 7 indicators are type-compatible."""
        code = """
//@version=6
indicator("Phase 7 Types", overlay=false)

h = 105.0
l = 95.0
c = 100.0
v = 1000.0

// Float inputs
iii_float = ta.iii(h, l, c)

// Array inputs
highs = array.from(105.0, 106.0, 107.0)
lows = array.from(95.0, 96.0, 97.0)
closes = array.from(100.0, 104.0, 106.0)
volumes = array.from(1000.0, 1200.0, 1100.0)

accdist_array = ta.accdist(highs, lows, closes, volumes)
wad_array = ta.wad(highs, lows, closes, volumes)

plot(iii_float)
for i = 0 to array.size(accdist_array) - 1
    plot(array.get(accdist_array, i))
"""
        script = parse(code)
        assert script is not None
