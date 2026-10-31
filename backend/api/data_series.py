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

"""Engine-owned OHLCV routes (``/data/series*``) and CCXT paging.

AXIS sends market identity only. PYNE Pro persists the bars (see
:mod:`backend.datastore.series`) and fetches them through the same CCXT
provider the datafeed gateway uses. ``/data/session*`` routes are registered in
``backend/app.py`` next to ``/session`` because they share its helpers.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import threading
import time

from collections.abc import Callable
from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request

from backend.api import datafeed
from backend.datastore import live
from backend.datastore import series as series_store
from backend.datastore.series import DataError
from backend.datastore.series import SeriesKey
from backend.middleware.auth import require_api_key
from backend.middleware.schemas import DATA_SERIES_FETCH_SCHEMA
from backend.middleware.schemas import DATA_SERIES_PROVIDE_SCHEMA
from backend.middleware.schemas import validate


logger = logging.getLogger(__name__)

bp = Blueprint("data_series", __name__, url_prefix="/data")

# CCXT page size and a hard stop on pages per request (bounds a runaway walk).
FETCH_PAGE_LIMIT = 1000
MAX_FETCH_PAGES = 200
# A tick re-reads this many bars before the stored newest so a corrected or
# still-forming bar is picked up.
TICK_OVERLAP_BARS = 2
# A tick only ever needs to catch up a few bars. When the stored anchor is
# staler than this window the walk is CLAMPED to the most recent TICK_MAX_BARS
# bars instead of paging through the whole gap — a stale anchor used to run the
# full 200-page budget (~200k sequential CCXT round trips), pin the request for
# minutes and serialize every other request on the same series behind key_lock.
TICK_MAX_BARS = 2500
SOURCE_FETCH = "ccxt-fetch"
SOURCE_TICK = "ccxt-tick"
SOURCE_GAP = "ccxt-gap"
# A weekend on a session venue, or an upstream that has no candles for the
# hole, must not refetch the same gap on every tick.
_GAP_GIVE_UP = 3
_gap_failures: dict[str, tuple[int, int]] = {}

# Short-lived reuse of the upstream tick walk, per series. AXIS ticks one
# session per script instance (chart + N indicators) against the same series
# within seconds of each other; without reuse each tick pays its own CCXT walk
# for identical candles — and on the single gunicorn worker those walks also
# serialize behind each other. Two mechanisms, both covering-only and safe:
#
# - cross-session time reuse: a fresh walk fetched for another session is
#   reused when it covers the requested window. The *same* session always
#   refetches, so forming-bar re-ticks observe every revision. A reused walk
#   may lag the newest seconds by the reuse window; the next cycle refreshes.
# - singleflight: concurrent ticks for one series share the in-flight walk
#   instead of stacking identical CCXT round trips.
#
# Truncated walks (hit ``max_bars``) never reach the newest bar, so they are
# neither cached nor shared. History-affecting routes (``/series/fetch``)
# never use this.
#
# 12s (not per-tick fresh): AXIS ticks chart + indicator sessions staggered a
# few seconds apart against the same series. A reused walk may lag the newest
# seconds; the next cycle refreshes. Same-session refetch still always walks,
# so forming-bar revisions are observed at least every other cycle.
TICK_WALK_REUSE_S = 12.0
_WALK_CACHE_MAX = 512


@dataclasses.dataclass
class _CachedWalk:
    fetched_at: float
    since_ms: int
    candles: list[dict[str, float | int]]
    owner_id: int | None


@dataclasses.dataclass
class _Flight:
    since_ms: int
    event: threading.Event
    candles: list[dict[str, float | int]] | None = None
    complete: bool = False


_walk_cache: dict[str, _CachedWalk] = {}
_flights: dict[str, _Flight] = {}
_walk_lock = threading.Lock()


def _filter_walk(candles: list[dict[str, float | int]], since_ms: int) -> list[dict[str, float | int]]:
    return [c for c in candles if int(c["time"]) * 1000 >= since_ms]


def _cached_walk(  # provider, key, window, budget + owner
    provider: Any,
    key: SeriesKey,
    *,
    since_ms: int,
    now_ms: int,
    max_bars: int | None,
    owner_id: int | None = None,
) -> list[dict[str, float | int]]:
    """Walk the upstream, sharing fresh walks for the same series when covering.

    Extra older candles in a shared walk are harmless: ``sync_session`` filters
    by each session's own tail.
    """
    now_mono = time.monotonic()
    with _walk_lock:
        hit = _walk_cache.get(key.text)
        if (
            hit is not None
            and now_mono - hit.fetched_at < TICK_WALK_REUSE_S
            and hit.since_ms <= since_ms
            and hit.owner_id != owner_id
        ):
            return _filter_walk(hit.candles, since_ms)
        flight = _flights.get(key.text)
        if flight is not None and flight.since_ms <= since_ms:
            waiter = True
        else:
            flight = _Flight(since_ms=since_ms, event=threading.Event())
            _flights[key.text] = flight
            waiter = False
    if waiter and flight is not None:
        if flight.event.wait(timeout=60.0) and flight.candles is not None and flight.complete:
            return _filter_walk(flight.candles, since_ms)
        # Timed out, or the owner failed / truncated: pay our own walk rather
        # than fail because a sibling tick did. (Unregistered: never nest.)
        return _collect_or_raise(provider, key, since_ms=since_ms, now_ms=now_ms, max_bars=max_bars)
    try:
        candles = _collect_or_raise(provider, key, since_ms=since_ms, now_ms=now_ms, max_bars=max_bars)
    except Exception:
        with _walk_lock:
            flight.event.set()
            if _flights.get(key.text) is flight:
                del _flights[key.text]
        raise
    complete = max_bars is None or len(candles) < max_bars
    with _walk_lock:
        if complete:
            if len(_walk_cache) >= _WALK_CACHE_MAX:
                oldest = min(_walk_cache, key=lambda k: _walk_cache[k].fetched_at)
                del _walk_cache[oldest]
            _walk_cache[key.text] = _CachedWalk(now_mono, since_ms, candles, owner_id)
        flight.candles = candles
        flight.complete = complete
        flight.event.set()
        if _flights.get(key.text) is flight:
            del _flights[key.text]
    return candles


# Test helper — clear the tick walk cache and in-flight registry between cases.
def _reset_walk_cache_for_tests() -> None:
    with _walk_lock:
        _walk_cache.clear()
        _flights.clear()
    with _provider_guard:
        _providers.clear()
        _provider_at.clear()
        _fetch_locks.clear()
    _gap_failures.clear()


def data_error_response(exc: DataError) -> tuple[Any, int]:
    return jsonify(exc.body()), exc.status


def provider_for(exchange: str, market: str = "spot") -> Any | None:
    """Cached CCXT provider for *exchange* + market type, or ``None`` when CCXT is missing.

    One provider (one ccxt exchange object) per (exchange, market, credentials): the
    first ``fetch_ohlcv`` on a fresh object pays ``loadMarkets`` (multi-MB
    ``exchangeInfo`` + rate-limit init, ~3s observed), so building a new
    provider per tick put a 3s floor under every cache-missing tick. Cached
    objects refresh after ``_PROVIDER_TTL_S`` so new listings appear without
    a restart. ``None`` is never cached — a missing-CCXT answer must not pin
    later tests/process states that install it.
    """
    _, credentials = datafeed._resolve_session(exchange, "")
    key = _provider_cache_key(exchange, credentials, market)
    now = time.monotonic()
    with _provider_guard:
        provider = _providers.get(key)
        if provider is not None and now - _provider_at.get(key, 0.0) < _PROVIDER_TTL_S:
            return provider
        provider = datafeed._make_provider(exchange, credentials, market)
        if provider is None:
            return None
        _providers[key] = provider
        _provider_at[key] = now
        _fetch_locks.setdefault(key, threading.Lock())
        return provider


def _provider_cache_key(exchange: str, credentials: dict[str, str] | None, market: str = "spot") -> str:
    """Cache key that separates credential sets without storing secrets."""
    try:
        fp = hashlib.sha256(json.dumps(credentials or {}, sort_keys=True, default=str).encode()).hexdigest()[:12]
    except Exception:  # unserializable creds still need a key
        fp = "nofp"
    mkt = str(market or "spot").strip().lower() or "spot"
    return f"{str(exchange or '').strip().lower()}|{mkt}|{fp}"


_providers: dict[str, Any] = {}
_provider_at: dict[str, float] = {}
# One fetch lock per cached provider: ccxt sync objects mutate rate-limit
# state per call, so concurrent tick walks for different series on one
# exchange serialize instead of racing it. Leaf lock — never held while
# acquiring ``_walk_lock`` (walks run outside it by design).
_fetch_locks: dict[str, threading.Lock] = {}
_provider_guard = threading.Lock()
# Cached exchange objects hold loadMarkets output; refresh periodically.
_PROVIDER_TTL_S = 1800.0


def _fetch_lock_for_exchange(exchange: str, market: str = "spot") -> threading.Lock:
    """Fetch-serialization lock for the cached provider of *exchange*."""
    _, credentials = datafeed._resolve_session(exchange, "")
    key = _provider_cache_key(exchange, credentials, market)
    with _provider_guard:
        return _fetch_locks.setdefault(key, threading.Lock())


def _ccxt_unavailable() -> DataError:
    return DataError(
        "CCXT_UNAVAILABLE",
        "CCXT not installed. Install with: pip install 'pynescript[datafeed]'",
        503,
    )


def collect_candles(
    provider: Any,
    key: SeriesKey,
    *,
    since_ms: int,
    now_ms: int,
    max_bars: int | None = None,
) -> list[dict[str, float | int]]:
    """Walk forward through CCXT ``fetch_ohlcv`` pages starting at ``since_ms``.

    Each page starts just after the previous page's newest candle. The walk
    stops when the newest candle is the forming bar, when a page is empty, when
    ``max_bars`` candles are held, or after ``MAX_FETCH_PAGES`` pages. Returns
    candles ascending by time, unique per time.
    """
    interval_s = key.interval_seconds
    now_s = now_ms // 1000
    found: dict[int, dict[str, float | int]] = {}
    cursor_ms = since_ms
    for _ in range(MAX_FETCH_PAGES):
        raw = provider.fetch_ohlcv(key.symbol, key.interval, since=cursor_ms, limit=FETCH_PAGE_LIMIT)
        rows = [
            bar
            for bar in (datafeed._candle_to_bar(c) for c in raw or [])
            if bar is not None and int(bar["time"]) * 1000 >= cursor_ms
        ]
        if not rows:
            break
        for bar in rows:
            found[int(bar["time"])] = bar
        last = max(int(bar["time"]) for bar in rows)
        if last + interval_s > now_s:
            break
        cursor_ms = (last + interval_s) * 1000
        if max_bars is not None and len(found) >= max_bars:
            break
    return [found[t] for t in sorted(found)]


def _collect_or_raise(
    provider: Any,
    key: SeriesKey,
    *,
    since_ms: int,
    now_ms: int,
    max_bars: int | None,
) -> list[dict[str, float | int]]:
    try:
        # Serialize walks per cached provider: ccxt sync exchange objects
        # mutate rate-limit state per call. The walk itself runs outside the
        # per-series lock (no nesting — this is a leaf lock).
        with _fetch_lock_for_exchange(key.exchange, key.market):
            return collect_candles(provider, key, since_ms=since_ms, now_ms=now_ms, max_bars=max_bars)
    except DataError:
        raise
    except Exception as exc:  # every provider failure is an upstream failure here
        if isinstance(exc, ImportError) or "not installed" in str(exc).lower():
            raise _ccxt_unavailable() from exc
        logger.warning("data series upstream %s: %s", key.exchange, exc)
        raise DataError("UPSTREAM", f"Failed to fetch OHLCV from {key.exchange}.", 502) from exc


def fetch_history(key: SeriesKey, history_bars: int) -> dict[str, Any]:
    """Fetch the newest ``history_bars`` bars for *key* and persist them."""
    provider = provider_for(key.exchange, key.market)
    if provider is None:
        raise _ccxt_unavailable()
    store = series_store.get_store()
    with store.key_lock(key.text):
        now_ms = series_store.now_seconds() * 1000
        since_ms = max(0, now_ms - history_bars * key.interval_seconds * 1000)
        candles = _collect_or_raise(provider, key, since_ms=since_ms, now_ms=now_ms, max_bars=history_bars)
        window = candles[-history_bars:]
        status = store.provide(key, window, source=SOURCE_FETCH)
    return {"fetched": len(window), **status}


def _gap_blocked(key_text: str, start: int) -> bool:
    prev = _gap_failures.get(key_text)
    return prev is not None and prev[0] == start and prev[1] >= _GAP_GIVE_UP


def _gap_failed(key_text: str, start: int) -> None:
    prev = _gap_failures.get(key_text)
    n = prev[1] + 1 if prev is not None and prev[0] == start else 1
    _gap_failures[key_text] = (start, n)


def _fill_one_gap(store: Any, provider: Any, key: SeriesKey, now_s: int) -> bool:
    """Write one page into the widest hole. True when a hole was seen.

    The page is at most ``TICK_MAX_BARS``. A hole larger than that shrinks
    on later ticks instead of one 200-page walk. No candles for that start
    (a closed market) gives up after ``_GAP_GIVE_UP`` tries.
    """
    step = key.interval_seconds
    gap = store.widest_gap(key, step)
    if gap is None:
        _gap_failures.pop(key.text, None)
        return False
    start, _end = gap
    if _gap_blocked(key.text, start):
        return True
    until_s = min(now_s, start + TICK_MAX_BARS * step)
    try:
        candles = _cached_walk(
            provider,
            key,
            since_ms=start * 1000,
            now_ms=until_s * 1000,
            max_bars=TICK_MAX_BARS,
            owner_id=None,
        )
    except DataError:
        _gap_failed(key.text, start)
        return True
    if not candles:
        _gap_failed(key.text, start)
        return True
    with store.key_lock(key.text):
        before = int(store.status(key)["count"])
        store.provide(key, candles, source=SOURCE_GAP)
        after = int(store.status(key)["count"])
    if after <= before:
        _gap_failed(key.text, start)
    else:
        _gap_failures.pop(key.text, None)
    return True


def sync_data_session(
    session: Any,
    binding: live.SeriesBinding,
    *,
    is_alive: Callable[[], bool] | None = None,
    on_apply: Callable[[str, Any], None] | None = None,
) -> live.SyncOutcome:
    """Pull candles since the stored newest and advance *session*.

    The network walk runs **outside** ``key_lock`` so a slow upstream cannot
    hold up every other request for the same series (head-of-line blocking);
    the lock only guards the fast local commit: the status read, the liveness
    check, the persist (closed + forming tip) and the session advance.

    When the stored anchor is staler than :data:`TICK_MAX_BARS`, the walk is
    clamped to a bounded recent window. One extra page is then written into
    the widest hole that clamp left behind. ``stale`` stays true while a hole
    was seen so the client reloads the session instead of keeping the jump.

    ``is_alive`` (optional) re-checks session liveness after the fetch; when it
    returns ``False`` the tick raises ``SESSION_GONE`` before persisting or
    advancing anything.
    """
    key = binding.key
    interval_s = key.interval_seconds
    provider = provider_for(key.exchange, key.market)
    if provider is None:
        raise _ccxt_unavailable()
    store = series_store.get_store()
    now_s = series_store.now_seconds()

    with store.key_lock(key.text):
        newest = store.status(key)["newest"]
    anchor = binding.last_time if newest is None else int(newest)
    stale = now_s - anchor > TICK_MAX_BARS * interval_s
    if stale:
        # Clamp to a bounded recent window instead of walking the whole gap.
        since_ms = max(0, now_s - (TICK_MAX_BARS + TICK_OVERLAP_BARS) * interval_s) * 1000
    else:
        since_ms = max(0, anchor - TICK_OVERLAP_BARS * interval_s) * 1000

    # Upstream walk outside the per-series lock. Bounded by the clamp above,
    # by max_bars and by MAX_FETCH_PAGES in collect_candles. Shared per series
    # for a few seconds (see _cached_walk): concurrent session ticks for the
    # same series reuse one walk instead of paying N identical CCXT round trips.
    candles = _cached_walk(
        provider,
        key,
        since_ms=since_ms,
        now_ms=now_s * 1000,
        max_bars=TICK_MAX_BARS,
        owner_id=id(session),
    )

    # The local commit (liveness, persist, session advance) is fast, so it
    # serializes concurrent ticks under the per-series lock — but the network
    # walk above does not hold it.
    with store.key_lock(key.text):
        if is_alive is not None and not is_alive():
            raise DataError("SESSION_GONE", "Session was released while the tick was in flight.", 404)
        # Persist closed bars and the forming tip (same as persist_feed_bars):
        # GET /data/series readers otherwise sit one bar behind the venue.
        if candles:
            store.provide(key, candles, source=SOURCE_TICK)
    # Network fill stays outside the per-series lock. One page only.
    hole = _fill_one_gap(store, provider, key, now_s)
    with store.key_lock(key.text):
        if is_alive is not None and not is_alive():
            raise DataError("SESSION_GONE", "Session was released while the tick was in flight.", 404)
        return live.sync_session(session, binding, candles, now_s, stale=stale or hole, on_apply=on_apply)


def _key_from_args(args: Any) -> SeriesKey:
    return series_store.make_key(args.get("exchange"), args.get("symbol"), args.get("interval"), args.get("market"))


def _key_from_body(body: dict[str, Any]) -> SeriesKey:
    return series_store.make_key(body.get("exchange"), body.get("symbol"), body.get("interval"), body.get("market"))


def _int_arg(args: Any, name: str, default: int, low: int, high: int) -> int:
    raw = args.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except ValueError as exc:
        raise DataError(f"INVALID_{name.upper()}", f"{name} must be an integer between {low} and {high}") from exc
    if value < low or value > high:
        raise DataError(f"INVALID_{name.upper()}", f"{name} must be an integer between {low} and {high}")
    return value


bp.register_error_handler(DataError, data_error_response)


@bp.route("/series", methods=["GET"])
@require_api_key
def series_status():
    """Stored bounds for one series. Unknown series report count 0."""
    key = _key_from_args(request.args)
    return jsonify({"status": "success", **series_store.get_store().status(key)}), 200


@bp.route("/series", methods=["DELETE"])
@require_api_key
def series_purge():
    """Drop every stored bar of one series (the engine's cache of the venue).

    A client that flushed its own dataset uses this to drop the engine's copy
    too, so the next read starts from the venue again. Per key only: the
    store is shared, so a purge never touches another series. Sessions bound
    to the purged key are dropped with the bars — resuming one afterwards
    would evaluate the window the purge just threw away.
    """
    key = _key_from_args(request.args)
    result = series_store.get_store().purge(key)
    try:
        from backend.middleware.sessions import SESSIONS

        dropped = SESSIONS.drop_by_key(key.text)
    except Exception:
        dropped = 0
    return jsonify({"status": "success", **result, "sessions_dropped": dropped}), 200


@bp.route("/series/bars", methods=["GET"])
@require_api_key
def series_bars():
    """Newest stored bars for a series, ascending."""
    key = _key_from_args(request.args)
    limit = _int_arg(
        request.args,
        "limit",
        series_store.DEFAULT_WINDOW_LIMIT,
        1,
        series_store.MAX_WINDOW_LIMIT,
    )
    bars = series_store.get_store().window(key, limit)
    return jsonify({"status": "success", "key": key.text, "count": len(bars), "bars": bars}), 200


@bp.route("/series/provide", methods=["POST"])
@require_api_key
def series_provide():
    """Upsert closed bars uploaded by the client (at most 5,000 per request)."""
    validated, err = validate(request.get_json(silent=True) or {}, DATA_SERIES_PROVIDE_SCHEMA)
    if err is not None:
        return err
    key = _key_from_body(validated)
    bars = validated["bars"]
    if len(bars) > series_store.MAX_PROVIDE_BARS:
        return jsonify(
            {
                "status": "error",
                "code": "BATCH_TOO_LARGE",
                "message": f"At most {series_store.MAX_PROVIDE_BARS} bars per request; split the upload into chunks.",
            }
        ), 413
    result = series_store.get_store().provide(key, bars, source=validated["source"])
    return jsonify(
        {
            "status": "success",
            "key": key.text,
            "added": result["added"],
            "updated": result["updated"],
            "count": result["count"],
            "newest": result["newest"],
        }
    ), 200


@bp.route("/series/fetch", methods=["POST"])
@require_api_key
def series_fetch():
    """Fetch the newest ``history_bars`` bars from the exchange via CCXT and persist them."""
    validated, err = validate(request.get_json(silent=True) or {}, DATA_SERIES_FETCH_SCHEMA)
    if err is not None:
        return err
    key = _key_from_body(validated)
    history = series_store.check_history_bars(validated["history_bars"])
    result = fetch_history(key, history)
    return jsonify(
        {
            "status": "success",
            "key": key.text,
            "fetched": result["fetched"],
            "count": result["count"],
            "oldest": result["oldest"],
            "newest": result["newest"],
        }
    ), 200
