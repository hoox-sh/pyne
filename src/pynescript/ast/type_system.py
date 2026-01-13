# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""
Pine Script v6 Type System Implementation

This module provides the core type system for Pine Script v6.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class TypeQualifier(Enum):
    """Type qualifiers in Pine Script"""

    CONST = "const"  # Constant, known at compile time
    SIMPLE = "simple"  # Simple, not changing per bar
    SERIES = "series"  # Series, can change per bar
    INPUT = "input"  # Input parameter from user


class BuiltinTypeKind(Enum):
    """Built-in type kinds"""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    COLOR = "color"
    NA = "na"


class Type:
    """Base class for all Pine Script types"""

    def __init__(self, name: str, qualifier: TypeQualifier | None = None) -> None:
        self.name = name
        self.qualifier = qualifier

    def __str__(self) -> str:
        if self.qualifier:
            return f"{self.qualifier.value} {self.name}"
        return self.name

    def is_compatible_with(self, other: Type) -> bool:
        """Check if this type is compatible with another type"""
        if isinstance(other, BuiltinType):
            return self == other
        return False


class BuiltinType(Type):
    """Represents a built-in Pine Script type"""

    def __init__(
        self,
        kind: BuiltinTypeKind,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        name = kind.value
        super().__init__(name, qualifier)
        self.kind = kind


class ArrayType(Type):
    """Represents an array type: array<T>"""

    def __init__(
        self,
        element_type: Type,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        self.element_type = element_type
        typename = f"array<{element_type.name}>"
        super().__init__(typename, qualifier)


class MatrixType(Type):
    """Represents a matrix type: matrix<T>"""

    def __init__(
        self,
        element_type: Type,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        self.element_type = element_type
        typename = f"matrix<{element_type.name}>"
        super().__init__(typename, qualifier)


class MapType(Type):
    """Represents a map type: map<K, V>"""

    def __init__(
        self,
        key_type: Type,
        value_type: Type,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        self.key_type = key_type
        self.value_type = value_type
        typename = f"map<{key_type.name}, {value_type.name}>"
        super().__init__(typename, qualifier)


class Field:
    """Represents a field in a user-defined type"""

    def __init__(
        self,
        name: str,
        field_type: Type,
        default_value: Any | None = None,
        varip: bool = False,
    ) -> None:
        self.name = name
        self.field_type = field_type
        self.default_value = default_value
        self.varip = varip

    def __repr__(self) -> str:
        varip_str = "varip " if self.varip else ""
        if self.default_value is not None:
            default_str = f" = {self.default_value}"
        else:
            default_str = ""
        return f"{varip_str}{self.field_type}{default_str} {self.name}"


class MethodSignature:
    """Represents a method signature"""

    def __init__(
        self,
        name: str,
        parameters: list[tuple[str, Type]],
        return_type: Type | None = None,
        is_builtin: bool = False,
    ) -> None:
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.is_builtin = is_builtin

    def __repr__(self) -> str:
        params = ", ".join(f"{p[1]} {p[0]}" for p in self.parameters)
        ret = f" -> {self.return_type}" if self.return_type else ""
        return f"method {self.name}({params}){ret}"


class UserDefinedType(Type):
    """Represents a user-defined type (UDT) in Pine Script"""

    def __init__(self, name: str, qualifier: TypeQualifier | None = None) -> None:
        super().__init__(name, qualifier)
        self.fields: dict[str, Field] = {}
        self.methods: dict[str, MethodSignature] = {}
        self.is_exported = False

    def add_field(self, field: Field) -> None:
        """Add a field to this UDT"""
        self.fields[field.name] = field

    def get_field(self, name: str) -> Field | None:
        """Get a field by name"""
        return self.fields.get(name)

    def add_method(self, method: MethodSignature) -> None:
        """Add a method to this UDT"""
        self.methods[method.name] = method

    def get_method(self, name: str) -> MethodSignature | None:
        """Get a method by name"""
        return self.methods.get(name)

    def __repr__(self) -> str:
        fields_str = "\n  ".join(str(f) for f in self.fields.values())
        return f"type {self.name}\n  {fields_str}"


class ObjectInstance:
    """Runtime representation of a UDT instance"""

    def __init__(self, udt: UserDefinedType) -> None:
        self.udt = udt
        self.fields: dict[str, Any] = {}

        # Initialize fields with their default values
        for field_name, field_def in udt.fields.items():
            self.fields[field_name] = field_def.default_value

    def get_field(self, name: str) -> Any:
        """Get the value of a field"""
        if name not in self.udt.fields:
            msg = f"Field '{name}' not found on type '{self.udt.name}'"
            raise AttributeError(msg)
        return self.fields.get(name)

    def set_field(self, name: str, value: Any) -> None:
        """Set the value of a field"""
        if name not in self.udt.fields:
            msg = f"Field '{name}' not found on type '{self.udt.name}'"
            raise AttributeError(msg)
        self.fields[name] = value

    def copy(self) -> ObjectInstance:
        """Create a shallow copy of this object instance"""
        new_instance = ObjectInstance(self.udt)
        new_instance.fields = self.fields.copy()
        return new_instance

    def __repr__(self) -> str:
        fields_str = ", ".join(f"{k}={v}" for k, v in self.fields.items())
        return f"{self.udt.name}({fields_str})"


class TypeRegistry:
    """Registry for all user-defined types in a script"""

    def __init__(self) -> None:
        self.types: dict[str, UserDefinedType] = {}
        self._builtin_types = self._init_builtin_types()

    @staticmethod
    def _init_builtin_types() -> dict[str, BuiltinType]:
        """Initialize built-in types"""
        return {
            "int": BuiltinType(BuiltinTypeKind.INT),
            "float": BuiltinType(BuiltinTypeKind.FLOAT),
            "bool": BuiltinType(BuiltinTypeKind.BOOL),
            "string": BuiltinType(BuiltinTypeKind.STRING),
            "color": BuiltinType(BuiltinTypeKind.COLOR),
            "na": BuiltinType(BuiltinTypeKind.NA),
        }

    def register_type(self, udt: UserDefinedType) -> None:
        """Register a user-defined type"""
        self.types[udt.name] = udt

    def get_type(self, name: str) -> Type | None:
        """Get a type by name (checks built-ins first, then UDTs)"""
        if name in self._builtin_types:
            return self._builtin_types[name]
        return self.types.get(name)

    def is_builtin_type(self, name: str) -> bool:
        """Check if a name refers to a built-in type"""
        return name in self._builtin_types

    def is_user_defined_type(self, name: str) -> bool:
        """Check if a name refers to a user-defined type"""
        return name in self.types

    def __repr__(self) -> str:
        return f"TypeRegistry({len(self.types)} user types)"


class MethodResolver:
    """Resolves method calls on UDT instances"""

    def __init__(self, type_registry: TypeRegistry) -> None:
        self.type_registry = type_registry

    def resolve_method(self, instance: ObjectInstance, method_name: str, args: list[Any]) -> Any:
        """
        Resolve and prepare a method call on a UDT instance.

        Args:
            instance: The object instance
            method_name: Name of the method
            args: Arguments to pass to the method

        Returns:
            The method signature and prepared context for execution

        Raises:
            AttributeError: If method not found on type
        """
        # Check for built-in methods first
        if method_name == "new":
            return self._handle_new(instance.udt, args)
        elif method_name == "copy":
            return self._handle_copy(instance)

        # Check for user-defined methods
        method_sig = instance.udt.get_method(method_name)
        if not method_sig:
            msg = f"Method '{method_name}' not found on type '{instance.udt.name}'"
            raise AttributeError(msg)

        return method_sig

    @staticmethod
    def _handle_new(udt: UserDefinedType, args: list[Any]) -> ObjectInstance:
        """Handle .new() constructor"""
        instance = ObjectInstance(udt)

        # Set fields from positional arguments
        field_names = list(udt.fields.keys())
        for i, arg in enumerate(args):
            if i < len(field_names):
                instance.set_field(field_names[i], arg)

        return instance

    @staticmethod
    def _handle_copy(instance: ObjectInstance) -> ObjectInstance:
        """Handle .copy() method"""
        return instance.copy()


# Module-level factory functions for common types
def int_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Create an int type"""
    return BuiltinType(BuiltinTypeKind.INT, qualifier)


def float_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Create a float type"""
    return BuiltinType(BuiltinTypeKind.FLOAT, qualifier)


def bool_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Create a bool type"""
    return BuiltinType(BuiltinTypeKind.BOOL, qualifier)


def string_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Create a string type"""
    return BuiltinType(BuiltinTypeKind.STRING, qualifier)


def color_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Create a color type"""
    return BuiltinType(BuiltinTypeKind.COLOR, qualifier)
