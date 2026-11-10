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
- ``S003`` — a value is too weak for its declared qualifier or base
  (``simple float x = close``, ``const int n = bar_index``, a ``series``
  argument passed to a ``simple`` parameter).
- ``S004`` — ``na`` has no contextual type (``x = na``). ``na`` in a typed
  context adopts that type and is not reported.

Builtin calls and member accesses on inferred-but-unknown receivers are
skipped: the catalog is intentionally incomplete for some host builtins
(parameter qualifiers such as ``ta.sma``'s ``simple int`` length are not
checked), and under-reporting is preferable to a false positive.
"""

from __future__ import annotations

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.ast.helper import walk
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import _type_expr_name
from pynescript.langserver.analysis import base_type_name
from pynescript.langserver.analysis import combine_types
from pynescript.langserver.analysis import types_compatible
from pynescript.langserver.protocol.utils import codepoint_column_to_utf16


CODE_UNKNOWN_MEMBER = "S001"
CODE_CALL_ARITY = "S002"
CODE_TYPE_MISMATCH = "S003"
CODE_NA_CONTEXT = "S004"

_UNKNOWN_MEMBER_MESSAGE = "Unknown {member_kind} '{name}' on {container_kind} '{container}'."


def collect(index: SymbolIndex | None) -> list[lsp.Diagnostic]:
    """Return semantic diagnostics for *index* (empty when unavailable).

    Columns are LSP UTF-16 code units. The symbol index stores Python
    code-point offsets; a non-BMP character earlier on the line (emoji)
    shifts the published range if that conversion is skipped.
    """
    if index is None:
        return []
    diagnostics = _unknown_members(index)
    diagnostics.extend(_call_arity(index))
    diagnostics.extend(_qualifier_mismatches(index))
    diagnostics.extend(_untyped_na(index))
    return [_diagnostic_utf16(index, item) for item in diagnostics if item is not None]


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
    missing = [param.name for param in params if getattr(param, "default", None) is None and param.name not in covered]
    if missing:
        joined = "', '".join(missing)
        return _diagnostic(
            _node_range(func, name),
            f"Function '{name}' is missing required argument(s): '{joined}'.",
        )
    return None


def _diagnostic(
    rng: lsp.Range | None,
    message: str,
    *,
    code: str = CODE_CALL_ARITY,
) -> lsp.Diagnostic | None:
    if rng is None:
        return None
    return lsp.Diagnostic(
        range=rng,
        severity=lsp.DiagnosticSeverity.Warning,
        message=message,
        source="pyne",
        code=code,
    )


def _diagnostic_utf16(index: SymbolIndex, diagnostic: lsp.Diagnostic) -> lsp.Diagnostic:
    """Convert a diagnostic's code-point columns to UTF-16."""
    rng = diagnostic.range
    diagnostic.range = lsp.Range(
        start=lsp.Position(line=rng.start.line, character=_column_utf16(index, rng.start.line, rng.start.character)),
        end=lsp.Position(line=rng.end.line, character=_column_utf16(index, rng.end.line, rng.end.character)),
    )
    return diagnostic


def _column_utf16(index: SymbolIndex, line: int, column: int) -> int:
    if column <= 0 or not index.lines or line < 0 or line >= len(index.lines):
        return max(0, column)
    text = index.lines[line]
    if text.endswith("\r"):
        text = text[:-1]
    column = min(column, len(text))
    return codepoint_column_to_utf16(text, column)


def _qualifier_mismatches(index: SymbolIndex) -> list[lsp.Diagnostic]:
    """S003 — declared qualifier/base is stronger than the value.

    Checks annotated assignments, ``:=`` / augmented assigns, and user-function
    arguments. ``na`` is compatible with every declared type (it adopts it).
    Unknown inferred types are skipped.
    """
    diagnostics: list[lsp.Diagnostic] = []
    for node in walk(index.tree):
        if isinstance(node, ast.Assign) and isinstance(node.target, ast.Name) and node.type is not None:
            diagnostic = _assignment_mismatch(index, node)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
            continue
        if isinstance(node, (ast.ReAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            diagnostic = _reassign_mismatch(index, node)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            diagnostics.extend(_call_type_mismatches(index, node))
    return diagnostics


def _untyped_na(index: SymbolIndex) -> list[lsp.Diagnostic]:
    """S004 — ``na`` used where no annotation or sibling operand gives it a type."""
    diagnostics: list[lsp.Diagnostic] = []
    for node in walk(index.tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.target, ast.Name):
            continue
        if node.type is not None or node.value is None:
            continue
        scope = index.scope_at(_line_index(node), int(getattr(node, "col_offset", 0) or 0))
        inferred = index.infer_type(node.value, scope)
        if inferred != "na":
            continue
        diagnostic = _diagnostic(
            _node_range(node.value, "na"),
            "Cannot determine the type of 'na' here. Annotate the variable or use it beside a typed value.",
            code=CODE_NA_CONTEXT,
        )
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return diagnostics


def _assignment_mismatch(index: SymbolIndex, node: ast.Assign) -> lsp.Diagnostic | None:
    declared = _type_expr_name(node.type)
    if not declared or node.value is None:
        return None
    scope = index.scope_at(_line_index(node), int(getattr(node, "col_offset", 0) or 0))
    inferred = index.infer_type(node.value, scope)
    if not inferred or inferred == "na" or types_compatible(inferred, declared):
        return None
    return _diagnostic(
        _node_range(node.value),
        f"Cannot use '{inferred}' where '{declared}' is required.",
        code=CODE_TYPE_MISMATCH,
    )


def _reassign_mismatch(index: SymbolIndex, node: Any) -> lsp.Diagnostic | None:
    name = node.target.id or ""
    scope = index.scope_at(_line_index(node.target), int(getattr(node.target, "col_offset", 0) or 0))
    symbol = index.resolve(name, scope)
    if symbol is None or not symbol.type_label or node.value is None:
        return None
    inferred = index.infer_type(node.value, scope)
    if isinstance(node, ast.AugAssign):
        op_name = type(node.op).__name__ if getattr(node, "op", None) is not None else ""
        op = "/" if op_name == "Div" else "+" if op_name == "Add" else None
        inferred = combine_types([symbol.type_label, inferred], op=op)
    if not inferred or inferred == "na" or types_compatible(inferred, symbol.type_label):
        return None
    return _diagnostic(
        _node_range(node.value),
        f"Cannot use '{inferred}' where '{symbol.type_label}' is required.",
        code=CODE_TYPE_MISMATCH,
    )


def _call_type_mismatches(index: SymbolIndex, call: ast.Call) -> list[lsp.Diagnostic]:
    func = call.func
    name = str(getattr(func, "id", "") or "")
    if not name:
        return []
    scope = index.scope_at(_line_index(func), int(getattr(func, "col_offset", 0) or 0))
    symbol = index.resolve(name, scope)
    if symbol is None or symbol.kind not in {"function", "method"}:
        return []
    declaration = symbol.node
    if not isinstance(declaration, ast.FunctionDef) or getattr(declaration, "method", False):
        return []
    params = list(declaration.args or [])
    diagnostics: list[lsp.Diagnostic] = []
    positional = 0
    seen_named = False
    for arg in call.args or []:
        arg_name = getattr(arg, "name", None)
        value = getattr(arg, "value", arg)
        if arg_name:
            seen_named = True
            param = next((item for item in params if getattr(item, "name", None) == arg_name), None)
        else:
            if seen_named:
                break
            param = params[positional] if positional < len(params) else None
            positional += 1
        if param is None:
            continue
        expected = _type_expr_name(getattr(param, "type", None))
        if not expected:
            continue
        inferred = index.infer_type(value, scope)
        if not inferred or inferred == "na" or types_compatible(inferred, expected):
            continue
        diagnostic = _diagnostic(
            _node_range(value),
            f"Cannot use '{inferred}' where '{expected}' is required.",
            code=CODE_TYPE_MISMATCH,
        )
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return diagnostics


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


__all__ = [
    "CODE_CALL_ARITY",
    "CODE_NA_CONTEXT",
    "CODE_TYPE_MISMATCH",
    "CODE_UNKNOWN_MEMBER",
    "collect",
]
