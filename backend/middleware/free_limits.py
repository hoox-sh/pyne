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

"""Optional free-tier abuse guards for unauthenticated ``/run`` paths.

Audit 2026-08-10 Wave A: free compute (``POST /run``, ``/run/batch``,
``/compile/prewarm``, ``WS /ws/run``) had no bar caps, IP rate limits, or
concurrency gates beyond the 5 MB body limit. When enabled, this module
enforces:

* max OHLCV bar count
* max Pine script character length
* per-process concurrency semaphore
* sliding-window IP rate limit (best-effort; multi-worker needs redis later)
* chart / mock / none data sources only

**Off by default.** Set ``FREE_TIER_LIMITS=1`` (or ``true`` / ``yes`` / ``on``)
to turn the suite on. Individual knobs still apply only while the master
switch is enabled; ``0`` on a numeric knob disables that knob.

Trusted AXIS clients
--------------------
Requests from the AXIS PWA / IDE carry ``Origin: https://axis.hoox.sh`` or
``X-AXIS-Client: pwa|ide``. These signals are **advisory, not
authentication**: any caller can forge them. They only lift the bar/script/
data-source caps and the concurrency slot. The per-IP sliding-window rate
limit is deliberately *not* bypassed and remains the only brake on trusted
traffic, so the total request budget is unchanged. Set ``AXIS_TRUST_TOKEN`` to
require the shared-secret ``X-AXIS-Token`` header as well.

Client IPs come from ``X-Real-IP`` (set by the bundled nginx) or the
rightmost ``X-Forwarded-For`` hop. Never use the leftmost hop: nginx appends
the peer to a client-supplied header, so the first entry is forgeable.
"""

from __future__ import annotations

import hmac
import os
import threading
import time

from collections import defaultdict
from collections import deque
from typing import Any

from flask import g
from flask import has_request_context
from flask import request


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _env_truthy(name: str, *, default: bool = False) -> bool:
    """Parse common truthy env strings (``1``/``true``/``yes``/``on``)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def free_tier_limits_enabled() -> bool:
    """True when the free-tier guard suite is opted in.

    Default **off** (self-hosted / AXIS local). Public hosts should set
    ``FREE_TIER_LIMITS=1``.
    """
    return _env_truthy("FREE_TIER_LIMITS")


# Advisory AXIS trust signals. Not authentication — see the module docstring.
_AXIS_TRUSTED_ORIGIN = "https://axis.hoox.sh"
_AXIS_TRUSTED_CLIENTS = frozenset({"pwa", "ide"})


def _trust_token_ok() -> bool:
    """Optional shared-secret gate for the advisory AXIS trust signal.

    When ``AXIS_TRUST_TOKEN`` is set, the caller must also send a matching
    ``X-AXIS-Token``. When unset, the legacy advisory behaviour is preserved
    for local/self-hosted AXIS setups. Public hosts should set the token.
    """
    expected = (os.environ.get("AXIS_TRUST_TOKEN") or "").strip()
    if not expected:
        return True
    provided = (request.headers.get("X-AXIS-Token") or "").strip()
    return bool(provided) and hmac.compare_digest(provided, expected)


def is_trusted_client() -> bool:
    """True when the request looks like the AXIS PWA or IDE.

    Accepts an exact ``Origin: https://axis.hoox.sh`` or a trimmed,
    case-insensitive ``X-AXIS-Client: pwa|ide``. These headers are client
    controlled and **advisory only**; callers must not treat this as
    authentication. Set ``AXIS_TRUST_TOKEN`` to require the shared-secret
    ``X-AXIS-Token`` header as well.
    """
    if not has_request_context():
        return False
    if not _trust_token_ok():
        return False
    origin = (request.headers.get("Origin") or "").strip()
    if origin == _AXIS_TRUSTED_ORIGIN:
        return True
    client = (request.headers.get("X-AXIS-Client") or "").strip().lower()
    return client in _AXIS_TRUSTED_CLIENTS


def trusted_client_bypass() -> bool:
    """True when the bounds/concurrency caps should be skipped for this request.

    Requires the master switch plus a trusted AXIS signal. The per-IP rate
    limit is intentionally **not** part of this bypass.
    """
    return free_tier_limits_enabled() and is_trusted_client()


def max_free_bars() -> int:
    """Max OHLCV bars on free run paths (default 5000 when the suite is on)."""
    return _env_int("FREE_MAX_BARS", 5000)


def max_free_script_chars() -> int:
    """Max Pine source length on free paths (default 256 KiB)."""
    return _env_int("FREE_MAX_SCRIPT_CHARS", 256 * 1024)


def max_free_concurrent() -> int:
    """Max simultaneous free runs per worker (default 4)."""
    return _env_int("FREE_MAX_CONCURRENT", 4)


def free_rate_limit() -> tuple[int, float]:
    """Return ``(max_requests, window_seconds)`` for free IP rate limit."""
    return (
        _env_int("FREE_RATE_LIMIT", 60),
        float(_env_int("FREE_RATE_WINDOW_SEC", 60) or 60),
    )


# Data sources that may open outbound network connections or need credentials.
# Free unauthenticated paths may only use chart bars or local mock series.
_FREE_ALLOWED_DATA_SOURCES = frozenset({"", "chart", "mock", "none"})


def free_data_source_allowed(data_source: str | None) -> bool:
    """True when *data_source* is safe on free (unauthenticated) routes."""
    if data_source is None:
        return True
    key = str(data_source).strip().lower()
    return key in _FREE_ALLOWED_DATA_SOURCES


class _ConcurrencyGate:
    """Process-local semaphore for free-tier runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0

    def try_acquire(self) -> bool:
        limit = max_free_concurrent()
        if limit <= 0:
            return True  # 0 = disabled
        with self._lock:
            if self._active >= limit:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._active > 0:
                self._active -= 1


class _IpRateLimiter:
    """Sliding-window counter keyed by client IP (best-effort, single-process)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, ip: str, max_req: int | None = None, window: float | None = None) -> bool:
        if max_req is None or window is None:
            max_req, window = free_rate_limit()
        if max_req <= 0:
            return True  # disabled
        now = time.monotonic()
        cutoff = now - window
        with self._lock:
            q = self._hits[ip]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_req:
                return False
            q.append(now)
            # Bound memory for many unique IPs
            if len(self._hits) > 10_000:
                stale = [k for k, v in self._hits.items() if not v or v[-1] < cutoff]
                for k in stale[:5000]:
                    del self._hits[k]
            return True


class _RedisRateLimiter:
    """Redis-backed fixed-window counter shared across workers/replicas.

    Uses ``INCR`` with a per-IP key that expires after the window, so the
    limit is enforced consistently regardless of which gunicorn worker or
    replica handles the request. Falls back to in-memory if Redis is
    unreachable (never blocks a request on a rate-limiter outage).
    """

    def __init__(self, url: str, prefix: str) -> None:
        self._prefix = prefix
        try:
            import redis as _redis

            self._client = _redis.Redis.from_url(url, decode_responses=True)
            self._client.ping()
        except Exception:
            self._client = None

    def _key(self, ip: str, window: int) -> str:
        # Bucket by integer window start so keys expire cleanly.
        bucket = int(time.time() // window)
        return f"pyne:ratelimit:{self._prefix}:{ip}:{window}:{bucket}"

    def allow(self, ip: str, max_req: int | None = None, window: float | None = None) -> bool:
        if max_req is None or window is None:
            max_req, window = free_rate_limit()
        if max_req <= 0:
            return True  # disabled
        if self._client is None:
            return True  # Redis unavailable: fail open (in-memory is the ops choice)
        try:
            current = self._client.incr(self._key(ip, int(window)))
            if current == 1:
                self._client.expire(self._key(ip, int(window)), int(window) + 1)
            return current <= max_req
        except Exception:
            return True  # fail open on Redis error


def _make_rate_limiter(prefix: str = "free") -> _IpRateLimiter | _RedisRateLimiter:
    """Pick a shared Redis limiter when REDIS_URL is set, else in-memory."""
    url = (os.environ.get("REDIS_URL") or "").strip()
    if url:
        return _RedisRateLimiter(url, prefix)
    return _IpRateLimiter()


_GATE = _ConcurrencyGate()
_RATE = _make_rate_limiter("free")
# Auth endpoints are always rate-limited: a random key costs one PBKDF2
# evaluation (~55 ms) even when the key does not exist. Shared across workers
# when Redis is configured so a distributed burn is still throttled.
_AUTH_RATE = _make_rate_limiter("auth")
# Editor bridge endpoints parse up to the global body cap; throttle them even
# when the free-tier suite is off so a browser page cannot pin a worker.
_LSP_RATE = _make_rate_limiter("lsp")


def lsp_rate_limit() -> tuple[int, float]:
    """Return ``(max_requests, window_seconds)`` for LSP bridge endpoints."""
    return (
        _env_int("LSP_RATE_LIMIT", 120),
        float(_env_int("LSP_RATE_WINDOW_SEC", 60) or 60),
    )


def auth_rate_limit() -> tuple[int, float]:
    """Return ``(max_requests, window_seconds)`` for auth endpoints."""
    return (
        _env_int("AUTH_RATE_LIMIT", 30),
        float(_env_int("AUTH_RATE_WINDOW_SEC", 60) or 60),
    )


def client_ip() -> str:
    """Best-effort client IP behind the bundled nginx proxy.

    nginx appends the peer address to any client-supplied ``X-Forwarded-For``
    (``$proxy_add_x_forwarded_for``), so the first hop is attacker-controlled.
    Prefer nginx's ``X-Real-IP``, then the rightmost XFF hop, and only then the
    socket peer. Deployments with multiple trusted proxies should set
    ``X-Real-IP`` at the edge.
    """
    real = (request.headers.get("X-Real-IP") or "").strip()
    if real:
        return real
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[-1].strip() or "unknown"
    return (request.remote_addr or "unknown").strip() or "unknown"


def check_free_rate_limit() -> tuple[dict[str, Any], int] | None:
    """Return ``(error_body, status)`` if rate-limited, else ``None``.

    Callers wrap the body with ``flask.jsonify`` as needed.
    No-op when :func:`free_tier_limits_enabled` is false.
    """
    if not free_tier_limits_enabled():
        return None
    ip = client_ip()
    if _RATE.allow(ip):
        return None
    max_req, window = free_rate_limit()
    return (
        {
            "status": "error",
            "code": "RATE_LIMITED",
            "message": (
                f"Free-tier rate limit exceeded ({max_req} requests / {int(window)}s). Retry later or use an API key."
            ),
        },
        429,
    )


def check_auth_rate_limit() -> tuple[dict[str, Any], int] | None:
    """Always-on rate limit for key validation/minting endpoints.

    Independent of ``FREE_TIER_LIMITS`` so a public auth route cannot be used
    to burn PBKDF2 CPU with random keys.
    """
    ip = client_ip()
    max_req, window = auth_rate_limit()
    if _AUTH_RATE.allow(ip, max_req=max_req, window=window):
        return None
    return (
        {
            "status": "error",
            "code": "RATE_LIMITED",
            "message": (f"Auth rate limit exceeded ({max_req} requests / {int(window)}s). Retry later."),
        },
        429,
    )


def check_lsp_rate_limit() -> tuple[dict[str, Any], int] | None:
    """Always-on rate limit for ``/lsp/*`` editor bridge endpoints."""
    ip = client_ip()
    max_req, window = lsp_rate_limit()
    if _LSP_RATE.allow(ip, max_req=max_req, window=window):
        return None
    return (
        {
            "status": "error",
            "code": "RATE_LIMITED",
            "message": (f"LSP rate limit exceeded ({max_req} requests / {int(window)}s). Retry later."),
        },
        429,
    )


_SLOT_HELD_ATTR = "_free_slot_held"


def _slot_held_here() -> bool:
    """True when this request context actually took a concurrency slot."""
    return bool(getattr(g, _SLOT_HELD_ATTR, False)) if has_request_context() else False


def acquire_free_slot() -> tuple[dict[str, Any], int] | None:
    """Try to take a concurrency slot; return error body or None on success.

    Trusted AXIS clients (advisory header, not auth) skip the slot entirely.
    No-op when :func:`free_tier_limits_enabled` is false (and :func:`release_free_slot`
    remains safe to call).
    """
    if not free_tier_limits_enabled():
        return None
    if trusted_client_bypass():
        return None
    if _GATE.try_acquire():
        # Only record a slot when the gate actually incremented its counter
        # (a 0 limit is "disabled" and does not take one).
        if has_request_context() and max_free_concurrent() > 0:
            setattr(g, _SLOT_HELD_ATTR, True)
        return None
    return (
        {
            "status": "error",
            "code": "TOO_MANY_REQUESTS",
            "message": (
                f"Free-tier concurrency limit reached ({max_free_concurrent()} simultaneous runs). Retry shortly."
            ),
        },
        429,
    )


def release_free_slot() -> None:
    """Release a slot acquired via :func:`acquire_free_slot`.

    Only releases a slot this request actually holds, so a trusted bypass (or
    a duplicate call) cannot free a slot belonging to another request. Outside
    a request context it keeps the old best-effort release.
    """
    if has_request_context():
        if not _slot_held_here():
            return
        setattr(g, _SLOT_HELD_ATTR, False)
    _GATE.release()


def validate_free_run_bounds(
    *,
    script: str | None = None,
    scripts: list[str] | None = None,
    ohlcv: list[Any] | None = None,
    data_source: str | None = None,
) -> tuple[dict[str, Any], int] | None:
    """Validate bar/script/data_source caps for free paths.

    Returns ``(error_body, status)`` on violation, else ``None``.
    Bodies are plain dicts (no Flask request context required).
    No-op when :func:`free_tier_limits_enabled` is false or the caller is a
    trusted AXIS client (:func:`trusted_client_bypass`).
    """
    if not free_tier_limits_enabled():
        return None
    if trusted_client_bypass():
        return None
    max_chars = max_free_script_chars()
    if max_chars > 0:
        sources: list[str] = []
        if isinstance(script, str):
            sources.append(script)
        if scripts:
            sources.extend(s for s in scripts if isinstance(s, str))
        for src in sources:
            if len(src) > max_chars:
                return (
                    {
                        "status": "error",
                        "code": "SCRIPT_TOO_LARGE",
                        "message": (f"Script exceeds free-tier limit ({max_chars} characters)."),
                    },
                    413,
                )

    max_bars = max_free_bars()
    if max_bars > 0 and isinstance(ohlcv, list) and len(ohlcv) > max_bars:
        return (
            {
                "status": "error",
                "code": "TOO_MANY_BARS",
                "message": (
                    f"OHLCV exceeds free-tier limit ({max_bars} bars). "
                    "Reduce data length or use an authenticated endpoint."
                ),
                "max_bars": max_bars,
                "got_bars": len(ohlcv),
            },
            413,
        )

    if not free_data_source_allowed(data_source):
        return (
            {
                "status": "error",
                "code": "DATA_SOURCE_FORBIDDEN",
                "message": (
                    "Free-tier runs may only use chart or mock data "
                    f"(got data_source={data_source!r}). "
                    "Authenticated Pro endpoints can use external feeds."
                ),
            },
            403,
        )

    return None
