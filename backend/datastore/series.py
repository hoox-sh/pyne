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

"""Persistent OHLCV series store for the PYNE Pro data plane.

Bars are kept per canonical series key in SQLite under ``PYNE_DATA_DIR``
(default ``data/``). The key is ``exchange|market|SYMBOL|interval``, for example
``binance|spot|BTC/USDT|1h``. Upserts are keyed by unix-second ``time`` and the
later write wins. Wire contract: ``docs/devops/engine-owned-data-plane.mdx``.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
import threading
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_DATA_DIR = "data"
DB_FILENAME = "ohlcv.sqlite3"
DEFAULT_MARKET = "spot"
MARKETS = ("spot", "swap", "future")
# AXIS UI uses linear/inverse; CCXT and this store use swap/future.
MARKET_ALIASES = {
    "spot": "spot",
    "swap": "swap",
    "future": "future",
    "linear": "swap",
    "usdt-m": "swap",
    "usdm": "swap",
    "futures": "swap",
    "inverse": "future",
    "coin-m": "future",
    "coinm": "future",
    "delivery": "future",
}
MAX_PROVIDE_BARS = 5000
DEFAULT_HISTORY_BARS = 5000
MAX_HISTORY_BARS = 100000
DEFAULT_WINDOW_LIMIT = 10000
MAX_WINDOW_LIMIT = 100000
# Retention ceiling per series: 2x the largest legit window (100k). A runaway
# backfill or a chatty client must not grow a series without bound.
MAX_SERIES_BARS = 200_000
MAX_SOURCE_LEN = 64

# Bind-parameter chunk size; stays well under SQLite's variable limit.
_CHUNK = 500
# A value at or above this is milliseconds (or later), not unix seconds.
_UNIX_SECONDS_LIMIT = 100_000_000_000
_OHLCV_FIELDS = ("open", "high", "low", "close", "volume")
_INTERVAL_RE = re.compile(r"^([1-9][0-9]{0,4})([a-zA-Z])$")
_INTERVAL_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3_600, "d": 86_400, "w": 604_800, "M": 2_592_000}
_EXCHANGE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._:/-]{0,63}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    key        TEXT PRIMARY KEY,
    exchange   TEXT NOT NULL,
    market     TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    interval   TEXT NOT NULL,
    count      INTEGER NOT NULL DEFAULT 0,
    oldest     INTEGER,
    newest     INTEGER,
    updated_at INTEGER NOT NULL DEFAULT 0,
    source     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bars (
    key    TEXT NOT NULL,
    time   INTEGER NOT NULL,
    open   REAL NOT NULL,
    high   REAL NOT NULL,
    low    REAL NOT NULL,
    close  REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (key, time)
) WITHOUT ROWID;
"""

_UPSERT_BAR = """
INSERT INTO bars (key, time, open, high, low, close, volume)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(key, time) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume
"""

_UPSERT_SERIES = """
INSERT INTO series (key, exchange, market, symbol, interval, count, oldest, newest, updated_at, source)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    count = excluded.count,
    oldest = excluded.oldest,
    newest = excluded.newest,
    updated_at = excluded.updated_at,
    source = excluded.source
"""


class DataError(Exception):
    """A request-level failure with a stable wire ``code`` and HTTP ``status``."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def body(self) -> dict[str, Any]:
        return {"status": "error", "code": self.code, "message": self.message}


def now_seconds() -> int:
    """Wall clock in unix seconds. Patched in tests to pin forming-bar decisions."""
    return int(time.time())


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def canonical_interval(raw: Any) -> str:
    """AXIS interval code with the unit normalized (``1H`` → ``1h``; ``1M`` stays month)."""
    text = _text(raw)
    match = _INTERVAL_RE.match(text)
    if match is None:
        raise DataError("INVALID_INTERVAL", f"interval {text!r} is not a supported code such as 1m, 1h or 1d")
    count, unit = match.group(1), match.group(2)
    unit = unit if unit in ("M", "m") else unit.lower()
    if unit not in _INTERVAL_UNIT_SECONDS:
        raise DataError("INVALID_INTERVAL", f"interval {text!r} is not a supported code such as 1m, 1h or 1d")
    return f"{count}{unit}"


def interval_seconds(interval: str) -> int:
    """Length of one bar for a canonical interval code."""
    return int(interval[:-1]) * _INTERVAL_UNIT_SECONDS[interval[-1]]


@dataclass(frozen=True)
class SeriesKey:
    """Canonical identity of one stored series."""

    exchange: str
    market: str
    symbol: str
    interval: str

    @property
    def text(self) -> str:
        return f"{self.exchange}|{self.market}|{self.symbol}|{self.interval}"

    @property
    def interval_seconds(self) -> int:
        return interval_seconds(self.interval)

    def identity_matches(self, exchange: Any, symbol: Any) -> bool:
        """Whether a caller's exchange + symbol name this series (case-insensitive).

        Compact load-form (``BNBUSDT``) and pair-form (``BNB/USDT``) match so a
        journaled session created before AXIS unified keys still ticks.
        """
        if self.exchange != _text(exchange).lower():
            return False
        stored = _text(self.symbol).upper()
        incoming = _text(symbol).upper()
        if not stored or not incoming:
            return False
        return stored == incoming or stored.replace("/", "") == incoming.replace("/", "")


def make_key(exchange: Any, symbol: Any, interval: Any, market: Any = None) -> SeriesKey:
    """Build the canonical series key from raw request fields."""
    ex = _text(exchange).lower()
    if not ex:
        raise DataError("INVALID_KEY", "exchange is required")
    if _EXCHANGE_RE.match(ex) is None:
        raise DataError("INVALID_KEY", "exchange must be a CCXT id (letters, digits, - or _)")
    sym = _text(symbol).upper()
    if not sym:
        raise DataError("INVALID_KEY", "symbol is required")
    if _SYMBOL_RE.match(sym) is None:
        raise DataError("INVALID_KEY", "symbol must be a pair such as BTC/USDT")
    mkt = MARKET_ALIASES.get((_text(market) or DEFAULT_MARKET).lower())
    if mkt is None:
        raise DataError("INVALID_MARKET", f"market must be one of {', '.join(MARKETS)}")
    if not _text(interval):
        raise DataError("INVALID_KEY", "interval is required")
    return SeriesKey(exchange=ex, market=mkt, symbol=sym, interval=canonical_interval(interval))


def check_history_bars(raw: Any) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1 or raw > MAX_HISTORY_BARS:
        raise DataError(
            "INVALID_HISTORY_BARS",
            f"history_bars must be an integer between 1 and {MAX_HISTORY_BARS}",
        )
    return raw


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DataError("INVALID_BARS", f"{label} must be a finite number")
    return float(value)


def _bar_time(value: Any, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or float(value) != int(value)
    ):
        raise DataError("INVALID_BARS", f"{label}.time must be an integer unix timestamp in seconds")
    t = int(value)
    if t <= 0 or t >= _UNIX_SECONDS_LIMIT:
        raise DataError("INVALID_BARS", f"{label}.time must be unix seconds, got {t}")
    return t


def normalize_bars(raw: Any) -> list[dict[str, float | int]]:
    """Validate bars, dedupe by time (last occurrence wins), and sort ascending."""
    if not isinstance(raw, list):
        raise DataError("INVALID_BARS", "bars must be a list")
    by_time: dict[int, dict[str, float | int]] = {}
    for index, item in enumerate(raw):
        label = f"bars[{index}]"
        if not isinstance(item, dict):
            raise DataError("INVALID_BARS", f"{label} must be an object")
        t = _bar_time(item.get("time"), label)
        row: dict[str, float | int] = {"time": t}
        for field in _OHLCV_FIELDS:
            row[field] = _finite(item.get(field), f"{label}.{field}")
        by_time[t] = row
    return [by_time[t] for t in sorted(by_time)]


class SeriesStore:
    """SQLite-backed OHLCV series. One connection, guarded by a lock (WAL)."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None, timeout=30.0)
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}
        self._key_locks_guard = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)

    def key_lock(self, key_text: str) -> threading.Lock:
        """Per-series lock for fetch/tick sequences (not for the SQLite connection)."""
        with self._key_locks_guard:
            lock = self._key_locks.get(key_text)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[key_text] = lock
            return lock

    def status(self, key: SeriesKey) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT count, oldest, newest, updated_at FROM series WHERE key = ?",
                (key.text,),
            ).fetchone()
        if row is None:
            return {"key": key.text, "count": 0, "oldest": None, "newest": None, "updated_at": None}
        count, oldest, newest, updated_at = row
        return {"key": key.text, "count": int(count), "oldest": oldest, "newest": newest, "updated_at": updated_at}

    def provide(self, key: SeriesKey, bars: Any, source: str = "") -> dict[str, Any]:
        """Upsert bars by time. Returns counts and the refreshed series bounds.

        Series are retention-capped at :data:`MAX_SERIES_BARS`; the oldest
        bars are trimmed when a provide pushes a series over the ceiling.
        """
        rows = normalize_bars(bars)
        now = now_seconds()
        with self._lock:
            conn = self._conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._existing_times(key.text, [int(r["time"]) for r in rows])
                for start in range(0, len(rows), _CHUNK):
                    conn.executemany(
                        _UPSERT_BAR,
                        [
                            (key.text, r["time"], r["open"], r["high"], r["low"], r["close"], r["volume"])
                            for r in rows[start : start + _CHUNK]
                        ],
                    )
                self._trim_locked(key.text)
                state = self._refresh_series_row(key, source[:MAX_SOURCE_LEN], now)
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        updated = len(existing)
        return {"added": len(rows) - updated, "updated": updated, **state}

    def purge(self, key: SeriesKey) -> dict[str, Any]:
        """Drop every stored bar of one series (and its metadata row).

        The store is the engine's cache of the venue's OHLCV — a client that
        wants a clean slate (a dataset flush) drops the series it owns and
        re-uploads / re-fetches it. Other series are untouched: the cache is
        shared, so a purge is always per key.
        """
        with self._lock:
            conn = self._conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                count = int(conn.execute("SELECT COUNT(*) FROM bars WHERE key = ?", (key.text,)).fetchone()[0])
                conn.execute("DELETE FROM bars WHERE key = ?", (key.text,))
                conn.execute("DELETE FROM series WHERE key = ?", (key.text,))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return {"key": key.text, "removed": count}

    def _trim_locked(self, key_text: str) -> None:
        """Drop the oldest bars when a series exceeds ``MAX_SERIES_BARS``. Caller holds the lock."""
        count = int(self._conn.execute("SELECT COUNT(*) FROM bars WHERE key = ?", (key_text,)).fetchone()[0])
        if count <= MAX_SERIES_BARS:
            return
        cutoff = self._conn.execute(
            "SELECT time FROM bars WHERE key = ? ORDER BY time DESC LIMIT 1 OFFSET ?",
            (key_text, MAX_SERIES_BARS - 1),
        ).fetchone()
        if cutoff is None:
            return
        self._conn.execute("DELETE FROM bars WHERE key = ? AND time < ?", (key_text, int(cutoff[0])))

    def window(self, key: SeriesKey, limit: int) -> list[dict[str, float | int]]:
        """Newest ``limit`` bars, returned in ascending time order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT time, open, high, low, close, volume FROM bars WHERE key = ? ORDER BY time DESC LIMIT ?",
                (key.text, int(limit)),
            ).fetchall()
        return [
            {"time": int(t), "open": o, "high": h, "low": lo, "close": c, "volume": v}
            for t, o, h, lo, c, v in reversed(rows)
        ]

    def widest_gap(self, key: SeriesKey, step_s: int) -> tuple[int, int] | None:
        """The widest internal hole, as ``(bar_before, bar_after)``.

        ``step_s`` is one interval. A step of exactly one bar is not a hole.
        ``None`` when the series is empty or continuous.
        """
        if step_s <= 0:
            return None
        with self._lock:
            row = self._conn.execute(
                """
                WITH ordered AS (
                  SELECT time, LAG(time) OVER (ORDER BY time) AS prev
                  FROM bars WHERE key = ?
                )
                SELECT prev, time FROM ordered
                WHERE prev IS NOT NULL AND time - prev > ?
                ORDER BY (time - prev) DESC
                LIMIT 1
                """,
                (key.text, int(step_s)),
            ).fetchone()
        if row is None or row[0] is None:
            return None
        return int(row[0]), int(row[1])

    def holes(self, key: SeriesKey, step_s: int, *, limit: int = 8) -> list[tuple[int, int]]:
        """Every internal hole, oldest first, as ``(bar_before, bar_after)``.

        A *hole* is a jump of more than one interval between adjacent stored
        bars — minutes the series is missing in the middle. The bounds of the
        series are not holes (a shorter history is not a defect). Used by the
        background healer, which fills them one page at a time.
        """
        if step_s <= 0 or limit <= 0:
            return []
        with self._lock:
            rows = self._conn.execute(
                """
                WITH ordered AS (
                  SELECT time, LAG(time) OVER (ORDER BY time) AS prev
                  FROM bars WHERE key = ?
                )
                SELECT prev, time FROM ordered
                WHERE prev IS NOT NULL AND time - prev > ?
                ORDER BY time ASC
                LIMIT ?
                """,
                (key.text, int(step_s), int(limit)),
            ).fetchall()
        return [(int(prev), int(nxt)) for prev, nxt in rows if prev is not None]

    def active_keys(self, *, updated_since: int, limit: int = 50) -> list[SeriesKey]:
        """Series written since ``updated_since`` (unix seconds), newest first.

        The healer only touches series a client is actually using — a dormant
        series is not worth an upstream walk.
        """
        if limit <= 0:
            return []
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT exchange, market, symbol, interval FROM series
                WHERE count > 1 AND updated_at >= ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (int(updated_since), int(limit)),
            ).fetchall()
        return [SeriesKey(exchange=ex, market=mkt, symbol=sym, interval=iv) for ex, mkt, sym, iv in rows]

    def _existing_times(self, key_text: str, times: list[int]) -> set[int]:
        found: set[int] = set()
        for start in range(0, len(times), _CHUNK):
            chunk = times[start : start + _CHUNK]
            marks = ",".join("?" * len(chunk))
            # S608: only "?" placeholders are interpolated; values are bound.
            query = f"SELECT time FROM bars WHERE key = ? AND time IN ({marks})"  # noqa: S608
            for (t,) in self._conn.execute(query, (key_text, *chunk)):
                found.add(int(t))
        return found

    def _refresh_series_row(self, key: SeriesKey, source: str, now: int) -> dict[str, Any]:
        count, oldest, newest = self._conn.execute(
            "SELECT COUNT(*), MIN(time), MAX(time) FROM bars WHERE key = ?",
            (key.text,),
        ).fetchone()
        self._conn.execute(
            _UPSERT_SERIES,
            (key.text, key.exchange, key.market, key.symbol, key.interval, int(count), oldest, newest, now, source),
        )
        return {"key": key.text, "count": int(count), "oldest": oldest, "newest": newest, "updated_at": now}


_STORE_GUARD = threading.Lock()
_STORE: SeriesStore | None = None


def data_dir() -> Path:
    raw = os.environ.get("PYNE_DATA_DIR", "").strip()
    return Path(raw) if raw else Path(DEFAULT_DATA_DIR)


def get_store() -> SeriesStore:
    """Process-wide store under ``PYNE_DATA_DIR``; reopened if the directory changes."""
    global _STORE
    path = data_dir() / DB_FILENAME
    with _STORE_GUARD:
        if _STORE is None or _STORE.path != path:
            _STORE = SeriesStore(path)
        return _STORE
