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

"""Click group ``pyne mcp`` plus first-class commands for MCP-only ops."""

from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any

import click

from pynescript.mcp.catalog import TOOL_NAMES
from pynescript.mcp.dispatch import call_tool
from pynescript.mcp.dispatch import parse_kv


def _echo_payload(payload: dict[str, Any], *, extra_fail: bool = False) -> None:
    click.echo(json.dumps(payload, indent=2, default=str))
    if payload.get("ok") is False or extra_fail:
        raise SystemExit(1)


def _payload_has_errors(payload: dict[str, Any]) -> bool:
    """True when the envelope reports error-severity findings.

    ``pyne lint`` exits non-zero on errors (``--fail-on errors`` by default),
    so the MCP call path must match — otherwise CI cannot gate on it.
    """
    count = payload.get("error_count")
    if isinstance(count, int) and count > 0:
        return True
    for key in ("findings", "diagnostics"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("severity") == "error":
                return True
    return False


def _load_json_opt(raw: str, *, label: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"invalid {label} JSON: {exc}"
        raise click.ClickException(msg) from exc


@click.group(
    "mcp",
    invoke_without_command=True,
    short_help="MCP server, client JSON, and in-process tool calls.",
)
@click.pass_context
def mcp_group(ctx: click.Context) -> None:
    """Run the PYNE MCP server, print client JSON, or call a tool in-process.

    ``pyne mcp`` (no subcommand) serves MCP (stdio by default; HTTP when
    ``PYNE_MCP_TRANSPORT`` is ``sse`` or ``streamable-http``) and needs
    ``pip install 'hoox-pyne[mcp]'``. ``config``, ``tools``, and ``call``
    work without the extra.

    \b
    Examples:
      pyne mcp config
      pyne mcp config --module
      pyne mcp tools
      pyne mcp call lint script.pine
      pyne mcp call execute script.pine --arg bars=24 --arg mode=interpret
      pyne mcp
    """
    if ctx.invoked_subcommand is None:
        try:
            from pynescript.mcp.server import run

            run()
        except ImportError as exc:
            raise click.ClickException(str(exc)) from exc


@mcp_group.command("config", short_help="Print MCP client JSON for Cursor / Claude / Inspector.")
@click.option(
    "--module",
    "use_module",
    is_flag=True,
    help="Use python -m pynescript.mcp instead of the pyne-mcp console script.",
)
def mcp_config_cmd(use_module: bool) -> None:
    """Print an ``mcpServers.pyne`` snippet (no secrets)."""
    from pynescript.mcp.server import client_config

    click.echo(json.dumps(client_config(module=use_module), indent=2))


@mcp_group.command("tools", short_help="List PYNE MCP tool names.")
@click.option("--json", "as_json", is_flag=True, help="Print a JSON array.")
def mcp_tools_cmd(as_json: bool) -> None:
    """Print catalog tool names (same as the stdio server)."""
    if as_json:
        click.echo(json.dumps(list(TOOL_NAMES), indent=2))
        return
    for name in TOOL_NAMES:
        click.echo(name)


@mcp_group.command("call", short_help="Execute one MCP tool in-process and print JSON.")
@click.argument("tool")
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=False, dir_okay=False, file_okay=True, readable=True, allow_dash=True),
)
@click.option("--source", "-s", default=None, help="Pine source (overrides PATH).")
@click.option("--encoding", default="utf-8", help="Text encoding when reading PATH.")
@click.option(
    "--json",
    "args_json",
    default="",
    help="JSON object of extra tool arguments (file path or inline).",
)
@click.option(
    "--arg",
    "-a",
    "args",
    multiple=True,
    help="KEY=VALUE extra argument (JSON value if parseable). Repeatable.",
)
@click.option("--name", "builtin_name", default=None, help="Shortcut for --arg name= (pyne_builtin).")
def mcp_call_cmd(
    tool: str,
    path: str | None,
    source: str | None,
    encoding: str,
    args_json: str,
    args: tuple[str, ...],
    builtin_name: str | None,
) -> None:
    """Call TOOL with the same JSON envelope the MCP server returns.

    TOOL may be a catalog name (``pyne_lint``) or a short alias (``lint``).
    PATH sets ``path``; ``-`` reads stdin as ``source``. No MCP SDK required.
    """
    payload: dict[str, Any] = {}
    extra = _load_json_opt(args_json, label="--json")
    if isinstance(extra, dict):
        payload.update(extra)
    elif extra is not None:
        msg = "--json must be a JSON object"
        raise click.ClickException(msg)
    for item in args:
        try:
            key, value = parse_kv(item)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        payload[key] = value
    if builtin_name:
        payload["name"] = builtin_name
    if source is not None:
        payload["source"] = source
    elif path == "-":
        payload["source"] = sys.stdin.read()
    elif path:
        payload["path"] = path
    if "encoding" not in payload:
        payload["encoding"] = encoding
    result = call_tool(tool, payload)
    _echo_payload(result, extra_fail=_payload_has_errors(result))


def _source_kwargs(filename: str, encoding: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"encoding": encoding}
    if filename == "-":
        kwargs["source"] = sys.stdin.read()
    else:
        kwargs["path"] = filename
    return kwargs


_PINE_FILE = click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, allow_dash=True)


@click.command("execute", short_help="Runtime.run Pine (interpret / compile / auto).")
@click.argument("filename", metavar="PATH", type=_PINE_FILE)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option(
    "--bars",
    type=int,
    default=50,
    show_default=True,
    help="Synthetic bar count when --ohlcv is omitted.",
)
@click.option(
    "--mode",
    type=click.Choice(["auto", "interpret", "compile"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Runtime host (same as pyne_execute).",
)
@click.option("--timeout", type=float, default=None, help="Seconds (default 30, cap 120).")
@click.option("--sample", type=int, default=8, show_default=True, help="Trailing plot samples (max 64).")
@click.option("--inputs", "inputs_json", default="", help="JSON object of input.* overrides (or a file path).")
@click.option("--ohlcv", "ohlcv_json", default="", help="JSON array of OHLCV rows, or a file path.")
@click.option("--ticker", default="MCP", show_default=True)
@click.option("--timeframe", default="1m", show_default=True)
@click.option("--trades", is_flag=True, help="Include strategy trade extras.")
def execute_cmd(
    filename: str,
    encoding: str,
    bars: int,
    mode: str,
    timeout: float | None,
    sample: int,
    inputs_json: str,
    ohlcv_json: str,
    ticker: str,
    timeframe: str,
    trades: bool,
) -> None:
    """Evaluate PATH with :class:`~pynescript.runtime.Runtime` and print JSON.

    Unlike ``pyne run`` (compile pipeline + synthetic columns), this is the
    MCP ``pyne_execute`` path: caller OHLCV rows, ``mode``, timeout, truncated plots.
    """
    from pynescript.mcp.ops.execute import execute_source

    inputs = _load_json_opt(inputs_json, label="--inputs")
    if inputs is not None and not isinstance(inputs, dict):
        msg = "--inputs must be a JSON object"
        raise click.ClickException(msg)
    ohlcv = _load_json_opt(ohlcv_json, label="--ohlcv")
    if ohlcv is not None and not isinstance(ohlcv, list):
        msg = "--ohlcv must be a JSON array of rows"
        raise click.ClickException(msg)
    kwargs = _source_kwargs(filename, encoding)
    kwargs.update(
        bars=bars,
        mode=mode,
        inputs=inputs,
        timeout_seconds=timeout,
        sample=sample,
        include_trades=trades,
        ticker=ticker,
        timeframe=timeframe,
        ohlcv=ohlcv,
    )
    _echo_payload(execute_source(**kwargs))


@click.command("symbols", short_help="Outline functions, inputs, plots, and strategy calls.")
@click.argument("filename", metavar="PATH", type=_PINE_FILE)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
def symbols_cmd(filename: str, encoding: str) -> None:
    """Print a JSON outline (MCP ``pyne_symbols``)."""
    from pynescript.mcp.ops.language import symbols_source

    _echo_payload(symbols_source(**_source_kwargs(filename, encoding)))


@click.command("parity", short_help="Compare interpret vs compile last plot values.")
@click.argument("filename", metavar="PATH", type=_PINE_FILE)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
@click.option("--bars", type=int, default=50, show_default=True)
@click.option("--timeout", type=float, default=None)
def parity_cmd(filename: str, encoding: str, bars: int, timeout: float | None) -> None:
    """JSON last-value parity (MCP ``pyne_parity``). Exit 1 when values diverge."""
    from pynescript.mcp.ops.execute import parity_source

    kwargs = _source_kwargs(filename, encoding)
    kwargs.update(bars=bars, timeout_seconds=timeout)
    payload = parity_source(**kwargs)
    _echo_payload(payload, extra_fail=bool(payload.get("ok") and payload.get("match") is False))


@click.command("diagnostics", short_help="Parse errors plus lint findings as one JSON list.")
@click.argument("filename", metavar="PATH", type=_PINE_FILE)
@click.option("--encoding", default="utf-8", help="Text encoding of the file.")
def diagnostics_cmd(filename: str, encoding: str) -> None:
    """JSON diagnostics (MCP ``pyne_diagnostics``). Exit 1 when any item is an error."""
    from pynescript.mcp.ops.language import diagnostics_source

    payload = diagnostics_source(**_source_kwargs(filename, encoding))
    _echo_payload(payload, extra_fail=_payload_has_errors(payload))


@click.command("builtin", short_help="Look up one Pine builtin from builtin_metadata.json.")
@click.argument("name")
def builtin_cmd(name: str) -> None:
    """Print JSON for NAME (MCP ``pyne_builtin``), e.g. ``ta.sma``."""
    from pynescript.mcp.ops.builtins import lookup_builtin

    _echo_payload(lookup_builtin(name))


def register_cli_commands(cli: click.Group) -> None:
    """Attach MCP-backed first-class commands onto the ``pyne`` group."""
    cli.add_command(execute_cmd)
    cli.add_command(symbols_cmd)
    cli.add_command(parity_cmd)
    cli.add_command(diagnostics_cmd)
    cli.add_command(builtin_cmd)
