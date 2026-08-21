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

"""Tests for the datafeed gateway blueprint."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from backend.app import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> FlaskClient:
    app.config["TESTING"] = True
    monkeypatch.setenv("ADMIN_TOKEN", "test-datafeed-token")
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys.json"))
    with app.test_client() as c:
        yield c


class TestHealth:
    def test_health_returns_200(self, client: FlaskClient) -> None:
        resp = client.get("/datafeed/health")
        assert resp.status_code == 200
        data = resp.json
        assert data["status"] == "ok"
        assert "exchanges" in data
        assert "binance" in data["exchanges"]
        assert "ccxt" in data

    def test_health_shows_active_sessions(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "k")
        monkeypatch.setenv("BINANCE_SECRET", "s")
        client.post("/datafeed/session", json={"exchange": "binance"})
        resp = client.get("/datafeed/health")
        assert resp.status_code == 200
        assert "binance" in resp.json["active_sessions"]


class TestOhlcv:
    def test_missing_exchange(self, client: FlaskClient) -> None:
        resp = client.get("/datafeed/ohlcv?symbol=BTC/USDT")
        assert resp.status_code == 400
        assert "exchange" in resp.json["error"]

    def test_missing_symbol(self, client: FlaskClient) -> None:
        resp = client.get("/datafeed/ohlcv?exchange=binance")
        assert resp.status_code == 400
        assert "symbol" in resp.json["error"]

    def test_missing_both(self, client: FlaskClient) -> None:
        resp = client.get("/datafeed/ohlcv")
        assert resp.status_code == 400

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_success(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = {
            "symbol": "BTC/USDT",
            "open": [100.0, 102.0],
            "high": [105.0, 108.0],
            "low": [95.0, 101.0],
            "close": [102.0, 106.0],
            "volume": [1000.0, 1200.0],
        }
        mock_make.return_value = mock_provider

        resp = client.get("/datafeed/ohlcv?exchange=binance&symbol=BTC/USDT&timeframe=1h&limit=2")
        assert resp.status_code == 200
        bars = resp.json
        assert len(bars) == 2
        assert bars[0]["open"] == 100.0
        assert bars[0]["close"] == 102.0
        assert bars[1]["open"] == 102.0
        assert bars[1]["close"] == 106.0
        assert isinstance(bars[0]["time"], int)
        assert isinstance(bars[1]["time"], int)

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_limit_slicing(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_provider = MagicMock()
        mock_provider.fetch.return_value = {
            "symbol": "ETH/USDT",
            "open": [1.0, 2.0, 3.0, 4.0, 5.0],
            "high": [1.1, 2.1, 3.1, 4.1, 5.1],
            "low": [0.9, 1.9, 2.9, 3.9, 4.9],
            "close": [1.05, 2.05, 3.05, 4.05, 5.05],
            "volume": [100.0, 200.0, 300.0, 400.0, 500.0],
        }
        mock_make.return_value = mock_provider

        resp = client.get("/datafeed/ohlcv?exchange=binance&symbol=ETH/USDT&limit=2")
        assert resp.status_code == 200
        bars = resp.json
        assert len(bars) == 2
        assert bars[0]["open"] == 4.0
        assert bars[1]["open"] == 5.0

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_ccxt_error(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_provider = MagicMock()
        mock_provider.fetch.side_effect = Exception("Network error")
        mock_make.return_value = mock_provider

        resp = client.get("/datafeed/ohlcv?exchange=binance&symbol=BTC/USDT")
        assert resp.status_code == 502
        assert "error" in resp.json

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_no_ccxt(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_make.return_value = None
        resp = client.get("/datafeed/ohlcv?exchange=binance&symbol=BTC/USDT")
        assert resp.status_code == 503
        assert "CCXT" in resp.json["error"]


class TestSession:
    def test_bind_missing_exchange(self, client: FlaskClient) -> None:
        resp = client.post("/datafeed/session", json={})
        assert resp.status_code == 400

    def test_bind_no_credentials(self, client: FlaskClient) -> None:
        resp = client.post("/datafeed/session", json={"exchange": "unknown"})
        assert resp.status_code == 404

    def test_bind_and_unbind(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.setenv("BINANCE_API_KEY", "test-key")
        monkeypatch.setenv("BINANCE_SECRET", "test-secret")

        resp = client.post("/datafeed/session", json={"exchange": "binance"})
        assert resp.status_code == 204

        health = client.get("/datafeed/health")
        assert "binance" in health.json["active_sessions"]

        resp = client.delete("/datafeed/session?exchange=binance")
        assert resp.status_code == 204

        health = client.get("/datafeed/health")
        assert "binance" not in health.json["active_sessions"]

    def test_unbind_missing_exchange(self, client: FlaskClient) -> None:
        resp = client.delete("/datafeed/session")
        assert resp.status_code == 400


class TestMarkets:
    def test_missing_exchange(self, client: FlaskClient) -> None:
        resp = client.get("/datafeed/markets")
        assert resp.status_code == 400

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_markets_success(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_exchange = MagicMock()
        mock_exchange.fetch_markets.return_value = [
            {"symbol": "BTC/USDT", "base": "BTC", "quote": "USDT", "active": True},
            {"symbol": "ETH/USDT", "base": "ETH", "quote": "USDT", "active": True},
        ]
        mock_provider = MagicMock()
        mock_provider._get_exchange.return_value = mock_exchange
        mock_make.return_value = mock_provider

        resp = client.get("/datafeed/markets?exchange=binance")
        assert resp.status_code == 200
        markets = resp.json
        assert len(markets) == 2
        assert markets[0]["symbol"] == "BTC/USDT"
        assert markets[0]["base"] == "BTC"
        assert markets[1]["symbol"] == "ETH/USDT"

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_markets_error(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_exchange = MagicMock()
        mock_exchange.fetch_markets.side_effect = Exception("Timeout")
        mock_provider = MagicMock()
        mock_provider._get_exchange.return_value = mock_exchange
        mock_make.return_value = mock_provider

        resp = client.get("/datafeed/markets?exchange=binance")
        assert resp.status_code == 502
        assert "error" in resp.json

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_markets_no_ccxt(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_make.return_value = None
        resp = client.get("/datafeed/markets?exchange=binance")
        assert resp.status_code == 503


class TestRunSecretRefusal:
    """POST /run must refuse inline api_key/secret unless DATAFEED_ALLOW_INLINE_KEYS=1."""

    def test_refuses_inline_api_key(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.delenv("DATAFEED_ALLOW_INLINE_KEYS", raising=False)
        resp = client.post(
            "/run",
            json={
                "script": 'indicator("test")',
                "data": [],
                "data_source": "chart",
                "data_options": {"api_key": "secret-key", "secret": "secret-value"},
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        body = resp.json
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "not allowed" in msg

    def test_refuses_only_api_key(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.delenv("DATAFEED_ALLOW_INLINE_KEYS", raising=False)
        resp = client.post(
            "/run",
            json={
                "script": 'indicator("test")',
                "data": [],
                "data_source": "chart",
                "data_options": {"api_key": "key-only"},
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        body = resp.json
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "not allowed" in msg

    def test_refuses_only_secret(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.delenv("DATAFEED_ALLOW_INLINE_KEYS", raising=False)
        resp = client.post(
            "/run",
            json={
                "script": 'indicator("test")',
                "data": [],
                "data_source": "chart",
                "data_options": {"secret": "secret-only"},
            },
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        body = resp.json
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "not allowed" in msg

    def test_allows_inline_when_flag_set(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.setenv("DATAFEED_ALLOW_INLINE_KEYS", "1")
        resp = client.post(
            "/run",
            json={
                "script": 'indicator("test")',
                "data": [],
                "data_source": "chart",
                "data_options": {"api_key": "key", "secret": "secret"},
            },
            headers={"Content-Type": "application/json"},
        )
        body = resp.json
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "not allowed" not in msg

    def test_no_data_options_is_fine(self, client: FlaskClient, monkeypatch) -> None:
        monkeypatch.delenv("DATAFEED_ALLOW_INLINE_KEYS", raising=False)
        resp = client.post(
            "/run",
            json={
                "script": 'indicator("test")',
                "data": [],
                "data_source": "chart",
            },
            headers={"Content-Type": "application/json"},
        )
        body = resp.json
        msg = (body.get("message") or body.get("error") or "").lower()
        assert "not allowed" not in msg
