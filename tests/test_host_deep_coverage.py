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

"""Deep coverage for runtime/host packing, calendar, session, and error paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pynescript.runtime import Runtime
from pynescript.runtime import host as host_mod
from pynescript.util.datafeed import MockDataFeed


def _bars(n: int = 8, offset: int = 0) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + (offset + i) * 60_000,
            "open": 100.0 + offset + i,
            "high": 101.0 + offset + i,
            "low": 99.0 + offset + i,
            "close": 100.5 + offset + i,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


class TestOhlcvPackCache:
    def test_ohlcv_pack_cached_hit_and_fingerprint_miss(self) -> None:
        host_mod._OHLCV_PACK_CACHE.clear()
        host_mod._OHLCV_LIST_CACHE.clear()
        rows = [
            {"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 3, "time": 10},
            {"open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 4, "time": 20},
        ]
        a = host_mod._ohlcv_pack_cached(rows)
        b = host_mod._ohlcv_pack_cached(rows)
        assert a[0] is b[0]
        assert a[3][-1] == pytest.approx(2.5)
        rows2 = list(rows)
        rows2[-1] = dict(rows2[-1])
        rows2[-1]["close"] = 9.0
        c = host_mod._ohlcv_pack_cached(rows2)
        assert c[3][-1] == pytest.approx(9.0)
        assert c[0] is not a[0]

    def test_ohlcv_cache_insert_evicts_by_entry_limit(self) -> None:
        host_mod._OHLCV_PACK_CACHE.clear()
        for i in range(host_mod._OHLCV_PACK_CACHE_MAX + 5):
            data = [
                {
                    "open": float(i),
                    "high": float(i) + 1,
                    "low": float(i) - 1,
                    "close": float(i) + 0.5,
                    "volume": 1.0,
                    "time": float(i),
                }
            ]
            host_mod._ohlcv_pack_cached(data)
        assert len(host_mod._OHLCV_PACK_CACHE) <= host_mod._OHLCV_PACK_CACHE_MAX

    def test_ohlcv_cache_insert_evicts_by_bar_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cache: dict[int, tuple] = {}
        monkeypatch.setenv("PYNE_OHLCV_CACHE_MAX_BARS", "5")
        for i in range(4):
            fp = (3, i, i, 1.0, 1.0)
            host_mod._ohlcv_cache_insert(cache, i, (object(), fp, (1,)), max_entries=10)
        assert host_mod._ohlcv_cache_total_bars(cache) <= 5
        assert len(cache) < 4

    def test_pack_ohlcv_columns_non_dict_and_missing_keys(self) -> None:
        packed = host_mod._pack_ohlcv_columns([{"close": 1.5}, "bad", {"open": 1, "high": 2, "low": 0, "close": 1}])  # type: ignore[list-item]
        o, _h, _low, c, v, t = packed
        assert len(o) == 3
        assert o[1] == 0.0 and v[1] == 1.0
        assert c[0] == pytest.approx(1.5)
        assert v[0] == 1.0
        assert t[1] == pytest.approx(host_mod._SYNTHETIC_BAR_MS)

    def test_pack_ohlcv_columns_cached_identity(self) -> None:
        host_mod._OHLCV_LIST_CACHE.clear()
        rows = _bars(3)
        a = host_mod._pack_ohlcv_columns_cached(rows)
        b = host_mod._pack_ohlcv_columns_cached(rows)
        assert a[0] is b[0]
        empty = host_mod._ohlcv_pack_cached([])
        assert all(len(col) == 0 for col in empty)


class TestPackInterpretPlotColumns:
    def test_pack_plot_kinds_title_clash_and_attrs(self) -> None:
        series, meta, primary = host_mod._pack_interpret_plot_columns(
            [[1.0, 2.0], [True, False], ["#f00", None], [1, None], [None, 3]],
            [
                {
                    "title": "a",
                    "kind": "plot",
                    "linewidth": 2,
                    "color": "#0f0",
                    "style": "line",
                    "offset": 1,
                    "trackprice": True,
                    "histbase": 0.5,
                    "display": "all",
                    "join": False,
                },
                {
                    "title": "shp",
                    "kind": "plotshape",
                    "location": "abovebar",
                    "text": "X",
                    "size": "small",
                    "char": "!",
                },
                {"title": "bg", "kind": "bgcolor"},
                {"title": "arr", "kind": "plotarrow"},
                {"title": "a", "kind": "hline", "linestyle": "dashed"},
            ],
        )
        assert "a" in series and "a_2" in series
        assert meta["a_2"]["kind"] == "hline"
        assert meta["a_2"].get("price") == pytest.approx(3.0)
        assert meta["shp"].get("char") == "!"
        assert meta["shp"].get("location") == "abovebar"
        assert meta["a"].get("trackprice") is True
        assert meta["a"].get("histbase") == pytest.approx(0.5)
        assert primary == series["a"]

    def test_pack_fill_and_plotcandle_components(self) -> None:
        _series, meta, _ = host_mod._pack_interpret_plot_columns(
            [[1, 2, 3], [4, 5, 6], [None, None, None]],
            [
                {"title": "p1", "kind": "plot"},
                {"title": "p2", "kind": "plot"},
                {"title": "f", "kind": "fill", "plot1": "p1", "plot2": "p2", "color": "#00f"},
            ],
        )
        assert meta["f"]["plot1"] == "p1"
        assert meta["f"]["plot2"] == "p2"

        series2, meta2, _ = host_mod._pack_interpret_plot_columns(
            [[10, 11], [9, 10], [12, 13], [8, 9]],
            [
                {
                    "title": "cdl",
                    "kind": "plotcandle",
                    "wickcolor": "#111",
                    "bordercolor": "#222",
                },
                {"title": "o", "kind": "plot", "ohlc_component": True},
                {"title": "h", "kind": "plot", "ohlc_component": True},
                {"title": "l", "kind": "plot", "ohlc_component": True},
            ],
        )
        assert "cdl.open" in series2 and "cdl.high" in series2 and "cdl.low" in series2
        assert meta2["cdl"]["wickcolor"] == "#111"
        assert meta2["cdl"]["open"] == "cdl.open"

    def test_pack_bars_done_slice_and_dirty(self) -> None:
        series, meta, _ = host_mod._pack_interpret_plot_columns(
            [[1, 2, 3, 4], [None, None, 5, 6]],
            [{"title": "p", "kind": "plot"}, {"title": "h", "kind": "hline"}],
            bars_done=2,
            pack_dirty=True,
        )
        assert series["p"] == [1, 2]
        assert len(series["h"]) == 2
        assert meta["p"]["kind"] == "plot"

    def test_pack_empty_and_unknown_kind(self) -> None:
        series, meta, primary = host_mod._pack_interpret_plot_columns([], [])
        assert series == {} and meta == {} and primary == []
        series2, meta2, _ = host_mod._pack_interpret_plot_columns(
            [[1, "x", None]],
            [{"kind": "custom", "title": 7}],
        )
        assert "7" in series2 or "plot_0" in series2 or list(series2)
        assert meta2[next(iter(meta2))]["kind"] == "custom"


class TestJsonPlotValueAndDiscard:
    def test_json_plot_value_edge_kinds(self) -> None:
        assert host_mod._json_plot_value(None, "line") is None
        assert host_mod._json_plot_value(True, "plotshape") is True
        assert host_mod._json_plot_value(0, "plotshape") is None
        assert host_mod._json_plot_value(2.5, "plotchar") is True
        assert host_mod._json_plot_value(float("nan"), "plotshape") is None
        assert host_mod._json_plot_value(2, "plotarrow") == 2
        assert host_mod._json_plot_value(True, "plotarrow") == 1.0
        assert host_mod._json_plot_value("nope", "plotarrow") is None
        assert host_mod._json_plot_value(" 3.5 ", "line") == pytest.approx(3.5)
        assert host_mod._json_plot_value("<PineImportStub x>", "line") is None
        assert host_mod._json_plot_value("#abc", "bgcolor") == "#abc"
        stub = SimpleNamespace(__pine_import_stub__=True)
        assert host_mod._json_plot_value(stub, "bgcolor") is None
        assert host_mod._json_plot_value(True, "line") == 1.0

    def test_discard_realtime_plot_tick_paths(self) -> None:
        ev = SimpleNamespace(
            _plot_n_bars=0,
            _plot_capture_i=2,
            _plot_value_cols=[[1, 2, 3], [4, 5, 6]],
        )
        host_mod._discard_realtime_plot_tick(ev)
        assert ev._plot_capture_i == 0
        assert ev._plot_value_cols == [[1, 2], [4, 5]]

        ev2 = SimpleNamespace(
            _plot_n_bars=10,
            _plot_capture_i=5,
            _plot_value_cols=[[1], [2]],
        )
        host_mod._discard_realtime_plot_tick(ev2)
        assert ev2._plot_capture_i == 0
        assert ev2._plot_value_cols == [[1], [2]]

        ev3 = SimpleNamespace(_plot_n_bars=0, _plot_capture_i=0, _plot_value_cols=None)
        host_mod._discard_realtime_plot_tick(ev3)
        assert ev3._plot_capture_i == 0


class TestLazyCalendarAndAttach:
    def test_lazy_calendar_full_field_materialization(self) -> None:
        cal = host_mod.LazyCalendarContext()
        cal.set_bar_time(1_700_000_000_000)
        for key in host_mod._CAL_KEYS:
            val = cal[key]
            assert isinstance(val, int), key
        assert cal["year"] >= 2020
        assert 1 <= cal["month"] <= 12
        assert 1 <= cal["dayofmonth"] <= 31
        assert 0 <= cal["hour"] <= 23
        assert 0 <= cal["dayofweek"] <= 7
        # Non-calendar keys survive bar advance; calendar keys refresh.
        cal["user"] = 42
        cal.set_bar_time(1_700_086_400_000)
        assert cal.get("user") == 42
        assert isinstance(cal["year"], int)
        assert isinstance(cal.get("dayofweek"), int)
        # Explicit calendar assignment before materialize is honored once.
        cal2 = host_mod.LazyCalendarContext()
        cal2.set_bar_time(1_700_000_000_000)
        cal2["year"] = 2099
        assert cal2["year"] == 2099
        assert isinstance(cal2["month"], int)

    def test_attach_logs_profile_merges_existing_meta(self) -> None:
        host_mod._clear_pine_logger()
        result = {"series": {"c": [1]}, "meta": {"keep": True}}
        out = host_mod._attach_logs_profile(
            result,
            total_ms=3.0,
            bars=1,
            mode="interpret",
            parse_ms=0.5,
            eval_ms=1.5,
            lines=[{"line": 2, "ms": 1.0, "execs": 2, "pct": 100.0}],
        )
        assert out["meta"]["keep"] is True
        assert "logs" in out and "profile" in out
        assert out["meta"]["profile"]["lines"][0]["line"] == 2
        assert out["profile"]["bars"] == 1


class TestSessionRealtimeAndErrors:
    def test_session_append_and_update_last_bar(self) -> None:
        src = """//@version=6
indicator("sess")
plot(close, "c")
plot(bar_index, "bi")
"""
        sess = Runtime(symbol="H").create_session(src, _bars(5), mode="interpret")
        out = sess.append_bars(_bars(2, offset=5))
        assert sess.bar_count == 7
        assert out["series"]["c"][-1] == pytest.approx(_bars(2, offset=5)[-1]["close"])
        tick = dict(_bars(7)[-1])
        tick["close"] = 999.0
        tick["high"] = 1000.0
        out2 = sess.update_last_bar(tick)
        assert sess.bar_count == 7
        assert out2["series"]["c"][-1] == pytest.approx(999.0)

    def test_realtime_helpers_resolve_and_forming(self) -> None:
        first, ticks = host_mod._resolve_realtime_first(20, realtime_ticks=3, realtime_last_bar=True)
        assert first == 19 and ticks == 3
        first2, ticks2 = host_mod._resolve_realtime_first(20, realtime_bars=5, realtime_ticks=2)
        assert first2 == 15 and ticks2 == 2
        hi, lo = host_mod._forming_hl(_bars(4), 2)
        assert hi == pytest.approx(103.0)
        assert lo == pytest.approx(101.0)

        src = """//@version=6
indicator("rt")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(close, "c")
"""
        out = Runtime(symbol="H").run(
            src,
            _bars(6),
            mode="interpret",
            realtime_last_bar=True,
            realtime_ticks=2,
            data_feed=MockDataFeed(symbol="H", start_price=100.0),
        )
        assert out.get("error") in (None, "") or "error" not in out
        assert out["series"]["rt"][-1] == 1

    def test_runtime_error_envelopes(self) -> None:
        bars = _bars(3)
        mode_err = Runtime(symbol="H").run('//@version=6\nindicator("t")\nplot(close)', bars, mode="bogus")
        assert mode_err["error_kind"] == "mode"
        assert "Unknown mode" in mode_err["error"]

        parse_err = Runtime(symbol="H").run("@@@not pine", bars, mode="interpret")
        assert parse_err["error_kind"] == "parse"
        assert parse_err.get("error_type") == "SyntaxError"

        runtime_err = Runtime(symbol="H").run(
            '//@version=6\nindicator("t")\nruntime.error("boom")\nplot(close)',
            bars,
            mode="interpret",
        )
        assert runtime_err["error_kind"] == "runtime"
        assert runtime_err.get("error_type") == "RuntimeError"
        assert "boom" in runtime_err["error"]

    def test_compile_mode_reports_parse_junk_as_parse_error(self) -> None:
        """Compile mode must surface parse failures like interpret (no stub success)."""
        bars = _bars(1)
        out = Runtime(symbol="H").run("@@@not pine", bars, mode="compile")
        assert out.get("error_kind") == "parse"
        assert out.get("error")
        series = out.get("series") or {}
        assert not [k for k in series if not str(k).startswith("__")]

    def test_interpret_and_compile_simple_parity(self) -> None:
        src = """//@version=6
indicator("p")
plot(close, "c")
plot(hlc3, "h")
"""
        bars = _bars(6)
        interp = Runtime(symbol="H").run(src, bars, mode="interpret")
        compiled = Runtime(symbol="H").run(src, bars, mode="compile")
        assert interp["series"]["c"][-1] == pytest.approx(compiled["series"]["c"][-1])
        assert interp["series"]["h"][-1] == pytest.approx(compiled["series"]["h"][-1])

    def test_series_values_jsonable_numpy_and_none(self) -> None:
        import numpy as np

        assert host_mod._series_values_jsonable(None) == []
        out = host_mod._series_values_jsonable(np.asarray([1.0, float("nan"), 3.0]))
        assert out[0] == pytest.approx(1.0)
        assert out[1] is None
        assert out[2] == pytest.approx(3.0)
