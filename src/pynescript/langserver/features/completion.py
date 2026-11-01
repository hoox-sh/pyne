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

"""Completion — ``textDocument/completion`` and ``completionItem/resolve``.

Public handlers:

- :func:`handle_completion` — scope-aware user symbols, ``.``-triggered
  builtins / UDT members / enum members / type constructors, keywords, and
  filtered builtin metadata
- :func:`handle_completion_resolve` — fill documentation for a completion item

User symbols come from :mod:`pynescript.langserver.analysis`; builtin items
come from :mod:`pynescript.langserver.providers.builtin_metadata` and
:mod:`pynescript.langserver.providers.completion_items`.
"""

from __future__ import annotations

import logging

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.langserver.analysis import BUILTIN_NAMESPACES
from pynescript.langserver.analysis import BUILTIN_VAR_TYPES
from pynescript.langserver.analysis import Symbol
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import build_symbol_index
from pynescript.langserver.protocol.utils import get_trigger_char
from pynescript.langserver.protocol.utils import in_comment_or_string
from pynescript.langserver.protocol.utils import trailing_ident
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.providers.completion_items import build_completion_item
from pynescript.langserver.providers.completion_items import build_completion_list
from pynescript.langserver.providers.completion_items import build_enum_member_completion
from pynescript.langserver.providers.completion_items import build_enum_name_items
from pynescript.langserver.providers.completion_items import build_keyword_items
from pynescript.langserver.providers.completion_items import build_module_completion
from pynescript.langserver.providers.completion_items import collect_user_enums


logger = logging.getLogger(__name__)

_EMPTY = lsp.CompletionList(is_incomplete=False, items=[])

_SYMBOL_KINDS: dict[str, lsp.CompletionItemKind] = {
    "variable": lsp.CompletionItemKind.Variable,
    "function": lsp.CompletionItemKind.Function,
    "method": lsp.CompletionItemKind.Method,
    "type": lsp.CompletionItemKind.Class,
    "enum": lsp.CompletionItemKind.Enum,
    "enum_member": lsp.CompletionItemKind.EnumMember,
    "field": lsp.CompletionItemKind.Field,
    "param": lsp.CompletionItemKind.Variable,
    "import": lsp.CompletionItemKind.Module,
}


def handle_completion(
    params: lsp.CompletionParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
    snippets: bool = True,
) -> lsp.CompletionList:
    """Return a completion list for the cursor position in *source*.

    Dot-prefix paths complete module members, user-enum members, UDT
    fields/methods, and type constructors; otherwise the list contains user
    symbols visible in the current scope, keywords, user enums, and filtered
    builtins.

    Args:
        params: Client ``CompletionParams`` (position / context).
        source: Document text, or ``None`` if unknown.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source*.
        analysis: Pre-built symbol index for *tree* (workspace cache). When
            omitted, one is built from *tree*/*source*.
        snippets: Emit snippet placeholders for builtins/functions.

    Returns:
        Always a :class:`~lsprotocol.types.CompletionList` (may be empty).
    """
    if not source:
        return _EMPTY

    position = params.position
    line = position.line
    character = position.character
    if in_comment_or_string(source, line, character):
        return _EMPTY

    lines = source.split("\n")
    text_before_cursor = lines[line][:character] if 0 <= line < len(lines) else ""
    prefix = trailing_ident(text_before_cursor)
    index = _resolve_analysis(source, tree, analysis)
    scope = index.scope_at(line, character) if index is not None else None

    if "." in prefix:
        module, _sep, member_prefix = prefix.rpartition(".")
        if not module:
            return _EMPTY
        if index is None:
            # Mid-edit buffers (e.g. ``s = Side.``) do not parse; fall back to
            # the source-scan enum collector so member completion still works.
            fallback_enums = collect_user_enums(None, source)
            if module in fallback_enums:
                return build_enum_member_completion(fallback_enums[module], member_prefix=member_prefix)
        return _module_completion(module, member_prefix, index, scope=scope, snippets=snippets)

    # A trigger character can fire before the dot is present in the prefix.
    if get_trigger_char(source, line, character) == "." and prefix:
        return _module_completion(prefix, "", index, scope=scope, snippets=snippets)

    items: list[lsp.CompletionItem] = []
    if index is not None and scope is not None:
        items.extend(_user_items(index, scope, prefix, snippets=snippets))

    enums = _enum_infos(index, source, tree)
    items.extend(build_keyword_items(prefix))
    items.extend(build_enum_name_items(enums, prefix))
    items.extend(_builtin_variable_items(prefix))
    builtin = build_completion_list(prefix=prefix, snippets=snippets)
    items.extend(builtin.items)

    # Stable de-dupe by label; user items win because they were added first.
    seen: set[str] = set()
    unique: list[lsp.CompletionItem] = []
    for item in items:
        if item.label in seen:
            continue
        seen.add(item.label)
        unique.append(item)
    return lsp.CompletionList(is_incomplete=False, items=unique)


def _resolve_analysis(
    source: str | None,
    tree: Any | None,
    analysis: SymbolIndex | None,
) -> SymbolIndex | None:
    if analysis is not None:
        return analysis
    if not source:
        return None
    if tree is ...:
        try:
            tree = parse_source(source)
        except Exception:
            tree = None
    if tree is None:
        # Mid-edit buffers commonly end in ``.`` / an unclosed call. Parse a
        # minimally repaired copy so completion can still resolve receivers and
        # scopes; positions before the cursor are unchanged.
        tree = _parse_best_effort(source)
        if tree is None:
            return None
    try:
        return build_symbol_index(tree, source)
    except Exception:
        return None


def _parse_best_effort(source: str) -> Any | None:
    """Parse *source*, trying cheap repairs for common mid-edit endings."""
    candidates = [source]
    trimmed = source.rstrip()
    if trimmed.endswith("."):
        candidates.extend([trimmed + "x", trimmed + "x)"])
    elif trimmed.endswith(("(", ",", "[")):
        candidates.extend([trimmed + "x)", trimmed + "0)"])
    candidates.append(trimmed + "\n")
    for candidate in candidates:
        try:
            return parse_source(candidate)
        except Exception as exc:
            logger.debug("completion: repair parse failed: %s", exc)
    return None


def parse_source(source: str) -> Any:
    """Parse *source* for standalone handler use (tests / non-workspace callers)."""
    from pynescript.ast.helper import parse

    return parse(source)


def _enum_infos(index: SymbolIndex | None, source: str | None, tree: Any | None) -> dict[str, dict[str, Any]]:
    """Enum metadata for keyword/name completion (analysis-backed when possible)."""
    if index is not None and index.enums:
        return {
            name: {
                "name": name,
                "members": [{"name": member.name, "value": None} for member in index.enum_member_symbols(name)],
                "lineno": 1,
                "col_offset": 0,
                "export": bool(symbol.export),
            }
            for name, symbol in index.enums.items()
        }
    resolved = tree if tree is not ... else None
    return collect_user_enums(resolved, source)


def _module_completion(
    module: str,
    member_prefix: str,
    index: SymbolIndex | None,
    *,
    scope: Any = None,
    snippets: bool,
) -> lsp.CompletionList:
    """Complete members of a module, enum, UDT value, type, or builtin namespace."""
    if index is not None:
        enum_symbol = index.enums.get(module)
        if enum_symbol is not None:
            info = {
                "name": module,
                "members": [{"name": member.name, "value": None} for member in index.enum_member_symbols(module)],
            }
            return build_enum_member_completion(info, member_prefix=member_prefix)

        type_symbol = index.types.get(module)
        if type_symbol is not None:
            return lsp.CompletionList(
                is_incomplete=False,
                items=_type_constructor_items(type_symbol, snippets=snippets),
            )

        if module in index.imports:
            # Published Pine libraries are not local files; do not invent
            # members. A future workspace-library index can fill this in.
            return _EMPTY

        symbol = index.resolve(module, scope or index.script_scope)
        if symbol is not None:
            if symbol.kind == "enum":
                info = {
                    "name": symbol.name,
                    "members": [
                        {"name": member.name, "value": None}
                        for member in index.enum_member_symbols(symbol.name)
                    ],
                }
                return build_enum_member_completion(info, member_prefix=member_prefix)
            if symbol.type_label:
                members = index.member_candidates(symbol.type_label)
                if members:
                    return lsp.CompletionList(
                        is_incomplete=False,
                        items=_member_items(members, member_prefix, snippets=snippets),
                    )
            # A user object with unknown type: stay quiet rather than showing
            # unrelated builtins.
            if module not in BUILTIN_NAMESPACES and not module.startswith(tuple(f"{ns}." for ns in BUILTIN_NAMESPACES)):
                return _EMPTY

    if module in BUILTIN_NAMESPACES or module.split(".", 1)[0] in BUILTIN_NAMESPACES:
        return build_module_completion(module, member_prefix=member_prefix, snippets=snippets)
    return _EMPTY


def _user_items(
    index: SymbolIndex,
    scope: Any,
    prefix: str,
    *,
    snippets: bool,
) -> list[lsp.CompletionItem]:
    needle = prefix.lower()
    items: list[lsp.CompletionItem] = []
    for symbol in index.symbols_in_scope(scope):
        if symbol.kind in {"field", "enum_member"}:
            continue
        if needle and not symbol.name.lower().startswith(needle):
            continue
        items.append(_symbol_item(symbol, snippets=snippets))
    return items


def _builtin_variable_items(prefix: str) -> list[lsp.CompletionItem]:
    """Completion items for OHLCV/time/bar_index-style built-in variables."""
    needle = prefix.lower()
    items: list[lsp.CompletionItem] = []
    for name, type_label in BUILTIN_VAR_TYPES.items():
        if needle and not name.lower().startswith(needle):
            continue
        items.append(
            lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Variable,
                detail=type_label,
                documentation=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"Built-in variable (`{type_label}`).",
                ),
                insert_text=name,
                insert_text_format=lsp.InsertTextFormat.PlainText,
                filter_text=name,
                sort_text="\x01" + name,
            )
        )
    return items


def _symbol_item(symbol: Symbol, *, snippets: bool) -> lsp.CompletionItem:
    kind = _SYMBOL_KINDS.get(symbol.kind, lsp.CompletionItemKind.Variable)
    detail = symbol.signature or symbol.type_label or symbol.kind
    documentation = "\n\n".join(symbol.annotations) if symbol.annotations else f"User-defined {symbol.kind}."
    insert_text = symbol.name
    insert_format = lsp.InsertTextFormat.PlainText
    if symbol.kind in {"function", "method"} and isinstance(symbol.node, ast.FunctionDef):
        insert_text, insert_format = _function_insert(symbol.node, snippets=snippets)
    return lsp.CompletionItem(
        label=symbol.name,
        kind=kind,
        detail=detail,
        documentation=lsp.MarkupContent(kind=lsp.MarkupKind.Markdown, value=documentation),
        insert_text=insert_text,
        insert_text_format=insert_format,
        filter_text=symbol.name,
        sort_text="\x00" + symbol.name,
        data={"pynescriptUser": True},
    )


def _function_insert(node: ast.FunctionDef, *, snippets: bool) -> tuple[str, lsp.InsertTextFormat]:
    name = node.name or ""
    params = [param for param in (node.args or []) if getattr(param, "name", None)]
    if node.method and params:
        # Pine methods declare the receiver as the first parameter; call sites
        # pass it implicitly.
        params = params[1:]
    if not snippets or not params:
        return name, lsp.InsertTextFormat.PlainText
    placeholders = ", ".join(
        f"${{{index}:{getattr(param, 'name', 'arg')}}}" for index, param in enumerate(params, 1)
    )
    return f"{name}({placeholders})", lsp.InsertTextFormat.Snippet


def _type_constructor_items(symbol: Symbol, *, snippets: bool) -> list[lsp.CompletionItem]:
    node = symbol.node
    fields: list[str] = []
    if isinstance(node, ast.TypeDef):
        fields = [
            target.id
            for stmt in node.body
            if isinstance(stmt, ast.Assign)
            for target in ([stmt.target] if isinstance(stmt.target, ast.Name) else [])
            if target.id
        ]
    insert = "new("
    if snippets:
        insert = "new(" + ", ".join(f"${{{index}:{field}}}" for index, field in enumerate(fields, 1)) + ")"
    return [
        lsp.CompletionItem(
            label=f"{symbol.name}.new",
            kind=lsp.CompletionItemKind.Constructor,
            detail=f"{symbol.name}.new(...)",
            documentation=lsp.MarkupContent(
                kind=lsp.MarkupKind.Markdown,
                value=f"Create a new `{symbol.name}` value.",
            ),
            insert_text=insert,
            insert_text_format=lsp.InsertTextFormat.Snippet if snippets and fields else lsp.InsertTextFormat.PlainText,
            filter_text="new",
            sort_text="\x00new",
            data={"pynescriptUser": True},
        )
    ]


def _member_items(members: list[Symbol], prefix: str, *, snippets: bool) -> list[lsp.CompletionItem]:
    needle = prefix.lower()
    items: list[lsp.CompletionItem] = []
    for symbol in members:
        if needle and not symbol.name.lower().startswith(needle):
            continue
        if symbol.kind == "method" and isinstance(symbol.node, ast.FunctionDef):
            insert_text, insert_format = _function_insert(symbol.node, snippets=snippets)
            kind = lsp.CompletionItemKind.Method
        else:
            insert_text, insert_format = symbol.name, lsp.InsertTextFormat.PlainText
            kind = lsp.CompletionItemKind.Field
        items.append(
            lsp.CompletionItem(
                label=symbol.name,
                kind=kind,
                detail=symbol.signature or symbol.type_label or symbol.kind,
                documentation=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value="\n\n".join(symbol.annotations) if symbol.annotations else f"User-defined {symbol.kind}.",
                ),
                insert_text=insert_text,
                insert_text_format=insert_format,
                filter_text=symbol.name,
                sort_text=symbol.name,
                data={"pynescriptUser": True},
            )
        )
    return items


def handle_completion_resolve(
    params: lsp.CompletionItem,
) -> lsp.CompletionItem:
    """Handle completionItem/resolve request.

    Enriches a builtin completion item with full documentation without
    replacing leaf insert text (``ta.`` + ``sma(...)`` must not become
    ``ta.ta.sma``). User items already carry their documentation and are
    returned unchanged.
    """
    data = getattr(params, "data", None)
    if isinstance(data, dict) and data.get("pynescriptUser"):
        return params
    builtin_info = get_builtin(params.label)
    if not builtin_info:
        return params
    snippets = params.insert_text_format == lsp.InsertTextFormat.Snippet
    resolved = build_completion_item(builtin_info, snippets=snippets)
    insert_text = params.insert_text
    if not insert_text or insert_text == resolved.insert_text:
        return resolved
    return lsp.CompletionItem(
        label=resolved.label,
        kind=resolved.kind,
        detail=resolved.detail,
        documentation=resolved.documentation,
        insert_text=insert_text,
        insert_text_format=params.insert_text_format or resolved.insert_text_format,
        filter_text=resolved.filter_text,
        sort_text=resolved.sort_text,
    )
