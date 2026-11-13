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

"""Canonical MCP tool / resource / prompt names (docs + tests)."""

from __future__ import annotations


TOOL_NAMES: tuple[str, ...] = (
    "pyne_info",
    "pyne_check",
    "pyne_format",
    "pyne_convert",
    "pyne_dump",
    "pyne_unparse",
    "pyne_lint",
    "pyne_compile",
    "pyne_prewarm",
    "pyne_run",
    "pyne_optimize",
    "pyne_data",
    "pyne_download_builtins",
    "pyne_runner_deploy",
    "pyne_runner_list",
    "pyne_runner_show",
    "pyne_runner_delete",
    "pyne_runner_tick",
    "pyne_runner_jobs",
    "pyne_runner_history",
    "pyne_runner_enable",
    "pyne_runner_disable",
    "pyne_parse",
    "pyne_symbols",
    "pyne_execute",
    "pyne_parity",
    "pyne_hover",
    "pyne_complete",
    "pyne_signature",
    "pyne_builtin",
    "pyne_diagnostics",
    "pyne_axb1",
    "pyne_sessions",
)

# Risk classes used by the MCP annotations and by Code Mode. ``write`` is the
# only class Code Mode treats as destructive; the direct tools keep their own
# behaviour and are never downgraded.
READ_TOOLS: frozenset[str] = frozenset(
    {
        "pyne_info",
        "pyne_check",
        "pyne_format",
        "pyne_convert",
        "pyne_dump",
        "pyne_unparse",
        "pyne_lint",
        "pyne_compile",
        "pyne_prewarm",
        "pyne_run",
        "pyne_optimize",
        "pyne_parse",
        "pyne_symbols",
        "pyne_execute",
        "pyne_parity",
        "pyne_hover",
        "pyne_complete",
        "pyne_signature",
        "pyne_builtin",
        "pyne_diagnostics",
        "pyne_axb1",
        "pyne_sessions",
    }
)

NETWORK_TOOLS: frozenset[str] = frozenset(
    {
        "pyne_data",
        "pyne_download_builtins",
        "pyne_runner_list",
        "pyne_runner_show",
        "pyne_runner_jobs",
        "pyne_runner_history",
    }
)

WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "pyne_runner_deploy",
        "pyne_runner_delete",
        "pyne_runner_tick",
        "pyne_runner_enable",
        "pyne_runner_disable",
    }
)

TOOL_RISK: dict[str, str] = {
    **dict.fromkeys(READ_TOOLS, "read"),
    **dict.fromkeys(NETWORK_TOOLS, "network"),
    **dict.fromkeys(WRITE_TOOLS, "write"),
}

# Namespace group for the Code Mode ``pyne.<group>.<op>`` client. The server
# wrappers all live in ``pynescript.mcp.server``; this map points at the real
# ops module so the namespace is stable and human-readable.
TOOL_GROUP: dict[str, str] = {
    "pyne_info": "info",
    "pyne_check": "language",
    "pyne_format": "language",
    "pyne_convert": "language",
    "pyne_dump": "language",
    "pyne_unparse": "language",
    "pyne_lint": "language",
    "pyne_parse": "language",
    "pyne_symbols": "language",
    "pyne_diagnostics": "language",
    "pyne_compile": "compile",
    "pyne_prewarm": "compile",
    "pyne_run": "compile",
    "pyne_execute": "execute",
    "pyne_parity": "execute",
    "pyne_optimize": "optimize",
    "pyne_data": "data",
    "pyne_download_builtins": "builtins",
    "pyne_builtin": "builtins",
    "pyne_hover": "lsp",
    "pyne_complete": "lsp",
    "pyne_signature": "lsp",
    "pyne_axb1": "axb1",
    "pyne_sessions": "sessions",
    "pyne_runner_deploy": "runner",
    "pyne_runner_list": "runner",
    "pyne_runner_show": "runner",
    "pyne_runner_delete": "runner",
    "pyne_runner_tick": "runner",
    "pyne_runner_jobs": "runner",
    "pyne_runner_history": "runner",
    "pyne_runner_enable": "runner",
    "pyne_runner_disable": "runner",
}


RESOURCE_URIS: tuple[str, ...] = (
    "pyne://info",
    "pyne://builtins",
)

PROMPT_NAMES: tuple[str, ...] = (
    "review_pine",
    "debug_pine",
    "convert_to_v6",
)
