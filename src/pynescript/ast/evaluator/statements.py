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

from pynescript.ast import node as ast
from pynescript.ast.type_system import BuiltinType
from pynescript.ast.type_system import BuiltinTypeKind
from pynescript.ast.type_system import Field
from pynescript.ast.type_system import MethodSignature
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType


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
