# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Autonomous history ensure + session create/resume for ``WS /ws/live`` (F-13).

A WS ``subscribe`` never brokers a fetch from the client: this module checks
the series store, walks history to the last closed bar on a miss
(:func:`fetch_history`), creates the interpret session over the stored window
and binds + journal-tracks it — the same shape as ``POST /data/session``.
``resume`` re-enters through the session store so journaled sessions rebuild
after a restart.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any


def parse_live_key(key_text: str) -> Any | None:
    """``exchange|market|SYMBOL|interval`` → SeriesKey, or ``None``."""
    from backend.datastore import series as series_store

    parts = (key_text or "").split("|")
    if len(parts) != 4:
        return None
    exchange, market, symbol, interval = parts
    try:
        return series_store.make_key(exchange, symbol, interval, market)
    except Exception:
        return None


def key_text_symbol(series_key_text: str) -> str:
    """Symbol part of a canonical key text (display name for the runtime)."""
    parts = (series_key_text or "").split("|")
    return parts[2] if len(parts) == 4 else ""


def _pooled_window_moved_on(store: Any, key: Any, session: Any, history_bars: Any) -> bool:
    """True when a pooled session's window no longer overlaps the store tail.

    Pool hits are keyed by content fingerprint, blind to the bars underneath:
    after a repair / replace / purge the store window can move hundreds of
    bars past a pooled session's birth anchor, and resuming it would evaluate
    a window the chart left behind (stale overlays that survive reloads —
    the fingerprint never changes). A lag beyond the requested window means
    zero overlap, so recreate instead of resume. Anything closer is a live
    session mid-tick and must keep sharing.
    """
    try:
        from backend.datastore import live as data_live

        binding = data_live.binding_of(session)
        anchor = int(binding.last_time) if binding is not None else 0
        status = store.status(key)
        count = int(status.get("count") or 0)
        newest = int(status.get("newest") or 0)
        step = int(key.interval_seconds) or 60
        if count <= 0:
            return True
        if anchor <= 0 or newest <= anchor:
            return _pooled_window_has_covered_hole(store, key, session, history_bars)
        return (newest - anchor) // step > max(1, int(history_bars)) or _pooled_window_has_covered_hole(store, key, session, history_bars)
    except Exception:
        return False


def _pooled_window_has_covered_hole(store: Any, key: Any, session: Any, history_bars: Any) -> bool:
    """True when the pooled session skipped slots the store now covers.

    A session created while the store had a transient hole keeps that hole
    forever, even after the feed fills it — every subscriber then sees a
    flat/stale segment and the client holds its last good plots. Detect a
    session with an internal gap whose missing slots exist in the current
    store window; recreate instead of resuming.
    """
    try:
        bars = getattr(session, "_ohlcv_data", None)
        if not isinstance(bars, list) or len(bars) < 3:
            return False
        step = int(key.interval_seconds) or 60
        times: list[int] = []
        for bar in bars:
            if not isinstance(bar, dict):
                return False
            try:
                t = int(bar.get("time"))
            except (TypeError, ValueError):
                return False
            times.append(t)
        holes: list[tuple[int, int]] = []
        for a, b in pairwise(times):
            if b - a > step * 1.5:
                holes.append((a, b))
        if not holes:
            return False
        window = store.window(key, max(len(bars), int(history_bars) if history_bars else len(bars)))
        have = {int(b.get("time")) for b in window if isinstance(b, dict) and b.get("time") is not None}
        for start, end in holes:
            t = start + step
            while t < end:
                if t in have:
                    return True
                t += step
        return False
    except Exception:
        return False


def ensure_live_session(
    kind: str,
    series_key_text: str,
    history_bars: Any,
    *,
    script: str | None = None,
    inputs: dict[str, Any] | None = None,
    libraries: list[dict[str, Any]] | None = None,
    profiler: bool = False,
    symbol: str = "",
) -> dict[str, Any]:
    """Ensure history + session for a subscribe. Never raises.

    Outcomes: ``ready`` (``session_id`` may be ``None`` for ``series`` kind —
    bars serve straight from the store), ``short`` (``have``/``need`` — the
    caller keeps the client at ``datafeed-loading``), ``error`` (``code``).
    """
    from backend.api import data_series
    from backend.datastore import live as data_live
    from backend.datastore import series as series_store
    from backend.middleware.sessions import SESSIONS

    key = parse_live_key(series_key_text)
    if key is None:
        return {"outcome": "error", "code": "BAD_KEY", "message": "Unparseable series key."}
    try:
        history = series_store.check_history_bars(history_bars)
    except Exception:
        return {"outcome": "error", "code": "BAD_HISTORY", "message": "Unusable history_bars."}

    if kind == "script" and not script:
        return {"outcome": "error", "code": "NO_SCRIPT", "message": "Script subscriptions need a script."}

    store = series_store.get_store()
    have = int(store.status(key)["count"])
    if have < history:
        try:
            data_series.fetch_history(key, history)
        except Exception as exc:  # upstream/CCXT failure is data, not a 500
            from backend.api.data_series import DataError

            if isinstance(exc, DataError):
                return {"outcome": "error", "code": exc.code, "message": str(exc)}
            return {"outcome": "error", "code": "UPSTREAM", "message": f"History fetch failed: {exc}"}
        have = int(store.status(key)["count"])
    if have < history:
        return {"outcome": "short", "have": have, "need": history}

    bars = store.window(key, history)
    if not bars:
        return {"outcome": "short", "have": 0, "need": history}
    if kind == "series":
        newest = int(bars[-1]["time"])
        return {"outcome": "ready", "session_id": None, "count": len(bars), "newest": newest}

    from src.pynescript.runtime.host import Runtime

    ticker = symbol or str(key_text_symbol(series_key_text))
    fingerprint = SESSIONS.shared_fingerprint(
        script=script or "",
        symbol=f"{series_key_text}|{ticker}",
        inputs=inputs or {},
        libraries=libraries or [],
        profiler=bool(profiler),
    )

    def _factory() -> Any:
        runtime = Runtime(symbol=ticker)
        return runtime.create_session(
            script or "",
            bars,
            inputs=inputs or None,
            libraries=libraries or None,
            profiler=bool(profiler),
            mode="interpret",
        )

    try:
        session_id, created = SESSIONS.acquire_shared(fingerprint, _factory)
    except RuntimeError:
        return {"outcome": "error", "code": "SESSIONS_FULL", "message": "Session capacity reached."}
    except Exception as exc:
        return {"outcome": "error", "code": "SESSION_CREATE_FAILED", "message": str(exc)[:500]}

    session = SESSIONS.get(session_id)
    if session is None:
        return {"outcome": "error", "code": "SESSION_CREATE_FAILED", "message": "Shared session vanished."}
    if not created and _pooled_window_moved_on(store, key, session, history):
        # The store window moved past the pooled session (repair / replace /
        # purge + refetch, or a gap the session never saw): resuming it would
        # evaluate bars that no longer overlap the chart, and every later
        # resubscribe would hit the same stale entry. Drop it (other tabs
        # sharing this id get SESSION_GONE so they re-ensure) and create
        # fresh over the current window.
        stale_id = session_id
        SESSIONS.drop(stale_id)
        try:
            from backend.api.live_push import notify_session_gone

            notify_session_gone(stale_id)
        except Exception:
            pass
        try:
            session_id, created = SESSIONS.acquire_shared(fingerprint, _factory)
        except RuntimeError:
            return {"outcome": "error", "code": "SESSIONS_FULL", "message": "Session capacity reached."}
        except Exception as exc:
            return {"outcome": "error", "code": "SESSION_CREATE_FAILED", "message": str(exc)[:500]}
        session = SESSIONS.get(session_id)
        if session is None:
            return {"outcome": "error", "code": "SESSION_CREATE_FAILED", "message": "Shared session vanished."}
    if created:
        data_live.bind_session(session, key, bars[-1])
        binding = data_live.binding_of(session)
        SESSIONS.track(
            session_id,
            script=script or "",
            symbol=symbol,
            inputs=inputs or {},
            libraries=libraries or [],
            profiler=bool(profiler),
            bars=list(bars),
            binding=(
                {"key": binding.key.text, "last_time": binding.last_time, "last_bar": dict(binding.last_bar)}
                if binding is not None
                else None
            ),
        )
    return {"outcome": "ready", "session_id": session_id, "count": len(bars), "newest": int(bars[-1]["time"])}


def resume_live_session(session_id: str) -> dict[str, Any]:
    """Re-enter a session (journal rebuild included). Never raises."""
    from backend.middleware.sessions import SESSIONS

    try:
        session = SESSIONS.get(session_id)
    except Exception:
        session = None
    if session is None:
        return {"outcome": "gone"}
    bars = getattr(session, "_ohlcv_data", None) or []
    return {"outcome": "ready", "session": session, "count": len(bars)}
