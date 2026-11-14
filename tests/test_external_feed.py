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

"""External feed (``backend.data.external_feed``): key mapping, cursor, sync.

No test touches the network: HTTP goes through a monkeypatched ``urlopen``
and the background loop is never started (or is stubbed) unless a test opts in.
"""

from __future__ import annotations

import io
import json

import pytest

from backend.data import external_feed
from backend.data.external_feed import ExternalFeedConfig
from backend.data.external_feed import FeedCursor
from backend.data.external_feed import FeedFetchError
from backend.data.external_feed import FeedResyncRequired
from backend.data.external_feed import canonical_feed_key
from backend.datastore.series import DataError
from backend.datastore.series import SeriesKey


def make_bar(t, px=100.0, closed=True):
    return {"time": t, "open": px, "high": px + 1, "low": px - 1, "close": px + 0.5, "volume": 10.0, "closed": closed}


def delta_frame(seq, times, forming=False, px=100.0):
    n = len(times)
    return {
        "feed": "binance|linear|BTC/USDT|1m|none|public",
        "seq": seq,
        "forming": forming,
        "upTo": times[-1] if times else 0,
        "times": list(times),
        "open": [px] * n,
        "high": [px + 1] * n,
        "low": [px - 1] * n,
        "close": [px + 0.5] * n,
        "volume": [10.0] * n,
    }


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch, tmp_path):
    """Restore module-level state mutated by the sync loop / registration."""
    monkeypatch.setenv("PYNE_DATA_DIR", str(tmp_path / "data"))
    saved = {
        "_started": external_feed._started,
        "_thread": external_feed._thread,
        "last_error": external_feed.last_error,
        "error_count": external_feed.error_count,
        "last_sync_at": external_feed.last_sync_at,
    }
    watches = dict(external_feed._watches)
    external_feed._watches.clear()
    external_feed.last_error = None
    external_feed.error_count = 0
    external_feed.last_sync_at = None
    external_feed._started = False
    external_feed._thread = None
    yield
    external_feed._watches.clear()
    external_feed._watches.update(watches)
    external_feed._started = saved["_started"]
    external_feed._thread = saved["_thread"]
    external_feed.last_error = saved["last_error"]
    external_feed.error_count = saved["error_count"]
    external_feed.last_sync_at = saved["last_sync_at"]


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeStore:
    def __init__(self):
        self.calls = []

    def provide(self, key, bars, source=""):
        rows = list(bars)
        self.calls.append({"key": key, "bars": rows, "source": source})
        return {
            "key": key.text,
            "added": len(rows),
            "updated": 0,
            "count": len(rows),
            "oldest": rows[0]["time"] if rows else None,
            "newest": rows[-1]["time"] if rows else None,
            "updated_at": 0,
        }

    def status(self, key):
        return {"key": key.text, "count": 0, "oldest": None, "newest": None, "updated_at": None}


# ── canonical_feed_key ───────────────────────────────────────────────────────


def test_canonical_feed_key_maps_markets():
    assert canonical_feed_key("Binance", "spot", "btc/usdt", "1m") == "binance|spot|BTC/USDT|1m|none|public"
    assert canonical_feed_key("binance", "swap", "BTC/USDT", "1h") == "binance|linear|BTC/USDT|1h|none|public"
    assert canonical_feed_key("binance", "future", "BTC/USDT", "4h") == "binance|linear|BTC/USDT|4h|none|public"
    assert canonical_feed_key("binance", "linear", "BTC/USDT", "1d") == "binance|linear|BTC/USDT|1d|none|public"
    assert canonical_feed_key("binance", "inverse", "BTC/USDT", "1d") == "binance|inverse|BTC/USDT|1d|none|public"


def test_canonical_feed_key_rejects_unknown_market():
    with pytest.raises(DataError):
        canonical_feed_key("binance", "margin", "BTC/USDT", "1m")


def test_canonical_feed_key_rejects_empty_parts():
    with pytest.raises(DataError):
        canonical_feed_key("", "spot", "BTC/USDT", "1m")
    with pytest.raises(DataError):
        canonical_feed_key("binance", "spot", "", "1m")
    with pytest.raises(DataError):
        canonical_feed_key("binance", "spot", "BTC/USDT", "")


# ── FeedCursor ───────────────────────────────────────────────────────────────


def test_apply_snapshot_sets_state_and_pending():
    cursor = FeedCursor()
    bars = [make_bar(1000 + i * 60) for i in range(3)]
    out = cursor.apply_snapshot({"seq": 7, "bars": bars})
    assert cursor.last_seq == 7
    assert [b["time"] for b in out] == [1000, 1060, 1120]
    assert len(cursor.take_pending()) == 3
    assert cursor.take_pending() == []


def test_apply_delta_appends_newer_bars():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 1, "bars": [make_bar(1000)]})
    cursor.take_pending()
    out = cursor.apply_delta(delta_frame(2, [1060, 1120]))
    assert [b["time"] for b in out] == [1000, 1060, 1120]
    assert cursor.last_seq == 2
    pending = cursor.take_pending()
    assert [b["time"] for b in pending] == [1060, 1120]


def test_apply_delta_overwrites_forming_tip():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 1, "bars": [make_bar(1000, closed=False)]})
    cursor.take_pending()
    out = cursor.apply_delta(delta_frame(2, [1000], forming=True, px=200.0))
    assert out[-1]["time"] == 1000
    assert out[-1]["close"] == 200.5
    assert out[-1]["closed"] is False


def test_apply_delta_rejects_older_than_tip():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 1, "bars": [make_bar(1000), make_bar(1060)]})
    with pytest.raises(FeedResyncRequired):
        cursor.apply_delta(delta_frame(2, [1000]))


def test_apply_delta_rejects_rewrite_of_closed_tip():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 1, "bars": [make_bar(1000, closed=True)]})
    with pytest.raises(FeedResyncRequired):
        cursor.apply_delta(delta_frame(2, [1000]))


def test_apply_delta_seq_gap_requires_resync():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 5, "bars": [make_bar(1000)]})
    with pytest.raises(FeedResyncRequired):
        cursor.apply_delta(delta_frame(7, [1060]))


def test_apply_delta_duplicate_seq_is_noop():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 5, "bars": [make_bar(1000)]})
    before = list(cursor.bars)
    out = cursor.apply_delta(delta_frame(5, [1060]))
    assert [b["time"] for b in out] == [b["time"] for b in before]
    assert cursor.last_seq == 5


def test_apply_delta_rejects_non_increasing_times():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 1, "bars": [make_bar(1000)]})
    with pytest.raises(FeedResyncRequired):
        cursor.apply_delta(delta_frame(2, [1120, 1060]))


def test_apply_delta_rejects_length_mismatch():
    cursor = FeedCursor()
    cursor.apply_snapshot({"seq": 1, "bars": [make_bar(1000)]})
    bad = delta_frame(2, [1060, 1120])
    bad["open"] = [1.0]
    with pytest.raises(FeedResyncRequired):
        cursor.apply_delta(bad)


# ── HTTP layer (monkeypatched urlopen) ───────────────────────────────────────


def _cfg() -> ExternalFeedConfig:
    return ExternalFeedConfig(
        source="external", url="https://feed.example", api_key="k", poll_s=1.0, provide_limit=1000
    )


def test_fetch_snapshot_parses_bars(monkeypatch):
    payload = {
        "kind": "snapshot",
        "feed": "f",
        "seq": 9,
        "from": 1000,
        "to": 1120,
        "bars": [make_bar(1000), make_bar(1060), make_bar(1120)],
    }
    monkeypatch.setattr(external_feed.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse(payload))
    bars = external_feed.fetch_snapshot(_cfg(), "f", 10)
    assert [b["time"] for b in bars] == [1000, 1060, 1120]


def test_fetch_delta_parses_deltas(monkeypatch):
    payload = {"seq": 8, "deltas": [delta_frame(8, [1060])]}
    monkeypatch.setattr(external_feed.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse(payload))
    deltas, new_seq = external_feed.fetch_delta(_cfg(), "f", 7)
    assert new_seq == 8
    assert deltas[0]["seq"] == 8


def test_fetch_delta_delta_gone_raises_resync(monkeypatch):
    payload = {"error": "delta_gone"}
    monkeypatch.setattr(external_feed.urllib.request, "urlopen", lambda req, timeout=None: FakeResponse(payload))
    with pytest.raises(FeedResyncRequired):
        external_feed.fetch_delta(_cfg(), "f", 3)


def test_fetch_delta_http_410_raises_resync(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 410, "gone", hdrs=None, fp=io.BytesIO(b""))

    monkeypatch.setattr(external_feed.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(FeedResyncRequired):
        external_feed.fetch_delta(_cfg(), "f", 3)


def test_fetch_snapshot_http_error_raises_fetch_error(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", hdrs=None, fp=io.BytesIO(b""))

    monkeypatch.setattr(external_feed.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(FeedFetchError):
        external_feed.fetch_snapshot(_cfg(), "f", 10)


# ── sync_feed ────────────────────────────────────────────────────────────────


def test_sync_feed_writes_through_store_provide():
    store = FakeStore()
    key = SeriesKey(exchange="binance", market="spot", symbol="BTC/USDT", interval="1m")
    result = external_feed.sync_feed(store, key, [make_bar(1000), make_bar(1060)])
    assert result["added"] == 2
    assert store.calls[0]["source"] == "external-feed"
    assert [b["time"] for b in store.calls[0]["bars"]] == [1000, 1060]
    # Bars reaching the store carry only OHLCV + time (no cursor bookkeeping).
    assert set(store.calls[0]["bars"][0]) == {"time", "open", "high", "low", "close", "volume"}


def test_sync_feed_empty_bars_does_not_touch_store():
    store = FakeStore()
    key = SeriesKey(exchange="binance", market="spot", symbol="BTC/USDT", interval="1m")
    result = external_feed.sync_feed(store, key, [])
    assert result["added"] == 0
    assert store.calls == []


# ── sync_one end to end (mocked transport) ───────────────────────────────────


def test_sync_one_snapshot_then_delta(monkeypatch):
    monkeypatch.setenv("PYNE_FEED_SOURCE", "external")
    monkeypatch.setenv("PYNE_FEED_URL", "https://feed.example")
    frames = iter(
        [
            {"kind": "snapshot", "feed": "f", "seq": 1, "from": 1000, "to": 1000, "bars": [make_bar(1000)]},
            {"seq": 2, "deltas": [delta_frame(2, [1060])]},
        ]
    )
    monkeypatch.setattr(external_feed, "_request", lambda cfg, path: next(frames))
    key = SeriesKey(exchange="binance", market="spot", symbol="BTC/USDT", interval="1m")
    feed_key = canonical_feed_key("binance", "spot", "BTC/USDT", "1m")
    external_feed.register_watch(feed_key, key)

    class _Store(FakeStore):
        pass

    store = _Store()
    monkeypatch.setattr(external_feed.series_store, "get_store", lambda: store)

    first = external_feed.sync_one(feed_key)
    assert first["fetched"] == 1
    assert [b["time"] for b in store.calls[0]["bars"]] == [1000]

    second = external_feed.sync_one(feed_key)
    assert second["fetched"] == 1
    assert [b["time"] for b in store.calls[1]["bars"]] == [1060]


def test_sync_one_delta_gone_triggers_snapshot(monkeypatch):
    monkeypatch.setenv("PYNE_FEED_SOURCE", "external")
    monkeypatch.setenv("PYNE_FEED_URL", "https://feed.example")
    calls: list[str] = []

    def fake_request(cfg, path):
        calls.append(path)
        if "/api/feed/delta" in path:
            return {"error": "delta_gone"}
        return {
            "kind": "snapshot",
            "feed": "f",
            "seq": 9,
            "from": 1000,
            "to": 1120,
            "bars": [make_bar(1000), make_bar(1060), make_bar(1120)],
        }

    monkeypatch.setattr(external_feed, "_request", fake_request)
    key = SeriesKey(exchange="binance", market="spot", symbol="BTC/USDT", interval="1m")
    feed_key = canonical_feed_key("binance", "spot", "BTC/USDT", "1m")
    external_feed.register_watch(feed_key, key)
    external_feed._get_watch(feed_key).cursor.apply_snapshot({"seq": 5, "bars": [make_bar(940)]})
    store = FakeStore()
    monkeypatch.setattr(external_feed.series_store, "get_store", lambda: store)

    result = external_feed.sync_one(feed_key)
    assert result["fetched"] == 3
    assert any("/api/feed/delta" in c for c in calls)
    assert any(c.startswith("/api/feed?") for c in calls)
    assert [b["time"] for b in store.calls[0]["bars"]] == [1000, 1060, 1120]


# ── background thread ────────────────────────────────────────────────────────


def test_start_external_feed_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PYNE_FEED_SOURCE", raising=False)
    assert external_feed.start_external_feed() is False
    assert external_feed._thread is None


def test_start_external_feed_is_idempotent(monkeypatch):
    monkeypatch.setenv("PYNE_FEED_SOURCE", "external")
    monkeypatch.setenv("PYNE_FEED_URL", "https://feed.example")
    import threading

    blocker = threading.Event()
    monkeypatch.setattr(external_feed, "_feed_loop", blocker.wait)
    assert external_feed.start_external_feed() is True
    thread = external_feed._thread
    assert thread is not None
    assert external_feed.start_external_feed() is True
    assert external_feed._thread is thread
