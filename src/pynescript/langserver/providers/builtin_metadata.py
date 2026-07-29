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

"""Builtin metadata provider.

Loads and serves builtin function metadata for LSP features.
"""

from __future__ import annotations

import json
import logging

from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class _MetadataCache:
    """Process-local metadata cache (avoids module-level ``global``)."""

    data: dict[str, Any] | None = None


def reset_metadata_cache() -> None:
    """Drop the in-process cache (tests / after regenerating JSON)."""
    _MetadataCache.data = None


def get_metadata() -> dict[str, Any]:
    """Get the builtin metadata dictionary.

    Load order:
    1. Plaintext ``builtin_metadata.json`` (dev / wheel install)
    2. Encrypted blob (Nuitka binary) via :mod:`metadata_decrypt`

    Returns:
        Dictionary mapping builtin names to metadata.
    """
    if _MetadataCache.data is None:
        providers_dir = Path(__file__).parent
        plain_path = providers_dir / "builtin_metadata.json"
        enc_path = providers_dir / "builtin_metadata.json.enc"

        loaded: dict[str, Any] | None = None

        # Prefer plaintext when present so regenerating JSON always wins in dev.
        if plain_path.exists():
            try:
                with open(plain_path, encoding="utf-8") as f:
                    loaded = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load plaintext builtin metadata: %s", exc)

        if loaded is None and enc_path.exists():
            try:
                # Lazy: only needed for Nuitka binary path
                from pynescript.langserver.providers import metadata_decrypt  # noqa: PLC0415

                loaded = metadata_decrypt.load_encrypted_metadata()
            except Exception as exc:
                logger.warning("Failed to decrypt builtin metadata: %s", exc)

        _MetadataCache.data = loaded if isinstance(loaded, dict) else {}

    return _MetadataCache.data


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
    return sorted(c for c in categories if c is not None)


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

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results[:limit]]
