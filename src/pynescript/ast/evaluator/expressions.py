from __future__ import annotations

import itertools
import operator

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType


# Optimize: Pre-cache operator references at module level
_OPERATOR_EQ = operator.eq
_OPERATOR_NE = operator.ne
_OPERATOR_LT = operator.lt
_OPERATOR_LE = operator.le
_OPERATOR_GT = operator.gt
_OPERATOR_GE = operator.ge
_OPERATOR_ADD = operator.add
_OPERATOR_SUB = operator.sub
_OPERATOR_MUL = operator.mul
_OPERATOR_DIV = operator.truediv
_OPERATOR_MOD = operator.mod
_OPERATOR_NOT = operator.not_
_OPERATOR_POS = operator.pos
_OPERATOR_NEG = operator.neg


class ExpressionEvaluator:
    def visit_BoolOp(self: EvaluatorProtocol, node: ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(self.visit(value) for value in node.values)
        if isinstance(node.op, ast.Or):
            return any(self.visit(value) for value in node.values)
        msg = f"unexpected node operator: {node.op}"
        raise ValueError(msg)

    def visit_BinOp(self: EvaluatorProtocol, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return _OPERATOR_ADD(left, right)
        elif isinstance(node.op, ast.Sub):
            return _OPERATOR_SUB(left, right)
        elif isinstance(node.op, ast.Mult):
            return _OPERATOR_MUL(left, right)
        elif isinstance(node.op, ast.Div):
            return _OPERATOR_DIV(left, right)
        elif isinstance(node.op, ast.Mod):
            return _OPERATOR_MOD(left, right)
        else:
            msg = f"Unsupported binary operator: {type(node.op)}"
            raise NotImplementedError(msg)

    def visit_UnaryOp(self: EvaluatorProtocol, node: ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return _OPERATOR_NOT(self.visit(node.operand))
        if isinstance(node.op, ast.UAdd):
            return _OPERATOR_POS(self.visit(node.operand))
        if isinstance(node.op, ast.USub):
            return _OPERATOR_NEG(self.visit(node.operand))
        msg = f"unexpected node operator: {node.op}"
        raise ValueError(msg)

    def visit_Conditional(self: EvaluatorProtocol, node: ast.Conditional) -> Any:
        test_result = self.visit(node.test)
        if test_result:
            return self.visit(node.body)
        else:
            return self.visit(node.orelse)

    def visit_Compare(self: EvaluatorProtocol, node: ast.Compare) -> Any:
        comparator_list = [node.left, *node.comparators]
        comparators = map(self.visit, comparator_list)
        compare_ops = [self.visit(op) for op in node.ops]
        comparator_pairs = list(itertools.pairwise(comparators))
        pairs = zip(compare_ops, comparator_pairs, strict=True)
        for op, (left, right) in pairs:
            if not op(left, right):
                return False
        return True

    def visit_Eq(self: EvaluatorProtocol, _node: ast.Eq):
        return _OPERATOR_EQ

    def visit_NotEq(self: EvaluatorProtocol, _node: ast.NotEq):
        return _OPERATOR_NE

    def visit_Lt(self: EvaluatorProtocol, _node: ast.Lt):
        return _OPERATOR_LT

    def visit_LtE(self: EvaluatorProtocol, _node: ast.LtE):
        return _OPERATOR_LE

    def visit_Gt(self: EvaluatorProtocol, _node: ast.Gt):
        return _OPERATOR_GT

    def visit_GtE(self: EvaluatorProtocol, _node: ast.GtE):
        return _OPERATOR_GE

    def visit_Call(self: EvaluatorProtocol, node: ast.Call):
        func = self.visit(node.func)
        args = []

        kwargs = {}

        for arg in node.args:
            if arg.name:  # type: ignore[attr-defined]
                kwargs[arg.name] = self.visit(arg.value)  # type: ignore[attr-defined]

            else:
                args.append(self.visit(arg.value))  # type: ignore[attr-defined]

        # Handle method call on UDT objects
        if isinstance(func, tuple) and len(func) == 3 and func[0] == "_method_call":
            _, obj_instance, method_name = func
            return self._invoke_method(obj_instance, method_name, args, kwargs)

        # Handle .new() method for UDT instantiation
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "new":
                type_obj = self.visit(node.func.value)
                if isinstance(type_obj, UserDefinedType):
                    return self._handle_udt_new(type_obj, args, kwargs)

        # Handle built-in functions
        if isinstance(func, str):
            return self._call_builtin(func, args)
        else:
            # For now, assume func is callable
            return func(*args, **kwargs)

    def _handle_udt_new(
        self: EvaluatorProtocol,
        udt: UserDefinedType,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> ObjectInstance:
        """Create a new instance of a UDT"""
        instance = ObjectInstance(udt)

        # Set fields from positional arguments
        field_names = list(udt.fields.keys())
        for i, arg in enumerate(args):
            if i < len(field_names):
                instance.set_field(field_names[i], arg)

        # Set fields from keyword arguments
        for key, value in kwargs.items():
            if key in udt.fields:
                instance.set_field(key, value)

        return instance

    def _invoke_method(
        self: EvaluatorProtocol,
        obj_instance: ObjectInstance,
        method_name: str,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        """Invoke a method on a UDT instance"""
        # Get the method definition from the UDT
        udt = obj_instance.udt
        if not hasattr(udt, "_method_defs") or method_name not in udt._method_defs:  # type: ignore
            msg = f"Method '{method_name}' not found on type '{udt.name}'"
            self._error(msg)  # type: ignore[attr-defined]

        method_def = udt._method_defs[method_name]  # type: ignore

        # Create a new scope for method execution
        old_context = self.context.copy()  # type: ignore[attr-defined]
        try:
            # Bind THIS to the instance
            self.context["this"] = obj_instance  # type: ignore[attr-defined]

            # Bind regular parameters
            param_names = [p.name for p in method_def.args if isinstance(p, ast.Param) and p.name != "this"]
            for param_name, arg_val in zip(param_names, args, strict=False):
                self.context[param_name] = arg_val  # type: ignore[attr-defined]

            # Bind keyword arguments
            for key, value in kwargs.items():
                self.context[key] = value  # type: ignore[attr-defined]

            # Execute method body - last expression is the return value
            result = None
            for stmt in method_def.body:
                if isinstance(stmt, ast.Expr):
                    # Evaluate expression (may be final return value)
                    result = self.visit(stmt.value)  # type: ignore[attr-defined]
                else:
                    self.visit(stmt)  # type: ignore[attr-defined]

            return result
        finally:
            # Restore the original context
            self.context = old_context  # type: ignore[attr-defined]
