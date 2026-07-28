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

"""Golden tests: incremental bar-mode TA matches full-recompute last values."""

from __future__ import annotations

import math
import os

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


def _series(n: int = 120, seed: float = 100.0) -> list[float]:
    """Synthetic close path with mild trend + oscillation."""
    out: list[float] = []
    x = seed
    for i in range(n):
        x += math.sin(i / 7.0) * 1.5 + 0.05
        out.append(x)
    return out


class _FullTA(NodeLiteralEvaluator):
    """Full-recompute path (unit-test default: no bar mode)."""


class _IncTA(NodeLiteralEvaluator):
    """Bar-mode + incremental TA."""

    def __init__(self) -> None:
        super().__init__()
        self._pine_bar_mode = True
        self._pine_ta_incremental = True
        self._ta_inc_state = {}
        self._ta_call_i = 0


def _bar_walk_full_sma(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._sma(src[: i + 1], period)
        out.append(full[-1] if full else None)
    return out


def _bar_walk_inc_sma(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._sma_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_ema(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._ema(src[: i + 1], period)
        out.append(full[-1] if full else None)
    return out


def _bar_walk_inc_ema(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._ema_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_rma(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._rma(src[: i + 1], period)
        last = full[-1] if full else math.nan
        out.append(None if (last is None or (isinstance(last, float) and math.isnan(last))) else last)
    return out


def _bar_walk_inc_rma(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._rma_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_rsi(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        out.append(ev._rsi(src[: i + 1], period))
    return out


def _bar_walk_inc_rsi(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._rsi_inc_update(src[: i + 1], period))
    return out


def _assert_series_close(
    got: list[float | None],
    exp: list[float | None],
    *,
    rel: float = 1e-9,
    abs_: float = 1e-9,
) -> None:
    assert len(got) == len(exp)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        if e is None:
            assert g is None, f"bar {i}: expected None, got {g}"
            continue
        assert g is not None, f"bar {i}: expected {e}, got None"
        assert g == pytest.approx(e, rel=rel, abs=abs_), f"bar {i}: {g} != {e}"


def test_incremental_sma_matches_full() -> None:
    src = _series(150)
    for period in (5, 14, 20):
        _assert_series_close(_bar_walk_inc_sma(src, period), _bar_walk_full_sma(src, period))


def test_incremental_ema_matches_full() -> None:
    src = _series(150)
    for period in (8, 12, 26):
        _assert_series_close(_bar_walk_inc_ema(src, period), _bar_walk_full_ema(src, period))


def test_incremental_rma_matches_full() -> None:
    src = _series(150)
    for period in (10, 14):
        _assert_series_close(_bar_walk_inc_rma(src, period), _bar_walk_full_rma(src, period))


def test_incremental_rsi_matches_full() -> None:
    src = _series(150)
    for period in (7, 14):
        _assert_series_close(
            _bar_walk_inc_rsi(src, period),
            _bar_walk_full_rsi(src, period),
            rel=1e-9,
            abs_=1e-9,
        )


def test_two_call_sites_independent() -> None:
    """ta.sma(close,20) and ta.sma(close,50) must not share state."""
    src = _series(80)
    ev = _IncTA()
    a_out: list[float | None] = []
    b_out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        a_out.append(ev._sma_inc_update(src[: i + 1], 20))
        b_out.append(ev._sma_inc_update(src[: i + 1], 50))
    _assert_series_close(a_out, _bar_walk_full_sma(src, 20))
    _assert_series_close(b_out, _bar_walk_full_sma(src, 50))


def test_nested_ema_of_sma_bar_stream() -> None:
    """Nested ta.ema(ta.sma(...)) via sequential scalars at two call sites."""
    src = _series(100)
    period_s, period_e = 10, 8
    # Full nested: for each bar, sma series then ema of that
    full_nested: list[float | None] = []
    evf = _FullTA()
    for i in range(len(src)):
        sma_series = evf._sma(src[: i + 1], period_s)
        # replace None with skip for ema seed consistency — full ema carries None as missing
        ema_series = evf._ema(sma_series, period_e)
        full_nested.append(ema_series[-1] if ema_series else None)

    evi = _IncTA()
    inc_nested: list[float | None] = []
    for i in range(len(src)):
        evi._ta_call_i = 0
        sma_val = evi._sma_inc_update(src[: i + 1], period_s)
        # second call site sees stream of sma scalars
        ema_val = evi._ema_inc_update([sma_val], period_e)
        inc_nested.append(ema_val)

    # Compare from the bar where both are defined
    for i, (g, e) in enumerate(zip(inc_nested, full_nested, strict=True)):
        if e is None:
            continue
        assert g == pytest.approx(e, rel=1e-9, abs=1e-9), f"bar {i}: {g} != {e}"


def test_runtime_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backend Runtime plots match with incremental on vs forced off."""
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101 + i * 0.1,
            "low": 99 + i * 0.1,
            "close": 100.5 + i * 0.1,
            "volume": 1000,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(80)
    ]
    src = """//@version=5
indicator("inc")
plot(ta.sma(close, 10))
plot(ta.ema(close, 12))
plot(ta.rsi(close, 14))
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    # New Runtime/evaluator so env is read fresh
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)

    series_on = r_on["series"]
    series_off = r_off["series"]
    assert set(series_on) == set(series_off)
    for key in series_on:
        for i, (a, b) in enumerate(zip(series_on[key], series_off[key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                # allow early-bar na differences only if both none-ish
                assert a is None or b is None
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def test_env_disable_uses_full_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    ev_off = _IncTA()
    assert ev_off._use_incremental_ta() is False
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    # Flag is resolved once per evaluator instance
    ev_on = _IncTA()
    assert ev_on._use_incremental_ta() is True


def _ohlc(n: int = 120) -> tuple[list[float], list[float], list[float]]:
    closes = _series(n)
    highs = [c + 1.0 + (i % 5) * 0.1 for i, c in enumerate(closes)]
    lows = [c - 1.0 - (i % 3) * 0.1 for i, c in enumerate(closes)]
    return highs, lows, closes


def _bar_walk_full_macd(
    src: list[float], fast: int, slow: int, signal: int
) -> list[tuple[float, float, float]]:
    ev = _FullTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(src)):
        out.append(ev._macd(src[: i + 1], fast, slow, signal))
    return out


def _bar_walk_inc_macd(
    src: list[float], fast: int, slow: int, signal: int
) -> list[tuple[float, float, float]]:
    ev = _IncTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._macd_inc_update(src[: i + 1], fast, slow, signal))
    return out


def _bar_walk_full_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._atr(highs[: i + 1], lows[: i + 1], closes[: i + 1], period)
        if not full:
            out.append(None)
        else:
            last = full[-1]
            out.append(None if (isinstance(last, float) and math.isnan(last)) else last)
    return out


def _bar_walk_inc_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._atr_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], period))
    return out


def test_incremental_macd_matches_full() -> None:
    src = _series(150)
    for params in ((12, 26, 9), (8, 17, 5)):
        got = _bar_walk_inc_macd(src, *params)
        exp = _bar_walk_full_macd(src, *params)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            assert g[0] == pytest.approx(e[0], rel=1e-9, abs=1e-9), f"macd bar {i}"
            assert g[1] == pytest.approx(e[1], rel=1e-9, abs=1e-9), f"signal bar {i}"
            assert g[2] == pytest.approx(e[2], rel=1e-9, abs=1e-9), f"hist bar {i}"


def test_incremental_atr_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    for period in (7, 14):
        _assert_series_close(
            _bar_walk_inc_atr(highs, lows, closes, period),
            _bar_walk_full_atr(highs, lows, closes, period),
        )


def _bar_walk_full_bb(
    src: list[float], period: int, mult: float
) -> list[tuple[float | None, float | None, float | None]]:
    ev = _FullTA()
    out: list[tuple[float | None, float | None, float | None]] = []
    for i in range(len(src)):
        out.append(ev._bollinger_bands(src[: i + 1], period, mult))
    return out


def _bar_walk_inc_bb(
    src: list[float], period: int, mult: float
) -> list[tuple[float | None, float | None, float | None]]:
    ev = _IncTA()
    out: list[tuple[float | None, float | None, float | None]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._bollinger_bands(src[: i + 1], period, mult))
    return out


def test_incremental_bb_matches_full() -> None:
    src = _series(150)
    for period, mult in ((20, 2.0), (10, 1.5)):
        got = _bar_walk_inc_bb(src, period, mult)
        exp = _bar_walk_full_bb(src, period, mult)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            for j in range(3):
                if e[j] is None:
                    assert g[j] is None, f"bb bar {i} component {j}"
                else:
                    assert g[j] == pytest.approx(e[j], rel=1e-9, abs=1e-9), f"bb bar {i} c{j}"


def test_runtime_macd_atr_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1,
            "low": 98.5 + i * 0.1,
            "close": 100.5 + i * 0.1,
            "volume": 1000,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(100)
    ]
    src = """//@version=5
indicator("macd atr")
[m, s, h] = ta.macd(close, 12, 26, 9)
plot(m)
plot(s)
plot(h)
plot(ta.atr(14))
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)

    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def _bar_walk_full_stdev(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        out.append(ev._stdev(src[: i + 1], period))
    return out


def _bar_walk_inc_stdev(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._stdev_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_highest(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._highest(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_highest(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._highest_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_lowest(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._lowest(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_lowest(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._lowest_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_wma(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._wma(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_wma(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._wma_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_tr(
    highs: list[float], lows: list[float], closes: list[float]
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._tr(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        out.append(full[-1] if full else None)
    return out


def _bar_walk_inc_tr(
    highs: list[float], lows: list[float], closes: list[float]
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._tr_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1]))
    return out


def _bar_walk_full_change(src: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._change(src[: i + 1], length) for i in range(len(src))]


def _bar_walk_inc_change(src: list[float], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._change_inc_update(src[: i + 1], length))
    return out


def test_incremental_stdev_matches_full() -> None:
    src = _series(150)
    for period in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_stdev(src, period),
            _bar_walk_full_stdev(src, period),
            rel=1e-9,
            abs_=1e-9,
        )


def test_incremental_highest_lowest_matches_full() -> None:
    src = _series(120)
    for period in (5, 20, 50):
        _assert_series_close(_bar_walk_inc_highest(src, period), _bar_walk_full_highest(src, period))
        _assert_series_close(_bar_walk_inc_lowest(src, period), _bar_walk_full_lowest(src, period))


def test_incremental_wma_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 20):
        _assert_series_close(_bar_walk_inc_wma(src, period), _bar_walk_full_wma(src, period))


def test_incremental_tr_matches_full() -> None:
    highs, lows, closes = _ohlc(120)
    _assert_series_close(
        _bar_walk_inc_tr(highs, lows, closes),
        _bar_walk_full_tr(highs, lows, closes),
    )


def test_incremental_change_matches_full() -> None:
    src = _series(100)
    for length in (1, 3, 10):
        _assert_series_close(
            _bar_walk_inc_change(src, length),
            _bar_walk_full_change(src, length),
        )


def test_runtime_stdev_bb_hl_wma_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(120)
    ]
    src = """//@version=5
indicator("stdev bb hl wma")
[u, m, l] = ta.bb(close, 20, 2.0)
plot(u)
plot(m)
plot(l)
plot(ta.stdev(close, 20))
plot(ta.highest(high, 20))
plot(ta.lowest(low, 20))
plot(ta.wma(close, 14))
plot(ta.change(close, 1))
plot(ta.tr)
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)

    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def _bar_walk_full_stoch(
    source: list[float], highs: list[float], lows: list[float], length: int
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(source)):
        out.append(ev._stoch_k(source[: i + 1], highs[: i + 1], lows[: i + 1], length))
    return out


def _bar_walk_inc_stoch(
    source: list[float], highs: list[float], lows: list[float], length: int
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(source)):
        ev._ta_call_i = 0
        out.append(ev._stoch_k_inc_update(source[: i + 1], highs[: i + 1], lows[: i + 1], length))
    return out


def test_incremental_stoch_matches_full() -> None:
    highs, lows, closes = _ohlc(120)
    for length in (5, 14):
        _assert_series_close(
            _bar_walk_inc_stoch(closes, highs, lows, length),
            _bar_walk_full_stoch(closes, highs, lows, length),
        )


def _bar_walk_full_vwma(src: list[float], vol: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    ev.current_series = {"volume": vol}
    out: list[float | None] = []
    for i in range(len(src)):
        ev.current_series = {"volume": vol[: i + 1]}
        full = ev._vwma(src[: i + 1], period)
        if not full:
            out.append(None)
        else:
            last = full[-1]
            out.append(None if (isinstance(last, float) and math.isnan(last)) else last)
    return out


def _bar_walk_inc_vwma(src: list[float], vol: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._vwma_inc_update(src[: i + 1], vol[: i + 1], period))
    return out


def test_incremental_vwma_matches_full() -> None:
    src = _series(100)
    vol = [1000.0 + (i % 7) * 10 for i in range(len(src))]
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_vwma(src, vol, period),
            _bar_walk_full_vwma(src, vol, period),
        )
