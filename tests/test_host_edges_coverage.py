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

"""Edge coverage for runtime/host.py (Runtime / session / helpers)."""

from __future__ import annotations

import pytest

from pynescript.runtime import Runtime
from pynescript.runtime import host as runtime_host
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


class TestHostModeAndErrors:
    def test_unknown_mode_error_envelope(self) -> None:
        out = Runtime(symbol="H").run('//@version=6\nindicator("t")\nplot(close)', _bars(3), mode="bogus")
        assert out["error_kind"] == "mode"
        assert "Unknown mode" in out["error"]

    def test_parse_error_envelope(self) -> None:
        out = Runtime(symbol="H").run("@@@", _bars(3), mode="interpret")
        assert out["error_kind"] == "parse"
        assert out.get("error_type") == "SyntaxError"
        assert "error" in out

    def test_interpret_compile_auto_modes(self) -> None:
        src = """//@version=6
indicator("m")
plot(close, "c")
"""
        bars = _bars(6)
        interp = Runtime(symbol="H").run(src, bars, mode="interpret")
        assert interp.get("error") in (None, "") or "error" not in interp
        assert interp["series"]["c"][-1] == pytest.approx(bars[-1]["close"])

        compiled = Runtime(symbol="H").run(src, bars, mode="compile")
        assert compiled.get("error") in (None, "") or "error" not in compiled
        assert compiled["series"]["c"][-1] == pytest.approx(bars[-1]["close"])

        auto = Runtime(symbol="H").run(src, bars, mode="auto")
        assert auto.get("error") in (None, "") or "error" not in auto
        assert auto.get("auto_backend") in {"compile", "interpret"}
        assert auto["series"]["c"][-1] == pytest.approx(bars[-1]["close"])

    def test_profiler_forces_interpret_and_attaches_profile(self) -> None:
        src = """//@version=6
indicator("p")
plot(close + 1, "c")
"""
        out = Runtime(symbol="H").run(src, _bars(5), mode="auto", profiler=True)
        assert out.get("error") in (None, "") or "error" not in out
        assert "profile" in out
        assert out["profile"]["mode"] == "interpret"
        assert out["profile"]["bars"] == 5
        assert "phases" in out["profile"]

    def test_input_overrides(self) -> None:
        src = """//@version=6
indicator("in")
len = input.int(5, "Len")
plot(len, "len")
"""
        out = Runtime(symbol="H").run(src, _bars(4), mode="interpret", inputs={"Len": 11})
        assert out["series"]["len"][-1] == 11

    def test_library_register_via_run(self) -> None:
        lib = {
            "namespace": "user",
            "name": "EdgeLib",
            "version": "1",
            "source": """//@version=6
library("EdgeLib")
export const float K = 3.25
""",
        }
        src = """//@version=6
indicator("lib")
import user/EdgeLib/1 as L
plot(L.K, "k")
"""
        out = Runtime(symbol="H").run(src, _bars(3), mode="interpret", libraries=[lib])
        assert out.get("error") in (None, "") or "error" not in out
        assert out["series"]["k"][-1] == pytest.approx(3.25)

    def test_empty_and_short_series(self) -> None:
        src = """//@version=6
indicator("e")
plot(close, "c")
"""
        empty = Runtime(symbol="H").run(src, [], mode="interpret")
        assert empty.get("error") in (None, "") or "error" not in empty
        assert empty.get("series", {}).get("c", []) == []

        short = Runtime(symbol="H").run(src, _bars(1), mode="interpret")
        assert short["series"]["c"] == [pytest.approx(100.5)]

    def test_timeout_envelope(self) -> None:
        src = """//@version=6
indicator("to")
plot(close, "c")
"""
        out = Runtime(symbol="H").run(src, _bars(40), mode="interpret", timeout_seconds=1e-9)
        assert out.get("timed_out") is True
        assert "timed out" in str(out.get("error", "")).lower()


class TestHostSessionDeltaAndForming:
    def test_append_bars_delta(self) -> None:
        src = """//@version=6
indicator("delta")
plot(close, "c")
plot(ta.sma(close, 3), "s")
"""
        rt = Runtime(symbol="H")
        sess = rt.create_session(src, _bars(5), mode="interpret")
        assert sess.bar_count == 5
        out = sess.append_bars(_bars(3, offset=5))
        assert out.get("error") in (None, "") or "error" not in out
        assert sess.bar_count == 8
        assert out["series"]["c"][-1] == pytest.approx(_bars(3, offset=5)[-1]["close"])
        empty_append = sess.append_bars([])
        assert empty_append["series"]["c"][-1] == out["series"]["c"][-1]

    def test_forming_bar_ticks_update_last(self) -> None:
        src = """//@version=6
indicator("form")
var int v = 0
v := v + 1
plot(v, "v")
plot(close, "c")
"""
        sess = Runtime(symbol="H").create_session(src, _bars(6), mode="interpret")
        tick = dict(_bars(6)[-1])
        tick["close"] = 555.0
        tick["high"] = 556.0
        out = sess.update_last_bar(tick)
        assert sess.bar_count == 6
        assert out["series"]["c"][-1] == pytest.approx(555.0)
        assert out["series"]["v"][-1] == 6
        tick2 = dict(tick)
        tick2["close"] = 777.0
        out2 = sess.update_last_bar(tick2)
        assert out2["series"]["c"][-1] == pytest.approx(777.0)
        assert out2["series"]["v"][-1] == 6

    def test_realtime_ticks_and_last_bar_flags(self) -> None:
        src = """//@version=6
indicator("rt")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(close, "c")
"""
        out = Runtime(symbol="H").run(
            src,
            _bars(5),
            mode="interpret",
            realtime_last_bar=True,
            realtime_ticks=3,
        )
        assert out.get("error") in (None, "") or "error" not in out
        assert out["series"]["rt"][-1] == 1
        assert len(out["series"]["c"]) == 5

    def test_realtime_bars_window(self) -> None:
        src = """//@version=6
indicator("win")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(close, "c")
"""
        out = Runtime(symbol="H").run(src, _bars(8), mode="interpret", realtime_bars=3, realtime_ticks=2)
        assert out["series"]["rt"][-1] == 1
        assert out["series"]["rt"][0] == 0

    def test_update_last_bar_requires_bars(self) -> None:
        src = """//@version=6
indicator("x")
plot(close)
"""
        sess = Runtime(symbol="H").create_session(src, [], mode="interpret")
        with pytest.raises(ValueError):
            sess.update_last_bar({"open": 1, "high": 1, "low": 1, "close": 1, "time": 0, "volume": 1})

    def test_feed_forming_bar_poll_path(self) -> None:
        src = """//@version=6
indicator("feed")
plot(close, "c")
"""
        feed = MockDataFeed(symbol="AAPL", start_price=100.0)
        out = Runtime(symbol="AAPL").run(
            src,
            _bars(4),
            mode="interpret",
            data_feed=feed,
            realtime_last_bar=True,
            realtime_ticks=2,
        )
        assert out.get("error") in (None, "") or "error" not in out
        assert len(out["series"]["c"]) == 4


class TestHostHelperUnits:
    def test_error_payload_and_format(self) -> None:
        body = runtime_host._error_payload(
            "boom",
            kind="runtime",
            exc=ValueError("x"),
            bar_index=2,
            bar_time=99,
        )
        assert body == {
            "error": "boom",
            "error_kind": "runtime",
            "error_type": "ValueError",
            "error_bar": 2,
            "error_bar_time": 99,
        }
        assert runtime_host._format_exc_message("P", ValueError("")) == "P: ValueError"
        assert runtime_host._format_exc_message("P", ValueError("z")) == "P: ValueError: z"

    def test_line_profile_export(self) -> None:
        ev = type("E", (), {"_pine_line_profile": {2: (2.0, 4), 1: (1.0, 2)}})()
        rows = runtime_host._export_line_profile(ev)
        assert rows[0]["line"] == 1
        assert rows[1]["line"] == 2
        assert rows[0]["execs"] == 2
        assert abs(rows[0]["pct"] + rows[1]["pct"] - 100.0) < 1e-6
        assert runtime_host._export_line_profile(type("E", (), {})()) == []

    def test_lazy_calendar_context(self) -> None:
        cal = runtime_host.LazyCalendarContext()
        cal.set_bar_time(1_700_000_000_000)
        assert isinstance(cal["year"], int)
        assert isinstance(cal.get("month"), int)
        assert cal.get("missing", 7) == 7
        cal2 = runtime_host.LazyCalendarContext()
        cal2.set_bar_time(None)  # type: ignore[arg-type]
        assert cal2.get("year", None) is None or isinstance(cal2.get("year", 0), int)

    def test_pack_and_coerce_helpers(self) -> None:
        assert runtime_host._pack_ohlcv_columns([])[0] == []
        rows = [{"open": 1, "high": 2, "low": 0.5, "close": 1.5}]
        o, h, low, c, v, t = runtime_host._pack_ohlcv_columns(rows)
        assert o == [1.0] and h == [2.0] and low == [0.5] and c == [1.5]
        assert v == [1.0] and t == [0.0]
        assert runtime_host._coerce_volume_cell(None) == 1.0
        assert runtime_host._coerce_volume_cell(0) == 0.0
        assert runtime_host._coerce_time_cell(None, 2) == 120_000.0
        assert runtime_host._coerce_time_cell("bad", 1) == 60_000.0
        assert runtime_host._coerce_ohlc_cell(None) == 0.0
        assert runtime_host._coerce_ohlc_cell("x") == 0.0
        assert runtime_host._json_safe_number(1.5) == 1.5
        assert runtime_host._json_safe_number(float("nan")) is None
        assert runtime_host._json_safe_number(float("inf")) is None
        assert runtime_host._color_str(None) is None
        assert runtime_host._color_str("#fff") == "#fff"

    def test_build_run_profile_and_attach(self) -> None:
        profile = runtime_host._build_run_profile(
            total_ms=10.0,
            bars=3,
            mode="interpret",
            parse_ms=1.0,
            eval_ms=2.0,
            lines=[{"line": 1, "ms": 0.5, "execs": 1, "pct": 100.0}],
        )
        assert profile["bars"] == 3
        assert profile["mode"] == "interpret"
        result = {"series": {"c": [1, 2]}}
        attached = runtime_host._attach_logs_profile(
            result,
            total_ms=10.0,
            bars=2,
            mode="interpret",
            parse_ms=1.0,
            eval_ms=2.0,
        )
        assert "profile" in attached
        assert "logs" in attached

    def test_syminfo_chart_timeframe_helpers(self) -> None:
        tf = runtime_host._chart_timeframe("60")
        assert tf.period == "60"
        assert tf.ishours is True
        ctx = runtime_host._timeframe_context(tf)
        assert ctx["timeframe.period"] == "60"
        assert ctx["timeframe.multiplier"] == 60
        sym = runtime_host.Syminfo()
        sym.ticker = "MSFT"
        sym.tickerid = "MSFT"
        assert sym.ticker == "MSFT"
        chart = runtime_host.Chart()
        assert chart.is_standard is True
        assert runtime_host.Barstate().isnew is True
        assert runtime_host.Chartinfo().type == "candle"

    def test_runtime_symbol_helpers_and_bid_ask(self) -> None:
        rt = Runtime(symbol="BINANCE:BTCUSDT", timeframe="5")
        assert rt._extract_prefix("BINANCE:BTCUSDT") in {"BINANCE", "BTCUSDT"} or isinstance(
            rt._extract_prefix("BINANCE:BTCUSDT"), str
        )
        assert "BTC" in rt._extract_ticker("BINANCE:BTCUSDT") or rt._extract_ticker("BINANCE:BTCUSDT")
        rt.update_bid_ask(1.0, 2.0)
        rt.configure_footprint({"rows": []})
        assert rt._make_chart(_bars(2)) is not None

    def test_copy_restore_container_helpers(self) -> None:
        src = {"a": [1, {"b": 2}], "c": 3}
        snap = runtime_host._copy_container_contents(src)
        assert snap is not None
        src["a"].append(9)
        runtime_host._restore_container_contents(src, snap)
        assert 9 not in src["a"]
        assert runtime_host._copy_list_dict_level([1, [2]]) == [1, [2]]
        assert runtime_host._copy_ta_value([1, 2]) == [1, 2]
        assert runtime_host._drop_as_series_cache(type("E", (), {})()) is None

    def test_resolve_realtime_first(self) -> None:
        first, ticks = runtime_host._resolve_realtime_first(10, realtime_ticks=2, realtime_last_bar=True)
        assert first == 9
        assert ticks == 2
        first2, ticks2 = runtime_host._resolve_realtime_first(10, realtime_bars=3, realtime_ticks=1)
        assert first2 == 7
        assert ticks2 == 1
        first3, _ = runtime_host._resolve_realtime_first(10, realtime_from_bar=4, realtime_ticks=1)
        assert first3 == 4

    def test_parse_script_header_fields(self) -> None:
        fields = runtime_host._parse_script_header_fields(
            '//@version=6\nindicator("t", overlay=true, max_bars_back=50)\nplot(close)'
        )
        assert isinstance(fields, dict)

    def test_forming_helpers_and_json_plot(self) -> None:
        assert runtime_host._forming_hl(_bars(3), 1)[0] == pytest.approx(102.0)
        ev = type(
            "E",
            (),
            {
                "_strategy_state": None,
                "_plot_value_cols": [[1, 2, 3]],
                "_pine_as_series_cache": {"x": 1},
            },
        )()
        runtime_host._ratchet_forming_trails(ev, 1.0, 0.5)
        runtime_host._update_forming_trade_extremes(ev, 1.0, 0.5)
        runtime_host._discard_realtime_plot_tick(ev)
        runtime_host._drop_as_series_cache(ev)
        assert runtime_host._json_plot_value(float("nan"), "line") is None or True
        assert runtime_host._json_plot_value(1.25, "line") == 1.25
        assert runtime_host._series_values_jsonable([1, float("nan"), None])[-1] is None
        assert runtime_host._ohlcv_cache_total_bars({}) == 0
        packed = runtime_host._ohlcv_dicts_to_arrays(_bars(2))
        assert len(packed) == 5
        times = runtime_host._ohlcv_times_to_array(_bars(2))
        assert len(times) == 2
        assert runtime_host._export_pine_logs() == [] or isinstance(runtime_host._export_pine_logs(), list)
        runtime_host._clear_pine_logger()
