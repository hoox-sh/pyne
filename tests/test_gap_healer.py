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

"""Hole detection + the background gap healer.

A stored series that loses minutes in the middle poisons every script run over
that window (Pine `na` for the missing bars). These tests pin the detection
(:meth:`SeriesStore.holes`), the give-up cooldown that used to strand a hole
forever, and the sweep that fills it without a client session.
"""

from __future__ import annotations

import pytest

from backend.api import data_series as data_api
from backend.api import gap_healer
from backend.datastore import series as series_store
from backend.datastore.series import SeriesStore
from backend.datastore.series import make_key


NOW = 1_700_000_040
MIN = 60
KEY = make_key("binance", "BTC/USDT", "1m")
KEY_TEXT = "binance|spot|BTC/USDT|1m"


def bar(t_s: int, px: float = 100.0) -> dict:
    return {"time": t_s, "open": px, "high": px + 1.0, "low": px - 1.0, "close": px + 0.5, "volume": 10.0}


def candle(t_s: int, px: float = 100.0) -> list[float]:
    return [t_s * 1000, px, px + 1.0, px - 1.0, px + 0.5, 10.0]


class FakeExchange:
    """Serves ``fetch_ohlcv`` from memory (no network)."""

    def __init__(self) -> None:
        self.candles: list[list[float]] = []
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def fetch_ohlcv(self, symbol, timeframe="1m", since=None, limit=None):
        self.calls.append({"symbol": symbol, "timeframe": timeframe, "since": since, "limit": limit})
        if self.error is not None:
            raise self.error
        rows = [c for c in self.candles if since is None or c[0] >= since]
        return rows[:limit] if limit else rows


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PYNE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("PYNE_GAP_HEAL", raising=False)
    monkeypatch.setattr(series_store, "now_seconds", lambda: NOW)
    data_api._reset_walk_cache_for_tests()
    gap_healer._reset_gap_healer_for_tests()
    yield
    data_api._reset_walk_cache_for_tests()
    gap_healer._reset_gap_healer_for_tests()


@pytest.fixture
def store() -> SeriesStore:
    # The process-wide store the API modules read (``PYNE_DATA_DIR`` is
    # per-test, so ``get_store`` reopens on the first call of each test).
    return series_store.get_store()


@pytest.fixture
def exchange() -> FakeExchange:
    return FakeExchange()


class TestHoles:
    def test_finds_internal_holes_oldest_first(self, store):
        # 0..3 then a 5-bar hole, then 9..10.
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(4)])
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(9, 11)])
        assert store.holes(KEY, MIN) == [(NOW + 3 * MIN, NOW + 9 * MIN)]
        assert store.widest_gap(KEY, MIN) == (NOW + 3 * MIN, NOW + 9 * MIN)

    def test_edges_are_not_holes(self, store):
        # A shorter history (leading) and a forming tip (trailing) are normal.
        store.provide(KEY, [bar(NOW + i * MIN) for i in (5, 6, 7)])
        assert store.holes(KEY, MIN) == []
        assert store.widest_gap(KEY, MIN) is None

    def test_continuous_series_has_no_holes(self, store):
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(20)])
        assert store.holes(KEY, MIN) == []

    def test_limit_bounds_the_scan(self, store):
        store.provide(KEY, [bar(NOW + i * MIN) for i in (0, 5, 10, 15)])
        assert len(store.holes(KEY, MIN, limit=1)) == 1
        assert store.holes(KEY, MIN, limit=0) == []


class TestActiveKeys:
    def test_only_recently_written_series(self, store, monkeypatch):
        store.provide(KEY, [bar(NOW), bar(NOW + MIN)], source="ccxt-tick")
        other = make_key("binance", "ETH/USDT", "1m")
        monkeypatch.setattr(series_store, "now_seconds", lambda: NOW + 10_000)
        store.provide(other, [bar(NOW), bar(NOW + MIN)], source="ccxt-tick")
        # A window that starts after the BTC write keeps only the fresher ETH.
        keys = store.active_keys(updated_since=NOW + 9_000)
        assert [k.text for k in keys] == ["binance|spot|ETH/USDT|1m"]
        # A window covering both returns newest first.
        assert [k.text for k in store.active_keys(updated_since=NOW - 900)] == [
            "binance|spot|ETH/USDT|1m",
            KEY_TEXT,
        ]

    def test_single_bar_series_is_skipped(self, store):
        store.provide(KEY, [bar(NOW)])
        assert store.active_keys(updated_since=NOW - 900) == []


class TestGiveUpCooldown:
    def test_blocked_then_retried_after_the_cooldown(self, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(data_api.time, "monotonic", lambda: clock["t"])
        for _ in range(data_api._GAP_GIVE_UP):
            data_api._gap_failed(KEY_TEXT, NOW)
        assert data_api._gap_blocked(KEY_TEXT, NOW) is True
        clock["t"] += data_api._GAP_RETRY_S + 1
        assert data_api._gap_blocked(KEY_TEXT, NOW) is False

    def test_a_different_hole_start_is_not_blocked(self, monkeypatch):
        monkeypatch.setattr(data_api.time, "monotonic", lambda: 1000.0)
        for _ in range(data_api._GAP_GIVE_UP):
            data_api._gap_failed(KEY_TEXT, NOW)
        assert data_api._gap_blocked(KEY_TEXT, NOW + MIN) is False


class TestHealSeriesGaps:
    def test_fills_a_hole_without_a_session(self, store, exchange):
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(4)])
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(9, 11)])
        exchange.candles = [candle(NOW + i * MIN) for i in range(11)]
        filled = data_api.heal_series_gaps(KEY, provider=exchange, now_s=NOW + 20 * MIN)
        assert filled == 1
        assert store.holes(KEY, MIN) == []
        assert store.status(KEY)["count"] == 11

    def test_no_hole_means_no_upstream_walk(self, store, exchange):
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(5)])
        assert data_api.heal_series_gaps(KEY, provider=exchange, now_s=NOW + MIN) == 0
        assert exchange.calls == []

    def test_upstream_failure_counts_and_blocks(self, store, exchange):
        store.provide(KEY, [bar(NOW + i * MIN) for i in (0, 5)])
        exchange.error = RuntimeError("venue down")
        for _ in range(data_api._GAP_GIVE_UP):
            assert data_api.heal_series_gaps(KEY, provider=exchange, now_s=NOW + 10 * MIN) == 0
        assert data_api._gap_blocked(KEY_TEXT, NOW) is True


class TestSweep:
    def test_sweep_heals_an_active_holed_series(self, store, exchange, monkeypatch):
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(4)])
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(9, 11)])
        exchange.candles = [candle(NOW + i * MIN) for i in range(11)]
        monkeypatch.setattr(data_api, "provider_for", lambda *a, **k: exchange)
        report = gap_healer.sweep_once(now_s=NOW)
        assert report == {"series": 1, "holes": 1, "filled": 1}
        assert store.holes(KEY, MIN) == []

    def test_sweep_is_a_no_op_without_holes(self, store, exchange, monkeypatch):
        store.provide(KEY, [bar(NOW + i * MIN) for i in range(5)])
        monkeypatch.setattr(data_api, "provider_for", lambda *a, **k: exchange)
        assert gap_healer.sweep_once(now_s=NOW) == {"series": 0, "holes": 0, "filled": 0}
        assert exchange.calls == []

    def test_sweep_skips_a_stale_series(self, store, exchange, monkeypatch):
        store.provide(KEY, [bar(NOW + i * MIN) for i in (0, 5)])
        monkeypatch.setattr(series_store, "now_seconds", lambda: NOW + 10_000)
        monkeypatch.setattr(data_api, "provider_for", lambda *a, **k: exchange)
        assert gap_healer.sweep_once() == {"series": 0, "holes": 0, "filled": 0}

    def test_healer_is_off_when_disabled(self, monkeypatch):
        monkeypatch.setenv("PYNE_GAP_HEAL", "0")
        assert gap_healer.enabled() is False
        assert gap_healer.start_gap_healer() is False

    def test_healer_never_starts_under_pytest(self, monkeypatch):
        # The suite creates holes on purpose; a sweep must not fill them.
        monkeypatch.delenv("PYNE_GAP_HEAL", raising=False)
        assert gap_healer.start_gap_healer() is False


class TestStats:
    def test_stats_reports_disarmed_and_sweep_counters(self, store, exchange, monkeypatch):
        before = gap_healer.stats()
        assert before["armed"] is False  # pytest never arms the thread
        store.provide(KEY, [bar(NOW + i * MIN) for i in (0, 5)])
        exchange.candles = [candle(NOW + i * MIN) for i in range(6)]
        monkeypatch.setattr(data_api, "provider_for", lambda *a, **k: exchange)
        gap_healer.sweep_once(now_s=NOW)
        after = gap_healer.stats()
        assert after["sweeps"] == before["sweeps"] + 1
        assert after["filled"] == before["filled"] + 1
        assert after["last_sweep_at"] == NOW
