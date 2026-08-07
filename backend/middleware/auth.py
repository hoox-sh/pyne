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

"""API key authentication and usage tracking middleware.

Provides :class:`APIKey`, pluggable :class:`APIKeyStore` (JSON / SQLite /
Redis), and Flask decorators :func:`require_api_key`, :func:`track_usage`,
and :func:`require_admin_token`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time

from dataclasses import dataclass
from dataclasses import field
from functools import wraps
from typing import Any
from typing import Protocol

from flask import g
from flask import jsonify
from flask import request


@dataclass
class APIKey:
    """In-memory view of a hashed API key (tier, usage, limits).

    Raw secrets are never stored here after mint; only ``key_hash`` (and
    ``key_id`` for display) persist in backends.
    """

    key_id: str
    key_hash: str
    tier: str = "free"
    calls_used: int = 0
    calls_limit: int | float = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    # Set by the store so increment_calls can persist without the caller knowing
    # which backend is active.
    _store: Any = field(default=None, repr=False, compare=False)

    def is_active(self) -> bool:
        """Whether the key may be used (revocation hook; always true today)."""
        return True

    def calls_remaining(self) -> int | float:
        """Remaining monthly quota, or ``inf`` when unlimited."""
        if self.calls_limit == 0 or self.calls_limit == float("inf"):
            return float("inf")
        return max(0, self.calls_limit - self.calls_used)

    def is_rate_limited(self) -> bool:
        """True when the monthly call quota is exhausted."""
        if self.calls_limit == 0 or self.calls_limit == float("inf"):
            return False
        return self.calls_used >= self.calls_limit

    def get_tier_info(self) -> dict[str, Any]:
        """Public tier/usage snapshot for API responses."""
        return {
            "tier": self.tier,
            "calls_used": self.calls_used,
            "calls_limit": self.calls_limit if self.calls_limit != float("inf") else 0,
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
        """Bump usage counters and persist via the owning store when set."""
        self.calls_used += count
        self.last_used = time.time()
        store = self._store
        if store is not None:
            store.persist_usage(self)


_TIER_LIMITS = {
    "free": 0,
    "hobby": 5_000,
    "pro": 50_000,
    "team": 200_000,
    "enterprise": float("inf"),
}


class _HashBackend(Protocol):
    """Minimal protocol shared by SQLiteKeyStore and RedisKeyStore."""

    def create(self, key_id: str, key_hash: str, tier: str, calls_limit: int | float) -> None: ...

    def get_by_hash(self, key_hash: str) -> dict[str, Any] | None: ...

    def get_by_id(self, key_id: str) -> dict[str, Any] | None: ...

    def delete_by_hash(self, key_hash: str) -> bool: ...

    def update_calls(self, key_id: str, calls_used: int, last_used: float) -> None: ...


def _limit_for_backend(limit: int | float) -> int | float:
    """Map unlimited (inf) to 0 for backends that store numeric limits."""
    if limit == float("inf"):
        return 0
    return limit


def _limit_from_backend(limit: int | float) -> int | float:
    """0 means unlimited in store semantics (matches free / enterprise)."""
    if limit == 0:
        return 0
    return limit


class APIKeyStore:
    """API key store with pluggable persistence.

    Backends:

    * ``json`` (default) — single-process JSON file. Stores raw keys as object
      keys (dev convenience only; not multi-worker safe).
    * ``sqlite`` — hash-only SQLite (WAL). Safe for multi-worker single host
      when the DB path is on a shared volume (e.g. ``/data/api_keys.db``).
    * ``redis`` — hash-only Redis. Safe for multi-replica (Cloud Run + Memorystore).

    Select via ``STORE_BACKEND`` (see :func:`get_key_store`).
    """

    _DEFAULT_JSON_PATH = "/data/api_keys.json"

    def __init__(self, backend: _HashBackend | None = None, store_path: str | None = None) -> None:
        self._backend = backend
        # Read env at init time so tests can monkeypatch API_KEY_STORE.
        self._store_path = store_path or os.environ.get("API_KEY_STORE", self._DEFAULT_JSON_PATH)
        # JSON mode only:
        self._keys: dict[str, APIKey] = {}
        self._key_by_id: dict[str, str] = {}
        if self._backend is None:
            self._load()

    def _load(self) -> None:
        path = self._store_path
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
                    _store=self,
                )
                self._keys[raw_key] = api_key
                self._key_by_id[api_key.key_id] = raw_key
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Corrupt or partial store — start empty rather than crash the API.
            self._keys.clear()
            self._key_by_id.clear()

    def _save(self) -> None:
        path = self._store_path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = {}
        for raw_key, api_key in self._keys.items():
            data[raw_key] = {
                "key_id": api_key.key_id,
                "key_hash": api_key.key_hash,
                "tier": api_key.tier,
                "calls_used": api_key.calls_used,
                "calls_limit": api_key.calls_limit if api_key.calls_limit != float("inf") else 0,
                "created_at": api_key.created_at,
                "last_used": api_key.last_used,
            }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def persist_usage(self, api_key: APIKey) -> None:
        """Write call counters after :meth:`APIKey.increment_calls`."""
        if self._backend is not None:
            self._backend.update_calls(api_key.key_id, api_key.calls_used, api_key.last_used)
            return
        self._save()

    def create_key(self, tier: str = "hobby") -> tuple[str, str]:
        """Mint a new API key; returns ``(raw_key, key_id)`` (raw shown once)."""
        raw_key = f"pyn_{secrets.token_urlsafe(32)}"
        key_id = hashlib.sha256(raw_key.encode()).hexdigest()[:12]
        key_hash = self._hash_key(raw_key)
        calls_limit = _TIER_LIMITS.get(tier, 0)

        if self._backend is not None:
            self._backend.create(
                key_id=key_id,
                key_hash=key_hash,
                tier=tier,
                calls_limit=_limit_for_backend(calls_limit),
            )
            return raw_key, key_id

        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            tier=tier,
            calls_limit=calls_limit,
            _store=self,
        )
        self._keys[raw_key] = api_key
        self._key_by_id[key_id] = raw_key
        self._save()
        return raw_key, key_id

    def _api_key_from_record(self, record: dict[str, Any]) -> APIKey:
        limit = _limit_from_backend(record.get("calls_limit", 0))
        return APIKey(
            key_id=record["key_id"],
            key_hash=record["key_hash"],
            tier=record.get("tier", "free"),
            calls_used=int(record.get("calls_used", 0)),
            calls_limit=limit,
            created_at=float(record.get("created_at", 0.0)),
            last_used=float(record.get("last_used", 0.0)),
            _store=self,
        )

    def get_key(self, raw_key: str) -> APIKey | None:
        """Look up a key by raw secret (hash lookup on sqlite/redis backends)."""
        if self._backend is not None:
            if not raw_key:
                return None
            record = self._backend.get_by_hash(self._hash_key(raw_key))
            if record is None:
                return None
            return self._api_key_from_record(record)
        return self._keys.get(raw_key)

    def get_by_id(self, key_id: str) -> APIKey | None:
        """Look up a key by public ``key_id`` (not the raw secret)."""
        if self._backend is not None:
            record = self._backend.get_by_id(key_id)
            if record is None:
                return None
            return self._api_key_from_record(record)
        raw_key = self._key_by_id.get(key_id)
        if raw_key:
            return self._keys.get(raw_key)
        return None

    def validate_key(self, raw_key: str) -> APIKey | None:
        """Return the key if present and active; else ``None``."""
        if not raw_key:
            return None
        api_key = self.get_key(raw_key)
        if api_key and api_key.is_active():
            return api_key
        return None

    def revoke_key(self, raw_key: str) -> bool:
        """Delete a key by raw secret; returns whether a record was removed."""
        if self._backend is not None:
            if not raw_key:
                return False
            return self._backend.delete_by_hash(self._hash_key(raw_key))
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


class _KeyStoreHolder:
    """Process-local holder so we avoid module-level ``global`` assignments."""

    store: APIKeyStore | None = None


def reset_key_store() -> None:
    """Drop the process-local singleton (tests / reconfiguration)."""
    _KeyStoreHolder.store = None


def _default_sqlite_path() -> str:
    # Prefer dedicated env; fall back next to JSON path with .db suffix.
    explicit = os.environ.get("API_KEY_STORE_SQLITE")
    if explicit:
        return explicit
    json_path = os.environ.get("API_KEY_STORE", "/data/api_keys.json")
    if json_path.endswith(".json"):
        return json_path[: -len(".json")] + ".db"
    return "/data/api_keys.db"


def _build_key_store() -> APIKeyStore:
    backend_name = (os.environ.get("STORE_BACKEND") or "json").strip().lower()
    if backend_name in {"sqlite", "sql", "db"}:
        from backend.middleware.key_store_sqlite import SQLiteKeyStore  # noqa: PLC0415

        path = _default_sqlite_path()
        parent = os.path.dirname(path)
        if parent and path != ":memory:":
            os.makedirs(parent, exist_ok=True)
        return APIKeyStore(backend=SQLiteKeyStore(path))
    if backend_name in {"redis", "memorystore"}:
        from backend.middleware.key_store_redis import RedisKeyStore  # noqa: PLC0415

        url = os.environ.get("REDIS_URL", "").strip()
        if not url:
            msg = "STORE_BACKEND=redis requires REDIS_URL to be set"
            raise RuntimeError(msg)
        return APIKeyStore(backend=RedisKeyStore(url=url))
    return APIKeyStore()


def get_key_store() -> APIKeyStore:
    """Return the process-local key store singleton.

    Backend selection (``STORE_BACKEND``, case-insensitive):

    * ``json`` (default) — file at ``API_KEY_STORE``
    * ``sqlite`` — ``API_KEY_STORE_SQLITE`` or ``API_KEY_STORE`` with ``.db``
    * ``redis`` — ``REDIS_URL`` (required)

    For multi-worker gunicorn use ``sqlite`` on a shared volume; for multi-replica
    Cloud Run use ``redis`` (e.g. Memorystore).
    """
    if _KeyStoreHolder.store is None:
        _KeyStoreHolder.store = _build_key_store()
    return _KeyStoreHolder.store


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
            if status_code < 400:  # noqa: PLR2004 — HTTP success range
                api_key.increment_calls()
            return response, status_code
        api_key.increment_calls()
        return result

    return decorated


def _provided_admin_token() -> str:
    """Extract admin credential from request headers."""
    header = (request.headers.get("X-Admin-Token") or "").strip()
    if header:
        return header
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    if auth.lower().startswith("admintoken "):
        return auth[11:].strip()
    return ""


def require_admin_token(f):
    """Require ``ADMIN_TOKEN`` via ``X-Admin-Token`` (or Bearer).

    Fail closed:

    * ``ADMIN_TOKEN`` unset/empty → 403 (admin minting disabled)
    * header missing or mismatch → 403

    Comparison uses :func:`hmac.compare_digest` (constant-time).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        expected = (os.environ.get("ADMIN_TOKEN") or "").strip()
        if not expected:
            return jsonify(
                {
                    "status": "error",
                    "code": "FORBIDDEN",
                    "message": "Admin access is disabled (ADMIN_TOKEN not configured).",
                }
            ), 403

        provided = _provided_admin_token()
        if not provided or not hmac.compare_digest(provided, expected):
            return jsonify(
                {
                    "status": "error",
                    "code": "FORBIDDEN",
                    "message": "Invalid or missing admin token (X-Admin-Token).",
                }
            ), 403

        g.is_admin = True
        return f(*args, **kwargs)

    return decorated
