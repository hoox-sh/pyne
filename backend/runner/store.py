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

"""SQLite registry for deployed runner scripts and cron state."""

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
    script_id     TEXT PRIMARY KEY,
    last_bar_time INTEGER NOT NULL DEFAULT 0,
    last_run_at   INTEGER NOT NULL DEFAULT 0,
    last_status   TEXT NOT NULL DEFAULT '',
    last_error    TEXT NOT NULL DEFAULT '',
    last_alerts   INTEGER NOT NULL DEFAULT 0,
    last_events   INTEGER NOT NULL DEFAULT 0
);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_path: str | None = None


def reset_store() -> None:
    """Drop the process connection (tests)."""
    global _conn, _path
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
        _path = None


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
        _conn = conn
        _path = path
        return conn


def validate_script_id(script_id: str) -> str | None:
    """Return an error string, or None when *script_id* is usable."""
    if not _SCRIPT_ID_RE.match(script_id or ""):
        return "id must be 1-64 chars of [A-Za-z0-9._-]"
    return None


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


def put_script(record: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace a deployed script. Raises ValueError on bad input."""
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
    stored = {
        "id": script_id,
        "name": str(record.get("name") or script_id),
        "script": script,
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": mode,
        "enabled": 1 if record.get("enabled", True) else 0,
        "data_source": data_source,
        "data_options": json.dumps(data_options),
        "period": str(record.get("period") or "6mo"),
        "max_bars": max_bars,
        "webhook_url": webhook,
        "forward_alerts": 1 if record.get("forward_alerts", True) else 0,
        "alert_last_bar": 1 if record.get("alert_last_bar", True) else 0,
        "alert_batch": 1 if record.get("alert_batch", True) else 0,
        "inputs": json.dumps(inputs),
        "libraries": json.dumps(libraries),
        "updated_at": int(time.time() * 1000),
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
            stored,
        )
    return get_script(script_id, include_source=True) or {}


def get_script(script_id: str, *, include_source: bool = True) -> dict[str, Any] | None:
    if validate_script_id(script_id):
        return None
    conn = _connect()
    with _lock:
        row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
    if row is None:
        return None
    return _row_to_script(row, include_source=include_source)


def delete_script(script_id: str) -> bool:
    if validate_script_id(script_id):
        return False
    conn = _connect()
    with _lock:
        cur = conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        conn.execute("DELETE FROM cron_state WHERE script_id = ?", (script_id,))
        return cur.rowcount > 0


def list_scripts(*, include_source: bool = False) -> list[dict[str, Any]]:
    conn = _connect()
    with _lock:
        rows = conn.execute("SELECT * FROM scripts ORDER BY id").fetchall()
    return [_row_to_script(r, include_source=include_source) for r in rows]


def list_enabled() -> list[dict[str, Any]]:
    conn = _connect()
    with _lock:
        rows = conn.execute("SELECT * FROM scripts WHERE enabled = 1 ORDER BY id").fetchall()
    return [_row_to_script(r, include_source=True) for r in rows]


def set_enabled(script_id: str, *, enabled: bool) -> bool:
    if validate_script_id(script_id):
        return False
    conn = _connect()
    with _lock:
        cur = conn.execute(
            "UPDATE scripts SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, int(time.time() * 1000), script_id),
        )
        return cur.rowcount > 0


def get_cron_state(script_id: str) -> dict[str, Any]:
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT * FROM cron_state WHERE script_id = ?", (script_id,)
        ).fetchone()
    if row is None:
        return {
            "script_id": script_id,
            "last_bar_time": 0,
            "last_run_at": 0,
            "last_status": "",
            "last_error": "",
            "last_alerts": 0,
            "last_events": 0,
        }
    return dict(row)


def put_cron_state(script_id: str, state: dict[str, Any]) -> None:
    conn = _connect()
    payload = {
        "script_id": script_id,
        "last_bar_time": int(state.get("last_bar_time") or 0),
        "last_run_at": int(state.get("last_run_at") or time.time() * 1000),
        "last_status": str(state.get("last_status") or ""),
        "last_error": str(state.get("last_error") or "")[:500],
        "last_alerts": int(state.get("last_alerts") or 0),
        "last_events": int(state.get("last_events") or 0),
    }
    with _lock:
        conn.execute(
            """
            INSERT INTO cron_state (
                script_id, last_bar_time, last_run_at, last_status,
                last_error, last_alerts, last_events
            ) VALUES (
                :script_id, :last_bar_time, :last_run_at, :last_status,
                :last_error, :last_alerts, :last_events
            )
            ON CONFLICT(script_id) DO UPDATE SET
                last_bar_time=excluded.last_bar_time,
                last_run_at=excluded.last_run_at,
                last_status=excluded.last_status,
                last_error=excluded.last_error,
                last_alerts=excluded.last_alerts,
                last_events=excluded.last_events
            """,
            payload,
        )
