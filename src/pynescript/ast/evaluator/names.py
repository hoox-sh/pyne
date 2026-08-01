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

"""Name, attribute, and subscript resolution for the Pine evaluator.

:class:`NameEvaluator` turns identifiers and ``a.b[i]`` paths into runtime
values or call markers consumed by :class:`~.expressions.ExpressionEvaluator`.

**Series history indexing (Pine):**

- For plain **lists** (the usual host bar-mode series: chronological, oldest
  first, newest last): ``series[0]`` is the current bar (``list[-1]``),
  ``series[1]`` is one bar ago (``list[-2]``), etc. Out of range → ``None``
  (na). Negative indices are rejected.
- Series **wrappers** with a ``history`` list often store **most-recent-first**
  history; array-method recovery may reverse that to chronological order.
- Scalars with no history: ``x[0]`` → ``x``, ``x[i>0]`` → ``None``.

**``na``:** bare name ``na`` resolves via the zero-arg builtin path to
``None``. Missing attributes soft-fail to ``None`` rather than a truthy
placeholder string.
"""

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
        "timenow",
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

# Pine host attr name → Python attribute when the two spellings differ.
_HOST_ATTR_ALIASES: dict[str, str] = {
    "is_heikinashi": "is_heikin_ashi",
    "is_heikin_ashi": "is_heikinashi",
    "is_linebreak": "is_line_break",
    "is_line_break": "is_linebreak",
    "is_pointfigure": "is_point_figure",
    "is_point_figure": "is_pointfigure",
    # TV ``chart.is_pnf`` (point-and-figure) → host ``is_point_figure``
    "is_pnf": "is_point_figure",
}


def ast_qualified_name(expr: ast.AST) -> str | None:
    """Build ``a.b.c`` from Attribute/Name AST nodes without evaluating values.

    Critical for strategy/request builtins: intermediate names like
    ``strategy.opentrades`` are zero-arg series variables; evaluating them
    while resolving ``strategy.opentrades.entry_price(...)`` would yield an
    int and break the longer qualified path.

    Iterative (not recursive) to avoid call frames on hot ``ta.*`` paths;
    dominant depth is 2 (``ta.sma``).
    """
    # Fast path: bare Name
    if isinstance(expr, ast.Name):
        return expr.id
    if not isinstance(expr, ast.Attribute):
        return None
    # Unroll first Attribute hop (ta.sma / strategy.entry)
    attr1 = expr.attr
    base = expr.value
    if isinstance(base, ast.Name):
        return f"{base.id}.{attr1}"
    if not isinstance(base, ast.Attribute):
        return None
    # Depth ≥ 3: strategy.opentrades.entry_price etc.
    parts: list[str] = [attr1, base.attr]
    cur = base.value
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return ".".join(parts)
    return None


class NameEvaluator:
    """Mixin: ``Name``, ``Attribute``, ``Subscript`` resolution.

    Produces either concrete values or method-call markers
    (``_method_call``, ``_array_method``, ``_ns_method``, ``_ext_method``)
    that :meth:`~.expressions.ExpressionEvaluator.visit_Call` consumes.
    """

    def visit_Name(self: EvaluatorProtocol, node: ast.Name) -> Any:
        """Resolve a bare identifier from ``context`` or as a zero-arg builtin.

        Lookup order:

        1. ``context[name]`` (hot path for OHLCV / locals each bar)
        2. Bare-series builtins (``na``, ``last_bar_index``, calendar series, …)
           via ``_call_builtin`` — so bare ``na`` yields ``None``
        3. Else the name **string** (lazy path for later builtin/call resolution)

        Args:
            node: Name with ``id``

        Returns:
            Bound value, builtin result, or unresolved name string
        """
        # Hot path: single dict lookup for bar-mode series (close/open/…) and locals.
        # ``try/except KeyError`` is faster than ``in`` + ``[]`` when the key hits
        # (dominant case after hosts inject OHLCV every bar).
        name = node.id
        try:
            return self.context[name]
        except KeyError:
            pass
        # Bare-name series builtins only (not functions like strategy/indicator that take args)
        if name in _BARE_SERIES_BUILTINS and self._is_registered_builtin(name):
            return self._call_builtin(name, [])
        # Return the name as a string if not in context - allows for lazy evaluation
        return name

    def visit_Attribute(self: EvaluatorProtocol, node: ast.Attribute) -> Any:
        """Resolve ``obj.attr`` / ``module.member`` without breaking qualified calls.

        Prefer AST-only qualified paths (see :func:`ast_qualified_name`) and
        registered zero-arg builtins **before** evaluating intermediate bases,
        so ``strategy.opentrades.entry_price(...)`` is not collapsed by
        evaluating ``strategy.opentrades`` to an int.

        Also handles library exports, UDT fields/methods, enums, array/drawing/
        matrix instance methods, and extension methods (including ``na``
        receivers). Unknown non-builtin paths return ``None`` (na).

        Args:
            node: Attribute with value and attr

        Returns:
            Value, method marker tuple, qualified-name string, or ``None``
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
            # Built-in UDT methods always available (not stored in type.methods):
            # ``instance.copy()`` — shallow clone (motion: ``__opt.copy()``).
            if node.attr == "copy":
                return ("_method_call", value, "copy")
            # Extension methods defined as free ``method foo(Type this, …)``
            # (motion: ``timer.isset(timer.new())``, ``option.isset(...)``).
            # Must run *before* field lookup so missing fields don't shadow them.
            ext = self.context.get(node.attr) if hasattr(self, "context") else None
            if callable(ext) and (
                getattr(ext, "__pine_method__", False)
                or getattr(ext, "__pine_overloads__", None)
            ):
                return ("_ext_method", value, node.attr)
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

        # Fallback: try getattr for plain Python objects (Syminfo, Timeframe, Chart, …).
        # None has no attributes worth reflecting.
        if value is not None and hasattr(value, node.attr):
            return getattr(value, node.attr)

        # Chart / host object aliases: Pine ``is_heikinashi`` vs ``is_heikin_ashi``.
        if value is not None and not isinstance(value, (str, int, float, bool, list, dict, tuple)):
            alias = _HOST_ATTR_ALIASES.get(node.attr)
            if alias is not None and hasattr(value, alias):
                return getattr(value, alias)

        # Last resort:
        # - If the qualified path is a *registered* builtin, keep the string so
        #   later Call dispatch can resolve it (historical lazy path).
        # - Otherwise return ``None`` (na). Returning a truthy string for unknown
        #   attrs (e.g. ``chart.is_heikinashi``) made booleans always true.
        if qualified_name and self._is_registered_builtin(qualified_name):
            return qualified_name
        return None

    def visit_Subscript(self: EvaluatorProtocol, node: ast.Subscript) -> Any:
        """Index a series, array, or matrix (``series[i]``, ``m[row, col]``).

        Pine series indexing (most-recent-first **offset**, not Python index):

        - ``series[0]`` — current bar
        - ``series[1]`` — previous bar
        - ``series[i]`` with ``i >= len`` — ``None`` (na)
        - ``series[na]`` / NaN / negative offset — ``None`` (na; soft-fail)

        Host lists are stored **chronologically** (oldest first), so the
        implementation maps offset ``i`` to ``list[-(i + 1)]``. Float offsets
        coerce to int. Matrix uses ``[row, col]``. String / container OOB
        (``IndexError`` / ``KeyError``) also soft-fails to na.

        Args:
            node: Subscript with value and slice

        Returns:
            Indexed element or ``None`` (na / out of range)

        Raises:
            ValueError: Bad matrix index, hard getitem failures, or unsupported pair
        """
        visit = self.visit
        # Evaluate the collection being indexed (e.g., array, series)
        value = visit(node.value)
        # Evaluate the index/slice expression
        slice_node = node.slice
        slice_ = visit(slice_node) if slice_node is not None else None  # type: ignore[arg-type]

        st = type(slice_)
        # na index → na (do not crash the bar loop)
        if slice_ is None:
            return None
        # Pine coerces float offsets (e.g. ``depth / 2``) to int for series[i]
        if st is float:
            if slice_ != slice_:  # NaN
                return None
            slice_ = int(slice_)
            st = int
        elif st is bool:
            # bool is int subclass; keep 0/1 but avoid treating as generic truthy
            slice_ = int(slice_)
            st = int

        vt = type(value)

        # Fast path: list/array with integer index (history series / array.get style)
        if vt is list and st is int:
            # Negative history offsets are invalid Pine; soft-fail to na
            # (warmup / for-to auto-step / highestbars misuse) rather than abort.
            if slice_ < 0:
                return None
            # Pine: series[0] = current (latest) → list[-1]; series[i] → list[-(i+1)]
            # Bounds: slice_ >= len → na (equivalent to abs(-(i+1)) > len)
            n = len(value)
            if slice_ >= n:
                return None
            return value[-(slice_ + 1)]

        # Handle Matrix indexing: m[row, col]
        if isinstance(value, Matrix):
            # slice_ should be a list [row, col] (from Tuple evaluation)
            if type(slice_) is list and len(slice_) == _MATRIX_INDEX_DIMENSIONS:
                return value[(slice_[0], slice_[1])]
            msg = f"Invalid matrix index: {slice_}. Expected [row, col]."
            raise ValueError(msg)

        # list subclasses (rare) — same Pine reverse-index semantics
        if isinstance(value, list) and st is int:
            if slice_ < 0:
                return None
            n = len(value)
            if slice_ >= n:
                return None
            return value[-(slice_ + 1)]

        if hasattr(value, "__getitem__"):
            try:
                return value[slice_]
            except (IndexError, KeyError):
                # str/list OOB, missing map key, etc. → na (do not abort bar)
                return None
            except Exception as e:
                msg = f"Subscript error for {type(value).__name__} with index {slice_}: {e}"
                raise ValueError(msg) from e
        # When subscripting a non-collection type (scalar), match PineScript
        # semantics: series[0] = current (the scalar itself), series[offset>0]
        # with no history returns None (PineScript 'na'). Negative → na.
        if st is int:
            if slice_ < 0 or slice_ > 0:
                return None
            return value
        value_type = type(value)
        slice_type = type(slice_)
        msg = f"Subscript not supported for {value_type} with {slice_type}"
        raise ValueError(msg)
