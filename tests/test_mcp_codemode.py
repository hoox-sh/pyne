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

"""Code Mode tests: sandbox boundary, bridge policy, and opt-in tool surface."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil

from typing import Any

import pytest

from pynescript.mcp.catalog import NETWORK_TOOLS
from pynescript.mcp.catalog import READ_TOOLS
from pynescript.mcp.catalog import TOOL_GROUP
from pynescript.mcp.catalog import TOOL_NAMES
from pynescript.mcp.catalog import TOOL_RISK
from pynescript.mcp.catalog import WRITE_TOOLS
from pynescript.mcp.codemode.bridge import create_handlers
from pynescript.mcp.codemode.protocol import CodeModeLimits
from pynescript.mcp.codemode.protocol import SandboxRequest
from pynescript.mcp.codemode.sandbox import LIB_DIRS
from pynescript.mcp.codemode.sandbox import build_bwrap_plan
from pynescript.mcp.codemode.sandbox import harness_path
from pynescript.mcp.codemode.sandbox import resolve_js_runtime
from pynescript.mcp.codemode.sandbox import resolve_sandbox_kind
from pynescript.mcp.codemode.sandbox import run_in_sandbox
from pynescript.mcp.codemode.view import build_catalog
from pynescript.mcp.codemode.view import build_namespaces
from pynescript.mcp.codemode.view import compact_catalog


HAS_RUNTIME = resolve_js_runtime({})[0] is not None
if os.environ.get("CI") and not HAS_RUNTIME:
    raise RuntimeError(
        "Code Mode tests require Node.js (node:vm). Install node in CI; "
        "without it the @requires_runtime cases would silently skip."
    )
HAS_BWRAP = shutil.which("bwrap") is not None
SUB = {"PYNE_MCP_CODE_MODE_SANDBOX": "subprocess", "PATH": os.environ.get("PATH", "/usr/bin")}
BASE_HASH = "b85e8e14e24fc6f25ea3180ff2aaadf14ab86944b7cdf35b4494f85a4f5eb75a"
# Server registration order, captured before Code Mode existed. The catalog
# tuple is a different order on purpose; the tool list is what clients see.
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

MINI = '//@version=6\nindicator("x")\nplot(close)\n'

requires_runtime = pytest.mark.skipif(not HAS_RUNTIME, reason="Node.js/Bun not installed")


def _search(code: str, env: dict[str, str] | None = None):
    return run_in_sandbox(
        SandboxRequest(mode="search", code=code, catalog=compact_catalog()),
        env=env or SUB,
    )


def _execute(code: str, handlers=None, env: dict[str, str] | None = None, limits: CodeModeLimits | None = None):
    return run_in_sandbox(
        SandboxRequest(
            mode="execute",
            code=code,
            namespaces=build_namespaces(),
            limits=limits or CodeModeLimits(),
        ),
        handlers=handlers or create_handlers(env=env or SUB),
        env=env or SUB,
    )


def test_risk_and_group_cover_the_catalog() -> None:
    assert set(TOOL_RISK) == set(TOOL_NAMES)
    assert set(TOOL_GROUP) == set(TOOL_NAMES)
    assert set(TOOL_RISK.values()) <= {"read", "network", "write"}
    assert {name for name, risk in TOOL_RISK.items() if risk == "write"} == set(WRITE_TOOLS)
    assert {name for name, risk in TOOL_RISK.items() if risk == "network"} == set(NETWORK_TOOLS)
    assert {name for name, risk in TOOL_RISK.items() if risk == "read"} == set(READ_TOOLS)


def test_compact_catalog_shape() -> None:
    entries = build_catalog()
    assert len(entries) == len(TOOL_NAMES)
    assert entries[0].tool == "pyne_info"
    lint = next(entry for entry in entries if entry.tool == "pyne_lint")
    assert lint.group == "language"
    assert lint.risk == "read"
    assert lint.destructive is False
    assert "source" in lint.args
    assert lint.required == ()
    row = lint.as_dict()
    assert row["short"] == "lint"
    assert row["args"] == ["source", "path", "encoding"]


def test_namespaces_are_grouped() -> None:
    namespaces = build_namespaces()
    assert namespaces["language"]["lint"] == "pyne_lint"
    assert namespaces["runner"]["delete"] == "pyne_runner_delete"
    assert namespaces["compile"]["run"] == "pyne_run"
    assert namespaces["execute"]["execute"] == "pyne_execute"


@requires_runtime
def test_search_narrows_the_catalog() -> None:
    result = _search('async () => catalog.filter((x) => x.group === "language" && x.short === "lint")')
    assert result.ok is True, result.message
    assert isinstance(result.value, list)
    assert [row["tool"] for row in result.value] == ["pyne_lint"]
    assert result.value[0]["risk"] == "read"


@requires_runtime
def test_search_can_return_only_one_field() -> None:
    result = _search('async () => catalog.filter((x) => x.risk === "write").map((x) => x.tool)')
    assert result.ok is True, result.message
    assert result.value == [
        "pyne_runner_deploy",
        "pyne_runner_delete",
        "pyne_runner_tick",
        "pyne_runner_enable",
        "pyne_runner_disable",
    ]


@requires_runtime
def test_execute_runs_a_read_only_op() -> None:
    code = f"async () => {{ const r = await pyne.language.lint({{source: {json.dumps(MINI)}}}); return {{ok: r.ok, findings: (r.findings || []).length}}; }}"
    result = _execute(code)
    assert result.ok is True, result.message
    assert result.value["ok"] is True
    assert result.value["findings"] == 0
    assert result.calls == 1


@requires_runtime
def test_execute_describe_returns_the_full_signature() -> None:
    result = _execute('async () => await pyne.describe("compile")')
    assert result.ok is True, result.message
    assert result.value["tool"] == "pyne_compile"
    assert [param["name"] for param in result.value["parameters"]] == ["source", "path", "encoding", "emit"]


@requires_runtime
def test_execute_refuses_a_destructive_op_without_the_operator_gate() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []

    def spy(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        seen.append((name, args or {}))
        return {"ok": True}

    result = _execute(
        'async () => await pyne.runner.delete({script_id: "abc"})', handlers=create_handlers(spy, env=SUB)
    )
    assert result.ok is True, result.message
    assert result.value["ok"] is False
    assert result.value["kind"] == "confirmation_required"
    assert result.value["tool"] == "pyne_runner_delete"
    assert seen == []


@requires_runtime
def test_execute_requires_a_confirm_token_for_a_destructive_op() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []

    def spy(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        seen.append((name, args or {}))
        return {"ok": True, "spy": name}

    env = dict(SUB, PYNE_MCP_CODE_MODE_ALLOW_DESTRUCTIVE="1")
    handlers = create_handlers(spy, env=env)
    first = _execute(
        'async () => await pyne.runner.delete({script_id: "abc"})',
        handlers=handlers,
        env=env,
    )
    assert first.ok is True, first.message
    assert first.value["ok"] is False
    assert first.value["kind"] == "confirmation_required"
    token = first.value["confirm_token"]
    assert token
    assert seen == []

    confirmed = _execute(
        f'async () => await pyne.runner.delete({{script_id: "abc", confirm_token: {json.dumps(token)}}})',
        handlers=handlers,
        env=env,
    )
    assert confirmed.ok is True, confirmed.message
    assert confirmed.value == {"ok": True, "spy": "pyne_runner_delete"}
    assert seen == [("pyne_runner_delete", {"script_id": "abc"})]


def test_confirm_token_is_bound_to_tool_and_arguments() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []

    def spy(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        seen.append((name, args or {}))
        return {"ok": True}

    env = dict(SUB, PYNE_MCP_CODE_MODE_ALLOW_DESTRUCTIVE="1")
    call = create_handlers(spy, env=env)["call"]

    first = call("pyne_runner_delete", {"script_id": "abc"})
    assert first["kind"] == "confirmation_required"
    token = first["confirm_token"]
    assert seen == []

    assert call("pyne_runner_delete", {"script_id": "abc", "confirm_token": token}) == {"ok": True}
    assert seen == [("pyne_runner_delete", {"script_id": "abc"})]
    seen.clear()

    different_args = call("pyne_runner_delete", {"script_id": "other", "confirm_token": token})
    assert different_args["ok"] is False
    assert different_args["kind"] == "confirmation_required"
    assert seen == []

    different_tool = call("pyne_runner_enable", {"script_id": "abc", "confirm_token": token})
    assert different_tool["ok"] is False
    assert different_tool["kind"] == "confirmation_required"
    assert seen == []

    forged = call("pyne_runner_delete", {"script_id": "abc", "confirm_token": "9999999999.deadbeef"})
    assert forged["ok"] is False
    assert forged["kind"] == "confirmation_required"
    assert seen == []


@requires_runtime
def test_process_env_is_not_reachable() -> None:
    result = _execute("async () => ({env: process.env})")
    assert result.ok is False
    assert "process is not defined" in result.message


@requires_runtime
def test_constructor_escape_is_blocked() -> None:
    result = _execute('async () => ({p: ({}).constructor.constructor("return process")()})')
    assert result.ok is False
    assert "Code generation from strings disallowed" in result.message


@requires_runtime
def test_require_is_not_reachable() -> None:
    result = _execute('async () => require("node:fs").readFileSync("/etc/passwd", "utf8")')
    assert result.ok is False
    assert "require is not defined" in result.message


@requires_runtime
def test_call_limit_is_enforced() -> None:
    limits = CodeModeLimits(max_calls=3)
    code = (
        "async () => { let n = 0; try { for (;;) { await pyne.call('pyne_info', {}); n += 1; } } "
        "catch (err) { return {n, err: String(err)}; } }"
    )
    result = _execute(code, limits=limits)
    assert result.ok is True, result.message
    assert result.value["n"] == 3
    assert "call limit reached (3)" in result.value["err"]


def test_code_size_limit_fails_before_spawn() -> None:
    result = run_in_sandbox(
        SandboxRequest(mode="search", code="x" * 100, catalog=(), limits=CodeModeLimits(max_code_chars=10)),
        env=SUB,
    )
    assert result.ok is False
    assert "limit is 10" in result.message


@requires_runtime
def test_result_truncation_is_marked() -> None:
    limits = CodeModeLimits(max_result_chars=100)
    result = _execute('async () => "x".repeat(500)', limits=limits)
    assert result.ok is True, result.message
    assert result.truncated is True
    assert result.value["truncated"] is True


@requires_runtime
def test_bwrap_plan_is_fail_closed() -> None:
    if not HAS_BWRAP:
        pytest.skip("bwrap not installed")
    runtime, error = resolve_js_runtime({})
    assert error is None and runtime is not None
    plan = build_bwrap_plan(runtime=runtime, harness=harness_path())
    assert plan.kind == "bwrap"
    assert plan.env == {}
    for flag in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--cap-drop"):
        assert flag in plan.cmd
    assert "--tmpfs" in plan.cmd and "/tmp" in plan.cmd
    assert "--bind" not in plan.cmd  # only read-only binds and tmpfs
    ro_binds = [
        (plan.cmd[index + 1], plan.cmd[index + 2]) for index, token in enumerate(plan.cmd) if token == "--ro-bind"
    ]
    allowed = {runtime, str(harness_path()), *LIB_DIRS}
    assert {source for source, _destination in ro_binds} <= allowed


def test_missing_bwrap_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pynescript.mcp.codemode.sandbox.shutil.which", lambda _name: None)
    kind, error = resolve_sandbox_kind({})
    assert kind is None
    assert error is not None
    assert "bubblewrap" in error
    assert "subprocess" in error


def test_subprocess_mode_is_explicit() -> None:
    kind, error = resolve_sandbox_kind({"PYNE_MCP_CODE_MODE_SANDBOX": "subprocess"})
    assert (kind, error) == ("subprocess", None)


@requires_runtime
def test_bwrap_run_when_available() -> None:
    if not HAS_BWRAP:
        pytest.skip("bwrap not installed")
    env = {"PATH": os.environ.get("PATH", "/usr/bin")}
    result = _search('async () => catalog.filter((x) => x.tool === "pyne_info")', env=env)
    assert result.ok is True, result.message
    assert result.value[0]["tool"] == "pyne_info"


# ---------------------------------------------------------------------------
# MCP tool surface: flag off is byte-identical, flag on adds exactly two tools.
# ---------------------------------------------------------------------------


def _tool_fingerprint(tools: list[Any]) -> tuple[int, str, list[str]]:
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


def _list_tools() -> tuple[int, str, list[str]]:
    from mcp import Client

    from pynescript.mcp.server import create_server

    async def _run():
        server = create_server()
        async with Client(server, raise_exceptions=True) as client:
            listing = await client.list_tools()
            tools = listing.tools if hasattr(listing, "tools") else listing
            return _tool_fingerprint(tools)

    return asyncio.run(_run())


def _payload(result: Any) -> dict[str, Any]:
    structured = result.structured_content
    if isinstance(structured, dict):
        if "ok" in structured:
            return structured
        inner = structured.get("result")
        if isinstance(inner, dict) and "ok" in inner:
            return inner
        if isinstance(inner, str):
            try:
                parsed = json.loads(inner)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return structured
    parts = [getattr(block, "text", "") for block in (result.content or [])]
    text = "\n".join(part for part in parts if part)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"ok": not result.is_error, "raw": text}


def test_flag_off_tool_list_is_byte_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    monkeypatch.delenv("PYNE_MCP_CODE_MODE", raising=False)
    count, digest, names = _list_tools()
    assert count == 33
    assert digest == BASE_HASH
    assert names == BASE_NAMES
    assert set(names) == set(TOOL_NAMES)


def test_flag_on_adds_exactly_two_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    monkeypatch.setenv("PYNE_MCP_CODE_MODE", "1")
    count, _digest, names = _list_tools()
    assert count == 35
    assert names[:33] == BASE_NAMES
    assert names[33:] == ["search", "execute"]


@requires_runtime
def test_flag_on_search_and_execute_through_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    monkeypatch.setenv("PYNE_MCP_CODE_MODE", "1")
    monkeypatch.setenv("PYNE_MCP_CODE_MODE_SANDBOX", "subprocess")

    from mcp import Client

    from pynescript.mcp.server import create_server

    async def _run():
        server = create_server()
        async with Client(server, raise_exceptions=True) as client:
            searched = _payload(
                await client.call_tool(
                    "search",
                    {"code": 'async () => catalog.filter((x) => x.short === "lint").map((x) => x.tool)'},
                )
            )
            executed = _payload(
                await client.call_tool(
                    "execute",
                    {
                        "code": (
                            "async () => { const r = await pyne.language.lint("
                            f"{{source: {json.dumps(MINI)}}}); "
                            "return {ok: r.ok, findings: (r.findings || []).length}; }"
                        )
                    },
                )
            )
            return searched, executed

    searched, executed = asyncio.run(_run())
    assert searched["ok"] is True
    assert searched["value"] == ["pyne_lint"]
    assert executed["ok"] is True
    assert executed["value"]["ok"] is True
    assert executed["value"]["findings"] == 0
