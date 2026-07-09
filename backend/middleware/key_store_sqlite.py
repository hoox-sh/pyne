# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""SQLite-backed API key store.

Used as the default persistent backend for ``APIKeyStore`` when running the
backend with more than one gunicorn worker. Schema:

    CREATE TABLE api_keys (
        key_hash TEXT PRIMARY KEY,        -- SHA-256 hex of the raw key
        key_id TEXT NOT NULL UNIQUE,
        tier TEXT NOT NULL,
        calls_used INTEGER NOT NULL DEFAULT 0,
        calls_limit INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        last_used REAL NOT NULL DEFAULT 0
    );

Thread-safety: ``sqlite3`` connections are guarded by a ``threading.Lock``.
WAL journal mode is enabled so multiple worker processes (each with their own
connection) can read concurrently while one writes.

We do not store the raw API key — only its SHA-256 hash. A leaked DB file
exposes identifiers, tiers, and call counts, but not the keys themselves.
"""

from __future__ import annotations

import sqlite3
import threading
import time

from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash    TEXT PRIMARY KEY,
    key_id      TEXT NOT NULL UNIQUE,
    tier        TEXT NOT NULL,
    calls_used  INTEGER NOT NULL DEFAULT 0,
    calls_limit INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    last_used   REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id);
"""


class SQLiteKeyStore:
    """Thread-safe SQLite-backed key store.

    Args:
        path: SQLite file path, or ``":memory:"`` for an in-process DB (useful
            for tests). Defaults to a process-local file under
            ``$TMPDIR/pynescript_keys.db`` so dev runs share state.
    """

    def __init__(self, path: str = ":memory:") -> None:
        self._path = path
        # check_same_thread=False lets gunicorn worker threads share the
        # connection; the lock below serialises writes.
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # WAL mode is a no-op for in-memory DBs; guard with the path.
            if self._path != ":memory:":
                try:
                    self._conn.execute("PRAGMA journal_mode=WAL")
                    self._conn.execute("PRAGMA synchronous=NORMAL")
                except sqlite3.DatabaseError:
                    # Some filesystems don't support WAL; fall back to default.
                    pass

    def create(self, key_id: str, key_hash: str, tier: str, calls_limit: int | float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO api_keys (key_hash, key_id, tier, calls_used, calls_limit, created_at, last_used)"
                " VALUES (?, ?, ?, 0, ?, ?, 0)",
                (key_hash, key_id, tier, calls_limit, time.time()),
            )

    def get_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT key_id, key_hash, tier, calls_used, calls_limit, created_at, last_used"
                " FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()
        if row is None:
            return None
        return {
            "key_id": row[0],
            "key_hash": row[1],
            "tier": row[2],
            "calls_used": row[3],
            "calls_limit": row[4],
            "created_at": row[5],
            "last_used": row[6],
        }

    def get_by_id(self, key_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT key_id, key_hash, tier, calls_used, calls_limit, created_at, last_used"
                " FROM api_keys WHERE key_id = ?",
                (key_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "key_id": row[0],
            "key_hash": row[1],
            "tier": row[2],
            "calls_used": row[3],
            "calls_limit": row[4],
            "created_at": row[5],
            "last_used": row[6],
        }

    def delete_by_hash(self, key_hash: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM api_keys WHERE key_hash = ?", (key_hash,))
            return cur.rowcount > 0

    def update_calls(self, key_id: str, calls_used: int, last_used: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE api_keys SET calls_used = ?, last_used = ? WHERE key_id = ?",
                (calls_used, last_used, key_id),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
