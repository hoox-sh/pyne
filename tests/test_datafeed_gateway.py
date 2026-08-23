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

from backend.api import datafeed as datafeed_mod
from backend.app import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> FlaskClient:
    app.config["TESTING"] = True
    monkeypatch.setenv("ADMIN_TOKEN", "test-datafeed-token")
    monkeypatch.setenv("STORE_BACKEND", "json")
    monkeypatch.setenv("API_KEY_STORE", str(tmp_path / "api_keys.json"))
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    datafeed_mod._sessions.clear()
    yield
    datafeed_mod._sessions.clear()


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
        mock_provider.fetch_ohlcv.return_value = [
            [1_700_000_000_000, 100.0, 105.0, 95.0, 102.0, 1000.0],
            [1_700_003_600_000, 102.0, 108.0, 101.0, 106.0, 1200.0],
        ]
        mock_make.return_value = mock_provider

        resp = client.get("/datafeed/ohlcv?exchange=binance&symbol=BTC/USDT&timeframe=1h&limit=2")
        assert resp.status_code == 200
        bars = resp.json
        assert len(bars) == 2
        assert bars[0]["open"] == 100.0
        assert bars[0]["close"] == 102.0
        assert bars[0]["time"] == 1_700_000_000
        assert bars[1]["open"] == 102.0
        assert bars[1]["close"] == 106.0
        assert bars[1]["time"] == 1_700_003_600
        mock_provider.fetch_ohlcv.assert_called_once_with(
            symbol="BTC/USDT", timeframe="1h", since=None, limit=2
        )

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_passes_since_and_limit(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_provider = MagicMock()
        mock_provider.fetch_ohlcv.return_value = []
        mock_make.return_value = mock_provider

        # AXIS walk-back: since = endTime*1000 - 100 * 3_600_000
        resp = client.get(
            "/datafeed/ohlcv?exchange=okx&symbol=ETH/USDT&timeframe=1h"
            "&since=1699640000000&limit=100"
        )
        assert resp.status_code == 200
        mock_provider.fetch_ohlcv.assert_called_once_with(
            symbol="ETH/USDT", timeframe="1h", since=1_699_640_000_000, limit=100
        )

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_passes_unknown_timeframe(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_provider = MagicMock()
        mock_provider.fetch_ohlcv.return_value = []
        mock_make.return_value = mock_provider
        resp = client.get("/datafeed/ohlcv?exchange=binance&symbol=BTC/USDT&timeframe=3m&limit=10")
        assert resp.status_code == 200
        mock_provider.fetch_ohlcv.assert_called_once_with(
            symbol="BTC/USDT", timeframe="3m", since=None, limit=10
        )

    @patch("backend.api.datafeed._make_provider")
    def test_fetch_ohlcv_ccxt_error(self, mock_make: MagicMock, client: FlaskClient) -> None:
        mock_provider = MagicMock()
        mock_provider.fetch_ohlcv.side_effect = Exception("Network error")
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

    def test_bind_axis_body_and_unbind_cred(self, client: FlaskClient) -> None:
        resp = client.post(
            "/datafeed/session",
            json={
                "exchange": "bybit",
                "credentialId": "ccxt:bybit",
                "apiKey": "AK-live",
                "secret": "SK-live",
                "password": "pp",
                "uid": "uid-1",
            },
        )
        assert resp.status_code == 204
        health = client.get("/datafeed/health")
        assert "bybit" in health.json["active_sessions"]
        assert datafeed_mod._sessions["bybit"]["password"] == "pp"  # noqa: S105
        assert datafeed_mod._sessions["ccxt:bybit"]["uid"] == "uid-1"

        resp = client.delete("/datafeed/session?cred=ccxt:bybit")
        assert resp.status_code == 204
        health = client.get("/datafeed/health")
        assert "bybit" not in health.json["active_sessions"]

    @patch("pynescript.util.data.CCXTProvider")
    def test_ohlcv_forwards_password_uid(self, mock_cls: MagicMock, client: FlaskClient) -> None:
        mock_inst = MagicMock()
        mock_inst.fetch_ohlcv.return_value = []
        mock_cls.return_value = mock_inst
        client.post(
            "/datafeed/session",
            json={
                "exchange": "okx",
                "credentialId": "ccxt:okx",
                "apiKey": "k",
                "secret": "s",
                "password": "passphrase",
                "uid": "u1",
            },
        )
        resp = client.get("/datafeed/ohlcv?exchange=okx&symbol=BTC/USDT&cred=ccxt:okx&limit=1")
        assert resp.status_code == 200
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["api_key"] == "k"
        assert kwargs["secret"] == "s"  # noqa: S105
        assert kwargs["password"] == "passphrase"  # noqa: S105
        assert kwargs["uid"] == "u1"


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


class TestCandleHelpers:
    def test_candle_to_bar_ms_timestamp(self) -> None:
        bar = datafeed_mod._candle_to_bar([1_700_000_000_000, 1, 2, 0.5, 1.5, 10])
        assert bar is not None
        assert bar["time"] == 1_700_000_000
        assert bar["open"] == 1.0
        assert bar["high"] == 2.0
        assert bar["low"] == 0.5
        assert bar["close"] == 1.5
        assert bar["volume"] == 10.0

    def test_latest_candle_from_watch_batch(self) -> None:
        raw = [
            [1, 1, 1, 1, 1, 1],
            [2, 2, 2, 2, 2, 2],
        ]
        assert datafeed_mod._latest_candle(raw) == [2, 2, 2, 2, 2, 2]


class TestCcxtProviderPassThrough:
    def test_parse_timeframe_does_not_remap_unknown(self) -> None:
        from pynescript.util.data import CCXTProvider

        p = CCXTProvider(exchange="binance")
        assert p._parse_timeframe("3m") == "3m"
        assert p._parse_timeframe("12h") == "12h"
        assert p._parse_timeframe("1M") == "1M"

    def test_constructor_stores_password_uid(self) -> None:
        from pynescript.util.data import CCXTProvider

        p = CCXTProvider(exchange="okx", api_key="k", secret="s", password="pp", uid="u")  # noqa: S106
        assert p._password == "pp"  # noqa: S105
        assert p._uid == "u"

    def test_fetch_ohlcv_forwards_since_limit_timeframe(self) -> None:
        from pynescript.util.data import CCXTProvider

        p = CCXTProvider(exchange="binance")
        ex = MagicMock()
        ex.fetch_ohlcv.return_value = [[1_700_000_000_000, 1, 1, 1, 1, 1]]
        p._exchange = ex
        out = p.fetch_ohlcv("BTC/USDT", "3m", since=10, limit=50)
        ex.fetch_ohlcv.assert_called_once_with("BTC/USDT", "3m", 10, 50)
        assert out == [[1_700_000_000_000, 1, 1, 1, 1, 1]]

    def test_fetch_ohlcv_rewrites_coinbase_usdt(self) -> None:
        from pynescript.util.data import CCXTProvider

        p = CCXTProvider(exchange="coinbase")
        ex = MagicMock()
        ex.fetch_ohlcv.return_value = [[1_700_000_000_000, 1, 1, 1, 1, 1]]
        p._exchange = ex
        p.fetch_ohlcv("BTC/USDT", "1m", since=None, limit=2)
        ex.fetch_ohlcv.assert_called_once_with("BTC/USD", "1m", None, 2)

    def test_tune_binance_spot_uses_vision_host(self) -> None:
        from types import SimpleNamespace

        from pynescript.util.data import tune_ccxt_public_urls

        ex = SimpleNamespace(
            urls={
                "api": {
                    "public": "https://api.binance.com/api/v3",
                    "private": "https://api.binance.com/api/v3",
                    "fapiPublic": "https://fapi.binance.com/fapi/v1",
                }
            },
            options={},
        )
        tune_ccxt_public_urls(ex, "binance")
        assert ex.urls["api"]["public"].startswith("https://data-api.binance.vision")
        assert ex.urls["api"]["fapiPublic"].startswith("https://fapi.binance.com")
        assert ex.options["fetchMarkets"] == ["spot"]
        tune_ccxt_public_urls(ex, "okx")  # no-op

    def test_normalize_coinbase_usdt_to_usd(self) -> None:
        from pynescript.util.data import normalize_ccxt_symbol

        assert normalize_ccxt_symbol("coinbase", "BTC/USDT") == "BTC/USD"
        assert normalize_ccxt_symbol("coinbase", "ETH/USDC") == "ETH/USD"
        assert normalize_ccxt_symbol("binance", "BTC/USDT") == "BTC/USDT"

    def test_geo_block_message(self) -> None:
        from pynescript.util.data import geo_block_message

        err = RuntimeError(
            "bybit GET https://api.bybit.com 403 Forbidden "
            "{ error:The Amazon CloudFront distribution is configured to block access from your country }"
        )
        msg = geo_block_message("bybit", err)
        assert msg is not None
        assert "blocked from this host" in msg
        assert "kraken" in msg
        assert geo_block_message("okx", RuntimeError("timeout")) is None


class TestWatchRestPoll:
    def test_poll_emits_latest_bar_then_stops(self) -> None:
        import queue
        import threading

        provider = MagicMock()
        provider.fetch_ohlcv.return_value = [
            [1_700_000_000_000, 1, 2, 0.5, 1.5, 10],
        ]
        out: queue.Queue = queue.Queue()
        stop = threading.Event()

        def _run() -> None:
            datafeed_mod.watch_rest_poll(provider, "BTC/USDT", "1m", out, stop)

        prev = datafeed_mod._WATCH_POLL_SEC
        datafeed_mod._WATCH_POLL_SEC = 0.01
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        try:
            bar = out.get(timeout=2.0)
            stop.set()
            t.join(timeout=2.0)
        finally:
            stop.set()
            datafeed_mod._WATCH_POLL_SEC = prev
        assert bar["time"] == 1_700_000_000
        assert bar["close"] == 1.5
