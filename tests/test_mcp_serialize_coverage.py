# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Broad unit coverage for MCP JSON envelopes and series helpers."""

from __future__ import annotations

from pynescript.mcp import serialize as ser


def test_ok_and_fail_shapes() -> None:
    assert ser.ok(a=1) == {"ok": True, "a": 1}
    body = ser.fail("boom", kind="parse", line=2, column=4, extra=9)
    assert body == {
        "ok": False,
        "error": "boom",
        "kind": "parse",
        "line": 2,
        "column": 4,
        "extra": 9,
    }
    assert ser.fail("x")["kind"] == "error"
    assert "line" not in ser.fail("x")


def test_jsonable_scalars_and_nan() -> None:
    assert ser.jsonable(None) is None
    assert ser.jsonable(True) is True
    assert ser.jsonable(3) == 3
    assert ser.jsonable("hi") == "hi"
    assert ser.jsonable(1.5) == 1.5
    assert ser.jsonable(float("nan")) is None
    assert ser.jsonable(float("inf")) is None
    assert ser.jsonable(float("-inf")) is None


def test_jsonable_bytes_dict_list_and_depth() -> None:
    assert ser.jsonable(b"abc\xff") == "abc\ufffd"
    assert ser.jsonable({"a": 1, 2: float("nan")}) == {"a": 1, "2": None}
    assert ser.jsonable((1, 2)) == [1, 2]
    nested = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": 1}}}}}}}}}}
    out = ser.jsonable(nested)
    # depth > 8 collapses nested values to a short string (h is depth 8, i→j collapses)
    assert isinstance(out["a"]["b"]["c"]["d"]["e"]["f"]["g"]["h"]["i"], str)


def test_jsonable_numpy_like_item_and_tolist() -> None:
    class Scalar:
        ndim = 0

        def item(self):
            return 42

    assert ser.jsonable(Scalar()) == 42

    class BadItem:
        ndim = 0

        def item(self):
            raise RuntimeError("nope")

    assert ser.jsonable(BadItem()).startswith("<")

    class Arr:
        def tolist(self):
            return [1, float("nan")]

    assert ser.jsonable(Arr()) == [1, None]

    class BadList:
        def tolist(self):
            raise RuntimeError("bad")

        def __str__(self) -> str:
            return "BadList()"

    assert ser.jsonable(BadList()) == "BadList()"


def test_clamp_helpers() -> None:
    assert ser.clamp_sample(0) == 1
    assert ser.clamp_sample(8) == 8
    assert ser.clamp_sample(999) == ser.SAMPLE_MAX
    assert ser.clamp_bars(1) == 2
    assert ser.clamp_bars(100) == 100
    assert ser.clamp_bars(10_000) == ser.BARS_MAX
    assert ser.clamp_timeout(None) == ser.TIMEOUT_DEFAULT
    assert ser.clamp_timeout(0) == ser.TIMEOUT_DEFAULT
    assert ser.clamp_timeout(-1) == ser.TIMEOUT_DEFAULT
    assert ser.clamp_timeout(15) == 15.0
    assert ser.clamp_timeout(999) == ser.TIMEOUT_MAX


def test_summarize_series_basic_and_na() -> None:
    s = ser.summarize_series([1.0, float("nan"), 3.0], sample=2)
    assert s["len"] == 3
    assert s["last"] == 3.0
    assert s["na_count"] == 1
    assert s["sample"] == [None, 3.0]


def test_summarize_series_scalar_and_bad_iter() -> None:
    assert ser.summarize_series(7)["sample"] == [7]
    assert ser.summarize_series("abc")["sample"] == ["abc"]

    class Boom:
        def __iter__(self):
            raise RuntimeError("iter")

    assert ser.summarize_series(Boom()) == {
        "len": 0,
        "last": None,
        "na_count": 0,
        "sample": [],
    }


def test_split_plots_empty() -> None:
    assert ser.split_plots(None) == ({}, {})
    assert ser.split_plots({}) == ({}, {})


def test_split_plots_runtime_envelope() -> None:
    result = {
        "mode": "interpret",
        "plots": [1, 2, 3],
        "series": {
            "close": [1, 2, 3, 4],
            "__events": [{"kind": "entry"}],
            "__trades": [{"id": 1}],
        },
        "compile_ms": 1.2,
        "generated_code": "x" * 10,
        "events": [{"kind": "entry"}],
        "inputs": [{"name": "len"}],
    }
    plots, extras = ser.split_plots(result, sample=2, include_trades=True)
    assert plots["close"]["len"] == 4
    assert plots["close"]["sample"] == [3, 4]
    assert extras["__events_count"] == 1
    assert extras["__events"] == [{"kind": "entry"}]
    assert extras["__trades_count"] == 1
    assert extras["generated_code_chars"] == 10
    assert "generated_code" not in extras
    assert extras["compile_ms"] == 1.2
    assert extras["inputs_count"] == 1
    assert "inputs" not in extras  # not a trade list key


def test_split_plots_runtime_fallback_to_plots_list() -> None:
    result = {"mode": "compile", "series": {}, "plots": [9, 8]}
    plots, _extras = ser.split_plots(result)
    assert plots["plot"]["sample"] == [9, 8]


def test_split_plots_compiled_map() -> None:
    result = {
        "sma": [1, 2, 3],
        "__events": [{"a": 1}],
        "timed_out": False,
        "error": None,
    }
    plots, extras = ser.split_plots(result, include_trades=False)
    assert "sma" in plots
    assert extras["__events_count"] == 1
    assert "__events" not in extras  # include_trades False
    assert extras["timed_out"] is False


def test_put_list_extra_non_iterable() -> None:
    extras: dict = {}
    ser._put_list_extra(extras, "events", object(), include_trades=True)
    assert "events" in extras


def test_strip_secrets_nested() -> None:
    payload = {
        "api_key": "sekrit",
        "Admin-Token": "t",
        "nested": {"password": "p", "ok": 1},
        "symbol": "BTC",
    }
    out = ser.strip_secrets(payload)
    assert out["api_key"] == "***"
    assert out["Admin-Token"] == "***"
    assert out["nested"]["password"] == "***"
    assert out["nested"]["ok"] == 1
    assert out["symbol"] == "BTC"


def test_is_runtime_envelope() -> None:
    assert ser._is_runtime_envelope({"series": {}, "mode": "auto"}) is True
    assert ser._is_runtime_envelope({"series": {}, "plots": []}) is True
    assert ser._is_runtime_envelope({"series": "nope"}) is False
    assert ser._is_runtime_envelope({"series": {}, "mode": "other"}) is False
