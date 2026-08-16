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

"""Golden tests for Phase 2.2 chronological series ring (PYNE_SERIES_RING).

Covers:
- O(1) lookback semantics: series[0]/[1]/[n], na on OOB/negative/None/NaN
- Optional maxlen ring (compose with T1 mentally)
- Flag default OFF → legacy PineSeries
- RingPineSeries duck-type parity with PineSeries for history[0] / reverse
"""

from __future__ import annotations

from collections import deque

import pytest

from pynescript.ast.evaluator.series_buffer import ChronoTailView
from pynescript.ast.evaluator.series_buffer import ChronologicalSeriesBuffer
from pynescript.ast.evaluator.series_buffer import NewestFirstHistoryView
from pynescript.ast.evaluator.series_buffer import RingPineSeries
from pynescript.ast.evaluator.series_buffer import make_series
from pynescript.ast.evaluator.series_buffer import series_ring_enabled


# ---------------------------------------------------------------------------
# ChronologicalSeriesBuffer — core lookback goldens
# ---------------------------------------------------------------------------


def test_buffer_empty_lookback_is_na() -> None:
    buf = ChronologicalSeriesBuffer()
    assert len(buf) == 0
    assert buf.current is None
    assert buf[0] is None
    assert buf[1] is None
    assert buf[-1] is None
    assert buf[None] is None


def test_buffer_index_0_1_n_and_oob_na() -> None:
    buf = ChronologicalSeriesBuffer()
    for v in (10.0, 20.0, 30.0):
        buf.append(v)

    # Pine offsets
    assert buf[0] == 30.0  # current
    assert buf[1] == 20.0  # previous
    assert buf[2] == 10.0  # n = len-1
    assert buf[3] is None  # OOB → na (never invent 0)

    assert buf.current == 30.0
    assert buf.lookback(0) == 30.0
    assert buf.lookback(1) == 20.0
    assert buf.lookback(99) is None


def test_buffer_float_offset_truncates_nan_is_na() -> None:
    buf = ChronologicalSeriesBuffer()
    buf.append(1.0)
    buf.append(2.0)
    buf.append(3.0)
    assert buf[1.9] == 2.0  # trunc toward zero
    assert buf[float("nan")] is None


def test_buffer_negative_offset_is_na() -> None:
    buf = ChronologicalSeriesBuffer()
    buf.append(5.0)
    assert buf[-1] is None
    assert buf[-5] is None


def test_buffer_chronological_materialize() -> None:
    buf = ChronologicalSeriesBuffer()
    for i in range(5):
        buf.append(float(i))
    assert buf.chronological() == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert list(buf) == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_buffer_maxlen_ring_drops_oldest() -> None:
    buf = ChronologicalSeriesBuffer(maxlen=3)
    for v in (1, 2, 3, 4, 5):
        buf.append(v)
    assert len(buf) == 3
    assert buf.chronological() == [3, 4, 5]
    assert buf[0] == 5
    assert buf[1] == 4
    assert buf[2] == 3
    assert buf[3] is None


def test_buffer_maxlen_one() -> None:
    buf = ChronologicalSeriesBuffer(maxlen=1)
    buf.append(10)
    buf.append(20)
    assert len(buf) == 1
    assert buf[0] == 20
    assert buf[1] is None
    assert buf.chronological() == [20]


def test_buffer_invalid_maxlen_raises() -> None:
    with pytest.raises(ValueError):
        ChronologicalSeriesBuffer(maxlen=0)
    with pytest.raises(ValueError):
        ChronologicalSeriesBuffer(maxlen=-3)


# ---------------------------------------------------------------------------
# NewestFirstHistoryView — legacy duck-type for _as_series reverse
# ---------------------------------------------------------------------------


def test_newest_first_view_matches_deque_semantics() -> None:
    buf = ChronologicalSeriesBuffer()
    for v in (10.0, 20.0, 30.0):
        buf.append(v)
    view = NewestFirstHistoryView(buf)

    # Newest-first (like PineSeries.history deque after appendleft)
    assert list(view) == [30.0, 20.0, 10.0]
    assert view[0] == 30.0
    assert view[1] == 20.0
    assert view[2] == 10.0

    # reversed(newest-first) → chronological (what _as_series expects)
    assert list(reversed(view)) == [10.0, 20.0, 30.0]
    assert list(reversed(view)) == list(reversed(deque([30.0, 20.0, 10.0])))


# ---------------------------------------------------------------------------
# RingPineSeries — PineSeries surface goldens
# ---------------------------------------------------------------------------


def test_ring_pineseries_offsets_match_legacy_pineseries() -> None:
    from backend.series import PineSeries

    legacy = PineSeries()
    ring = RingPineSeries()
    for v in (10.0, 20.0, 30.0, None, 50.0):
        legacy.update(v)
        ring.update(v)

    for i in range(8):
        assert ring[i] == legacy[i], f"offset {i}: ring={ring[i]!r} legacy={legacy[i]!r}"
    assert ring[None] is None
    assert ring[float("nan")] is None
    assert ring[-1] is None
    assert ring[1.9] == legacy[1.9]
    assert ring.current == legacy.current == 50.0
    # history[0] newest for both
    assert ring.history[0] == legacy.history[0] == 50.0


def test_ring_pineseries_history_reverse_for_as_series() -> None:
    """_as_series does list(reversed(history)) → chronological."""
    ring = RingPineSeries(history_length=100)
    for i in range(10):
        ring.update(float(i))
    chrono = list(reversed(ring.history))
    assert chrono == [float(i) for i in range(10)]
    assert chrono[-1] == ring.current


def test_ring_pineseries_arithmetic_na_safe() -> None:
    a = RingPineSeries(10.0)
    b = RingPineSeries(None)
    assert (a + 5) == 15.0
    assert (a + b) is None
    assert (a * 2) == 20.0
    empty = RingPineSeries()
    assert empty.current is None
    assert empty[0] is None


def test_ring_set_history_length_keeps_newest() -> None:
    ring = RingPineSeries(history_length=10)
    for i in range(8):
        ring.update(i)
    ring.set_history_length(3)
    assert len(ring.history) == 3
    assert ring.history_length == 3
    assert ring[0] == 7
    assert ring[1] == 6
    assert ring[2] == 5
    assert ring[3] is None


# ---------------------------------------------------------------------------
# Flag default OFF — no correctness loss
# ---------------------------------------------------------------------------


def test_series_ring_enabled_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYNE_SERIES_RING", raising=False)
    assert series_ring_enabled() is False
    monkeypatch.setenv("PYNE_SERIES_RING", "0")
    assert series_ring_enabled() is False
    monkeypatch.setenv("PYNE_SERIES_RING", "false")
    assert series_ring_enabled() is False
    monkeypatch.setenv("PYNE_SERIES_RING", "1")
    assert series_ring_enabled() is True
    monkeypatch.setenv("PYNE_SERIES_RING", "true")
    assert series_ring_enabled() is True


def test_make_series_default_is_legacy_pineseries(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.series import PineSeries
    from backend.series import make_pine_series

    monkeypatch.setenv("PYNE_SERIES_RING", "0")
    s = make_pine_series()
    assert type(s) is PineSeries
    s2 = make_series(force_ring=False)
    assert type(s2) is PineSeries


def test_make_series_flag_on_returns_ring(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.series import make_pine_series

    monkeypatch.setenv("PYNE_SERIES_RING", "1")
    s = make_pine_series()
    assert type(s) is RingPineSeries
    s2 = make_series(force_ring=True)
    assert type(s2) is RingPineSeries


def test_runtime_flag_off_close_offsets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag off: Runtime still serves correct close[0]/[1] (legacy path)."""
    from backend.runtime import Runtime

    monkeypatch.setenv("PYNE_SERIES_RING", "0")
    bars = [
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0 + i,
            "volume": 1.0,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(5)
    ]
    src = """//@version=5
indicator("ring_off")
plot(close[0], "c0")
plot(close[1], "c1")
plot(close[10], "c10")
"""
    out = Runtime(symbol="T").run(src, bars)
    assert "error" not in out, out.get("error")
    series = out.get("series") or {}
    # Find plots by title if present, else by insertion order
    vals = list(series.values())
    assert len(vals) >= 3
    c0, c1, c10 = vals[0], vals[1], vals[2]
    assert c0[-1] == 104.0
    # close[1] on last bar is previous close
    assert c1[-1] == 103.0
    # OOB lookback → na on all bars (only 5 bars, offset 10)
    assert all(v is None for v in c10)


def test_runtime_flag_on_close_offsets_match_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ring on ≡ ring off for close[0]/[1]/[n] goldens.

    Distinct source comments avoid host parse-AST cache key collisions on
    multi-run (AST may be mutated in place during visit — residual of the
    parse-cache path, not the ring).
    """
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0 + i,
            "volume": 1.0,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(8)
    ]
    src_off = """//@version=5
indicator("ring_parity_off")
// ring-off path
plot(close[0], "c0")
plot(close[1], "c1")
plot(close[3], "c3")
plot(close[20], "c20")
"""
    src_on = """//@version=5
indicator("ring_parity_on")
// ring-on path
plot(close[0], "c0")
plot(close[1], "c1")
plot(close[3], "c3")
plot(close[20], "c20")
"""
    monkeypatch.setenv("PYNE_SERIES_RING", "0")
    off = Runtime(symbol="T").run(src_off, bars)
    monkeypatch.setenv("PYNE_SERIES_RING", "1")
    on = Runtime(symbol="T").run(src_on, bars)
    assert "error" not in off or not off.get("error"), off.get("error")
    assert "error" not in on or not on.get("error"), on.get("error")
    off_s = list((off.get("series") or {}).values())
    on_s = list((on.get("series") or {}).values())
    assert len(off_s) == 4 and len(on_s) == 4, (off.get("series"), on.get("series"))
    for a, b in zip(off_s, on_s, strict=True):
        assert a == b


def test_as_series_accepts_ring_pineseries() -> None:
    """TA materialization path: reverse history → chronological, capped."""
    from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers

    class _H(TechnicalHelpers):
        def _error(self, message: str) -> None:
            raise RuntimeError(message)

    ev = _H()
    ring = RingPineSeries(history_length=500)
    for i in range(20):
        ring.update(float(i))
    mat = ev._as_series(ring)
    assert mat[-1] == 19.0
    assert mat[0] == 0.0
    assert len(mat) == 20


# ---------------------------------------------------------------------------
# Correctness harden goldens (parity with list PineSeries)
# ---------------------------------------------------------------------------


def test_history_length_matches_legacy_pineseries() -> None:
    """0 / None / negative must not leave the ring uncapped (legacy: 1000 / 1)."""
    from backend.series import DEFAULT_PINESERIES_HISTORY
    from backend.series import PineSeries

    cases = (0, None, False, -1, -5, 1, 5, 1000)
    for hl in cases:
        pine = PineSeries(history_length=hl)  # type: ignore[arg-type]
        ring = RingPineSeries(history_length=hl)  # type: ignore[arg-type]
        assert ring.history_length == pine.history.maxlen, hl
    # Falsy → default floor; negative → 1
    assert RingPineSeries(history_length=0).history_length == DEFAULT_PINESERIES_HISTORY
    assert RingPineSeries(history_length=None).history_length == DEFAULT_PINESERIES_HISTORY
    assert RingPineSeries(history_length=-3).history_length == 1


def test_ring_is_pineseries_subclass() -> None:
    from backend.series import PineSeries

    ring = RingPineSeries(1.0)
    assert isinstance(ring, PineSeries)
    assert type(ring) is RingPineSeries


def test_oob_negative_inf_nan_never_zero() -> None:
    from math import inf
    from math import nan

    from backend.series import PineSeries

    pine = PineSeries()
    ring = RingPineSeries()
    pine.update(7.0)
    ring.update(7.0)
    for idx in (-1, -99, 1, 100, None, nan, inf, -inf, object(), "x", 1 + 0j):
        pv, rv = pine[idx], ring[idx]
        assert pv is None, idx
        assert rv is None, idx
        assert pv != 0 and rv != 0


def test_zero_value_is_not_na() -> None:
    """Stored 0.0 must survive lookback; na is None, never coerced to 0."""
    ring = RingPineSeries()
    ring.update(0.0)
    ring.update(None)
    ring.update(0.0)
    assert ring[0] == 0.0
    assert ring[1] is None
    assert ring[2] == 0.0
    assert ring[3] is None


def test_set_current_same_bar_does_not_push() -> None:
    from backend.series import PineSeries

    pine = PineSeries()
    ring = RingPineSeries()
    pine.update(1.0)
    ring.update(1.0)
    pine.update(2.0)
    ring.update(2.0)
    pine.set_current(9.0)
    ring.set_current(9.0)
    assert len(ring.history) == len(pine.history) == 2
    assert ring[0] == pine[0] == 9.0
    assert ring[1] == pine[1] == 1.0
    assert ring[2] is None
    # empty → first sample
    empty = RingPineSeries()
    empty.set_current(3.0)
    assert empty[0] == 3.0
    assert empty[1] is None
    assert len(empty.history) == 1


def test_history_setitem_and_appendleft_deque_parity() -> None:
    ring = RingPineSeries()
    for v in (10.0, 20.0, 30.0):
        ring.update(v)
    ring.history[0] = 99.0
    assert ring[0] == 99.0
    assert ring.buffer.lookback(0) == 99.0
    ring.history.appendleft(100.0)
    assert ring[0] == 100.0
    assert ring[1] == 99.0
    # bool index (deque accepts True/False via operator.index)
    assert ring.history[False] == 100.0
    assert ring.history[True] == 99.0


def test_ring_wrap_many_cycles_matches_legacy() -> None:
    from backend.series import PineSeries

    pine = PineSeries(history_length=4)
    ring = RingPineSeries(history_length=4)
    for i in range(25):
        pine.update(float(i))
        ring.update(float(i))
        assert list(ring.history) == list(pine.history), i
        for off in range(-1, 8):
            assert ring[off] == pine[off], (i, off)
            # OOB / negative never invent 0
            if off < 0 or off >= 4:
                assert ring[off] is None
    assert ring.buffer.chronological() == [21.0, 22.0, 23.0, 24.0]
    assert ring[0] == 24.0
    assert ring[3] == 21.0
    assert ring[4] is None


def test_apply_bar_sample_ring_no_dual_list() -> None:
    """Ring wrapper + dest=None is the host dual-write skip."""
    from backend.series import apply_bar_sample

    ring = RingPineSeries(history_length=8)
    apply_bar_sample(ring, 1.0)
    apply_bar_sample(ring, 2.0)
    apply_bar_sample(ring, 3.0)
    assert ring.current == 3.0
    assert ring[0] == 3.0
    assert ring[1] == 2.0
    assert ring.buffer.chronological() == [1.0, 2.0, 3.0]


def test_set_current_after_wrap() -> None:
    ring = RingPineSeries(history_length=3)
    for v in (1.0, 2.0, 3.0, 4.0, 5.0):
        ring.update(v)
    ring.set_current(50.0)
    assert ring[0] == 50.0
    assert ring[1] == 4.0
    assert ring[2] == 3.0
    assert ring[3] is None
    assert ring.buffer.chronological() == [3.0, 4.0, 50.0]


def test_as_series_after_ring_wrap_keeps_newest_window() -> None:
    from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers

    class _H(TechnicalHelpers):
        def _error(self, message: str) -> None:
            raise RuntimeError(message)

    ev = _H()
    ev._SERIES_MAX = 4  # type: ignore[attr-defined]
    ring = RingPineSeries(history_length=4)
    for i in range(10):
        ring.update(float(i))
    mat = ev._as_series(ring)
    assert mat == [6.0, 7.0, 8.0, 9.0]


def test_runtime_ring_and_cap_sma_matches_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ring + list cap: SMA(20) last-N matches flag-off; close[n] OOB is na."""
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache

        clear_parse_cache()
    except Exception:  # noqa: BLE001
        pass

    bars = [
        {
            "open": 100.0 + i * 0.1,
            "high": 101.0 + i * 0.1,
            "low": 99.0 + i * 0.1,
            "close": 100.0 + i,
            "volume": 1.0,
            "time": 1_700_000_000_000 + i * 86_400_000,
        }
        for i in range(80)
    ]
    src_off = """//@version=5
indicator("ring_cap_off")
plot(ta.sma(close, 20), "s")
plot(close[1], "c1")
plot(close[200], "c200")
"""
    src_on = """//@version=5
indicator("ring_cap_on")
plot(ta.sma(close, 20), "s")
plot(close[1], "c1")
plot(close[200], "c200")
"""
    monkeypatch.setenv("PYNE_SERIES_CAP", "1")
    monkeypatch.setenv("PYNE_SERIES_RING", "0")
    off = Runtime(symbol="T").run(src_off, bars)
    monkeypatch.setenv("PYNE_SERIES_RING", "1")
    on = Runtime(symbol="T").run(src_on, bars)
    assert "error" not in off, off.get("error")
    assert "error" not in on, on.get("error")
    for key in ("s", "c1", "c200"):
        a, b = off["series"][key], on["series"][key]
        assert len(a) == len(b) == 80
        # last 40 SMA / close[1] cells; c200 is na on every bar
        if key == "c200":
            assert all(v is None for v in a) and all(v is None for v in b)
        else:
            for x, y in zip(a[-40:], b[-40:], strict=True):
                if x is None and y is None:
                    continue
                assert x is not None and y is not None
                assert abs(float(x) - float(y)) <= 1e-9


def test_chrono_tail_view_keep_window_and_slice() -> None:
    buf = ChronologicalSeriesBuffer(maxlen=8)
    for i in range(10):
        buf.append(float(i))
    # buffer newest 8: 2..9; tail keep=4 → 6,7,8,9
    view = ChronoTailView(buf, keep=4)
    assert len(view) == 4
    assert list(view) == [6.0, 7.0, 8.0, 9.0]
    assert view[0] == 6.0
    assert view[-1] == 9.0
    assert view[1:3] == [7.0, 8.0]
    with pytest.raises(IndexError):
        _ = view[4]


def test_chrono_tail_view_grows_until_keep() -> None:
    buf = ChronologicalSeriesBuffer(maxlen=16)
    view = ChronoTailView(buf, keep=5)
    assert len(view) == 0
    buf.append(1.0)
    buf.append(2.0)
    assert list(view) == [1.0, 2.0]
    for i in range(3, 10):
        buf.append(float(i))
    assert list(view) == [5.0, 6.0, 7.0, 8.0, 9.0]
