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

"""Integration tests for Phase 3: Method Invocation

Tests the complete flow of method definition, invocation, and THIS binding.
"""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestMethodDefinition:
    """Test method definition and parsing"""

    def test_simple_method_definition(self):
        """Parse a simple method definition"""
        code = """
type Trade
    float price = 0.0

method getValue(Trade this) =>
    this.price
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_with_parameters(self):
        """Method with additional parameters"""
        code = """
type Account
    float balance = 0.0

method withdraw(Account this, float amount) =>
    this.balance - amount
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_with_multiple_parameters(self):
        """Method with multiple parameters"""
        code = """
type Order
    float entry = 0.0
    float stop = 0.0

method isValid(Order this, float minEntry, float maxStop) =>
    this.entry > minEntry and this.stop < maxStop
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestMethodInvocation:
    """Test method calls on objects"""

    def test_simple_method_call(self):
        """Call a simple method"""
        code = """
indicator("Test")

type Trade
    float price = 0.0

method getValue(Trade this) =>
    this.price

t = Trade.new(100.0)
result = t.getValue()
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_call_with_arguments(self):
        """Call method with arguments"""
        code = """
indicator("Test")

type Account
    float balance = 0.0

method withdraw(Account this, float amount) =>
    this.balance - amount

a = Account.new(1000.0)
result = a.withdraw(100.0)
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_call_with_multiple_arguments(self):
        """Call method with multiple arguments"""
        code = """
indicator("Test")

type Order
    float entry = 0.0

method calculateProfit(Order this, float exit, float qty) =>
    (exit - this.entry) * qty

o = Order.new(100.0)
profit = o.calculateProfit(105.0, 10)
plot(profit)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestTHISBinding:
    """Test THIS parameter binding in methods"""

    def test_this_field_access(self):
        """THIS parameter binds correctly for field access"""
        code = """
indicator("Test")

type Data
    float value = 0.0

method getValue(Data this) =>
    this.value

d = Data.new(42.0)
result = d.getValue()
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_this_field_mutation_in_method(self):
        """THIS enables field mutation in method"""
        code = """
indicator("Test")

type Counter
    int count = 0

method increment(Counter this) =>
    this.count := this.count + 1
    this.count

c = Counter.new()
result = c.increment()
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_this_in_calculations(self):
        """THIS works in complex calculations"""
        code = """
indicator("Test")

type Price
    float bid = 0.0
    float ask = 0.0

method spread(Price this) =>
    this.ask - this.bid

p = Price.new(100.0, 100.5)
sp = p.spread()
plot(sp)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestMethodReturnValues:
    """Test return values from methods"""

    def test_method_implicit_return(self):
        """Method returns last expression implicitly"""
        code = """
indicator("Test")

type Trade
    float entry = 0.0
    float exit = 0.0

method profit(Trade this) =>
    this.exit - this.entry

t = Trade.new(100.0, 105.0)
p = t.profit()
plot(p)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_return_with_conditions(self):
        """Method with conditional logic"""
        code = """
indicator("Test")

type Signal
    float value = 0.0

method isStrong(Signal this) =>
    if this.value > 50.0
        true
    else
        false

s = Signal.new(75.0)
result = s.isStrong()
plot(result ? 1 : 0)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestMultipleMethods:
    """Test types with multiple methods"""

    def test_multiple_methods_on_same_type(self):
        """Type can have multiple methods"""
        code = """
indicator("Test")

type Trade
    float price = 0.0
    int qty = 0

method value(Trade this) =>
    this.price * this.qty

method cost(Trade this, float fee) =>
    this.value() + fee

t = Trade.new(100.0, 10)
v = t.value()
c = t.cost(50.0)
plot(v + c)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_calling_another_method(self):
        """Methods can call other methods on same object"""
        code = """
indicator("Test")

type Account
    float balance = 0.0

method getBalance(Account this) =>
    this.balance

method isRich(Account this) =>
    this.getBalance() > 1000.0

a = Account.new(2000.0)
result = a.isRich()
plot(result ? 1 : 0)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestComplexMethodScenarios:
    """Test complex method usage scenarios"""

    def test_method_with_loops(self):
        """Method with loop logic"""
        code = """
indicator("Test")

type Series
    array<float> values = array.new<float>()

method sum(Series this) =>
    total = 0.0
    for i = 0 to array.size(this.values) - 1
        total := total + array.get(this.values, i)
    total

s = Series.new()
result = s.sum()
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_method_with_conditionals(self):
        """Method with conditional logic"""
        code = """
indicator("Test")

type Portfolio
    float value = 0.0

method status(Portfolio this) =>
    if this.value > 5000.0
        "rich"
    else if this.value > 1000.0
        "moderate"
    else
        "small"

p = Portfolio.new(3000.0)
s = p.status()
plot(1)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_nested_object_method_call(self):
        """Call methods on nested objects"""
        code = """
indicator("Test")

type Price
    float value = 0.0

method getPrice(Price this) =>
    this.value

type Quote
    Price p = Price.new()

method quotePrice(Quote this) =>
    this.p.getPrice()

q = Quote.new()
q.p := Price.new(100.0)
result = q.quotePrice()
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_exported_method(self):
        """Methods can be exported"""
        code = """
indicator("Test")

type Trade
    float price = 0.0

export method getValue(Trade this) =>
    this.price

t = Trade.new(100.0)
result = t.getValue()
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestMethodIssetOnNa:
    """Console-style ``x.isset(fallback)`` when ``x`` is still na."""

    def test_udt_isset_on_na_receiver(self):
        from backend.runtime import Runtime

        bars = [
            {
                "time": 1_000 + i * 60,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
            for i in range(3)
        ]
        src = """
//@version=5
indicator("isset-na")
type theme
    color color_text = color.white

method isset(theme _theme, theme _replacement) =>
    na(_theme) ? _replacement : _theme

method init(theme this, theme __theme = na) =>
    this := this.isset(__theme.isset(theme.new()))
    this

theme u = theme.new().init(na)
plot(na(u) ? 0 : 1)
"""
        result = Runtime(symbol="TEST").run(src, bars)
        assert "error" not in result, result.get("error")
        assert result["plots"] == [1, 1, 1]


class TestUdtNewNameShadowing:
    """Type.Name collision: method insights must not break insights.new()."""

    def test_type_new_when_method_shares_type_name(self):
        from backend.runtime import Runtime

        bars = [
            {
                "time": 1_741_910_400 + i * 86_400,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
            for i in range(3)
        ]
        src = """
//@version=5
indicator("shadow-new")
type insights
    int total = 0
    int new = 0

method insights(int this) =>
    this + 1

method isset(insights a, insights b) =>
    na(a) ? b : a

insights x = na
insights y = x.isset(insights.new())
plot(na(y) ? 0 : 1)
plot(y.new)
"""
        result = Runtime(symbol="TEST").run(src, bars)
        assert "error" not in result, result.get("error")
        assert result["plots"][-1] in (0, 1) or result["plots"] == [1, 1, 1]
        # constructor succeeded: plots are numeric, not error
        assert all(isinstance(v, (int, float)) for v in result["plots"])


class TestUdtFieldCallSyntax:
    """Console-style zero-arg field calls: ``this.columns()``."""

    def test_field_as_zero_arg_call(self):
        from backend.runtime import Runtime

        bars = [
            {
                "time": 1_741_910_400 + i * 86_400,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
            for i in range(3)
        ]
        src = """
//@version=5
indicator("field-call")
type terminal
    int columns = 4
    int rows = 5

method area(terminal this) =>
    this.columns() * this.rows()

terminal t = terminal.new()
plot(t.area())
"""
        result = Runtime(symbol="TEST").run(src, bars)
        assert "error" not in result, result.get("error")
        assert result["plots"] == [20, 20, 20]


class TestBarLoopMethodRegistration:
    """Bar-loop hosts must not grow multi-dispatch tables every bar."""

    def test_overloads_stable_across_revisits(self):
        from pynescript.ast.evaluator import NodeLiteralEvaluator
        from pynescript.ast.helper import parse

        src = """
//@version=5
indicator("overload-stable")
method tostring(series int this) =>
    str.tostring(this)
method tostring(series float this) =>
    str.tostring(this)
method tostring(series string this) =>
    this
plot(1)
"""
        tree = parse(src)
        ev = NodeLiteralEvaluator()
        for _ in range(8):
            ev.visit(tree)
        n = len(ev.context["tostring"].__pine_overloads__)
        assert n == 3, f"expected 3 overloads, got {n} (accumulation leak)"

    def test_defs_locked_skips_reregister(self):
        from backend.evaluator import CustomEvaluator
        from pynescript.ast.helper import parse

        src = """
//@version=5
indicator("defs-lock")
method tostring(series int this) =>
    str.tostring(this)
plot(1)
"""
        tree = parse(src)
        ev = CustomEvaluator()
        ev.visit(tree)
        first = ev.context["tostring"]
        ev._pine_defs_locked = True
        ev.visit(tree)
        assert ev.context["tostring"] is first


class TestBareNaAndLabelDelete:
    """Console demo: bare ``na``, optional UDT args, label.delete after chaining."""

    def test_bare_na_is_none(self):
        from pynescript.ast.evaluator import NodeLiteralEvaluator

        ev = NodeLiteralEvaluator()
        ev.evaluate_script("x = na")
        assert ev.context["x"] is None
        ev.evaluate_script("y = na(na)\nz = na(1)")
        assert ev.context["y"] is True
        assert ev.context["z"] is False

    def test_init_with_na_theme_keeps_object(self):
        """``terminal.new().init(na)`` must not stringify the instance."""
        from pynescript.ast.evaluator import NodeLiteralEvaluator
        from pynescript.ast.type_system import ObjectInstance

        src = """
//@version=5
indicator("init-na")
type theme
    color color_text = color.white
type terminal
    int columns = 1

method init(terminal this, theme __theme = na) =>
    this

terminal console = terminal.new().init(na)
plot(1)
"""
        ev = NodeLiteralEvaluator()
        ev.evaluate_script(src)
        assert isinstance(ev.context["console"], ObjectInstance)
        assert ev.context["console"].udt.name == "terminal"

    def test_label_log_inline_style_chain_then_delete(self):
        """``label.new(...).log_inline(console)`` must stay a Label for ``.delete()``."""
        from pynescript.ast.evaluator import NodeLiteralEvaluator
        from pynescript.ast.evaluator.builtins.drawing import Label
        from pynescript.ast.type_system import ObjectInstance

        src = """
//@version=5
indicator("label-delete")
type terminal
    int columns = 1

method init(terminal this, theme __theme = na) =>
    this

method tostring(series label this) =>
    this.get_text()

method log(terminal this, series string _title, series string _data) =>
    this

method log_inline(series label this, terminal _console, series string _title = '') =>
    _console.log(_title, this.tostring())
    this

terminal console = terminal.new().init(na)
label testLabel = label.new(0, close, 'Test Label').log_inline(console)
testLabel.delete()
plot(1)
"""
        ev = NodeLiteralEvaluator()
        ev.context["close"] = 100.0
        ev.context["bar_index"] = 0
        ev.evaluate_script(src)
        assert isinstance(ev.context["console"], ObjectInstance)
        tl = ev.context["testLabel"]
        assert isinstance(tl, Label)
        assert tl.deleted is True

    def test_label_new_point_kwarg_expands_coords(self):
        from pynescript.ast.evaluator import NodeLiteralEvaluator

        src = """
//@version=5
indicator("label-point")
p = chart.point.from_index(10, 42.5)
l = label.new(point = p, text = "hi")
plot(l.get_x())
plot(l.get_y())
"""
        ev = NodeLiteralEvaluator()
        ev.evaluate_script(src)
        assert ev.context["l"].x == 10
        assert ev.context["l"].y == 42.5
