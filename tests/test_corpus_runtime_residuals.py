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

"""Unit goldens for high-frequency corpus Runtime residual themes (C1).

High-value soft paths used by residual recovery:

1. ``ta.dmi`` / period soft-na (+ dual-namespace bare ``method dmi``)
2. ``line.get_price`` / ``get_y*`` with na line
3. unary ``ta.change(source)`` (length defaults to 1)
4. ``request.security`` lower-TF guard stays EXPECTED (do not soft-kill)
5. ``runtime.error`` still raises (must not be suppressed)
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

from backend.runtime import Runtime
from backend.series import PineSeries
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.evaluator.builtins.drawing import Line
from pynescript.util.corpus_sanitize import sanitize_corpus_source
from tests.fixtures.parity.ohlcv import OHLCV

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
                "time": 1_700_000_000_000 + i * 60_000,
                "volume": 1000.0,
            }
        )
        price = c
    return out


def _plot0(result: dict) -> list:
    series = result.get("series") or {}
    if "plot_0" in series:
        return series["plot_0"]
    return result.get("plots") or []


def _is_pine_na(value: object) -> bool:
    """True for Runtime plot na (None or IEEE nan)."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


# ---------------------------------------------------------------------------
# 1. ta.dmi / period soft-na
# ---------------------------------------------------------------------------


class TestTaDmiNaLengthSoft:
    """``ta.dmi`` with na length → ``[na, na, na]`` (not hard-fail)."""

    def test_dmi_2arg_na_length_is_na_tuple(self) -> None:
        src = """//@version=5
indicator("t")
[diplus, diminus, adx] = ta.dmi(na, na)
plot(diplus)
plot(diminus)
plot(adx)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        for key in ("plot_0", "plot_1", "plot_2"):
            vals = series.get(key) or []
            assert vals, key
            assert all(_is_pine_na(v) for v in vals), vals

    def test_dmi_4arg_na_length_is_na_tuple(self) -> None:
        src = """//@version=5
indicator("t")
[diplus, diminus, adx] = ta.dmi(high, low, close, na)
plot(diplus)
plot(diminus)
plot(adx)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        for key in ("plot_0", "plot_1", "plot_2"):
            vals = series.get(key) or []
            assert vals, key
            assert all(_is_pine_na(v) for v in vals), vals

    def test_dmi_4arg_na_ohlc_is_na_tuple(self) -> None:
        src = """//@version=5
indicator("t")
[diplus, diminus, adx] = ta.dmi(na, na, na, 14)
plot(diplus)
plot(diminus)
plot(adx)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        for key in ("plot_0", "plot_1", "plot_2"):
            vals = series.get(key) or []
            assert vals, key
            assert all(_is_pine_na(v) for v in vals), vals

    def test_dmi_unresolved_length_is_na(self) -> None:
        src = """//@version=5
indicator("t")
[diplus, diminus, adx] = ta.dmi(diLength, adxSmoothing)
plot(diplus)
plot(nz(diplus, -1))
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        assert _is_pine_na(p0[-1])
        p1 = series.get("plot_1")
        if p1 is not None:
            assert float(p1[-1]) == -1.0

    def test_dmi_float_period_still_works(self) -> None:
        src = """//@version=5
indicator("t")
[diplus, diminus, adx] = ta.dmi(14.0, 14.0)
plot(adx)
"""
        r = Runtime().run(src, _bars(40), mode="interpret")
        assert "error" not in r, r.get("error")
        assert r.get("plots") is not None


class TestCustomMethodDmiDualNamespace:
    """Bare ``method dmi`` must not fall through to bare ``ta.dmi`` after series shadow.

    Pattern from set01 ML perceptron scripts:
    ``method dmi(...); float dmi = dmi(High, Low, Close, Period)``.
    """

    def test_method_dmi_series_name_reuse_stays_on_method(self) -> None:
        src = """//@version=5
indicator("t")
method dmi(float h, float l, float c, int p=20) =>
    42.0 + (h - l) * 0.0 + c * 0.0 + p * 0.0
float dmi = dmi(high, low, close, 14)
plot(dmi)
"""
        r = Runtime().run(src, _bars(10), mode="interpret")
        assert "error" not in r, r.get("error")
        plots = _plot0(r)
        assert len(plots) == 10
        for v in plots:
            assert abs(float(v) - 42.0) < 1e-9, plots

    def test_method_dmi_with_security_unpack_no_run_fail(self) -> None:
        src = """//@version=5
indicator("t")
Timeframe = input.timeframe("1")
Period = input.int(14)
[Open, High, Low, Close, Volume, Time] = request.security("", Timeframe, [open, high, low, close, volume, time])
method rma(float x, int p) => ta.rma(x, p)
method dmi(float h, float l, float c, int p=20) =>
    float up = ta.change(h)
    float down = -ta.change(l)
    float tr = math.max(h - l, math.abs(h - nz(c[1])), math.abs(l - nz(c[1])))
    float atr = ta.rma(tr, p)
    float plus = fixnan(100 * ta.rma(up > down and up > 0 ? up : 0.0, p) / atr)
    float minus = fixnan(100 * ta.rma(down > up and down > 0 ? down : 0.0, p) / atr)
    float diff = plus - minus
    den = ta.highest(diff, p) - ta.lowest(diff, p)
    den == 0 ? 50.0 : 100 * (diff - ta.lowest(diff, p)) / den
float dmi = dmi(High, Low, Close, Period)
plot(dmi)
plot(na(dmi) ? 0 : 1)
"""
        r = Runtime().run(src, _bars(40), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        flags = series.get("plot_1") or []
        # After warmup at least some bars should be non-na
        assert any(int(x) == 1 for x in flags[-10:]), flags


class TestCorpusPerceptronDmiScripts:
    """One-shot Runtime eval of the two set01 RUN_FAIL residual scripts."""

    @pytest.mark.parametrize(
        "rel",
        [
            "set01/indicators/231_ind_machine_learning_perceptron_based_strategy_v_2.pine",
            "set01/strategies/075_str_machine_learning_perceptron_based_strategy_v_3.pine",
        ],
    )
    def test_perceptron_scripts_no_ta_dmi_run_fail(self, rel: str) -> None:
        path = DATA / rel
        if not path.is_file():
            pytest.skip(f"missing corpus file {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(40), mode="interpret")
        err = r.get("error") or ""
        assert "error" not in r or not err, err
        assert "ta.dmi" not in str(err)


# ---------------------------------------------------------------------------
# 2. line.get_price / get_y* with na line
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_drawings():
    DrawingRegistry.reset()
    yield
    DrawingRegistry.reset()


class TestLineGetPriceSoftNaAndSeries:
    """TV-ish soft-na + series unwrap for line getters / get_price.

    Corpus residuals:
    - set03/0886 ``var line = na`` then ``get_y*`` / ``line.get_price`` before create
    - set04/0951 ``line.new(..., high[5], ..., high)`` stores PineSeries endpoints
    """

    def test_get_price_na_line_returns_na(self) -> None:
        e = NodeLiteralEvaluator()
        m = e._build_builtin_map()
        assert m["line.get_price"]([None, 0]) is None
        assert m["line.get_price"]([None, 5]) is None

    def test_get_coords_na_line_returns_na(self) -> None:
        e = NodeLiteralEvaluator()
        m = e._build_builtin_map()
        assert m["line.get_x1"]([None]) is None
        assert m["line.get_y1"]([None]) is None
        assert m["line.get_x2"]([None]) is None
        assert m["line.get_y2"]([None]) is None

    def test_get_price_na_endpoint_returns_na(self) -> None:
        e = NodeLiteralEvaluator()
        m = e._build_builtin_map()
        ln = Line(0, None, 10, 10.0)
        DrawingRegistry.add_line(ln)
        assert m["line.get_price"]([ln, 5]) is None
        assert m["line.get_y1"]([ln]) is None
        assert m["line.get_y2"]([ln]) == pytest.approx(10.0)

    def test_get_price_pine_series_endpoints(self) -> None:
        e = NodeLiteralEvaluator()
        m = e._build_builtin_map()
        y1 = PineSeries(0.0)
        y2 = PineSeries(10.0)
        ln = m["line.new"]([0, y1, 10, y2])
        assert isinstance(ln.y1, PineSeries)
        price = m["line.get_price"]([ln, 5])
        assert price == pytest.approx(5.0)
        assert m["line.get_y1"]([ln]) == pytest.approx(0.0)
        assert m["line.get_y2"]([ln]) == pytest.approx(10.0)

    def test_runtime_na_line_then_get_price(self) -> None:
        src = """//@version=6
indicator("t")
var line directionLine = na
float lineValue = line.get_price(directionLine, bar_index)
float y2 = directionLine.get_y2()
float y1 = line.get_y1(directionLine)
plot(lineValue)
plot(y2)
plot(y1)
"""
        r = Runtime().run(src, _bars(5), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        for key in ("plot_0", "plot_1", "plot_2"):
            vals = series.get(key) or r.get("plots") or []
            if key == "plot_0" or series.get(key) is not None:
                assert all(_is_pine_na(v) for v in (series.get(key) or vals)), key

    def test_runtime_line_new_series_endpoints_get_price(self) -> None:
        src = """//@version=6
indicator("GetPrice", overlay=true)
var line l = na
if bar_index == 10
    l := line.new(0, high[5], bar_index, high)
plot(line.get_price(l, bar_index), color=color.green)
"""
        r = Runtime().run(src, _bars(20), mode="interpret")
        assert "error" not in r, r.get("error")
        plots = r.get("plots") or []
        assert any(isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)) for v in plots[10:])


@pytest.mark.skipif(
    not (DATA / "set03/indicators/0886_ind_reading_line_values_demo.pine").is_file(),
    reason="corpus script not present",
)
def test_corpus_0886_reading_line_values_demo() -> None:
    src = (DATA / "set03/indicators/0886_ind_reading_line_values_demo.pine").read_text()
    r = Runtime().run(src, OHLCV, mode="interpret")
    assert "error" not in r, r.get("error")


@pytest.mark.skipif(
    not (DATA / "set04/indicators/0951_ind_getprice.pine").is_file(),
    reason="corpus script not present",
)
def test_corpus_0951_getprice() -> None:
    src = (DATA / "set04/indicators/0951_ind_getprice.pine").read_text()
    r = Runtime().run(src, OHLCV, mode="interpret")
    assert "error" not in r, r.get("error")


# ---------------------------------------------------------------------------
# 3. unary ta.change(source)
# ---------------------------------------------------------------------------


class TestTaChangeUnary:
    """TV ``ta.change(source)`` defaults length to 1."""

    def test_unary_change_equals_length_one(self) -> None:
        src = """//@version=5
indicator("t")
plot(ta.change(close))
plot(ta.change(close, 1))
"""
        r = Runtime().run(src, _bars(8), mode="interpret")
        assert "error" not in r, r.get("error")
        series = r.get("series") or {}
        p0 = series.get("plot_0") or r["plots"]
        p1 = series.get("plot_1")
        if p1 is not None:
            for a, b in zip(p0, p1, strict=False):
                if _is_pine_na(a) and _is_pine_na(b):
                    continue
                assert a == pytest.approx(float(b))
            assert any(not _is_pine_na(v) for v in p0[1:])


# ---------------------------------------------------------------------------
# 4–5. request.security lower-TF EXPECTED + runtime.error hard-fail
# ---------------------------------------------------------------------------


class TestIntentionalRuntimeErrorDemos:
    """Library ``runtime.error`` + lower-TF security guard must stay hard-fail.

    Corpus runner classifies these as EXPECTED_FAIL. Soft-killing inflates OK%.
    """

    # Core intentional demos (subset must remain listed; runner may have more).
    _CORE_EXPECTED = (
        "set02/libraries/019_lib_functionnnetwork.pine",
        "set02/libraries/021_lib_analysisinterpolationloess.pine",
        "set02/libraries/026_lib_mathcomplexoperator.pine",
        "set02/libraries/032_lib_colorscheme.pine",
        "set02/libraries/036_lib_mathcomplextrigonometry.pine",
        "set04/indicators/0703_ind_higher_timeframe_security_demo.pine",
    )

    def test_expected_fail_classifier_includes_lower_tf_and_runtime_error(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "corpus_run_runtime.py"
        if not script.is_file():
            pytest.skip("corpus_run_runtime.py missing")
        spec = importlib.util.spec_from_file_location("corpus_run_runtime_harness", script)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for rel in self._CORE_EXPECTED:
            assert rel in mod.EXPECTED_FAIL_RELS, f"missing EXPECTED_FAIL: {rel}"
            assert mod.is_expected_fail(rel, "RuntimeError: demo"), rel
            assert not mod.is_expected_fail(rel, ""), rel

    def test_runtime_error_builtin_still_raises(self) -> None:
        src = """//@version=5
indicator("t")
runtime.error("must not soft-suppress")
plot(close)
"""
        r = Runtime().run(src, _bars(3), mode="interpret")
        err = r.get("error")
        assert err, "runtime.error must surface as Runtime error"
        assert "must not soft-suppress" in str(err)

    @pytest.mark.parametrize(
        "rel",
        [
            "set02/libraries/019_lib_functionnnetwork.pine",
            "set04/indicators/0703_ind_higher_timeframe_security_demo.pine",
        ],
    )
    def test_intentional_demos_still_surface_runtime_error(self, rel: str) -> None:
        path = DATA / rel
        if not path.is_file():
            pytest.skip(f"missing {rel}")
        src = sanitize_corpus_source(path.read_text(encoding="utf-8", errors="replace"))
        r = Runtime().run(src, _bars(30), mode="interpret")
        assert r.get("error"), f"{rel}: expected runtime error, got clean run"
        err = str(r["error"])
        assert (
            "RuntimeError" in err
            or "runtime" in err.lower()
            or "timeframe" in err.lower()
            or "error" in err.lower()
        )
