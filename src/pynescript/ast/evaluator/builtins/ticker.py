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

"""Ticker functions for PineScript v6 evaluator."""

from __future__ import annotations

from typing import Any


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
    symbol: str = "",
    session: str | None = None,
    adjust: str | None = None,
    *extra: object,
    **kwargs: object,
) -> TickerInfo:
    """Create a new ticker object.

    Creates a ticker symbol with optional session and adjustment parameters.
    Extra positional/keyword args (TV has more overloads) are ignored.

    Args:
        symbol: The ticker symbol (e.g., "AAPL", "EURUSD")
        session: Trading session ("regular", "extended", etc.)
        adjust: Adjustment type ("splits", "dividends", etc.)

    Returns:
        TickerInfo object representing the configured ticker
    """
    if kwargs:
        session = kwargs.get("session", session)  # type: ignore[assignment]
        adjust = kwargs.get("adjustment", kwargs.get("adjust", adjust))  # type: ignore[assignment]
        if not symbol and "symbol" in kwargs:
            symbol = str(kwargs["symbol"])
    return TickerInfo(str(symbol) if symbol is not None else "", session, adjust)


def ticker_modify(
    ticker: str | TickerInfo,
    symbol: str | None = None,
    session: str | None = None,
    adjust: str | None = None,
    *extra: object,
    **kwargs: object,
) -> TickerInfo:
    """Modify an existing ticker object.

    Creates a copy of the ticker with modified parameters.

    TradingView forms::

        ticker.modify(tickerid, session, adjustment)
        ticker.modify(syminfo.tickerid, adjustment=adjustment.dividends)

    ``adjustment`` is accepted as a kw alias for ``adjust`` (corpus demos).
    Extra positional/keyword args are ignored so arity drift does not TypeError.

    Args:
        ticker: The original ticker object (or raw symbol string)
        symbol: New symbol (or None to keep original)
        session: New session (or None to keep original)
        adjust: New adjustment (or None to keep original)

    Returns:
        New TickerInfo object with modified parameters
    """
    if kwargs:
        if symbol is None and kwargs.get("symbol") is not None:
            symbol = str(kwargs["symbol"])  # type: ignore[assignment]
        if session is None and kwargs.get("session") is not None:
            session = str(kwargs["session"])  # type: ignore[assignment]
        # TV docs name the parameter ``adjustment``; keep ``adjust`` as alias.
        adj_kw = kwargs.get("adjustment", kwargs.get("adjust"))
        if adj_kw is not None:
            adjust = str(adj_kw)  # type: ignore[assignment]
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


_PNF_SOURCES = frozenset(
    {
        "hl",
        "close",
        "open",
        "high",
        "low",
        "hlc3",
        "ohlc4",
        "hlcc4",
        "oc2",
        "h",
        "l",
        "o",
        "c",
    }
)


def _as_float_default(v: Any, default: float = 1.0) -> float:
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def _as_int_or_none(v: Any) -> int | None:
    try:
        return None if v is None else int(float(v))
    except (TypeError, ValueError):
        return None


def ticker_pointfigure(
    ticker_str: str,
    source_or_boxsize: Any = 1.0,
    style: str | None = None,
    param: float | int | None = None,
    reversal: int | float | None = None,
    *_extra: Any,
    **kwargs: Any,
) -> TickerInfo:
    """Create a Point and Figure chart ticker from a symbol.

    TradingView forms:

    - ``ticker.pointfigure(symbol, boxsize)`` / ``(..., boxsize, style)``
      (legacy short form)
    - ``ticker.pointfigure(symbol, source, style, param, reversal)``
      e.g. ``ticker.pointfigure(syminfo.tickerid, "hl", "Traditional", 1, 3)``
      or ``(..., "hl", "ATR", 14, 3)``

    Extra positional args are ignored so corpus arity does not TypeError.
    """
    source: str | None = None
    boxsize = 1.0
    style_s: str | None = str(style) if style is not None else None
    rev = _as_int_or_none(reversal)

    # Named kwargs (TV-style) override positionals when present
    if kwargs.get("source") is not None:
        source = str(kwargs["source"])
    if kwargs.get("style") is not None:
        style_s = str(kwargs["style"])
    if kwargs.get("param") is not None:
        boxsize = _as_float_default(kwargs["param"])
    if kwargs.get("boxsize") is not None:
        boxsize = _as_float_default(kwargs["boxsize"])
    if kwargs.get("reversal") is not None:
        rev = _as_int_or_none(kwargs["reversal"])

    arg1 = source_or_boxsize
    is_source = isinstance(arg1, str) and (
        arg1.lower() in _PNF_SOURCES or not _looks_like_number(arg1)
    )
    if is_source:
        # Full form: (symbol, source, style, param, reversal)
        source = str(arg1)
        if style is not None:
            style_s = str(style)
        if param is not None:
            boxsize = _as_float_default(param)
    else:
        # Legacy: (symbol, boxsize[, style])
        boxsize = _as_float_default(arg1, 1.0)
        if style is not None:
            style_s = str(style)
        if param is not None:
            boxsize = _as_float_default(param, boxsize)

    parts = [str(ticker_str), str(boxsize)]
    if source:
        parts.append(source)
    if style_s:
        parts.append(style_s)
    if rev is not None:
        parts.append(str(rev))
    ticker = TickerInfo(f"PF({','.join(parts)})")
    ticker.pointfigure_applied = True
    if style_s:
        ticker.style = style_s
    if source:
        ticker.source = source  # type: ignore[attr-defined]
    if rev is not None:
        ticker.reversal = rev  # type: ignore[attr-defined]
    return ticker


def _looks_like_number(v: Any) -> bool:
    """True when *v* can be parsed as a float (legacy boxsize string)."""
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


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


def ticker_inherit(
    ticker_str: str | TickerInfo | None = None,
    symbol: str | TickerInfo | None = None,
    *_extra: Any,
) -> TickerInfo:
    """Inherit chart properties for a ticker (session/adjust from main chart).

    Pine forms:
    - ``ticker.inherit(symbol)`` — inherit chart session/adjust for *symbol*
    - ``ticker.inherit(from, symbol)`` — inherit from *from* ticker for *symbol*
      (used by TradingView sample scripts such as Performance)
    """
    # Two-arg form: first is source (often chart tickerid), second is target symbol
    if symbol is not None:
        if isinstance(symbol, TickerInfo):
            target = symbol.symbol
        else:
            target = str(symbol) if symbol is not None else ""
        if isinstance(ticker_str, TickerInfo):
            return TickerInfo(
                symbol=target or ticker_str.symbol,
                session=ticker_str.session,
                adjust=ticker_str.adjust,
            )
        return TickerInfo(symbol=target)

    if isinstance(ticker_str, TickerInfo):
        return TickerInfo(
            symbol=ticker_str.symbol,
            session=ticker_str.session,
            adjust=ticker_str.adjust,
        )
    sym = str(ticker_str) if ticker_str is not None else ""
    return TickerInfo(symbol=sym)


def ticker_standard(ticker_str: str) -> TickerInfo:
    """Create a standard OHLC ticker from a symbol.

    Ensures standard candlestick format.

    Args:
        ticker_str: The base ticker symbol

    Returns:
        TickerInfo with standard OHLC format
    """
    return TickerInfo(str(ticker_str))


def tickerid_v4(
    prefix: str | None = None,
    ticker: str | None = None,
    *extra: object,
    **kwargs: object,
) -> str:
    """Pine v3/v4 bare ``tickerid(prefix, ticker)`` constructor.

    Builds an exchange:symbol identifier string. Replaced in v5+ by
    ``ticker.new`` / ``syminfo.tickerid``.

    Forms:
    - ``tickerid(prefix, ticker)`` → ``"PREFIX:TICKER"``
    - ``tickerid(ticker)`` → ``"TICKER"`` (single-arg form)
    """
    if kwargs:
        prefix = kwargs.get("prefix", prefix)  # type: ignore[assignment]
        ticker = kwargs.get("ticker", kwargs.get("symbol", ticker))  # type: ignore[assignment]
    p = str(prefix).strip() if prefix is not None else ""
    t = str(ticker).strip() if ticker is not None else ""
    if p and t:
        return f"{p}:{t}"
    if t:
        return t
    if p and not t:
        # Single-arg call often passes the full ticker as the first parameter.
        return p
    return ""


def split_symbol(symbol: Any) -> tuple[str, str]:
    """Split a ticker id into ``(prefix, ticker)``.

    Pine ``syminfo.prefix(tickerid)`` / ``syminfo.ticker(tickerid)`` parse forms:

    - ``"NASDAQ:AAPL"`` → ``("NASDAQ", "AAPL")``
    - ``"AAPL"`` → ``("", "AAPL")``
    - ``TickerInfo`` → parse its ``.symbol``
    - ``None`` / empty → ``("", "")``
    """
    if symbol is None:
        return "", ""
    if isinstance(symbol, TickerInfo):
        symbol = symbol.symbol
    s = str(symbol).strip()
    if not s:
        return "", ""
    if ":" in s:
        prefix, ticker = s.split(":", 1)
        return prefix, ticker
    return "", s


def extract_prefix(symbol: Any) -> str:
    """Exchange prefix of *symbol* (empty when no ``EXCHANGE:`` part)."""
    return split_symbol(symbol)[0]


def extract_ticker(symbol: Any) -> str:
    """Ticker without exchange prefix (bare symbol or part after ``:``)."""
    return split_symbol(symbol)[1]


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
    # Pine v3/v4 bare aliases
    namespace["tickerid"] = _as_builtin_handler(tickerid_v4)
    namespace["heikinashi"] = _as_builtin_handler(ticker_heikinashi)
    namespace["kagi"] = _as_builtin_handler(ticker_kagi)
    namespace["linebreak"] = _as_builtin_handler(ticker_linebreak)
    namespace["pointfigure"] = _as_builtin_handler(ticker_pointfigure)
    namespace["renko"] = _as_builtin_handler(ticker_renko)
    # Dual-mode free-function fallbacks (no host context). Preferred path is
    # UtilityFunctionsMixin bound handlers which read chart ``syminfo``.
    def _prefix_fn(symbol: Any = None, *a: Any, **k: Any) -> str:
        if symbol is None:
            symbol = k.get("tickerid", k.get("symbol"))
        return extract_prefix(symbol)

    def _ticker_fn(symbol: Any = None, *a: Any, **k: Any) -> str:
        if symbol is None:
            symbol = k.get("tickerid", k.get("symbol"))
        return extract_ticker(symbol)

    if "syminfo.prefix" not in namespace:
        namespace["syminfo.prefix"] = _as_builtin_handler(_prefix_fn)
    if "syminfo.ticker" not in namespace:
        namespace["syminfo.ticker"] = _as_builtin_handler(_ticker_fn)
