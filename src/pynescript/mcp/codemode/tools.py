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

"""The two model-facing Code Mode tools: ``search`` and ``execute``.

They are registered only when ``PYNE_MCP_CODE_MODE=1``. With the flag unset the
server never imports this module, so the tool list is byte-identical.
"""

from __future__ import annotations

from typing import Any

from pynescript.mcp.codemode.bridge import Handlers
from pynescript.mcp.codemode.bridge import create_handlers
from pynescript.mcp.codemode.protocol import DEFAULT_LIMITS
from pynescript.mcp.codemode.protocol import CodeModeLimits
from pynescript.mcp.codemode.protocol import SandboxRequest
from pynescript.mcp.codemode.protocol import SandboxResult
from pynescript.mcp.codemode.sandbox import PlanError
from pynescript.mcp.codemode.sandbox import SandboxPlan
from pynescript.mcp.codemode.sandbox import run_in_sandbox
from pynescript.mcp.codemode.view import build_namespaces
from pynescript.mcp.codemode.view import compact_catalog


_SEARCH_DESCRIPTION = (
    "Search the live PYNE MCP catalog by running JavaScript against it instead of "
    "loading every tool schema into context. `code` is an async arrow function with no "
    "parameters; the binding `catalog` is an array of "
    "{ tool, short, group, risk, destructive, summary, args, required }. Filter it and "
    "return only the rows you need. Full signatures stay behind execute + pyne.describe. "
    "Runs in a bubblewrap sandbox with no filesystem, network, or environment access. "
    "If the operator sets PYNE_MCP_CODE_MODE_SANDBOX=subprocess the environment is still "
    "cleared but host filesystem reads are possible."
)

_EXECUTE_DESCRIPTION = (
    "Run JavaScript that calls PYNE operations, composes several calls, and returns only "
    "the data you need. `code` is an async arrow function with no parameters. Bindings: "
    "`pyne.call(tool, args)` runs one catalog tool; `pyne.describe(tool)` returns its full "
    "signature; `pyne.<group>.<op>(args)` is the same call with a namespace, for example "
    "`pyne.language.lint({source})` or `pyne.execute.execute({source, bars})`. Every call "
    "is re-resolved and re-validated by the server through the same dispatch path as the "
    "direct tools. Destructive tools (risk=write) are refused unless the operator sets "
    "PYNE_MCP_CODE_MODE_ALLOW_DESTRUCTIVE=1, and even then the first call returns "
    "confirmation_required with a single-use confirm_token bound to the tool and its "
    "canonical arguments; pass it back as args.confirm_token on a second call with the "
    "same arguments. A token is consumed on first successful use, and a token minted "
    "for different arguments or a different tool is rejected. "
    "Runs in a bubblewrap sandbox with no "
    "filesystem, network, or environment access; if the operator sets "
    "PYNE_MCP_CODE_MODE_SANDBOX=subprocess the environment is still cleared but host "
    "filesystem reads are possible."
)


def _envelope(mode: str, result: SandboxResult) -> dict[str, Any]:
    if not result.ok:
        return {
            "ok": False,
            "mode": mode,
            "message": result.message,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
        }
    return {
        "ok": True,
        "mode": mode,
        "value": result.value,
        "calls": result.calls,
        "logs": list(result.logs),
        "truncated": result.truncated,
        "duration_ms": result.duration_ms,
    }


def register_code_mode(
    server: Any,
    *,
    limits: CodeModeLimits | None = None,
    plan: SandboxPlan | PlanError | None = None,
    handlers: Handlers | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Register exactly ``search`` and ``execute`` on *server*."""
    from mcp.types import ToolAnnotations

    active_limits = limits or DEFAULT_LIMITS
    catalog = compact_catalog()
    namespaces = build_namespaces()
    active_handlers = handlers or create_handlers(env=env)

    def search(code: str) -> dict[str, Any]:
        """Search the catalog with JavaScript; returns only the rows you ask for."""
        result = run_in_sandbox(
            SandboxRequest(mode="search", code=code, catalog=catalog, limits=active_limits),
            plan=plan,
            env=env,
        )
        return _envelope("search", result)

    def execute(code: str) -> dict[str, Any]:
        """Call PYNE operations from JavaScript through the re-validated bridge."""
        result = run_in_sandbox(
            SandboxRequest(mode="execute", code=code, namespaces=namespaces, limits=active_limits),
            handlers=active_handlers,
            plan=plan,
            env=env,
        )
        return _envelope("execute", result)

    server.add_tool(
        search,
        name="search",
        title="Search the PYNE MCP catalog",
        description=_SEARCH_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    server.add_tool(
        execute,
        name="execute",
        title="Execute PYNE operations from code",
        description=_EXECUTE_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )
