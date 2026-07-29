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

"""Pine Script type model (qualifiers, builtins, UDTs, registry).

Used by the evaluator and tooling to represent ``const``/``simple``/``series``/
``input`` qualifiers, built-in kinds, collections (``array``/``matrix``/``map``),
user-defined types, and runtime UDT instances. Not star-exported from
:mod:`pynescript.ast`; import this module directly.

Public highlights: :class:`Type`, :class:`BuiltinType`, :class:`UserDefinedType`,
:class:`TypeRegistry`, :class:`ObjectInstance`, :class:`MethodResolver`, and
factories :func:`int_type`, :func:`float_type`, :func:`bool_type`,
:func:`string_type`, :func:`color_type`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class TypeQualifier(Enum):
    """Pine type qualifier (const / simple / series / input)."""

    CONST = "const"  # Constant, known at compile time
    SIMPLE = "simple"  # Simple, not changing per bar
    SERIES = "series"  # Series, can change per bar
    INPUT = "input"  # Input parameter from user


class BuiltinTypeKind(Enum):
    """Enumeration of built-in scalar type names."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    COLOR = "color"
    NA = "na"
    ENUM = "enum"  # Pine v6 enum type integration


class Type:
    """Base for all modeled Pine types (name + optional qualifier)."""

    def __init__(self, name: str, qualifier: TypeQualifier | None = None) -> None:
        self.name = name
        self.qualifier = qualifier

    def __str__(self) -> str:
        if self.qualifier:
            return f"{self.qualifier.value} {self.name}"
        return self.name

    def is_compatible_with(self, other: Type) -> bool:
        """Return True if this type is assignment-compatible with *other*.

        Default: only equal :class:`BuiltinType` instances are compatible.
        """
        if isinstance(other, BuiltinType):
            return self == other
        return False


class BuiltinType(Type):
    """Built-in scalar type keyed by :class:`BuiltinTypeKind`."""

    def __init__(
        self,
        kind: BuiltinTypeKind,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        name = kind.value
        super().__init__(name, qualifier)
        self.kind = kind


class ArrayType(Type):
    """``array<T>`` collection type."""

    def __init__(
        self,
        element_type: Type,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        self.element_type = element_type
        typename = f"array<{element_type.name}>"
        super().__init__(typename, qualifier)


class MatrixType(Type):
    """``matrix<T>`` collection type."""

    def __init__(
        self,
        element_type: Type,
        qualifier: TypeQualifier | None = None,
    ) -> None:
        self.element_type = element_type
        typename = f"matrix<{element_type.name}>"
        super().__init__(typename, qualifier)


class MapType(Type):
    """``map<K, V>`` collection type."""

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
    """Field of a user-defined type (name, type, default, optional ``varip``)."""

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
    """Named method signature: parameters and optional return type."""

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
    """User-defined type (UDT) with fields and methods."""

    def __init__(self, name: str, qualifier: TypeQualifier | None = None) -> None:
        super().__init__(name, qualifier)
        self.fields: dict[str, Field] = {}
        self.methods: dict[str, MethodSignature] = {}
        self.is_exported = False

    def add_field(self, field: Field) -> None:
        """Register *field* under its name (overwrites same name)."""
        self.fields[field.name] = field

    def get_field(self, name: str) -> Field | None:
        """Return the field named *name*, or ``None``."""
        return self.fields.get(name)

    def add_method(self, method: MethodSignature) -> None:
        """Register *method* under its name (overwrites same name)."""
        self.methods[method.name] = method

    def get_method(self, name: str) -> MethodSignature | None:
        """Return the method named *name*, or ``None``."""
        return self.methods.get(name)

    def __repr__(self) -> str:
        fields_str = "\n  ".join(str(f) for f in self.fields.values())
        return f"type {self.name}\n  {fields_str}"


class ObjectInstance:
    """Runtime instance of a :class:`UserDefinedType`."""

    def __init__(self, udt: UserDefinedType) -> None:
        self.udt = udt
        self.fields: dict[str, Any] = {}

        # Initialize fields with their default values
        for field_name, field_def in udt.fields.items():
            self.fields[field_name] = field_def.default_value

    def get_field(self, name: str) -> Any:
        """Return the value of field *name*.

        Raises:
            AttributeError: If *name* is not a field of the UDT.
        """
        if name not in self.udt.fields:
            msg = f"Field '{name}' not found on type '{self.udt.name}'"
            raise AttributeError(msg)
        return self.fields.get(name)

    def set_field(self, name: str, value: Any) -> None:
        """Set field *name* to *value*.

        Raises:
            AttributeError: If *name* is not a field of the UDT.
        """
        if name not in self.udt.fields:
            msg = f"Field '{name}' not found on type '{self.udt.name}'"
            raise AttributeError(msg)
        self.fields[name] = value

    def copy(self) -> ObjectInstance:
        """Return a shallow copy (field dict copied; values shared)."""
        new_instance = ObjectInstance(self.udt)
        new_instance.fields = self.fields.copy()
        return new_instance

    def __repr__(self) -> str:
        fields_str = ", ".join(f"{k}={v}" for k, v in self.fields.items())
        return f"{self.udt.name}({fields_str})"


class TypeRegistry:
    """Name → type map for builtins and registered UDTs in a script."""

    def __init__(self) -> None:
        self.types: dict[str, UserDefinedType] = {}
        self._builtin_types = self._init_builtin_types()

    @staticmethod
    def _init_builtin_types() -> dict[str, BuiltinType]:
        """Return the default built-in name → :class:`BuiltinType` map."""
        return {
            "int": BuiltinType(BuiltinTypeKind.INT),
            "float": BuiltinType(BuiltinTypeKind.FLOAT),
            "bool": BuiltinType(BuiltinTypeKind.BOOL),
            "string": BuiltinType(BuiltinTypeKind.STRING),
            "color": BuiltinType(BuiltinTypeKind.COLOR),
            "na": BuiltinType(BuiltinTypeKind.NA),
            "enum": BuiltinType(BuiltinTypeKind.ENUM),
        }

    def register_type(self, udt: UserDefinedType) -> None:
        """Register *udt* under ``udt.name`` (overwrites same name)."""
        self.types[udt.name] = udt

    def get_type(self, name: str) -> Type | None:
        """Look up *name* among builtins first, then registered UDTs."""
        if name in self._builtin_types:
            return self._builtin_types[name]
        return self.types.get(name)

    def is_builtin_type(self, name: str) -> bool:
        """True if *name* is a built-in type name."""
        return name in self._builtin_types

    def is_user_defined_type(self, name: str) -> bool:
        """True if *name* is a registered UDT."""
        return name in self.types

    def __repr__(self) -> str:
        return f"TypeRegistry({len(self.types)} user types)"


class MethodResolver:
    """Resolve method names on UDT instances (including ``.new`` / ``.copy``)."""

    def __init__(self, type_registry: TypeRegistry) -> None:
        self.type_registry = type_registry

    def resolve_method(self, instance: ObjectInstance, method_name: str, args: list[Any]) -> Any:
        """Resolve *method_name* on *instance*.

        Built-ins: ``new`` constructs an :class:`ObjectInstance` (positional
        args map to field order); ``copy`` returns a shallow copy. Otherwise
        returns the registered :class:`MethodSignature`.

        Raises:
            AttributeError: If the method is not defined on the UDT.
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
        """Construct a UDT instance; apply positional *args* to fields in order."""
        instance = ObjectInstance(udt)

        # Set fields from positional arguments
        field_names = list(udt.fields.keys())
        for i, arg in enumerate(args):
            if i < len(field_names):
                instance.set_field(field_names[i], arg)

        return instance

    @staticmethod
    def _handle_copy(instance: ObjectInstance) -> ObjectInstance:
        """Return ``instance.copy()`` for the ``.copy()`` method."""
        return instance.copy()


# Module-level factory functions for common types
def int_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Return a ``int`` :class:`BuiltinType` with optional *qualifier*."""
    return BuiltinType(BuiltinTypeKind.INT, qualifier)


def float_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Return a ``float`` :class:`BuiltinType` with optional *qualifier*."""
    return BuiltinType(BuiltinTypeKind.FLOAT, qualifier)


def bool_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Return a ``bool`` :class:`BuiltinType` with optional *qualifier*."""
    return BuiltinType(BuiltinTypeKind.BOOL, qualifier)


def string_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Return a ``string`` :class:`BuiltinType` with optional *qualifier*."""
    return BuiltinType(BuiltinTypeKind.STRING, qualifier)


def color_type(qualifier: TypeQualifier | None = None) -> BuiltinType:
    """Return a ``color`` :class:`BuiltinType` with optional *qualifier*."""
    return BuiltinType(BuiltinTypeKind.COLOR, qualifier)
