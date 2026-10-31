# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import asyncio

from types import SimpleNamespace
from typing import Any

import pytest

from pynescript.util.data import AlphaVantageProvider
from pynescript.util.data import ChartOHLCVProvider
from pynescript.util.data import DataProviderError
from pynescript.util.data import MockDataProvider
from pynescript.util.data import YahooFinanceProvider
from pynescript.util.data import geo_block_message
from pynescript.util.data import get_provider
from pynescript.util.data import normalize_ccxt_symbol
from pynescript.util.data import resolve_request_sources
from pynescript.util.data import tune_ccxt_public_urls
from pynescript.util.datafeed import CompositeDataFeed
from pynescript.util.datafeed import DataFeed
from pynescript.util.datafeed import MockDataFeed
from pynescript.util.datafeed import get_datafeed
from pynescript.util.datafeed import poll_forming_ohlcv


class _NoPoll:
    pass


class _RaisingPoll:
    def poll_ohlcv(self, symbol: str, timeframe: str = "1m") -> list[Any] | None:
        raise RuntimeError("boom")


class _BadCandleFeed:
    def __init__(self, candle: Any) -> None:
        self._candle = candle

    def poll_ohlcv(self, symbol: str, timeframe: str = "1m") -> Any:
        return self._candle


def test_poll_forming_ohlcv_none_and_missing() -> None:
    assert poll_forming_ohlcv(None, "BTC/USDT") is None
    assert poll_forming_ohlcv(_NoPoll(), "BTC/USDT") is None
    assert poll_forming_ohlcv(_RaisingPoll(), "X") is None
    assert poll_forming_ohlcv(_BadCandleFeed(None), "X") is None
    assert poll_forming_ohlcv(_BadCandleFeed([]), "X") is None


def test_poll_forming_ohlcv_malformed() -> None:
    assert poll_forming_ohlcv(_BadCandleFeed(["not-a-ts", 1, 2, 3, 4, 5]), "X") is None
    assert poll_forming_ohlcv(_BadCandleFeed([1_700_000_000_000, 1]), "X") is None
    assert poll_forming_ohlcv(_BadCandleFeed(object()), "X") is None


def test_poll_forming_ohlcv_flat_and_nested() -> None:
    flat = [1_700_000_000_000, 10.0, 12.0, 9.0, 11.0, 100.0]
    got = poll_forming_ohlcv(_BadCandleFeed(flat), "BTC/USDT", "5m")
    assert got == (1_700_000_000_000.0, 10.0, 12.0, 9.0, 11.0, 100.0)

    nested = [
        [1_700_000_000_000, 1.0, 2.0, 0.5, 1.5, 10.0],
        [1_700_000_060_000, 2.0, 3.0, 1.5, 2.5, 20.0],
    ]
    got2 = poll_forming_ohlcv(_BadCandleFeed(nested), "ETH/USDT")
    assert got2 == (1_700_000_060_000.0, 2.0, 3.0, 1.5, 2.5, 20.0)

    no_vol = [1_700_000_000_000, 1.0, 2.0, 0.5, 1.5]
    got3 = poll_forming_ohlcv(_BadCandleFeed(no_vol), "X")
    assert got3 is not None
    assert got3[5] == 0.0


def test_poll_forming_ohlcv_mock_scripted_and_synthetic() -> None:
    scripted = [
        [1_700_000_000_000, 100.0, 101.0, 99.0, 100.5, 50.0],
        [1_700_000_060_000, 100.5, 102.0, 100.0, 101.0, 60.0],
    ]
    feed = MockDataFeed(scripted=scripted, start_price=100.0)
    first = poll_forming_ohlcv(feed, "BTC/USDT")
    assert first == (1_700_000_000_000.0, 100.0, 101.0, 99.0, 100.5, 50.0)
    second = poll_forming_ohlcv(feed, "BTC/USDT")
    assert second is not None and second[4] == 101.0
    assert poll_forming_ohlcv(feed, "BTC/USDT") is None

    synth = MockDataFeed(start_price=42.0)
    candle = poll_forming_ohlcv(synth, "X")
    assert candle is not None
    assert candle[1] == 42.0
    assert candle[4] == 42.5


def test_mock_datafeed_sync_helpers() -> None:
    feed = MockDataFeed(symbol="ETH/USDT", start_price=2000.0)
    ticker = feed.fetch_latest_ticker()
    assert ticker["symbol"] == "ETH/USDT"
    assert ticker["last"] == 2000.0
    rows = feed.fetch_latest_ohlcv(limit=3)
    assert len(rows) == 3
    assert rows[0][1] == pytest.approx(2000.0)

    scripted = MockDataFeed(scripted=[[1, 1, 1, 1, "bad", 1]])
    assert scripted.poll_ohlcv("X") == [1, 1, 1, 1, "bad", 1]


def test_composite_poll_prefers_primary_then_fallback() -> None:
    primary = MockDataFeed(scripted=[[10, 1.0, 2.0, 0.5, 1.5, 9.0]])
    fallback = MockDataFeed(scripted=[[20, 2.0, 3.0, 1.0, 2.5, 8.0]])
    comp = CompositeDataFeed(primary, fallback)
    assert poll_forming_ohlcv(comp, "X") == (10.0, 1.0, 2.0, 0.5, 1.5, 9.0)
    # primary exhausted → fallback
    assert poll_forming_ohlcv(comp, "X") == (20.0, 2.0, 3.0, 1.0, 2.5, 8.0)
    assert poll_forming_ohlcv(comp, "X") is None

    class _Boom(DataFeed):
        async def watch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int | None = None):
            if False:
                yield []

        async def watch_trades(self, symbol: str, limit: int | None = None):
            if False:
                yield {}

        async def watch_ticker(self, symbol: str):
            if False:
                yield {}

        async def watch_order_book(self, symbol: str, limit: int = 20):
            if False:
                yield {}

        def poll_ohlcv(self, symbol: str, timeframe: str = "1m") -> list[Any] | None:
            raise RuntimeError("primary fail")

    boom = CompositeDataFeed(_Boom(), MockDataFeed(scripted=[[30, 3, 4, 2, 3.5, 1]]))
    assert poll_forming_ohlcv(boom, "X")[0] == 30.0  # type: ignore[index]


def test_get_datafeed_mock_kwargs() -> None:
    feed = get_datafeed("mock", start_price=11.0, symbol="AAA/BBB")
    assert isinstance(feed, MockDataFeed)
    assert feed.symbol == "AAA/BBB"
    assert feed.price == 11.0


def test_mock_async_streams_close() -> None:
    async def _run() -> None:
        feed = MockDataFeed(start_price=100.0)
        async with feed:
            ohlcv = await anext(feed.watch_ohlcv("BTC/USDT"))
            trade = await anext(feed.watch_trades())
            ticker = await anext(feed.watch_ticker())
            book = await anext(feed.watch_order_book(limit=3))
        assert len(ohlcv) == 6
        assert "price" in trade
        assert ticker["last"]
        assert len(book["bids"]) == 3
        assert feed._closed is True

    asyncio.run(_run())


def test_chart_ohlcv_provider_symbol_matching() -> None:
    bars = [
        {"time": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0},
        {"time": 2, "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 12.0},
    ]
    prov = ChartOHLCVProvider(bars, symbol="AAPL")
    hit = prov.fetch("AAPL")
    assert hit["close"] == [1.5, 2.0]
    assert hit["symbol"] == "AAPL"
    assert prov.fetch("NASDAQ:AAPL")["close"] == [1.5, 2.0]
    assert prov.fetch("CHART")["close"] == [1.5, 2.0]
    assert prov.fetch("MSFT")["close"] == []
    quote = prov.fetch_quote("AAPL")
    assert quote["last"] == 2.0
    assert quote["volume"] == 12.0
    empty_q = ChartOHLCVProvider([], symbol="X").fetch_quote("X")
    assert empty_q["last"] == 0.0
    foreign_q = prov.fetch_quote("MSFT")
    assert foreign_q["last"] == 0.0


def test_mock_data_provider_periods_and_quotes() -> None:
    prov = MockDataProvider(seed=7)
    data = prov.fetch("AAPL", period="1mo", interval="1d")
    assert data["symbol"] == "AAPL"
    assert len(data["close"]) == 30
    assert all(c > 0 for c in data["close"])
    btc = prov.fetch("BTC", period="1d")
    assert len(btc["close"]) == 1
    quote = prov.fetch_quote("ETH")
    assert quote["symbol"] == "ETH"
    assert quote["last"] == 3000
    assert quote["bid"] < quote["ask"]
    unknown = MockDataProvider(seed=1).fetch_quote("ZZZ")
    assert unknown["last"] == 100.0


def test_yahoo_and_alphavantage_stubs_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    yf = YahooFinanceProvider()
    real_import = __import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "yfinance":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    with pytest.raises(DataProviderError, match="yfinance"):
        yf._get_yf()

    av = AlphaVantageProvider(api_key="demo")
    assert av._api_key == "demo"
    with pytest.raises(DataProviderError, match="alpha-vantage"):

        def fake_av_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name.startswith("alpha_vantage"):
                raise ImportError("missing")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_av_import)
        av._get_client()

    got = get_provider("alphavantage", api_key="k")
    assert isinstance(got, AlphaVantageProvider)


def test_normalize_ccxt_and_geo_and_tune() -> None:
    assert normalize_ccxt_symbol("coinbaseexchange", "ETHUSDT") == "ETH/USD"
    assert normalize_ccxt_symbol("coinbase", "SOL/USDT") == "SOL/USD"
    assert normalize_ccxt_symbol("", "BTC/USDT") == "BTC/USDT"
    assert geo_block_message("okx", RuntimeError("restricted location")) is not None
    assert geo_block_message("okx", RuntimeError("Eligibility denied")) is not None
    assert geo_block_message("okx", RuntimeError("ok")) is None

    ex = SimpleNamespace(
        options={"defaultType": "spot"},
        urls={"api": {"public": "https://api.binance.com/api", "fapi": "https://fapi.binance.com"}},
    )
    tune_ccxt_public_urls(ex, "binance")
    assert "data-api.binance.vision" in ex.urls["api"]["public"]
    assert ex.urls["api"]["fapi"] == "https://fapi.binance.com"

    futures = SimpleNamespace(options={"defaultType": "future"}, urls={"api": {}})
    tune_ccxt_public_urls(futures, "binance")  # no-op for non-spot
    tune_ccxt_public_urls(ex, "kraken")  # no-op other venue


def test_resolve_request_sources_alphavantage_and_explicit() -> None:
    feed, provider = resolve_request_sources(data_source="alphavantage", source_options={"api_key": "demo"})
    assert feed is None
    assert isinstance(provider, AlphaVantageProvider)

    sentinel_feed = object()
    sentinel_prov = object()
    assert resolve_request_sources(data_feed=sentinel_feed, data_provider=sentinel_prov) == (
        sentinel_feed,
        sentinel_prov,
    )

    bars = [{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    _, chart = resolve_request_sources(chart_bars=bars, symbol="XYZ")
    assert isinstance(chart, ChartOHLCVProvider)
    assert chart.fetch("XYZ")["close"] == [1.0]
