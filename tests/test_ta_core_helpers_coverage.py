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

"""Unit coverage for TechnicalHelpers pure helpers in technical_submodules.core."""

from __future__ import annotations

import math

from collections import deque
from types import SimpleNamespace

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers


@pytest.fixture()
def h() -> NodeLiteralEvaluator:
    """Full evaluator already mixes TechnicalHelpers via TechnicalAnalysisMixin."""
    ev = NodeLiteralEvaluator()
    n = 40
    high = [float(100 + i) for i in range(n)]
    low = [float(90 + i) for i in range(n)]
    close = [float(95 + i) for i in range(n)]
    ev.current_series = {
        "open": [float(94 + i) for i in range(n)],
        "high": high,
        "low": low,
        "close": close,
        "hl2": [(high[i] + low[i]) / 2.0 for i in range(n)],
        "hlc3": close,
        "volume": [1000.0 + i for i in range(n)],
    }
    return ev


def _enable_inc(ev: NodeLiteralEvaluator) -> None:
    ev._pine_bar_mode = True  # type: ignore[attr-defined]
    ev._pine_ta_incremental = True  # type: ignore[attr-defined]
    if hasattr(ev, "_pine_ta_inc_cached"):
        delattr(ev, "_pine_ta_inc_cached")
    ev._ta_call_i = 0  # type: ignore[attr-defined]
    ev._ta_inc_state = {}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Flags / slots / series_last / finite
# ---------------------------------------------------------------------------


class TestBarModeIncrementalSlots:
    def test_bar_mode_and_incremental_flags(self, h: NodeLiteralEvaluator, monkeypatch: pytest.MonkeyPatch) -> None:
        assert h._bar_mode() is False
        h._pine_bar_mode = True  # type: ignore[attr-defined]
        assert h._bar_mode() is True
        if hasattr(h, "_pine_ta_inc_cached"):
            delattr(h, "_pine_ta_inc_cached")
        monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
        assert h._use_incremental_ta() is False
        delattr(h, "_pine_ta_inc_cached")
        monkeypatch.setenv("PYNE_TA_INCREMENTAL", "1")
        h._pine_ta_incremental = True  # type: ignore[attr-defined]
        assert h._use_incremental_ta() is True
        assert h._use_incremental_ta() is True

    def test_ta_next_slot_and_key1(self, h: NodeLiteralEvaluator) -> None:
        assert h._ta_next_slot() == 0
        assert h._ta_next_slot() == 1
        h._ta_call_i = "2"  # type: ignore[attr-defined]
        assert h._ta_next_slot() == 2
        bucket = h._ta_state_bucket()
        assert isinstance(bucket, dict)
        if hasattr(h, "_ta_inc_state"):
            delattr(h, "_ta_inc_state")
        if hasattr(h, "_ta_call_i"):
            delattr(h, "_ta_call_i")
        if hasattr(h, "_ta_key_cache"):
            delattr(h, "_ta_key_cache")
        _b, key = h._ta_key1("sma", 14)
        assert key == ("sma", 0, 14)
        _b2, key2 = h._ta_key1("sma", 14)
        assert key2 == ("sma", 1, 14)
        h._ta_call_i = 0  # type: ignore[attr-defined]
        _b3, key3 = h._ta_key1("sma", 14)
        assert key3 == ("sma", 0, 14)
        h._ta_call_i = 0  # type: ignore[attr-defined]
        _b4, key4 = h._ta_key1("ema", 14)
        assert key4[0] == "ema"

    def test_series_last_and_finite(self, h: NodeLiteralEvaluator) -> None:
        assert TechnicalHelpers._series_last([1, 2, 3]) == 3
        assert TechnicalHelpers._series_last([]) is None
        assert TechnicalHelpers._series_last(None) is None
        assert TechnicalHelpers._series_last(7.5) == 7.5
        assert TechnicalHelpers._series_last(SimpleNamespace(current=9)) == 9
        hist = SimpleNamespace(history=deque([5, 4, 3]))
        assert TechnicalHelpers._series_last(hist) == 5
        empty_hist = SimpleNamespace(history=deque())
        assert TechnicalHelpers._series_last(empty_hist) is None
        assert TechnicalHelpers._series_last((1, 2, 8)) == 8
        assert TechnicalHelpers._finite_or_none(1.5) == 1.5
        assert TechnicalHelpers._finite_or_none(float("nan")) is None
        assert TechnicalHelpers._finite_or_none(None) is None
        assert TechnicalHelpers._finite_or_none(True) == 1.0
        assert TechnicalHelpers._finite_or_none("3.2") == pytest.approx(3.2)
        assert TechnicalHelpers._finite_or_none("x") is None


class TestAsSeriesExpectHelpers:
    def test_as_series_list_and_history(self, h: NodeLiteralEvaluator) -> None:
        assert h._as_series([1.0, 2.0]) == [1.0, 2.0]
        hist = SimpleNamespace(history=deque([3.0, 2.0, 1.0]), current=3.0)
        out = h._as_series(hist)
        assert out == [1.0, 2.0, 3.0]
        out2 = h._as_series(hist)
        assert out2 is out or out2 == out
        empty = SimpleNamespace(history=deque(), current=9.0)
        assert h._as_series(empty) == [9.0]
        assert h._as_series("close")[-1] == pytest.approx(h.current_series["close"][-1])
        assert h._as_series("1.25") == [1.25]
        assert h._as_series("#bad") == []
        assert h._as_series(42) == [42]

    def test_context_series_and_period_like(self, h: NodeLiteralEvaluator) -> None:
        assert h._context_series("high")[-1] == pytest.approx(139.0)
        assert h._context_series("missing") == []
        assert h._context_source("close") is h.current_series["close"]
        assert h._context_source("nope") == []
        assert h._is_period_like(14) is True
        assert h._is_period_like(14.0) is True
        assert h._is_period_like(True) is False
        assert h._is_period_like([10]) is True
        assert h._is_period_like(SimpleNamespace(current=5)) is True
        assert h._is_period_like("x") is False

    def test_expect_series_period_only_and_last_sample(self, h: NodeLiteralEvaluator) -> None:
        series, period = h._expect_series([h.current_series["close"], 5], 2)
        assert period == 5
        assert series[-1] == h.current_series["close"][-1]
        series2, p2 = h._expect_series([14], 2, allow_period_only=True, default_source="high")
        assert p2 == 14
        assert series2[-1] == h.current_series["high"][-1]
        _enable_inc(h)
        raw, p3 = h._expect_series(
            [h.current_series["close"], 7],
            2,
            last_sample_ok=True,
        )
        assert p3 == 7
        assert raw is h.current_series["close"]
        raw2, p4 = h._expect_series([10], 2, allow_period_only=True, default_source="low", last_sample_ok=True)
        assert p4 == 10
        assert raw2 is h.current_series["low"]
        a, b = h._expect_two_series([[1, 2], [3, 4]])
        assert a[-1] == 2 and b[-1] == 4
        a2, b2 = h._expect_two_series([[1], [2]], last_sample_ok=True)
        assert a2 == [1] and b2 == [2]
        assert h._expect_period(None, "period") == 0
        assert h._expect_int(3.0, "i") == 3
        assert h._expect_number(2.5, "n") == 2.5

    def test_expect_series_arity_error(self, h: NodeLiteralEvaluator) -> None:
        with pytest.raises(ValueError):
            h._expect_series([], 2)
        with pytest.raises(ValueError):
            h._expect_series([14], 2, allow_period_only=True, default_source=None)


class TestCrossCmpRisingFalling:
    def test_cmp_helpers(self, h: NodeLiteralEvaluator) -> None:
        assert TechnicalHelpers._cmp_lt(1, 2) is True
        assert TechnicalHelpers._cmp_lt(None, 1) is None
        assert TechnicalHelpers._cmp_lt("a", 1) is None
        assert TechnicalHelpers._cmp_gt(3, 1) is True
        assert TechnicalHelpers._cmp_le(1, 1) is True
        assert TechnicalHelpers._cmp_ge(2, 1) is True
        assert TechnicalHelpers._cmp_ge("x", 1) is None

    def test_crossover_under_cross(self, h: NodeLiteralEvaluator) -> None:
        assert h._crossover([1.0, 3.0], [2.0, 2.0]) is True
        assert h._crossover([1.0], [1.0]) is False
        assert h._crossunder([3.0, 1.0], [2.0, 2.0]) is True
        assert h._cross([1.0, 3.0], [2.0, 2.0]) is True
        assert h._cross([1.0, 1.5], [2.0, 2.5]) is False

    def test_cross_stateful(self, h: NodeLiteralEvaluator) -> None:
        # Same call-site across bars: reset _cross_call_i each "bar".
        h._cross_call_i = 0  # type: ignore[attr-defined]
        h._cross_state = {}  # type: ignore[attr-defined]
        assert h._cross_stateful(1.0, 2.0, under=False) is False
        h._cross_call_i = 0  # type: ignore[attr-defined]
        assert h._cross_stateful(3.0, 2.0, under=False) is True
        h._cross_call_i = 0  # type: ignore[attr-defined]
        h._cross_state = {}  # type: ignore[attr-defined]
        assert h._cross_stateful(3.0, 2.0, under=True) is False
        h._cross_call_i = 0  # type: ignore[attr-defined]
        assert h._cross_stateful(1.0, 2.0, under=True) is True
        h._cross_call_i = 0  # type: ignore[attr-defined]
        h._cross_state = {}  # type: ignore[attr-defined]
        h._cross_stateful(1.0, 2.0, under=False, either=True)
        h._cross_call_i = 0  # type: ignore[attr-defined]
        assert h._cross_stateful(3.0, 2.0, under=False, either=True) is True
        h._cross_call_i = 0  # type: ignore[attr-defined]
        h._cross_state = {0: ("a", "b")}  # type: ignore[attr-defined]
        assert h._cross_stateful("x", "y", under=False) is False

    def test_rising_falling_highestbars(self, h: NodeLiteralEvaluator) -> None:
        up = [1.0, 2.0, 3.0, 4.0, 5.0]
        down = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert h._rising(up, 3) is True
        assert h._falling(down, 3) is True
        assert h._rising(down, 3) is False
        assert h._falling([1.0, None, 0.0], 1) is False
        assert h._rising([1.0, "x", 3.0], 1) is False
        assert h._highestbars(up, 3) == 0
        assert h._lowestbars(up, 3) == -2
        assert h._highestbars(up, 99) == -1
        assert h._highestbars([None, None], 2) == -1
        assert h._swma([1.0, 2.0, 3.0, 4.0]) == pytest.approx((1 + 4 + 6 + 4) / 6.0)
        assert h._swma([1.0, 2.0]) is None
        assert h._change(up, 2) == pytest.approx(2.0)
        assert h._change([1.0], 1) is None
        assert h._mom(up, 2) == pytest.approx(2.0)
        assert h._mom([1.0, None, 3.0], 1) is None


class TestWindowTrAndMaHelpers:
    def test_tr_and_minmax_format(self, h: NodeLiteralEvaluator) -> None:
        highs = [10.0, 12.0, 11.0]
        lows = [9.0, 10.0, 9.5]
        closes = [9.5, 11.0, 10.0]
        tr = h._tr(highs, lows, closes)
        assert tr[0] is None
        assert tr[1] == pytest.approx(2.5)
        assert h._tr([], [], []) == []
        mins = h._min_series([3.0, 1.0, None, 2.0], 2)
        assert mins[-1] == 2.0
        maxs = h._max_series([3.0, 1.0, None, 2.0], 2)
        assert maxs[1] == 3.0
        fmt = h._format_series([1.0, None])
        assert fmt[0] == 1.0 and math.isnan(fmt[1])

    def test_sma_ema_rma_wma_stdev(self, h: NodeLiteralEvaluator) -> None:
        series = [float(i) for i in range(1, 21)]
        sma = h._sma(series, 5)
        assert sma[-1] == pytest.approx(18.0)
        ema = h._ema(series, 5)
        assert ema[-1] is not None
        rma = h._rma(series, 5)
        assert rma[-1] is not None
        wma = h._wma(series, 5)
        assert wma == pytest.approx(sum(i * w for i, w in zip(series[-5:], range(1, 6), strict=True)) / 15.0)
        assert h._highest(series, 5) == 20.0
        assert h._lowest(series, 5) == 16.0
        assert h._stdev(series, 5) is not None

    def test_base_error_not_implemented_on_bare_helpers(self) -> None:
        bare = TechnicalHelpers()
        with pytest.raises(NotImplementedError):
            bare._error("x")

    def test_cap_series_list(self, h: NodeLiteralEvaluator) -> None:
        h._SERIES_MAX = 5  # type: ignore[attr-defined]
        long = list(range(20))
        capped = h._cap_series_list(long)
        assert len(capped) == 5
        assert capped[-1] == 19

    def test_finalize_and_as_series_or_raw(self, h: NodeLiteralEvaluator) -> None:
        h._pine_bar_mode = True  # type: ignore[attr-defined]
        assert h._finalize_series([1.0, 2.0, 3.0]) == 3.0
        h._pine_bar_mode = False  # type: ignore[attr-defined]
        assert h._finalize_series([1.0, 2.0]) == [1.0, 2.0]
        _enable_inc(h)
        raw = h._as_series_or_raw([1, 2, 3], last_sample_ok=True)
        assert raw == [1, 2, 3]
