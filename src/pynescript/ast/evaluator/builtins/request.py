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

from __future__ import annotations

import random

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


# Define constants for magic numbers
REQUEST_SECURITY_MIN_ARGS = 2
REQUEST_OHLCV_LIMIT = 5
OHLCV_CLOSE_IDX = 4
REQUEST_RECENT_LIMIT = 5
REQUEST_MOCK_PRICE = 100.0
LOWER_TF_SIMULATE_MULTIPLIER = 2  # for demo lower tf bar count from latest data


@dataclass
class VolumeRow:
    """Volume row in a footprint object.

    Represents a single price level in a footprint with its volume data.
    Added in Pine Script v6 (January 2026).
    """

    up_price: float = 0.0
    down_price: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta: float = 0.0
    is_imbalance: bool = False
    is_poc: bool = False
    is_vah: bool = False
    is_val: bool = False


@dataclass
class Footprint:
    """Footprint object representing volume profile data for a bar.

    Contains volume data at each price level, including buy/sell volumes,
    delta, Point of Control (POC), and Value Area (VA) boundaries.
    Added in Pine Script v6 (January 2026).
    """

    num_ticks: int = 100
    va_percentage: int = 70
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    delta: float = 0.0
    total_volume: float = 0.0
    vah_row: VolumeRow | None = None
    val_row: VolumeRow | None = None
    poc_row: VolumeRow | None = None
    rows: list[VolumeRow] = field(default_factory=list)


class FootprintBuiltinsMixin(BuiltinDispatchMixin):
    """Footprint type methods for accessing volume profile data.

    Added in Pine Script v6 (January 2026).
    """

    def _footprint_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "footprint.buy_volume": self._handle_footprint_buy_volume,
            "footprint.sell_volume": self._handle_footprint_sell_volume,
            "footprint.delta": self._handle_footprint_delta,
            "footprint.vah": self._handle_footprint_vah,
            "footprint.val": self._handle_footprint_val,
            "footprint.poc": self._handle_footprint_poc,
            "volume_row.up_price": self._handle_volume_row_up_price,
            "volume_row.down_price": self._handle_volume_row_down_price,
        }

    def _handle_footprint_buy_volume(self, args: list[Any]) -> float:
        """footprint.buy_volume(footprint) - Get total buy volume from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.buy_volume
        return 0.0

    def _handle_footprint_sell_volume(self, args: list[Any]) -> float:
        """footprint.sell_volume(footprint) - Get total sell volume from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.sell_volume
        return 0.0

    def _handle_footprint_delta(self, args: list[Any]) -> float:
        """footprint.delta(footprint) - Get volume delta from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.delta
        return 0.0

    def _handle_footprint_vah(self, args: list[Any]) -> VolumeRow | None:
        """footprint.vah(footprint) - Get Value Area High row from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.vah_row
        return None

    def _handle_footprint_val(self, args: list[Any]) -> VolumeRow | None:
        """footprint.val(footprint) - Get Value Area Low row from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.val_row
        return None

    def _handle_footprint_poc(self, args: list[Any]) -> VolumeRow | None:
        """footprint.poc(footprint) - Get Point of Control row from footprint."""
        fp = args[0] if len(args) > 0 else None
        if isinstance(fp, Footprint):
            return fp.poc_row
        return None

    def _handle_volume_row_up_price(self, args: list[Any]) -> float:
        """volume_row.up_price(volume_row) - Get upper price of volume row."""
        vr = args[0] if len(args) > 0 else None
        if isinstance(vr, VolumeRow):
            return vr.up_price
        return 0.0

    def _handle_volume_row_down_price(self, args: list[Any]) -> float:
        """volume_row.down_price(volume_row) - Get lower price of volume row."""
        vr = args[0] if len(args) > 0 else None
        if isinstance(vr, VolumeRow):
            return vr.down_price
        return 0.0


class RequestBuiltinsMixin(BuiltinDispatchMixin):
    """
    Request/data fetching functions for multi-timeframe and fundamental data.
    """

    def _request_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "request.security": self._handle_request_security,
            "request.security_lower_tf": (self._handle_request_security_lower_tf),
            "request.dividends": self._handle_request_dividends,
            "request.earnings": self._handle_request_earnings,
            "request.splits": self._handle_request_splits,
            "request.financial": self._handle_request_financial,
            "request.quandl": self._handle_request_quandl,
            "request.economic": self._handle_request_economic,
            "request.currency_rate": self._handle_request_currency_rate,
            "request.seed": self._handle_request_seed,
            "request.footprint": self._handle_request_footprint,
        }

    def _get_expression_prices(self, expression: str, prices: list[float]) -> list[float]:
        """Return a list of prices based on the expression."""
        expr = expression.lower()
        if expr in ("open", "o"):
            return [p - 0.5 for p in prices]
        if expr in ("high", "h"):
            return [p + 1.0 for p in prices]
        if expr in ("low", "l"):
            return [p - 1.0 for p in prices]
        if expr == "volume":
            return [1000000, 1100000, 1200000, 1050000, 1300000]
        return prices  # Default to close

    def _handle_request_security(self, args: list[Any]) -> Any:  # noqa: C901,PLR0912
        # complexity acceptable: handles multiple data source fallbacks + exprs
        """
        request.security(symbol, timeframe, expression, gaps, lookahead)

        Request data from another symbol or timeframe.

        v6+: Supports real data via context['data_provider'] (historical)
        or context['data_feed'] (CCXTProDataFeed for live/latest data).

        Falls back to mock data if no real provider/feed is configured.
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        timeframe = args[1] if len(args) > 1 else "D"
        expression = args[2] if len(args) > REQUEST_SECURITY_MIN_ARGS else "close"

        # v6 dynamic: handle series (lists) by taking last
        if isinstance(symbol, list):
            symbol = symbol[-1] if symbol else "AAPL"
        if isinstance(timeframe, list):
            timeframe = timeframe[-1] if timeframe else "D"
        if isinstance(expression, list):
            expression = expression[-1] if expression else "close"

        symbol_str = str(symbol).upper() if not isinstance(symbol, str) else symbol.upper()

        # Try real data provider (historical or live)
        data_feed = self.context.get("data_feed") if hasattr(self, "context") else None
        data_provider = self.context.get("data_provider") if hasattr(self, "context") else None

        if data_feed is not None:
            try:
                # Use sync wrapper on CCXTProDataFeed for latest data
                if hasattr(data_feed, "fetch_latest_ohlcv"):
                    ohlcv = data_feed.fetch_latest_ohlcv(symbol, str(timeframe), limit=REQUEST_OHLCV_LIMIT)
                    if ohlcv:
                        closes = [c[OHLCV_CLOSE_IDX] for c in ohlcv if len(c) > OHLCV_CLOSE_IDX]
                        if closes:
                            return self._get_expression_prices(str(expression), closes)
                # Fallback: try ticker last price
                if hasattr(data_feed, "fetch_latest_ticker"):
                    ticker = data_feed.fetch_latest_ticker(symbol)
                    last = ticker.get("last") or ticker.get("close") or REQUEST_MOCK_PRICE
                    return self._get_expression_prices(str(expression), [float(last)] * REQUEST_OHLCV_LIMIT)
            except Exception:  # noqa: S110 - fallback to mock data on feed error
                pass  # fall back to mock

        if data_provider is not None and hasattr(data_provider, "fetch"):
            try:
                data = data_provider.fetch(symbol, period="1d", interval=str(timeframe))
                closes = data.get("close", [])
                if closes:
                    recent = closes[-REQUEST_RECENT_LIMIT:] if len(closes) >= REQUEST_RECENT_LIMIT else closes
                    return self._get_expression_prices(str(expression), [float(x) for x in recent])
            except Exception:  # noqa: S110 - fallback to mock data on provider error
                pass

        # Fallback mock data (original behavior)
        base_prices = {
            "AAPL": [100.0, 101.5, 102.0, 103.5, 105.0],
            "GOOGL": [1000.0, 1015.5, 1020.0, 1035.5, 1050.0],
            "BTC/USD": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
            "BTC/USDT": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
        }

        prices = base_prices.get(symbol_str, [100.0, 101.0, 102.0, 101.5, 103.0])
        if isinstance(expression, str):
            return self._get_expression_prices(expression, prices)
        return prices

    def _handle_request_security_lower_tf(self, args: list[Any]) -> Any:
        """
        request.security_lower_tf(symbol, timeframe, expression)

        Request lower timeframe data within the current timeframe.
        Now supports data_feed / data_provider when wired (reuses latest for demo).
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        timeframe = args[1] if len(args) > 1 else "5m"
        expression = args[2] if len(args) > 2 else "close"  # noqa: PLR2004 - arg count check

        # Try data feed/provider for consistency with request.security
        data_feed = self.context.get("data_feed") if hasattr(self, "context") else None
        data_provider = self.context.get("data_provider") if hasattr(self, "context") else None

        if data_feed is not None and hasattr(data_feed, "fetch_latest_ohlcv"):
            try:
                ohlcv = data_feed.fetch_latest_ohlcv(symbol, str(timeframe), limit=REQUEST_RECENT_LIMIT)
                if ohlcv:
                    closes = [c[OHLCV_CLOSE_IDX] for c in ohlcv if len(c) > OHLCV_CLOSE_IDX]
                    if closes:
                        return closes * LOWER_TF_SIMULATE_MULTIPLIER  # simulate more lower-tf bars from latest
            except Exception:  # noqa: S110
                pass

        if data_provider is not None and hasattr(data_provider, "fetch"):
            try:
                data = data_provider.fetch(symbol, period="1d", interval=str(timeframe))
                closes = data.get("close", [])
                if closes:
                    return closes[-REQUEST_RECENT_LIMIT:] or closes
            except Exception:  # noqa: S110
                pass

        # Fallback mock intrabar data (simulated lower timeframe)
        intrabar_prices = [100.0 + i * 0.25 for i in range(10)]
        if isinstance(expression, str):
            return self._get_expression_prices(str(expression), intrabar_prices)
        return intrabar_prices

    def _handle_request_dividends(self, args: list[Any]) -> float:
        """
        request.dividends(symbol, currency)

        Request dividend information for a symbol.

        Parameters:
            symbol: Symbol/ticker string (str)
            currency: Currency code (str or None)

        Returns dividend amount as float.
        This is a mock implementation.
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        # currency = args[1] if len(args) > 1 else "USD"

        # Mock: return dividend amounts for known symbols
        dividends = {
            "AAPL": 0.24,
            "MSFT": 0.62,
            "JNJ": 1.13,
        }
        return dividends.get(str(symbol).upper(), 0.0)

    def _handle_request_earnings(self, args: list[Any]) -> float:
        """
        request.earnings(symbol, currency)

        Request earnings information for a symbol.

        Parameters:
            symbol: Symbol/ticker string (str)
            currency: Currency code (str or None)

        Returns earnings per share as float.
        This is a mock implementation.
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        # currency = args[1] if len(args) > 1 else "USD"

        # Mock: return EPS for known symbols
        eps = {
            "AAPL": 5.61,
            "MSFT": 9.27,
            "JNJ": 9.13,
        }
        return eps.get(str(symbol).upper(), 0.0)

    def _handle_request_splits(self, args: list[Any]) -> float:
        """
        request.splits(symbol, currency)

        Request stock split information for a symbol.

        Parameters:
            symbol: Symbol/ticker string (str)
            currency: Currency code (str or None)

        Returns split ratio as float.
        This is a mock implementation.
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        # currency = args[1] if len(args) > 1 else "USD"

        # Mock: return split ratios (1.0 = no split)
        splits = {
            "AAPL": 4.0,  # 4-for-1 split
            "TSLA": 3.0,  # 3-for-1 split
            "MSFT": 1.0,  # no recent split
        }
        return splits.get(str(symbol).upper(), 1.0)

    def _handle_request_financial(self, args: list[Any]) -> float:
        """
        request.financial(symbol, financial_id, period)

        Request financial statement data (from SEC filings).

        Parameters:
            symbol: Symbol/ticker string (str)
            financial_id: Financial metric identifier (str)
            period: Reporting period (str, e.g., "FQ", "FY")

        Returns financial metric value as float.
        This is a mock implementation.
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        financial_id = args[1] if len(args) > 1 else "REVENUE"
        # period = args[2] if len(args) > 2 else "FY"

        # Mock: return financial metrics
        financials = {
            ("AAPL", "REVENUE"): 383285000000,
            ("AAPL", "NET_INCOME"): 96995000000,
            ("MSFT", "REVENUE"): 198716000000,
            ("MSFT", "NET_INCOME"): 72794000000,
        }
        key = (str(symbol).upper(), str(financial_id).upper())
        return float(financials.get(key, 0.0))

    def _handle_request_quandl(self, args: list[Any]) -> Any:
        """
        request.quandl(quandl_code, column)

        Request data from Quandl database.

        Parameters:
            quandl_code: Quandl dataset code (str)
            column: Column name within dataset (str)

        Returns series data from Quandl dataset.
        This is a mock implementation.
        """
        quandl_code = args[0] if len(args) > 0 else "EIA/PET_RWTC_D"
        # column = args[1] if len(args) > 1 else "Value"

        # Mock: return time series data for common Quandl datasets
        if "PET_RWTC" in str(quandl_code):
            # Oil prices (WTI Crude Oil)
            return [50.0, 51.5, 52.0, 51.0, 53.5, 55.0, 54.5, 56.0]
        if "GDPC" in str(quandl_code):
            # GDP data
            return [21060000, 21200000, 21400000, 21600000]

        # Default: return generic series
        return [100.0, 101.0, 102.0, 101.5, 103.0]

    def _handle_request_economic(self, args: list[Any]) -> Any:
        """
        request.economic(country, indicator_code)

        Request economic indicator data (e.g., unemployment, inflation).

        Parameters:
            country: Country code (str, e.g., "US", "EU")
            indicator_code: Economic indicator code (str)

        Returns economic data as series or value.
        This is a mock implementation.
        """
        country = args[0] if len(args) > 0 else "US"
        indicator_code = args[1] if len(args) > 1 else "UNRATE"

        # Mock: return economic indicators
        if str(indicator_code).upper() == "UNRATE":
            # US Unemployment Rate (%)
            if str(country).upper() == "US":
                return [3.5, 3.4, 3.6, 3.7, 3.8]
            # EU Unemployment Rate (%)
            if str(country).upper() == "EU":
                return [6.1, 6.0, 6.2, 6.3, 6.4]

        if str(indicator_code).upper() == "INFLATION":
            # Inflation Rate (%)
            if str(country).upper() == "US":
                return [3.4, 3.2, 3.0, 2.9, 2.8]
            if str(country).upper() == "EU":
                return [2.6, 2.4, 2.2, 2.1, 2.0]

        # Default: return generic series
        return [100.0, 101.0, 102.0, 101.5, 103.0]

    def _handle_request_currency_rate(self, args: list[Any]) -> float:
        """
        request.currency_rate(from_currency, to_currency)

        Request exchange rate between two currencies.

        Parameters:
            from_currency: Source currency code (str, e.g., "USD")
            to_currency: Target currency code (str, e.g., "EUR")

        Returns exchange rate as float.
        This is a mock implementation.
        """
        from_currency = args[0] if len(args) > 0 else "USD"
        to_currency = args[1] if len(args) > 1 else "EUR"

        # Mock: return exchange rates
        rates = {
            ("USD", "EUR"): 0.92,
            ("USD", "GBP"): 0.79,
            ("USD", "JPY"): 149.5,
            ("EUR", "USD"): 1.09,
            ("EUR", "GBP"): 0.86,
            ("GBP", "USD"): 1.27,
        }

        key = (str(from_currency).upper(), str(to_currency).upper())
        return rates.get(key, 1.0)

    def _handle_request_seed(self, args: list[Any]) -> None:
        """
        request.seed(seed_value)

        Seed the random number generator for reproducible random data.

        Parameters:
            seed_value: Random seed (int)

        Returns None.
        This is a mock implementation.
        """
        seed_value = args[0] if len(args) > 0 else 0

        # Seed Python's random module for reproducibility
        random.seed(seed_value)

    def _handle_request_footprint(self, args: list[Any]) -> Footprint | None:
        """
        request.footprint(num_ticks, va_percentage)

        Request volume footprint data for the current bar.
        Added in Pine Script v6 (January 2026).

        Parameters:
            num_ticks: Number of ticks per footprint row (int)
            va_percentage: Value Area percentage (int, default 70)

        Returns:
            Footprint object containing volume profile data, or None if no data available.
        This is a mock implementation that generates sample footprint data.
        """
        num_ticks = args[0] if len(args) > 0 else 100
        va_percentage = args[1] if len(args) > 1 else 70

        rows: list[VolumeRow] = []
        base_price = 100.0
        tick_size = 0.01

        for i in range(num_ticks):
            price_level = base_price + (i * tick_size)
            row = VolumeRow(
                up_price=price_level + tick_size,
                down_price=price_level,
                buy_volume=1000.0 + (random.random() * 500),
                sell_volume=900.0 + (random.random() * 500),
                delta=100.0 + (random.random() * 200 - 100),
                is_imbalance=random.random() < 0.1,  # noqa: PLR2004 - mock data gen
                is_poc=(i == num_ticks // 2),
                is_vah=(i == int(num_ticks * 0.7)),
                is_val=(i == int(num_ticks * 0.3)),
            )
            rows.append(row)

        poc_idx = num_ticks // 2
        vah_idx = int(num_ticks * 0.7)
        val_idx = int(num_ticks * 0.3)

        total_buy = sum(r.buy_volume for r in rows)
        total_sell = sum(r.sell_volume for r in rows)

        footprint = Footprint(
            num_ticks=num_ticks,
            va_percentage=va_percentage,
            buy_volume=total_buy,
            sell_volume=total_sell,
            delta=total_buy - total_sell,
            total_volume=total_buy + total_sell,
            vah_row=rows[vah_idx] if vah_idx < len(rows) else None,
            val_row=rows[val_idx] if val_idx < len(rows) else None,
            poc_row=rows[poc_idx] if poc_idx < len(rows) else None,
            rows=rows,
        )

        return footprint
