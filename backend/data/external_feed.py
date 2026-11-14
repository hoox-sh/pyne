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

"""External market feed (AXIS / Cloudflare Worker) as the engine's bar source.

When ``PYNE_FEED_SOURCE=external`` the engine stops walking CCXT and is fed
bars by an external feed instead — the shared AXIS feed served by the CF
Worker at ``worker.axis.hoox.sh`` (``GET /api/feed`` snapshot,
``GET /api/feed/delta`` incremental). Bars fetched here land in the same
:class:`~backend.datastore.series.SeriesStore` the CCXT path writes to, so
every downstream consumer (``/data/series*``, ``/data/session*``, the live
session tick) is unchanged and cannot tell which source produced a bar.

Env:

- ``PYNE_FEED_SOURCE`` — ``internal`` (default) or ``external``.
- ``PYNE_FEED_URL`` — base URL of the feed, e.g. ``https://worker.axis.hoox.sh``.
  Required when ``PYNE_FEED_SOURCE=external``; without it every sync fails loudly
  (the engine does NOT silently fall back to CCXT — mixed sources would
  double-write the store).
- ``PYNE_FEED_API_KEY`` — optional bearer token, sent as ``Authorization: Bearer``.
- ``PYNE_FEED_POLL_S`` — poll interval for the background thread (default ``1.0``).
- ``PYNE_FEED_PROVIDE_LIMIT`` — max bars per snapshot/provide call (default ``1000``).

Market mapping (pyne → CF feed ``spot|linear|inverse``): ``swap`` and
``future`` both map to ``linear`` because the CF feed has no dated/perpetual
distinction yet and pyne has no inverse-swap distinction. ``linear`` and
``inverse`` pass through unchanged; anything else is rejected.

Wire contract (as implemented by the AXIS worker):

- ``GET {base}/api/feed?feed=<key>`` → ``200 {kind:"snapshot", feed, seq, from,
  to, bars:[{time,open,high,low,close,volume,closed}]}``. Bar ``time`` is unix
  **seconds**. ``closed`` marks a finalized bar.
- ``GET {base}/api/feed/delta?feed=<key>&after=<seq>`` → ``200 {seq, deltas:[
  {feed, seq, forming, upTo, times[], open[], high[], low[], close[], volume[]}]}``.
  ``delta_gone`` (HTTP 410, or a body whose ``error``/``code`` is ``delta_gone``
  or a truthy ``delta_gone`` flag) means the server no longer has the deltas
  after ``after`` — the caller must re-snapshot. That raises
  :class:`FeedResyncRequired`.

Sequence handling mirrors the PWA client (``src/engine/feed-client.ts``):
a duplicate delta seq is a no-op, a gap raises :class:`FeedResyncRequired`,
and any bar older than the current tip raises :class:`FeedResyncRequired`.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from backend.datastore import series as series_store
from backend.datastore.series import DataError
from backend.datastore.series import SeriesKey


logger = logging.getLogger(__name__)

HTTP_TIMEOUT_S = 5.0
SOURCE_EXTERNAL = "external-feed"
_HTTP_POLL_MIN_S = 0.2

# Market mapping pyne → CF feed. Anything outside this set is rejected.
_MARKET_MAP = {
    "spot": "spot",
    "swap": "linear",  # pyne perpetual swap ≈ CF "linear"
    "future": "linear",  # pyne dated future ≈ CF "linear" (no dated segment yet)
    "linear": "linear",
    "inverse": "inverse",
}


class FeedError(Exception):
    """Base class for external-feed failures."""


class FeedFetchError(FeedError):
    """The feed could not be reached or returned something unusable."""


class FeedResyncRequired(FeedError):
    """The delta stream is no longer applicable — caller must re-snapshot."""


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class ExternalFeedConfig:
    """Resolved ``PYNE_FEED_*`` environment."""

    source: str = "internal"
    url: str = ""
    api_key: str = ""
    poll_s: float = 1.0
    provide_limit: int = 1000

    @classmethod
    def from_env(cls) -> ExternalFeedConfig:
        return cls(
            source=(os.environ.get("PYNE_FEED_SOURCE", "internal").strip().lower() or "internal"),
            url=os.environ.get("PYNE_FEED_URL", "").strip().rstrip("/"),
            api_key=os.environ.get("PYNE_FEED_API_KEY", "").strip(),
            poll_s=_env_float("PYNE_FEED_POLL_S", 1.0),
            provide_limit=_env_int("PYNE_FEED_PROVIDE_LIMIT", 1000),
        )

    @property
    def enabled(self) -> bool:
        return self.source == "external"


def enabled() -> bool:
    """True when the process is configured for the external feed."""
    return ExternalFeedConfig.from_env().enabled


def canonical_feed_key(exchange: Any, market: Any, symbol: Any, interval: Any) -> str:
    """Map pyne identity to the CF feed key: ``venue|market|SYMBOL|interval|none|public``."""
    venue = str(exchange or "").strip().lower()
    if not venue:
        raise DataError("INVALID_KEY", "exchange is required")
    raw_market = str(market or "spot").strip().lower()
    mapped = _MARKET_MAP.get(raw_market)
    if mapped is None:
        raise DataError(
            "INVALID_MARKET",
            f"market {raw_market!r} cannot be mapped to an external feed market "
            f"(supported: {', '.join(sorted(_MARKET_MAP))})",
        )
    sym = str(symbol or "").strip().upper()
    if not sym:
        raise DataError("INVALID_KEY", "symbol is required")
    intv = str(interval or "").strip()
    if not intv:
        raise DataError("INVALID_KEY", "interval is required")
    return f"{venue}|{mapped}|{sym}|{intv}|none|public"


# ─── HTTP ────────────────────────────────────────────────────────────────────


def _request(cfg: ExternalFeedConfig, path: str) -> Any:
    if not cfg.url:
        raise FeedFetchError("PYNE_FEED_URL is not set (PYNE_FEED_SOURCE=external)")
    if not cfg.url.lower().startswith(("http://", "https://")):
        raise FeedFetchError("PYNE_FEED_URL must be an http(s) URL")
    headers = {
        "Accept": "application/json",
        # Cloudflare blocks python-urllib's default UA outright.
        "User-Agent": "pyne-feed-client/1.0 (+https://github.com/hoox-sh/pyne)",
    }
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    req = urllib.request.Request(f"{cfg.url}{path}", headers=headers)  # noqa: S310 - operator-configured http(s) feed URL
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310 - operator-configured http(s) feed URL
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 410:
            raise FeedResyncRequired("feed reports the requested delta is gone (HTTP 410)") from exc
        raise FeedFetchError(f"feed HTTP {exc.code} for {path}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedFetchError(f"feed request failed for {path}: {exc}") from exc
    try:
        return json.loads(body)
    except ValueError as exc:
        raise FeedFetchError(f"feed returned invalid JSON for {path}") from exc


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _num(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                raise FeedFetchError(f"{label} is not a number") from None
        else:
            raise FeedFetchError(f"{label} is not a number")
    out = float(value)
    if out != out or out in (float("inf"), float("-inf")):
        raise FeedFetchError(f"{label} is not finite")
    return out


def _norm_bar(item: Any, *, strict: bool) -> dict[str, Any] | None:
    try:
        if not isinstance(item, dict):
            raise FeedFetchError("bar is not an object")
        t = _num(item.get("time"), "time")
        if t != int(t) or t <= 0:
            raise FeedFetchError("time must be a positive integer (unix seconds)")
        bar = {
            "time": int(t),
            "open": _num(item.get("open"), "open"),
            "high": _num(item.get("high"), "high"),
            "low": _num(item.get("low"), "low"),
            "close": _num(item.get("close"), "close"),
            "volume": _num(item.get("volume"), "volume"),
            "closed": bool(item.get("closed", False)),
        }
    except FeedFetchError:
        if strict:
            raise
        return None
    return bar


def _fetch_snapshot_frame(cfg: ExternalFeedConfig, feed_key: str, limit: int) -> tuple[int, list[dict[str, Any]]]:
    """``GET {base}/api/feed?feed=<key>`` → ``(seq, bars)`` (oldest first)."""
    data = _request(cfg, f"/api/feed?feed={_quote(feed_key)}&limit={int(limit)}")
    if not isinstance(data, dict):
        raise FeedFetchError("snapshot response is not an object")
    raw_bars = data.get("bars")
    if not isinstance(raw_bars, list):
        raise FeedFetchError("snapshot response has no bars array")
    raw_seq = data.get("seq")
    seq = int(raw_seq) if isinstance(raw_seq, (int, float)) and not isinstance(raw_seq, bool) else 0
    bars = [b for b in (_norm_bar(item, strict=False) for item in raw_bars) if b is not None]
    bars.sort(key=lambda b: b["time"])
    limit = max(1, int(limit))
    return seq, bars[-limit:]


def fetch_snapshot(cfg: ExternalFeedConfig, feed_key: str, limit: int) -> list[dict[str, Any]]:
    """``GET {base}/api/feed?feed=<key>`` → normalized bars (oldest first)."""
    return _fetch_snapshot_frame(cfg, feed_key, limit)[1]


def _delta_gone(data: dict[str, Any]) -> bool:
    if data.get("delta_gone"):
        return True
    for field_name in ("error", "code", "reason"):
        value = data.get(field_name)
        if isinstance(value, str) and value.strip().lower() == "delta_gone":
            return True
    return False


def fetch_delta(cfg: ExternalFeedConfig, feed_key: str, after_seq: int) -> tuple[list[dict[str, Any]], int]:
    """``GET {base}/api/feed/delta?feed=<key>&after=<seq>``.

    Returns ``(deltas, new_seq)``. Raises :class:`FeedResyncRequired` when the
    server no longer has the deltas after ``after_seq``.
    """
    data = _request(cfg, f"/api/feed/delta?feed={_quote(feed_key)}&after={int(after_seq)}")
    if not isinstance(data, dict):
        raise FeedFetchError("delta response is not an object")
    if _delta_gone(data):
        raise FeedResyncRequired(f"feed {feed_key}: deltas after seq {after_seq} are gone")
    deltas = data.get("deltas")
    if deltas is None:
        deltas = []
    if not isinstance(deltas, list):
        raise FeedFetchError("delta response 'deltas' is not a list")
    raw_seq = data.get("seq")
    if isinstance(raw_seq, bool) or not isinstance(raw_seq, (int, float)):
        raw_seq = None
    new_seq = (
        int(raw_seq)
        if raw_seq is not None
        else (
            int(deltas[-1]["seq"])
            if deltas and isinstance(deltas[-1], dict) and isinstance(deltas[-1].get("seq"), int)
            else int(after_seq)
        )
    )
    return deltas, new_seq


# ─── Cursor ──────────────────────────────────────────────────────────────────


def _norm_delta(delta: Any) -> dict[str, Any]:
    """Validate one delta frame; raise :class:`FeedResyncRequired` if unusable."""
    if not isinstance(delta, dict):
        raise FeedResyncRequired("delta is not an object")
    seq = delta.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise FeedResyncRequired("delta seq must be a non-negative integer")
    forming = delta.get("forming")
    if not isinstance(forming, bool):
        raise FeedResyncRequired("delta.forming must be a boolean")
    times = delta.get("times")
    arrays: dict[str, list[Any]] = {}
    for name in ("open", "high", "low", "close", "volume"):
        value = delta.get(name)
        if not isinstance(value, list):
            raise FeedResyncRequired(f"delta.{name} must be a list")
        arrays[name] = value
    if not isinstance(times, list) or not times:
        raise FeedResyncRequired("delta.times must be a non-empty list")
    n = len(times)
    for name, value in arrays.items():
        if len(value) != n:
            raise FeedResyncRequired(f"delta.{name} length {len(value)} != times length {n}")
    norm_times: list[int] = []
    prev = 0
    for i, t in enumerate(times):
        try:
            tf = _num(t, f"times[{i}]")
        except FeedFetchError as exc:
            raise FeedResyncRequired(str(exc)) from exc
        if tf != int(tf) or tf <= 0:
            raise FeedResyncRequired(f"times[{i}] is not a positive integer")
        ti = int(tf)
        if i > 0 and ti <= prev:
            raise FeedResyncRequired("delta times are not strictly increasing")
        prev = ti
        norm_times.append(ti)
    out: dict[str, Any] = {"seq": seq, "forming": forming, "times": norm_times}
    for name, value in arrays.items():
        try:
            out[name] = [_num(v, f"{name}[{j}]") for j, v in enumerate(value)]
        except FeedFetchError as exc:
            raise FeedResyncRequired(str(exc)) from exc
    return out


@dataclass
class FeedCursor:
    """In-memory seq tracker + bar cache for one feed.

    Mirrors the TS client (``src/engine/feed-client.ts``): a forming bar at
    the tip is overwritten in place, strictly newer bars are appended, and
    anything older than the tip — or a seq gap — means the local state can no
    longer be trusted and a snapshot resync is required.
    """

    bars: list[dict[str, Any]] = field(default_factory=list)
    last_seq: int | None = None
    pending: list[dict[str, Any]] = field(default_factory=list)

    @property
    def initialized(self) -> bool:
        return self.last_seq is not None

    def reset(self) -> None:
        self.bars = []
        self.last_seq = None
        self.pending = []

    def take_pending(self) -> list[dict[str, Any]]:
        pending, self.pending = self.pending, []
        return pending

    def apply_snapshot(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(snapshot, dict):
            raise FeedResyncRequired("snapshot is not an object")
        seq = snapshot.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise FeedResyncRequired("snapshot seq must be a non-negative integer")
        raw_bars = snapshot.get("bars")
        if not isinstance(raw_bars, list):
            raise FeedResyncRequired("snapshot has no bars array")
        bars = [b for b in (_norm_bar(item, strict=False) for item in raw_bars) if b is not None]
        bars.sort(key=lambda b: b["time"])
        # Last write wins on duplicate times.
        deduped: dict[int, dict[str, Any]] = {}
        for bar in bars:
            deduped[bar["time"]] = bar
        self.bars = [deduped[t] for t in sorted(deduped)]
        self.last_seq = seq
        self.pending = list(self.bars)
        return list(self.bars)

    def apply_delta(self, delta: dict[str, Any]) -> list[dict[str, Any]]:
        norm = _norm_delta(delta)
        seq = norm["seq"]
        if self.last_seq is not None:
            if seq <= self.last_seq:
                # Duplicate delivery — idempotent no-op.
                return list(self.bars)
            if seq > self.last_seq + 1:
                raise FeedResyncRequired(f"seq gap: have {self.last_seq}, got {seq}")

        times = norm["times"]
        n = len(times)
        tip_time = self.bars[-1]["time"] if self.bars else None
        if tip_time is not None and times[0] < tip_time:
            raise FeedResyncRequired(f"delta starts at {times[0]}, before tip {tip_time}")

        changed: list[dict[str, Any]] = []
        for i in range(n):
            closed = (i < n - 1) or not norm["forming"]
            bar = {
                "time": times[i],
                "open": norm["open"][i],
                "high": norm["high"][i],
                "low": norm["low"][i],
                "close": norm["close"][i],
                "volume": norm["volume"][i],
                "closed": closed,
            }
            tip = self.bars[-1] if self.bars else None
            if tip is not None and bar["time"] == tip["time"]:
                if tip.get("closed"):
                    raise FeedResyncRequired(f"delta rewrites closed bar at {bar['time']}")
                self.bars[-1] = bar
            else:
                if tip is not None:
                    self.bars[-1] = {**tip, "closed": True}
                self.bars.append(bar)
            changed.append(bar)
        if self.bars:
            self.bars[-1] = {**self.bars[-1], "closed": not norm["forming"]}
        self.pending.extend(changed)
        self.last_seq = seq
        return list(self.bars)


# ─── Watch registry ──────────────────────────────────────────────────────────


@dataclass
class _Watch:
    series_key: SeriesKey
    cursor: FeedCursor = field(default_factory=FeedCursor)


_watches: dict[str, _Watch] = {}
_watches_lock = threading.Lock()

# Module-level observability for the background thread.
last_error: str | None = None
error_count: int = 0
last_sync_at: float | None = None


def _note_error(exc: BaseException | str) -> None:
    global last_error, error_count
    last_error = str(exc)
    error_count += 1


def register_watch(feed_key: str, series_key: Any) -> None:
    """Register (idempotently) a feed→series binding for the background poller.

    ``series_key`` may be a :class:`SeriesKey` or its ``exchange|market|SYMBOL|interval`` text.
    Re-registering keeps the existing cursor (no forced resync).
    """
    if isinstance(series_key, SeriesKey):
        sk = series_key
    else:
        parts = str(series_key).split("|")
        if len(parts) != 4:
            raise DataError("INVALID_KEY", f"cannot parse series key {series_key!r}")
        sk = SeriesKey(exchange=parts[0], market=parts[1], symbol=parts[2], interval=parts[3])
    with _watches_lock:
        if feed_key not in _watches:
            _watches[feed_key] = _Watch(series_key=sk)


def unregister_watch(feed_key: str) -> None:
    with _watches_lock:
        _watches.pop(feed_key, None)


def watched_feeds() -> list[str]:
    with _watches_lock:
        return sorted(_watches)


def is_externally_fed(series_key_text: str) -> bool:
    """True when the external feed owns this series (external mode + watched)."""
    if not enabled():
        return False
    with _watches_lock:
        return any(w.series_key.text == series_key_text for w in _watches.values())


def _get_watch(feed_key: str) -> _Watch | None:
    with _watches_lock:
        return _watches.get(feed_key)


def _watch_snapshot() -> list[tuple[str, _Watch]]:
    with _watches_lock:
        return list(_watches.items())


# ─── Sync ────────────────────────────────────────────────────────────────────


def sync_feed(store: Any, key: SeriesKey, bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert ``bars`` into the store through the same path ``provide`` uses."""
    if not bars:
        return {"key": key.text, "added": 0, "updated": 0, **store.status(key)}
    payload = [{k: b[k] for k in ("time", "open", "high", "low", "close", "volume")} for b in bars]
    return store.provide(key, payload, source=SOURCE_EXTERNAL)


def _sync_cursor(cfg: ExternalFeedConfig, feed_key: str, watch: _Watch) -> None:
    """Advance *watch*'s cursor from the feed (delta, or snapshot on first run)."""
    cursor = watch.cursor
    if cursor.initialized:
        try:
            deltas, _new_seq = fetch_delta(cfg, feed_key, int(cursor.last_seq or 0))
            for delta in deltas:
                cursor.apply_delta(delta)
            return
        except FeedResyncRequired:
            cursor.reset()
    seq, bars = _fetch_snapshot_frame(cfg, feed_key, cfg.provide_limit)
    cursor.apply_snapshot({"seq": seq, "bars": bars})


def sync_one(feed_key: str) -> dict[str, Any]:
    """One-shot sync of a watched feed: fetch → merge → persist.

    Returns a dict with ``fetched`` and the ``provide`` result fields.
    Raises on failure (callers decide whether to degrade or propagate).
    """
    global last_sync_at
    cfg = ExternalFeedConfig.from_env()
    if not cfg.enabled:
        raise FeedFetchError("PYNE_FEED_SOURCE is not 'external'")
    watch = _get_watch(feed_key)
    if watch is None:
        raise FeedFetchError(f"feed {feed_key!r} is not watched")
    try:
        _sync_cursor(cfg, feed_key, watch)
    except Exception as exc:
        _note_error(exc)
        raise
    pending = watch.cursor.take_pending()
    store = series_store.get_store()
    result = sync_feed(store, watch.series_key, pending)
    last_sync_at = time.time()
    return {"status": "success", "fetched": len(pending), **result}


# ─── Background thread ───────────────────────────────────────────────────────

_start_guard = threading.Lock()
_started = False
_thread: threading.Thread | None = None


def start_external_feed() -> bool:
    """Start the polling thread once per process. No-op unless external mode."""
    global _started, _thread
    if not ExternalFeedConfig.from_env().enabled:
        return False
    with _start_guard:
        if _started and _thread is not None and _thread.is_alive():
            return True
        thread = threading.Thread(target=_feed_loop, name="pyne-external-feed", daemon=True)
        thread.start()
        _thread = thread
        _started = True
    logger.info("external feed poller started (poll=%ss)", ExternalFeedConfig.from_env().poll_s)
    return True


def _feed_loop() -> None:
    while True:
        poll = 1.0
        try:
            cfg = ExternalFeedConfig.from_env()
            poll = max(_HTTP_POLL_MIN_S, cfg.poll_s)
            _poll_once(cfg)
        except Exception as exc:  # never let the thread die
            _note_error(exc)
            logger.warning("external feed poll failed: %s", exc)
        time.sleep(poll)


def _poll_once(cfg: ExternalFeedConfig) -> None:
    global last_sync_at
    for feed_key, watch in _watch_snapshot():
        try:
            _sync_cursor(cfg, feed_key, watch)
            pending = watch.cursor.take_pending()
            if pending:
                store = series_store.get_store()
                sync_feed(store, watch.series_key, pending)
            last_sync_at = time.time()
        except Exception as exc:  # per-feed failure never stops the loop
            _note_error(exc)
            logger.warning("external feed sync failed for %s: %s", feed_key, exc)


def stats() -> dict[str, Any]:
    """Observability snapshot for /stats and debugging."""
    return {
        "enabled": enabled(),
        "armed": bool(_started and _thread is not None and _thread.is_alive()),
        "watched": watched_feeds(),
        "error_count": error_count,
        "last_error": last_error,
        "last_sync_at": int(last_sync_at) if last_sync_at else None,
    }
