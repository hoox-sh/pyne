# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import json
import urllib.error

from pathlib import Path
from typing import Any
from unittest.mock import patch

import click
import pytest

from click.testing import CliRunner

from pynescript.util import runner_cli
from pynescript.util.runner_cli import DEFAULT_URL
from pynescript.util.runner_cli import api_request
from pynescript.util.runner_cli import runner_group


MINI = """//@version=5
indicator("runner")
plot(close)
"""


class _Resp:
    def __init__(self, body: str | bytes, code: int = 200) -> None:
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.code = code
        self.status = code

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_api_request_rejects_non_http_scheme() -> None:
    with pytest.raises(click.ClickException, match="http:// or https://"):
        api_request("ftp://example.com", "GET", "/scripts")


def test_api_request_get_ok_and_empty() -> None:
    with patch("urllib.request.urlopen", return_value=_Resp('{"scripts":[]}')) as mock_open:
        out = api_request("http://127.0.0.1:5002", "GET", "/scripts", token=" secret ")
        assert out == {"scripts": []}
        req = mock_open.call_args[0][0]
        assert req.get_header("X-admin-token") == "secret" or req.headers.get("X-Admin-Token") == "secret"

    with patch("urllib.request.urlopen", return_value=_Resp("")):
        assert api_request(DEFAULT_URL, "GET", "/scripts") == {}


def test_api_request_post_json_body() -> None:
    with patch("urllib.request.urlopen", return_value=_Resp('{"ok":true}')) as mock_open:
        out = api_request(
            "https://api.example/",
            "POST",
            "/scripts",
            body={"id": "demo", "script": "x"},
            token="tok",
        )
        assert out["ok"] is True
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://api.example/scripts"
        assert req.data is not None
        assert json.loads(req.data.decode("utf-8"))["id"] == "demo"


def test_api_request_http_error_runner_disabled() -> None:
    err = urllib.error.HTTPError(
        "http://x/scripts",
        403,
        "Forbidden",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"code":"RUNNER_DISABLED","message":"off"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(click.ClickException, match="PYNE_RUNNER=1"):
            api_request(DEFAULT_URL, "GET", "/scripts")


def test_api_request_http_error_message_and_status() -> None:
    err = urllib.error.HTTPError(
        "http://x/scripts",
        400,
        "Bad",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"message":"bad id"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(click.ClickException, match="bad id"):
            api_request(DEFAULT_URL, "GET", "/scripts")

    err2 = urllib.error.HTTPError(
        "http://x/scripts",
        502,
        "Bad Gateway",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b"not-json"),
    )
    with patch("urllib.request.urlopen", side_effect=err2):
        with pytest.raises(click.ClickException, match="HTTP 502"):
            api_request(DEFAULT_URL, "GET", "/scripts")


def test_api_request_url_error_and_bad_json() -> None:
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("refused"),
    ):
        with pytest.raises(click.ClickException, match="Cannot reach"):
            api_request(DEFAULT_URL, "GET", "/scripts")

    with patch("urllib.request.urlopen", return_value=_Resp("not-json")):
        with pytest.raises(click.ClickException, match="non-JSON"):
            api_request(DEFAULT_URL, "GET", "/scripts")

    with patch("urllib.request.urlopen", return_value=_Resp("[1,2,3]")):
        with pytest.raises(click.ClickException, match="non-object"):
            api_request(DEFAULT_URL, "GET", "/scripts")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pine_file(tmp_path: Path) -> Path:
    path = tmp_path / "demo.pine"
    path.write_text(MINI, encoding="utf-8")
    return path


def _patch_api(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[tuple[str, str, dict | None]]:
    calls: list[tuple[str, str, dict | None]] = []

    def fake(url: str, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        body = kwargs.get("body") if isinstance(kwargs.get("body"), dict) else None
        calls.append((method, path, body))
        return handler(url, method, path, body)

    monkeypatch.setattr(runner_cli, "api_request", fake)
    return calls


def test_runner_list_empty_and_rows(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_api(monkeypatch, lambda *_a: {"scripts": []})
    r = runner.invoke(runner_group, ["list"])
    assert r.exit_code == 0
    assert "no hosted scripts" in r.output
    assert calls[0][0] == "GET"

    def with_rows(*_a: Any) -> dict[str, Any]:
        return {
            "scripts": [
                {"id": "a", "enabled": True, "symbol": "BTCUSDT", "timeframe": "1d", "data_source": "mock"},
                {"id": "b", "enabled": False, "symbol": "ETHUSDT", "timeframe": "1h", "data_source": "ccxt"},
            ]
        }

    _patch_api(monkeypatch, with_rows)
    r2 = runner.invoke(runner_group, ["list"])
    assert "a  on" in r2.output
    assert "b  off" in r2.output

    r3 = runner.invoke(runner_group, ["list", "--json"])
    assert r3.exit_code == 0
    assert json.loads(r3.output)["scripts"][0]["id"] == "a"


def test_runner_show_delete_enable_disable(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_url: str, method: str, path: str, body: dict | None) -> dict[str, Any]:
        if method == "GET":
            return {"script": {"id": "demo", "enabled": True}}
        if method == "DELETE":
            return {"deleted": "demo"}
        if method == "PUT":
            return {"updated": body}
        return {}

    calls = _patch_api(monkeypatch, handler)
    show = runner.invoke(runner_group, ["show", "demo"])
    assert show.exit_code == 0
    assert "demo" in show.output

    deleted = runner.invoke(runner_group, ["delete", "demo"])
    assert deleted.exit_code == 0
    assert "demo" in deleted.output

    en = runner.invoke(runner_group, ["enable", "demo"])
    assert en.exit_code == 0
    dis = runner.invoke(runner_group, ["disable", "demo"])
    assert dis.exit_code == 0
    assert any(c[0] == "PUT" and c[1] == "/cron/jobs" for c in calls)
    assert any(c[0] == "DELETE" and c[1] == "/scripts/demo" for c in calls)


def test_runner_jobs_and_tick_formats(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_url: str, method: str, path: str, body: dict | None) -> dict[str, Any]:
        if path == "/cron/jobs":
            return {
                "jobs": [
                    {
                        "id": "demo",
                        "enabled": True,
                        "cron": {"last_status": "ok", "last_bar_time": 123},
                    }
                ]
            }
        if path == "/cron/run":
            if body and body.get("force"):
                return {"jobs": [{"script_id": "demo", "status": "ok", "mode": "interpret"}]}
            return {"jobs": []}
        return {}

    _patch_api(monkeypatch, handler)
    jobs = runner.invoke(runner_group, ["jobs"])
    assert jobs.exit_code == 0
    assert "demo" in jobs.output
    assert "last=ok" in jobs.output

    jobs_json = runner.invoke(runner_group, ["jobs", "--json"])
    assert json.loads(jobs_json.output)["jobs"][0]["id"] == "demo"

    empty_tick = runner.invoke(runner_group, ["tick"])
    assert "no jobs" in empty_tick.output

    forced = runner.invoke(runner_group, ["tick", "--id", "demo", "--force", "--json"])
    assert forced.exit_code == 0
    payload = json.loads(forced.output)
    assert payload["jobs"][0]["status"] == "ok"


def test_runner_deploy_with_exchange_and_defaults(
    runner: CliRunner, pine_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def handler(_url: str, method: str, path: str, body: dict | None) -> dict[str, Any]:
        seen["body"] = body
        return {"script": {"id": body["id"] if body else "x", "data_source": "ccxt", "enabled": False}}

    _patch_api(monkeypatch, handler)
    r = runner.invoke(
        runner_group,
        [
            "deploy",
            str(pine_file),
            "--source",
            "ccxt",
            "--exchange",
            "kraken",
            "--disabled",
            "--symbol",
            "ETHUSDT",
            "--timeframe",
            "1h",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "deployed" in r.output
    body = seen["body"]
    assert body["id"] == "demo"
    assert body["data_source"] == "ccxt"
    assert body["enabled"] is False
    assert body["data_options"] == {"exchange": "kraken"}
    assert body["symbol"] == "ETHUSDT"
    assert "indicator" in body["script"]


def test_runner_group_stores_url_and_token(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake(url: str, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        captured["url"] = url
        captured["token"] = kwargs.get("token")
        return {"scripts": []}

    monkeypatch.setattr(runner_cli, "api_request", fake)
    r = runner.invoke(runner_group, ["--url", "https://pynescript.online/", "--token", "abc", "list"])
    assert r.exit_code == 0
    assert captured["url"] == "https://pynescript.online"
    assert captured["token"] == "abc"


def test_echo_json_helper(capsys: pytest.CaptureFixture[str]) -> None:
    runner_cli._echo_json({"a": 1, "b": Path(".")})
    out = capsys.readouterr().out
    assert '"a": 1' in out
