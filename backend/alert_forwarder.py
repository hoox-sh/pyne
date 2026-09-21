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

"""Pro API alert webhook delivery (roadmap L2).

Mirrors pyne-worker edge webhooks with a **sync** Flask-friendly POST path.

Configuration (highest priority first):

1. Per-request ``webhook_url`` on ``POST /run``
2. Env ``ALERT_WEBHOOK_URL`` (server default)

Request flags:

- ``forward_alerts`` (default true) — skip delivery when false
- ``alert_last_bar`` (default true) — only POST firings on the last OHLCV bar
- ``alert_batch`` (default true) — one batch POST vs one POST per alert

SSRF policy (audit 2026-08-10 Wave A):

* Only ``http`` / ``https`` schemes
* Block loopback, link-local, private RFC1918, and cloud metadata hosts by default
* Set ``ALERT_WEBHOOK_ALLOW_PRIVATE=1`` only for trusted private-network demos
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Client-visible webhook failure text (no exception / traceback leakage).
_FORWARD_FAILED = "forward failed"

HttpPostJson = Callable[[str, dict[str, Any]], int]

_SOURCE = "pyne-pro-api"
_USER_AGENT = "pynescript-pro-api-alerts/1.0"

_forward_executor: ThreadPoolExecutor | None = None
_forward_executor_lock = threading.Lock()


def _get_forward_executor() -> ThreadPoolExecutor:
    """Lazy shared worker pool for off-thread webhook delivery."""
    global _forward_executor
    with _forward_executor_lock:
        if _forward_executor is None:
            _forward_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pine-alert-fwd")
        return _forward_executor


def _async_delivery_enabled() -> bool:
    return (os.environ.get("ALERT_WEBHOOK_ASYNC") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _forward_logged(
    alerts: list[Any],
    url: str,
    batch: bool,
    symbol: str | None,
) -> None:
    """Off-thread wrapper so webhook failures never surface as task errors."""
    try:
        forward_alerts(alerts, url, batch=batch, symbol=symbol)
    except Exception:  # noqa: BLE001 — background task; log only
        logger.exception("async alert forward failed: %s", url)


# Hostnames blocked even when they resolve to public IPs (defense in depth).
_BLOCKED_WEBHOOK_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "metadata.gce.internal",
    }
)


def default_webhook_url() -> str | None:
    """Server default from ``ALERT_WEBHOOK_URL`` env (SSRF-checked)."""
    raw = (os.environ.get("ALERT_WEBHOOK_URL") or "").strip()
    if not raw:
        return None
    return normalize_webhook_url(raw)


def _allow_private_webhooks() -> bool:
    return (os.environ.get("ALERT_WEBHOOK_ALLOW_PRIVATE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# TTL cache for SSRF DNS verdicts: avoids blocking getaddrinfo twice per
# /run request (early validation + forward-time re-check).
_DNS_VERDICT_TTL = 300.0
_dns_verdicts: dict[str, tuple[float, bool]] = {}
_dns_verdicts_lock = threading.Lock()


def _resolve_dns_blocked(host: str) -> bool:
    """Cached ``getaddrinfo``-based private-host check for *host*."""
    now = time.monotonic()
    with _dns_verdicts_lock:
        cached = _dns_verdicts.get(host)
        if cached is not None and now - cached[0] < _DNS_VERDICT_TTL:
            return cached[1]
    blocked = _dns_resolve_blocked_uncached(host)
    with _dns_verdicts_lock:
        if len(_dns_verdicts) > 4096:
            _dns_verdicts.clear()
        _dns_verdicts[host] = (now, blocked)
    return blocked


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True when *ip* is not a public unicast address.

    Unwraps IPv4-mapped / 6to4 so ``::ffff:127.0.0.1`` is treated as loopback.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped
        if mapped is not None:
            ip = mapped
        else:
            sixtofour = ip.sixtofour
            if sixtofour is not None:
                ip = sixtofour
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def _dns_resolve_blocked_uncached(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _ip_is_blocked(ip):
            return True
    return False


def _parse_literal_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse a hostname that is itself an IP (dotted, IPv6, or decimal IPv4)."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if not host.isdigit():
        return None
    try:
        return ipaddress.IPv4Address(int(host))
    except (ValueError, OverflowError):
        return None


def _host_is_blocked(hostname: str) -> bool:
    """True when *hostname* is loopback/private/metadata and private URLs are disallowed."""
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return True
    if host in _BLOCKED_WEBHOOK_HOSTS:
        return not _allow_private_webhooks()
    # Strip brackets from IPv6 literals
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    ip = _parse_literal_ip(host)
    if ip is not None:
        return False if _allow_private_webhooks() else _ip_is_blocked(ip)
    if _allow_private_webhooks():
        return False
    # Resolve DNS and reject if any address is non-public.
    # Unresolvable hostnames are allowed here — delivery will fail at POST time.
    # (Failing closed on DNS would break tests and legitimate not-yet-published hosts.)
    return _resolve_dns_blocked(host)


def is_webhook_url_safe(url: str) -> bool:
    """Return True when *url* is an allowed outbound webhook destination."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    # Reject userinfo (user:pass@host) — rarely needed and aids smuggling
    if parsed.username is not None or parsed.password is not None:
        return False
    hostname = parsed.hostname or ""
    return not _host_is_blocked(hostname)


def normalize_webhook_url(url: Any) -> str | None:
    """Return a stripped safe http(s) URL or ``None`` if invalid/empty/blocked.

    Blocks private/loopback/metadata targets unless
    ``ALERT_WEBHOOK_ALLOW_PRIVATE=1`` is set (audit 2026-08-10 SSRF fix).
    """
    if url is None:
        return None
    s = str(url).strip()
    if not s:
        return None
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if not is_webhook_url_safe(s):
        return None
    return s


def filter_alerts_for_bar(
    alerts: list[Any],
    bar_time: int | None,
    *,
    bar_index: int | None = None,
) -> list[dict[str, Any]]:
    """Keep alerts that fired on *bar_time* (preferred) or *bar_index*."""
    if not alerts:
        return []
    out: list[dict[str, Any]] = []
    for a in alerts:
        if not isinstance(a, dict):
            continue
        if bar_time is not None:
            try:
                at = int(a.get("time") if a.get("time") is not None else -1)
            except (TypeError, ValueError):
                at = -1
            if at != int(bar_time):
                continue
        elif bar_index is not None:
            try:
                bi = int(a.get("bar_index") if a.get("bar_index") is not None else -1)
            except (TypeError, ValueError):
                bi = -1
            if bi != int(bar_index):
                continue
        out.append(dict(a))
    return out


def build_alert_payload(alert: dict[str, Any], *, symbol: str | None = None) -> dict[str, Any]:
    """JSON body for a single alert (Discord-friendly ``content`` included)."""
    message = str(alert.get("message") or "")
    title = alert.get("title")
    payload: dict[str, Any] = {
        "type": "pine_alert",
        "source": _SOURCE,
        "message": message,
        "freq": str(alert.get("freq") or "once_per_bar"),
        "alert_source": str(alert.get("source") or "alert"),
    }
    if title:
        payload["title"] = str(title)
    for key in (
        "bar_index",
        "time",
        "symbol",
        "timeframe",
        "script_id",
        "run_id",
    ):
        if alert.get(key) is not None:
            payload[key] = alert[key]
    if symbol and "symbol" not in payload:
        payload["symbol"] = symbol
    if title and message:
        payload["content"] = f"**{title}**: {message}"
    elif message:
        payload["content"] = message
    return payload


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse 30x so a public hook cannot bounce into RFC1918 / metadata."""

    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def http_post_json(url: str, body: dict[str, Any], *, timeout: float = 10.0) -> int:
    """POST JSON via urllib; returns HTTP status code.

    Does not follow redirects (SSRF: public URL → 302 → loopback/metadata).
    Re-checks :func:`is_webhook_url_safe` at POST time (DNS rebinding).
    """
    if not is_webhook_url_safe(url):
        msg = "blocked webhook url"
        raise ValueError(msg)
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "X-Source": _SOURCE,
        },
    )
    try:
        with _NO_REDIRECT_OPENER.open(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as e:
        return int(e.code)


def forward_alerts(
    alerts: list[Any],
    webhook_url: str,
    *,
    http_post: HttpPostJson | None = None,
    batch: bool = True,
    symbol: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """POST alert firings to *webhook_url* (sync).

    Returns ``{forwarded, failed, errors, url, batch}``.
    """
    result: dict[str, Any] = {
        "forwarded": 0,
        "failed": 0,
        "errors": [],
        "url": webhook_url,
        "batch": batch,
    }
    if not webhook_url or not alerts:
        return result

    post = http_post or (
        lambda u, b: http_post_json(
            u,
            b,
            timeout=timeout if timeout is not None else float(os.environ.get("ALERT_WEBHOOK_TIMEOUT") or 10),
        )
    )
    payloads = [build_alert_payload(a, symbol=symbol) for a in alerts if isinstance(a, dict)]
    if not payloads:
        return result

    try:
        if batch:
            body: dict[str, Any] = {
                "type": "pine_alert_batch",
                "source": _SOURCE,
                "count": len(payloads),
                "alerts": payloads,
            }
            if len(payloads) == 1 and payloads[0].get("content"):
                body["content"] = payloads[0]["content"]
            status = post(webhook_url, body)
            if 200 <= int(status) < 300:
                result["forwarded"] = len(payloads)
            else:
                result["failed"] = len(payloads)
                result["errors"].append(f"batch HTTP {status}")
        else:
            for p in payloads:
                try:
                    status = post(webhook_url, p)
                    if 200 <= int(status) < 300:
                        result["forwarded"] += 1
                    else:
                        result["failed"] += 1
                        result["errors"].append(f"bar {p.get('bar_index', '?')}: HTTP {status}")
                except Exception as exc:
                    logger.warning("alert webhook post failed: %s", exc)
                    result["failed"] += 1
                    result["errors"].append(f"bar {p.get('bar_index', '?')}: {_FORWARD_FAILED}")
    except Exception as exc:
        logger.warning("alert webhook batch failed: %s", exc)
        result["failed"] = len(payloads)
        result["errors"].append(_FORWARD_FAILED)

    return result


def maybe_forward_run_alerts(
    *,
    alerts: list[Any] | None,
    ohlcv: list[Any] | None,
    webhook_url: str | None,
    enable_forward: bool = True,
    alert_last_bar: bool = True,
    alert_batch: bool = True,
    symbol: str | None = None,
    http_post: HttpPostJson | None = None,
    async_delivery: bool | None = None,
) -> dict[str, Any] | None:
    """Apply last-bar filter and forward when a destination URL is set.

    With ``async_delivery`` (opt-in via ``ALERT_WEBHOOK_ASYNC=1``), the HTTP
    POST runs on a background worker so a slow webhook never stalls the
    ``/run`` request; the returned meta reports ``filter: "pending"``.

    Returns forward meta dict, or ``None`` when nothing was attempted.
    """
    if not enable_forward:
        return None
    url = normalize_webhook_url(webhook_url) or default_webhook_url()
    if not url:
        return None
    raw = [a for a in (alerts or []) if isinstance(a, dict)]
    if not raw:
        return {"forwarded": 0, "failed": 0, "errors": [], "url": url, "count": 0}

    to_send = raw
    filter_mode = "all"
    if alert_last_bar and ohlcv:
        last = ohlcv[-1] if isinstance(ohlcv[-1], dict) else {}
        last_time = last.get("time")
        try:
            last_time_i = int(last_time) if last_time is not None else None
        except (TypeError, ValueError):
            last_time_i = None
        last_index = len(ohlcv) - 1
        filtered = filter_alerts_for_bar(raw, last_time_i, bar_index=last_index)
        # If time-based filter empty but we have bar_index hits, prefer index
        if not filtered and last_time_i is not None:
            filtered = filter_alerts_for_bar(raw, None, bar_index=last_index)
        to_send = filtered
        filter_mode = "last_bar"

    use_async = _async_delivery_enabled() if async_delivery is None else bool(async_delivery)
    if use_async and http_post is None:
        # Deliver off-thread; the request does not wait on the webhook.
        executor = _get_forward_executor()
        executor.submit(
            _forward_logged,
            to_send,
            url,
            alert_batch,
            symbol,
        )
        return {
            "forwarded": 0,
            "failed": 0,
            "errors": [],
            "url": url,
            "batch": alert_batch,
            "filter": "pending",
            "count": len(to_send),
            "async": True,
        }

    meta = forward_alerts(
        to_send,
        url,
        http_post=http_post,
        batch=alert_batch,
        symbol=symbol,
    )
    meta["filter"] = filter_mode
    meta["count"] = len(to_send)
    return meta
