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

"""Redis-backed runner store (optional backend, ``PYNE_RUNNER_STORE_BACKEND=redis``).

Lets several API replicas share deployed scripts, cron state, and run
history; the tick lock becomes a ``SET NX`` token instead of a filesystem
flock. Imported lazily from :mod:`backend.runner.store` so the ``redis``
package is only required when this backend is actually selected.

Key layout (prefix ``pyne:runner:``)::

    scripts           -> hash: script_id -> JSON record (full source)
    cron              -> hash: script_id -> JSON cron state
    history           -> list: JSON run entries, newest first (cap 1000)
    history:<id>      -> list: JSON run entries per script (cap 100)
    ticklock          -> SET NX token for the running tick

The script record necessarily stores source and ``webhook_url`` in
plaintext (reads redact the webhook at the API layer, same as SQLite).
Keep Redis private — the compose service never publishes ports.
"""

from __future__ import annotations

import json
import os
import time

from typing import Any


_PREFIX = "pyne:runner:"

# Global audit-log cap (per-script caps mirror SQLite's _HISTORY_PER_SCRIPT).
_HISTORY_GLOBAL_CAP = 1000
_HISTORY_PER_SCRIPT_CAP = 100

_CRON_DEFAULTS: dict[str, Any] = {
    "last_bar_time": 0,
    "last_run_at": 0,
    "last_status": "",
    "last_error": "",
    "last_alerts": 0,
    "last_events": 0,
    "consecutive_errors": 0,
    "next_due_at": 0,
    "last_forward_status": "",
}


class RunnerRedisStore:
    """Redis-backed runner store. Requires the ``redis`` package.

    Args:
        url: Redis connection URL (e.g. ``redis://localhost:6379/0``).
        client: Pre-constructed ``redis.Redis`` instance. Overrides ``url``
            when provided; useful for tests with an in-memory fake.
    """

    def __init__(self, url: str = "redis://localhost:6379/0", client: Any = None) -> None:
        if client is None:
            try:
                import redis
            except ImportError as exc:
                msg = (
                    "The 'redis' package is required for the Redis runner store. "
                    "Install it with `pip install redis` or use PYNE_RUNNER_STORE_BACKEND=sqlite."
                )
                raise ImportError(msg) from exc
            client = redis.Redis.from_url(url, decode_responses=True)
        self._client = client

    # --- scripts registry --------------------------------------------------

    def put_script(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Store a normalized script record; returns the stored record."""
        self._client.hset(_PREFIX + "scripts", str(rec["id"]), json.dumps(rec))
        return self.get_script(str(rec["id"]), include_source=True) or {}

    def get_script(self, script_id: str, *, include_source: bool = True) -> dict[str, Any] | None:
        raw = self._client.hget(_PREFIX + "scripts", script_id)
        if raw is None:
            return None
        rec = json.loads(raw)
        if not include_source:
            rec.pop("script", None)
        return rec

    def delete_script(self, script_id: str) -> bool:
        pipe = self._client.pipeline()
        pipe.hdel(_PREFIX + "scripts", script_id)
        pipe.hdel(_PREFIX + "cron", script_id)
        pipe.delete(_PREFIX + "history:" + script_id)
        results = pipe.execute()
        return bool(results and results[0])

    def list_scripts(self, *, include_source: bool = False) -> list[dict[str, Any]]:
        raw = self._client.hgetall(_PREFIX + "scripts")
        recs = [json.loads(v) for v in raw.values()]
        recs.sort(key=lambda r: str(r.get("id") or ""))
        if not include_source:
            for rec in recs:
                rec.pop("script", None)
        return recs

    def list_enabled(self) -> list[dict[str, Any]]:
        return [rec for rec in self.list_scripts(include_source=True) if rec.get("enabled")]

    def set_enabled(self, script_id: str, *, enabled: bool) -> bool:
        raw = self._client.hget(_PREFIX + "scripts", script_id)
        if raw is None:
            return False
        rec = json.loads(raw)
        rec["enabled"] = bool(enabled)
        rec["updated_at"] = int(time.time() * 1000)
        self._client.hset(_PREFIX + "scripts", script_id, json.dumps(rec))
        return True

    # --- cron state ---------------------------------------------------------

    def get_cron_state(self, script_id: str) -> dict[str, Any]:
        state = {"script_id": script_id, **_CRON_DEFAULTS}
        raw = self._client.hget(_PREFIX + "cron", script_id)
        if raw:
            try:
                state.update(json.loads(raw))
            except (TypeError, ValueError):
                pass
        return state

    def put_cron_state(self, script_id: str, state: dict[str, Any]) -> None:
        """Merge *state* over the stored cron state (same semantics as SQLite)."""
        from backend.runner.store import _cron_payload

        merged = self.get_cron_state(script_id)
        merged.update({k: v for k, v in state.items() if k != "script_id"})
        payload = {"script_id": script_id, **_cron_payload(script_id, merged)}
        payload["last_run_at"] = int(state.get("last_run_at") or time.time() * 1000)
        self._client.hset(_PREFIX + "cron", script_id, json.dumps(payload))

    # --- run history --------------------------------------------------------

    def record_run(self, entry: dict[str, Any]) -> None:
        from backend.runner.store import _history_payload

        payload = _history_payload(entry)
        sid = payload["script_id"]
        if not sid:
            return
        blob = json.dumps(payload)
        pipe = self._client.pipeline()
        pipe.lpush(_PREFIX + "history", blob)
        pipe.ltrim(_PREFIX + "history", 0, _HISTORY_GLOBAL_CAP - 1)
        pipe.lpush(_PREFIX + "history:" + sid, blob)
        pipe.ltrim(_PREFIX + "history:" + sid, 0, _HISTORY_PER_SCRIPT_CAP - 1)
        pipe.execute()

    def list_runs(self, script_id: str | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 500))
        key = _PREFIX + ("history:" + script_id if script_id else "history")
        rows = self._client.lrange(key, 0, limit - 1)
        return [json.loads(r) for r in rows]

    # --- tick lock ----------------------------------------------------------

    def acquire_tick_lock(self) -> Any | None:
        """``SET NX EX`` token across replicas. ``None`` = another tick holds it."""
        from backend.runner import poll_seconds

        token = f"{os.getpid()}-{time.time_ns()}"
        ttl = max(120, int(poll_seconds() * 2))
        ok = self._client.set(_PREFIX + "ticklock", token, nx=True, ex=ttl)
        if not ok:
            return None
        return _RedisTickLock(self._client, token)


class _RedisTickLock:
    """Tick lock held via a Redis token with an expiry safety net."""

    def __init__(self, client: Any, token: str) -> None:
        self._client = client
        self._token = token
        self._key = _PREFIX + "ticklock"

    def release(self) -> None:
        # GET + DEL (no Lua): the expiry bounds any race, and ticks are
        # idempotent thanks to the last_bar_time skip.
        try:
            if self._client.get(self._key) == self._token:
                self._client.delete(self._key)
        except Exception:
            pass
