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

"""Unit tests for UDT type system classes

Tests the core UDT classes:
- UserDefinedType: Represents a UDT definition
- Field: Represents a type field
- ObjectInstance: Represents a runtime instance
"""

from __future__ import annotations

import pytest

from pynescript.ast.type_system import BuiltinType
from pynescript.ast.type_system import BuiltinTypeKind
from pynescript.ast.type_system import Field
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType


class TestUserDefinedType:
    """Test UserDefinedType class"""

    def test_create_user_defined_type(self):
        """Create a UDT with fields"""
        udt = UserDefinedType("Trade")

        # Add fields
        price_field = Field("price", BuiltinType(BuiltinTypeKind.FLOAT), 100.5)
        qty_field = Field("qty", BuiltinType(BuiltinTypeKind.INT), 0)

        udt.add_field(price_field)
        udt.add_field(qty_field)

        # Verify fields were added
        assert udt.get_field("price") is price_field
        assert udt.get_field("qty") is qty_field
        assert len(udt.fields) == 2

    def test_get_field_returns_none_for_missing(self):
        """Getting a non-existent field returns None"""
        udt = UserDefinedType("Trade")
        assert udt.get_field("missing") is None

    def test_user_defined_type_name(self):
        """UDT has correct name"""
        udt = UserDefinedType("MyType")
        assert udt.name == "MyType"
        assert "MyType" in str(udt)


class TestField:
    """Test Field class"""

    def test_create_field(self):
        """Create a field with type and default value"""
        field_type = BuiltinType(BuiltinTypeKind.FLOAT)
        field = Field("price", field_type, 99.99)

        assert field.name == "price"
        assert field.field_type is field_type
        assert field.default_value == 99.99
        assert field.varip is False

    def test_field_with_varip(self):
        """Create a field with varip modifier"""
        field_type = BuiltinType(BuiltinTypeKind.INT)
        field = Field("counter", field_type, 0, varip=True)

        assert field.name == "counter"
        assert field.varip is True

    def test_field_without_default_value(self):
        """Field can have None as default value"""
        field_type = BuiltinType(BuiltinTypeKind.STRING)
        field = Field("label", field_type, None)

        assert field.default_value is None

    def test_field_repr(self):
        """Field has proper repr"""
        field_type = BuiltinType(BuiltinTypeKind.FLOAT)
        field = Field("amount", field_type, 100.0)

        repr_str = repr(field)
        assert "amount" in repr_str
        assert "100.0" in repr_str


class TestObjectInstance:
    """Test ObjectInstance class"""

    def test_create_object_instance(self):
        """Create an instance of a UDT"""
        # Create UDT with fields
        udt = UserDefinedType("Trade")
        udt.add_field(Field("price", BuiltinType(BuiltinTypeKind.FLOAT), 100.0))
        udt.add_field(Field("qty", BuiltinType(BuiltinTypeKind.INT), 0))

        # Create instance
        obj = ObjectInstance(udt)

        assert obj.udt is udt
        assert obj.get_field("price") == 100.0
        assert obj.get_field("qty") == 0

    def test_set_field_value(self):
        """Set field value on object instance"""
        udt = UserDefinedType("Account")
        udt.add_field(Field("balance", BuiltinType(BuiltinTypeKind.FLOAT), 1000.0))

        obj = ObjectInstance(udt)
        assert obj.get_field("balance") == 1000.0

        # Mutate field
        obj.set_field("balance", 2000.0)
        assert obj.get_field("balance") == 2000.0

    def test_set_field_raises_on_missing_field(self):
        """Setting non-existent field raises AttributeError"""
        udt = UserDefinedType("Data")
        udt.add_field(Field("value", BuiltinType(BuiltinTypeKind.INT), 0))

        obj = ObjectInstance(udt)

        with pytest.raises(AttributeError, match="Field 'missing' not found"):
            obj.set_field("missing", 42)

    def test_get_field_raises_on_missing_field(self):
        """Getting non-existent field raises AttributeError"""
        udt = UserDefinedType("Data")
        udt.add_field(Field("value", BuiltinType(BuiltinTypeKind.INT), 0))

        obj = ObjectInstance(udt)

        with pytest.raises(AttributeError, match="Field 'missing' not found"):
            obj.get_field("missing")

    def test_copy_instance(self):
        """Copy creates a shallow copy of instance"""
        udt = UserDefinedType("Record")
        udt.add_field(Field("amount", BuiltinType(BuiltinTypeKind.FLOAT), 100.0))

        obj1 = ObjectInstance(udt)
        obj1.set_field("amount", 150.0)

        # Copy object
        obj2 = obj1.copy()

        # Verify copy has same values
        assert obj2.get_field("amount") == 150.0

        # Mutate original
        obj1.set_field("amount", 200.0)

        # Copy should not be affected (shallow copy for primitives)
        assert obj2.get_field("amount") == 150.0

    def test_object_instance_repr(self):
        """ObjectInstance has proper repr"""
        udt = UserDefinedType("Point")
        udt.add_field(Field("x", BuiltinType(BuiltinTypeKind.FLOAT), 0.0))
        udt.add_field(Field("y", BuiltinType(BuiltinTypeKind.FLOAT), 0.0))

        obj = ObjectInstance(udt)
        obj.set_field("x", 10.0)
        obj.set_field("y", 20.0)

        repr_str = repr(obj)
        assert "Point" in repr_str
        assert "x=10.0" in repr_str or "x = 10.0" in repr_str


class TestIntegration:
    """Integration tests for type system"""

    def test_multiple_instances_independent(self):
        """Multiple instances of same type are independent"""
        udt = UserDefinedType("Trade")
        udt.add_field(Field("price", BuiltinType(BuiltinTypeKind.FLOAT), 0.0))

        obj1 = ObjectInstance(udt)
        obj2 = ObjectInstance(udt)

        obj1.set_field("price", 100.0)
        obj2.set_field("price", 200.0)

        # Each object has independent state
        assert obj1.get_field("price") == 100.0
        assert obj2.get_field("price") == 200.0

    def test_nested_types(self):
        """Can create instances with user-defined types as fields"""
        # Create inner type
        inner_udt = UserDefinedType("Point")
        inner_udt.add_field(Field("x", BuiltinType(BuiltinTypeKind.FLOAT), 0.0))

        # Create outer type that references inner
        outer_udt = UserDefinedType("Line")
        outer_udt.add_field(Field("start", inner_udt, None))

        # Create instances
        inner_obj = ObjectInstance(inner_udt)
        inner_obj.set_field("x", 10.0)

        outer_obj = ObjectInstance(outer_udt)
        outer_obj.set_field("start", inner_obj)

        # Verify nested access
        start_point = outer_obj.get_field("start")
        assert start_point.get_field("x") == 10.0
