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

"""Builtin metadata lookup and pine-facade catalog list (no download)."""

from __future__ import annotations

from typing import Any

from pynescript.mcp.serialize import fail
from pynescript.mcp.serialize import ok


def lookup_builtin(name: str) -> dict[str, Any]:
    """Return one builtin from ``builtin_metadata.json``."""
    from pynescript.langserver.providers.builtin_metadata import get_builtin

    path = (name or "").strip()
    if not path:
        return fail("name is required", kind="io")
    info = get_builtin(path)
    if info is None:
        alt = path if "." in path else f"ta.{path}"
        info = get_builtin(alt)
        path = alt if info is not None else path
    if info is None:
        return fail(f"unknown builtin: {name}", kind="io")
    return ok(
        name=path,
        label=info.get("label"),
        kind=info.get("kind"),
        detail=info.get("detail"),
        brief=info.get("brief"),
        documentation=info.get("documentation"),
        snippet=info.get("snippet"),
        category=info.get("category"),
    )


def list_builtins(*, category: str | None = None, limit: int = 200) -> dict[str, Any]:
    """Compact catalog: name + detail (+ category)."""
    from pynescript.langserver.providers.builtin_metadata import get_metadata

    meta = get_metadata()
    items: list[dict[str, Any]] = []
    for name, info in meta.items():
        if category and info.get("category") != category:
            continue
        items.append(
            {
                "name": name,
                "detail": info.get("detail") or info.get("label") or name,
                "category": info.get("category"),
                "brief": info.get("brief") or "",
            }
        )
        if len(items) >= max(1, min(limit, 5000)):
            break
    return ok(count=len(items), builtins=items)


def list_facade_templates(*, limit: int | None = None) -> dict[str, Any]:
    """List TradingView pine-facade builtin templates (network). Does not download."""
    try:
        from pynescript.util.pine_facade import _meta_name
        from pynescript.util.pine_facade import list_builtin_scripts
    except ImportError:
        return fail(
            "TradingView builtin download was removed from this package.",
            kind="unsupported",
        )

    try:
        catalog = list_builtin_scripts()
    except Exception as exc:
        return fail(f"{type(exc).__name__}: {exc}", kind="network")
    if not isinstance(catalog, list):
        return fail("unexpected facade catalog shape", kind="network")
    rows: list[dict[str, Any]] = []
    for meta in catalog:
        if not isinstance(meta, dict):
            continue
        rows.append(
            {
                "name": _meta_name(meta),
                "id": str(meta.get("scriptIdPart") or meta.get("scriptId") or ""),
                "kind": str(meta.get("extraKind") or meta.get("kind") or ""),
                "version": str(meta.get("version") or ""),
            }
        )
        if limit is not None and len(rows) >= max(1, limit):
            break
    return ok(count=len(rows), templates=rows, listed=len(catalog))
