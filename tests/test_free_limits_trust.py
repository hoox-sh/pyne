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

"""AXIS PWA/IDE trust bypass: skip bounds/concurrency, keep the IP rate limit.

The trust signal (``Origin`` or ``X-AXIS-Client``) is advisory, not
authentication. These tests pin the frozen contract:

* trusted clients skip the bar cap
* trusted clients do **not** skip the per-IP rate limit
* untrusted callers behave exactly as before
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from flask import Flask

from backend.middleware import free_limits


SCRIPT = '//@version=5\nindicator("t")\nplot(close)\n'


def _bars(n: int) -> list[dict[str, float | int]]:
    return [{"open": 1, "high": 1, "low": 1, "close": 1, "time": i, "volume": 1} for i in range(n)]


def _run_body(n: int) -> dict[str, object]:
    return {"script": SCRIPT, "data": _bars(n), "mode": "interpret"}


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[object]:
    """Flask test client with the contract env and isolated limiter state."""
    monkeypatch.setenv("ADMIN_TOKEN", "ci-test-admin-token")
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys.json"))
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    monkeypatch.setenv("FREE_MAX_BARS", "3")
    monkeypatch.setenv("FREE_RATE_LIMIT", "2")
    monkeypatch.setenv("FREE_RATE_WINDOW_SEC", "60")
    # Isolate the rate-limit assertions from the concurrency gate.
    monkeypatch.setenv("FREE_MAX_CONCURRENT", "0")

    # Module-level limiters survive between tests; start from a clean slate.
    free_limits._RATE._hits.clear()
    free_limits._GATE._active = 0

    from backend.app import app

    assert isinstance(app, Flask)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_trusted_axis_bypasses_bounds_but_not_rate_limit(client) -> None:
    """One run: untrusted 413, trusted not 413, then 429 for both at #3."""
    four_bars = _run_body(4)
    two_bars = _run_body(2)

    # 1. Untrusted oversized payload keeps today's behaviour: 413.
    resp = client.post(
        "/run",
        json=four_bars,
        environ_base={"REMOTE_ADDR": "10.10.0.1"},
    )
    assert resp.status_code == 413
    assert resp.json["code"] == "TOO_MANY_BARS"

    # 2. Same payload from the AXIS PWA origin skips the bar cap.
    resp = client.post(
        "/run",
        json=four_bars,
        headers={"Origin": "https://axis.hoox.sh"},
        environ_base={"REMOTE_ADDR": "10.10.0.2"},
    )
    assert resp.status_code != 413
    assert resp.json.get("code") != "TOO_MANY_BARS"

    # 3. Same payload from the AXIS IDE header (trimmed, case-insensitive).
    resp = client.post(
        "/run",
        json=four_bars,
        headers={"X-AXIS-Client": " IDE "},
        environ_base={"REMOTE_ADDR": "10.10.0.3"},
    )
    assert resp.status_code != 413
    assert resp.json.get("code") != "TOO_MANY_BARS"

    # 4. Trusted clients still hit the 60/60s per-IP limit (2 in this test).
    for _ in range(2):
        resp = client.post(
            "/run",
            json=two_bars,
            headers={"Origin": "https://axis.hoox.sh"},
            environ_base={"REMOTE_ADDR": "10.10.0.4"},
        )
        assert resp.status_code != 429
    resp = client.post(
        "/run",
        json=two_bars,
        headers={"Origin": "https://axis.hoox.sh"},
        environ_base={"REMOTE_ADDR": "10.10.0.4"},
    )
    assert resp.status_code == 429
    assert resp.json["code"] == "RATE_LIMITED"

    # 5. Untrusted callers still hit the same limit.
    for _ in range(2):
        resp = client.post(
            "/run",
            json=two_bars,
            environ_base={"REMOTE_ADDR": "10.10.0.5"},
        )
        assert resp.status_code != 429
    resp = client.post(
        "/run",
        json=two_bars,
        environ_base={"REMOTE_ADDR": "10.10.0.5"},
    )
    assert resp.status_code == 429
    assert resp.json["code"] == "RATE_LIMITED"


def test_axis_preflight_allows_client_header(client) -> None:
    """PWA preflight must allow https://axis.hoox.sh and X-AXIS-Client."""
    resp = client.options(
        "/run",
        headers={
            "Origin": "https://axis.hoox.sh",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-axis-client",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://axis.hoox.sh"
    allowed = resp.headers.get("Access-Control-Allow-Headers", "").lower()
    assert "x-axis-client" in allowed


def test_is_trusted_client_header_semantics(monkeypatch) -> None:
    """Exact origin; trimmed/case-insensitive client header; nothing else."""
    monkeypatch.setenv("FREE_TIER_LIMITS", "1")
    from backend.app import app

    cases = [
        ({"Origin": "https://axis.hoox.sh"}, True),
        ({"Origin": "https://axis.hoox.sh.evil.example"}, False),
        ({"Origin": "http://axis.hoox.sh"}, False),
        ({"X-AXIS-Client": "pwa"}, True),
        ({"X-AXIS-Client": "PWA"}, True),
        ({"X-AXIS-Client": " ide "}, True),
        ({"X-AXIS-Client": "web"}, False),
        ({}, False),
    ]
    for headers, expected in cases:
        with app.test_request_context("/run", headers=headers):
            assert free_limits.is_trusted_client() is expected
