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

"""API key authentication and usage tracking middleware."""

from __future__ import annotations

import hashlib
import os
import time

from dataclasses import dataclass
from dataclasses import field
from functools import wraps
from typing import Any

from flask import g
from flask import jsonify
from flask import request


@dataclass
class APIKey:
    key_id: str
    key_hash: str
    tier: str = "free"
    calls_used: int = 0
    calls_limit: int | float = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0

    def is_active(self) -> bool:
        return True

    def calls_remaining(self) -> int | float:
        if self.calls_limit == 0:
            return float("inf")
        return max(0, self.calls_limit - self.calls_used)

    def is_rate_limited(self) -> bool:
        if self.calls_limit == 0:
            return False
        return self.calls_used >= self.calls_limit

    def get_tier_info(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "calls_used": self.calls_used,
            "calls_limit": self.calls_limit,
            "calls_remaining": self.calls_remaining(),
            "reset_at": self._get_reset_time(),
        }

    def _get_reset_time(self) -> int:
        now = int(time.time())
        month_start = int(
            time.mktime(time.struct_time((now // (32 * 86400) + 1, (now // 86400) % 32 + 1, 1, 0, 0, 0, 0, 0, -1)))
        )
        return month_start

    def increment_calls(self, count: int = 1) -> None:
        self.calls_used += count
        self.last_used = time.time()


_TIER_LIMITS = {
    "free": 0,
    "hobby": 5_000,
    "pro": 50_000,
    "team": 200_000,
    "enterprise": float("inf"),
}


class APIKeyStore:
    """JSON-file-backed API key store."""

    _STORE_PATH = os.environ.get("API_KEY_STORE", "/root/pynescript/data/api_keys.json")

    def __init__(self):
        self._keys: dict[str, APIKey] = {}
        self._key_by_id: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        import json

        path = self._STORE_PATH
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for raw_key, info in data.items():
                api_key = APIKey(
                    key_id=info["key_id"],
                    key_hash=info["key_hash"],
                    tier=info.get("tier", "free"),
                    calls_used=info.get("calls_used", 0),
                    calls_limit=info.get("calls_limit", 0),
                    created_at=info.get("created_at", 0.0),
                    last_used=info.get("last_used", 0.0),
                )
                self._keys[raw_key] = api_key
                self._key_by_id[api_key.key_id] = raw_key
        except Exception:
            pass

    def _save(self) -> None:
        import json

        path = self._STORE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {}
        for raw_key, api_key in self._keys.items():
            data[raw_key] = {
                "key_id": api_key.key_id,
                "key_hash": api_key.key_hash,
                "tier": api_key.tier,
                "calls_used": api_key.calls_used,
                "calls_limit": api_key.calls_limit,
                "created_at": api_key.created_at,
                "last_used": api_key.last_used,
            }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def create_key(self, tier: str = "hobby") -> tuple[str, str]:
        import secrets

        raw_key = f"pyn_{secrets.token_urlsafe(32)}"
        key_id = hashlib.sha256(raw_key.encode()).hexdigest()[:12]
        key_hash = self._hash_key(raw_key)

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            tier=tier,
            calls_limit=_TIER_LIMITS.get(tier, 0),
        )
        self._keys[raw_key] = api_key
        self._key_by_id[key_id] = raw_key
        self._save()
        return raw_key, key_id

    def get_key(self, raw_key: str) -> APIKey | None:
        return self._keys.get(raw_key)

    def get_by_id(self, key_id: str) -> APIKey | None:
        raw_key = self._key_by_id.get(key_id)
        if raw_key:
            return self._keys.get(raw_key)
        return None

    def validate_key(self, raw_key: str) -> APIKey | None:
        if not raw_key:
            return None
        api_key = self._keys.get(raw_key)
        if api_key and api_key.is_active():
            return api_key
        return None

    def revoke_key(self, raw_key: str) -> bool:
        if raw_key in self._keys:
            key_id = self._keys[raw_key].key_id
            del self._keys[raw_key]
            del self._key_by_id[key_id]
            self._save()
            return True
        return False

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()


_key_store: APIKeyStore | None = None


def get_key_store() -> APIKeyStore:
    global _key_store
    if _key_store is None:
        _key_store = APIKeyStore()
    return _key_store


def require_api_key(f):
    """Decorator to require a valid API key for an endpoint."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            raw_key = auth_header[7:]
        elif auth_header.startswith("ApiKey "):
            raw_key = auth_header[7:]
        else:
            raw_key = request.args.get("api_key", "")

        store = get_key_store()
        api_key = store.validate_key(raw_key)

        if api_key is None:
            return jsonify(
                {
                    "status": "error",
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API key. Get one at https://pynescript.ai",
                }
            ), 401

        if api_key.is_rate_limited():
            return jsonify(
                {
                    "status": "error",
                    "code": "RATE_LIMITED",
                    "message": f"Monthly limit reached ({api_key.calls_limit} calls). Upgrade at https://pynescript.ai",
                    "tier_info": api_key.get_tier_info(),
                }
            ), 429

        g.api_key = api_key
        return f(*args, **kwargs)

    return decorated


def track_usage(f):
    """Decorator to track API call usage."""

    @wraps(f)
    @require_api_key
    def decorated(*args, **kwargs):
        api_key: APIKey = g.api_key
        result = f(*args, **kwargs)
        if isinstance(result, tuple):
            response, status_code = result
            if status_code < 400:
                api_key.increment_calls()
            return response, status_code
        api_key.increment_calls()
        return result

    return decorated


def require_admin_token(f):
    """Decorator to require admin privileges (placeholder for consolidation).

    In production this would check a special admin key or role.
    For now it allows the call (tests + dev).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        # TODO: implement real admin check using key store or env
        g.is_admin = True
        return f(*args, **kwargs)

    return decorated
