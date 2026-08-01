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

"""Expression evaluation: operators, comparisons, calls, conditionals.

:class:`ExpressionEvaluator` implements ``visit_*`` for expression AST nodes.
Cross-cutting rules used throughout this module:

- **``na``** is ``None``. Arithmetic and comparisons with ``None`` propagate
  ``na`` (comparisons that yield ``None`` are treated as false in bool chains).
- **Series lists** use element-wise ops; lengths align on the trailing edge
  (most recent bars) when they differ.
- **Series wrappers** (``PineSeries`` / objects with ``.current`` + ``.history``)
  unwrap to ``.current`` before scalar arithmetic.
- **Calls** resolve builtins by qualified AST path before evaluating
  intermediate attributes, so ``strategy.entry(...)`` is not broken by
  zero-arg series like ``strategy.long``.
"""

from __future__ import annotations

import operator

from collections.abc import Callable
from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.names import _BARE_SERIES_BUILTINS
from pynescript.ast.evaluator.names import ast_qualified_name
from pynescript.ast.evaluator.types import EvaluatorProtocol
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import UserDefinedType


def _type_error_from_callee(exc: BaseException) -> bool:
    """True if *exc* originated inside the called function, not at the call site.

    Signature mismatches (wrong arity / unexpected kwargs) have no deeper frames
    and may soft-fail to ``na`` for overload/extension dispatch. Body
    ``TypeError`` / programming bugs must propagate so the Runtime bar loop
    fails closed instead of silently returning empty/na results.
    """
    tb = exc.__traceback__
    return tb is not None and tb.tb_next is not None


# Sentinel: attribute-call recovery did not apply
_ATTR_CALL_MISS = object()
_MISSING = object()

# Series wrapper type names (avoid allocating a set on every operand unwrap)
_SERIES_TYPE_NAMES = frozenset({"PineSeries", "_SeriesResult"})

# Call-site kind tags (stable AST nodes across bars — resolve once per site).
# ``_SITE_Q``: Attribute whose qualified name is a registered builtin (ta.sma).
# ``_SITE_QB``: same, with bound (tag, handler) after first invoke.
# ``_SITE_B``: bare Name that is a registered builtin (plot, na, year).
# ``_SITE_BB``: bare Name with bound handler (user shadow still checked).
# ``_SITE_G``: general path (methods, UDFs, UDT.new, recovered attrs).
# ``_SITE_GN``: general path with bare Name callee (UDF / local callable).
_SITE_Q = 0
_SITE_QB = 3
_SITE_B = 1
_SITE_BB = 4
_SITE_G = 2
_SITE_GN = 5

# Shared empty kwargs — never mutate (hot path avoids ``{}`` alloc).
_EMPTY_KW: dict[str, Any] = {}

# Arg-plan opcodes (precompiled per Call site; skips visit frames for Name/Const).
# Positional: (_AP_NAME, id) | (_AP_CONST, value) | (_AP_VISIT, value_ast)
# Keyword:    (_AP_KW_NAME, kw, id) | (_AP_KW_CONST, kw, value) | (_AP_KW_VISIT, kw, value_ast)
_AP_NAME = 0
_AP_CONST = 1
_AP_VISIT = 2
_AP_KW_NAME = 3
_AP_KW_CONST = 4
_AP_KW_VISIT = 5


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

# Raw ops for direct ``_elementwise_binary(op, a, b)`` — skips the
# ``_na_safe_binary`` wrapper frame on the BinOp / Compare hot path.
_BINOP_RAW: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: _safe_truediv,
    ast.Mod: operator.mod,
}
_CMPOP_RAW: dict[type, Callable[[Any, Any], Any]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# Full NA-safe callables (AugAssign, visit_Eq fallbacks, external imports)
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
    """Mixin: boolean/binary/unary ops, comparisons, calls, ternary, if/switch expressions.

    Designed for the bar-mode hot path (hosts inject bare floats for OHLCV).
    Numeric pairs short-circuit into pure Python ops; series and ``na`` fall
    through :func:`_elementwise_binary`.

    Method-call markers produced by :class:`~.names.NameEvaluator`
    (``_method_call``, ``_array_method``, ``_ns_method``, ``_ext_method``)
    are interpreted in :meth:`visit_Call`. UDF and UDT method bodies rebind
    parameters on the live ``context`` (see :meth:`_invoke_method`).
    """

    def visit_BoolOp(self: EvaluatorProtocol, node: ast.BoolOp):
        """Evaluate boolean operations (and, or).

        Implements short-circuit evaluation:
        - ``and``: stops at first falsy value
        - ``or``: stops at first truthy value

        ``None`` (na) is falsy in this context. Returns a Python ``bool``.
        Manual loop avoids generator + ``all``/``any`` frame overhead.

        Args:
            node: BoolOp node with operator and list of values

        Returns:
            Boolean result of the operation
        """
        op_t = type(node.op)
        values = node.values
        visit = self.visit
        if op_t is ast.And:
            # Mirror ``all(...)``: na / 0 / False short-circuit to False
            for value in values:
                if not visit(value):
                    return False
            return True
        if op_t is ast.Or:
            for value in values:
                if visit(value):
                    return True
            return False
        msg = f"unexpected node operator: {node.op}"
        raise ValueError(msg)

    def visit_BinOp(self: EvaluatorProtocol, node: ast.BinOp):
        """Evaluate binary arithmetic (``+ - * / %``) with Pine na/series rules.

        - Any ``None`` operand → ``None`` (na).
        - Division by zero → ``None`` (not an exception).
        - List operands → element-wise via :func:`_elementwise_binary`.

        Dominant bar-mode path (bare int/float) is inlined to avoid the
        ``_na_safe_binary`` wrapper frame.

        Args:
            node: BinOp with left, op, right

        Returns:
            Numeric result, list, or ``None``

        Raises:
            ValueError: If the operator type is not in the dispatch table
        """
        visit = self.visit
        left = visit(node.left)
        right = visit(node.right)
        op_t = type(node.op)

        # Ultra-fast path: bare numeric pair (hosts inject floats per bar)
        tl = type(left)
        if tl is float or tl is int:
            tr = type(right)
            if tr is float or tr is int:
                if op_t is ast.Add:
                    return left + right
                if op_t is ast.Sub:
                    return left - right
                if op_t is ast.Mult:
                    return left * right
                if op_t is ast.Div:
                    return _safe_truediv(left, right)
                if op_t is ast.Mod:
                    try:
                        return left % right
                    except ZeroDivisionError:
                        return None
            elif right is None:
                return None
        elif left is None:
            tr = type(right)
            if tr is float or tr is int or right is None:
                return None

        raw = _BINOP_RAW.get(op_t)
        if raw is None:
            msg = f"Unsupported binary operator: {type(node.op)}"
            raise ValueError(msg)
        return _elementwise_binary(raw, left, right)

    def visit_UnaryOp(self: EvaluatorProtocol, node: ast.UnaryOp):
        """Evaluate unary ``not``, ``-``, ``+``.

        Unary ops on ``na`` propagate ``na`` (including ``not na`` → ``None``),
        matching Pine rather than Python's ``not None`` → ``True``.

        Args:
            node: UnaryOp with op and operand

        Returns:
            Result, or ``None`` when the operand is na

        Raises:
            ValueError: If the operator type is not recognized
        """
        operand = self.visit(node.operand)
        op_t = type(node.op)
        t = type(operand)
        # Scalar / bool fast path — no wrapper frame
        if t is float or t is int or t is bool:
            if op_t is ast.USub:
                return -operand
            if op_t is ast.UAdd:
                return +operand
            if op_t is ast.Not:
                return not operand
        if operand is None:
            # Pine: unary ops on na propagate na (including ``not na`` → na)
            return None
        op_fn = _UNARYOP_DISPATCH.get(op_t)
        if op_fn is None:
            msg = f"unexpected node operator: {node.op}"
            raise ValueError(msg)
        return op_fn(operand)

    def visit_Conditional(self: EvaluatorProtocol, node: ast.Conditional) -> Any:
        """Ternary ``cond ? body : orelse`` (Pine conditional expression).

        The unused branch is not evaluated. ``na`` / falsy tests take
        ``orelse`` (Python truthiness: ``None`` and ``0`` are false).
        """
        visit = self.visit
        if visit(node.test):
            return visit(node.body)
        return visit(node.orelse)

    def visit_Compare(self: EvaluatorProtocol, node: ast.Compare) -> Any:
        """Chained comparisons (``a < b < c``) with short-circuit and na rules.

        Operands evaluate left-to-right. A comparison that yields ``None``
        (operand was na) fails the chain → ``False`` so ``if a < b`` is false
        when either side is na. Element-wise list results are truthy only if
        any element is true.

        Args:
            node: Compare with left, ops, comparators

        Returns:
            ``True`` if every link succeeds, else ``False``
        """
        visit = self.visit
        left = visit(node.left)
        ops = node.ops
        comparators = node.comparators
        n = len(ops)

        # Short-circuit: stop at first failed comparison
        for i in range(n):
            op_t = type(ops[i])
            right = visit(comparators[i])

            tl = type(left)
            tr = type(right)
            # Scalar numeric compare — dominant after series unwrap / bar inject
            if (tl is float or tl is int) and (tr is float or tr is int):
                if op_t is ast.Lt:
                    result = left < right
                elif op_t is ast.LtE:
                    result = left <= right
                elif op_t is ast.Gt:
                    result = left > right
                elif op_t is ast.GtE:
                    result = left >= right
                elif op_t is ast.Eq:
                    result = left == right
                elif op_t is ast.NotEq:
                    result = left != right
                else:
                    raw = _CMPOP_RAW.get(op_t)
                    if raw is None:
                        result = visit(ops[i])(left, right)
                    else:
                        result = _elementwise_binary(raw, left, right)
            else:
                raw = _CMPOP_RAW.get(op_t)
                if raw is None:
                    result = visit(ops[i])(left, right)
                else:
                    result = _elementwise_binary(raw, left, right)

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
        """Evaluate a function or method call.

        Dispatch order (simplified):

        1. **Qualified-attribute builtins** — ``strategy.entry(...)``,
           ``ta.sma(...)`` resolved from the AST path *before* visiting
           intermediate attributes (zero-arg series would otherwise collapse
           the qualified name).
        2. **Bare-name builtins** — ``year(ts)``, ``na(x)``; user callables in
           ``context`` shadow bare ta.* aliases.
        3. **Method markers** from :meth:`~.names.NameEvaluator.visit_Attribute`
           — UDT methods, ``array.*``, drawing/matrix namespaces, extension
           ``method`` free functions.
        4. **``Type.new(...)``** UDT construction.
        5. **Callable** in context / recovered instance attr; non-callables
           soft-fail to ``None`` (na).

        Call-site resolution is cached by ``id(node)`` across bars: AST nodes
        are stable for the script lifetime, so qualified-name + registry
        lookups run once per site (not once per bar). Bound sites also store a
        precompiled **arg plan** so Name/Constant args skip ``visit`` frames.

        Args:
            node: Call with func and argument list (positional + named)

        Returns:
            Call result, or ``None`` on soft-fail
        """
        # Per-Call-node site cache (stable AST across the bar loop).
        # Pre-allocated on BaseEvaluator; miss → resolve once.
        site_cache = self.__dict__.get("_call_site_cache")
        if site_cache is None:
            site_cache = {}
            self._call_site_cache = site_cache  # type: ignore[attr-defined]
        site_key = id(node)
        site = site_cache.get(site_key)
        if site is None:
            site = self._resolve_call_site(node)
            site_cache[site_key] = site

        kind = site[0]

        # Bound qualified builtin (ta.sma after first bar) — no name lookup.
        # site = (_SITE_QB, tag, handler, name, arg_plan)
        # Dominant multi-TA path: check first.
        if kind == _SITE_QB:
            args, kwargs = self._eval_arg_plan(site[4])
            if kwargs is not _EMPTY_KW and kwargs:
                return self._call_builtin(site[3], args, kwargs=kwargs)  # type: ignore[attr-defined]
            tag, handler = site[1], site[2]
            if tag == 1:
                return handler(args)
            if tag == 0:
                return handler
            return handler(*args)

        # Bound bare Name builtin (plot after first bar).
        # site = (_SITE_BB, name, tag, handler, arg_plan)
        if kind == _SITE_BB:
            name, tag, handler, plan = site[1], site[2], site[3], site[4]
            args, kwargs = self._eval_arg_plan(plan)
            user = self.context.get(name)  # type: ignore[attr-defined]
            if callable(user):
                try:
                    return user(*args, **kwargs)
                except TypeError as e:
                    if _type_error_from_callee(e):
                        raise
                    try:
                        return user(*args)
                    except TypeError as e2:
                        if _type_error_from_callee(e2):
                            raise
                        return None
            if kwargs is not _EMPTY_KW and kwargs:
                return self._call_builtin(name, args, kwargs=kwargs)  # type: ignore[attr-defined]
            if tag == 1:
                return handler(args)
            if tag == 0:
                return handler
            return handler(*args)

        # Fast path: ta.*/strategy.*/math.* — resolve name once, then bind.
        # site = (_SITE_Q, name, arg_plan)
        if kind == _SITE_Q:
            name, plan = site[1], site[2]
            args, kwargs = self._eval_arg_plan(plan)
            result = self._call_builtin(name, args, kwargs=kwargs)  # type: ignore[attr-defined]
            bound = self._lookup_bound_builtin(name)
            if bound is not None:
                site_cache[site_key] = (_SITE_QB, bound[0], bound[1], name, plan)
            return result

        # Fast path: bare Name builtins (plot, na, year, …).
        # User callables in context still shadow each bar (cheap dict.get).
        # site = (_SITE_B, name, arg_plan)
        if kind == _SITE_B:
            name, plan = site[1], site[2]
            args, kwargs = self._eval_arg_plan(plan)
            user = self.context.get(name)  # type: ignore[attr-defined]
            if callable(user):
                try:
                    return user(*args, **kwargs)
                except TypeError as e:
                    if _type_error_from_callee(e):
                        raise
                    try:
                        return user(*args)
                    except TypeError as e2:
                        if _type_error_from_callee(e2):
                            raise
                        return None
            result = self._call_builtin(name, args, kwargs=kwargs)  # type: ignore[attr-defined]
            bound = self._lookup_bound_builtin(name)
            if bound is not None:
                site_cache[site_key] = (_SITE_BB, name, bound[0], bound[1], plan)
            return result

        # Bare-name UDF / local callable — skip visit(func) Attribute machinery.
        # site = (_SITE_GN, name, arg_plan)
        if kind == _SITE_GN:
            name, plan = site[1], site[2]
            args, kwargs = self._eval_arg_plan(plan)
            func = self.context.get(name)  # type: ignore[attr-defined]
            if not callable(func):
                # Name may be lazy string or missing — fall back once.
                return self._visit_Call_general(node, plan)
            try:
                return func(*args, **kwargs)
            except TypeError as e:
                if _type_error_from_callee(e):
                    raise
                try:
                    return func(*args)
                except TypeError as e2:
                    if _type_error_from_callee(e2):
                        raise
                    return None

        # General path: methods, UDT.new, recovered attrs.
        # site = (_SITE_G, arg_plan)
        return self._visit_Call_general(node, site[1] if len(site) > 1 else None)

    def _lookup_bound_builtin(self: EvaluatorProtocol, name: str) -> tuple[int, Any] | None:
        """Return ``(tag, handler)`` from the resolved-builtin cache, if present."""
        resolved = self.__dict__.get("_builtin_resolved")
        if not resolved:
            return None
        return resolved.get(name)

    def _resolve_call_site(self: EvaluatorProtocol, node: ast.Call) -> tuple:
        """Classify a Call node once for the bar-loop site cache.

        Returns site tuples that always include a precompiled arg plan.
        """
        plan = self._build_arg_plan(node)
        func = node.func
        # Attribute: prefer AST qualified path (ta.sma, strategy.entry, …).
        if type(func) is ast.Attribute:
            qual = ast_qualified_name(func)
            if qual and self._is_registered_builtin(qual):
                return (_SITE_Q, qual, plan)
            return (_SITE_G, plan)
        # Bare Name: plot / na / year / bare ta aliases / UDFs.
        if type(func) is ast.Name:
            name = func.id
            if self._is_registered_builtin(name):
                return (_SITE_B, name, plan)
            return (_SITE_GN, name, plan)
        return (_SITE_G, plan)

    def _build_arg_plan(self: EvaluatorProtocol, node: ast.Call) -> tuple:
        """Precompile Call args into opcodes so hot bars skip visit frames.

        Name → context lookup (same semantics as :meth:`visit_Name` hot path).
        Constant with ``kind is None`` or ``"#"`` → literal value.
        Everything else falls back to ``visit(value_ast)``.
        """
        arg_nodes = node.args
        if not arg_nodes:
            return ()
        plan: list[tuple] = []
        for arg in arg_nodes:
            kw = arg.name  # type: ignore[attr-defined]
            val = arg.value  # type: ignore[attr-defined]
            vt = type(val)
            if vt is ast.Name:
                if kw:
                    plan.append((_AP_KW_NAME, kw, val.id))
                else:
                    plan.append((_AP_NAME, val.id))
            elif vt is ast.Constant and (val.kind is None or val.kind == "#"):
                if kw:
                    plan.append((_AP_KW_CONST, kw, val.value))
                else:
                    plan.append((_AP_CONST, val.value))
            else:
                if kw:
                    plan.append((_AP_KW_VISIT, kw, val))
                else:
                    plan.append((_AP_VISIT, val))
        return tuple(plan)

    def _eval_arg_plan(
        self: EvaluatorProtocol,
        plan: tuple,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Execute a precompiled arg plan → ``(args, kwargs)``.

        Name resolution mirrors :meth:`~.names.NameEvaluator.visit_Name` for the
        dominant context-hit path; KeyError falls through to bare-series / lazy
        name semantics without allocating a temporary AST node.

        Common shapes (plot(x), ta.sma(x, n), ta.bb(x, n, mult)) are unrolled
        to avoid per-arg opcode branching and list appends.
        """
        n = len(plan)
        if n == 0:
            return [], _EMPTY_KW

        ctx = self.context  # type: ignore[attr-defined]
        bare = _BARE_SERIES_BUILTINS

        # --- Unrolled positional-only shapes (no kwargs) ---
        if n == 1:
            op = plan[0]
            code = op[0]
            if code == _AP_NAME:
                name = op[1]
                try:
                    return [ctx[name]], _EMPTY_KW
                except KeyError:
                    if name in bare and self._is_registered_builtin(name):
                        return [self._call_builtin(name, [])], _EMPTY_KW  # type: ignore[attr-defined]
                    return [name], _EMPTY_KW
            if code == _AP_CONST:
                return [op[1]], _EMPTY_KW
            if code == _AP_VISIT:
                return [self.visit(op[1])], _EMPTY_KW
            # single kwarg — fall through

        elif n == 2:
            a0, a1 = plan[0], plan[1]
            c0, c1 = a0[0], a1[0]
            # ta.sma(close, 14) / ta.highest(high, 20)
            if c0 == _AP_NAME and c1 == _AP_CONST:
                name = a0[1]
                try:
                    return [ctx[name], a1[1]], _EMPTY_KW
                except KeyError:
                    if name in bare and self._is_registered_builtin(name):
                        return [self._call_builtin(name, []), a1[1]], _EMPTY_KW  # type: ignore[attr-defined]
                    return [name, a1[1]], _EMPTY_KW
            if c0 == _AP_NAME and c1 == _AP_NAME:
                n0, n1 = a0[1], a1[1]
                try:
                    return [ctx[n0], ctx[n1]], _EMPTY_KW
                except KeyError:
                    pass  # fall through to general
            if c0 == _AP_CONST and c1 == _AP_CONST:
                return [a0[1], a1[1]], _EMPTY_KW

        elif n == 3:
            a0, a1, a2 = plan[0], plan[1], plan[2]
            # ta.bb(close, 20, 2.0)
            if a0[0] == _AP_NAME and a1[0] == _AP_CONST and a2[0] == _AP_CONST:
                name = a0[1]
                try:
                    return [ctx[name], a1[1], a2[1]], _EMPTY_KW
                except KeyError:
                    if name in bare and self._is_registered_builtin(name):
                        return [self._call_builtin(name, []), a1[1], a2[1]], _EMPTY_KW  # type: ignore[attr-defined]
                    return [name, a1[1], a2[1]], _EMPTY_KW

        # --- General opcode interpreter ---
        visit = self.visit
        args: list[Any] = []
        kwargs: dict[str, Any] | None = None
        for op in plan:
            code = op[0]
            if code == _AP_NAME:
                name = op[1]
                try:
                    args.append(ctx[name])
                except KeyError:
                    if name in bare and self._is_registered_builtin(name):
                        args.append(self._call_builtin(name, []))  # type: ignore[attr-defined]
                    else:
                        args.append(name)
            elif code == _AP_CONST:
                args.append(op[1])
            elif code == _AP_VISIT:
                args.append(visit(op[1]))
            elif code == _AP_KW_NAME:
                if kwargs is None:
                    kwargs = {}
                name = op[2]
                try:
                    kwargs[op[1]] = ctx[name]
                except KeyError:
                    if name in bare and self._is_registered_builtin(name):
                        kwargs[op[1]] = self._call_builtin(name, [])  # type: ignore[attr-defined]
                    else:
                        kwargs[op[1]] = name
            elif code == _AP_KW_CONST:
                if kwargs is None:
                    kwargs = {}
                kwargs[op[1]] = op[2]
            else:  # _AP_KW_VISIT
                if kwargs is None:
                    kwargs = {}
                kwargs[op[1]] = visit(op[2])
        return args, kwargs if kwargs is not None else _EMPTY_KW

    def _visit_Call_general(
        self: EvaluatorProtocol,
        node: ast.Call,
        arg_plan: tuple | None = None,
    ):
        """Call dispatch for non-static-builtin sites (methods, UDFs, UDT).

        Skips re-checking ``_is_qualified_attribute_builtin_call`` /
        bare-name registry (already classified as general by the site cache).
        """
        func = self.visit(node.func)
        if arg_plan is not None:
            args, kwargs = self._eval_arg_plan(arg_plan)
        else:
            args, kwargs = self._collect_call_args(node)

        # Method markers from visit_Attribute: one type check, then tag.
        if type(func) is tuple and len(func) == _METHOD_CALL_TUPLE_LENGTH:
            tag = func[0]
            if tag == "_method_call":
                _, obj_instance, method_name = func
                return self._invoke_method(obj_instance, method_name, args, kwargs)
            if tag == "_array_method":
                _, receiver, method_name = func
                return self._call_builtin(  # type: ignore[attr-defined]
                    f"array.{method_name}", [receiver, *args], kwargs=kwargs
                )
            if tag == "_ns_method":
                _, receiver, qual_name = func
                return self._call_builtin(qual_name, [receiver, *args], kwargs=kwargs)  # type: ignore[attr-defined]
            if tag == "_ext_method":
                _, receiver, method_name = func
                ext = self.context.get(method_name)  # type: ignore[attr-defined]
                if callable(ext):
                    try:
                        return ext(receiver, *args, **kwargs)
                    except TypeError as e:
                        if _type_error_from_callee(e):
                            raise
                        try:
                            return ext(receiver, *args)
                        except TypeError as e2:
                            if _type_error_from_callee(e2):
                                raise
                            return None
                return None

        # Handle .new() method for UDT instantiation
        node_func = node.func
        if type(node_func) is ast.Attribute and node_func.attr == "new":
            type_obj = self._resolve_udt_constructor(node_func.value)
            if isinstance(type_obj, UserDefinedType):
                return self._handle_udt_new(type_obj, args, kwargs)

        # Zero-arg call on a UDT/series field: ``this.columns()`` where ``columns``
        # is an int field. Prefer the field value over "not callable".
        if (
            type(node_func) is ast.Attribute
            and not args
            and not kwargs
            and not isinstance(func, (str, tuple))
            and not callable(func)
        ):
            return func

        # Handle built-in functions recovered as qualified-name strings
        if isinstance(func, str):
            # Empty string is not a callable name (dual-mode property value).
            if not func:
                if type(node_func) is ast.Attribute:
                    recovered = self._recover_instance_attr_call(node_func, args, kwargs)
                    if recovered is not _ATTR_CALL_MISS:
                        return recovered
                return None
            if type(node_func) is ast.Attribute and (
                "." in func or not self._is_registered_builtin(func)
            ):
                recovered = self._recover_instance_attr_call(node_func, args, kwargs)
                if recovered is not _ATTR_CALL_MISS:
                    return recovered
            return self._call_builtin(func, args, kwargs=kwargs)  # type: ignore[attr-defined]

        # Soft-fail non-callables (stubs, na) — return None
        if not callable(func):
            return None
        try:
            return func(*args, **kwargs)
        except TypeError as e:
            # Signature mismatch → na; TypeError raised inside callee → fail closed
            if _type_error_from_callee(e):
                raise
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

        Computes the qualified name once (no double ``ast_qualified_name``).
        """
        node_func = node.func
        if not isinstance(node_func, ast.Attribute):
            # Caller violated the precondition; fail loudly so the bug is
            # obvious in development rather than silently miscompiling.
            raise TypeError("_dispatch_qualified_attribute_builtin requires node.func to be ast.Attribute")
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

        Local ``visit`` bind + positional-only empty kwargs (no dict alloc
        until a named arg appears).
        """
        arg_nodes = node.args
        if not arg_nodes:
            return [], _EMPTY_KW
        # Prefer precompiled plan (Name/Const skip visit frames).
        return self._eval_arg_plan(self._build_arg_plan(node))

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
                    except TypeError as e:
                        if _type_error_from_callee(e):
                            raise
                        return None

        # Extension methods (including na receiver)
        ext = self.context.get(name) if hasattr(self, "context") else None  # type: ignore[attr-defined]
        if callable(ext) and getattr(ext, "__pine_method__", False):
            try:
                return ext(receiver, *args, **kwargs)
            except TypeError as e:
                if _type_error_from_callee(e):
                    raise
                try:
                    return ext(receiver, *args)
                except TypeError as e2:
                    if _type_error_from_callee(e2):
                        raise
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
        """Construct a UDT instance (``TypeName.new(...)`` / positional + kwargs fields)."""
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
        """Run a UDT method body with in-place parameter rebind on ``context``.

        Binds the receiver as the first parameter (and always as ``this``),
        applies defaults, executes the method body, then restores prior
        bindings. Does **not** ``dict.copy()`` the context — hosts mutate
        ``bar_index`` / OHLCV on the same dict each bar.

        Built-in ``copy`` (no user body) returns a shallow :class:`ObjectInstance`
        clone — required by motion/console ``option.copy()`` / ``theme.copy()``.
        """
        # Built-in UDT methods (not user-defined method bodies)
        if method_name == "copy":
            return obj_instance.copy()

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
        # Prefer AST path for Attribute bases (array.new) — do not evaluate
        if isinstance(node.value, ast.Attribute):
            base = ast_qualified_name(node.value)
        else:
            base = self.visit(node.value)

        type_name: str | None = None
        type_arg = node.args
        if isinstance(type_arg, ast.Name):
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
        """Evaluate ``if`` / ``else``; return the last expression of the taken branch.

        Body statements that are not ``Expr`` still run for side effects.
        Uses Python truthiness (``None``/``0``/``False`` → else branch).

        Args:
            node: If with test, body, orelse

        Returns:
            Last expression value of the taken branch, or ``None``
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
