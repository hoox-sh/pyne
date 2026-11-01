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

"""Opt-in semantic diagnostics derived from the static symbol index.

The editor stays quiet by default (``pynescript.diagnostics.semantic`` is
``false``). When enabled, only findings that are **decidable from declarations**
are reported — never guesses about builtins or dynamically typed expressions:

- ``S001`` — unknown member on a user-declared type or enum
  (``p.distnace``, ``Side.Selll``).
- ``S002`` — user-function call arity / parameter-name mismatch
  (too many positional arguments, missing required arguments, unknown named
  argument).

Builtin calls and member accesses on inferred-but-unknown receivers are
skipped: the catalog is intentionally incomplete for some host builtins, and
under-reporting is preferable to a false positive.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.ast.helper import walk
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import base_type_name


CODE_UNKNOWN_MEMBER = "S001"
CODE_CALL_ARITY = "S002"

_UNKNOWN_MEMBER_MESSAGE = "Unknown {member_kind} '{name}' on {container_kind} '{container}'."


def collect(index: SymbolIndex | None) -> list[lsp.Diagnostic]:
    """Return semantic diagnostics for *index* (empty when unavailable)."""
    if index is None:
        return []
    diagnostics = _unknown_members(index)
    diagnostics.extend(_call_arity(index))
    return diagnostics


def _unknown_members(index: SymbolIndex) -> list[lsp.Diagnostic]:
    diagnostics: list[lsp.Diagnostic] = []
    for member in index.member_refs:
        if member.kind != "unknown":
            continue
        container, container_kind = _member_container(index, member)
        if container is None:
            continue
        diagnostics.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(line=member.line, character=member.column),
                    end=lsp.Position(line=member.end_line, character=member.end_column),
                ),
                severity=lsp.DiagnosticSeverity.Warning,
                message=_UNKNOWN_MEMBER_MESSAGE.format(
                    member_kind="member" if container_kind == "enum" else "field or method",
                    name=member.name,
                    container_kind=container_kind,
                    container=container,
                ),
                source="pyne",
                code=CODE_UNKNOWN_MEMBER,
            )
        )
    return diagnostics


def _member_container(index: SymbolIndex, member: Any) -> tuple[str | None, str]:
    """Return ``(container_name, "type"|"enum")`` for an unresolved member."""
    receiver = member.node.value
    if isinstance(receiver, ast.Name):
        name = receiver.id or ""
        if name in index.enums:
            return name, "enum"
        if name in index.types:
            return name, "type"
    base = base_type_name(member.base_type)
    if base is None:
        return None, "type"
    if base in index.enums:
        return base, "enum"
    if base in index.types:
        return base, "type"
    return None, "type"


def _call_arity(index: SymbolIndex) -> list[lsp.Diagnostic]:
    diagnostics: list[lsp.Diagnostic] = []
    for node in walk(index.tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        diagnostic = _arity_diagnostic(index, node)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return diagnostics


def _arity_diagnostic(index: SymbolIndex, call: ast.Call) -> lsp.Diagnostic | None:
    func = call.func
    name = str(getattr(func, "id", "") or "")
    if not name:
        return None
    scope = index.scope_at(_line_index(func), int(getattr(func, "col_offset", 0) or 0))
    symbol = index.resolve(name, scope)
    if symbol is None or symbol.kind != "function":
        return None
    declaration = symbol.node
    if not isinstance(declaration, ast.FunctionDef) or getattr(declaration, "method", False):
        return None
    params: list[Any] = list(declaration.args or [])
    if any(not getattr(param, "name", None) for param in params):
        # Destructured / unnamed parameters: arity cannot be checked safely.
        return None
    param_names = [param.name for param in params]
    if len(set(param_names)) != len(param_names):
        return None

    positional: list[Any] = []
    named: dict[str, Any] = {}
    seen_named = False
    for arg in call.args or []:
        arg_name = getattr(arg, "name", None)
        if arg_name:
            seen_named = True
            if arg_name not in param_names:
                return _diagnostic(
                    _arg_name_range(index, arg),
                    f"Function '{name}' has no parameter named '{arg_name}'.",
                )
            if arg_name in named:
                continue
            named[arg_name] = arg
        else:
            if seen_named:
                # Positional after named: leave it to the parser/runtime.
                return None
            positional.append(arg)

    if len(positional) > len(params):
        return _diagnostic(
            _node_range(func, name),
            f"Function '{name}' expects at most {len(params)} argument(s) but got {len(positional)}.",
        )

    covered = set(param_names[: len(positional)]) | set(named)
    missing = [
        param.name for param in params if getattr(param, "default", None) is None and param.name not in covered
    ]
    if missing:
        joined = "', '".join(missing)
        return _diagnostic(
            _node_range(func, name),
            f"Function '{name}' is missing required argument(s): '{joined}'.",
        )
    return None


def _diagnostic(rng: lsp.Range | None, message: str) -> lsp.Diagnostic | None:
    if rng is None:
        return None
    return lsp.Diagnostic(
        range=rng,
        severity=lsp.DiagnosticSeverity.Warning,
        message=message,
        source="pyne",
        code=CODE_CALL_ARITY,
    )


def _line_index(node: Any) -> int:
    """0-based line for a 1-based AST node."""
    return max(0, int(getattr(node, "lineno", 1) or 1) - 1)


def _node_range(node: Any, fallback_name: str = "") -> lsp.Range | None:
    line = getattr(node, "lineno", None)
    column = getattr(node, "col_offset", None)
    if line is None or column is None:
        return None
    end_line = getattr(node, "end_lineno", None) or line
    end_column = getattr(node, "end_col_offset", None)
    if end_column is None:
        end_column = int(column) + len(fallback_name)
    return lsp.Range(
        start=lsp.Position(line=int(line) - 1, character=int(column)),
        end=lsp.Position(line=int(end_line) - 1, character=int(end_column)),
    )


def _arg_name_range(index: SymbolIndex, arg: Any) -> lsp.Range | None:
    """Locate the ``name=`` part of a named call argument."""
    name = getattr(arg, "name", None)
    value = getattr(arg, "value", None)
    if not name or value is None:
        return None
    line = _line_index(value)
    column = getattr(value, "col_offset", None)
    if column is None or not (0 <= line < len(index.lines)):
        return None
    text = index.lines[line]
    start = text.rfind(name, 0, int(column))
    if start < 0:
        return None
    between = text[start + len(name) : int(column)]
    if between.strip() != "=":
        return None
    return lsp.Range(
        start=lsp.Position(line=line, character=start),
        end=lsp.Position(line=line, character=start + len(name)),
    )


__all__ = ["CODE_CALL_ARITY", "CODE_UNKNOWN_MEMBER", "collect"]
