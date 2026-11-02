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

"""PYNE Model Context Protocol server (stdio or HTTP).

Install the extra::

    pip install "hoox-pyne[mcp]"

Then run ``pyne-mcp`` or ``pyne mcp``, print client JSON with ``pyne mcp config``,
or execute a tool in-process with ``pyne mcp call`` / ``pyne execute``.
"""

from __future__ import annotations

from typing import Any


__all__ = [
    "call_tool",
    "client_config",
    "create_server",
    "resolve_tool_name",
    "run",
    "run_stdio",
    "serve_kwargs_from_env",
]


def __getattr__(name: str) -> Any:
    if name in {"client_config", "create_server", "run", "run_stdio", "serve_kwargs_from_env"}:
        from pynescript.mcp import server as mcp_server

        return getattr(mcp_server, name)
    if name in {"call_tool", "resolve_tool_name"}:
        from pynescript.mcp import dispatch as mcp_dispatch

        return getattr(mcp_dispatch, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
