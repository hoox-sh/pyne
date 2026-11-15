# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for autonomous history ensure + resume (F-13). Store is isolated per
test via ``PYNE_DATA_DIR``; bars are provided locally so no network is used.
"""

from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from backend.api.live_ensure import ensure_live_session
from backend.api.live_ensure import resume_live_session


KEY = "binance|spot|BTC/USDT|1m"


def _bars10():
    return [
        {"time": 1_700_000_000 + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in range(10)
    ]


@pytest.fixture()
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PYNE_DATA_DIR", str(tmp_path / "data"))


def _provide(bars):
    from backend.datastore import series as series_store

    key = series_store.make_key("binance", "BTC/USDT", "1m", "spot")
    series_store.get_store().provide(key, bars, source="test")
    return key


def test_bad_key_rejected(_isolated):
    out = ensure_live_session("series", "junk", 50)
    assert out["outcome"] == "error"
    assert out["code"] == "BAD_KEY"


def test_script_without_script_rejected(_isolated):
    out = ensure_live_session("script", KEY, 50)
    assert out["outcome"] == "error"
    assert out["code"] == "NO_SCRIPT"


def test_series_kind_ready_without_session(_isolated):
    _provide(_bars10())
    out = ensure_live_session("series", KEY, 10)
    assert out["outcome"] == "ready"
    assert out["session_id"] is None
    assert out["count"] == 10


def test_script_kind_creates_bound_session(_isolated):
    _provide(_bars10())
    out = ensure_live_session("script", KEY, 10, script="indicator()", symbol="BTCUSDT")
    assert out["outcome"] == "ready"
    assert out["session_id"]
    resumed = resume_live_session(out["session_id"])
    assert resumed["outcome"] == "ready"
    assert resumed["count"] == 10


def test_identical_script_subs_share_one_session(_isolated):
    _provide(_bars10())
    a = ensure_live_session("script", KEY, 10, script="indicator()", symbol="BTCUSDT")
    b = ensure_live_session("script", KEY, 10, script="indicator()", symbol="BTCUSDT")
    assert a["outcome"] == b["outcome"] == "ready"
    assert a["session_id"] == b["session_id"]
    other = ensure_live_session("script", KEY, 10, script='indicator("x")', symbol="BTCUSDT")
    assert other["session_id"] != a["session_id"]


def test_resume_unknown_is_gone(_isolated):
    assert resume_live_session("nope") == {"outcome": "gone"}


def test_stale_pooled_session_recreates_over_current_store(_isolated):
    """A pool hit whose window the store moved past recreates (no zombie).

    Regression: after a repair / purge + refetch, resubscribing resumed the
    pre-repair pooled session by fingerprint, evaluating bars that no longer
    overlap the chart (stale overlays surviving reloads). A lag beyond the
    requested window must drop the entry and create fresh.
    """
    from backend.middleware.sessions import SESSIONS

    def bars10(start):
        return [
            {"time": start + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
            for i in range(10)
        ]

    script = 'indicator("stale-recreate-probe")'
    _provide(bars10(1_700_000_000))
    a = ensure_live_session("script", KEY, 10, script=script, symbol="BTCUSDT")
    assert a["outcome"] == "ready"
    # The store window moves a full day past the pooled anchor.
    _provide(bars10(1_700_000_000 + 86_400))
    b = ensure_live_session("script", KEY, 10, script=script, symbol="BTCUSDT")
    assert b["outcome"] == "ready"
    assert b["session_id"] != a["session_id"]
    assert SESSIONS.get(a["session_id"]) is None
    assert b["newest"] == 1_700_000_000 + 86_400 + 9 * 60


def test_pooled_session_with_covered_hole_recreates(_isolated):
    """A pooled session whose bars skip a window the store later fills is stale."""
    from backend.datastore import series as series_store

    key = series_store.make_key("binance", "BTC/USDT", "1m", "spot")
    holed = [
        {"time": 1_700_000_000 + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in list(range(5)) + list(range(8, 12))
    ]
    series_store.get_store().provide(key, holed, source="test")
    script = 'indicator("hole-recreate-probe")'
    first = ensure_live_session("script", KEY, 9, script=script, symbol="BTCUSDT")
    assert first["outcome"] == "ready"
    # The feed later fills the hole; the pooled session must not be resumed.
    filled = [
        {"time": 1_700_000_000 + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in range(5, 8)
    ]
    series_store.get_store().provide(key, filled, source="test")
    second = ensure_live_session("script", KEY, 9, script=script, symbol="BTCUSDT")
    assert second["outcome"] == "ready"
    assert second["session_id"] != first["session_id"]


def test_healthy_pooled_session_keeps_sharing(_isolated):
    """A pool hit lagging less than the window still shares (no churn)."""
    script = 'indicator("healthy-share-probe")'
    _provide(_bars10())
    a = ensure_live_session("script", KEY, 10, script=script, symbol="BTCUSDT")
    # One new bar lands (a normal tick): the anchor trails by a single bar.
    _provide(
        [
            {
                "time": 1_700_000_000 + 10 * 60,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
            }
        ]
    )
    b = ensure_live_session("script", KEY, 10, script=script, symbol="BTCUSDT")
    assert b["outcome"] == "ready"
    assert b["session_id"] == a["session_id"]


def test_empty_store_window_is_stale(_isolated):
    """A pooled session over a purged (empty) store must recreate, not share."""
    from types import SimpleNamespace

    from backend.api.live_ensure import _pooled_window_moved_on
    from backend.datastore import live as data_live
    from backend.datastore import series as series_store

    key = series_store.make_key("binance", "BTC/USDT", "1m", "spot")
    bar = {"time": 1_700_000_000, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
    session = SimpleNamespace()
    data_live.bind_session(session, key, bar)
    store = series_store.get_store()
    assert _pooled_window_moved_on(store, key, session, 10) is True
    _provide(_bars10())
    # Current window overlaps the birth anchor — not stale.
    assert _pooled_window_moved_on(store, key, session, 10) is False


def test_purge_drops_journaled_unloaded_session(_isolated, tmp_path, monkeypatch):
    """DELETE-cascade after a restart: journaled id is gone, get does not rebuild."""
    from backend.api.live_ensure import resume_live_session
    from backend.datastore import series as series_store
    from backend.middleware.sessions import SESSIONS

    db = str(tmp_path / "sessions.db")
    monkeypatch.setattr(SESSIONS, "_db_path", db)
    key = series_store.make_key("binance", "PURGE/USDT", "1m", "spot")
    series_store.get_store().provide(key, _bars10(), source="test")
    script = 'indicator("purge-journal-probe")'
    created = ensure_live_session("script", key.text, 10, script=script, symbol="PURGEUSDT")
    assert created["outcome"] == "ready"
    sid = created["session_id"]
    SESSIONS._sessions.pop(sid, None)
    SESSIONS._last_seen.pop(sid, None)
    for fp, pooled in list(SESSIONS._shared.items()):
        if pooled == sid:
            del SESSIONS._shared[fp]
    SESSIONS._shared_refs.pop(sid, None)
    series_store.get_store().purge(key)
    assert SESSIONS.drop_by_key(key.text) == 1
    assert resume_live_session(sid) == {"outcome": "gone"}
    assert SESSIONS.get(sid) is None
