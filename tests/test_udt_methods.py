"""Integration tests for Phase 3: Method Invocation

Tests the complete flow of method definition, invocation, and THIS binding.
"""

from __future__ import annotations

from pynescript.ast.helper import parse, unparse


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
