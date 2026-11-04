# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Redis runner store (PYNE_RUNNER_STORE_BACKEND=redis) — fake-client unit + API tests."""

from __future__ import annotations

from typing import Any

import pytest

from flask.testing import FlaskClient

import backend.runner.store_redis as store_redis_module

from backend.app import app
from backend.runner import store
from backend.runner.store import reset_store
from backend.runner.store_redis import RunnerRedisStore
from backend.runner.store_redis import _RedisTickLock


_PINE = """
//@version=6
indicator("redis-runner")
plot(close)
"""


class _Pipe:
    """Minimal redis pipeline over a dict store (str values)."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._ops: list[tuple] = []

    def hset(self, name: str, key: str, value: str) -> _Pipe:
        self._ops.append(("hset", name, key, value))
        return self

    def hdel(self, name: str, key: str) -> _Pipe:
        self._ops.append(("hdel", name, key))
        return self

    def delete(self, *keys: str) -> _Pipe:
        for key in keys:
            self._ops.append(("delete", key))
        return self

    def lpush(self, name: str, value: str) -> _Pipe:
        self._ops.append(("lpush", name, value))
        return self

    def ltrim(self, name: str, start: int, end: int) -> _Pipe:
        self._ops.append(("ltrim", name, start, end))
        return self

    def execute(self) -> list[Any]:
        out: list[Any] = []
        for op in self._ops:
            kind = op[0]
            if kind == "hset":
                _, name, key, value = op
                self._data.setdefault(name, {})[key] = value
                out.append(1)
            elif kind == "hdel":
                bucket = self._data.get(op[1], {})
                out.append(1 if bucket.pop(op[2], None) is not None else 0)
            elif kind == "delete":
                out.append(1 if self._data.pop(op[1], None) is not None else 0)
            elif kind == "lpush":
                self._data.setdefault(op[1], []).insert(0, op[2])
                out.append(len(self._data[op[1]]))
            elif kind == "ltrim":
                lst = self._data.setdefault(op[1], [])
                start, end = op[2], op[3]
                if start == 0:
                    del lst[end + 1 :]
                out.append(True)
        self._ops.clear()
        return out


class FakeRedis:
    """In-memory stand-in for redis.Redis(decode_responses=True)."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    def pipeline(self) -> _Pipe:
        return _Pipe(self.data)

    def hset(self, name: str, key: str, value: str) -> int:
        self.data.setdefault(name, {})[key] = value
        return 1

    def hget(self, name: str, key: str) -> str | None:
        return self.data.get(name, {}).get(key)

    def hgetall(self, name: str) -> dict[str, str]:
        return dict(self.data.get(name, {}))

    def hdel(self, name: str, key: str) -> int:
        return 1 if self.data.get(name, {}).pop(key, None) is not None else 0

    def delete(self, *keys: str) -> int:
        n = 0
        for key in keys:
            if self.data.pop(key, None) is not None:
                n += 1
        return n

    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> bool | None:
        if nx and name in self.data:
            return None
        self.data[name] = value
        return True

    def get(self, name: str) -> str | None:
        return self.data.get(name)

    def lpush(self, name: str, value: str) -> int:
        self.data.setdefault(name, []).insert(0, value)
        return len(self.data[name])

    def ltrim(self, name: str, start: int, end: int) -> bool:
        lst = self.data.setdefault(name, [])
        if start == 0:
            del lst[end + 1 :]
        return True

    def lrange(self, name: str, start: int, end: int) -> list[str]:
        return list(self.data.get(name, []))[start : end + 1 if end >= 0 else None]


@pytest.fixture
def redis_store(monkeypatch) -> RunnerRedisStore:
    """Facade on the redis backend, backed by one shared FakeRedis."""
    client = FakeRedis()
    monkeypatch.setenv("PYNE_RUNNER_STORE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6399/0")
    monkeypatch.setattr(
        store_redis_module,
        "RunnerRedisStore",
        lambda **_kwargs: RunnerRedisStore(client=client),
    )
    reset_store()
    yield client
    reset_store()


def _body(**extra) -> dict[str, Any]:
    body = {
        "id": "sma-bot",
        "script": _PINE,
        "symbol": "TEST",
        "timeframe": "1d",
        "mode": "interpret",
        "data_source": "mock",
        "max_bars": 80,
        "enabled": True,
    }
    body.update(extra)
    return body


class TestRedisStoreUnit:
    def test_scripts_registry_roundtrip(self, redis_store: FakeRedis):
        rec = store.put_script(_body())
        assert rec["id"] == "sma-bot"
        assert "plot(close)" in rec["script"]

        got = store.get_script("sma-bot")
        assert got is not None
        assert "plot(close)" in got["script"]

        listed = store.list_scripts(include_source=False)
        assert len(listed) == 1 and "script" not in listed[0]

        assert store.list_enabled()[0]["id"] == "sma-bot"
        assert store.set_enabled("sma-bot", enabled=False) is True
        assert store.list_enabled() == []
        assert store.set_enabled("nope", enabled=True) is False

        assert store.delete_script("sma-bot") is True
        assert store.get_script("sma-bot") is None
        assert store.delete_script("sma-bot") is False

    def test_cron_state_merge_semantics(self, redis_store: FakeRedis):
        store.put_cron_state("sma-bot", {"last_bar_time": 123, "last_status": "ok", "last_alerts": 2})
        # Partial patch must not wipe earlier fields.
        store.put_cron_state("sma-bot", {"last_status": "error", "last_error": "fetch_failed"})
        state = store.get_cron_state("sma-bot")
        assert state["last_bar_time"] == 123
        assert state["last_alerts"] == 2
        assert state["last_status"] == "error"
        assert state["last_run_at"] > 0

        # Unknown script returns defaults.
        fresh = store.get_cron_state("unknown")
        assert fresh["last_bar_time"] == 0 and fresh["consecutive_errors"] == 0

    def test_history_caps_and_listing(self, redis_store: FakeRedis):
        for i in range(3):
            store.record_run({"script_id": "a", "ts": 1000 + i, "status": "ok", "alerts": i})
        store.record_run({"script_id": "b", "ts": 2000, "status": "error", "reason": "fetch_failed"})

        runs = store.list_runs()
        assert [r["ts"] for r in runs] == [2000, 1002, 1001, 1000]
        assert runs[0]["reason"] == "fetch_failed"

        only_a = store.list_runs("a", limit=2)
        assert [r["ts"] for r in only_a] == [1002, 1001]

        # Per-script cap 100.
        for i in range(150):
            store.record_run({"script_id": "a", "ts": 3000 + i, "status": "ok"})
        assert len(store.list_runs("a", limit=500)) == 100

        # Global cap 1000.
        for i in range(1200):
            store.record_run({"script_id": "c", "ts": 4000 + i, "status": "ok"})
        assert len(store.list_runs(limit=500)) == 500
        assert len(redis_store.data["pyne:runner:history"]) == 1000

        store.record_run({"script_id": "", "status": "ok"})  # ignored

    def test_tick_lock_setnx(self, redis_store: FakeRedis):
        s1 = RunnerRedisStore(client=redis_store)
        s2 = RunnerRedisStore(client=redis_store)

        first = s1.acquire_tick_lock()
        assert first is not None
        # A second holder is refused while the token lives.
        assert s2.acquire_tick_lock() is None
        first.release()

        second = s2.acquire_tick_lock()
        assert second is not None
        second.release()

        # A foreign token must never delete another holder's lock.
        third = s1.acquire_tick_lock()
        assert third is not None
        _RedisTickLock(redis_store, "not-the-token").release()
        assert redis_store.get("pyne:runner:ticklock") is not None
        third.release()
        assert redis_store.get("pyne:runner:ticklock") is None

    def test_validation_errors_raise(self, redis_store: FakeRedis):
        with pytest.raises(ValueError):
            store.put_script(_body(id="../evil"))
        with pytest.raises(ValueError):
            store.put_script(_body(timeframe="7h"))
        with pytest.raises(ValueError):
            store.put_script({"id": "x"})

    def test_redis_backend_requires_redis_url(self, monkeypatch):
        monkeypatch.setenv("PYNE_RUNNER_STORE_BACKEND", "redis")
        monkeypatch.delenv("REDIS_URL", raising=False)
        reset_store()
        try:
            with pytest.raises(RuntimeError, match="REDIS_URL"):
                store.list_scripts()
        finally:
            reset_store()


class TestRedisBackendEndToEnd:
    @pytest.fixture
    def client(self, redis_store: FakeRedis, monkeypatch) -> FlaskClient:
        app.config["TESTING"] = True
        monkeypatch.setenv("PYNE_RUNNER", "1")
        monkeypatch.setenv("PYNE_RUNNER_SCHEDULER", "0")
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        with app.test_client() as client:
            yield client

    def test_full_flow_over_redis(self, client: FlaskClient, redis_store: FakeRedis):
        health = client.get("/health")
        assert health.json["features"]["script_runner_store"] == "redis"

        resp = client.post("/scripts", json=_body())
        assert resp.status_code == 201, resp.json
        assert "plot(close)" in resp.json["script"]["script"]

        listed = client.get("/scripts")
        assert listed.json["count"] == 1
        assert "script" not in listed.json["scripts"][0]

        ticked = client.post("/cron/run", json={"force": True})
        assert ticked.status_code == 200, ticked.json
        assert ticked.json["jobs"][0]["status"] == "ok"

        # Cron state and history live in redis, not SQLite.
        assert "pyne:runner:cron" in redis_store.data
        history = client.get("/cron/history")
        assert history.json["count"] == 1
        assert history.json["runs"][0]["script_id"] == "sma-bot"

        deleted = client.delete("/scripts/sma-bot")
        assert deleted.status_code == 200
        assert "pyne:runner:scripts" not in redis_store.data or not redis_store.data["pyne:runner:scripts"]
