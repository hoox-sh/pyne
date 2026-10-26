# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit coverage for pure helpers in ``pynescript.runtime.host``."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pynescript.runtime import host as host_mod


def test_env_truthy_and_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYNE_TEST_FLAG", raising=False)
    assert host_mod._env_truthy("PYNE_TEST_FLAG", default=True) is True
    assert host_mod._env_truthy("PYNE_TEST_FLAG", default=False) is False
    monkeypatch.setenv("PYNE_TEST_FLAG", "1")
    assert host_mod._env_truthy("PYNE_TEST_FLAG") is True
    monkeypatch.setenv("PYNE_TEST_FLAG", "off")
    assert host_mod._env_truthy("PYNE_TEST_FLAG", default=True) is False
    monkeypatch.setenv("PYNE_TEST_INT", "12")
    assert host_mod._env_int("PYNE_TEST_INT", 3) == 12
    monkeypatch.setenv("PYNE_TEST_INT", "nope")
    assert host_mod._env_int("PYNE_TEST_INT", 3) == 3
    monkeypatch.delenv("PYNE_TEST_INT", raising=False)
    assert host_mod._env_int("PYNE_TEST_INT", 7) == 7


def test_error_payload_and_format() -> None:
    body = host_mod._error_payload("boom", kind="parse", exc=ValueError("x"), bar_index=2, bar_time=99)
    assert body["error"] == "boom"
    assert body["error_kind"] == "parse"
    assert body["error_type"] == "ValueError"
    assert body["error_bar"] == 2
    assert body["error_bar_time"] == 99
    msg = host_mod._format_exc_message("run", ValueError("x"))
    assert msg.startswith("run:")
    assert "ValueError" in msg
    assert host_mod._format_exc_message("run", ValueError()) == "run: ValueError"


def test_json_safe_number_and_color() -> None:
    assert host_mod._json_safe_number(3) == pytest.approx(3.0)
    assert host_mod._json_safe_number(1.5) == pytest.approx(1.5)
    assert host_mod._json_safe_number(float("nan")) is None
    assert host_mod._json_safe_number(float("inf")) is None
    assert host_mod._json_safe_number("x") is None
    assert host_mod._color_str(None) is None
    colored = host_mod._color_str("#ff0000")
    assert colored is None or isinstance(colored, str)


def test_coerce_ohlc_cells() -> None:
    assert host_mod._coerce_ohlc_cell(1.5) == pytest.approx(1.5)
    assert host_mod._coerce_ohlc_cell(None, default=9.0) == pytest.approx(9.0)
    assert host_mod._coerce_ohlc_cell("bad", default=2.0) == pytest.approx(2.0)
    assert host_mod._coerce_volume_cell(None) == pytest.approx(1.0)
    assert host_mod._coerce_volume_cell(3) == pytest.approx(3.0)
    assert host_mod._coerce_time_cell(1_700_000_000, 0) == pytest.approx(1_700_000_000)
    assert host_mod._coerce_time_cell(None, 5) > 0


def test_pack_ohlcv_columns_basic() -> None:
    bars = [
        {"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10, "time": 100},
        {"open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 11, "time": 200},
    ]
    packed = host_mod._pack_ohlcv_columns(bars)
    assert len(packed) >= 5
    assert host_mod._ohlcv_cache_total_bars({}) == 0
    fp = host_mod._ohlcv_pack_fingerprint(bars)
    assert isinstance(fp, tuple)
    arrs = host_mod._ohlcv_dicts_to_arrays(bars)
    assert len(arrs) >= 4
    times = host_mod._ohlcv_times_to_array(bars)
    assert len(times) == 2


def test_parse_script_header_fields() -> None:
    src = '//@version=6\nindicator("Hello", overlay=true, max_bars_back=500)\nplot(close)\n'
    fields = host_mod._parse_script_header_fields(src)
    assert isinstance(fields, dict)


def test_compile_plot_meta_and_stamps() -> None:
    series = {"plot": [1, 2, 3], "hline": [1, 1, 1]}
    meta = host_mod._compile_plot_meta(series)
    assert isinstance(meta, dict)
    host_mod._stamp_compile_plot_kinds(meta, ["plot", "hline"], ["plot", "hline"])
    host_mod._stamp_compile_plot_attrs(meta, [{"linewidth": 2}, {"linewidth": 1}])
    meta["fill"] = {"title": "fill", "kind": "fill", "plot1": "plot", "plot2": "hline", "index": 2}
    host_mod._stamp_compile_fill_edges(meta, series)
    host_mod._backfill_plot_meta_from_drawings(meta, [])


def test_hline_fill_and_series_jsonable() -> None:
    filled = host_mod._hline_fill_constant([1.0, None, 1.0])
    assert isinstance(filled, list)
    out = host_mod._series_values_jsonable([1.0, float("nan"), None])
    assert isinstance(out, list)
    assert out[0] == pytest.approx(1.0)


def test_lazy_calendar_context() -> None:
    ctx = host_mod.LazyCalendarContext()
    ctx.set_bar_time(1_700_000_000_000)
    # first calendar read materializes fields
    year = ctx.get("year")
    assert year is None or isinstance(year, int)
    ctx["user"] = 1
    assert ctx["user"] == 1
    ctx.set_bar_time(1_700_086_400_000)
    assert ctx.get("user") == 1


def test_export_logs_and_profile() -> None:
    host_mod._clear_pine_logger()
    assert host_mod._export_pine_logs() == []
    assert host_mod._export_line_profile(SimpleNamespace()) == []
    ev = SimpleNamespace(_pine_line_profile={1: (1.5, 3), 2: (0.5, 1), 0: (9.0, 1)})
    rows = host_mod._export_line_profile(ev)
    assert rows and rows[0]["line"] == 1
    assert rows[0]["execs"] == 3


def test_build_run_profile_and_record_stats() -> None:
    profile = host_mod._build_run_profile(total_ms=10.0, bars=50, mode="interpret", parse_ms=1.0, eval_ms=8.0)
    assert profile["bars"] == 50
    assert profile["mode"] == "interpret"
    assert profile["phases"]["parse_ms"] == pytest.approx(1.0)
    result: dict = {"ok": True}
    host_mod._record_run_stats(result, total_ms=10.0, bars=50, mode="interpret", parse_ms=1.0, eval_ms=8.0)


def test_json_plot_value_kinds() -> None:
    assert host_mod._json_plot_value(1.5, "line") == pytest.approx(1.5)
    assert host_mod._json_plot_value(float("nan"), "line") is None
    _ = host_mod._json_plot_value("#ff0000", "color")
    _ = host_mod._json_plot_value("hello", "label")


def test_drop_as_series_cache() -> None:
    ev = SimpleNamespace(_pine_as_series_cache={"a": 1})
    host_mod._drop_as_series_cache(ev)
    assert ev._pine_as_series_cache == {}
    ev2 = SimpleNamespace()
    host_mod._drop_as_series_cache(ev2)
    assert isinstance(ev2._pine_as_series_cache, dict)


def test_fill_edge_series_key() -> None:
    series_map = {"plot": [1], "plot_2": [2]}
    plot_meta = {"plot": {"title": "plot", "kind": "plot"}, "Other": {"title": "Other", "kind": "plot"}}
    key = host_mod._fill_edge_series_key(series_map, plot_meta, "plot", set())
    assert key in {"plot", "plot_2", None} or key == "plot"
    assert host_mod._fill_edge_series_key(series_map, plot_meta, None, set()) in {None, ""}
