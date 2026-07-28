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

from __future__ import annotations

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.builtins.drawing import Box
from pynescript.ast.evaluator.builtins.drawing import Label
from pynescript.ast.evaluator.builtins.drawing import Line
from pynescript.ast.evaluator.builtins.drawing import LineFill
from pynescript.ast.evaluator.builtins.drawing import Polyline
from pynescript.ast.evaluator.builtins.drawing import Table
from pynescript.ast.evaluator.builtins.matrix import Matrix
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance


_MATRIX_INDEX_DIMENSIONS = 2

# Drawing instance → namespace for method dispatch (``la.get_text()`` → ``label.get_text``).
_DRAWING_METHOD_NS: dict[type, str] = {
    Label: "label",
    Line: "line",
    Box: "box",
    Table: "table",
    Polyline: "polyline",
    LineFill: "linefill",
}

# Zero-arg series resolved as bare names (not callables that take arguments).
# Time components (year/month/…) are dual-use: bare series *and* year(time).
# Bare form is handled here; call form is early-dispatched in visit_Call.
# ``na`` is dual-use too: bare value (None) and ``na(x)`` predicate — call form
# is early-dispatched in visit_Call so bare resolution here only covers ``= na``.
_BARE_SERIES_BUILTINS = frozenset(
    {
        "na",
        "last_bar_index",
        "last_bar_time",
        "bid",
        "ask",
        "year",
        "month",
        "dayofmonth",
        "dayofweek",
        "hour",
        "minute",
        "second",
        "time_close",
        "time_tradingday",
        "weekofyear",
    }
)


def ast_qualified_name(expr: ast.AST) -> str | None:
    """Build ``a.b.c`` from Attribute/Name AST nodes without evaluating values.

    Critical for strategy/request builtins: intermediate names like
    ``strategy.opentrades`` are zero-arg series variables; evaluating them
    while resolving ``strategy.opentrades.entry_price(...)`` would yield an
    int and break the longer qualified path.
    """
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = ast_qualified_name(expr.value)
        if base is None:
            return None
        return f"{base}.{expr.attr}"
    return None


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
        # Hot path: single dict lookup for bar-mode series (close/open/…) and locals.
        # Prefer ``.get`` + sentinel over ``in`` + ``[]`` (one hash vs two).
        name = node.id
        ctx = self.context
        try:
            return ctx[name]
        except KeyError:
            pass
        # Bare-name series builtins only (not functions like strategy/indicator that take args)
        if name in _BARE_SERIES_BUILTINS and self._is_registered_builtin(name):
            return self._call_builtin(name, [])
        # Return the name as a string if not in context - allows for lazy evaluation
        return name

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
        # AST-based qualified path (does not evaluate intermediates)
        qualified_name = ast_qualified_name(node)

        # Fast path: exact context key (e.g. "strategy.position_size")
        if qualified_name and qualified_name in self.context:
            return self.context[qualified_name]

        # Zero-arg builtins / series vars (strategy.long, strategy.position_size, …)
        # Prefer this BEFORE evaluating intermediates so nested paths like
        # strategy.opentrades.entry_price stay intact for call dispatch.
        if qualified_name and self._is_registered_builtin(qualified_name):
            return self._call_builtin(qualified_name, [])

        # Evaluate the base value (left side of dot operator) for objects
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
                # Prefer multi-dispatch free function when overloads exist
                # (Console: many ``log(terminal, T)`` / ``tostring`` variants).
                # UDT._method_defs only keeps the last method of a given name.
                ext = self.context.get(node.attr) if hasattr(self, "context") else None
                if callable(ext) and getattr(ext, "__pine_overloads__", None):
                    return ("_ext_method", value, node.attr)
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

        # Array instance methods: mark for dispatch as array.<method>(self, ...)
        # Prefer the live list object (mutators need the same identity).
        receiver = value
        if not isinstance(receiver, list) and hasattr(value, "history"):
            hist = getattr(value, "history", None)
            if isinstance(hist, list):
                # history is most-recent-first; reverse for chronological array
                try:
                    receiver = list(reversed(hist))
                except Exception:
                    receiver = value
        if isinstance(receiver, list):
            array_qual = f"array.{node.attr}"
            if self._is_registered_builtin(array_qual):  # type: ignore[attr-defined]
                return ("_array_method", receiver, node.attr)

        # Drawing instance methods: ``la.get_text()`` → ``label.get_text(la)``
        # Exact type lookup (drawing classes are concrete; avoids isinstance chain).
        drawing_ns = _DRAWING_METHOD_NS.get(type(value))
        if drawing_ns is not None:
            drawing_qual = f"{drawing_ns}.{node.attr}"
            if self._is_registered_builtin(drawing_qual):  # type: ignore[attr-defined]
                return ("_ns_method", value, drawing_qual)

        # Matrix instance methods: ``m.rows()`` → ``matrix.rows(m)``
        if type(value) is Matrix or isinstance(value, Matrix):
            matrix_qual = f"matrix.{node.attr}"
            if self._is_registered_builtin(matrix_qual):  # type: ignore[attr-defined]
                return ("_ns_method", value, matrix_qual)

        # Standalone ``method foo(Type this, ...)`` stored as free function ``foo``:
        # ``x.foo(...)`` → bind receiver as first arg.
        # Only match callables tagged as Pine methods — never ordinary functions
        # that happen to share a name (``update()`` vs ``zigZag.update()``).
        #
        # Receiver may be ``na`` (None) or a primitive (string/color). Libraries
        # like Console use ``x.isset(fallback)`` while ``x`` is still na
        # (``this.__theme.isset(theme.new())``). Skipping None previously
        # surfaced as ``Unknown built-in function: '__theme.isset'``.
        ext = self.context.get(node.attr) if hasattr(self, "context") else None
        if (
            callable(ext)
            and not isinstance(ext, type)
            and getattr(ext, "__pine_method__", False)
        ):
            # ObjectInstance already handled via UDT methods / fields above.
            if not isinstance(value, ObjectInstance):
                return ("_ext_method", value, node.attr)

        # Fallback: try getattr for plain Python objects (Syminfo, Timeframe, etc.)
        # None has no attributes worth reflecting.
        if value is not None and hasattr(value, node.attr):
            return getattr(value, node.attr)

        # Last resort: return qualified name string for later resolution
        return qualified_name if qualified_name is not None else f"{value}.{node.attr}"

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

        # Pine coerces float offsets (e.g. ``depth / 2``) to int for series[i]
        if isinstance(slice_, float):
            if slice_ != slice_:  # NaN
                return None
            slice_ = int(slice_)
        elif isinstance(slice_, bool):
            # bool is int subclass; keep 0/1 but avoid treating as generic truthy
            slice_ = int(slice_)

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
        # When subscripting a non-collection type (scalar), match PineScript
        # semantics: series[0] = current (the scalar itself), series[offset>0]
        # with no history returns None (PineScript 'na').
        if isinstance(slice_, int) and slice_ >= 0:
            return None if slice_ > 0 else value
        # Negative indexing not supported in PineScript
        if isinstance(slice_, int) and slice_ < 0:
            msg = "Negative indices not supported in PineScript"
            raise ValueError(msg)
        value_type = type(value)
        slice_type = type(slice_)
        msg = f"Subscript not supported for {value_type} with {slice_type}"
        raise ValueError(msg)
