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

import time

import pytest

from flask.testing import FlaskClient

from backend.app import app
from backend.runner import scheduler
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


class TestRunnerScheduling:
    """Timeframe due gate, backoff, run history, worker pool, webhook status."""

    def test_history_records_runs(self, client: FlaskClient):
        assert client.post("/scripts", json=_script_body()).status_code == 201
        first = client.post("/cron/run", json={"force": True})
        assert first.json["jobs"][0]["status"] == "ok"

        # Routine no_new_bar skips stay out of the audit log.
        client.post("/cron/run", json={})
        hist = client.get("/cron/history")
        assert hist.status_code == 200
        assert hist.json["count"] == 1
        run = hist.json["runs"][0]
        assert run["script_id"] == "sma-bot"
        assert run["status"] == "ok"
        assert run["last_bar_time"] > 0

        empty = client.get("/cron/history?script_id=unknown")
        assert empty.json["count"] == 0

    def test_backoff_after_fetch_failure(self, client: FlaskClient, monkeypatch):
        state = {"fail": True}
        real_fetch = scheduler.fetch_ohlcv

        def flaky(rec):
            if state["fail"]:
                raise RuntimeError("feed down")
            return real_fetch(rec)

        monkeypatch.setattr(scheduler, "fetch_ohlcv", flaky)
        assert client.post("/scripts", json=_script_body()).status_code == 201

        t1 = client.post("/cron/run", json={})
        job = t1.json["jobs"][0]
        assert job["status"] == "error"
        assert job["reason"] == "fetch_failed"
        assert job["next_due_at"] > 0
        cron = client.get("/scripts/sma-bot").json["script"]["cron"]
        assert cron["consecutive_errors"] == 1
        assert cron["next_due_at"] > 0
        # last_bar_time survives the partial error patch (merge semantics)
        assert cron["last_status"] == "error"

        # Non-forced tick waits out the exponential backoff.
        t2 = client.post("/cron/run", json={})
        assert t2.json["jobs"][0]["status"] == "skipped"
        assert t2.json["jobs"][0]["reason"] == "backoff"

        # Force bypasses backoff; a success resets it.
        state["fail"] = False
        t3 = client.post("/cron/run", json={"force": True})
        assert t3.json["jobs"][0]["status"] == "ok"
        cron2 = client.get("/scripts/sma-bot").json["script"]["cron"]
        assert cron2["consecutive_errors"] == 0
        assert cron2["next_due_at"] == 0

        # A later failure must not wipe last_bar_time (partial-patch merge).
        state["fail"] = True
        t4 = client.post("/cron/run", json={"force": True})
        assert t4.json["jobs"][0]["status"] == "error"
        cron3 = client.get("/scripts/sma-bot").json["script"]["cron"]
        assert cron3["last_status"] == "error"
        assert cron3["last_bar_time"] == cron2["last_bar_time"]

        statuses = sorted(r["status"] for r in client.get("/cron/history").json["runs"])
        assert statuses == ["error", "error", "ok"]

    def test_timeframe_due_gate_skips_fetch(self, client: FlaskClient, monkeypatch):
        now_ms = int(time.time() * 1000)
        bars = [
            {
                "time": now_ms - (80 - i) * 3_600_000,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
            for i in range(80)
        ]
        calls = {"n": 0}

        def stub(rec):
            calls["n"] += 1
            return bars

        monkeypatch.setattr(scheduler, "fetch_ohlcv", stub)
        assert client.post("/scripts", json=_script_body(timeframe="1w")).status_code == 201

        first = client.post("/cron/run", json={"force": True})
        assert first.json["jobs"][0]["status"] == "ok"
        assert calls["n"] == 1

        # Last bar is fresh (< 1w old): the next poll must not even fetch.
        second = client.post("/cron/run", json={})
        job = second.json["jobs"][0]
        assert job["status"] == "skipped"
        assert job["reason"] == "not_due"
        assert calls["n"] == 1

    def test_worker_pool_ticks_all_scripts(self, client: FlaskClient, monkeypatch):
        monkeypatch.setenv("PYNE_RUNNER_WORKERS", "2")
        for sid in ("a-1", "b-2", "c-3"):
            assert client.post("/scripts", json=_script_body(id=sid)).status_code == 201
        resp = client.post("/cron/run", json={"force": True})
        assert resp.status_code == 200, resp.json
        assert resp.json["count"] == 3
        assert [j["script_id"] for j in resp.json["jobs"]] == ["a-1", "b-2", "c-3"]
        assert all(j["status"] == "ok" for j in resp.json["jobs"])
        assert resp.json["ok"] == 3

    def test_webhook_failure_recorded(self, client: FlaskClient, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("hook down")

        monkeypatch.setattr(scheduler, "_forward_alerts", boom)
        assert client.post("/scripts", json=_script_body(webhook_url="https://example.com/hook")).status_code == 201

        resp = client.post("/cron/run", json={"force": True})
        job = resp.json["jobs"][0]
        assert job["status"] == "ok"
        assert job["alert_forward_status"].startswith("error")

        cron = client.get("/scripts/sma-bot").json["script"]["cron"]
        assert cron["last_status"] == "ok"
        assert cron["last_forward_status"].startswith("error")

        runs = client.get("/cron/history").json["runs"]
        assert runs[0]["forward_status"].startswith("error")
