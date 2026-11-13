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

"""Wire protocol and limits between the MCP server and the sandbox harness.

One JSON object per line, newline delimited, over the child's stdin/stdout. The
child's stderr is diagnostics only and is never parsed.

parent -> child, first line::

    {"type": "job", "mode": "search"|"execute", "code": str,
     "catalog": str|null, "namespaces": str|null, "maxCalls": int}

child -> parent, zero or more::

    {"type": "call", "id": int, "method": "call"|"describe",
     "target": str, "args": object|null}

parent -> child, one per call::

    {"type": "reply", "id": int, "ok": bool, "json": str}

child -> parent, exactly one::

    {"type": "done", "json": str, "calls": int, "logs": [str]}
    {"type": "error", "message": str}

``json`` is always a string, never a nested object. That is deliberate: only
primitives cross into the JavaScript context, so a host object can never become
a ``constructor`` bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Literal


Mode = Literal["search", "execute"]


@dataclass(frozen=True)
class CodeModeLimits:
    """Hard limits applied by the parent, not by the sandboxed code."""

    timeout_ms: int = 60_000
    max_calls: int = 50
    max_code_chars: int = 20_000
    max_result_chars: int = 200_000


DEFAULT_LIMITS = CodeModeLimits()


@dataclass(frozen=True)
class SandboxRequest:
    """One sandbox job. ``code`` is untrusted model output."""

    mode: Mode
    code: str
    catalog: tuple[dict[str, Any], ...] = ()
    namespaces: dict[str, dict[str, str]] = field(default_factory=dict)
    limits: CodeModeLimits = DEFAULT_LIMITS


@dataclass(frozen=True)
class SandboxResult:
    """Normalized result of one sandbox job."""

    ok: bool
    value: Any = None
    message: str = ""
    stderr: str = ""
    calls: int = 0
    logs: tuple[str, ...] = ()
    duration_ms: int = 0
    truncated: bool = False
