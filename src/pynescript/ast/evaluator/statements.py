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

# Sentinel: param was not present in context before binding (pop on unbind).
_CONTEXT_MISSING: Any = object()


def _type_spec_tag(spec: Any) -> str | None:
    """Coarse type tag from a type AST node (Name / Qualify / Specialize / Attribute)."""
    if spec is None:
        return None
    # matrix<float> / array<label> / map<string, float>
    if isinstance(spec, ast.Specialize):
        base = spec.value
        base_tag: str | None = None
        if isinstance(base, ast.Name):
            base_tag = base.id
        elif isinstance(base, ast.Attribute):
            base_tag = base.attr
        if not base_tag:
            return None
        # First type argument only (array/matrix element, map key ignored)
        elem = spec.args
        elem_tag: str | None = None
        if isinstance(elem, ast.Name):
            elem_tag = elem.id
        elif isinstance(elem, ast.Attribute):
            elem_tag = elem.attr
        elif isinstance(elem, ast.Specialize):
            elem_tag = _type_spec_tag(elem)
        if elem_tag:
            return f"{base_tag}.{elem_tag}"
        return base_tag
    # series label / series string / series color
    if isinstance(spec, ast.Qualify):
        return _type_spec_tag(spec.value)
    if isinstance(spec, ast.Name):
        return spec.id
    if isinstance(spec, ast.Attribute):
        # chart.point → point (receiver matching uses point / ChartPoint)
        return spec.attr
    return None


def _first_param_type_tag(node: ast.FunctionDef) -> str | None:
    """Extract a coarse type tag from a method's first parameter for overload dispatch.

    Examples: ``matrix.float``, ``array.label``, ``label``, ``theme``, ``string``.
    """
    tags = _param_type_tags(node)
    return tags[0] if tags else None


def _param_type_tags(node: ast.FunctionDef) -> list[str | None]:
    """Type tags for every method parameter (receiver first)."""
    tags: list[str | None] = []
    for param in node.args:
        if not isinstance(param, ast.Param):
            continue
        tags.append(_type_spec_tag(param.type) if param.type is not None else None)
    return tags


_SERIES_TYPE_NAMES = frozenset({"PineSeries", "_SeriesResult"})
_UNWRAP_MISSING = object()


def _unwrap_series_receiver(receiver: Any) -> Any:
    """If *receiver* is a PineSeries-like wrapper, return its current scalar."""
    t = type(receiver)
    if t is float or t is int or receiver is None or t is bool:
        return receiver
    if t is list or t is str or t is tuple or t is dict or t is bytes:
        return receiver
    if t.__name__ in _SERIES_TYPE_NAMES:
        return receiver.current
    current = getattr(receiver, "current", _UNWRAP_MISSING)
    if current is not _UNWRAP_MISSING and hasattr(receiver, "history"):
        return current
    return receiver


def _normalize_na(value: Any) -> Any:
    """Map unresolved bare-name ``\"na\"`` (and similar) to the na sentinel None.

    Before bare ``na`` was wired to the builtin, ``visit_Name`` returned the
    string ``\"na\"``. That broke optional UDT args (``init(theme = na)``) and
    multi-dispatch (theme tag rejected the string → generic ``str()`` fallback
    destroyed ObjectInstance / Label receivers — Console ``testLabel.delete``).
    """
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in {"na", "nan", "none"}:
        return None
    return value


# Types that must never win multi-dispatch for ``na`` receivers (matrix tostring
# uses this.columns(); drawing types don't make sense for na either).
_NA_EXCLUDED_TAGS = frozenset(
    {
        "matrix",
        "array",
        "map",
        "label",
        "line",
        "linefill",
        "box",
        "polyline",
        "point",
        "footprint",
        "volume_row",
    }
)


def _receiver_matches_type_tag(tag: str | None, receiver: Any) -> bool:
    """True if *receiver* is compatible with a method first-param type tag."""
    if tag is None:
        return False
    tag_l = tag.lower()
    receiver = _normalize_na(receiver)
    # na: only match isset-style / primitive overloads — never matrix/array tostring
    if receiver is None:
        base = tag_l.split(".", 1)[0]
        return base not in _NA_EXCLUDED_TAGS

    # Built-in drawing / collection types
    try:
        from pynescript.ast.evaluator.builtins.drawing import Box
        from pynescript.ast.evaluator.builtins.drawing import ChartPoint
        from pynescript.ast.evaluator.builtins.drawing import Label
        from pynescript.ast.evaluator.builtins.drawing import Line
        from pynescript.ast.evaluator.builtins.drawing import LineFill
        from pynescript.ast.evaluator.builtins.drawing import Polyline
        from pynescript.ast.evaluator.builtins.drawing import Table
        from pynescript.ast.evaluator.builtins.matrix import Matrix
    except Exception:  # pragma: no cover
        Box = Label = Line = LineFill = Polyline = Table = ChartPoint = Matrix = ()  # type: ignore

    # matrix / matrix.float / matrix.string
    if tag_l == "matrix" or tag_l.startswith("matrix."):
        return isinstance(receiver, Matrix)
    # array / array.string / array<label>
    if tag_l == "array" or tag_l.startswith("array."):
        if not isinstance(receiver, list):
            return False
        if not tag_l.startswith("array."):
            return True
        if not receiver:
            return True  # empty array matches any array.*
        elem_tag = tag.split(".", 1)[1]
        return _receiver_matches_type_tag(elem_tag, receiver[0])
    # map / map.string (key type ignored)
    if tag_l == "map" or tag_l.startswith("map."):
        return isinstance(receiver, dict)
    if tag_l == "table" and isinstance(receiver, Table):
        return True
    if tag_l == "label" and isinstance(receiver, Label):
        return True
    if tag_l == "line" and isinstance(receiver, Line):
        return True
    if tag_l == "linefill" and isinstance(receiver, LineFill):
        return True
    if tag_l == "box" and isinstance(receiver, Box):
        return True
    if tag_l == "polyline" and isinstance(receiver, Polyline):
        return True
    if tag_l in {"chart.point", "point"} and isinstance(receiver, ChartPoint):
        return True
    if tag_l == "string" and isinstance(receiver, str):
        return True
    if tag_l == "int" and isinstance(receiver, int) and not isinstance(receiver, bool):
        return True
    if tag_l == "float" and isinstance(receiver, (int, float)) and not isinstance(receiver, bool):
        return True
    if tag_l == "bool" and isinstance(receiver, bool):
        return True
    if tag_l == "color":
        # Only hex / color.* / rgba strings — not every str (else string loses to color)
        if isinstance(receiver, str):
            s = receiver.strip()
            return s.startswith("#") or s.startswith("color.") or s.startswith("rgb")
        if isinstance(receiver, int) and not isinstance(receiver, bool):
            return True
        return False
    if isinstance(receiver, ObjectInstance) and receiver.udt.name == tag:
        return True
    return False


def _match_score(tag: str | None, receiver: Any) -> int:
    """Higher is better. Used to prefer string over weak color, float over int, etc."""
    if not _receiver_matches_type_tag(tag, receiver):
        return -1
    if tag is None:
        return 0
    tag_l = tag.lower()
    # Exact structural matches (prefer specialized array.string over bare array)
    if tag_l.startswith("matrix."):
        return 110
    if tag_l == "matrix":
        return 100
    if tag_l.startswith("array."):
        return 110
    if tag_l == "array":
        return 100
    if tag_l.startswith("map.") or tag_l == "map":
        return 100
    if tag_l in {"label", "line", "box", "table", "polyline", "linefill", "point"}:
        return 100
    if tag_l == "string" and isinstance(receiver, str):
        return 90
    if tag_l == "bool" and isinstance(receiver, bool):
        return 90
    if tag_l == "int" and isinstance(receiver, int) and not isinstance(receiver, bool):
        return 80
    if tag_l == "float" and isinstance(receiver, float):
        return 85
    if tag_l == "float" and isinstance(receiver, int) and not isinstance(receiver, bool):
        return 50  # int can widen to float
    if tag_l == "color":
        return 70
    if isinstance(receiver, ObjectInstance) and receiver.udt.name == tag:
        return 100
    if receiver is None:
        return 20
    return 10


def _score_overload_for_args(fn: Any, args: tuple | list) -> int:
    """Sum of per-arg match scores; -1 if any concrete arg fails to match.

    Prefers overloads whose typed-parameter count matches the number of
    provided args so ``log(terminal, string)`` wins over
    ``log(terminal, string, label)`` when only two args are passed.
    """
    tags = getattr(fn, "__pine_param_types__", None)
    if not tags:
        tags = [getattr(fn, "__pine_first_type__", None)]
    # Drop trailing None tags (untyped params)
    while tags and tags[-1] is None:
        tags = tags[:-1]
    if len(tags) < len(args):
        # Extra args with no parameter types — reject
        return -1
    total = 0
    for j, arg in enumerate(args):
        tag = tags[j] if j < len(tags) else None
        if tag is None:
            if j == 0:
                return -1
            continue
        s = _match_score(tag, arg)
        if s < 0:
            un = _unwrap_series_receiver(arg)
            if un is not arg:
                s = _match_score(tag, un)
            if s < 0:
                return -1
        total += s
    # Exact arity wins over overloads with unused optional trailing params
    if len(tags) == len(args):
        total += 30
    else:
        # optional trailing params: small penalty so 2-arg call prefers 2-param sig
        total -= 5 * (len(tags) - len(args))
    return total


def _pick_method_overload(overloads: list, receiver: Any, rest_args: tuple | list = ()) -> Any:
    """Choose the best method overload for call args (highest score, then last)."""
    # Coerce bare-name ``\"na\"`` so optional UDT params (theme = na) match.
    receiver = _normalize_na(receiver)
    rest_norm = [_normalize_na(a) for a in rest_args]
    call_args: list[Any] = [receiver, *rest_norm]

    scored: list[tuple[int, int, Any]] = []
    for i, fn in enumerate(overloads):
        score = _score_overload_for_args(fn, call_args)
        if score >= 0:
            scored.append((score, i, fn))

    if scored:
        scored.sort(key=lambda t: (t[0], t[1]))
        chosen = scored[-1][2]
        # If first arg is series and overload wants float/int, unwrap on call
        first_tag = (getattr(chosen, "__pine_param_types__", None) or [None])[0]
        unwrapped = _unwrap_series_receiver(receiver)
        if (
            unwrapped is not receiver
            and first_tag in {"float", "int", "bool", "string", "color"}
            and _match_score(first_tag, unwrapped) >= 0
        ):

            def _unwrap_and_call(*a, __fn=chosen, __scalar=unwrapped, **kwargs):
                if a:
                    return __fn(__scalar, *a[1:], **kwargs)
                return __fn(__scalar, **kwargs)

            _unwrap_and_call.__pine_method__ = True  # type: ignore[attr-defined]
            _unwrap_and_call.__pine_first_type__ = first_tag  # type: ignore[attr-defined]
            return _unwrap_and_call

        return chosen

    # No matching overload — never fall back to an arbitrary last method
    # (Console's last ``tostring`` is matrix and uses ``this.columns()``).
    if receiver is None:

        def _na_passthrough(*a, **kwargs):
            # isset(na, replacement) → replacement; tostring(na) → na
            return a[1] if len(a) > 1 else None

        _na_passthrough.__pine_method__ = True  # type: ignore[attr-defined]
        return _na_passthrough

    unwrapped = _unwrap_series_receiver(receiver)

    def _generic_tostring(*a, __recv=unwrapped if unwrapped is not receiver else receiver, **kwargs):
        r = a[0] if a else __recv
        r = _unwrap_series_receiver(r)
        r = _normalize_na(r)
        if r is None:
            return None
        if isinstance(r, bool):
            return "true" if r else "false"
        # Never stringify structured Pine values — that broke Console chaining
        # (``label.new(...).log_inline(console)`` → str → ``testLabel.delete``).
        if isinstance(r, ObjectInstance):
            return r
        if isinstance(r, (list, dict, tuple)):
            return r
        try:
            from pynescript.ast.evaluator.builtins.drawing import Box
            from pynescript.ast.evaluator.builtins.drawing import Label
            from pynescript.ast.evaluator.builtins.drawing import Line
            from pynescript.ast.evaluator.builtins.drawing import LineFill
            from pynescript.ast.evaluator.builtins.drawing import Polyline
            from pynescript.ast.evaluator.builtins.drawing import Table
            from pynescript.ast.evaluator.builtins.matrix import Matrix

            if isinstance(r, (Label, Line, Box, Table, Polyline, LineFill, Matrix)):
                return r
        except Exception:  # pragma: no cover
            pass
        return str(r)

    _generic_tostring.__pine_method__ = True  # type: ignore[attr-defined]
    return _generic_tostring


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
        # -- Handle var / varip: initialize once (first time declaration runs) --
        # Pine ``var`` is not strictly bar_index==0: a ``var`` inside
        # ``if barstate.islast`` or a function body must init on first
        # *execution* of that declaration, which may be a later bar.
        is_var = node.mode is not None and isinstance(node.mode, (ast.Var, ast.VarIp))
        is_const = node.mode is not None and isinstance(node.mode, ast.Const)  # v6 const decl

        if is_var:
            if isinstance(node.target, ast.Name):
                name: str = node.target.id  # type: ignore[attr-defined]
                declared: set[str] = self._var_declarations  # type: ignore[attr-defined]
                if name not in declared:
                    if node.value:
                        value = self.visit(node.value)  # type: ignore[attr-defined]
                        self.context[name] = value  # type: ignore[attr-defined]
                    declared.add(name)
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
                if isinstance(value, (list, tuple)):
                    values = list(value)
                elif hasattr(value, "history") and isinstance(getattr(value, "history", None), list):
                    # _SeriesResult: if history looks like a multi-value tuple
                    # (mixed / non-scalar elements), unpack history; else pad current.
                    hist = list(getattr(value, "history", []) or [])
                    # history is most-recent-first; multi-value returns store one
                    # tuple as a single "current" — prefer current when it is a
                    # sequence matching the unpack arity.
                    current = getattr(value, "current", None)
                    if isinstance(current, (list, tuple)) and len(current) == len(elts):
                        values = list(current)
                    elif len(hist) == len(elts) and not all(
                        x is None or isinstance(x, (int, float, bool)) for x in hist
                    ):
                        # chronological order for unpack (history is reverse)
                        values = list(reversed(hist))
                    else:
                        values = [current] * len(elts)
                elif value is not None and hasattr(value, "__iter__") and not isinstance(
                    value, (str, bytes, dict)
                ):
                    # Do NOT iterate Matrix/UDT objects as unpack sources — only
                    # plain sequences. Matrices are iterable by row and would
                    # corrupt `[arr, mat] = …` when the RHS is wrongly a matrix.
                    from pynescript.ast.evaluator.builtins.matrix import Matrix

                    if isinstance(value, Matrix):
                        values = [None] * len(elts)
                    else:
                        try:
                            values = list(value)
                        except TypeError:
                            values = [None] * len(elts)
                else:
                    # Soft-fail: assign None to each target (stub libs, na, etc.)
                    values = [None] * len(elts)
                # Pad / truncate to target count
                if len(values) < len(elts):
                    values = values + [None] * (len(elts) - len(values))
                for target_node, val in zip(elts, values, strict=False):
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
        """Handle reassignment (``x := x + 1`` / ``obj.field := value``).

        Evaluates the right-hand side and stores the result in the target
        variable. This is the Pine Script ``:=`` operator, distinct from
        ``AugAssign`` (``x += 1``). Supports simple names and UDT/object
        field mutation (``settings.devThreshold := …``).

        Args:
            node: The ReAssign node with target and value

        Raises:
            ValueError: If reassignment target is unsupported
        """
        value = self.visit(node.value)  # type: ignore[attr-defined]
        if isinstance(node.target, ast.Name):
            self.context[node.target.id] = value  # type: ignore[attr-defined]
            return

        # obj.field := value  (UDT instances and plain objects with setattr)
        if isinstance(node.target, ast.Attribute):
            obj = self.visit(node.target.value)  # type: ignore[attr-defined]
            if obj is None:
                return
            if isinstance(obj, ObjectInstance):
                obj.set_field(node.target.attr, value)
                return
            # Library/UDT-like objects that expose fields as attributes
            if hasattr(obj, "set_field") and callable(obj.set_field):
                obj.set_field(node.target.attr, value)
                return
            try:
                setattr(obj, node.target.attr, value)
                return
            except Exception:
                pass
            if isinstance(obj, dict):
                obj[node.target.attr] = value
                return

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
            ctx = self.context  # type: ignore[attr-defined]
            if var_name in ctx:
                current = ctx[var_name]
                rhs = self.visit(node.value)  # type: ignore[attr-defined]
                # Direct elementwise path (no wrapper frame); matches visit_BinOp.
                from pynescript.ast.evaluator.expressions import (
                    _BINOP_RAW,
                    _elementwise_binary,
                )

                raw = _BINOP_RAW.get(type(node.op))
                if raw is not None:
                    ctx[var_name] = _elementwise_binary(raw, current, rhs)
                    return

        msg = f"Unsupported augmented assignment: {type(node.target)}"
        self._error(msg)  # type: ignore[attr-defined]

    def visit_TypeDef(self, node: ast.TypeDef):
        """Process a type definition and register it in the TypeRegistry"""
        if getattr(self, "_pine_defs_locked", False):
            return
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
        if getattr(self, "_pine_defs_locked", False):
            return
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
        """Execute a while loop. v6 strict bool.

        Caps iterations at 1_000_000 (same as ``for``) so a non-terminating
        condition cannot hang the evaluator indefinitely.
        """
        last_result = None
        max_iters = 1_000_000
        iters = 0
        while iters < max_iters:
            iters += 1
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
        """Execute a for-to loop (numeric range).

        When ``by``/step is omitted, Pine uses ``+1`` if ``from <= to`` and
        ``-1`` if ``from > to`` (so ``for i = size - 1 to 0`` iterates downward).
        """
        target_name = node.target.id if isinstance(node.target, ast.Name) else None
        if not target_name:
            msg = "For loop target must be a name"
            self._error(msg)  # type: ignore[attr-defined]
            raise RuntimeError(msg)

        start = self.visit(node.start)  # type: ignore[attr-defined]
        if start is None:
            return None
        try:
            start_f = float(start)
        except (TypeError, ValueError):
            return None

        explicit_step = node.step is not None
        if explicit_step:
            step = self.visit(node.step)  # type: ignore[attr-defined]
            if step is None:
                return None
            try:
                step = float(step)
            except (TypeError, ValueError):
                return None
            if step == 0:
                return None
        else:
            step = None  # decide after first end eval

        # v6: re-evaluate the end bound on every iteration (dynamic for loop boundaries)
        # Pine Script for loops are inclusive of end
        current = start_f
        last_result = None
        # Safety cap against infinite loops from bad dynamic bounds
        max_iters = 1_000_000
        iters = 0
        while iters < max_iters:
            iters += 1
            end = self.visit(node.end)  # type: ignore[attr-defined]  # dynamic re-eval
            if end is None:
                break
            try:
                end_f = float(end)
            except (TypeError, ValueError):
                break
            if step is None:
                step = 1.0 if start_f <= end_f else -1.0
            if not (current <= end_f if step > 0 else current >= end_f):
                break
            # Prefer int counters when values are integral (array indices)
            self.context[target_name] = (  # type: ignore[attr-defined]
                int(current) if current == int(current) else current
            )
            result, should_break = self._execute_loop_body(node.body)
            if result is not None:
                last_result = result
            if should_break:
                break
            current += step
        return last_result

    def visit_ForIn(self, node: ast.ForIn):
        """Execute a for-in loop (iteration over collection).

        Supports:
        - ``for v in arr``
        - ``for [i, v] in arr`` — Pine index+value pairs over arrays (enumerate)
        - ``for [k, v] in pairs`` — unpack when each element is already a pair
        """
        target = node.target
        iterable = self.visit(node.iter)  # type: ignore[attr-defined]

        # Handle different iterable types (list, Matrix, Map?)
        # Pine Script 'for x in array' iterates values.
        # Soft-fail non-iterables (stubs, na, security scalars) → empty loop.
        if iterable is None:
            return None
        if isinstance(iterable, (str, bytes, dict)):
            return None
        if not hasattr(iterable, "__iter__"):
            return None

        last_result = None
        try:
            # Pine: ``for [i, v] in array`` yields index+value pairs.
            # Use enumerate when iterating a list with a 2-tuple target.
            use_enumerate = (
                isinstance(target, ast.Tuple)
                and len(target.elts) == 2
                and isinstance(iterable, list)
            )
            iterator = enumerate(iterable) if use_enumerate else iter(iterable)
        except TypeError:
            return None

        for item in iterator:
            # Bind loop target(s)
            if isinstance(target, ast.Name):
                self.context[target.id] = item  # type: ignore[attr-defined]
            elif isinstance(target, ast.Tuple):
                if isinstance(item, (list, tuple)):
                    values = list(item)
                else:
                    values = [item]
                elts = target.elts
                if len(values) < len(elts):
                    values = values + [None] * (len(elts) - len(values))
                for tnode, val in zip(elts, values, strict=False):
                    if isinstance(tnode, ast.Name):
                        self.context[tnode.id] = val  # type: ignore[attr-defined]
            else:
                msg = "For loop target must be a name or tuple"
                self._error(msg)  # type: ignore[attr-defined]
                raise RuntimeError(msg)

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
        """Define a user-defined function or method.

        Pine ``method m(Type this, ...) => ...`` (outside a type body) is
        registered on the UDT so ``instance.m()`` resolves. The same
        callable is also stored under ``m`` for free-function form.

        Bar-loop hosts re-visit the full script AST each bar. After the first
        bar, ``_pine_defs_locked`` skips re-binding so multi-dispatch tables
        do not grow unboundedly (Console ``tostring`` × N bars → timeout).
        """
        # Already bound on a prior bar — keep existing callables.
        if getattr(self, "_pine_defs_locked", False):
            return

        if node.method:
            self._register_standalone_method(node)

        func_name = node.name

        # Create a closure
        def user_function(*args, **kwargs):
            """Call a user function without replacing ``self.context``.

            Runtime hosts (pyne-worker) mutate the *same* context dict each bar
            (``bar_index``, ``time``, …). Replacing ``self.context`` with
            ``dict.copy()`` orphaned those updates so every function always
            saw ``bar_index == 0``. Only parameter bindings are scoped; other
            keys (including ``var`` locals) stay on the live context so they
            persist across bars for the call site.
            """
            ctx = self.context  # type: ignore[attr-defined]
            params = [arg for arg in node.args if isinstance(arg, ast.Param)]
            saved: dict[str, Any] = {}
            missing = _CONTEXT_MISSING

            def _bind(name: str, value: Any) -> None:
                if name not in saved:
                    saved[name] = ctx[name] if name in ctx else missing
                ctx[name] = value

            try:
                # Bind positional arguments
                for i, value in enumerate(args):
                    if i < len(params):
                        _bind(params[i].name, value)

                # Bind keyword arguments
                for key, value in kwargs.items():
                    _bind(key, value)

                # Apply parameter defaults for unbound params
                for param in params:
                    if param.name not in saved and param.default is not None:
                        _bind(param.name, self.visit(param.default))  # type: ignore[attr-defined]

                # Execute body
                result = None
                for stmt in node.body:
                    if isinstance(stmt, ast.Expr):
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

        # Tag Pine ``method`` callables so instance dispatch does not treat
        # ordinary functions (e.g. local ``update()``) as extension methods
        # on every object (``zigZag.update()`` → infinite recursion).
        if node.method:
            user_function.__pine_method__ = True  # type: ignore[attr-defined]
            param_tags = _param_type_tags(node)
            user_function.__pine_first_type__ = param_tags[0] if param_tags else None  # type: ignore[attr-defined]
            user_function.__pine_param_types__ = param_tags  # type: ignore[attr-defined]
            # Multi-dispatch overloads (Console: dozens of ``tostring`` / ``log`` / ``isset``).
            # Last definition used to overwrite the previous → wrong body ran
            # (e.g. c.log("hi") picking log(terminal, label) → recursive this.log).
            existing = self.context.get(func_name)  # type: ignore[attr-defined]
            overloads: list = []
            if callable(existing) and getattr(existing, "__pine_overloads__", None):
                overloads = list(existing.__pine_overloads__)  # type: ignore[attr-defined]
            elif callable(existing) and getattr(existing, "__pine_method__", False):
                overloads = [existing]
            # Dedup by param-type signature so a second full-script pass (bar loop
            # without defs lock) replaces rather than appends. Unbounded growth
            # made multi-dispatch O(bars²) and hit the 30s frontend timeout.
            replaced = False
            for i, prev in enumerate(overloads):
                if getattr(prev, "__pine_param_types__", None) == param_tags:
                    overloads[i] = user_function
                    replaced = True
                    break
            if not replaced:
                overloads.append(user_function)

            def multi_dispatch(*args, __overloads=overloads, **kwargs):
                # Coerce bare-name \"na\" → None before dispatch and body bind
                # (Console: ``.init(_THEME ? customTheme : na)``).
                args = tuple(_normalize_na(a) for a in args)
                if not args:
                    return __overloads[-1](*args, **kwargs)
                chosen = _pick_method_overload(__overloads, args[0], args[1:])
                return chosen(*args, **kwargs)

            multi_dispatch.__pine_method__ = True  # type: ignore[attr-defined]
            multi_dispatch.__pine_overloads__ = overloads  # type: ignore[attr-defined]
            multi_dispatch.__pine_first_type__ = None  # type: ignore[attr-defined]
            multi_dispatch.__pine_param_types__ = None  # type: ignore[attr-defined]
            self.context[func_name] = multi_dispatch  # type: ignore[attr-defined]
            if getattr(node, "export", None):
                self._register_export(func_name, multi_dispatch)
            return

        self.context[func_name] = user_function  # type: ignore[attr-defined]
        if getattr(node, "export", None):
            self._register_export(func_name, user_function)

    def _register_standalone_method(self, node: ast.FunctionDef) -> None:
        """Attach ``method name(Type this, ...)`` to the UDT named by the first param type."""
        if not node.args:
            return
        first = node.args[0]
        if not isinstance(first, ast.Param) or first.type is None:
            return

        type_name: str | None = None
        type_spec = first.type
        if isinstance(type_spec, ast.Name):
            type_name = type_spec.id
        elif isinstance(type_spec, ast.Attribute):
            # Rare: namespace.Type — use trailing attr
            type_name = type_spec.attr

        if not type_name:
            return

        udt = self.type_registry.get_type(type_name)
        if udt is None:
            existing = self.context.get(type_name)  # type: ignore[attr-defined]
            if isinstance(existing, UserDefinedType):
                udt = existing
        if not isinstance(udt, UserDefinedType):
            return

        parameters: list[tuple[str, Type]] = []
        for param in node.args:
            if not isinstance(param, ast.Param):
                continue
            if param is first:
                continue
            param_type: Type = (
                self._convert_type_spec_to_type(param.type)
                if param.type
                else BuiltinType(BuiltinTypeKind.STRING)
            )
            parameters.append((param.name, param_type))

        method_sig = MethodSignature(
            name=node.name,
            parameters=parameters,
            return_type=None,
            is_builtin=False,
        )
        udt.add_method(method_sig)
        if not hasattr(udt, "_method_defs"):
            udt._method_defs = {}  # type: ignore[attr-defined]
        udt._method_defs[node.name] = node  # type: ignore[attr-defined]

    def _load_library_source(self, source: str) -> None:
        """Evaluate a library script's definitions only (no showcase body).

        Keeps ``library()``, ``export type``/``export method``/``export const``,
        and non-export helpers (``method isset`` etc.) while skipping free
        statements like Console's interactive demo (``testLabel.delete()`` …).
        """
        tree = parse_pine(source, mode="exec")
        for stmt in getattr(tree, "body", []) or []:
            kind = type(stmt).__name__
            if kind in {"FunctionDef", "TypeDef", "EnumDef", "Import"}:
                self.visit(stmt)  # type: ignore[attr-defined]
                continue
            if kind == "Assign":
                # const / exported vars used by methods
                self.visit(stmt)  # type: ignore[attr-defined]
                continue
            if kind == "Expr":
                val = getattr(stmt, "value", None)
                if isinstance(val, ast.Call):
                    func = val.func
                    if isinstance(func, ast.Name) and func.id in {"library", "indicator", "strategy"}:
                        self.visit(stmt)  # type: ignore[attr-defined]

    def visit_Import(self, node: ast.Import):
        """Resolve ``import namespace/name/version [as alias]`` against the library registry.

        Libraries are resolved by exact path when registered with namespace+version,
        or by library title (``name``) after a prior ``evaluate_script(library(...))``.
        Explicit sources registered via ``register_library_source`` are loaded lazily.
        """
        if getattr(self, "_pine_defs_locked", False):
            return
        namespace = node.namespace
        name = node.name
        version = int(node.version) if node.version is not None else None
        alias = node.alias or name

        registry = self._library_registry  # type: ignore[attr-defined]
        mod = registry.lookup(namespace=namespace, name=name, version=version)

        if mod is None and namespace is not None and version is not None:
            source = registry.get_source(namespace, name, version)
            if source is not None:
                # Load library definitions only (skip chart demo / example bodies).
                # TradingView does not re-run library showcase scripts on import.
                self._load_library_source(source)  # type: ignore[attr-defined]
                mod = registry.lookup(namespace=namespace, name=name, version=version)
                if mod is None:
                    # Title-only registration from library("name")
                    mod = registry.lookup(name=name)
                    if mod is not None:
                        mod.namespace = namespace
                        mod.version = version
                        registry.register(mod)

        if mod is None:
            # Soft-stub unknown remote libraries (TradingView/*) so the rest of
            # the script can still evaluate. Missing members return None.
            path = f"{namespace}/{name}/{version}"
            try:
                # Chainable no-op stub so ``lib.Foo.new(...)`` / ``lib.bar()``
                # do not raise. Missing libraries degrade to empty behaviour.
                class _StubLib:
                    def __getattr__(self, item: str) -> _StubLib:
                        return self

                    def __call__(self, *a, **k):  # noqa: ANN001
                        return self

                    def __bool__(self) -> bool:
                        return False

                    def __iter__(self):
                        # Support multi-assign unpacking: [a,b,c] = stub.foo()
                        return iter([None] * 8)

                    def __getitem__(self, key):  # noqa: ANN001
                        return None

                    def __len__(self) -> int:
                        return 0

                    def __add__(self, other):  # noqa: ANN001
                        return other

                    def __radd__(self, other):  # noqa: ANN001
                        return other

                    def __sub__(self, other):  # noqa: ANN001
                        return other

                    def __rsub__(self, other):  # noqa: ANN001
                        return other

                stub = _StubLib()
                self.context[alias] = stub  # type: ignore[attr-defined]
                return stub
            except Exception:
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
