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

RESOURCE_URIS: tuple[str, ...] = (
    "pyne://info",
    "pyne://builtins",
)

PROMPT_NAMES: tuple[str, ...] = (
    "review_pine",
    "debug_pine",
    "convert_to_v6",
)
