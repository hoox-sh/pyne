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

"""Integration tests for Phase 2: Object Instantiation

Tests the complete flow of UDT object creation, field access, and mutation.
"""

from __future__ import annotations

from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


class TestObjectInstantiation:
    """Test basic object instantiation"""

    def test_simple_object_creation(self):
        """Parse and evaluate simple UDT instantiation"""
        code = """
indicator("Test", overlay=true)

type Trade
    float price = 0.0
    int qty = 0

t = Trade.new()
plot(t.price)
        """
        # Parse should succeed
        ast = parse(code)
        assert ast is not None

        # Unparse and reparse should work (round-trip)
        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_object_with_positional_arguments(self):
        """Create object with constructor arguments"""
        code = """
indicator("Test")

type Trade
    float price
    int qty

t = Trade.new(99.50, 100)
plot(t.price)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_object_with_named_arguments(self):
        """Create object with named arguments"""
        code = """
indicator("Test")

type Trade
    float price = 0.0
    int qty = 0

t = Trade.new(price=99.50, qty=100)
plot(t.price)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_multiple_object_instances(self):
        """Create multiple instances of same type"""
        code = """
indicator("Test")

type Point
    float x = 0.0
    float y = 0.0

p1 = Point.new(10.0, 20.0)
p2 = Point.new(30.0, 40.0)
plot(p1.x + p2.y)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestFieldAccess:
    """Test field access on objects"""

    def test_field_access_simple(self):
        """Access object fields after creation"""
        code = """
indicator("Test")

type Data
    float close = 0.0
    float high = 0.0

d = Data.new(100.0, 105.0)
result = d.close + d.high
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_nested_field_access(self):
        """Access nested object fields"""
        code = """
indicator("Test")

type Price
    float bid = 100.0

type Quote
    Price p = Price.new()

q = Quote.new()
plot(q.p.bid)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_field_access_in_expression(self):
        """Use field access in calculations"""
        code = """
indicator("Test")

type Trade
    float entry = 0.0
    float exit = 0.0

t = Trade.new(100.0, 105.0)
profit = t.exit - t.entry
plot(profit)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestFieldMutation:
    """Test field mutation on objects"""

    def test_field_mutation_simple(self):
        """Mutate object fields"""
        code = """
indicator("Test")

type Balance
    float amount = 0.0

b = Balance.new(1000.0)
b.amount := b.amount * 1.05
plot(b.amount)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_field_mutation_in_loop(self):
        """Mutate fields multiple times"""
        code = """
indicator("Test")

type Counter
    int count = 0

c = Counter.new()
c.count := 1
c.count := 2
plot(c.count)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_field_mutation_with_calculation(self):
        """Mutate fields with calculations"""
        code = """
indicator("Test")

type Account
    float balance = 1000.0

a = Account.new()
withdrawal = 100.0
a.balance := a.balance - withdrawal
plot(a.balance)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestObjectCopy:
    """Test .copy() method on objects"""

    def test_object_copy_basic(self):
        """Test .copy() method"""
        code = """
indicator("Test")

type Record
    float value = 100.0

r1 = Record.new()
r2 = r1.copy()
plot(r1.value)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_object_copy_with_mutation(self):
        """Copy and mutate independently"""
        code = """
indicator("Test")

type Item
    float price = 100.0

i1 = Item.new()
i2 = i1.copy()
i2.price := 200.0
plot(i1.price)
plot(i2.price)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestObjectsInArrays:
    """Test storing objects in arrays"""

    def test_object_in_array(self):
        """Store objects in arrays"""
        code = """
indicator("Test")

type Trade
    float price = 0.0

trades = array.new<Trade>()
t = Trade.new(99.50)
array.push(trades, t)
result = trades.get(0).price
plot(result)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_multiple_objects_in_array(self):
        """Store multiple objects in array"""
        code = """
indicator("Test")

type Quote
    float bid = 0.0
    float ask = 0.0

quotes = array.new<Quote>()
q1 = Quote.new(100.0, 100.5)
q2 = Quote.new(101.0, 101.5)
array.push(quotes, q1)
array.push(quotes, q2)
plot(quotes.get(0).bid)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestNestedObjects:
    """Test nested object types"""

    def test_nested_object_access(self):
        """Access nested object fields"""
        code = """
indicator("Test")

type Price
    float bid = 0.0
    float ask = 0.0

type Quote
    Price p = Price.new()

q = Quote.new()
q.p := Price.new(100.0, 100.5)
plot(q.p.bid)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_nested_object_mutation(self):
        """Mutate nested object fields"""
        code = """
indicator("Test")

type Coord
    float x = 0.0
    float y = 0.0

type Location
    Coord c = Coord.new()

loc = Location.new()
loc.c.x := 10.0
plot(loc.c.x)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)


class TestComplexScenarios:
    """Test complex usage scenarios"""

    def test_trade_management(self):
        """Complex trade management scenario"""
        code = """
indicator("Trade Manager")

type Trade
    float entry = 0.0
    float stop = 0.0
    float target = 0.0
    int qty = 0

trades = array.new<Trade>()

t = Trade.new(100.0, 99.0, 102.0, 10)
array.push(trades, t)

if array.size(trades) > 0
    trade = trades.get(0)
    plot(trade.entry)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_multiple_udt_types(self):
        """Multiple different UDT types"""
        code = """
indicator("Multi-Type")

type Price
    float value = 0.0

type Volume
    int count = 0

type Bar
    Price p = Price.new()
    Volume v = Volume.new()

bar = Bar.new()
bar.p.value := 100.0
bar.v.count := 1000
plot(bar.p.value)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)

    def test_object_initialization_patterns(self):
        """Various object initialization patterns"""
        code = """
indicator("Init Patterns")

type Config
    float ratio = 0.5
    int limit = 100

c1 = Config.new()
c2 = Config.new(0.75)
c3 = Config.new(0.9, 50)
c4 = Config.new(ratio=0.8, limit=200)

plot(c1.ratio)
        """
        ast = parse(code)
        assert ast is not None

        unparsed = unparse(ast)
        reparsed = parse(unparsed)
        assert repr(ast) == repr(reparsed)
