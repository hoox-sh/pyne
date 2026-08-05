# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit goldens for high-frequency corpus Runtime residual themes (C1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.runtime import Runtime
from pynescript.util.corpus_sanitize import sanitize_corpus_source

DATA = Path(__file__).resolve().parent / "data"


def _bars(n: int = 30) -> list[dict]:
    out: list[dict] = []
    price = 100.0
    for i in range(n):
        o = price
        c = price + (0.5 if i % 2 == 0 else -0.3)
        out.append(
            {
                "open": o,
                "high": max(o, c) + 0.5,
                "low": min(o, c) - 0.5,
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0,
            }
        )
        price = c
    return out


class TestKwargNoneNotTrimmed:
    def test_array_push_value_na(self) -> None:
        src = """//@version=5
indicator("t")
a = array.new_float()
array.push(id=a, value=na)
plot(array.size(a))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_array_push_value_number(self) -> None:
        src = """//@version=5
indicator("t")
a = array.new_float()
array.push(id=a, value=1.5)
plot(array.get(a, 0))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 1.5) < 1e-9


class TestArrayPushSoftArityAndNewcolor:
    """set05 residual: ``array.push takes array and value`` (~3+1).

    - Truncated TV docs demos end with bare ``array.push()``.
    - Community alias ``array.newcolor`` (no underscore) left receivers as na.
    """

    def test_array_push_zero_arg_noop(self) -> None:
        src = """//@version=6
indicator("t")
a = array.new<float>(5, 0)
array.push()
plot(array.size(a))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 5

    def test_array_push_na_id_noop(self) -> None:
        src = """//@version=5
indicator("t")
array.push(id=na, value=1.0)
plot(1)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_array_newcolor_alias_and_push_kwargs(self) -> None:
        # set05/indicators/8986_ind_gradients.pine pattern
        src = """//@version=5
indicator("t")
var color gradient = array.newcolor(size=0, initial_value=#000000)
if barstate.isfirst
    array.push(id=gradient, value=color.red)
plot(array.size(gradient))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_set05_array_insert_demo_zero_push(self) -> None:
        rel = "set05/indicators/6842_ind_array_insert.pine"
        path = DATA / rel
        if not path.is_file():
            pytest.skip(f"missing corpus file {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8"))
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_set05_gradients_newcolor(self) -> None:
        rel = "set05/indicators/8986_ind_gradients.pine"
        path = DATA / rel
        if not path.is_file():
            pytest.skip(f"missing corpus file {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8"))
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")


class TestSubscriptUnsupportedSoftNa:
    """set05 residual: ``Subscript not supported for <class …>`` (~3).

    Unresolved names resolve to their id *string*; nested-if scrape reorders can
    evaluate ``series[x2]`` before ``x2`` is bound → soft-na, not hard error.
    """

    def test_na_with_str_index_soft_fails(self) -> None:
        src = """//@version=5
indicator("t")
s = na
plot(na(s["foo"]) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_scalar_with_unresolved_name_index_soft_fails(self) -> None:
        # ``x2`` never assigned → visit_Name returns the string "x2"
        src = """//@version=5
indicator("t")
v = close
plot(na(v[x2]) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_set05_oath_strategy_subscript(self) -> None:
        rel = "set05/strategies/3270_str_oath.pine"
        path = DATA / rel
        if not path.is_file():
            pytest.skip(f"missing corpus file {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8"))
        r = Runtime().run(src, _bars(60), mode="interpret")
        assert "error" not in r, r.get("error")


class TestArrayGetSetKwargsAndNa:
    """C1 residual: array.get/set kwargs merge + soft-na index."""

    def test_array_get_kwargs(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(1.0, 2.0, 3.0)
plot(array.get(id=a, index=1))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 2.0) < 1e-9

    def test_array_get_index_na(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(1.0, 2.0, 3.0)
plot(nz(array.get(id=a, index=na), -1))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert float(r["plots"][-1]) == -1.0

    def test_array_set_kwargs_value(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(1.0, 2.0, 3.0)
array.set(id=a, index=1, value=9.5)
plot(array.get(a, 1))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 9.5) < 1e-9

    def test_array_set_value_na_kwargs(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(1.0, 2.0, 3.0)
array.set(id=a, index=1, value=na)
plot(nz(array.get(a, 1), -1))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert float(r["plots"][-1]) == -1.0

    def test_array_set_index_na_noop(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(1.0, 2.0, 3.0)
array.set(id=a, index=na, value=9.0)
plot(array.get(a, 1))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 2.0) < 1e-9

    def test_array_set_method_kwargs(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(1.0, 2.0, 3.0)
a.set(index=0, value=4.0)
plot(a.get(index=0))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 4.0) < 1e-9

    def test_stub_index_2d_to_1d_polyfill(self) -> None:
        """Unresolved ArrayExtension still flattens indices for array.get/set."""
        src = """//@version=5
indicator("t")
import FakeUser/ArrayExtension/1 as ae
a = array.new_float(size=9, initial_value=0.0)
array.set(id=a, index=ae.index_2d_to_1d(dimension_x=3, dimension_y=3, index_x=1, index_y=2), value=7.0)
plot(array.get(id=a, index=ae.index_2d_to_1d(3, 3, 1, 2)))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 7.0) < 1e-9


class TestV4Tonumber:
    def test_bare_tonumber(self) -> None:
        src = """//@version=5
indicator("t")
plot(tonumber("12.5"))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 12.5) < 1e-9


class TestMathIsfinite:
    def test_isfinite(self) -> None:
        src = """//@version=5
indicator("t")
plot(math.isfinite(close) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1


class TestStrategyTradeFields:
    def test_entry_comment_registered(self) -> None:
        src = """//@version=5
strategy("t")
strategy.entry("L", strategy.long, comment="c1")
if bar_index > 3
    strategy.close("L")
c = strategy.closedtrades.entry_comment(0)
plot(str.length(c))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_opentrades_entry_id(self) -> None:
        src = """//@version=5
strategy("t")
strategy.entry("Long", strategy.long)
id = strategy.opentrades.entry_id(0)
plot(str.length(id))
"""
        r = Runtime().run(src, _bars(10), mode="interpret")
        assert "error" not in r, r.get("error")


class TestColorStringCoercion:
    """C1: color.r/g/b/t and plots accept hex strings (context color.* is str)."""

    def test_color_r_on_named_constant(self) -> None:
        src = """//@version=5
indicator("t")
plot(color.r(color.red))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        # v6 context constant color.red is "#F23645"
        assert int(r["plots"][-1]) == 0xF2

    def test_color_channels_on_hex_literal(self) -> None:
        src = """//@version=5
indicator("t")
c = #00FF80
plot(color.r(c) + color.g(c) + color.b(c))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert int(r["plots"][-1]) == 0 + 255 + 0x80

    def test_color_t_on_hex_with_alpha(self) -> None:
        from pynescript.ast.evaluator.builtins.color import color_t

        # Fully transparent AA=00 → transp 100
        assert color_t("#FF000000") == 100
        # Opaque
        assert color_t("#FF0000FF") == 0
        assert color_t("#FF0000") == 0

    def test_plot_color_hex_kwarg(self) -> None:
        src = """//@version=5
indicator("t")
plot(close, color=#2962FF)
plot(color.b(#2962FF))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        # First series is close; channel lives on series.plot_1
        series = r.get("series") or {}
        ch = series.get("plot_1") or r["plots"]
        assert int(ch[-1]) == 0xFF

    def test_rgba_string_coercion(self) -> None:
        from pynescript.ast.evaluator.builtins.color import color_b
        from pynescript.ast.evaluator.builtins.color import color_g
        from pynescript.ast.evaluator.builtins.color import color_r
        from pynescript.ast.evaluator.builtins.color import color_t

        assert color_r("rgba(10, 20, 30, 1)") == 10
        assert color_g("rgb(10, 20, 30)") == 20
        assert color_b("rgba(10, 20, 30, 0.5)") == 30
        assert color_t("rgba(0, 0, 0, 0)") == 100


class TestStrReplace:
    """C1 residual: str.replace arity / occurrence / coerce / TV kwargs."""

    def test_three_arg_first_only(self) -> None:
        src = """//@version=5
indicator("t")
s = str.replace("abab", "a", "c")
plot(str.length(s))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        # "cbab" length 4
        assert r["plots"][-1] == 4

    def test_occurrence_zero(self) -> None:
        # TV docs sample: first "FTX" → "BINANCE"
        src = """//@version=5
indicator("t")
s = str.replace("FTX:BTCUSD / FTX:BTCEUR", "FTX", "BINANCE", 0)
// "BINANCE:BTCUSD / FTX:BTCEUR" — starts with B not F
plot(str.startswith(s, "BINANCE") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_occurrence_one(self) -> None:
        src = """//@version=5
indicator("t")
s = str.replace("Hello world!", "o", "0", 1)
// second "o" → "Hello w0rld!"
plot(str.contains(s, "w0rld") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_kwargs_source_target_replacement(self) -> None:
        src = """//@version=5
indicator("t")
s = str.replace_all(source="a b c", target=" ", replacement="-")
plot(str.length(s))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        # "a-b-c"
        assert r["plots"][-1] == 5

    def test_kwargs_out_of_order(self) -> None:
        src = """//@version=5
indicator("t")
s = str.replace_all(target=" ", replacement="-", source="a b")
plot(str.length(s))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        # "a-b"
        assert r["plots"][-1] == 3

    def test_na_source_soft_coerce(self) -> None:
        # Explicit na source must soft-coerce, not hard-fail
        src = """//@version=5
indicator("t")
s = str.replace_all(na, "X", "")
plot(str.length(s))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 0

    def test_coerce_number_args(self) -> None:
        src = """//@version=5
indicator("t")
s = str.replace(str.tostring(10101), "0", "x")
plot(str.length(s))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        # "1x101" first only
        assert r["plots"][-1] == 5


class TestTimestampDateStrings:
    """C1 residual: timestamp() date-string overloads used by corpus strategies."""

    @pytest.mark.parametrize(
        "date_str,expect_ms",
        [
            # Classic TV forms
            ("Dec 01 2021 23:59:59", 1_638_403_199_000),
            ("01 Jan 2000 00:00:00 GMT+10", 946_648_800_000),
            ("01 Jan 2000 13:30 +0000", 946_733_400_000),
            # 3-digit offset (+000 == UTC)
            ("01 Jan 1970 00:00 +000", 0),
            # ISO with attached offset (no space)
            ("2022-01-01T00:00:00+0000", 1_640_995_200_000),
            ("2013-01-01T00:00:00+08:00", 1_356_969_600_000),
            # Space-separated Y M D
            ("2021 01 01", 1_609_459_200_000),
            # Missing day/month space + Sept alias + French Janv
            ("15Aug 2022 14:00 +0000", 1_660_572_000_000),
            ("01 Sept 2021 06:00", 1_630_476_000_000),
            ("1 Janv 2020 00:00:00", 1_577_836_800_000),
            # Leading UTC
            ("UTC 01 Jan 2020 00:00", 1_577_836_800_000),
            # Year 0000 session template (normalized to year 1)
            ("0000-01-01 09:00:00", -62_135_564_400_000),
        ],
    )
    def test_parse_known_formats(self, date_str: str, expect_ms: int) -> None:
        from pynescript.ast.evaluator.builtins.utility import UtilityFunctionsMixin

        class _H(UtilityFunctionsMixin):
            def _error(self, msg: str) -> None:
                raise RuntimeError(msg)

        got = _H()._parse_timestamp_string(date_str)
        assert got == expect_ms, f"{date_str!r}: got {got}, expected {expect_ms}"

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "0930",
            "2025",
            "2024-04-028",
            "not a date",
            "GMT",
            "America/New_York",
        ],
    )
    def test_garbage_not_silently_parsed(self, bad: str) -> None:
        from pynescript.ast.evaluator.builtins.utility import UtilityFunctionsMixin

        class _H(UtilityFunctionsMixin):
            def _error(self, msg: str) -> None:
                raise RuntimeError(msg)

        assert _H()._parse_timestamp_string(bad) is None

    def test_runtime_timestamp_string(self) -> None:
        src = """//@version=5
indicator("t")
// Space YMD + ISO offset + 3-digit TZ — corpus residual themes
a = timestamp("2021 01 01")
b = timestamp("2022-01-01T00:00:00+0000")
c = timestamp("01 Jan 1970 00:00 +000")
plot(a == 1609459200000 ? 1 : 0)
plot(b == 1640995200000 ? 1 : 0)
plot(c)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        # Prefer named series when multi-plot; else flat plots
        if "plot_0" in series or "plot" in series:
            p0 = series.get("plot_0") or series.get("plot")
            p1 = series.get("plot_1")
            p2 = series.get("plot_2")
            assert p0 and int(p0[-1]) == 1
            if p1 is not None:
                assert int(p1[-1]) == 1
            if p2 is not None:
                assert int(p2[-1]) == 0
        else:
            plots = r.get("plots") or []
            assert plots, r



class TestSeriesIndexSoftFail:
    """C1 residual: negative / na / OOB history and str OOB → na, not Runtime Error."""

    def test_negative_history_offset_returns_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(close[-1])
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is None

    def test_for_to_auto_step_negative_index_soft_fails(self) -> None:
        # for i = 0 to -1 uses step -1 → i hits -1; must not abort bar loop
        src = """//@version=5
indicator("t")
s = 0.0
for i = 0 to -1
    s += nz(close[i])
plot(s)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_na_index_returns_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(close[na])
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is None

    def test_history_oob_returns_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(close[1000])
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is None

    def test_str_index_oob_soft_fails(self) -> None:
        # Python str supports []; short strings OOB must not raise Subscript error
        src = """//@version=5
indicator("t")
s = "a"
c = s[1]
plot(na(c) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1


class TestSyminfoDualMode:
    """C1 residual: ``Unknown built-in function: ''`` from dual-mode syminfo.*."""

    def test_prefix_function_parses_exchange(self) -> None:
        src = """//@version=5
indicator("t")
pref = syminfo.prefix("NASDAQ:AAPL")
plot(str.length(pref))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 6  # "NASDAQ"

    def test_ticker_function_parses_bare(self) -> None:
        src = """//@version=5
indicator("t")
tick = syminfo.ticker("NASDAQ:AAPL")
plot(str.length(tick))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 4  # "AAPL"

    def test_prefix_and_ticker_properties(self) -> None:
        src = """//@version=5
indicator("t")
plot(str.length(syminfo.prefix) + str.length(syminfo.ticker))
"""
        r = Runtime(symbol="NASDAQ:AAPL").run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 10  # 6 + 4

    def test_empty_builtin_name_soft_fails(self) -> None:
        """Defensive: empty call name → na (not hard error)."""
        from pynescript.ast.evaluator import NodeLiteralEvaluator

        ev = NodeLiteralEvaluator()
        assert ev._call_builtin("", []) is None

    def test_prefix_with_default_runtime_symbol(self) -> None:
        # Default Runtime symbol is bare "AAPL" (empty host prefix). Function form
        # must still parse the argument — was Unknown built-in function: ''.
        src = """//@version=5
indicator("t")
pref = syminfo.prefix("NASDAQ:AAPL")
tick = syminfo.ticker("NASDAQ:AAPL")
plot(str.length(pref) + str.length(tick))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 10


class TestTaFloatPeriod:
    """C1: ta.* length may be float / series float; na length → na (not hard fail)."""

    def test_sma_float_literal_period(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.sma(close, 14.0))
"""
        r = Runtime().run(src, _bars(40), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is not None

    def test_rsi_series_float_period(self) -> None:
        src = """//@version=5
indicator("t")
len = close > 0 ? 14.0 : 10.0
plot(ta.rsi(close, len))
"""
        r = Runtime().run(src, _bars(40), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is not None

    def test_ema_input_float_period(self) -> None:
        src = """//@version=5
indicator("t")
len = input.float(20.0, "Length")
plot(ta.ema(close, len))
"""
        r = Runtime().run(src, _bars(40), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is not None

    def test_sma_na_period_is_na(self) -> None:
        src = """//@version=5
indicator("t")
float len = na
plot(ta.sma(close, len))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert last is None or (isinstance(last, float) and last != last)


class TestIntSoftCoerceAndTickerModify:
    """set05 residual: int('pyramid_val') / ticker.modify(adjustment=) / str.tonumber(na)."""

    def test_int_non_numeric_string_is_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(na(int("pyramid_val")) ? 1 : 0)
plot(na(int("abc")) ? 1 : 0)
plot(int("2.01"))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or series.get("plot") or r["plots"]
        assert int(p0[-1]) == 1
        # third plot is int("2.01") → 2 when multi-series present
        p2 = series.get("plot_2")
        if p2 is not None:
            assert int(p2[-1]) == 2

    def test_strategy_pyramiding_unresolved_name_soft(self) -> None:
        # Mirrors sanitize dropping pyramid_val=1 before strategy(...)
        src = """//@version=5
strategy("t", pyramiding=pyramid_val, default_qty_value=cash_given_per_lot)
plot(close)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_ticker_modify_adjustment_kwarg(self) -> None:
        src = """//@version=5
indicator("t")
t = ticker.modify(syminfo.tickerid, adjustment=adjustment.dividends)
plot(str.length(str.tostring(t)) > 0 ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_str_tonumber_na_and_number(self) -> None:
        src = """//@version=5
indicator("t")
plot(na(str.tonumber(na)) ? 1 : 0)
plot(str.tonumber(12.5))
plot(na(str.tonumber("not-a-number")) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or series.get("plot") or r["plots"]
        assert int(p0[-1]) == 1
        p1 = series.get("plot_1")
        if p1 is not None:
            assert abs(float(p1[-1]) - 12.5) < 1e-9


class TestLocalFunctionNotUnknownBuiltin:
    """set05 residual: ``Unknown built-in function: 'f_priorBarsSatisfied'`` (~4).

    Root causes:
    1. Sanitize version-island pick dropped UDF defs from earlier sections.
    2. Bare missing names were promoted to ``_call_builtin`` → hard ValueError.

    Local/UDF calls must resolve from context; missing helpers soft-fail to na.
    """

    def test_udf_in_script_runs_not_unknown_builtin(self) -> None:
        src = """//@version=5
indicator("t")
f_priorBarsSatisfied(_objectToEval, _numOfBarsToLookBack) =>
    returnVal = false
    for i = 0 to _numOfBarsToLookBack
        if _objectToEval[i] == true
            returnVal := true
    returnVal
plot(f_priorBarsSatisfied(close > open, 2) ? 1 : 0)
"""
        r = Runtime().run(src, _bars(15), mode="interpret")
        assert "error" not in r, r.get("error")
        assert "Unknown built-in" not in str(r.get("error", ""))
        assert r["plots"][-1] in (0, 1)

    def test_missing_helper_soft_fails_to_na(self) -> None:
        """Demo helper never defined (``BarInSession``, ``sampleStdev``) → na."""
        src = """//@version=5
indicator("t")
plot(BarInSession("0930-1600") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(15), mode="interpret")
        assert "error" not in r, r.get("error")
        # Missing helper → na/falsey → 0
        assert float(r["plots"][-1]) == 0.0

    def test_missing_sample_stdev_soft_fails(self) -> None:
        src = """//@version=5
indicator("t")
plot(nz(sampleStdev(close, 10), -1))
"""
        r = Runtime().run(src, _bars(15), mode="interpret")
        assert "error" not in r, r.get("error")
        assert float(r["plots"][-1]) == -1.0

    def test_missing_helper_single_plot_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(nz(f_missingHelper(close), -99))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert float(r["plots"][-1]) == -99.0

    def test_context_udf_shadows_before_builtin_error(self) -> None:
        """User callable in context is preferred over unknown-builtin path."""
        src = """//@version=5
indicator("t")
myHelper(x) => x * 2
plot(myHelper(3))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 6.0) < 1e-9


class TestStrategyInitialCapitalReassign:
    """set05 residual: strategy.initial_capital = N → Unsupported reassignment target Attribute."""

    def test_strategy_initial_capital_assign_reads_back(self) -> None:
        src = """//@version=5
strategy("t")
strategy.initial_capital = 50000
plot(strategy.initial_capital)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 50000.0) < 1e-9

    def test_strategy_initial_capital_updates_equity(self) -> None:
        src = """//@version=5
strategy("t")
strategy.initial_capital = 25000
plot(strategy.equity)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 25000.0) < 1e-9

    def test_udt_field_reassign_still_works(self) -> None:
        src = """//@version=5
indicator("t")
type S
    float v
var S s = S.new(1.0)
s.v := 3.5
plot(s.v)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 3.5) < 1e-9

    def test_corpus_strategy_with_initial_capital_assign(self) -> None:
        rel = "set05/strategies/0893_str_bollinger_bands_backtesting.pine"
        path = DATA / rel
        if not path.exists():
            pytest.skip(f"missing {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(50), mode="interpret")
        assert "error" not in r, f"{rel}: {r.get('error')}"


class TestBareTaSeriesAliases:
    """set05 residual: bare ``obv``/``accdist``/``vwap`` as series (not name strings).

    Pine v3/v4 expose these as built-in series variables equivalent to zero-arg
    ``ta.obv`` / ``ta.accdist`` / ``ta.vwap``. Unresolved bare names used to
    leak as strings into ``ema(...)`` → ``float('obv')`` Runtime Error.
    """

    def test_bare_obv_plot_is_numeric(self) -> None:
        src = """//@version=4
study("t")
plot(obv)
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert isinstance(last, (int, float)), last
        assert last == last  # not NaN

    def test_bare_obv_in_ema_no_crash(self) -> None:
        # Corpus pattern: value = (obv - ema(obv,len))/1000000
        src = """//@version=4
study("t")
value = (obv - ema(obv, 5)) / 1000000
plot(value)
"""
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert last is None or isinstance(last, (int, float))

    def test_bare_accdist_in_ema_no_crash(self) -> None:
        src = """//@version=4
study("t")
osc = ema(accdist, 3) - ema(accdist, 10)
plot(osc)
"""
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert last is None or isinstance(last, (int, float))

    def test_bare_vwap_in_ema_no_crash(self) -> None:
        src = """//@version=4
study("t")
plot(ema(vwap, 7))
"""
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert last is None or isinstance(last, (int, float))

    def test_ta_qualified_still_works(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.obv)
plot(ta.accdist)
plot(ta.vwap)
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_unknown_source_string_soft_fails_not_crash(self) -> None:
        """Defense: non-series string source → na path, not float() crash."""
        from pynescript.ast.evaluator import NodeLiteralEvaluator

        ev = NodeLiteralEvaluator()
        # Simulate bar-mode current_series without alias
        ev.current_series = {"close": [1.0, 2.0, 3.0], "volume": [10.0, 10.0, 10.0]}  # type: ignore[attr-defined]
        assert ev._as_series("not_a_series") == []  # type: ignore[attr-defined]
        # Numeric string still coerces
        assert ev._as_series("12.5") == [12.5]  # type: ignore[attr-defined]


class TestLinregLengthAndKamaArity:
    """set05 residual: ta.linreg length<2 hard error; ta.kama arity hard error.

    - OTT scripts default OTT Period to 1 and call ``ta.linreg(src, 1, …)``.
    - TV returns na for short length rather than raising.
    - ``ta.kama(source, length)`` uses Kaufman defaults fast=2, slow=30.
    - UDF named ``kama`` that rebinds ``kama = 0.0`` must stay callable across bars.
    """

    def test_linreg_length_1_is_na(self) -> None:
        src = """//@version=5
indicator("t")
length = 1
plot(ta.linreg(close, length, 0))
"""
        r = Runtime().run(src, _bars(10), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert last is None or (isinstance(last, float) and last != last)

    def test_linreg_length_0_is_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.linreg(close, 0, 0))
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        last = r["plots"][-1]
        assert last is None or (isinstance(last, float) and last != last)

    def test_linreg_length_valid_still_numeric(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.linreg(close, 5, 0))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        assert isinstance(r["plots"][-1], (int, float))
        assert r["plots"][-1] == r["plots"][-1]

    def test_ott_tsf_length_1_no_crash(self) -> None:
        """Corpus OTT pattern: length=1 default into TSF via linreg."""
        src = """//@version=5
strategy("t")
length = input.int(defval=1, title="OTT Period", minval=1)
src = close
Tsf_Func(src, length) =>
    lrc = ta.linreg(src, length, 0)
    lrc1 = ta.linreg(src, length, 1)
    lrs = (lrc - lrc1)
    TSF = ta.linreg(src, length, 0) + lrs
    TSF
plot(Tsf_Func(src, length))
"""
        r = Runtime().run(src, _bars(15), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_kama_two_arg_defaults(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.kama(close, 10))
"""
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" not in r, r.get("error")
        assert isinstance(r["plots"][-1], (int, float))

    def test_kama_four_arg_matches_two_arg_defaults(self) -> None:
        src = """//@version=5
indicator("t")
a = ta.kama(close, 10)
b = ta.kama(close, 10, 2, 30)
plot(a - b)
"""
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1])) < 1e-9

    def test_udf_named_kama_with_self_series_survives_bars(self) -> None:
        """set05 klinger / noscoobies: UDF ``kama`` rebinds local series ``kama``."""
        src = """//@version=5
indicator("t")
kama(src) =>
    kama = 0.0
    kama := nz(kama[1]) + 0.1 * (src - nz(kama[1]))
plot(kama(close))
"""
        r = Runtime().run(src, _bars(8), mode="interpret")
        assert "error" not in r, r.get("error")
        assert len(r["plots"]) == 8

    def test_udf_kama_two_arg_v2_style(self) -> None:
        src = """//@version=2
study("t")
kama(close, amaLength) =>
    diff = abs(close[0] - close[1])
    signal = abs(close - close[amaLength])
    noise = sum(diff, amaLength)
    efratio = noise != 0 ? signal / noise : 1
    smooth = pow(efratio * (0.666 - 0.0645) + 0.0645, 2)
    kama = nz(kama[1], close) + smooth * (close - nz(kama[1], close))
    kama
plot(kama(close, 1))
"""
        r = Runtime().run(src, _bars(8), mode="interpret")
        assert "error" not in r, r.get("error")
        assert len(r["plots"]) == 8


class TestStrContainsFamilySoftNa:
    """C1 residual: str.contains / startswith / endswith na + coerce."""

    def test_contains_na_is_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(na(str.contains(na, "a")) ? 1 : 0)
plot(na(str.contains("abc", na)) ? 1 : 0)
plot(str.contains("abc", "b") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or series.get("plot") or r["plots"]
        assert int(p0[-1]) == 1
        p2 = series.get("plot_2")
        if p2 is not None:
            assert int(p2[-1]) == 1

    def test_startswith_endswith_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(na(str.startswith(na, "x")) ? 1 : 0)
plot(str.endswith("hello", "lo") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")

    def test_contains_number_coerce(self) -> None:
        src = """//@version=5
indicator("t")
plot(str.contains(str.tostring(10101), "010") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1


class TestPeriodUnresolvedNameSoftNa:
    """C1 residual: ta.* length is unresolved name string → na, not hard fail."""

    def test_sma_unresolved_length_is_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(nz(ta.sma(close, length), -1))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        assert float(r["plots"][-1]) == -1.0

    def test_rsi_unresolved_rsiLen_is_na(self) -> None:
        src = """//@version=5
indicator("t")
plot(nz(ta.rsi(close, rsiLen), -1))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        assert float(r["plots"][-1]) == -1.0

    def test_numeric_string_period_still_works(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.sma(close, "14"))
"""
        r = Runtime().run(src, _bars(40), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is not None

    def test_extra_ta_args_soft_ignored(self) -> None:
        src = """//@version=6
indicator("t")
extra = 1
plot(ta.sma(close, 14, extra))
"""
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] is not None


class TestTickerStandardZeroArg:
    """C1 residual: ticker.standard() uses chart ticker; string concat works."""

    def test_zero_arg_stringifies(self) -> None:
        src = """//@version=5
indicator("t")
s = ticker.standard() + " /"
plot(str.length(s) > 0 ? 1 : 0)
"""
        r = Runtime(symbol="NASDAQ:AAPL").run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1

    def test_one_arg_still_works(self) -> None:
        src = """//@version=5
indicator("t")
s = str.tostring(ticker.standard("BATS:SPY"))
plot(str.contains(s, "SPY") ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1


class TestArraySomeUnaryAndMatrixFillRegion:
    """C1 residual: array.some() on bools; matrix.fill region form."""

    def test_array_some_unary_bools(self) -> None:
        src = """//@version=5
indicator("t")
a = array.from(false, true, false)
plot(a.some() ? 1 : 0)
b = array.from(false, false)
plot(b.some() ? 1 : 0)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or series.get("plot") or r["plots"]
        assert int(p0[-1]) == 1

    def test_matrix_fill_region(self) -> None:
        src = """//@version=6
indicator("t")
m = matrix.new<float>(4, 5, 0.0)
matrix.fill(m, 7.0, 0, 2, 1, 3)
plot(matrix.get(m, 0, 1))
plot(matrix.get(m, 0, 0))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or series.get("plot") or r["plots"]
        assert abs(float(p0[-1]) - 7.0) < 1e-9
        p1 = series.get("plot_1")
        if p1 is not None:
            assert abs(float(p1[-1]) - 0.0) < 1e-9

    def test_array_standardize_with_history_na(self) -> None:
        src = """//@version=6
indicator("t")
a = array.new_float(0)
for i = 0 to 9
    array.push(a, close[i])
b = array.standardize(a)
plot(nz(array.min(b), 0))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")


class TestStrConcatAndAlertSoft:
    """C1 residual: str+number concat; zero-arg alert no-op."""

    def test_str_plus_number_concat(self) -> None:
        src = """//@version=5
indicator("t")
s = "ISIN: " + 12.5
plot(str.length(s))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert int(r["plots"][-1]) == len("ISIN: 12.5")

    def test_alert_zero_arg_noop(self) -> None:
        src = """//@version=6
indicator("t")
alert()
plot(1)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 1


class TestCorpusScripts:
    @pytest.mark.parametrize(
        "rel",
        [
            "set01/indicators/119_ind_session_input_parser.pine",
            "set01/libraries/005_lib_withglobalpass.pine",
            # C1 array.get/set residual (stub index_2d_to_1d → real index)
            "set01/libraries/017_lib_mathsearchdijkstra.pine",
            "set02/libraries/034_lib_probability.pine",
            "set04/indicators/0739_ind_non_ascii_case_demo.pine",
            "set04/strategies/0140_str_strategy_closedtrades_entry_comment_example.pine",
            "set03/strategies/0267_str_strategy_opentrades_max_drawdown_example_1.pine",
            # C1 str.replace residual (4-arg occurrence form)
            "set04/indicators/0867_ind_str_replace.pine",
            # C1 timestamp() date-string residual samples
            "set03/strategies/0229_str_btcusdt_daily_enhanced_bitcoin_bull_market_support.pine",
            "set05/strategies/0156_str_morning_scalp.pine",  # 15Aug +0000
            "set05/strategies/2143_str_heikin_ashi_roc_percentile_strategy_2.pine",  # "2015 03 03"
            # C1 negative series index residual samples
            "set02/indicators/111_ind_ehlers_hilbert_transform_sinewave_ht_sine.pine",
            "set02/indicators/115_ind_ehlers_hilbert_transform_dominant_cycle_phase_ht_dcphase.pine",
            # C1 Unknown built-in function: '' — dual-mode syminfo.prefix/ticker
            "set04/indicators/0912_ind_syminfo_prefix_fun.pine",
            "set04/indicators/0913_ind_syminfo_ticker_fun.pine",
            # C1 strategy.initial_capital = N (Attribute ReAssign)
            "set05/strategies/0893_str_bollinger_bands_backtesting.pine",
            "set05/strategies/0769_str_buy_and_sell_bullish_engulfing_the_quant_science_2.pine",
            # C1 bare TA series aliases (obv / accdist / vwap)
            "set05/indicators/8386_ind_valancer.pine",
            "set05/indicators/8601_ind_price_levels_hline.pine",
            "set05/indicators/9042_ind_tf_chaikin_oscillator_indicator.pine",
            "set05/strategies/4510_str_strat_stemwap.pine",
            # set05: int('pyramid_val') via strategy(pyramiding=…) after sanitize
            "set05/strategies/6632_str_tradinggroundhog_strategy_and_fractal_v1.pine",
            "set05/strategies/6650_str_tradinggroundhog_strategy_and_wavetrend_v2.pine",
            "set05/strategies/6674_str_adaptive_volatility_breakout_trading_strategy.pine",
            # set05: ticker.modify(..., adjustment=adjustment.dividends)
            "set05/indicators/7602_ind_custom_contexts_demo_2.pine",
            "set05/indicators/7704_ind_custom_contexts_demo_1.pine",
            # set05: str.tonumber(na / non-string) soft
            "set05/indicators/7362_ind_gexbot.pine",
            "set05/strategies/0082_str_dynamic_stop_loss_demo.pine",
            # set05 local-UDF-as-builtin (f_priorBarsSatisfied / multi-section //@version)
            "set05/strategies/0367_str_strategy_myth_busting_10_insidebar_plus_ema.pine",
            "set05/strategies/3169_str_strategy_myth_busting_10_insidebar_plus_ema_2.pine",
            "set05/strategies/0682_str_strategy_myth_busting_7_macdbb_plus_ssl_plus_vsf.pine",
            "set05/strategies/3243_str_strategy_myth_busting_7_macdbb_plus_ssl_plus_vsf_2.pine",
            # set05 ta.linreg length<2 soft-na (OTT / slope)
            "set05/indicators/9066_ind_slope.pine",
            "set05/strategies/0360_str_rsi_ott_tp_sl.pine",
            "set05/strategies/1247_str_multiple_ott.pine",
            "set05/strategies/3160_str_rsi_ott_rsi_and_ott_bands_strategy_analysis.pine",
            # set05 ta.kama arity / UDF self-name kama
            "set05/indicators/8860_ind_klinger.pine",
            "set05/strategies/6253_str_noscoobies_slow_heiken_ashi_and_exponential_moving_average_strategy_2_2.pine",
            # Round 7 C1 residual recovery samples
            "set02/indicators/220_ind_parameter_naming_test_cases.pine",
            "set02/indicators/238_ind_test_script.pine",
            "set03/indicators/0743_ind_flowbias.pine",
            "set03/indicators/0915_ind_checking_for_substrings_demo.pine",
            "set03/indicators/0688_ind_confluence_of_alerts_v2.pine",
            "set03/indicators/0957_ind_isin_demo.pine",
            "set03/indicators/0923_ind_syminfo_timezone_demo.pine",
            "set04/indicators/0838_ind_matrix_fill_example.pine",
            "set04/indicators/0891_ind_array_standardize_example.pine",
            "set04/indicators/0623_ind_chart_s_visible_high_low.pine",
        ],
    )
    def test_residual_scripts_ok(self, rel: str) -> None:
        path = DATA / rel
        if not path.exists():
            pytest.skip(f"missing {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(50), mode="interpret")
        assert "error" not in r, f"{rel}: {r.get('error')}"


class TestSet05TimeoutHotPaths:
    """Cheap host-side wins for set05 interpret TIMEOUT themes.

    Categories still expected to stay slow / TIMEOUT without full ML rewrites
    (see agent writeup): SuperTrend AI k-means (maxIter=1000/bar), RANSAC ML
    regression, Nebula/to_method mega-scripts with heavy UDF/drawing, ICT/SMC
    scanners, and intentional "loop is too long" demos (≈5e5 AST iters/bar).
    """

    def test_static_for_to_inclusive_bounds(self) -> None:
        """Constant-bound for-to uses static path; end is inclusive."""
        src = """//@version=5
indicator("t")
s = 0
for i = 1 to 10
    s := s + i
plot(s)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 55  # 1+…+10

    def test_static_for_to_downward(self) -> None:
        src = """//@version=5
indicator("t")
s = 0
for i = 3 to 1
    s := s + i
plot(s)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 6

    def test_nested_const_timestamp_loop_completes(self) -> None:
        """TV "loop is too long" pattern: nested loops + literal timestamp().

        Must finish quickly enough for corpus 10s budgets on small bar counts
        (const-fold timestamp + static for-to). Result is always 0 on synthetic
        bars (times never fall on 2017-02-23).
        """
        import time

        src = """//@version=5
indicator("Loop is too long", max_bars_back = 101)
s = 0
for i = 1 to 1e3
    for j = 0 to 100
        if timestamp(2017, 02, 23, 00, 00) <= time[j] and time[j] < timestamp(2017, 02, 23, 23, 59)
            s := s + 1
plot(s)
"""
        t0 = time.perf_counter()
        r = Runtime().run(src, _bars(10), mode="interpret")
        elapsed = time.perf_counter() - t0
        assert "error" not in r, r.get("error")
        assert r["plots"][-1] == 0
        # Pre-fix baseline was ~10s for 5 bars; 10 bars should stay well under 10s.
        assert elapsed < 8.0, f"nested timestamp loop too slow: {elapsed:.2f}s"

    def test_array_kwargs_merge_without_typeerror(self) -> None:
        """array.* named kwargs must merge via _KWARG_ORDER (no per-call inspect)."""
        src = """//@version=5
indicator("t")
a = array.new_float(size=2, initial_value=1.5)
array.set(id=a, index=1, value=9.0)
plot(array.get(id=a, index=0) + array.get(id=a, index=1))
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        assert "error" not in r, r.get("error")
        assert abs(float(r["plots"][-1]) - 10.5) < 1e-9

    def test_series_name_subscript_offset(self) -> None:
        """Name[Name] series history fast path keeps Pine reverse-offset semantics."""
        src = """//@version=5
indicator("t")
plot(close[0], title="c0")
plot(nz(close[1], -1), title="c1")
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r["series"]
        assert series["c0"][-1] == series["c0"][-1]
        assert series["c1"][-1] == series["c0"][-2]
        assert series["c1"][0] == -1


class TestIntentionalRuntimeErrorDemos:
    """R7/R8 residual: library runtime.error + lower-TF guard must stay hard-fail.

    Do **not** soft-suppress these — they match TradingView fail-closed library
    unit tests. Corpus runner classifies them as EXPECTED_FAIL (not OK).
    """

    # Paths relative to tests/data/ (same list as scripts/corpus_run_runtime.py).
    _EXPECTED = (
        "set02/libraries/019_lib_functionnnetwork.pine",
        "set02/libraries/021_lib_analysisinterpolationloess.pine",
        "set02/libraries/026_lib_mathcomplexoperator.pine",
        "set02/libraries/032_lib_colorscheme.pine",
        "set02/libraries/036_lib_mathcomplextrigonometry.pine",
        "set04/indicators/0703_ind_higher_timeframe_security_demo.pine",
    )

    def test_expected_fail_classifier_paths(self) -> None:
        import importlib.util
        from pathlib import Path as P

        root = P(__file__).resolve().parents[1]
        script = root / "scripts" / "corpus_run_runtime.py"
        spec = importlib.util.spec_from_file_location("corpus_run_runtime_harness", script)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.EXPECTED_FAIL_RELS == frozenset(self._EXPECTED)
        for rel in self._EXPECTED:
            abs_path = str(DATA / rel)
            assert mod.is_expected_fail(abs_path, "RuntimeError: demo guard"), rel
            assert mod.is_expected_fail(rel, "RuntimeError: x"), rel
            # Empty error must not classify (timeout-as-OK path for other libs).
            assert not mod.is_expected_fail(abs_path, ""), rel
        assert not mod.is_expected_fail(
            "set01/indicators/001_ind_whatever.pine", "RuntimeError: boom"
        )

    @pytest.mark.parametrize(
        "rel",
        [
            "set02/libraries/019_lib_functionnnetwork.pine",
            "set04/indicators/0703_ind_higher_timeframe_security_demo.pine",
        ],
    )
    def test_intentional_demos_still_surface_runtime_error(self, rel: str) -> None:
        """Sample of the residual list: Runtime must still report error (no soft-OK)."""
        path = DATA / rel
        if not path.is_file():
            pytest.skip(f"missing {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert "error" in r and r["error"], f"{rel}: expected runtime error, got clean run"
