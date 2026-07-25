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
        self.style = None  # v6 e.g. "PercentageLTP"

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
    ticker: str | TickerInfo,
    symbol: str | None = None,
    session: str | None = None,
    adjust: str | None = None,
) -> TickerInfo:
    """Modify an existing ticker object.

    Creates a copy of the ticker with modified parameters.

    Args:
        ticker: The original ticker object (or raw symbol string)
        symbol: New symbol (or None to keep original)
        session: New session (or None to keep original)
        adjust: New adjustment (or None to keep original)

    Returns:
        New TickerInfo object with modified parameters
    """
    if isinstance(ticker, str):
        ticker = TickerInfo(ticker)
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


def ticker_kagi(ticker_str: str, short: float = 3.0, style: str = None) -> TickerInfo:
    """Create a Kagi chart ticker from a symbol.

    Applies Kagi charting transformation. v6 style support.

    Args:
        ticker_str: The base ticker symbol
        short: The reversal amount for Kagi charts
        style: e.g. "PercentageLTP"

    Returns:
        TickerInfo with Kagi transformation applied
    """
    ticker = TickerInfo(f"KAGI({ticker_str},{short})")
    ticker.kagi_applied = True
    if style:
        ticker.style = style
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


def ticker_pointfigure(ticker_str: str, boxsize: float = 1.0, style: str = None) -> TickerInfo:
    """Create a Point and Figure chart ticker from a symbol.

    Applies Point and Figure charting transformation. v6: style e.g. "PercentageLTP"

    Args:
        ticker_str: The base ticker symbol
        boxsize: The box size for point and figure charting
        style: optional style

    Returns:
        TickerInfo with Point and Figure transformation applied
    """
    ticker = TickerInfo(f"PF({ticker_str},{boxsize})")
    ticker.pointfigure_applied = True
    if style:
        ticker.style = style
    return ticker


def ticker_renko(ticker_str: str, boxsize: float = 1.0, style: str = None) -> TickerInfo:
    """Create a Renko chart ticker from a symbol.

    Applies Renko charting transformation. v6: supports style="PercentageLTP" etc.

    Args:
        ticker_str: The base ticker symbol
        boxsize: The brick size for Renko charts
        style: Chart style e.g. "PercentageLTP" (v6)

    Returns:
        TickerInfo with Renko transformation applied
    """
    ticker = TickerInfo(f"RENKO({ticker_str},{boxsize})")
    ticker.renko_applied = True
    if style:
        ticker.style = style
    return ticker


def ticker_inherit(ticker_str: str | TickerInfo | None = None) -> TickerInfo:
    """Inherit chart properties for a ticker (session/adjust from main chart).

    Pine: ``ticker.inherit(symbol)`` returns a ticker that inherits the chart's
    session and adjustment settings.
    """
    if isinstance(ticker_str, TickerInfo):
        return TickerInfo(
            symbol=ticker_str.symbol,
            session=ticker_str.session,
            adjust=ticker_str.adjust,
        )
    symbol = str(ticker_str) if ticker_str is not None else ""
    return TickerInfo(symbol=symbol)


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
    from .declarations import _as_builtin_handler

    namespace["ticker.new"] = _as_builtin_handler(ticker_new)
    namespace["ticker.modify"] = _as_builtin_handler(ticker_modify)
    namespace["ticker.heikinashi"] = _as_builtin_handler(ticker_heikinashi)
    namespace["ticker.kagi"] = _as_builtin_handler(ticker_kagi)
    namespace["ticker.linebreak"] = _as_builtin_handler(ticker_linebreak)
    namespace["ticker.pointfigure"] = _as_builtin_handler(ticker_pointfigure)
    namespace["ticker.renko"] = _as_builtin_handler(ticker_renko)
    namespace["ticker.standard"] = _as_builtin_handler(ticker_standard)
    namespace["ticker.inherit"] = _as_builtin_handler(ticker_inherit)
