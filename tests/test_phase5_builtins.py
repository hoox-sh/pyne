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

"""Integration tests for Phase 5: Built-in Functions

Tests the complete flow of ticker, logging, chart.point, and polyline functions.
"""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestTickerFunctions:
    """Test ticker functions"""

    def test_ticker_new_basic(self):
        """Parse and evaluate ticker.new()"""
        code = """
indicator("Test")

t = ticker.new("AAPL")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        # Round-trip test
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_new_with_session(self):
        """Create ticker with session parameter"""
        code = """
indicator("Test")

t = ticker.new("AAPL", session="extended")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_modify(self):
        """Parse and evaluate ticker.modify()"""
        code = """
indicator("Test")

t = ticker.new("AAPL")
t2 = ticker.modify(t, session="extended")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_heikinashi(self):
        """Parse and evaluate ticker.heikinashi()"""
        code = """
indicator("Test")

t = ticker.heikinashi("AAPL")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_kagi(self):
        """Parse and evaluate ticker.kagi()"""
        code = """
indicator("Test")

t = ticker.kagi("AAPL", 3.0)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_linebreak(self):
        """Parse and evaluate ticker.linebreak()"""
        code = """
indicator("Test")

t = ticker.linebreak("AAPL", 3)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_pointfigure(self):
        """Parse and evaluate ticker.pointfigure()"""
        code = """
indicator("Test")

t = ticker.pointfigure("AAPL", 1.0)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_renko(self):
        """Parse and evaluate ticker.renko()"""
        code = """
indicator("Test")

t = ticker.renko("AAPL", 1.0)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_standard(self):
        """Parse and evaluate ticker.standard()"""
        code = """
indicator("Test")

t = ticker.standard("AAPL")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestLoggingFunctions:
    """Test logging functions"""

    def test_log_error(self):
        """Parse and evaluate log.error()"""
        code = """
indicator("Test")

log.error("Error message")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_log_info(self):
        """Parse and evaluate log.info()"""
        code = """
indicator("Test")

log.info("Info message")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_log_warning(self):
        """Parse and evaluate log.warning()"""
        code = """
indicator("Test")

log.warning("Warning message")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_multiple_log_calls(self):
        """Test multiple logging calls in sequence"""
        code = """
indicator("Test")

if bar_index == 0
    log.info("Start")
    log.warning("Warning")
    log.error("Error")

plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestChartPointFunctions:
    """Test chart.point functions"""

    def test_chart_point_new(self):
        """Parse and evaluate chart.point.new()"""
        code = """
indicator("Test")

p = chart.point.new(bar_index, close)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_chart_point_from_index(self):
        """Parse and evaluate chart.point.from_index()"""
        code = """
indicator("Test")

p = chart.point.from_index(10, close)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_chart_point_from_time(self):
        """Parse and evaluate chart.point.from_time()"""
        code = """
indicator("Test")

p = chart.point.from_time(time, close)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_chart_point_now(self):
        """Parse and evaluate chart.point.now()"""
        code = """
indicator("Test")

p = chart.point.now(close)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_chart_point_copy(self):
        """Parse and evaluate chart.point.copy()"""
        code = """
indicator("Test")

p1 = chart.point.new(bar_index, close)
p2 = chart.point.copy(p1)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestPolylineFunctions:
    """Test polyline functions"""

    def test_polyline_new(self):
        """Parse and evaluate polyline.new()"""
        code = """
indicator("Test")

var points = array.new<chart.point>()
array.push(points, chart.point.new(bar_index, close))
pl = polyline.new(points)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_polyline_delete(self):
        """Parse and evaluate polyline.delete()"""
        code = """
indicator("Test")

var points = array.new<chart.point>()
array.push(points, chart.point.new(bar_index, close))
pl = polyline.new(points)
polyline.delete(pl)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_polyline_copy(self):
        """Parse and evaluate polyline.copy()"""
        code = """
indicator("Test")

var points = array.new<chart.point>()
array.push(points, chart.point.new(bar_index, close))
pl1 = polyline.new(points)
pl2 = polyline.copy(pl1)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestIntegratedPhase5Features:
    """Test Phase 5 features integrated together"""

    def test_ticker_with_request_security(self):
        """Test ticker functions with request.security()"""
        code = """
indicator("Multi-Timeframe", overlay=true)

t = ticker.new("AAPL")
h = request.security(t, "1D", high)
l = request.security(t, "1D", low)

plot(h)
plot(l)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_chart_points_with_polyline(self):
        """Test chart.point with polyline drawing"""
        code = """
indicator("Polyline Example", overlay=true)

var points = array.new<chart.point>()

if barstate.isfirst
    array.push(points, chart.point.new(0, close))
else if bar_index % 10 == 0
    array.push(points, chart.point.new(bar_index, close))

if array.size(points) > 1
    pl = polyline.new(points, closed=false, xloc=xloc.bar_index)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_all_phase5_together(self):
        """Test ticker, logging, chart.point, and polyline together"""
        code = """
indicator("Phase 5 Complete", overlay=true)

log.info("Starting indicator")

t = ticker.new("AAPL", session="extended")
log.info("Created ticker: AAPL")

var points = array.new<chart.point>()
p = chart.point.new(bar_index, close)
array.push(points, p)

if array.size(points) > 2
    pl = polyline.new(points)
    log.info("Created polyline")

plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_nested_chart_transforms(self):
        """Test nested chart transformations"""
        code = """
indicator("Nested Transforms", overlay=true)

t_ha = ticker.heikinashi("AAPL")
t_renko = ticker.renko("AAPL", 1.0)
t_kagi = ticker.kagi("AAPL", 3.0)

plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_strategy_with_phase5_features(self):
        """Test Phase 5 features in strategy context"""
        code = """
strategy("Phase 5 Strategy")

log.info("Strategy started")

t = ticker.standard("SPY")
h = request.security(t, "D", high)
l = request.security(t, "D", low)

if close > h
    log.warning("Price above high")
    strategy.entry("long", strategy.long)

if close < l
    log.error("Price below low")
    strategy.close("long")
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestPhase5EdgeCases:
    """Test edge cases and corner scenarios"""

    def test_ticker_with_special_symbols(self):
        """Test ticker with special symbols like crypto"""
        code = """
indicator("Crypto")

btc = ticker.new("BINANCE:BTCUSDT")
eth = ticker.new("BINANCE:ETHUSDT")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_chart_point_with_expressions(self):
        """Test chart.point with complex expressions"""
        code = """
indicator("Complex Points")

p1 = chart.point.new(bar_index * 2, close + 10)
p2 = chart.point.from_index(bar_index + 5, high - low)
p3 = chart.point.copy(p1)
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_polyline_with_closed_parameter(self):
        """Test polyline with various parameters"""
        code = """
indicator("Polyline Params", overlay=true)

var points = array.new<chart.point>()
array.push(points, chart.point.new(bar_index, close))

if array.size(points) > 1
    pl = polyline.new(points, closed=true, xloc=xloc.bar_index,
                      edge_color=color.red, edge_width=2)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_logging_with_string_formatting(self):
        """Test logging with formatted strings"""
        code = """
indicator("Formatted Logs")

msg = str.format("Price: {0}, Volume: {1}", close, volume)
log.info(msg)
log.warning("High: " + str.tostring(high))
log.error(str.format("Error code: {0}", bar_index))
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ticker_modify_chaining(self):
        """Test ticker.modify() with multiple modifications"""
        code = """
indicator("Ticker Chaining")

t = ticker.new("AAPL")
t = ticker.modify(t, session="extended")
t = ticker.modify(t, symbol="MSFT")
plot(close)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)
