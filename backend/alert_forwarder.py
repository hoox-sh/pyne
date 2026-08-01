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
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from typing import Callable
from urllib.parse import urlparse

HttpPostJson = Callable[[str, dict[str, Any]], int]

_SOURCE = "pyne-pro-api"
_USER_AGENT = "pynescript-pro-api-alerts/1.0"


def default_webhook_url() -> str | None:
    """Server default from ``ALERT_WEBHOOK_URL`` env."""
    raw = (os.environ.get("ALERT_WEBHOOK_URL") or "").strip()
    return raw or None


def normalize_webhook_url(url: Any) -> str | None:
    """Return a stripped http(s) URL or ``None`` if invalid/empty."""
    if url is None:
        return None
    s = str(url).strip()
    if not s:
        return None
    parsed = urlparse(s)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
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


def http_post_json(url: str, body: dict[str, Any], *, timeout: float = 10.0) -> int:
    """POST JSON via urllib; returns HTTP status code."""
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
            timeout=timeout
            if timeout is not None
            else float(os.environ.get("ALERT_WEBHOOK_TIMEOUT") or 10),
        )
    )
    payloads = [
        build_alert_payload(a, symbol=symbol) for a in alerts if isinstance(a, dict)
    ]
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
                        result["errors"].append(
                            f"bar {p.get('bar_index', '?')}: HTTP {status}"
                        )
                except Exception as e:  # noqa: BLE001
                    result["failed"] += 1
                    result["errors"].append(f"bar {p.get('bar_index', '?')}: {e!s}")
    except Exception as e:  # noqa: BLE001
        result["failed"] = len(payloads)
        result["errors"].append(str(e))

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
) -> dict[str, Any] | None:
    """Apply last-bar filter and forward when a destination URL is set.

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
