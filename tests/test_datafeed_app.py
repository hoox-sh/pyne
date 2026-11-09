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

"""Standalone compose datafeed app (blueprint + CORS, no Pro API routes)."""

from __future__ import annotations

import pytest

from flask.testing import FlaskClient

from backend.api import datafeed as datafeed_mod
from backend.datafeed_app import create_app


@pytest.fixture
def client() -> FlaskClient:
    application = create_app()
    application.config["TESTING"] = True
    with application.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    datafeed_mod._sessions.clear()
    yield
    datafeed_mod._sessions.clear()


def test_max_content_length_is_capped() -> None:
    application = create_app()
    assert application.config["MAX_CONTENT_LENGTH"] == 5 * 1024 * 1024


def test_health_and_root(client: FlaskClient) -> None:
    health = client.get("/datafeed/health")
    assert health.status_code == 200
    body = health.get_json()
    assert body["status"] == "ok"
    assert "ccxt" in body
    root = client.get("/")
    assert root.status_code == 200
    assert root.get_json()["status"] == "ok"


def test_pro_api_routes_are_absent(client: FlaskClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 404


def test_cors_echoes_origin(client: FlaskClient) -> None:
    resp = client.get("/datafeed/health", headers={"Origin": "https://axis.hoox.sh"})
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://axis.hoox.sh"


def test_options_preflight(client: FlaskClient) -> None:
    resp = client.options(
        "/datafeed/ohlcv",
        headers={
            "Origin": "https://axis.hoox.sh",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == "https://axis.hoox.sh"
    allowed = resp.headers.get("Access-Control-Allow-Headers", "").lower()
    assert "x-axis-client" in allowed
