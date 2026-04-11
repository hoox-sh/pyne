# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Completion items builder.

Builds LSP CompletionItem objects from builtin metadata.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.langserver.providers.builtin_metadata import (
    fuzzy_filter,
    get_all_categories,
    get_builtins_by_category,
    get_metadata,
    get_builtin,
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


def build_completion_item(info: dict) -> lsp.CompletionItem:
    """Build a single CompletionItem from metadata.

    Args:
        info: Metadata dict from builtin_metadata.

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


def build_module_completion(module: str) -> lsp.CompletionList:
    """Build completions for a specific module.

    Args:
        module: The module name (e.g., "ta", "strategy").

    Returns:
        CompletionList with completions for that module.
    """
    all_metadata = get_metadata()
    prefix = module + "."

    items = []
    for name, info in all_metadata.items():
        if name.startswith(prefix):
            items.append(info)

    items.sort(key=lambda x: x.get("label", ""))

    completion_items = []
    for info in items:
        completion_items.append(build_completion_item(info))

    return lsp.CompletionList(
        is_incomplete=False,
        items=completion_items,
    )


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


def _sort_text(label: str) -> str:
    """Generate sort text for a completion item.

    Modules come first (ta., strategy., etc.), then alphabetically.
    """
    parts = label.split(".")
    if len(parts) == 1:
        return "\x02" + label  # Root functions second
    return "\x01" + label  # Module functions first
