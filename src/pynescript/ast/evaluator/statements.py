from __future__ import annotations

from pynescript.ast import node as ast
from pynescript.ast.type_system import BuiltinType, BuiltinTypeKind, Field, UserDefinedType


class StatementEvaluator:
    def visit_Script(self, node: ast.Script):
        for stmt in node.body:
            self.visit(stmt)  # type: ignore[attr-defined]

    def visit_Assign(self, node: ast.Assign):
        if node.value:
            value = self.visit(node.value)  # type: ignore[attr-defined]
            if isinstance(node.target, ast.Name):
                self.context[node.target.id] = value  # type: ignore[attr-defined]
            else:
                msg = f"Unsupported assignment target: {type(node.target)}"
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
                # Methods will be handled later
                pass

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
