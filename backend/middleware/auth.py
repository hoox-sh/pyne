# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""API key authentication and usage tracking middleware."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from flask import g, jsonify, request


@dataclass
class APIKey:
    key_id: str
    key_hash: str
    tier: str = "free"
    calls_used: int = 0
    calls_limit: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0

    def is_active(self) -> bool:
        return True

    def calls_remaining(self) -> int:
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
    """In-memory API key store. In production, replace with PostgreSQL."""

    def __init__(self):
        self._keys: dict[str, APIKey] = {}
        self._key_by_id: dict[str, str] = {}

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
