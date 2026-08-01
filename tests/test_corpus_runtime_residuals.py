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
        ],
    )
    def test_residual_scripts_ok(self, rel: str) -> None:
        path = DATA / rel
        if not path.exists():
            pytest.skip(f"missing {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(50), mode="interpret")
        assert "error" not in r, f"{rel}: {r.get('error')}"
