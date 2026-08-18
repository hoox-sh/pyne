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

"""Free-tier abuse guards and hash-only key store (audit 2026-08-10 Wave A)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.middleware.auth import APIKeyStore
from backend.middleware.auth import reset_key_store
from backend.middleware.free_limits import free_data_source_allowed
from backend.middleware.free_limits import free_tier_limits_enabled
from backend.middleware.free_limits import max_free_bars
from backend.middleware.free_limits import validate_free_run_bounds


def test_free_tier_limits_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("FREE_TIER_LIMITS", raising=False)
    assert free_tier_limits_enabled() is False
    assert validate_free_run_bounds(ohlcv=[{"close": 1}] * 10_001) is None
    assert validate_free_run_bounds(script="x" * (256 * 1024 + 1)) is None
    assert validate_free_run_bounds(data_source="ccxt") is None


def test_free_tier_limits_opt_in_truthy(monkeypatch) -> None:
    for raw in ("1", "true", "YES", "On"):
        monkeypatch.setenv("FREE_TIER_LIMITS", raw)
        assert free_tier_limits_enabled() is True
    for raw in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("FREE_TIER_LIMITS", raw)
        assert free_tier_limits_enabled() is False


def test_free_data_source_allowlist() -> None:
    assert free_data_source_allowed(None)
    assert free_data_source_allowed("")
    assert free_data_source_allowed("chart")
    assert free_data_source_allowed("mock")
    assert not free_data_source_allowed("ccxt")
    assert not free_data_source_allowed("yahoo")
    assert not free_data_source_allowed("alphavantage")


def test_validate_free_run_bounds_bars(monkeypatch) -> None:
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    monkeypatch.setenv("FREE_MAX_BARS", "10")
    # Re-read via function (reads env each call)
    assert max_free_bars() == 10
    err = validate_free_run_bounds(ohlcv=[{"close": 1}] * 11)
    assert err is not None
    body, code = err
    assert code == 413
    assert body["code"] == "TOO_MANY_BARS"


def test_validate_free_run_bounds_script(monkeypatch) -> None:
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    monkeypatch.setenv("FREE_MAX_SCRIPT_CHARS", "20")
    err = validate_free_run_bounds(script="x" * 21)
    assert err is not None
    body, code = err
    assert code == 413
    assert body["code"] == "SCRIPT_TOO_LARGE"


def test_validate_free_run_bounds_data_source(monkeypatch) -> None:
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    err = validate_free_run_bounds(data_source="ccxt")
    assert err is not None
    body, code = err
    assert code == 403
    assert body["code"] == "DATA_SOURCE_FORBIDDEN"


def test_json_key_store_is_hash_only(tmp_path: Path) -> None:
    """Raw secrets must never appear as JSON object keys or values on disk."""
    store_path = tmp_path / "keys.json"
    store = APIKeyStore(store_path=str(store_path))
    raw, key_id = store.create_key("hobby")
    assert raw.startswith("pyn_")
    assert key_id

    on_disk = json.loads(store_path.read_text(encoding="utf-8"))
    blob = store_path.read_text(encoding="utf-8")
    assert raw not in blob
    assert raw not in on_disk
    # Keys are SHA-256 hex digests
    for k, rec in on_disk.items():
        assert len(k) == 64
        assert rec["key_hash"] == k
        assert rec["key_id"] == key_id

    # Round-trip validate via hash lookup
    found = store.validate_key(raw)
    assert found is not None
    assert found.key_id == key_id

    assert store.revoke_key(raw) is True
    assert store.validate_key(raw) is None


def test_json_key_store_migrates_legacy_raw_keys(tmp_path: Path) -> None:
    """Legacy files keyed by raw secret are rewritten hash-only on load."""
    store_path = tmp_path / "legacy.json"
    raw = "pyn_legacy_secret_for_migration_test_only"
    import hashlib

    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_id = key_hash[:12]
    store_path.write_text(
        json.dumps(
            {
                raw: {
                    "key_id": key_id,
                    "key_hash": key_hash,
                    "tier": "hobby",
                    "calls_used": 0,
                    "calls_limit": 5000,
                    "created_at": 1.0,
                    "last_used": 0.0,
                }
            }
        ),
        encoding="utf-8",
    )
    store = APIKeyStore(store_path=str(store_path))
    assert store.validate_key(raw) is not None
    rewritten = store_path.read_text(encoding="utf-8")
    assert raw not in rewritten
    data = json.loads(rewritten)
    assert key_hash in data


def test_run_rejects_ssrf_webhook(client, monkeypatch) -> None:
    """POST /run returns 400 for private webhook_url."""
    monkeypatch.delenv("ALERT_WEBHOOK_ALLOW_PRIVATE", raising=False)
    bars = [
        {"open": 1, "high": 1, "low": 1, "close": 1, "time": 1, "volume": 1},
        {"open": 1, "high": 1, "low": 1, "close": 1, "time": 2, "volume": 1},
    ]
    script = '//@version=5\nindicator("t")\nplot(close)\n'
    resp = client.post(
        "/run",
        json={
            "script": script,
            "data": bars,
            "mode": "interpret",
            "webhook_url": "http://127.0.0.1/hook",
        },
    )
    assert resp.status_code == 400
    assert resp.json["code"] == "WEBHOOK_URL_BLOCKED"


def test_run_rejects_too_many_bars(client, monkeypatch) -> None:
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    monkeypatch.setenv("FREE_MAX_BARS", "3")
    bars = [
        {"open": 1, "high": 1, "low": 1, "close": 1, "time": i, "volume": 1}
        for i in range(5)
    ]
    script = '//@version=5\nindicator("t")\nplot(close)\n'
    resp = client.post(
        "/run",
        json={"script": script, "data": bars, "mode": "interpret"},
    )
    assert resp.status_code == 413
    assert resp.json["code"] == "TOO_MANY_BARS"


def test_health_reports_free_tier_limits_flag(client, monkeypatch) -> None:
    monkeypatch.delenv("FREE_TIER_LIMITS", raising=False)
    off = client.get("/health")
    assert off.status_code == 200
    assert off.json["features"]["free_tier_limits"] is False
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    on = client.get("/health")
    assert on.json["features"]["free_tier_limits"] is True


def test_run_skips_bar_cap_when_limits_off(client, monkeypatch) -> None:
    monkeypatch.delenv("FREE_TIER_LIMITS", raising=False)
    monkeypatch.setenv("FREE_MAX_BARS", "3")
    bars = [
        {"open": 1, "high": 1, "low": 1, "close": 1, "time": i, "volume": 1}
        for i in range(5)
    ]
    script = '//@version=5\nindicator("t")\nplot(close)\n'
    resp = client.post(
        "/run",
        json={"script": script, "data": bars, "mode": "interpret"},
    )
    assert resp.status_code != 413
    assert resp.json.get("code") != "TOO_MANY_BARS"


def test_run_rejects_external_data_source(client, monkeypatch) -> None:
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    bars = [
        {"open": 1, "high": 1, "low": 1, "close": 1, "time": 1, "volume": 1},
        {"open": 1, "high": 1, "low": 1, "close": 1, "time": 2, "volume": 1},
    ]
    script = '//@version=5\nindicator("t")\nplot(close)\n'
    resp = client.post(
        "/run",
        json={
            "script": script,
            "data": bars,
            "mode": "interpret",
            "data_source": "yahoo",
        },
    )
    assert resp.status_code == 403
    assert resp.json["code"] == "DATA_SOURCE_FORBIDDEN"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Minimal Flask test client with isolated key store.

    Rate/concurrency knobs are zeroed so tests that opt into
    ``FREE_TIER_LIMITS`` still do not trip IP/slot gates.
    """
    monkeypatch.setenv("ADMIN_TOKEN", "ci-test-admin-token")
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys.json"))
    monkeypatch.setenv("FREE_RATE_LIMIT", "0")
    monkeypatch.setenv("FREE_MAX_CONCURRENT", "0")
    reset_key_store()
    from backend.app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    reset_key_store()
