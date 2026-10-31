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

"""Coverage for ``backend.api.preview`` handlers and indicator helpers."""

from __future__ import annotations

import base64

import pytest

from flask.testing import FlaskClient

from backend.api import preview as preview_mod
from backend.app import app
from backend.middleware.auth import reset_key_store


_TEST_ADMIN_TOKEN = "test-admin-token-for-preview-coverage"
_ADMIN_HEADERS = {"X-Admin-Token": _TEST_ADMIN_TOKEN, "Content-Type": "application/json"}

_TINY_SCRIPT = """//@version=6
indicator("preview_cov")
plot(close)
"""

_TINY_STRATEGY = """//@version=6
strategy("preview_bt")
plot(close)
"""


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


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _close(n: int = 40) -> list[float]:
    return [100.0 + i * 0.5 + (i % 4) for i in range(n)]


class TestPreviewChartSchema:
    def test_unknown_fields(self, client: FlaskClient, api_key: str) -> None:
        resp = client.post(
            "/preview/chart",
            json={"data": {"close": [1.0, 2.0]}, "extra": True},
            headers=_auth(api_key),
        )
        assert resp.status_code == 400
        assert resp.json["code"] == "UNKNOWN_FIELDS"

    def test_line_happy_path_with_script(self, client: FlaskClient, api_key: str) -> None:
        close = _close(20)
        resp = client.post(
            "/preview/chart",
            json={
                "script": _TINY_SCRIPT,
                "data": {"close": close},
                "options": {"type": "line", "color": "#00AA00", "width": 320, "height": 180},
            },
            headers=_auth(api_key),
        )
        assert resp.status_code == 200, resp.json
        assert resp.json["status"] == "success"
        assert resp.json["meta"]["bars"] == 20
        assert resp.json["meta"]["type"] == "line"
        assert resp.json["meta"]["first_value"] == close[0]
        assert resp.json["meta"]["last_value"] == close[-1]
        raw = base64.b64decode(resp.json["chart"])
        assert raw.startswith(b"\x89PNG")

    def test_ohlcv_and_volume_options(self, client: FlaskClient, api_key: str) -> None:
        ohlcv = {
            "open": [100, 101, 102],
            "high": [105, 106, 107],
            "low": [99, 100, 101],
            "close": [101, 103, 105],
            "volume": [10, 11, 12],
        }
        resp = client.post(
            "/preview/chart",
            json={"data": ohlcv, "options": {"type": "ohlcv", "show_volume": True}},
            headers=_auth(api_key),
        )
        assert resp.status_code == 200, resp.json
        assert resp.json["meta"]["type"] == "ohlcv"

        line = client.post(
            "/preview/chart",
            json={"data": ohlcv, "options": {"type": "line", "show_volume": True}},
            headers=_auth(api_key),
        )
        assert line.status_code == 200, line.json
        assert line.json["meta"]["type"] == "line"

    def test_no_data_and_no_close(self, client: FlaskClient, api_key: str) -> None:
        r1 = client.post("/preview/chart", json={"script": _TINY_SCRIPT}, headers=_auth(api_key))
        assert r1.status_code == 400
        assert r1.json["code"] == "NO_DATA"
        r2 = client.post(
            "/preview/chart",
            json={"data": {"open": [1, 2]}},
            headers=_auth(api_key),
        )
        assert r2.status_code == 400
        assert r2.json["code"] == "NO_CLOSE_DATA"

    def test_render_error_path(self, client: FlaskClient, api_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*_a, **_k):
            raise RuntimeError("render fail")

        monkeypatch.setattr(preview_mod, "render_line_chart", _boom)
        resp = client.post(
            "/preview/chart",
            json={"data": {"close": [1.0, 2.0, 3.0]}},
            headers=_auth(api_key),
        )
        assert resp.status_code == 500
        assert resp.json["code"] == "RENDER_ERROR"


class TestPreviewIndicator:
    def test_unknown_fields(self, client: FlaskClient, api_key: str) -> None:
        resp = client.post(
            "/preview/indicator",
            json={"expression": "ta.sma(close, 5)", "data": {"close": _close()}, "bogus": 1},
            headers=_auth(api_key),
        )
        assert resp.status_code == 400
        assert resp.json["code"] == "UNKNOWN_FIELDS"

    def test_sma_ema_rsi_macd_happy(self, client: FlaskClient, api_key: str) -> None:
        close = _close(60)
        for expr in (
            "ta.sma(close, 14)",
            "ta.ema(close, 12)",
            "ta.rsi(close, 14)",
            "ta.macd(close)",
            "close",
        ):
            resp = client.post(
                "/preview/indicator",
                json={"expression": expr, "data": {"close": close}, "options": {"color": "#FF9800"}},
                headers=_auth(api_key),
            )
            assert resp.status_code == 200, (expr, resp.json)
            assert resp.json["status"] == "success"
            assert resp.json["meta"]["expression"] == expr
            assert resp.json["meta"]["bars"] == len(close)

    def test_no_data_paths(self, client: FlaskClient, api_key: str) -> None:
        r1 = client.post(
            "/preview/indicator",
            json={"expression": "ta.sma(close, 5)"},
            headers=_auth(api_key),
        )
        assert r1.status_code == 400
        assert r1.json["code"] == "NO_DATA"
        r2 = client.post(
            "/preview/indicator",
            json={"expression": "ta.sma(close, 5)", "data": {"volume": [1, 2]}},
            headers=_auth(api_key),
        )
        assert r2.status_code == 400
        assert r2.json["code"] == "NO_CLOSE_DATA"

    def test_bad_expression_falls_back_to_close(self, client: FlaskClient, api_key: str) -> None:
        close = _close(10)
        resp = client.post(
            "/preview/indicator",
            json={"expression": "ta.sma(close, not_an_int)", "data": {"close": close}},
            headers=_auth(api_key),
        )
        assert resp.status_code == 200, resp.json
        assert resp.json["meta"]["last_value"] == close[-1]


class TestBacktestQuick:
    def test_unknown_fields(self, client: FlaskClient, api_key: str) -> None:
        resp = client.post(
            "/backtest/quick",
            json={"script": _TINY_STRATEGY, "mock_data": True, "nope": 1},
            headers=_auth(api_key),
        )
        assert resp.status_code == 400
        assert resp.json["code"] == "UNKNOWN_FIELDS"

    def test_mock_happy_path(self, client: FlaskClient, api_key: str) -> None:
        resp = client.post(
            "/backtest/quick",
            json={
                "script": _TINY_STRATEGY,
                "mock_data": True,
                "mock_bars": 40,
                "initial_capital": 25000.0,
            },
            headers=_auth(api_key),
        )
        assert resp.status_code == 200, resp.json
        assert resp.json["status"] == "success"
        assert "result" in resp.json
        assert resp.json["meta"]["initial_capital"] == 25000.0
        assert resp.json["meta"]["bars"] == 40

    def test_no_script_and_no_data(self, client: FlaskClient, api_key: str) -> None:
        r1 = client.post("/backtest/quick", json={"mock_data": True}, headers=_auth(api_key))
        assert r1.status_code == 400
        assert r1.json["code"] == "NO_SCRIPT"
        r2 = client.post(
            "/backtest/quick",
            json={"script": _TINY_STRATEGY, "mock_data": False},
            headers=_auth(api_key),
        )
        assert r2.status_code == 400
        assert r2.json["code"] == "NO_DATA"

    def test_provided_ohlcv(self, client: FlaskClient, api_key: str) -> None:
        close = _close(50)
        resp = client.post(
            "/backtest/quick",
            json={
                "script": _TINY_STRATEGY,
                "data": {"close": close},
                "mock_data": False,
                "initial_capital": 10000.0,
            },
            headers=_auth(api_key),
        )
        assert resp.status_code == 200, resp.json
        assert resp.json["meta"]["bars"] == 50


class TestComputeIndicatorHelpers:
    def test_sma_ema_rsi_macd_direct(self) -> None:
        close = list(range(1, 40))
        sma = preview_mod._compute_indicator("ta.sma(close, 5)", close)
        assert sma[3] is None
        assert sma[4] == pytest.approx(sum(close[:5]) / 5)
        ema = preview_mod._compute_indicator("ta.ema(close, 5)", close)
        assert ema[4] is not None
        rsi = preview_mod._compute_indicator("ta.rsi(close, 5)", close)
        assert any(v is not None for v in rsi)
        macd = preview_mod._compute_indicator("ta.macd(close)", close)
        assert len(macd) == len(close)
        assert preview_mod._compute_indicator("unknown", close) == close

    def test_short_series_helpers(self) -> None:
        assert all(v is None for v in preview_mod._ema([1.0, 2.0], 5))
        assert all(v is None for v in preview_mod._rsi([1.0, 2.0], 5))
        # flat series → rsi branch with avg_loss == 0
        flat = [10.0] * 20
        rsi = preview_mod._rsi(flat, 5)
        assert any(v == 100.0 for v in rsi if v is not None)
