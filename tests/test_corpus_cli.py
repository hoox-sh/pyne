# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""CLI smoke tests for ``pyne corpus``."""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from click.testing import CliRunner

from pynescript.__main__ import cli
from pynescript.util.corpus_runtime import EXPECTED_FAIL_RELS
from pynescript.util.corpus_runtime import corpus_rel_path
from pynescript.util.corpus_runtime import is_expected_fail
from pynescript.util.corpus_runtime import resolve_data_root
from pynescript.util.corpus_runtime import run_corpus


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_corpus_help(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["corpus", "--help"])
    assert r.exit_code == 0
    assert "corpus" in r.output.lower()
    assert "run" in r.output
    assert "list" in r.output


def test_corpus_run_help(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["corpus", "run", "--help"])
    assert r.exit_code == 0
    assert "--sets" in r.output
    assert "--mode" in r.output
    assert "compile" in r.output


def test_root_help_mentions_corpus(runner: CliRunner) -> None:
    r = runner.invoke(cli, ["--help"])
    assert r.exit_code == 0
    assert "corpus" in r.output


def test_corpus_list_json(runner: CliRunner, tmp_path: Path) -> None:
    (tmp_path / "set01" / "indicators").mkdir(parents=True)
    (tmp_path / "set01" / "indicators" / "a.pine").write_text(
        '//@version=5\nindicator("a")\nplot(close)\n', encoding="utf-8"
    )
    (tmp_path / "set02").mkdir()
    r = runner.invoke(
        cli,
        ["corpus", "list", "--data", str(tmp_path), "--json", "--plain"],
    )
    assert r.exit_code == 0, r.output
    rows = json.loads(r.output)
    by_name = {row["set"]: row["count"] for row in rows}
    assert by_name["set01"] == 1
    assert by_name["set02"] == 0


def test_corpus_list_plain(runner: CliRunner, tmp_path: Path) -> None:
    (tmp_path / "set01").mkdir()
    (tmp_path / "set01" / "x.pine").write_text('//@version=5\nindicator("x")\nplot(1)\n', encoding="utf-8")
    r = runner.invoke(cli, ["corpus", "list", "--data", str(tmp_path), "--plain"])
    assert r.exit_code == 0, r.output
    assert "set01" in r.output
    assert "1" in r.output


def test_corpus_run_parse_mini_set(runner: CliRunner, tmp_path: Path) -> None:
    """End-to-end ``pyne corpus run`` on a tiny synthetic set (parse mode)."""
    pine_dir = tmp_path / "data" / "set01" / "indicators"
    pine_dir.mkdir(parents=True)
    (pine_dir / "ok.pine").write_text('//@version=5\nindicator("ok")\nplot(close)\n', encoding="utf-8")
    cache = tmp_path / "cache"
    out = cache / "mini.csv"
    r = runner.invoke(
        cli,
        [
            "corpus",
            "run",
            "--sets",
            "set01",
            "--mode",
            "parse",
            "--data",
            str(tmp_path / "data"),
            "--cache",
            str(cache),
            "--out",
            str(out),
            "--workers",
            "1",
            "--plain",
            "--no-strict",
        ],
    )
    assert r.exit_code == 0, r.output
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "OK" in text
    assert "ok.pine" in text
    assert out.with_name("mini_summary.txt").exists()


def test_run_corpus_api_parse(tmp_path: Path) -> None:
    data = tmp_path / "tests_data"
    d = data / "set01"
    d.mkdir(parents=True)
    (d / "a.pine").write_text('//@version=5\nindicator("a")\nplot(1)\n', encoding="utf-8")
    out = tmp_path / "out.csv"
    result = run_corpus(
        sets=["set01"],
        mode="parse",
        workers=1,
        out=out,
        data_root=data,
        cache_dir=tmp_path / "cache",
        echo=lambda _m: None,
    )
    assert result.ok == 1
    assert result.fail == 0
    assert result.exit_code == 0


def test_is_expected_fail_helpers() -> None:
    rel = next(iter(EXPECTED_FAIL_RELS))
    assert is_expected_fail(rel, "Parse Error: boom")
    assert not is_expected_fail(rel, "")
    assert not is_expected_fail("set01/indicators/nope.pine", "Parse Error: x")


def test_corpus_rel_path_and_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYNE_CORPUS_DATA", str(tmp_path))
    assert resolve_data_root() == tmp_path.resolve()
    f = tmp_path / "set03" / "x.pine"
    f.parent.mkdir(parents=True)
    f.write_text("x", encoding="utf-8")
    assert corpus_rel_path(str(f), tmp_path) == "set03/x.pine"
