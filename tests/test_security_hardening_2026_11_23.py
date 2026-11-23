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

"""Regression tests for the 2026-11-23 hardening pass.

Covers the public-surface fixes that are easy to regress: proxy-aware client
IPs, auth/LSP throttles, owner-scoped datafeed sessions, library-source caps,
the calendar reset timestamp, and query-string key opt-in.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import pytest

from flask.testing import FlaskClient

from backend.middleware import free_limits
from backend.middleware.auth import APIKey
from backend.middleware.auth import reset_key_store


SCRIPT = '//@version=5\nindicator("t")\nplot(close)\n'


def _bars(n: int) -> list[dict[str, float | int]]:
    return [{"open": 1, "high": 1, "low": 1, "close": 1, "time": i, "volume": 1} for i in range(n)]


@pytest.fixture
def client(tmp_path, monkeypatch) -> FlaskClient:
    monkeypatch.setenv("ADMIN_TOKEN", "hardening-admin-token")
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys.json"))
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    monkeypatch.setenv("FREE_MAX_BARS", "10")
    monkeypatch.setenv("FREE_MAX_SCRIPT_CHARS", "1000")
    monkeypatch.setenv("FREE_MAX_CONCURRENT", "0")
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2")
    monkeypatch.setenv("AUTH_RATE_WINDOW_SEC", "60")
    monkeypatch.setenv("LSP_RATE_LIMIT", "2")
    monkeypatch.setenv("LSP_RATE_WINDOW_SEC", "60")
    free_limits._RATE._hits.clear()
    free_limits._AUTH_RATE._hits.clear()
    free_limits._LSP_RATE._hits.clear()
    free_limits._GATE._active = 0
    reset_key_store()

    from backend.app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    reset_key_store()


def _mint_key(client: FlaskClient, tier: str = "pro") -> dict[str, str]:
    resp = client.post(
        "/auth/create_key",
        json={"tier": tier},
        headers={"X-Admin-Token": "hardening-admin-token"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {
        "raw": resp.json["api_key"],
        "key_id": resp.json["key_id"],
        "headers": {"Authorization": f"Bearer {resp.json['api_key']}"},
    }


def test_reset_at_is_current_month_start() -> None:
    key = APIKey(key_id="k", key_hash="v2:test")
    expected = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    assert key._get_reset_time() == int(expected.timestamp())


def test_client_ip_uses_trusted_hops(monkeypatch) -> None:
    from backend.app import app

    with app.test_request_context(
        "/run",
        headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1", "X-Real-IP": "10.0.0.1"},
    ):
        assert free_limits.client_ip() == "10.0.0.1"
    with app.test_request_context("/run", headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}):
        assert free_limits.client_ip() == "10.0.0.1"
    with app.test_request_context("/run", environ_base={"REMOTE_ADDR": "10.0.0.2"}):
        assert free_limits.client_ip() == "10.0.0.2"


def test_query_api_key_is_opt_in(client: FlaskClient, monkeypatch) -> None:
    key = _mint_key(client)
    resp = client.get(f"/auth/usage?api_key={key['raw']}")
    assert resp.status_code == 401

    monkeypatch.setenv("ALLOW_API_KEY_QUERY", "1")
    resp = client.get(f"/auth/usage?api_key={key['raw']}")
    assert resp.status_code == 200


def test_auth_validate_is_rate_limited(client: FlaskClient) -> None:
    for _ in range(2):
        resp = client.post("/auth/validate", json={"api_key": "pyn_random"})
        assert resp.status_code == 401
    resp = client.post("/auth/validate", json={"api_key": "pyn_random"})
    assert resp.status_code == 429
    assert resp.json["code"] == "RATE_LIMITED"


def test_lsp_source_cap_and_rate_limit(client: FlaskClient) -> None:
    too_large = "x" * (256 * 1024 + 1)
    resp = client.post("/lsp/convert", json={"source": too_large})
    assert resp.status_code == 413
    assert resp.json["code"] == "SOURCE_TOO_LARGE"

    # The oversized request still consumed one LSP slot; one more succeeds,
    # then the third is throttled.
    assert client.post("/lsp/convert", json={"source": SCRIPT}).status_code == 200
    resp = client.post("/lsp/convert", json={"source": SCRIPT})
    assert resp.status_code == 429


def test_free_run_rejects_oversized_library_source(client: FlaskClient) -> None:
    body = {
        "script": SCRIPT,
        "data": _bars(1),
        "mode": "interpret",
        "libraries": [
            {
                "namespace": "ns",
                "name": "Lib",
                "version": 1,
                "source": '//@version=6\nlibrary("Lib")\n' + "x" * 2000,
            }
        ],
    }
    resp = client.post("/run", json=body)
    assert resp.status_code == 413
    assert resp.json["code"] == "SCRIPT_TOO_LARGE"


def test_session_create_respects_free_bounds(client: FlaskClient) -> None:
    resp = client.post("/session", json={"script": SCRIPT, "data": _bars(11)})
    assert resp.status_code == 413
    assert resp.json["code"] == "TOO_MANY_BARS"


def test_datafeed_sessions_are_owner_scoped(monkeypatch) -> None:
    from backend.api import datafeed as datafeed_mod

    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET", raising=False)
    datafeed_mod._sessions.clear()
    try:
        datafeed_mod._store_session("owner-a", "binance", {"api_key": "A"})
        assert datafeed_mod._resolve_session("owner-a", "binance", "")[1] == {"api_key": "A"}
        assert datafeed_mod._resolve_session("owner-b", "binance", "")[1] is None
        assert datafeed_mod._resolve_session("owner-b", "binance", "binance")[1] is None
    finally:
        datafeed_mod._sessions.clear()


def test_axis_trust_token_gate(monkeypatch) -> None:
    from backend.app import app

    monkeypatch.setenv("AXIS_TRUST_TOKEN", "shared-secret")
    with app.test_request_context("/run", headers={"X-AXIS-Client": "pwa"}):
        assert free_limits.is_trusted_client() is False
    with app.test_request_context(
        "/run",
        headers={"X-AXIS-Client": "pwa", "X-AXIS-Token": "shared-secret"},
    ):
        assert free_limits.is_trusted_client() is True


def test_array_growth_cap_is_configurable(monkeypatch) -> None:
    from pynescript.compiler import numba_builtins as nb

    monkeypatch.setattr(nb, "_ARRAY_MAX_GROW", 5)
    arr: list[object] = []
    nb.safe_list_set(arr, 6, 1.0)
    assert arr == []
    nb.safe_list_set(arr, 4, 1.0)
    assert len(arr) == 5


def test_compile_cache_stats_expose_library_key_memo() -> None:
    from pynescript.compiler import engine

    stats = engine.compile_cache_stats()
    assert "library_key_entries" in stats
    assert "library_key_max" in stats
    assert stats["library_key_max"] == engine._LIBRARY_KEY_CACHE_MAX
