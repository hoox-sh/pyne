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

"""Compact, typed view of the PYNE MCP capability surface.

``search`` receives this array and filters it. Descriptions, defaults, and
choices stay behind ``execute`` + ``pyne.describe``; keeping the injected array
small is the whole point of Code Mode.
"""

from __future__ import annotations

import inspect

from dataclasses import dataclass
from typing import Any

from pynescript.mcp.catalog import TOOL_GROUP
from pynescript.mcp.catalog import TOOL_NAMES
from pynescript.mcp.catalog import TOOL_RISK
from pynescript.mcp.dispatch import resolve_tool_name


@dataclass(frozen=True)
class CatalogEntry:
    """One compact catalog row."""

    tool: str
    short: str
    group: str
    risk: str
    destructive: bool
    summary: str
    args: tuple[str, ...]
    required: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "short": self.short,
            "group": self.group,
            "risk": self.risk,
            "destructive": self.destructive,
            "summary": self.summary,
            "args": list(self.args),
            "required": list(self.required),
        }


def _server_function(name: str) -> Any:
    from pynescript.mcp import server as mcp_server

    fn = getattr(mcp_server, name, None)
    if not callable(fn):
        msg = f"MCP catalog tool missing on server: {name}"
        raise RuntimeError(msg)
    return fn


def _summary(fn: Any) -> str:
    doc = inspect.getdoc(fn) or ""
    first = doc.strip().splitlines()[0] if doc.strip() else ""
    return " ".join(first.split())[:160]


def _parameters(fn: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return (), ()
    names: list[str] = []
    required: list[str] = []
    for name, param in signature.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        names.append(name)
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return tuple(names), tuple(required)


def _group(name: str) -> str:
    return TOOL_GROUP.get(name, "misc")


def build_catalog() -> tuple[CatalogEntry, ...]:
    """Build one compact row per catalog tool, in catalog order."""
    entries: list[CatalogEntry] = []
    for name in TOOL_NAMES:
        fn = _server_function(name)
        args, required = _parameters(fn)
        risk = TOOL_RISK.get(name, "read")
        entries.append(
            CatalogEntry(
                tool=name,
                short=name.removeprefix("pyne_"),
                group=_group(name),
                risk=risk,
                destructive=risk == "write",
                summary=_summary(fn),
                args=args,
                required=required,
            )
        )
    return tuple(entries)


def compact_catalog() -> tuple[dict[str, Any], ...]:
    """The JSON-serializable array injected into ``search``."""
    return tuple(entry.as_dict() for entry in build_catalog())


def build_namespaces() -> dict[str, dict[str, str]]:
    """Map ``group -> op -> catalog tool`` for the ``pyne.<group>.<op>`` client."""
    namespaces: dict[str, dict[str, str]] = {}
    for entry in build_catalog():
        op = entry.short
        prefix = f"{entry.group}_"
        if op.startswith(prefix) and len(op) > len(prefix):
            op = op[len(prefix) :]
        namespaces.setdefault(entry.group, {})[op] = entry.tool
    return namespaces


def describe_tool(target: str) -> dict[str, Any]:
    """Full signature for one tool, safe to hand to sandboxed code."""
    resolved = resolve_tool_name(target)
    if resolved is None:
        return {
            "ok": False,
            "kind": "io",
            "error": f"unknown tool: {target}",
            "tools": list(TOOL_NAMES),
        }
    fn = _server_function(resolved)
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        signature = None
    parameters: list[dict[str, Any]] = []
    if signature is not None:
        for name, param in signature.parameters.items():
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            default = param.default
            parameters.append(
                {
                    "name": name,
                    "kind": str(param.kind).rsplit(".", 1)[-1],
                    "required": default is inspect.Parameter.empty,
                    "default": None if default is inspect.Parameter.empty else repr(default),
                    "annotation": None if param.annotation is inspect.Parameter.empty else str(param.annotation),
                }
            )
    risk = TOOL_RISK.get(resolved, "read")
    return {
        "ok": True,
        "tool": resolved,
        "short": resolved.removeprefix("pyne_"),
        "group": _group(resolved),
        "risk": risk,
        "destructive": risk == "write",
        "summary": _summary(fn),
        "doc": inspect.getdoc(fn) or "",
        "parameters": parameters,
    }
