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

"""Real-time and Historical Data Integration for PyneScript.

This module provides data connectors for fetching market data:
- Mock provider for testing
- Yahoo Finance (yfinance)
- Alpha Vantage API

Usage:
    from pynescript.util.data import YahooFinanceProvider

    provider = YahooFinanceProvider()
    data = provider.fetch("AAPL", "1y", "1d")
    print(data['close'][:5])
"""

from __future__ import annotations

import random

from abc import ABC
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from typing import Any


class DataProvider(ABC):
    """Abstract base class for data providers."""

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Fetch historical data.

        Args:
            symbol: Stock/asset symbol (e.g., "AAPL", "BTC-USD")
            period: Time period (e.g., "1d", "1w", "1mo", "1y", "5y")
            interval: Data interval (e.g., "1m", "5m", "1h", "1d", "1w")

        Returns:
            Dictionary with 'open', 'high', 'low', 'close', 'volume' keys

        Raises:
            DataProviderError: If data fetch fails
        """
        ...

    @abstractmethod
    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch current quote.

        Args:
            symbol: Stock/asset symbol

        Returns:
            Dictionary with price data
        """
        ...


class DataProviderError(Exception):
    """Error raised by data providers."""

    pass


class ChartOHLCVProvider(DataProvider):
    """Historical provider backed by in-memory chart bars (Runtime OHLCV).

    Used so ``request.security`` on the chart symbol returns the same series
    the script is evaluating, without network I/O.
    """

    def __init__(self, bars: list[dict[str, Any]], symbol: str = "CHART"):
        self._bars = list(bars or [])
        self._symbol = str(symbol).upper()

    def _matches_chart(self, symbol: str) -> bool:
        """Only serve bars for the chart symbol (not foreign fundamentals)."""
        s = str(symbol or "").strip().upper()
        chart = (self._symbol or "CHART").strip().upper()
        if not s or s in {"CHART", "SYMBOL", "TICKER", "NONE", chart}:
            return True
        if s.split(":")[-1] == chart.split(":")[-1]:
            return True
        return False

    def fetch(
        self,
        symbol: str = "CHART",
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        _ = period, interval
        empty = {
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "time": [],
            "symbol": self._symbol,
        }
        if not self._matches_chart(symbol):
            return empty
        bars = self._bars
        if not bars:
            return empty
        return {
            "open": [float(b.get("open", 0.0)) for b in bars],
            "high": [float(b.get("high", 0.0)) for b in bars],
            "low": [float(b.get("low", 0.0)) for b in bars],
            "close": [float(b.get("close", 0.0)) for b in bars],
            "volume": [float(b.get("volume", 0.0)) for b in bars],
            "time": [b.get("time", 0) for b in bars],
            "symbol": self._symbol,
        }

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        if not self._matches_chart(symbol) or not self._bars:
            return {"last": 0.0, "close": 0.0, "symbol": self._symbol}
        last = self._bars[-1]
        c = float(last.get("close", 0.0))
        return {
            "symbol": self._symbol,
            "last": c,
            "close": c,
            "open": float(last.get("open", c)),
            "high": float(last.get("high", c)),
            "low": float(last.get("low", c)),
            "volume": float(last.get("volume", 0.0)),
            "timestamp": last.get("time", 0),
        }


class MockDataProvider(DataProvider):
    """Mock data provider for testing and development.

    Generates realistic-looking OHLCV data without external API calls.
    """

    def __init__(self, seed: int | None = None):
        """Initialize mock provider.

        Args:
            seed: Random seed for reproducible data
        """
        self._rng = random.Random(seed)

    def fetch(
        self,
        symbol: str = "TEST",
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Generate mock OHLCV data.

        Args:
            symbol: Symbol name (used for seed)
            period: Time period
            interval: Data interval

        Returns:
            Dictionary with mock OHLCV data
        """
        period_map = {
            "1d": 1,
            "1w": 7,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
        }
        days = period_map.get(period, 365)

        num_bars = min(days, 5000)
        start_price = self._get_seed_price(symbol)

        close = [start_price]
        for _ in range(num_bars - 1):
            change = self._rng.gauss(0.0005, 0.02) * close[-1]
            close.append(max(close[-1] + change, 0.01))

        opens = close[:-1]
        opens.insert(0, start_price * (1 + self._rng.uniform(-0.01, 0.01)))

        volatility = 0.02
        highs = [max(o, c) * (1 + self._rng.uniform(0, volatility)) for o, c in zip(opens, close, strict=False)]
        lows = [min(o, c) * (1 - self._rng.uniform(0, volatility)) for o, c in zip(opens, close, strict=False)]

        base_volume = 1000000 if not symbol.startswith("BTC") else 100000
        volumes = [int(self._rng.gauss(base_volume, base_volume * 0.3)) for _ in range(num_bars)]
        volumes = [max(v, 1) for v in volumes]

        return {
            "symbol": symbol,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": close,
            "volume": volumes,
        }

    def fetch_quote(self, symbol: str = "TEST") -> dict[str, Any]:
        """Generate mock quote.

        Args:
            symbol: Symbol name

        Returns:
            Dictionary with mock quote data
        """
        price = self._get_seed_price(symbol)
        spread = price * 0.001

        return {
            "symbol": symbol,
            "bid": price - spread,
            "ask": price + spread,
            "last": price,
            "open": price * (1 + self._rng.uniform(-0.02, 0.02)),
            "high": price * (1 + self._rng.uniform(0, 0.05)),
            "low": price * (1 - self._rng.uniform(0, 0.05)),
            "volume": int(self._rng.gauss(1000000, 300000)),
            "timestamp": datetime.now().isoformat(),
        }

    def _get_seed_price(self, symbol: str) -> float:
        """Get base price for symbol."""
        seed_map = {
            "BTC": 50000,
            "ETH": 3000,
            "SPY": 500,
            "QQQ": 400,
            "AAPL": 180,
            "GOOGL": 140,
            "MSFT": 380,
            "TSLA": 250,
            "NVDA": 500,
            "AMZN": 180,
        }
        return seed_map.get(symbol.upper(), 100.0)


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance data provider using yfinance library.

    Requires: pip install yfinance
    """

    def __init__(self):
        """Initialize Yahoo Finance provider."""
        self._yf: Any | None = None

    def _get_yf(self):
        """Lazy import yfinance."""
        if self._yf is None:
            try:
                import yfinance as yf

                self._yf = yf
            except ImportError:
                msg = "yfinance not installed. Install with: pip install yfinance"
                raise DataProviderError(msg)
        return self._yf

    def fetch(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Fetch data from Yahoo Finance.

        Args:
            symbol: Stock/asset symbol
            period: Time period (1d, 1w, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 5m, 15m, 30m, 60m, 1h, 1d, 1w, 1mo)

        Returns:
            Dictionary with OHLCV data
        """
        yf = self._get_yf()

        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)

        if data.empty:
            msg = f"No data found for symbol: {symbol}"
            raise DataProviderError(msg)

        return {
            "symbol": symbol,
            "open": data["Open"].tolist(),
            "high": data["High"].tolist(),
            "low": data["Low"].tolist(),
            "close": data["Close"].tolist(),
            "volume": data["Volume"].tolist(),
        }

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch current quote from Yahoo Finance.

        Args:
            symbol: Stock/asset symbol

        Returns:
            Dictionary with quote data
        """
        yf = self._get_yf()

        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            "symbol": symbol,
            "bid": info.get("bid", 0) or 0,
            "ask": info.get("ask", 0) or 0,
            "last": info.get("currentPrice", 0) or 0,
            "open": info.get("open", 0) or 0,
            "high": info.get("dayHigh", 0) or 0,
            "low": info.get("dayLow", 0) or 0,
            "volume": info.get("volume", 0) or 0,
            "timestamp": datetime.now().isoformat(),
        }


class AlphaVantageProvider(DataProvider):
    """Alpha Vantage data provider.

    Requires: pip install alpha-vantage
    Get free API key: https://www.alphavantage.co/support/#api-key
    """

    def __init__(self, api_key: str = "demo"):
        """Initialize Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key (default: "demo" has limited access)
        """
        self._api_key = api_key
        self._client: dict[str, Any] | None = None

    def _get_client(self) -> dict[str, Any]:
        """Lazy import alpha-vantage."""
        if self._client is None:
            try:
                from alpha_vantage.foreignexchange import ForeignExchange
                from alpha_vantage.techindicators import TechIndicators

                self._client = {"fx": ForeignExchange(key=self._api_key), "ti": TechIndicators(key=self._api_key)}
            except ImportError:
                msg = "alpha-vantage not installed. Install with: pip install alpha-vantage"
                raise DataProviderError(msg)
        return self._client

    def fetch(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Fetch data from Alpha Vantage.

        Args:
            symbol: Stock/asset symbol (e.g., "IBM", "EUR/USD")
            period: Time period (compact, full)
            interval: Data interval

        Returns:
            Dictionary with OHLCV data
        """
        client = self._get_client()

        try:
            data, meta = client["ti"].get_daily(symbol=symbol, outputsize="full" if period == "full" else "compact")
        except Exception as e:
            msg = f"Failed to fetch data: {e}"
            raise DataProviderError(msg)

        dates = sorted(data.keys(), reverse=True)
        limit = 365 if period == "compact" else None
        if limit:
            dates = dates[:limit]

        return {
            "symbol": symbol,
            "open": [float(data[d]["1. open"]) for d in dates],
            "high": [float(data[d]["2. high"]) for d in dates],
            "low": [float(data[d]["3. low"]) for d in dates],
            "close": [float(data[d]["4. close"]) for d in dates],
            "volume": [int(data[d]["5. volume"]) for d in dates],
        }

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch current quote from Alpha Vantage.

        Args:
            symbol: Stock/asset symbol

        Returns:
            Dictionary with quote data
        """
        client = self._get_client()

        try:
            data, _ = client["ti"].get_quote_endpoint(symbol=symbol)
        except Exception as e:
            msg = f"Failed to fetch quote: {e}"
            raise DataProviderError(msg)

        return {
            "symbol": symbol,
            "last": float(data.get("05. price", 0)),
            "open": float(data.get("02. open", 0)),
            "high": float(data.get("03. high", 0)),
            "low": float(data.get("04. low", 0)),
            "volume": int(data.get("06. volume", 0)),
            "timestamp": data.get("07. latest trading day", ""),
        }


class CCXTProvider(DataProvider):
    """CCXT crypto exchange data provider.

    Supports 100+ exchanges including Binance, Coinbase, Kraken, etc.
    Requires: pip install ccxt

    Usage:
        >>> provider = get_provider("ccxt", exchange="binance")
        >>> data = provider.fetch("BTC/USDT", "1y")
    """

    def __init__(
        self,
        exchange: str = "binance",
        api_key: str = "",
        secret: str = "",
    ):
        """Initialize CCXT provider.

        Args:
            exchange: Exchange name (binance, coinbase, kraken, etc.)
            api_key: API key for authenticated requests
            secret: API secret for authenticated requests
        """
        self._exchange_name = exchange
        self._api_key = api_key
        self._secret = secret
        self._exchange: Any | None = None

    def _get_exchange(self):
        """Lazy import and initialize CCXT."""
        if self._exchange is None:
            try:
                import ccxt

                exchange_class = getattr(ccxt, self._exchange_name.lower(), None)
                if exchange_class is None:
                    msg = f"Exchange '{self._exchange_name}' not found in CCXT"
                    raise DataProviderError(msg)

                params = {}
                if self._api_key and self._secret:
                    params["apiKey"] = self._api_key
                    params["secret"] = self._secret

                self._exchange = exchange_class(params)
            except ImportError:
                msg = "ccxt not installed. Install with: pip install ccxt"
                raise DataProviderError(msg)
        return self._exchange

    def _parse_timeframe(self, interval: str) -> str:
        """Convert interval to CCXT timeframe."""
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
        }
        return mapping.get(interval, "1d")

    def fetch(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Fetch OHLCV data from CCXT exchange.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT", "ETH/BTC")
            period: Time period (used to calculate since timestamp)
            interval: Data interval

        Returns:
            Dictionary with OHLCV data
        """
        exchange = self._get_exchange()

        period_map = {
            "1d": 1,
            "1w": 7,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
        }
        days = period_map.get(period, 365)
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        timeframe = self._parse_timeframe(interval)

        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since)
        except Exception as e:
            msg = f"Failed to fetch data from {self._exchange_name}: {e}"
            raise DataProviderError(msg)

        return {
            "symbol": symbol,
            "open": [c[1] for c in ohlcv],
            "high": [c[2] for c in ohlcv],
            "low": [c[3] for c in ohlcv],
            "close": [c[4] for c in ohlcv],
            "volume": [c[5] for c in ohlcv],
        }

    def fetch_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch current quote from CCXT exchange.

        Args:
            symbol: Trading pair

        Returns:
            Dictionary with quote data
        """
        exchange = self._get_exchange()

        try:
            ticker = exchange.fetch_ticker(symbol)
        except Exception as e:
            msg = f"Failed to fetch quote: {e}"
            raise DataProviderError(msg)

        return {
            "symbol": symbol,
            "bid": ticker.get("bid", 0) or 0,
            "ask": ticker.get("ask", 0) or 0,
            "last": ticker.get("last", 0) or 0,
            "open": ticker.get("open", 0) or 0,
            "high": ticker.get("high", 0) or 0,
            "low": ticker.get("low", 0) or 0,
            "volume": ticker.get("baseVolume", 0) or 0,
            "timestamp": datetime.now().isoformat(),
        }


def get_provider(name: str = "yahoo", **kwargs) -> DataProvider:
    """Get a data provider by name.

    Args:
        name: Provider name ("mock", "yahoo", "alphavantage", "ccxt")
        **kwargs: Provider-specific options

    Returns:
        DataProvider instance

    Examples:
        >>> provider = get_provider("mock")
        >>> provider = get_provider("yahoo")
        >>> provider = get_provider("alphavantage", api_key="YOUR_KEY")
        >>> provider = get_provider("ccxt", exchange="binance")
    """
    providers: dict[str, type[DataProvider]] = {
        "mock": MockDataProvider,
        "yahoo": YahooFinanceProvider,
        "alphavantage": AlphaVantageProvider,
        "ccxt": CCXTProvider,
        "chart": ChartOHLCVProvider,  # needs bars= kwargs
    }

    if name not in providers:
        msg = f"Unknown provider: {name}. Available: {list(providers.keys())}"
        raise DataProviderError(msg)

    provider_kwargs = {}
    if name == "alphavantage":
        provider_kwargs["api_key"] = kwargs.get("api_key", "demo")
    elif name == "ccxt":
        provider_kwargs["exchange"] = kwargs.get("exchange", "binance")
        provider_kwargs["api_key"] = kwargs.get("api_key", "")
        provider_kwargs["secret"] = kwargs.get("secret", "")
    elif name == "chart":
        provider_kwargs["bars"] = kwargs.get("bars", [])
        provider_kwargs["symbol"] = kwargs.get("symbol", "CHART")

    return providers[name](**provider_kwargs)


def resolve_request_sources(
    *,
    data_feed: Any = None,
    data_provider: Any = None,
    chart_bars: list[dict[str, Any]] | None = None,
    symbol: str = "CHART",
    data_source: str | None = None,
    source_options: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    """Resolve (data_feed, data_provider) for Runtime / request.* wiring.

    Priority:
    1. Explicit ``data_feed`` / ``data_provider`` arguments
    2. ``data_source`` factory: mock | ccxt | ccxtpro | yahoo | alphavantage
    3. Chart bars as historical provider (always attached when bars given and
       no other provider was set)

    Returns:
        ``(data_feed, data_provider)`` possibly None.
    """
    opts = dict(source_options or {})
    feed = data_feed
    provider = data_provider

    if data_source:
        src = str(data_source).lower()
        if src in {"mock", "ccxtpro", "ccxt", "pro"} and feed is None:
            from pynescript.util.datafeed import get_datafeed

            if src == "mock":
                feed = get_datafeed("mock", **opts)
            else:
                feed = get_datafeed(
                    "ccxtpro",
                    exchange=opts.get("exchange", "binance"),
                    api_key=opts.get("api_key", ""),
                    secret=opts.get("secret", ""),
                    password=opts.get("password", ""),
                    sandbox=bool(opts.get("sandbox", False)),
                )
        elif src in {"yahoo", "alphavantage", "ccxt"} and provider is None:
            # historical-only providers
            if src == "ccxt":
                provider = get_provider("ccxt", **opts)
            else:
                provider = get_provider(src, **opts)
        elif src == "mock" and provider is None and feed is None:
            provider = get_provider("mock", seed=opts.get("seed"))

    if provider is None and chart_bars:
        provider = ChartOHLCVProvider(chart_bars, symbol=symbol)

    return feed, provider


__all__ = [
    "AlphaVantageProvider",
    "CCXTProvider",
    "ChartOHLCVProvider",
    "DataProvider",
    "DataProviderError",
    "MockDataProvider",
    "YahooFinanceProvider",
    "get_provider",
    "resolve_request_sources",
]
