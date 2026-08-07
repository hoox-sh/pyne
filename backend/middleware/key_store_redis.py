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

"""Redis-backed API key store (optional backend).

Used as an alternative to :mod:`key_store_sqlite` when the deployment already
runs Redis (e.g. for caching or session storage). Imported lazily so the
``redis`` package is only required if the operator actually selects this
backend. See :class:`APIKeyStore` in ``auth.py`` for backend selection.

Schema (one hash per key, keyed by SHA-256 of the raw key)::

    apikey:<key_hash> -> {
        key_id, tier, calls_used, calls_limit, created_at, last_used
    }

We do not store the raw API key — only its SHA-256 hash.
"""

from __future__ import annotations

import json
import time

from typing import Any


_KEY_PREFIX = "apikey:"


class RedisKeyStore:
    """Redis-backed key store. Requires the ``redis`` package.

    Args:
        url: Redis connection URL (e.g. ``redis://localhost:6379/0``).
        client: Pre-constructed ``redis.Redis`` instance. Overrides ``url`` if
            both are provided; useful for tests with ``fakeredis``.
    """

    def __init__(self, url: str = "redis://localhost:6379/0", client: Any = None) -> None:
        if client is None:
            try:
                import redis  # noqa: PLC0415
            except ImportError as exc:
                msg = (
                    "The 'redis' package is required for the Redis backend. "
                    "Install it with `pip install redis` or set STORE_BACKEND=sqlite."
                )
                raise ImportError(msg) from exc
            client = redis.Redis.from_url(url, decode_responses=True)
        self._client = client

    def create(self, key_id: str, key_hash: str, tier: str, calls_limit: int | float) -> None:
        """Insert a hashed key hash and secondary id→hash index."""
        record = {
            "key_id": key_id,
            "key_hash": key_hash,
            "tier": tier,
            "calls_used": 0,
            "calls_limit": calls_limit,
            "created_at": time.time(),
            "last_used": 0.0,
        }
        # HSET is one round-trip and atomic; map fields one by one.
        pipe = self._client.pipeline()
        pipe.hset(_KEY_PREFIX + key_hash, mapping={k: _encode(v) for k, v in record.items()})
        # Maintain a secondary index for get_by_id: a hash of id -> key_hash.
        pipe.hset("apikey:by_id", key_id, key_hash)
        pipe.execute()

    def get_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        """Return the key record for *key_hash*, or ``None``."""
        data = self._client.hgetall(_KEY_PREFIX + key_hash)
        if not data:
            return None
        return _decode_record(data)

    def get_by_id(self, key_id: str) -> dict[str, Any] | None:
        """Return the key record for public *key_id*, or ``None``."""
        key_hash = self._client.hget("apikey:by_id", key_id)
        if not key_hash:
            return None
        return self.get_by_hash(key_hash)

    def delete_by_hash(self, key_hash: str) -> bool:
        """Delete by hash (and id index); returns whether a record existed."""
        # Look up key_id first so we can clean the secondary index.
        record = self.get_by_hash(key_hash)
        if record is None:
            return False
        pipe = self._client.pipeline()
        pipe.delete(_KEY_PREFIX + key_hash)
        pipe.hdel("apikey:by_id", record["key_id"])
        pipe.execute()
        return True

    def update_calls(self, key_id: str, calls_used: int, last_used: float) -> None:
        """Persist usage counters for *key_id*."""
        # We have the key_hash already if we got here via APIKey._store, but
        # update_calls only knows key_id. Resolve it once.
        key_hash = self._client.hget("apikey:by_id", key_id)
        if not key_hash:
            return
        self._client.hset(
            _KEY_PREFIX + key_hash,
            mapping={
                "calls_used": _encode(calls_used),
                "last_used": _encode(last_used),
            },
        )

    def close(self) -> None:
        """No-op: process-wide Redis pool is not closed here."""
        # The shared connection pool is process-wide; do not close it.
        # Callers that need a hard close should construct their own client.
        return


def _encode(value: Any) -> str:
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return str(value)


def _decode_record(data: dict[str, str]) -> dict[str, Any]:
    return {
        "key_id": data["key_id"],
        "key_hash": data["key_hash"],
        "tier": data["tier"],
        "calls_used": json.loads(data["calls_used"]),
        "calls_limit": json.loads(data["calls_limit"]),
        "created_at": json.loads(data["created_at"]),
        "last_used": json.loads(data["last_used"]),
    }
