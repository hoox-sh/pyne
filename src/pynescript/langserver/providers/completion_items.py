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

"""Completion items — build LSP lists from builtin metadata.

Public builders used by :mod:`pynescript.langserver.features.completion`:

- :func:`build_completion_list` — filtered builtins (optional category headers)
- :func:`build_completion_item` — one :class:`~lsprotocol.types.CompletionItem`
- :func:`build_module_completion` — members of a module prefix (e.g. ``ta``)
- :func:`build_keyword_items` / :func:`collect_user_enums` — keywords and user enums

Metadata comes from :mod:`pynescript.langserver.providers.builtin_metadata`.
"""

from __future__ import annotations

import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.langserver.providers.builtin_metadata import fuzzy_filter
from pynescript.langserver.providers.builtin_metadata import get_all_categories
from pynescript.langserver.providers.builtin_metadata import get_metadata


# Soft keywords and structural keywords not present in builtin metadata.
# Lexer treats type/method/enum/as/by/to/const as identifiers outside keyword position.
PINE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("and", "Logical AND; both operands must be true."),
    ("as", "Import alias or type cast."),
    ("break", "Exit the innermost loop."),
    ("by", "Step of a counted `for` loop (`for i = 0 to n by 2`)."),
    ("const", "Qualify a declaration as a compile-time constant."),
    ("continue", "Skip to the next loop iteration."),
    ("else", "Alternative branch of an `if` or `switch`."),
    ("enum", "Declare a user-defined enum."),
    ("export", "Export a library member for use by other scripts."),
    ("false", "Boolean false."),
    ("for", "Counted `for` loop or `for ... in` over a collection."),
    ("if", "Conditional branch; optional `else`."),
    ("import", "Import a library."),
    ("in", "Iterate a collection in a `for ... in` loop."),
    ("method", "Declare a method on a user-defined type."),
    ("not", "Logical NOT."),
    ("once", "Run a block the first time its condition is true on a closed bar."),
    ("or", "Logical OR; true if either operand is true."),
    ("switch", "Multi-way `switch` expression."),
    ("to", "End bound of a counted `for` loop."),
    ("true", "Boolean true."),
    ("type", "Declare a user-defined type."),
    ("var", "Persistent variable; initialized once and kept across bars."),
    ("varip", "Intrabar-persistent variable; updates on every tick."),
    ("while", "Loop while a condition is true."),
)


def build_completion_list(prefix: str = "", include_categories: bool = True) -> lsp.CompletionList:
    """Build a completion list for Pine Script.

    Args:
        prefix: Optional prefix to filter by (e.g., "ta.").
        include_categories: Include category headers in completion list.

    Returns:
        LSP CompletionList with completion items.
    """
    metadata = get_metadata()
    items = list(metadata.values())

    # Filter by prefix
    if prefix:
        if prefix.endswith("."):
            # Module completion (e.g., "ta.")
            items = [i for i in items if i.get("label", "").startswith(prefix)]
        else:
            # Fuzzy filter
            items = fuzzy_filter(prefix, items)

    # Sort alphabetically
    items.sort(key=lambda x: x.get("label", ""))

    completion_items = []
    seen_labels = set()

    # Group by category if including headers
    if include_categories:
        categories = get_all_categories()
        for category in categories:
            category_items = [i for i in items if i.get("category") == category]
            if not category_items:
                continue

            # Add category header
            header = _build_category_header(category, len(category_items))
            completion_items.append(header)

            # Add items in this category
            for item in category_items:
                if item["label"] not in seen_labels:
                    completion_items.append(build_completion_item(item))
                    seen_labels.add(item["label"])
    else:
        for item in items:
            if item["label"] not in seen_labels:
                completion_items.append(build_completion_item(item))
                seen_labels.add(item["label"])

    return lsp.CompletionList(
        is_incomplete=False,
        items=completion_items,
    )


def build_completion_item(info: dict, *, insert_leaf: bool = False) -> lsp.CompletionItem:
    """Build a single CompletionItem from metadata.

    Args:
        info: Metadata dict from builtin_metadata.
        insert_leaf: When True, insert only the name after the last ``.``
            (used after a module trigger so ``ta.`` + ``sma`` does not become
            ``ta.ta.sma``).

    Returns:
        LSP CompletionItem.
    """
    label = info.get("label", "")
    detail = info.get("detail", "")
    brief = info.get("brief", "")
    snippet = info.get("snippet", info.get("detail", ""))
    documentation = info.get("documentation", brief)

    # Determine insert text format
    if "${" in snippet:
        insert_text_format = lsp.InsertTextFormat.Snippet
        insert_text = snippet
    else:
        insert_text_format = lsp.InsertTextFormat.PlainText
        insert_text = label

    if insert_leaf and "." in label:
        leaf = label.rsplit(".", 1)[-1]
        if insert_text.startswith(label):
            insert_text = leaf + insert_text[len(label) :]
        elif "." in insert_text:
            insert_text = insert_text.rsplit(".", 1)[-1]

    return lsp.CompletionItem(
        label=label,
        kind=lsp.CompletionItemKind.Function,
        detail=detail,
        documentation=lsp.MarkupContent(kind=lsp.MarkupKind.Markdown, value=documentation),
        insert_text=insert_text,
        insert_text_format=insert_text_format,
        filter_text=" ".join(label.split(".")) + " " + brief,
        sort_text=_sort_text(label),
    )


def build_module_completion(module: str, member_prefix: str = "") -> lsp.CompletionList:
    """Build completions for a specific module.

    Args:
        module: The module name (e.g., "ta", "strategy").
        member_prefix: Optional filter on the member name after the last ``.``.

    Returns:
        CompletionList with completions for that module.
    """
    all_metadata = get_metadata()
    prefix = module + "."
    needle = member_prefix.lower()

    items = []
    for name, info in all_metadata.items():
        if not name.startswith(prefix):
            continue
        leaf = name[len(prefix) :]
        if needle and not leaf.lower().startswith(needle):
            continue
        items.append(info)

    items.sort(key=lambda x: (_module_item_rank(x.get("label", "")), x.get("label", "")))

    completion_items = []
    for info in items:
        completion_items.append(build_completion_item(info, insert_leaf=True))

    return lsp.CompletionList(
        is_incomplete=False,
        items=completion_items,
    )


def build_keyword_items(prefix: str = "") -> list[lsp.CompletionItem]:
    """Completion items for Pine keywords missing from builtin metadata."""
    needle = prefix.lower()
    items: list[lsp.CompletionItem] = []
    for name, brief in PINE_KEYWORDS:
        if needle and not name.startswith(needle):
            continue
        items.append(
            lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Keyword,
                detail=name,
                documentation=lsp.MarkupContent(kind=lsp.MarkupKind.Markdown, value=brief),
                insert_text=name,
                insert_text_format=lsp.InsertTextFormat.PlainText,
                filter_text=name,
                sort_text="\x00" + name,
            )
        )
    return items


_ENUM_HEADER = re.compile(r"^[ \t]*(?:export[ \t]+)?enum[ \t]+([A-Za-z_][A-Za-z0-9_]*)")
_ENUM_MEMBER = re.compile(r"^[ \t]+([A-Za-z_][A-Za-z0-9_]*)(?:[ \t]*=[ \t]*([^\n \t]+?))?[ \t]*$")


def collect_user_enums(tree: Any, source: str | None = None) -> dict[str, dict[str, Any]]:
    """Map user enum name → ``{name, members, lineno, col_offset, export}``.

    Prefers the AST when available. Falls back to a line scan of *source* so
    mid-edit buffers (``s = Side.``) still complete members.
    """
    result = _collect_user_enums_from_tree(tree)
    if result or not source:
        return result
    return _collect_user_enums_from_source(source)


def _collect_user_enums_from_tree(tree: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if tree is None:
        return result

    for stmt in getattr(tree, "body", None) or []:
        if not isinstance(stmt, ast.EnumDef):
            continue
        name = getattr(stmt, "name", None)
        if not name:
            continue
        members: list[dict[str, Any]] = []
        for item in getattr(stmt, "body", None) or []:
            target = getattr(item, "target", None)
            mid = getattr(target, "id", None) if target is not None else None
            if not mid:
                continue
            value = getattr(item, "value", None)
            lit = getattr(value, "value", None) if value is not None else None
            members.append(
                {
                    "name": mid,
                    "value": lit,
                    "lineno": getattr(target, "lineno", None) or getattr(item, "lineno", 1) or 1,
                    "col_offset": getattr(target, "col_offset", 0) or 0,
                }
            )
        result[name] = {
            "name": name,
            "members": members,
            "lineno": getattr(stmt, "lineno", 1) or 1,
            "col_offset": getattr(stmt, "col_offset", 0) or 0,
            "export": bool(getattr(stmt, "export", 0)),
        }
    return result


def _collect_user_enums_from_source(source: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    lines = source.split("\n")
    i = 0
    while i < len(lines):
        header = _ENUM_HEADER.match(lines[i])
        if not header:
            i += 1
            continue
        name = header.group(1)
        header_line = i + 1
        export = lines[i].lstrip().startswith("export")
        members: list[dict[str, Any]] = []
        i += 1
        while i < len(lines):
            raw = lines[i]
            if not raw.strip():
                i += 1
                continue
            mem = _ENUM_MEMBER.match(raw)
            if not mem:
                break
            lit = mem.group(2)
            if lit is not None:
                lit = lit.strip().strip("'\"")
            members.append(
                {
                    "name": mem.group(1),
                    "value": lit,
                    "lineno": i + 1,
                    "col_offset": len(raw) - len(raw.lstrip()),
                }
            )
            i += 1
        result[name] = {
            "name": name,
            "members": members,
            "lineno": header_line,
            "col_offset": 0,
            "export": export,
        }
    return result


def build_enum_name_items(enums: dict[str, dict[str, Any]], prefix: str = "") -> list[lsp.CompletionItem]:
    """Completion items for user-defined enum type names."""
    needle = prefix.lower()
    items: list[lsp.CompletionItem] = []
    for name, info in sorted(enums.items()):
        if needle and not name.lower().startswith(needle):
            continue
        member_names = ", ".join(m["name"] for m in info.get("members", []))
        items.append(
            lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.Enum,
                detail=f"enum {name}",
                documentation=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"User-defined enum.{f' Members: {member_names}' if member_names else ''}",
                ),
                insert_text=name,
                insert_text_format=lsp.InsertTextFormat.PlainText,
                filter_text=name,
                sort_text="\x00" + name,
            )
        )
    return items


def build_enum_member_completion(
    enum_info: dict[str, Any],
    member_prefix: str = "",
) -> lsp.CompletionList:
    """Member completions for a user enum (insert leaf name only)."""
    needle = member_prefix.lower()
    enum_name = enum_info.get("name", "")
    items: list[lsp.CompletionItem] = []
    for member in enum_info.get("members", []):
        name = member.get("name", "")
        if not name:
            continue
        if needle and not name.lower().startswith(needle):
            continue
        value = member.get("value")
        detail = f"{enum_name}.{name}"
        if value is not None:
            detail = f"{detail} = {value!r}"
        items.append(
            lsp.CompletionItem(
                label=f"{enum_name}.{name}",
                kind=lsp.CompletionItemKind.EnumMember,
                detail=detail,
                documentation=lsp.MarkupContent(
                    kind=lsp.MarkupKind.Markdown,
                    value=f"Member of user enum `{enum_name}`.",
                ),
                insert_text=name,
                insert_text_format=lsp.InsertTextFormat.PlainText,
                filter_text=name,
                sort_text=name,
            )
        )
    return lsp.CompletionList(is_incomplete=False, items=items)


def _build_category_header(category: str, count: int) -> lsp.CompletionItem:
    """Build a category header completion item.

    Args:
        category: The category name.
        count: Number of items in the category.

    Returns:
        CompletionItem that acts as a header.
    """
    # Pretty-print category name
    display_name = _format_category_name(category)

    return lsp.CompletionItem(
        label=f"--- {display_name} ({count}) ---",
        kind=lsp.CompletionItemKind.Folder,
        insert_text="",
        sort_text="\x00" + category,  # Sort headers first
    )


def _format_category_name(category: str) -> str:
    """Format a category name for display."""
    if category == "ta.technical_analysis":
        return "Technical Analysis (ta.*)"
    if category == "builtin":
        return "Built-in Variables"
    return category.title().replace("_", " ").replace(".", " / ")


def _build_see_also(name: str) -> str:
    """Build 'See also' section for documentation."""
    related = _get_related_functions(name)
    if not related:
        return ""
    return "**See also:** " + ", ".join(f"`{r}`" for r in related)


def _get_related_functions(name: str) -> list[str]:
    """Get related functions for cross-referencing."""
    related_map = {
        "ta.sma": ["ta.ema", "ta.rma", "ta.wma", "ta.vwma"],
        "ta.ema": ["ta.sma", "ta.rma", "ta.wma", "ta.vwma"],
        "ta.rsi": ["ta.stoch", "ta.mfi", "ta.cci"],
        "ta.macd": ["ta.rsi", "ta.stoch", "ta.bb"],
        "ta.bb": ["ta.macd", "ta.kc", "ta.env"],
        "ta.atr": ["ta.tr", "ta.rma"],
        "strategy.entry": ["strategy.exit", "strategy.order"],
        "strategy.long": ["strategy.short", "strategy.close"],
    }
    return related_map.get(name, [])


# Frequent module members — keep these near the top of `ta.` / `strategy.` lists
# so HTTP/editor caps (e.g. 120 items) still include them.
_PINNED_LEAVES = frozenset(
    {
        "sma",
        "ema",
        "rsi",
        "macd",
        "atr",
        "bb",
        "stoch",
        "vwap",
        "wma",
        "rma",
        "entry",
        "exit",
        "close",
        "long",
        "short",
    }
)


def _module_item_rank(label: str) -> int:
    leaf = label.rsplit(".", 1)[-1]
    return 0 if leaf in _PINNED_LEAVES else 1


def _sort_text(label: str) -> str:
    """Generate sort text for a completion item.

    Modules come first (ta., strategy., etc.), then alphabetically.
    """
    parts = label.split(".")
    if len(parts) == 1:
        return "\x02" + label  # Root functions second
    return "\x01" + label  # Module functions first
