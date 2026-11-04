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

"""Hosted runner HTTP client (CLI ``pyne runner``). Does not import Flask."""

from __future__ import annotations

import os

from typing import Any

from pynescript.mcp.ops.common import load_source
from pynescript.mcp.serialize import fail
from pynescript.mcp.serialize import ok
from pynescript.mcp.serialize import strip_secrets
from pynescript.util.runner_cli import DEFAULT_URL
from pynescript.util.runner_cli import api_request


def _origin(url: str | None) -> str:
    raw = (url or os.environ.get("PYNE_API_URL") or DEFAULT_URL).rstrip("/")
    return raw


def _token(token: str | None) -> str:
    return (token or os.environ.get("ADMIN_TOKEN") or "").strip()


def _call(
    method: str,
    path: str,
    *,
    url: str | None,
    token: str | None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        data = api_request(_origin(url), method, path, body=body, token=_token(token))
    except Exception as exc:
        return fail(str(exc), kind="network")
    if isinstance(data, dict):
        return ok(**strip_secrets(data))
    return ok(result=data)


def runner_deploy(
    source: str | None = None,
    path: str | None = None,
    *,
    encoding: str = "utf-8",
    script_id: str = "",
    symbol: str = "BTCUSDT",
    timeframe: str = "1d",
    data_source: str = "mock",
    exchange: str = "",
    period: str = "6mo",
    mode: str = "auto",
    max_bars: int = 5000,
    webhook: str = "",
    disabled: bool = False,
    url: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """POST /scripts. Network. Does not echo webhook/token."""
    loaded = load_source(source, path, encoding=encoding)
    if isinstance(loaded, dict):
        return loaded
    text, label = loaded
    sid = (script_id or (path.rsplit("/", 1)[-1].rsplit(".", 1)[0] if path else "script")).strip()
    body: dict[str, Any] = {
        "id": sid,
        "name": sid,
        "script": text,
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": mode,
        "data_source": data_source.lower(),
        "period": period,
        "max_bars": max_bars,
        "enabled": not disabled,
        "webhook_url": webhook,
    }
    if exchange.strip():
        body["data_options"] = {"exchange": exchange.strip()}
    result = _call("POST", "/scripts", url=url, token=token, body=body)
    if not result.get("ok"):
        return result
    rec = result.get("script") if isinstance(result.get("script"), dict) else result
    if isinstance(rec, dict):
        rec = strip_secrets(dict(rec))
    return ok(file=label, script=rec)


def runner_list(*, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    return _call("GET", "/scripts", url=url, token=token)


def runner_show(script_id: str, *, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    if not script_id.strip():
        return fail("script_id is required", kind="io")
    result = _call("GET", f"/scripts/{script_id.strip()}", url=url, token=token)
    if result.get("ok"):
        return ok(**strip_secrets({k: v for k, v in result.items() if k != "ok"}))
    return result


def runner_delete(script_id: str, *, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    if not script_id.strip():
        return fail("script_id is required", kind="io")
    return _call("DELETE", f"/scripts/{script_id.strip()}", url=url, token=token)


def runner_tick(
    *,
    script_id: str = "",
    force: bool = False,
    url: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"force": force}
    if script_id.strip():
        body["script_id"] = script_id.strip()
    return _call("POST", "/cron/run", url=url, token=token, body=body)


def runner_jobs(*, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    return _call("GET", "/cron/jobs", url=url, token=token)


def runner_enable(
    script_id: str,
    *,
    enabled: bool = True,
    url: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    if not script_id.strip():
        return fail("script_id is required", kind="io")
    return _call(
        "PUT",
        "/cron/jobs",
        url=url,
        token=token,
        body={"jobs": [{"script_id": script_id.strip(), "enabled": enabled}]},
    )


def runner_history(
    script_id: str = "",
    *,
    limit: int = 50,
    url: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """GET /cron/history — recent ok / error runs (audit log)."""
    query = f"limit={max(1, min(int(limit or 50), 500))}"
    sid = script_id.strip()
    if sid:
        query += f"&script_id={sid}"
    return _call("GET", f"/cron/history?{query}", url=url, token=token)
