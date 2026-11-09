# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""``WS /ws/live`` — engine-owned subscription plane (F-10).

One socket per client carries N multiplexed subscriptions::

    → { "type": "auth", "payload": { "token": "…" } }
    ← { "type": "auth.ok" }

    → { "type": "subscribe", "id": "…", "payload": {
            "kind": "series" | "script",
            "meta": { "exchange", "market", "symbol", "interval", "history_bars"? },
            "script"?, "inputs"?, "libraries"?, "mode"? } }
    ← { "type": "status", "id": "…", "sessionId": "…",
         "payload": { "code": "datafeed-loading", "have": 0, "need": 5000 } }

    → { "type": "ping" }  ← { "type": "pong" }

Auth mirrors the REST API-key middleware: a ``Bearer``/``ApiKey`` handshake
header or ``?api_key=`` pre-authenticates the connection, otherwise the first
frame must be ``auth``. Unauthenticated frames are rejected with
``UNAUTHORIZED``; rate-limited keys with ``RATE_LIMITED``.

This module owns the transport + auth + subscription registry only. History
ensure, feed ticks and ``full``/``delta``/``close`` frames land in F-11..F-13;
until then a subscribe is honestly answered with ``datafeed-loading`` and
``resume``/``repair`` with ``SESSION_GONE`` (repair aliases resume).

The protocol core (:class:`LiveConnection`) is socket-free so it unit-tests
without a WS client; :func:`register_live_route` wires the flask-sock loop.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import math
import threading
import time

from typing import Any


logger = logging.getLogger(__name__)


PROTOCOL_VERSION = "live/1"

DEFAULT_HISTORY_BARS = 5000
MIN_HISTORY_BARS = 50
MAX_HISTORY_BARS = 100000


def canonical_series_key(meta: dict[str, Any]) -> str | None:
    """``exchange|market|SYMBOL|interval`` or ``None`` when malformed."""
    try:
        from backend.datastore.series import make_key

        return make_key(
            meta.get("exchange"),
            meta.get("symbol"),
            meta.get("interval"),
            meta.get("market"),
        ).text
    except Exception:
        return None


def clamp_history_bars(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_HISTORY_BARS
    return max(MIN_HISTORY_BARS, min(MAX_HISTORY_BARS, n))


def extract_handshake_key(headers: dict[str, str], args: dict[str, str]) -> str:
    """API key from upgrade headers or query string (mirrors REST middleware)."""
    auth = headers.get("Authorization", "") or headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    if auth.startswith("ApiKey "):
        return auth[7:]
    return args.get("api_key", "") or args.get("token", "")


def validate_ws_key(raw_key: str) -> tuple[Any | None, str | None]:
    """Validate a WS credential. Returns ``(api_key, None)`` or ``(None, code)``."""
    from backend.middleware.auth import get_key_store

    store = get_key_store()
    api_key = store.validate_key(raw_key or "")
    if api_key is None:
        return None, "UNAUTHORIZED"
    if api_key.is_rate_limited():
        return None, "RATE_LIMITED"
    return api_key, None


class LiveRegistry:
    """In-memory subscription registry (single worker, like live sessions)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._subs: dict[str, dict[str, Any]] = {}
        self._seqs: dict[str, int] = {}

    def subscribe(self, client_id: str, kind: str, series_key: str, history_bars: int) -> dict[str, Any]:
        with self._lock:
            existing = self._subs.get(client_id)
            if existing is not None and existing["series_key"] == series_key:
                return existing
            session = {
                "session_id": f"live_{next(self._ids)}",
                "kind": kind,
                "series_key": series_key,
                "history_bars": history_bars,
            }
            self._subs[client_id] = session
            return session

    def get(self, client_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._subs.get(client_id)

    def release(self, client_id: str) -> bool:
        with self._lock:
            self._seqs.pop(client_id, None)
            return self._subs.pop(client_id, None) is not None

    def attach(self, client_id: str, engine_session_id: str | None, bars: list[dict[str, Any]]) -> None:
        """Stash the engine session + evaluated window on a subscription."""
        with self._lock:
            record = self._subs.get(client_id)
            if record is not None:
                record["engine_session_id"] = engine_session_id
                record["bars"] = list(bars)
                record["count"] = len(bars)
                last = bars[-1] if bars else None
                if isinstance(last, dict) and "time" in last:
                    try:
                        record["last_time"] = int(last["time"])
                    except (TypeError, ValueError):
                        record["last_time"] = 0

    def next_seq(self, client_id: str) -> int:
        """Monotonic per-subscription frame sequence (F-12 gap detection)."""
        with self._lock:
            seq = self._seqs.get(client_id, 0) + 1
            self._seqs[client_id] = seq
            return seq

    def client_ids_for_engine(self, engine_session_id: str) -> list[str]:
        """Subscription ids currently attached to one engine session."""
        if not engine_session_id:
            return []
        with self._lock:
            return [cid for cid, rec in self._subs.items() if rec.get("engine_session_id") == engine_session_id]


_SHARED_REGISTRY = LiveRegistry()


class LiveConnection:
    """Socket-free protocol core: validate + route one parsed frame."""

    def __init__(
        self,
        registry: LiveRegistry | None = None,
        *,
        authed: bool = False,
        ensurer: Any = None,
        resumer: Any = None,
        store_window: Any = None,
        hub: Any = None,
        sender: Any = None,
        attacher: Any = None,
    ) -> None:
        self._registry = registry or _SHARED_REGISTRY
        self.authed = authed
        self._ensurer = ensurer
        self._resumer = resumer
        self._store_window_fn = store_window
        self._hub = hub
        self._sender = sender
        self._attacher = attacher
        self._closed = False
        self._lock = threading.Lock()
        self._gens: dict[str, int] = {}
        self._owned: set[str] = set()
        # AXB1 negotiation state per subscription id (HP PR 7): set on
        # subscribe when the client asks for encoding "axb1", overwritten on
        # resubscribe, popped on unsubscribe. "last_time" is the newest bar
        # time seen so far — the re-tick vs append discriminator.
        self._axb1_subs: dict[str, dict[str, Any]] = {}

    @property
    def closed(self) -> bool:
        return self._closed

    def generation(self, client_id: str) -> int:
        with self._lock:
            return self._gens.get(client_id, 0)

    def still_current(self, client_id: str, token: int) -> bool:
        with self._lock:
            return (not self._closed) and self._gens.get(client_id, 0) == token

    def invalidate(self, client_id: str) -> int:
        """Bump so an in-flight ensure for this id cannot attach."""
        with self._lock:
            n = self._gens.get(client_id, 0) + 1
            self._gens[client_id] = n
            return n

    def close(self) -> None:
        """Socket gone: stale-token every owned sub and drop feed/hub listeners."""
        with self._lock:
            self._closed = True
            ids = list(self._owned)
            for cid in ids:
                self._gens[cid] = self._gens.get(cid, 0) + 1
            self._owned.clear()
            self._axb1_subs.clear()
        for cid in ids:
            self._detach(cid)

    def _send(self, frame: dict[str, Any]) -> None:
        """Single outbound path: negotiate AXB1 here; JSON stays the default."""
        if self._sender is None:
            return
        self._sender(self.encode_outbound(frame))

    def encode_outbound(self, frame: dict[str, Any]) -> dict[str, Any] | bytes:
        """Map one reply/hub frame to AXB1 bytes when its sub negotiated it.

        A pure negotiation step (no socket I/O) so ``serve_live_ws.dispatch``
        and socket-free tests share the exact wire path. JSON is the default
        and the compatibility guarantee: frames without a negotiated
        subscription — or anything :func:`map_live_frame` cannot represent
        losslessly (script frames, multi-bar deltas, ``idle`` status, control
        frames) — pass through untouched.

        Cursor discipline: the frame is classified with the PRE-bump cursor
        (a single-bar delta is a re-tick only when its bar time is not newer),
        then the cursor grows via ``max()`` — it never moves backwards.
        """
        if not isinstance(frame, dict):
            return frame
        raw_id = frame.get("id")
        state = self._axb1_subs.get(str(raw_id)) if raw_id is not None else None
        if state is None:
            return frame
        prev = state.get("last_time")
        mode = state.get("mode", "basic")
        encoded: bytes | None = None
        try:
            encoded = map_live_frame(frame, last_time=prev, mode=mode)
        except Exception:  # a bad frame must never kill the send path
            logger.warning("axb1 encode failed for %s", frame.get("type"), exc_info=True)
        derived = _axb1_cursor_time(frame)
        if derived is not None and (prev is None or derived > prev):
            state["last_time"] = derived
        return frame if encoded is None else encoded

    def _claim(self, client_id: str) -> None:
        with self._lock:
            if not self._closed:
                self._owned.add(client_id)

    def _detach(self, client_id: str) -> None:
        record = self._registry.get(client_id)
        if record is not None:
            try:
                from backend.api.feed_manager import get_feed_manager

                get_feed_manager().unsubscribe(
                    str(record.get("series_key") or ""),
                    str(record.get("engine_session_id") or client_id),
                )
            except Exception:
                pass
        if self._hub is not None:
            try:
                self._hub.unregister(client_id)
            except Exception:
                pass
        self._registry.release(client_id)

    def _attach(
        self,
        key_text: str,
        engine_session_id: str | None,
        client_id: str,
        *,
        token: int | None = None,
    ) -> None:
        if engine_session_id is None or self._closed:
            return
        if token is not None and not self.still_current(client_id, token):
            return
        if self._hub is not None and self._sender is not None:
            # Register the wrapped sender so hub frames go through the AXB1
            # negotiation (encode_outbound) before they hit the socket.
            self._hub.register(client_id, self._send)
        if self._closed or (token is not None and not self.still_current(client_id, token)):
            if self._hub is not None:
                try:
                    self._hub.unregister(client_id)
                except Exception:
                    pass
            return
        attacher = self._attacher
        if attacher is None:
            from backend.api.live_push import attach_feed as _attach_feed

            attacher = _attach_feed
        try:
            attacher(key_text, engine_session_id, client_id, self._registry, self._hub)
        except Exception:  # attach failure degrades to snapshot-only
            logger.warning("feed attach failed for %s (%s)", key_text, client_id, exc_info=True)
            return
        if token is not None and not self.still_current(client_id, token):
            self._detach(client_id)

    def _ensure(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        ensurer = self._ensurer
        if ensurer is None:
            from backend.api.live_ensure import ensure_live_session

            ensurer = ensure_live_session
        return ensurer(*args, **kwargs)

    def _resume_session(self, session_id: str) -> dict[str, Any]:
        resumer = self._resumer
        if resumer is None:
            from backend.api.live_ensure import resume_live_session

            resumer = resume_live_session
        return resumer(session_id)

    # -- replies ---------------------------------------------------------
    @staticmethod
    def _err(req_id: Any, message: str, code: str, **extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {"type": "error", "message": message, "code": code}
        if req_id is not None:
            out["id"] = req_id
        out.update(extra)
        return out

    # -- entry point -----------------------------------------------------
    def handle_dict(self, msg: Any) -> list[dict[str, Any]]:
        if not isinstance(msg, dict):
            return [self._err(None, "Frame must be a JSON object", "BAD_FRAME")]
        mtype = str(msg.get("type") or "")
        req_id = msg.get("id")

        if mtype == "ping":
            return [{"type": "pong", **({"id": req_id} if req_id is not None else {})}]
        if mtype == "auth":
            return self._handle_auth(req_id, msg.get("payload"))

        if not self.authed:
            return [
                self._err(
                    req_id,
                    "Authenticate first (auth frame or API key handshake)",
                    "UNAUTHORIZED",
                    retryable=False,
                )
            ]

        if mtype == "subscribe":
            return self._handle_subscribe(req_id, msg.get("payload"))
        if mtype == "resume":
            return self._handle_resume(req_id, msg.get("payload"))
        if mtype == "repair":
            return self._handle_repair(req_id, msg.get("payload"))
        if mtype == "unsubscribe":
            return self._handle_unsubscribe(req_id)
        return [self._err(req_id, f"Unknown type: {mtype}", "UNKNOWN_TYPE")]

    # -- handlers --------------------------------------------------------
    def _handle_auth(self, req_id: Any, payload: Any) -> list[dict[str, Any]]:
        token = payload.get("token", "") if isinstance(payload, dict) else ""
        _, code = validate_ws_key(str(token or ""))
        if code is not None:
            return [self._err(req_id, "Invalid or missing API key", code, retryable=False)]
        self.authed = True
        out: dict[str, Any] = {"type": "auth.ok"}
        if req_id is not None:
            out["id"] = req_id
        return [out]

    def _handle_subscribe(self, req_id: Any, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return [self._err(req_id, "subscribe needs a payload object", "BAD_SUBSCRIBE")]
        kind = payload.get("kind")
        if kind not in ("series", "script"):
            return [self._err(req_id, "kind must be series|script", "BAD_SUBSCRIBE")]
        meta = payload.get("meta")
        series_key = canonical_series_key(meta) if isinstance(meta, dict) else None
        if series_key is None:
            return [self._err(req_id, "meta needs exchange/symbol/interval", "BAD_SUBSCRIBE")]
        if kind == "script" and not payload.get("script"):
            return [self._err(req_id, "script subscriptions need a script", "BAD_SUBSCRIBE")]
        history_bars = clamp_history_bars((meta or {}).get("history_bars"))
        if req_id is None:
            return [self._err(None, "subscribe needs an id", "BAD_SUBSCRIBE")]
        client_id = str(req_id)
        token = self.generation(client_id)
        # AXB1 negotiation (HP PR 7 / axb1-full): binary outbound only when
        # the client explicitly asked for it on subscribe. Resubscribe
        # overwrites, and a subscribe without the flag drops back to all-JSON.
        encoding = str(payload.get("encoding") or "")
        if encoding == "axb1":
            self._axb1_subs[client_id] = {"last_time": None, "mode": "basic"}
        elif encoding == "axb1-full":
            self._axb1_subs[client_id] = {"last_time": None, "mode": "full"}
        else:
            self._axb1_subs.pop(client_id, None)
        # Tell the client we are fetching before the 4-9s first walk so the
        # HUD is honest and the socket is not silent during ensure.
        pending = self._registry.subscribe(client_id, str(kind), series_key, history_bars)
        self._claim(client_id)
        if self._sender is not None:
            try:
                self._send(
                    {
                        "type": "status",
                        "id": req_id,
                        "sessionId": pending["session_id"],
                        "payload": {
                            "code": "datafeed-loading",
                            "need": history_bars,
                            "message": "fetching history",
                        },
                    }
                )
            except Exception:
                logger.warning("early datafeed-loading send failed", exc_info=True)
        ensured = self._ensure(
            str(kind),
            series_key,
            history_bars,
            script=payload.get("script") if isinstance(payload.get("script"), str) else None,
            inputs=payload.get("inputs") if isinstance(payload.get("inputs"), dict) else None,
            libraries=payload.get("libraries") if isinstance(payload.get("libraries"), list) else None,
            profiler=bool(payload.get("profiler")),
            symbol=str(meta.get("symbol", "")) if isinstance(meta, dict) else "",
        )
        if not self.still_current(client_id, token):
            return []
        if ensured.get("outcome") == "error":
            return [
                self._err(
                    req_id, str(ensured.get("message") or "ensure failed"), str(ensured.get("code") or "ENSURE_FAILED")
                )
            ]
        if ensured.get("outcome") == "short":
            session = self._registry.subscribe(client_id, str(kind), series_key, history_bars)
            return [
                {
                    "type": "status",
                    "id": req_id,
                    "sessionId": session["session_id"],
                    "payload": {
                        "code": "datafeed-loading",
                        "have": int(ensured.get("have") or 0),
                        "need": int(ensured.get("need") or history_bars),
                        "message": "fetching history",
                    },
                }
            ]
        return self._emit_ready(client_id, str(kind), series_key, ensured, token=token)

    def _handle_resume(self, req_id: Any, payload: Any) -> list[dict[str, Any]]:
        record = self._registry.get(str(req_id)) if req_id is not None else None
        if record is None:
            return [
                self._err(
                    req_id,
                    "Unknown subscription — subscribe again",
                    "SESSION_GONE",
                    retryable=True,
                )
            ]
        client_id = str(req_id)
        token = self.generation(client_id)
        # AXB1 re-negotiation on resume: same rules as subscribe.
        encoding = str(payload.get("encoding") or "") if isinstance(payload, dict) else ""
        if encoding == "axb1":
            self._axb1_subs[client_id] = {"last_time": None, "mode": "basic"}
        elif encoding == "axb1-full":
            self._axb1_subs[client_id] = {"last_time": None, "mode": "full"}
        else:
            self._axb1_subs.pop(client_id, None)
        engine_session_id = record.get("engine_session_id")
        if engine_session_id:
            resumed = self._resume_session(str(engine_session_id))
            if not self.still_current(client_id, token):
                return []
            if resumed.get("outcome") == "ready":
                return self._emit_snapshot(client_id, record, resumed.get("session"), token=token)
        # Gone or series-kind: re-ensure history, then snapshot from the store.
        return self._emit_ready(
            client_id, str(record.get("kind") or "series"), str(record.get("series_key") or ""), None, token=token
        )

    def _emit_ready(
        self,
        client_id: str,
        kind: str,
        series_key: str,
        ensured: dict[str, Any] | None,
        *,
        token: int | None = None,
    ) -> list[dict[str, Any]]:
        """status(datafeed-ready) → [status(calculating)] → full → status(live)."""
        from backend.api.live_ensure import parse_live_key

        if ensured is None:
            record = self._registry.get(client_id) or {}
            ensured = self._ensure(kind, series_key, int(record.get("history_bars") or DEFAULT_HISTORY_BARS))
            if token is not None and not self.still_current(client_id, token):
                return []
            if ensured.get("outcome") != "ready":
                return [self._status_loading(client_id, ensured)]
        if token is not None and not self.still_current(client_id, token):
            return []
        session = self._registry.subscribe(
            client_id, kind, series_key, int(ensured.get("count") or 0) or DEFAULT_HISTORY_BARS
        )
        frames: list[dict[str, Any]] = [make_status(session["session_id"], "datafeed-ready", client_id)]
        bars: list[dict[str, Any]] = []
        full_kwargs: dict[str, Any] = {}
        full_count: int | None = None
        if kind == "script" and ensured.get("session_id"):
            resumed = self._resume_session(str(ensured["session_id"]))
            live_session = resumed.get("session")
            bars = self._bars_of(live_session)
            # full.count must match evaluated columns / delta numbering
            # (result.count), not the ensure-window length. A longer declared
            # count makes AXIS reject every delta and resubscribe.
            full_count, full_kwargs = self._script_full_columns(live_session, bars)
            frames.append(make_status(session["session_id"], "calculating", client_id))
        else:
            bars = self._store_window(series_key, int(ensured.get("count") or 0))
            full_kwargs = {"bars": bars}
            full_count = len(bars)
        self._registry.attach(client_id, ensured.get("session_id"), bars)
        # A series-kind subscription has no engine session (its bars serve
        # straight from the store), but it still needs the feed: without an
        # attach nothing keeps the store moving, and the client only ever got
        # the frozen ensure-time snapshot. The registry's own live id is the
        # listener key — stable per client + series, so a re-subscribe replaces
        # the listener in place instead of stacking one per frame.
        if token is not None and not self.still_current(client_id, token):
            self._detach(client_id)
            return []
        self._attach(
            series_key,
            ensured.get("session_id") or session["session_id"],
            client_id,
            token=token,
        )
        key = parse_live_key(series_key)
        watermark = closed_upto(bars, int(key.interval_seconds) if key else 60, int(time.time()))
        seq = self._registry.next_seq(client_id)
        frames.append(
            make_full(
                session["session_id"],
                seq,
                series_key,
                int(full_count if full_count is not None else len(bars)),
                watermark,
                client_id,
                **full_kwargs,
            )
        )
        frames.append(make_status(session["session_id"], "live", client_id))
        return frames

    def _emit_snapshot(
        self,
        client_id: str,
        record: dict[str, Any],
        live_session: Any,
        *,
        token: int | None = None,
    ) -> list[dict[str, Any]]:
        """Resume answer: fresh full snapshot + live (delta-continuation is future work)."""
        from backend.api.live_ensure import parse_live_key

        if token is not None and not self.still_current(client_id, token):
            return []
        session_id = str(record.get("engine_session_id") or "")
        bars = self._bars_of(live_session)
        count, full_kwargs = self._script_full_columns(live_session, bars)
        key = parse_live_key(str(record.get("series_key") or ""))
        watermark = closed_upto(bars, int(key.interval_seconds) if key else 60, int(time.time()))
        seq = self._registry.next_seq(client_id)
        return [
            make_full(
                session_id,
                seq,
                str(record.get("series_key") or ""),
                count,
                watermark,
                client_id,
                **full_kwargs,
            ),
            make_status(session_id, "live", client_id),
        ]

    @staticmethod
    def _bars_of(live_session: Any) -> list[dict[str, Any]]:
        bars = getattr(live_session, "_ohlcv_data", None) if live_session is not None else None
        return list(bars) if isinstance(bars, list) else []

    @staticmethod
    def _script_full_columns(
        live_session: Any, bars: list[dict[str, Any]]
    ) -> tuple[int, dict[str, Any]]:
        """Build script ``full`` columns keyed to the evaluated prefix length.

        ``LiveSession.result()`` reports ``count`` / ``times`` / plots for bars
        actually evaluated. The session window (``_ohlcv_data`` / ensure count)
        can be longer. Deltas are numbered from ``result["count"]``, so the
        opening ``full`` must declare that same length or the client cannot
        splice and falls into a full-snapshot loop every tick.
        """
        try:
            result = live_session.result() if live_session is not None else {}
        except Exception:
            result = {}
        if not isinstance(result, dict):
            result = {}
        result_count = result.get("count")
        if isinstance(result_count, int) and result_count >= 0:
            count = result_count
        else:
            count = len(bars)
        times = result.get("times")
        if isinstance(times, list) and len(times) == count:
            bar_times: list[Any] = list(times)
        else:
            bar_times = [b["time"] for b in bars[:count]]
        return count, {
            "plots": result.get("plots"),
            "series": result.get("series"),
            "bar_times": bar_times,
            "plot_meta": result.get("plot_meta"),
            "events": result.get("events"),
            "drawings": result.get("drawings"),
        }
    def _store_window(self, series_key: str, limit: int) -> list[dict[str, Any]]:
        if self._store_window_fn is not None:
            return list(self._store_window_fn(series_key, limit))
        from backend.api.live_ensure import parse_live_key
        from backend.datastore import series as series_store

        key = parse_live_key(series_key)
        if key is None:
            return []
        try:
            return series_store.get_store().window(key, max(1, limit))
        except Exception:
            return []

    def _status_loading(self, client_id: str, ensured: dict[str, Any]) -> dict[str, Any]:
        session = self._registry.get(client_id) or {"session_id": f"pending-{client_id}"}
        if ensured.get("outcome") == "error":
            return self._err(
                client_id, str(ensured.get("message") or "ensure failed"), str(ensured.get("code") or "ENSURE_FAILED")
            )
        return {
            "type": "status",
            "id": client_id,
            "sessionId": session["session_id"],
            "payload": {
                "code": "datafeed-loading",
                "have": int(ensured.get("have") or 0),
                "need": int(ensured.get("need") or 0),
                "message": "fetching history",
            },
        }

    def _handle_repair(self, req_id: Any, payload: Any) -> list[dict[str, Any]]:
        # Repair aliases resume: a fresh snapshot from the current store /
        # session is enough to heal a close mismatch or seq gap.
        return self._handle_resume(req_id, payload if isinstance(payload, dict) else {})

    def _handle_unsubscribe(self, req_id: Any) -> list[dict[str, Any]]:
        if req_id is not None:
            client_id = str(req_id)
            self.invalidate(client_id)
            with self._lock:
                self._owned.discard(client_id)
            self._axb1_subs.pop(client_id, None)
            self._detach(client_id)
        return [
            {
                "type": "status",
                **({"id": req_id} if req_id is not None else {}),
                "payload": {"code": "idle", "message": "released"},
            }
        ]


def serve_live_ws(ws: Any, registry: LiveRegistry | None = None) -> None:
    """flask-sock loop for ``WS /ws/live`` (handshake pre-auth + frames)."""
    import queue as _queue

    from flask import request as flask_request

    from backend.api.live_push import HUB

    headers = dict(flask_request.headers or {})
    args = dict(flask_request.args or {})
    authed = False
    raw = extract_handshake_key(headers, args)
    if raw:
        _, code = validate_ws_key(raw)
        authed = code is None

    sock_thread = threading.current_thread()
    outbound: _queue.Queue[Any] = _queue.Queue()
    conn: LiveConnection

    def to_wire(data: dict[str, Any] | bytes) -> dict[str, Any] | bytes:
        # AXB1 frames are already on the wire format; JSON stays json.dumps.
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        return json.dumps(data)

    def sender(frame: dict[str, Any] | bytes) -> None:
        # flask-sock is not safe from the feed thread; only this loop sends.
        if conn.closed:
            return
        if threading.current_thread() is sock_thread:
            ws.send(to_wire(frame))
            return
        outbound.put(frame)

    def drain_outbound() -> None:
        while True:
            try:
                frame = outbound.get_nowait()
            except _queue.Empty:
                return
            if conn.closed:
                continue
            try:
                ws.send(to_wire(frame))
            except Exception:
                return

    conn = LiveConnection(registry, authed=authed, hub=HUB, sender=sender)
    inflight: dict[str, threading.Thread] = {}
    inflight_keys: dict[str, str] = {}

    def dispatch(frame: dict[str, Any]) -> None:
        try:
            for reply in conn.handle_dict(frame):
                # encode_outbound is a no-op passthrough unless the client
                # negotiated encoding "axb1" for this subscription id.
                sender(conn.encode_outbound(reply))
        except Exception:  # a bad ensure must not kill the loop
            logger.exception("live frame handler failed")

    def run_ensure(frame: dict[str, Any], req_id: str) -> None:
        try:
            dispatch(frame)
        finally:
            if inflight.get(req_id) is threading.current_thread():
                inflight.pop(req_id, None)
                inflight_keys.pop(req_id, None)

    def drop_inflight(req_id: str) -> None:
        inflight.pop(req_id, None)
        inflight_keys.pop(req_id, None)

    def teardown() -> None:
        inflight.clear()
        inflight_keys.clear()
        try:
            conn.close()
        except Exception:
            logger.exception("live ws close failed")
        drain_outbound()

    if authed:
        try:
            ws.send(json.dumps({"type": "auth.ok"}))
        except Exception:
            return
    while True:
        try:
            incoming = ws.receive(timeout=0.05)
        except TypeError:
            incoming = ws.receive()
        except Exception as exc:  # timeout classes differ by transport
            name = type(exc).__name__.lower()
            if "timeout" in name:
                incoming = ""
            else:
                teardown()
                break
        drain_outbound()
        if incoming is None:
            # ``simple_websocket`` returns **None on a timeout**, not only when
            # the peer closed — a quiet socket (a slow history ensure, the
            # client between heartbeats) must not tear the plane down. A real
            # disconnect raises ``ConnectionClosed`` and is handled above.
            if not getattr(ws, "connected", True):
                teardown()
                break
            continue
        if incoming == "":
            # Snapshot: ensure threads pop themselves from ``inflight`` on exit.
            dead = [k for k, t in list(inflight.items()) if not t.is_alive()]
            for k in dead:
                t = inflight.get(k)
                if t is not None and not t.is_alive():
                    inflight.pop(k, None)
                    inflight_keys.pop(k, None)
            continue
        try:
            msg = json.loads(incoming) if isinstance(incoming, str) else json.loads(incoming.decode("utf-8"))
        except Exception:
            ws.send(json.dumps({"type": "error", "message": "Invalid JSON frame", "code": "BAD_JSON"}))
            continue
        mtype = str(msg.get("type") or "") if isinstance(msg, dict) else ""
        # History ensure blocks; keep ping/pong and outbound drain on this thread.
        if mtype in ("subscribe", "resume", "repair"):
            req_id = str(msg.get("id") or "")
            payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            new_key = canonical_series_key(meta) if mtype == "subscribe" else None
            prev = inflight.get(req_id)
            if prev is not None and prev.is_alive():
                prev_key = inflight_keys.get(req_id)
                if mtype == "subscribe" and new_key and prev_key and new_key != prev_key:
                    conn.invalidate(req_id)
                else:
                    continue
            t = threading.Thread(target=run_ensure, args=(msg, req_id), name="live-ws-ensure", daemon=True)
            inflight[req_id] = t
            if new_key:
                inflight_keys[req_id] = new_key
            t.start()
        elif mtype == "unsubscribe":
            drop_inflight(str(msg.get("id") or ""))
            dispatch(msg)
        else:
            dispatch(msg)
        drain_outbound()


def register_live_route(sock: Any, registry: LiveRegistry | None = None) -> None:
    """Register ``WS /ws/live`` on a flask-sock instance."""

    @sock.route("/ws/live")
    def ws_live(ws):  # type: ignore[no-untyped-def]
        """Engine-owned subscription plane (see module docstring)."""
        serve_live_ws(ws, registry)


def subscription_fingerprint(kind: str, series_key: str, script: str = "") -> str:
    """Stable id for a (kind, series, script) subscription."""
    digest = hashlib.sha256(f"{kind}|{series_key}|{script}".encode()).hexdigest()
    return digest[:16]


# ---------------------------------------------------------------------------
# Frame builders (F-12): status / full / delta / close with seq + watermark.
# ---------------------------------------------------------------------------


def closed_upto(candles: list[dict[str, Any]], interval_s: int, now_s: int) -> int:
    """Newest bar time fully closed at ``now_s`` (0 when none is closed)."""
    upto = 0
    for bar in candles or []:
        try:
            t = int(bar["time"])
        except (KeyError, TypeError, ValueError):
            continue
        if t + interval_s <= now_s and t > upto:
            upto = t
    return upto


def make_status(
    session_id: str,
    code: str,
    req_id: Any = None,
    *,
    have: int | None = None,
    need: int | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "status", "sessionId": session_id, "payload": {"code": code}}
    if req_id is not None:
        out["id"] = req_id
    if have is not None:
        out["payload"]["have"] = have
    if need is not None:
        out["payload"]["need"] = need
    if message is not None:
        out["payload"]["message"] = message
    return out


def make_full(
    session_id: str,
    seq: int,
    series_key: str,
    count: int,
    watermark: int,
    req_id: Any = None,
    *,
    bars: list[dict[str, Any]] | None = None,
    bar_times: list[int] | None = None,
    plots: Any = None,
    series: dict[str, Any] | None = None,
    plot_meta: Any = None,
    events: Any = None,
    drawings: Any = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(seq, int) or seq < 1:
        raise ValueError("full frames need a positive seq")
    payload: dict[str, Any] = {
        "seriesKey": series_key,
        "count": count,
        "closed_upto": watermark,
    }
    if bars is not None:
        payload["bars"] = bars
    if bar_times is not None:
        payload["bar_times"] = bar_times
    if plots is not None:
        payload["plots"] = plots
    if series is not None:
        payload["series"] = series
    if plot_meta is not None:
        payload["plot_meta"] = plot_meta
    if events is not None:
        payload["events"] = events
    if drawings is not None:
        payload["drawings"] = drawings
    if meta is not None:
        payload["meta"] = meta
    out: dict[str, Any] = {
        "type": "full",
        "sessionId": session_id,
        "seq": seq,
        "payload": payload,
    }
    if req_id is not None:
        out["id"] = req_id
    return out


def make_delta(
    session_id: str,
    seq: int,
    base_index: int,
    count: int,
    tail_len: int,
    watermark: int,
    req_id: Any = None,
    *,
    forming: bool | None = None,
    plots: Any = None,
    series: dict[str, Any] | None = None,
    bars: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(seq, int) or seq < 1:
        raise ValueError("delta frames need a positive seq")
    if tail_len != count - base_index:
        raise ValueError("tail_len must equal count - base_index")
    payload: dict[str, Any] = {
        "base_index": base_index,
        "count": count,
        "tail_len": tail_len,
        "closed_upto": watermark,
    }
    if forming is not None:
        payload["forming"] = forming
    if plots is not None:
        payload["plots"] = plots
    if series is not None:
        payload["series"] = series
    if bars is not None:
        payload["bars"] = bars
    out: dict[str, Any] = {
        "type": "delta",
        "sessionId": session_id,
        "seq": seq,
        "payload": payload,
    }
    if req_id is not None:
        out["id"] = req_id
    return out


def make_close(
    session_id: str,
    seq: int,
    index: int,
    bar_time: int,
    ohlcv: dict[str, Any],
    req_id: Any = None,
) -> dict[str, Any]:
    if not isinstance(seq, int) or seq < 1:
        raise ValueError("close frames need a positive seq")
    for field in ("open", "high", "low", "close", "volume"):
        if field not in ohlcv:
            raise ValueError(f"close frame ohlcv is missing {field}")
    out: dict[str, Any] = {
        "type": "close",
        "sessionId": session_id,
        "seq": seq,
        "payload": {"index": index, "time": bar_time, "ohlcv": dict(ohlcv)},
    }
    if req_id is not None:
        out["id"] = req_id
    return out


# -- AXB1 outbound mapping (HP PR 7) --------------------------------------
#
# Pure JSON → AXB1 projection used by LiveConnection.encode_outbound. Each
# helper maps one pyne frame type to exactly one AXB1 opcode and returns None
# for anything it cannot represent losslessly — JSON fallback is the honesty
# rule, never a mangled binary frame.


def _axb1_cursor_time(frame: dict[str, Any]) -> int | None:
    """Newest bar time a full/delta frame carries (cursor input, None if absent)."""
    if frame.get("type") not in ("full", "delta"):
        return None
    payload = frame.get("payload")
    if not isinstance(payload, dict):
        return None
    bars = payload.get("bars")
    if not isinstance(bars, list) or not bars:
        return None
    last = bars[-1]
    if not isinstance(last, dict) or "time" not in last:
        return None
    try:
        return int(last["time"])
    except (TypeError, ValueError):
        return None


def _map_status(header: Any, payload: dict[str, Any]) -> bytes | None:
    from pynescript.runtime import axb1 as _axb1

    code = payload.get("code")
    if code not in _axb1.AXB1_STATUS_CODES:  # "idle" and friends stay JSON
        return None
    detail = payload.get("message") or payload.get("detail") or ""
    return _axb1.encode_status(
        header,
        status_code=str(code),
        detail=str(detail),
        have=int(payload.get("have") or 0),
        need=int(payload.get("need") or 0),
    )


def _map_full(header: Any, payload: dict[str, Any], scale: int) -> bytes | None:
    from pynescript.runtime import axb1 as _axb1

    bars = payload.get("bars")
    if not isinstance(bars, list) or not bars:
        return None  # script snapshots (plots/series/bar_times/…) stay JSON
    if set(payload) - {"seriesKey", "count", "closed_upto", "bars"}:
        return None  # any structured leftover stays JSON, never JSON_BLOB
    count = payload.get("count")
    if not isinstance(count, int) or count != len(bars) or "closed_upto" not in payload:
        return None
    closed_upto = int(payload["closed_upto"])
    time_s: list[int] = []
    columns: dict[str, list] = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    try:
        for bar in bars:
            if not isinstance(bar, dict):
                return None
            time_s.append(int(bar["time"]))
            for field in ("open", "high", "low", "close"):
                columns[field].append(_axb1.price_to_ticks(float(bar[field]), scale))
            columns["volume"].append(float(bar["volume"]))
    except (KeyError, TypeError, ValueError):
        return None
    flags = [1 if t <= closed_upto else 2 for t in time_s]
    return _axb1.encode_snapshot_ohlcv(
        header,
        price_scale=scale,
        count=count,
        closed_upto=closed_upto,
        hot_from_index=0,
        time_s=time_s,
        flags=flags,
        ohlcv=columns,
    )


def _map_delta(header: Any, payload: dict[str, Any], last_time: int | None, scale: int) -> bytes | None:
    from pynescript.runtime import axb1 as _axb1

    bars = payload.get("bars")
    if payload.get("unchanged") is True:
        leftovers = set(payload) - {"base_index", "count", "tail_len", "closed_upto", "forming", "unchanged"}
        if leftovers or bars:  # data inside an "unchanged" frame is not droppable
            return None
        return _axb1.encode_unchanged(header)
    if not isinstance(bars, list) or len(bars) != 1 or payload.get("tail_len") != 1:
        return None  # script deltas (no bars) and multi-bar tails are not representable
    if set(payload) - {"base_index", "count", "tail_len", "closed_upto", "forming", "bars"}:
        return None
    bar = bars[0]
    if not isinstance(bar, dict) or "time" not in bar:
        return None
    try:
        bar_time = int(bar["time"])
    except (TypeError, ValueError):
        return None
    # Re-tick vs append: pyne's delta envelope is byte-identical for both
    # (base_index == count - 1, tail_len == 1), so base/count/tail cannot
    # classify them — the cursor (newest bar time) is the only discriminator.
    # TIP_UPDATE never grows AXIS's count, so mapping an append as a tip would
    # freeze the chart; anything newer than the cursor stays JSON instead.
    if last_time is None or bar_time > last_time:
        return None
    mask = int(_axb1.TipMask.TIME)
    tip: dict[str, Any] = {"flags": 1, "time_s": bar_time}
    try:
        for field, bit in (
            ("open", _axb1.TipMask.OPEN),
            ("high", _axb1.TipMask.HIGH),
            ("low", _axb1.TipMask.LOW),
            ("close", _axb1.TipMask.CLOSE),
        ):
            if field in bar:
                mask |= int(bit)
                tip[field] = _axb1.price_to_ticks(float(bar[field]), scale)
        if "volume" in bar:
            mask |= int(_axb1.TipMask.VOLUME)
            tip["volume"] = float(bar["volume"])
    except (TypeError, ValueError):
        return None
    tip["mask"] = mask
    return _axb1.encode_tip_update(header, tip)


def _map_close(header: Any, payload: dict[str, Any], scale: int) -> bytes | None:
    from pynescript.runtime import axb1 as _axb1

    if set(payload) - {"index", "time", "ohlcv", "tip"}:
        return None
    try:
        index = int(payload["index"])
        bar_time = int(payload["time"])
        raw = payload["ohlcv"]
        if not isinstance(raw, dict):
            return None
        ohlcv: dict[str, Any] = {}
        for field in ("open", "high", "low", "close"):
            ohlcv[field] = _axb1.price_to_ticks(float(raw[field]), scale)
        ohlcv["volume"] = float(raw["volume"])
    except (KeyError, TypeError, ValueError):
        return None
    tip = payload.get("tip")
    if tip is None:
        return _axb1.encode_close_verify(header, index=index, time_s=bar_time, ohlcv=ohlcv)
    if not isinstance(tip, dict) or "time" not in tip:
        return None  # an odd tip shape must not be silently dropped
    try:
        tip_time = int(tip["time"])
        mask = int(_axb1.TipMask.TIME)
        tip_fields: dict[str, Any] = {"flags": int(tip.get("flags") or 1), "time_s": tip_time}
        for field, bit in (
            ("open", _axb1.TipMask.OPEN),
            ("high", _axb1.TipMask.HIGH),
            ("low", _axb1.TipMask.LOW),
            ("close", _axb1.TipMask.CLOSE),
        ):
            if field in tip:
                mask |= int(bit)
                tip_fields[field] = _axb1.price_to_ticks(float(tip[field]), scale)
        if "volume" in tip:
            mask |= int(_axb1.TipMask.VOLUME)
            tip_fields["volume"] = float(tip["volume"])
        tip_fields["mask"] = mask
    except (TypeError, ValueError):
        return None
    return _axb1.encode_append_bar(
        header,
        price_scale=scale,
        closed_index=index,
        closed_time=bar_time,
        ohlcv=ohlcv,
        tip=tip_fields,
    )


def _map_error(header: Any, frame: dict[str, Any], payload: dict[str, Any]) -> bytes | None:
    from pynescript.runtime import axb1 as _axb1

    code = frame.get("code", payload.get("code"))
    message = frame.get("message", payload.get("message"))
    if code is None or message is None:
        return None
    retryable = frame.get("retryable")
    if retryable is None:
        retryable = payload.get("retryable")
    return _axb1.encode_error(header, code=str(code), message=str(message), retryable=bool(retryable))


def _map_full_plots(header: Any, payload: dict[str, Any]) -> bytes | None:
    """AXB1 SNAPSHOT_PLOTS for a full script frame, JSON fallback = ``None``."""
    from pynescript.runtime import axb1 as _axb1

    # Only script snapshots (no bars) are eligible; extra metadata keeps JSON.
    allowed = {"seriesKey", "count", "closed_upto", "series", "plots", "bar_times"}
    if set(payload) - allowed or "bars" in payload:
        return None
    count = payload.get("count")
    if not isinstance(count, int) or count < 0 or "closed_upto" not in payload:
        return None
    closed_upto = int(payload["closed_upto"])
    series = payload.get("series")
    plots: list[dict[str, Any]] = []
    if isinstance(series, dict) and series:
        # ``series`` maps plot key → equal-length numeric array.
        for key, values in series.items():
            if not isinstance(key, str) or not isinstance(values, list) or len(values) != count:
                return None
            try:
                plots.append({"key": key, "kind": _axb1.ValueKind.UnitFloat64, "values": [float(v) for v in values]})
            except (TypeError, ValueError):
                return None
    else:
        # Legacy ``plots: [[...]]`` fallback: a single non-empty row becomes
        # plot key "0". Anything else falls back to JSON.
        plots_list = payload.get("plots")
        if not isinstance(plots_list, list) or len(plots_list) != 1:
            return None
        inner = plots_list[0]
        if not isinstance(inner, list) or not inner or len(inner) != count:
            return None
        try:
            plots = [{"key": "0", "kind": _axb1.ValueKind.UnitFloat64, "values": [float(v) for v in inner]}]
        except (TypeError, ValueError):
            return None
    if not plots:
        return None
    times: list[int] | None = None
    bar_times = payload.get("bar_times")
    if isinstance(bar_times, list) and len(bar_times) == count:
        try:
            times = [int(t) for t in bar_times]
        except (TypeError, ValueError):
            return None
    return _axb1.encode_snapshot_plots(
        header,
        count=count,
        closed_upto=closed_upto,
        times=times,
        plots=plots,
    )


def _map_delta_multi_bar(header: Any, payload: dict[str, Any], scale: int) -> bytes | None:
    """AXB1 APPEND_BARS for a multi-bar series delta, JSON fallback = ``None``."""
    from pynescript.runtime import axb1 as _axb1

    bars = payload.get("bars")
    if not isinstance(bars, list) or len(bars) < 2:
        return None
    allowed = {"base_index", "count", "tail_len", "closed_upto", "forming", "bars"}
    if set(payload) - allowed or payload.get("unchanged") is True:
        return None
    count = payload.get("count")
    if not isinstance(count, int) or count < 1:
        return None
    if payload.get("tail_len") != len(bars) or "closed_upto" not in payload:
        return None
    closed_upto = int(payload["closed_upto"])
    time_s: list[int] = []
    columns: dict[str, list] = {"open": [], "high": [], "low": [], "close": [], "volume": []}
    try:
        for bar in bars:
            if not isinstance(bar, dict):
                return None
            time_s.append(int(bar["time"]))
            for field in ("open", "high", "low", "close"):
                columns[field].append(_axb1.price_to_ticks(float(bar[field]), scale))
            columns["volume"].append(float(bar["volume"]))
    except (KeyError, TypeError, ValueError):
        return None
    flags = [1 if t <= closed_upto else 2 for t in time_s]
    return _axb1.encode_append_bars(
        header,
        price_scale=scale,
        count=len(bars),
        closed_upto=closed_upto,
        closed_index=count - 1,
        time_s=time_s,
        flags=flags,
        ohlcv=columns,
        tip={"mask": 0, "flags": 0},
    )


def _map_delta_plots(header: Any, payload: dict[str, Any]) -> bytes | None:
    """AXB1 PLOT_TIP for a single-bar script delta, JSON fallback = ``None``."""
    from pynescript.runtime import axb1 as _axb1

    if payload.get("tail_len") != 1:
        return None
    allowed = {"base_index", "count", "tail_len", "closed_upto", "forming", "series", "plots", "bars"}
    if set(payload) - allowed or payload.get("unchanged") is True or "bars" in payload:
        return None
    count = payload.get("count")
    if not isinstance(count, int) or count < 1:
        return None
    series = payload.get("series")
    tips: list[dict[str, Any]] = []
    if isinstance(series, dict) and series:
        for key, values in series.items():
            if not isinstance(key, str) or not isinstance(values, list) or len(values) != 1:
                return None
            try:
                value = float(values[0])
            except (TypeError, ValueError):
                return None
            if not math.isfinite(value):
                return None
            tips.append(
                {"key_hash": _axb1.fnv1a32(key), "kind": _axb1.ValueKind.UnitFloat64, "value": value}
            )
    else:
        plots_list = payload.get("plots")
        if not isinstance(plots_list, list) or len(plots_list) != 1:
            return None
        inner = plots_list[0]
        if not isinstance(inner, list) or len(inner) != 1:
            return None
        try:
            value = float(inner[0])
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        tips.append(
            {"key_hash": _axb1.fnv1a32("0"), "kind": _axb1.ValueKind.UnitFloat64, "value": value}
        )
    if not tips:
        return None
    return _axb1.encode_plot_tip(header, tips)


def map_live_frame(
    frame: dict[str, Any],
    *,
    last_time: int | None = None,
    price_scale: int | None = None,
    mode: str = "basic",
) -> bytes | None:
    """Map one ``/ws/live`` JSON frame to AXB1 bytes; ``None`` = stay JSON.

    Pure and socket-free: builds the header from the frame's id/session/seq,
    dispatches per frame type, and returns None for anything it cannot
    represent losslessly. Requires a resolvable subscription id (it becomes
    ``sub_id_hash``, which the AXIS ingest side uses for routing).
    """
    from pynescript.runtime import axb1 as _axb1

    if not isinstance(frame, dict):
        return None
    raw_id = frame.get("id")
    if raw_id is None:
        return None
    payload = frame.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    header = _axb1.Header(
        seq=int(frame.get("seq") or 0),
        sub_id_hash=_axb1.fnv1a32(str(raw_id)),
        session_hash=_axb1.fnv1a32(str(frame.get("sessionId") or "")),
        ts_ms=int(frame.get("ts") or time.time() * 1000),
    )
    scale = price_scale if price_scale is not None else _axb1.PRICE_SCALE_DEFAULT
    mtype = frame.get("type")
    if mtype == "status":
        return _map_status(header, payload)
    if mtype == "full":
        out = _map_full(header, payload, scale)
        if out is None and mode == "full":
            out = _map_full_plots(header, payload)
        return out
    if mtype == "delta":
        out = _map_delta(header, payload, last_time, scale)
        if out is None and mode == "full":
            out = _map_delta_multi_bar(header, payload, scale)
        if out is None and mode == "full":
            out = _map_delta_plots(header, payload)
        return out
    if mtype == "close":
        return _map_close(header, payload, scale)
    if mtype == "error":
        return _map_error(header, frame, payload)
    return None  # pong / auth.ok / unknown control frames stay JSON
