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

"""Optional hosted script runner (PYNE_RUNNER) — registry + bar-close tick."""

from __future__ import annotations

import pytest

from flask.testing import FlaskClient

from backend.app import app
from backend.runner.store import reset_store


_PINE = """
//@version=6
indicator("runner")
plot(close)
alertcondition(close > open, "up", "green")
"""


@pytest.fixture
def client(tmp_path, monkeypatch) -> FlaskClient:
    app.config["TESTING"] = True
    monkeypatch.setenv("PYNE_RUNNER", "1")
    monkeypatch.setenv("PYNE_RUNNER_SCHEDULER", "0")
    monkeypatch.setenv("PYNE_RUNNER_DB", str(tmp_path / "runner.db"))
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    reset_store()
    with app.test_client() as client:
        yield client
    reset_store()


@pytest.fixture
def off_client(monkeypatch) -> FlaskClient:
    app.config["TESTING"] = True
    monkeypatch.setenv("PYNE_RUNNER", "0")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with app.test_client() as client:
        yield client


def _script_body(**extra):
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


class TestRunnerDisabled:
    def test_health_flag_off(self, off_client: FlaskClient):
        resp = off_client.get("/health")
        assert resp.status_code == 200
        assert resp.json["features"]["script_runner"] is False
        assert "/scripts" not in str(resp.json.get("endpoints", {}))

    def test_routes_404(self, off_client: FlaskClient):
        resp = off_client.get("/scripts")
        assert resp.status_code == 404
        assert resp.json["code"] == "RUNNER_DISABLED"


class TestRunnerRegistry:
    def test_health_flag_on(self, client: FlaskClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json["features"]["script_runner"] is True
        assert resp.json["features"]["script_runner_scheduler"] is False
        assert "/scripts" in str(resp.json.get("endpoints", {}))
        assert "/cron/run" in str(resp.json.get("endpoints", {}))

    def test_put_list_get_delete(self, client: FlaskClient):
        resp = client.post("/scripts", json=_script_body())
        assert resp.status_code == 201, resp.json
        rec = resp.json["script"]
        assert rec["id"] == "sma-bot"
        assert rec["data_source"] == "mock"
        assert "plot(close)" in rec["script"]

        listed = client.get("/scripts")
        assert listed.status_code == 200
        assert listed.json["count"] == 1
        assert "script" not in listed.json["scripts"][0]

        got = client.get("/scripts/sma-bot")
        assert got.status_code == 200
        assert "script" in got.json["script"]
        assert "cron" in got.json["script"]

        deleted = client.delete("/scripts/sma-bot")
        assert deleted.status_code == 200
        assert client.get("/scripts/sma-bot").status_code == 404

    def test_rejects_bad_id(self, client: FlaskClient):
        resp = client.post("/scripts", json=_script_body(id="../evil"))
        assert resp.status_code == 400
        assert resp.json["code"] == "INVALID_SCRIPT"

    def test_admin_token_required_when_set(self, client: FlaskClient, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret-admin")
        resp = client.post("/scripts", json=_script_body(id="locked"))
        assert resp.status_code == 403
        resp = client.post(
            "/scripts",
            json=_script_body(id="locked"),
            headers={"X-Admin-Token": "secret-admin"},
        )
        assert resp.status_code == 201, resp.json

    def test_get_redacts_webhook_without_admin_token(self, client: FlaskClient, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret-admin")
        headers = {"X-Admin-Token": "secret-admin"}
        hook = "https://example.com/hooks/abc"
        assert (
            client.post(
                "/scripts",
                json=_script_body(id="hooked", webhook_url=hook),
                headers=headers,
            ).status_code
            == 201
        )
        listed = client.get("/scripts")
        assert listed.status_code == 200
        assert listed.json["scripts"][0]["webhook_url"] == ""
        got = client.get("/scripts/hooked")
        assert got.status_code == 200
        assert got.json["script"]["webhook_url"] == ""
        listed_admin = client.get("/scripts", headers=headers)
        assert listed_admin.json["scripts"][0]["webhook_url"] == hook
        got_admin = client.get("/scripts/hooked", headers=headers)
        assert got_admin.json["script"]["webhook_url"] == hook


class TestRunnerCron:
    def test_tick_mock_then_skip(self, client: FlaskClient):
        assert client.post("/scripts", json=_script_body()).status_code == 201
        first = client.post("/cron/run", json={"force": True})
        assert first.status_code == 200, first.json
        jobs = first.json.get("jobs") or []
        assert len(jobs) == 1
        assert jobs[0]["status"] == "ok"
        assert jobs[0]["script_id"] == "sma-bot"

        second = client.post("/cron/run", json={})
        assert second.status_code == 200
        assert second.json["jobs"][0]["status"] == "skipped"
        assert second.json["jobs"][0]["reason"] == "no_new_bar"

    def test_disable_via_cron_jobs(self, client: FlaskClient):
        assert client.post("/scripts", json=_script_body()).status_code == 201
        resp = client.put("/cron/jobs", json={"jobs": [{"script_id": "sma-bot", "enabled": False}]})
        assert resp.status_code == 200
        assert resp.json["updated"][0]["enabled"] is False
        tick = client.post("/cron/run", json={"force": True})
        assert tick.json.get("jobs") == []
