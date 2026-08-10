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

"""Free-tier abuse guards for unauthenticated ``/run`` paths.

Audit 2026-08-10 Wave A: free compute (``POST /run``, ``/run/batch``,
``/compile/prewarm``, ``WS /ws/run``) had no bar caps, IP rate limits, or
concurrency gates beyond the 5 MB body limit. This module enforces:

* max OHLCV bar count
* max Pine script character length
* per-process concurrency semaphore
* sliding-window IP rate limit (best-effort; multi-worker needs redis later)

All limits are overridable via env for local demos and load tests.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict
from collections import deque
from typing import Any

from flask import request


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def max_free_bars() -> int:
    """Max OHLCV bars on free run paths (default 5000)."""
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
    """Sliding-window counter keyed by client IP (best-effort)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, ip: str) -> bool:
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


_GATE = _ConcurrencyGate()
_RATE = _IpRateLimiter()


def client_ip() -> str:
    """Best-effort client IP (honors first X-Forwarded-For hop when present)."""
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    return (request.remote_addr or "unknown").strip() or "unknown"


def check_free_rate_limit() -> tuple[dict[str, Any], int] | None:
    """Return ``(error_body, status)`` if rate-limited, else ``None``.

    Callers wrap the body with ``flask.jsonify`` as needed.
    """
    ip = client_ip()
    if _RATE.allow(ip):
        return None
    max_req, window = free_rate_limit()
    return (
        {
            "status": "error",
            "code": "RATE_LIMITED",
            "message": (
                f"Free-tier rate limit exceeded ({max_req} requests / "
                f"{int(window)}s). Retry later or use an API key."
            ),
        },
        429,
    )


def acquire_free_slot() -> tuple[dict[str, Any], int] | None:
    """Try to take a concurrency slot; return error body or None on success."""
    if _GATE.try_acquire():
        return None
    return (
        {
            "status": "error",
            "code": "TOO_MANY_REQUESTS",
            "message": (
                f"Free-tier concurrency limit reached "
                f"({max_free_concurrent()} simultaneous runs). Retry shortly."
            ),
        },
        429,
    )


def release_free_slot() -> None:
    """Release a slot acquired via :func:`acquire_free_slot`."""
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
    """
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
                        "message": (
                            f"Script exceeds free-tier limit "
                            f"({max_chars} characters)."
                        ),
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
