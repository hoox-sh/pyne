# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import operator

from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType


# Optimize: Pre-cache operator references at module level
# These imports reduce attribute lookup overhead for frequent operations
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

_METHOD_CALL_TUPLE_LENGTH = 3


class ExpressionEvaluator:
    """Evaluates expression AST nodes: boolean, binary, unary, comparisons, and calls.

    Handles all expression types including:
    - Boolean operations (and, or)
    - Binary operations (arithmetic, comparison)
    - Unary operations (not, negation, positive)
    - Function/method calls with argument handling
    - Ternary conditionals
    - List/tuple comprehensions
    """

    def visit_BoolOp(self: EvaluatorProtocol, node: ast.BoolOp):
        """Evaluate boolean operations (and, or).

        Implements short-circuit evaluation:
        - 'and': stops at first falsy value
        - 'or': stops at first truthy value

        Args:
            node: BoolOp node with operator and list of values

        Returns:
            Boolean result of the operation
        """
        # Evaluate 'and' operation with short-circuit: return first falsy or last value
        if isinstance(node.op, ast.And):
            return all(self.visit(value) for value in node.values)
        # Evaluate 'or' operation with short-circuit: return first truthy or last value
        if isinstance(node.op, ast.Or):
            return any(self.visit(value) for value in node.values)
        msg = f"unexpected node operator: {node.op}"
        raise ValueError(msg)

    def visit_BinOp(self: EvaluatorProtocol, node: ast.BinOp):
        """Evaluate binary operations (arithmetic, bitwise).

        Supports: +, -, *, /, % (modulo), and bitwise operations.

        Args:
            node: BinOp node with left operand, right operand, and operator

        Returns:
            Result of applying the binary operator to the operands

        Raises:
            NotImplementedError: If operator is not supported
        """
        # Evaluate both operands
        left = self.visit(node.left)
        right = self.visit(node.right)

        # Dispatch to the appropriate operator function
        if isinstance(node.op, ast.Add):
            # Addition: numbers, string concatenation, or list concatenation
            return _OPERATOR_ADD(left, right)
        elif isinstance(node.op, ast.Sub):
            # Subtraction: numeric only
            return _OPERATOR_SUB(left, right)
        elif isinstance(node.op, ast.Mult):
            # Multiplication: numbers, string/list repetition
            return _OPERATOR_MUL(left, right)
        elif isinstance(node.op, ast.Div):
            # Division: always true division (/)
            return _OPERATOR_DIV(left, right)
        elif isinstance(node.op, ast.Mod):
            # Modulo: remainder after division
            return _OPERATOR_MOD(left, right)
        else:
            msg = f"Unsupported binary operator: {type(node.op)}"
            raise ValueError(msg)

    def visit_UnaryOp(self: EvaluatorProtocol, node: ast.UnaryOp):
        """Evaluate unary operations (not, negation, positive).

        Args:
            node: UnaryOp node with operand and operator

        Returns:
            Result of applying the unary operator to the operand

        Raises:
            ValueError: If operator is not recognized
        """
        # Logical negation: inverts boolean value
        if isinstance(node.op, ast.Not):
            return _OPERATOR_NOT(self.visit(node.operand))
        # Unary positive: no-op but validates operand is numeric
        if isinstance(node.op, ast.UAdd):
            return _OPERATOR_POS(self.visit(node.operand))
        # Unary negation: negates numeric value
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
        """Evaluate comparison operations with short-circuiting.

        Evaluates chained comparisons (e.g., a < b < c) efficiently:
        - Evaluates operands left-to-right
        - Stops as soon as a comparison fails (short-circuit)
        - Only evaluates the right operand if the left comparison succeeded

        Args:
            node: Compare node with left operand, operators, and comparators

        Returns:
            True if all comparisons are true, False otherwise
        """
        # Evaluate the first operand (leftmost)
        left = self.visit(node.left)

        # Iterate through pairs of (operator, right_operand)
        # This loop implements short-circuiting: if any comparison fails,
        # we return False immediately and stop evaluating remaining operands.
        for op_node, comparator_node in zip(node.ops, node.comparators, strict=True):
            op = self.visit(op_node)
            right = self.visit(comparator_node)

            if not op(left, right):
                return False

            # The right operand becomes the left operand for the next comparison
            left = right

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
        # Early-dispatch for qualified-attribute builtins (subtask 1.1.2):
        # when ``node.func`` is an ``Attribute`` whose qualified name is a
        # registered builtin, dispatch by qualified name and return the
        # result. This must happen BEFORE visiting ``node.func`` because
        # bare-reference zero-arg builtins like ``strategy.long`` are
        # eagerly evaluated by ``visit_Attribute`` to the value ``"long"``
        # — losing the qualified name needed to dispatch the call form.
        if self._is_qualified_attribute_builtin_call(node):
            return self._dispatch_qualified_attribute_builtin(node)

        func = self.visit(node.func)
        args, kwargs = self._collect_call_args(node)

        # Handle method call on UDT objects
        if isinstance(func, tuple) and len(func) == _METHOD_CALL_TUPLE_LENGTH and func[0] == "_method_call":
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
            return self._call_builtin(func, args, kwargs=kwargs)
        else:
            # For now, assume func is callable
            return func(*args, **kwargs)

    def _is_qualified_attribute_builtin_call(
        self: EvaluatorProtocol,
        node: ast.Call,
    ) -> bool:
        """True if ``node.func`` is an ``Attribute`` whose qualified name
        is a registered builtin. See subtask 1.1.2.

        Uses AST-only path building so intermediate zero-arg series like
        ``strategy.opentrades`` are not evaluated while resolving
        ``strategy.opentrades.entry_price(...)``.
        """
        if not isinstance(node.func, ast.Attribute):
            return False
        from pynescript.ast.evaluator.names import ast_qualified_name

        qual = ast_qualified_name(node.func)
        return bool(qual and self._is_registered_builtin(qual))

    def _dispatch_qualified_attribute_builtin(
        self: EvaluatorProtocol,
        node: ast.Call,
    ) -> Any:
        """Dispatch a call whose function is a qualified-attribute builtin
        (e.g. ``strategy.entry(...)``). Caller must have already checked
        ``_is_qualified_attribute_builtin_call``. See subtask 1.1.2 and
        1.2.
        """
        node_func = node.func
        if not isinstance(node_func, ast.Attribute):
            # Caller violated the precondition; fail loudly so the bug is
            # obvious in development rather than silently miscompiling.
            raise TypeError("_dispatch_qualified_attribute_builtin requires node.func to be ast.Attribute")
        from pynescript.ast.evaluator.names import ast_qualified_name

        qualified_name = ast_qualified_name(node_func)
        if not qualified_name:
            raise TypeError("could not resolve qualified builtin name from AST")
        args, kwargs = self._collect_call_args(node)
        return self._call_builtin(qualified_name, args, kwargs=kwargs)

    def _collect_call_args(
        self: EvaluatorProtocol,
        node: ast.Call,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Walk ``node.args`` and return ``(args, kwargs)`` with each
        value evaluated. Used by both the early-dispatch path and the
        main call path. See subtask 1.1.2.
        """
        args: list[Any] = []
        kwargs: dict[str, Any] = {}
        for arg in node.args:
            if arg.name:  # type: ignore[attr-defined]
                kwargs[arg.name] = self.visit(arg.value)  # type: ignore[attr-defined]
            else:
                args.append(self.visit(arg.value))  # type: ignore[attr-defined]
        return args, kwargs

    def _is_registered_builtin(self: EvaluatorProtocol, name: str) -> bool:
        """True if ``name`` is in the builtin dispatch map.

        Used by ``visit_Call`` to recognize qualified attribute references
        to builtins (e.g. ``strategy.long``) BEFORE ``visit_Attribute``
        eagerly evaluates them. See subtask 1.1.2.
        """
        if getattr(self, "_builtin_dispatch", None) is None and hasattr(self, "_build_builtin_map"):
            self._builtin_dispatch = self._build_builtin_map()
        dispatch = getattr(self, "_builtin_dispatch", None)
        return dispatch is not None and name in dispatch

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

    def visit_If(self: EvaluatorProtocol, node: ast.If) -> Any:
        """Evaluate an if-expression.

        Args:
            node: If node with test, body, and orelse

        Returns:
            The value of the last expression in the executed branch, or None
        """
        if self.visit(node.test):
            result = None
            for stmt in node.body:
                if isinstance(stmt, ast.Expr):
                    result = self.visit(stmt.value)
                else:
                    self.visit(stmt)
            return result
        else:
            result = None
            for stmt in node.orelse:
                if isinstance(stmt, ast.Expr):
                    result = self.visit(stmt.value)
                else:
                    self.visit(stmt)
            return result

    def visit_Switch(self: EvaluatorProtocol, node: ast.Switch) -> Any:
        """Evaluate a switch-expression.

        Args:
            node: Switch node with subject and cases

        Returns:
            The value of the executed case block, or None
        """
        subject_val = self.visit(node.subject) if node.subject else None

        for case in node.cases:
            match = False
            if case.pattern:  # type: ignore[attr-defined]
                pattern_val = self.visit(case.pattern)  # type: ignore[attr-defined]
                if subject_val is not None:
                    match = subject_val == pattern_val
                else:
                    match = bool(pattern_val)
            else:
                # Default case (no pattern)
                match = True

            if match:
                result = None
                for stmt in case.body:  # type: ignore[attr-defined]
                    if isinstance(stmt, ast.Expr):
                        result = self.visit(stmt.value)
                    else:
                        self.visit(stmt)
                return result
        return None
