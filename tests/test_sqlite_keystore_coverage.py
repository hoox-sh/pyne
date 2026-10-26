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

"""Coverage for ``backend.middleware.key_store_sqlite.SQLiteKeyStore``."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.middleware.key_store_sqlite import SQLiteKeyStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteKeyStore:
    db = tmp_path / "keys.db"
    ks = SQLiteKeyStore(path=str(db))
    yield ks
    ks.close()


class TestSQLiteKeyStoreCRUD:
    def test_create_get_update_delete(self, store: SQLiteKeyStore) -> None:
        store.create("kid-1", "hash-1", "hobby", 100)
        by_hash = store.get_by_hash("hash-1")
        assert by_hash is not None
        assert by_hash["key_id"] == "kid-1"
        assert by_hash["key_hash"] == "hash-1"
        assert by_hash["tier"] == "hobby"
        assert by_hash["calls_used"] == 0
        assert by_hash["calls_limit"] == 100
        assert by_hash["created_at"] > 0
        assert by_hash["last_used"] == 0

        by_id = store.get_by_id("kid-1")
        assert by_id is not None
        assert by_id["key_hash"] == "hash-1"

        assert store.get_by_hash("missing") is None
        assert store.get_by_id("missing") is None

        store.update_calls("kid-1", 7, 123.5)
        updated = store.get_by_hash("hash-1")
        assert updated is not None
        assert updated["calls_used"] == 7
        assert updated["last_used"] == 123.5

        # update on unknown id is a silent no-op
        store.update_calls("ghost", 1, 1.0)
        assert store.get_by_id("ghost") is None

        assert store.delete_by_hash("hash-1") is True
        assert store.get_by_hash("hash-1") is None
        assert store.get_by_id("kid-1") is None
        assert store.delete_by_hash("hash-1") is False

    def test_multiple_keys_and_limits(self, store: SQLiteKeyStore) -> None:
        store.create("a", "ha", "free", 10)
        store.create("b", "hb", "pro", 0)
        assert store.get_by_id("a")["tier"] == "free"
        assert store.get_by_id("b")["calls_limit"] == 0
        store.update_calls("b", 3, 99.0)
        assert store.get_by_hash("hb")["calls_used"] == 3
        assert store.delete_by_hash("ha") is True
        assert store.get_by_id("b") is not None


class TestSQLiteKeyStoreMemoryAndPersistence:
    def test_memory_backend(self) -> None:
        ks = SQLiteKeyStore(path=":memory:")
        try:
            ks.create("m1", "mh", "hobby", 5)
            assert ks.get_by_hash("mh")["key_id"] == "m1"
            assert ks.delete_by_hash("mh") is True
        finally:
            ks.close()

    def test_file_persists_across_instances(self, tmp_path: Path) -> None:
        path = str(tmp_path / "persist.db")
        ks1 = SQLiteKeyStore(path=path)
        ks1.create("p1", "ph", "pro", 50)
        ks1.update_calls("p1", 2, 10.0)
        ks1.close()

        ks2 = SQLiteKeyStore(path=path)
        try:
            rec = ks2.get_by_id("p1")
            assert rec is not None
            assert rec["key_hash"] == "ph"
            assert rec["calls_used"] == 2
            assert rec["last_used"] == 10.0
            assert rec["tier"] == "pro"
        finally:
            ks2.close()

    def test_duplicate_hash_raises(self, store: SQLiteKeyStore) -> None:
        store.create("k1", "same", "hobby", 1)
        with pytest.raises(Exception):
            store.create("k2", "same", "hobby", 1)
