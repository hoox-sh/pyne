# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fill coverage gaps in MCP ops modules (optimize / runner / builtins)."""

from __future__ import annotations

from typing import Any

import pytest

from pynescript.mcp.ops import builtins as builtins_ops
from pynescript.mcp.ops import optimize as optimize_ops
from pynescript.mcp.ops import runner as runner_ops


STRATEGY = """//@version=6
strategy("opt")
len = input.int(10, "len")
plot(ta.sma(close, len))
"""

SPACE = {"params": [{"name": "len", "kind": "int", "min": 5, "max": 15, "step": 5}]}


def test_lookup_builtin_requires_name() -> None:
    assert builtins_ops.lookup_builtin("")["ok"] is False
    assert builtins_ops.lookup_builtin("   ")["kind"] == "io"


def test_lookup_builtin_known_and_ta_prefix() -> None:
    r = builtins_ops.lookup_builtin("ta.sma")
    assert r["ok"] is True
    assert r["name"] == "ta.sma"
    # bare name may resolve via ta. prefix
    r2 = builtins_ops.lookup_builtin("sma")
    assert r2["ok"] is True


def test_lookup_builtin_unknown() -> None:
    r = builtins_ops.lookup_builtin("definitely.not.a.builtin.xyz")
    assert r["ok"] is False
    assert "unknown" in r["error"]


def test_list_builtins_filter_and_limit() -> None:
    all_items = builtins_ops.list_builtins(limit=5)
    assert all_items["ok"] is True
    assert all_items["count"] == 5
    filtered = builtins_ops.list_builtins(category="__no_such_cat__", limit=20)
    assert filtered["ok"] is True
    assert filtered["count"] == 0


def test_list_facade_templates_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom():
        raise RuntimeError("offline")

    monkeypatch.setattr("pynescript.util.pine_facade.list_builtin_scripts", boom)
    r = builtins_ops.list_facade_templates()
    assert r["ok"] is False
    assert r["kind"] == "network"


def test_list_facade_templates_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pynescript.util.pine_facade.list_builtin_scripts",
        lambda: [
            {"scriptIdPart": "1", "extraKind": "indicator", "version": "6", "scriptName": "A"},
            "bad",
            {"scriptId": "2", "kind": "strategy"},
        ],
    )
    r = builtins_ops.list_facade_templates(limit=1)
    assert r["ok"] is True
    assert r["count"] == 1
    assert r["listed"] == 3


def test_optimize_requires_space() -> None:
    r = optimize_ops.optimize_source(source=STRATEGY, bars=40, trials=2)
    assert r["ok"] is False
    assert "space" in r["error"]


def test_optimize_bad_space_json() -> None:
    r = optimize_ops.optimize_source(source=STRATEGY, space_json="{not-json", bars=40, trials=2)
    assert r["ok"] is False
    r2 = optimize_ops.optimize_source(source=STRATEGY, space_json="[]", bars=40, trials=2)
    assert r2["ok"] is False


def test_optimize_happy_path_in_sample() -> None:
    r = optimize_ops.optimize_source(
        source=STRATEGY,
        space=SPACE,
        bars=60,
        trials=3,
        sampler="random",
        objective="net_pnl",
        validation="in-sample",
        seed=1,
    )
    assert r["ok"] is True
    assert "study" in r


def test_optimize_walk_forward_too_short() -> None:
    r = optimize_ops.optimize_source(
        source=STRATEGY,
        space=SPACE,
        bars=20,
        trials=2,
        validation="walk-forward",
        train_bars=50,
        test_bars=20,
        seed=1,
    )
    assert r["ok"] is False
    assert "walk-forward" in r["error"]


def test_runner_show_delete_require_id() -> None:
    assert runner_ops.runner_show("")["ok"] is False
    assert runner_ops.runner_delete("  ")["ok"] is False


def test_runner_call_network_and_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("down")

    monkeypatch.setattr(runner_ops, "api_request", boom)
    assert runner_ops.runner_list(url="http://example.test")["kind"] == "network"

    def ok_scripts(*_a, **_k):
        return {"webhook_url": "http://x", "scripts": [{"id": "a"}]}

    monkeypatch.setattr(runner_ops, "api_request", ok_scripts)
    r = runner_ops.runner_list(url="http://example.test", token="tok")
    assert r["ok"] is True
    # top-level secret keys are redacted (list items are not deep-walked)
    assert r["webhook_url"] == "***"
    assert r["scripts"][0]["id"] == "a"


def test_runner_deploy_and_tick(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls: list[tuple] = []

    def fake_api(origin, method, path, body=None, token=""):
        calls.append((method, path, body, token))
        if method == "POST" and path == "/scripts":
            return {"script": {"id": "demo", "webhook_url": "secret"}}
        return {"ok": True}

    monkeypatch.setattr(runner_ops, "api_request", fake_api)
    pine = tmp_path / "demo.pine"
    pine.write_text(STRATEGY, encoding="utf-8")
    r = runner_ops.runner_deploy(path=str(pine), script_id="demo", webhook="http://hook", token="T")
    assert r["ok"] is True
    assert r["script"]["webhook_url"] == "***"
    t = runner_ops.runner_tick(script_id="demo", force=True, url="http://api", token="T")
    assert t["ok"] is True
    assert any(c[1] == "/cron/run" for c in calls)


def test_runner_jobs_and_enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner_ops, "api_request", lambda *a, **k: {"jobs": []})
    assert runner_ops.runner_jobs()["ok"] is True
    monkeypatch.setattr(runner_ops, "api_request", lambda *a, **k: {"id": "x", "enabled": True})
    r = runner_ops.runner_enable("x", enabled=True)
    assert r["ok"] is True
