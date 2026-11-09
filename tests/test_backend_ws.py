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

"""WebSocket run channel (``WS /ws/run``) suite.

The WS envelope must have the same surface as ``POST /run``: optional fields
(``libraries`` included) used to be dropped by the envelope mapper, so
published-library imports resolved over REST but failed over WS.

The end-to-end test runs the real Flask app on a background thread and talks to
it with a real WebSocket client (werkzeug's dev server exposes
``werkzeug.socket``, which ``simple_websocket`` hijacks — the same mechanism
flask-sock uses under gunicorn).
"""

from __future__ import annotations

import json
import threading

import pytest

from backend.app import _ws_envelope_to_payload
from backend.app import app


pytest.importorskip("simple_websocket")
pytest.importorskip("flask_sock")

from simple_websocket import Client


_BARS = [
    {"open": 100, "high": 105, "low": 98, "close": 102, "time": 1},
    {"open": 102, "high": 108, "low": 101, "close": 105, "time": 2},
]

_LIB_SOURCE = """//@version=6
library("Lib")
export const float FOO = 1.5
"""


class TestWsEnvelopePayload:
    """Envelope → REST body mapping (unit level)."""

    def test_forwards_libraries(self):
        payload = _ws_envelope_to_payload(
            {
                "type": "run",
                "id": "r1",
                "script": "//@version=6\nplot(close)",
                "data": _BARS,
                "libraries": [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_SOURCE}],
            }
        )
        assert payload["libraries"][0]["namespace"] == "ns"

    def test_forwards_optional_run_fields(self):
        payload = _ws_envelope_to_payload(
            {
                "script": "//@version=6\nplot(close)",
                "data": _BARS,
                "symbol": "BTCUSDT",
                "mode": "interpret",
                "inputs": {"n": 2},
                "profiler": True,
                "timeout_seconds": 30.0,
                "timeframe": "1m",
            }
        )
        assert payload["symbol"] == "BTCUSDT"
        assert payload["mode"] == "interpret"
        assert payload["inputs"] == {"n": 2}
        assert payload["profiler"] is True
        assert payload["timeout_seconds"] == 30.0
        assert payload["timeframe"] == "1m"

    def test_omits_null_optionals(self):
        payload = _ws_envelope_to_payload(
            {"script": "//@version=6\nplot(close)", "data": _BARS, "symbol": None, "libraries": None}
        )
        assert "symbol" not in payload
        assert "libraries" not in payload

    def test_keeps_script_and_data(self):
        payload = _ws_envelope_to_payload({"script": "//@version=6\nplot(close)", "data": _BARS})
        assert payload["script"].startswith("//@version=6")
        assert payload["data"] == _BARS


@pytest.fixture
def ws_server():
    """Serve the Flask app on a background thread and yield its WS URL."""
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    try:
        yield f"ws://{host}:{port}/ws/run"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _roundtrip(ws_url: str, frame: dict) -> dict:
    client = Client(ws_url)
    try:
        client.send(json.dumps(frame))
        return json.loads(client.receive(timeout=30))
    finally:
        client.close()


class TestWsRun:
    """End-to-end ``WS /ws/run`` frames."""

    def test_run_frame_returns_result(self, ws_server: str):
        reply = _roundtrip(
            ws_server,
            {
                "type": "run",
                "id": "r1",
                "script": '//@version=6\nindicator("ws")\nplot(close)',
                "data": _BARS,
                "mode": "interpret",
                "symbol": "BTCUSDT",
            },
        )
        assert reply["type"] == "result", reply
        assert reply["id"] == "r1"
        assert reply["status"] == "success", reply
        assert reply["plots"] == [102, 105]

    def test_run_frame_resolves_library_import(self, ws_server: str):
        """``libraries`` must reach the evaluator over WS (AXIS library imports)."""
        script = """//@version=6
indicator("ws lib")
import ns/Lib/1 as x
plot(x.FOO)
"""
        reply = _roundtrip(
            ws_server,
            {
                "type": "run",
                "id": "r2",
                "script": script,
                "data": _BARS,
                "mode": "interpret",
                "libraries": [
                    {"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_SOURCE},
                ],
            },
        )
        assert reply["type"] == "result", reply
        assert reply["status"] == "success", reply
        assert reply["plots"] == [1.5, 1.5]

    def test_ping_frame_returns_pong(self, ws_server: str):
        reply = _roundtrip(ws_server, {"type": "ping", "id": "p1"})
        assert reply["type"] == "pong"
        assert reply["id"] == "p1"
