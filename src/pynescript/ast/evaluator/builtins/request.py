from __future__ import annotations

import random
from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler


class RequestBuiltinsMixin(BuiltinDispatchMixin):
    """Request/data fetching functions for multi-timeframe and fundamental data."""

    def _request_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "request.security": self._handle_request_security,
            "request.security_lower_tf": self._handle_request_security_lower_tf,
            "request.dividends": self._handle_request_dividends,
            "request.earnings": self._handle_request_earnings,
            "request.splits": self._handle_request_splits,
            "request.financial": self._handle_request_financial,
            "request.quandl": self._handle_request_quandl,
            "request.economic": self._handle_request_economic,
            "request.currency_rate": self._handle_request_currency_rate,
            "request.seed": self._handle_request_seed,
        }

    def _handle_request_security(self, args: list[Any]) -> Any:
        """
        request.security(symbol, timeframe, expression, gaps, lookahead)

        Request data from another symbol or timeframe.

        Parameters:
            symbol: Symbol/ticker string (str)
            timeframe: Timeframe string (e.g., "1H", "D") (str)
            expression: Expression to evaluate (series, value, or variable)
            gaps: Gap handling mode ("on", "off") (str or None)
            lookahead: Lookahead mode ("on", "off", "barmerge") (str or None)

        Returns series data or value depending on expression type.
        This is a mock implementation that returns deterministic data.
        """
        symbol = args[0] if len(args) > 0 else "AAPL"
        _timeframe = args[1] if len(args) > 1 else "D"
        expression = args[2] if len(args) > 2 else "close"
        _gaps = args[3] if len(args) > 3 else "on"
        _lookahead = args[4] if len(args) > 4 else "off"

        # Mock implementation: return a series of prices based on symbol
        base_prices = {
            "AAPL": [100.0, 101.5, 102.0, 103.5, 105.0],
            "GOOGL": [1000.0, 1015.5, 1020.0, 1035.5, 1050.0],
            "BTC/USD": [25000.0, 26000.0, 27000.0, 26500.0, 28000.0],
        }

        prices = base_prices.get(
            str(symbol).upper(),
            [100.0, 101.0, 102.0, 101.5, 103.0],
        )

        # Return the series for the requested expression
        if isinstance(expression, str):
            if expression.lower() in ("close", "c"):
                return prices
            elif expression.lower() in ("open", "o"):
                return [p - 0.5 for p in prices]
            elif expression.lower() in ("high", "h"):
                return [p + 1.0 for p in prices]
            elif expression.lower() in ("low", "l"):
                return [p - 1.0 for p in prices]
            elif expression.lower() == "volume":
                return [1000000, 1100000, 1200000, 1050000, 1300000]

        # Default: return close prices
        return prices

    def _handle_request_security_lower_tf(self, args: list[Any]) -> Any:
        """
        request.security_lower_tf(symbol, timeframe, expression)

        Request lower timeframe data within the current timeframe.

        Parameters:
            symbol: Symbol/ticker string (str)
            timeframe: Target timeframe (str)
            expression: Expression to evaluate (Any)

        Returns list of values from lower timeframe bars.
        This is a mock implementation.
        """
        _symbol = args[0] if len(args) > 0 else "AAPL"
        _timeframe = args[1] if len(args) > 1 else "5m"
        _expression = args[2] if len(args) > 2 else "close"

        # Mock implementation: return intrabar data
        intrabar_prices = [
            100.0, 100.25, 100.5, 100.75, 101.0,
            101.25, 101.5, 101.75, 102.0, 102.25,
        ]
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
        _currency = args[1] if len(args) > 1 else "USD"

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
        _currency = args[1] if len(args) > 1 else "USD"

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
        _currency = args[1] if len(args) > 1 else "USD"

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
        _period = args[2] if len(args) > 2 else "FY"

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
        _column = args[1] if len(args) > 1 else "Value"

        # Mock: return time series data for common Quandl datasets
        if "PET_RWTC" in str(quandl_code):
            # Oil prices (WTI Crude Oil)
            return [50.0, 51.5, 52.0, 51.0, 53.5, 55.0, 54.5, 56.0]
        elif "GDPC" in str(quandl_code):
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
            elif str(country).upper() == "EU":
                return [6.1, 6.0, 6.2, 6.3, 6.4]

        elif str(indicator_code).upper() == "INFLATION":
            # Inflation Rate (%)
            if str(country).upper() == "US":
                return [3.4, 3.2, 3.0, 2.9, 2.8]
            elif str(country).upper() == "EU":
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
