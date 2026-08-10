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

"""Statement evaluation: script body, assignments, defs, imports, loops.

:class:`StatementEvaluator` walks statement-level AST nodes. Hosts call
``visit(Script)`` **once per bar** after updating OHLCV / ``bar_index`` in
``context``. Across that loop:

- **``var`` / ``varip``** run their initializer only the first time that
  declaration executes (see ``_var_declarations``), then keep the stored
  value on later bars — including when the first execution is not bar 0
  (e.g. ``var`` inside ``if barstate.islast``).
- **``FunctionDef`` / ``TypeDef`` / ``Import``** may be skipped after the host
  sets ``_pine_defs_locked`` (avoids multi-dispatch table growth O(bars²)).
- **UDF bodies** rebind parameters on the live ``context`` dict and restore
  them on return (never replace ``self.context`` with a copy).
- **``na``** is ``None``; unresolved optional args are normalized via
  :func:`_normalize_na`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.evaluator.builtins.declarations import ScriptDeclaration
from pynescript.ast.evaluator.libraries import STUB_KNOWN_EXPORTS
from pynescript.ast.evaluator.libraries import LibraryModule
from pynescript.ast.evaluator.names import ast_qualified_name
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
    """Control-flow signal: exit the innermost loop (``break``)."""

    pass


class ContinueLoop(Exception):
    """Control-flow signal: skip to the next loop iteration (``continue``)."""

    pass


class StatementEvaluator:
    """Mixin: script body, assign/reassign, function/type/enum defs, import, loops.

    Expects ``context``, ``type_registry``, and (from
    :class:`~pynescript.ast.evaluator.NodeLiteralEvaluator`)
    ``_var_declarations`` / library registry attributes.

    Multi-dispatch for overloaded ``method`` free functions stores a list of
    callables under one context name; overload pick uses coarse param type tags
    (``matrix.float``, ``label``, …).
    """

    context: dict[str, Any]
    type_registry: TypeRegistry

    def _collect_history_names(self, node: Any, out: set[str]) -> None:
        """Collect Name bases of history Subscripts (``x[1]``, ``x[n]``)."""
        if node is None or not hasattr(node, "__dict__"):
            return
        if isinstance(node, ast.Subscript) and isinstance(getattr(node, "value", None), ast.Name):
            out.add(node.value.id)
        for child in node.__dict__.values():
            if isinstance(child, list):
                for c in child:
                    self._collect_history_names(c, out)
            else:
                self._collect_history_names(child, out)

    def _coerce_typed_assign_value(self, type_node: Any, value: Any) -> Any:
        """Coerce RHS of ``float x = …`` / ``int n = …`` to a snapshot scalar.

        Pine series operands (``close``, UDF ``series float`` params) arrive as
        ``PineSeries`` handles. Typed locals must hold the bar's numeric value
        so subsequent ``array.set`` / arithmetic do not alias live series.
        """
        type_name: str | None = None
        if isinstance(type_node, ast.Name):
            type_name = getattr(type_node, "id", None)
        elif isinstance(type_node, str):
            type_name = type_node
        if not type_name:
            return value
        # Unwrap series wrapper → current sample
        if value is not None and hasattr(value, "current") and hasattr(value, "history"):
            value = getattr(value, "current", value)
        if type_name == "float":
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        if type_name == "int":
            if value is None:
                return None
            try:
                return int(value) if not isinstance(value, float) else int(value)
            except (TypeError, ValueError):
                return None
        if type_name == "bool":
            if value is None:
                return False
            return bool(value)
        if type_name in ("string", "str"):
            if value is None:
                return None
            return str(value)
        # color / other typed names — leave as-is after series unwrap
        return value

    def _bind_series_name(self, name: str, value: Any) -> Any:
        """Store *value* for *name*, tracking history when ``name`` is subscripted.

        Only names collected into ``_history_names`` (via ``x[1]`` uses) are
        wrapped. Same-bar reassignment (``x = 0.0`` then ``x := expr``)
        overwrites the current sample so ``x[1]`` is the previous bar's final
        value (Fisher / self-ref scripts).
        """
        history_names: set[str] = getattr(self, "_history_names", None) or set()
        if name not in history_names:
            self.context[name] = value
            return value

        # Host OHLCV / any multi-bar series (``time``, ``close``, …) — never
        # alias by reference into a *different* name.  ``last = time`` then
        # ``last := …`` would otherwise mutate the host ``time`` buffer
        # (dividend_yield last_div_ttm_time path) and break ``time[j]`` history.
        # Copy the current scalar into a fresh series for *name* instead.
        if (
            hasattr(value, "current")
            and hasattr(value, "history")
            and hasattr(value, "update")
        ):
            value = getattr(value, "current", value)

        # Only track scalar numerics / na (not maps, arrays, UDT handles, strings).
        if value is not None and type(value) not in (int, float, bool):
            try:
                import numbers

                if not isinstance(value, numbers.Real):
                    self.context[name] = value
                    return value
                value = float(value)
            except Exception:
                self.context[name] = value
                return value

        bar = self.context.get("bar_index", 0)
        try:
            bar_i = int(bar) if bar is not None else 0
        except (TypeError, ValueError):
            bar_i = 0

        # Note: empty dict is falsy — never use ``getattr(...) or {}`` here.
        last_map: dict[Any, int] | None = getattr(self, "_series_assign_bar", None)
        if last_map is None:
            last_map = {}
            self._series_assign_bar = last_map  # type: ignore[attr-defined]

        # UDF series locals share the bare name (``kf``) across call sites but
        # hold distinct PineSeries instances. Tracking only by name makes the
        # second ``kahlman(...)`` on the same bar see last_map[name]==bar and
        # ``set_current`` without pushing history — filter state never advances.
        # Key by (udf_call_site, name) when inside a UDF, else by name.
        udf_site = getattr(self, "_pine_udf_site", None)
        track_key: Any = (udf_site, name) if udf_site is not None else name

        existing = self.context.get(name)
        if (
            hasattr(existing, "update")
            and hasattr(existing, "current")
            and hasattr(existing, "history")
        ):
            if last_map.get(track_key) == bar_i and hasattr(existing, "set_current"):
                existing.set_current(value)
            elif last_map.get(track_key) == bar_i:
                existing.current = value
                hist = getattr(existing, "history", None)
                if hist is not None and len(hist) > 0:
                    try:
                        hist[0] = value
                    except (TypeError, AttributeError):
                        existing.update(value)
                else:
                    existing.update(value)
            else:
                existing.update(value)
            last_map[track_key] = bar_i
            self.context[name] = existing
            return existing

        try:
            from pynescript.ast.evaluator.series_buffer import make_series

            ps = make_series(history_length=512)
            if hasattr(ps, "update"):
                ps.update(value)
            else:
                ps.current = value
        except Exception:
            self.context[name] = value
            return value
        last_map[track_key] = bar_i
        self.context[name] = ps
        return ps

    def visit_Script(self, node: ast.Script):
        """Execute every top-level statement; return the last value.

        Hosts re-enter this per bar. Also detects ``library("Title")`` and
        registers ``export`` members into the in-process library registry at
        the end of the visit.

        When ``_pine_line_profile`` is a ``dict`` (profiler mode), each
        top-level statement is timed and aggregated by ``lineno`` as
        ``{line: [ms_sum, execs]}``.

        Args:
            node: Root ``Script`` with ``body`` statement list
        """
        # Once per script: collect names used with history subscript so assigns
        # can track PineSeries across bars (``ma[barsback]``, ``x[1]``, …).
        if not getattr(self, "_history_names_scanned", False):
            hist: set[str] = set()
            self._collect_history_names(node, hist)
            self._history_names = hist  # type: ignore[attr-defined]
            self._history_names_scanned = True  # type: ignore[attr-defined]
        # Fresh library-export buffer for this script evaluation
        self._pending_library_exports = {}  # type: ignore[attr-defined]
        self._active_library = None  # type: ignore[attr-defined]
        last: Any = None
        visit = self.visit
        line_prof: dict[int, list[float]] | None = getattr(self, "_pine_line_profile", None)
        # Hot path: walk body via visitor cache (Assign/Expr/Call already have
        # lean handlers). Avoid extra per-stmt Python dispatch layers that
        # regress tiny scripts (minimal = 2 stmts).
        if line_prof is not None:
            # Lazy import keeps hot path free of time when profiler is off
            from time import perf_counter

            for stmt in node.body:
                ln = int(getattr(stmt, "lineno", 0) or 0)
                t0 = perf_counter()
                last = visit(stmt)  # type: ignore[attr-defined]
                if ln >= 1:
                    dt_ms = (perf_counter() - t0) * 1000.0
                    bucket = line_prof.get(ln)
                    if bucket is None:
                        line_prof[ln] = [dt_ms, 1.0]
                    else:
                        bucket[0] += dt_ms
                        bucket[1] += 1.0
                # Detect library("Title") declaration from Expr(Call(...))
                if isinstance(last, ScriptDeclaration) and last.script_type == "library":
                    self._active_library = LibraryModule(title=str(last.title))  # type: ignore[attr-defined]
        else:
            for stmt in node.body:
                last = visit(stmt)  # type: ignore[attr-defined]
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
        """Assignment, including ``var`` / ``varip`` / ``const`` and tuple unpack.

        Modes:

        - **``var`` / ``varip``** — initializer runs only the first time this
          declaration executes (name recorded in ``_var_declarations``). Later
          visits skip so the value persists across bars. Not limited to
          ``bar_index == 0``: a ``var`` inside a conditional or function inits
          on first *execution*, which may be a later bar.
        - **``const``** — always initializes (no cross-bar skip like ``var``).
        - **plain** — evaluate RHS and store; supports ``export`` for libraries
          and ``[a, b] = …`` unpack (lists, multi-value series wrappers).

        Args:
            node: Assign with target, value, optional mode / type / export

        Raises:
            ValueError: Unsupported target form
        """
        mode = node.mode
        # Dominant bar-loop path: plain ``name = expr`` (no var/const mode).
        # Avoids isinstance on Var/VarIp/Const for every assign every bar.
        if mode is None:
            if node.value:
                rhs = node.value
                # Call RHS is the common case (s = ta.sma(...)); skip visit frame.
                if type(rhs) is ast.Call:
                    value = self.visit_Call(rhs)  # type: ignore[attr-defined]
                else:
                    value = self.visit(rhs)  # type: ignore[attr-defined]
                # Typed declarations: ``float x = close`` must snapshot the
                # current scalar — storing the PineSeries handle makes
                # ``array.set(buf, i, x)`` keep live references so every slot
                # tracks the latest bar (breaks ring-buffer SMAs / BBI).
                type_node = getattr(node, "type", None)
                if type_node is not None:
                    value = self._coerce_typed_assign_value(type_node, value)
                target = node.target
                if type(target) is ast.Name:
                    stored = self._bind_series_name(target.id, value)
                    if getattr(node, "export", None):
                        self._register_export(target.id, stored)
                    # Return assigned value so UDF bodies ending in ``x = expr``
                    # yield expr (Pine: last expression is the function result).
                    if (
                        stored is not None
                        and hasattr(stored, "current")
                        and hasattr(stored, "history")
                    ):
                        return getattr(stored, "current", stored)
                    return stored
                if type(target) is ast.Tuple:
                    self._assign_tuple_unpack(target, value)
                    return value
                msg = f"Unsupported assignment target: {type(target)}"
                self._error(msg)  # type: ignore[attr-defined]
            return

        # -- Handle var / varip ------------------------------------------------
        # Pine ``var`` is not strictly bar_index==0: a ``var`` inside
        # ``if barstate.islast`` or a function body must init on first
        # *execution* of that declaration, which may be a later bar.
        #
        # ``varip`` matches ``var`` on historical bars. On realtime ticks
        # (``barstate.isrealtime``), we re-run the initializer each update so
        # the value can track intrabar state when the host sets the flag.
        # Default Runtime historical loop keeps ``isrealtime=False``; opt-in
        # ``Runtime.run(realtime_last_bar=True)`` / ``realtime_ticks=N`` sets
        # the flag on the last bar (multi-tick re-visits when N>1).
        if isinstance(mode, (ast.Var, ast.VarIp)):
            if isinstance(node.target, ast.Name):
                name: str = node.target.id  # type: ignore[attr-defined]
                declared: set[str] = self._var_declarations  # type: ignore[attr-defined]
                is_varip = isinstance(mode, ast.VarIp)
                ctx = getattr(self, "context", {}) or {}
                barstate = ctx.get("barstate")
                is_rt = bool(getattr(barstate, "isrealtime", False)) if barstate is not None else False
                if is_varip and is_rt:
                    # Realtime tick: re-evaluate RHS every update (reference varip).
                    if node.value:
                        value = self.visit(node.value)  # type: ignore[attr-defined]
                        self._bind_series_name(name, value)
                    declared.add(name)
                    return
                if name not in declared:
                    if node.value:
                        value = self.visit(node.value)  # type: ignore[attr-defined]
                        self._bind_series_name(name, value)
                    declared.add(name)
                return
            msg = f"Unsupported var/varip target: {type(node.target)}"
            self._error(msg)  # type: ignore[attr-defined]
            return

        if isinstance(mode, ast.Const):
            # v6: const always initializes (no re-init like var)
            if node.value and isinstance(node.target, ast.Name):
                value = self.visit(node.value)  # type: ignore[attr-defined]
                self._bind_series_name(node.target.id, value)
            return

        # -- Regular assignment with unexpected mode object (fallback)
        if node.value:
            value = self.visit(node.value)  # type: ignore[attr-defined]
            if isinstance(node.target, ast.Name):
                stored = self._bind_series_name(node.target.id, value)
                if getattr(node, "export", None):
                    self._register_export(node.target.id, stored)
            elif isinstance(node.target, ast.Tuple):
                self._assign_tuple_unpack(node.target, value)
            else:
                msg = f"Unsupported assignment target: {type(node.target)}"
                self._error(msg)  # type: ignore[attr-defined]

    def _assign_tuple_unpack(self, target: ast.Tuple, value: Any) -> None:
        """Unpack RHS into ``[a, b, …]`` targets (lists, multi-value series, soft-fail)."""
        elts = target.elts
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
                # Bind through series funnel so history names keep wrappers.
                self._bind_series_name(target_node.id, val)  # type: ignore[attr-defined]
            else:
                msg = f"Unsupported unpack target: {type(target_node)}"
                self._error(msg)  # type: ignore[attr-defined]
                return

    def _reassign_qualified_namespace(self, qname: str, value: Any) -> bool:
        """Write dotted namespace targets (``strategy.initial_capital = …``).

        ``visit_Name("strategy")`` returns the bare string ``"strategy"`` when
        the name is not in ``context`` (lazy builtin path). ``setattr`` then
        fails and the old ReAssign path raised *Unsupported reassignment
        target: Attribute* even though the AST target is valid.

        Known strategy series fields update :attr:`_strategy_state` (so later
        ``strategy.initial_capital`` / equity math stay consistent). Any other
        ``a.b`` path is stored under the qualified context key so subsequent
        Attribute reads (context-first) observe the write.

        Returns:
            True if this path handled the write (caller should return).
        """
        if not qname or "." not in qname:
            return False

        # Mutable strategy declaration-style fields (corpus: strategy.initial_capital = N)
        if qname == "strategy.initial_capital":
            try:
                cap = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                cap = 0.0
            st = getattr(self, "_strategy_state", None)
            if st is not None:
                st.initial_capital = cap
                st.risk_free_capital = cap
                # Keep peak/trough aligned when capital is set before trading.
                st._equity_peak = cap
                st._equity_trough = cap
            # Shadow context so Attribute fast-path sees the same value
            self.context[qname] = cap  # type: ignore[attr-defined]
            return True

        # Generic namespace write: context key shadows builtins / unresolved paths
        self.context[qname] = value  # type: ignore[attr-defined]
        return True

    def visit_ReAssign(self, node: ast.ReAssign):
        """Handle reassignment (``x := x + 1`` / ``obj.field := value``).

        Evaluates the right-hand side and stores the result in the target
        variable. This is the Pine Script ``:=`` operator, distinct from
        ``AugAssign`` (``x += 1``). Supports simple names, UDT/object field
        mutation (``settings.devThreshold := …``), and namespace attributes
        (``strategy.initial_capital = 50000`` — parser emits ReAssign).

        Args:
            node: The ReAssign node with target and value

        Raises:
            ValueError: If reassignment target is unsupported
        """
        target = node.target
        # Dominant path: ``s := s + 1`` / ``x := expr`` simple name target.
        if type(target) is ast.Name:
            value = self.visit(node.value)  # type: ignore[attr-defined]
            stored = self._bind_series_name(target.id, value)
            # Pine ``:=`` is an expression; UDF bodies may end with reassignment.
            if (
                stored is not None
                and hasattr(stored, "current")
                and hasattr(stored, "history")
            ):
                return getattr(stored, "current", stored)
            return stored

        value = self.visit(node.value)  # type: ignore[attr-defined]
        # obj.field := value  (UDT instances and plain objects with setattr)
        if isinstance(target, ast.Attribute):
            # Builtin namespaces (strategy.*, etc.): base Name is often a bare
            # string, not a mutable object — handle via qualified path first
            # when the base is not a live instance.
            qname = ast_qualified_name(node.target)
            base_node = node.target.value
            # Prefer object mutation when base is a real binding (UDT handle).
            obj: Any = None
            try_object = True
            if isinstance(base_node, ast.Name):
                # Only skip object path when Name is unresolved string / missing
                bound = self.context.get(base_node.id)  # type: ignore[attr-defined]
                if bound is None and base_node.id not in self.context:  # type: ignore[attr-defined]
                    # Unresolved namespace name → qualified write
                    if qname and self._reassign_qualified_namespace(qname, value):
                        return
                    try_object = False
                else:
                    obj = bound
            if try_object:
                if obj is None and not isinstance(base_node, ast.Name):
                    obj = self.visit(base_node)  # type: ignore[attr-defined]
                elif obj is None and isinstance(base_node, ast.Name):
                    # Present in context as None → soft no-op (na handle)
                    return
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
                except (AttributeError, TypeError):
                    # Expected for frozen/slots objects — try dict-style next.
                    pass
                except Exception as e:
                    # Unexpected programming errors must not soft-fail to no-op.
                    msg = f"Reassignment failed for attribute {node.target.attr!r}: {e}"
                    self._error(msg)  # type: ignore[attr-defined]
                    return
                if isinstance(obj, dict):
                    obj[node.target.attr] = value
                    return
                # Base resolved to a non-mutable value (e.g. str namespace from
                # visit_Name fallback, int series). Fall back to qualified write.
                if qname and self._reassign_qualified_namespace(qname, value):
                    return

            msg = f"Unsupported reassignment target: {type(node.target)}"
            self._error(msg)  # type: ignore[attr-defined]
            return

        msg = f"Unsupported reassignment target: {type(node.target)}"
        self._error(msg)  # type: ignore[attr-defined]

    def visit_AugAssign(self, node: ast.AugAssign):
        """Augmented assignment (``x += 1``, UDT field write via attribute target).

        Name targets use the same na/series element-wise ops as
        :meth:`~.expressions.ExpressionEvaluator.visit_BinOp`. Attribute
        targets set UDT fields when the object is an :class:`~pynescript.ast.type_system.ObjectInstance`.

        Args:
            node: AugAssign with target, op, value
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
                    # Route through series bind so history-tracked names keep
                    # PineSeries identity (audit Wave B / AGENT_02 C2).
                    result = _elementwise_binary(raw, current, rhs)
                    self._bind_series_name(var_name, result)  # type: ignore[attr-defined]
                    return

        msg = f"Unsupported augmented assignment: {type(node.target)}"
        self._error(msg)  # type: ignore[attr-defined]

    def visit_TypeDef(self, node: ast.TypeDef):
        """Register a UDT (fields, methods, optional ``export``) in the type registry.

        Skipped when ``_pine_defs_locked`` is set (multi-bar hosts after first bar).
        """
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
        """Map a type AST node (``Name``) to a :class:`~pynescript.ast.type_system.Type`."""
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
        """Bind an enum as a ``dict`` of members in ``context`` (optional ``export``).

        Skipped when ``_pine_defs_locked`` is set.
        """
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
        value = node.value
        # Dominant: plot(...)/strategy.* calls — skip visitor.visit frame.
        if type(value) is ast.Call:
            return self.visit_Call(value)  # type: ignore[attr-defined]
        return self.visit(value)  # type: ignore[attr-defined]

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

        v6 re-evaluates the end bound every iteration (dynamic boundaries). When
        the end (and optional step) AST nodes are plain constants, the bound is
        fixed — skip the per-iteration ``visit`` (dominant cost in nested
        ``for i = 1 to 1e3`` / ``for j = 0 to 100`` corpus demos).
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
        step: float | None
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

        # Static end/step: Constant nodes cannot change mid-loop.
        end_node = node.end
        static_end = type(end_node) is ast.Constant and (
            end_node.kind is None or end_node.kind == "#"
        )
        static_step = (not explicit_step) or (
            type(node.step) is ast.Constant
            and (node.step.kind is None or node.step.kind == "#")  # type: ignore[union-attr]
        )

        if static_end and static_step:
            end_val = end_node.value  # type: ignore[attr-defined]
            if end_val is None:
                return None
            try:
                end_f = float(end_val)
            except (TypeError, ValueError):
                return None
            if step is None:
                step = 1.0 if start_f <= end_f else -1.0
            return self._run_for_to_static(
                target_name, start_f, end_f, step, node.body
            )

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

    def _run_for_to_static(
        self,
        target_name: str,
        start_f: float,
        end_f: float,
        step: float,
        body: Sequence[ast.AST],
    ) -> Any:
        """Inclusive for-to with fixed numeric bounds (no per-iter end visit)."""
        last_result = None
        max_iters = 1_000_000
        # Integer range: use Python range (faster counter + inclusive end).
        if (
            start_f == int(start_f)
            and end_f == int(end_f)
            and step == int(step)
            and step != 0
        ):
            start_i = int(start_f)
            end_i = int(end_f)
            step_i = int(step)
            # range stop is exclusive; Pine end is inclusive.
            stop = end_i + (1 if step_i > 0 else -1)
            ctx = self.context  # type: ignore[attr-defined]
            n = 0
            for current_i in range(start_i, stop, step_i):
                n += 1
                if n > max_iters:
                    break
                ctx[target_name] = current_i
                result, should_break = self._execute_loop_body(body)
                if result is not None:
                    last_result = result
                if should_break:
                    break
            return last_result

        current = start_f
        iters = 0
        ctx = self.context  # type: ignore[attr-defined]
        while iters < max_iters:
            iters += 1
            if not (current <= end_f if step > 0 else current >= end_f):
                break
            ctx[target_name] = int(current) if current == int(current) else current
            result, should_break = self._execute_loop_body(body)
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
        """Raise :class:`BreakLoop` for the enclosing loop runner."""
        raise BreakLoop

    def visit_Continue(self, _node: ast.Continue):
        """Raise :class:`ContinueLoop` for the enclosing loop runner."""
        raise ContinueLoop

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Define a user function or standalone ``method`` (with multi-dispatch).

        - Ordinary functions become callables in ``context[name]``.
        - Pine ``method m(Type this, ...) => ...`` is also attached to the UDT
          for ``instance.m()`` and tagged ``__pine_method__`` for extension
          dispatch; overloads share one multi-dispatch entry.
        - After the first bar, hosts set ``_pine_defs_locked`` so this visitor
          no-ops and multi-dispatch tables do not grow O(bars²).

        The generated callable rebinds parameters **in place** on ``context``
        and restores prior values in ``finally`` (see nested ``user_function``).
        """
        # Already bound on a prior bar — keep existing callables.
        if getattr(self, "_pine_defs_locked", False):
            return

        if node.method:
            self._register_standalone_method(node)

        func_name = node.name

        # Pre-bind once: param list + body plan (Expr vs statement). Avoids
        # re-scanning node.args / isinstance body checks on every UDF call.
        params = tuple(arg for arg in node.args if isinstance(arg, ast.Param))
        param_names = tuple(p.name for p in params)
        param_name_set = frozenset(param_names)
        defaults: tuple[tuple[str, Any], ...] = tuple(
            (p.name, p.default) for p in params if p.default is not None
        )
        body_plan: list[tuple[bool, Any]] = []
        for stmt in node.body:
            if type(stmt) is ast.Expr:
                body_plan.append((True, stmt.value))
            else:
                body_plan.append((False, stmt))
        body_plan_t = tuple(body_plan)
        n_params = len(params)
        # Series locals that use history (``kf[1]``) must be isolated per
        # call site — two ``kahlman(...)`` invocations cannot share one ``kf``.
        series_locals: set[str] = set()
        self._collect_history_names(node, series_locals)
        series_locals -= param_name_set
        series_locals_t = frozenset(series_locals)
        fsl: dict[str, frozenset[str]] = getattr(self, "_func_series_locals", None)  # type: ignore[attr-defined]
        if fsl is None:
            fsl = {}
            self._func_series_locals = fsl  # type: ignore[attr-defined]
        fsl[func_name] = series_locals_t

        # Create a closure
        def user_function(
            *args,
            __names=param_names,
            __defaults=defaults,
            __body=body_plan_t,
            __n=n_params,
            __fname=func_name,
            __series_locals=series_locals_t,
            **kwargs,
        ):
            """Invoke a UDF with in-place param rebind on the live context.

            Hosts mutate the *same* ``context`` dict each bar (``bar_index``,
            ``time``, OHLCV). Replacing ``self.context`` with ``dict.copy()``
            would orphan those updates (every call would see bar 0). Only
            parameter names are scoped; other keys — including ``var``
            locals — remain on the shared dict across bars.

            The function name itself is always snapshotted: Pine scripts often
            reuse the UDF name as a local series (``kama() => kama = 0.0; …``).
            Without restoring the callable, bar 1+ falls through to the bare
            ta.* alias and hard-fails on arity.

            Series locals with history (``x[1]``) are persisted **per call site**
            (``id`` of the Call AST node, set by ``visit_Call``) so multiple
            invocations of the same UDF do not share one ``kf``/``velo`` series.
            """
            ctx = self.context  # type: ignore[attr-defined]
            saved: dict[str, Any] = {}
            missing = _CONTEXT_MISSING

            def _bind(name: str, value: Any) -> None:
                if name not in saved:
                    saved[name] = ctx[name] if name in ctx else missing
                ctx[name] = value

            # Per-call-site store for series locals (compile uses __st_*_cN).
            site = int(getattr(self, "_pine_udf_site", 0) or 0)
            site_store: dict[str, Any] | None = None
            if __series_locals:
                all_stores: dict[tuple[str, int], dict[str, Any]] = getattr(
                    self, "_udf_call_site_state", None
                )  # type: ignore[attr-defined]
                if all_stores is None:
                    all_stores = {}
                    self._udf_call_site_state = all_stores  # type: ignore[attr-defined]
                site_store = all_stores.setdefault((__fname, site), {})

            try:
                # Protect UDF binding from body series init of the same name.
                if __fname not in saved:
                    saved[__fname] = ctx[__fname] if __fname in ctx else missing

                # Restore this call site's series locals (or clear for first run).
                if site_store is not None:
                    for n in __series_locals:
                        if n not in saved:
                            saved[n] = ctx[n] if n in ctx else missing
                        if n in site_store:
                            ctx[n] = site_store[n]
                        else:
                            ctx.pop(n, None)

                # Bind positional arguments
                for i, value in enumerate(args):
                    if i < __n:
                        _bind(__names[i], value)

                # Bind keyword arguments
                for key, value in kwargs.items():
                    _bind(key, value)

                # Apply parameter defaults for unbound params
                for dname, dast in __defaults:
                    if dname not in saved:
                        _bind(dname, self.visit(dast))  # type: ignore[attr-defined]

                # Execute pre-classified body
                result = None
                visit = self.visit
                for is_expr, item in __body:
                    if is_expr:
                        # Result-producing expression (often a Call).
                        if type(item) is ast.Call:
                            result = self.visit_Call(item)  # type: ignore[attr-defined]
                        else:
                            result = visit(item)  # type: ignore[attr-defined]
                    else:
                        # Assign/ReAssign are Pine expressions: last one is the
                        # function return value when the body ends with them.
                        # Important: ``None`` (Pine ``na``) is a valid assign
                        # result — do not keep a prior statement's value (e.g.
                        # tuple unpack ``[a,b]=…``) or ADX-like UDFs return 0
                        # instead of ``na`` during RMA warmup.
                        val = visit(item)  # type: ignore[attr-defined]
                        if type(item) in (ast.Assign, ast.ReAssign):
                            result = val
                # Persist series locals for this call site across bars.
                if site_store is not None:
                    for n in __series_locals:
                        if n in ctx:
                            site_store[n] = ctx[n]
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
            # Dual namespace: keep UDF callable even if a series reuses the name.
            ufuncs: dict[str, Any] = getattr(self, "_user_functions", None)  # type: ignore[attr-defined]
            if ufuncs is None:
                ufuncs = {}
                self._user_functions = ufuncs  # type: ignore[attr-defined]
            ufuncs[func_name] = multi_dispatch
            self.context[func_name] = multi_dispatch  # type: ignore[attr-defined]
            if getattr(node, "export", None):
                self._register_export(func_name, multi_dispatch)
            return

        ufuncs = getattr(self, "_user_functions", None)  # type: ignore[attr-defined]
        if ufuncs is None:
            ufuncs = {}
            self._user_functions = ufuncs  # type: ignore[attr-defined]
        ufuncs[func_name] = user_function
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
                # Reference Pine does not re-run library showcase scripts on import.
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
            # Soft-stub unknown remote libraries (remote library paths) so the rest of
            # the script can still evaluate. Missing members return None.
            path = f"{namespace}/{name}/{version}"
            try:
                # Chainable no-op stub so ``lib.Foo.new(...)`` / ``lib.bar()``
                # do not raise. Missing libraries degrade to empty behaviour.
                # Known helpers (e.g. ArrayExtension.index_2d_to_1d) are
                # polyfilled so array.get/set receive real indices.
                class _StubLib:
                    __pine_import_stub__ = True
                    __pine_import_path__ = path

                    def __getattr__(self, item: str) -> Any:
                        known = STUB_KNOWN_EXPORTS.get(item)
                        if known is not None:
                            return known
                        # Empty-collection API: ``zigZag.pivots.size()`` must be
                        # numeric 0 so ``size() < 2`` triggers the same
                        # runtime.error path as compile (safe_len → 0). Returning
                        # self made ``stub < 2`` soft-fail to False and silently
                        # skip Auto Fib Retracement's insufficient-pivot error.
                        if item in ("size", "length", "len"):
                            return lambda *_a, **_k: 0
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

                    def __repr__(self) -> str:
                        return f"<PineImportStub {path}>"

                stub = _StubLib()
                self.context[alias] = stub  # type: ignore[attr-defined]
                # Track for hosts / diagnostics (corpus Runtime, API tooling)
                stubs = getattr(self, "_import_stubs", None)
                if stubs is None:
                    stubs = []
                    self._import_stubs = stubs  # type: ignore[attr-defined]
                stubs.append({"path": path, "alias": alias, "namespace": namespace, "name": name, "version": version})
                # Surface once via log.warning when logger is available
                try:
                    from pynescript.ast.evaluator.builtins.logging import log_warning

                    log_warning(
                        "Unresolved import {0} as {1} — empty stub (register_library_source to load real lib)",
                        path,
                        alias,
                    )
                except Exception:
                    pass
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
        """Statement-style if/else via :meth:`_execute_block` (``na`` test → false).

        Note: on :class:`~pynescript.ast.evaluator.NodeLiteralEvaluator`,
        :class:`~.expressions.ExpressionEvaluator` precedes this mixin in the
        MRO, so its ``visit_If`` is the one that actually runs.
        """
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
        """Switch/case: equality match on subject, or truthy patterns when subject is absent.

        Same MRO note as :meth:`visit_If` — ExpressionEvaluator's ``visit_Switch``
        wins on the composed evaluator. Keep this path aligned for any host that
        mixes StatementEvaluator alone: **subject present but ``na``** uses
        equality (``na`` only matches ``na``), never boolean-pattern mode.
        """
        from pynescript.ast.evaluator.expressions import _switch_case_matches

        has_subject = node.subject is not None
        subject_val = self.visit(node.subject) if has_subject else None  # type: ignore[attr-defined]

        for case in node.cases:
            pattern = case.pattern  # type: ignore[attr-defined]
            if pattern is not None:
                pattern_val = self.visit(pattern)  # type: ignore[attr-defined]
                if not _switch_case_matches(has_subject, subject_val, pattern_val):
                    continue
            return self._execute_block(case.body)  # type: ignore[arg-type, attr-defined]
        return None

    def _execute_loop_body(self, stmts: Sequence[ast.AST]) -> tuple[Any, bool]:
        """Run one loop iteration; map :class:`BreakLoop` / :class:`ContinueLoop`.

        Returns:
            ``(last_expr_result, should_break)``
        """
        result = None
        should_break = False
        visit = self.visit  # type: ignore[attr-defined]
        try:
            # Single-statement bodies dominate nested corpus loops.
            n = len(stmts)
            if n == 1:
                stmt = stmts[0]
                val = visit(stmt)
                st = type(stmt)
                if (
                    st is ast.Expr
                    or st is ast.If
                    or st is ast.Switch
                    or st is ast.ForTo
                    or st is ast.ForIn
                    or st is ast.While
                    or st is ast.ReAssign
                    or st is ast.Assign
                ):
                    result = val
                return result, False
            for stmt in stmts:
                val = visit(stmt)
                st = type(stmt)
                if (
                    st is ast.Expr
                    or st is ast.If
                    or st is ast.Switch
                    or st is ast.ForTo
                    or st is ast.ForIn
                    or st is ast.While
                ):
                    result = val
                else:
                    result = None
        except BreakLoop:
            should_break = True
        except ContinueLoop:
            pass
        return result, should_break
