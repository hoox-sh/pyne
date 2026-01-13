# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Ticker functions for PineScript v6 evaluator."""

from __future__ import annotations


class TickerInfo:
    """Represents a ticker symbol with optional modifications."""

    def __init__(
        self,
        symbol: str,
        session: str | None = None,
        adjust: str | None = None,
    ):
        """Initialize a ticker info object.

        Args:
            symbol: The ticker symbol (e.g., "AAPL", "EURUSD")
            session: Trading session type (e.g., "extended", "regular")
            adjust: Adjustment type for splits/dividends (e.g., "splits", "dividends")
        """
        self.symbol = str(symbol)
        self.session = session
        self.adjust = adjust
        self.heikinashi_applied = False
        self.kagi_applied = False
        self.linebreak_applied = False
        self.pointfigure_applied = False
        self.renko_applied = False

    def __repr__(self) -> str:
        """Return string representation of ticker."""
        parts = [f"'{self.symbol}'"]
        if self.session:
            parts.append(f"session='{self.session}'")
        if self.adjust:
            parts.append(f"adjust='{self.adjust}'")
        return f"ticker({', '.join(parts)})"

    def __str__(self) -> str:
        """Return string representation of ticker."""
        return self.__repr__()


def ticker_new(
    symbol: str,
    session: str | None = None,
    adjust: str | None = None,
) -> TickerInfo:
    """Create a new ticker object.

    Creates a ticker symbol with optional session and adjustment parameters.

    Args:
        symbol: The ticker symbol (e.g., "AAPL", "EURUSD")
        session: Trading session ("regular", "extended", etc.)
        adjust: Adjustment type ("splits", "dividends", etc.)

    Returns:
        TickerInfo object representing the configured ticker
    """
    return TickerInfo(symbol, session, adjust)


def ticker_modify(
    ticker: TickerInfo,
    symbol: str | None = None,
    session: str | None = None,
    adjust: str | None = None,
) -> TickerInfo:
    """Modify an existing ticker object.

    Creates a copy of the ticker with modified parameters.

    Args:
        ticker: The original ticker object
        symbol: New symbol (or None to keep original)
        session: New session (or None to keep original)
        adjust: New adjustment (or None to keep original)

    Returns:
        New TickerInfo object with modified parameters
    """
    new_symbol = symbol if symbol is not None else ticker.symbol
    new_session = session if session is not None else ticker.session
    new_adjust = adjust if adjust is not None else ticker.adjust
    return TickerInfo(new_symbol, new_session, new_adjust)


def ticker_heikinashi(ticker_str: str) -> TickerInfo:
    """Create a Heikin-Ashi ticker from a symbol.

    Applies Heikin-Ashi candlestick transformation.

    Args:
        ticker_str: The base ticker symbol

    Returns:
        TickerInfo with Heikin-Ashi transformation applied
    """
    ticker = TickerInfo(f"HA({ticker_str})")
    ticker.heikinashi_applied = True
    return ticker


def ticker_kagi(ticker_str: str, short: float = 3.0) -> TickerInfo:
    """Create a Kagi chart ticker from a symbol.

    Applies Kagi charting transformation.

    Args:
        ticker_str: The base ticker symbol
        short: The reversal amount for Kagi charts

    Returns:
        TickerInfo with Kagi transformation applied
    """
    ticker = TickerInfo(f"KAGI({ticker_str},{short})")
    ticker.kagi_applied = True
    return ticker


def ticker_linebreak(ticker_str: str, reversal: int = 3) -> TickerInfo:
    """Create a Line Break chart ticker from a symbol.

    Applies Line Break charting transformation.

    Args:
        ticker_str: The base ticker symbol
        reversal: Number of lines for reversal

    Returns:
        TickerInfo with Line Break transformation applied
    """
    ticker = TickerInfo(f"LB({ticker_str},{reversal})")
    ticker.linebreak_applied = True
    return ticker


def ticker_pointfigure(ticker_str: str, boxsize: float = 1.0) -> TickerInfo:
    """Create a Point and Figure chart ticker from a symbol.

    Applies Point and Figure charting transformation.

    Args:
        ticker_str: The base ticker symbol
        boxsize: The box size for point and figure charting

    Returns:
        TickerInfo with Point and Figure transformation applied
    """
    ticker = TickerInfo(f"PF({ticker_str},{boxsize})")
    ticker.pointfigure_applied = True
    return ticker


def ticker_renko(ticker_str: str, boxsize: float = 1.0) -> TickerInfo:
    """Create a Renko chart ticker from a symbol.

    Applies Renko charting transformation.

    Args:
        ticker_str: The base ticker symbol
        boxsize: The brick size for Renko charts

    Returns:
        TickerInfo with Renko transformation applied
    """
    ticker = TickerInfo(f"RENKO({ticker_str},{boxsize})")
    ticker.renko_applied = True
    return ticker


def ticker_standard(ticker_str: str) -> TickerInfo:
    """Create a standard OHLC ticker from a symbol.

    Ensures standard candlestick format.

    Args:
        ticker_str: The base ticker symbol

    Returns:
        TickerInfo with standard OHLC format
    """
    return TickerInfo(str(ticker_str))


def register_ticker_functions(namespace: dict) -> None:
    """Register all ticker functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["ticker.new"] = ticker_new
    namespace["ticker.modify"] = ticker_modify
    namespace["ticker.heikinashi"] = ticker_heikinashi
    namespace["ticker.kagi"] = ticker_kagi
    namespace["ticker.linebreak"] = ticker_linebreak
    namespace["ticker.pointfigure"] = ticker_pointfigure
    namespace["ticker.renko"] = ticker_renko
    namespace["ticker.standard"] = ticker_standard
