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

import operator

from collections.abc import Callable
from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType


# Sentinel: attribute-call recovery did not apply
_ATTR_CALL_MISS = object()
_MISSING = object()

# Series wrapper type names (avoid allocating a set on every operand unwrap)
_SERIES_TYPE_NAMES = frozenset({"PineSeries", "_SeriesResult"})


def _as_scalar_operand(value):
    """Coerce PineSeries-like objects to their current scalar for arithmetic.

    Always unwrap series wrappers — including when ``current`` is ``None`` (na) —
    so comparisons do not attempt ``None < None`` via object fallbacks.

    Fast paths use identity type checks (``type(x) is float``) for the common
    bar-mode case where hosts inject bare floats into context.
    """
    t = type(value)
    # Dominant bar-mode path: bare numerics / None
    if t is float or t is int or value is None or t is bool:
        return value
    if t is list or t is str or t is tuple or t is dict or t is bytes:
        return value
    # Named series wrappers (PineSeries from backend.series, etc.)
    if t.__name__ in _SERIES_TYPE_NAMES:
        return value.current
    # Duck-type rare wrappers that expose .current + .history
    current = getattr(value, "current", _MISSING)
    if current is not _MISSING and hasattr(value, "history"):
        return current
    return value


def _elementwise_binary(op, a, b):
    """Apply *op* with Pine NA (None) and series (list) semantics.

    - ``None`` operands propagate NA.
    - Two lists → element-wise (zip from the end when lengths differ).
    - List + scalar → broadcast.
    - Scalars → normal op.

    Pure numeric operands take a zero-allocation fast path (no list/series work).
    """
    ta = a.__class__
    tb = b.__class__
    # Ultra-fast path: bare int/float arithmetic (most bar-mode BinOps)
    if ta is float or ta is int:
        if tb is float or tb is int:
            try:
                return op(a, b)
            except TypeError:
                return None
        if b is None:
            return None
    elif a is None and (tb is float or tb is int or b is None):
        return None

    a = _as_scalar_operand(a)
    b = _as_scalar_operand(b)

    # Re-check after unwrap (series → scalar)
    ta = a.__class__
    tb = b.__class__
    if ta is float or ta is int:
        if tb is float or tb is int:
            try:
                return op(a, b)
            except TypeError:
                return None
        if b is None:
            return None
    elif a is None and (tb is float or tb is int or b is None):
        return None

    if ta is list and tb is list:
        if len(a) == len(b):
            return [None if x is None or y is None else op(x, y) for x, y in zip(a, b)]
        # Align on the trailing edge (most recent bars)
        n = min(len(a), len(b))
        a_tail, b_tail = a[-n:], b[-n:]
        body = [None if x is None or y is None else op(x, y) for x, y in zip(a_tail, b_tail)]
        if len(a) > len(b):
            return [None] * (len(a) - n) + body
        return [None] * (len(b) - n) + body

    if ta is list:
        if b is None:
            return [None] * len(a)
        return [None if x is None else op(x, b) for x in a]

    if tb is list:
        if a is None:
            return [None] * len(b)
        return [None if y is None else op(a, y) for y in b]

    if a is None or b is None:
        return None
    # Soft-fail mismatched types (str vs int, etc.) → na
    try:
        return op(a, b)
    except TypeError:
        return None


def _na_safe_binary(op):
    """Return None/series-safe binary operator."""

    def wrapper(a, b):
        return _elementwise_binary(op, a, b)

    return wrapper


def _na_safe_unary(op):
    """Return None-safe unary operator; maps over series lists."""

    def wrapper(a):
        t = type(a)
        if t is float or t is int or t is bool:
            return op(a)
        if a is None:
            return None
        a = _as_scalar_operand(a)
        if type(a) is list:
            return [None if x is None else op(x) for x in a]
        if a is None:
            return None
        return op(a)

    return wrapper


_OPERATOR_EQ = _na_safe_binary(operator.eq)
_OPERATOR_NE = _na_safe_binary(operator.ne)
_OPERATOR_LT = _na_safe_binary(operator.lt)
_OPERATOR_LE = _na_safe_binary(operator.le)
_OPERATOR_GT = _na_safe_binary(operator.gt)
_OPERATOR_GE = _na_safe_binary(operator.ge)
_OPERATOR_ADD = _na_safe_binary(operator.add)
_OPERATOR_SUB = _na_safe_binary(operator.sub)
_OPERATOR_MUL = _na_safe_binary(operator.mul)


def _safe_truediv(a, b):
    """Division with Pine NA / zero-divisor semantics (returns na, not exception)."""
    try:
        if b == 0 or b == 0.0:
            return None
        return operator.truediv(a, b)
    except (TypeError, ZeroDivisionError, OverflowError):
        return None


_OPERATOR_DIV = _na_safe_binary(_safe_truediv)
_OPERATOR_MOD = _na_safe_binary(operator.mod)
_OPERATOR_NOT = _na_safe_unary(operator.not_)
_OPERATOR_POS = _na_safe_unary(operator.pos)
_OPERATOR_NEG = _na_safe_unary(operator.neg)

# Module-level type → operator maps (avoid isinstance chains + visit(op) on Compare)
_BINOP_DISPATCH: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: _OPERATOR_ADD,
    ast.Sub: _OPERATOR_SUB,
    ast.Mult: _OPERATOR_MUL,
    ast.Div: _OPERATOR_DIV,
    ast.Mod: _OPERATOR_MOD,
}
_UNARYOP_DISPATCH: dict[type, Callable[[Any], Any]] = {
    ast.Not: _OPERATOR_NOT,
    ast.UAdd: _OPERATOR_POS,
    ast.USub: _OPERATOR_NEG,
}
_CMPOP_DISPATCH: dict[type, Callable[[Any, Any], Any]] = {
    ast.Eq: _OPERATOR_EQ,
    ast.NotEq: _OPERATOR_NE,
    ast.Lt: _OPERATOR_LT,
    ast.LtE: _OPERATOR_LE,
    ast.Gt: _OPERATOR_GT,
    ast.GtE: _OPERATOR_GE,
}

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
        op_t = type(node.op)
        if op_t is ast.And:
            return all(self.visit(value) for value in node.values)
        if op_t is ast.Or:
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
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_fn = _BINOP_DISPATCH.get(type(node.op))
        if op_fn is None:
            msg = f"Unsupported binary operator: {type(node.op)}"
            raise ValueError(msg)
        return op_fn(left, right)

    def visit_UnaryOp(self: EvaluatorProtocol, node: ast.UnaryOp):
        """Evaluate unary operations (not, negation, positive).

        Args:
            node: UnaryOp node with operand and operator

        Returns:
            Result of applying the unary operator to the operand

        Raises:
            ValueError: If operator is not recognized
        """
        op_fn = _UNARYOP_DISPATCH.get(type(node.op))
        if op_fn is None:
            msg = f"unexpected node operator: {node.op}"
            raise ValueError(msg)
        return op_fn(self.visit(node.operand))

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
        left = self.visit(node.left)
        cmp_dispatch = _CMPOP_DISPATCH

        # Short-circuit: stop at first failed comparison
        for op_node, comparator_node in zip(node.ops, node.comparators, strict=True):
            # Type-map dispatch — skip full visitor for Eq/Lt/… operator nodes
            op = cmp_dispatch.get(type(op_node))
            if op is None:
                op = self.visit(op_node)
            right = self.visit(comparator_node)

            result = op(left, right)
            # Pine: comparison with na yields na (None). Treat as failed for
            # chained bool context so `if a < b` is false when either side is na.
            if result is None:
                return False
            if type(result) is list:
                # Element-wise series compare — truthy only if any True (rare path)
                if not any(result):
                    return False
            elif not result:
                return False

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

        # Early-dispatch bare Name builtins (year/time/month/…) BEFORE
        # visiting the name: hosts often inject scalar ``time``/``year`` into
        # context for series use, which would otherwise make ``year(ts)``
        # resolve to a non-callable int and soft-fail to na.
        #
        # User-defined functions/methods in context take precedence over bare
        # ta.* aliases (v3/v4 mirrors like ``cmf``, ``rsi``, ``linreg``). Local
        # ``cmf(len)`` / ``vwma(src, vol, period)`` must not route to ``ta.cmf``.
        if isinstance(node.func, ast.Name) and self._is_registered_builtin(node.func.id):
            args, kwargs = self._collect_call_args(node)
            ctx = getattr(self, "context", None)
            user = ctx.get(node.func.id) if isinstance(ctx, dict) else None
            if callable(user):
                try:
                    return user(*args, **kwargs)
                except TypeError:
                    try:
                        return user(*args)
                    except TypeError:
                        return None
            return self._call_builtin(node.func.id, args, kwargs=kwargs)

        func = self.visit(node.func)
        args, kwargs = self._collect_call_args(node)

        # Handle method call on UDT objects
        if isinstance(func, tuple) and len(func) == _METHOD_CALL_TUPLE_LENGTH and func[0] == "_method_call":
            _, obj_instance, method_name = func
            return self._invoke_method(obj_instance, method_name, args, kwargs)

        # Array instance methods: ``arr.push(x)`` → ``array.push(arr, x)``
        if isinstance(func, tuple) and len(func) == 3 and func[0] == "_array_method":
            _, receiver, method_name = func
            return self._call_builtin(f"array.{method_name}", [receiver, *args], kwargs=kwargs)  # type: ignore[attr-defined]

        # Drawing/namespace instance methods: ``la.get_text()`` → ``label.get_text(la)``
        if isinstance(func, tuple) and len(func) == 3 and func[0] == "_ns_method":
            _, receiver, qual_name = func
            return self._call_builtin(qual_name, [receiver, *args], kwargs=kwargs)  # type: ignore[attr-defined]

        # Extension methods: ``method addCell(table t, ...)`` + ``display.addCell(...)``
        if isinstance(func, tuple) and len(func) == 3 and func[0] == "_ext_method":
            _, receiver, method_name = func
            ext = self.context.get(method_name)  # type: ignore[attr-defined]
            if callable(ext):
                try:
                    return ext(receiver, *args, **kwargs)
                except TypeError:
                    try:
                        return ext(receiver, *args)
                    except TypeError:
                        return None
            return None

        # Handle .new() method for UDT instantiation
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "new":
                type_obj = self._resolve_udt_constructor(node.func.value)
                if isinstance(type_obj, UserDefinedType):
                    return self._handle_udt_new(type_obj, args, kwargs)

        # Zero-arg call on a UDT/series field: ``this.columns()`` where ``columns``
        # is an int field (Console uses both ``this.columns`` and ``this.columns()``
        # / matrix ``this.columns()``). Prefer the field value over "not callable".
        if (
            isinstance(node.func, ast.Attribute)
            and not args
            and not kwargs
            and not isinstance(func, (str, tuple))
            and not callable(func)
        ):
            return func

        # Handle built-in functions
        if isinstance(func, str):
            # Failed attribute resolution often yields AST paths like
            # ``this.columns`` / ``this.rows``. Recover instance field/method
            # before treating the string as a global builtin name.
            if isinstance(node.func, ast.Attribute) and (
                "." in func or not self._is_registered_builtin(func)
            ):
                recovered = self._recover_instance_attr_call(node.func, args, kwargs)
                if recovered is not _ATTR_CALL_MISS:
                    return recovered
            return self._call_builtin(func, args, kwargs=kwargs)
        else:
            # Soft-fail non-callables (stubs, na) — return None
            if not callable(func):
                return None
            try:
                return func(*args, **kwargs)
            except TypeError:
                return None

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

        Caches ``_builtin_dispatch`` after first use (shared with ``_call_builtin``).
        """
        dispatch = self.__dict__.get("_builtin_dispatch")
        if dispatch is None:
            build = getattr(self, "_build_builtin_map", None)
            if build is None:
                return False
            dispatch = build()
            self._builtin_dispatch = dispatch
        return name in dispatch

    def _recover_instance_attr_call(
        self: EvaluatorProtocol,
        attr_node: Any,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> Any:
        """Re-resolve ``receiver.attr(...)`` after failed attribute evaluation.

        Common when ``this`` was temporarily shadowed mid-call, or when a UDT
        field is written as a zero-arg call (``this.columns()``). Also covers
        matrix/array instance methods when the first Attribute pass returned a
        bare qualified-name string.
        """
        from pynescript.ast import node as ast_mod
        from pynescript.ast.evaluator.builtins.drawing import Box
        from pynescript.ast.evaluator.builtins.drawing import Label
        from pynescript.ast.evaluator.builtins.drawing import Line
        from pynescript.ast.evaluator.builtins.drawing import LineFill
        from pynescript.ast.evaluator.builtins.drawing import Polyline
        from pynescript.ast.evaluator.builtins.drawing import Table
        from pynescript.ast.evaluator.builtins.matrix import Matrix

        # Fresh receiver lookup (prefer live context for Name bases)
        if isinstance(attr_node.value, ast_mod.Name):
            rid = attr_node.value.id
            receiver = self.context.get(rid, rid)  # type: ignore[attr-defined]
        else:
            receiver = self.visit(attr_node.value)
        name = attr_node.attr

        # Matrix instance methods: m.columns() / m.rows() / m.get(...)
        if isinstance(receiver, Matrix):
            qual = f"matrix.{name}"
            if self._is_registered_builtin(qual):
                return self._call_builtin(qual, [receiver, *args], kwargs=kwargs)

        # Array instance methods
        if isinstance(receiver, list):
            qual = f"array.{name}"
            if self._is_registered_builtin(qual):
                return self._call_builtin(qual, [receiver, *args], kwargs=kwargs)

        # Drawing namespaces
        for cls, ns in (
            (Label, "label"),
            (Line, "line"),
            (Box, "box"),
            (Table, "table"),
            (Polyline, "polyline"),
            (LineFill, "linefill"),
        ):
            if isinstance(receiver, cls):
                qual = f"{ns}.{name}"
                if self._is_registered_builtin(qual):
                    return self._call_builtin(qual, [receiver, *args], kwargs=kwargs)
                break

        # UDT methods / fields
        if isinstance(receiver, ObjectInstance):
            if receiver.udt.get_method(name):
                return self._invoke_method(receiver, name, args, kwargs)
            if name in receiver.udt.fields:
                val = receiver.get_field(name)
                if not args and not kwargs:
                    return val
                if callable(val):
                    try:
                        return val(*args, **(kwargs or {}))
                    except TypeError:
                        return None

        # Extension methods (including na receiver)
        ext = self.context.get(name) if hasattr(self, "context") else None  # type: ignore[attr-defined]
        if callable(ext) and getattr(ext, "__pine_method__", False):
            try:
                return ext(receiver, *args, **kwargs)
            except TypeError:
                try:
                    return ext(receiver, *args)
                except TypeError:
                    return None

        return _ATTR_CALL_MISS

    def _resolve_udt_constructor(self: EvaluatorProtocol, type_expr: Any) -> UserDefinedType | None:
        """Resolve the UDT for ``TypeName.new(...)`` / ``alias.TypeName.new(...)``.

        Prefer the live value when it is already a ``UserDefinedType``. If the
        type name was shadowed by a method or function of the same name
        (Console library: ``export type insights`` + ``method insights(terminal)``),
        fall back to ``type_registry`` so constructors keep working.
        """
        from pynescript.ast import node as ast_mod
        from pynescript.ast.evaluator.libraries import LibraryModule

        # Direct UDT in context
        val = self.visit(type_expr)
        if isinstance(val, UserDefinedType):
            return val

        registry = getattr(self, "type_registry", None)

        # alias.TypeName where Type is on a LibraryModule export
        if isinstance(type_expr, ast_mod.Attribute):
            base = self.visit(type_expr.value)
            if isinstance(base, LibraryModule):
                exported = base.exports.get(type_expr.attr)
                if isinstance(exported, UserDefinedType):
                    return exported
            if registry is not None:
                found = registry.get_type(type_expr.attr)
                if isinstance(found, UserDefinedType):
                    return found

        # Bare name shadowed by method/function — use type registry
        name: str | None = None
        if isinstance(type_expr, ast_mod.Name):
            name = type_expr.id
        elif isinstance(val, str):
            name = val

        if name and registry is not None:
            found = registry.get_type(name)
            if isinstance(found, UserDefinedType):
                return found
        return None

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

        # Bind params on the *live* context dict (do not replace it — hosts
        # mutate bar_index/time in place each bar).
        ctx = self.context  # type: ignore[attr-defined]
        missing = object()
        saved: dict[str, Any] = {}

        def _bind(name: str, value: Any) -> None:
            if name not in saved:
                saved[name] = ctx[name] if name in ctx else missing
            ctx[name] = value

        try:
            # Bind the receiver to the first parameter name (usually ``this``)
            # and always expose ``this`` for Pine convention.
            params = [p for p in method_def.args if isinstance(p, ast.Param)]
            if params:
                _bind(params[0].name, obj_instance)
            _bind("this", obj_instance)

            # Bind remaining parameters (skip receiver)
            extra_params = params[1:]
            for param, arg_val in zip(extra_params, args, strict=False):
                _bind(param.name, arg_val)

            # Bind keyword arguments
            for key, value in kwargs.items():
                _bind(key, value)

            # Defaults for unbound params with defaults
            for param in extra_params:
                if param.name not in saved and param.default is not None:
                    _bind(param.name, self.visit(param.default))  # type: ignore[attr-defined]

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
            for name, old in saved.items():
                if old is missing:
                    ctx.pop(name, None)
                else:
                    ctx[name] = old

    def visit_Specialize(self: EvaluatorProtocol, node: ast.Specialize) -> Any:
        """Evaluate a type-specialization expression (e.g. ``array.new<float>``).

        Maps ``array.new<float>`` → registered builtin ``array.new_float`` so
        the subsequent Call dispatches correctly. Uses AST-only base path so
        zero-arg builtins like ``array.new`` are not eagerly evaluated to ``[]``.
        """
        from pynescript.ast import node as ast_mod
        from pynescript.ast.evaluator.names import ast_qualified_name

        # Prefer AST path for Attribute bases (array.new) — do not evaluate
        if isinstance(node.value, ast_mod.Attribute):
            base = ast_qualified_name(node.value)
        else:
            base = self.visit(node.value)

        type_name: str | None = None
        type_arg = node.args
        if isinstance(type_arg, ast_mod.Name):
            type_name = type_arg.id
        elif type_arg is not None:
            tval = self.visit(type_arg)
            if isinstance(tval, str):
                type_name = tval

        if isinstance(base, str) and type_name:
            specialized = f"{base}_{type_name}"
            if self._is_registered_builtin(specialized):  # type: ignore[attr-defined]
                return specialized
            if self._is_registered_builtin(base):  # type: ignore[attr-defined]
                return base
        return base

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
