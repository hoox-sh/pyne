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

"""Realtime data feeds using CCXT Pro (WebSocket streaming).

This module provides async data feeds for live market data from 100+ crypto
exchanges via CCXT Pro:

- OHLCV candles (real-time)
- Trades
- Ticker
- Order book

CCXT Pro is the WebSocket/realtime counterpart to the historical CCXTProvider
in data.py.

Requires:
    pip install ccxt

Usage:
    from pynescript.util.datafeed import get_datafeed

    async def main():
        feed = get_datafeed("ccxtpro", exchange="binance")
        async with feed:
            async for candle in feed.watch_ohlcv("BTC/USDT", "1m"):
                print(candle)
                break  # process one update

    import asyncio
    asyncio.run(main())

Notes:
- All methods are async generators or coroutines.
- The underlying CCXT Pro exchange handles reconnection and backoff.
- Use one CCXTProDataFeed per exchange (it can watch multiple symbols).
- Not all exchanges support all watch_* methods. See https://docs.ccxt.com/

This complements the historical DataProvider in data.py and can be used to
power live evaluation, request.security simulation, or custom strategies.
"""

from __future__ import annotations

import asyncio
import random

from abc import ABC
from abc import abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


class DataFeedError(Exception):
    """Error raised by realtime data feeds."""


class DataFeed(ABC):
    """Abstract base class for realtime data feeds."""

    @abstractmethod
    async def watch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int | None = None,
    ) -> AsyncIterator[list[Any]]:
        """Stream real-time OHLCV candles.

        Args:
            symbol: Trading pair (e.g. "BTC/USDT")
            timeframe: Candle interval (e.g. "1m", "5m", "1h", "1d")
            limit: Optional number of candles per update

        Yields:
            List of [timestamp, open, high, low, close, volume] (or list of them)
        """
        ...

    @abstractmethod
    async def watch_trades(
        self,
        symbol: str,
        limit: int | None = None,
    ) -> AsyncIterator[dict[str, Any] | list[dict[str, Any]]]:
        """Stream real-time trades.

        Yields:
            Trade dict(s) with keys like 'id', 'timestamp', 'price', 'amount', 'side', etc.
        """
        ...

    @abstractmethod
    async def watch_ticker(self, symbol: str) -> AsyncIterator[dict[str, Any]]:
        """Stream real-time ticker updates.

        Yields:
            Ticker dict with bid, ask, last, high, low, volume, etc.
        """
        ...

    @abstractmethod
    async def watch_order_book(self, symbol: str, limit: int = 20) -> AsyncIterator[dict[str, Any]]:
        """Stream real-time order book snapshots.

        Yields:
            Order book with 'bids', 'asks', 'timestamp', etc.
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Close the underlying connection(s)."""
        pass  # default no-op for subclasses that do not need explicit close

    async def __aenter__(self) -> DataFeed:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


class CCXTProDataFeed(DataFeed):
    """Real-time data feed powered by CCXT Pro WebSockets.

    Supports the same exchanges as the historical CCXTProvider plus realtime
    capabilities on supported venues (Binance, Bybit, OKX, Coinbase, Kraken, etc.).

    Example:
        feed = CCXTProDataFeed(exchange="binance")
        async with feed:
            async for candle in feed.watch_ohlcv("BTC/USDT", "1m"):
                ...
    """

    def __init__(
        self,
        exchange: str = "binance",
        api_key: str = "",
        secret: str = "",
        password: str = "",
        sandbox: bool = False,  # noqa: FBT001,FBT002 - CLI/ factory friendly
        **options: Any,
    ) -> None:
        """Initialize the CCXT Pro feed.

        Args:
            exchange: Exchange id (binance, bybit, okx, coinbase, kraken, ...)
            api_key: Optional API key for private streams
            secret: Optional API secret
            password: Optional passphrase (required by some exchanges)
            sandbox: Use testnet/sandbox if supported
            **options: Extra options passed to the CCXT Pro exchange constructor
        """
        self._exchange_name = exchange.lower()
        self._api_key = api_key
        self._secret = secret
        self._password = password
        self._sandbox = sandbox
        self._options = options
        self._exchange: Any | None = None

    async def _get_exchange(self) -> Any:
        """Lazily create the CCXT Pro exchange instance."""
        if self._exchange is None:
            try:
                import ccxt.pro as ccxtpro  # type: ignore[import-not-found]  # noqa: PLC0415 - lazy to avoid hard dep
            except ImportError as e:
                msg = "ccxt is required for CCXTProDataFeed. Install with: pip install ccxt"
                raise DataFeedError(msg) from e

            exchange_class = getattr(ccxtpro, self._exchange_name, None)
            if exchange_class is None:
                msg = (
                    f"Exchange '{self._exchange_name}' not found in ccxt.pro. "
                    "Check available exchanges with ccxt.pro.exchanges"
                )
                raise DataFeedError(msg)

            params: dict[str, Any] = dict(self._options)
            if self._api_key:
                params["apiKey"] = self._api_key
            if self._secret:
                params["secret"] = self._secret
            if self._password:
                params["password"] = self._password
            if self._sandbox:
                params["sandbox"] = True

            self._exchange = exchange_class(params)

        return self._exchange

    async def watch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int | None = None,
    ) -> AsyncIterator[list[Any]]:
        """Stream OHLCV updates using watch_ohlcv."""
        exchange = await self._get_exchange()
        while True:
            try:
                ohlcv = await exchange.watch_ohlcv(symbol, timeframe, limit=limit)
                if ohlcv:
                    yield ohlcv
            except Exception as e:  # broad to let ccxt handle reconnect logic
                # Most pro implementations recover internally on next call
                # Yielding error info is optional; here we just continue
                if "closed" in str(e).lower() or "connection" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                msg = f"watch_ohlcv error: {e}"
                raise DataFeedError(msg) from e

    async def watch_trades(
        self,
        symbol: str,
        limit: int | None = None,
    ) -> AsyncIterator[dict[str, Any] | list[dict[str, Any]]]:
        """Stream trades using watch_trades."""
        exchange = await self._get_exchange()
        while True:
            try:
                trades = await exchange.watch_trades(symbol, limit=limit)
                if trades:
                    yield trades
            except Exception as e:
                if "closed" in str(e).lower() or "connection" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                msg = f"watch_trades error: {e}"
                raise DataFeedError(msg) from e

    async def watch_ticker(self, symbol: str) -> AsyncIterator[dict[str, Any]]:
        """Stream ticker updates using watch_ticker."""
        exchange = await self._get_exchange()
        while True:
            try:
                ticker = await exchange.watch_ticker(symbol)
                yield ticker
            except Exception as e:
                if "closed" in str(e).lower() or "connection" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                msg = f"watch_ticker error: {e}"
                raise DataFeedError(msg) from e

    async def watch_order_book(self, symbol: str, limit: int = 20) -> AsyncIterator[dict[str, Any]]:
        """Stream order book using watch_order_book."""
        exchange = await self._get_exchange()
        while True:
            try:
                ob = await exchange.watch_order_book(symbol, limit)
                yield ob
            except Exception as e:
                if "closed" in str(e).lower() or "connection" in str(e).lower():
                    await asyncio.sleep(1)
                    continue
                msg = f"watch_order_book error: {e}"
                raise DataFeedError(msg) from e

    async def close(self) -> None:
        """Close the exchange WebSocket connection."""
        if self._exchange is not None:
            try:
                await self._exchange.close()
            except Exception:  # noqa: S110 - best effort shutdown
                pass
            self._exchange = None

    async def __aenter__(self) -> CCXTProDataFeed:
        await self._get_exchange()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    # --- Sync convenience methods for compatibility with sync evaluator / request.* ---
    def fetch_latest_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 1) -> list[Any]:
        """Synchronous one-shot fetch of latest OHLCV (uses asyncio.run internally).

        Useful for request.security in a mostly-sync context.
        """
        return asyncio.run(self._fetch_latest_ohlcv_async(symbol, timeframe, limit))

    async def _fetch_latest_ohlcv_async(self, symbol: str, timeframe: str = "1m", limit: int = 1) -> list[Any]:
        exchange = await self._get_exchange()
        # Use watch once to get fresh data, fallback to fetch if needed
        try:
            ohlcv = await exchange.watch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv[-limit:] if ohlcv else []
        except Exception:
            # Fallback to REST fetch_ohlcv for latest
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv or []

    def fetch_latest_ticker(self, symbol: str) -> dict[str, Any]:
        """Synchronous fetch of latest ticker."""
        return asyncio.run(self._fetch_latest_ticker_async(symbol))

    async def _fetch_latest_ticker_async(self, symbol: str) -> dict[str, Any]:
        exchange = await self._get_exchange()
        try:
            return await exchange.watch_ticker(symbol)
        except Exception:
            return await exchange.fetch_ticker(symbol) or {}


def get_datafeed(name: str = "ccxtpro", **kwargs: Any) -> DataFeed:
    """Factory for realtime data feeds.

    Args:
        name: "ccxtpro" | "mock"
        **kwargs: Passed to the feed constructor

    Returns:
        A DataFeed instance.
    """
    if name in ("ccxtpro", "ccxt", "pro"):
        return CCXTProDataFeed(
            exchange=kwargs.get("exchange", "binance"),
            api_key=kwargs.get("api_key", ""),
            secret=kwargs.get("secret", ""),
            password=kwargs.get("password", ""),
            sandbox=kwargs.get("sandbox", False),
            **{k: v for k, v in kwargs.items() if k not in {"exchange", "api_key", "secret", "password", "sandbox"}},
        )
    if name == "mock":
        return MockDataFeed(**kwargs)

    msg = f"Unknown datafeed: {name}. Supported: 'ccxtpro', 'mock'"
    raise DataFeedError(msg)


class MockDataFeed(DataFeed):
    """Mock realtime data feed for testing (no network required).

    Generates synthetic streaming data.
    """

    def __init__(self, symbol: str = "BTC/USDT", start_price: float = 25000.0):
        self.symbol = symbol
        self.price = start_price
        self._closed = False

    async def watch_ohlcv(
        self, symbol: str | None = None, timeframe: str = "1m", limit: int | None = None
    ) -> AsyncIterator[list[Any]]:
        ts = 1700000000000
        while not self._closed:
            self.price *= 1 + random.uniform(-0.001, 0.001)
            o = self.price
            h = o * (1 + random.uniform(0, 0.002))
            lo = o * (1 - random.uniform(0, 0.002))
            c = o * (1 + random.uniform(-0.001, 0.001))
            v = random.uniform(100, 1000)
            yield [ts, o, h, lo, c, v]
            ts += 60_000
            await asyncio.sleep(0.01)  # fast simulation

    async def watch_trades(
        self, symbol: str | None = None, limit: int | None = None
    ) -> AsyncIterator[dict[str, Any] | list[dict[str, Any]]]:
        sym = symbol or self.symbol
        while not self._closed:
            self.price *= 1 + random.uniform(-0.0005, 0.0005)
            yield {
                "symbol": sym,
                "price": self.price,
                "amount": random.uniform(0.1, 2.0),
                "side": random.choice(["buy", "sell"]),
                "timestamp": 1700000000000,
            }
            await asyncio.sleep(0.01)

    async def watch_ticker(self, symbol: str | None = None) -> AsyncIterator[dict[str, Any]]:
        sym = symbol or self.symbol
        while not self._closed:
            self.price *= 1 + random.uniform(-0.0003, 0.0003)
            yield {
                "symbol": sym,
                "last": self.price,
                "bid": self.price - 1,
                "ask": self.price + 1,
                "high": self.price * 1.01,
                "low": self.price * 0.99,
            }
            await asyncio.sleep(0.01)

    async def watch_order_book(self, symbol: str | None = None, limit: int = 20) -> AsyncIterator[dict[str, Any]]:
        sym = symbol or self.symbol
        while not self._closed:
            yield {
                "symbol": sym,
                "bids": [[self.price - i * 0.5, 1.0] for i in range(limit)],
                "asks": [[self.price + i * 0.5, 1.0] for i in range(limit)],
            }
            await asyncio.sleep(0.01)

    async def close(self) -> None:
        self._closed = True

    async def __aenter__(self) -> MockDataFeed:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


# Composite / unified feed example
class CompositeDataFeed(DataFeed):
    """Unified datafeed that tries realtime first, falls back to other sources.

    Useful for hybrid historical + live usage.
    """

    def __init__(self, primary: DataFeed, fallback: DataFeed | None = None):
        self.primary = primary
        self.fallback = fallback

    async def watch_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int | None = None):
        try:
            async for item in self.primary.watch_ohlcv(symbol, timeframe, limit):
                yield item
        except Exception:
            if self.fallback:
                # Note: fallback may be sync historical; here we just re-raise or yield mock
                async for item in self.fallback.watch_ohlcv(symbol, timeframe, limit):  # type: ignore[attr-defined]
                    yield item
            else:
                raise

    async def watch_trades(self, symbol: str, limit: int | None = None):
        async for item in self.primary.watch_trades(symbol, limit):
            yield item

    async def watch_ticker(self, symbol: str):
        async for item in self.primary.watch_ticker(symbol):
            yield item

    async def watch_order_book(self, symbol: str, limit: int = 20):
        async for item in self.primary.watch_order_book(symbol, limit):
            yield item

    async def close(self):
        await self.primary.close()
        if self.fallback and hasattr(self.fallback, "close"):
            await self.fallback.close()  # type: ignore[attr-defined]


# --- Order execution / position tracking on top of datafeed (point 3) ---


@dataclass
class Order:
    id: str
    symbol: str
    side: str  # "buy" / "sell"
    qty: float
    price: float | None = None  # None = market
    filled: bool = False
    avg_fill_price: float | None = None


class DataFeedBroker:
    """Simple paper-trading broker driven by a realtime DataFeed.

    Tracks positions and simulates fills using streaming prices from the feed.
    Can be used together with the Pine evaluator's strategy events for live simulation.
    """

    def __init__(self, feed: DataFeed, initial_balance: float = 100_000.0):
        self.feed = feed
        self.balance = initial_balance
        self.positions: dict[str, float] = {}  # symbol -> qty (positive long)
        self.orders: dict[str, Order] = {}
        self._order_counter = 0
        self._running = False

    def place_order(self, symbol: str, side: str, qty: float, price: float | None = None) -> str:
        """Place a limit or market order. Returns order id."""
        self._order_counter += 1
        oid = f"ord_{self._order_counter}"
        order = Order(id=oid, symbol=symbol, side=side, qty=qty, price=price)
        self.orders[oid] = order
        return oid

    async def run(self, symbols: list[str] | None = None) -> None:
        """Drive the broker using the datafeed (listens to tickers/trades for fills)."""
        self._running = True
        symbols = symbols or ["BTC/USDT"]
        try:
            async with self.feed:
                # Simple: use ticker stream to simulate price updates and fill orders
                async for ticker in self.feed.watch_ticker(symbols[0]):
                    if not self._running:
                        break
                    price = ticker.get("last") or ticker.get("bid") or ticker.get("ask")
                    if price is None:
                        continue
                    await self._process_fills(price)
        finally:
            self._running = False

    async def _process_fills(self, current_price: float) -> None:
        for _oid, order in list(self.orders.items()):
            if order.filled:
                continue
            fill = False
            if order.price is None:  # market
                fill = True
            elif order.side == "buy" and current_price <= order.price:
                fill = True
            elif order.side == "sell" and current_price >= order.price:
                fill = True

            if fill:
                cost = current_price * order.qty
                if order.side == "buy":
                    if self.balance >= cost:
                        self.balance -= cost
                        self.positions[order.symbol] = self.positions.get(order.symbol, 0) + order.qty
                else:
                    pos = self.positions.get(order.symbol, 0)
                    if pos >= order.qty:
                        self.balance += cost
                        self.positions[order.symbol] = pos - order.qty
                order.filled = True
                order.avg_fill_price = current_price
                # In real integration you would emit StrategyEvent here

    def get_position(self, symbol: str) -> float:
        return self.positions.get(symbol, 0.0)

    def get_balance(self) -> float:
        return self.balance

    async def stop(self) -> None:
        self._running = False
        await self.feed.close()


__all__ = [
    "CCXTProDataFeed",
    "CompositeDataFeed",
    "DataFeed",
    "DataFeedBroker",
    "DataFeedError",
    "MockDataFeed",
    "get_datafeed",
]
