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

"""Thin Flask edge coverage for /stats, 404 JSON shape, and auth failures."""

from __future__ import annotations

import pytest

from flask.testing import FlaskClient

from backend.app import _public_exc_message
from backend.app import _sanitize_error_for_response
from backend.app import app
from backend.middleware.auth import reset_key_store


_TEST_ADMIN_TOKEN = "test-admin-token-for-backend-edges"
_ADMIN_HEADERS = {"X-Admin-Token": _TEST_ADMIN_TOKEN, "Content-Type": "application/json"}


@pytest.fixture
def client(tmp_path, monkeypatch) -> FlaskClient:
    app.config["TESTING"] = True
    monkeypatch.setenv("ADMIN_TOKEN", _TEST_ADMIN_TOKEN)
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys_edges.json"))
    reset_key_store()
    with app.test_client() as client:
        yield client
    reset_key_store()


class TestStatsAndNotFound:
    def test_stats_ok_shape(self, client: FlaskClient) -> None:
        resp = client.get("/stats")
        assert resp.status_code == 200
        body = resp.json
        assert body["status"] == "ok"
        assert "counters" in body
        assert "latencies" in body
        assert "gauges" in body
        assert "compile_cache" in body
        assert "sessions" in body
        assert "notes" in body

    def test_health_json(self, client: FlaskClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json
        assert body.get("status") in {"healthy", "ok", "up"} or "version" in body or "features" in body

    def test_unknown_path_json_404(self, client: FlaskClient) -> None:
        resp = client.get("/no/such/endpoint/xyz")
        assert resp.status_code == 404
        body = resp.json
        assert body["status"] == "error"
        assert body["code"] == "NOT_FOUND"
        assert "not found" in body["message"].lower()


class TestErrorSanitizer:
    def test_drops_traceback_frames_and_paths(self) -> None:
        blob = (
            "Traceback (most recent call last):\n"
            '  File "/app/backend/app.py", line 12, in tick\n'
            "    raise RuntimeError('boom')\n"
            "RuntimeError: undeclared identifier 'foo'"
        )
        assert _sanitize_error_for_response(blob) == "RuntimeError: undeclared identifier 'foo'"
        assert "/app/" not in _sanitize_error_for_response(blob)

    def test_public_exc_uses_type_name_when_only_frames(self) -> None:
        class _FrameOnly(Exception):
            def __str__(self) -> str:
                return 'File "/secret/core.py", line 9, in run'

        msg = _public_exc_message(_FrameOnly())
        assert msg == "_FrameOnly"
        assert "secret" not in msg
        assert "core.py" not in msg


class TestAuthFailureShapes:
    def test_usage_without_key_401(self, client: FlaskClient) -> None:
        resp = client.get("/auth/usage")
        assert resp.status_code == 401
        body = resp.json
        assert body["status"] == "error"
        assert body["code"] == "UNAUTHORIZED"
        assert "message" in body

    def test_run_get_method_not_allowed(self, client: FlaskClient) -> None:
        resp = client.get("/run")
        assert resp.status_code == 405

    def test_optimize_missing_script_shape(self, client: FlaskClient) -> None:
        resp = client.post("/optimize", json={})
        assert resp.status_code == 400
        body = resp.json
        assert body["status"] == "error"
        assert body["code"] == "MISSING_FIELD"

    def test_create_key_wrong_admin(self, client: FlaskClient) -> None:
        resp = client.post(
            "/auth/create_key",
            json={"tier": "hobby"},
            headers={"X-Admin-Token": "wrong-token", "Content-Type": "application/json"},
        )
        assert resp.status_code in {401, 403}
        assert resp.json is not None

    def test_validate_missing_body(self, client: FlaskClient) -> None:
        resp = client.post("/auth/validate", json={})
        assert resp.status_code in {400, 401, 422}
        assert resp.json is not None
