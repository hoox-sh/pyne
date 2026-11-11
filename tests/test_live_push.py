# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""End-to-end push loop (F-13/F-19 prerequisite): subscribe → full, then a
feed batch advances the session and emits ``delta`` (+ ``close``) to the
socket. Feeds, sessions and sockets are all fakes except the real protocol,
registry, delta envelope and session math.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from backend.api.live_push import HUB
from backend.api.live_push import PushHub


@pytest.fixture(autouse=True)
def _disable_forming_conflate(monkeypatch):
    monkeypatch.setattr("backend.api.live_push.CONFLATE_MS", 0)


from backend.api.live_ws import LiveConnection
from backend.api.live_ws import LiveRegistry


META = {"exchange": "binance", "market": "spot", "symbol": "btc/usdt", "interval": "1m"}
KEY_TEXT = "binance|spot|BTC/USDT|1m"


def _bars10():
    return [
        {"time": 1_700_000_000 + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in range(10)
    ]


class _FakeSession:
    def __init__(self, bars):
        self._ohlcv_data = list(bars)
        self.ticks = []
        self.appends = []

    def update_last_bar(self, bar):
        self.ticks.append(dict(bar))
        self._ohlcv_data[-1] = dict(bar)

    def append_bars(self, bars):
        self.appends.extend([dict(b) for b in bars])
        self._ohlcv_data.extend([dict(b) for b in bars])

    def result(self):
        n = len(self._ohlcv_data)
        return {
            "plots": [[1.0] * n],
            "series": {"a": [1.0] * n},
            "count": n,
            "times": [int(b["time"]) for b in self._ohlcv_data],
        }


class _Outcome:
    def __init__(self, **kw):
        base = {"unchanged": False, "appended": 0, "forming": False, "grown": 0, "reticked": 0}
        base.update(kw)
        self.__dict__.update(base)


class FakeWs:
    def __init__(self):
        self.sent: list[dict] = []
        self._started = False
        self._idles = 0

    def receive(self, timeout=None):
        if not self._started:
            self._started = True
            return json.dumps(
                {"type": "subscribe", "id": "sub-1", "payload": {"kind": "script", "meta": META, "script": "x"}}
            )
        if self.sent or self._idles > 100:
            return None
        self._idles += 1
        if timeout is not None:
            raise TimeoutError("timeout")
        return ""

    def send(self, raw):
        self.sent.append(json.loads(raw))


def _serve_loop(ws, registry, **conn_kw):
    import backend.api.live_ws as ws_mod

    from backend.api.live_ws import serve_live_ws
    from backend.app import app

    real_conn_cls = ws_mod.LiveConnection

    def fake_conn_factory(registry=None, authed=False, **kw):
        extras = {k: v for k, v in kw.items() if k in ("hub", "sender")}
        return real_conn_cls(registry=registry, authed=True, **conn_kw, **extras)

    ws_mod.LiveConnection = fake_conn_factory  # type: ignore[assignment]
    try:
        with app.test_request_context("/ws/live"):
            serve_live_ws(_DisconnectOnNone(ws), registry)
    finally:
        ws_mod.LiveConnection = real_conn_cls


class _DisconnectOnNone:
    """Test-socket adapter: ``receive() -> None`` means "peer closed".

    ``serve_live_ws`` follows ``simple_websocket`` semantics, where ``None``
    only means "timeout" and the loop ends when ``connected`` goes false.
    The fakes in this module signal a close by returning ``None`` (timeouts
    raise ``TimeoutError`` / return ``""``), so translate that convention.
    """

    def __init__(self, ws):
        self._ws = ws
        self.connected = True

    def receive(self, timeout=None):
        msg = self._ws.receive(timeout)
        if msg is None:
            self.connected = False
        return msg

    def send(self, raw):
        self._ws.send(raw)


def _join_ensure_workers(timeout=2.0):
    for t in list(threading.enumerate()):
        if t.name == "live-ws-ensure" and t is not threading.current_thread():
            t.join(timeout)


_READY_BAR = {"time": 1, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}


def test_push_hub_routes_and_drops_dead_sockets():
    hub = PushHub()
    seen = []
    hub.register("c1", seen.append)
    assert hub.send("c1", {"a": 1}) is True
    assert seen == [{"a": 1}]

    def _boom(_f):
        raise RuntimeError("dead")

    hub.register("c2", _boom)
    assert hub.send("c2", {"a": 1}) is False
    assert hub.send("ghost", {"a": 1}) is False


def test_feed_batch_emits_delta_to_socket(monkeypatch):
    import backend.api.live_push as push_mod

    session = _FakeSession(_bars10())
    registry = LiveRegistry()
    record = registry.subscribe("sub-1", "script", KEY_TEXT, 10)
    registry.attach("sub-1", "ses-1", _bars10())

    sent: list[dict] = []
    hub = PushHub()
    hub.register("sub-1", sent.append)

    monkeypatch.setattr(push_mod, "HUB", hub)

    class _FakeManager:
        def subscribe(self, key_text, session_id, cb):
            self.cb = cb
            return True

        def unsubscribe(self, key_text, session_id):
            return None

    fake_manager = _FakeManager()

    import backend.middleware.sessions as sessions_mod

    monkeypatch.setattr(sessions_mod.SESSIONS, "get", lambda _sid: session)

    attached = []

    def fake_attach(key_text, engine_session_id, client_id, reg, hub=None):
        attached.append((key_text, engine_session_id, client_id))

        def on_candles(candles):
            from backend.datastore import live as live_mod

            binding = live_mod.bind_session(session, _key(), session._ohlcv_data[-1])
            outcome = _Outcome(grown=1, reticked=0, appended=0, forming=True)
            for frame in push_mod.emit_push_frames(
                client_id, reg, session, engine_session_id, binding, outcome, candles, 1_700_000_000 + 10 * 60 + 30
            ):
                (hub or push_mod.HUB).send(client_id, frame)

        fake_manager.subscribe(key_text, engine_session_id, on_candles)
        return True

    def _key():
        from backend.datastore import series as series_store

        return series_store.make_key("binance", "BTC/USDT", "1m", "spot")

    conn = LiveConnection(
        registry=registry,
        authed=True,
        ensurer=lambda kind, key, history, **kw: {"outcome": "ready", "session_id": "ses-1", "count": 10, "newest": 1},
        resumer=lambda sid: {"outcome": "ready", "session": session, "count": 10},
        store_window=lambda _k, _l: _bars10(),
        hub=hub,
        sender=sent.append,
        attacher=fake_attach,
    )
    replies = conn.handle_dict(
        {"type": "subscribe", "id": "sub-1", "payload": {"kind": "script", "meta": META, "script": "x"}}
    )
    assert [r.get("type") for r in replies] == ["status", "status", "full", "status"]
    assert attached == [(KEY_TEXT, "ses-1", "sub-1")]

    # One forming tick on top of the 10-bar window.
    tick = dict(_bars10()[-1])
    tick["close"] = 1.5
    fake_manager.cb([tick])
    deltas = [f for f in sent if f.get("type") == "delta"]
    assert len(deltas) == 1
    delta = deltas[0]
    assert delta["type"] == "delta"
    assert delta["seq"] == 2
    assert delta["payload"]["tail_len"] == 1
    assert delta["payload"]["closed_upto"] == 0 or isinstance(delta["payload"]["closed_upto"], int)
    # The tail's bar-time axis travels with the delta (no axis = the client can
    # only trust its own chart, which is how a cross-timeframe merge goes
    # unnoticed). It is the evaluated result's own tail, never the feed batch.
    assert delta["payload"]["times"] == [int(tick["time"])]
    # And the frame names its timeframe so a client can assert before joining.
    assert delta["payload"]["interval"] == "1m"


def test_serve_loop_subscribe_over_fake_socket():
    ws = FakeWs()
    conn_registry = LiveRegistry()
    _serve_loop(
        ws,
        conn_registry,
        ensurer=lambda kind, key, history, **_: {"outcome": "short", "have": 0, "need": 50},
    )
    assert ws.sent and ws.sent[0]["payload"]["code"] == "datafeed-loading"
    assert HUB is not None


def test_serve_loop_answers_ping_while_ensure_blocks():
    started = threading.Event()
    release = threading.Event()

    def ensurer(*_a, **_k):
        started.set()
        assert release.wait(2)
        return {"outcome": "short", "have": 0, "need": 50}

    class Ws:
        def __init__(self):
            self.sent: list[dict] = []
            self.step = 0

        def receive(self, timeout=None):
            if self.step == 0:
                self.step = 1
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 1:
                assert started.wait(2)
                self.step = 2
                return json.dumps({"type": "ping", "id": "p"})
            release.set()
            self.step = 3
            return None

        def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = Ws()
    _serve_loop(ws, LiveRegistry(), ensurer=ensurer)
    types = [f.get("type") for f in ws.sent]
    assert "pong" in types
    assert any((f.get("payload") or {}).get("code") == "datafeed-loading" for f in ws.sent)


def test_serve_loop_duplicate_subscribe_while_ensure_blocks_single_full():
    started = threading.Event()
    release = threading.Event()
    ensure_calls: list[int] = []
    attached: list[str] = []

    def ensurer(*_a, **_k):
        ensure_calls.append(1)
        started.set()
        assert release.wait(2)
        return {"outcome": "ready", "session_id": None, "count": 1, "newest": 1}

    class Ws:
        def __init__(self):
            self.sent: list[dict] = []
            self.step = 0

        def receive(self, timeout=None):
            if self.step == 0:
                self.step = 1
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 1:
                assert started.wait(2)
                self.step = 2
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if not any(f.get("type") == "full" for f in self.sent):
                release.set()
                if timeout is not None:
                    raise TimeoutError("timeout")
                return ""
            return None

        def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = Ws()
    registry = LiveRegistry()
    _serve_loop(
        ws,
        registry,
        ensurer=ensurer,
        store_window=lambda *_a, **_k: [_READY_BAR],
        attacher=lambda *_a, **_k: attached.append("s"),
    )
    fulls = [f for f in ws.sent if f.get("type") == "full"]
    assert len(ensure_calls) == 1
    assert len(fulls) == 1
    assert len(attached) == 1


def test_serve_loop_close_during_ensure_does_not_attach(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    attached: list[str] = []
    hub = PushHub()
    monkeypatch.setattr("backend.api.live_push.HUB", hub)

    def ensurer(*_a, **_k):
        started.set()
        assert release.wait(2)
        return {"outcome": "ready", "session_id": None, "count": 1, "newest": 1}

    class Ws:
        def __init__(self):
            self.sent: list[dict] = []
            self.step = 0

        def receive(self, timeout=None):
            if self.step == 0:
                self.step = 1
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 1:
                assert started.wait(2)
                self.step = 2
                return None

        def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = Ws()
    registry = LiveRegistry()
    _serve_loop(
        ws,
        registry,
        ensurer=ensurer,
        store_window=lambda *_a, **_k: [_READY_BAR],
        attacher=lambda *_a, **_k: attached.append("s"),
    )
    release.set()
    _join_ensure_workers()
    assert attached == []
    assert hub._senders.get("s") is None
    assert registry.get("s") is None


def test_serve_loop_receive_error_during_ensure_does_not_attach(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    attached: list[str] = []
    hub = PushHub()
    monkeypatch.setattr("backend.api.live_push.HUB", hub)

    def ensurer(*_a, **_k):
        started.set()
        assert release.wait(2)
        return {"outcome": "ready", "session_id": None, "count": 1, "newest": 1}

    class Ws:
        def __init__(self):
            self.sent: list[dict] = []
            self.step = 0

        def receive(self, timeout=None):
            if self.step == 0:
                self.step = 1
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 1:
                assert started.wait(2)
                self.step = 2
                raise ConnectionError("socket gone")

        def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = Ws()
    registry = LiveRegistry()
    _serve_loop(
        ws,
        registry,
        ensurer=ensurer,
        store_window=lambda *_a, **_k: [_READY_BAR],
        attacher=lambda *_a, **_k: attached.append("s"),
    )
    release.set()
    _join_ensure_workers()
    assert attached == []
    assert hub._senders.get("s") is None
    assert registry.get("s") is None


def test_serve_loop_unsubscribe_during_ensure_skips_attach():
    started = threading.Event()
    release = threading.Event()
    attached: list[str] = []

    def ensurer(*_a, **_k):
        started.set()
        assert release.wait(2)
        return {"outcome": "ready", "session_id": None, "count": 1, "newest": 1}

    class Ws:
        def __init__(self):
            self.sent: list[dict] = []
            self.step = 0
            self._idles = 0

        def receive(self, timeout=None):
            if self.step == 0:
                self.step = 1
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 1:
                assert started.wait(2)
                self.step = 2
                return json.dumps({"type": "unsubscribe", "id": "s"})
            if self.step == 2:
                release.set()
                self.step = 3
            if any(f.get("type") == "full" for f in self.sent):
                return None
            if self._idles > 100:
                return None
            self._idles += 1
            if timeout is not None:
                raise TimeoutError("timeout")
            return ""

        def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = Ws()
    registry = LiveRegistry()
    _serve_loop(
        ws,
        registry,
        ensurer=ensurer,
        store_window=lambda *_a, **_k: [_READY_BAR],
        attacher=lambda *_a, **_k: attached.append("s"),
    )
    assert any((f.get("payload") or {}).get("code") == "idle" for f in ws.sent)
    assert not any(f.get("type") == "full" for f in ws.sent)
    assert attached == []
    assert registry.get("s") is None


def test_serve_loop_unsubscribe_then_subscribe_gets_full():
    started = threading.Event()
    release = threading.Event()
    attached: list[str] = []
    ensure_calls: list[int] = []

    def ensurer(*_a, **_k):
        ensure_calls.append(1)
        started.set()
        assert release.wait(2)
        return {"outcome": "ready", "session_id": None, "count": 1, "newest": 1}

    class Ws:
        def __init__(self):
            self.sent: list[dict] = []
            self.step = 0

        def receive(self, timeout=None):
            if self.step == 0:
                self.step = 1
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 1:
                assert started.wait(2)
                started.clear()
                self.step = 2
                return json.dumps({"type": "unsubscribe", "id": "s"})
            if self.step == 2:
                self.step = 3
                return json.dumps({"type": "subscribe", "id": "s", "payload": {"kind": "series", "meta": META}})
            if self.step == 3:
                assert started.wait(2), "second subscribe did not start ensure"
                self.step = 4
                release.set()
            if any(f.get("type") == "full" for f in self.sent):
                return None
            if timeout is not None:
                raise TimeoutError("timeout")
            return ""

        def send(self, raw):
            self.sent.append(json.loads(raw))

    ws = Ws()
    registry = LiveRegistry()
    _serve_loop(
        ws,
        registry,
        ensurer=ensurer,
        store_window=lambda *_a, **_k: [_READY_BAR],
        attacher=lambda *_a, **_k: attached.append("s"),
    )
    _join_ensure_workers()
    assert any((f.get("payload") or {}).get("code") == "idle" for f in ws.sent)
    assert len([f for f in ws.sent if f.get("type") == "full"]) == 1
    assert len(attached) == 1


def test_series_push_emits_bars_delta_and_close():
    from backend.api import live_push as push_mod

    registry = LiveRegistry()
    registry.subscribe("sub-s", "series", KEY_TEXT, 10)
    registry.attach("sub-s", None, _bars10())
    record = registry.get("sub-s")
    assert record is not None
    batch = [
        {"time": 1_700_000_000 + 10 * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        {"time": 1_700_000_000 + 11 * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
    ]
    now_s = 1_700_000_000 + 11 * 60 + 61
    frames = push_mod.emit_series_push("sub-s", registry, record, batch, now_s)
    assert frames[0]["type"] == "delta"
    assert frames[0]["payload"]["base_index"] == 10
    assert frames[0]["payload"]["count"] == 12
    assert frames[0]["payload"]["tail_len"] == 2
    assert frames[0]["payload"]["bars"] == batch
    assert frames[1]["type"] == "close"
    assert frames[1]["payload"]["time"] == 1_700_000_000 + 11 * 60
    assert record["count"] == 12


def test_series_push_forming_retick_does_not_grow_count():
    from backend.api import live_push as push_mod

    registry = LiveRegistry()
    registry.subscribe("sub-s", "series", KEY_TEXT, 10)
    registry.attach("sub-s", None, _bars10())
    record = registry.get("sub-s")
    assert record is not None
    assert record["count"] == 10
    tip_time = 1_700_000_000 + 9 * 60
    batch = [{"time": tip_time, "open": 1.0, "high": 2.0, "low": 1.0, "close": 1.5, "volume": 3.0}]
    now_s = tip_time + 10
    frames = push_mod.emit_series_push("sub-s", registry, record, batch, now_s)
    assert frames[0]["type"] == "delta"
    assert frames[0]["payload"]["count"] == 10
    assert frames[0]["payload"]["tail_len"] == 1
    assert frames[0]["payload"]["base_index"] == 9
    assert frames[0]["payload"]["bars"] == batch
    assert record["count"] == 10
    # A second re-tick of the same slot still does not invent bars.
    frames2 = push_mod.emit_series_push("sub-s", registry, record, batch, now_s)
    assert frames2[0]["payload"]["count"] == 10
    assert record["count"] == 10


def test_forming_batches_conflate_on_the_feed_thread(monkeypatch):
    import backend.api.live_push as push_mod

    monkeypatch.setattr(push_mod, "CONFLATE_MS", 40)
    registry = LiveRegistry()
    registry.subscribe("sub-s", "series", KEY_TEXT, 10)
    registry.attach("sub-s", None, _bars10())
    sent: list[dict] = []
    hub = PushHub()
    hub.register("sub-s", sent.append)
    monkeypatch.setattr(push_mod, "HUB", hub)

    class _Mgr:
        def subscribe(self, key_text, session_id, cb):
            self.cb = cb
            return True

        def unsubscribe(self, *_a):
            return None

    mgr = _Mgr()
    monkeypatch.setattr("backend.api.feed_manager.get_feed_manager", lambda: mgr)
    monkeypatch.setattr(push_mod, "persist_feed_bars", lambda *_a, **_k: True)
    assert push_mod.attach_feed(KEY_TEXT, "ses", "sub-s", registry, hub) is True
    tip_time = 1_700_000_000 + 9 * 60
    mgr.cb([{"time": tip_time, "open": 1.0, "high": 1.1, "low": 1.0, "close": 1.05, "volume": 1.0}])
    mgr.cb([{"time": tip_time, "open": 1.0, "high": 1.2, "low": 1.0, "close": 1.15, "volume": 2.0}])
    assert sent == []
    deadline = time.time() + 1.0
    while time.time() < deadline and not sent:
        time.sleep(0.02)
    deltas = [f for f in sent if f.get("type") == "delta"]
    assert len(deltas) == 1
    assert deltas[0]["payload"]["bars"][0]["close"] == 1.15


def test_notify_session_gone_reaches_attached_clients():
    from backend.api import live_push as push_mod

    registry = LiveRegistry()
    registry.subscribe("sub-a", "script", KEY_TEXT, 10)
    registry.subscribe("sub-b", "script", KEY_TEXT, 10)
    registry.attach("sub-a", "eng-1", _bars10())
    registry.attach("sub-b", "eng-1", _bars10())
    sent: list[dict] = []
    hub = PushHub()
    hub.register("sub-a", sent.append)
    hub.register("sub-b", sent.append)
    n = push_mod.notify_session_gone("eng-1", registry=registry, hub=hub)
    assert n == 2
    assert {f["id"] for f in sent} == {"sub-a", "sub-b"}
    assert all(f["code"] == "SESSION_GONE" and f["retryable"] is True for f in sent)
    assert push_mod.notify_session_gone("nobody", registry=registry, hub=hub) == 0


def test_attach_feed_gone_session_emits_session_gone(monkeypatch):
    from backend.api import live_push as push_mod
    from backend.middleware.sessions import SESSIONS

    registry = LiveRegistry()
    registry.subscribe("sub-s", "script", KEY_TEXT, 10)
    registry.attach("sub-s", "missing-ses", _bars10())
    sent: list[dict] = []
    hub = PushHub()
    hub.register("sub-s", sent.append)
    monkeypatch.setattr(push_mod, "HUB", hub)

    class _Mgr:
        def subscribe(self, key_text, session_id, cb):
            self.cb = cb
            return True

        def unsubscribe(self, *_a):
            self.unsubscribed = True

    mgr = _Mgr()
    monkeypatch.setattr("backend.api.feed_manager.get_feed_manager", lambda: mgr)
    monkeypatch.setattr(push_mod, "persist_feed_bars", lambda *_a, **_k: True)
    monkeypatch.setattr(SESSIONS, "get", lambda *_a, **_k: None)
    assert push_mod.attach_feed(KEY_TEXT, "missing-ses", "sub-s", registry, hub) is True
    mgr.cb([{"time": 1_700_000_000, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}])
    assert sent and sent[0]["code"] == "SESSION_GONE"
    assert getattr(mgr, "unsubscribed", False) is True


# ---------------------------------------------------------------------------
# Store sink: the feed keeps the stored series advancing.
#
# The engine's live feed advances *sessions* walk-free; nothing on that path
# touched the series store, so a kind:series subscription (and every reader of
# GET /data/series) reported `newest` frozen at the bar history was ensured at
# — lagging the venue forever while the feed streamed the very bars that would
# have healed it.
# ---------------------------------------------------------------------------


def _provide(bars):
    from backend.datastore import series as series_store

    key = series_store.make_key("binance", "BTC/USDT", "1m", "spot")
    series_store.get_store().provide(key, bars, source="test")
    return key


@pytest.fixture()
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PYNE_DATA_DIR", str(tmp_path / "data"))
    import backend.api.live_push as push_mod

    push_mod._persisted.clear()
    yield
    push_mod._persisted.clear()


def test_persist_feed_bars_advances_stored_bounds(_isolated):
    import backend.api.live_push as push_mod

    from backend.datastore import series as series_store

    key = _provide(_bars10())
    before = series_store.get_store().status(key)
    assert before["newest"] == _bars10()[-1]["time"]

    newer = dict(_bars10()[-1], time=before["newest"] + 60, close=1.5)
    assert push_mod.persist_feed_bars(KEY_TEXT, [newer], now_ms=1_000) is True

    after = series_store.get_store().status(key)
    assert after["newest"] == newer["time"]
    assert after["count"] == before["count"] + 1


def test_persist_feed_bars_updates_the_forming_row_and_throttles_reticks(_isolated, monkeypatch):
    import backend.api.live_push as push_mod

    from backend.datastore import series as series_store

    key = _provide(_bars10())
    provides: list = []
    real_get_store = series_store.get_store

    class _CountingStore:
        def __init__(self, store):
            self._store = store

        def provide(self, *args, **kwargs):
            provides.append((args, kwargs))
            return self._store.provide(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._store, name)

    monkeypatch.setattr(series_store, "get_store", lambda: _CountingStore(real_get_store()))

    tip = dict(_bars10()[-1], close=2.0)
    assert push_mod.persist_feed_bars(KEY_TEXT, [tip], now_ms=1_000) is True
    # The forming row lands upserted, so the next snapshot serves the live tip.
    assert series_store.get_store().window(key, 1)[0]["close"] == 2.0
    # Re-ticks of the same slot inside the window are dropped …
    assert push_mod.persist_feed_bars(KEY_TEXT, [tip], now_ms=1_500) is False
    # … and written once the window elapses, or as soon as a new slot opens.
    assert push_mod.persist_feed_bars(KEY_TEXT, [tip], now_ms=1_000 + push_mod.PERSIST_MIN_MS) is True
    newer = dict(tip, time=tip["time"] + 60)
    assert push_mod.persist_feed_bars(KEY_TEXT, [newer], now_ms=1_001 + push_mod.PERSIST_MIN_MS) is True
    assert len(provides) == 3


def test_persist_feed_bars_fails_soft(_isolated, monkeypatch):
    import backend.api.live_push as push_mod

    from backend.datastore import series as series_store

    _provide(_bars10())
    assert push_mod.persist_feed_bars("junk", [_bars10()[-1]]) is False
    assert push_mod.persist_feed_bars(KEY_TEXT, []) is False
    assert push_mod.persist_feed_bars(KEY_TEXT, ["junk"]) is False

    message = "db down"

    def _boom(*_args, **_kwargs):
        raise RuntimeError(message)

    monkeypatch.setattr(series_store, "get_store", _boom)
    assert push_mod.persist_feed_bars(KEY_TEXT, [_bars10()[-1]], now_ms=9_000) is False


def test_series_subscription_attaches_feed_and_persists(_isolated, monkeypatch):
    """A kind:series subscribe now binds its feed: deltas reach the socket and
    the stored bounds move, instead of a frozen ensure-time snapshot."""
    import backend.api.feed_manager as feed_mod

    from backend.datastore import series as series_store

    key = _provide(_bars10())
    registry = LiveRegistry()
    attached: list = []

    class _FakeManager:
        def subscribe(self, key_text, session_id, callback):
            attached.append((key_text, session_id))
            self.cb = callback
            return True

        def unsubscribe(self, key_text, session_id):
            return None

    manager = _FakeManager()
    monkeypatch.setattr(feed_mod, "get_feed_manager", lambda: manager)

    sent: list[dict] = []
    hub = PushHub()
    hub.register("sub-s", sent.append)

    conn = LiveConnection(
        registry=registry,
        authed=True,
        ensurer=lambda _kind, _key, _history, **_kw: {
            "outcome": "ready",
            "session_id": None,
            "count": 10,
            "newest": 1,
        },
        store_window=lambda _k, _l: _bars10(),
        hub=hub,
        sender=sent.append,
    )
    replies = conn.handle_dict({"type": "subscribe", "id": "sub-s", "payload": {"kind": "series", "meta": META}})
    assert [r["type"] for r in replies] == ["status", "full", "status"]

    # The listener id is the subscription's own live id — stable per client +
    # series, so a re-subscribe replaces the listener instead of stacking one.
    assert attached == [(KEY_TEXT, "live_1")]

    batch = [dict(_bars10()[-1], time=_bars10()[-1]["time"] + 60, close=1.5)]
    manager.cb(batch)

    deltas = [f for f in sent if f.get("type") == "delta"]
    assert deltas[0]["type"] == "delta"
    assert deltas[0]["payload"]["bars"] == batch
    assert deltas[0]["payload"]["base_index"] == 10
    assert series_store.get_store().status(key)["newest"] == batch[0]["time"]
