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

"""Official MCP SDK server: tools, resources, and prompts for PYNE."""

from __future__ import annotations

import importlib.util
import json

from typing import Any

from pynescript import __version__
from pynescript.mcp.ops.axb1 import verify_axb1_vectors
from pynescript.mcp.ops.builtins import list_builtins
from pynescript.mcp.ops.builtins import list_facade_templates
from pynescript.mcp.ops.builtins import lookup_builtin
from pynescript.mcp.ops.compile import compile_source
from pynescript.mcp.ops.compile import prewarm_sources
from pynescript.mcp.ops.compile import run_synthetic
from pynescript.mcp.ops.data import fetch_data
from pynescript.mcp.ops.execute import execute_source
from pynescript.mcp.ops.execute import parity_source
from pynescript.mcp.ops.info import info_payload
from pynescript.mcp.ops.language import check_sources
from pynescript.mcp.ops.language import convert_source
from pynescript.mcp.ops.language import diagnostics_source
from pynescript.mcp.ops.language import dump_source
from pynescript.mcp.ops.language import format_source
from pynescript.mcp.ops.language import lint_source
from pynescript.mcp.ops.language import parse_source
from pynescript.mcp.ops.language import symbols_source
from pynescript.mcp.ops.language import unparse_source
from pynescript.mcp.ops.lsp import complete_source
from pynescript.mcp.ops.lsp import hover_source
from pynescript.mcp.ops.lsp import signature_source
from pynescript.mcp.ops.optimize import optimize_source
from pynescript.mcp.ops.runner import runner_delete
from pynescript.mcp.ops.runner import runner_deploy
from pynescript.mcp.ops.runner import runner_enable
from pynescript.mcp.ops.runner import runner_jobs
from pynescript.mcp.ops.runner import runner_list
from pynescript.mcp.ops.runner import runner_show
from pynescript.mcp.ops.runner import runner_tick
from pynescript.mcp.ops.sessions import inspect_sessions


_INSTRUCTIONS = """\
PYNE MCP — Pine Script™ parse, lint, convert, compile, and run (in-process Python).
Prefer source= over path= so scripts can be pasted. Tools return JSON {ok, ...};
parse/runtime failures are ok=false (not protocol errors). Plot series are truncated
(last N). AXIS MCP is a different server (chart PWA); do not call axis_* tools here.
Default data provider is mock. Runner tools hit the Pro API (PYNE_API_URL / ADMIN_TOKEN).
"""


def _require_mcp() -> None:
    if importlib.util.find_spec("mcp") is None:
        msg = "MCP extra missing. Install with: pip install 'hoox-pyne[mcp]'"
        raise ImportError(msg)


def pyne_info() -> dict[str, Any]:
    """Package version, Python, numba, and entry points (CLI pyne info)."""
    return info_payload()


def pyne_check(
    source: str | None = None,
    path: str | None = None,
    paths: list[str] | None = None,
    encoding: str = "utf-8",
    ext: str = ".pine",
) -> dict[str, Any]:
    """Parse-only validation (CLI pyne check). source, path, or paths."""
    return check_sources(source, path, paths, encoding=encoding, ext=ext)


def pyne_format(source: str | None = None, path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
    """Canonicalize Pine via parse → unparse. Returns source; does not write disk."""
    return format_source(source, path, encoding=encoding)


def pyne_convert(
    source: str | None = None,
    path: str | None = None,
    to: int = 6,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Rewrite older Pine toward v5 or v6 (CLI pyne convert --to)."""
    return convert_source(source, path, to=to, encoding=encoding)


def pyne_dump(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    indent: int = 2,
    as_json: bool = True,
) -> dict[str, Any]:
    """AST dump text plus JSON tree (CLI pyne parse-and-dump)."""
    return dump_source(source, path, encoding=encoding, indent=indent, as_json=as_json)


def pyne_unparse(source: str | None = None, path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
    """Round-trip parse → unparse (CLI pyne parse-and-unparse)."""
    return unparse_source(source, path, encoding=encoding)


def pyne_lint(source: str | None = None, path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
    """Static diagnostics (CLI pyne lint --json)."""
    return lint_source(source, path, encoding=encoding)


def pyne_compile(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    emit: bool = False,
) -> dict[str, Any]:
    """Compile-check or emit generated Python (CLI pyne compile / --emit)."""
    return compile_source(source, path, encoding=encoding, emit=emit)


def pyne_prewarm(paths: list[str] | None = None, encoding: str = "utf-8", force: bool = False) -> dict[str, Any]:
    """Warm Numba builtins and optional script IR caches (CLI pyne prewarm)."""
    return prewarm_sources(paths, encoding=encoding, force=force)


def pyne_run(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    bars: int = 50,
    sample: int = 8,
) -> dict[str, Any]:
    """Compile and run on synthetic OHLCV (CLI pyne run). For real bars use pyne_execute."""
    return run_synthetic(source, path, encoding=encoding, bars=bars, sample=sample)


def pyne_optimize(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    space: dict[str, Any] | None = None,
    space_json: str = "",
    bars: int = 120,
    trials: int = 20,
    sampler: str = "auto",
    objective: str = "composite",
    validation: str = "holdout",
    train_bars: int | None = None,
    test_bars: int | None = None,
    step_bars: int | None = None,
    holdout_frac: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Search strategy input.* values (CLI pyne optimize). space or space_json required."""
    return optimize_source(
        source,
        path,
        encoding=encoding,
        space=space,
        space_json=space_json,
        bars=bars,
        trials=trials,
        sampler=sampler,
        objective=objective,
        validation=validation,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        holdout_frac=holdout_frac,
        seed=seed,
    )


def pyne_data(
    symbol: str,
    provider: str = "mock",
    period: str = "1y",
    interval: str = "1d",
    api_key: str = "",
    secret: str = "",
    exchange: str = "binance",
    include_series: bool = True,
) -> dict[str, Any]:
    """Fetch OHLCV. Default provider mock (no network). yahoo/ccxt/alphavantage hit the network."""
    return fetch_data(
        symbol,
        provider=provider,
        period=period,
        interval=interval,
        api_key=api_key,
        secret=secret,
        exchange=exchange,
        include_series=include_series,
    )


def pyne_download_builtins(limit: int | None = None) -> dict[str, Any]:
    """List pine-facade builtin template names (network). Does not download files."""
    return list_facade_templates(limit=limit)


def pyne_runner_deploy(
    source: str | None = None,
    path: str | None = None,
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
    """Upload a Pine script to the Pro API hosted runner (POST /scripts). Network."""
    return runner_deploy(
        source,
        path,
        encoding=encoding,
        script_id=script_id,
        symbol=symbol,
        timeframe=timeframe,
        data_source=data_source,
        exchange=exchange,
        period=period,
        mode=mode,
        max_bars=max_bars,
        webhook=webhook,
        disabled=disabled,
        url=url,
        token=token,
    )


def pyne_runner_list(url: str | None = None, token: str | None = None) -> dict[str, Any]:
    """List hosted runner scripts (GET /scripts). Network."""
    return runner_list(url=url, token=token)


def pyne_runner_show(script_id: str, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    """Show one hosted script (GET /scripts/:id). Network. Webhook may be redacted."""
    return runner_show(script_id, url=url, token=token)


def pyne_runner_delete(script_id: str, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    """Delete a hosted script (DELETE /scripts/:id). Network."""
    return runner_delete(script_id, url=url, token=token)


def pyne_runner_tick(
    script_id: str = "",
    force: bool = False,
    url: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Run due hosted scripts (POST /cron/run). Network."""
    return runner_tick(script_id=script_id, force=force, url=url, token=token)


def pyne_runner_jobs(url: str | None = None, token: str | None = None) -> dict[str, Any]:
    """List cron jobs (GET /cron/jobs). Network."""
    return runner_jobs(url=url, token=token)


def pyne_runner_enable(script_id: str, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    """Enable ticks for a hosted script. Network."""
    return runner_enable(script_id, enabled=True, url=url, token=token)


def pyne_runner_disable(script_id: str, url: str | None = None, token: str | None = None) -> dict[str, Any]:
    """Disable ticks for a hosted script. Network."""
    return runner_enable(script_id, enabled=False, url=url, token=token)


def pyne_parse(source: str | None = None, path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
    """Structured parse: version, kind (indicator/strategy/library), title, located errors."""
    return parse_source(source, path, encoding=encoding)


def pyne_symbols(source: str | None = None, path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
    """Outline: functions, types, enums, input.*, plots, strategy.entry."""
    return symbols_source(source, path, encoding=encoding)


def pyne_execute(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    ohlcv: list[dict[str, Any]] | None = None,
    bars: int = 50,
    mode: str = "auto",
    inputs: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
    sample: int = 8,
    include_trades: bool = False,
    ticker: str = "MCP",
    timeframe: str = "1m",
) -> dict[str, Any]:
    """Runtime.run with caller OHLCV rows {time,open,high,low,close,volume?}. Truncated plots."""
    return execute_source(
        source,
        path,
        encoding=encoding,
        ohlcv=ohlcv,
        bars=bars,
        mode=mode,
        inputs=inputs,
        timeout_seconds=timeout_seconds,
        sample=sample,
        include_trades=include_trades,
        ticker=ticker,
        timeframe=timeframe,
    )


def pyne_parity(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    ohlcv: list[dict[str, Any]] | None = None,
    bars: int = 50,
    timeout_seconds: float | None = None,
    ticker: str = "MCP",
    timeframe: str = "1m",
) -> dict[str, Any]:
    """Compare interpret vs compile last plot values (rtol=1e-5, atol=1e-6)."""
    return parity_source(
        source,
        path,
        encoding=encoding,
        ohlcv=ohlcv,
        bars=bars,
        timeout_seconds=timeout_seconds,
        ticker=ticker,
        timeframe=timeframe,
    )


def pyne_hover(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    line: int = 0,
    character: int = 0,
) -> dict[str, Any]:
    """Markdown hover at a 0-based cursor (same as LSP textDocument/hover)."""
    return hover_source(source, path, encoding=encoding, line=line, character=character)


def pyne_complete(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    line: int = 0,
    character: int = 0,
    limit: int = 40,
) -> dict[str, Any]:
    """Completion items at a 0-based cursor (same as LSP textDocument/completion)."""
    return complete_source(source, path, encoding=encoding, line=line, character=character, limit=limit)


def pyne_signature(
    source: str | None = None,
    path: str | None = None,
    encoding: str = "utf-8",
    line: int = 0,
    character: int = 0,
) -> dict[str, Any]:
    """Signature help for the enclosing call (same as LSP textDocument/signatureHelp)."""
    return signature_source(source, path, encoding=encoding, line=line, character=character)


def pyne_builtin(name: str) -> dict[str, Any]:
    """Look up one Pine builtin (e.g. ta.sma) from builtin_metadata.json."""
    return lookup_builtin(name)


def pyne_diagnostics(source: str | None = None, path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
    """Parse errors plus lint findings in one list."""
    return diagnostics_source(source, path, encoding=encoding)


def pyne_axb1(
    vectors_path: str | None = None,
    vectors: Any | None = None,
    only: Any | None = None,
) -> dict[str, Any]:
    """Verify the AXB1 encoder against golden vectors (hex-exact).

    Defaults to the bundled ``tests/data/axb1-vectors.json`` — the wire
    contract shared with AXIS. ``vectors`` takes inline JSON (doc or bare
    array), ``vectors_path`` a file, ``only`` selects vectors by name.
    Also runs fnv1a32 hash checks and codec reject-rule probes.
    """
    return verify_axb1_vectors(vectors_path=vectors_path, vectors=vectors, only=only)


def pyne_sessions(key: str | None = None) -> dict[str, Any]:
    """Inspect pooled live sessions: anchor vs store window, zombie suspects.

    ``key`` optionally filters to one ``exchange|market|SYMBOL|interval``
    series. Read-only — never creates or drops a session.
    """
    return inspect_sessions(key=key)


def review_pine(source: str) -> str:
    """Review Pine: lint, convert to v6 if needed, report issues."""
    return (
        "Review this Pine Script™. Call pyne_lint and pyne_parse, convert to v6 with "
        "pyne_convert if the version is below 6, and summarize remaining diagnostics.\n\n"
        f"```pinescript\n{source}\n```"
    )


def debug_pine(source: str) -> str:
    """Debug Pine: parse, lint, then run 50 synthetic bars."""
    return (
        "Debug this Pine Script™. Use pyne_parse, pyne_lint, then pyne_run with 50 bars. "
        "Explain parse/runtime errors and last plot values.\n\n"
        f"```pinescript\n{source}\n```"
    )


def convert_to_v6(source: str) -> str:
    """Convert Pine to v6 and list remaining W002/C002 issues."""
    return (
        "Convert this Pine Script™ to v6 with pyne_convert (to=6), then pyne_lint. "
        "Show the converted source and remaining W002/C002 findings.\n\n"
        f"```pinescript\n{source}\n```"
    )


def create_server() -> Any:
    """Build an ``MCPServer`` with every PYNE tool, resource, and prompt."""
    _require_mcp()
    from mcp.server import MCPServer
    from mcp.types import ToolAnnotations

    mcp = MCPServer(
        "pyne",
        title="PYNE",
        description="Pine Script™ parse, lint, compile, and run",
        instructions=_INSTRUCTIONS,
        website_url="https://hoox.sh/pyne",
        version=__version__,
    )
    ro = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    net = ToolAnnotations(read_only_hint=True, open_world_hint=True)
    write = ToolAnnotations(read_only_hint=False, open_world_hint=True, destructive_hint=True, idempotent_hint=False)

    for fn, hint in (
        (pyne_info, ro),
        (pyne_check, ro),
        (pyne_format, ro),
        (pyne_convert, ro),
        (pyne_dump, ro),
        (pyne_unparse, ro),
        (pyne_lint, ro),
        (pyne_compile, ro),
        (pyne_prewarm, ro),
        (pyne_run, ro),
        (pyne_optimize, ro),
        (pyne_parse, ro),
        (pyne_symbols, ro),
        (pyne_execute, ro),
        (pyne_parity, ro),
        (pyne_hover, ro),
        (pyne_complete, ro),
        (pyne_signature, ro),
        (pyne_builtin, ro),
        (pyne_diagnostics, ro),
        (pyne_axb1, ro),
        (pyne_sessions, ro),
        (pyne_data, net),
        (pyne_download_builtins, net),
        (pyne_runner_list, net),
        (pyne_runner_show, net),
        (pyne_runner_jobs, net),
        (pyne_runner_deploy, write),
        (pyne_runner_delete, write),
        (pyne_runner_tick, write),
        (pyne_runner_enable, write),
        (pyne_runner_disable, write),
    ):
        mcp.add_tool(fn, annotations=hint)

    @mcp.resource("pyne://info", mime_type="application/json")
    def resource_info() -> str:
        """Package version and extras."""
        return json.dumps(info_payload(), indent=2)

    @mcp.resource("pyne://builtins", mime_type="application/json")
    def resource_builtins() -> str:
        """Compact builtin catalog (name, detail, category)."""
        return json.dumps(list_builtins(limit=2000), indent=2)

    @mcp.resource("pyne://builtins/{name}", mime_type="application/json")
    def resource_builtin(name: str) -> str:
        """One builtin by path (e.g. ta.sma)."""
        return json.dumps(lookup_builtin(name), indent=2)

    mcp.prompt()(review_pine)
    mcp.prompt()(debug_pine)
    mcp.prompt()(convert_to_v6)
    return mcp


_HTTP_TRANSPORTS = frozenset({"sse", "streamable-http"})


def serve_kwargs_from_env() -> tuple[str, dict[str, Any]]:
    """Read ``PYNE_MCP_TRANSPORT`` / ``HOST`` / ``PORT`` for ``MCPServer.run``.

    Default is stdio (CLI / editor hosts). Compose sets
    ``PYNE_MCP_TRANSPORT=streamable-http`` and ``PYNE_MCP_HOST=0.0.0.0``.
    """
    import os

    transport = (os.environ.get("PYNE_MCP_TRANSPORT") or "stdio").strip() or "stdio"
    if transport != "stdio" and transport not in _HTTP_TRANSPORTS:
        msg = f"Unknown PYNE_MCP_TRANSPORT={transport!r} (stdio|sse|streamable-http)"
        raise ValueError(msg)
    if transport == "stdio":
        return transport, {}
    host = (os.environ.get("PYNE_MCP_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port_raw = (os.environ.get("PYNE_MCP_PORT") or "8000").strip() or "8000"
    return transport, {"host": host, "port": int(port_raw)}


def run_stdio() -> None:
    """Serve MCP over stdio (``pyne-mcp`` / ``pyne mcp``)."""
    create_server().run(transport="stdio")


def run() -> None:
    """Serve MCP using ``PYNE_MCP_TRANSPORT`` (stdio default)."""
    transport, kwargs = serve_kwargs_from_env()
    create_server().run(transport=transport, **kwargs)  # type: ignore[arg-type]


def client_config(*, module: bool = False) -> dict[str, Any]:
    """Cursor/Claude ``mcpServers`` JSON (no secrets)."""
    if module:
        return {"mcpServers": {"pyne": {"command": "python", "args": ["-m", "pynescript.mcp"]}}}
    return {"mcpServers": {"pyne": {"command": "pyne-mcp", "args": []}}}
