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

"""Parent-side handlers for calls arriving from the sandbox.

The parent is the policy enforcement point. It never trusts the child: every
request is resolved, risk-classified, and dispatched through the same
``dispatch.call_tool`` path the direct tools use.

Confirm tokens are single-use. The set of consumed token signatures lives in
process memory only (an in-memory nonce store, no external store); a restart
revokes every outstanding token. Consumed nonces are pruned once their token
expiry has passed, so the store stays bounded by the number of tokens minted
within one TTL window.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time

from collections.abc import Callable
from typing import Any

from pynescript.mcp.catalog import TOOL_RISK
from pynescript.mcp.codemode.view import describe_tool
from pynescript.mcp.dispatch import call_tool
from pynescript.mcp.dispatch import resolve_tool_name
from pynescript.mcp.serialize import jsonable


Handler = Callable[[str, Any], Any]
Handlers = dict[str, Handler]

_DESTRUCTIVE_FLAG = "PYNE_MCP_CODE_MODE_ALLOW_DESTRUCTIVE"
_CONFIRM_FIELD = "confirm_token"
_CONFIRM_TOKEN_TTL_S = 300


def destructive_allowed(env: dict[str, str] | None = None) -> bool:
    """True only when the operator explicitly opts into destructive calls."""
    source = os.environ if env is None else env
    return (source.get(_DESTRUCTIVE_FLAG) or "").strip() == "1"


class _ConfirmTokenCodec:
    """HMAC tokens bound to (resolved tool, canonical args, expiry).

    The secret lives in the parent process only. The child sandbox receives a
    token string, never the secret, so a forged or re-bound token fails.

    Verification is single-use: a successfully verified token signature is
    recorded in an in-memory nonce set and rejected on any replay. The store is
    process-local (a restart revokes all outstanding tokens) and is pruned of
    entries whose token expiry has passed, so it cannot grow without bound.
    """

    def __init__(self, ttl_s: int = _CONFIRM_TOKEN_TTL_S) -> None:
        self._secret = secrets.token_bytes(32)
        self._ttl_s = ttl_s
        self._used: dict[str, int] = {}

    def issue(self, tool: str, payload: dict[str, Any]) -> tuple[str, int]:
        expires_at = int(time.time()) + self._ttl_s
        return f"{expires_at}.{self._sign(tool, payload, expires_at)}", expires_at

    def verify(self, token: Any, tool: str, payload: dict[str, Any]) -> bool:
        if not isinstance(token, str):
            return False
        expires_raw, separator, signature = token.partition(".")
        if not separator or not expires_raw.isdigit():
            return False
        expires_at = int(expires_raw)
        now = int(time.time())
        if expires_at < now:
            return False
        if not hmac.compare_digest(signature, self._sign(tool, payload, expires_at)):
            return False
        self._prune(now)
        if signature in self._used:
            return False
        self._used[signature] = expires_at
        return True

    def _prune(self, now: int) -> None:
        expired = [sig for sig, expires_at in self._used.items() if expires_at < now]
        for sig in expired:
            del self._used[sig]

    def _sign(self, tool: str, payload: dict[str, Any], expires_at: int) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        message = f"{tool}\0{canonical}\0{expires_at}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()


def _split_confirm_token(args: Any) -> tuple[Any, Any]:
    """Return ``(token, payload)`` with the reserved confirm key removed."""
    if args is None:
        return None, {}
    if not isinstance(args, dict):
        return None, args
    token = args.get(_CONFIRM_FIELD)
    if token is None:
        return None, dict(args)
    payload = {key: value for key, value in args.items() if key != _CONFIRM_FIELD}
    return token, payload


def create_handlers(
    dispatcher: Callable[[str, dict[str, Any] | None], dict[str, Any]] | None = None,
    env: dict[str, str] | None = None,
) -> Handlers:
    """Build the two sandbox methods, ``call`` and ``describe``.

    ``dispatcher`` is a test seam; production uses ``dispatch.call_tool``.
    """
    run = dispatcher or call_tool
    tokens = _ConfirmTokenCodec()

    def call(target: str, args: Any) -> dict[str, Any]:
        resolved = resolve_tool_name(target)
        if resolved is None:
            return {
                "ok": False,
                "kind": "io",
                "error": f"unknown tool: {target}",
            }
        risk = TOOL_RISK.get(resolved, "read")
        token, payload = _split_confirm_token(args)
        if not isinstance(payload, dict):
            return {
                "ok": False,
                "kind": "io",
                "tool": resolved,
                "error": "arguments must be a JSON object",
            }
        if risk == "write":
            if not destructive_allowed(env):
                return {
                    "ok": False,
                    "kind": "confirmation_required",
                    "tool": resolved,
                    "risk": risk,
                    "error": (
                        f"{resolved} is destructive and Code Mode is fail-closed for "
                        f"destructive tools. The operator must set {_DESTRUCTIVE_FLAG}=1."
                    ),
                    "hint": f"Set {_DESTRUCTIVE_FLAG}=1 on the server process to allow it.",
                }
            if token is None:
                issued_token, expires_at = tokens.issue(resolved, payload)
                return {
                    "ok": False,
                    "kind": "confirmation_required",
                    "tool": resolved,
                    "risk": risk,
                    "confirm_token": issued_token,
                    "expires_at": expires_at,
                    "error": (
                        f"{resolved} is destructive. Call again with {_CONFIRM_FIELD} to confirm these exact arguments."
                    ),
                    "hint": (
                        f"Pass the returned {_CONFIRM_FIELD} back on a second call; the "
                        f"token is bound to {resolved} and these arguments."
                    ),
                }
            if not tokens.verify(token, resolved, payload):
                return {
                    "ok": False,
                    "kind": "confirmation_required",
                    "tool": resolved,
                    "risk": risk,
                    "error": (
                        f"{_CONFIRM_FIELD} is invalid, expired, or was minted for a "
                        f"different tool or different arguments."
                    ),
                    "hint": (
                        f"Call again without {_CONFIRM_FIELD} to mint a fresh token for "
                        f"the exact arguments you intend to run."
                    ),
                }
        return jsonable(run(resolved, payload))

    def describe(target: str, _args: Any = None) -> dict[str, Any]:
        return describe_tool(target)

    return {"call": call, "describe": describe}
