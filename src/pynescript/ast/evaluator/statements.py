# Copyright 2024-2025 jango_blockchained
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

from __future__ import annotations

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.type_system import BuiltinType
from pynescript.ast.type_system import BuiltinTypeKind
from pynescript.ast.type_system import Field
from pynescript.ast.type_system import MethodSignature
from pynescript.ast.type_system import ObjectInstance
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

    def visit_Script(self, node: ast.Script):
        """Execute all statements in a script.

        Args:
            node: The Script node containing the body of statements
        """
        # Execute each statement in order
        for stmt in node.body:
            # Delegate to visit method for the statement type
            self.visit(stmt)  # type: ignore[attr-defined]

    def visit_Assign(self, node: ast.Assign):
        """Evaluate an assignment statement.

        Assigns a value to a variable in the current context.

        Args:
            node: The Assign node with target and value

        Raises:
            ValueError: If assignment target is not a simple name
        """
        # Only proceed if there's a value to assign (not None)
        if node.value:
            # Evaluate the right-hand side expression
            value = self.visit(node.value)  # type: ignore[attr-defined]
            # Handle simple name assignment (e.g., x = 5)
            if isinstance(node.target, ast.Name):
                # Store the value in context under the variable name
                self.context[node.target.id] = value  # type: ignore[attr-defined]
            else:
                msg = f"Unsupported assignment target: {type(node.target)}"
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

        # For other cases, fall back to regular assignment handling
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
                        param_type = self._convert_type_spec_to_type(param.type) if param.type else None
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
        self.type_registry.register_type(udt)  # type: ignore[attr-defined]

        # Also store it in the context for backward compatibility
        self.context[type_name] = udt  # type: ignore[attr-defined]

    def _convert_type_spec_to_type(self, type_spec):
        """Convert a type specification AST node to a Type object"""
        # For now, handle simple cases
        if isinstance(type_spec, ast.Name):
            type_name = type_spec.id
            # Try to get from registry first
            registered = self.type_registry.get_type(type_name)  # type: ignore[attr-defined]
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
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                member_name = stmt.target.id
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Name):
                member_name = stmt.value.id
            else:
                msg = f"Unsupported statement in enum body: {type(stmt)}"
                self._error(msg)  # type: ignore[attr-defined]

            if member_name:
                # The value is symbolic, representing member access
                enum_members[member_name] = f"{enum_name}.{member_name}"

        # Store the enum definition in the context
        self.context[enum_name] = enum_members  # type: ignore[attr-defined]

    def visit_Expr(self, node: ast.Expr):
        """Evaluate an expression statement."""
        return self.visit(node.value)  # type: ignore[attr-defined]

    def visit_While(self, node: ast.While):
        """Execute a while loop."""
        last_result = None
        while self.visit(node.test):  # type: ignore[attr-defined]
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

        start = self.visit(node.start)  # type: ignore[attr-defined]
        end = self.visit(node.end)  # type: ignore[attr-defined]
        step = self.visit(node.step) if node.step else 1  # type: ignore[attr-defined]

        # Pine Script for loops are inclusive of end
        # Handle step direction
        def condition(i):
            return i <= end if step > 0 else i >= end

        current = start
        last_result = None
        while condition(current):
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

    def visit_Break(self, node: ast.Break):
        raise BreakLoop

    def visit_Continue(self, node: ast.Continue):
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

    def _execute_block(self, stmts: list[ast.AST]):
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
        """Evaluate an if-else structure."""
        # Evaluate condition
        if self.visit(node.test):  # type: ignore[attr-defined]
            # Execute body (block)
            return self._execute_block(node.body)
        elif node.orelse:
            # Execute else/elif
            if isinstance(node.orelse, list):
                return self._execute_block(node.orelse)
            else:
                # Single node (nested If for elif)
                return self.visit(node.orelse)  # type: ignore[attr-defined]
        return None

    def visit_Switch(self, node: ast.Switch):
        """Evaluate a switch structure."""
        subject_val = self.visit(node.subject) if node.subject else None  # type: ignore[attr-defined]
        
        for case in node.cases:
            if case.pattern:
                # Pattern matching
                pattern_val = self.visit(case.pattern)  # type: ignore[attr-defined]
                if subject_val is not None:
                    # Switch with subject: match equality
                    if subject_val == pattern_val:
                        return self._execute_block(case.body)
                else:
                    # Switch without subject: pattern must be boolean true
                    if pattern_val:
                        return self._execute_block(case.body)
            else:
                # Default case (no pattern)
                return self._execute_block(case.body)
        return None

    def _execute_loop_body(self, stmts: list[ast.AST]) -> tuple[Any, bool]:
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
