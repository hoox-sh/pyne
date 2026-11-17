# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof: 0.7.1 verify debt (version, CLI/MCP surfaces, fail-closed)."""

# ruff: noqa: S101, T201

from __future__ import annotations

import builtins

from click.testing import CliRunner

from pynescript.__about__ import __version__
from pynescript.__main__ import cli
from pynescript.mcp.ops import builtins as builtins_ops
from pynescript.util import pine_facade as facade


def main() -> None:
    assert __version__

    runner = CliRunner()
    calls: dict[str, dict] = {}
    original_download = facade.download_builtin_scripts
    facade.download_builtin_scripts = lambda *_, **kwargs: calls.setdefault("kwargs", kwargs) or {}
    try:
        result = runner.invoke(cli, ["download-builtins", "--list", "--plain"])
        assert result.exit_code == 0, result.output
        assert calls["kwargs"]["dry_run"] is True
    finally:
        facade.download_builtin_scripts = original_download

    original_list = facade.list_builtin_scripts
    facade.list_builtin_scripts = lambda: [{"scriptName": "RSI", "scriptIdPart": "STD;RSI", "version": "52"}]
    try:
        listed = builtins_ops.list_facade_templates()
        assert listed["ok"] is True
        assert listed["count"] == 1
        assert listed["templates"][0]["id"] == "STD;RSI"
    finally:
        facade.list_builtin_scripts = original_list

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pynescript.util.pine_facade":
            raise ImportError("removed")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        removed = runner.invoke(cli, ["download-builtins", "--list", "--plain"])
        assert removed.exit_code != 0
        assert "removed" in removed.output.lower()
        removed_mcp = builtins_ops.list_facade_templates()
        assert removed_mcp["ok"] is False
        assert removed_mcp["kind"] == "unsupported"
    finally:
        builtins.__import__ = real_import

    print(f"VERIFY_DEBT_OK version={__version__} format=1 cli=1 mcp=1 failclosed=1")


if __name__ == "__main__":
    main()
