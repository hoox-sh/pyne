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

"""Unit tests for ``pynescript.util.pine_facade`` (no live pine-facade traffic)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from pynescript.__main__ import cli
from pynescript.util.pine_facade import _meta_kind
from pynescript.util.pine_facade import _meta_name
from pynescript.util.pine_facade import _normalize_filename
from pynescript.util.pine_facade import assign_filenames
from pynescript.util.pine_facade import download_builtin_scripts
from pynescript.util.pine_facade import main as facade_main
from pynescript.util.pine_facade import render_catalog


CATALOG = [
    {"scriptName": "Relative Strength Index", "scriptIdPart": "STD;RSI", "version": "52"},
    {"scriptName": "Supertrend", "scriptIdPart": "STD;Supertrend", "version": "12"},
    {"scriptName": "Strategy Example", "scriptIdPart": "STD;Strategy", "version": "3"},
]


def test_normalize_filename_matches_builtin_corpus_names() -> None:
    assert _normalize_filename("Average Directional Index") == "average_directional_index.pine"
    assert _normalize_filename("Bull Bear Power") == "bull_bear_power.pine"
    assert _normalize_filename("Chande/Kroll Stop") == "chande_kroll_stop.pine"
    assert _normalize_filename("Kaufman's Adaptive") == "kaufmans_adaptive.pine"


def test_assign_filenames_suffixes_version_on_clash() -> None:
    catalog = [
        {"scriptName": "Pivot Points High Low", "version": "22.0"},
        {"scriptName": "Pivot Points High Low", "version": "11.0"},
        {"scriptName": "RSI", "version": "46.0"},
    ]
    names = [fn for _meta, fn in assign_filenames(catalog)]
    assert names == [
        "pivot_points_high_low.pine",
        "pivot_points_high_low_v11.pine",
        "rsi.pine",
    ]


def test_meta_name_unescapes_html_entities() -> None:
    assert _meta_name({"scriptName": "Kaufman&#039;s Adaptive Moving Average"}) == (
        "Kaufman's Adaptive Moving Average"
    )


def test_meta_kind_falls_back_to_name() -> None:
    assert _meta_kind({}, "Strategy Example") == "strategy"
    assert _meta_kind({}, "RSI") == "indicator"
    assert _meta_kind({"extra": {"kind": "library"}}, "Math") == "library"
    assert _meta_kind({"extra": {"kind": "study"}}, "Volume") == "indicator"


def test_render_catalog_plain(capsys, tmp_path: Path) -> None:
    render_catalog(CATALOG, tmp_path, worker_count=4, existing=set(), console=None)
    out = capsys.readouterr().out
    assert "pine facade" in out
    assert "Relative Strength Index" in out
    assert "Supertrend" in out
    assert "strategy" in out


def test_download_dry_run_does_not_fetch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pynescript.util.pine_facade.list_builtin_scripts",
        lambda session=None: list(CATALOG),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("get_script must not run in dry-run")

    monkeypatch.setattr("pynescript.util.pine_facade.get_script", _boom)
    summary = download_builtin_scripts(tmp_path, dry_run=True, confirm=False, plain=True)
    assert summary["total"] == 3
    assert summary["saved"] == 0
    assert list(tmp_path.glob("*.pine")) == []


def test_download_writes_and_can_skip_existing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "pynescript.util.pine_facade.list_builtin_scripts",
        lambda session=None: list(CATALOG),
    )

    def _fake_get(script_id_part, version, session=None):
        return {"source": f"//@version=5\nindicator(\"{script_id_part}\")\n"}

    monkeypatch.setattr("pynescript.util.pine_facade.get_script", _fake_get)
    first = download_builtin_scripts(
        tmp_path, max_workers=1, confirm=False, plain=True
    )
    assert first["saved"] == 3
    assert first["failed"] == 0
    pines = sorted(p.name for p in tmp_path.glob("*.pine"))
    assert pines == [
        "relative_strength_index.pine",
        "strategy_example.pine",
        "supertrend.pine",
    ]
    second = download_builtin_scripts(
        tmp_path, max_workers=1, confirm=False, plain=True, skip_existing=True
    )
    assert second["saved"] == 0
    assert second["skipped"] == 3


def test_module_help_exits_zero() -> None:
    try:
        code = facade_main(["--help"])
    except SystemExit as exc:
        code = exc.code
    assert code == 0


def test_cli_download_builtins_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["download-builtins", "--help"])
    assert result.exit_code == 0
    assert "--list" in result.output
    assert "--yes" in result.output
    assert "catalog" in result.output.lower() or "builtin" in result.output.lower()
