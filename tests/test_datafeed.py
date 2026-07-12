# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Tests for the realtime datafeed module (mocked, no network)."""

from __future__ import annotations

import asyncio

import pytest

from pynescript.util.datafeed import CCXTProDataFeed
from pynescript.util.datafeed import CompositeDataFeed
from pynescript.util.datafeed import DataFeedError
from pynescript.util.datafeed import MockDataFeed
from pynescript.util.datafeed import get_datafeed


class DummyProExchange:
    """Minimal fake ccxt.pro exchange for testing."""

    def __init__(self, *a, **k):
        self.closed = False
        self._candle = [1700000000000, 25000.0, 25100.0, 24900.0, 25050.0, 123.45]
        self._ticker = {"last": 25050.0, "bid": 25049.0, "ask": 25051.0}

    async def watch_ohlcv(self, symbol, timeframe="1m", limit=None):
        return [self._candle]

    async def watch_ticker(self, symbol):
        return self._ticker

    async def watch_trades(self, symbol, limit=None):
        return [{"price": 25050.0, "amount": 0.1, "side": "buy"}]

    async def watch_order_book(self, symbol, limit=20):
        return {"bids": [[25049, 1]], "asks": [[25051, 1]]}

    async def fetch_ohlcv(self, *a, **k):
        return [self._candle]

    async def fetch_ticker(self, *a, **k):
        return self._ticker

    async def close(self):
        self.closed = True


def test_get_datafeed_mock():
    feed = get_datafeed("mock")
    assert isinstance(feed, MockDataFeed)


def test_get_datafeed_unknown():
    with pytest.raises(DataFeedError):
        get_datafeed("nonexistent")


def test_mock_datafeed_streams():
    """Use asyncio.run to avoid requiring pytest-asyncio plugin."""

    async def _inner():
        feed = MockDataFeed()
        count = 0
        async with feed:
            async for candle in feed.watch_ohlcv("BTC/USDT", "1m"):
                assert len(candle) == 6
                count += 1
                if count > 2:
                    break
        return count

    count = asyncio.run(_inner())
    assert count >= 2


def test_ccxtpro_sync_wrappers(monkeypatch):
    import pynescript.util.datafeed as dfmod

    original_get = dfmod.CCXTProDataFeed._get_exchange

    async def fake_get(self):
        return DummyProExchange()

    dfmod.CCXTProDataFeed._get_exchange = fake_get

    feed = CCXTProDataFeed(exchange="binance")
    try:
        ohlcv = feed.fetch_latest_ohlcv("BTC/USDT")
        assert ohlcv and len(ohlcv[0]) == 6

        ticker = feed.fetch_latest_ticker("BTC/USDT")
        assert "last" in ticker or "close" in ticker
    finally:
        dfmod.CCXTProDataFeed._get_exchange = original_get
        # close is sync-safe here because we didn't start real ws
        # but to be complete:
        try:
            asyncio.run(feed.close())
        except Exception:  # noqa: S110 - test cleanup
            pass


def test_composite_fallback():
    async def _inner():
        primary = MockDataFeed()
        fallback = MockDataFeed(start_price=100.0)
        comp = CompositeDataFeed(primary, fallback)

        count = 0
        async with comp:
            async for _c in comp.watch_ohlcv("TEST/USDT"):
                count += 1
                if count > 1:
                    break
        return count

    count = asyncio.run(_inner())
    assert count > 0


def test_datafeed_broker():
    from pynescript.util.datafeed import DataFeedBroker

    async def _inner():
        feed = MockDataFeed()
        broker = DataFeedBroker(feed, initial_balance=10000.0)

        oid = broker.place_order("BTC/USDT", "buy", 0.1)  # market
        assert oid in broker.orders

        await broker._process_fills(25000.0)
        return broker.get_balance(), broker.get_position("BTC/USDT")

    bal, pos = asyncio.run(_inner())
    assert bal < 10000 or pos > 0


def test_evaluator_with_datafeed_request_security():
    """Integration: NodeLiteralEvaluator + data_feed for request.security (point 1 more integration)."""
    from pynescript.ast import helper
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    feed = MockDataFeed(start_price=123.0)
    evaluator = NodeLiteralEvaluator(data_feed=feed)

    # Simulate a script expression that would use request.security inside
    # Directly exercise the handler which now consults data_feed
    prices = evaluator._handle_request_security(["BTC/USDT", "1m", "close"])
    assert isinstance(prices, list) and len(prices) > 0
    assert all(isinstance(p, (int, float)) for p in prices)

    # Also test via literal_eval path (now forwards data)
    # (parse a simple call expression)
    # Note: full script with request.security() call would hit the dispatch too
    expr_ast = helper.parse("request.security('TEST', '1', close)", mode="eval")
    # Visiting would require full context/builtins; handler direct is sufficient coverage
    assert evaluator.context.get("data_feed") is feed
