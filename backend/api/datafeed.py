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

"""Datafeed gateway blueprint — CCXT REST + optional CCXT Pro watch.

Mirrors the AXIS sidecar contract (`packages/datafeed`):

    GET    /datafeed/ohlcv     — ``fetch_ohlcv(symbol, timeframe, since, limit)``
    GET    /datafeed/markets   — list markets for an exchange
    POST   /datafeed/session   — bind RAM credentials (exchange and/or credentialId)
    DELETE /datafeed/session   — unbind (``exchange=`` or ``cred=ccxt:<exchange>``)
    GET    /datafeed/health    — gateway health + ``ccxt_exchanges``
    WS     /datafeed/watch     — CCXT Pro ``watch_ohlcv`` (registered via flask-sock)

Bars are ``{time, open, high, low, close, volume}`` with ``time`` in unix seconds
from CCXT ``candle[0]`` (ms). AXIS DSM walk-back sends ``since`` in milliseconds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import queue
import threading

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request


logger = logging.getLogger(__name__)

datafeed_bp = Blueprint("datafeed", __name__, url_prefix="/datafeed")

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

_PERIOD_DAYS: dict[str, int] = {
    "1d": 1,
    "1w": 7,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
}

# RAM-only: exchange id and optional AXIS credentialId (``ccxt:<exchange>``)
_sessions: dict[str, dict[str, str]] = {}


def _opt_int(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        n = int(float(raw))
    except (TypeError, ValueError):
        return None
    return n


_CCXT_CANDLE_LEN = 6
_CCXT_MS_EPOCH = 10_000_000_000  # values above this are milliseconds, not seconds


def _candle_to_bar(candle: Any) -> dict[str, float | int] | None:
    """Map a CCXT candle ``[ms, o, h, l, c, v]`` to an AXIS bar (unix seconds)."""
    if not isinstance(candle, (list, tuple)) or len(candle) < _CCXT_CANDLE_LEN:
        return None
    try:
        ts = float(candle[0])
    except (TypeError, ValueError):
        return None
    if math.isnan(ts):
        return None
    # CCXT timestamps are milliseconds; AXIS sidecar does Math.floor(c[0]/1000).
    time_s = int(ts // 1000) if ts > _CCXT_MS_EPOCH else int(ts)
    try:
        return {
            "time": time_s,
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
        }
    except (TypeError, ValueError):
        return None


def _latest_candle(raw: Any) -> Any:
    """CCXT Pro ``watch_ohlcv`` yields a list of candles; REST yields the same."""
    if not raw:
        return None
    if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
        return raw[-1]
    return raw


def _get_env_credentials(exchange: str) -> dict[str, str] | None:
    env_map = _ENV_KEYS.get(exchange.lower())
    if not env_map:
        return None
    creds: dict[str, str] = {}
    for key, env_var in env_map.items():
        val = os.environ.get(env_var, "")
        if val:
            creds[key] = val
    return creds if creds else None


def _get_credentials(exchange: str) -> dict[str, str] | None:
    if exchange in _sessions:
        return _sessions[exchange]
    return _get_env_credentials(exchange)


def _resolve_session(exchange: str, cred: str) -> tuple[str, dict[str, str] | None]:
    """Resolve exchange id + bound keys from ``exchange=`` and/or ``cred=ccxt:<ex>``."""
    exchange = (exchange or "").strip()
    cred = (cred or "").strip()
    if not exchange and cred.startswith("ccxt:"):
        exchange = cred[5:]
    elif not exchange and cred:
        exchange = cred
    creds: dict[str, str] | None = None
    if cred and cred in _sessions:
        creds = _sessions[cred]
    if creds is None and exchange:
        creds = _get_credentials(exchange)
    return exchange, creds


def _make_provider(exchange: str, credentials: dict[str, str] | None = None):
    """Create a CCXTProvider for *exchange* (public if credentials are empty)."""
    try:
        from pynescript.util.data import CCXTProvider  # noqa: PLC0415
    except ImportError:
        return None
    creds = credentials or {}
    return CCXTProvider(
        exchange=exchange,
        api_key=creds.get("api_key", ""),
        secret=creds.get("secret", ""),
        password=creds.get("password", ""),
        uid=creds.get("uid", ""),
    )


def _store_session(exchange: str, creds: dict[str, str], credential_id: str = "") -> None:
    _sessions[exchange] = creds
    if credential_id:
        _sessions[credential_id] = creds


# ---------------------------------------------------------------------------
# GET /datafeed/ohlcv
# ---------------------------------------------------------------------------


@datafeed_bp.route("/ohlcv", methods=["GET"])
def fetch_ohlcv():  # type: ignore[no-untyped-def]
    """Fetch historical OHLCV via CCXT ``fetch_ohlcv``.

    Query params (AXIS ``ccxt-rest``):
        exchange, symbol, timeframe, since (ms), limit, cred
    Legacy: period (1d/1w/1mo/…) derives ``since`` when ``since`` is omitted.
    """
    exchange, credentials = _resolve_session(
        request.args.get("exchange", "").strip(),
        request.args.get("cred", "").strip(),
    )
    symbol = request.args.get("symbol", "").strip()
    timeframe = request.args.get("timeframe", "1h").strip() or "1h"

    if not exchange or not symbol:
        return jsonify({"error": "exchange and symbol are required"}), 400

    since = _opt_int(request.args.get("since"))
    limit = _opt_int(request.args.get("limit"))
    if limit is not None and limit <= 0:
        limit = None
    period = request.args.get("period", "").strip()
    if since is None and period:
        days = _PERIOD_DAYS.get(period, 365)
        since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    if since is None and limit is None:
        limit = 500

    provider = _make_provider(exchange, credentials)
    if provider is None:
        return (
            jsonify({"error": "CCXT not installed. Install with: pip install 'pynescript[datafeed]'"}),
            503,
        )

    try:
        raw = provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
    except Exception as exc:
        logger.warning("datafeed ohlcv: %s", exc)
        if "not installed" in str(exc).lower():
            return jsonify({"error": "Data provider not installed"}), 503
        return jsonify({"error": "Failed to fetch OHLCV data"}), 502

    bars = []
    for candle in raw or []:
        bar = _candle_to_bar(candle)
        if bar is not None:
            bars.append(bar)
    return jsonify(bars)


# ---------------------------------------------------------------------------
# GET /datafeed/markets
# ---------------------------------------------------------------------------


@datafeed_bp.route("/markets", methods=["GET"])
def fetch_markets():  # type: ignore[no-untyped-def]
    """List available markets for an exchange."""
    exchange, credentials = _resolve_session(
        request.args.get("exchange", "").strip(),
        request.args.get("cred", "").strip(),
    )
    if not exchange:
        return jsonify({"error": "exchange is required"}), 400

    provider = _make_provider(exchange, credentials)
    if provider is None:
        return jsonify({"error": "CCXT not installed"}), 503

    try:
        ex = provider._get_exchange()
        markets = ex.fetch_markets()
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
        logger.warning("datafeed markets: %s", exc)
        return jsonify({"error": "Failed to fetch market data"}), 502


# ---------------------------------------------------------------------------
# POST /datafeed/session — bind credentials
# ---------------------------------------------------------------------------


@datafeed_bp.route("/session", methods=["POST"])
def bind_session():  # type: ignore[no-untyped-def]
    """Bind RAM credentials.

    AXIS body: ``{exchange, credentialId, apiKey, secret, password?, uid?}``.
    Operator fallback: ``{exchange}`` binds env vars.
    """
    body = request.get_json(silent=True) or {}
    exchange = str(body.get("exchange", "")).strip()
    if not exchange:
        return jsonify({"error": "exchange is required"}), 400

    credential_id = str(body.get("credentialId") or body.get("credential_id") or "").strip()
    api_key = str(body.get("apiKey") or body.get("api_key") or "").strip()
    secret = str(body.get("secret") or "").strip()
    password = str(body.get("password") or body.get("passphrase") or "").strip()
    uid = str(body.get("uid") or "").strip()
    if api_key and secret:
        creds: dict[str, str] = {"api_key": api_key, "secret": secret}
        if password:
            creds["password"] = password
        if uid:
            creds["uid"] = uid
        _store_session(exchange, creds, credential_id)
        return "", 204

    credentials = _get_credentials(exchange) or _get_env_credentials(exchange)
    if not credentials:
        return (
            jsonify({"error": (f"No credentials found for {exchange}. POST apiKey+secret or set env vars.")}),
            404,
        )

    _store_session(exchange, credentials, credential_id)
    return "", 204


# ---------------------------------------------------------------------------
# DELETE /datafeed/session — unbind credentials
# ---------------------------------------------------------------------------


@datafeed_bp.route("/session", methods=["DELETE"])
def unbind_session():  # type: ignore[no-untyped-def]
    """Remove bound credentials (``exchange=`` and/or AXIS ``cred=ccxt:<ex>``)."""
    exchange = request.args.get("exchange", "").strip()
    cred = request.args.get("cred", "").strip()
    if not exchange and cred.startswith("ccxt:"):
        exchange = cred[5:]
    if not exchange and not cred:
        return jsonify({"error": "exchange is required"}), 400

    if cred:
        _sessions.pop(cred, None)
    if exchange:
        _sessions.pop(exchange, None)
        _sessions.pop(f"ccxt:{exchange}", None)
    return "", 204


# ---------------------------------------------------------------------------
# GET /datafeed/health
# ---------------------------------------------------------------------------


@datafeed_bp.route("/health", methods=["GET"])
def gateway_health():  # type: ignore[no-untyped-def]
    """Gateway health check + available exchanges."""
    try:
        import ccxt  # noqa: F401,PLC0415

        has_ccxt = True
    except ImportError:
        has_ccxt = False

    exchanges = list(_ENV_KEYS.keys())
    payload: dict[str, Any] = {
        "status": "ok",
        "ccxt": has_ccxt,
        "exchanges": exchanges,
        "active_sessions": sorted({k for k in _sessions if not k.startswith("ccxt:")}),
    }
    if has_ccxt:
        try:
            import ccxt as _ccxt  # noqa: PLC0415

            payload["ccxt_exchanges"] = sorted(_ccxt.exchanges)
        except Exception:  # pragma: no cover  # noqa: S110
            pass
    return jsonify(payload)


def _watch_put(out_q: queue.Queue[Any], bar: dict[str, float | int]) -> None:
    try:
        out_q.put_nowait(bar)
    except queue.Full:
        try:
            out_q.get_nowait()
        except queue.Empty:
            pass
        try:
            out_q.put_nowait(bar)
        except queue.Full:
            pass


_WATCH_POLL_SEC = 1.0


def watch_rest_poll(
    provider: Any,
    symbol: str,
    timeframe: str,
    out_q: queue.Queue[Any],
    stop: threading.Event,
) -> None:
    """Emit latest REST candle while *stop* is clear (geo-block / Pro WS fallback)."""
    last: dict[str, float | int] | None = None
    while not stop.is_set():
        try:
            raw = provider.fetch_ohlcv(symbol, timeframe, since=None, limit=2)
            bar = _candle_to_bar(_latest_candle(raw))
            if bar is not None and bar != last:
                last = bar
                _watch_put(out_q, bar)
        except Exception as exc:
            logger.warning("datafeed watch poll error: %s", exc)
        stop.wait(_WATCH_POLL_SEC)


def run_watch_producer(  # noqa: PLR0913
    exchange: str,
    creds: dict[str, str],
    symbol: str,
    timeframe: str,
    out_q: queue.Queue[Any],
    stop: threading.Event,
) -> None:
    """CCXT Pro watch, then REST poll if the venue/WS is unreachable."""
    try:
        from pynescript.util.datafeed import CCXTProDataFeed  # noqa: PLC0415

        opts: dict[str, Any] = {}
        if creds.get("uid"):
            opts["uid"] = creds["uid"]

        async def _pro() -> None:
            feed = CCXTProDataFeed(
                exchange=exchange,
                api_key=creds.get("api_key", ""),
                secret=creds.get("secret", ""),
                password=creds.get("password", ""),
                **opts,
            )
            async with feed:
                agen = feed.watch_ohlcv(symbol, timeframe)
                while not stop.is_set():
                    raw = await asyncio.wait_for(agen.__anext__(), timeout=20.0)
                    bar = _candle_to_bar(_latest_candle(raw))
                    if bar is not None:
                        _watch_put(out_q, bar)

        asyncio.run(_pro())
    except Exception as exc:
        if stop.is_set():
            return
        logger.warning("datafeed watch pro failed, polling REST: %s", exc)
        provider = _make_provider(exchange, creds)
        if provider is None:
            return
        watch_rest_poll(provider, symbol, timeframe, out_q, stop)


def register_watch_route(sock: Any) -> None:
    """Register ``WS /datafeed/watch`` (CCXT Pro, REST poll fallback)."""

    @sock.route("/datafeed/watch")
    def datafeed_watch(ws):  # type: ignore[no-untyped-def]
        exchange, credentials = _resolve_session(
            request.args.get("exchange", "").strip(),
            request.args.get("cred", "").strip(),
        )
        symbol = request.args.get("symbol", "").strip()
        timeframe = request.args.get("timeframe", "1m").strip() or "1m"
        if not exchange or not symbol:
            try:
                ws.close()
            except Exception:  # noqa: S110
                pass
            return

        stop = threading.Event()
        out_q: queue.Queue[Any] = queue.Queue(maxsize=8)
        worker = threading.Thread(
            target=run_watch_producer,
            args=(exchange, credentials or {}, symbol, timeframe, out_q, stop),
            name="datafeed-watch",
            daemon=True,
        )
        worker.start()
        try:
            while worker.is_alive() or not out_q.empty():
                try:
                    bar = out_q.get(timeout=1.0)
                except queue.Empty:
                    continue
                ws.send(json.dumps(bar))
        except Exception as exc:
            logger.warning("datafeed watch send error: %s", exc)
        finally:
            stop.set()
