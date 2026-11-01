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

"""Static scope/symbol analysis for the language server.

This module is intentionally **not** an evaluator. It uses the same ANTLR4 →
ASDL AST as the runtime and answers editor questions that need more than a
flat name scan:

* which declaration does this identifier resolve to?
* what is its inferred Pine type (conservatively)?
* which fields/methods does a UDT value expose?
* which occurrences belong to the same symbol for references/rename?

The model is deliberately conservative: unknown types stay ``None`` and are
never guessed. That keeps hover/inlay/completion useful without inventing
semantics that Pine does not have.

Public API:
    :class:`Symbol`, :class:`Scope`, :class:`SymbolIndex`,
    :func:`build_symbol_index`, :func:`infer_type`.
"""

from __future__ import annotations

import re

from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from pynescript.ast import node as ast
from pynescript.ast.helper import iter_child_nodes


# Builtin namespaces that behave like modules. Kept local so analysis does not
# depend on the completion provider (and therefore stays cheap to import).
BUILTIN_NAMESPACES: frozenset[str] = frozenset(
    {
        "alert",
        "array",
        "barstate",
        "box",
        "chart",
        "color",
        "input",
        "label",
        "line",
        "linefill",
        "log",
        "map",
        "math",
        "matrix",
        "plot",
        "polyline",
        "request",
        "runtime",
        "session",
        "str",
        "strategy",
        "syminfo",
        "ta",
        "table",
        "ticker",
        "time",
        "timeframe",
    }
)

# Builtin variables with stable Pine types. Only names that are plain ``Name``
# nodes are listed; namespaced properties (syminfo.ticker, …) are handled by
# builtin metadata in the feature layer.
BUILTIN_VAR_TYPES: dict[str, str] = {
    "open": "series float",
    "high": "series float",
    "low": "series float",
    "close": "series float",
    "volume": "series float",
    "hl2": "series float",
    "hlc3": "series float",
    "ohlc4": "series float",
    "time": "series int",
    "time_close": "series int",
    "bar_index": "series int",
    "last_bar_index": "series int",
    "na": "na",
}

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TYPE_QUALIFIERS = {"const", "input", "simple", "series"}
_MAX_INFER_DEPTH = 24


@dataclass(eq=False)
class Symbol:
    """One declared Pine symbol.

    ``kind`` is one of ``variable``, ``function``, ``method``, ``type``,
    ``enum``, ``enum_member``, ``field``, ``param``, or ``import``.
    """

    name: str
    kind: str
    node: Any
    scope: Scope
    name_node: Any | None = None
    type_label: str | None = None
    mode: str | None = None
    export: bool = False
    container: str | None = None
    annotations: list[str] = field(default_factory=list)
    signature: str | None = None
    order: int = 0


@dataclass(eq=False)
class Scope:
    """A lexical Pine scope (script, function, block, type, enum)."""

    kind: str
    node: Any
    parent: Scope | None
    start: tuple[int, int] = (0, 0)
    end: tuple[int, int] = (0, 0)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    children: list[Scope] = field(default_factory=list)

    def define(self, symbol: Symbol) -> Symbol:
        """Register *symbol* unless the name is already declared in this scope."""
        existing = self.symbols.get(symbol.name)
        if existing is not None:
            return existing
        self.symbols[symbol.name] = symbol
        return symbol

    def lookup(self, name: str) -> Symbol | None:
        """Resolve *name* in this scope, then walk parents."""
        scope: Scope | None = self
        while scope is not None:
            symbol = scope.symbols.get(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        return None


@dataclass(eq=False)
class Occurrence:
    """An exact identifier occurrence bound to a symbol (or unresolved)."""

    name: str
    line: int
    column: int
    end_line: int
    end_column: int
    scope: Scope
    node: Any
    symbol: Symbol | None
    write: bool = False
    type_use: bool = False

    def contains(self, line: int, column: int) -> bool:
        """True when LSP position (*line*, *column*) is inside this range."""
        if line < self.line or line > self.end_line:
            return False
        if line == self.line and column < self.column:
            return False
        if line == self.end_line and column > self.end_column:
            return False
        return True


@dataclass(eq=False)
class MemberRef:
    """A ``receiver.member`` access with its inferred receiver type."""

    name: str
    line: int
    column: int
    end_line: int
    end_column: int
    scope: Scope
    node: Any
    base_type: str | None
    symbol: Symbol | None = None
    kind: str = "unknown"  # field | method | enum_member | constructor | builtin | import | unknown
    builtin_name: str | None = None

    def contains(self, line: int, column: int) -> bool:
        """True when LSP position (*line*, *column*) is inside this range."""
        if line < self.line or line > self.end_line:
            return False
        if line == self.line and column < self.column:
            return False
        if line == self.end_line and column > self.end_column:
            return False
        return True


class SymbolIndex:
    """Scope tree, declarations, occurrences, and conservative type inference."""

    def __init__(self, tree: Any, source: str, uri: str | None = None) -> None:
        self.tree = tree
        self.source = source
        self.uri = uri
        self.lines = source.split("\n") if source else [""]
        self.script_scope = Scope(
            "script",
            tree,
            None,
            start=(0, 0),
            end=(len(self.lines) - 1, len(self.lines[-1]) if self.lines else 0),
        )
        self.scopes: list[Scope] = [self.script_scope]
        self.symbols: list[Symbol] = []
        self.occurrences: list[Occurrence] = []
        self.member_refs: list[MemberRef] = []
        self.types: dict[str, Symbol] = {}
        self.enums: dict[str, Symbol] = {}
        self.enum_members: dict[str, dict[str, Symbol]] = {}
        self.udt_fields: dict[str, dict[str, Symbol]] = {}
        self.udt_methods: dict[str, dict[str, Symbol]] = {}
        self.functions: dict[str, Symbol] = {}
        self.imports: dict[str, Symbol] = {}
        self._scope_for_node: dict[int, Scope] = {}
        self._seen_occurrences: set[tuple[int, str, bool]] = set()
        self._order = 0
        self._build()

    # ------------------------------------------------------------------
    # Public queries
    # ------------------------------------------------------------------

    def scope_at(self, line: int, column: int) -> Scope:
        """Return the deepest scope containing LSP position (*line*, *column*)."""
        best = self.script_scope
        for scope in self.scopes:
            if _span_contains(scope.start, scope.end, line, column):
                best = scope
        return best

    def resolve(self, name: str, scope: Scope | None = None) -> Symbol | None:
        """Resolve *name* starting at *scope* (script scope by default)."""
        if not name:
            return None
        return (scope or self.script_scope).lookup(name)

    def symbol_at(self, line: int, column: int) -> Symbol | None:
        """Resolve the symbol at a cursor position, including member accesses."""
        occurrence = self.occurrence_at(line, column)
        if occurrence is not None:
            return occurrence.symbol
        member = self.member_at(line, column)
        if member is not None:
            return member.symbol
        # Fallback for positions not represented by the AST (e.g. a name in a
        # comment or a mid-edit buffer): use the identifier segment and scope.
        word = _word_at(self.lines, line, column)
        if not word:
            return None
        return self.resolve(word, self.scope_at(line, column))

    def occurrence_at(self, line: int, column: int) -> Occurrence | None:
        """Return the identifier occurrence containing the cursor."""
        for occurrence in self.occurrences:
            if occurrence.contains(line, column):
                return occurrence
        return None

    def member_at(self, line: int, column: int) -> MemberRef | None:
        """Return the member access containing the cursor."""
        for member in self.member_refs:
            if member.contains(line, column):
                return member
        return None

    def occurrences_for(self, symbol: Symbol, *, include_declaration: bool = True) -> list[Occurrence]:
        """Return all occurrences bound to *symbol*."""
        result = [occ for occ in self.occurrences if occ.symbol is symbol]
        if not include_declaration:
            result = [occ for occ in result if not occ.write or occ.node is not symbol.name_node]
        result.sort(key=lambda occ: (occ.line, occ.column))
        return result

    def symbols_in_scope(self, scope: Scope, *, include_parents: bool = True) -> list[Symbol]:
        """User symbols visible from *scope* (nearest first, no duplicates)."""
        result: list[Symbol] = []
        seen: set[str] = set()
        current: Scope | None = scope
        while current is not None:
            for symbol in current.symbols.values():
                if symbol.name not in seen:
                    seen.add(symbol.name)
                    result.append(symbol)
            if not include_parents:
                break
            current = current.parent
        return result

    def member_candidates(self, base_type: str | None) -> list[Symbol]:
        """Fields + methods available on *base_type* (UDT), sorted by name."""
        if not base_type:
            return []
        base = _base_type_name(base_type)
        if not base:
            return []
        fields = list(self.udt_fields.get(base, {}).values())
        methods = list(self.udt_methods.get(base, {}).values())
        return sorted(fields + methods, key=lambda symbol: symbol.name)

    def enum_member_symbols(self, enum_name: str) -> list[Symbol]:
        """Members of *enum_name* sorted by declaration order."""
        members = self.enum_members.get(enum_name, {})
        return sorted(members.values(), key=lambda symbol: symbol.order)

    # ------------------------------------------------------------------
    # Type inference
    # ------------------------------------------------------------------

    def infer_type(self, expr: Any, scope: Scope | None = None, depth: int = 0) -> str | None:
        """Conservatively infer a Pine type label for *expr*.

        Returns strings such as ``series float``, ``Point``, ``array<float>``,
        ``input int``, or ``None`` when the type cannot be known statically.
        """
        if expr is None or depth > _MAX_INFER_DEPTH:
            return None
        scope = scope or self.script_scope
        if isinstance(expr, ast.Constant):
            return _constant_type(expr.value)
        if isinstance(expr, ast.Name):
            symbol = self.resolve(expr.id or "", scope)
            if symbol is not None and symbol.type_label:
                return symbol.type_label
            return BUILTIN_VAR_TYPES.get(expr.id or "")
        if isinstance(expr, ast.Attribute):
            return self._infer_attribute(expr, scope, depth + 1)
        if isinstance(expr, ast.Call):
            return self._infer_call(expr, scope, depth + 1)
        if isinstance(expr, ast.Subscript):
            return self.infer_type(expr.value, scope, depth + 1)
        if isinstance(expr, ast.BinOp):
            return _infer_binop(
                self.infer_type(expr.left, scope, depth + 1),
                self.infer_type(expr.right, scope, depth + 1),
            )
        if isinstance(expr, ast.UnaryOp):
            return self.infer_type(expr.operand, scope, depth + 1)
        if isinstance(expr, (ast.Compare, ast.BoolOp)):
            return "series bool"
        if isinstance(expr, ast.Conditional):
            return self.infer_type(expr.body, scope, depth + 1) or self.infer_type(expr.orelse, scope, depth + 1)
        if isinstance(expr, ast.Qualify):
            inner = self.infer_type(expr.value, scope, depth + 1)
            qualifier = _node_name(expr.qualifier)
            if inner and qualifier:
                return f"{qualifier} {inner}"
            return inner
        if isinstance(expr, ast.Specialize):
            base = _node_name(expr.value)
            args = ", ".join(filter(None, (_type_expr_name(arg) for arg in _specialize_args(expr))))
            return f"{base}<{args}>" if base and args else base
        if isinstance(expr, ast.Tuple):
            return "tuple"
        if isinstance(expr, (ast.If, ast.Switch, ast.Once)):
            body = getattr(expr, "body", None) or []
            if body:
                last = body[-1]
                value = getattr(last, "value", None) if isinstance(last, ast.Expr) else last
                return self.infer_type(value, scope, depth + 1)
        return None

    def _infer_attribute(self, expr: ast.Attribute, scope: Scope, depth: int) -> str | None:
        base_type = self.infer_type(expr.value, scope, depth)
        name = expr.attr or ""
        if not base_type:
            if isinstance(expr.value, ast.Name) and expr.value.id == "color":
                return "series color"
            return None
        base = _base_type_name(base_type)
        if not base:
            return None
        field_symbol = self.udt_fields.get(base, {}).get(name)
        if field_symbol is not None:
            return field_symbol.type_label
        if base in self.enums:
            return base
        if base == "color" or _is_namespace(base, "color"):
            return "series color"
        return None

    def _infer_call(self, expr: ast.Call, scope: Scope, depth: int) -> str | None:
        func = expr.func
        if isinstance(func, ast.Specialize):
            base = _type_expr_name(func.value)
            args = [_type_expr_name(arg) for arg in _specialize_args(func)]
            if base == "array.new" and args:
                return f"array<{args[0]}>"
            if base == "matrix.new" and args:
                return f"matrix<{args[0]}>"
            if base == "map.new" and len(args) >= 2:
                return f"map<{args[0]}, {args[1]}>"
            return None
        if isinstance(func, ast.Name):
            symbol = self.resolve(func.id or "", scope)
            if symbol is not None:
                return _function_return_type(symbol, self)
            return _builtin_return_type(func.id or "")
        if isinstance(func, ast.Attribute):
            name = func.attr or ""
            base_expr = func.value
            base_type = self.infer_type(base_expr, scope, depth)
            if isinstance(base_expr, ast.Name):
                base_name = base_expr.id or ""
                if base_name in self.types:
                    if name == "new":
                        return base_name
                    method = self.udt_methods.get(base_name, {}).get(name)
                    if method is not None:
                        return _function_return_type(method, self)
                if base_name in self.enums:
                    return base_name
                if base_name in BUILTIN_NAMESPACES:
                    receiver_type = None
                    if expr.args:
                        first = getattr(expr.args[0], "value", None)
                        receiver_type = self.infer_type(first, scope, depth)
                    collection_type = _collection_result(base_name, name, receiver_type or base_type)
                    if collection_type:
                        return collection_type
                    return _builtin_return_type(f"{base_name}.{name}")
            if base_type:
                base = _base_type_name(base_type)
                if base:
                    method = self.udt_methods.get(base, {}).get(name)
                    if method is not None:
                        return _function_return_type(method, self)
                    if base in self.enums:
                        return base
                    collection_type = _collection_result(base, name, base_type)
                    if collection_type:
                        return collection_type
            qualified = _qualified_name(func)
            return _builtin_return_type(qualified) if qualified else None
        return None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        body = getattr(self.tree, "body", None) or []
        self._predeclare(body, self.script_scope)
        self._walk_body(body, self.script_scope)

    def _predeclare(self, body: list[Any], scope: Scope) -> None:
        for stmt in body:
            if isinstance(stmt, ast.FunctionDef):
                self._declare_function(stmt, scope)
            elif isinstance(stmt, ast.TypeDef):
                self._declare_type(stmt, scope)
            elif isinstance(stmt, ast.EnumDef):
                self._declare_enum(stmt, scope)
            elif isinstance(stmt, ast.Import):
                self._declare_import(stmt, scope)
            elif isinstance(stmt, ast.Assign):
                self._declare_assign_targets(stmt, scope)

    def _new_symbol(
        self,
        name: str,
        kind: str,
        node: Any,
        scope: Scope,
        *,
        name_node: Any | None = None,
        type_label: str | None = None,
        mode: str | None = None,
        export: bool = False,
        container: str | None = None,
        annotations: list[str] | None = None,
        signature: str | None = None,
    ) -> Symbol:
        self._order += 1
        symbol = Symbol(
            name=name,
            kind=kind,
            node=node,
            scope=scope,
            name_node=name_node,
            type_label=type_label,
            mode=mode,
            export=export,
            container=container,
            annotations=list(annotations or []),
            signature=signature,
            order=self._order,
        )
        self.symbols.append(symbol)
        return symbol

    def _declare_function(self, node: ast.FunctionDef, scope: Scope) -> Symbol:
        name = node.name or ""
        if not name:
            return self._new_symbol("", "function", node, scope)
        kind = "method" if node.method else "function"
        container = None
        if node.method and node.args:
            container = _type_expr_name(getattr(node.args[0], "type", None))
        symbol = self._new_symbol(
            name,
            kind,
            node,
            scope,
            name_node=node,
            type_label=_type_expr_name(node.returns),
            export=bool(node.export),
            container=container,
            annotations=_annotations_of(node),
            signature=_function_signature(node),
        )
        scope.define(symbol)
        self.functions[name] = symbol
        if container:
            self.udt_methods.setdefault(container, {})[name] = symbol
        return symbol

    def _declare_type(self, node: ast.TypeDef, scope: Scope) -> Symbol:
        name = node.name or ""
        symbol = self._new_symbol(
            name,
            "type",
            node,
            scope,
            name_node=node,
            export=bool(node.export),
            annotations=_annotations_of(node),
            signature=f"{'export ' if node.export else ''}type {name}",
        )
        if name:
            scope.define(symbol)
            self.types[name] = symbol
        type_scope = self._make_scope("type", node, scope, body=node.body)
        self._scope_for_node[id(node)] = type_scope
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in _assign_targets(stmt):
                    if not isinstance(target, ast.Name):
                        continue
                    field_symbol = self._new_symbol(
                        target.id or "",
                        "field",
                        stmt,
                        type_scope,
                        name_node=target,
                        type_label=_type_expr_name(stmt.type) or self.infer_type(stmt.value, scope),
                        export=bool(stmt.export),
                        container=name,
                        annotations=_annotations_of(stmt),
                        signature=_field_signature(stmt, target),
                    )
                    if name:
                        self.udt_fields.setdefault(name, {})[field_symbol.name] = field_symbol
                    type_scope.define(field_symbol)
        return symbol

    def _declare_enum(self, node: ast.EnumDef, scope: Scope) -> Symbol:
        name = node.name or ""
        symbol = self._new_symbol(
            name,
            "enum",
            node,
            scope,
            name_node=node,
            export=bool(node.export),
            annotations=_annotations_of(node),
            signature=f"{'export ' if node.export else ''}enum {name}",
        )
        if name:
            scope.define(symbol)
            self.enums[name] = symbol
        enum_scope = self._make_scope("enum", node, scope, body=node.body)
        self._scope_for_node[id(node)] = enum_scope
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                member = self._new_symbol(
                    stmt.target.id or "",
                    "enum_member",
                    stmt,
                    enum_scope,
                    name_node=stmt.target,
                    type_label=name,
                    export=bool(node.export),
                    container=name,
                    annotations=_annotations_of(stmt),
                    signature=f"{name}.{stmt.target.id}",
                )
                if name:
                    self.enum_members.setdefault(name, {})[member.name] = member
                enum_scope.define(member)
        return symbol

    def _declare_import(self, node: ast.Import, scope: Scope) -> Symbol:
        alias = node.alias or node.name or ""
        signature = f"import {node.namespace}/{node.name}/{node.version}"
        if node.alias:
            signature += f" as {node.alias}"
        symbol = self._new_symbol(
            alias,
            "import",
            node,
            scope,
            name_node=node,
            type_label=f"{node.namespace}/{node.name}/{node.version}",
            signature=signature,
        )
        if alias:
            scope.define(symbol)
            self.imports[alias] = symbol
        return symbol

    def _declare_assign_targets(self, node: ast.Assign, scope: Scope) -> None:
        type_label = _type_expr_name(node.type) or self.infer_type(node.value, scope)
        mode = _mode_name(node.mode)
        for target in _assign_targets(node):
            if not isinstance(target, ast.Name):
                continue
            symbol = self._new_symbol(
                target.id or "",
                "variable",
                node,
                scope,
                name_node=target,
                type_label=type_label,
                mode=mode,
                export=bool(node.export),
                annotations=_annotations_of(node),
                signature=_assign_signature(node, target),
            )
            scope.define(symbol)

    def _make_scope(self, kind: str, node: Any, parent: Scope, *, body: list[Any] | None = None) -> Scope:
        start, end = _scope_span(node, body, self.lines)
        scope = Scope(kind, node, parent, start=start, end=end)
        parent.children.append(scope)
        self.scopes.append(scope)
        return scope

    def _walk_body(self, body: list[Any], scope: Scope) -> None:
        for stmt in body:
            self._walk_stmt(stmt, scope)

    def _walk_stmt(self, node: Any, scope: Scope) -> None:
        if isinstance(node, ast.FunctionDef):
            symbol = scope.symbols.get(node.name or "")
            if symbol is not None:
                self._add_occurrence(symbol, node, node.name or "", scope, write=True)
            fn_scope = self._make_scope("function", node, scope)
            self._scope_for_node[id(node)] = fn_scope
            for param in node.args or []:
                self._walk_type_expr(getattr(param, "type", None), fn_scope)
                default = getattr(param, "default", None)
                if default is not None:
                    self._walk_expr(default, fn_scope)
                param_name = getattr(param, "name", None)
                if not param_name:
                    continue
                param_symbol = self._new_symbol(
                    param_name,
                    "param",
                    param,
                    fn_scope,
                    name_node=param,
                    type_label=_type_expr_name(getattr(param, "type", None)),
                    signature=_param_signature(param),
                )
                fn_scope.define(param_symbol)
            self._walk_type_expr(node.returns, fn_scope)
            self._predeclare(node.body, fn_scope)
            self._walk_body(node.body, fn_scope)
            return

        if isinstance(node, ast.TypeDef):
            symbol = scope.symbols.get(node.name or "")
            if symbol is not None:
                self._add_occurrence(symbol, node, node.name or "", scope, write=True)
            type_scope = self._scope_for_node.get(id(node))
            if type_scope is None:
                type_scope = self._make_scope("type", node, scope, body=node.body)
                self._scope_for_node[id(node)] = type_scope
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    self._walk_type_expr(stmt.type, type_scope)
                    for target in _assign_targets(stmt):
                        if isinstance(target, ast.Name):
                            field_symbol = type_scope.symbols.get(target.id or "")
                            if field_symbol is not None:
                                self._add_occurrence(field_symbol, target, target.id or "", type_scope, write=True)
            return

        if isinstance(node, ast.EnumDef):
            symbol = scope.symbols.get(node.name or "")
            if symbol is not None:
                self._add_occurrence(symbol, node, node.name or "", scope, write=True)
            enum_scope = self._scope_for_node.get(id(node))
            if enum_scope is None:
                enum_scope = self._make_scope("enum", node, scope, body=node.body)
                self._scope_for_node[id(node)] = enum_scope
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                    member = enum_scope.symbols.get(stmt.target.id or "")
                    if member is not None:
                        self._add_occurrence(member, stmt.target, stmt.target.id or "", enum_scope, write=True)
                    self._walk_expr(stmt.value, enum_scope)
            return

        if isinstance(node, ast.Import):
            alias = node.alias or node.name or ""
            symbol = scope.symbols.get(alias)
            if symbol is not None:
                self._add_occurrence(symbol, node, alias, scope, write=True)
            return

        if isinstance(node, ast.Assign):
            self._walk_type_expr(node.type, scope)
            for target in _assign_targets(node):
                self._walk_target(target, scope, declare=True)
            self._walk_expr(node.value, scope)
            return

        if isinstance(node, (ast.ReAssign, ast.AugAssign)):
            self._walk_target(node.target, scope, declare=False)
            self._walk_expr(getattr(node, "value", None), scope)
            return

        if isinstance(node, ast.Expr):
            self._walk_expr(node.value, scope)
            return

        if isinstance(node, (ast.Break, ast.Continue)):
            return

        # Unknown statement shape: walk children as expressions.
        for child in iter_child_nodes(node):
            self._walk_expr(child, scope)

    def _declare_loop_target(self, target: Any, scope: Scope) -> None:
        """Declare a ``for`` target in the loop scope."""
        if isinstance(target, ast.Name):
            symbol = self._new_symbol(
                target.id or "",
                "variable",
                target,
                scope,
                name_node=target,
                signature=f"for {target.id}",
            )
            scope.define(symbol)
            return
        if isinstance(target, ast.Tuple):
            for elt in target.elts or []:
                self._declare_loop_target(elt, scope)

    def _walk_target(self, target: Any, scope: Scope, *, declare: bool) -> None:
        if isinstance(target, ast.Name):
            name = target.id or ""
            symbol = scope.symbols.get(name) if declare else self.resolve(name, scope)
            if symbol is not None:
                self._add_occurrence(symbol, target, name, scope, write=True)
            return
        if isinstance(target, ast.Tuple):
            for elt in target.elts or []:
                self._walk_target(elt, scope, declare=declare)
            return
        if isinstance(target, ast.Attribute):
            self._walk_expr(target.value, scope)
            self._add_member_ref(target, scope, write=True)
            return
        if isinstance(target, ast.Subscript):
            self._walk_expr(target.value, scope)
            self._walk_expr(target.slice, scope)
            return
        self._walk_expr(target, scope)

    def _walk_expr(self, node: Any, scope: Scope) -> None:
        if node is None:
            return
        if isinstance(node, ast.Name):
            name = node.id or ""
            symbol = self.resolve(name, scope)
            self._add_occurrence(symbol, node, name, scope, write=False)
            return
        if isinstance(node, ast.Attribute):
            self._walk_expr(node.value, scope)
            self._add_member_ref(node, scope, write=False)
            return
        if isinstance(node, ast.Call):
            self._walk_expr(node.func, scope)
            for arg in node.args or []:
                self._walk_expr(getattr(arg, "value", arg), scope)
            return
        if isinstance(node, ast.Subscript):
            self._walk_expr(node.value, scope)
            self._walk_expr(node.slice, scope)
            return
        if isinstance(node, ast.BinOp):
            self._walk_expr(node.left, scope)
            self._walk_expr(node.right, scope)
            return
        if isinstance(node, ast.BoolOp):
            for value in node.values or []:
                self._walk_expr(value, scope)
            return
        if isinstance(node, ast.UnaryOp):
            self._walk_expr(node.operand, scope)
            return
        if isinstance(node, ast.Compare):
            self._walk_expr(node.left, scope)
            for comparator in node.comparators or []:
                self._walk_expr(comparator, scope)
            return
        if isinstance(node, ast.Conditional):
            self._walk_expr(node.test, scope)
            self._walk_expr(node.body, scope)
            self._walk_expr(node.orelse, scope)
            return
        if isinstance(node, ast.Tuple):
            for elt in node.elts or []:
                self._walk_expr(elt, scope)
            return
        if isinstance(node, ast.Qualify):
            self._walk_expr(node.value, scope)
            return
        if isinstance(node, ast.Specialize):
            self._walk_expr(node.value, scope)
            for arg in _specialize_args(node):
                self._walk_type_expr(arg, scope)
            return
        if isinstance(node, ast.If):
            self._walk_expr(node.test, scope)
            self._walk_block(node.body, scope, "if")
            if node.orelse:
                self._walk_block(node.orelse, scope, "else")
            return
        if isinstance(node, ast.While):
            self._walk_expr(node.test, scope)
            self._walk_block(node.body, scope, "while")
            return
        if isinstance(node, ast.ForTo):
            self._walk_expr(node.start, scope)
            self._walk_expr(node.end, scope)
            self._walk_expr(node.step, scope)
            loop_scope = self._make_scope("for", node, scope, body=node.body)
            self._declare_loop_target(node.target, loop_scope)
            self._walk_target(node.target, loop_scope, declare=True)
            self._predeclare(node.body, loop_scope)
            self._walk_body(node.body, loop_scope)
            return
        if isinstance(node, ast.ForIn):
            self._walk_expr(node.iter, scope)
            loop_scope = self._make_scope("for", node, scope, body=node.body)
            self._declare_loop_target(node.target, loop_scope)
            self._walk_target(node.target, loop_scope, declare=True)
            self._predeclare(node.body, loop_scope)
            self._walk_body(node.body, loop_scope)
            return
        if isinstance(node, ast.Switch):
            self._walk_expr(node.subject, scope)
            for case in node.cases or []:
                case_body = getattr(case, "body", None) or []
                case_scope = self._make_scope("switch", case, scope, body=case_body)
                self._walk_expr(getattr(case, "pattern", None), case_scope)
                self._predeclare(case_body, case_scope)
                self._walk_body(case_body, case_scope)
            return
        if isinstance(node, ast.Once):
            self._walk_expr(node.test, scope)
            self._walk_block(node.body, scope, "once")
            return
        for child in iter_child_nodes(node):
            self._walk_expr(child, scope)

    def _walk_block(self, body: list[Any], parent: Scope, kind: str) -> None:
        block_scope = self._make_scope(kind, body[0] if body else parent.node, parent, body=body)
        self._predeclare(body, block_scope)
        self._walk_body(body, block_scope)

    def _walk_type_expr(self, node: Any, scope: Scope) -> None:
        if node is None:
            return
        if isinstance(node, ast.Name):
            symbol = self.resolve(node.id or "", scope)
            if symbol is not None and symbol.kind in {"type", "enum"}:
                self._add_occurrence(symbol, node, node.id or "", scope, write=False, type_use=True)
            return
        if isinstance(node, ast.Attribute):
            self._walk_type_expr(node.value, scope)
            self._add_member_ref(node, scope, write=False, type_use=True)
            return
        if isinstance(node, (ast.Qualify, ast.Specialize)):
            self._walk_type_expr(getattr(node, "value", None), scope)
            for arg in _specialize_args(node):
                self._walk_type_expr(arg, scope)
            return
        for child in iter_child_nodes(node):
            self._walk_type_expr(child, scope)

    def _add_occurrence(
        self,
        symbol: Symbol | None,
        node: Any,
        name: str,
        scope: Scope,
        *,
        write: bool,
        type_use: bool = False,
    ) -> None:
        if not name:
            return
        key = (id(node), name, write)
        if key in self._seen_occurrences:
            return
        self._seen_occurrences.add(key)
        span = _name_span(node, name, self.lines)
        if span is None:
            return
        self.occurrences.append(
            Occurrence(
                name=name,
                line=span[0],
                column=span[1],
                end_line=span[2],
                end_column=span[3],
                scope=scope,
                node=node,
                symbol=symbol,
                write=write,
                type_use=type_use,
            )
        )

    def _add_member_ref(self, node: ast.Attribute, scope: Scope, *, write: bool, type_use: bool = False) -> None:
        name = node.attr or ""
        if not name:
            return
        span = _attr_span(node, name, self.lines)
        if span is None:
            return
        base_type = self.infer_type(node.value, scope)
        base_name = _base_type_name(base_type) if base_type else None
        kind = "unknown"
        symbol: Symbol | None = None
        builtin_name: str | None = None

        # Enum member / type constructor / UDT member.
        if isinstance(node.value, ast.Name):
            receiver = node.value.id or ""
            if receiver in self.enums:
                symbol = self.enum_members.get(receiver, {}).get(name)
                if symbol is not None:
                    kind = "enum_member"
            elif receiver in self.types:
                if name == "new":
                    kind = "constructor"
                else:
                    symbol = self.udt_methods.get(receiver, {}).get(name)
                    if symbol is not None:
                        kind = "method"
            elif receiver in self.imports:
                kind = "import"
            elif receiver in BUILTIN_NAMESPACES:
                builtin_name = f"{receiver}.{name}"
                kind = "builtin"
        if symbol is None and base_name:
            field_symbol = self.udt_fields.get(base_name, {}).get(name)
            if field_symbol is not None:
                symbol = field_symbol
                kind = "field"
            else:
                method = self.udt_methods.get(base_name, {}).get(name)
                if method is not None:
                    symbol = method
                    kind = "method"
        if symbol is None and kind == "unknown":
            qualified = _qualified_name(node)
            if qualified:
                root = qualified.split(".", 1)[0]
                if root in BUILTIN_NAMESPACES:
                    builtin_name = qualified
                    kind = "builtin"

        member = MemberRef(
            name=name,
            line=span[0],
            column=span[1],
            end_line=span[2],
            end_column=span[3],
            scope=scope,
            node=node,
            base_type=base_type,
            symbol=symbol,
            kind=kind,
            builtin_name=builtin_name,
        )
        self.member_refs.append(member)
        if symbol is not None:
            self._add_occurrence(symbol, node, name, scope, write=write, type_use=type_use)


def build_symbol_index(tree: Any, source: str, uri: str | None = None) -> SymbolIndex:
    """Build a :class:`SymbolIndex` for *tree* and *source*."""
    return SymbolIndex(tree, source, uri)


def ensure_symbol_index(
    source: str | None,
    tree: Any | None = ...,
    analysis: SymbolIndex | None = None,
) -> SymbolIndex | None:
    """Return *analysis*, or build one from *tree*/*source*.

    ``tree is ...`` means "parse the source"; ``tree is None`` means the
    workspace already failed to parse and no index is available.
    """
    if analysis is not None:
        return analysis
    if not source:
        return None
    if tree is ...:
        try:
            from pynescript.ast.helper import parse

            tree = parse(source)
        except Exception:
            return None
    if tree is None:
        return None
    try:
        return build_symbol_index(tree, source)
    except Exception:
        return None


def infer_type(index: SymbolIndex, expr: Any, scope: Scope | None = None) -> str | None:
    """Module-level convenience wrapper for :meth:`SymbolIndex.infer_type`."""
    return index.infer_type(expr, scope)


# ----------------------------------------------------------------------
# Source-position helpers
# ----------------------------------------------------------------------


def _span_contains(start: tuple[int, int], end: tuple[int, int], line: int, column: int) -> bool:
    if (line, column) < start:
        return False
    if (line, column) > end:
        return False
    return True


def _scope_span(node: Any, body: list[Any] | None, lines: list[str]) -> tuple[tuple[int, int], tuple[int, int]]:
    start = _node_start(node)
    end = _node_end(node, lines)
    if body:
        last = body[-1]
        body_end = _node_end(last, lines)
        if body_end > end or end == start:
            end = body_end
    return start, end


def _node_start(node: Any) -> tuple[int, int]:
    lineno = int(getattr(node, "lineno", 1) or 1)
    col = int(getattr(node, "col_offset", 0) or 0)
    return (max(0, lineno - 1), max(0, col))


def _node_end(node: Any, lines: list[str]) -> tuple[int, int]:
    start_line = max(0, int(getattr(node, "lineno", 1) or 1) - 1)
    lineno = int(getattr(node, "end_lineno", None) or getattr(node, "lineno", 1) or 1)
    col = getattr(node, "end_col_offset", None)
    line_idx = max(0, lineno - 1)
    if col is None:
        text = lines[line_idx] if 0 <= line_idx < len(lines) else ""
        col = len(text)
    col = max(0, int(col))
    # ANTLR often reports the end as the first column of the next line. Treat
    # that as the previous line's end so a block scope does not swallow the
    # next top-level statement.
    if col == 0 and line_idx > start_line:
        line_idx -= 1
        col = len(lines[line_idx]) if 0 <= line_idx < len(lines) else 0
    return (line_idx, col)


def _line_text(lines: list[str], line: int) -> str:
    if 0 <= line < len(lines):
        return lines[line]
    return ""


def _word_at(lines: list[str], line: int, column: int) -> str:
    text = _line_text(lines, line)
    if not text:
        return ""
    col = max(0, min(column, len(text)))
    start = col
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
        start -= 1
    end = col
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    return text[start:end]


def _find_ident(
    line: str,
    name: str,
    *,
    start: int = 0,
    end: int | None = None,
    last: bool = False,
) -> tuple[int, int] | None:
    if not name:
        return None
    end = len(line) if end is None else min(len(line), max(0, end))
    start = max(0, min(start, end))
    matches = [
        (match.start(), match.end())
        for match in _IDENT_RE.finditer(line, start, end)
        if match.group(0) == name
    ]
    if not matches:
        return None
    return matches[-1] if last else matches[0]


def _name_span(node: Any, name: str, lines: list[str]) -> tuple[int, int, int, int] | None:
    """Exact 0-based ``(line, col, end_line, end_col)`` for a declared name."""
    if not name:
        return None
    lineno = int(getattr(node, "lineno", 1) or 1)
    line_idx = max(0, lineno - 1)
    line = _line_text(lines, line_idx)
    if not line:
        return None
    start_col = int(getattr(node, "col_offset", 0) or 0)
    end_col = getattr(node, "end_col_offset", None)
    end_col = int(end_col) if isinstance(end_col, int) else len(line)

    if isinstance(node, ast.Name):
        if line[start_col : start_col + len(name)] == name:
            return (line_idx, start_col, line_idx, start_col + len(name))
    if isinstance(node, ast.Param):
        segment = line[start_col:end_col]
        before_default = segment.split("=", 1)[0]
        found = _find_ident(before_default, name, last=True)
        if found is not None:
            col = start_col + found[0]
            return (line_idx, col, line_idx, col + len(name))
    if isinstance(node, ast.FunctionDef):
        # ``export method name(...)`` — the name is the last identifier before
        # the parameter list.
        head_end = line.find("(", start_col)
        if head_end < 0:
            head_end = end_col
        found = _find_ident(line, name, start=start_col, end=head_end, last=True)
        if found is not None:
            return (line_idx, found[0], line_idx, found[1])
    if isinstance(node, (ast.TypeDef, ast.EnumDef)):
        # ``export type Name`` / ``enum Name`` — first match on the header.
        head_end = line.find("{", start_col)
        if head_end < 0:
            head_end = end_col
        found = _find_ident(line, name, start=start_col, end=head_end, last=False)
        if found is not None:
            return (line_idx, found[0], line_idx, found[1])
    if isinstance(node, ast.Import):
        found = _find_ident(line, name, start=start_col, end=end_col, last=True)
        if found is not None:
            return (line_idx, found[0], line_idx, found[1])
    if isinstance(node, ast.Attribute):
        if end_col >= len(name) and line[end_col - len(name) : end_col] == name:
            return (line_idx, end_col - len(name), line_idx, end_col)
    if isinstance(node, ast.Arg):
        if line[start_col : start_col + len(name)] == name:
            return (line_idx, start_col, line_idx, start_col + len(name))
    found = _find_ident(line, name, start=start_col, end=end_col, last=False)
    if found is not None:
        return (line_idx, found[0], line_idx, found[1])
    found = _find_ident(line, name, last=True)
    if found is not None:
        return (line_idx, found[0], line_idx, found[1])
    return None


def _attr_span(node: ast.Attribute, name: str, lines: list[str]) -> tuple[int, int, int, int] | None:
    lineno = int(getattr(node, "lineno", 1) or 1)
    line_idx = max(0, lineno - 1)
    line = _line_text(lines, line_idx)
    if not line:
        return None
    end_col = getattr(node, "end_col_offset", None)
    if isinstance(end_col, int) and end_col >= len(name) and line[end_col - len(name) : end_col] == name:
        return (line_idx, end_col - len(name), line_idx, end_col)
    start_col = int(getattr(node, "col_offset", 0) or 0)
    found = _find_ident(line, name, start=start_col, last=True)
    if found is not None:
        return (line_idx, found[0], line_idx, found[1])
    return None


def _annotations_of(node: Any) -> list[str]:
    """Return a node's annotation strings as ``list[str]``."""
    raw = getattr(node, "annotations", None) or []
    return [item.decode() if isinstance(item, bytes) else str(item) for item in raw]


def _assign_targets(node: ast.Assign) -> list[Any]:
    target = node.target
    if isinstance(target, ast.Tuple):
        return list(target.elts or [])
    return [target]


def _constant_type(value: Any) -> str | None:
    if isinstance(value, bool):
        return "const bool"
    if isinstance(value, int):
        return "const int"
    if isinstance(value, float):
        return "const float"
    if isinstance(value, str):
        return "const string"
    return None


def _infer_binop(left: str | None, right: str | None) -> str | None:
    if left is None and right is None:
        return None
    if left == "series string" or right == "series string":
        return "series string"
    if (left and "string" in left) or (right and "string" in right):
        return "string"
    if (left and "float" in left) or (right and "float" in right):
        return "series float"
    if (left and "int" in left) or (right and "int" in right):
        return "series int"
    return left or right


def _collection_result(base: str | None, member: str, base_type: str | None) -> str | None:
    """Return the element/value type for ``array.get`` / ``map.get`` style calls."""
    if not base or not base_type:
        return None
    if "<" not in base_type or not base_type.endswith(">"):
        return None
    inner = base_type[base_type.find("<") + 1 : -1]
    parts = [part.strip() for part in inner.split(",")]
    if base in {"array", "matrix"} and member in {"get", "shift", "pop", "first", "last"}:
        return parts[0] if parts else None
    if base == "map" and member in {"get"} and len(parts) >= 2:
        return parts[1]
    return None


def _function_return_type(symbol: Symbol, index: SymbolIndex) -> str | None:
    if symbol.type_label:
        return symbol.type_label
    node = symbol.node
    if not isinstance(node, ast.FunctionDef):
        return None
    body = node.body or []
    if not body:
        return None
    last = body[-1]
    value = last.value if isinstance(last, ast.Expr) else None
    if value is None:
        return None
    fn_scope = index._scope_for_node.get(id(node), symbol.scope)
    return index.infer_type(value, fn_scope)


def _builtin_return_type(name: str) -> str | None:
    """Best-effort builtin return type from metadata; ``None`` when unknown."""
    if not name:
        return None
    try:
        from pynescript.langserver.providers.builtin_metadata import get_builtin

        info = get_builtin(name)
    except Exception:
        return None
    if not info:
        return None
    # ``input.*`` returns an input-qualified type even when the docstring arrow
    # says ``→ int value``. Keep this ahead of generic doc parsing.
    if name.startswith("input."):
        leaf = name.split(".", 1)[1]
        if leaf in {"int", "float", "bool", "string", "color", "symbol", "session", "source", "time", "timeframe", "price"}:
            return f"input {leaf}"
        return "input"
    detail = str(info.get("detail") or "")
    if "→" in detail:
        result = detail.split("→", 1)[1].strip()
        return result or None
    documentation = str(info.get("documentation") or "")
    match = re.search(r"→\s*([^\n.]+)", documentation)
    if match:
        return match.group(1).strip()
    if name.startswith("ta."):
        return "series float"
    if name.startswith("math."):
        return "series float"
    if name.startswith("str."):
        return "series string"
    if name.startswith("color."):
        return "series color"
    for drawing in ("line", "linefill", "label", "box", "table", "polyline"):
        if name.startswith(drawing + "."):
            return drawing
    if name in {"array.new", "array.from", "array.copy"}:
        return "array"
    if name in {"matrix.new", "matrix.copy"}:
        return "matrix"
    if name in {"map.new", "map.copy"}:
        return "map"
    return None


def _type_expr_name(node: Any) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id or None
    if isinstance(node, ast.Attribute):
        base = _type_expr_name(node.value)
        return f"{base}.{node.attr}" if base and node.attr else (node.attr or None)
    if isinstance(node, ast.Qualify):
        inner = _type_expr_name(node.value)
        qualifier = _node_name(node.qualifier)
        return f"{qualifier} {inner}" if qualifier and inner else (inner or qualifier)
    if isinstance(node, ast.Specialize):
        base = _type_expr_name(node.value)
        args = ", ".join(filter(None, (_type_expr_name(arg) for arg in _specialize_args(node))))
        return f"{base}<{args}>" if base and args else base
    return None


def _specialize_args(node: Any) -> list[Any]:
    """Return ``Specialize.args`` as a flat list (singular field or Tuple)."""
    args = getattr(node, "args", None)
    if args is None:
        return []
    values = args if isinstance(args, list) else [args]
    flattened: list[Any] = []
    for value in values:
        if isinstance(value, ast.Tuple):
            flattened.extend(value.elts or [])
        else:
            flattened.append(value)
    return flattened


def _base_type_name(type_label: str | None) -> str | None:
    if not type_label:
        return None
    label = type_label.strip()
    for qualifier in _TYPE_QUALIFIERS:
        if label.startswith(qualifier + " "):
            label = label[len(qualifier) + 1 :].strip()
    if "<" in label:
        label = label.split("<", 1)[0].strip()
    return label or None


def _is_namespace(base: str, namespace: str) -> bool:
    return base == namespace


def _node_name(node: Any) -> str | None:
    if node is None:
        return None
    name = type(node).__name__.lower()
    return name if name in _TYPE_QUALIFIERS else None


def _mode_name(node: Any) -> str | None:
    if node is None:
        return None
    name = type(node).__name__.lower()
    return name if name in {"var", "varip"} else None


def _qualified_name(node: Any) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr or "")
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id or "")
    parts.reverse()
    return ".".join(part for part in parts if part)


def _function_signature(node: ast.FunctionDef) -> str:
    prefix = ""
    if node.export:
        prefix += "export "
    if node.method:
        prefix += "method "
    params = ", ".join(filter(None, (_param_signature(param) for param in (node.args or []))))
    result = f"{prefix}{node.name}({params})"
    returns = _type_expr_name(node.returns)
    if returns:
        result += f" → {returns}"
    return result


def _param_signature(param: Any) -> str:
    type_label = _type_expr_name(getattr(param, "type", None))
    name = getattr(param, "name", None) or ""
    return f"{type_label} {name}".strip() if type_label else name


def _field_signature(node: ast.Assign, target: ast.Name) -> str:
    type_label = _type_expr_name(node.type)
    name = target.id or ""
    return f"{type_label} {name}".strip() if type_label else name


def _assign_signature(node: ast.Assign, target: ast.Name) -> str:
    type_label = _type_expr_name(node.type)
    name = target.id or ""
    mode = _mode_name(node.mode)
    parts = []
    if mode:
        parts.append(mode)
    if type_label:
        parts.append(type_label)
    parts.append(name)
    return " ".join(parts)


def iter_symbols(index: SymbolIndex) -> Iterator[Symbol]:
    """Yield every declared symbol in declaration order."""
    return iter(index.symbols)


__all__ = [
    "BUILTIN_NAMESPACES",
    "BUILTIN_VAR_TYPES",
    "MemberRef",
    "Occurrence",
    "Scope",
    "Symbol",
    "SymbolIndex",
    "build_symbol_index",
    "ensure_symbol_index",
    "infer_type",
    "iter_symbols",
]
