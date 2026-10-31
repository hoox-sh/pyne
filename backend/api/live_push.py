# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Feed → session → socket push loop (closes the F-13/F-19 gap).

A WS ``subscribe`` ensures history and answers ``full``; without this module
nothing would ever push again. :func:`attach_feed` binds the engine session to
its series feed: each candle batch advances the session walk-free
(:func:`apply_feed_candles`) and emits ``delta`` + ``close`` frames with
per-subscription ``seq`` through the :class:`PushHub` sender the socket loop
registers. Every batch is also upserted into the series store
(:func:`persist_feed_bars`), because a ``kind: series`` subscription — and any
reader of ``GET /data/series`` — renders the stored bounds, which no other path
on this plane advances.

Unchanged ticks emit nothing (the client already holds the tip). Sessions
released or TTL-evicted detach themselves on the next batch.
"""

from __future__ import annotations

import logging
import threading
import time

from collections.abc import Callable
from typing import Any


logger = logging.getLogger(__name__)


class PushHub:
    """Routes frames to live sockets by subscription id (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._senders: dict[str, Callable[[dict[str, Any]], None]] = {}

    def register(self, client_id: str, send: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._senders[client_id] = send

    def unregister(self, client_id: str) -> None:
        with self._lock:
            self._senders.pop(client_id, None)

    def send(self, client_id: str, frame: dict[str, Any]) -> bool:
        with self._lock:
            send = self._senders.get(client_id)
        if send is None:
            return False
        try:
            send(frame)
        except Exception:  # a dead socket must not kill the feed
            return False
        return True


HUB = PushHub()


def notify_session_gone(
    engine_session_id: str,
    *,
    registry: Any | None = None,
    hub: PushHub | None = None,
) -> int:
    """Tell every live socket still attached to this engine session it's gone.

    Stale-pool recreate drops the shared object; remaining tabs would otherwise
    tick a vanished id until the next resume. Best-effort: a missing hub or
    registry is a no-op, never raises.
    """
    if not engine_session_id:
        return 0
    try:
        from backend.api.live_ws import _SHARED_REGISTRY
    except Exception:
        return 0
    registry = registry if registry is not None else _SHARED_REGISTRY
    hub = hub if hub is not None else HUB
    try:
        client_ids = registry.client_ids_for_engine(engine_session_id)
    except Exception:
        return 0
    sent = 0
    for client_id in client_ids:
        frame = {
            "type": "error",
            "id": client_id,
            "message": "Session was replaced; subscribe again",
            "code": "SESSION_GONE",
            "retryable": True,
        }
        if hub.send(client_id, frame):
            sent += 1
    return sent


# Forming re-ticks (same bar slot) coalesce on the feed thread. Closes and
# multi-slot batches flush immediately so seq / close frames stay ordered.
CONFLATE_MS = 75
_conflate_lock = threading.Lock()
_conflate_latest: dict[str, list[dict[str, Any]]] = {}
_conflate_timers: dict[str, threading.Timer] = {}


# A kline stream pushes the forming bar on every trade, so a feed batch can
# arrive several times a second. The stored bounds only need to track the slot
# boundary promptly and the forming bar's values approximately (clients get the
# sub-second tip from the ``delta`` frames this module emits).
PERSIST_MIN_MS = 2_000

_persist_lock = threading.Lock()
_persisted: dict[str, tuple[int, int]] = {}


def persist_feed_bars(key_text: str, candles: list[dict[str, Any]], now_ms: int | None = None) -> bool:
    """Upsert a feed batch into the series store so its bounds keep moving.

    Nothing on the feed path otherwise touches the store: the engine's own feed
    advances *sessions* walk-free (:func:`apply_feed_candles`), while the store
    only moves when a REST walk runs (``fetch_history``) or a data session
    ticks (``sync_data_session``). A series served straight from the store — a
    ``kind: series`` subscription, and every reader of ``GET /data/series`` —
    therefore reported ``newest`` frozen at the bar history was ensured at,
    lagging the venue forever while the very feed streaming those bars on
    socket deltas could not heal it.

    Batches are upserted by time, so the venue's re-ticks of the forming bar
    converge and a batch another path already persisted is a no-op. Throttled
    per series (:data:`PERSIST_MIN_MS`): a new slot always persists, a re-tick
    of the current one at most once per window. Never raises — a store failure
    must not take the feed down with it.
    """
    from backend.api.data_series import SOURCE_TICK
    from backend.api.live_ensure import parse_live_key
    from backend.datastore import series as series_store

    batch = [c for c in candles if isinstance(c, dict) and "time" in c]
    if not batch:
        return False
    key = parse_live_key(key_text)
    if key is None:
        return False
    newest = max(int(c["time"]) for c in batch)
    at = int(time.time() * 1000) if now_ms is None else int(now_ms)
    with _persist_lock:
        seen_at, seen_newest = _persisted.get(key_text, (0, 0))
        if newest <= seen_newest and at - seen_at < PERSIST_MIN_MS:
            return False
        _persisted[key_text] = (at, max(newest, seen_newest))
    try:
        series_store.get_store().provide(key, batch, source=SOURCE_TICK)
    except Exception:  # a store write must not kill the feed
        logger.warning("feed persist failed for %s", key_text, exc_info=True)
        return False
    return True


def _journal_recorder(session_id: str) -> Callable[[str, Any], None]:
    from backend.app import _make_session_journal_recorder

    return _make_session_journal_recorder(session_id)


def emit_push_frames(
    client_id: str,
    registry: Any,
    session: Any,
    engine_session_id: str,
    binding: Any,
    outcome: Any,
    candles: list[dict[str, Any]],
    now_s: int,
) -> list[dict[str, Any]]:
    """Advance frames for one script-session feed batch. Returns emitted frames."""
    from backend.api.live_ws import closed_upto
    from backend.api.live_ws import make_close
    from backend.api.live_ws import make_delta

    if getattr(outcome, "unchanged", True):
        return []
    try:
        result = session.result()
    except Exception:
        return []
    if not isinstance(result, dict) or "error" in result:
        return []
    tail_len = int(getattr(outcome, "grown", 0) or 0) + int(getattr(outcome, "reticked", 0) or 0)
    # Forming re-ticks ship last-value only — never the full plot window.
    if bool(getattr(outcome, "forming", False)) and int(getattr(outcome, "appended", 0) or 0) == 0:
        tail_len = 1
    if tail_len <= 0:
        return []
    from backend.app import _delta_envelope

    envelope = _delta_envelope(result, engine_session_id, {}, tail_len)
    if not isinstance(envelope, dict) or "delta" not in envelope:
        return []
    delta_block = envelope["delta"]
    interval_s = int(binding.key.interval_seconds)
    watermark = closed_upto(candles, interval_s, now_s)
    emitted: list[dict[str, Any]] = []
    seq = registry.next_seq(client_id)
    emitted.append(
        make_delta(
            engine_session_id,
            seq,
            int(delta_block["base_index"]),
            int(delta_block["count"]),
            int(delta_block["tail_len"]),
            watermark,
            client_id,
            forming=bool(getattr(outcome, "forming", False)),
            plots=envelope.get("plots"),
            series=envelope.get("series") if isinstance(envelope.get("series"), dict) else None,
        )
    )
    count = int(delta_block["count"])
    if int(getattr(outcome, "appended", 0) or 0) > 0 and watermark > 0:
        final = next((c for c in candles if int(c["time"]) == watermark), None)
        if final is not None:
            index = count - 1 - (1 if getattr(outcome, "forming", False) else 0)
            seq = registry.next_seq(client_id)
            emitted.append(
                make_close(
                    engine_session_id,
                    seq,
                    max(0, index),
                    watermark,
                    {k: final[k] for k in ("open", "high", "low", "close", "volume")},
                    client_id,
                )
            )
    return emitted


def emit_series_push(
    client_id: str,
    registry: Any,
    record: dict[str, Any],
    candles: list[dict[str, Any]],
    now_s: int,
) -> list[dict[str, Any]]:
    """Series-kind push: candle bars with positional cursor, no session needed."""
    from backend.api.live_ensure import parse_live_key
    from backend.api.live_ws import closed_upto
    from backend.api.live_ws import make_close
    from backend.api.live_ws import make_delta

    batch = [c for c in candles if isinstance(c, dict) and "time" in c]
    if not batch:
        return []
    key = parse_live_key(str(record.get("series_key") or ""))
    interval_s = int(key.interval_seconds) if key else 60
    by_time: dict[int, dict[str, Any]] = {}
    for candle in batch:
        try:
            by_time[int(candle["time"])] = candle
        except (TypeError, ValueError):
            continue
    if not by_time:
        return []
    ordered = [by_time[t] for t in sorted(by_time)]
    newest = int(ordered[-1]["time"])
    count = int(record.get("count") or 0)
    last_time = int(record.get("last_time") or 0)
    new_bars = [c for c in ordered if int(c["time"]) > last_time]
    if not new_bars:
        # Forming re-tick of the current tip: same count, tail_len=1.
        tip = ordered[-1]
        before = max(0, count - 1) if count > 0 else 0
        after = count if count > 0 else 1
        record["count"] = after
        record["last_time"] = newest
        watermark = closed_upto([tip], interval_s, now_s)
        session_id = str(record.get("engine_session_id") or f"series-{client_id}")
        seq = registry.next_seq(client_id)
        emitted = [
            make_delta(
                session_id,
                seq,
                before,
                after,
                after - before,
                watermark,
                client_id,
                bars=[tip],
            )
        ]
    else:
        before = count
        after = before + len(new_bars)
        record["count"] = after
        record["last_time"] = newest
        watermark = closed_upto(new_bars, interval_s, now_s)
        session_id = str(record.get("engine_session_id") or f"series-{client_id}")
        seq = registry.next_seq(client_id)
        emitted = [
            make_delta(
                session_id,
                seq,
                before,
                after,
                len(new_bars),
                watermark,
                client_id,
                bars=new_bars,
            )
        ]
    if watermark > 0:
        final = next((c for c in batch if int(c["time"]) == watermark), None)
        if final is not None:
            emitted.append(
                make_close(
                    session_id,
                    registry.next_seq(client_id),
                    after - 1,
                    watermark,
                    {k: final[k] for k in ("open", "high", "low", "close", "volume")},
                    client_id,
                )
            )
    return emitted


def attach_feed(
    key_text: str,
    engine_session_id: str,
    client_id: str,
    registry: Any,
    hub: PushHub | None = None,
) -> bool:
    """Bind an engine session to its series feed with WS emission."""
    from backend.api.feed_manager import apply_feed_candles
    from backend.api.feed_manager import get_feed_manager
    from backend.api.feed_manager import now_seconds
    from backend.datastore import live as data_live
    from backend.middleware.sessions import SESSIONS

    hub = hub or HUB
    manager = get_feed_manager()

    def _push_batch(candles: list[dict[str, Any]]) -> None:
        now_s = now_seconds()
        persist_feed_bars(key_text, candles)
        record = registry.get(client_id)
        if record is not None and str(record.get("kind") or "") == "series":
            for frame in emit_series_push(client_id, registry, record, candles, now_s):
                hub.send(client_id, frame)
            return
        session = SESSIONS.get(engine_session_id)
        if session is None:
            manager.unsubscribe(key_text, engine_session_id)
            hub.send(
                client_id,
                {
                    "type": "error",
                    "id": client_id,
                    "message": "Session was released",
                    "code": "SESSION_GONE",
                    "retryable": True,
                },
            )
            hub.unregister(client_id)
            return
        binding = data_live.binding_of(session)
        if binding is None:
            return
        try:
            outcome = apply_feed_candles(
                session, binding, candles, now_s, on_apply=_journal_recorder(engine_session_id)
            )
        except Exception:
            logger.warning("feed apply failed for %s", key_text, exc_info=True)
            return
        for frame in emit_push_frames(
            client_id, registry, session, engine_session_id, binding, outcome, candles, now_s
        ):
            hub.send(client_id, frame)

    def _flush_conflate() -> None:
        with _conflate_lock:
            batch = _conflate_latest.pop(client_id, None)
            _conflate_timers.pop(client_id, None)
        if batch:
            _push_batch(batch)

    def on_candles(candles: list[dict[str, Any]]) -> None:
        times: set[int] = set()
        for candle in candles or []:
            try:
                times.add(int(candle["time"]))
            except (TypeError, ValueError, KeyError):
                continue
        forming_only = len(times) == 1 and CONFLATE_MS > 0
        if forming_only:
            with _conflate_lock:
                _conflate_latest[client_id] = list(candles)
                timer = _conflate_timers.get(client_id)
                if timer is None or not timer.is_alive():
                    timer = threading.Timer(CONFLATE_MS / 1000.0, _flush_conflate)
                    timer.daemon = True
                    _conflate_timers[client_id] = timer
                    timer.start()
            return
        with _conflate_lock:
            pending = _conflate_latest.pop(client_id, None)
            timer = _conflate_timers.pop(client_id, None)
        if timer is not None:
            timer.cancel()
        if pending:
            _push_batch(pending)
        _push_batch(candles)

    subscribed = manager.subscribe(key_text, engine_session_id, on_candles)
    return subscribed is not None
