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
Comprehensive tests for Pine Script v6 Enhancements

Tests cover the following v6 features:
- Dynamic request.* calls with series string arguments
- Scope limit removal (already native in Python)
- Dynamic for loop boundaries
- bid/ask variables on 1T timeframe
"""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestDynamicRequestCalls:
    """Test dynamic request.* calls with series string arguments (v6 November 2024)"""

    def test_request_security_with_string_symbol(self):
        """request.security with string symbol argument"""
        code = """
indicator("Dynamic Request Security")
symbol = "AAPL"
result = request.security(symbol, "D", close)
plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_request_security_with_timeframe_variable(self):
        """request.security with timeframe variable (v6 dynamic)"""
        code = """
indicator("Dynamic Timeframe")
tf = "1H"
result = request.security("AAPL", tf, close)
plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_request_security_with_expression_variable(self):
        """request.security with expression variable (v6 dynamic)"""
        code = """
indicator("Dynamic Expression")
expr = close
result = request.security("AAPL", "D", expr)
plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_request_security_all_dynamic(self):
        """request.security with all parameters dynamic (v6 feature)"""
        code = """
indicator("Fully Dynamic Request")
sym = "AAPL"
tf = "1H"
ex = close
result = request.security(sym, tf, ex)
plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_request_security_lower_tf_dynamic(self):
        """request.security_lower_tf with dynamic arguments (v6)"""
        code = """
indicator("Dynamic Lower TF")
symbol = "AAPL"
tf = "5m"
result = request.security_lower_tf(symbol, tf, close)
plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_multiple_dynamic_requests(self):
        """Multiple dynamic request.* calls in sequence"""
        code = """
indicator("Multiple Requests")
symbols = array.from("AAPL", "GOOGL", "MSFT")
for i = 0 to array.size(symbols) - 1
    sym = array.get(symbols, i)
    result = request.security(sym, "D", close)
    plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestBidAskVariables:
    """Test bid/ask variables on 1T timeframe (v6 February 2025)"""

    def test_bid_variable_available(self):
        """bid variable is available on 1T timeframe"""
        code = """
indicator("Bid/Ask Test", timeframe="1")
plot(bid)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_ask_variable_available(self):
        """ask variable is available on 1T timeframe"""
        code = """
indicator("Bid/Ask Test", timeframe="1")
plot(ask)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_bid_ask_together(self):
        """Both bid and ask variables in same indicator"""
        code = """
indicator("Bid Ask Spread")
spread = ask - bid
plot(spread)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_bid_ask_in_condition(self):
        """Using bid/ask in conditional logic"""
        code = """
indicator("Bid Ask Conditional")
if close > bid
    strategy.entry("long", strategy.long)
if close < ask
    strategy.entry("short", strategy.short)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_bid_ask_with_arrays(self):
        """bid/ask with array operations"""
        code = """
indicator("Bid Ask Arrays")
bids = array.new_float()
array.push(bids, bid)
last_bid = array.last(bids)
plot(last_bid)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestDynamicForLoops:
    """Test dynamic for loop boundaries (v6 March 2025)"""

    def test_for_loop_with_variable_to_value(self):
        """for loop with variable upper boundary"""
        code = """
indicator("Dynamic Loop Boundary")
length = 10
sum = 0
for i = 0 to length - 1
    sum = sum + close[i]
plot(sum)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_for_loop_with_expression_boundary(self):
        """for loop with expression boundary"""
        code = """
indicator("Expression Boundary")
sum = 0
for i = 0 to bar_index / 2
    sum = sum + close[i]
plot(sum)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_for_loop_with_function_boundary(self):
        """for loop with function call boundary"""
        code = """
indicator("Function Boundary")
sum = 0
for i = 0 to math.floor(bar_index / 2)
    sum = sum + close[i]
plot(sum)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_nested_for_loops_dynamic(self):
        """Nested for loops with dynamic boundaries"""
        code = """
indicator("Nested Dynamic Loops")
rows = 5
cols = 10
matrix_val = matrix.new<float>()
for i = 0 to rows - 1
    for j = 0 to cols - 1
        matrix.set(matrix_val, i, j, close)
plot(matrix.elements_count(matrix_val))
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_for_loop_with_reassigned_boundary(self):
        """for loop where boundary variable changes"""
        code = """
indicator("Reassigned Boundary")
length = 5
if close > open
    length = 10
sum = 0
for i = 0 to length - 1
    sum = sum + close[i]
plot(sum)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestV6ScopeImprovements:
    """Test scope improvements in v6 (November 2024 - unlimited scope)"""

    def test_deep_variable_nesting(self):
        """Variables in deeply nested structures"""
        code = """
indicator("Deep Nesting")
if true
    if true
        if true
            if true
                if true
                    x = 10
                    plot(x)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_multiple_conditional_branches(self):
        """Multiple conditional branches with variables"""
        code = """
indicator("Multiple Branches")
if close > open
    x = 10
else if close < open
    x = 5
else
    x = 0
plot(x)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_loop_with_nested_conditionals(self):
        """Loops with nested conditionals"""
        code = """
indicator("Loop Nested Conditionals")
sum = 0
for i = 0 to 100
    if close[i] > open[i]
        if volume[i] > 1000000
            sum = sum + close[i]
plot(sum)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestV6FeatureIntegration:
    """Test integration of multiple v6 features together"""

    def test_dynamic_request_with_bid_ask(self):
        """Dynamic request.* with bid/ask variables"""
        code = """
indicator("Dynamic Request + Bid/Ask")
symbol = "AAPL"
result = request.security(symbol, "D", close)
spread = ask - bid
plot(result + spread)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_dynamic_loops_with_bid_ask(self):
        """Dynamic for loops with bid/ask"""
        code = """
indicator("Loop + Bid/Ask")
length = 10
bid_avg = bid
for i = 0 to length - 1
    bid_avg = bid_avg + bid[i]
bid_avg = bid_avg / length
plot(bid_avg)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_all_v6_features_combined(self):
        """All Phase 6 v6 features combined"""
        code = """
indicator("All V6 Features")
// Dynamic request
symbol = "AAPL"
tf = "1H"
expr = close
result = request.security(symbol, tf, expr)

// Bid/Ask variables
spread = ask - bid

// Dynamic loop boundaries
length = 10
sum = 0
for i = 0 to length - 1
    sum = sum + close[i]

// Combine all
final_value = result + spread + (sum / length)
plot(final_value)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestV6EdgeCases:
    """Test edge cases and special scenarios for v6 features"""

    def test_request_security_in_loop(self):
        """request.security called inside a loop"""
        code = """
indicator("Request in Loop")
for i = 0 to 5
    result = request.security("AAPL", "D", close)
    plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_bid_ask_in_arrays(self):
        """bid/ask used with array operations"""
        code = """
indicator("Bid/Ask in Array")
bids = array.from(bid, bid[1], bid[2])
asks = array.from(ask, ask[1], ask[2])
plot(array.avg(bids))
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_dynamic_for_loop_with_zero_boundary(self):
        """for loop with zero or negative boundary"""
        code = """
indicator("Zero Boundary")
length = 0
for i = 0 to length - 1
    plot(close)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_request_with_complex_expression(self):
        """request.security with complex expression"""
        code = """
indicator("Complex Request Expression")
symbol = "AAPL"
tf = "D"
complex_expr = (close + high + low) / 3
result = request.security(symbol, tf, complex_expr)
plot(result)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_bid_ask_with_na_handling(self):
        """bid/ask with NA value handling"""
        code = """
indicator("Bid/Ask NA Handling")
if na(bid)
    bid_value = close
else
    bid_value = bid
plot(bid_value)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestFootprintRequests:
    """Test footprint data access (January 2026)"""

    def test_request_footprint_basic(self):
        """request.footprint basic usage"""
        code = """
indicator("Footprint Demo")
fp = request.footprint(100, 70)
plot(close)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_footprint_methods(self):
        """footprint.*() method calls"""
        code = """
indicator("Footprint Methods")
fp = request.footprint(100, 70)
buyVol = fp.buy_volume()
sellVol = fp.sell_volume()
delta = fp.delta()
plot(buyVol)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_footprint_row_methods(self):
        """volume_row.*() method calls"""
        code = """
indicator("Volume Row Methods")
fp = request.footprint(100, 70)
pocRow = fp.poc()
if not na(pocRow)
    upPrice = pocRow.up_price()
    downPrice = pocRow.down_price()
plot(upPrice)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


def _string_constants_containing(tree, needle: str) -> list[str]:
    from pynescript.ast import walk
    from pynescript.ast.grammar.asdl.generated.PinescriptASTNode import Constant

    return [
        n.value
        for n in walk(tree)
        if isinstance(n, Constant) and isinstance(n.value, str) and needle in n.value
    ]


class TestMultilineStrings:
    """Test multiline strings (April 2026 v6)"""

    def test_multiline_double_quote(self):
        """Basic multiline with \"\"\" — preserves newlines and indentation."""
        code = '''
indicator("Multiline Test")
s = """line one
  indented line two
line three"""
log.info(s)
'''
        tree = parse(code)
        values = _string_constants_containing(tree, "line one")
        assert values, "expected multiline string constant in AST"
        assert values[0] == "line one\n  indented line two\nline three"

        unparsed = unparse(tree)
        assert '"""' in unparsed
        reparsed = parse(unparsed)
        values2 = _string_constants_containing(reparsed, "line one")
        assert values2[0] == values[0]

    def test_multiline_single_quote(self):
        code = """
indicator("Multiline Single")
s = '''multi
line'''
"""
        tree = parse(code)
        values = _string_constants_containing(tree, "multi")
        assert values
        assert values[0] == "multi\nline"
        unparsed = unparse(tree)
        reparsed = parse(unparsed)
        assert repr(tree) == repr(reparsed)

    def test_multiline_one_line_triple(self):
        """Triple quotes on a single physical line still parse as a string."""
        code = '''
indicator("One line triple")
s = """hello world"""
'''
        values = _string_constants_containing(parse(code), "hello world")
        assert values


class TestExportConst:
    """Test library export const variables (June 2025)"""

    def test_export_const_float(self):
        code = """
//@version=6
library("MyConstants")
export const float SILVER_RATIO = 1.0 + math.sqrt(2)
"""
        from pynescript.ast import walk
        from pynescript.ast.grammar.asdl.generated.PinescriptASTNode import Assign

        tree = parse(code)
        assigns = [n for n in walk(tree) if isinstance(n, Assign) and getattr(n, "export", None)]
        assert len(assigns) == 1
        assert assigns[0].target.id == "SILVER_RATIO"
        assert assigns[0].export == 1

        unparsed = unparse(tree)
        assert "export const float SILVER_RATIO" in unparsed
        reparsed = parse(unparsed)
        assigns2 = [n for n in walk(reparsed) if isinstance(n, Assign) and getattr(n, "export", None)]
        assert len(assigns2) == 1
        assert assigns2[0].target.id == "SILVER_RATIO"

    def test_export_const_int_string_bool(self):
        code = """
//@version=6
library("Consts")
export const int MAX_LEN = 100
export const string NAME = "demo"
export const bool FLAG = true
"""
        from pynescript.ast import walk
        from pynescript.ast.grammar.asdl.generated.PinescriptASTNode import Assign

        tree = parse(code)
        exported = [n for n in walk(tree) if isinstance(n, Assign) and getattr(n, "export", None)]
        names = {n.target.id for n in exported}
        assert names == {"MAX_LEN", "NAME", "FLAG"}
        unparsed = unparse(tree)
        reparsed = parse(unparsed)
        assert repr(tree) == repr(reparsed)


class TestPlotLinestyle:
    """Test plot linestyle parameter (September 2025)"""

    def test_plot_linestyle_solid(self):
        """plot with linestyle=plot.linestyle_solid"""
        code = """
indicator("Solid Line")
plot(close, linestyle=plot.linestyle_solid)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_plot_linestyle_dashed(self):
        """plot with linestyle=plot.linestyle_dashed"""
        code = """
indicator("Dashed Line")
plot(close, linestyle=plot.linestyle_dashed)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_plot_linestyle_dotted(self):
        """plot with linestyle=plot.linestyle_dotted"""
        code = """
indicator("Dotted Line")
plot(close, linestyle=plot.linestyle_dotted)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestInputActiveParameter:
    """Test input active parameter (July 2025)"""

    def test_input_with_active_true(self):
        """input with active=true"""
        code = """
indicator("Active Input Demo")
enableSmoothing = input.bool(false, "Enable", group="Settings")
smoothLength = input.int(9, "Length", group="Settings", active=enableSmoothing)
plot(close)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_input_with_active_false(self):
        """input with active=false"""
        code = """
indicator("Inactive Input Demo")
fixedValue = input.int(14, "Fixed Length", active=false)
plot(close)
        """
        ast = parse(code)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)
