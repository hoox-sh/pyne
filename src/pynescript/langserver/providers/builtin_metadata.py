# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Builtin metadata provider.

Loads and serves builtin function metadata for LSP features.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_metadata: dict[str, Any] | None = None


def get_metadata() -> dict[str, Any]:
    """Get the builtin metadata dictionary.

    Loads from JSON on first call, then caches in memory.
    Supports encrypted metadata (for compiled binary) and plaintext (for development).

    Returns:
        Dictionary mapping builtin names to metadata.
    """
    global _metadata

    if _metadata is None:
        providers_dir = Path(__file__).parent
        plain_path = providers_dir / "builtin_metadata.json"
        enc_path = providers_dir / "builtin_metadata.json.enc"

        if enc_path.exists():
            try:
                from pynescript.langserver.providers.metadata_decrypt import get_metadata_cached

                _metadata = get_metadata_cached()
            except Exception:
                _metadata = {}
        elif plain_path.exists():
            with open(plain_path, "r", encoding="utf-8") as f:
                _metadata = json.load(f)
        else:
            _metadata = {}

    return _metadata


def get_builtin(name: str) -> dict[str, Any] | None:
    """Get metadata for a specific builtin.

    Args:
        name: The builtin name (e.g., "ta.sma").

    Returns:
        Metadata dict or None if not found.
    """
    metadata = get_metadata()
    return metadata.get(name)


def get_builtins_by_category(category: str) -> list[dict[str, Any]]:
    """Get all builtins in a category.

    Args:
        category: The category name.

    Returns:
        List of metadata dicts.
    """
    metadata = get_metadata()
    return [info for info in metadata.values() if info.get("category") == category]


def get_all_categories() -> list[str]:
    """Get all unique categories.

    Returns:
        Sorted list of category names.
    """
    metadata = get_metadata()
    categories = {info.get("category") for info in metadata.values()}
    return sorted(categories)


def fuzzy_filter(query: str, items: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    """Filter items by fuzzy match on label.

    Args:
        query: The search query.
        items: List of metadata dicts.
        limit: Maximum number of results.

    Returns:
        Filtered list of items.
    """
    if not query:
        return items[:limit]

    query_lower = query.lower()
    results = []

    for item in items:
        label = item.get("label", "").lower()
        category = item.get("category", "").lower()
        brief = item.get("brief", "").lower()

        # Check for substring matches
        score = 0
        if label == query_lower:
            score = 1000
        elif label.startswith(query_lower):
            score = 500
        elif query_lower in label:
            score = 100
        elif query_lower in category:
            score = 50
        elif query_lower in brief:
            score = 25

        if score > 0:
            results.append((score, item))

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:limit]]
