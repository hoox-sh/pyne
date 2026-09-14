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

"""Click group ``pyne runner`` — HTTP client for the Flask hosted runner.

Talks to ``POST /scripts`` and ``POST /cron/run`` on the Pro API
(``PYNE_RUNNER=1``). Does not import ``backend``; stdlib urllib only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from pathlib import Path
from typing import Any

import click


DEFAULT_URL = "http://127.0.0.1:5002"


def api_request(
    url: str,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    token: str = "",
    timeout: float = 120.0,
) -> dict[str, Any]:
    """JSON request against the Pro API. Raises ``click.ClickException`` on error."""
    origin = url.rstrip("/")
    if not origin.startswith(("http://", "https://")):
        msg = "URL must be http:// or https://"
        raise click.ClickException(msg)
    payload = None
    headers = {"Accept": "application/json"}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        origin + path,
        data=payload,
        method=method.upper(),
        headers=headers,
    )
    tok = (token or "").strip()
    if tok:
        req.add_header("X-Admin-Token", tok)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and data.get("code") == "RUNNER_DISABLED":
            msg = "Hosted runner is off. Set PYNE_RUNNER=1 on the API host."
            raise click.ClickException(msg) from exc
        message = ""
        if isinstance(data, dict):
            message = str(data.get("message") or data.get("error") or "")
        raise click.ClickException(message or f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        msg = f"Cannot reach {url}: {exc.reason}"
        raise click.ClickException(msg) from exc
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = "API returned non-JSON"
        raise click.ClickException(msg) from exc
    if not isinstance(parsed, dict):
        msg = "API returned a non-object JSON payload"
        raise click.ClickException(msg)
    return parsed


def _ctx_api(ctx: click.Context, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    obj = ctx.ensure_object(dict)
    return api_request(
        str(obj.get("runner_url") or DEFAULT_URL),
        method,
        path,
        body=body,
        token=str(obj.get("runner_token") or ""),
    )


def _echo_json(data: dict[str, Any]) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


@click.group("runner", short_help="Deploy and tick hosted scripts on the Pro API.")
@click.option(
    "--url",
    envvar="PYNE_API_URL",
    default=DEFAULT_URL,
    show_default=True,
    help="Pro API origin (env PYNE_API_URL).",
)
@click.option(
    "--token",
    envvar="ADMIN_TOKEN",
    default="",
    help="X-Admin-Token when the API has ADMIN_TOKEN set.",
)
@click.pass_context
def runner_group(ctx: click.Context, url: str, token: str) -> None:
    """Talk to the optional Flask hosted runner (PYNE_RUNNER=1).

    Deploy a .pine file, then tick it on bar close without AXIS holding
    the connection.

    \b
    Examples:
      pyne runner deploy script.pine --id demo --symbol BTCUSDT
      pyne runner tick --id demo --force
      pyne runner list
    """
    ctx.ensure_object(dict)
    ctx.obj["runner_url"] = url.rstrip("/")
    ctx.obj["runner_token"] = token or os.environ.get("ADMIN_TOKEN", "")


@runner_group.command("deploy", short_help="Upload a Pine file as a hosted script.")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path))
@click.option("--id", "script_id", default="", help="Registry id (default: file stem).")
@click.option("--symbol", default="BTCUSDT", show_default=True)
@click.option("--timeframe", default="1d", show_default=True)
@click.option(
    "--source",
    "data_source",
    default="mock",
    show_default=True,
    type=click.Choice(["mock", "yahoo", "ccxt", "alphavantage"], case_sensitive=False),
    help="OHLCV provider for each tick.",
)
@click.option("--exchange", default="", help="CCXT exchange id (when --source ccxt).")
@click.option("--period", default="6mo", show_default=True)
@click.option("--mode", default="auto", show_default=True, type=click.Choice(["interpret", "compile", "auto"]))
@click.option("--max-bars", default=5000, show_default=True, type=int)
@click.option("--webhook", default="", help="L2 alert webhook URL.")
@click.option("--disabled", is_flag=True, help="Store the script but do not schedule it.")
@click.option("--encoding", default="utf-8", help="Text encoding of PATH.")
@click.pass_context
def deploy_cmd(
    ctx: click.Context,
    path: Path,
    script_id: str,
    symbol: str,
    timeframe: str,
    data_source: str,
    exchange: str,
    period: str,
    mode: str,
    max_bars: int,
    webhook: str,
    disabled: bool,
    encoding: str,
) -> None:
    """Read PATH and POST /scripts. Ticks use the API data_source on each run."""
    source = path.read_text(encoding=encoding)
    sid = (script_id or path.stem).strip()
    body: dict[str, Any] = {
        "id": sid,
        "name": sid,
        "script": source,
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
    result = _ctx_api(ctx, "POST", "/scripts", body)
    rec = result.get("script") if isinstance(result.get("script"), dict) else result
    sid_out = rec.get("id", sid)
    src_out = rec.get("data_source", data_source)
    on = rec.get("enabled", True)
    click.echo(f"deployed {sid_out}  source={src_out}  enabled={on}")


@runner_group.command("list", short_help="List hosted scripts.")
@click.option("--json", "as_json", is_flag=True, help="Print the API payload.")
@click.pass_context
def list_cmd(ctx: click.Context, as_json: bool) -> None:
    result = _ctx_api(ctx, "GET", "/scripts")
    if as_json:
        _echo_json(result)
        return
    rows = result.get("scripts") or []
    if not rows:
        click.echo("no hosted scripts")
        return
    for rec in rows:
        flag = "on" if rec.get("enabled") else "off"
        click.echo(
            f"{rec.get('id')}  {flag}  {rec.get('symbol')}/{rec.get('timeframe')}  {rec.get('data_source')}"
        )


@runner_group.command("show", short_help="Show one hosted script and cron state.")
@click.argument("script_id")
@click.pass_context
def show_cmd(ctx: click.Context, script_id: str) -> None:
    result = _ctx_api(ctx, "GET", f"/scripts/{script_id}")
    _echo_json(result)


@runner_group.command("delete", short_help="Remove a hosted script.")
@click.argument("script_id")
@click.pass_context
def delete_cmd(ctx: click.Context, script_id: str) -> None:
    result = _ctx_api(ctx, "DELETE", f"/scripts/{script_id}")
    click.echo(result.get("deleted") or script_id)


@runner_group.command("tick", short_help="Run due hosted scripts (POST /cron/run).")
@click.option("--id", "script_id", default="", help="Tick only this script id.")
@click.option("--force", is_flag=True, help="Run even when last bar time did not advance.")
@click.option("--json", "as_json", is_flag=True, help="Print the API payload.")
@click.pass_context
def tick_cmd(ctx: click.Context, script_id: str, force: bool, as_json: bool) -> None:
    """Execute the hosted runner once. Same path as the VPS systemd timer."""
    body: dict[str, Any] = {"force": force}
    if script_id.strip():
        body["script_id"] = script_id.strip()
    result = _ctx_api(ctx, "POST", "/cron/run", body)
    if as_json:
        _echo_json(result)
        return
    jobs = result.get("jobs") or []
    if not jobs:
        click.echo("no jobs")
        return
    for job in jobs:
        sid = job.get("script_id")
        status = job.get("status")
        extra = job.get("reason") or job.get("mode") or ""
        click.echo(f"{sid}  {status}  {extra}".rstrip())


@runner_group.command("jobs", short_help="List cron jobs and last tick state.")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def jobs_cmd(ctx: click.Context, as_json: bool) -> None:
    result = _ctx_api(ctx, "GET", "/cron/jobs")
    if as_json:
        _echo_json(result)
        return
    for rec in result.get("jobs") or []:
        cron = rec.get("cron") if isinstance(rec.get("cron"), dict) else {}
        click.echo(
            f"{rec.get('id')}  enabled={rec.get('enabled')}  "
            f"last={cron.get('last_status') or '-'}  bar={cron.get('last_bar_time') or 0}"
        )


@runner_group.command("enable", short_help="Enable a hosted script for ticks.")
@click.argument("script_id")
@click.pass_context
def enable_cmd(ctx: click.Context, script_id: str) -> None:
    result = _ctx_api(ctx, "PUT", "/cron/jobs", {"jobs": [{"script_id": script_id, "enabled": True}]})
    click.echo(json.dumps(result.get("updated") or result, default=str))


@runner_group.command("disable", short_help="Disable ticks for a hosted script.")
@click.argument("script_id")
@click.pass_context
def disable_cmd(ctx: click.Context, script_id: str) -> None:
    result = _ctx_api(ctx, "PUT", "/cron/jobs", {"jobs": [{"script_id": script_id, "enabled": False}]})
    click.echo(json.dumps(result.get("updated") or result, default=str))
