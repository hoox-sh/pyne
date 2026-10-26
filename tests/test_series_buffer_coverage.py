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

"""Thorough unit coverage for ``pynescript.ast.evaluator.series_buffer``."""

from __future__ import annotations

import math

import pytest

from pynescript.ast.evaluator.series_buffer import ChronologicalSeriesBuffer
from pynescript.ast.evaluator.series_buffer import ChronoTailView
from pynescript.ast.evaluator.series_buffer import NewestFirstHistoryView
from pynescript.ast.evaluator.series_buffer import RingPineSeries
from pynescript.ast.evaluator.series_buffer import evaluator_history_length
from pynescript.ast.evaluator.series_buffer import make_series
from pynescript.runtime.series import DEFAULT_PINESERIES_HISTORY
from pynescript.runtime.series import PineSeries


# ---------------------------------------------------------------------------
# ChronologicalSeriesBuffer
# ---------------------------------------------------------------------------


class TestChronologicalSeriesBuffer:
    def test_maxlen_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="maxlen"):
            ChronologicalSeriesBuffer(0)
        with pytest.raises(ValueError):
            ChronologicalSeriesBuffer(-3)

    def test_unbounded_append_lookback_iter_repr(self) -> None:
        buf = ChronologicalSeriesBuffer()
        assert len(buf) == 0
        assert buf.current is None
        assert buf.lookback(0) is None
        assert "ChronologicalSeriesBuffer" in repr(buf)
        for v in (10, 20, 30):
            buf.append(v)
        assert len(buf) == 3
        assert buf.current == 30
        assert buf.lookback(0) == 30
        assert buf.lookback(1) == 20
        assert buf.lookback(2) == 10
        assert buf.lookback(3) is None
        assert buf.lookback(-1) is None
        assert buf[0] == 30
        assert buf[1] == 20
        assert buf[99] is None
        assert list(buf) == [10, 20, 30]
        assert buf.chronological() == [10, 20, 30]
        assert "len=3" in repr(buf)

    def test_update_alias_and_clear_unbounded(self) -> None:
        buf = ChronologicalSeriesBuffer()
        buf.update(1)
        buf.update(2)
        assert buf.current == 2
        buf.clear()
        assert len(buf) == 0
        assert buf.chronological() == []
        assert buf.current is None

    def test_ring_overwrite_oldest_and_clear_keeps_capacity(self) -> None:
        buf = ChronologicalSeriesBuffer(maxlen=3)
        for v in (1, 2, 3, 4, 5):
            buf.append(v)
        assert len(buf) == 3
        assert buf.chronological() == [3, 4, 5]
        assert buf.lookback(0) == 5
        assert buf.lookback(2) == 3
        assert list(buf) == [3, 4, 5]
        buf.clear()
        assert len(buf) == 0
        assert buf.maxlen == 3
        assert buf.chronological() == []
        buf.append(9)
        assert buf.chronological() == [9]
        assert buf[0] == 9

    def test_ring_partial_fill_chronological(self) -> None:
        buf = ChronologicalSeriesBuffer(maxlen=5)
        buf.append(1)
        buf.append(2)
        assert len(buf) == 2
        assert buf.chronological() == [1, 2]
        assert list(buf) == [1, 2]
        assert buf.lookback(0) == 2
        assert buf.lookback(1) == 1

    def test_getitem_na_offsets(self) -> None:
        buf = ChronologicalSeriesBuffer()
        buf.append(1.0)
        assert buf[float("nan")] is None
        assert buf[float("inf")] is None
        assert buf[float("-inf")] is None
        assert buf["x"] is None
        assert buf[None] is None
        assert buf[-1] is None
        assert buf[1.9] is None  # only one sample; offset 1 OOB
        buf.append(2.0)
        buf.append(3.0)
        assert buf[1.9] == 2.0

    def test_empty_chronological_and_iter(self) -> None:
        buf = ChronologicalSeriesBuffer(maxlen=4)
        assert buf.chronological() == []
        assert list(buf) == []
        assert buf[0] is None

    def test_many_wrap_cycles(self) -> None:
        buf = ChronologicalSeriesBuffer(maxlen=4)
        for i in range(20):
            buf.append(i)
        assert buf.chronological() == [16, 17, 18, 19]
        assert [buf.lookback(i) for i in range(4)] == [19, 18, 17, 16]
        assert buf.lookback(4) is None


# ---------------------------------------------------------------------------
# ChronoTailView
# ---------------------------------------------------------------------------


class TestChronoTailView:
    def test_keep_must_be_positive(self) -> None:
        buf = ChronologicalSeriesBuffer()
        with pytest.raises(ValueError, match="keep"):
            ChronoTailView(buf, keep=0)
        with pytest.raises(ValueError):
            ChronoTailView(buf, keep=-1)

    def test_window_slice_and_errors(self) -> None:
        buf = ChronologicalSeriesBuffer(maxlen=8)
        for i in range(10):
            buf.append(float(i))
        view = ChronoTailView(buf, keep=4)
        assert len(view) == 4
        assert list(view) == [6.0, 7.0, 8.0, 9.0]
        assert view[0] == 6.0
        assert view[-1] == 9.0
        assert view[1:3] == [7.0, 8.0]
        assert view[::2] == [6.0, 8.0]
        with pytest.raises(IndexError):
            _ = view[4]
        with pytest.raises(IndexError):
            _ = view[-5]
        with pytest.raises(TypeError):
            _ = view["x"]  # type: ignore[index]
        assert "ChronoTailView" in repr(view)

    def test_grows_until_keep(self) -> None:
        buf = ChronologicalSeriesBuffer()
        view = ChronoTailView(buf, keep=3)
        assert len(view) == 0
        buf.append(1)
        assert list(view) == [1]
        buf.append(2)
        buf.append(3)
        buf.append(4)
        assert list(view) == [2, 3, 4]

    def test_bool_index_via_operator_index(self) -> None:
        buf = ChronologicalSeriesBuffer()
        for v in (10, 20, 30):
            buf.append(v)
        view = ChronoTailView(buf, keep=3)
        assert view[False] == 10  # type: ignore[index]
        assert view[True] == 20  # type: ignore[index]


# ---------------------------------------------------------------------------
# NewestFirstHistoryView
# ---------------------------------------------------------------------------


class TestNewestFirstHistoryView:
    def test_index_slice_iter_reversed(self) -> None:
        buf = ChronologicalSeriesBuffer()
        for v in (10.0, 20.0, 30.0):
            buf.append(v)
        view = NewestFirstHistoryView(buf)
        assert len(view) == 3
        assert list(view) == [30.0, 20.0, 10.0]
        assert view[0] == 30.0
        assert view[-1] == 10.0
        assert view[0:2] == [30.0, 20.0]
        assert list(reversed(view)) == [10.0, 20.0, 30.0]
        assert "NewestFirstHistoryView" in repr(view)

    def test_setitem_and_appendleft(self) -> None:
        buf = ChronologicalSeriesBuffer(maxlen=5)
        for v in (1, 2, 3):
            buf.append(v)
        view = NewestFirstHistoryView(buf)
        view[0] = 99
        assert buf.lookback(0) == 99
        view[-1] = 7
        assert buf.chronological()[0] == 7
        view.appendleft(100)
        assert buf.lookback(0) == 100
        assert list(view)[0] == 100

    def test_setitem_errors(self) -> None:
        buf = ChronologicalSeriesBuffer()
        buf.append(1)
        view = NewestFirstHistoryView(buf)
        with pytest.raises(IndexError):
            view[5] = 1
        with pytest.raises(IndexError):
            view[-5] = 1
        with pytest.raises(TypeError):
            view["x"] = 1  # type: ignore[index]

    def test_getitem_errors(self) -> None:
        buf = ChronologicalSeriesBuffer()
        view = NewestFirstHistoryView(buf)
        with pytest.raises(IndexError):
            _ = view[0]
        buf.append(1)
        with pytest.raises(TypeError):
            _ = view["nope"]  # type: ignore[index]

    def test_setitem_on_unbounded_buffer(self) -> None:
        buf = ChronologicalSeriesBuffer()
        for v in (1, 2, 3):
            buf.append(v)
        view = NewestFirstHistoryView(buf)
        view[1] = 20
        assert buf.lookback(1) == 20
        assert buf.chronological() == [1, 20, 3]


# ---------------------------------------------------------------------------
# RingPineSeries + factories
# ---------------------------------------------------------------------------


class TestRingPineSeriesExtra:
    def test_basic_offsets_and_repr(self) -> None:
        r = RingPineSeries(history_length=5)
        r.update(1)
        r.update(2)
        r.update(3)
        assert r[0] == 3
        assert r[1] == 2
        assert r[10] is None
        assert r.current == 3
        assert r.history_length == 5
        assert "RingPineSeries" in repr(r)
        assert r.chrono_order is True

    def test_initial_value_seed(self) -> None:
        r = RingPineSeries(7.5, history_length=10)
        assert r.current == 7.5
        assert r[0] == 7.5
        assert len(r.history) == 1
        empty = RingPineSeries(None, history_length=3)
        assert empty.current is None
        assert len(empty.history) == 0

    def test_set_history_length_noop_and_shrink(self) -> None:
        r = RingPineSeries(history_length=8)
        for i in range(6):
            r.update(i)
        r.set_history_length(8)  # noop
        assert r.history_length == 8
        r.set_history_length(3)
        assert r.history_length == 3
        assert list(r.history) == [5, 4, 3]
        assert r[0] == 5

    def test_set_current_empty_and_wrapped(self) -> None:
        empty = RingPineSeries(history_length=3)
        empty.set_current(42)
        assert empty[0] == 42
        assert len(empty.history) == 1
        r = RingPineSeries(history_length=3)
        for v in (1, 2, 3, 4):
            r.update(v)
        r.set_current(50)
        assert r.buffer.chronological() == [2, 3, 50]

    def test_na_and_zero_preserved(self) -> None:
        r = RingPineSeries(history_length=10)
        r.update(0.0)
        r.update(None)
        r.update(0.0)
        assert r[0] == 0.0
        assert r[1] is None
        assert r[2] == 0.0
        assert r[math.nan] is None
        assert r[math.inf] is None

    def test_falsy_history_length_policy(self) -> None:
        assert RingPineSeries(history_length=0).history_length == DEFAULT_PINESERIES_HISTORY
        assert RingPineSeries(history_length=None).history_length == DEFAULT_PINESERIES_HISTORY  # type: ignore[arg-type]
        assert RingPineSeries(history_length=-2).history_length == 1


class TestMakeSeriesAndEvaluatorHistory:
    def test_make_series_force_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PYNE_SERIES_RING", raising=False)
        legacy = make_series(1.0, history_length=16, force_ring=False)
        assert type(legacy) is PineSeries
        ring = make_series(1.0, history_length=16, force_ring=True)
        assert type(ring) is RingPineSeries
        monkeypatch.setenv("PYNE_SERIES_RING", "1")
        auto_on = make_series(history_length=8)
        assert type(auto_on) is RingPineSeries
        monkeypatch.setenv("PYNE_SERIES_RING", "0")
        auto_off = make_series(history_length=8)
        assert type(auto_off) is PineSeries

    def test_evaluator_history_length(self) -> None:
        assert evaluator_history_length(None) == DEFAULT_PINESERIES_HISTORY
        assert evaluator_history_length(object()) == DEFAULT_PINESERIES_HISTORY

        class _Ev:
            _pine_series_cap = 2500

        # raised cap when evaluator exposes a larger series cap
        assert evaluator_history_length(_Ev()) >= DEFAULT_PINESERIES_HISTORY
