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

from __future__ import annotations

import base64

import pytest

from flask.testing import FlaskClient

from backend.app import app
from backend.middleware.auth import reset_key_store
from backend.services.backtest import generate_mock_ohlcv
from backend.services.backtest import run_backtest
from backend.services.chart_renderer import render_equity_curve
from backend.services.chart_renderer import render_line_chart


# Admin minting is fail-closed without ADMIN_TOKEN; tests set a fixed value.
_TEST_ADMIN_TOKEN = "test-admin-token-for-backend-suite"  # noqa: S105
_ADMIN_HEADERS = {"X-Admin-Token": _TEST_ADMIN_TOKEN, "Content-Type": "application/json"}


@pytest.fixture
def client(tmp_path, monkeypatch) -> FlaskClient:
    app.config["TESTING"] = True
    monkeypatch.setenv("ADMIN_TOKEN", _TEST_ADMIN_TOKEN)
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys.json"))
    reset_key_store()
    with app.test_client() as client:
        yield client
    reset_key_store()


@pytest.fixture
def api_key(client: FlaskClient) -> str:
    resp = client.post("/auth/create_key", json={"tier": "hobby"}, headers=_ADMIN_HEADERS)
    assert resp.status_code == 200, resp.json
    return resp.json["api_key"]


class TestHealth:
    def test_health_check(self, client: FlaskClient):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json["status"] == "healthy"
        assert "endpoints" in resp.json


class TestAuth:
    def test_create_key(self, client: FlaskClient):
        resp = client.post("/auth/create_key", json={"tier": "pro"}, headers=_ADMIN_HEADERS)
        assert resp.status_code == 200
        assert resp.json["status"] == "success"
        assert resp.json["tier"] == "pro"
        assert resp.json["api_key"].startswith("pyn_")
        assert len(resp.json["api_key"]) > 30

    def test_create_key_requires_admin_token(self, client: FlaskClient):
        resp = client.post("/auth/create_key", json={"tier": "hobby"})
        assert resp.status_code == 403
        assert resp.json["code"] == "FORBIDDEN"

    def test_create_key_rejects_wrong_admin_token(self, client: FlaskClient):
        resp = client.post(
            "/auth/create_key",
            json={"tier": "hobby"},
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert resp.status_code == 403
        assert resp.json["code"] == "FORBIDDEN"

    def test_create_key_disabled_without_admin_env(self, client: FlaskClient, monkeypatch):
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        resp = client.post("/auth/create_key", json={"tier": "hobby"}, headers=_ADMIN_HEADERS)
        assert resp.status_code == 403
        assert "not configured" in resp.json["message"]

    def test_create_key_invalid_tier(self, client: FlaskClient):
        resp = client.post("/auth/create_key", json={"tier": "invalid"}, headers=_ADMIN_HEADERS)
        assert resp.status_code == 400
        assert resp.json["code"] == "INVALID_TIER"

    def test_validate_key(self, client: FlaskClient):
        resp = client.post("/auth/create_key", json={"tier": "hobby"}, headers=_ADMIN_HEADERS)
        raw_key = resp.json["api_key"]

        resp = client.post("/auth/validate", json={"api_key": raw_key})
        assert resp.status_code == 200
        assert resp.json["status"] == "success"
        assert resp.json["tier"] == "hobby"
        assert resp.json["active"] is True
        assert resp.json["rate_limited"] is False

    def test_validate_invalid_key(self, client: FlaskClient):
        resp = client.post("/auth/validate", json={"api_key": "invalid_key"})
        assert resp.status_code == 401

    def test_usage_tracking(self, client: FlaskClient, api_key: str):
        client.post(
            "/preview/chart", json={"data": {"close": [100, 101, 102]}}, headers={"Authorization": f"Bearer {api_key}"}
        )

        resp = client.get("/auth/usage", headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status_code == 200
        assert resp.json["usage"]["calls_used"] >= 1

    def test_unauthorized_access(self, client: FlaskClient):
        resp = client.post("/preview/chart", json={"data": {"close": [100, 101, 102]}})
        assert resp.status_code == 401

    def test_sqlite_backend_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", _TEST_ADMIN_TOKEN)
        monkeypatch.setenv("STORE_BACKEND", "sqlite")
        monkeypatch.setenv("API_KEY_STORE_SQLITE", str(tmp_path / "keys.db"))
        reset_key_store()
        app.config["TESTING"] = True
        with app.test_client() as client:
            resp = client.post("/auth/create_key", json={"tier": "pro"}, headers=_ADMIN_HEADERS)
            assert resp.status_code == 200, resp.json
            raw_key = resp.json["api_key"]
            # New store instance (simulates another worker) still sees the key
            reset_key_store()
            resp = client.post("/auth/validate", json={"api_key": raw_key})
            assert resp.status_code == 200
            assert resp.json["tier"] == "pro"
        reset_key_store()


class TestRun:
    def test_run_success(self, client: FlaskClient):
        resp = client.post(
            "/run",
            json={
                "script": "//@version=5\nplot(close)",
                "data": [
                    {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1},
                    {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json["status"] == "success"
        assert len(resp.json["plots"]) == 2
        assert resp.json["plots"] == [102, 105]
        # Dual-host: empty alerts list is always present (parity with pyne-worker)
        assert resp.json.get("alerts") == []

    def test_run_exports_alerts(self, client: FlaskClient):
        """alert() firings surface on /run (interpret path)."""
        bars = [
            {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1000, "volume": 10},
            {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2000, "volume": 12},
            {"open": 105, "high": 110, "low": 104, "close": 108, "time": 3000, "volume": 11},
        ]
        script = """//@version=5
indicator("alerts")
if bar_index == 1
    alert("hello-pro")
plot(close)
"""
        resp = client.post(
            "/run",
            json={"script": script, "data": bars, "mode": "interpret"},
        )
        assert resp.status_code == 200, resp.json
        assert resp.json["status"] == "success"
        alerts = resp.json.get("alerts") or []
        assert any(a.get("message") == "hello-pro" for a in alerts)
        hit = next(a for a in alerts if a.get("message") == "hello-pro")
        assert hit.get("bar_index") == 1
        assert hit.get("source") == "alert"
        # Empty log.* scripts still export logs + profile (and under meta).
        assert resp.json.get("logs") == []
        profile = resp.json.get("profile")
        assert isinstance(profile, dict)
        assert profile.get("mode") in ("interpret", "compile", "auto")
        assert "total_ms" in profile
        assert "phases" in profile
        assert profile.get("lines") == []  # profiler off by default
        meta = resp.json.get("meta") or {}
        assert meta.get("logs") == []
        assert isinstance(meta.get("profile"), dict)

    def test_run_profiler_line_stats(self, client: FlaskClient):
        """profiler=true returns non-empty per-line timings for interpret."""
        bars = [
            {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1, "volume": 10},
            {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2, "volume": 12},
            {"open": 105, "high": 110, "low": 104, "close": 108, "time": 3, "volume": 11},
        ]
        script = """//@version=5
indicator("prof")
length = input.int(2, "Length")
v = ta.sma(close, length)
plot(v, "sma")
"""
        resp = client.post(
            "/run",
            json={
                "script": script,
                "data": bars,
                "mode": "interpret",
                "profiler": True,
            },
        )
        assert resp.status_code == 200, resp.json
        body = resp.json
        assert body["status"] == "success"
        profile = body.get("profile") or {}
        assert profile.get("mode") == "interpret"
        lines = profile.get("lines") or []
        assert isinstance(lines, list)
        assert len(lines) >= 1
        for row in lines:
            assert "line" in row and int(row["line"]) >= 1
            assert "ms" in row
            assert "execs" in row
            assert "pct" in row
        # Also under meta for clients that only read meta.profile
        assert body.get("meta", {}).get("profile", {}).get("lines") == lines

    def test_run_exports_logs_and_profile(self, client: FlaskClient):
        """log.info/warning/error appear in response.logs and meta.logs."""
        bars = [
            {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1, "volume": 10},
            {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2, "volume": 12},
        ]
        script = """//@version=6
indicator("logs")
if barstate.isfirst
    log.info("hello-info")
    log.warning("hello-warn")
    log.error("hello-err")
plot(close)
"""
        resp = client.post(
            "/run",
            json={"script": script, "data": bars, "mode": "interpret"},
        )
        assert resp.status_code == 200, resp.json
        body = resp.json
        assert body["status"] == "success"
        logs = body.get("logs") or []
        assert isinstance(logs, list)
        levels = {e.get("level") for e in logs if isinstance(e, dict)}
        messages = " ".join(str(e.get("message") or "") for e in logs if isinstance(e, dict))
        assert "info" in levels
        assert "warning" in levels
        assert "error" in levels
        assert "hello-info" in messages
        assert "hello-warn" in messages
        assert "hello-err" in messages
        # Duplicated under meta for meta-only clients
        assert body.get("meta", {}).get("logs") == logs
        profile = body.get("profile") or {}
        assert profile.get("mode") == "interpret"
        assert profile.get("bars") == 2
        assert isinstance(profile.get("total_ms"), (int, float))
        phases = profile.get("phases") or {}
        assert "parse_ms" in phases
        assert "eval_ms" in phases
        # Default profiler off → empty lines; phase profile still present
        assert isinstance(profile.get("lines"), list)
        assert body.get("meta", {}).get("profile") == profile

    def test_run_mode_compile_body(self, client: FlaskClient):
        """Body mode=compile uses the Numba/object compile path when available."""
        bars = [
            {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1, "volume": 10},
            {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2, "volume": 12},
        ]
        resp = client.post(
            "/run",
            json={
                "script": "//@version=5\nindicator('t')\nplot(close)",
                "data": bars,
                "mode": "compile",
            },
        )
        assert resp.status_code == 200, resp.json
        body = resp.json
        assert body["status"] == "success"
        assert body.get("mode") == "compile"
        assert body["plots"] == [102, 105]
        assert isinstance(body.get("logs"), list)
        profile = body.get("profile") or {}
        assert profile.get("mode") == "compile"
        assert "total_ms" in profile
        assert body.get("meta", {}).get("profile") == profile

    def test_run_mode_compile_query_fallback(self, client: FlaskClient):
        """Legacy clients put mode only on the query string — still honor it."""
        bars = [
            {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1, "volume": 10},
            {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2, "volume": 12},
        ]
        resp = client.post(
            "/run?mode=compile",
            json={
                "script": "//@version=5\nindicator('t')\nplot(close)",
                "data": bars,
            },
        )
        assert resp.status_code == 200, resp.json
        body = resp.json
        assert body["status"] == "success"
        assert body.get("mode") == "compile"

    def test_run_compile_nan_series_is_json_null(self, client: FlaskClient):
        """Warm-up NaNs must be null — browsers reject bare NaN as invalid JSON."""
        bars = [
            {
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 98.0 + i,
                "close": 102.0 + i,
                "time": i + 1,
                "volume": 10,
            }
            for i in range(20)
        ]
        resp = client.post(
            "/run",
            json={
                "script": "//@version=5\nindicator('sma')\nplot(ta.sma(close, 14))",
                "data": bars,
                "mode": "compile",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
        raw = resp.get_data(as_text=True)
        assert "NaN" not in raw
        assert "Infinity" not in raw
        body = resp.get_json()
        assert body["status"] == "success"
        assert body.get("mode") == "compile"
        series = body.get("series") or {}
        assert series, "expected at least one plot series"
        first = next(iter(series.values()))
        assert isinstance(first, list)
        # First bars of SMA(14) are null (warm-up), later bars are finite numbers
        assert first[0] is None
        assert any(isinstance(x, (int, float)) for x in first)

    def test_run_no_script(self, client: FlaskClient):
        resp = client.post("/run", json={"data": []})
        assert resp.status_code == 400
        # Schema validation fires before NO_SCRIPT empty-string check
        assert resp.json["code"] in ("NO_SCRIPT", "MISSING_FIELD")

    def test_run_no_data(self, client: FlaskClient):
        resp = client.post("/run", json={"script": "//@version=5\nplot(close)"})
        assert resp.status_code == 400
        assert resp.json["code"] in ("NO_DATA", "MISSING_FIELD")

    def test_run_batch_success(self, client: FlaskClient):
        bars = [
            {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1, "volume": 10},
            {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2, "volume": 12},
        ]
        resp = client.post(
            "/run/batch",
            json={
                "data": bars,
                "scripts": [
                    {"id": "a", "script": "//@version=5\nindicator('a')\nplot(close)"},
                    {"id": "b", "script": "//@version=5\nindicator('b')\nplot(open)"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json
        assert body["status"] in ("success", "partial")
        assert body["count"] == 2
        assert body["ok"] >= 1
        ids = {r["id"] for r in body["results"]}
        assert ids == {"a", "b"}
        for r in body["results"]:
            if r["status"] == "success":
                assert len(r["plots"]) == 2

    def test_run_batch_too_many(self, client: FlaskClient):
        resp = client.post(
            "/run/batch",
            json={
                "data": [{"open": 1, "high": 1, "low": 1, "close": 1, "time": 1}],
                "scripts": [{"id": str(i), "script": "//@version=5\nplot(close)"} for i in range(9)],
            },
        )
        assert resp.status_code == 400
        assert resp.json["code"] == "TOO_MANY_SCRIPTS"


class TestPreview:
    def test_chart_preview(self, client: FlaskClient, api_key: str):
        resp = client.post(
            "/preview/chart",
            json={
                "data": {"close": [100 + i for i in range(50)]},
                "options": {"type": "line", "width": 400, "height": 200},
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert resp.status_code == 200
        assert resp.json["status"] == "success"
        assert "chart" in resp.json
        assert resp.json["meta"]["bars"] == 50
        img_data = base64.b64decode(resp.json["chart"])
        assert img_data.startswith(b"\x89PNG")

    def test_chart_preview_ohlcv(self, client: FlaskClient, api_key: str):
        ohlcv = {
            "open": [100, 101, 102, 103, 104],
            "high": [105, 106, 107, 108, 109],
            "low": [99, 100, 101, 102, 103],
            "close": [101, 103, 105, 107, 109],
            "volume": [1000, 1100, 1200, 1300, 1400],
        }
        resp = client.post(
            "/preview/chart",
            json={
                "data": ohlcv,
                "options": {"type": "ohlcv"},
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert resp.status_code == 200
        assert resp.json["meta"]["type"] == "ohlcv"

    def test_chart_preview_no_data(self, client: FlaskClient, api_key: str):
        resp = client.post("/preview/chart", json={}, headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status_code == 400
        assert resp.json["code"] == "NO_DATA"

    def test_chart_preview_no_close_data(self, client: FlaskClient, api_key: str):
        resp = client.post(
            "/preview/chart",
            json={
                "data": {"open": [100, 101]},
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 400
        assert resp.json["code"] == "NO_CLOSE_DATA"

    def test_indicator_preview_sma(self, client: FlaskClient, api_key: str):
        resp = client.post(
            "/preview/indicator",
            json={
                "expression": "ta.sma(close, 14)",
                "data": {"close": [100 + i * 0.5 + (i % 3) for i in range(30)]},
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert resp.status_code == 200
        assert resp.json["status"] == "success"
        assert "chart" in resp.json


class TestBacktest:
    def test_quick_backtest_mock(self, client: FlaskClient, api_key: str):
        resp = client.post(
            "/backtest/quick",
            json={
                "script": "//@version=5\nstrategy('Test')",
                "mock_data": True,
                "mock_bars": 100,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert resp.status_code == 200
        assert resp.json["status"] == "success"
        result = resp.json["result"]
        assert "equity_curve" in result
        assert "summary" in result
        assert "equity_chart" in result
        assert result["summary"]["total_trades"] >= 0

    def test_quick_backtest_no_script(self, client: FlaskClient, api_key: str):
        resp = client.post("/backtest/quick", json={"mock_data": True}, headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status_code == 400
        assert resp.json["code"] == "NO_SCRIPT"

    def test_backtest_with_real_data(self, client: FlaskClient, api_key: str):
        ohlcv = {
            "close": [100 + i + (i % 5) * 0.5 for i in range(100)],
        }
        resp = client.post(
            "/backtest/quick",
            json={
                "script": "//@version=5\nstrategy('Test')",
                "data": ohlcv,
                "initial_capital": 50000.0,
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert resp.status_code == 200
        assert resp.json["result"]["summary"]["total_trades"] >= 0


class TestChartRenderer:
    def test_render_line_chart(self):
        values = [100, 101, 102, 101, 103, 105, 104, 106]
        chart_b64 = render_line_chart(values, title="Test Chart", width=400, height=200)
        img_data = base64.b64decode(chart_b64)
        assert img_data.startswith(b"\x89PNG")

    def test_render_line_chart_empty(self):
        chart_b64 = render_line_chart([], title="Empty")
        img_data = base64.b64decode(chart_b64)
        assert img_data.startswith(b"\x89PNG")

    def test_render_equity_curve(self):
        equity = [10000, 10100, 10050, 10200, 10150, 10300]
        chart_b64 = render_equity_curve(equity, width=400)
        img_data = base64.b64decode(chart_b64)
        assert img_data.startswith(b"\x89PNG")

    def test_render_with_volume(self):
        values = [100 + i for i in range(30)]
        ohlcv = {"volume": [1000 + i * 10 for i in range(30)]}
        chart_b64 = render_line_chart(values, show_volume=True, ohlcv=ohlcv)
        img_data = base64.b64decode(chart_b64)
        assert img_data.startswith(b"\x89PNG")


class TestBacktestService:
    def test_generate_mock_ohlcv(self):
        ohlcv = generate_mock_ohlcv(n_bars=50)
        assert len(ohlcv["close"]) == 50
        assert len(ohlcv["open"]) == 50
        assert len(ohlcv["high"]) == 50
        assert len(ohlcv["low"]) == 50
        assert len(ohlcv["volume"]) == 50

    def test_run_backtest(self):
        ohlcv = generate_mock_ohlcv(n_bars=100)
        result = run_backtest("//@version=5\nstrategy('Test')", ohlcv)
        assert len(result.equity_curve) == 100
        assert result.total_trades >= 0
        assert -100 <= result.sharpe_ratio <= 100

    def test_backtest_metrics(self):
        ohlcv = generate_mock_ohlcv(n_bars=50)
        result = run_backtest("//@version=5\nstrategy('Test')", ohlcv)
        summary = result.to_dict()["summary"]
        assert "total_pnl" in summary
        assert "sharpe_ratio" in summary
        assert "max_drawdown" in summary
        assert "win_rate" in summary
        assert "profit_factor" in summary
