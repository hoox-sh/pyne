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

Credential binding (``POST/DELETE /datafeed/session``) requires an API key and
is scoped to that key's owner. Public OHLCV/markets reads may use operator env
credentials anonymously, but never another caller's bound session.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import math
import os
import queue
import threading
import time

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from flask import Blueprint
from flask import g
from flask import jsonify
from flask import request

from backend.middleware.auth import optional_api_key
from backend.middleware.auth import require_api_key
from pynescript import stats as _stats
from pynescript.debug import scope_enabled as _debug_scope


logger = logging.getLogger(__name__)


def _dbg(msg: str, *args: Any) -> None:
    """Emit one datafeed-gateway debug line when ``PYNE_DEBUG`` is enabled."""
    if _debug_scope(__name__):
        logger.debug(msg, *args)


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

# RAM-only: (owner key_id, exchange id or AXIS credentialId) -> credentials.
# Owner scoping prevents one caller's bound exchange keys from being used by
# another caller; anonymous public reads still fall back to env credentials.
_sessions: dict[tuple[str, str], dict[str, str]] = {}


def _session_owner() -> str:
    """Key-store id of the authenticated caller, or ``anonymous``."""
    api_key = getattr(g, "api_key", None)
    return str(getattr(api_key, "key_id", "") or "anonymous")


def _bound_exchange_names() -> set[str]:
    """Exchange names with at least one bound session (never secrets)."""
    return {exchange for (_owner, exchange) in _sessions if not exchange.startswith("ccxt:")}


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


def _get_credentials(owner: str, exchange: str) -> dict[str, str] | None:
    bound = _sessions.get((owner, exchange))
    if bound is not None:
        return bound
    return _get_env_credentials(exchange)


def _resolve_session(owner: str, exchange: str, cred: str) -> tuple[str, dict[str, str] | None]:
    """Resolve exchange id + bound keys from ``exchange=`` and/or ``cred=ccxt:<ex>``."""
    exchange = (exchange or "").strip()
    cred = (cred or "").strip()
    if not exchange and cred.startswith("ccxt:"):
        exchange = cred[5:]
    elif not exchange and cred:
        exchange = cred
    creds: dict[str, str] | None = None
    if cred:
        creds = _sessions.get((owner, cred))
    if creds is None and exchange:
        creds = _get_credentials(owner, exchange)
    return exchange, creds


def _make_provider(
    exchange: str,
    credentials: dict[str, str] | None = None,
    market: str = "spot",
):
    """Create a CCXTProvider for *exchange* (public if credentials are empty)."""
    try:
        from pynescript.util.data import CCXTProvider
    except ImportError:
        return None
    creds = credentials or {}
    default_type = market if market in ("spot", "swap", "future") else "spot"
    return CCXTProvider(
        exchange=exchange,
        api_key=creds.get("api_key", ""),
        secret=creds.get("secret", ""),
        password=creds.get("password", ""),
        uid=creds.get("uid", ""),
        default_type=default_type,
    )


def _store_session(owner: str, exchange: str, creds: dict[str, str], credential_id: str = "") -> None:
    _sessions[(owner, exchange)] = creds
    if credential_id:
        _sessions[(owner, credential_id)] = creds


# ---------------------------------------------------------------------------
# GET /datafeed/ohlcv
# ---------------------------------------------------------------------------


@datafeed_bp.route("/ohlcv", methods=["GET"])
@optional_api_key
def fetch_ohlcv():  # type: ignore[no-untyped-def]
    """Fetch historical OHLCV via CCXT ``fetch_ohlcv``.

    Query params (AXIS ``ccxt-rest``):
        exchange, symbol, timeframe, since (ms), limit, cred
    Legacy: period (1d/1w/1mo/…) derives ``since`` when ``since`` is omitted.
    Authenticated callers may use their own bound credentials; anonymous
    callers fall back to operator env credentials only.
    """
    exchange, credentials = _resolve_session(
        _session_owner(),
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
        _dbg("GET /datafeed/ohlcv 503 ccxt missing exchange=%s symbol=%s", exchange, symbol)
        _stats.count("datafeed.gateway", dim="ohlcv_unavailable")
        return (
            jsonify({"error": "CCXT not installed. Install with: pip install 'pynescript[datafeed]'"}),
            503,
        )

    _dbg(
        "GET /datafeed/ohlcv exchange=%s symbol=%s timeframe=%s since=%s limit=%s period=%s auth=%s",
        exchange,
        symbol,
        timeframe,
        since,
        limit,
        period or None,
        bool(credentials),
    )
    _stats.count("datafeed.gateway", dim="ohlcv")
    _t_fetch0 = time.perf_counter()
    try:
        raw = provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since, limit=limit)
    except Exception as exc:
        logger.warning("datafeed ohlcv: %s", exc)
        _dbg(
            "GET /datafeed/ohlcv FAILED exchange=%s symbol=%s in %.1fms: %s",
            exchange,
            symbol,
            (time.perf_counter() - _t_fetch0) * 1000.0,
            exc,
        )
        _stats.count("datafeed.gateway_errors", dim="ohlcv")
        _stats.latency("datafeed.gateway_ohlcv", time.perf_counter() - _t_fetch0)
        if "not installed" in str(exc).lower():
            return jsonify({"error": "Data provider not installed"}), 503
        return jsonify({"error": "Failed to fetch OHLCV data"}), 502

    bars = []
    dropped = 0
    for candle in raw or []:
        bar = _candle_to_bar(candle)
        if bar is not None:
            bars.append(bar)
        else:
            dropped += 1
    _dbg(
        "GET /datafeed/ohlcv -> %d bars (dropped %d) exchange=%s symbol=%s in %.1fms",
        len(bars),
        dropped,
        exchange,
        symbol,
        (time.perf_counter() - _t_fetch0) * 1000.0,
    )
    _stats.count("datafeed.gateway_bars", len(bars))
    _stats.count("datafeed.gateway_dropped_candles", dropped)
    _stats.latency("datafeed.gateway_ohlcv", time.perf_counter() - _t_fetch0)
    return jsonify(bars)


# ---------------------------------------------------------------------------
# GET /datafeed/markets
# ---------------------------------------------------------------------------


@datafeed_bp.route("/markets", methods=["GET"])
@optional_api_key
def fetch_markets():  # type: ignore[no-untyped-def]
    """List available markets for an exchange."""
    exchange, credentials = _resolve_session(
        _session_owner(),
        request.args.get("exchange", "").strip(),
        request.args.get("cred", "").strip(),
    )
    if not exchange:
        return jsonify({"error": "exchange is required"}), 400

    provider = _make_provider(exchange, credentials)
    if provider is None:
        _dbg("GET /datafeed/markets 503 ccxt missing exchange=%s", exchange)
        _stats.count("datafeed.gateway", dim="markets_unavailable")
        return jsonify({"error": "CCXT not installed"}), 503

    _dbg("GET /datafeed/markets exchange=%s auth=%s", exchange, bool(credentials))
    _stats.count("datafeed.gateway", dim="markets")
    _t_mkt0 = time.perf_counter()
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
        _dbg(
            "GET /datafeed/markets -> %d markets exchange=%s in %.1fms",
            len(simplified),
            exchange,
            (time.perf_counter() - _t_mkt0) * 1000.0,
        )
        _stats.count("datafeed.gateway_markets", len(simplified))
        _stats.latency("datafeed.gateway_markets", time.perf_counter() - _t_mkt0)
        return jsonify(simplified)
    except Exception as exc:
        logger.warning("datafeed markets: %s", exc)
        _dbg("GET /datafeed/markets FAILED exchange=%s: %s", exchange, exc)
        _stats.count("datafeed.gateway_errors", dim="markets")
        _stats.latency("datafeed.gateway_markets", time.perf_counter() - _t_mkt0)
        return jsonify({"error": "Failed to fetch market data"}), 502


# ---------------------------------------------------------------------------
# POST /datafeed/session — bind credentials
# ---------------------------------------------------------------------------


@datafeed_bp.route("/session", methods=["POST"])
@require_api_key
def bind_session():  # type: ignore[no-untyped-def]
    """Bind RAM credentials for the authenticated caller.

    AXIS body: ``{exchange, credentialId, apiKey, secret, password?, uid?}``.
    Operator fallback: ``{exchange}`` binds env vars. Credentials are scoped to
    the API-key owner; anonymous callers cannot bind or consume them.
    """
    owner = _session_owner()
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
        _store_session(owner, exchange, creds, credential_id)
        # Never log key material — only whether each field was supplied.
        _dbg(
            "POST /datafeed/session bound exchange=%s credential_id=%s inline has_password=%s has_uid=%s",
            exchange,
            credential_id or None,
            bool(password),
            bool(uid),
        )
        _stats.count("datafeed.session_binds", dim="inline")
        _stats.set_gauge("datafeed.bound_sessions", len(_bound_exchange_names()))
        return "", 204

    credentials = _get_credentials(owner, exchange) or _get_env_credentials(exchange)
    if not credentials:
        _dbg("POST /datafeed/session 404 exchange=%s (no inline creds, no env vars)", exchange)
        _stats.count("datafeed.session_binds", dim="not_found")
        return (
            jsonify({"error": (f"No credentials found for {exchange}. POST apiKey+secret or set env vars.")}),
            404,
        )

    _store_session(owner, exchange, credentials, credential_id)
    _dbg(
        "POST /datafeed/session bound exchange=%s credential_id=%s source=env",
        exchange,
        credential_id or None,
    )
    _stats.count("datafeed.session_binds", dim="env")
    _stats.set_gauge("datafeed.bound_sessions", len(_bound_exchange_names()))
    return "", 204


# ---------------------------------------------------------------------------
# DELETE /datafeed/session — unbind credentials
# ---------------------------------------------------------------------------


@datafeed_bp.route("/session", methods=["DELETE"])
@require_api_key
def unbind_session():  # type: ignore[no-untyped-def]
    """Remove this caller's bound credentials."""
    owner = _session_owner()
    exchange = request.args.get("exchange", "").strip()
    cred = request.args.get("cred", "").strip()
    if not exchange and cred.startswith("ccxt:"):
        exchange = cred[5:]
    if not exchange and not cred:
        return jsonify({"error": "exchange is required"}), 400

    if cred:
        _sessions.pop((owner, cred), None)
    if exchange:
        _sessions.pop((owner, exchange), None)
        _sessions.pop((owner, f"ccxt:{exchange}"), None)
    _dbg("DELETE /datafeed/session unbound exchange=%s cred=%s", exchange or None, cred or None)
    _stats.count("datafeed.session_unbinds")
    _stats.set_gauge("datafeed.bound_sessions", len(_bound_exchange_names()))
    return "", 204


# ---------------------------------------------------------------------------
# GET /datafeed/health
# ---------------------------------------------------------------------------


@datafeed_bp.route("/health", methods=["GET"])
def gateway_health():  # type: ignore[no-untyped-def]
    """Gateway health check + available exchanges."""
    has_ccxt = importlib.util.find_spec("ccxt") is not None

    exchanges = list(_ENV_KEYS.keys())
    payload: dict[str, Any] = {
        "status": "ok",
        "ccxt": has_ccxt,
        "exchanges": exchanges,
        "active_sessions": sorted(_bound_exchange_names()),
    }
    if has_ccxt:
        try:
            import ccxt as _ccxt

            payload["ccxt_exchanges"] = sorted(_ccxt.exchanges)
        except Exception:  # pragma: no cover
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
            _dbg("watch REST poll error %s %s %s: %s", getattr(provider, "_exchange_name", "?"), symbol, timeframe, exc)
            _stats.count("datafeed.watch_poll_errors", dim="rest")
        stop.wait(_WATCH_POLL_SEC)


def run_watch_producer(
    exchange: str,
    creds: dict[str, str],
    symbol: str,
    timeframe: str,
    out_q: queue.Queue[Any],
    stop: threading.Event,
) -> None:
    """CCXT Pro watch, then REST poll if the venue/WS is unreachable."""
    _dbg("watch producer start exchange=%s symbol=%s timeframe=%s auth=%s", exchange, symbol, timeframe, bool(creds))
    _stats.count("datafeed.watch_producers", dim=exchange)
    try:
        from pynescript.util.datafeed import CCXTProDataFeed

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
        _dbg("watch producer CCXT Pro failed, falling back to REST poll: %s", exc)
        _stats.count("datafeed.watch_fallbacks", dim="rest_poll")
        provider = _make_provider(exchange, creds)
        if provider is None:
            return
        watch_rest_poll(provider, symbol, timeframe, out_q, stop)


def register_watch_route(sock: Any) -> None:
    """Register ``WS /datafeed/watch`` (CCXT Pro, REST poll fallback)."""

    @sock.route("/datafeed/watch")
    def datafeed_watch(ws):  # type: ignore[no-untyped-def]
        exchange, credentials = _resolve_session(
            _session_owner(),
            request.args.get("exchange", "").strip(),
            request.args.get("cred", "").strip(),
        )
        symbol = request.args.get("symbol", "").strip()
        timeframe = request.args.get("timeframe", "1m").strip() or "1m"
        if not exchange or not symbol:
            try:
                ws.close()
            except Exception:
                pass
            return

        stop = threading.Event()
        out_q: queue.Queue[Any] = queue.Queue(maxsize=8)
        _dbg(
            "WS /datafeed/watch open exchange=%s symbol=%s timeframe=%s auth=%s",
            exchange,
            symbol,
            timeframe,
            bool(credentials),
        )
        _stats.inc_gauge("datafeed.watch_connections")
        _stats.count("datafeed.watch_connections")
        worker = threading.Thread(
            target=run_watch_producer,
            args=(exchange, credentials or {}, symbol, timeframe, out_q, stop),
            name="datafeed-watch",
            daemon=True,
        )
        worker.start()
        n_sent = 0
        try:
            while worker.is_alive() or not out_q.empty():
                try:
                    bar = out_q.get(timeout=1.0)
                except queue.Empty:
                    continue
                ws.send(json.dumps(bar))
                n_sent += 1
                if n_sent <= 3 or n_sent % 100 == 0:
                    _dbg("WS /datafeed/watch sent bar #%d %s", n_sent, bar)
        except Exception as exc:
            logger.warning("datafeed watch send error: %s", exc)
            _dbg("WS /datafeed/watch send error after %d bar(s): %s", n_sent, exc)
            _stats.count("datafeed.watch_errors")
        finally:
            stop.set()
            _dbg("WS /datafeed/watch closed exchange=%s symbol=%s bars_sent=%d", exchange, symbol, n_sent)
            _stats.dec_gauge("datafeed.watch_connections")
            _stats.count("datafeed.watch_bars", n_sent)
