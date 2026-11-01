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

"""Semantic tokens — ``textDocument/semanticTokens/full`` and ``/range``.

Public handlers: :func:`handle_semantic_tokens`,
:func:`handle_semantic_tokens_range`. Walks the AST and emits an LSP
delta-encoded token stream (line, start, length, type, modifiers) for builtins,
user functions, types, and variables beyond TextMate alone. Range clips to
tokens whose start falls inside the requested LSP range.

**Contract:** token type indices must match
:func:`pynescript.langserver.config.semantic_token_types` (and modifiers
:func:`~pynescript.langserver.config.semantic_token_modifiers`). Legend is
advertised in :func:`~pynescript.langserver.config.get_server_capabilities`.
"""

from __future__ import annotations

from typing import Any

import lsprotocol.types as lsp

from pynescript.ast import helper as ast_helper
from pynescript.ast import node as ast
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.config import semantic_token_types


# Indices into semantic_token_types()
_TT = {name: i for i, name in enumerate(semantic_token_types())}

# Modifier bitmasks into semantic_token_modifiers()
_MOD_DECLARATION = 1 << 0
_MOD_DEFINITION = 1 << 1
_MOD_READONLY = 1 << 2
_MOD_DEFAULT_LIBRARY = 1 << 3

# Namespaces that are always library builtins when used as Attribute.value
_BUILTIN_NS = frozenset(
    {
        "ta",
        "math",
        "str",
        "array",
        "matrix",
        "map",
        "strategy",
        "request",
        "input",
        "color",
        "line",
        "label",
        "box",
        "table",
        "polyline",
        "log",
        "ticker",
        "timeframe",
        "chart",
        "runtime",
        "syminfo",
        "barstate",
        "session",
        "time",
    }
)


def handle_semantic_tokens(
    _params: lsp.SemanticTokensParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> lsp.SemanticTokens | None:
    """Return full-document semantic tokens for *source*.

    Args:
        _params: Client params (document URI unused; source is passed in).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse (skips a redundant re-parse).
            Omit (default ``...``) to parse from *source*.
        analysis: Pre-built symbol index for *tree* (user references/params).

    Returns:
        :class:`~lsprotocol.types.SemanticTokens` with encoded ``data``
        (empty list if source missing or parse fails).
    """
    return lsp.SemanticTokens(data=_encode(_collect_tokens(source, tree, analysis)))


def handle_semantic_tokens_range(
    params: lsp.SemanticTokensRangeParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> lsp.SemanticTokens | None:
    """Return semantic tokens whose start falls inside *params.range*.

    Inclusive start, exclusive end (typical LSP). Empty source, unparsed
    documents, or ``tree=None`` yield an empty ``data`` array.

    Args:
        params: Client range params (document URI unused; source is passed in).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse (skips a redundant re-parse).
            Omit (default ``...``) to parse from *source*.
        analysis: Pre-built symbol index for *tree*.

    Returns:
        :class:`~lsprotocol.types.SemanticTokens` with encoded ``data``
        (empty list if source missing, parse fails, or no tokens in range).
    """
    raw = _collect_tokens(source, tree, analysis)
    clipped = [t for t in raw if _start_in_range(t[0], t[1], params.range)]
    return lsp.SemanticTokens(data=_encode(clipped))


def _collect_tokens(
    source: str | None,
    tree: Any | None,
    analysis: SymbolIndex | None = None,
) -> list[tuple[int, int, int, int, int]]:
    if tree is ...:
        if not source:
            return []
        try:
            tree = ast_helper.parse(source)
        except Exception:
            return []
    if tree is None:
        return []

    raw: list[tuple[int, int, int, int, int]] = []
    index = ensure_symbol_index(source, tree, analysis)
    if index is not None:
        _collect_from_index(index, raw)
        # Builtin namespace/member tokens are not user symbols; keep the AST
        # attribute pass for those.
        _collect_builtin_attrs(tree, raw)
    else:
        _collect(tree, raw)
    raw.sort(key=lambda t: (t[0], t[1], -t[4]))
    return _dedupe(raw)


def _dedupe(
    tokens: list[tuple[int, int, int, int, int]],
) -> list[tuple[int, int, int, int, int]]:
    """Drop duplicate ranges; keep the declaration-richest token."""
    seen: dict[tuple[int, int, int], tuple[int, int, int, int, int]] = {}
    for token in tokens:
        key = (token[0], token[1], token[2])
        existing = seen.get(key)
        if existing is None or token[4] > existing[4]:
            seen[key] = token
    return sorted(seen.values(), key=lambda t: (t[0], t[1]))


def _collect_from_index(index: SymbolIndex, out: list[tuple[int, int, int, int, int]]) -> None:
    """Emit declaration/reference tokens from the static symbol index."""
    for occurrence in index.occurrences:
        symbol = occurrence.symbol
        if symbol is None:
            continue
        token_type = _TOKEN_TYPE_BY_KIND.get(symbol.kind)
        if token_type is None:
            continue
        mods = 0
        is_declaration = occurrence.write and occurrence.node is symbol.name_node
        if is_declaration:
            mods |= _MOD_DECLARATION
            if symbol.kind in {"function", "method", "type", "enum"}:
                mods |= _MOD_DEFINITION
        out.append(
            (
                occurrence.line,
                occurrence.column,
                max(1, occurrence.end_column - occurrence.column),
                _TT[token_type],
                mods,
            )
        )


_TOKEN_TYPE_BY_KIND: dict[str, str] = {
    "variable": "variable",
    "function": "function",
    "method": "method",
    "type": "class",
    "enum": "type",
    "enum_member": "property",
    "field": "property",
    "param": "parameter",
    "import": "namespace",
}


def _collect_builtin_attrs(tree: Any, out: list[tuple[int, int, int, int, int]]) -> None:
    """Emit namespace/method tokens for builtin ``ta.sma``-style attributes."""
    for node in ast_helper.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        value = getattr(node, "value", None)
        attr = getattr(node, "attr", None)
        if isinstance(value, ast.Name) and value.id in _BUILTIN_NS and isinstance(attr, str):
            _emit_name(value, value.id, _TT["namespace"], _MOD_DEFAULT_LIBRARY | _MOD_READONLY, out)
            _emit_attr(node, attr, _TT["method"], _MOD_DEFAULT_LIBRARY, out)


def _start_in_range(line: int, col: int, rng: lsp.Range) -> bool:
    """True if token start (line, col) is in *rng* (inclusive start, exclusive end)."""
    start = rng.start
    end = rng.end
    if (line, col) < (start.line, start.character):
        return False
    if (line, col) >= (end.line, end.character):
        return False
    return True


def _collect(node: Any, out: list[tuple[int, int, int, int, int]]) -> None:
    if node is None:
        return

    _emit_for_node(node, out)

    for child in _iter_children(node):
        _collect(child, out)


def _emit_for_node(node: Any, out: list[tuple[int, int, int, int, int]]) -> None:
    if isinstance(node, ast.FunctionDef):
        _emit_name(node, getattr(node, "name", None), _TT["function"], _MOD_DEFINITION | _MOD_DECLARATION, out)
        return
    if isinstance(node, ast.TypeDef):
        _emit_name(node, getattr(node, "name", None), _TT["class"], _MOD_DEFINITION | _MOD_DECLARATION, out)
        return
    if isinstance(node, ast.EnumDef):
        _emit_name(node, getattr(node, "name", None), _TT["type"], _MOD_DEFINITION | _MOD_DECLARATION, out)
        return
    if isinstance(node, ast.Assign):
        target = getattr(node, "target", None)
        if isinstance(target, ast.Name):
            _emit_name(target, target.id, _TT["variable"], _MOD_DECLARATION, out)
        return
    if isinstance(node, ast.Attribute):
        value = getattr(node, "value", None)
        attr = getattr(node, "attr", None)
        if isinstance(value, ast.Name) and value.id in _BUILTIN_NS and isinstance(attr, str):
            _emit_name(value, value.id, _TT["namespace"], _MOD_DEFAULT_LIBRARY | _MOD_READONLY, out)
            _emit_attr(node, attr, _TT["method"], _MOD_DEFAULT_LIBRARY, out)
        elif isinstance(attr, str):
            _emit_attr(node, attr, _TT["property"], 0, out)


def _iter_children(node: Any) -> list[Any]:
    children: list[Any] = []
    for field in getattr(node, "_fields", ()) or ():
        value = getattr(node, field, None)
        if value is None:
            continue
        if isinstance(value, list):
            children.extend(v for v in value if v is not None and hasattr(v, "_fields"))
        elif hasattr(value, "_fields"):
            children.append(value)
    return children


def _emit_name(
    node: Any,
    name: str | None,
    token_type: int,
    mods: int,
    out: list[tuple[int, int, int, int, int]],
) -> None:
    if not name:
        return
    line = max(0, int(getattr(node, "lineno", 1) or 1) - 1)
    col = max(0, int(getattr(node, "col_offset", 0) or 0))
    out.append((line, col, len(name), token_type, mods))


def _emit_attr(
    node: Any,
    attr: str,
    token_type: int,
    mods: int,
    out: list[tuple[int, int, int, int, int]],
) -> None:
    """Emit token for attribute name; col is approximate from end of Attribute node."""
    line = max(0, int(getattr(node, "lineno", 1) or 1) - 1)
    # Prefer end_col_offset of the attribute if present; else parent col + rough offset
    end_col = getattr(node, "end_col_offset", None)
    if isinstance(end_col, int) and end_col >= len(attr):
        col = end_col - len(attr)
    else:
        col = max(0, int(getattr(node, "col_offset", 0) or 0))
    out.append((line, col, len(attr), token_type, mods))


def _encode(tokens: list[tuple[int, int, int, int, int]]) -> list[int]:
    data: list[int] = []
    prev_line = 0
    prev_col = 0
    for line, col, length, ttype, mods in tokens:
        d_line = line - prev_line
        d_col = col - prev_col if d_line == 0 else col
        data.extend([d_line, d_col, length, ttype, mods])
        prev_line = line
        prev_col = col
    return data
