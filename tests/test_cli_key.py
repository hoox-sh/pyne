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

"""CLI tests for ``pyne key create``.

Every test points ``API_KEY_STORE`` / ``API_KEY_STORE_SQLITE`` at ``tmp_path``
and resets the process-local store singleton, so no test can mint into a real
key store (or into the repo).
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys

from collections.abc import Iterator
from pathlib import Path

import pytest

from click.testing import CliRunner
from click.testing import Result

from pynescript.__main__ import cli


_ADMIN_TOKEN = "test-admin-token-for-key-cli"
_RAW_KEY_RE = re.compile(r"pyn_[A-Za-z0-9_-]+")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def json_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the JSON backend at a temp file and drop the cached singleton."""
    from backend.middleware.auth import reset_key_store

    store_path = tmp_path / "api_keys.json"
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(store_path))
    monkeypatch.delenv("API_KEY_STORE_SQLITE", raising=False)
    reset_key_store()
    yield store_path
    reset_key_store()


@pytest.fixture
def sqlite_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the SQLite backend at a temp DB and drop the cached singleton."""
    from backend.middleware.auth import reset_key_store

    db_path = tmp_path / "api_keys.db"
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("API_KEY_STORE_SQLITE", str(db_path))
    reset_key_store()
    yield db_path
    reset_key_store()


def _mint(runner: CliRunner, *args: str) -> Result:
    return runner.invoke(cli, ["key", "create", *args])


def _raw_key(result: Result) -> str:
    match = _RAW_KEY_RE.search(result.output)
    assert match is not None, result.output
    return match.group(0)


def test_key_group_registered(runner: CliRunner) -> None:
    """``pyne --help`` lists the group and ``pyne key --help`` lists ``create``."""
    top = runner.invoke(cli, ["--help"])
    assert top.exit_code == 0, top.output
    assert "key" in top.output

    group = runner.invoke(cli, ["key", "--help"])
    assert group.exit_code == 0, group.output
    assert "create" in group.output


def test_key_create_mints_key(
    runner: CliRunner,
    json_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``ADMIN_TOKEN`` set the key is minted, persisted, and shown once."""
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)

    result = _mint(runner)

    assert result.exit_code == 0, result.output
    raw_key = _raw_key(result)
    assert raw_key.startswith("pyn_")
    assert result.output.count(raw_key) == 1
    assert "hobby" in result.output
    assert "Store this API key securely. It will not be shown again." in result.output
    assert json_store.exists()

    from backend.middleware.auth import get_key_store

    record = get_key_store().get_key(raw_key)
    assert record is not None
    assert record.tier == "hobby"
    assert record.key_id in result.output


def test_key_create_respects_tier(
    runner: CliRunner,
    json_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)

    result = _mint(runner, "--tier", "pro")

    assert result.exit_code == 0, result.output
    assert "pro" in result.output

    from backend.middleware.auth import get_key_store

    record = get_key_store().get_key(_raw_key(result))
    assert record is not None
    assert record.tier == "pro"


def test_key_create_refuses_without_admin_token(
    runner: CliRunner,
    json_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``ADMIN_TOKEN`` → non-zero exit, no secret printed, no key written."""
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    result = _mint(runner)

    assert result.exit_code != 0
    assert "ADMIN_TOKEN" in result.output
    assert "pyn_" not in result.output
    assert not json_store.exists()


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_key_create_refuses_blank_admin_token(
    runner: CliRunner,
    json_store: Path,
    monkeypatch: pytest.MonkeyPatch,
    blank: str,
) -> None:
    """Set-but-empty is treated as unset, exactly like the HTTP decorator."""
    monkeypatch.setenv("ADMIN_TOKEN", blank)

    result = _mint(runner)

    assert result.exit_code != 0
    assert "ADMIN_TOKEN is not set" in result.output
    assert "pyn_" not in result.output
    assert not json_store.exists()


def test_key_create_rejects_unknown_tier(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Click's ``Choice`` rejects anything outside the five tiers (exit 2)."""
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)

    result = _mint(runner, "--tier", "platinum")

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "pyn_" not in result.output


def test_key_create_json_payload(
    runner: CliRunner,
    json_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--json`` emits exactly ``{status, api_key, key_id, tier}``."""
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)

    result = _mint(runner, "--tier", "team", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == {"status", "api_key", "key_id", "tier"}
    assert payload["status"] == "success"
    assert payload["tier"] == "team"
    assert payload["api_key"].startswith("pyn_")
    assert payload["key_id"]

    from backend.middleware.auth import get_key_store

    assert get_key_store().get_key(payload["api_key"]) is not None


def test_key_create_sqlite_is_hash_only(
    runner: CliRunner,
    sqlite_store: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SQLite backend stores a PBKDF2 hash, never the raw secret."""
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)

    result = _mint(runner, "--tier", "hobby")

    assert result.exit_code == 0, result.output
    raw_key = _raw_key(result)

    with sqlite3.connect(sqlite_store) as conn:
        rows = conn.execute("SELECT key_hash, tier FROM api_keys").fetchall()
    assert len(rows) == 1
    key_hash, tier = rows[0]
    assert tier == "hobby"
    assert key_hash.startswith("v2:")
    assert key_hash != raw_key
    assert raw_key.encode() not in sqlite_store.read_bytes()

    # Lookup by raw secret still works: the hash is the only stored material.
    from backend.middleware.auth import get_key_store

    assert get_key_store().get_key(raw_key) is not None


def test_key_create_without_pro_backend(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pip install without ``backend/`` fails cleanly, not with a traceback."""
    monkeypatch.setenv("ADMIN_TOKEN", _ADMIN_TOKEN)
    monkeypatch.setitem(sys.modules, "backend.middleware.auth", None)

    result = _mint(runner)

    assert result.exit_code != 0
    assert "Pro backend" in result.output
    assert "pyn_" not in result.output
    assert not isinstance(result.exception, ModuleNotFoundError)
