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

"""Exhaustive unit coverage for ``technical_submodules.common`` pure helpers + edges."""

from __future__ import annotations

import math
import statistics

from types import SimpleNamespace
from typing import Any

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.technical_submodules.common import CommonIndicators as _Common


def _trend(n: int = 30) -> list[float]:
    return [float(i) for i in range(1, n + 1)]


def _ohlcv(n: int = 40) -> dict[str, list[float]]:
    high = [float(100 + i) for i in range(n)]
    low = [float(90 + i) for i in range(n)]
    close = [float(95 + i) for i in range(n)]
    open_ = [float(94 + i) for i in range(n)]
    vol = [1000.0 + i for i in range(n)]
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "hl2": [(high[i] + low[i]) / 2.0 for i in range(n)],
        "hlc3": close,
        "volume": vol,
    }


@pytest.fixture()
def ev() -> NodeLiteralEvaluator:
    evaluator = NodeLiteralEvaluator()
    evaluator.current_series = _ohlcv(60)
    return evaluator


def _enable_incremental(ev: NodeLiteralEvaluator) -> None:
    ev._pine_bar_mode = True  # type: ignore[attr-defined]
    ev._pine_ta_incremental = True  # type: ignore[attr-defined]
    if hasattr(ev, "_pine_ta_inc_cached"):
        delattr(ev, "_pine_ta_inc_cached")
    ev._ta_call_i = 0  # type: ignore[attr-defined]
    ev._ta_inc_state = {}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestPureHelpers:
    def test_range_change_momentum(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend(10)
        assert _Common._range(ev, series, 5) == pytest.approx(4.0)
        assert _Common._range(ev, [None, None], 2) is None
        assert _Common._change(ev, series, 1) == pytest.approx(1.0)
        assert _Common._change(ev, series, 3) == pytest.approx(3.0)
        assert _Common._change(ev, [1.0], 1) is None
        assert _Common._change(ev, [1.0, None], 1) is None
        assert _Common._change(ev, [None, 2.0], 1) is None
        assert _Common._change(ev, ["a", "b"], 1) is None
        assert _Common._momentum(ev, series, 2) == pytest.approx(2.0)
        assert _Common._momentum(ev, [1.0, 2.0], 5) is None
        assert _Common._momentum(ev, [1.0, None, 3.0], 1) is None
        assert _Common._momentum(ev, ["x", "y"], 1) is None

    def test_cumsum_dev_median_mode(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._cumsum(ev, [1, None, 2.5, "x", 3]) == pytest.approx(6.5)
        assert _Common._cumsum(ev, []) == 0.0

        assert _Common._dev(ev, [1.0, 2.0, 3.0], 3) == pytest.approx(2.0 / 3.0)
        assert _Common._dev(ev, [1.0, 2.0], 3) is None
        assert _Common._dev(ev, [1.0, 2.0, 3.0], 0) is None
        assert _Common._dev(ev, [1.0, None, 3.0], 3) is None
        assert _Common._dev(ev, [1.0, "x", 3.0], 3) is None
        assert _Common._dev(ev, [1.0, math.nan, 3.0], 3) is None

        assert _Common._median(ev, [3.0, 1.0, 2.0], 3) == pytest.approx(2.0)
        assert _Common._median(ev, [1.0], 3) is None
        assert _Common._median(ev, [None, None, None], 3) is None

        assert _Common._mode(ev, [1.0, 1.0, 2.0], 3) == pytest.approx(1.0)
        assert _Common._mode(ev, [1.0], 3) is None
        assert _Common._mode(ev, [None, None], 2) is None

    def test_mode_statistics_error_fallback(self, ev: NodeLiteralEvaluator, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(_values: Any) -> float:
            raise statistics.StatisticsError("no unique mode")

        monkeypatch.setattr(statistics, "mode", _boom)
        assert _Common._mode(ev, [1.0, 2.0, 3.0], 3) == pytest.approx(1.0)

    def test_percentrank_variance_vwap(self, ev: NodeLiteralEvaluator) -> None:
        series = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _Common._percentrank(ev, series, 5) == pytest.approx(80.0)
        assert _Common._percentrank(ev, series, 10) is None
        assert _Common._percentrank(ev, [7.0], 1) == pytest.approx(50.0)
        assert _Common._percentrank(ev, [1.0, None], 2) == pytest.approx(50.0)
        assert _Common._percentrank(ev, [1.0, 2.0, None], 3) is None

        assert _Common._variance(ev, series, 5) == pytest.approx(statistics.pvariance(series))
        assert _Common._variance(ev, series, 1) is None
        assert _Common._variance(ev, [1.0, 2.0], 5) is None
        assert _Common._variance(ev, [1.0, None, 3.0], 3) is None
        assert _Common._variance(ev, [1.0, "x", 3.0], 3) is None
        assert _Common._variance(ev, [1.0, math.nan, 3.0], 3) is None

        assert _Common._vwap(ev, [10.0, 20.0, 30.0]) == pytest.approx(20.0)
        assert _Common._vwap(ev, []) == 0

    def test_adx_helper_edges(self, ev: NodeLiteralEvaluator) -> None:
        high = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        low = [9.0, 9.5, 10.0, 10.5, 11.0, 11.5]
        close = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5]
        assert _Common._adx(ev, high, low, close, 0) == 0.0
        assert _Common._adx(ev, high, low, close, 20) == 0.0
        assert isinstance(_Common._adx(ev, high * 5, low * 5, close * 5, 3), float)


# ---------------------------------------------------------------------------
# Builtin edges (non-incremental)
# ---------------------------------------------------------------------------


class TestBuiltinEdges:
    def test_range_unary_high_low(self, ev: NodeLiteralEvaluator) -> None:
        # Fixture highs 100..159 / lows 90..149 → last-5 high 159, low 145 → 14
        out = _Common._builtin_ta_range(ev, [5])
        assert out == pytest.approx(14.0)

    def test_range_unary_empty_context(self, ev: NodeLiteralEvaluator) -> None:
        ev.current_series = {"high": [], "low": [], "close": []}
        assert _Common._builtin_ta_range(ev, [3]) is None

    def test_max_min_period_and_empty(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_max(ev, [series, 5]) == pytest.approx(30.0)
        assert _Common._builtin_ta_min(ev, [series, 5]) == pytest.approx(26.0)

    def test_change_arg_errors_and_float_period(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_change(ev, [])
        with pytest.raises(Exception):
            _Common._builtin_ta_change(ev, [_trend(), 1, 2])
        assert _Common._builtin_ta_change(ev, [_trend(), 2.0]) == pytest.approx(2.0)

    def test_expected_value_errors(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_expected_value(ev, [[1.0]])
        with pytest.raises(Exception):
            _Common._builtin_ta_expected_value(ev, [[1.0, 2.0], [0.5]])
        assert _Common._builtin_ta_expected_value(ev, [1.0, 1.0]) == pytest.approx(1.0)
        assert _Common._builtin_ta_expected_value(ev, [["x"], ["y"]]) == pytest.approx(0.0)

    def test_skewness_kurtosis_errors_and_zero_std(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_skewness(ev, [[1.0]])
        with pytest.raises(Exception):
            _Common._builtin_ta_kurtosis(ev, [[1.0]])
        flat = [5.0] * 10
        assert _Common._builtin_ta_skewness(ev, [flat, 5]) == pytest.approx(0.0)
        assert _Common._builtin_ta_kurtosis(ev, [flat, 5]) == pytest.approx(0.0)
        # Valid count shortfall inside window (None padding)
        assert _Common._builtin_ta_skewness(ev, [[1.0, None, 2.0, None, 3.0], 5]) is None
        assert _Common._builtin_ta_kurtosis(ev, [[1.0, None, 2.0, None, 3.0], 5]) is None

    def test_parkinson_garman_edges(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_parkinson(ev, [[1.0]])
        with pytest.raises(Exception):
            _Common._builtin_ta_garman_klass(ev, [[1.0], [1.0], [1.0]])
        assert _Common._builtin_ta_parkinson(ev, [[], [1.0]]) is None
        assert _Common._builtin_ta_parkinson(ev, [[10.0], [None]]) is None
        assert _Common._builtin_ta_parkinson(ev, [[5.0], [5.0]]) is None
        assert _Common._builtin_ta_parkinson(ev, [10.0, 5.0]) == pytest.approx(
            math.sqrt(math.log(2.0) ** 2 / (4 * math.log(2)))
        )

        assert _Common._builtin_ta_garman_klass(ev, [[], [1], [1], [1]]) is None
        assert _Common._builtin_ta_garman_klass(ev, [[10], [9], [None], [9]]) is None
        assert _Common._builtin_ta_garman_klass(ev, [[5], [5], [5], [5]]) is None
        assert _Common._builtin_ta_garman_klass(ev, [110.0, 90.0, 100.0, 95.0]) is not None

    def test_barssince_list_and_scalar(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_barssince(ev, [])
        assert _Common._builtin_ta_barssince(ev, [[False, False, True, False]]) == 1
        assert _Common._builtin_ta_barssince(ev, [[False, False, False]]) == 2
        assert _Common._builtin_ta_barssince(ev, [True]) == 0
        assert _Common._builtin_ta_barssince(ev, [False]) == 1
        # Non-bool scalars: anything other than False/None counts as true.
        assert _Common._builtin_ta_barssince(ev, [0]) == 0
        assert _Common._builtin_ta_barssince(ev, [2]) == 0
        assert _Common._builtin_ta_barssince(ev, [None]) == 1

    def test_pivothigh_pivotlow_edges(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_pivothigh(ev, [[1.0], 1])
        with pytest.raises(Exception):
            _Common._builtin_ta_pivotlow(ev, [[1.0], 1])
        assert _Common._builtin_ta_pivothigh(ev, [[1.0, 2.0, None], 1, 0]) is None
        assert _Common._builtin_ta_pivotlow(ev, [[3.0, 2.0, None], 1, 0]) is None
        # Nested series-like wrappers
        nested = SimpleNamespace(current=None, history=[1])
        assert _Common._builtin_ta_pivothigh(ev, [[1.0, 2.0, nested], 1, 0]) is None
        wrapped = SimpleNamespace(current=50.0, history=[50.0])
        left = SimpleNamespace(current=40.0, history=[40.0])
        assert _Common._builtin_ta_pivothigh(ev, [[left, left, wrapped], 2, 0]) == pytest.approx(50.0)
        # Non-float current
        bad = SimpleNamespace(current="x", history=["x"])
        assert _Common._builtin_ta_pivothigh(ev, [[1.0, 2.0, bad], 1, 0]) is None
        # Comparison TypeError path (object as immediate left neighbor)
        assert _Common._builtin_ta_pivothigh(ev, [[10.0, object(), 3.0], 1, 0]) is None
        assert _Common._builtin_ta_pivotlow(ev, [[0.0, object(), 1.0], 1, 0]) is None
        # Not a pivot (left higher/lower)
        assert _Common._builtin_ta_pivothigh(ev, [[10.0, 9.0], 1, 0]) is None
        assert _Common._builtin_ta_pivotlow(ev, [[1.0, 2.0], 1, 0]) is None

    def test_pivot_point_levels_forms(self, ev: NodeLiteralEvaluator) -> None:
        traditional = _Common._builtin_ta_pivot_point_levels(ev, [110.0, 90.0, 100.0, True])
        assert traditional["pivot"] == pytest.approx(100.0)
        fib = _Common._builtin_ta_pivot_point_levels(ev, [110.0, 90.0, 100.0, False])
        assert fib["r1"] == pytest.approx(100.0 + 0.382 * 20.0)
        assert fib["s2"] == pytest.approx(100.0 - 0.618 * 20.0)
        with pytest.raises(Exception):
            _Common._builtin_ta_pivot_point_levels(ev, [110.0, 90.0])
        # String type → context OHLC form
        levels = _Common._builtin_ta_pivot_point_levels(ev, ["Traditional"])
        assert isinstance(levels, list) and len(levels) == 7
        ev.current_series = {"high": [], "low": [], "close": []}
        assert _Common._builtin_ta_pivot_point_levels(ev, ["Traditional"]) == []
        ev.current_series = {"high": [None], "low": [1.0], "close": [1.0]}
        assert _Common._builtin_ta_pivot_point_levels(ev, ["Traditional"]) == []

    def test_cog_edges(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_cog(ev, [_trend(), 0])
        assert math.isnan(_Common._builtin_ta_cog(ev, [[1.0, 2.0], 5]))
        assert math.isnan(_Common._builtin_ta_cog(ev, [[0.0, 0.0, 0.0], 3]))

    def test_dmi_forms(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(Exception):
            _Common._builtin_ta_dmi(ev, [14])
        assert _Common._builtin_ta_dmi(ev, [0, 14]) == (None, None, None)
        high, low, close = ev.current_series["high"], ev.current_series["low"], ev.current_series["close"]
        plus, minus, _adx = _Common._builtin_ta_dmi(ev, [high, low, close, 10])
        assert plus is not None and minus is not None
        assert _Common._builtin_ta_dmi(ev, [high, low, close, 0]) == (None, None, None)
        assert _Common._builtin_ta_dmi(ev, [None, low, close, 5]) == (None, None, None)
        # Length mismatch
        assert _Common._builtin_ta_dmi(ev, [high[:5], low, close, 3]) == (None, None, None)

    def test_supertrend_zigzag_adx_edges(self, ev: NodeLiteralEvaluator) -> None:
        high, low = ev.current_series["high"], ev.current_series["low"]
        with pytest.raises(Exception):
            _Common._builtin_ta_supertrend(ev, [high, low])
        with pytest.raises(Exception):
            _Common._builtin_ta_supertrend(ev, [high, low, 0])
        # Exact arity is 3 (multiplier defaults to 1.0 inside the handler).
        lower, upper, direction = _Common._builtin_ta_supertrend(ev, [high, low, 5])
        assert lower < upper
        assert direction in (-1, 0, 1)
        with pytest.raises(Exception):
            _Common._builtin_ta_supertrend(ev, [high, low, 5, 2.0])
        # Warmup NaN ATR path still returns bands
        short_h, short_l = [1.0, 2.0], [0.5, 1.0]
        _Common._builtin_ta_supertrend(ev, [short_h, short_l, 5])

        with pytest.raises(Exception):
            _Common._builtin_ta_zigzag(ev, [[1.0]])
        assert _Common._builtin_ta_zigzag(ev, [[1.0], 5.0])[2] == 0
        assert _Common._builtin_ta_zigzag(ev, [[None, None], 5.0])[2] == 0
        hi, lo, _d = _Common._builtin_ta_zigzag(ev, [[10.0, 11.0], 0.01])
        assert hi == pytest.approx(11.0) and lo == pytest.approx(10.0)

        assert _Common._builtin_ta_adx(ev, [14, 14]) == pytest.approx(_Common._builtin_ta_adx(ev, [14]), abs=1e-6)


# ---------------------------------------------------------------------------
# Incremental / bar-mode branches
# ---------------------------------------------------------------------------


class TestIncrementalBranches:
    def test_cross_rising_falling_inc(self, ev: NodeLiteralEvaluator) -> None:
        _enable_incremental(ev)
        # last-sample ok paths
        assert isinstance(_Common._builtin_ta_crossover(ev, [[1.0, 3.0], [2.0, 2.0]]), bool)
        assert isinstance(_Common._builtin_ta_crossunder(ev, [[3.0, 1.0], [2.0, 2.0]]), bool)
        assert isinstance(_Common._builtin_ta_cross(ev, [[1.0, 2.0], [2.0, 1.0]]), bool)
        assert isinstance(_Common._builtin_ta_rising(ev, [_trend(), 3]), bool)
        assert isinstance(_Common._builtin_ta_falling(ev, [list(reversed(_trend())), 3]), bool)
        assert isinstance(_Common._builtin_ta_highestbars(ev, [_trend(), 5]), int)
        assert isinstance(_Common._builtin_ta_lowestbars(ev, [_trend(), 5]), int)

    def test_bar_mode_short_series_fallback(self, ev: NodeLiteralEvaluator) -> None:
        ev._pine_bar_mode = True  # type: ignore[attr-defined]
        ev._pine_ta_incremental = False  # type: ignore[attr-defined]
        if hasattr(ev, "_pine_ta_inc_cached"):
            delattr(ev, "_pine_ta_inc_cached")
        # Force non-incremental bar mode with short series → *_inc_update path
        short = [1.0, 2.0]
        assert isinstance(_Common._builtin_ta_rising(ev, [short, 5]), bool)
        assert isinstance(_Common._builtin_ta_falling(ev, [short, 5]), bool)
        assert _Common._builtin_ta_highestbars(ev, [short, 5]) is None
        assert _Common._builtin_ta_lowestbars(ev, [short, 5]) is None

    def test_stats_and_utils_inc(self, ev: NodeLiteralEvaluator) -> None:
        _enable_incremental(ev)
        series = _trend(40)
        high = ev.current_series["high"]
        low = ev.current_series["low"]
        close = ev.current_series["close"]
        last_range = last_bin = last_max = last_min = None
        last_chg = last_mom = last_cum = None
        last_dev = last_med = last_mode = last_pr = last_var = None
        last_skew = last_kurt = last_cog = last_adx = last_adx2 = last_adx3 = None
        last_bs = None
        for i in range(1, len(series)):
            ev._ta_call_i = 0  # type: ignore[attr-defined]
            prefix = series[: i + 1]
            last_range = _Common._builtin_ta_range(ev, [5])
            last_bin = _Common._builtin_ta_range(ev, [prefix, 5])
            last_max = _Common._builtin_ta_max(ev, [prefix, 5])
            last_min = _Common._builtin_ta_min(ev, [prefix, 5])
            last_chg = _Common._builtin_ta_change(ev, [prefix, 1])
            last_mom = _Common._builtin_ta_mom(ev, [prefix, 3])
            last_cum = _Common._builtin_ta_cum(ev, [prefix[-1]])
            last_dev = _Common._builtin_ta_dev(ev, [prefix, 5])
            last_med = _Common._builtin_ta_median(ev, [prefix, 5])
            last_mode = _Common._builtin_ta_mode(ev, [prefix, 5])
            last_pr = _Common._builtin_ta_percentrank(ev, [prefix, 5])
            last_var = _Common._builtin_ta_variance(ev, [prefix, 5])
            last_skew = _Common._builtin_ta_skewness(ev, [prefix, 10])
            last_kurt = _Common._builtin_ta_kurtosis(ev, [prefix, 10])
            last_bs = _Common._builtin_ta_barssince(ev, [i % 4 == 0])
            last_cog = _Common._builtin_ta_cog(ev, [prefix, 5])
            last_adx = _Common._builtin_ta_adx(ev, [14])
            last_adx2 = _Common._builtin_ta_adx(ev, [high[: i + 1], low[: i + 1], close[: i + 1], 10])
            last_adx3 = _Common._builtin_ta_adx(ev, [10, 14])
        assert last_range is not None
        assert last_bin is not None
        assert last_max is not None and last_min is not None
        assert last_chg is not None and last_mom is not None
        assert last_cum is not None
        assert last_dev is not None and last_med is not None
        assert last_mode is not None and last_pr is not None
        assert last_var is not None
        assert last_skew is not None and last_kurt is not None
        assert last_bs is not None
        assert last_cog is not None and not (isinstance(last_cog, float) and math.isnan(last_cog))
        assert last_adx is not None and last_adx2 is not None and last_adx3 is not None
