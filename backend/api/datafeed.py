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

"""Datafeed gateway blueprint — HTTP wrapper around CCXTProvider.

Endpoints:
    GET  /datafeed/ohlcv    — fetch historical OHLCV via CCXTProvider
    GET  /datafeed/markets  — list markets for an exchange
    POST /datafeed/session  — bind server-side credentials for an exchange
    DELETE /datafeed/session — unbind credentials
    GET  /datafeed/health   — gateway health + available exchanges
"""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request

logger = logging.getLogger(__name__)

datafeed_bp = Blueprint("datafeed", __name__, url_prefix="/datafeed")

# ---------------------------------------------------------------------------
# Credential store (server-side, env-based for v1)
# ---------------------------------------------------------------------------

_ENV_KEYS: dict[str, dict[str, str]] = {
    "binance": {"api_key": "BINANCE_API_KEY", "secret": "BINANCE_SECRET"},
    "okx": {
        "api_key": "OKX_API_KEY",
        "secret": "OKX_SECRET",
        "password": "OKX_PASSPHRASE",
    },
    "bybit": {"api_key": "BYBIT_API_KEY", "secret": "BYBIT_SECRET"},
    "coinbase": {
        "api_key": "COINBASE_API_KEY",
        "secret": "COINBASE_SECRET",
        "password": "COINBASE_PASSPHRASE",
    },
    "kraken": {"api_key": "KRAKEN_API_KEY", "secret": "KRAKEN_SECRET"},
}

# Active sessions: exchange -> credential dict (RAM-only)
_sessions: dict[str, dict[str, str]] = {}


def _get_credentials(exchange: str) -> dict[str, str] | None:
    """Return credentials for an exchange from active session or env vars."""
    if exchange in _sessions:
        return _sessions[exchange]
    env_map = _ENV_KEYS.get(exchange.lower())
    if not env_map:
        return None
    creds: dict[str, str] = {}
    for key, env_var in env_map.items():
        val = os.environ.get(env_var, "")
        if val:
            creds[key] = val
    return creds if creds else None


def _make_provider(exchange: str, credentials: dict[str, str] | None = None):
    """Create a CCXTProvider instance for the given exchange."""
    try:
        from pynescript.util.data import CCXTProvider
    except ImportError:
        return None
    api_key = credentials.get("api_key", "") if credentials else ""
    secret = credentials.get("secret", "") if credentials else ""
    return CCXTProvider(exchange=exchange, api_key=api_key, secret=secret)


# ---------------------------------------------------------------------------
# GET /datafeed/ohlcv
# ---------------------------------------------------------------------------


@datafeed_bp.route("/ohlcv", methods=["GET"])
def fetch_ohlcv():  # type: ignore[no-untyped-def]
    """Fetch historical OHLCV candles via CCXTProvider.

    Query params:
        exchange  — exchange id (binance, okx, bybit, coinbase, kraken)
        symbol    — unified symbol (BTC/USDT)
        timeframe — candle interval (1m, 5m, 1h, 1d)
        period    — time period (1d, 1w, 1mo, 3mo, 6mo, 1y, 2y)
        limit     — max bars to return (sliced from provider result)
    """
    exchange = request.args.get("exchange", "").strip()
    symbol = request.args.get("symbol", "").strip()
    timeframe = request.args.get("timeframe", "1h").strip()
    period = request.args.get("period", "1y").strip()
    limit = request.args.get("limit", 500, type=int)

    if not exchange or not symbol:
        return jsonify({"error": "exchange and symbol are required"}), 400

    credentials = _get_credentials(exchange)
    provider = _make_provider(exchange, credentials)
    if provider is None:
        return (
            jsonify({"error": "CCXT not installed. Install with: pip install 'pynescript[datafeed]'"}),
            503,
        )

    try:
        result = provider.fetch(symbol=symbol, period=period, interval=timeframe)
    except Exception as exc:
        logger.warning("datafeed ohlcv error: %s", exc)
        return jsonify({"error": str(exc)}), 502

    # CCXTProvider returns {symbol, open[], high[], low[], close[], volume[]}
    # Convert to AXIS Bar format: {time, open, high, low, close, volume}
    opens = result.get("open", [])
    highs = result.get("high", [])
    lows = result.get("low", [])
    closes = result.get("close", [])
    volumes = result.get("volume", [])
    n = min(len(opens), len(highs), len(lows), len(closes), len(volumes))

    # CCXTProvider doesn't expose timestamps directly; synthesize from index
    # The provider fetches from `since` (now - period) at the given interval
    from datetime import datetime, timedelta, timezone

    interval_map = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
    step = interval_map.get(timeframe, 3600)

    period_days_map = {"1d": 1, "1w": 7, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    days = period_days_map.get(period, 365)
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

    bars = []
    for i in range(n):
        bars.append(
            {
                "time": start_ts + i * step,
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "volume": float(volumes[i]),
            }
        )

    if limit and len(bars) > limit:
        bars = bars[-limit:]

    return jsonify(bars)


# ---------------------------------------------------------------------------
# GET /datafeed/markets
# ---------------------------------------------------------------------------


@datafeed_bp.route("/markets", methods=["GET"])
def fetch_markets():  # type: ignore[no-untyped-def]
    """List available markets for an exchange.

    Query params:
        exchange — exchange id
    """
    exchange = request.args.get("exchange", "").strip()
    if not exchange:
        return jsonify({"error": "exchange is required"}), 400

    credentials = _get_credentials(exchange)
    provider = _make_provider(exchange, credentials)
    if provider is None:
        return jsonify({"error": "CCXT not installed"}), 503

    try:
        ex = provider._get_exchange()
        markets = ex.fetch_markets()
        # Simplify to essential fields
        simplified = []
        for m in markets:
            simplified.append(
                {
                    "symbol": m.get("symbol", ""),
                    "base": m.get("base", ""),
                    "quote": m.get("quote", ""),
                    "active": m.get("active", True),
                }
            )
        return jsonify(simplified)
    except Exception as exc:
        logger.warning("datafeed markets error: %s", exc)
        return jsonify({"error": str(exc)}), 502


# ---------------------------------------------------------------------------
# POST /datafeed/session — bind credentials
# ---------------------------------------------------------------------------


@datafeed_bp.route("/session", methods=["POST"])
def bind_session():  # type: ignore[no-untyped-def]
    """Bind server-side credentials for an exchange.

    Body (JSON):
        { "exchange": "binance" }
    """
    body = request.get_json(silent=True) or {}
    exchange = body.get("exchange", "").strip()
    if not exchange:
        return jsonify({"error": "exchange is required"}), 400

    credentials = _get_credentials(exchange)
    if not credentials:
        return (
            jsonify({"error": f"No credentials found for {exchange}. Set env vars or use /datafeed/session."}),
            404,
        )

    _sessions[exchange] = credentials
    return "", 204


# ---------------------------------------------------------------------------
# DELETE /datafeed/session — unbind credentials
# ---------------------------------------------------------------------------


@datafeed_bp.route("/session", methods=["DELETE"])
def unbind_session():  # type: ignore[no-untyped-def]
    """Remove bound credentials for an exchange.

    Query params:
        exchange — exchange id
    """
    exchange = request.args.get("exchange", "").strip()
    if not exchange:
        return jsonify({"error": "exchange is required"}), 400

    _sessions.pop(exchange, None)
    return "", 204


# ---------------------------------------------------------------------------
# GET /datafeed/health
# ---------------------------------------------------------------------------


@datafeed_bp.route("/health", methods=["GET"])
def gateway_health():  # type: ignore[no-untyped-def]
    """Gateway health check + available exchanges."""
    try:
        import ccxt  # noqa: F401

        has_ccxt = True
    except ImportError:
        has_ccxt = False

    exchanges = list(_ENV_KEYS.keys())
    return jsonify(
        {
            "status": "ok",
            "ccxt": has_ccxt,
            "exchanges": exchanges,
            "active_sessions": list(_sessions.keys()),
        }
    )
