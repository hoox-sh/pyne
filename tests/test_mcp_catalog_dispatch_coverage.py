# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json

from pathlib import Path

import click
import pytest

from pynescript.mcp import cli as mcp_cli
from pynescript.mcp.catalog import PROMPT_NAMES
from pynescript.mcp.catalog import RESOURCE_URIS
from pynescript.mcp.catalog import TOOL_NAMES
from pynescript.mcp.dispatch import _bind
from pynescript.mcp.dispatch import call_tool
from pynescript.mcp.dispatch import coerce_cli_value
from pynescript.mcp.dispatch import parse_kv
from pynescript.mcp.dispatch import resolve_tool_name
from pynescript.mcp.ops import common as ops_common
from pynescript.mcp.ops.builtins import list_builtins
from pynescript.mcp.ops.builtins import lookup_builtin
from pynescript.mcp.ops.info import has_mcp_sdk
from pynescript.mcp.ops.info import info_payload
from pynescript.mcp.ops.language import convert_source
from pynescript.mcp.ops.language import lint_source
from pynescript.mcp.ops.language import parse_source
from pynescript.mcp.ops.language import unparse_source


MINI = """//@version=5
indicator("cli_smoke")
plot(close)
"""

V4 = """//@version=4
study("old")
plot(close)
"""


def test_tool_names_are_unique_and_prefixed() -> None:
    assert len(TOOL_NAMES) == len(set(TOOL_NAMES))
    assert all(name.startswith("pyne_") for name in TOOL_NAMES)
    for required in (
        "pyne_info",
        "pyne_parse",
        "pyne_lint",
        "pyne_unparse",
        "pyne_convert",
        "pyne_builtin",
        "pyne_execute",
    ):
        assert required in TOOL_NAMES


def test_resource_and_prompt_catalog() -> None:
    assert "pyne://info" in RESOURCE_URIS
    assert "pyne://builtins" in RESOURCE_URIS
    assert set(PROMPT_NAMES) == {"review_pine", "debug_pine", "convert_to_v6"}


def test_resolve_tool_name_variants() -> None:
    assert resolve_tool_name("lint") == "pyne_lint"
    assert resolve_tool_name("pyne_lint") == "pyne_lint"
    assert resolve_tool_name("pyne-lint") == "pyne_lint"
    assert resolve_tool_name("  convert  ") == "pyne_convert"
    assert resolve_tool_name("info") == "pyne_info"
    assert resolve_tool_name("builtin") == "pyne_builtin"
    assert resolve_tool_name("nope") is None
    assert resolve_tool_name(None) is None  # type: ignore[arg-type]
    assert resolve_tool_name("") is None
    assert resolve_tool_name("   ") is None
    assert resolve_tool_name("pyne_not_real") is None


def test_coerce_cli_value_and_parse_kv() -> None:
    assert coerce_cli_value("") == ""
    assert coerce_cli_value("  ") == ""
    assert coerce_cli_value("24") == 24
    assert coerce_cli_value("true") is True
    assert coerce_cli_value("null") is None
    assert coerce_cli_value('[1, 2]') == [1, 2]
    assert coerce_cli_value('{"a": 1}') == {"a": 1}
    assert coerce_cli_value("interpret") == "interpret"
    assert coerce_cli_value(" not-json ") == " not-json "
    assert parse_kv("bars=16") == ("bars", 16)
    assert parse_kv("flag=false") == ("flag", False)
    with pytest.raises(ValueError, match="KEY=VALUE"):
        parse_kv("novalue")
    with pytest.raises(ValueError, match="KEY=VALUE"):
        parse_kv("=onlyvalue")
    with pytest.raises(ValueError, match="KEY=VALUE"):
        parse_kv("")


def test_bind_filters_unknown_kwargs() -> None:
    def fn(source: str, bars: int = 10) -> dict:
        return {"source": source, "bars": bars}

    assert _bind(fn, {"source": "x", "bars": 3, "extra": 9}) == {"source": "x", "bars": 3}

    def kwargs_fn(**kwargs: object) -> dict:
        return dict(kwargs)

    assert _bind(kwargs_fn, {"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_call_tool_unknown_returns_ok_false() -> None:
    out = call_tool("definitely_not_a_tool", {})
    assert out["ok"] is False
    assert out["kind"] == "io"
    assert "unknown tool" in out["error"]
    assert set(out["tools"]) == set(TOOL_NAMES)


def test_call_tool_lint_alias_and_missing_source() -> None:
    aliased = call_tool("lint", {"source": MINI})
    assert aliased["ok"] is True
    assert isinstance(aliased["findings"], list)

    missing = call_tool("pyne_lint", {})
    assert missing["ok"] is False
    assert missing["kind"] == "io"
    assert "source or path" in missing["error"]

    missing_parse = call_tool("parse", {})
    assert missing_parse["ok"] is False
    assert missing_parse["kind"] == "io"


def test_call_tool_happy_paths_inline_source() -> None:
    parsed = call_tool("pyne_parse", {"source": MINI})
    assert parsed["ok"] is True
    assert parsed["kind"] == "indicator"
    assert parsed["title"] == "cli_smoke"
    assert parsed["version"] == 5

    linted = call_tool("pyne_lint", {"source": MINI})
    assert linted["ok"] is True
    assert linted["error_count"] == 0

    unparsed = call_tool("pyne_unparse", {"source": MINI})
    assert unparsed["ok"] is True
    assert "indicator" in unparsed["source"]

    converted = call_tool("pyne_convert", {"source": V4, "to": 6})
    assert converted["ok"] is True
    assert converted["to"] == 6
    assert "//@version=6" in converted["source"] or "indicator" in converted["source"]

    info = call_tool("pyne_info", {})
    assert info["ok"] is True
    assert info["name"] == "pynescript"
    assert info["distribution"] == "hoox-pyne"
    assert "version" in info
    assert info["entry_points"]["mcp"] == "pyne-mcp"

    builtin = call_tool("pyne_builtin", {"name": "ta.sma"})
    assert builtin["ok"] is True
    assert builtin["name"] == "ta.sma"

    short_builtin = call_tool("builtin", {"name": "sma"})
    assert short_builtin["ok"] is True
    assert "sma" in short_builtin["name"]


def test_call_tool_bad_convert_target_and_empty_builtin() -> None:
    bad_to = call_tool("convert", {"source": MINI, "to": 4})
    assert bad_to["ok"] is False
    assert bad_to["kind"] == "io"

    empty = call_tool("pyne_builtin", {"name": ""})
    assert empty["ok"] is False
    assert "name is required" in empty["error"]

    miss = call_tool("pyne_builtin", {"name": "not.a.real.builtin.zzz"})
    assert miss["ok"] is False


def test_ops_direct_happy_paths() -> None:
    assert parse_source(source=MINI)["ok"] is True
    assert lint_source(source=MINI)["ok"] is True
    assert unparse_source(source=MINI)["ok"] is True
    assert convert_source(source=V4, to=5)["ok"] is True
    payload = info_payload()
    assert payload["ok"] is True
    assert isinstance(has_mcp_sdk(), bool)
    assert lookup_builtin("ta.ema")["ok"] is True
    listed = list_builtins(category="ta.technical_analysis", limit=5)
    assert listed["ok"] is True
    assert listed["count"] <= 5
    assert listed["builtins"]
    bare = list_builtins(limit=3)
    assert bare["count"] == 3


def test_load_source_helpers(tmp_path: Path) -> None:
    assert ops_common.load_source(source=MINI) == (MINI, "<mcp>")
    pine = tmp_path / "x.pine"
    pine.write_text(MINI, encoding="utf-8")
    text, label = ops_common.load_source(path=str(pine))  # type: ignore[misc]
    assert "indicator" in text
    assert str(pine) == label

    missing = ops_common.load_source()
    assert isinstance(missing, dict)
    assert missing["ok"] is False

    absent = ops_common.load_source(path=str(tmp_path / "nope.pine"))
    assert isinstance(absent, dict)
    assert absent["ok"] is False
    assert "not found" in absent["error"]


def test_synthetic_ohlcv_and_declaration_helpers() -> None:
    cols = ops_common.synthetic_ohlcv_cols(5)
    assert len(cols["close"]) == 5
    assert cols["volume"][0] == 1000.0
    rows = ops_common.synthetic_ohlcv_rows(3)
    assert rows[0]["time"] == 1_700_000_000
    assert rows[2]["volume"] == 1002.0

    assert ops_common.version_from_source(MINI) == 5
    assert ops_common.version_from_source("plot(close)") is None

    from pynescript.ast import parse

    tree = parse(MINI)
    kind, title = ops_common.script_declaration(tree)
    assert kind == "indicator"
    assert title == "cli_smoke"

    study = parse('//@version=3\nstudy("s")\nplot(close)\n')
    kind2, title2 = ops_common.script_declaration(study)
    assert kind2 == "indicator"
    assert title2 == "s"


def test_cli_payload_helpers(tmp_path: Path) -> None:
    assert mcp_cli._payload_has_errors({"ok": True, "error_count": 2}) is True
    assert mcp_cli._payload_has_errors({"ok": True, "error_count": 0}) is False
    assert mcp_cli._payload_has_errors(
        {"findings": [{"severity": "warning"}, {"severity": "error"}]}
    )
    assert mcp_cli._payload_has_errors({"diagnostics": [{"severity": "error"}]})
    assert mcp_cli._payload_has_errors({"findings": "nope"}) is False
    assert mcp_cli._payload_has_errors({}) is False

    assert mcp_cli._load_json_opt("", label="x") is None
    assert mcp_cli._load_json_opt("  ", label="x") is None
    assert mcp_cli._load_json_opt('{"a": 1}', label="x") == {"a": 1}
    jf = tmp_path / "args.json"
    jf.write_text('{"bars": 8}', encoding="utf-8")
    assert mcp_cli._load_json_opt(str(jf), label="--json") == {"bars": 8}
    with pytest.raises(click.ClickException, match="invalid"):
        mcp_cli._load_json_opt("{not-json", label="--json")

    path_kw = mcp_cli._source_kwargs("script.pine", "latin-1")
    assert path_kw == {"encoding": "latin-1", "path": "script.pine"}


def test_cli_echo_payload_exits_on_fail(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        mcp_cli._echo_payload({"ok": False, "error": "boom"})
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert '"ok": false' in out or '"ok": false'.replace(" ", "") in out.replace(" ", "")

    mcp_cli._echo_payload({"ok": True, "x": 1})
    ok_out = capsys.readouterr().out
    assert '"ok": true' in ok_out or '"x": 1' in ok_out

    with pytest.raises(SystemExit):
        mcp_cli._echo_payload({"ok": True, "match": False}, extra_fail=True)


def test_handlers_cover_every_catalog_tool() -> None:
    from pynescript.mcp.dispatch import _handlers

    names = set(_handlers())
    assert names == set(TOOL_NAMES)
    for name in TOOL_NAMES:
        assert callable(_handlers()[name])
