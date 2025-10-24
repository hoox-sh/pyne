from __future__ import annotations

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance


class NameEvaluator:
    def visit_Name(self: EvaluatorProtocol, node: ast.Name) -> Any:
        if node.id in self.context:
            return self.context[node.id]
        return node.id

    def visit_Attribute(self: EvaluatorProtocol, node: ast.Attribute) -> Any:
        qualified_name = f"{self.visit(node.value)}.{node.attr}"
        if qualified_name in self.context:
            return self.context[qualified_name]

        value = self.visit(node.value)

        # Handle UDT object field/method access
        if isinstance(value, ObjectInstance):
            # Check if it's a method first
            if value.udt.get_method(node.attr):
                # Return a bound method marker - (instance, method_name)
                return ("_method_call", value, node.attr)
            # Otherwise try to get field
            return value.get_field(node.attr)

        # Handle Enum member access
        if isinstance(value, dict):
            member_name = node.attr
            if member_name in value:
                return value[member_name]
            self._error(f"Enum member '{member_name}' not found in enum.")

        if isinstance(value, str) and value in self.context:
            enum_def = self.context[value]
            if isinstance(enum_def, dict):
                member_name = node.attr
                if member_name in enum_def:
                    return enum_def[member_name]
                self._error(f"Enum member '{member_name}' not found in enum '{value}'.")

        return qualified_name

    def visit_Subscript(self: EvaluatorProtocol, node: ast.Subscript) -> Any:
        value = self.visit(node.value)
        slice_ = self.visit(node.slice) if node.slice else None  # type: ignore[arg-type]
        if isinstance(value, list) and isinstance(slice_, int):
            if slice_ < 0:
                msg = "Negative indices not supported in PineScript"
                raise ValueError(msg)
            # PineScript: series[0] is current, series[1] is previous
            index = -(slice_ + 1)
            if abs(index) > len(value):
                return None  # PineScript returns na for out of bounds
            return value[index]
        else:
            value_type = type(value)
            slice_type = type(slice_)
            msg = f"Subscript not supported for {value_type} with {slice_type}"
            raise NotImplementedError(msg)
