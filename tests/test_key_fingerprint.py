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

"""Fast invalid-key rejection via the SHA-256 fingerprint index."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.middleware.auth import APIKeyStore
from backend.middleware.auth import reset_key_store
from backend.middleware.key_store_sqlite import SQLiteKeyStore


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_key_store()
    yield
    reset_key_store()


def test_new_keys_use_v2_prefix_and_fingerprint(tmp_path: Path) -> None:
    store = APIKeyStore(store_path=str(tmp_path / "keys.json"))
    raw, key_id = store.create_key("pro")
    assert raw.startswith("pyn_v2_")
    assert store.get_key(raw) is not None
    assert store.get_key(raw).key_id == key_id  # type: ignore[union-attr]
    assert store.get_key(raw).key_fingerprint  # type: ignore[union-attr]


def test_invalid_v2_key_skips_pbkdf2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = APIKeyStore(store_path=str(tmp_path / "keys.json"))
    raw, _key_id = store.create_key("pro")
    calls: list[str] = []
    real = APIKeyStore._hash_key

    def spy(key: str) -> str:
        calls.append(key)
        return real(key)

    monkeypatch.setattr(APIKeyStore, "_hash_key", staticmethod(spy))
    assert store.get_key("pyn_v2_definitely-not-a-real-key") is None
    assert calls == []

    assert store.get_key(raw) is not None
    assert calls == [raw]


def test_unknown_prefix_skips_pbkdf2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = APIKeyStore(store_path=str(tmp_path / "keys.json"))
    calls: list[str] = []
    monkeypatch.setattr(
        APIKeyStore,
        "_hash_key",
        staticmethod(lambda key: calls.append(key) or "unused"),
    )
    assert store.get_key("not-a-pyne-key") is None
    assert calls == []


def test_legacy_key_falls_back_to_pbkdf2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = APIKeyStore(store_path=str(tmp_path / "keys.json"))
    calls: list[str] = []
    real = APIKeyStore._hash_key
    monkeypatch.setattr(
        APIKeyStore,
        "_hash_key",
        staticmethod(lambda key: calls.append(key) or real(key)),
    )
    assert store.get_key("pyn_legacy-invalid") is None
    assert calls == ["pyn_legacy-invalid"]


def test_sqlite_fingerprint_index() -> None:
    ks = SQLiteKeyStore(path=":memory:")
    try:
        ks.create("kid", "hash", "pro", 100, key_fingerprint="fp")
        rec = ks.get_by_fingerprint("fp")
        assert rec is not None
        assert rec["key_id"] == "kid"
        assert rec["key_fingerprint"] == "fp"
        assert ks.get_by_fingerprint("missing") is None
        assert ks.delete_by_hash("hash") is True
        assert ks.get_by_fingerprint("fp") is None
    finally:
        ks.close()
