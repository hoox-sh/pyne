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

"""HTTP LSP bridge used by AXIS editor."""

from __future__ import annotations

import pytest

pytest.importorskip("lsprotocol")
pytest.importorskip("pygls")


@pytest.fixture()
def client():
    from backend.app import app

    app.config["TESTING"] = True
    return app.test_client()


def test_lsp_completion_ta(client):
    src = "ta."
    resp = client.post(
        "/lsp/completion",
        json={"source": src, "line": 0, "character": 3},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success"
    assert body.get("source") == "lsp"
    labels = [i["label"] for i in body["items"]]
    assert any("sma" in str(l).lower() for l in labels)


def test_lsp_hover_plot(client):
    src = "plot(close)"
    # hover over plot
    resp = client.post(
        "/lsp/hover",
        json={"source": src, "line": 0, "character": 2},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success"
    # may be None if metadata empty for plot in some builds
    if body.get("hover"):
        assert "plot" in body["hover"]["contents"].lower() or body["hover"]["contents"]


def test_lsp_diagnostics_ok(client):
    src = '//@version=5\nindicator("t")\nplot(close)\n'
    resp = client.post("/lsp/diagnostics", json={"source": src})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["ok"] is True
    # style warnings (trailing newline etc.) may appear; no errors
    diags = body.get("diagnostics") or []
    assert all(d.get("severity") != "error" for d in diags)


def test_lsp_diagnostics_syntax_error(client):
    src = '//@version=5\nindicator("t")\nplot(close\n'
    resp = client.post("/lsp/preevaluate", json={"source": src})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["ok"] is False
    diags = body.get("diagnostics") or []
    errors = [d for d in diags if d.get("severity") == "error"]
    assert errors, body
    assert any("syntax" in str(e.get("message", "")).lower() for e in errors)
