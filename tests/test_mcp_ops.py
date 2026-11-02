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

"""Ops-layer tests for PYNE MCP (no MCP SDK required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pynescript.mcp.catalog import TOOL_NAMES
from pynescript.mcp.dispatch import call_tool
from pynescript.mcp.dispatch import parse_kv
from pynescript.mcp.dispatch import resolve_tool_name
from pynescript.mcp.ops.builtins import lookup_builtin
from pynescript.mcp.ops.compile import compile_source
from pynescript.mcp.ops.compile import run_synthetic
from pynescript.mcp.ops.data import fetch_data
from pynescript.mcp.ops.execute import execute_source
from pynescript.mcp.ops.execute import parity_source
from pynescript.mcp.ops.info import info_payload
from pynescript.mcp.ops.language import check_sources
from pynescript.mcp.ops.language import convert_source
from pynescript.mcp.ops.language import diagnostics_source
from pynescript.mcp.ops.language import dump_source
from pynescript.mcp.ops.language import format_source
from pynescript.mcp.ops.language import lint_source
from pynescript.mcp.ops.language import parse_source
from pynescript.mcp.ops.language import symbols_source
from pynescript.mcp.ops.lsp import complete_source
from pynescript.mcp.ops.lsp import hover_source
from pynescript.mcp.serialize import jsonable
from pynescript.mcp.serialize import split_plots
from pynescript.mcp.serialize import strip_secrets
from pynescript.mcp.server import client_config
from pynescript.mcp.server import serve_kwargs_from_env


MINI = """//@version=5
indicator("cli_smoke")
plot(close)
"""

SMA = """//@version=6
indicator("sma")
plot(ta.sma(close, 5))
"""

BAD = """//@version=6
indicator("bad"
plot(close)
"""


def test_info_payload_shape() -> None:
    payload = info_payload()
    assert payload["ok"] is True
    assert payload["name"] == "pynescript"
    assert payload["distribution"] == "hoox-pyne"
    assert payload["entry_points"]["mcp"] == "pyne-mcp"
    assert payload["entry_points"]["cli"] == "pyne"


def test_client_config() -> None:
    cfg = client_config()
    assert cfg["mcpServers"]["pyne"]["command"] == "pyne-mcp"
    mod = client_config(module=True)
    assert mod["mcpServers"]["pyne"]["args"] == ["-m", "pynescript.mcp"]


def test_serve_kwargs_from_env_stdio_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYNE_MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("PYNE_MCP_HOST", raising=False)
    monkeypatch.delenv("PYNE_MCP_PORT", raising=False)
    transport, kwargs = serve_kwargs_from_env()
    assert transport == "stdio"
    assert kwargs == {}


def test_serve_kwargs_from_env_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYNE_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("PYNE_MCP_HOST", "0.0.0.0")  # noqa: S104 — compose bind
    monkeypatch.setenv("PYNE_MCP_PORT", "8080")
    transport, kwargs = serve_kwargs_from_env()
    assert transport == "streamable-http"
    assert kwargs == {"host": "0.0.0.0", "port": 8080}  # noqa: S104


def test_serve_kwargs_from_env_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYNE_MCP_TRANSPORT", "websocket")
    with pytest.raises(ValueError, match="Unknown PYNE_MCP_TRANSPORT"):
        serve_kwargs_from_env()


def test_parse_ok() -> None:
    result = parse_source(MINI)
    assert result["ok"] is True
    assert result["kind"] == "indicator"
    assert result["title"] == "cli_smoke"
    assert result["version"] == 5
    assert result["errors"] == []


def test_parse_error_located() -> None:
    result = parse_source(BAD)
    assert result["ok"] is False
    assert result["kind"] == "parse"
    assert result.get("line")


def test_check_source_and_path(tmp_path: Path) -> None:
    pine = tmp_path / "ok.pine"
    pine.write_text(MINI, encoding="utf-8")
    one = check_sources(source=MINI)
    assert one["ok"] is True
    assert one["fail_count"] == 0
    many = check_sources(path=str(pine))
    assert many["fail_count"] == 0
    bad = check_sources(source=BAD)
    assert bad["fail_count"] == 1


def test_format_and_convert() -> None:
    formatted = format_source(MINI)
    assert formatted["ok"] is True
    assert "indicator" in formatted["source"]
    converted = convert_source(MINI, to=6)
    assert converted["ok"] is True
    assert "//@version=6" in converted["source"] or converted["to"] == 6


def test_lint_and_diagnostics() -> None:
    linted = lint_source(MINI)
    assert linted["ok"] is True
    assert isinstance(linted["findings"], list)
    diag = diagnostics_source(BAD)
    assert diag["ok"] is True
    assert any(item["severity"] == "error" for item in diag["diagnostics"])


def test_dump_and_symbols() -> None:
    dumped = dump_source(MINI)
    assert dumped["ok"] is True
    assert "Script" in dumped["dump"]
    assert dumped.get("tree", {}).get("_type") == "Script"
    outline = symbols_source(MINI)
    assert outline["ok"] is True
    kinds = {s["kind"] for s in outline["symbols"]}
    assert "plot" in kinds


def test_builtin_lookup() -> None:
    hit = lookup_builtin("ta.sma")
    assert hit["ok"] is True
    assert hit["name"] == "ta.sma"
    miss = lookup_builtin("not.a.real.builtin.zzz")
    assert miss["ok"] is False


def test_compile_emit() -> None:
    result = compile_source(MINI, emit=True)
    assert result["ok"] is True
    assert "def " in result["python"] or "execute" in result["python"]


def test_run_synthetic() -> None:
    result = run_synthetic(MINI, bars=16, sample=4)
    assert result["ok"] is True
    assert result["bars"] == 16
    assert result["plots"]
    first = next(iter(result["plots"].values()))
    assert first["len"] == 16
    assert len(first["sample"]) <= 4


def test_split_plots_runtime_envelope() -> None:
    plots, extras = split_plots(
        {
            "plots": [1.0, 2.0, 110.6],
            "series": {"sma": [1.0, 2.0, 110.6]},
            "mode": "compile",
            "compile_ms": 12.3,
            "run_ms": 4.1,
            "compile_cached": False,
            "object_mode": False,
            "events": [{"type": "entry"}],
            "count": 3,
        }
    )
    assert list(plots) == ["sma"]
    assert plots["sma"]["last"] == 110.6
    assert "compile_ms" not in plots
    assert extras["compile_ms"] == 12.3
    assert extras["events_count"] == 1
    assert "events" not in extras


def test_split_plots_compiled_map() -> None:
    plots, extras = split_plots({"plot": [1, 2, 3], "__events": [{"x": 1}, {"x": 2}]})
    assert plots["plot"]["len"] == 3
    assert extras["__events_count"] == 2


def test_execute_interpret() -> None:
    result = execute_source(MINI, bars=20, mode="interpret", sample=4)
    assert result["ok"] is True
    assert result["bars"] == 20
    assert result["plots"]
    assert "compile_ms" not in result["plots"]
    first = next(iter(result["plots"].values()))
    assert first["len"] == 20
    encoded = str(result)
    assert len(encoded) < 200_000


def test_parity_sma() -> None:
    result = parity_source(SMA, bars=24)
    assert result["ok"] is True
    assert result["match"] is True
    assert result["mismatches"] == []


def test_data_mock() -> None:
    result = fetch_data("AAPL", provider="mock", period="1mo")
    assert result["ok"] is True
    assert result["bars"] > 0
    assert result["provider"] == "mock"


def test_hover_sma() -> None:
    src = "plot(ta.sma(close, 14))\n"
    col = src.index("sma")
    result = hover_source(src, line=0, character=col)
    if not result["ok"] and result.get("kind") == "io":
        return
    assert result["ok"] is True
    assert result["found"] is True
    assert "sma" in (result.get("markdown") or "").lower() or "ta.sma" in (result.get("markdown") or "")


def test_complete_ta_dot() -> None:
    src = "ta."
    result = complete_source(src, line=0, character=3, limit=10)
    if not result["ok"] and result.get("kind") == "io":
        return
    assert result["ok"] is True
    labels = [i["label"] for i in result["items"]]
    assert labels


def test_jsonable_nan_and_strip_secrets() -> None:
    assert jsonable(float("nan")) is None
    redacted = strip_secrets({"api_key": "secret", "symbol": "BTC"})
    assert redacted["api_key"] == "***"
    assert redacted["symbol"] == "BTC"


def test_resolve_tool_name_aliases() -> None:
    assert resolve_tool_name("pyne_lint") == "pyne_lint"
    assert resolve_tool_name("lint") == "pyne_lint"
    assert resolve_tool_name("pyne-execute") == "pyne_execute"
    assert resolve_tool_name("not-a-tool") is None
    assert resolve_tool_name("") is None


def test_parse_kv_json_and_string() -> None:
    assert parse_kv("bars=24") == ("bars", 24)
    assert parse_kv("mode=interpret") == ("mode", "interpret")
    assert parse_kv("flag=true") == ("flag", True)
    assert parse_kv("name=ta.sma") == ("name", "ta.sma")


def test_call_tool_lint_and_alias() -> None:
    named = call_tool("pyne_lint", {"source": MINI})
    short = call_tool("lint", {"source": MINI})
    assert named["ok"] is True
    assert short["ok"] is True
    assert isinstance(named["findings"], list)


def test_call_tool_execute_and_unknown() -> None:
    executed = call_tool("execute", {"source": MINI, "bars": 16, "mode": "interpret", "sample": 4})
    assert executed["ok"] is True
    assert executed["bars"] == 16
    assert executed["plots"]
    unknown = call_tool("nope")
    assert unknown["ok"] is False
    assert unknown["kind"] == "io"
    assert "pyne_lint" in unknown["tools"]


def test_call_tool_covers_catalog() -> None:
    from pynescript.mcp.dispatch import _handlers

    assert set(_handlers()) == set(TOOL_NAMES)


def test_call_axb1_verifies_bundled_vectors() -> None:
    from pynescript.mcp.ops.axb1 import bundled_vectors_path

    assert bundled_vectors_path() is not None
    out = call_tool("axb1", {})
    assert out["ok"] is True, out.get("failures")
    assert out["vectors_checked"] == out["vectors_total"] > 0
    assert out["vectors_failed"] == 0
    assert out["hash_checks"]["failed"] == 0
    assert all(out["reject_rules"].values())


def test_call_axb1_only_filter_and_alias() -> None:
    import json as _json

    from pynescript.mcp.ops.axb1 import bundled_vectors_path

    doc = _json.loads(bundled_vectors_path().read_text(encoding="utf-8"))
    first = doc["vectors"][0]["name"]
    out = call_tool("pyne_axb1", {"only": first})
    assert out["ok"] is True
    assert out["vectors_checked"] == 1
    assert out["vectors_passed"] == 1


def test_call_sessions_inspects_pool_and_flags_zombie(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PYNE_DATA_DIR", str(tmp_path / "data"))
    from backend.api.live_ensure import ensure_live_session
    from backend.datastore import series as series_store

    key = series_store.make_key("binance", "PROBE/USDT", "1m", "spot")
    start = 1_700_000_000
    bars = [
        {"time": start + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0} for i in range(10)
    ]
    series_store.get_store().provide(key, bars, source="test")
    script = 'indicator("mcp-sessions-probe")'
    a = ensure_live_session("script", key.text, 10, script=script, symbol="PROBEUSDT")
    assert a["outcome"] == "ready"
    b = ensure_live_session("script", key.text, 10, script=script, symbol="PROBEUSDT")
    assert b["session_id"] == a["session_id"]

    out = call_tool("sessions", {"key": key.text})
    assert out["ok"] is True
    assert out["count"] == 1
    entry = out["sessions"][0]
    assert entry["pooled"] is True
    assert entry["resident"] is True
    assert entry["key"] == key.text
    assert entry["anchor_time"] == start + 9 * 60
    assert entry["lag_bars"] == 0
    assert entry["suspect"] is False

    # The store window moves a full day past the pooled anchor: the session
    # is provably left behind and must be flagged.
    moved = [
        {"time": start + 86_400 + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in range(10)
    ]
    series_store.get_store().purge(key)
    series_store.get_store().provide(key, moved, source="test")
    out = call_tool("pyne_sessions", {"key": key.text})
    entry = out["sessions"][0]
    assert entry["lag_bars"] == 1440
    assert entry["suspect"] is True
    assert "left behind" in entry["why"]


def test_call_sessions_sees_journaled_nonresident(tmp_path, monkeypatch) -> None:
    """A session journaled by another worker (memory gone) still inspects.

    Simulates a backend restart: the journal row survives while this
    process's memory does not. The entry must show resident=false with the
    same anchor the (now unreachable) session was born over.
    """
    monkeypatch.setenv("PYNE_DATA_DIR", str(tmp_path / "data"))
    db_path = str(tmp_path / "sessions.db")
    monkeypatch.setenv("PYNE_SESSION_DB", db_path)
    from backend.api.live_ensure import ensure_live_session
    from backend.datastore import series as series_store
    from backend.middleware.sessions import SESSIONS

    # The singleton binds its journal path at import; pin it explicitly so
    # this test is independent of whichever test imported it first.
    monkeypatch.setattr(SESSIONS, "_db_path", db_path)

    key = series_store.make_key("binance", "GHOST/USDT", "1m", "spot")
    start = 1_700_000_000
    bars = [
        {"time": start + i * 60, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0} for i in range(10)
    ]
    series_store.get_store().provide(key, bars, source="test")
    script = 'indicator("mcp-sessions-ghost-probe")'
    created = ensure_live_session("script", key.text, 10, script=script, symbol="GHOSTUSDT")
    assert created["outcome"] == "ready"
    sid = created["session_id"]

    # Evict from memory without touching the journal (a restart would).
    SESSIONS._sessions.pop(sid, None)
    for fp, pooled in list(SESSIONS._shared.items()):
        if pooled == sid:
            del SESSIONS._shared[fp]
    SESSIONS._shared_refs.pop(sid, None)

    out = call_tool("pyne_sessions", {"key": key.text})
    assert out["ok"] is True
    assert out["count"] == 1
    entry = out["sessions"][0]
    assert entry["resident"] is False
    assert entry["key"] == key.text
    assert entry["anchor_time"] == start + 9 * 60
    assert entry["suspect"] is False


def test_enrich_coerces_string_anchor_times() -> None:
    """Journal bindings may encode last_time as a string; lag still computes."""
    from backend.datastore import series as series_store
    from pynescript.mcp.ops.sessions import _enrich

    key = series_store.make_key("binance", "STR/USDT", "1m", "spot")
    start = 1_700_000_000

    class _Store:
        def status(self, _k):
            return {"oldest": start, "newest": start + 9 * 60, "count": 10}

    row = {"key": key.text, "anchor_time": str(start + 9 * 60)}
    out = _enrich(series_store, _Store(), row)
    assert out["lag_bars"] == 0
    assert out["suspect"] is False

    left_behind = {"key": key.text, "anchor_time": str(start - 86_400)}
    flagged = _enrich(series_store, _Store(), left_behind)
    assert flagged["suspect"] is True
    assert flagged["lag_bars"] == (9 * 60 + 86_400) // 60
    assert "left behind" in flagged["why"]
