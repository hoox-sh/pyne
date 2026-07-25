# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.builtins.declarations import ScriptDeclaration
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.helper import parse as parse_pine
from pynescript.ast.type_system import BuiltinType
from pynescript.ast.type_system import BuiltinTypeKind
from pynescript.ast.type_system import Field
from pynescript.ast.type_system import MethodSignature
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import Type
from pynescript.ast.type_system import TypeRegistry
from pynescript.ast.type_system import UserDefinedType


class BreakLoop(Exception):
    """Signal to break out of a loop."""

    pass


class ContinueLoop(Exception):
    """Signal to continue to the next iteration of a loop."""

    pass


class StatementEvaluator:
    """Evaluates statement nodes: assignments, function definitions, type definitions, and control flow.

    Handles:
    - Variable assignments and augmented assignments (+=, -=, etc.)
    - Function and method definitions
    - User-defined type (UDT) definitions with fields and methods
    - Control flow (if/else, loops)
    - Return statements
    """

    context: dict[str, Any]
    type_registry: TypeRegistry

    def visit_Script(self, node: ast.Script):
        """Execute all statements in a script.

        Tracks ``library(...)`` declarations and registers exported members
        (``export const``, ``export f() => ...``) into the library registry.

        Args:
            node: The Script node containing the body of statements
        """
        # Fresh library-export buffer for this script evaluation
        self._pending_library_exports = {}  # type: ignore[attr-defined]
        self._active_library = None  # type: ignore[attr-defined]
        last: Any = None
        for stmt in node.body:
            last = self.visit(stmt)  # type: ignore[attr-defined]
            # Detect library("Title") declaration from Expr(Call(...))
            if isinstance(last, ScriptDeclaration) and last.script_type == "library":
                self._active_library = LibraryModule(title=str(last.title))  # type: ignore[attr-defined]
        self._finalize_library_registration()
        return last

    def _finalize_library_registration(self) -> None:
        """If this script was a library, register collected exports."""
        active: LibraryModule | None = getattr(self, "_active_library", None)
        if active is None:
            return
        pending: dict[str, Any] = getattr(self, "_pending_library_exports", {})
        active.exports.update(pending)
        self._library_registry.register(active)  # type: ignore[attr-defined]
        self._active_library = None  # type: ignore[attr-defined]
        self._pending_library_exports = {}  # type: ignore[attr-defined]

    def _register_export(self, name: str, value: Any) -> None:
        """Record an exported member while evaluating a library script."""
        pending: dict[str, Any] = getattr(self, "_pending_library_exports", None)  # type: ignore[attr-defined]
        if pending is None:
            self._pending_library_exports = {}  # type: ignore[attr-defined]
            pending = self._pending_library_exports  # type: ignore[attr-defined]
        pending[name] = value

    def visit_Assign(self, node: ast.Assign):
        """Evaluate an assignment statement.

        Assigns a value to a variable in the current context.

        ``var`` / ``varip`` declarations (``node.mode == Var/VarIp``) are
        only executed on the first bar (``bar_index == 0``). On subsequent
        bars the declaration is skipped so the variable retains its value
        across bars — the canonical Pine Script ``var`` semantics.

        Args:
            node: The Assign node with target, value, and optional mode

        Raises:
            ValueError: If assignment target is not a simple name
        """
        # -- Handle var / varip: only assign on first bar ------------------
        first_bar = self.context.get("bar_index", 0) == 0  # type: ignore[attr-defined]
        is_var = node.mode is not None and isinstance(node.mode, (ast.Var, ast.VarIp))
        is_const = node.mode is not None and isinstance(node.mode, ast.Const)  # v6 const decl

        if is_var:
            if isinstance(node.target, ast.Name):
                name: str = node.target.id  # type: ignore[attr-defined]
                if first_bar:
                    if node.value:
                        value = self.visit(node.value)  # type: ignore[attr-defined]
                        self.context[name] = value  # type: ignore[attr-defined]
                    self._var_declarations.add(name)  # type: ignore[attr-defined]
                else:
                    pass
                return
            msg = f"Unsupported var/varip target: {type(node.target)}"
            self._error(msg)  # type: ignore[attr-defined]
            return

        if is_const:
            # v6: const always initializes (no re-init like var)
            if node.value and isinstance(node.target, ast.Name):
                value = self.visit(node.value)  # type: ignore[attr-defined]
                self.context[node.target.id] = value  # type: ignore[attr-defined]
            return

        # -- Regular assignment (also covers `const T name = expr` type-qualifier form)
        if node.value:
            value = self.visit(node.value)  # type: ignore[attr-defined]
            if isinstance(node.target, ast.Name):
                self.context[node.target.id] = value  # type: ignore[attr-defined]
                # June 2025: export const / export typed vars from libraries
                if getattr(node, "export", None):
                    self._register_export(node.target.id, value)
            elif isinstance(node.target, ast.Tuple):
                # Tuple unpacking: [a, b, c] = expression
                elts = node.target.elts
                if not isinstance(value, (list, tuple)):
                    msg = f"Cannot unpack {type(value).__name__} value"
                    self._error(msg)  # type: ignore[attr-defined]
                    return
                for target_node, val in zip(elts, value, strict=False):
                    if isinstance(target_node, ast.Name):
                        self.context[target_node.id] = val
                    else:
                        msg = f"Unsupported unpack target: {type(target_node)}"
                        self._error(msg)  # type: ignore[attr-defined]
                        return
            else:
                msg = f"Unsupported assignment target: {type(node.target)}"
                self._error(msg)  # type: ignore[attr-defined]

    def visit_ReAssign(self, node: ast.ReAssign):
        """Handle reassignment (``x := x + 1``).

        Evaluates the right-hand side and stores the result in the target
        variable. This is the Pine Script ``:=`` operator, distinct from
        ``AugAssign`` (``x += 1``).

        Args:
            node: The ReAssign node with target and value

        Raises:
            ValueError: If reassignment target is not a simple name
        """
        value = self.visit(node.value)  # type: ignore[attr-defined]
        if isinstance(node.target, ast.Name):
            self.context[node.target.id] = value  # type: ignore[attr-defined]
        else:
            msg = f"Unsupported reassignment target: {type(node.target)}"
            self._error(msg)  # type: ignore[attr-defined]

    def visit_AugAssign(self, node: ast.AugAssign):
        """Handle augmented assignment (e.g., obj.field := value).

        Modifies existing values in-place using operators like +=, -=, etc.

        Args:
            node: The AugAssign node with target, value, and operator
        """
        # Handle field mutation on UDT objects (obj.field := value)
        if isinstance(node.target, ast.Attribute):
            # Get the object being modified
            obj = self.visit(node.target.value)  # type: ignore[attr-defined]
            # If it's a UDT instance, set the field on the object
            if isinstance(obj, ObjectInstance):
                # Evaluate the new value
                value = self.visit(node.value)  # type: ignore[attr-defined]
                # Mutate the field directly
                obj.set_field(node.target.attr, value)
                return

        # Handle simple variable augmented assignment (x += 1, x -= 1, etc.)
        if isinstance(node.target, ast.Name):
            var_name = node.target.id
            if var_name in self.context:  # type: ignore[attr-defined]
                current = self.context[var_name]  # type: ignore[attr-defined]
                rhs = self.visit(node.value)  # type: ignore[attr-defined]
                from pynescript.ast.evaluator.expressions import (
                    _OPERATOR_ADD,
                    _OPERATOR_SUB,
                    _OPERATOR_MUL,
                    _OPERATOR_DIV,
                )

                _AUGOP_MAP: dict = {
                    ast.Add: _OPERATOR_ADD,
                    ast.Sub: _OPERATOR_SUB,
                    ast.Mult: _OPERATOR_MUL,
                    ast.Div: _OPERATOR_DIV,
                }
                op_fn = _AUGOP_MAP.get(type(node.op))
                if op_fn:
                    self.context[var_name] = op_fn(current, rhs)  # type: ignore[attr-defined]
                    return

        msg = f"Unsupported augmented assignment: {type(node.target)}"
        self._error(msg)  # type: ignore[attr-defined]

    def visit_TypeDef(self, node: ast.TypeDef):
        """Process a type definition and register it in the TypeRegistry"""
        type_name = node.name
        udt = UserDefinedType(type_name)
        udt.is_exported = bool(node.export)

        # Process field definitions and method definitions
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                # This is a field definition
                field_name = None
                field_type = None
                default_value = None
                varip = False

                if isinstance(stmt.target, ast.Name):
                    field_name = stmt.target.id

                # Extract type specification
                if stmt.type:
                    field_type = self._convert_type_spec_to_type(stmt.type)

                # Extract default value
                if stmt.value:
                    default_value = self.visit(stmt.value)  # type: ignore[attr-defined]

                # Check for varip modifier
                if stmt.mode and isinstance(stmt.mode, ast.VarIp):
                    varip = True

                if field_name and field_type:
                    field = Field(
                        name=field_name,
                        field_type=field_type,
                        default_value=default_value,
                        varip=varip,
                    )
                    udt.add_field(field)
            elif isinstance(stmt, ast.FunctionDef) and stmt.method:
                # This is a method definition
                # Store the method definition in the UDT
                method_name = stmt.name
                # Extract parameter types and names
                parameters = []
                for param in stmt.args:
                    if isinstance(param, ast.Param):
                        # Skip the THIS parameter (handled specially)
                        if param.name == "this":
                            continue
                        param_type: Type = (
                            self._convert_type_spec_to_type(param.type)
                            if param.type
                            else BuiltinType(BuiltinTypeKind.STRING)
                        )
                        parameters.append((param.name, param_type))

                method_sig = MethodSignature(
                    name=method_name,
                    parameters=parameters,
                    return_type=None,  # For now, we don't infer return types
                    is_builtin=False,
                )
                udt.add_method(method_sig)

                # Also store the actual method body for later execution
                # We'll store it as a special attribute on the UDT
                if not hasattr(udt, "_method_defs"):
                    udt._method_defs = {}  # type: ignore
                udt._method_defs[method_name] = stmt  # type: ignore

        # Register the type in the registry
        self.type_registry.register_type(udt)

        # Also store it in the context for backward compatibility
        self.context[type_name] = udt

        # Library export: type is accessible as alias.TypeName after import
        if getattr(node, "export", None):
            self._register_export(type_name, udt)

    def _convert_type_spec_to_type(self, type_spec):
        """Convert a type specification AST node to a Type object"""
        # For now, handle simple cases
        if isinstance(type_spec, ast.Name):
            type_name = type_spec.id
            # Try to get from registry first
            registered = self.type_registry.get_type(type_name)
            if registered:
                return registered
            # Fall back to built-in types
            type_map = {
                "int": BuiltinTypeKind.INT,
                "float": BuiltinTypeKind.FLOAT,
                "bool": BuiltinTypeKind.BOOL,
                "string": BuiltinTypeKind.STRING,
                "color": BuiltinTypeKind.COLOR,
            }
            if type_name in type_map:
                return BuiltinType(type_map[type_name])

        # For more complex types, we'd need to handle them here
        # For now, return a simple built-in type as fallback
        return BuiltinType(BuiltinTypeKind.STRING)

    def visit_EnumDef(self, node: ast.EnumDef):
        enum_name = node.name
        enum_members = {}
        for stmt in node.body:
            member_name = None
            value = None
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                member_name = stmt.target.id
                if stmt.value:
                    value = self.visit(stmt.value)  # type: ignore[attr-defined]
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Name):
                member_name = stmt.value.id
            else:
                msg = f"Unsupported statement in enum body: {type(stmt)}"
                self._error(msg)  # type: ignore[attr-defined]

            if member_name:
                if value is not None:
                    enum_members[member_name] = value
                else:
                    # Symbolic member for simple enums; access via Enum.member returns this
                    enum_members[member_name] = f"{enum_name}.{member_name}"

        # Store the enum definition (dict of members) in the context
        self.context[enum_name] = enum_members  # type: ignore[attr-defined]
        # Also register for qualified access if needed
        self.context[f"{enum_name}"] = enum_members  # type: ignore[attr-defined]

        # Library export: enum dict accessible as alias.EnumName after import
        if getattr(node, "export", None):
            self._register_export(enum_name, enum_members)

    def visit_Expr(self, node: ast.Expr):
        """Evaluate an expression statement."""
        return self.visit(node.value)  # type: ignore[attr-defined]

    def visit_While(self, node: ast.While):
        """Execute a while loop. v6 strict bool."""
        last_result = None
        while True:
            test_val = self.visit(node.test)  # type: ignore[attr-defined]
            if test_val is None:
                test_val = False
            if not bool(test_val):
                break
            result, should_break = self._execute_loop_body(node.body)
            if result is not None:
                last_result = result
            if should_break:
                break
        return last_result

    def visit_ForTo(self, node: ast.ForTo):
        """Execute a for-to loop (numeric range)."""
        target_name = node.target.id if isinstance(node.target, ast.Name) else None
        if not target_name:
            msg = "For loop target must be a name"
            self._error(msg)  # type: ignore[attr-defined]
            raise RuntimeError(msg)

        start = self.visit(node.start)  # type: ignore[attr-defined]
        step = self.visit(node.step) if node.step else 1  # type: ignore[attr-defined]

        # v6: re-evaluate the end bound on every iteration (dynamic for loop boundaries)
        # Pine Script for loops are inclusive of end
        current = start
        last_result = None
        while True:
            end = self.visit(node.end)  # type: ignore[attr-defined]  # dynamic re-eval
            if not (current <= end if step > 0 else current >= end):
                break
            self.context[target_name] = current  # type: ignore[attr-defined]
            result, should_break = self._execute_loop_body(node.body)
            if result is not None:
                last_result = result
            if should_break:
                break
            current += step
        return last_result

    def visit_ForIn(self, node: ast.ForIn):
        """Execute a for-in loop (iteration over collection)."""
        target_name = node.target.id if isinstance(node.target, ast.Name) else None
        if not target_name:
            msg = "For loop target must be a name"
            self._error(msg)  # type: ignore[attr-defined]
            raise RuntimeError(msg)

        iterable = self.visit(node.iter)  # type: ignore[attr-defined]

        # Handle different iterable types (list, Matrix, Map?)
        # Pine Script 'for x in array' iterates values.
        if not hasattr(iterable, "__iter__"):
            msg = f"Object of type {type(iterable)} is not iterable"
            self._error(msg)  # type: ignore[attr-defined]

        last_result = None
        for item in iterable:
            self.context[target_name] = item  # type: ignore[attr-defined]
            result, should_break = self._execute_loop_body(node.body)
            if result is not None:
                last_result = result
            if should_break:
                break
        return last_result

    def visit_Break(self, _node: ast.Break):
        raise BreakLoop

    def visit_Continue(self, _node: ast.Continue):
        raise ContinueLoop

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Define a user-defined function."""
        if node.method:
            # Methods are handled in TypeDef, but if a method appears outside?
            # Pine Script methods must be in types or are "methods" on types via 'method' keyword?
            # If 'method' keyword is used for user-defined methods on built-in types or UDTs.
            # For now, treat as regular function if not inside TypeDef?
            # But builder.py sets method=1 for 'method' keyword.
            pass

        func_name = node.name

        # Create a closure
        def user_function(*args, **kwargs):
            # Create new scope
            old_context = self.context.copy()  # type: ignore[attr-defined]
            try:
                # Bind positional arguments
                param_names = [arg.name for arg in node.args if isinstance(arg, ast.Param)]
                for i, value in enumerate(args):
                    if i < len(param_names):
                        self.context[param_names[i]] = value  # type: ignore[attr-defined]

                # Bind keyword arguments
                for key, value in kwargs.items():
                    self.context[key] = value  # type: ignore[attr-defined]

                # Execute body
                result = None
                for stmt in node.body:
                    if isinstance(stmt, ast.Expr):
                        result = self.visit(stmt.value)  # type: ignore[attr-defined]
                    else:
                        self.visit(stmt)  # type: ignore[attr-defined]
                return result
            finally:
                self.context = old_context  # type: ignore[attr-defined]

        self.context[func_name] = user_function  # type: ignore[attr-defined]
        if getattr(node, "export", None):
            self._register_export(func_name, user_function)

    def visit_Import(self, node: ast.Import):
        """Resolve ``import namespace/name/version [as alias]`` against the library registry.

        Libraries are resolved by exact path when registered with namespace+version,
        or by library title (``name``) after a prior ``evaluate_script(library(...))``.
        Explicit sources registered via ``register_library_source`` are loaded lazily.
        """
        namespace = node.namespace
        name = node.name
        version = int(node.version) if node.version is not None else None
        alias = node.alias or name

        registry = self._library_registry  # type: ignore[attr-defined]
        mod = registry.lookup(namespace=namespace, name=name, version=version)

        if mod is None and namespace is not None and version is not None:
            source = registry.get_source(namespace, name, version)
            if source is not None:
                # Load library source into the same evaluator (exports accumulate)
                self.visit(parse_pine(source, mode="exec"))  # type: ignore[attr-defined]
                mod = registry.lookup(namespace=namespace, name=name, version=version)
                if mod is None:
                    # Title-only registration from library("name")
                    mod = registry.lookup(name=name)
                    if mod is not None:
                        mod.namespace = namespace
                        mod.version = version
                        registry.register(mod)

        if mod is None:
            path = f"{namespace}/{name}/{version}"
            msg = f"Unknown library import: {path}"
            self._error(msg)  # type: ignore[attr-defined]
            return

        # Bind path identity if not already
        if mod.namespace is None and namespace is not None:
            mod.namespace = namespace
        if mod.version is None and version is not None:
            mod.version = version
            registry.register(mod)

        self.context[alias] = mod  # type: ignore[attr-defined]
        return mod

    def _execute_block(self, stmts: Sequence[ast.AST]):
        """Execute a block of statements and return the value of the last expression."""
        result = None
        for stmt in stmts:
            val = self.visit(stmt)  # type: ignore[attr-defined]
            # In Pine Script, the return value of a block is the value of the last expression.
            # If the last statement is not an expression (e.g. assignment), it returns na (None).
            # We update result for every statement.
            # If visit(stmt) returns None (e.g. Assign), result becomes None.
            # If visit(stmt) returns value (e.g. Expr, If, Switch), result becomes value.
            result = val
        return result

    def visit_If(self, node: ast.If):
        """Evaluate an if-else structure. v6: strict bool, na -> false."""
        test_val = self.visit(node.test)  # type: ignore[attr-defined]
        if test_val is None:
            test_val = False
        if bool(test_val):
            return self._execute_block(node.body)
        elif node.orelse:
            if isinstance(node.orelse, list):
                return self._execute_block(node.orelse)
            else:
                return self.visit(node.orelse)  # type: ignore[attr-defined]
        return None

    def visit_Switch(self, node: ast.Switch):
        """Evaluate a switch structure."""
        subject_val = self.visit(node.subject) if node.subject else None  # type: ignore[attr-defined]

        for case in node.cases:
            if case.pattern:  # type: ignore[attr-defined]
                # Pattern matching
                pattern_val = self.visit(case.pattern)  # type: ignore[attr-defined]
                if subject_val is not None:
                    # Switch with subject: match equality
                    if subject_val == pattern_val:
                        return self._execute_block(case.body)  # type: ignore[arg-type, attr-defined]
                # Switch without subject: pattern must be boolean true
                elif pattern_val:
                    return self._execute_block(case.body)  # type: ignore[arg-type, attr-defined]
            else:
                # Default case (no pattern)
                return self._execute_block(case.body)  # type: ignore[arg-type, attr-defined]
        return None

    def _execute_loop_body(self, stmts: Sequence[ast.AST]) -> tuple[Any, bool]:
        """Execute loop body. Returns (result, should_break)."""
        result = None
        should_break = False
        try:
            for stmt in stmts:
                val = self.visit(stmt)  # type: ignore[attr-defined]
                if isinstance(stmt, ast.Expr):
                    result = val
                elif isinstance(stmt, (ast.If, ast.Switch, ast.ForTo, ast.ForIn, ast.While)):
                    result = val
                else:
                    result = None
        except BreakLoop:
            should_break = True
        except ContinueLoop:
            pass
        return result, should_break
