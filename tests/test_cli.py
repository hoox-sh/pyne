# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CLI smoke tests for ``pynescript`` Click entry point.

CI-fast: no network, no ``pinescript_filepath`` / builtin corpus fixtures.
Uses tiny inline Pine snippets under ``tmp_path`` only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from pynescript import __version__
from pynescript.__main__ import cli


MINI = """//@version=5
indicator("cli_smoke")
plot(close)
"""

# Spacing / blanks that unparse canonicalizes away (format --check → exit 1).
NEEDS_REFORMAT = """//@version=5


indicator(  "cli_fmt"  )
plot(  close  )


"""


@pytest.fixture
def pine_file(tmp_path: Path) -> Path:
    p = tmp_path / "smoke.pine"
    p.write_text(MINI, encoding="utf-8")
    return p


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _combined(r) -> str:  # noqa: ANN001 — click.testing.Result
    """Stdout + stderr + exception text (Click may put status on either stream)."""
    parts = [r.output or "", getattr(r, "stderr", None) or "", str(r.exception or "")]
    return "".join(parts)


# ---------------------------------------------------------------------------
# Root / version / help
# ---------------------------------------------------------------------------


def test_root_help(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--help"])
    assert r.exit_code == 0
    out = r.output
    assert "check" in out
    assert "compile" in out
    assert "run" in out
    assert "format" in out
    assert "info" in out


def test_version_option(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--version"])
    assert r.exit_code == 0
    # click.version_option message="%(version)s"
    assert __version__ in r.output


def test_version_short_option(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["-V"])
    assert r.exit_code == 0
    assert __version__ in r.output


def test_no_subcommand_shows_help(runner: CliRunner) -> None:
    r = runner.invoke(cli, [])
    assert r.exit_code == 0
    assert "Usage" in r.output or "Commands" in r.output or "check" in r.output


# ---------------------------------------------------------------------------
# check — exit codes, quiet, missing file, stdin
# ---------------------------------------------------------------------------


def test_check_ok(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["check", str(pine_file), "-q"])
    assert r.exit_code == 0
    # quiet: no per-file status noise
    assert r.output.strip() == ""


def test_check_ok_verbose(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["check", str(pine_file)])
    assert r.exit_code == 0
    assert "ok" in r.output.lower() or "✔" in r.output or str(pine_file) in r.output


def test_check_fail(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.pine"
    bad.write_text("//@version=5\nindicator(\n", encoding="utf-8")
    r = runner.invoke(cli, ["check", str(bad), "-q"])
    assert r.exit_code == 1


def test_check_fail_verbose(runner: CliRunner, tmp_path: Path) -> None:
    bad = tmp_path / "bad.pine"
    bad.write_text("//@version=5\nindicator(\n", encoding="utf-8")
    r = runner.invoke(cli, ["check", str(bad)])
    assert r.exit_code == 1
    low = _combined(r).lower()
    assert "fail" in low or "✘" in _combined(r) or "error" in low or "failed" in low


def test_check_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.pine"
    r = runner.invoke(cli, ["check", str(missing)])
    assert r.exit_code != 0
    assert "not found" in _combined(r).lower()


def test_check_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["check", "-"], input=MINI)
    assert r.exit_code == 0


def test_check_stdin_quiet_bad(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["check", "-", "-q"], input="//@version=5\nindicator(\n")
    assert r.exit_code == 1
    assert r.output.strip() == ""


def test_check_directory(runner: CliRunner, tmp_path: Path) -> None:
    good = tmp_path / "a.pine"
    good.write_text(MINI, encoding="utf-8")
    (tmp_path / "skip.txt").write_text("not pine", encoding="utf-8")
    r = runner.invoke(cli, ["check", str(tmp_path), "-q"])
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# parse / dump / format
# ---------------------------------------------------------------------------


def test_alias_dump(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["dump", str(pine_file)])
    assert r.exit_code == 0
    assert "Script" in r.output or "script" in r.output.lower() or "body" in r.output


def test_dump_missing_file(runner: CliRunner, tmp_path: Path) -> None:
    r = runner.invoke(cli, ["dump", str(tmp_path / "nope.pine")])
    assert r.exit_code != 0


def test_dump_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["dump", "-"], input=MINI)
    assert r.exit_code == 0
    assert len(r.output) > 10


def test_format_check_already_formatted(runner: CliRunner, tmp_path: Path) -> None:
    """Write via fmt -w first, then --check must exit 0."""
    p = tmp_path / "fmt.pine"
    p.write_text(MINI, encoding="utf-8")
    w = runner.invoke(cli, ["fmt", str(p), "-w"])
    assert w.exit_code == 0, w.output
    r = runner.invoke(cli, ["format", str(p), "--check"])
    assert r.exit_code == 0, r.output
    assert "formatted" in r.output.lower() or "ok" in r.output.lower() or "✔" in r.output


def test_format_check_needs_reformat(runner: CliRunner, tmp_path: Path) -> None:
    p = tmp_path / "messy.pine"
    p.write_text(NEEDS_REFORMAT, encoding="utf-8")
    r = runner.invoke(cli, ["format", str(p), "--check"])
    # Extra blanks / spacing differ from unparse canonical form
    assert r.exit_code == 1, _combined(r)
    low = _combined(r).lower()
    assert "reformat" in low or "fail" in low or "✘" in _combined(r)


def test_format_write(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["fmt", str(pine_file), "-w"])
    assert r.exit_code == 0
    text = pine_file.read_text(encoding="utf-8")
    assert text.strip()
    assert "indicator" in text


def test_format_stdout(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["format", str(pine_file)])
    assert r.exit_code == 0
    assert "indicator" in r.output
    assert "plot" in r.output


def test_format_write_stdin_rejected(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["format", "-", "-w"], input=MINI)
    assert r.exit_code != 0
    low = _combined(r).lower()
    assert "stdin" in low or "write" in low


# ---------------------------------------------------------------------------
# lint
# ---------------------------------------------------------------------------


def test_lint_clean(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["lint", str(pine_file), "--fail-on", "never"])
    assert r.exit_code == 0


def test_lint_json(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["lint", str(pine_file), "--json", "--fail-on", "never"])
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert isinstance(payload, list)


def test_lint_stdin(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["lint", "-", "--fail-on", "never", "-q"], input=MINI)
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


def test_info_json_shape(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["info", "--json"])
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["name"] == "pynescript"
    assert payload["version"] == __version__
    assert isinstance(payload["python"], str) and payload["python"]
    assert isinstance(payload["platform"], str) and payload["platform"]
    assert isinstance(payload["numba"], bool)
    assert isinstance(payload["rich"], bool)
    assert payload["entry_points"]["cli"] == "pynescript"
    assert payload["entry_points"]["lsp"] == "pynescript-lsp"
    assert "hoox.sh" in payload["docs"]


def test_info_text(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["info"])
    assert r.exit_code == 0
    assert "pynescript" in r.output
    assert __version__ in r.output or "version" in r.output.lower() or "package" in r.output.lower()


def test_info_alias_ls(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["ls", "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["name"] == "pynescript"


# ---------------------------------------------------------------------------
# compile / run — no network; graceful without numba
# ---------------------------------------------------------------------------


def test_compile_emit(runner: CliRunner, pine_file: Path) -> None:
    """``--emit`` is transpile-only and must work without numba."""
    r = runner.invoke(cli, ["compile", str(pine_file), "--emit", "--no-time"])
    assert r.exit_code == 0, r.output
    assert "execute" in r.output or "def " in r.output


def test_compile(runner: CliRunner, pine_file: Path) -> None:
    """Full compile: ok with or without numba; failures must be graceful (exit 1 + message)."""
    r = runner.invoke(cli, ["compile", str(pine_file), "--no-time"])
    combined = _combined(r)
    if r.exit_code == 0:
        low = combined.lower()
        assert "compiled" in low or "ok" in low or "mode=" in low or "✔" in combined
    else:
        # Graceful failure path (e.g. numeric mode without numba)
        assert r.exit_code == 1
        assert combined.strip(), "expected error message, not empty failure"
        # Should not dump a raw Python traceback as the only signal
        assert "Traceback (most recent call last)" not in combined or "numba" in combined.lower()


def test_run(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["run", str(pine_file), "--bars", "16", "--json"])
    combined = _combined(r)
    if r.exit_code == 0:
        payload = json.loads(r.output)
        assert payload["bars"] == 16
        assert "plots" in payload
        assert isinstance(payload["plots"], dict)
    else:
        # Same grace rule as compile when numba is absent for pure-numeric scripts
        assert r.exit_code == 1
        assert combined.strip()


def test_run_bad_bars(runner: CliRunner, pine_file: Path) -> None:
    r = runner.invoke(cli, ["run", str(pine_file), "--bars", "1"])
    assert r.exit_code != 0
    assert "bars" in _combined(r).lower()


# ---------------------------------------------------------------------------
# data — mock only (no network)
# ---------------------------------------------------------------------------


def test_data_mock(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock"])
    assert r.exit_code == 0, r.output
    assert "bars" in r.output.lower() or "close" in r.output.lower() or "AAPL" in r.output


def test_data_mock_json(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["data", "AAPL", "--provider", "mock", "--format", "json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["provider"] == "mock"
    assert payload["bars"] > 0
    assert len(payload["close"]) == payload["bars"]


def test_data_does_not_use_network_providers_in_suite() -> None:
    """Guard: this module must never invoke non-mock data providers."""
    src = Path(__file__).read_text(encoding="utf-8")
    for line in src.splitlines():
        if "invoke" not in line:
            continue
        assert not re.search(r"--provider[\"',\s]+(yahoo|ccxt|alphavantage)", line)
        if "--provider" in line:
            assert "mock" in line


# ---------------------------------------------------------------------------
# Unknown command
# ---------------------------------------------------------------------------


def test_unknown_command(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["this-command-does-not-exist-xyz"])
    assert r.exit_code != 0
