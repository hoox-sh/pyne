# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for PYNE MCP Code Mode (card pyne-mcp-add-code-mode-search-ex-d319b5e5).

Run from the pynescript repo root:

    python3 .oo/plans/pyne-codemode-2026-11-13.proof.py

Every check below is an assertion. The final OK lines are what `oo proof attach`
matches; an exit 0 alone is not the proof.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sys

from typing import Any

from pynescript.mcp.catalog import NETWORK_TOOLS
from pynescript.mcp.catalog import READ_TOOLS
from pynescript.mcp.catalog import TOOL_GROUP
from pynescript.mcp.catalog import TOOL_NAMES
from pynescript.mcp.catalog import TOOL_RISK
from pynescript.mcp.catalog import WRITE_TOOLS
from pynescript.mcp.codemode.bridge import create_handlers
from pynescript.mcp.codemode.protocol import SandboxRequest
from pynescript.mcp.codemode.sandbox import build_bwrap_plan
from pynescript.mcp.codemode.sandbox import harness_path
from pynescript.mcp.codemode.sandbox import resolve_js_runtime
from pynescript.mcp.codemode.sandbox import run_in_sandbox
from pynescript.mcp.codemode.view import build_catalog
from pynescript.mcp.codemode.view import build_namespaces
from pynescript.mcp.codemode.view import compact_catalog


BASE_HASH = "b85e8e14e24fc6f25ea3180ff2aaadf14ab86944b7cdf35b4494f85a4f5eb75a"
BASE_NAMES = [
    "pyne_info",
    "pyne_check",
    "pyne_format",
    "pyne_convert",
    "pyne_dump",
    "pyne_unparse",
    "pyne_lint",
    "pyne_compile",
    "pyne_prewarm",
    "pyne_run",
    "pyne_optimize",
    "pyne_parse",
    "pyne_symbols",
    "pyne_execute",
    "pyne_parity",
    "pyne_hover",
    "pyne_complete",
    "pyne_signature",
    "pyne_builtin",
    "pyne_diagnostics",
    "pyne_axb1",
    "pyne_sessions",
    "pyne_data",
    "pyne_download_builtins",
    "pyne_runner_list",
    "pyne_runner_show",
    "pyne_runner_jobs",
    "pyne_runner_history",
    "pyne_runner_deploy",
    "pyne_runner_delete",
    "pyne_runner_tick",
    "pyne_runner_enable",
    "pyne_runner_disable",
]
MINI = '//@version=6\nindicator("proof")\nplot(close)\n'
SUB = {"PYNE_MCP_CODE_MODE_SANDBOX": "subprocess", "PATH": os.environ.get("PATH", "/usr/bin")}


def tool_fingerprint(tools: list[Any]) -> tuple[int, str, list[str]]:
    rows = []
    for tool in tools:
        annotations = tool.annotations
        rows.append(
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "annotations": annotations.model_dump()
                if hasattr(annotations, "model_dump")
                else (annotations.__dict__ if annotations else None),
            }
        )
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return len(rows), hashlib.sha256(blob.encode()).hexdigest(), [row["name"] for row in rows]


def list_tools() -> tuple[int, str, list[str]]:
    from mcp import Client

    from pynescript.mcp.server import create_server

    async def _run():
        server = create_server()
        async with Client(server, raise_exceptions=True) as client:
            listing = await client.list_tools()
            tools = listing.tools if hasattr(listing, "tools") else listing
            return tool_fingerprint(tools)

    return asyncio.run(_run())


def check_catalog() -> dict[str, Any]:
    assert set(TOOL_RISK) == set(TOOL_NAMES)
    assert set(TOOL_GROUP) == set(TOOL_NAMES)
    assert {name for name, risk in TOOL_RISK.items() if risk == "write"} == set(WRITE_TOOLS)
    assert {name for name, risk in TOOL_RISK.items() if risk == "network"} == set(NETWORK_TOOLS)
    assert {name for name, risk in TOOL_RISK.items() if risk == "read"} == set(READ_TOOLS)
    entries = build_catalog()
    assert len(entries) == len(TOOL_NAMES) == 33
    lint = next(entry for entry in entries if entry.tool == "pyne_lint")
    assert lint.group == "language" and lint.risk == "read"
    namespaces = build_namespaces()
    assert namespaces["language"]["lint"] == "pyne_lint"
    assert namespaces["runner"]["delete"] == "pyne_runner_delete"
    return {"catalog_entries": len(entries), "groups": sorted(namespaces)}


def check_search() -> dict[str, Any]:
    result = run_in_sandbox(
        SandboxRequest(
            mode="search",
            code='async () => catalog.filter((x) => x.group === "language" && x.short === "lint")',
            catalog=compact_catalog(),
        ),
        env=SUB,
    )
    assert result.ok is True, result.message
    assert [row["tool"] for row in result.value] == ["pyne_lint"]
    assert result.value[0]["risk"] == "read"
    return {"search_rows": result.value}


def check_execute() -> dict[str, Any]:
    code = (
        "async () => { const r = await pyne.language.lint("
        f"{{source: {json.dumps(MINI)}}}); "
        "return {ok: r.ok, findings: (r.findings || []).length}; }"
    )
    result = run_in_sandbox(
        SandboxRequest(mode="execute", code=code, namespaces=build_namespaces()),
        handlers=create_handlers(env=SUB),
        env=SUB,
    )
    assert result.ok is True, result.message
    assert result.value == {"ok": True, "findings": 0}
    assert result.calls == 1
    return {"execute_value": result.value, "calls": result.calls}


def check_destructive_gate() -> dict[str, Any]:
    seen: list[tuple[str, dict[str, Any]]] = []

    def spy(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        seen.append((name, args or {}))
        return {"ok": True}

    code = 'async () => await pyne.runner.delete({script_id: "abc"})'
    refused = run_in_sandbox(
        SandboxRequest(mode="execute", code=code, namespaces=build_namespaces()),
        handlers=create_handlers(spy, env=SUB),
        env=SUB,
    )
    assert refused.ok is True, refused.message
    assert refused.value["ok"] is False
    assert refused.value["kind"] == "confirmation_required"
    assert seen == []

    allow = dict(SUB, PYNE_MCP_CODE_MODE_ALLOW_DESTRUCTIVE="1")
    handlers = create_handlers(spy, env=allow)
    first = run_in_sandbox(
        SandboxRequest(mode="execute", code=code, namespaces=build_namespaces()),
        handlers=handlers,
        env=allow,
    )
    assert first.ok is True, first.message
    assert first.value["ok"] is False
    assert first.value["kind"] == "confirmation_required"
    token = first.value["confirm_token"]
    assert isinstance(token, str) and token
    assert seen == []

    confirmed_code = f'async () => await pyne.runner.delete({{script_id: "abc", confirm_token: {json.dumps(token)}}})'
    allowed = run_in_sandbox(
        SandboxRequest(mode="execute", code=confirmed_code, namespaces=build_namespaces()),
        handlers=handlers,
        env=allow,
    )
    assert allowed.ok is True, allowed.message
    assert allowed.value == {"ok": True}
    assert seen == [("pyne_runner_delete", {"script_id": "abc"})]
    seen.clear()

    different_args_code = (
        f'async () => await pyne.runner.delete({{script_id: "other", confirm_token: {json.dumps(token)}}})'
    )
    different_args = run_in_sandbox(
        SandboxRequest(mode="execute", code=different_args_code, namespaces=build_namespaces()),
        handlers=handlers,
        env=allow,
    )
    assert different_args.ok is True, different_args.message
    assert different_args.value["ok"] is False
    assert different_args.value["kind"] == "confirmation_required"
    assert seen == []

    different_tool_code = (
        f'async () => await pyne.runner.enable({{script_id: "abc", confirm_token: {json.dumps(token)}}})'
    )
    different_tool = run_in_sandbox(
        SandboxRequest(mode="execute", code=different_tool_code, namespaces=build_namespaces()),
        handlers=handlers,
        env=allow,
    )
    assert different_tool.ok is True, different_tool.message
    assert different_tool.value["ok"] is False
    assert different_tool.value["kind"] == "confirmation_required"
    assert seen == []

    forged_code = f'async () => await pyne.runner.delete({{script_id: "abc", confirm_token: "9999999999.deadbeef"}})'
    forged = run_in_sandbox(
        SandboxRequest(mode="execute", code=forged_code, namespaces=build_namespaces()),
        handlers=handlers,
        env=allow,
    )
    assert forged.ok is True, forged.message
    assert forged.value["ok"] is False
    assert forged.value["kind"] == "confirmation_required"
    assert seen == []

    return {
        "flag_off": refused.value["kind"],
        "flag_on_first": first.value["kind"],
        "confirmed": allowed.value,
        "different_args": different_args.value["kind"],
        "different_tool": different_tool.value["kind"],
        "forged": forged.value["kind"],
    }


def check_escapes() -> dict[str, Any]:
    env_result = run_in_sandbox(
        SandboxRequest(mode="execute", code="async () => ({env: process.env})", namespaces=build_namespaces()),
        handlers=create_handlers(env=SUB),
        env=SUB,
    )
    assert env_result.ok is False
    assert "process is not defined" in env_result.message

    escape_result = run_in_sandbox(
        SandboxRequest(
            mode="execute",
            code='async () => ({p: ({}).constructor.constructor("return process")()})',
            namespaces=build_namespaces(),
        ),
        handlers=create_handlers(env=SUB),
        env=SUB,
    )
    assert escape_result.ok is False
    assert "Code generation from strings disallowed" in escape_result.message
    return {"process_env": env_result.message, "constructor": escape_result.message}


def check_bwrap() -> dict[str, Any]:
    runtime, error = resolve_js_runtime({})
    assert error is None and runtime is not None
    plan = build_bwrap_plan(runtime=runtime, harness=harness_path())
    assert plan.kind == "bwrap" and plan.env == {}
    for flag in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--cap-drop"):
        assert flag in plan.cmd
    assert "--tmpfs" in plan.cmd and "--bind" not in plan.cmd
    ro_binds = [
        (plan.cmd[index + 1], plan.cmd[index + 2]) for index, token in enumerate(plan.cmd) if token == "--ro-bind"
    ]
    assert all(
        source in {runtime, str(harness_path()), "/usr/lib", "/usr/lib64", "/lib", "/lib64"} for source, _ in ro_binds
    )
    if shutil.which("bwrap"):
        result = run_in_sandbox(
            SandboxRequest(
                mode="search",
                code='async () => catalog.filter((x) => x.tool === "pyne_info")',
                catalog=compact_catalog(),
            ),
            env={"PATH": os.environ.get("PATH", "/usr/bin")},
        )
        assert result.ok is True, result.message
        assert result.value[0]["tool"] == "pyne_info"
        return {"bwrap": "ran", "ro_binds": [source for source, _ in ro_binds]}
    return {"bwrap": "plan-only", "ro_binds": [source for source, _ in ro_binds]}


def check_flag() -> dict[str, Any]:
    saved = os.environ.pop("PYNE_MCP_CODE_MODE", None)
    try:
        off_count, off_hash, off_names = list_tools()
        assert off_count == 33
        assert off_hash == BASE_HASH
        assert off_names == BASE_NAMES
        assert set(off_names) == set(TOOL_NAMES)
    finally:
        if saved is not None:
            os.environ["PYNE_MCP_CODE_MODE"] = saved
    os.environ["PYNE_MCP_CODE_MODE"] = "1"
    on_count, _on_hash, on_names = list_tools()
    assert on_count == 35
    assert on_names[:33] == BASE_NAMES
    assert on_names[33:] == ["search", "execute"]
    return {
        "flag_off": {"count": off_count, "sha256": off_hash},
        "flag_on": {"count": on_count, "added": on_names[33:]},
    }


def main() -> int:
    summary = {
        "catalog": check_catalog(),
        "search": check_search(),
        "execute": check_execute(),
        "destructive_gate": check_destructive_gate(),
        "escapes": check_escapes(),
        "bwrap": check_bwrap(),
        "flag": check_flag(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("OK_pyne_codemode_search_narrows")
    print("OK_pyne_codemode_execute_read_only")
    print("OK_pyne_codemode_destructive_gate_fail_closed")
    print("OK_pyne_codemode_confirm_token_bound_to_tool_and_args")
    print("OK_pyne_codemode_process_env_and_escape_blocked")
    print("OK_pyne_codemode_flag_off_hash_and_flag_on_two_tools")
    return 0


if __name__ == "__main__":
    sys.exit(main())
