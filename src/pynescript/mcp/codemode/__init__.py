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

"""Opt-in Code Mode for the PYNE MCP server.

Two model-facing tools, ``search`` and ``execute``, take one JavaScript async
arrow function each. The code runs in a separate process inside a bubblewrap
namespace and calls back into this Python process over newline-delimited JSON.
Python is never evaluated from model-authored text.

Enable with ``PYNE_MCP_CODE_MODE=1``. Unset, this package is not imported by the
server and the tool list is unchanged.
"""

from __future__ import annotations

from pynescript.mcp.codemode.protocol import DEFAULT_LIMITS
from pynescript.mcp.codemode.protocol import CodeModeLimits
from pynescript.mcp.codemode.protocol import SandboxRequest
from pynescript.mcp.codemode.protocol import SandboxResult


__all__ = [
    "CODE_MODE_TOOL_NAMES",
    "DEFAULT_LIMITS",
    "CodeModeLimits",
    "SandboxRequest",
    "SandboxResult",
    "code_mode_enabled",
    "register_code_mode",
]


CODE_MODE_TOOL_NAMES: tuple[str, ...] = ("search", "execute")


def code_mode_enabled(env: dict[str, str] | None = None) -> bool:
    """True only for the exact opt-in value ``PYNE_MCP_CODE_MODE=1``."""
    import os

    source = os.environ if env is None else env
    return (source.get("PYNE_MCP_CODE_MODE") or "").strip() == "1"


def __getattr__(name: str) -> object:
    if name == "register_code_mode":
        from pynescript.mcp.codemode.tools import register_code_mode

        return register_code_mode
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
