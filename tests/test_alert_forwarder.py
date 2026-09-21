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

"""Unit tests for Pro API alert webhook helpers (L2)."""

from __future__ import annotations

import pytest

from backend.alert_forwarder import build_alert_payload
from backend.alert_forwarder import filter_alerts_for_bar
from backend.alert_forwarder import forward_alerts
from backend.alert_forwarder import maybe_forward_run_alerts
from backend.alert_forwarder import normalize_webhook_url


def test_normalize_webhook_url() -> None:
    assert normalize_webhook_url("https://hooks.example/x") == "https://hooks.example/x"
    assert normalize_webhook_url("ftp://bad") is None
    assert normalize_webhook_url("") is None
    assert normalize_webhook_url("  ") is None


def test_normalize_webhook_url_blocks_ssrf_targets() -> None:
    """Audit 2026-08-10: private/loopback/metadata hosts are rejected by default."""
    from backend.alert_forwarder import is_webhook_url_safe

    assert normalize_webhook_url("http://127.0.0.1/hook") is None
    assert normalize_webhook_url("http://localhost/hook") is None
    assert normalize_webhook_url("http://10.0.0.5/hook") is None
    assert normalize_webhook_url("http://192.168.1.1/hook") is None
    assert normalize_webhook_url("http://169.254.169.254/latest/meta-data/") is None
    assert normalize_webhook_url("http://metadata.google.internal/") is None
    assert is_webhook_url_safe("https://hooks.example.com/x") is True


def test_normalize_webhook_url_blocks_mapped_and_decimal_loopback() -> None:
    """IPv4-mapped IPv6 and decimal IPv4 must not bypass the private-host check."""
    assert normalize_webhook_url("http://[::ffff:127.0.0.1]/hook") is None
    assert normalize_webhook_url("http://[::ffff:169.254.169.254]/latest/meta-data/") is None
    assert normalize_webhook_url("http://[::ffff:10.0.0.5]/hook") is None
    assert normalize_webhook_url("http://2130706433/hook") is None  # 127.0.0.1


def test_http_post_json_rejects_blocked_url() -> None:
    from backend.alert_forwarder import http_post_json

    with pytest.raises(ValueError, match="blocked"):
        http_post_json("http://127.0.0.1/hook", {"a": 1})


def test_http_post_json_does_not_follow_redirect(monkeypatch) -> None:
    """Public-looking 302 must not be followed (SSRF via Location)."""
    import threading

    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer

    from backend.alert_forwarder import http_post_json

    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_POST(self) -> None:
            hits.append(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            if self.path == "/hook":
                self.send_response(302)
                self.send_header("Location", "/private")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    port = int(httpd.server_address[1])
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("ALERT_WEBHOOK_ALLOW_PRIVATE", "1")
        status = http_post_json(f"http://127.0.0.1:{port}/hook", {"x": 1})
        assert status == 302
        assert hits == ["/hook"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_normalize_webhook_url_allow_private_env(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_WEBHOOK_ALLOW_PRIVATE", "1")
    assert normalize_webhook_url("http://10.0.0.5/hook") == "http://10.0.0.5/hook"
    assert normalize_webhook_url("http://127.0.0.1/hook") == "http://127.0.0.1/hook"


def test_filter_last_bar() -> None:
    alerts = [
        {"message": "a", "time": 100, "bar_index": 0},
        {"message": "b", "time": 200, "bar_index": 1},
    ]
    out = filter_alerts_for_bar(alerts, 200)
    assert [a["message"] for a in out] == ["b"]


def test_build_payload() -> None:
    p = build_alert_payload({"message": "hi", "title": "T", "source": "alertcondition"})
    assert p["source"] == "pyne-pro-api"
    assert p["content"] == "**T**: hi"
    assert p["alert_source"] == "alertcondition"


def test_forward_batch() -> None:
    posted: list[dict] = []

    def post(url: str, body: dict) -> int:
        posted.append(body)
        return 204

    meta = forward_alerts(
        [{"message": "a"}, {"message": "b"}],
        "https://hooks.test/",
        http_post=post,
        batch=True,
    )
    assert meta["forwarded"] == 2
    assert posted[0]["type"] == "pine_alert_batch"
    assert posted[0]["count"] == 2


def test_maybe_forward_last_bar_only() -> None:
    posted: list[dict] = []

    def post(url: str, body: dict) -> int:
        posted.append(body)
        return 200

    ohlcv = [
        {"time": 100, "open": 1, "high": 1, "low": 1, "close": 1},
        {"time": 200, "open": 1, "high": 1, "low": 1, "close": 1},
    ]
    meta = maybe_forward_run_alerts(
        alerts=[
            {"message": "old", "time": 100, "bar_index": 0},
            {"message": "new", "time": 200, "bar_index": 1},
        ],
        ohlcv=ohlcv,
        webhook_url="https://hooks.test/",
        enable_forward=True,
        alert_last_bar=True,
        http_post=post,
    )
    assert meta is not None
    assert meta["forwarded"] == 1
    assert meta["filter"] == "last_bar"
    assert posted[0]["alerts"][0]["message"] == "new"


def test_forward_exception_does_not_leak_message() -> None:
    """Webhook transport failures must not echo exception text to the client."""
    secret = "secret traceback details"

    def boom(_url: str, _body: dict) -> int:
        raise RuntimeError(secret)

    meta = forward_alerts(
        [{"message": "a"}],
        "https://hooks.test/",
        http_post=boom,
        batch=True,
    )
    assert meta["failed"] == 1
    assert meta["errors"] == ["forward failed"]
    blob = str(meta)
    assert "secret" not in blob
    assert "traceback" not in blob
    assert "RuntimeError" not in blob


def test_forward_per_alert_exception_does_not_leak_message() -> None:
    secret = "connection reset by peer: internal host"

    def boom(_url: str, _body: dict) -> int:
        raise OSError(secret)

    meta = forward_alerts(
        [{"message": "a", "bar_index": 3}],
        "https://hooks.test/",
        http_post=boom,
        batch=False,
    )
    assert meta["failed"] == 1
    assert meta["errors"] == ["bar 3: forward failed"]
    blob = str(meta)
    assert "connection reset" not in blob
    assert "internal host" not in blob
