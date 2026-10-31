# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit coverage for Redis API key store with an in-memory fake client."""

from __future__ import annotations

from typing import Any

import pytest

from backend.middleware.key_store_redis import RedisKeyStore
from backend.middleware.key_store_redis import _decode_record
from backend.middleware.key_store_redis import _encode


def _apply_hset(store: dict[str, dict[str, str]], name: str, *args: Any, mapping: dict[str, str] | None = None) -> None:
    bucket = store.setdefault(name, {})
    if mapping:
        bucket.update({str(k): str(v) for k, v in mapping.items()})
        return
    if len(args) >= 2:
        bucket[str(args[0])] = str(args[1])


class _Pipe:
    def __init__(self, store: dict[str, dict[str, str]]) -> None:
        self._store = store
        self._ops: list[tuple] = []

    def hset(self, name: str, *args: Any, mapping: dict[str, str] | None = None, **kwargs: Any) -> _Pipe:
        self._ops.append(("hset", name, args, mapping or kwargs or None))
        return self

    def delete(self, key: str) -> _Pipe:
        self._ops.append(("delete", key))
        return self

    def hdel(self, key: str, field: str) -> _Pipe:
        self._ops.append(("hdel", key, field))
        return self

    def execute(self) -> list[Any]:
        out: list[Any] = []
        for op in self._ops:
            if op[0] == "hset":
                _, name, args, mapping = op
                _apply_hset(self._store, name, *args, mapping=mapping)
                out.append(1)
            elif op[0] == "delete":
                out.append(1 if self._store.pop(op[1], None) is not None else 0)
            elif op[0] == "hdel":
                bucket = self._store.get(op[1], {})
                out.append(1 if bucket.pop(op[2], None) is not None else 0)
        self._ops.clear()
        return out


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, str]] = {}

    def pipeline(self) -> _Pipe:
        return _Pipe(self.data)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.data.get(key, {}))

    def hget(self, key: str, field: str) -> str | None:
        return self.data.get(key, {}).get(field)

    def hset(self, name: str, *args: Any, mapping: dict[str, str] | None = None, **kwargs: Any) -> int:
        _apply_hset(self.data, name, *args, mapping=mapping or (kwargs or None))
        return 1


def test_encode_decode() -> None:
    assert _encode(3) == "3"
    assert _encode(1.5) == "1.5"
    assert _encode("abc") == "abc"
    raw = {
        "key_id": "k1",
        "key_hash": "hh",
        "tier": "pro",
        "calls_used": "2",
        "calls_limit": "100",
        "created_at": "1.0",
        "last_used": "0.0",
    }
    rec = _decode_record(raw)
    assert rec["calls_used"] == 2
    assert rec["calls_limit"] == 100
    assert rec["tier"] == "pro"


def test_create_get_update_delete() -> None:
    client = FakeRedis()
    store = RedisKeyStore(client=client)
    store.create("kid", "hash1", "free", 50)
    rec = store.get_by_hash("hash1")
    assert rec is not None
    assert rec["key_id"] == "kid"
    assert rec["tier"] == "free"
    assert rec["calls_used"] == 0
    assert store.get_by_id("kid")["key_hash"] == "hash1"
    assert store.get_by_id("missing") is None
    assert store.get_by_hash("nope") is None

    store.update_calls("kid", 7, 123.0)
    rec2 = store.get_by_hash("hash1")
    assert rec2["calls_used"] == 7
    assert rec2["last_used"] == 123.0

    store.update_calls("ghost", 1, 1.0)  # no-op
    assert store.delete_by_hash("hash1") is True
    assert store.get_by_hash("hash1") is None
    assert store.get_by_id("kid") is None
    assert store.delete_by_hash("hash1") is False
    store.close()  # no-op


def test_import_error_without_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "redis" or name.startswith("redis."):
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    with pytest.raises(ImportError, match="redis"):
        RedisKeyStore(url="redis://localhost:6379/0")
