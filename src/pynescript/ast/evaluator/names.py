# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.builtins.matrix import Matrix
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance


_MATRIX_INDEX_DIMENSIONS = 2


class NameEvaluator:
    """Evaluates name-related AST nodes: identifiers, attributes, subscripts.

    Handles resolution of:
    - Simple names (variables, functions) from context
    - Qualified names (module.attribute) with fallback to context lookup
    - User-Defined Type (UDT) fields and method calls
    - Enum member access
    - Subscript operations with PineScript-specific indexing semantics
    """

    def visit_Name(self: EvaluatorProtocol, node: ast.Name) -> Any:
        """Evaluate a simple name node (variable or identifier reference).

        Args:
            node: The Name AST node containing the identifier string

        Returns:
            The value from context if the name is defined, otherwise returns the name string itself
            (allowing it to be resolved as a string literal or builtin reference)
        """
        # Check if the name is defined in the current context (variables, functions, classes, etc.)
        if node.id in self.context:
            return self.context[node.id]
        # Return the name as a string if not in context - allows for lazy evaluation
        return node.id

    def visit_Attribute(self: EvaluatorProtocol, node: ast.Attribute) -> Any:
        """Evaluate an attribute access node (e.g., obj.attr, module.function).

        Handles multiple attribute resolution strategies:
        1. Direct context lookup for qualified names
        2. UDT (User-Defined Type) field and method access with binding
        3. Enum member access with validation
        4. Fallback to qualified name string for module-level lookups

        Args:
            node: The Attribute AST node with value and attr properties

        Returns:
            The attribute value, a bound method marker, or a qualified name string
        """
        # Build qualified name for direct context lookup (e.g., "module.func")
        qualified_name = f"{self.visit(node.value)}.{node.attr}"
        # Fast path: check if qualified name is directly in context
        if qualified_name in self.context:
            return self.context[qualified_name]

        # Evaluate the base value (left side of dot operator)
        value = self.visit(node.value)

        # Imported library module: alias.member (export const / export f)
        if isinstance(value, LibraryModule):
            if node.attr in value.exports:
                return value.exports[node.attr]
            self._error(f"Library '{value.title}' has no exported member '{node.attr}'")

        # Handle UDT object field/method access
        if isinstance(value, ObjectInstance):
            # UDT methods are looked up first (method has priority over field)
            if value.udt.get_method(node.attr):
                # Return a bound method marker - tuple of (marker, instance, method_name)
                # This will be interpreted by call evaluation to bind the instance
                return ("_method_call", value, node.attr)
            # Otherwise try to get field (property or attribute of the UDT instance)
            return value.get_field(node.attr)

        # Handle Enum member access - value is a dict of enum members
        if isinstance(value, dict):
            member_name = node.attr
            # Check if the member exists in the enum dictionary
            if member_name in value:
                return value[member_name]
            # Enum member not found - raise error
            self._error(f"Enum member '{member_name}' not found in enum.")

        # Handle string reference to enum (e.g., accessing "EnumName.member")
        # where value is the string name of an enum
        if isinstance(value, str) and value in self.context:
            enum_def = self.context[value]
            # If the referenced value is indeed an enum (dict), look up member
            if isinstance(enum_def, dict):
                member_name = node.attr
                # Check if member exists in the enum definition
                if member_name in enum_def:
                    return enum_def[member_name]
                # Enum member not found - raise error with context
                self._error(f"Enum member '{member_name}' not found in enum '{value}'.")

        # Fallback: return qualified name string for later resolution
        # (e.g., for module-level attributes not yet resolved)
        # Special case for zero-arg registered builtins like strategy.long / strategy.short
        # (see plan subtask 1.1.2 / 1.3)
        if self._is_registered_builtin(qualified_name):
            return self._call_builtin(qualified_name, [])

        return qualified_name

    def visit_Subscript(self: EvaluatorProtocol, node: ast.Subscript) -> Any:
        """Evaluate a subscript/index access node (e.g., series[index], array[0]).

        PineScript has unique indexing semantics where series[0] refers to the current value,
        series[1] refers to the previous value, etc. (reverse chronological order).

        Args:
            node: The Subscript AST node with value and slice properties

        Returns:
            The indexed value, or None (na) if out of bounds (per PineScript spec)

        Raises:
            ValueError: If negative indices are used (not supported in PineScript)
            NotImplementedError: If subscripting is not supported for the value type
        """
        # Evaluate the collection being indexed (e.g., array, series)
        value = self.visit(node.value)
        # Evaluate the index/slice expression
        slice_ = self.visit(node.slice) if node.slice else None  # type: ignore[arg-type]

        # Handle Matrix indexing: m[row, col]
        if isinstance(value, Matrix):
            # slice_ should be a list [row, col] (from Tuple evaluation)
            if isinstance(slice_, list) and len(slice_) == _MATRIX_INDEX_DIMENSIONS:
                return value[(slice_[0], slice_[1])]
            msg = f"Invalid matrix index: {slice_}. Expected [row, col]."
            raise ValueError(msg)

        # Handle list/array indexing with integer indices
        if isinstance(value, list) and isinstance(slice_, int):
            # PineScript doesn't support negative indices (backwards indexing)
            if slice_ < 0:
                msg = "Negative indices not supported in PineScript"
                raise ValueError(msg)
            # Convert PineScript index to Python index:
            # PineScript: series[0] = current (latest), series[1] = previous
            # Python: list[0] = first (oldest), list[-1] = last (latest)
            # So series[i] -> list[-(i+1)]
            index = -(slice_ + 1)
            # Check bounds and return None (PineScript 'na') for out-of-bounds access
            if abs(index) > len(value):
                return None  # PineScript returns na for out of bounds
            return value[index]
        elif hasattr(value, "__getitem__"):
            try:
                return value[slice_]
            except Exception as e:
                msg = f"Subscript error for {type(value).__name__} with index {slice_}: {e}"
                raise ValueError(msg) from e
        else:
            # Subscripting not supported for non-list or non-integer index types
            value_type = type(value)
            slice_type = type(slice_)
            msg = f"Subscript not supported for {value_type} with {slice_type}"
            raise ValueError(msg)
