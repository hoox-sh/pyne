# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CLI smoke tests for ``pynescript`` Click entry point."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from pynescript.__main__ import cli


MINI = """//@version=5
indicator("cli_smoke")
plot(close)
"""


@pytest.fixture
def pine_file(tmp_path: Path) -> Path:
    p = tmp_path / "smoke.pine"
    p.write_text(MINI, encoding="utf-8")
    return p


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_root_help(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--help"])
    assert r.exit_code == 0
    assert "check" in r.output
    assert "compile" in r.output
    assert "run" in r.output
    assert "format" in r.output


def test_alias_dump(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["dump", str(pine_file)])
    assert r.exit_code == 0
    assert "Script" in r.output or "script" in r.output.lower() or "body" in r.output


def test_check_ok(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["check", str(pine_file), "-q"])
    assert r.exit_code == 0


def test_check_fail(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.pine"
    bad.write_text("//@version=5\nindicator(\n", encoding="utf-8")
    r = runner.invoke(cli, ["check", str(bad), "-q"])
    assert r.exit_code == 1


def test_format_check(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["format", str(pine_file), "--check"])
    # may or may not need reformat depending on unparse; exit 0 or 1 both valid
    assert r.exit_code in (0, 1)


def test_format_write(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["fmt", str(pine_file), "-w"])
    assert r.exit_code == 0
    assert pine_file.read_text(encoding="utf-8").strip()


def test_lint_clean(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["lint", str(pine_file), "--fail-on", "never"])
    assert r.exit_code == 0


def test_lint_json(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["lint", str(pine_file), "--json", "--fail-on", "never"])
    assert r.exit_code == 0
    assert r.output.strip().startswith("[")


def test_info_json(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["info", "--json"])
    assert r.exit_code == 0
    assert "pynescript" in r.output
    assert "version" in r.output


def test_compile(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["compile", str(pine_file), "--no-time"])
    assert r.exit_code == 0, r.output
    assert "compiled" in r.output.lower() or "ok" in r.output.lower() or "mode=" in r.output


def test_run(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["run", str(pine_file), "--bars", "16", "--json"])
    assert r.exit_code == 0, r.output
    assert "bars" in r.output
    assert "plots" in r.output


def test_data_mock(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock"])
    assert r.exit_code == 0, r.output
    assert "bars" in r.output.lower() or "close" in r.output.lower()
