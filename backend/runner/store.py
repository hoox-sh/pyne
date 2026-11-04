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

"""Registry for deployed runner scripts, cron state, and run history.

Backend selection via ``PYNE_RUNNER_STORE_BACKEND`` (case-insensitive):

* ``sqlite`` (default) — local SQLite file (``PYNE_RUNNER_DB``), single host.
  Ticks serialize with a flock next to the database.
* ``redis`` — shared Redis (``REDIS_URL``, required) so several API replicas
  see the same scripts; ticks serialize with a ``SET NX`` token instead of
  flock. See :mod:`backend.runner.store_redis`.

Every public function dispatches on the backend. The SQLite implementation is
the ``_sqlite_*`` family; the Redis store is imported lazily so the ``redis``
package is only required when an operator actually selects that backend.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time

from typing import Any


_SCRIPT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_VALID_MODES = frozenset({"interpret", "compile", "auto"})
_MAX_SCRIPT = 100_000
_TF_OK = frozenset(
    {
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1M",
    }
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scripts (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    script        TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    timeframe     TEXT NOT NULL,
    mode          TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    data_source   TEXT NOT NULL DEFAULT 'mock',
    data_options  TEXT NOT NULL DEFAULT '{}',
    period        TEXT NOT NULL DEFAULT '6mo',
    max_bars      INTEGER NOT NULL DEFAULT 5000,
    webhook_url   TEXT NOT NULL DEFAULT '',
    forward_alerts INTEGER NOT NULL DEFAULT 1,
    alert_last_bar INTEGER NOT NULL DEFAULT 1,
    alert_batch   INTEGER NOT NULL DEFAULT 1,
    inputs        TEXT NOT NULL DEFAULT '{}',
    libraries     TEXT NOT NULL DEFAULT '[]',
    updated_at    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cron_state (
    script_id            TEXT PRIMARY KEY,
    last_bar_time        INTEGER NOT NULL DEFAULT 0,
    last_run_at          INTEGER NOT NULL DEFAULT 0,
    last_status          TEXT NOT NULL DEFAULT '',
    last_error           TEXT NOT NULL DEFAULT '',
    last_alerts          INTEGER NOT NULL DEFAULT 0,
    last_events          INTEGER NOT NULL DEFAULT 0,
    consecutive_errors   INTEGER NOT NULL DEFAULT 0,
    next_due_at          INTEGER NOT NULL DEFAULT 0,
    last_forward_status  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS run_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id     TEXT NOT NULL,
    ts            INTEGER NOT NULL,
    status        TEXT NOT NULL,
    reason        TEXT NOT NULL DEFAULT '',
    last_bar_time INTEGER NOT NULL DEFAULT 0,
    mode          TEXT NOT NULL DEFAULT '',
    alerts        INTEGER NOT NULL DEFAULT 0,
    events        INTEGER NOT NULL DEFAULT 0,
    error         TEXT NOT NULL DEFAULT '',
    forward_status TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_run_history_script ON run_history(script_id, id DESC);
"""

# Columns added to ``cron_state`` after the first release; existing databases
# get them via ALTER TABLE (CREATE TABLE IF NOT EXISTS cannot evolve a table).
_CRON_STATE_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("consecutive_errors", "ALTER TABLE cron_state ADD COLUMN consecutive_errors INTEGER NOT NULL DEFAULT 0"),
    ("next_due_at", "ALTER TABLE cron_state ADD COLUMN next_due_at INTEGER NOT NULL DEFAULT 0"),
    ("last_forward_status", "ALTER TABLE cron_state ADD COLUMN last_forward_status TEXT NOT NULL DEFAULT ''"),
)

# Runs kept per script in ``run_history`` (routine no_new_bar / not_due
# skips are not recorded, so this is runs that did something).
_HISTORY_PER_SCRIPT = 100

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

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_path: str | None = None
_redis_store_obj: Any | None = None


def reset_store() -> None:
    """Drop the process connection and cached backend (tests)."""
    global _conn, _path, _redis_store_obj
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
        _path = None
    _redis_store_obj = None


def _connect() -> sqlite3.Connection:
    global _conn, _path
    from backend.runner import db_path

    path = db_path()
    with _lock:
        if _conn is not None and _path == path:
            return _conn
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        parent = os.path.dirname(path)
        if parent and parent not in {".", ""} and path != ":memory:":
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error:
            pass
        conn.executescript(_SCHEMA)
        _migrate(conn)
        _conn = conn
        _path = path
        return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was first created."""
    try:
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(cron_state)")}
    except sqlite3.Error:
        return
    for col, ddl in _CRON_STATE_MIGRATIONS:
        if col in cols:
            continue
        try:
            conn.execute(ddl)
        except sqlite3.Error:
            pass


def validate_script_id(script_id: str) -> str | None:
    """Return an error string, or None when *script_id* is usable."""
    if not _SCRIPT_ID_RE.match(script_id or ""):
        return "id must be 1-64 chars of [A-Za-z0-9._-]"
    return None


def normalized_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a deploy body. Raises ``ValueError`` on bad input.

    The result is the canonical script-record shape shared by every backend.
    """
    script_id = str(record.get("id") or "").strip()
    err = validate_script_id(script_id)
    if err:
        raise ValueError(err)
    script = record.get("script")
    if not isinstance(script, str) or not script.strip():
        raise ValueError("Missing or invalid 'script'")
    if len(script) > _MAX_SCRIPT:
        raise ValueError(f"Script exceeds {_MAX_SCRIPT} character limit")
    mode = str(record.get("mode") or "auto").strip().lower()
    if mode not in _VALID_MODES:
        raise ValueError(f"Invalid mode {mode!r}; use interpret|compile|auto")
    timeframe = str(record.get("timeframe") or "1d").strip()
    if timeframe not in _TF_OK:
        raise ValueError(f"Invalid timeframe {timeframe!r}")
    symbol = str(record.get("symbol") or "BTCUSDT").strip() or "BTCUSDT"
    if len(symbol) > 32:
        raise ValueError("symbol too long")
    try:
        max_bars = int(record.get("max_bars") or 5000)
    except (TypeError, ValueError) as exc:
        raise ValueError("'max_bars' must be an integer") from exc
    if max_bars < 50 or max_bars > 100_000:
        raise ValueError("'max_bars' must be between 50 and 100000")
    data_source = str(record.get("data_source") or "mock").strip().lower() or "mock"
    data_options = record.get("data_options") if isinstance(record.get("data_options"), dict) else {}
    inputs = record.get("inputs") if isinstance(record.get("inputs"), dict) else {}
    libraries = record.get("libraries") if isinstance(record.get("libraries"), list) else []
    webhook = str(record.get("webhook_url") or "").strip()
    return {
        "id": script_id,
        "name": str(record.get("name") or script_id),
        "script": script,
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": mode,
        "enabled": bool(record.get("enabled", True)),
        "data_source": data_source,
        "data_options": data_options,
        "period": str(record.get("period") or "6mo"),
        "max_bars": max_bars,
        "webhook_url": webhook,
        "forward_alerts": bool(record.get("forward_alerts", True)),
        "alert_last_bar": bool(record.get("alert_last_bar", True)),
        "alert_batch": bool(record.get("alert_batch", True)),
        "inputs": inputs,
        "libraries": libraries,
        "updated_at": int(time.time() * 1000),
    }


def _cron_payload(script_id: str, merged: dict[str, Any]) -> dict[str, Any]:
    """Coerce a merged cron-state dict into the canonical stored shape."""
    return {
        "last_bar_time": int(merged.get("last_bar_time") or 0),
        "last_run_at": int(merged.get("last_run_at") or 0),
        "last_status": str(merged.get("last_status") or ""),
        "last_error": str(merged.get("last_error") or "")[:500],
        "last_alerts": int(merged.get("last_alerts") or 0),
        "last_events": int(merged.get("last_events") or 0),
        "consecutive_errors": int(merged.get("consecutive_errors") or 0),
        "next_due_at": int(merged.get("next_due_at") or 0),
        "last_forward_status": str(merged.get("last_forward_status") or "")[:200],
    }


def _history_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """Coerce one run into the canonical history-record shape."""
    return {
        "script_id": str(entry.get("script_id") or ""),
        "ts": int(entry.get("ts") or time.time() * 1000),
        "status": str(entry.get("status") or "")[:32],
        "reason": str(entry.get("reason") or "")[:64],
        "last_bar_time": int(entry.get("last_bar_time") or 0),
        "mode": str(entry.get("mode") or "")[:16],
        "alerts": int(entry.get("alerts") or 0),
        "events": int(entry.get("events") or 0),
        "error": str(entry.get("error") or "")[:500],
        "forward_status": str(entry.get("forward_status") or "")[:200],
    }


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _backend_store() -> Any | None:
    """Redis store singleton when ``PYNE_RUNNER_STORE_BACKEND=redis``, else None."""
    global _redis_store_obj
    from backend.runner import store_backend

    if store_backend() != "redis":
        return None
    if _redis_store_obj is None:
        from backend.runner.store_redis import RunnerRedisStore

        url = os.environ.get("REDIS_URL", "").strip()
        if not url:
            raise RuntimeError("PYNE_RUNNER_STORE_BACKEND=redis requires REDIS_URL to be set")
        _redis_store_obj = RunnerRedisStore(url=url)
    return _redis_store_obj


# ---------------------------------------------------------------------------
# Tick lock (flock for SQLite, SET NX token for Redis)
# ---------------------------------------------------------------------------


class _SqliteTickLock:
    """Exclusive flock held for one full tick."""

    def __init__(self, fh: Any) -> None:
        self._fh = fh

    def release(self) -> None:
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self._fh.close()
        except Exception:
            pass


def acquire_tick_lock() -> Any | None:
    """Serialize one tick across workers / replicas. ``None`` = already held."""
    backend = _backend_store()
    if backend is not None:
        return backend.acquire_tick_lock()
    try:
        fh = open(_flock_path(), "a+b")
    except OSError:
        return None
    try:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            fh.close()
        except Exception:
            pass
        return None
    return _SqliteTickLock(fh)


def _flock_path() -> str:
    from backend.runner import db_path

    path = db_path()
    if path == ":memory:":
        return os.path.join(os.environ.get("TMPDIR", "/tmp"), "pyne_runner.lock")
    return path + ".lock"


# ---------------------------------------------------------------------------
# Public facade (dispatches on the backend)
# ---------------------------------------------------------------------------


def put_script(record: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace a deployed script. Raises ValueError on bad input."""
    stored = normalized_record(record)
    backend = _backend_store()
    if backend is not None:
        return backend.put_script(stored)
    return _sqlite_put_script(stored)


def get_script(script_id: str, *, include_source: bool = True) -> dict[str, Any] | None:
    backend = _backend_store()
    if backend is not None:
        return backend.get_script(script_id, include_source=include_source)
    return _sqlite_get_script(script_id, include_source=include_source)


def delete_script(script_id: str) -> bool:
    backend = _backend_store()
    if backend is not None:
        return backend.delete_script(script_id)
    return _sqlite_delete_script(script_id)


def list_scripts(*, include_source: bool = False) -> list[dict[str, Any]]:
    backend = _backend_store()
    if backend is not None:
        return backend.list_scripts(include_source=include_source)
    return _sqlite_list_scripts(include_source=include_source)


def list_enabled() -> list[dict[str, Any]]:
    backend = _backend_store()
    if backend is not None:
        return backend.list_enabled()
    return _sqlite_list_enabled()


def set_enabled(script_id: str, *, enabled: bool) -> bool:
    backend = _backend_store()
    if backend is not None:
        return backend.set_enabled(script_id, enabled=enabled)
    return _sqlite_set_enabled(script_id, enabled=enabled)


def get_cron_state(script_id: str) -> dict[str, Any]:
    backend = _backend_store()
    if backend is not None:
        return backend.get_cron_state(script_id)
    return _sqlite_get_cron_state(script_id)


def put_cron_state(script_id: str, state: dict[str, Any]) -> None:
    """Merge *state* into the cron row for *script_id*.

    Missing keys keep their stored value (so a partial patch such as
    ``{"last_status": "error"}`` no longer wipes ``last_bar_time``).
    ``last_run_at`` always advances to now unless the caller pins it.
    """
    backend = _backend_store()
    if backend is not None:
        backend.put_cron_state(script_id, state)
        return
    _sqlite_put_cron_state(script_id, state)


def record_run(entry: dict[str, Any]) -> None:
    """Append one run to history and prune per-script rows (backend-specific)."""
    backend = _backend_store()
    if backend is not None:
        backend.record_run(entry)
        return
    _sqlite_record_run(entry)


def list_runs(script_id: str | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    """Recent history rows, newest first (optionally one script)."""
    backend = _backend_store()
    if backend is not None:
        return backend.list_runs(script_id, limit=limit)
    return _sqlite_list_runs(script_id, limit=limit)


# ---------------------------------------------------------------------------
# SQLite implementation (default backend)
# ---------------------------------------------------------------------------


def _row_to_script(row: sqlite3.Row, *, include_source: bool) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "id": row["id"],
        "name": row["name"],
        "symbol": row["symbol"],
        "timeframe": row["timeframe"],
        "mode": row["mode"],
        "enabled": bool(row["enabled"]),
        "data_source": row["data_source"],
        "data_options": json.loads(row["data_options"] or "{}"),
        "period": row["period"],
        "max_bars": int(row["max_bars"]),
        "webhook_url": row["webhook_url"] or "",
        "forward_alerts": bool(row["forward_alerts"]),
        "alert_last_bar": bool(row["alert_last_bar"]),
        "alert_batch": bool(row["alert_batch"]),
        "inputs": json.loads(row["inputs"] or "{}"),
        "libraries": json.loads(row["libraries"] or "[]"),
        "updated_at": int(row["updated_at"]),
    }
    if include_source:
        rec["script"] = row["script"]
    return rec


def _sqlite_put_script(stored: dict[str, Any]) -> dict[str, Any]:
    sql = {
        "id": stored["id"],
        "name": stored["name"],
        "script": stored["script"],
        "symbol": stored["symbol"],
        "timeframe": stored["timeframe"],
        "mode": stored["mode"],
        "enabled": 1 if stored["enabled"] else 0,
        "data_source": stored["data_source"],
        "data_options": json.dumps(stored["data_options"]),
        "period": stored["period"],
        "max_bars": stored["max_bars"],
        "webhook_url": stored["webhook_url"],
        "forward_alerts": 1 if stored["forward_alerts"] else 0,
        "alert_last_bar": 1 if stored["alert_last_bar"] else 0,
        "alert_batch": 1 if stored["alert_batch"] else 0,
        "inputs": json.dumps(stored["inputs"]),
        "libraries": json.dumps(stored["libraries"]),
        "updated_at": stored["updated_at"],
    }
    conn = _connect()
    with _lock:
        conn.execute(
            """
            INSERT INTO scripts (
                id, name, script, symbol, timeframe, mode, enabled,
                data_source, data_options, period, max_bars, webhook_url,
                forward_alerts, alert_last_bar, alert_batch, inputs, libraries,
                updated_at
            ) VALUES (
                :id, :name, :script, :symbol, :timeframe, :mode, :enabled,
                :data_source, :data_options, :period, :max_bars, :webhook_url,
                :forward_alerts, :alert_last_bar, :alert_batch, :inputs, :libraries,
                :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                script=excluded.script,
                symbol=excluded.symbol,
                timeframe=excluded.timeframe,
                mode=excluded.mode,
                enabled=excluded.enabled,
                data_source=excluded.data_source,
                data_options=excluded.data_options,
                period=excluded.period,
                max_bars=excluded.max_bars,
                webhook_url=excluded.webhook_url,
                forward_alerts=excluded.forward_alerts,
                alert_last_bar=excluded.alert_last_bar,
                alert_batch=excluded.alert_batch,
                inputs=excluded.inputs,
                libraries=excluded.libraries,
                updated_at=excluded.updated_at
            """,
            sql,
        )
    return _sqlite_get_script(stored["id"], include_source=True) or {}


def _sqlite_get_script(script_id: str, *, include_source: bool = True) -> dict[str, Any] | None:
    if validate_script_id(script_id):
        return None
    conn = _connect()
    with _lock:
        row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
    if row is None:
        return None
    return _row_to_script(row, include_source=include_source)


def _sqlite_delete_script(script_id: str) -> bool:
    if validate_script_id(script_id):
        return False
    conn = _connect()
    with _lock:
        cur = conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        conn.execute("DELETE FROM cron_state WHERE script_id = ?", (script_id,))
        conn.execute("DELETE FROM run_history WHERE script_id = ?", (script_id,))
        return cur.rowcount > 0


def _sqlite_list_scripts(*, include_source: bool = False) -> list[dict[str, Any]]:
    conn = _connect()
    with _lock:
        rows = conn.execute("SELECT * FROM scripts ORDER BY id").fetchall()
    return [_row_to_script(r, include_source=include_source) for r in rows]


def _sqlite_list_enabled() -> list[dict[str, Any]]:
    conn = _connect()
    with _lock:
        rows = conn.execute("SELECT * FROM scripts WHERE enabled = 1 ORDER BY id").fetchall()
    return [_row_to_script(r, include_source=True) for r in rows]


def _sqlite_set_enabled(script_id: str, *, enabled: bool) -> bool:
    if validate_script_id(script_id):
        return False
    conn = _connect()
    with _lock:
        cur = conn.execute(
            "UPDATE scripts SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, int(time.time() * 1000), script_id),
        )
        return cur.rowcount > 0


def _sqlite_get_cron_state(script_id: str) -> dict[str, Any]:
    conn = _connect()
    with _lock:
        row = conn.execute("SELECT * FROM cron_state WHERE script_id = ?", (script_id,)).fetchone()
    if row is None:
        return {"script_id": script_id, **_CRON_DEFAULTS}
    return dict(row)


def _sqlite_put_cron_state(script_id: str, state: dict[str, Any]) -> None:
    conn = _connect()
    merged = _sqlite_get_cron_state(script_id)
    merged.update({k: v for k, v in state.items() if k != "script_id"})
    payload = {"script_id": script_id, **_cron_payload(script_id, merged)}
    payload["last_run_at"] = int(state.get("last_run_at") or time.time() * 1000)
    with _lock:
        conn.execute(
            """
            INSERT INTO cron_state (
                script_id, last_bar_time, last_run_at, last_status,
                last_error, last_alerts, last_events, consecutive_errors,
                next_due_at, last_forward_status
            ) VALUES (
                :script_id, :last_bar_time, :last_run_at, :last_status,
                :last_error, :last_alerts, :last_events, :consecutive_errors,
                :next_due_at, :last_forward_status
            )
            ON CONFLICT(script_id) DO UPDATE SET
                last_bar_time=excluded.last_bar_time,
                last_run_at=excluded.last_run_at,
                last_status=excluded.last_status,
                last_error=excluded.last_error,
                last_alerts=excluded.last_alerts,
                last_events=excluded.last_events,
                consecutive_errors=excluded.consecutive_errors,
                next_due_at=excluded.next_due_at,
                last_forward_status=excluded.last_forward_status
            """,
            payload,
        )


def _sqlite_record_run(entry: dict[str, Any]) -> None:
    conn = _connect()
    payload = _history_payload(entry)
    if not payload["script_id"]:
        return
    with _lock:
        conn.execute(
            """
            INSERT INTO run_history (
                script_id, ts, status, reason, last_bar_time, mode,
                alerts, events, error, forward_status
            ) VALUES (
                :script_id, :ts, :status, :reason, :last_bar_time, :mode,
                :alerts, :events, :error, :forward_status
            )
            """,
            payload,
        )
        conn.execute(
            """
            DELETE FROM run_history WHERE script_id = :sid AND id NOT IN (
                SELECT id FROM run_history WHERE script_id = :sid
                ORDER BY id DESC LIMIT :keep
            )
            """,
            {"sid": payload["script_id"], "keep": _HISTORY_PER_SCRIPT},
        )


def _sqlite_list_runs(script_id: str | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
    conn = _connect()
    limit = max(1, min(int(limit or 50), 500))
    with _lock:
        if script_id:
            rows = conn.execute(
                "SELECT * FROM run_history WHERE script_id = ? ORDER BY id DESC LIMIT ?",
                (script_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM run_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]
