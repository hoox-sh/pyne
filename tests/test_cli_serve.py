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

"""CLI tests for ``pyne serve`` and ``pyne datafeed serve``.

The guided-install cases block the import and never call the real server.
The success cases replace ``main`` so Flask's dev server cannot bind a port.
"""

from __future__ import annotations

import builtins
import sys

from typing import Any

import pytest

from click.testing import CliRunner
from click.testing import Result

from pynescript.__main__ import cli


_PRO_INSTALL = "pip install 'hoox-pyne[pro]'"
_DATAFEED_INSTALL = "pip install 'hoox-pyne[datafeed]'"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def entry_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Replace both app entry points so a successful command cannot listen."""
    import backend.app as pro
    import backend.datafeed_app as feed

    calls = {"pro": 0, "datafeed": 0, "flask.run": 0}

    def pro_main() -> None:
        calls["pro"] += 1

    def feed_main() -> None:
        calls["datafeed"] += 1

    def flask_run(self: object, *args: object, **kwargs: object) -> None:
        calls["flask.run"] += 1

    monkeypatch.setattr(pro, "main", pro_main)
    monkeypatch.setattr(feed, "main", feed_main)
    monkeypatch.setattr(pro.Flask, "run", flask_run)
    monkeypatch.setattr(feed.Flask, "run", flask_run)
    return calls


def _shown(result: Result) -> str:
    """Stdout, stderr, and the exception text Click captured."""
    stderr = getattr(result, "stderr", None) or ""
    return f"{result.output}{stderr}{result.exception or ''}"


def _lists_command(output: str, name: str) -> bool:
    """True when Click's command table lists ``name`` (not a substring like ``server``)."""
    prefix = f"{name} "
    for line in output.splitlines():
        text = line.strip()
        if text == name or text.startswith(prefix):
            return True
    return False


def _block_module(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Make the next import of ``name`` raise ``ModuleNotFoundError``."""
    monkeypatch.setitem(sys.modules, name, None)


def _block_imports(monkeypatch: pytest.MonkeyPatch, blocked: set[str]) -> None:
    """Raise ``ModuleNotFoundError`` for the named top-level modules."""
    real_import = builtins.__import__

    def guarded(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        root = name.split(".", 1)[0]
        if root in blocked:
            raise ModuleNotFoundError(f"No module named {root!r}", name=root)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded)


def test_help_shows_serve_and_datafeed(runner: CliRunner) -> None:
    """``pyne --help`` lists both commands; datafeed help lists ``serve``."""
    top = runner.invoke(cli, ["--help"])
    assert top.exit_code == 0, top.output
    assert _lists_command(top.output, "serve")
    assert _lists_command(top.output, "datafeed")

    group = runner.invoke(cli, ["datafeed", "--help"])
    assert group.exit_code == 0, group.output
    assert _lists_command(group.output, "serve")

    bare = runner.invoke(cli, ["datafeed"])
    assert bare.exit_code == 0, bare.output
    assert _lists_command(bare.output, "serve")

    serve_help = runner.invoke(cli, ["serve", "--help"])
    assert serve_help.exit_code == 0, serve_help.output
    assert _PRO_INSTALL in serve_help.output

    feed_help = runner.invoke(cli, ["datafeed", "serve", "--help"])
    assert feed_help.exit_code == 0, feed_help.output
    assert _DATAFEED_INSTALL in feed_help.output


def test_serve_dry_run_names_existing_entry_without_listening(
    runner: CliRunner,
    entry_calls: dict[str, int],
) -> None:
    result = runner.invoke(cli, ["serve", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "backend.app:main" in result.output
    assert entry_calls == {"pro": 0, "datafeed": 0, "flask.run": 0}


def test_datafeed_dry_run_names_existing_entry_without_listening(
    runner: CliRunner,
    entry_calls: dict[str, int],
) -> None:
    result = runner.invoke(cli, ["datafeed", "serve", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "backend.datafeed_app:main" in result.output
    assert entry_calls == {"pro": 0, "datafeed": 0, "flask.run": 0}


def test_serve_delegates_to_backend_app_main(
    runner: CliRunner,
    entry_calls: dict[str, int],
) -> None:
    result = runner.invoke(cli, ["serve"])

    assert result.exit_code == 0, result.output
    assert entry_calls["pro"] == 1
    assert entry_calls["datafeed"] == 0
    assert entry_calls["flask.run"] == 0


def test_datafeed_serve_delegates_to_datafeed_app_main(
    runner: CliRunner,
    entry_calls: dict[str, int],
) -> None:
    result = runner.invoke(cli, ["datafeed", "serve"])

    assert result.exit_code == 0, result.output
    assert entry_calls["datafeed"] == 1
    assert entry_calls["pro"] == 0
    assert entry_calls["flask.run"] == 0


def _assert_guided(result: Result, install: str, calls: dict[str, int]) -> None:
    text = _shown(result)
    assert result.exit_code != 0, text
    assert install in text
    assert "Traceback" not in text
    assert not isinstance(result.exception, ModuleNotFoundError)
    assert calls["flask.run"] == 0
    assert calls["pro"] == 0
    assert calls["datafeed"] == 0


def test_serve_guides_when_backend_package_missing(
    runner: CliRunner,
    entry_calls: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_module(monkeypatch, "backend.app")

    result = runner.invoke(cli, ["serve"])

    _assert_guided(result, _PRO_INSTALL, entry_calls)


def test_serve_guides_when_pro_extra_missing(
    runner: CliRunner,
    entry_calls: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing Flask import is the [pro] extra, not a bare traceback."""
    monkeypatch.delitem(sys.modules, "backend.app", raising=False)
    _block_imports(monkeypatch, {"flask", "flask_cors", "gunicorn"})

    result = runner.invoke(cli, ["serve"])

    _assert_guided(result, _PRO_INSTALL, entry_calls)


def test_datafeed_serve_guides_when_backend_package_missing(
    runner: CliRunner,
    entry_calls: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_module(monkeypatch, "backend.datafeed_app")

    result = runner.invoke(cli, ["datafeed", "serve"])

    _assert_guided(result, _DATAFEED_INSTALL, entry_calls)


def test_datafeed_serve_guides_when_datafeed_extra_missing(
    runner: CliRunner,
    entry_calls: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "backend.datafeed_app", raising=False)
    _block_imports(monkeypatch, {"flask", "flask_sock", "ccxt"})

    result = runner.invoke(cli, ["datafeed", "serve"])

    _assert_guided(result, _DATAFEED_INSTALL, entry_calls)


def test_dry_run_still_guides_when_extra_missing(
    runner: CliRunner,
    entry_calls: dict[str, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--dry-run`` must not hide a missing extra behind a success exit."""
    _block_module(monkeypatch, "backend.app")
    _block_module(monkeypatch, "backend.datafeed_app")

    pro = runner.invoke(cli, ["serve", "--dry-run"])
    feed = runner.invoke(cli, ["datafeed", "serve", "--dry-run"])

    _assert_guided(pro, _PRO_INSTALL, entry_calls)
    _assert_guided(feed, _DATAFEED_INSTALL, entry_calls)
