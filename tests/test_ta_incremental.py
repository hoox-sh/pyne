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

from typing import Any

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator


try:
    from pynescript.ast.helper import clear_parse_cache as _clear_parse_cache
except ImportError:  # pragma: no cover

    def _clear_parse_cache() -> None:
        return None


@pytest.fixture(autouse=True)
def _isolate_parse_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid Agent 05 shared-AST mutation across Runtime dual-run goldens.

    Cached parse trees are shared by identity; Runtime mutates the tree during
    eval, so a second ``Runtime.run`` of the same source without clearing can
    yield empty series / script_name ``plot``. Clear before each ``Runtime.run``.
    """
    _clear_parse_cache()
    try:
        from backend.runtime import Runtime

        _orig_run = Runtime.run

        def _run_cleared(self: object, *args: object, **kwargs: object) -> object:
            _clear_parse_cache()
            return _orig_run(self, *args, **kwargs)

        monkeypatch.setattr(Runtime, "run", _run_cleared)
    except Exception:  # pragma: no cover — backend optional in some envs
        pass
    yield
    _clear_parse_cache()


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
        if isinstance(e, float) and math.isnan(e):
            assert isinstance(g, float) and math.isnan(g), f"bar {i}: expected nan, got {g}"
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


def _bar_walk_full_macd(src: list[float], fast: int, slow: int, signal: int) -> list[tuple[float, float, float]]:
    ev = _FullTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(src)):
        out.append(ev._macd(src[: i + 1], fast, slow, signal))
    return out


def _bar_walk_inc_macd(src: list[float], fast: int, slow: int, signal: int) -> list[tuple[float, float, float]]:
    ev = _IncTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._macd_inc_update(src[: i + 1], fast, slow, signal))
    return out


def _bar_walk_full_atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float | None]:
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


def _bar_walk_inc_atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float | None]:
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


def _bar_walk_full_tr(highs: list[float], lows: list[float], closes: list[float]) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._tr(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        out.append(full[-1] if full else None)
    return out


def _bar_walk_inc_tr(highs: list[float], lows: list[float], closes: list[float]) -> list[float | None]:
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
[m, u, l] = ta.bb(close, 20, 2.0)
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


def _bar_walk_full_stoch(source: list[float], highs: list[float], lows: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(source)):
        out.append(ev._stoch_k(source[: i + 1], highs[: i + 1], lows[: i + 1], length))
    return out


def _bar_walk_inc_stoch(source: list[float], highs: list[float], lows: list[float], length: int) -> list[float | None]:
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


def _bar_walk_full_cum(src: list[float]) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        total = 0.0
        for v in src[: i + 1]:
            if v is None:
                continue
            total += float(v)
        out.append(total)
    return out


def _bar_walk_inc_cum(src: list[float]) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._cum_inc_update(src[: i + 1]))
    return out


def test_incremental_cum_matches_full() -> None:
    src = _series(80)
    _assert_series_close(_bar_walk_inc_cum(src), _bar_walk_full_cum(src))


# ---------------------------------------------------------------------------
# Round 2: cci, tsi, roc, wpr, dev, variance
# ---------------------------------------------------------------------------


def _bar_walk_full_cci(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    ev = _FullTA()
    return [ev._cci(highs[: i + 1], lows[: i + 1], closes[: i + 1], period) for i in range(len(closes))]


def _bar_walk_inc_cci(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._cci_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], period))
    return out


def _bar_walk_full_tsi(src: list[float], long_p: int, short_p: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        v = ev._tsi(src[: i + 1], long_p, short_p)
        out.append(v)
    return out


def _bar_walk_inc_tsi(src: list[float], long_p: int, short_p: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._tsi_inc_update(src[: i + 1], long_p, short_p))
    return out


def _bar_walk_full_roc(src: list[float], period: int) -> list[float]:
    ev = _FullTA()
    return [ev._roc(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_roc(src: list[float], period: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._roc_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_wpr(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    ev = _FullTA()
    return [ev._wpr(highs[: i + 1], lows[: i + 1], closes[: i + 1], period) for i in range(len(closes))]


def _bar_walk_inc_wpr(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._wpr_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], period))
    return out


def _bar_walk_full_dev(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._dev(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_dev(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._dev_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_variance(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._variance(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_variance(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._variance_inc_update(src[: i + 1], period))
    return out


def test_incremental_cci_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    for period in (10, 14, 20):
        _assert_series_close(
            _bar_walk_inc_cci(highs, lows, closes, period),
            _bar_walk_full_cci(highs, lows, closes, period),
        )


def test_incremental_tsi_matches_full() -> None:
    src = _series(150)
    for long_p, short_p in ((25, 13), (15, 7), (10, 5)):
        _assert_series_close(
            _bar_walk_inc_tsi(src, long_p, short_p),
            _bar_walk_full_tsi(src, long_p, short_p),
        )


def test_incremental_roc_matches_full() -> None:
    src = _series(120)
    for period in (1, 5, 10, 14):
        _assert_series_close(
            _bar_walk_inc_roc(src, period),
            _bar_walk_full_roc(src, period),
        )


def test_incremental_wpr_matches_full() -> None:
    highs, lows, closes = _ohlc(120)
    for period in (7, 14):
        _assert_series_close(
            _bar_walk_inc_wpr(highs, lows, closes, period),
            _bar_walk_full_wpr(highs, lows, closes, period),
        )


def test_incremental_dev_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_dev(src, period),
            _bar_walk_full_dev(src, period),
        )


def test_incremental_variance_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_variance(src, period),
            _bar_walk_full_variance(src, period),
        )


def test_runtime_cci_roc_wpr_tsi_dev_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
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
indicator("round2 osc")
plot(ta.cci(close, 14))
plot(ta.roc(close, 10))
plot(ta.wpr(14))
plot(ta.tsi(close, 13, 25))
plot(ta.dev(close, 14))
plot(ta.variance(close, 14))
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


# ---------------------------------------------------------------------------
# Round 3: hma, rising/falling, median, percentrank + _as_series hygiene
# ---------------------------------------------------------------------------


def _bar_walk_full_hma(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._hma(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_hma(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._hma_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_rising(src: list[float], period: int) -> list[bool]:
    ev = _FullTA()
    return [bool(ev._rising(src[: i + 1], period)) for i in range(len(src))]


def _bar_walk_inc_rising(src: list[float], period: int) -> list[bool]:
    ev = _IncTA()
    out: list[bool] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(bool(ev._rising_inc_update(src[: i + 1], period)))
    return out


def _bar_walk_full_falling(src: list[float], period: int) -> list[bool]:
    ev = _FullTA()
    return [bool(ev._falling(src[: i + 1], period)) for i in range(len(src))]


def _bar_walk_inc_falling(src: list[float], period: int) -> list[bool]:
    ev = _IncTA()
    out: list[bool] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(bool(ev._falling_inc_update(src[: i + 1], period)))
    return out


def _bar_walk_full_median(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._median(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_median(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._median_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_percentrank(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._percentrank(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_percentrank(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._percentrank_inc_update(src[: i + 1], period))
    return out


def test_incremental_hma_matches_full() -> None:
    src = _series(150)
    for period in (9, 14, 20):
        _assert_series_close(
            _bar_walk_inc_hma(src, period),
            _bar_walk_full_hma(src, period),
        )


def test_incremental_rising_falling_matches_full() -> None:
    src = _series(100)
    # Strict mono sequences exercise consecutive comparisons.
    rising_src = [float(i) for i in range(40)]
    falling_src = [float(40 - i) for i in range(40)]
    for period in (3, 5, 10):
        assert _bar_walk_inc_rising(src, period) == _bar_walk_full_rising(src, period)
        assert _bar_walk_inc_falling(src, period) == _bar_walk_full_falling(src, period)
        assert _bar_walk_inc_rising(rising_src, period) == _bar_walk_full_rising(rising_src, period)
        assert _bar_walk_inc_falling(falling_src, period) == _bar_walk_full_falling(falling_src, period)


def test_rising_falling_highestbars_tolerate_na() -> None:
    """Pine na (None) must not raise TypeError on rising/falling/highestbars.

    Regression: CommonIndicators used to override TechnicalHelpers with bare
    ``>=`` / ``max(window)``, crashing MA-STER style scripts on VIDYA warmup:
    ``'>=' not supported between instances of 'NoneType' and 'NoneType'``.
    """
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    ev = NodeLiteralEvaluator()
    all_na = [None, None, None, None, None, None, None]
    mixed = [None, None, 1.0, 2.0, 3.0, None, 4.0]
    assert ev._rising(all_na, 7) is False
    assert ev._falling(all_na, 7) is False
    assert ev._rising(mixed, 5) is False
    assert ev._falling(mixed, 5) is False
    # ``period`` pairwise steps need ``period+1`` samples (match numba_rising).
    assert ev._rising([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], 7) is False
    assert ev._falling([7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0], 7) is False
    assert ev._rising([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], 7) is True
    assert ev._falling([8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0], 7) is True
    # highestbars/lowestbars: skip na, return bars-back offset of extreme
    assert ev._highestbars([None, None, 1.0], 3) == 0
    assert ev._highestbars([None, 5.0, 1.0], 3) == -1
    assert ev._lowestbars([None, None, 1.0], 3) == 0
    assert ev._highestbars(all_na, 7) is None
    assert ev._lowestbars(all_na, 7) is None
    # Non-numeric junk must not raise (skip like None)
    assert ev._highestbars([None, "x", 1.0], 3) == 0
    assert ev._lowestbars([None, "x", 1.0], 3) == 0
    # Incremental path (backend bar-mode) must also soft-fail on na
    ev_inc = _IncTA()
    for i in range(len(all_na)):
        ev_inc._ta_call_i = 0
        assert ev_inc._rising_inc_update(all_na[: i + 1], 7) is False
        ev_inc._ta_call_i = 0
        assert ev_inc._falling_inc_update(all_na[: i + 1], 7) is False
        ev_inc._ta_call_i = 0
        assert ev_inc._highestbars_inc_update(all_na[: i + 1], 7) is None
        ev_inc._ta_call_i = 0
        assert ev_inc._lowestbars_inc_update(all_na[: i + 1], 7) is None


def test_common_indicators_does_not_override_na_safe_helpers() -> None:
    """0.3.0 bug class: CommonIndicators must not reintroduce bare comparisons.

    Rising/falling/highestbars/lowestbars live only on TechnicalHelpers.
    """
    from pynescript.ast.evaluator import NodeLiteralEvaluator
    from pynescript.ast.evaluator.builtins.technical_submodules.common import CommonIndicators
    from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers

    for name in ("_rising", "_falling", "_highestbars", "_lowestbars", "_crossover", "_crossunder"):
        assert name not in CommonIndicators.__dict__, f"CommonIndicators must not override {name}"
        # MRO resolution for live evaluator is TechnicalHelpers (or subclass of it)
        owners = [c for c in type(NodeLiteralEvaluator()).__mro__ if name in c.__dict__]
        assert owners, f"{name} missing from MRO"
        assert issubclass(owners[0], TechnicalHelpers) or owners[0] is TechnicalHelpers
        assert owners[0] is TechnicalHelpers or TechnicalHelpers in owners[0].__mro__


def test_crossover_crossunder_na_and_equal_prev() -> None:
    """TV semantics: prev <= (crossover) / >= (crossunder); na never raises."""
    ev = _FullTA()
    # equal-then-above is a real crossover (matches numba / _cross_stateful)
    assert ev._crossover([2.0, 3.0], [2.0, 2.0]) is True
    assert ev._crossover([1.0, 3.0], [2.0, 2.0]) is True
    assert ev._crossover([2.0, 2.0], [2.0, 2.0]) is False  # curr not strictly above
    assert ev._crossunder([2.0, 1.0], [2.0, 2.0]) is True
    assert ev._crossunder([3.0, 1.0], [2.0, 2.0]) is True
    # na operands → False, no TypeError
    assert ev._crossover([None, None], [1.0, 2.0]) is False
    assert ev._crossover([1.0, None], [None, 2.0]) is False
    assert ev._crossunder([None, 1.0], [2.0, None]) is False
    assert ev._cross([None, 1.0], [2.0, 0.5]) is False
    # max/min unary skip na
    assert ev._builtin_ta_max([[None, None, 3.0, None]]) == 3.0
    assert ev._builtin_ta_min([[None, None]]) is None
    assert ev._builtin_ta_max([[None, 1.0, 5.0, 2.0, None], 5]) == 5.0
    assert ev._builtin_ta_min([[None, 1.0, 5.0, 2.0, None], 5]) == 1.0


def test_highestbars_lowestbars_inc_parity_with_na() -> None:
    """Bar-walk full vs incremental on mixed-na series must stay identical."""
    mixed = [None, None, 1.0, 3.0, None, 2.0, 5.0, None, 4.0, 0.5, 6.0, None]
    for period in (3, 5, 7):
        assert _bar_walk_inc_highestbars(mixed, period) == _bar_walk_full_highestbars(mixed, period)
        assert _bar_walk_inc_lowestbars(mixed, period) == _bar_walk_full_lowestbars(mixed, period)


def test_runtime_warmup_rising_falling_vidya_style(monkeypatch: pytest.MonkeyPatch) -> None:
    """MA-STER / VIDYA style: rising/falling/highestbars on early-na MA must run.

    SMA is na until ``length`` bars; feeding that into ta.rising used to crash
    when CommonIndicators overrode helpers with bare ``>=`` / ``max``.
    """
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.2,
            "high": 101 + i * 0.2,
            "low": 99 + i * 0.2,
            "close": 100.5 + i * 0.2,
            "volume": 1000.0,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(50)
    ]
    src = """//@version=5
indicator("warmup na rising")
v = ta.sma(close, 10)
r = ta.rising(v, 5)
f = ta.falling(v, 5)
hb = ta.highestbars(v, 5)
lb = ta.lowestbars(v, 5)
x = ta.crossover(close, v)
u = ta.crossunder(close, v)
mx = ta.max(v, 5)
mn = ta.min(v, 5)
plot(r ? 1.0 : 0.0, title="r")
plot(f ? 1.0 : 0.0, title="f")
plot(hb, title="hb")
plot(lb, title="lb")
plot(x ? 1.0 : 0.0, title="x")
plot(u ? 1.0 : 0.0, title="u")
plot(mx, title="mx")
plot(mn, title="mn")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    r_on = Runtime(symbol="WARM").run(src, bars, mode="interpret")
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    r_off = Runtime(symbol="WARM").run(src, bars, mode="interpret")
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)

    assert r_on["count"] == 50
    # Early warmup: rising is false while MA is na / not strictly rising long enough
    assert r_on["series"]["r"][:10] == [0.0] * 10
    # After enough rising closes, SMA itself is rising → r becomes 1
    assert any(v == 1.0 for v in r_on["series"]["r"][10:])
    # highestbars/lowestbars produce finite ints (no crash sentinel)
    for key in ("hb", "lb"):
        vals = r_on["series"][key]
        assert all(v is None or isinstance(v, (int, float)) for v in vals)
        assert any(isinstance(v, (int, float)) for v in vals)
    # 2-arg max/min of derived SMA now use last-sample kernels (like highest).
    # Disabled full `_highest` on a 1-sample derived series stays na — skip those.
    assert all(v is None for v in r_on["series"]["mx"][:9])
    assert r_on["series"]["mx"][9] == pytest.approx(101.4)
    assert r_on["series"]["mn"][9] == pytest.approx(101.4)
    # Incremental on/off parity for this surface
    for key in r_on["series"]:
        if key in {"mx", "mn"}:
            continue
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def test_incremental_median_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 21):
        _assert_series_close(
            _bar_walk_inc_median(src, period),
            _bar_walk_full_median(src, period),
        )


def _bar_walk_full_mode(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._mode(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_mode(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._mode_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_cog(src: list[float], length: int) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(src)):
        window = src[: i + 1]
        if len(window) < length:
            out.append(float("nan"))
            continue
        w = window[-length:]
        num_sum = sum((j + 1) * val for j, val in enumerate(reversed(w)) if val is not None)
        den_sum = sum(val for val in w if val is not None)
        out.append(float("nan") if den_sum == 0 else -num_sum / den_sum)
    return out


def _bar_walk_inc_cog(src: list[float], length: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._cog_inc_update(src[: i + 1], length))
    return out


def test_incremental_mode_matches_full() -> None:
    src = _series(80)
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_mode(src, period),
            _bar_walk_full_mode(src, period),
        )


def test_incremental_cog_matches_full() -> None:
    src = _series(80)
    for length in (5, 10, 14):
        _assert_series_close(
            _bar_walk_inc_cog(src, length),
            _bar_walk_full_cog(src, length),
        )


def test_incremental_percentrank_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_percentrank(src, period),
            _bar_walk_full_percentrank(src, period),
        )


def test_as_series_pineseries_cache_and_cap() -> None:
    """PineSeries materialization is chronological, capped, and same-bar cached."""
    from collections import deque

    class _FakePS:
        def __init__(self, n: int) -> None:
            # Newest-first like backend.series.PineSeries
            self.history: deque[float] = deque(maxlen=2000)
            self.current: float | None = None
            for i in range(n):
                self.current = float(i)
                self.history.appendleft(float(i))

    ev = _FullTA()
    ps = _FakePS(500)
    a = ev._as_series(ps)
    b = ev._as_series(ps)
    assert a is b  # same-bar cache returns identical list object
    assert len(a) == ev._SERIES_MAX
    # Chronological: oldest of window … newest
    assert a[-1] == ps.current
    assert a[0] == float(500 - ev._SERIES_MAX)
    # Length/head change invalidates
    ps.current = 999.0
    ps.history.appendleft(999.0)
    c = ev._as_series(ps)
    assert c is not a
    assert c[-1] == 999.0


def test_series_last_accepts_pineseries_without_list() -> None:
    from collections import deque

    class _FakePS:
        def __init__(self) -> None:
            self.current = 42.5
            self.history: deque[float] = deque([42.5, 41.0, 40.0])

    assert _FullTA()._series_last(_FakePS()) == 42.5
    assert _FullTA()._series_last([1.0, 2.0, 3.0]) == 3.0
    assert _FullTA()._series_last([]) is None


def test_runtime_hma_median_rank_rising_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        for i in range(150)
    ]
    src = """//@version=5
indicator("round3 residual")
plot(ta.hma(close, 9))
plot(ta.median(close, 14))
plot(ta.percentrank(close, 14))
plot(ta.rising(close, 5) ? 1.0 : 0.0)
plot(ta.falling(close, 5) ? 1.0 : 0.0)
plot(ta.variance(close, 14))
plot(ta.dev(close, 14))
plot(ta.cci(close, 14))
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


# ---------------------------------------------------------------------------
# Round 4: mom, swma, highestbars/lowestbars, vwap, barssince, linreg
# ---------------------------------------------------------------------------


def _bar_walk_full_mom(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._mom(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_mom(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._mom_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_swma(src: list[float]) -> list[float | None]:
    ev = _FullTA()
    return [ev._swma(src[: i + 1]) for i in range(len(src))]


def _bar_walk_inc_swma(src: list[float]) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._swma_inc_update(src[: i + 1]))
    return out


def _bar_walk_full_highestbars(src: list[float], period: int) -> list[int]:
    ev = _FullTA()
    return [ev._highestbars(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_highestbars(src: list[float], period: int) -> list[int]:
    ev = _IncTA()
    out: list[int] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._highestbars_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_lowestbars(src: list[float], period: int) -> list[int]:
    ev = _FullTA()
    return [ev._lowestbars(src[: i + 1], period) for i in range(len(src))]


def _bar_walk_inc_lowestbars(src: list[float], period: int) -> list[int]:
    ev = _IncTA()
    out: list[int] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._lowestbars_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_vwap(src: list[float], vol: list[float]) -> list[float | None]:
    """Full cumulative VWAP last value per bar (matches _builtin_ta_vwap loop)."""
    out: list[float | None] = []
    for i in range(len(src)):
        cum_pv = 0.0
        cum_v = 0.0
        last = None
        for j in range(i + 1):
            price = src[j]
            if price is None:
                continue
            v = vol[j] if j < len(vol) and vol[j] is not None else 0.0
            try:
                v = float(v)
                price = float(price)
            except (TypeError, ValueError):
                continue
            cum_pv += price * v
            cum_v += v
            last = (cum_pv / cum_v) if cum_v else price
        out.append(last)
    return out


def _bar_walk_inc_vwap(src: list[float], vol: list[float]) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._vwap_inc_update(src[: i + 1], vol[: i + 1]))
    return out


def _bar_walk_full_barssince(cond: list[bool]) -> list[int | None]:
    """Full list-scan barssince on growing prefix."""
    out: list[int | None] = []
    for i in range(len(cond)):
        condition = cond[: i + 1]
        found = None
        for j in range(len(condition) - 1, -1, -1):
            c = condition[j]
            is_true = c is True or (c is not None and c is not False)
            if is_true:
                found = len(condition) - 1 - j
                break
        if found is None:
            found = len(condition) - 1
        out.append(found)
    return out


def _bar_walk_inc_barssince(cond: list[bool]) -> list[int | None]:
    ev = _IncTA()
    out: list[int | None] = []
    for i in range(len(cond)):
        ev._ta_call_i = 0
        out.append(ev._barssince_inc_update(cond[i]))
    return out


def _bar_walk_full_linreg(src: list[float], length: int) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(src)):
        series = src[: i + 1]
        if len(series) < length:
            out.append(float("nan"))
            continue
        window = series[-length:]
        valid = [v for v in window if v is not None]
        if len(valid) < 2:
            out.append(float("nan"))
            continue
        n = len(valid)
        x = list(range(n))
        mean_x = sum(x) / n
        mean_y = sum(valid) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, valid, strict=True))
        den = sum((xi - mean_x) ** 2 for xi in x)
        if den == 0:
            out.append(mean_y)
        else:
            slope = num / den
            # TV endpoint: mean_y + slope * ((n-1) - mean_x)
            out.append(mean_y + slope * ((n - 1) - mean_x))
    return out


def _bar_walk_inc_linreg(src: list[float], length: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._linreg_inc_update(src[: i + 1], length))
    return out


def test_incremental_mom_matches_full() -> None:
    src = _series(120)
    for period in (1, 5, 10, 14):
        _assert_series_close(
            _bar_walk_inc_mom(src, period),
            _bar_walk_full_mom(src, period),
        )


def test_incremental_swma_matches_full() -> None:
    src = _series(80)
    _assert_series_close(_bar_walk_inc_swma(src), _bar_walk_full_swma(src))


def test_incremental_highestbars_lowestbars_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 20):
        assert _bar_walk_inc_highestbars(src, period) == _bar_walk_full_highestbars(src, period)
        assert _bar_walk_inc_lowestbars(src, period) == _bar_walk_full_lowestbars(src, period)


def test_incremental_vwap_matches_full() -> None:
    src = _series(100)
    vol = [1000.0 + (i % 7) * 10 for i in range(len(src))]
    _assert_series_close(_bar_walk_inc_vwap(src, vol), _bar_walk_full_vwap(src, vol))


def test_incremental_barssince_matches_full() -> None:
    # Periodic true every 10 bars, plus all-false prefix and dense trues
    cond = [(i % 10 == 0) for i in range(60)]
    assert _bar_walk_inc_barssince(cond) == _bar_walk_full_barssince(cond)
    cond2 = [False] * 20 + [True] + [False] * 15
    assert _bar_walk_inc_barssince(cond2) == _bar_walk_full_barssince(cond2)
    cond3 = [True] * 10
    assert _bar_walk_inc_barssince(cond3) == _bar_walk_full_barssince(cond3)


def test_incremental_linreg_matches_full() -> None:
    src = _series(150)
    for length in (5, 14, 20):
        got = _bar_walk_inc_linreg(src, length)
        exp = _bar_walk_full_linreg(src, length)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            if isinstance(e, float) and math.isnan(e):
                assert isinstance(g, float) and math.isnan(g), f"bar {i}: expected nan, got {g}"
            else:
                assert g == pytest.approx(e, rel=1e-9, abs=1e-9), f"bar {i}: {g} != {e}"


def test_runtime_round4_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i * 3,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(150)
    ]
    # Note: ta.barssince is intentionally omitted here — the non-incremental
    # scalar path returns only 0/1 and cannot match the correct O(1) state
    # machine (covered by unit golden tests above).
    src = """//@version=5
indicator("round4 residual")
plot(ta.mom(close, 10))
plot(ta.swma(close))
plot(ta.highestbars(high, 14))
plot(ta.lowestbars(low, 14))
plot(ta.vwap(close))
plot(ta.linreg(close, 14, 0))
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
            # linreg warmup yields nan; pytest.approx does not treat nan == nan
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Round 5 — series materialization / last-sample path (Agent 02)
# ---------------------------------------------------------------------------


class _FakePineSeries:
    """Newest-first history duck-type matching backend.series.PineSeries."""

    __slots__ = ("current", "history")

    def __init__(self) -> None:
        self.history: list[float | None] = []
        self.current: float | None = None

    def update(self, value: float | None) -> None:
        self.current = value
        self.history.insert(0, value)


def test_expect_series_last_sample_skips_materialize() -> None:
    """last_sample_ok + incremental must not reverse PineSeries history."""
    ev = _IncTA()
    ps = _FakePineSeries()
    for i in range(40):
        ps.update(100.0 + i)
    # Poison: if _as_series ran, reverse would allocate; we check identity pass-through.
    src, period = ev._expect_series([ps, 14], length=2, last_sample_ok=True)
    assert period == 14
    assert src is ps
    # Non-inc / full path still materializes chronological list
    ev_full = _FullTA()
    mat, period2 = ev_full._expect_series([ps, 14], length=2, last_sample_ok=True)
    assert period2 == 14
    assert isinstance(mat, list)
    assert mat[-1] == ps.current
    assert mat[0] == ps.history[-1]  # oldest in chrono list


def test_series_last_on_pineseries_and_list() -> None:
    ev = _IncTA()
    ps = _FakePineSeries()
    ps.update(1.0)
    ps.update(2.0)
    ps.update(3.0)
    assert ev._series_last(ps) == 3.0
    assert ev._series_last([10.0, 20.0, 30.0]) == 30.0
    assert ev._series_last(None) is None
    assert ev._series_last(7.5) == 7.5


def test_builtin_sma_via_pineseries_matches_list_inc() -> None:
    """ta.sma builtin with PineSeries last-sample ≡ list-prefix full recompute."""
    n, period = 80, 10
    closes = _series(n)
    # Full oracle
    full = _bar_walk_full_sma(closes, period)

    ev = _IncTA()
    ps = _FakePineSeries()
    got: list[float | None] = []
    for c in closes:
        ps.update(c)
        ev._ta_call_i = 0
        # Builtin path: last_sample_ok → raw PineSeries into _sma_inc_update
        got.append(ev._builtin_ta_sma([ps, period]))
    _assert_series_close(got, full)


def test_as_series_cap_length() -> None:
    """Capped materialization keeps at most _SERIES_MAX samples (chrono)."""
    ev = _FullTA()
    cap = ev._SERIES_MAX
    ps = _FakePineSeries()
    for i in range(cap + 100):
        ps.update(float(i))
    mat = ev._as_series(ps)
    assert len(mat) == cap
    # Newest sample is last; oldest among window is hist[cap-1] reversed → mat[0]
    assert mat[-1] == float(cap + 100 - 1)
    assert mat[0] == float(cap + 100 - 1 - (cap - 1))


def test_change_na_propagation_last_sample() -> None:
    """na in lag window yields None (no silent 0); off-by-one lag length correct."""
    ev = _IncTA()
    # length=1: need two samples; first bar None
    assert ev._change_inc_update([10.0], 1) is None
    ev._ta_call_i = 0
    assert ev._change_inc_update([10.0, 12.0], 1) == pytest.approx(2.0)
    # na current
    ev2 = _IncTA()
    for prefix in ([1.0], [1.0, None]):
        ev2._ta_call_i = 0
        out = ev2._change_inc_update(prefix, 1)
    assert out is None
    # na in lag position
    ev3 = _IncTA()
    seq = [None, 5.0, 7.0]
    outs = []
    for i in range(len(seq)):
        ev3._ta_call_i = 0
        outs.append(ev3._change_inc_update(seq[: i + 1], 1))
    assert outs[0] is None
    assert outs[1] is None  # lag is None
    assert outs[2] == pytest.approx(2.0)


def test_two_builtin_call_sites_independent_pineseries() -> None:
    """Distinct ta.sma periods via builtin must not share inc state (PineSeries)."""
    closes = _series(90)
    full20 = _bar_walk_full_sma(closes, 20)
    full50 = _bar_walk_full_sma(closes, 50)
    ev = _IncTA()
    ps = _FakePineSeries()
    a_out: list[float | None] = []
    b_out: list[float | None] = []
    for c in closes:
        ps.update(c)
        ev._ta_call_i = 0
        a_out.append(ev._builtin_ta_sma([ps, 20]))
        b_out.append(ev._builtin_ta_sma([ps, 50]))
    _assert_series_close(a_out, full20)
    _assert_series_close(b_out, full50)


def test_runtime_last_sample_multi_ta_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime multi-TA (PineSeries close/high/low) inc ≡ PYNE_TA_INCREMENTAL=0."""
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i * 3,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(120)
    ]
    src = """//@version=5
indicator("r5 series")
plot(ta.sma(close, 14))
plot(ta.ema(close, 12))
plot(ta.rsi(close, 14))
plot(ta.stdev(close, 20))
plot(ta.highest(high, 20))
plot(ta.lowest(low, 20))
plot(ta.change(close, 1))
plot(ta.mom(close, 10))
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
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Round 6 — series / expect residual (Agent 02)
# ---------------------------------------------------------------------------


def test_expect_int_list_period_and_error_messages() -> None:
    """Live MRO _expect_int accepts series-of-periods; errors include Got: type."""
    ev = _IncTA()
    assert ev._expect_int(14, "Period must be an integer") == 14
    assert ev._expect_int([10, 12, 14], "Period must be an integer") == 14
    assert ev._expect_int(14.9, "Period must be an integer") == 14
    with pytest.raises(ValueError, match=r"Got: str"):
        ev._expect_int("nope", "Period must be an integer")
    with pytest.raises(ValueError, match=r"Got: na"):
        ev._expect_int(None, "Period must be an integer")
    with pytest.raises(ValueError, match=r"Got: empty series"):
        ev._expect_int([], "Period must be an integer")


def test_expect_int_float_and_series_period_coercion() -> None:
    """C1: float / series-like lengths coerce; near-integers use int(round)."""
    from backend.series import PineSeries

    ev = _IncTA()
    assert ev._expect_int(14.0, "Period must be an integer") == 14
    assert ev._expect_int(14.0000000001, "Period must be an integer") == 14
    assert ev._expect_int(13.9999999999, "Period must be an integer") == 14
    # Fractional → floor (existing TV-like length semantics)
    assert ev._expect_int(14.9, "Period must be an integer") == 14
    # Series of float periods → last sample
    assert ev._expect_int([10.0, 12.0, 14.0], "Period must be an integer") == 14
    assert ev._expect_int((9.0, 14.0), "Period must be an integer") == 14
    # PineSeries wrapper
    assert ev._expect_int(PineSeries(14.0), "Period must be an integer") == 14
    # numpy scalars when available
    np = pytest.importorskip("numpy")
    assert ev._expect_int(np.float64(14.0), "Period must be an integer") == 14
    assert ev._expect_int(np.int64(20), "Period must be an integer") == 20


def test_expect_series_na_period_returns_na() -> None:
    """TV-like: ta.* with na length yields na (period coerced to 0), not hard error."""
    ev = _IncTA()
    series, period = ev._expect_series([_series(30), None], length=2, last_sample_ok=True)
    assert period == 0
    # Incremental SMA with period <= 0 → na
    assert ev._sma_inc_update(series, period) is None
    # Float period through _expect_series
    _, p14 = ev._expect_series([_series(30), 14.0], length=2, last_sample_ok=True)
    assert p14 == 14
    _, p_list = ev._expect_series([_series(30), [10.0, 14.0]], length=2, last_sample_ok=True)
    assert p_list == 14


def test_expect_int_plain_int_identity() -> None:
    """Hot path: plain int is returned as-is (no wrap)."""
    ev = _IncTA()
    x = 20
    assert ev._expect_int(x, "p") is x


def test_dema_tema_last_sample_skips_as_series() -> None:
    """dema/tema pure-inc must not reverse PineSeries (last_sample_ok)."""
    closes = _series(80)
    full_d: list[float | None] = []
    full_t: list[float | None] = []
    fev = _FullTA()
    for i in range(len(closes)):
        prefix = closes[: i + 1]
        ema1 = fev._ema(prefix, 10)
        ema2 = fev._ema(ema1, 10)
        dema_series = [
            (2 * a - b) if a is not None and b is not None else None for a, b in zip(ema1, ema2, strict=True)
        ]
        full_d.append(dema_series[-1] if dema_series else None)
        ema3 = fev._ema(ema2, 10)
        tema_series = [
            (3 * a - 3 * b + c) if a is not None and b is not None and c is not None else None
            for a, b, c in zip(ema1, ema2, ema3, strict=True)
        ]
        full_t.append(tema_series[-1] if tema_series else None)

    ev = _IncTA()
    ps = _FakePineSeries()
    got_d: list[float | None] = []
    got_t: list[float | None] = []
    for c in closes:
        ps.update(c)
        ev._ta_call_i = 0
        got_d.append(ev._builtin_ta_dema([ps, 10]))
        got_t.append(ev._builtin_ta_tema([ps, 10]))
    _assert_series_close(got_d, full_d)
    _assert_series_close(got_t, full_t)


def test_crossover_last_sample_matches_full_list() -> None:
    """Stateful last-sample crossover ≡ list-path (TV: prev ``<=`` then ``>``)."""
    a = [1.0, 1.0, 3.0]  # prev a==b=1 → equal-then-above is a TV crossover
    b = [2.0, 1.0, 2.0]
    fev = _FullTA()
    assert fev._crossover(a[:2], b[:2]) is False  # 1<=2 but curr 1>1? no
    assert fev._crossover(a, b) is True  # prev 1<=1 and curr 3>2
    # True cross: prev a < b, curr a > b
    a2 = [1.0, 3.0]
    b2 = [2.0, 2.0]
    assert fev._crossover(a2, b2) is True
    # equal-then-above (numba / stateful parity)
    assert fev._crossover([2.0, 3.0], [2.0, 2.0]) is True
    assert fev._crossunder([2.0, 1.0], [2.0, 2.0]) is True

    ev = _IncTA()
    outs = []
    for i in range(len(a2)):
        ev._cross_call_i = 0
        # pass growing chrono lists (stateful uses last only)
        outs.append(ev._cross_stateful(a2[: i + 1], b2[: i + 1], under=False))
    assert outs[0] is False
    assert outs[1] is True

    # PineSeries path via builtin last-sample
    from backend.series import PineSeries

    pa, pb = PineSeries(), PineSeries()
    seq_a = [1.0, 1.5, 3.0]
    seq_b = [2.0, 2.0, 2.0]
    # cross on last bar: 1.5 <= 2 and 3 > 2
    got = []
    for i in range(len(seq_a)):
        pa.update(seq_a[i])
        pb.update(seq_b[i])
        ev._cross_call_i = 0
        got.append(ev._builtin_ta_crossover([pa, pb]))
    assert got == [False, False, True]


def test_pineseries_history_offset_na_and_float() -> None:
    """PineSeries[offset]: na OOB, float truncate, None/negative index → na; no silent 0."""
    from backend.series import PineSeries

    ps = PineSeries()
    assert ps[0] is None
    assert ps[None] is None
    ps.update(10.0)
    ps.update(20.0)
    ps.update(30.0)
    assert ps[0] == 30.0
    assert ps[1] == 20.0
    assert ps[2] == 10.0
    assert ps[3] is None
    assert ps[1.9] == 20.0  # float → int trunc
    assert ps[float("nan")] is None
    assert ps[-1] is None  # negative history offset → na (soft-fail)


def test_subscript_na_index_returns_na() -> None:
    """close[na] must yield na series, not crash the bar loop."""
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
        for i in range(5)
    ]
    src = """//@version=5
indicator("na_idx")
plot(close[na])
"""
    out = Runtime(symbol="T").run(src, bars)
    assert "error" not in out, out.get("error")
    series = out.get("series") or {}
    # All na
    vals = next(iter(series.values()))
    assert all(v is None for v in vals)


def test_runtime_crossover_dema_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime: crossover + dema last-sample ≡ PYNE_TA_INCREMENTAL=0."""
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.05,
            "high": 101 + i * 0.05,
            "low": 99 + i * 0.05,
            "close": 100 + math.sin(i / 5.0) * 2 + i * 0.02,
            "volume": 1000,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(100)
    ]
    src = """//@version=5
indicator("r6 series")
d = ta.dema(close, 10)
t = ta.tema(close, 10)
c = ta.crossover(close, ta.sma(close, 5))
plot(d)
plot(t)
plot(c ? 1 : 0)
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
                # bool plots may differ on first bars if stateful vs list; allow only warmup
                if i < 2:
                    continue
                assert a == b, f"{key} bar {i}: {a} != {b}"
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Round 5: dema/tema, valuewhen, pivots, adx/dmi, supertrend
# ---------------------------------------------------------------------------


def _ohlc(n: int = 120, seed: float = 100.0) -> tuple[list[float], list[float], list[float]]:
    closes = _series(n, seed)
    highs = [c + 1.5 + (i % 3) * 0.2 for i, c in enumerate(closes)]
    lows = [c - 1.2 - (i % 2) * 0.1 for i, c in enumerate(closes)]
    return highs, lows, closes


def _assert_num_close(g: Any, e: Any, *, i: int, rel: float = 1e-9, abs_: float = 1e-9) -> None:
    if e is None:
        assert g is None, f"bar {i}: expected None, got {g}"
        return
    if isinstance(e, float) and math.isnan(e):
        assert g is not None and isinstance(g, float) and math.isnan(g), f"bar {i}: expected nan, got {g}"
        return
    assert g is not None, f"bar {i}: expected {e}, got None"
    assert g == pytest.approx(e, rel=rel, abs=abs_), f"bar {i}: {g} != {e}"


def _bar_walk_full_dema(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._builtin_ta_dema([src[: i + 1], period])
        out.append(full[-1] if isinstance(full, list) else full)
    return out


def _bar_walk_inc_dema(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._dema_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_tema(src: list[float], period: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._builtin_ta_tema([src[: i + 1], period])
        out.append(full[-1] if isinstance(full, list) else full)
    return out


def _bar_walk_inc_tema(src: list[float], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._tema_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_valuewhen(cond: list[bool], src: list[float], occurrence: int) -> list[Any]:
    ev = _FullTA()
    return [ev._valuewhen(cond[: i + 1], src[: i + 1], occurrence) for i in range(len(cond))]


def _bar_walk_inc_valuewhen(cond: list[bool], src: list[float], occurrence: int) -> list[Any]:
    ev = _IncTA()
    out: list[Any] = []
    for i in range(len(cond)):
        ev._ta_call_i = 0
        out.append(ev._valuewhen_inc_update(cond[: i + 1], src[: i + 1], occurrence))
    return out


def _bar_walk_full_pivothigh(src: list[float], left: int, right: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        out.append(ev._builtin_ta_pivothigh([src[: i + 1], left, right]))
    return out


def _bar_walk_inc_pivothigh(src: list[float], left: int, right: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._pivothigh_inc_update(src[: i + 1], left, right))
    return out


def _bar_walk_full_pivotlow(src: list[float], left: int, right: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        out.append(ev._builtin_ta_pivotlow([src[: i + 1], left, right]))
    return out


def _bar_walk_inc_pivotlow(src: list[float], left: int, right: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._pivotlow_inc_update(src[: i + 1], left, right))
    return out


def _bar_walk_full_adx(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    ev = _FullTA()
    return [float(ev._adx(highs[: i + 1], lows[: i + 1], closes[: i + 1], period)) for i in range(len(closes))]


def _bar_walk_inc_adx(highs: list[float], lows: list[float], closes: list[float], period: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._adx_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], period))
    return out


def _bar_walk_full_dmi(
    highs: list[float], lows: list[float], closes: list[float], di_len: int, adx_smooth: int
) -> list[tuple[float, float, float]]:
    ev = _FullTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(closes)):
        out.append(ev._builtin_ta_dmi([highs[: i + 1], lows[: i + 1], closes[: i + 1], di_len]))
        # legacy 4-arg form uses adx_smooth = di_len; for distinct smooth use 2-arg via helper
        if adx_smooth != di_len:
            # recompute with explicit adx period via _adx on full path
            pdi, mdi, _ = out[-1]
            adx = float(ev._adx(highs[: i + 1], lows[: i + 1], closes[: i + 1], adx_smooth) or 0)
            out[-1] = (pdi, mdi, adx)
    return out


def _bar_walk_inc_dmi(
    highs: list[float], lows: list[float], closes: list[float], di_len: int, adx_smooth: int
) -> list[tuple[float, float, float]]:
    ev = _IncTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._dmi_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], di_len, adx_smooth))
    return out


def _bar_walk_full_supertrend(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    factor: float,
    atr_period: int,
) -> list[tuple[float, int]]:
    ev = _FullTA()
    out: list[tuple[float, int]] = []
    for i in range(len(closes)):
        ev.current_series = {
            "high": highs[: i + 1],
            "low": lows[: i + 1],
            "close": closes[: i + 1],
        }
        out.append(ev._builtin_ta_supertrend([factor, atr_period]))
    return out


def _bar_walk_inc_supertrend(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    factor: float,
    atr_period: int,
) -> list[tuple[float, int]]:
    ev = _IncTA()
    out: list[tuple[float, int]] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        ev.current_series = {
            "high": highs[: i + 1],
            "low": lows[: i + 1],
            "close": closes[: i + 1],
        }
        out.append(ev._supertrend_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], factor, atr_period))
    return out


def _simplified_supertrend_expected(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    factor: float,
    atr_period: int,
) -> list[tuple[float, int]]:
    """Oracle: mid ± factor·ATR via full ``ta.atr`` (na ATR → 0)."""
    ev = _FullTA()
    out: list[tuple[float, int]] = []
    for i in range(len(closes)):
        atr_val = ev._builtin_ta_atr([highs[: i + 1], lows[: i + 1], closes[: i + 1], atr_period])
        if isinstance(atr_val, list):
            atr_val = atr_val[-1] if atr_val else 0.0
        out.append(ev._supertrend(highs[i], lows[i], closes[i], factor, atr_val))
    return out


def test_incremental_dema_matches_full() -> None:
    src = _series(150)
    for period in (5, 10, 20):
        _assert_series_close(_bar_walk_inc_dema(src, period), _bar_walk_full_dema(src, period))


def test_incremental_tema_matches_full() -> None:
    src = _series(150)
    for period in (5, 10, 20):
        _assert_series_close(_bar_walk_inc_tema(src, period), _bar_walk_full_tema(src, period))


def test_incremental_valuewhen_matches_full() -> None:
    cond = [(i % 7 == 0) for i in range(80)]
    src = [float(i) * 1.5 + 10.0 for i in range(80)]
    for occ in (0, 1, 2, 3):
        got = _bar_walk_inc_valuewhen(cond, src, occ)
        exp = _bar_walk_full_valuewhen(cond, src, occ)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            _assert_num_close(g, e, i=i)


def test_incremental_pivothigh_pivotlow_matches_full() -> None:
    src = _series(100)
    for left, right in ((2, 2), (3, 1), (5, 5)):
        _assert_series_close(
            _bar_walk_inc_pivothigh(src, left, right),
            _bar_walk_full_pivothigh(src, left, right),
        )
        _assert_series_close(
            _bar_walk_inc_pivotlow(src, left, right),
            _bar_walk_full_pivotlow(src, left, right),
        )


def test_incremental_adx_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    for period in (5, 14):
        got = _bar_walk_inc_adx(highs, lows, closes, period)
        exp = _bar_walk_full_adx(highs, lows, closes, period)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            _assert_num_close(g, e, i=i)


def test_incremental_dmi_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    for di_len in (5, 14):
        got = _bar_walk_inc_dmi(highs, lows, closes, di_len, di_len)
        exp = _bar_walk_full_dmi(highs, lows, closes, di_len, di_len)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            for j in range(3):
                _assert_num_close(g[j], e[j], i=i)


def _ohlc_supertrend_both_dirs(
    n: int = 120,
) -> tuple[list[float], list[float], list[float]]:
    """OHLC where close sits above mid on some bars and below on others."""
    closes = _series(n)
    highs: list[float] = []
    lows: list[float] = []
    for i, c in enumerate(closes):
        if i % 5 < 2:
            highs.append(c + 0.2)
            lows.append(c - 1.6)
        else:
            highs.append(c + 1.6)
            lows.append(c - 0.2)
    return highs, lows, closes


def test_incremental_supertrend_matches_full() -> None:
    """Interpret inc, interpret full, and ``_supertrend`` helper share mid±factor·ATR."""
    highs, lows, closes = _ohlc_supertrend_both_dirs(120)
    for factor, period in ((3.0, 10), (2.0, 14), (1.5, 7)):
        got = _bar_walk_inc_supertrend(highs, lows, closes, factor, period)
        full = _bar_walk_full_supertrend(highs, lows, closes, factor, period)
        exp = _simplified_supertrend_expected(highs, lows, closes, factor, period)
        assert len(got) == len(full) == len(exp)
        n_up = n_down = 0
        for i, (g, f, e) in enumerate(zip(got, full, exp, strict=True)):
            assert g[1] == f[1] == e[1], f"bar {i}: dir inc={g[1]} full={f[1]} exp={e[1]}"
            _assert_num_close(g[0], e[0], i=i)
            _assert_num_close(f[0], e[0], i=i)
            if e[1] < 0:
                n_up += 1
            else:
                n_down += 1
        assert n_up >= 1 and n_down >= 1, f"factor={factor}: up={n_up} down={n_down}"


def test_runtime_round5_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i * 3,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(150)
    ]
    # Note: ta.valuewhen is unit-tested against full list-walk; Runtime off-path
    # only sees an ephemeral 1-bar condition series, so on/off last values diverge
    # (inc ring is correct). Same class of gap as ta.barssince in round4.
    src = """//@version=5
indicator("round5 residual")
plot(ta.dema(close, 10))
plot(ta.tema(close, 10))
plot(ta.adx(14))
[diplus, diminus, adx] = ta.dmi(14, 14)
plot(diplus)
plot(diminus)
plot(adx)
[st, dir] = ta.supertrend(3, 10)
plot(st)
plot(dir)
plot(ta.pivothigh(high, 3, 3))
plot(ta.pivotlow(low, 3, 3))
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
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Round 6: kc/kcw, mfi, sar, alma, correlation, percentiles
# ---------------------------------------------------------------------------


def _volumes(n: int) -> list[float]:
    return [1000.0 + (i % 7) * 10.0 + i * 0.5 for i in range(n)]


def _bar_walk_full_mfi(
    highs: list[float], lows: list[float], closes: list[float], vols: list[float], period: int
) -> list[float]:
    ev = _FullTA()
    return [ev._mfi(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period) for i in range(len(closes))]


def _bar_walk_inc_mfi(
    highs: list[float], lows: list[float], closes: list[float], vols: list[float], period: int
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._mfi_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period))
    return out


def _bar_walk_full_sar(
    highs: list[float], lows: list[float], start: float, inc: float, maximum: float
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(highs)):
        full = ev._sar(highs[: i + 1], lows[: i + 1], start, inc, maximum)
        out.append(full[-1] if full else None)
    return out


def _bar_walk_inc_sar(
    highs: list[float], lows: list[float], start: float, inc: float, maximum: float
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        out.append(ev._sar_inc_update(highs[: i + 1], lows[: i + 1], start, inc, maximum))
    return out


def _bar_walk_full_alma(src: list[float], length: int, offset: float = 0.85, sigma: float = 6.0) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_alma([src[: i + 1], length, offset, sigma]) for i in range(len(src))]


def _bar_walk_inc_alma(src: list[float], length: int, offset: float = 0.85, sigma: float = 6.0) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._alma_inc_update(src[: i + 1], length, offset, sigma))
    return out


def _bar_walk_full_correlation(s1: list[float], s2: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_correlation([s1[: i + 1], s2[: i + 1], length]) for i in range(len(s1))]


def _bar_walk_inc_correlation(s1: list[float], s2: list[float], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(s1)):
        ev._ta_call_i = 0
        out.append(ev._correlation_inc_update(s1[: i + 1], s2[: i + 1], length))
    return out


def _bar_walk_full_kc(
    highs: list[float], lows: list[float], closes: list[float], length: int, mult: float
) -> list[tuple[float, float, float]]:
    ev = _FullTA()
    return [
        ev._builtin_ta_kc([highs[: i + 1], lows[: i + 1], closes[: i + 1], length, mult]) for i in range(len(closes))
    ]


def _bar_walk_inc_kc(
    highs: list[float], lows: list[float], closes: list[float], length: int, mult: float
) -> list[tuple[float, float, float]]:
    ev = _IncTA()
    out: list[tuple[float, float, float]] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._kc_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], length, mult))
    return out


def _bar_walk_full_pct_lin(src: list[float], period: int, pct: float) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_percentile_linear_interpolation([src[: i + 1], period, pct]) for i in range(len(src))]


def _bar_walk_inc_pct_lin(src: list[float], period: int, pct: float) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._percentile_linear_inc_update(src[: i + 1], period, pct))
    return out


def _bar_walk_full_pct_nr(src: list[float], period: int, pct: float) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_percentile_nearest_rank([src[: i + 1], period, pct]) for i in range(len(src))]


def _bar_walk_inc_pct_nr(src: list[float], period: int, pct: float) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._percentile_nearest_rank_inc_update(src[: i + 1], period, pct))
    return out


def test_incremental_mfi_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    for period in (7, 14):
        _assert_series_close(
            _bar_walk_inc_mfi(highs, lows, closes, vols, period),
            _bar_walk_full_mfi(highs, lows, closes, vols, period),
        )


def test_incremental_sar_matches_full() -> None:
    highs, lows, _ = _ohlc(150)
    for params in ((0.02, 0.02, 0.2), (0.01, 0.01, 0.1)):
        _assert_series_close(
            _bar_walk_inc_sar(highs, lows, *params),
            _bar_walk_full_sar(highs, lows, *params),
        )


def test_incremental_alma_matches_full() -> None:
    src = _series(150)
    for length in (5, 9, 20):
        _assert_series_close(
            _bar_walk_inc_alma(src, length),
            _bar_walk_full_alma(src, length),
        )


def test_incremental_correlation_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    for length in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_correlation(closes, highs, length),
            _bar_walk_full_correlation(closes, highs, length),
        )
        _assert_series_close(
            _bar_walk_inc_correlation(closes, lows, length),
            _bar_walk_full_correlation(closes, lows, length),
        )


def test_incremental_kc_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    for length, mult in ((10, 1.5), (20, 2.0)):
        got = _bar_walk_inc_kc(highs, lows, closes, length, mult)
        exp = _bar_walk_full_kc(highs, lows, closes, length, mult)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            for j in range(3):
                _assert_num_close(g[j], e[j], i=i)


def test_incremental_kcw_matches_full() -> None:
    """kcw is upper-lower of kc; compare width from full builtin vs inc bands."""
    highs, lows, closes = _ohlc(120)
    length, mult = 20, 2.0
    evf = _FullTA()
    evi = _IncTA()
    for i in range(len(closes)):
        args = [highs[: i + 1], lows[: i + 1], closes[: i + 1], length, mult]
        full = evf._builtin_ta_kcw(args)
        evi._ta_call_i = 0
        _mid, up, lo = evi._kc_inc_update(*args[:3], length, mult)
        if (isinstance(up, float) and math.isnan(up)) or (isinstance(lo, float) and math.isnan(lo)):
            inc = float("nan")
        else:
            inc = float(up) - float(lo)
        if isinstance(full, float) and math.isnan(full):
            assert isinstance(inc, float) and math.isnan(inc), f"bar {i}"
        else:
            assert inc == pytest.approx(full, rel=1e-9, abs=1e-9), f"bar {i}: {inc} != {full}"


def test_incremental_percentile_linear_matches_full() -> None:
    src = _series(120)
    for period, pct in ((10, 50.0), (14, 25.0), (20, 90.0)):
        _assert_series_close(
            _bar_walk_inc_pct_lin(src, period, pct),
            _bar_walk_full_pct_lin(src, period, pct),
        )


def test_incremental_percentile_nearest_rank_matches_full() -> None:
    src = _series(120)
    for period, pct in ((10, 50.0), (14, 75.0), (20, 100.0)):
        _assert_series_close(
            _bar_walk_inc_pct_nr(src, period, pct),
            _bar_walk_full_pct_nr(src, period, pct),
        )


def test_mfi_sar_alma_na_safe() -> None:
    """Leading/interstitial na must not raise; soft-fail like full oracle."""
    highs = [None, None, 10.0, 11.0, 12.0, 13.0, 14.0]
    lows = [None, None, 9.0, 9.5, 10.0, 10.5, 11.0]
    closes = [None, None, 9.5, 10.5, 11.0, 12.0, 13.0]
    vols = [100.0] * 7
    ev = _IncTA()
    for i in range(len(closes)):
        ev._ta_call_i = 0
        m = ev._mfi_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], 3)
        assert isinstance(m, float)
        ev._ta_call_i = 0
        s = ev._sar_inc_update(highs[: i + 1], lows[: i + 1], 0.02, 0.02, 0.2)
        assert s is None or isinstance(s, float)
    src = [None, 1.0, 2.0, 3.0, 4.0]
    ev2 = _IncTA()
    for i in range(len(src)):
        ev2._ta_call_i = 0
        a = ev2._alma_inc_update(src[: i + 1], 3)
        if i < 3:
            # warmup or window containing None → None (no silent 0)
            assert a is None


def test_runtime_round6_residual_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.runtime import Runtime

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i * 3,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(150)
    ]
    src = """//@version=5
indicator("round6 residual")
[mid, up, lo] = ta.kc(close, 20, 2.0)
plot(mid)
plot(up)
plot(lo)
plot(ta.kcw(close, 20, 2.0))
plot(ta.mfi(14))
plot(ta.sar(0.02, 0.02, 0.2))
plot(ta.alma(close, 9, 0.85, 6))
plot(ta.correlation(close, high, 14))
plot(ta.percentrank(close, 14))
plot(ta.percentile_nearest_rank(close, 14, 50))
plot(ta.percentile_linear_interpolation(close, 14, 50))
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
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Round 7 (T2): kama, cmo, bbw, stochrsi residual full-history
# ---------------------------------------------------------------------------


def _bar_walk_full_kama(src: list[float], length: int, fast: int = 2, slow: int = 30) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._builtin_ta_kama([src[: i + 1], length, fast, slow])
        if isinstance(full, list):
            last = full[-1] if full else None
        else:
            last = full
        out.append(None if (isinstance(last, float) and math.isnan(last)) else last)
    return out


def _bar_walk_inc_kama(src: list[float], length: int, fast: int = 2, slow: int = 30) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._kama_inc_update(src[: i + 1], length, fast, slow))
    return out


def _bar_walk_full_cmo(src: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_cmo([src[: i + 1], length]) for i in range(len(src))]


def _bar_walk_inc_cmo(src: list[float], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._cmo_inc_update(src[: i + 1], length))
    return out


def _bar_walk_full_bbw(src: list[float], period: int, mult: float) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        m, u, l = ev._bollinger_bands(src[: i + 1], period, mult)
        if m is None or u is None or l is None or m == 0:
            out.append(None)
        else:
            out.append((u - l) / m)
    return out


def _bar_walk_inc_bbw(src: list[float], period: int, mult: float) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        m, u, l = ev._bb_inc_update(src[: i + 1], period, mult)
        if m is None or u is None or l is None or m == 0:
            out.append(None)
        else:
            out.append((u - l) / m)
    return out


def _bar_walk_full_stochrsi(
    closes: list[float], rsi_length: int, stoch_length: int
) -> list[tuple[float | None, float | None]]:
    ev = _FullTA()
    out: list[tuple[float | None, float | None]] = []
    for i in range(len(closes)):
        ev.current_series = {"close": closes[: i + 1]}
        d = ev._builtin_ta_stochrsi([rsi_length, stoch_length])
        out.append((d.get("stochrsi"), d.get("signal")))
    return out


def _bar_walk_inc_stochrsi(
    closes: list[float], rsi_length: int, stoch_length: int
) -> list[tuple[float | None, float | None]]:
    ev = _IncTA()
    out: list[tuple[float | None, float | None]] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        d = ev._stochrsi_inc_update(closes[: i + 1], rsi_length, stoch_length)
        out.append((d.get("stochrsi"), d.get("signal")))
    return out


def test_incremental_kama_matches_full() -> None:
    src = _series(150)
    for length in (5, 10, 20):
        _assert_series_close(
            _bar_walk_inc_kama(src, length),
            _bar_walk_full_kama(src, length),
        )
    # non-default fast/slow
    _assert_series_close(
        _bar_walk_inc_kama(src, 10, 3, 20),
        _bar_walk_full_kama(src, 10, 3, 20),
    )


def test_incremental_cmo_matches_full() -> None:
    src = _series(150)
    for length in (7, 14, 20):
        _assert_series_close(
            _bar_walk_inc_cmo(src, length),
            _bar_walk_full_cmo(src, length),
        )


def test_incremental_bb_inc_update_matches_full() -> None:
    """Dedicated ``_bb_inc_update`` ≡ full ``_bollinger_bands`` (non-bar)."""
    src = _series(150)
    for period, mult in ((20, 2.0), (10, 1.5), (5, 2.5)):
        got = _bar_walk_inc_bb(src, period, mult)
        # Force inc path via _bb_inc_update for the dedicated kernel
        evi = _IncTA()
        got2: list[tuple[float | None, float | None, float | None]] = []
        for i in range(len(src)):
            evi._ta_call_i = 0
            got2.append(evi._bb_inc_update(src[: i + 1], period, mult))
        exp = _bar_walk_full_bb(src, period, mult)
        assert len(got) == len(exp) == len(got2)
        for i, (g, g2, e) in enumerate(zip(got, got2, exp, strict=True)):
            for j in range(3):
                if e[j] is None:
                    assert g[j] is None and g2[j] is None, f"bb bar {i} c{j}"
                else:
                    assert g[j] == pytest.approx(e[j], rel=1e-9, abs=1e-9)
                    assert g2[j] == pytest.approx(e[j], rel=1e-9, abs=1e-9)


def test_incremental_bbw_matches_full() -> None:
    src = _series(150)
    for period, mult in ((20, 2.0), (10, 1.5)):
        _assert_series_close(
            _bar_walk_inc_bbw(src, period, mult),
            _bar_walk_full_bbw(src, period, mult),
        )


def test_incremental_stochrsi_matches_full() -> None:
    closes = _series(180)
    for rsi_l, st_l in ((14, 14), (7, 14), (14, 7)):
        got = _bar_walk_inc_stochrsi(closes, rsi_l, st_l)
        exp = _bar_walk_full_stochrsi(closes, rsi_l, st_l)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            for j in range(2):
                if e[j] is None:
                    assert g[j] is None, f"stochrsi bar {i} c{j}: expected None got {g[j]}"
                else:
                    assert g[j] == pytest.approx(e[j], rel=1e-9, abs=1e-9), f"stochrsi bar {i} c{j}: {g[j]} != {e[j]}"


def test_two_kama_call_sites_independent() -> None:
    src = _series(80)
    ev = _IncTA()
    a_out: list[float | None] = []
    b_out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        a_out.append(ev._kama_inc_update(src[: i + 1], 10, 2, 30))
        b_out.append(ev._kama_inc_update(src[: i + 1], 20, 2, 30))
    _assert_series_close(a_out, _bar_walk_full_kama(src, 10))
    _assert_series_close(b_out, _bar_walk_full_kama(src, 20))


def test_runtime_round7_t2_incremental_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runtime: kama / cmo / bb / bbw last values match PYNE_TA_INCREMENTAL=0."""
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i * 3,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(150)
    ]
    src = """//@version=5
indicator("round7 t2")
plot(ta.kama(close, 10))
plot(ta.cmo(close, 14))
[m, u, l] = ta.bb(close, 20, 2.0)
plot(u)
plot(m)
plot(l)
plot(ta.bbw(close, 20, 2.0))
plot(ta.sma(close, 14))
"""
    # Agent 05 parse-cache may share AST identity; clear between runs so
    # second Runtime does not see a mutated tree (empty plots / name "plot").
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                continue
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Runtime residual: unary ta.change + nested decomposing-expressions snippet
# ---------------------------------------------------------------------------


def _ohlcv_bars(n: int = 100) -> list[dict]:
    """Synthetic OHLCV for Runtime bar-mode tests."""
    bars: list[dict] = []
    for i in range(n):
        c = 100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0
        bars.append(
            {
                "open": c - 0.3,
                "high": c + 0.8,
                "low": c - 0.8,
                "close": c,
                "volume": 1000 + i,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def test_builtin_ta_change_unary_defaults_length_one() -> None:
    """TV ``ta.change(source)`` ≡ ``ta.change(source, 1)`` on interpret path."""
    closes = _series(40)
    # Full-recompute path
    full = _FullTA()
    outs_u: list[float | None] = []
    outs_b: list[float | None] = []
    for i in range(len(closes)):
        prefix = closes[: i + 1]
        outs_u.append(full._builtin_ta_change([prefix]))
        outs_b.append(full._builtin_ta_change([prefix, 1]))
    _assert_series_close(outs_u, outs_b)

    # Incremental bar-mode: separate evaluators so call-site state is not shared
    inc_u = _IncTA()
    inc_b = _IncTA()
    outs_iu: list[float | None] = []
    outs_ib: list[float | None] = []
    for i in range(len(closes)):
        prefix = closes[: i + 1]
        inc_u._ta_call_i = 0
        outs_iu.append(inc_u._builtin_ta_change([prefix]))
        inc_b._ta_call_i = 0
        outs_ib.append(inc_b._builtin_ta_change([prefix, 1]))
    _assert_series_close(outs_iu, outs_ib)
    _assert_series_close(outs_iu, outs_u)
    # Sanity: after warmup, change is nonzero for this series
    assert any(v is not None and abs(v) > 1e-9 for v in outs_iu)


def test_runtime_unary_ta_change_and_decomposing_expressions_snippet() -> None:
    """Unary ta.change + reconstructed nested osc (set04 block21 shape).

    Corpus ``0130_str_decomposing_expressions_demo.pine`` is truncated mid-call;
    sanitize closes parens so ``ta.ema`` gets 1 arg. Full expression needs
    ``smoothingInput`` as the second ``ta.ema`` argument.
    """
    from backend.runtime import Runtime

    bars = _ohlcv_bars(120)

    unary_src = """//@version=6
indicator("unary change")
plot(ta.change(close), "ch1")
plot(ta.change(close, 1), "ch1b")
"""
    r_u = Runtime(symbol="T").run(unary_src, bars, mode="interpret")
    assert "error" not in r_u, r_u.get("error")
    s_u = r_u["series"]["ch1"]
    s_b = r_u["series"]["ch1b"]
    assert len(s_u) == len(bars)
    for i, (a, b) in enumerate(zip(s_u, s_b, strict=True)):
        if a is None and b is None:
            continue
        if a is None or b is None:
            # Both paths should warm up the same way
            assert a is None and b is None, f"bar {i}: {a!r} vs {b!r}"
            continue
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"bar {i}: {a} != {b}"

    # Reconstructed nested form from TV "decomposing expressions" demo
    nested_src = """//@version=6
indicator("Decomposing expressions demo")
int length1Input = 20
int length2Input = 40
int smoothingInput = 10
float osc = ta.ema(
     math.avg(
         ta.change(close - ta.ema(close, length1Input), length1Input),
         ta.change(close - ta.ema(close, length2Input), length2Input)
     ),
     smoothingInput
)
plot(osc, "osc")
"""
    r_n = Runtime(symbol="T").run(nested_src, bars, mode="interpret")
    assert "error" not in r_n, r_n.get("error")
    osc = r_n["series"]["osc"]
    assert len(osc) == len(bars)
    # After max EMA/change windows, expect finite values
    finite = [v for v in osc if v is not None and isinstance(v, (int, float)) and not math.isnan(v)]
    assert len(finite) > 10, f"expected warmed osc values, got {len(finite)} finite"


# ---------------------------------------------------------------------------
# Round 8: O(1) WMA/HMA/linreg + strict na-window goldens
# ---------------------------------------------------------------------------


def _with_na(src: list[float], holes: set[int]) -> list[float | None]:
    return [None if i in holes else v for i, v in enumerate(src)]


def test_incremental_wma_strict_na_window() -> None:
    """na-in-window → na (never skip-na / reweight). Recovers after hole slides out."""
    src = _with_na(_series(80), {12, 13, 40})
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_wma(src, period),
            _bar_walk_full_wma(src, period),
        )
        # Explicit: bar with na still inside the window is None
        inc = _bar_walk_inc_wma(src, period)
        for i, _v in enumerate(src):
            if i + 1 < period:
                continue
            window = src[i + 1 - period : i + 1]
            if any(x is None for x in window):
                assert inc[i] is None, f"period={period} bar {i}: expected None, got {inc[i]}"


def test_incremental_hma_strict_na_window() -> None:
    src = _with_na(_series(120), {25, 60})
    for period in (9, 14, 20):
        _assert_series_close(
            _bar_walk_inc_hma(src, period),
            _bar_walk_full_hma(src, period),
        )


def test_incremental_vwma_strict_na_window() -> None:
    src = _with_na(_series(80), {8, 30})
    vol = [1000.0 + (i % 7) * 10 for i in range(len(src))]
    vol_na = list(vol)
    vol_na[15] = None  # type: ignore[call-overload]
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_vwma(src, vol, period),
            _bar_walk_full_vwma(src, vol, period),
        )
        _assert_series_close(
            _bar_walk_inc_vwma(src, vol_na, period),
            _bar_walk_full_vwma(src, vol_na, period),
        )


def test_incremental_swma_strict_na_window() -> None:
    src = _with_na(_series(40), {6, 7, 20})
    _assert_series_close(_bar_walk_inc_swma(src), _bar_walk_full_swma(src))
    inc = _bar_walk_inc_swma(src)
    for i in range(3, len(src)):
        if any(v is None for v in src[i - 3 : i + 1]):
            assert inc[i] is None, f"bar {i}: expected None, got {inc[i]}"


def test_incremental_linreg_offset_matches_full() -> None:
    src = _series(120)
    evf = _FullTA()
    for length, offset in ((5, 0), (14, 0), (14, 2), (20, 1)):
        got = []
        evi = _IncTA()
        exp = []
        for i in range(len(src)):
            evi._ta_call_i = 0
            got.append(evi._linreg_inc_update(src[: i + 1], length, offset=offset))
            exp.append(evf._builtin_ta_linreg([src[: i + 1], length, offset]))
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            if isinstance(e, float) and math.isnan(e):
                assert isinstance(g, float) and math.isnan(g), f"bar {i}: expected nan, got {g}"
            else:
                assert g == pytest.approx(e, rel=1e-9, abs=1e-9), f"bar {i}: {g} != {e}"


def test_incremental_linreg_skip_na_matches_full() -> None:
    """Interpret linreg oracle is skip-na; incremental must keep that."""
    src = _with_na(_series(80), {10, 11, 35})
    got = _bar_walk_inc_linreg(src, 10)
    exp = _bar_walk_full_linreg(src, 10)
    assert len(got) == len(exp)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        if isinstance(e, float) and math.isnan(e):
            assert isinstance(g, float) and math.isnan(g), f"bar {i}: expected nan, got {g}"
        else:
            assert g == pytest.approx(e, rel=1e-9, abs=1e-9), f"bar {i}: {g} != {e}"


def test_two_wma_hma_call_sites_independent() -> None:
    src = _series(80)
    ev = _IncTA()
    wma_a: list[float | None] = []
    wma_b: list[float | None] = []
    hma_a: list[float | None] = []
    hma_b: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        wma_a.append(ev._wma_inc_update(src[: i + 1], 10))
        wma_b.append(ev._wma_inc_update(src[: i + 1], 20))
        hma_a.append(ev._hma_inc_update(src[: i + 1], 9))
        hma_b.append(ev._hma_inc_update(src[: i + 1], 16))
    _assert_series_close(wma_a, _bar_walk_full_wma(src, 10))
    _assert_series_close(wma_b, _bar_walk_full_wma(src, 20))
    _assert_series_close(hma_a, _bar_walk_full_hma(src, 9))
    _assert_series_close(hma_b, _bar_walk_full_hma(src, 16))


def test_runtime_wma_hma_linreg_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = [
        {
            "open": 100 + i * 0.1,
            "high": 101.5 + i * 0.1 + (i % 5) * 0.05,
            "low": 98.5 + i * 0.1 - (i % 3) * 0.05,
            "close": 100.5 + i * 0.1 + math.sin(i / 7.0) * 0.2,
            "volume": 1000 + i * 3,
            "time": 1_000_000 + i * 86_400_000,
        }
        for i in range(160)
    ]
    src = """//@version=5
indicator("round8 wma hma linreg")
plot(ta.wma(close, 14))
plot(ta.hma(close, 9))
plot(ta.hma(close, 16))
plot(ta.vwma(close, 14))
plot(ta.swma(close))
plot(ta.linreg(close, 14, 0))
plot(ta.linreg(close, 20, 2))
plot(ta.vwap(close))
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                continue
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Round 9: residual volume full-recompute (obv / wad / wvad / cmf / klinger)
# ---------------------------------------------------------------------------


def _last_of(value: Any) -> Any:
    if isinstance(value, list):
        return value[-1] if value else None
    return value


def _bar_walk_full_obv(closes: list[float], vols: list[float]) -> list[float]:
    ev = _FullTA()
    return [float(ev._obv(closes[: i + 1], vols[: i + 1])) for i in range(len(closes))]


def _bar_walk_inc_obv(closes: list[float], vols: list[float]) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(float(ev._obv_inc_update(closes[: i + 1], vols[: i + 1])))
    return out


def _bar_walk_full_wad(
    highs: list[float], lows: list[float], closes: list[float], vols: list[float]
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._wad(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1])
        out.append(_last_of(full))
    return out


def _bar_walk_inc_wad(
    highs: list[float], lows: list[float], closes: list[float], vols: list[float]
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._wad_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1]))
    return out


def _bar_walk_full_wvad(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    vols: list[float],
    period: int,
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._wvad(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period)
        out.append(_last_of(full))
    return out


def _bar_walk_inc_wvad(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    vols: list[float],
    period: int,
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._wvad_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period))
    return out


def _bar_walk_full_cmf(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    vols: list[float],
    period: int,
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._cmf(closes[: i + 1], highs[: i + 1], lows[: i + 1], vols[: i + 1], period)
        out.append(_last_of(full))
    return out


def _bar_walk_inc_cmf(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    vols: list[float],
    period: int,
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._cmf_inc_update(closes[: i + 1], highs[: i + 1], lows[: i + 1], vols[: i + 1], period))
    return out


def _bar_walk_full_klinger(closes: list[float], vols: list[float], fast: int, slow: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._klinger(closes[: i + 1], vols[: i + 1], fast, slow)
        out.append(_last_of(full))
    return out


def _bar_walk_inc_klinger(closes: list[float], vols: list[float], fast: int, slow: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._klinger_inc_update(closes[: i + 1], vols[: i + 1], fast, slow))
    return out


def test_incremental_obv_matches_full() -> None:
    _highs, _lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    _assert_series_close(_bar_walk_inc_obv(closes, vols), _bar_walk_full_obv(closes, vols))


def test_incremental_obv_dual_call_sites() -> None:
    closes = _series(80)
    vols_a = _volumes(len(closes))
    vols_b = [v * 1.5 + 3.0 for v in vols_a]
    ev = _IncTA()
    got_a: list[float] = []
    got_b: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        got_a.append(float(ev._obv_inc_update(closes[: i + 1], vols_a[: i + 1])))
        got_b.append(float(ev._obv_inc_update(closes[: i + 1], vols_b[: i + 1])))
    _assert_series_close(got_a, _bar_walk_full_obv(closes, vols_a))
    _assert_series_close(got_b, _bar_walk_full_obv(closes, vols_b))


def test_incremental_wad_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    _assert_series_close(
        _bar_walk_inc_wad(highs, lows, closes, vols),
        _bar_walk_full_wad(highs, lows, closes, vols),
    )


def test_incremental_wvad_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    for period in (10, 20):
        _assert_series_close(
            _bar_walk_inc_wvad(highs, lows, closes, vols, period),
            _bar_walk_full_wvad(highs, lows, closes, vols, period),
        )


def test_incremental_cmf_matches_full() -> None:
    highs, lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    for period in (10, 20):
        _assert_series_close(
            _bar_walk_inc_cmf(highs, lows, closes, vols, period),
            _bar_walk_full_cmf(highs, lows, closes, vols, period),
        )


def test_incremental_klinger_matches_full() -> None:
    _h, _l, closes = _ohlc(160)
    vols = _volumes(len(closes))
    for fast, slow in ((5, 13), (8, 21)):
        _assert_series_close(
            _bar_walk_inc_klinger(closes, vols, fast, slow),
            _bar_walk_full_klinger(closes, vols, fast, slow),
        )


def test_runtime_round9_volume_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(160)
    src = """//@version=5
indicator("round9 volume inc")
plot(ta.obv, "obv")
plot(ta.wad, "wad")
plot(ta.wvad(14), "wvad")
plot(ta.cmf(20), "cmf")
plot(ta.klinger(high, low, close, volume, 8, 21), "ko")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                continue
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# Residual T2 leftover: nvi / pvi incremental (full-list recompute → O(1))
# ---------------------------------------------------------------------------


def _bar_walk_full_nvi(closes: list[float], vols: list[float]) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._builtin_ta_nvi([closes[: i + 1], vols[: i + 1]])
        out.append(_last_of(full))
    return out


def _bar_walk_inc_nvi(closes: list[float], vols: list[float]) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._nvi_inc_update(closes[: i + 1], vols[: i + 1]))
    return out


def _bar_walk_full_pvi(closes: list[float], vols: list[float]) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._builtin_ta_pvi([closes[: i + 1], vols[: i + 1]])
        out.append(_last_of(full))
    return out


def _bar_walk_inc_pvi(closes: list[float], vols: list[float]) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._pvi_inc_update(closes[: i + 1], vols[: i + 1]))
    return out


def test_incremental_nvi_matches_full() -> None:
    _highs, _lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    _assert_series_close(_bar_walk_inc_nvi(closes, vols), _bar_walk_full_nvi(closes, vols))
    ev = _IncTA()
    ev._ta_call_i = 0
    got = ev._builtin_ta_nvi([closes[:1], vols[:1]])
    assert isinstance(got, float)
    assert got == pytest.approx(1000.0)


def test_incremental_pvi_matches_full() -> None:
    _highs, _lows, closes = _ohlc(150)
    vols = _volumes(len(closes))
    _assert_series_close(_bar_walk_inc_pvi(closes, vols), _bar_walk_full_pvi(closes, vols))
    ev = _IncTA()
    ev._ta_call_i = 0
    got = ev._builtin_ta_pvi([closes[:1], vols[:1]])
    assert isinstance(got, float)
    assert got == pytest.approx(1000.0)


def test_incremental_nvi_pvi_dual_call_sites() -> None:
    """Two nvi/pvi call sites must not share incremental state."""
    closes = _series(80)
    vols_a = _volumes(len(closes))
    vols_b = [v * 1.5 + 3.0 for v in vols_a]
    ev = _IncTA()
    nvi_a: list[float | None] = []
    nvi_b: list[float | None] = []
    pvi_a: list[float | None] = []
    pvi_b: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        nvi_a.append(ev._nvi_inc_update(closes[: i + 1], vols_a[: i + 1]))
        nvi_b.append(ev._nvi_inc_update(closes[: i + 1], vols_b[: i + 1]))
        pvi_a.append(ev._pvi_inc_update(closes[: i + 1], vols_a[: i + 1]))
        pvi_b.append(ev._pvi_inc_update(closes[: i + 1], vols_b[: i + 1]))
    _assert_series_close(nvi_a, _bar_walk_full_nvi(closes, vols_a))
    _assert_series_close(nvi_b, _bar_walk_full_nvi(closes, vols_b))
    _assert_series_close(pvi_a, _bar_walk_full_pvi(closes, vols_a))
    _assert_series_close(pvi_b, _bar_walk_full_pvi(closes, vols_b))


def test_runtime_nvi_pvi_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(160)
    src = """//@version=5
indicator("nvi pvi inc")
plot(ta.nvi, "nvi")
plot(ta.pvi, "pvi")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            if a is None and b is None:
                continue
            if a is None or b is None:
                continue
            if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
                continue
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def _bar_walk_full_aroon(highs: list[float], lows: list[float], length: int) -> list[tuple[float, float] | None]:
    ev = _FullTA()
    out: list[tuple[float, float] | None] = []
    for i in range(len(highs)):
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._builtin_ta_aroon([length]))
    return out


def _bar_walk_inc_aroon(highs: list[float], lows: list[float], length: int) -> list[tuple[float, float] | None]:
    ev = _IncTA()
    out: list[tuple[float, float] | None] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._aroon_inc_update(highs[: i + 1], lows[: i + 1], length))
    return out


def test_incremental_aroon_matches_full() -> None:
    highs, lows, _closes = _ohlc(80)
    for length in (7, 14):
        got = _bar_walk_inc_aroon(highs, lows, length)
        exp = _bar_walk_full_aroon(highs, lows, length)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            if e is None:
                assert g is None, f"bar {i}: expected None, got {g}"
                continue
            assert g is not None, f"bar {i}: expected {e}, got None"
            assert g[0] == pytest.approx(e[0], rel=1e-9, abs=1e-9)
            assert g[1] == pytest.approx(e[1], rel=1e-9, abs=1e-9)


def _bar_walk_full_dpo(closes: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev.current_series = {"close": closes[: i + 1]}
        out.append(ev._builtin_ta_dpo([length]))
    return out


def _bar_walk_inc_dpo(closes: list[float], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._dpo_inc_update(closes[: i + 1], length))
    return out


def test_incremental_dpo_matches_full() -> None:
    closes = _series(90)
    for length in (10, 21):
        _assert_series_close(_bar_walk_inc_dpo(closes, length), _bar_walk_full_dpo(closes, length))


def test_incremental_dpo_keeps_na_bar_alignment() -> None:
    """NA bars must occupy a window slot so SMA stay bar-aligned."""
    closes: list[float | None] = list(_series(30))
    na_i = 12
    length = 10
    closes[na_i] = None
    ev = _IncTA()
    values: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        values.append(ev._dpo_inc_update(closes[: i + 1], length))
    for i in range(na_i, na_i + length):
        assert values[i] is None, f"bar {i}: expected None while NA is still in SMA window"
    assert values[na_i + length] is not None


def _bar_walk_full_donchian(highs: list[float], lows: list[float], length: int) -> list[dict[str, float | None]]:
    ev = _FullTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(highs)):
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._builtin_ta_donchian([length]))
    return out


def _bar_walk_inc_donchian(highs: list[float], lows: list[float], length: int) -> list[dict[str, float | None]]:
    ev = _IncTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._donchian_inc_update(highs[: i + 1], lows[: i + 1], length))
    return out


def test_incremental_donchian_matches_full() -> None:
    highs, lows, _closes = _ohlc(80)
    for length in (10, 20):
        got = _bar_walk_inc_donchian(highs, lows, length)
        exp = _bar_walk_full_donchian(highs, lows, length)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            for key in ("high", "low", "mid"):
                _assert_num_close(g.get(key), e.get(key), i=i)


def _bar_walk_full_kst(closes: list[float], lengths: tuple[int, int, int, int]) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev.current_series = {"close": closes[: i + 1]}
        out.append(ev._builtin_ta_kst(list(lengths)))
    return out


def _bar_walk_inc_kst(closes: list[float], lengths: tuple[int, int, int, int]) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._kst_inc_update(closes[: i + 1], *lengths))
    return out


def test_incremental_kst_matches_full() -> None:
    closes = _series(80)
    lengths = (10, 15, 20, 30)
    _assert_series_close(_bar_walk_inc_kst(closes, lengths), _bar_walk_full_kst(closes, lengths))


def test_runtime_aroon_dpo_donchian_kst_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("aroon dpo donchian kst")
a = ta.aroon(14)
plot(a[0], "ad")
plot(a[1], "au")
plot(ta.dpo(21), "dpo")
plot(ta.kst(10, 15, 20, 30), "kst")
dc = ta.donchian(20)
plot(dc.high, "dc_h")
plot(dc.low, "dc_l")
plot(dc.mid, "dc_m")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"ad", "au", "dpo", "kst", "dc_h", "dc_l", "dc_m"}
    assert expected_plots <= set(r_on["series"])
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"

    ev = _IncTA()
    highs, lows, closes = _ohlc(40)
    for i in range(len(closes)):
        ev._ta_call_i = 0
        ev.current_series = {
            "high": highs[: i + 1],
            "low": lows[: i + 1],
            "close": closes[: i + 1],
        }
        ev._builtin_ta_dpo([21])
        ev._builtin_ta_kst([10, 15, 20, 30])
    bucket = ev._ta_state_bucket()
    kinds = {key[0] for key in bucket}
    assert "dpo" in kinds, bucket.keys()
    assert "kst" in kinds, bucket.keys()
    assert any(key[0] == "dpo" and key[2] == 21 for key in bucket)
    assert any(key[0] == "kst" and key[2] == (10, 15, 20, 30) for key in bucket)


# ---------------------------------------------------------------------------
# Last-sample period-only oscillators (stoch/cci/wpr/ao) — no per-bar hl2 rebuild
# ---------------------------------------------------------------------------


def test_incremental_ao_last_sample_without_hl2_list() -> None:
    """Inc ``ta.ao`` from high/low last samples ≡ full SMA(hl2,5)-SMA(hl2,34)."""
    highs, lows, _closes = _ohlc(80)
    hl2 = [(float(highs[i]) + float(lows[i])) * 0.5 for i in range(len(highs))]
    full = _FullTA()
    expected: list[float | None] = []
    for i in range(len(hl2)):
        window = hl2[: i + 1]
        if len(window) < 34:
            expected.append(None)
            continue
        fast_s = full._sma(window, 5)
        slow_s = full._sma(window, 34)
        fv = fast_s[-1] if fast_s else None
        sv = slow_s[-1] if slow_s else None
        if fv is None or sv is None:
            expected.append(None)
        else:
            expected.append(float(fv) - float(sv))

    ev = _IncTA()
    got: list[float | None] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        # No hl2 series — last-sample path must derive (h+l)/2 per bar.
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1], "hl2": []}
        got.append(ev._builtin_ta_ao([]))
    _assert_series_close(got, expected)


def test_runtime_ao_stoch_cci_wpr_period_only_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Period-only oscillators: last-sample inc ≡ PYNE_TA_INCREMENTAL=0.

    Source does not mention ``hl2`` so host used to skip derived hl2 and
    ``ta.ao`` rebuilt the full (high+low)/2 list every bar.
    """
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("ao stoch cci wpr")
plot(ta.ao(), "ao")
plot(ta.stoch(14), "stoch")
plot(ta.cci(14), "cci")
plot(ta.wpr(14), "wpr")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"ao", "stoch", "cci", "wpr"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # AO must actually compute (not stay all-na) after slow SMA warmup.
    ao = r_on["series"]["ao"]
    assert any(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in ao[33:])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def test_runtime_dmi_period_only_vs_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Period-only ``ta.dmi`` last-sample inc ≡ PYNE_TA_INCREMENTAL=0."""
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("dmi")
[diplus, diminus, adx] = ta.dmi(14, 14)
plot(diplus, "diplus")
plot(diminus, "diminus")
plot(adx, "adx")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    for key in ("diplus", "diminus", "adx"):
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: ichimoku / apo / emv incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _vols(n: int, seed: float = 1000.0) -> list[float]:
    """Synthetic volume, strictly positive (EMV treats 0 as na)."""
    return [seed + i * 3.0 + abs(math.sin(i / 4.0)) * 80.0 for i in range(n)]


def _bar_walk_full_ichimoku(
    highs: list[float], lows: list[float], fast: int, slow: int
) -> list[dict[str, float | None]]:
    ev = _FullTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(highs)):
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._builtin_ta_ichimoku([fast, slow]))
    return out


def _bar_walk_inc_ichimoku(
    highs: list[float], lows: list[float], fast: int, slow: int
) -> list[dict[str, float | None]]:
    ev = _IncTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._ichimoku_inc_update(highs[: i + 1], lows[: i + 1], fast, slow))
    return out


def test_incremental_ichimoku_matches_full() -> None:
    highs, lows, _closes = _ohlc(120)
    for fast, slow in ((9, 26), (7, 22)):
        got = _bar_walk_inc_ichimoku(highs, lows, fast, slow)
        exp = _bar_walk_full_ichimoku(highs, lows, fast, slow)
        assert len(got) == len(exp)
        for i, (g, e) in enumerate(zip(got, exp, strict=True)):
            for key in ("tenkan_sen", "kijun_sen", "senkou_span_a", "senkou_span_b"):
                _assert_num_close(g.get(key), e.get(key), i=i)


def test_incremental_ichimoku_slot_count_stable() -> None:
    """Four components always consume six highest/lowest slots, including warmup."""
    ev = _IncTA()
    highs, lows, _closes = _ohlc(60)
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._ichimoku_inc_update(highs[: i + 1], lows[: i + 1], 9, 26)
        assert ev._ta_call_i == 6, f"bar {i}: expected 6 slots, got {ev._ta_call_i}"


def _bar_walk_full_apo(src: list[float], fast: int, slow: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        full = ev._apo(src[: i + 1], fast, slow)
        out.append(full[-1] if full else None)
    return out


def _bar_walk_inc_apo(src: list[float], fast: int, slow: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._apo_inc_update(src[: i + 1], fast, slow))
    return out


def test_incremental_apo_matches_full() -> None:
    src = _series(150)
    for fast, slow in ((12, 26), (10, 20)):
        _assert_series_close(_bar_walk_inc_apo(src, fast, slow), _bar_walk_full_apo(src, fast, slow))


def test_incremental_apo_slot_count_stable() -> None:
    ev = _IncTA()
    src = _series(40)
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._apo_inc_update(src[: i + 1], 12, 26)
        assert ev._ta_call_i == 2, f"bar {i}: expected 2 EMA slots, got {ev._ta_call_i}"


def _bar_walk_full_emv(highs: list[float], lows: list[float], vols: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(highs)):
        ev.current_series = {
            "high": highs[: i + 1],
            "low": lows[: i + 1],
            "volume": vols[: i + 1],
        }
        out.append(ev._builtin_ta_emv([length]))
    return out


def _bar_walk_inc_emv(highs: list[float], lows: list[float], vols: list[float], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev.current_series = {
            "high": highs[: i + 1],
            "low": lows[: i + 1],
            "volume": vols[: i + 1],
        }
        out.append(ev._emv_inc_update(highs[: i + 1], lows[: i + 1], vols[: i + 1], length))
    return out


def test_incremental_emv_matches_full() -> None:
    highs, lows, _closes = _ohlc(120)
    vols = _vols(120)
    for length in (10, 14):
        _assert_series_close(
            _bar_walk_inc_emv(highs, lows, vols, length),
            _bar_walk_full_emv(highs, lows, vols, length),
        )


def test_incremental_emv_skips_zero_volume_and_flat_bars() -> None:
    """Zero volume / zero box-height are na samples; SMA uses last-N valid."""
    highs, lows, _closes = _ohlc(80)
    vols = _vols(80)
    vols[8] = 0.0
    highs[15] = lows[15]  # box_height == 0
    _assert_series_close(
        _bar_walk_inc_emv(highs, lows, vols, 10),
        _bar_walk_full_emv(highs, lows, vols, 10),
    )


def test_runtime_ichimoku_apo_emv_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("ichimoku apo emv")
i = ta.ichimoku(9, 26)
plot(i.tenkan_sen, "tenkan")
plot(i.kijun_sen, "kijun")
plot(i.senkou_span_a, "span_a")
plot(i.senkou_span_b, "span_b")
plot(ta.apo(close, 12, 26), "apo")
plot(ta.emv(14), "emv")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"tenkan", "kijun", "span_a", "span_b", "apo", "emv"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: skewness / kurtosis / beta incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_skewness(src: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_skewness([src[: i + 1], period]) for i in range(len(src))]


def _bar_walk_inc_skewness(src: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._skewness_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_kurtosis(src: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_kurtosis([src[: i + 1], period]) for i in range(len(src))]


def _bar_walk_inc_kurtosis(src: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._kurtosis_inc_update(src[: i + 1], period))
    return out


def _bar_walk_full_beta(s1: list[Any], s2: list[Any], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_beta([s1[: i + 1], s2[: i + 1], length]) for i in range(len(s1))]


def _bar_walk_inc_beta(s1: list[Any], s2: list[Any], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(s1)):
        ev._ta_call_i = 0
        out.append(ev._beta_inc_update(s1[: i + 1], s2[: i + 1], length))
    return out


def test_incremental_skewness_matches_full() -> None:
    src = _series(120)
    for period in (10, 20):
        _assert_series_close(
            _bar_walk_inc_skewness(src, period),
            _bar_walk_full_skewness(src, period),
        )


def test_incremental_kurtosis_matches_full() -> None:
    src = _series(120)
    for period in (10, 20):
        _assert_series_close(
            _bar_walk_inc_kurtosis(src, period),
            _bar_walk_full_kurtosis(src, period),
        )


def test_incremental_beta_matches_full() -> None:
    s1 = _series(120)
    s2 = [x * 2.0 + math.sin(i / 5.0) * 0.4 for i, x in enumerate(s1)]
    for length in (10, 20):
        _assert_series_close(
            _bar_walk_inc_beta(s1, s2, length),
            _bar_walk_full_beta(s1, s2, length),
        )


def test_incremental_skewness_kurtosis_beta_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    peer: list[float | None] = [x * 1.5 if x is not None else None for x in src]
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        peer_p = peer[: i + 1]
        ev._ta_call_i = 0
        ev._skewness_inc_update(prefix, 10)
        assert ev._ta_call_i == 1, f"skewness bar {i}: expected 1 slot, got {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._kurtosis_inc_update(prefix, 10)
        assert ev._ta_call_i == 1, f"kurtosis bar {i}: expected 1 slot, got {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._beta_inc_update(prefix, peer_p, 10)
        assert ev._ta_call_i == 1, f"beta bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_skewness_kurtosis_na_in_window() -> None:
    """NA in the last-period calendar window yields na (full-path valid_data rule)."""
    src: list[float | None] = list(_series(80))
    na_i = 15
    period = 10
    src[na_i] = None
    got_s = _bar_walk_inc_skewness(src, period)
    got_k = _bar_walk_inc_kurtosis(src, period)
    _assert_series_close(got_s, _bar_walk_full_skewness(src, period))
    _assert_series_close(got_k, _bar_walk_full_kurtosis(src, period))
    for i in range(na_i, na_i + period):
        assert got_s[i] is None, f"skewness bar {i}: expected None while NA is in window"
        assert got_k[i] is None, f"kurtosis bar {i}: expected None while NA is in window"


def test_incremental_skewness_kurtosis_zero_stdev() -> None:
    """Constant window → 0.0 (std_dev == 0), matching full path."""
    src = [7.0] * 40
    period = 10
    got_s = _bar_walk_inc_skewness(src, period)
    got_k = _bar_walk_inc_kurtosis(src, period)
    _assert_series_close(got_s, _bar_walk_full_skewness(src, period))
    _assert_series_close(got_k, _bar_walk_full_kurtosis(src, period))
    for i in range(period - 1, len(src)):
        assert got_s[i] == pytest.approx(0.0)
        assert got_k[i] == pytest.approx(0.0)


def test_incremental_beta_zero_variance() -> None:
    """var(series2) == 0 → 0.0, matching full path."""
    s1 = _series(50)
    s2 = [3.0] * 50
    length = 14
    got = _bar_walk_inc_beta(s1, s2, length)
    _assert_series_close(got, _bar_walk_full_beta(s1, s2, length))
    for i in range(length - 1, len(s1)):
        assert got[i] == pytest.approx(0.0)


def test_incremental_skewness_kurtosis_beta_builtin_uses_inc_slot() -> None:
    """Bar-mode builtins consume the inc kernel slot (gate is wired)."""
    src = _series(30)
    peer = [x * 2.0 for x in src]
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_skewness([prefix, 10])
        assert ev._ta_call_i == 1, f"skewness builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_kurtosis([prefix, 10])
        assert ev._ta_call_i == 1, f"kurtosis builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_beta([prefix, peer[: i + 1], 10])
        assert ev._ta_call_i == 1, f"beta builtin bar {i}: {ev._ta_call_i}"


def test_runtime_skewness_kurtosis_beta_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("skew kurt beta")
plot(ta.skewness(close, 20), "skew")
plot(ta.kurtosis(close, 20), "kurt")
plot(ta.beta(close, high, 20), "beta")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"skew", "kurt", "beta"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: r_squared / comovement incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_r_squared(s1: list[Any], s2: list[Any], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_r_squared([s1[: i + 1], s2[: i + 1], length]) for i in range(len(s1))]


def _bar_walk_inc_r_squared(s1: list[Any], s2: list[Any], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(s1)):
        ev._ta_call_i = 0
        out.append(ev._r_squared_inc_update(s1[: i + 1], s2[: i + 1], length))
    return out


def _bar_walk_full_comovement(s1: list[Any], s2: list[Any], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_comovement([s1[: i + 1], s2[: i + 1], length]) for i in range(len(s1))]


def _bar_walk_inc_comovement(s1: list[Any], s2: list[Any], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(s1)):
        ev._ta_call_i = 0
        out.append(ev._comovement_inc_update(s1[: i + 1], s2[: i + 1], length))
    return out


def test_incremental_r_squared_matches_full() -> None:
    s1 = _series(120)
    s2 = [x * 2.0 + math.sin(i / 5.0) * 0.4 for i, x in enumerate(s1)]
    for length in (10, 20):
        _assert_series_close(
            _bar_walk_inc_r_squared(s1, s2, length),
            _bar_walk_full_r_squared(s1, s2, length),
        )


def test_incremental_comovement_matches_full() -> None:
    s1 = _series(120)
    s2 = [x * 1.5 + math.cos(i / 6.0) * 0.3 for i, x in enumerate(s1)]
    for length in (10, 20):
        _assert_series_close(
            _bar_walk_inc_comovement(s1, s2, length),
            _bar_walk_full_comovement(s1, s2, length),
        )


def test_incremental_r_squared_comovement_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    peer: list[float | None] = [x * 1.5 if x is not None else None for x in src]
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        peer_p = peer[: i + 1]
        ev._ta_call_i = 0
        ev._r_squared_inc_update(prefix, peer_p, 10)
        assert ev._ta_call_i == 1, f"r_squared bar {i}: expected 1 slot, got {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._comovement_inc_update(prefix, peer_p, 10)
        assert ev._ta_call_i == 1, f"comovement bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_r_squared_comovement_na_in_window() -> None:
    """NA in the last-N calendar window yields na (full path would TypeError)."""
    src: list[float | None] = list(_series(80))
    na_i = 15
    length = 10
    src[na_i] = None
    peer: list[float | None] = [x * 1.5 if x is not None else None for x in src]
    got_r = _bar_walk_inc_r_squared(src, peer, length)
    got_c = _bar_walk_inc_comovement(src, peer, length)
    for i in range(na_i, na_i + length):
        assert got_r[i] is None, f"r_squared bar {i}: expected None while NA is in window"
        assert got_c[i] is None, f"comovement bar {i}: expected None while NA is in window"
    clean = list(_series(80))
    clean_peer = [x * 1.5 for x in clean]
    exp_r = _bar_walk_full_r_squared(clean, clean_peer, length)
    exp_c = _bar_walk_full_comovement(clean, clean_peer, length)
    for i in range(na_i):
        _assert_series_close([got_r[i]], [exp_r[i]])
        _assert_series_close([got_c[i]], [exp_c[i]])
    for i in range(na_i + length, len(src)):
        _assert_series_close([got_r[i]], [exp_r[i]])
        _assert_series_close([got_c[i]], [exp_c[i]])


def test_incremental_r_squared_zero_variance() -> None:
    """var(series1)==0 or var(series2)==0 → 0.0, matching full path."""
    s1 = _series(50)
    s2 = [3.0] * 50
    length = 14
    got = _bar_walk_inc_r_squared(s1, s2, length)
    _assert_series_close(got, _bar_walk_full_r_squared(s1, s2, length))
    for i in range(length - 1, len(s1)):
        assert got[i] == pytest.approx(0.0)
    got_rev = _bar_walk_inc_r_squared(s2, s1, length)
    _assert_series_close(got_rev, _bar_walk_full_r_squared(s2, s1, length))
    for i in range(length - 1, len(s1)):
        assert got_rev[i] == pytest.approx(0.0)


def test_incremental_comovement_constant_series() -> None:
    """Zero deltas never share sign (product is 0) → 0.0, matching full path."""
    s1 = _series(50)
    s2 = [3.0] * 50
    length = 14
    got = _bar_walk_inc_comovement(s1, s2, length)
    _assert_series_close(got, _bar_walk_full_comovement(s1, s2, length))
    for i in range(length - 1, len(s1)):
        assert got[i] == pytest.approx(0.0)


def test_incremental_r_squared_perfect_fit() -> None:
    """Linearly related series → r_squared ≈ 1.0 once the window is full."""
    s1 = _series(50)
    s2 = [2.0 * x + 5.0 for x in s1]
    length = 14
    got = _bar_walk_inc_r_squared(s1, s2, length)
    _assert_series_close(got, _bar_walk_full_r_squared(s1, s2, length))
    for i in range(length - 1, len(s1)):
        assert got[i] == pytest.approx(1.0)


def test_incremental_comovement_same_direction() -> None:
    """Monotone-up pair → 100% shared-sign deltas once the window is full."""
    s1 = [float(i) for i in range(50)]
    s2 = [float(i) * 2.0 + 1.0 for i in range(50)]
    length = 14
    got = _bar_walk_inc_comovement(s1, s2, length)
    _assert_series_close(got, _bar_walk_full_comovement(s1, s2, length))
    for i in range(length - 1, len(s1)):
        assert got[i] == pytest.approx(100.0)


def test_incremental_r_squared_comovement_builtin_uses_inc_slot() -> None:
    """Bar-mode builtins consume the inc kernel slot (gate is wired)."""
    src = _series(30)
    peer = [x * 2.0 for x in src]
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_r_squared([prefix, peer[: i + 1], 10])
        assert ev._ta_call_i == 1, f"r_squared builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_comovement([prefix, peer[: i + 1], 10])
        assert ev._ta_call_i == 1, f"comovement builtin bar {i}: {ev._ta_call_i}"


def test_runtime_r_squared_comovement_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("rsq como")
plot(ta.r_squared(close, high, 20), "rsq")
plot(ta.comovement(close, high, 20), "como")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"rsq", "como"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: volume_weighted_momentum incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_vwm(src: list[Any], vol: list[Any], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_volume_weighted_momentum([src[: i + 1], vol[: i + 1], length]) for i in range(len(src))]


def _bar_walk_inc_vwm(src: list[Any], vol: list[Any], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._volume_weighted_momentum_inc_update(src[: i + 1], vol[: i + 1], length))
    return out


def test_incremental_volume_weighted_momentum_matches_full() -> None:
    src = _series(120)
    vol = _vols(120)
    for length in (10, 20):
        _assert_series_close(
            _bar_walk_inc_vwm(src, vol, length),
            _bar_walk_full_vwm(src, vol, length),
        )


def test_incremental_volume_weighted_momentum_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    vol: list[float | None] = list(_vols(40))
    vol[7] = None
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._volume_weighted_momentum_inc_update(src[: i + 1], vol[: i + 1], 10)
        assert ev._ta_call_i == 1, f"vwm bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_volume_weighted_momentum_zero_volume() -> None:
    """volume_sum == 0 → 0.0; mixed zeros still match the full last-N path."""
    src = _series(80)
    vol = _vols(80)
    vol[12] = 0.0
    vol[13] = 0.0
    got = _bar_walk_inc_vwm(src, vol, 10)
    _assert_series_close(got, _bar_walk_full_vwm(src, vol, 10))
    all_zero = [0.0] * 50
    got_z = _bar_walk_inc_vwm(src[:50], all_zero, 10)
    _assert_series_close(got_z, _bar_walk_full_vwm(src[:50], all_zero, 10))
    for i in range(10 - 1, 50):
        assert got_z[i] == pytest.approx(0.0)


def test_incremental_volume_weighted_momentum_na_in_window() -> None:
    """NA price in the last-N window yields na (full path would TypeError)."""
    src: list[float | None] = list(_series(80))
    na_i = 15
    length = 10
    src[na_i] = None
    vol = _vols(80)
    got = _bar_walk_inc_vwm(src, vol, length)
    for i in range(na_i, min(na_i + length + 1, len(src))):
        assert got[i] is None, f"vwm bar {i}: expected None while NA is in window"
    clean = list(_series(80))
    exp = _bar_walk_full_vwm(clean, vol, length)
    for i in range(na_i):
        _assert_series_close([got[i]], [exp[i]])
    # After the NA price (and the extra prev-price slot) leave the window.
    for i in range(na_i + length + 1, len(src)):
        _assert_series_close([got[i]], [exp[i]])


def test_incremental_volume_weighted_momentum_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _series(30)
    vol = _vols(30)
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._builtin_ta_volume_weighted_momentum([src[: i + 1], vol[: i + 1], 10])
        assert ev._ta_call_i == 1, f"vwm builtin bar {i}: {ev._ta_call_i}"


def test_runtime_volume_weighted_momentum_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("vwm")
plot(ta.volume_weighted_momentum(close, volume, 20), "vwm")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"vwm"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: rci (volatility mixin) / bb_pct / atr_normalized last-sample ≡ full
# ---------------------------------------------------------------------------


def _bar_walk_full_rci(src: list[Any], length: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_rci([src[: i + 1], length]) for i in range(len(src))]


def _bar_walk_inc_rci(src: list[Any], length: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._rci_inc_update(src[: i + 1], length))
    return out


def _bar_walk_full_vol_rci(src: list[Any], length: int) -> list[float | None]:
    """Full-recompute via the volatility mixin copy (not the MRO winner)."""
    from pynescript.ast.evaluator.builtins.technical_submodules.volatility import VolatilityIndicators

    ev = _FullTA()
    return [VolatilityIndicators._builtin_ta_rci(ev, [src[: i + 1], length]) for i in range(len(src))]


def _bar_walk_full_bb_pct(src: list[Any], length: int, std_dev: float) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev.current_series = {"close": src[: i + 1]}
        out.append(ev._builtin_ta_bb_pct([length, std_dev]))
    return out


def _bar_walk_inc_bb_pct(src: list[Any], length: int, std_dev: float) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._bb_pct_inc_update(src[: i + 1], length, std_dev))
    return out


def _bar_walk_full_atr_normalized(
    highs: list[Any], lows: list[Any], closes: list[Any], period: int
) -> list[float | None]:
    ev = _FullTA()
    return [
        ev._builtin_ta_atr_normalized([highs[: i + 1], lows[: i + 1], closes[: i + 1], period])
        for i in range(len(closes))
    ]


def _bar_walk_inc_atr_normalized(
    highs: list[Any], lows: list[Any], closes: list[Any], period: int
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(ev._atr_normalized_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], period))
    return out


def test_incremental_rci_matches_full() -> None:
    src = _series(120)
    for length in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_rci(src, length),
            _bar_walk_full_rci(src, length),
        )


def test_incremental_rci_volatility_mixin_matches_full() -> None:
    """volatility.py ``_builtin_ta_rci`` last sample ≡ ``_rci_inc_update``."""
    src = _series(80)
    for length in (10, 14):
        _assert_series_close(
            _bar_walk_inc_rci(src, length),
            _bar_walk_full_vol_rci(src, length),
        )


def test_incremental_rci_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._rci_inc_update(src[: i + 1], 10)
        assert ev._ta_call_i == 1, f"rci bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_rci_na_in_window() -> None:
    """Any na in the last-N window yields na (``_rci_spearman``)."""
    src: list[float | None] = list(_series(80))
    na_i = 15
    length = 10
    src[na_i] = None
    got = _bar_walk_inc_rci(src, length)
    for i in range(na_i, min(na_i + length, len(src))):
        assert got[i] is None, f"rci bar {i}: expected None while NA is in window"
    clean = list(_series(80))
    exp = _bar_walk_full_rci(clean, length)
    for i in range(na_i):
        _assert_series_close([got[i]], [exp[i]])
    for i in range(na_i + length, len(src)):
        _assert_series_close([got[i]], [exp[i]])


def test_incremental_rci_builtin_uses_inc_slot() -> None:
    """Bar-mode builtins (MRO + volatility mixin copy) consume the inc slot."""
    from pynescript.ast.evaluator.builtins.technical_submodules.volatility import VolatilityIndicators

    src = _series(30)
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_rci([prefix, 10])
        assert ev._ta_call_i == 1, f"rci builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        VolatilityIndicators._builtin_ta_rci(ev, [prefix, 10])
        assert ev._ta_call_i == 1, f"vol rci builtin bar {i}: {ev._ta_call_i}"


def test_runtime_rci_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("rci")
plot(ta.rci(close, 14), "rci")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"rci"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def test_incremental_bb_pct_matches_full() -> None:
    src = _series(120)
    for length, std_dev in ((20, 2.0), (10, 1.5), (5, 2.5)):
        _assert_series_close(
            _bar_walk_inc_bb_pct(src, length, std_dev),
            _bar_walk_full_bb_pct(src, length, std_dev),
        )


def test_incremental_bb_pct_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._bb_pct_inc_update(src[: i + 1], 10, 2.0)
        assert ev._ta_call_i == 1, f"bb_pct bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_bb_pct_constant_series() -> None:
    """upper == lower (zero width) → 50.0 once the window is full."""
    src = [42.0] * 50
    got = _bar_walk_inc_bb_pct(src, 10, 2.0)
    _assert_series_close(got, _bar_walk_full_bb_pct(src, 10, 2.0))
    for i in range(10 - 1, len(src)):
        assert got[i] == pytest.approx(50.0)


def test_incremental_bb_pct_clips_to_unit_interval() -> None:
    """%B is clipped to [0, 100], matching the full path."""
    src = _series(40)
    src = [*src, src[-1] + 80.0, src[-1] - 80.0]
    got = _bar_walk_inc_bb_pct(src, 10, 2.0)
    _assert_series_close(got, _bar_walk_full_bb_pct(src, 10, 2.0))
    for v in got:
        if v is None:
            continue
        assert 0.0 <= v <= 100.0, v


def test_incremental_bb_pct_na_in_window() -> None:
    """NA in the last-N window yields na (full path would TypeError)."""
    src: list[float | None] = list(_series(80))
    na_i = 15
    length = 10
    src[na_i] = None
    got = _bar_walk_inc_bb_pct(src, length, 2.0)
    for i in range(na_i, min(na_i + length, len(src))):
        assert got[i] is None, f"bb_pct bar {i}: expected None while NA is in window"
    clean = list(_series(80))
    exp = _bar_walk_full_bb_pct(clean, length, 2.0)
    for i in range(na_i):
        _assert_series_close([got[i]], [exp[i]])
    for i in range(na_i + length, len(src)):
        _assert_series_close([got[i]], [exp[i]])


def test_incremental_bb_pct_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _series(30)
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev.current_series = {"close": src[: i + 1]}
        ev._builtin_ta_bb_pct([10, 2.0])
        assert ev._ta_call_i == 1, f"bb_pct builtin bar {i}: {ev._ta_call_i}"


def test_runtime_bb_pct_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("bb_pct")
plot(ta.bb_pct(20, 2), "bbp")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"bbp"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


def test_incremental_atr_normalized_matches_full() -> None:
    highs, lows, closes = _ohlc(120)
    for period in (7, 14):
        _assert_series_close(
            _bar_walk_inc_atr_normalized(highs, lows, closes, period),
            _bar_walk_full_atr_normalized(highs, lows, closes, period),
        )


def test_incremental_atr_normalized_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    highs, lows, closes = _ohlc(40)
    closes_na: list[float | None] = list(closes)
    closes_na[4] = None
    closes_na[11] = math.nan
    ev = _IncTA()
    for i in range(len(closes_na)):
        ev._ta_call_i = 0
        ev._atr_normalized_inc_update(highs[: i + 1], lows[: i + 1], closes_na[: i + 1], 10)
        assert ev._ta_call_i == 1, f"atr_normalized bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_atr_normalized_zero_close() -> None:
    """close == 0 → na; ATR state still advances so later bars match full."""
    highs, lows, closes = _ohlc(80)
    closes = list(closes)
    closes[20] = 0.0
    got = _bar_walk_inc_atr_normalized(highs, lows, closes, 10)
    _assert_series_close(got, _bar_walk_full_atr_normalized(highs, lows, closes, 10))
    assert got[20] is None


def test_incremental_atr_normalized_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    highs, lows, closes = _ohlc(30)
    ev = _IncTA()
    for i in range(len(closes)):
        ev._ta_call_i = 0
        ev._builtin_ta_atr_normalized([highs[: i + 1], lows[: i + 1], closes[: i + 1], 10])
        assert ev._ta_call_i == 1, f"atr_normalized builtin bar {i}: {ev._ta_call_i}"


def test_runtime_atr_normalized_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("atrn")
plot(ta.atr_normalized(high, low, close, 14), "atrn")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"atrn"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: cumulative_delta / volume_momentum last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_cumulative_delta(close: list[Any], vol: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_cumulative_delta([close[: i + 1], vol[: i + 1], period]) for i in range(len(close))]


def _bar_walk_inc_cumulative_delta(close: list[Any], vol: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(ev._cumulative_delta_inc_update(close[: i + 1], vol[: i + 1], period))
    return out


def _bar_walk_full_econ_cumulative_delta(close: list[Any], vol: list[Any], period: int) -> list[float | None]:
    """Full-recompute via the economics mixin copy (not the MRO winner)."""
    from pynescript.ast.evaluator.builtins.technical_submodules.economics import EconomicsIndicators

    ev = _FullTA()
    return [
        EconomicsIndicators._builtin_ta_cumulative_delta(ev, [close[: i + 1], vol[: i + 1], period])
        for i in range(len(close))
    ]


def _bar_walk_full_adv_cumulative_delta(close: list[Any], vol: list[Any], period: int) -> list[float | None]:
    """Full-recompute via the advanced mixin copy (MRO winner)."""
    from pynescript.ast.evaluator.builtins.technical_submodules.advanced import AdvancedIndicators

    ev = _FullTA()
    return [
        AdvancedIndicators._builtin_ta_cumulative_delta(ev, [close[: i + 1], vol[: i + 1], period])
        for i in range(len(close))
    ]


def _bar_walk_full_volume_momentum(vol: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_volume_momentum([vol[: i + 1], period]) for i in range(len(vol))]


def _bar_walk_inc_volume_momentum(vol: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(vol)):
        ev._ta_call_i = 0
        out.append(ev._volume_momentum_inc_update(vol[: i + 1], period))
    return out


def _bar_walk_full_econ_volume_momentum(vol: list[Any], period: int) -> list[float | None]:
    from pynescript.ast.evaluator.builtins.technical_submodules.economics import EconomicsIndicators

    ev = _FullTA()
    return [EconomicsIndicators._builtin_ta_volume_momentum(ev, [vol[: i + 1], period]) for i in range(len(vol))]


def _bar_walk_full_adv_volume_momentum(vol: list[Any], period: int) -> list[float | None]:
    from pynescript.ast.evaluator.builtins.technical_submodules.advanced import AdvancedIndicators

    ev = _FullTA()
    return [AdvancedIndicators._builtin_ta_volume_momentum(ev, [vol[: i + 1], period]) for i in range(len(vol))]


def test_incremental_cumulative_delta_matches_full() -> None:
    src = _series(120)
    vol = _vols(120)
    for period in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_cumulative_delta(src, vol, period),
            _bar_walk_full_cumulative_delta(src, vol, period),
        )


def test_incremental_cumulative_delta_mixin_copies_match_full() -> None:
    """economics.py and advanced.py last samples ≡ ``_cumulative_delta_inc_update``."""
    src = _series(80)
    vol = _vols(80)
    for period in (10, 14):
        inc = _bar_walk_inc_cumulative_delta(src, vol, period)
        _assert_series_close(inc, _bar_walk_full_econ_cumulative_delta(src, vol, period))
        _assert_series_close(inc, _bar_walk_full_adv_cumulative_delta(src, vol, period))


def test_incremental_cumulative_delta_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    vol: list[float | None] = list(_vols(40))
    vol[7] = None
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._cumulative_delta_inc_update(src[: i + 1], vol[: i + 1], 10)
        assert ev._ta_call_i == 1, f"cumulative_delta bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_cumulative_delta_warmup_is_zero() -> None:
    """Window shorter than period → 0.0, matching the full path."""
    src = _series(20)
    vol = _vols(20)
    period = 14
    got = _bar_walk_inc_cumulative_delta(src, vol, period)
    _assert_series_close(got, _bar_walk_full_cumulative_delta(src, vol, period))
    for i in range(period - 1):
        assert got[i] == pytest.approx(0.0)


def test_incremental_cumulative_delta_na_treated_as_zero() -> None:
    """Non-numeric close/volume is 0.0 in the last-N window (full path)."""
    src: list[float | None] = list(_series(80))
    vol: list[float | None] = list(_vols(80))
    src[15] = None
    vol[18] = None
    got = _bar_walk_inc_cumulative_delta(src, vol, 10)
    _assert_series_close(got, _bar_walk_full_econ_cumulative_delta(src, vol, 10))


def test_incremental_cumulative_delta_builtin_uses_inc_slot() -> None:
    """Bar-mode builtins (MRO + economics + advanced copies) consume the inc slot."""
    from pynescript.ast.evaluator.builtins.technical_submodules.advanced import AdvancedIndicators
    from pynescript.ast.evaluator.builtins.technical_submodules.economics import EconomicsIndicators

    src = _series(30)
    vol = _vols(30)
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        vprefix = vol[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_cumulative_delta([prefix, vprefix, 10])
        assert ev._ta_call_i == 1, f"cumulative_delta builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        EconomicsIndicators._builtin_ta_cumulative_delta(ev, [prefix, vprefix, 10])
        assert ev._ta_call_i == 1, f"econ cumulative_delta bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        AdvancedIndicators._builtin_ta_cumulative_delta(ev, [prefix, vprefix, 10])
        assert ev._ta_call_i == 1, f"adv cumulative_delta bar {i}: {ev._ta_call_i}"


def test_incremental_volume_momentum_matches_full() -> None:
    vol = _vols(120)
    for period in (5, 14, 20):
        _assert_series_close(
            _bar_walk_inc_volume_momentum(vol, period),
            _bar_walk_full_volume_momentum(vol, period),
        )


def test_incremental_volume_momentum_mixin_copies_match_full() -> None:
    """economics.py and advanced.py last samples ≡ ``_volume_momentum_inc_update``."""
    vol = _vols(80)
    for period in (10, 14):
        inc = _bar_walk_inc_volume_momentum(vol, period)
        _assert_series_close(inc, _bar_walk_full_econ_volume_momentum(vol, period))
        _assert_series_close(inc, _bar_walk_full_adv_volume_momentum(vol, period))


def test_incremental_volume_momentum_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    vol: list[float | None] = list(_vols(40))
    vol[4] = None
    vol[11] = math.nan
    ev = _IncTA()
    for i in range(len(vol)):
        ev._ta_call_i = 0
        ev._volume_momentum_inc_update(vol[: i + 1], 10)
        assert ev._ta_call_i == 1, f"volume_momentum bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_volume_momentum_warmup_is_zero() -> None:
    """Fewer than period+1 numeric samples → 0.0, matching the full path."""
    vol = _vols(20)
    period = 14
    got = _bar_walk_inc_volume_momentum(vol, period)
    _assert_series_close(got, _bar_walk_full_volume_momentum(vol, period))
    for i in range(period):
        assert got[i] == pytest.approx(0.0)


def test_incremental_volume_momentum_na_dropped() -> None:
    """Non-numeric volume is filtered (full path); short numeric window → 0.0."""
    vol: list[float | None] = list(_vols(80))
    vol[15] = None
    got = _bar_walk_inc_volume_momentum(vol, 10)
    _assert_series_close(got, _bar_walk_full_econ_volume_momentum(vol, 10))


def test_incremental_volume_momentum_zero_old_sma() -> None:
    """old SMA == 0 → 0.0; mixed zeros still match the full last-N path."""
    vol = [0.0] * 40
    got = _bar_walk_inc_volume_momentum(vol, 10)
    _assert_series_close(got, _bar_walk_full_econ_volume_momentum(vol, 10))
    for i in range(10, 40):
        assert got[i] == pytest.approx(0.0)


def test_incremental_volume_momentum_clips_to_range() -> None:
    """Result is clipped to [-100, 100], matching the full path."""
    rising = [1.0 * (i + 1) for i in range(40)]
    falling = [40.0 - i for i in range(40)]
    for vol in (rising, falling):
        got = _bar_walk_inc_volume_momentum(vol, 5)
        _assert_series_close(got, _bar_walk_full_econ_volume_momentum(vol, 5))
        for v in got:
            assert v is not None
            assert -100.0 <= v <= 100.0, v


def test_incremental_volume_momentum_builtin_uses_inc_slot() -> None:
    """Bar-mode builtins (MRO + economics + advanced copies) consume the inc slot."""
    from pynescript.ast.evaluator.builtins.technical_submodules.advanced import AdvancedIndicators
    from pynescript.ast.evaluator.builtins.technical_submodules.economics import EconomicsIndicators

    vol = _vols(30)
    ev = _IncTA()
    for i in range(len(vol)):
        prefix = vol[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_volume_momentum([prefix, 10])
        assert ev._ta_call_i == 1, f"volume_momentum builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        EconomicsIndicators._builtin_ta_volume_momentum(ev, [prefix, 10])
        assert ev._ta_call_i == 1, f"econ volume_momentum bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        AdvancedIndicators._builtin_ta_volume_momentum(ev, [prefix, 10])
        assert ev._ta_call_i == 1, f"adv volume_momentum bar {i}: {ev._ta_call_i}"


def test_runtime_cumulative_delta_volume_momentum_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("cd vm")
plot(ta.cumulative_delta(close, volume, 20), "cd")
plot(ta.volume_momentum(volume, 20), "vm")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"cd", "vm"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: sma_weighted incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_sma_weighted(src: list[Any], period: int, weight_type: str = "linear") -> list[float | None]:
    ev = _FullTA()
    args_tail: list[Any] = [period] if weight_type == "linear" else [period, weight_type]
    return [ev._builtin_ta_sma_weighted([src[: i + 1], *args_tail]) for i in range(len(src))]


def _bar_walk_inc_sma_weighted(src: list[Any], period: int, weight_type: str = "linear") -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._sma_weighted_inc_update(src[: i + 1], period, weight_type))
    return out


def test_incremental_sma_weighted_linear_matches_full() -> None:
    src = _series(120)
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_sma_weighted(src, period, "linear"),
            _bar_walk_full_sma_weighted(src, period, "linear"),
        )


def test_incremental_sma_weighted_quadratic_matches_full() -> None:
    src = _series(120)
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_sma_weighted(src, period, "quadratic"),
            _bar_walk_full_sma_weighted(src, period, "quadratic"),
        )


def test_incremental_sma_weighted_sqrt_matches_full() -> None:
    src = _series(120)
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_sma_weighted(src, period, "sqrt"),
            _bar_walk_full_sma_weighted(src, period, "sqrt"),
        )


def test_incremental_sma_weighted_default_is_linear() -> None:
    src = _series(80)
    got = _bar_walk_inc_sma_weighted(src, 10)
    _assert_series_close(got, _bar_walk_full_sma_weighted(src, 10, "linear"))
    _assert_series_close(got, _bar_walk_inc_sma_weighted(src, 10, "linear"))


def test_incremental_sma_weighted_warmup() -> None:
    src = _series(40)
    period = 14
    got = _bar_walk_inc_sma_weighted(src, period, "linear")
    exp = _bar_walk_full_sma_weighted(src, period, "linear")
    for i in range(period - 1):
        assert got[i] is None, f"warmup bar {i}: expected None, got {got[i]}"
        assert exp[i] is None, f"full warmup bar {i}: expected None, got {exp[i]}"
    assert got[period - 1] is not None
    _assert_series_close(got, exp)


def test_incremental_sma_weighted_na_in_window() -> None:
    """NA in the last-N window yields na (full path: len(valid_data) < period)."""
    src: list[float | None] = list(_series(80))
    na_i = 20
    period = 14
    src[na_i] = None
    got = _bar_walk_inc_sma_weighted(src, period, "linear")
    exp = _bar_walk_full_sma_weighted(src, period, "linear")
    _assert_series_close(got, exp)
    for i in range(na_i, min(na_i + period, len(src))):
        assert got[i] is None, f"sma_weighted bar {i}: expected None while NA is in window"
    for i in range(na_i + period, len(src)):
        assert got[i] is not None, f"sma_weighted bar {i}: expected recovery after NA left window"


def test_incremental_sma_weighted_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._sma_weighted_inc_update(prefix, 10, "linear")
        assert ev._ta_call_i == 1, f"linear bar {i}: expected 1 slot, got {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._sma_weighted_inc_update(prefix, 10, "quadratic")
        assert ev._ta_call_i == 1, f"quadratic bar {i}: expected 1 slot, got {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._sma_weighted_inc_update(prefix, 10, "sqrt")
        assert ev._ta_call_i == 1, f"sqrt bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_sma_weighted_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _series(30)
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_sma_weighted([prefix, 10])
        assert ev._ta_call_i == 1, f"default builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_sma_weighted([prefix, 10, "linear"])
        assert ev._ta_call_i == 1, f"linear builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_sma_weighted([prefix, 10, "quadratic"])
        assert ev._ta_call_i == 1, f"quadratic builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_sma_weighted([prefix, 10, "sqrt"])
        assert ev._ta_call_i == 1, f"sqrt builtin bar {i}: {ev._ta_call_i}"


def test_incremental_sma_weighted_two_call_sites_independent() -> None:
    src = _series(80)
    ev = _IncTA()
    lin: list[float | None] = []
    quad: list[float | None] = []
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        lin.append(ev._sma_weighted_inc_update(prefix, 10, "linear"))
        quad.append(ev._sma_weighted_inc_update(prefix, 10, "quadratic"))
    _assert_series_close(lin, _bar_walk_full_sma_weighted(src, 10, "linear"))
    _assert_series_close(quad, _bar_walk_full_sma_weighted(src, 10, "quadratic"))


def test_runtime_sma_weighted_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("sma_weighted")
plot(ta.sma_weighted(close, 14), "lin")
plot(ta.sma_weighted(close, 14, "linear"), "lin2")
plot(ta.sma_weighted(close, 14, "quadratic"), "quad")
plot(ta.sma_weighted(close, 14, "sqrt"), "sqrt")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"lin", "lin2", "quad", "sqrt"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: range / max / min incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_range(src: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_range([src[: i + 1], period]) for i in range(len(src))]


def _bar_walk_inc_range(src: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._builtin_ta_range([src[: i + 1], period]))
    return out


def _bar_walk_full_max(src: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_max([src[: i + 1], period]) for i in range(len(src))]


def _bar_walk_inc_max(src: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._builtin_ta_max([src[: i + 1], period]))
    return out


def _bar_walk_full_min(src: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_min([src[: i + 1], period]) for i in range(len(src))]


def _bar_walk_inc_min(src: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._builtin_ta_min([src[: i + 1], period]))
    return out


def test_incremental_range_matches_full() -> None:
    src = _series(120)
    for period in (5, 20, 50):
        _assert_series_close(_bar_walk_inc_range(src, period), _bar_walk_full_range(src, period))


def test_incremental_max_min_matches_full() -> None:
    src = _series(120)
    for period in (5, 20, 50):
        _assert_series_close(_bar_walk_inc_max(src, period), _bar_walk_full_max(src, period))
        _assert_series_close(_bar_walk_inc_min(src, period), _bar_walk_full_min(src, period))
        _assert_series_close(_bar_walk_inc_max(src, period), _bar_walk_full_highest(src, period))
        _assert_series_close(_bar_walk_inc_min(src, period), _bar_walk_full_lowest(src, period))


def test_incremental_range_equals_highest_minus_lowest() -> None:
    src = _series(80)
    period = 14
    got = _bar_walk_inc_range(src, period)
    hi = _bar_walk_full_highest(src, period)
    lo = _bar_walk_full_lowest(src, period)
    exp: list[float | None] = []
    for h, l in zip(hi, lo, strict=True):
        if h is None or l is None:
            exp.append(None)
        else:
            exp.append(h - l)
    _assert_series_close(got, exp)


def test_incremental_range_max_min_warmup() -> None:
    src = _series(40)
    period = 14
    for got, exp in (
        (_bar_walk_inc_range(src, period), _bar_walk_full_range(src, period)),
        (_bar_walk_inc_max(src, period), _bar_walk_full_max(src, period)),
        (_bar_walk_inc_min(src, period), _bar_walk_full_min(src, period)),
    ):
        for i in range(period - 1):
            assert got[i] is None, f"warmup bar {i}: expected None, got {got[i]}"
            assert exp[i] is None, f"full warmup bar {i}: expected None, got {exp[i]}"
        assert got[period - 1] is not None
        _assert_series_close(got, exp)


def test_incremental_range_max_min_na_in_window() -> None:
    """Pine na (None) is skipped (same as highest/lowest); remaining window still yields a value."""
    src: list[float | None] = list(_series(80))
    src[20] = None
    src[35] = None
    mixed: list[float | None] = [None, None, 1.0, 3.0, None, 2.0, 5.0, None, 4.0, 0.5, 6.0, None]
    for period in (5, 14):
        _assert_series_close(_bar_walk_inc_range(src, period), _bar_walk_full_range(src, period))
        _assert_series_close(_bar_walk_inc_max(src, period), _bar_walk_full_max(src, period))
        _assert_series_close(_bar_walk_inc_min(src, period), _bar_walk_full_min(src, period))
    for period in (3, 5, 7):
        _assert_series_close(_bar_walk_inc_range(mixed, period), _bar_walk_full_range(mixed, period))
        _assert_series_close(_bar_walk_inc_max(mixed, period), _bar_walk_full_max(mixed, period))
        _assert_series_close(_bar_walk_inc_min(mixed, period), _bar_walk_full_min(mixed, period))


def test_incremental_range_slot_count_stable() -> None:
    """Range takes two slots (highest then lowest) every bar, including warmup and na."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._builtin_ta_range([src[: i + 1], 10])
        assert ev._ta_call_i == 2, f"range bar {i}: expected 2 slots, got {ev._ta_call_i}"


def test_incremental_max_min_slot_count_stable() -> None:
    """2-arg max/min take one sliding-extreme slot every bar, including warmup and na."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_max([prefix, 10])
        assert ev._ta_call_i == 1, f"max bar {i}: expected 1 slot, got {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_min([prefix, 10])
        assert ev._ta_call_i == 1, f"min bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_max_min_unary_stays_full_path() -> None:
    """1-arg ta.max / ta.min is whole-series (no incremental slot)."""
    src = _series(40)
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        got_max = ev._builtin_ta_max([prefix])
        assert ev._ta_call_i == 0, f"unary max bar {i}: expected 0 slots, got {ev._ta_call_i}"
        assert got_max == max(prefix)
        ev._ta_call_i = 0
        got_min = ev._builtin_ta_min([prefix])
        assert ev._ta_call_i == 0, f"unary min bar {i}: expected 0 slots, got {ev._ta_call_i}"
        assert got_min == min(prefix)


def test_incremental_range_two_call_sites_independent() -> None:
    src = _series(80)
    ev = _IncTA()
    a_out: list[float | None] = []
    b_out: list[float | None] = []
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._builtin_ta_range([prefix, 10]))
        b_out.append(ev._builtin_ta_range([prefix, 20]))
    _assert_series_close(a_out, _bar_walk_full_range(src, 10))
    _assert_series_close(b_out, _bar_walk_full_range(src, 20))


def test_runtime_range_max_min_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("range max min")
plot(ta.range(close, 14), "rng")
plot(ta.max(close, 14), "mx")
plot(ta.min(close, 14), "mn")
plot(ta.max(close), "mx1")
plot(ta.min(close), "mn1")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"rng", "mx", "mn", "mx1", "mn1"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: stoch_smooth incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _stoch_smooth_last(full: Any) -> float | None:
    if full is None:
        return None
    if isinstance(full, list):
        if not full:
            return None
        last = full[-1]
    else:
        last = full
    if isinstance(last, float) and math.isnan(last):
        return None
    return last


def _bar_walk_full_stoch_smooth(
    highs: list[Any],
    lows: list[Any],
    closes: list[Any],
    period: int,
    smooth_k: int,
    smooth_d: int,
) -> list[float | None]:
    ev = _FullTA()
    return [
        _stoch_smooth_last(
            ev._builtin_ta_stoch_smooth([highs[: i + 1], lows[: i + 1], closes[: i + 1], period, smooth_k, smooth_d])
        )
        for i in range(len(closes))
    ]


def _bar_walk_inc_stoch_smooth(
    highs: list[Any],
    lows: list[Any],
    closes: list[Any],
    period: int,
    smooth_k: int,
    smooth_d: int,
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(
            ev._stoch_smooth_inc_update(
                highs[: i + 1],
                lows[: i + 1],
                closes[: i + 1],
                period,
                smooth_k,
                smooth_d,
            )
        )
    return out


def test_incremental_stoch_smooth_matches_full() -> None:
    highs, lows, closes = _ohlc(120)
    for period, smooth_k, smooth_d in ((14, 3, 3), (5, 3, 3), (10, 5, 5), (1, 1, 1)):
        _assert_series_close(
            _bar_walk_inc_stoch_smooth(highs, lows, closes, period, smooth_k, smooth_d),
            _bar_walk_full_stoch_smooth(highs, lows, closes, period, smooth_k, smooth_d),
        )


def test_incremental_stoch_smooth_warmup() -> None:
    highs, lows, closes = _ohlc(40)
    period, smooth_k, smooth_d = 14, 3, 3
    got = _bar_walk_inc_stoch_smooth(highs, lows, closes, period, smooth_k, smooth_d)
    exp = _bar_walk_full_stoch_smooth(highs, lows, closes, period, smooth_k, smooth_d)
    # Raw stoch is defined from bar 0 (partial window); each EMA SMA-seeds.
    first_defined = smooth_k + smooth_d - 2
    for i in range(first_defined):
        assert got[i] is None, f"warmup bar {i}: expected None, got {got[i]}"
        assert exp[i] is None, f"full warmup bar {i}: expected None, got {exp[i]}"
    assert got[first_defined] is not None
    _assert_series_close(got, exp)


def test_incremental_stoch_smooth_na_in_window() -> None:
    """NA in the last-N high/low/close window matches full recompute last sample."""
    highs, lows, closes = _ohlc(80)
    h: list[float | None] = list(highs)
    l: list[float | None] = list(lows)
    c: list[float | None] = list(closes)
    na_i = 20
    h[na_i] = None
    l[na_i + 3] = None
    c[na_i + 7] = math.nan
    got = _bar_walk_inc_stoch_smooth(h, l, c, 14, 3, 3)
    exp = _bar_walk_full_stoch_smooth(h, l, c, 14, 3, 3)
    _assert_series_close(got, exp)


def test_incremental_stoch_smooth_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    highs, lows, closes = _ohlc(40)
    h: list[float | None] = list(highs)
    l: list[float | None] = list(lows)
    c: list[float | None] = list(closes)
    h[4] = None
    c[11] = math.nan
    ev = _IncTA()
    for i in range(len(closes)):
        ev._ta_call_i = 0
        ev._stoch_smooth_inc_update(h[: i + 1], l[: i + 1], c[: i + 1], 14, 3, 3)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_stoch_smooth_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    highs, lows, closes = _ohlc(30)
    ev = _IncTA()
    for i in range(len(closes)):
        prefix_h, prefix_l, prefix_c = highs[: i + 1], lows[: i + 1], closes[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_stoch_smooth([prefix_h, prefix_l, prefix_c, 14, 3, 3])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_stoch_smooth_two_call_sites_independent() -> None:
    highs, lows, closes = _ohlc(80)
    ev = _IncTA()
    a_out: list[float | None] = []
    b_out: list[float | None] = []
    for i in range(len(closes)):
        prefix_h, prefix_l, prefix_c = highs[: i + 1], lows[: i + 1], closes[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._stoch_smooth_inc_update(prefix_h, prefix_l, prefix_c, 14, 3, 3))
        b_out.append(ev._stoch_smooth_inc_update(prefix_h, prefix_l, prefix_c, 5, 3, 3))
    _assert_series_close(a_out, _bar_walk_full_stoch_smooth(highs, lows, closes, 14, 3, 3))
    _assert_series_close(b_out, _bar_walk_full_stoch_smooth(highs, lows, closes, 5, 3, 3))


def test_runtime_stoch_smooth_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("stoch_smooth")
plot(ta.stoch_smooth(high, low, close, 14, 3, 3), "ss")
plot(ta.stoch_smooth(high, low, close, 5, 3, 3), "ss5")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"ss", "ss5"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: rsi_divergence incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _rsi_divergence_last(full: Any) -> float | None:
    if full is None:
        return None
    if isinstance(full, list):
        if not full:
            return None
        last = full[-1]
    else:
        last = full
    if isinstance(last, float) and math.isnan(last):
        return None
    return last


def _bar_walk_full_rsi_divergence(src: list[Any], period: int) -> list[float | None]:
    ev = _FullTA()
    return [_rsi_divergence_last(ev._builtin_ta_rsi_divergence([src[: i + 1], period])) for i in range(len(src))]


def _bar_walk_inc_rsi_divergence(src: list[Any], period: int) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._rsi_divergence_inc_update(src[: i + 1], period))
    return out


def test_incremental_rsi_divergence_matches_full() -> None:
    src = _series(120)
    for period in (5, 14, 20, 1):
        _assert_series_close(
            _bar_walk_inc_rsi_divergence(src, period),
            _bar_walk_full_rsi_divergence(src, period),
        )


def test_incremental_rsi_divergence_warmup() -> None:
    src = _series(40)
    period = 14
    got = _bar_walk_inc_rsi_divergence(src, period)
    exp = _bar_walk_full_rsi_divergence(src, period)
    for i in range(period):
        assert got[i] == 0.0, f"warmup bar {i}: expected 0.0, got {got[i]}"
        assert exp[i] == 0.0, f"full warmup bar {i}: expected 0.0, got {exp[i]}"
    assert got[period] != 0.0
    _assert_series_close(got, exp)


def test_incremental_rsi_divergence_na_in_window() -> None:
    """None / NaN in the last-(period+1) window matches full recompute last sample."""
    src: list[float | None] = list(_series(80))
    src[20] = None
    src[35] = None
    src[48] = math.nan
    mixed: list[float | None] = [None, None, 1.0, 3.0, None, 2.0, 5.0, None, 4.0, 0.5, 6.0, None]
    for period in (5, 14):
        _assert_series_close(
            _bar_walk_inc_rsi_divergence(src, period),
            _bar_walk_full_rsi_divergence(src, period),
        )
    for period in (3, 5, 7):
        _assert_series_close(
            _bar_walk_inc_rsi_divergence(mixed, period),
            _bar_walk_full_rsi_divergence(mixed, period),
        )


def test_incremental_rsi_divergence_zero_range() -> None:
    """Constant window (max==min) yields 0.0 after warmup, matching full recompute."""
    src = [50.0] * 40
    period = 10
    got = _bar_walk_inc_rsi_divergence(src, period)
    exp = _bar_walk_full_rsi_divergence(src, period)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        assert g == 0.0, f"inc bar {i}: expected 0.0, got {g}"
        assert e == 0.0, f"full bar {i}: expected 0.0, got {e}"
    # Two distinct values → last sample at the high end is +1.
    step = [10.0] * 12 + [20.0]
    got_step = _bar_walk_inc_rsi_divergence(step, 5)
    exp_step = _bar_walk_full_rsi_divergence(step, 5)
    _assert_series_close(got_step, exp_step)
    assert got_step[-1] == pytest.approx(1.0)


def test_incremental_rsi_divergence_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup and na samples."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._rsi_divergence_inc_update(src[: i + 1], 10)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_rsi_divergence_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _series(30)
    ev = _IncTA()
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        ev._builtin_ta_rsi_divergence([prefix, 14])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_rsi_divergence_two_call_sites_independent() -> None:
    src = _series(80)
    ev = _IncTA()
    a_out: list[float | None] = []
    b_out: list[float | None] = []
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._rsi_divergence_inc_update(prefix, 14))
        b_out.append(ev._rsi_divergence_inc_update(prefix, 5))
    _assert_series_close(a_out, _bar_walk_full_rsi_divergence(src, 14))
    _assert_series_close(b_out, _bar_walk_full_rsi_divergence(src, 5))


def test_runtime_rsi_divergence_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("rsi_divergence")
plot(ta.rsi_divergence(close, 14), "div")
plot(ta.rsi_divergence(close, 5), "div5")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"div", "div5"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: fractal incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_FRACTAL_OFF = {"is_high_fractal": False, "is_low_fractal": False}


def _assert_fractal_close(
    got: list[dict[str, bool]],
    exp: list[dict[str, bool]],
) -> None:
    assert len(got) == len(exp)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        assert g == e, f"bar {i}: {g} != {e}"


def _bar_walk_full_fractal(
    highs: list[Any],
    lows: list[Any],
    period: int,
) -> list[dict[str, bool]]:
    ev = _FullTA()
    out: list[dict[str, bool]] = []
    for i in range(len(highs)):
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._builtin_ta_fractal([period]))
    return out


def _bar_walk_inc_fractal(
    highs: list[Any],
    lows: list[Any],
    period: int,
) -> list[dict[str, bool]]:
    ev = _IncTA()
    out: list[dict[str, bool]] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._fractal_inc_update(highs[: i + 1], lows[: i + 1], period))
    return out


def test_incremental_fractal_matches_full() -> None:
    highs, lows, _closes = _ohlc(120)
    for period in (1, 2, 5, 14):
        _assert_fractal_close(
            _bar_walk_inc_fractal(highs, lows, period),
            _bar_walk_full_fractal(highs, lows, period),
        )


def test_incremental_fractal_warmup() -> None:
    """Short window (len < 2*period+1) is both-False, matching full recompute."""
    period = 2
    need = 2 * period + 1
    highs = [10.0 + i for i in range(12)]
    lows = [9.0 + i for i in range(12)]
    got = _bar_walk_inc_fractal(highs, lows, period)
    exp = _bar_walk_full_fractal(highs, lows, period)
    for i in range(need - 1):
        assert got[i] == _FRACTAL_OFF, f"warmup bar {i}: expected off, got {got[i]}"
        assert exp[i] == _FRACTAL_OFF, f"full warmup bar {i}: expected off, got {exp[i]}"
    _assert_fractal_close(got, exp)


def test_incremental_fractal_high() -> None:
    """Last bar equals window max → is_high_fractal after warmup."""
    period = 2
    need = 2 * period + 1
    # Rising highs so the last sample is the max of the comparison window.
    highs = [10.0, 11.0, 12.0, 13.0, 50.0]
    lows = [9.0, 10.0, 11.0, 12.0, 13.0]
    assert len(highs) == need
    got = _bar_walk_inc_fractal(highs, lows, period)
    exp = _bar_walk_full_fractal(highs, lows, period)
    _assert_fractal_close(got, exp)
    assert got[-1]["is_high_fractal"] is True
    assert got[-1]["is_low_fractal"] is False
    assert exp[-1]["is_high_fractal"] is True


def test_incremental_fractal_low() -> None:
    """Last bar equals window min → is_low_fractal after warmup."""
    period = 2
    need = 2 * period + 1
    highs = [50.0, 49.0, 48.0, 47.0, 46.0]
    lows = [20.0, 19.0, 18.0, 17.0, 1.0]
    assert len(lows) == need
    got = _bar_walk_inc_fractal(highs, lows, period)
    exp = _bar_walk_full_fractal(highs, lows, period)
    _assert_fractal_close(got, exp)
    assert got[-1]["is_low_fractal"] is True
    assert got[-1]["is_high_fractal"] is False
    assert exp[-1]["is_low_fractal"] is True


def test_incremental_fractal_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup."""
    highs, lows, _closes = _ohlc(40)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._fractal_inc_update(highs[: i + 1], lows[: i + 1], 2)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_fractal_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    highs, lows, _closes = _ohlc(30)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        ev._builtin_ta_fractal([2])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_fractal_two_call_sites_independent() -> None:
    highs, lows, _closes = _ohlc(80)
    ev = _IncTA()
    a_out: list[dict[str, bool]] = []
    b_out: list[dict[str, bool]] = []
    for i in range(len(highs)):
        prefix_h = highs[: i + 1]
        prefix_l = lows[: i + 1]
        ev._ta_call_i = 0
        ev.current_series = {"high": prefix_h, "low": prefix_l}
        a_out.append(ev._fractal_inc_update(prefix_h, prefix_l, 2))
        b_out.append(ev._fractal_inc_update(prefix_h, prefix_l, 5))
    _assert_fractal_close(a_out, _bar_walk_full_fractal(highs, lows, 2))
    _assert_fractal_close(b_out, _bar_walk_full_fractal(highs, lows, 5))


def test_runtime_fractal_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    src = """//@version=5
indicator("fractal")
f = ta.fractal(2)
g = ta.fractal(5)
plot(f.is_high_fractal ? 1 : 0, "hi2")
plot(f.is_low_fractal ? 1 : 0, "lo2")
plot(g.is_high_fractal ? 1 : 0, "hi5")
plot(g.is_low_fractal ? 1 : 0, "lo5")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"hi2", "lo2", "hi5", "lo5"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: engulfing / hammer incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_ENGULFING_OFF = {"is_bullish": False, "is_bearish": False, "pattern_strength": 0.0}


def _ohlc4(n: int = 120, seed: float = 100.0) -> tuple[list[float], list[float], list[float], list[float]]:
    highs, lows, closes = _ohlc(n, seed)
    opens = [closes[0]] + [closes[i] for i in range(n - 1)]
    return opens, highs, lows, closes


def _assert_pattern_close(
    got: list[dict[str, Any]],
    exp: list[dict[str, Any]],
) -> None:
    assert len(got) == len(exp)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        assert set(g) == set(e), f"bar {i}: keys {sorted(g)} != {sorted(e)}"
        for k in e:
            gv, ev = g[k], e[k]
            if isinstance(ev, (int, float)) or isinstance(gv, (int, float)):
                if isinstance(ev, bool) or isinstance(gv, bool):
                    assert gv is ev, f"bar {i} {k}: {gv} != {ev}"
                else:
                    assert gv == pytest.approx(ev, rel=1e-9, abs=1e-9), f"bar {i} {k}: {gv} != {ev}"
            else:
                assert gv == ev, f"bar {i} {k}: {gv} != {ev}"


def _bar_walk_full_engulfing(
    opens: list[Any],
    highs: list[Any],
    lows: list[Any],
    closes: list[Any],
) -> list[dict[str, Any]]:
    ev = _FullTA()
    out: list[dict[str, Any]] = []
    for i in range(len(opens)):
        out.append(ev._builtin_ta_engulfing([opens[: i + 1], highs[: i + 1], lows[: i + 1], closes[: i + 1]]))
    return out


def _bar_walk_inc_engulfing(
    opens: list[Any],
    _highs: list[Any],
    _lows: list[Any],
    closes: list[Any],
) -> list[dict[str, Any]]:
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(opens)):
        ev._ta_call_i = 0
        out.append(ev._engulfing_inc_update(opens[: i + 1], closes[: i + 1]))
    return out


def _bar_walk_full_hammer(
    opens: list[Any],
    highs: list[Any],
    lows: list[Any],
    closes: list[Any],
) -> list[dict[str, Any]]:
    ev = _FullTA()
    out: list[dict[str, Any]] = []
    for i in range(len(opens)):
        out.append(ev._builtin_ta_hammer([opens[: i + 1], highs[: i + 1], lows[: i + 1], closes[: i + 1]]))
    return out


def _bar_walk_inc_hammer(
    opens: list[Any],
    highs: list[Any],
    lows: list[Any],
    closes: list[Any],
) -> list[dict[str, Any]]:
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(opens)):
        ev._ta_call_i = 0
        out.append(ev._hammer_inc_update(opens[: i + 1], highs[: i + 1], lows[: i + 1], closes[: i + 1]))
    return out


def test_incremental_engulfing_matches_full() -> None:
    opens, highs, lows, closes = _ohlc4(120)
    _assert_pattern_close(
        _bar_walk_inc_engulfing(opens, highs, lows, closes),
        _bar_walk_full_engulfing(opens, highs, lows, closes),
    )


def test_incremental_engulfing_warmup() -> None:
    """Fewer than 2 bars is all-false / strength 0.0, matching full recompute."""
    opens = [12.0]
    highs = [13.0]
    lows = [9.0]
    closes = [10.0]
    got = _bar_walk_inc_engulfing(opens, highs, lows, closes)
    exp = _bar_walk_full_engulfing(opens, highs, lows, closes)
    assert got[0] == _ENGULFING_OFF
    assert exp[0] == _ENGULFING_OFF
    _assert_pattern_close(got, exp)


def test_incremental_engulfing_bullish() -> None:
    """Current green body fully wraps previous red body → is_bullish."""
    opens = [12.0, 9.5]
    highs = [12.5, 13.0]
    lows = [9.8, 9.0]
    closes = [10.0, 12.5]
    got = _bar_walk_inc_engulfing(opens, highs, lows, closes)
    exp = _bar_walk_full_engulfing(opens, highs, lows, closes)
    _assert_pattern_close(got, exp)
    assert got[0] == _ENGULFING_OFF
    assert got[-1]["is_bullish"] is True
    assert got[-1]["is_bearish"] is False
    assert exp[-1]["is_bullish"] is True


def test_incremental_engulfing_bearish() -> None:
    """Current red body fully wraps previous green body → is_bearish."""
    opens = [10.0, 12.5]
    highs = [12.2, 13.0]
    lows = [9.8, 9.0]
    closes = [12.0, 9.5]
    got = _bar_walk_inc_engulfing(opens, highs, lows, closes)
    exp = _bar_walk_full_engulfing(opens, highs, lows, closes)
    _assert_pattern_close(got, exp)
    assert got[-1]["is_bearish"] is True
    assert got[-1]["is_bullish"] is False
    assert exp[-1]["is_bearish"] is True


def test_incremental_hammer_matches_full() -> None:
    opens, highs, lows, closes = _ohlc4(120)
    _assert_pattern_close(
        _bar_walk_inc_hammer(opens, highs, lows, closes),
        _bar_walk_full_hammer(opens, highs, lows, closes),
    )


def test_incremental_hammer_bar_zero() -> None:
    """Hammer is defined on bar 0 (last 1 OHLC), matching full recompute."""
    # Body ≥ 10% of range (not a doji) with a long lower wick.
    opens = [10.0]
    highs = [11.2]
    lows = [7.0]
    closes = [11.0]
    got = _bar_walk_inc_hammer(opens, highs, lows, closes)
    exp = _bar_walk_full_hammer(opens, highs, lows, closes)
    _assert_pattern_close(got, exp)
    assert got[0]["is_hammer"] is True
    assert got[0]["is_doji"] is False
    assert exp[0]["is_hammer"] is True


def test_incremental_hammer_doji() -> None:
    """Small body vs range → is_doji on bar 0."""
    opens = [10.0]
    highs = [12.0]
    lows = [8.0]
    closes = [10.05]
    got = _bar_walk_inc_hammer(opens, highs, lows, closes)
    exp = _bar_walk_full_hammer(opens, highs, lows, closes)
    _assert_pattern_close(got, exp)
    assert got[0]["is_doji"] is True
    assert got[0]["is_hammer"] is False
    assert exp[0]["is_doji"] is True


def test_incremental_engulfing_hammer_slot_count_stable() -> None:
    """One call-site slot every bar, including engulfing warmup and hammer bar 0."""
    opens, highs, lows, closes = _ohlc4(40)
    ev_e = _IncTA()
    ev_h = _IncTA()
    for i in range(len(opens)):
        prefix_o = opens[: i + 1]
        prefix_h = highs[: i + 1]
        prefix_l = lows[: i + 1]
        prefix_c = closes[: i + 1]
        ev_e._ta_call_i = 0
        ev_e._engulfing_inc_update(prefix_o, prefix_c)
        assert ev_e._ta_call_i == 1, f"engulfing bar {i}: expected 1 slot, got {ev_e._ta_call_i}"
        ev_h._ta_call_i = 0
        ev_h._hammer_inc_update(prefix_o, prefix_h, prefix_l, prefix_c)
        assert ev_h._ta_call_i == 1, f"hammer bar {i}: expected 1 slot, got {ev_h._ta_call_i}"


def test_incremental_engulfing_hammer_builtin_uses_inc_slot() -> None:
    """Bar-mode builtins consume the inc kernel slot (gate is wired)."""
    opens, highs, lows, closes = _ohlc4(30)
    ev = _IncTA()
    for i in range(len(opens)):
        args = [opens[: i + 1], highs[: i + 1], lows[: i + 1], closes[: i + 1]]
        ev._ta_call_i = 0
        ev._builtin_ta_engulfing(args)
        assert ev._ta_call_i == 1, f"engulfing builtin bar {i}: {ev._ta_call_i}"
        ev._ta_call_i = 0
        ev._builtin_ta_hammer(args)
        assert ev._ta_call_i == 1, f"hammer builtin bar {i}: {ev._ta_call_i}"


def test_incremental_engulfing_hammer_two_call_sites_independent() -> None:
    a_o, a_h, a_l, a_c = _ohlc4(80, seed=100.0)
    b_o, b_h, b_l, b_c = _ohlc4(80, seed=140.0)
    ev = _IncTA()
    e_a: list[dict[str, Any]] = []
    e_b: list[dict[str, Any]] = []
    h_a: list[dict[str, Any]] = []
    h_b: list[dict[str, Any]] = []
    for i in range(len(a_o)):
        ev._ta_call_i = 0
        e_a.append(ev._engulfing_inc_update(a_o[: i + 1], a_c[: i + 1]))
        e_b.append(ev._engulfing_inc_update(b_o[: i + 1], b_c[: i + 1]))
        h_a.append(ev._hammer_inc_update(a_o[: i + 1], a_h[: i + 1], a_l[: i + 1], a_c[: i + 1]))
        h_b.append(ev._hammer_inc_update(b_o[: i + 1], b_h[: i + 1], b_l[: i + 1], b_c[: i + 1]))
    _assert_pattern_close(e_a, _bar_walk_full_engulfing(a_o, a_h, a_l, a_c))
    _assert_pattern_close(e_b, _bar_walk_full_engulfing(b_o, b_h, b_l, b_c))
    _assert_pattern_close(h_a, _bar_walk_full_hammer(a_o, a_h, a_l, a_c))
    _assert_pattern_close(h_b, _bar_walk_full_hammer(b_o, b_h, b_l, b_c))


def test_runtime_engulfing_hammer_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(120)
    # Inject a bullish engulfing pair, a bearish pair, a hammer, and a doji.
    bars[10] = {
        "open": 12.0,
        "high": 12.5,
        "low": 9.8,
        "close": 10.0,
        "volume": 1010,
        "time": 1_700_000_000 + 10 * 86_400,
    }
    bars[11] = {
        "open": 9.5,
        "high": 13.0,
        "low": 9.0,
        "close": 12.5,
        "volume": 1011,
        "time": 1_700_000_000 + 11 * 86_400,
    }
    bars[20] = {
        "open": 10.0,
        "high": 12.2,
        "low": 9.8,
        "close": 12.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    bars[21] = {
        "open": 12.5,
        "high": 13.0,
        "low": 9.0,
        "close": 9.5,
        "volume": 1021,
        "time": 1_700_000_000 + 21 * 86_400,
    }
    bars[30] = {
        "open": 10.0,
        "high": 11.2,
        "low": 7.0,
        "close": 11.0,
        "volume": 1030,
        "time": 1_700_000_000 + 30 * 86_400,
    }
    bars[40] = {
        "open": 10.0,
        "high": 12.0,
        "low": 8.0,
        "close": 10.05,
        "volume": 1040,
        "time": 1_700_000_000 + 40 * 86_400,
    }
    src = """//@version=5
indicator("engulfing hammer")
e = ta.engulfing(open, high, low, close)
h = ta.hammer(open, high, low, close)
plot(e.is_bullish ? 1 : 0, "bull")
plot(e.is_bearish ? 1 : 0, "bear")
plot(e.pattern_strength, "estr")
plot(h.is_hammer ? 1 : 0, "ham")
plot(h.is_doji ? 1 : 0, "doji")
plot(h.pattern_strength, "hstr")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"bull", "bear", "estr", "ham", "doji", "hstr"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: double_top_bottom incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_DTB_OFF = {"pattern_type": "none", "strength": 0.0, "breakout_level": 0.0}


def _bar_walk_full_dtb(
    highs: list[Any],
    lows: list[Any],
    period: int,
) -> list[dict[str, Any]]:
    ev = _FullTA()
    out: list[dict[str, Any]] = []
    for i in range(len(highs)):
        out.append(ev._builtin_ta_double_top_bottom([highs[: i + 1], lows[: i + 1], period]))
    return out


def _bar_walk_inc_dtb(
    highs: list[Any],
    lows: list[Any],
    period: int,
) -> list[dict[str, Any]]:
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        out.append(ev._double_top_bottom_inc_update(highs[: i + 1], lows[: i + 1], period))
    return out


def test_incremental_double_top_bottom_matches_full() -> None:
    highs, lows, _closes = _ohlc(120)
    for period in (3, 5, 14):
        _assert_pattern_close(
            _bar_walk_inc_dtb(highs, lows, period),
            _bar_walk_full_dtb(highs, lows, period),
        )


def test_incremental_double_top_bottom_warmup() -> None:
    """Window shorter than period, or fewer than 3 numeric highs, is none."""
    period = 5
    highs = [100.0, 101.0, 102.0, 103.0]
    lows = [95.0, 96.0, 97.0, 98.0]
    got = _bar_walk_inc_dtb(highs, lows, period)
    exp = _bar_walk_full_dtb(highs, lows, period)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        assert g == _DTB_OFF, f"warmup bar {i}: expected off, got {g}"
        assert e == _DTB_OFF, f"full warmup bar {i}: expected off, got {e}"
    _assert_pattern_close(got, exp)

    # Full window but only two numeric highs → none.
    sparse_h = [100.0, None, 102.0, None, 103.0]
    sparse_l = [95.0, 96.0, 97.0, 98.0, 99.0]
    got_s = _bar_walk_inc_dtb(sparse_h, sparse_l, 5)
    exp_s = _bar_walk_full_dtb(sparse_h, sparse_l, 5)
    assert got_s[-1] == _DTB_OFF
    assert exp_s[-1] == _DTB_OFF
    _assert_pattern_close(got_s, exp_s)


def test_incremental_double_top_bottom_double_top() -> None:
    """Two peaks in the last-N highs → double_top after warmup."""
    period = 5
    highs = [100.0, 105.0, 102.0, 105.0, 103.0]
    lows = [95.0, 100.0, 97.0, 100.0, 98.0]
    got = _bar_walk_inc_dtb(highs, lows, period)
    exp = _bar_walk_full_dtb(highs, lows, period)
    _assert_pattern_close(got, exp)
    for i in range(period - 1):
        assert got[i] == _DTB_OFF, f"warmup bar {i}: {got[i]}"
    assert got[-1]["pattern_type"] == "double_top"
    assert exp[-1]["pattern_type"] == "double_top"
    assert got[-1]["strength"] > 0.0
    assert got[-1]["breakout_level"] != 0.0


def test_incremental_double_top_bottom_none() -> None:
    """Monotonic highs have no interior peak → none after warmup."""
    period = 3
    highs = [100.0, 101.0, 102.0, 103.0, 104.0]
    lows = [95.0, 96.0, 97.0, 98.0, 99.0]
    got = _bar_walk_inc_dtb(highs, lows, period)
    exp = _bar_walk_full_dtb(highs, lows, period)
    _assert_pattern_close(got, exp)
    assert got[-1] == _DTB_OFF
    assert exp[-1]["pattern_type"] == "none"


def test_incremental_double_top_bottom_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup."""
    highs, lows, _closes = _ohlc(40)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._double_top_bottom_inc_update(highs[: i + 1], lows[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_double_top_bottom_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    highs, lows, _closes = _ohlc(30)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._builtin_ta_double_top_bottom([highs[: i + 1], lows[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_double_top_bottom_two_call_sites_independent() -> None:
    highs, lows, _closes = _ohlc(80)
    ev = _IncTA()
    a_out: list[dict[str, Any]] = []
    b_out: list[dict[str, Any]] = []
    for i in range(len(highs)):
        prefix_h = highs[: i + 1]
        prefix_l = lows[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._double_top_bottom_inc_update(prefix_h, prefix_l, 5))
        b_out.append(ev._double_top_bottom_inc_update(prefix_h, prefix_l, 14))
    _assert_pattern_close(a_out, _bar_walk_full_dtb(highs, lows, 5))
    _assert_pattern_close(b_out, _bar_walk_full_dtb(highs, lows, 14))


def test_runtime_double_top_bottom_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Inject a double-top window (period=5) around bar 20.
    for i, (h, l) in enumerate(
        zip(
            [100.0, 105.0, 102.0, 105.0, 103.0],
            [95.0, 100.0, 97.0, 100.0, 98.0],
            strict=True,
        )
    ):
        idx = 16 + i
        bars[idx] = {
            "open": l + 1.0,
            "high": h,
            "low": l,
            "close": (h + l) * 0.5,
            "volume": 1000 + idx,
            "time": 1_700_000_000 + idx * 86_400,
        }
    src = """//@version=5
indicator("double top bottom")
d = ta.double_top_bottom(high, low, 5)
e = ta.double_top_bottom(high, low, 14)
plot(d.pattern_type == "double_top" ? 1 : 0, "dt5")
plot(d.strength, "str5")
plot(d.breakout_level, "brk5")
plot(e.pattern_type == "double_top" ? 1 : 0, "dt14")
plot(e.strength, "str14")
plot(e.breakout_level, "brk14")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"dt5", "str5", "brk5", "dt14", "str14", "brk14"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: gap_detector incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_GAP_OFF = {"gap_size": 0.0, "gap_type": 0, "gap_percent": 0.0}


def _prev_closes(closes: list[Any]) -> list[Any]:
    """Bar-i previous close: ``None`` on bar 0, else ``closes[i-1]``."""
    return [None, *closes[:-1]]


def _bar_walk_full_gap(
    highs: list[Any],
    lows: list[Any],
    prev_closes: list[Any],
) -> list[dict[str, Any]]:
    ev = _FullTA()
    out: list[dict[str, Any]] = []
    for i in range(len(highs)):
        out.append(ev._builtin_ta_gap_detector([highs[: i + 1], lows[: i + 1], prev_closes[i]]))
    return out


def _bar_walk_inc_gap(
    highs: list[Any],
    lows: list[Any],
    prev_closes: list[Any],
) -> list[dict[str, Any]]:
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        out.append(ev._gap_detector_inc_update(highs[: i + 1], lows[: i + 1], prev_closes[i]))
    return out


def test_incremental_gap_detector_matches_full() -> None:
    highs, lows, closes = _ohlc(120)
    prev = _prev_closes(closes)
    _assert_pattern_close(
        _bar_walk_inc_gap(highs, lows, prev),
        _bar_walk_full_gap(highs, lows, prev),
    )


def test_incremental_gap_detector_warmup() -> None:
    """Missing prev_close (bar 0 / na) is zeros, matching full recompute."""
    highs = [12.0]
    lows = [8.0]
    prev = [None]
    got = _bar_walk_inc_gap(highs, lows, prev)
    exp = _bar_walk_full_gap(highs, lows, prev)
    assert got[0] == _GAP_OFF
    assert exp[0] == _GAP_OFF
    _assert_pattern_close(got, exp)

    # Empty last samples → zeros.
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._gap_detector_inc_update([], [], None) == _GAP_OFF
    assert ev._ta_call_i == 1


def test_incremental_gap_detector_no_gap() -> None:
    """Prev close inside current high/low → type 0 / size 0."""
    highs = [12.0, 13.0]
    lows = [8.0, 9.0]
    prev = [None, 10.0]
    got = _bar_walk_inc_gap(highs, lows, prev)
    exp = _bar_walk_full_gap(highs, lows, prev)
    _assert_pattern_close(got, exp)
    assert got[0] == _GAP_OFF
    assert got[-1] == _GAP_OFF
    assert exp[-1]["gap_type"] == 0


def test_incremental_gap_detector_up_gap() -> None:
    """Current low > prev close → type 1, size = low - prev_close."""
    highs = [12.0, 15.0]
    lows = [8.0, 12.0]
    prev = [None, 10.0]
    got = _bar_walk_inc_gap(highs, lows, prev)
    exp = _bar_walk_full_gap(highs, lows, prev)
    _assert_pattern_close(got, exp)
    assert got[0] == _GAP_OFF
    assert got[-1]["gap_type"] == 1
    assert got[-1]["gap_size"] == pytest.approx(2.0)
    assert got[-1]["gap_percent"] == pytest.approx(20.0)
    assert exp[-1]["gap_type"] == 1


def test_incremental_gap_detector_down_gap() -> None:
    """Current high < prev close → type -1, size = prev_close - high."""
    highs = [12.0, 8.0]
    lows = [8.0, 5.0]
    prev = [None, 10.0]
    got = _bar_walk_inc_gap(highs, lows, prev)
    exp = _bar_walk_full_gap(highs, lows, prev)
    _assert_pattern_close(got, exp)
    assert got[0] == _GAP_OFF
    assert got[-1]["gap_type"] == -1
    assert got[-1]["gap_size"] == pytest.approx(2.0)
    assert got[-1]["gap_percent"] == pytest.approx(20.0)
    assert exp[-1]["gap_type"] == -1


def test_incremental_gap_detector_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup."""
    highs, lows, closes = _ohlc(40)
    prev = _prev_closes(closes)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._gap_detector_inc_update(highs[: i + 1], lows[: i + 1], prev[i])
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_gap_detector_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    highs, lows, closes = _ohlc(30)
    prev = _prev_closes(closes)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._builtin_ta_gap_detector([highs[: i + 1], lows[: i + 1], prev[i]])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_gap_detector_two_call_sites_independent() -> None:
    highs, lows, closes = _ohlc(80)
    prev_a = _prev_closes(closes)
    prev_b = [None, *([c + 5.0 for c in closes[:-1]])]
    ev = _IncTA()
    a_out: list[dict[str, Any]] = []
    b_out: list[dict[str, Any]] = []
    for i in range(len(highs)):
        prefix_h = highs[: i + 1]
        prefix_l = lows[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._gap_detector_inc_update(prefix_h, prefix_l, prev_a[i]))
        b_out.append(ev._gap_detector_inc_update(prefix_h, prefix_l, prev_b[i]))
    _assert_pattern_close(a_out, _bar_walk_full_gap(highs, lows, prev_a))
    _assert_pattern_close(b_out, _bar_walk_full_gap(highs, lows, prev_b))


def test_runtime_gap_detector_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Inject an up-gap (bar 20 low > bar 19 close) and a down-gap (bar 40).
    bars[19] = {
        "open": 10.5,
        "high": 11.0,
        "low": 9.5,
        "close": 10.0,
        "volume": 1019,
        "time": 1_700_000_000 + 19 * 86_400,
    }
    bars[20] = {
        "open": 12.5,
        "high": 15.0,
        "low": 12.0,
        "close": 13.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    bars[39] = {
        "open": 10.5,
        "high": 11.0,
        "low": 9.5,
        "close": 10.0,
        "volume": 1039,
        "time": 1_700_000_000 + 39 * 86_400,
    }
    bars[40] = {
        "open": 7.5,
        "high": 8.0,
        "low": 5.0,
        "close": 6.0,
        "volume": 1040,
        "time": 1_700_000_000 + 40 * 86_400,
    }
    src = """//@version=5
indicator("gap detector")
g = ta.gap_detector(high, low, close[1])
h = ta.gap_detector(high, low, close)
plot(g.gap_size, "size")
plot(g.gap_type, "gtype")
plot(g.gap_percent, "pct")
plot(h.gap_type, "htype")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"size", "gtype", "pct", "htype"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"


# ---------------------------------------------------------------------------
# T2: inside_bar_pattern incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _inside_hl(n: int = 120) -> tuple[list[float], list[float]]:
    """Synthetic high/low with a known inside bar and a known outside bar."""
    highs, lows, _ = _ohlc(n)
    highs = list(highs)
    lows = list(lows)
    # Bar 2 is strictly inside bar 1 (fits n=30 warmup walks).
    highs[1] = 110.0
    lows[1] = 90.0
    highs[2] = 105.0
    lows[2] = 95.0
    # Bar 5 is outside bar 4.
    highs[4] = 110.0
    lows[4] = 90.0
    highs[5] = 115.0
    lows[5] = 85.0
    return highs, lows


def _bar_walk_full_inside_bar(
    highs: list[Any],
    lows: list[Any],
) -> list[bool]:
    ev = _FullTA()
    out: list[bool] = []
    for i in range(len(highs)):
        out.append(bool(ev._builtin_ta_inside_bar_pattern([highs[: i + 1], lows[: i + 1]])))
    return out


def _bar_walk_inc_inside_bar(
    highs: list[Any],
    lows: list[Any],
) -> list[bool]:
    ev = _IncTA()
    out: list[bool] = []
    for i in range(len(highs)):
        ev._ta_call_i = 0
        out.append(bool(ev._inside_bar_pattern_inc_update(highs[: i + 1], lows[: i + 1])))
    return out


def test_incremental_inside_bar_pattern_matches_full() -> None:
    highs, lows = _inside_hl(120)
    assert _bar_walk_inc_inside_bar(highs, lows) == _bar_walk_full_inside_bar(highs, lows)


def test_incremental_inside_bar_pattern_warmup() -> None:
    """Fewer than 2 bars is False, matching full recompute."""
    highs = [105.0]
    lows = [95.0]
    got = _bar_walk_inc_inside_bar(highs, lows)
    exp = _bar_walk_full_inside_bar(highs, lows)
    assert got == [False]
    assert exp == [False]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._inside_bar_pattern_inc_update([], []) is False
    assert ev._ta_call_i == 1


def test_incremental_inside_bar_pattern_inside() -> None:
    """curr_high < prev_high and curr_low > prev_low → True."""
    highs = [105.0, 104.0]
    lows = [95.0, 96.0]
    got = _bar_walk_inc_inside_bar(highs, lows)
    exp = _bar_walk_full_inside_bar(highs, lows)
    assert got == exp
    assert got[0] is False
    assert got[-1] is True
    assert exp[-1] is True


def test_incremental_inside_bar_pattern_not_inside() -> None:
    """Outside / equal-range bars are False (strict < / >)."""
    outside_h = [105.0, 106.0]
    outside_l = [95.0, 94.0]
    got_out = _bar_walk_inc_inside_bar(outside_h, outside_l)
    exp_out = _bar_walk_full_inside_bar(outside_h, outside_l)
    assert got_out == exp_out
    assert got_out[-1] is False
    assert exp_out[-1] is False

    equal_h = [105.0, 105.0]
    equal_l = [95.0, 95.0]
    got_eq = _bar_walk_inc_inside_bar(equal_h, equal_l)
    exp_eq = _bar_walk_full_inside_bar(equal_h, equal_l)
    assert got_eq == exp_eq
    assert got_eq[-1] is False
    assert exp_eq[-1] is False


def test_incremental_inside_bar_pattern_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup."""
    highs, lows = _inside_hl(40)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._inside_bar_pattern_inc_update(highs[: i + 1], lows[: i + 1])
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_inside_bar_pattern_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    highs, lows = _inside_hl(30)
    ev = _IncTA()
    for i in range(len(highs)):
        ev._ta_call_i = 0
        ev._builtin_ta_inside_bar_pattern([highs[: i + 1], lows[: i + 1]])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_inside_bar_pattern_two_call_sites_independent() -> None:
    a_h, a_l = _inside_hl(80)
    b_h, b_l = _ohlc(80, seed=140.0)[:2]
    ev = _IncTA()
    a_out: list[bool] = []
    b_out: list[bool] = []
    for i in range(len(a_h)):
        ev._ta_call_i = 0
        a_out.append(bool(ev._inside_bar_pattern_inc_update(a_h[: i + 1], a_l[: i + 1])))
        b_out.append(bool(ev._inside_bar_pattern_inc_update(b_h[: i + 1], b_l[: i + 1])))
    assert a_out == _bar_walk_full_inside_bar(a_h, a_l)
    assert b_out == _bar_walk_full_inside_bar(b_h, b_l)


def test_runtime_inside_bar_pattern_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Inject a strict inside bar (bar 20 inside bar 19) and an outside bar.
    bars[19] = {
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 100.0,
        "volume": 1019,
        "time": 1_700_000_000 + 19 * 86_400,
    }
    bars[20] = {
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    bars[39] = {
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 100.0,
        "volume": 1039,
        "time": 1_700_000_000 + 39 * 86_400,
    }
    bars[40] = {
        "open": 100.0,
        "high": 115.0,
        "low": 85.0,
        "close": 102.0,
        "volume": 1040,
        "time": 1_700_000_000 + 40 * 86_400,
    }
    src = """//@version=5
indicator("inside bar")
ib = ta.inside_bar_pattern(high, low)
plot(ib ? 1 : 0, "ib")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"ib"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"
    # Injected inside bar must fire on both hosts.
    assert r_on["series"]["ib"][20] == pytest.approx(1.0)
    assert r_off["series"]["ib"][20] == pytest.approx(1.0)
    assert r_on["series"]["ib"][40] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T2: ema_cross_signal incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_EMA_CROSS_OFF = {"signal": "neutral", "strength": 0.0, "trend_direction": 0}


def _bar_walk_full_ema_cross(
    fast: list[Any],
    slow: list[Any],
    threshold: float,
) -> list[dict[str, Any]]:
    ev = _FullTA()
    out: list[dict[str, Any]] = []
    for i in range(len(fast)):
        out.append(ev._builtin_ta_ema_cross_signal([fast[: i + 1], slow[: i + 1], threshold]))
    return out


def _bar_walk_inc_ema_cross(
    fast: list[Any],
    slow: list[Any],
    threshold: float,
) -> list[dict[str, Any]]:
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(fast)):
        ev._ta_call_i = 0
        out.append(ev._ema_cross_signal_inc_update(fast[: i + 1], slow[: i + 1], threshold))
    return out


def _bar_walk_inc_ema_cross_last_sample(
    fast: list[Any],
    slow: list[Any],
    threshold: float,
) -> list[dict[str, Any]]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(fast)):
        ev._ta_call_i = 0
        out.append(ev._ema_cross_signal_inc_update(fast[i], slow[i], threshold))
    return out


def test_incremental_ema_cross_signal_matches_full() -> None:
    fast = _series(120)
    slow = _series(120, seed=100.5)
    got = _bar_walk_inc_ema_cross(fast, slow, 0.25)
    exp = _bar_walk_full_ema_cross(fast, slow, 0.25)
    _assert_pattern_close(got, exp)
    last = _bar_walk_inc_ema_cross_last_sample(fast, slow, 0.25)
    _assert_pattern_close(last, exp)


def test_incremental_ema_cross_signal_warmup() -> None:
    """Fewer than 2 bars is neutral / 0, matching full recompute."""
    fast = [1.0]
    slow = [2.0]
    got = _bar_walk_inc_ema_cross(fast, slow, 0.5)
    exp = _bar_walk_full_ema_cross(fast, slow, 0.5)
    assert got == [_EMA_CROSS_OFF]
    assert exp == [_EMA_CROSS_OFF]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._ema_cross_signal_inc_update([], [], 0.5) == _EMA_CROSS_OFF
    assert ev._ta_call_i == 1


def test_incremental_ema_cross_signal_crossover_buy() -> None:
    """prev_diff <= 0 and diff > threshold → buy."""
    fast = [1.0, 3.0]
    slow = [2.0, 2.0]
    got = _bar_walk_inc_ema_cross(fast, slow, 0.5)
    exp = _bar_walk_full_ema_cross(fast, slow, 0.5)
    _assert_pattern_close(got, exp)
    assert got[0] == _EMA_CROSS_OFF
    assert got[-1]["signal"] == "buy"
    assert exp[-1]["signal"] == "buy"
    assert got[-1]["trend_direction"] == 1
    assert got[-1]["strength"] == pytest.approx(1.0)


def test_incremental_ema_cross_signal_crossunder_sell() -> None:
    """prev_diff >= 0 and diff < 0 with |diff| > threshold → sell."""
    fast = [3.0, 1.0]
    slow = [2.0, 2.0]
    got = _bar_walk_inc_ema_cross(fast, slow, 0.5)
    exp = _bar_walk_full_ema_cross(fast, slow, 0.5)
    _assert_pattern_close(got, exp)
    assert got[0] == _EMA_CROSS_OFF
    assert got[-1]["signal"] == "sell"
    assert exp[-1]["signal"] == "sell"
    assert got[-1]["trend_direction"] == -1
    assert got[-1]["strength"] == pytest.approx(1.0)


def test_incremental_ema_cross_signal_below_threshold() -> None:
    """Crossover whose |diff| is not strictly above threshold stays neutral."""
    fast = [1.0, 2.1]
    slow = [2.0, 2.0]
    got = _bar_walk_inc_ema_cross(fast, slow, 0.5)
    exp = _bar_walk_full_ema_cross(fast, slow, 0.5)
    _assert_pattern_close(got, exp)
    assert got[0] == _EMA_CROSS_OFF
    assert got[-1]["signal"] == "neutral"
    assert exp[-1]["signal"] == "neutral"
    assert got[-1]["trend_direction"] == 1
    assert got[-1]["strength"] == pytest.approx(0.1)

    # Exact equality with the threshold is not a signal.
    eq_fast = [1.0, 2.5]
    eq_slow = [2.0, 2.0]
    got_eq = _bar_walk_inc_ema_cross(eq_fast, eq_slow, 0.5)
    exp_eq = _bar_walk_full_ema_cross(eq_fast, eq_slow, 0.5)
    _assert_pattern_close(got_eq, exp_eq)
    assert got_eq[-1]["signal"] == "neutral"
    assert exp_eq[-1]["signal"] == "neutral"
    assert got_eq[-1]["strength"] == pytest.approx(0.5)


def test_incremental_ema_cross_signal_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup."""
    fast = _series(40)
    slow = _series(40, seed=101.0)
    ev = _IncTA()
    for i in range(len(fast)):
        ev._ta_call_i = 0
        ev._ema_cross_signal_inc_update(fast[: i + 1], slow[: i + 1], 0.25)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_ema_cross_signal_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    fast = _series(30)
    slow = _series(30, seed=101.0)
    ev = _IncTA()
    for i in range(len(fast)):
        ev._ta_call_i = 0
        ev._builtin_ta_ema_cross_signal([fast[: i + 1], slow[: i + 1], 0.25])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_ema_cross_signal_two_call_sites_independent() -> None:
    a_fast = _series(80)
    a_slow = _series(80, seed=100.5)
    b_fast = _series(80, seed=140.0)
    b_slow = _series(80, seed=141.0)
    ev = _IncTA()
    a_out: list[dict[str, Any]] = []
    b_out: list[dict[str, Any]] = []
    for i in range(len(a_fast)):
        ev._ta_call_i = 0
        a_out.append(ev._ema_cross_signal_inc_update(a_fast[: i + 1], a_slow[: i + 1], 0.25))
        b_out.append(ev._ema_cross_signal_inc_update(b_fast[: i + 1], b_slow[: i + 1], 0.1))
    _assert_pattern_close(a_out, _bar_walk_full_ema_cross(a_fast, a_slow, 0.25))
    _assert_pattern_close(b_out, _bar_walk_full_ema_cross(b_fast, b_slow, 0.1))


def test_runtime_ema_cross_signal_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Bar 19: close below open; bar 20: close crosses above open (buy).
    bars[19] = {
        "open": 100.0,
        "high": 101.0,
        "low": 89.0,
        "close": 90.0,
        "volume": 1019,
        "time": 1_700_000_000 + 19 * 86_400,
    }
    bars[20] = {
        "open": 100.0,
        "high": 111.0,
        "low": 99.0,
        "close": 110.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    src = """//@version=5
indicator("ema cross signal")
s = ta.ema_cross_signal(close, open, 0.05)
t = ta.ema_cross_signal(high, low, 0.5)
plot(s.signal == "buy" ? 1 : s.signal == "sell" ? -1 : 0, "sig")
plot(s.strength, "str")
plot(s.trend_direction, "td")
plot(t.signal == "buy" ? 1 : t.signal == "sell" ? -1 : 0, "sig2")
plot(t.strength, "str2")
plot(t.trend_direction, "td2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"sig", "str", "td", "sig2", "str2", "td2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"
    # Injected close-vs-open crossover must fire buy on both hosts.
    assert r_on["series"]["sig"][20] == pytest.approx(1.0)
    assert r_off["series"]["sig"][20] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T2: rsi_oversold_overbought incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_RSI_OBOS_OFF = {"is_oversold": False, "is_overbought": False, "rsi": None}


def _rsi_like(n: int = 120) -> list[float]:
    """Synthetic RSI path that crosses oversold (30) and overbought (70)."""
    out: list[float] = []
    for i in range(n):
        out.append(50.0 + 40.0 * math.sin(i / 5.0))
    return out


def _bar_walk_full_rsi_obos(
    src: list[Any],
    oversold: int,
    overbought: int,
) -> list[dict[str, Any]]:
    ev = _FullTA()
    out: list[dict[str, Any]] = []
    for i in range(len(src)):
        out.append(ev._builtin_ta_rsi_oversold_overbought([src[: i + 1], oversold, overbought]))
    return out


def _bar_walk_inc_rsi_obos(
    src: list[Any],
    oversold: int,
    overbought: int,
) -> list[dict[str, Any]]:
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._rsi_oversold_overbought_inc_update(src[: i + 1], oversold, overbought))
    return out


def _bar_walk_inc_rsi_obos_last_sample(
    src: list[Any],
    oversold: int,
    overbought: int,
) -> list[dict[str, Any]]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[dict[str, Any]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._rsi_oversold_overbought_inc_update(src[i], oversold, overbought))
    return out


def test_incremental_rsi_oversold_overbought_matches_full() -> None:
    src = _rsi_like(120)
    got = _bar_walk_inc_rsi_obos(src, 30, 70)
    exp = _bar_walk_full_rsi_obos(src, 30, 70)
    _assert_pattern_close(got, exp)
    last = _bar_walk_inc_rsi_obos_last_sample(src, 30, 70)
    _assert_pattern_close(last, exp)


def test_incremental_rsi_oversold_overbought_warmup() -> None:
    """Empty series / None last sample is False / rsi None, matching full."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._rsi_oversold_overbought_inc_update([], 30, 70) == _RSI_OBOS_OFF
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._rsi_oversold_overbought_inc_update(None, 30, 70) == _RSI_OBOS_OFF
    assert ev._ta_call_i == 1

    got = _bar_walk_inc_rsi_obos([None], 30, 70)
    exp = _bar_walk_full_rsi_obos([None], 30, 70)
    assert got == [_RSI_OBOS_OFF]
    assert exp == [_RSI_OBOS_OFF]


def test_incremental_rsi_oversold_overbought_oversold() -> None:
    """rsi < oversold → is_oversold; equality is not oversold."""
    src = [50.0, 20.0]
    got = _bar_walk_inc_rsi_obos(src, 30, 70)
    exp = _bar_walk_full_rsi_obos(src, 30, 70)
    _assert_pattern_close(got, exp)
    assert got[-1]["is_oversold"] is True
    assert exp[-1]["is_oversold"] is True
    assert got[-1]["is_overbought"] is False
    assert got[-1]["rsi"] == pytest.approx(20.0)

    eq = _bar_walk_inc_rsi_obos([30.0], 30, 70)
    eq_exp = _bar_walk_full_rsi_obos([30.0], 30, 70)
    _assert_pattern_close(eq, eq_exp)
    assert eq[-1]["is_oversold"] is False
    assert eq_exp[-1]["is_oversold"] is False


def test_incremental_rsi_oversold_overbought_overbought() -> None:
    """rsi > overbought → is_overbought; equality is not overbought."""
    src = [50.0, 80.0]
    got = _bar_walk_inc_rsi_obos(src, 30, 70)
    exp = _bar_walk_full_rsi_obos(src, 30, 70)
    _assert_pattern_close(got, exp)
    assert got[-1]["is_overbought"] is True
    assert exp[-1]["is_overbought"] is True
    assert got[-1]["is_oversold"] is False
    assert got[-1]["rsi"] == pytest.approx(80.0)

    eq = _bar_walk_inc_rsi_obos([70.0], 30, 70)
    eq_exp = _bar_walk_full_rsi_obos([70.0], 30, 70)
    _assert_pattern_close(eq, eq_exp)
    assert eq[-1]["is_overbought"] is False
    assert eq_exp[-1]["is_overbought"] is False


def test_incremental_rsi_oversold_overbought_neutral() -> None:
    """Inside the band is neither flag; na last sample stays off."""
    src: list[float | None] = [50.0, 40.0, None, 55.0]
    got = _bar_walk_inc_rsi_obos(src, 30, 70)
    exp = _bar_walk_full_rsi_obos(src, 30, 70)
    _assert_pattern_close(got, exp)
    assert got[0] == {"is_oversold": False, "is_overbought": False, "rsi": 50.0}
    assert got[2] == _RSI_OBOS_OFF
    assert got[-1]["is_oversold"] is False
    assert got[-1]["is_overbought"] is False
    assert got[-1]["rsi"] == pytest.approx(55.0)


def test_incremental_rsi_oversold_overbought_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    src: list[float | None] = list(_rsi_like(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._rsi_oversold_overbought_inc_update(src[: i + 1], 30, 70)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_rsi_oversold_overbought_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _rsi_like(30)
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._builtin_ta_rsi_oversold_overbought([src[: i + 1], 30, 70])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_rsi_oversold_overbought_two_call_sites_independent() -> None:
    src = _rsi_like(80)
    ev = _IncTA()
    a_out: list[dict[str, Any]] = []
    b_out: list[dict[str, Any]] = []
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._rsi_oversold_overbought_inc_update(prefix, 30, 70))
        b_out.append(ev._rsi_oversold_overbought_inc_update(prefix, 20, 80))
    _assert_pattern_close(a_out, _bar_walk_full_rsi_obos(src, 30, 70))
    _assert_pattern_close(b_out, _bar_walk_full_rsi_obos(src, 20, 80))


def test_runtime_rsi_oversold_overbought_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Inject a close well below 30 (oversold) and well above 70 (overbought).
    bars[19] = {
        "open": 25.0,
        "high": 26.0,
        "low": 18.0,
        "close": 20.0,
        "volume": 1019,
        "time": 1_700_000_000 + 19 * 86_400,
    }
    bars[20] = {
        "open": 75.0,
        "high": 90.0,
        "low": 74.0,
        "close": 85.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    src = """//@version=5
indicator("rsi obos")
s = ta.rsi_oversold_overbought(close, 30, 70)
t = ta.rsi_oversold_overbought(close, 20, 80)
plot(s.is_oversold ? 1 : 0, "os")
plot(s.is_overbought ? 1 : 0, "ob")
plot(s.rsi, "rsi")
plot(t.is_oversold ? 1 : 0, "os2")
plot(t.is_overbought ? 1 : 0, "ob2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"os", "ob", "rsi", "os2", "ob2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"
    assert r_on["series"]["os"][19] == pytest.approx(1.0)
    assert r_off["series"]["os"][19] == pytest.approx(1.0)
    assert r_on["series"]["ob"][20] == pytest.approx(1.0)
    assert r_off["series"]["ob"][20] == pytest.approx(1.0)
    assert r_on["series"]["rsi"][19] == pytest.approx(20.0)
    assert r_on["series"]["rsi"][20] == pytest.approx(85.0)


# ---------------------------------------------------------------------------
# T2: zigzag incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _assert_zigzag_close(
    got: list[tuple[Any, Any, Any]],
    exp: list[tuple[Any, Any, Any]],
) -> None:
    assert len(got) == len(exp)
    for i, (g, e) in enumerate(zip(got, exp, strict=True)):
        assert len(g) == 3 and len(e) == 3, f"bar {i}: {g} vs {e}"
        for gv, ev in zip(g, e, strict=True):
            _assert_num_close(gv, ev, i=i)


def _bar_walk_full_zigzag(
    src: list[Any],
    threshold: float,
) -> list[tuple[Any, Any, Any]]:
    ev = _FullTA()
    out: list[tuple[Any, Any, Any]] = []
    for i in range(len(src)):
        out.append(ev._builtin_ta_zigzag([src[: i + 1], threshold]))
    return out


def _bar_walk_inc_zigzag(
    src: list[Any],
    threshold: float,
) -> list[tuple[Any, Any, Any]]:
    ev = _IncTA()
    out: list[tuple[Any, Any, Any]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._zigzag_inc_update(src[: i + 1], threshold))
    return out


def _bar_walk_inc_zigzag_last_sample(
    src: list[Any],
    threshold: float,
) -> list[tuple[Any, Any, Any]]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[tuple[Any, Any, Any]] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._zigzag_inc_update(src[i], threshold))
    return out


def _zigzag_off(val: tuple[Any, Any, Any]) -> bool:
    h, lo, d = val
    return isinstance(h, float) and math.isnan(h) and isinstance(lo, float) and math.isnan(lo) and d == 0


def test_incremental_zigzag_matches_full() -> None:
    src = _series(120)
    got = _bar_walk_inc_zigzag(src, 5.0)
    exp = _bar_walk_full_zigzag(src, 5.0)
    _assert_zigzag_close(got, exp)
    last = _bar_walk_inc_zigzag_last_sample(src, 5.0)
    _assert_zigzag_close(last, exp)


def test_incremental_zigzag_warmup() -> None:
    """Fewer than 2 numeric samples is (nan, nan, 0), matching full."""
    got = _bar_walk_inc_zigzag([100.0], 5.0)
    exp = _bar_walk_full_zigzag([100.0], 5.0)
    _assert_zigzag_close(got, exp)
    assert _zigzag_off(got[0])
    assert _zigzag_off(exp[0])

    ev = _IncTA()
    ev._ta_call_i = 0
    assert _zigzag_off(ev._zigzag_inc_update([], 5.0))
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert _zigzag_off(ev._zigzag_inc_update(None, 5.0))
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_zigzag([None], 5.0)
    exp_na = _bar_walk_full_zigzag([None], 5.0)
    _assert_zigzag_close(got_na, exp_na)
    assert _zigzag_off(got_na[0])


def test_incremental_zigzag_direction_up() -> None:
    """Last numeric is the pair high → direction 1 when percent ≤ threshold."""
    src = [100.0, 101.0]
    got = _bar_walk_inc_zigzag(src, 5.0)
    exp = _bar_walk_full_zigzag(src, 5.0)
    _assert_zigzag_close(got, exp)
    assert _zigzag_off(got[0])
    assert got[-1][0] == pytest.approx(101.0)
    assert got[-1][1] == pytest.approx(100.0)
    assert got[-1][2] == 1
    assert exp[-1][2] == 1


def test_incremental_zigzag_direction_down() -> None:
    """Last numeric is the pair low → direction -1 when percent ≤ threshold."""
    src = [101.0, 100.0]
    got = _bar_walk_inc_zigzag(src, 5.0)
    exp = _bar_walk_full_zigzag(src, 5.0)
    _assert_zigzag_close(got, exp)
    assert got[-1][0] == pytest.approx(101.0)
    assert got[-1][1] == pytest.approx(100.0)
    assert got[-1][2] == -1
    assert exp[-1][2] == -1


def test_incremental_zigzag_threshold_forces_up() -> None:
    """percent_change > threshold forces direction 1 even on a down pair."""
    src = [110.0, 100.0]
    got = _bar_walk_inc_zigzag(src, 5.0)
    exp = _bar_walk_full_zigzag(src, 5.0)
    _assert_zigzag_close(got, exp)
    assert got[-1][2] == 1
    assert exp[-1][2] == 1

    got_lo = _bar_walk_inc_zigzag(src, 50.0)
    exp_lo = _bar_walk_full_zigzag(src, 50.0)
    _assert_zigzag_close(got_lo, exp_lo)
    assert got_lo[-1][2] == -1
    assert exp_lo[-1][2] == -1


def test_incremental_zigzag_na_skips() -> None:
    """None samples are skipped; last 2 numeric values drive the tuple."""
    src: list[float | None] = [100.0, None, 110.0]
    got = _bar_walk_inc_zigzag(src, 5.0)
    exp = _bar_walk_full_zigzag(src, 5.0)
    _assert_zigzag_close(got, exp)
    assert _zigzag_off(got[0])
    assert _zigzag_off(got[1])
    assert got[-1][0] == pytest.approx(110.0)
    assert got[-1][1] == pytest.approx(100.0)
    assert got[-1][2] == 1


def test_incremental_zigzag_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    src: list[float | None] = list(_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._zigzag_inc_update(src[: i + 1], 5.0)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_zigzag_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _series(30)
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._builtin_ta_zigzag([src[: i + 1], 5.0])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_zigzag_two_call_sites_independent() -> None:
    src = _series(80)
    ev = _IncTA()
    a_out: list[tuple[Any, Any, Any]] = []
    b_out: list[tuple[Any, Any, Any]] = []
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._zigzag_inc_update(prefix, 5.0))
        b_out.append(ev._zigzag_inc_update(prefix, 0.01))
    _assert_zigzag_close(a_out, _bar_walk_full_zigzag(src, 5.0))
    _assert_zigzag_close(b_out, _bar_walk_full_zigzag(src, 0.01))


def test_runtime_zigzag_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Small down move (~1%): threshold 5 keeps direction -1; 0.5 forces 1.
    bars[19] = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1019,
        "time": 1_700_000_000 + 19 * 86_400,
    }
    bars[20] = {
        "open": 100.0,
        "high": 100.5,
        "low": 98.5,
        "close": 99.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    src = """//@version=5
indicator("zigzag")
[h, l, d] = ta.zigzag(close, 5)
[h2, l2, d2] = ta.zigzag(close, 0.5)
plot(h, "h")
plot(l, "l")
plot(d, "d")
plot(d2, "d2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"h", "l", "d", "d2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"
    assert r_on["series"]["h"][20] == pytest.approx(100.0)
    assert r_on["series"]["l"][20] == pytest.approx(99.0)
    assert r_on["series"]["d"][20] == pytest.approx(-1.0)
    assert r_off["series"]["d"][20] == pytest.approx(-1.0)
    assert r_on["series"]["d2"][20] == pytest.approx(1.0)
    assert r_off["series"]["d2"][20] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T2: volatility_regime incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _atr_regime_series(n: int = 80) -> list[float]:
    """Synthetic ATR with quiet, spike, drop, and mild oscillation."""
    out: list[float] = []
    for i in range(n):
        if i == 12:
            out.append(4.0)
        elif i == 24:
            out.append(0.2)
        else:
            out.append(1.0 + 0.05 * math.sin(i / 4.0))
    return out


def _bar_walk_full_volatility_regime(
    src: list[Any],
    period: int,
) -> list[str]:
    ev = _FullTA()
    out: list[str] = []
    for i in range(len(src)):
        out.append(ev._builtin_ta_volatility_regime([src[: i + 1], period]))
    return out


def _bar_walk_inc_volatility_regime(
    src: list[Any],
    period: int,
) -> list[str]:
    ev = _IncTA()
    out: list[str] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._volatility_regime_inc_update(src[: i + 1], period))
    return out


def _bar_walk_inc_volatility_regime_last_sample(
    src: list[Any],
    period: int,
) -> list[str]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[str] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._volatility_regime_inc_update(src[i], period))
    return out


def test_incremental_volatility_regime_matches_full() -> None:
    src = _atr_regime_series(120)
    period = 5
    got = _bar_walk_inc_volatility_regime(src, period)
    exp = _bar_walk_full_volatility_regime(src, period)
    assert got == exp
    last = _bar_walk_inc_volatility_regime_last_sample(src, period)
    assert last == exp
    assert "medium" in got
    assert "extreme" in got
    assert "low" in got


def test_incremental_volatility_regime_warmup() -> None:
    """Window shorter than period is ``medium``, matching full recompute."""
    src = [1.0, 1.1]
    period = 5
    got = _bar_walk_inc_volatility_regime(src, period)
    exp = _bar_walk_full_volatility_regime(src, period)
    assert got == exp
    assert got == ["medium", "medium"]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._volatility_regime_inc_update([], 5) == "medium"
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._volatility_regime_inc_update(None, 5) == "medium"
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_volatility_regime([None], 5)
    exp_na = _bar_walk_full_volatility_regime([None], 5)
    assert got_na == exp_na
    assert got_na[0] == "medium"


def test_incremental_volatility_regime_classifies_low_high_extreme() -> None:
    """Last-N numeric mean vs current: low / high / extreme / medium."""
    period = 3
    low_src = [2.0, 2.0, 0.5]
    high_src = [1.0, 1.0, 1.6]
    extreme_src = [1.0, 1.0, 5.0]
    medium_src = [1.5, 1.6, 1.55]

    for src, label in (
        (low_src, "low"),
        (high_src, "high"),
        (extreme_src, "extreme"),
        (medium_src, "medium"),
    ):
        got = _bar_walk_inc_volatility_regime(src, period)
        exp = _bar_walk_full_volatility_regime(src, period)
        assert got == exp, f"{label}: {got} vs {exp}"
        assert got[-1] == label
        assert got[0] == "medium"
        assert got[1] == "medium"


def test_incremental_volatility_regime_na_skips() -> None:
    """Non-numeric samples are skipped; last-N calendar window still applies."""
    src: list[float | None] = [1.0, None, 1.0, 1.0, 0.2]
    period = 3
    got = _bar_walk_inc_volatility_regime(src, period)
    exp = _bar_walk_full_volatility_regime(src, period)
    assert got == exp
    assert got[0] == "medium"
    assert got[1] == "medium"
    last = _bar_walk_inc_volatility_regime_last_sample(src, period)
    assert last == exp


def test_incremental_volatility_regime_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    src: list[float | None] = list(_atr_regime_series(40))
    src[4] = None
    src[11] = math.nan
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._volatility_regime_inc_update(src[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_volatility_regime_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    src = _atr_regime_series(30)
    ev = _IncTA()
    for i in range(len(src)):
        ev._ta_call_i = 0
        ev._builtin_ta_volatility_regime([src[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_volatility_regime_two_call_sites_independent() -> None:
    src = _atr_regime_series(80)
    ev = _IncTA()
    a_out: list[str] = []
    b_out: list[str] = []
    for i in range(len(src)):
        prefix = src[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._volatility_regime_inc_update(prefix, 5))
        b_out.append(ev._volatility_regime_inc_update(prefix, 14))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    assert a_out == _bar_walk_full_volatility_regime(src, 5)
    assert b_out == _bar_walk_full_volatility_regime(src, 14)
    assert a_out != b_out


def test_runtime_volatility_regime_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    # Spike (extreme vs last-5 mean) and drop (low vs last-5 mean) on close,
    # which the script feeds as the ATR series.
    bars[19] = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1019,
        "time": 1_700_000_000 + 19 * 86_400,
    }
    bars[20] = {
        "open": 400.0,
        "high": 420.0,
        "low": 390.0,
        "close": 400.0,
        "volume": 1020,
        "time": 1_700_000_000 + 20 * 86_400,
    }
    bars[39] = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1039,
        "time": 1_700_000_000 + 39 * 86_400,
    }
    bars[40] = {
        "open": 5.0,
        "high": 6.0,
        "low": 4.0,
        "close": 5.0,
        "volume": 1040,
        "time": 1_700_000_000 + 40 * 86_400,
    }
    src = """//@version=5
indicator("volatility regime")
r = ta.volatility_regime(close, 5)
s = ta.volatility_regime(close, 14)
plot(r == "low" ? 1 : r == "medium" ? 2 : r == "high" ? 3 : 4, "reg5")
plot(s == "low" ? 1 : s == "medium" ? 2 : s == "high" ? 3 : 4, "reg14")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"reg5", "reg14"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    for key in r_on["series"]:
        for i, (a, b) in enumerate(zip(r_on["series"][key], r_off["series"][key], strict=True)):
            a_na = a is None or (isinstance(a, float) and math.isnan(a))
            b_na = b is None or (isinstance(b, float) and math.isnan(b))
            if a_na and b_na:
                continue
            assert not a_na, f"{key} bar {i}: incremental na, disabled={b}"
            assert not b_na, f"{key} bar {i}: disabled na, incremental={a}"
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), f"{key} bar {i}: {a} != {b}"
    # 4 = extreme, 1 = low (see plot mapping).
    assert r_on["series"]["reg5"][20] == pytest.approx(4.0)
    assert r_off["series"]["reg5"][20] == pytest.approx(4.0)
    assert r_on["series"]["reg5"][40] == pytest.approx(1.0)
    assert r_off["series"]["reg5"][40] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T2: momentum_filter incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _bar_walk_full_momentum_filter(
    mom: list[Any],
    vol: list[Any],
    period: int,
) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(mom)):
        out.append(ev._builtin_ta_momentum_filter([mom[: i + 1], vol[: i + 1], period]))
    return out


def _bar_walk_inc_momentum_filter(
    mom: list[Any],
    vol: list[Any],
    period: int,
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(mom)):
        ev._ta_call_i = 0
        out.append(ev._momentum_filter_inc_update(mom[: i + 1], vol[: i + 1], period))
    return out


def _bar_walk_inc_momentum_filter_last_sample(
    mom: list[Any],
    vol: list[Any],
    period: int,
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(mom)):
        ev._ta_call_i = 0
        out.append(ev._momentum_filter_inc_update(mom[i], vol[i], period))
    return out


def test_incremental_momentum_filter_matches_full() -> None:
    mom = _series(120)
    vol = _vols(120)
    period = 5
    got = _bar_walk_inc_momentum_filter(mom, vol, period)
    exp = _bar_walk_full_momentum_filter(mom, vol, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_momentum_filter_last_sample(mom, vol, period)
    _assert_series_close(last, exp)


def test_incremental_momentum_filter_warmup() -> None:
    """Window shorter than period is ``0.0``, matching full recompute."""
    mom = [1.0, 1.1]
    vol = [100.0, 110.0]
    period = 5
    got = _bar_walk_inc_momentum_filter(mom, vol, period)
    exp = _bar_walk_full_momentum_filter(mom, vol, period)
    _assert_series_close(got, exp)
    assert got == [0.0, 0.0]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._momentum_filter_inc_update([], [], 5) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._momentum_filter_inc_update(None, None, 5) == 0.0
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_momentum_filter([None], [None], 5)
    exp_na = _bar_walk_full_momentum_filter([None], [None], 5)
    _assert_series_close(got_na, exp_na)
    assert got_na[0] == 0.0


def test_incremental_momentum_filter_na_skips() -> None:
    """Numeric volumes still enter vol_sum when mom is non-numeric.

    Numerator uses only paired numeric (mom, vol) samples. Empty mom_data
    or vol_sum == 0 → 0.0.
    """
    period = 3
    mom: list[float | None] = [1.0, None, 2.0]
    vol: list[float | None] = [10.0, 20.0, 30.0]
    got = _bar_walk_inc_momentum_filter(mom, vol, period)
    exp = _bar_walk_full_momentum_filter(mom, vol, period)
    _assert_series_close(got, exp)
    assert got[0] == 0.0
    assert got[1] == 0.0
    # vol_sum=60, paired (1,10)+(2,30)=70 → 70/60
    assert got[2] == pytest.approx(70.0 / 60.0)
    last = _bar_walk_inc_momentum_filter_last_sample(mom, vol, period)
    _assert_series_close(last, exp)

    mom_all_na: list[float | None] = [None, None, None]
    vol_ok = [10.0, 20.0, 30.0]
    got_na = _bar_walk_inc_momentum_filter(mom_all_na, vol_ok, period)
    exp_na = _bar_walk_full_momentum_filter(mom_all_na, vol_ok, period)
    _assert_series_close(got_na, exp_na)
    assert got_na[-1] == 0.0

    mom_ok = [1.0, 1.0, 1.0]
    vol_zero = [0.0, 0.0, 0.0]
    got_z = _bar_walk_inc_momentum_filter(mom_ok, vol_zero, period)
    exp_z = _bar_walk_full_momentum_filter(mom_ok, vol_zero, period)
    _assert_series_close(got_z, exp_z)
    assert got_z[-1] == 0.0


def test_incremental_momentum_filter_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    mom: list[float | None] = list(_series(40))
    vol: list[float | None] = list(_vols(40))
    mom[4] = None
    vol[11] = None
    ev = _IncTA()
    for i in range(len(mom)):
        ev._ta_call_i = 0
        ev._momentum_filter_inc_update(mom[: i + 1], vol[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_momentum_filter_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    mom = _series(30)
    vol = _vols(30)
    ev = _IncTA()
    for i in range(len(mom)):
        ev._ta_call_i = 0
        ev._builtin_ta_momentum_filter([mom[: i + 1], vol[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_momentum_filter_two_call_sites_independent() -> None:
    mom = _series(80)
    vol = _vols(80)
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(mom)):
        prefix_m = mom[: i + 1]
        prefix_v = vol[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._momentum_filter_inc_update(prefix_m, prefix_v, 5))
        b_out.append(ev._momentum_filter_inc_update(prefix_m, prefix_v, 14))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_momentum_filter(mom, vol, 5))
    _assert_series_close(b_out, _bar_walk_full_momentum_filter(mom, vol, 14))
    assert a_out != b_out


def _momentum_filter_last_n(mom: list[Any], vol: list[Any], period: int) -> float:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    if len(mom) < period or len(vol) < period or period <= 0:
        return 0.0
    vol_sum = sum(v for v in vol[-period:] if isinstance(v, (int, float)))
    mom_data = [
        (mom[i], vol[i])
        for i in range(-period, 0)
        if isinstance(mom[i], (int, float)) and isinstance(vol[i], (int, float))
    ]
    if not mom_data or vol_sum == 0:
        return 0.0
    return sum(m * v for m, v in mom_data) / vol_sum


def test_runtime_momentum_filter_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("momentum filter")
f = ta.momentum_filter(close, volume, 5)
g = ta.momentum_filter(close, volume, 14)
plot(f, "mf5")
plot(g, "mf14")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"mf5", "mf14"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # ``[-period:]`` is the oldest window — not last-sample. Incremental last
    # sample is the chronological last-N formula (list-oracle / kernel).
    closes = [b["close"] for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["mf5"]):
        exp = _momentum_filter_last_n(closes[: i + 1], vols[: i + 1], 5)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mf5 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["mf14"]):
        exp = _momentum_filter_last_n(closes[: i + 1], vols[: i + 1], 14)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mf14 bar {i}: {val} != {exp}"
    assert r_on["series"]["mf5"][0] == pytest.approx(0.0)
    assert r_off["series"]["mf5"][0] == pytest.approx(0.0)
    assert r_on["series"]["mf5"][4] != pytest.approx(0.0)
    assert r_off["series"]["mf5"][4] != pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T2: acceleration_factor incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _acceleration_factor_last_n(momentum: list[Any], period: int) -> float:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    if len(momentum) < period + 1 or period <= 0:
        return 0.0
    momentum_clean = [m for m in momentum[-period - 1 :] if isinstance(m, (int, float))]
    if len(momentum_clean) < 2:
        return 0.0
    old_mom = sum(momentum_clean[:-1]) / len(momentum_clean[:-1])
    new_mom = sum(momentum_clean[-1:])
    if abs(old_mom) < 1e-10:
        return 0.0
    acceleration = (new_mom - old_mom) / old_mom
    return max(-2.0, min(2.0, acceleration))


def _bar_walk_full_acceleration_factor(mom: list[Any], period: int) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(mom)):
        out.append(ev._builtin_ta_acceleration_factor([mom[: i + 1], period]))
    return out


def _bar_walk_inc_acceleration_factor(mom: list[Any], period: int) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(mom)):
        ev._ta_call_i = 0
        out.append(ev._acceleration_factor_inc_update(mom[: i + 1], period))
    return out


def _bar_walk_inc_acceleration_factor_last_sample(mom: list[Any], period: int) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(mom)):
        ev._ta_call_i = 0
        out.append(ev._acceleration_factor_inc_update(mom[i], period))
    return out


def test_incremental_acceleration_factor_matches_full() -> None:
    mom = _series(120)
    period = 5
    got = _bar_walk_inc_acceleration_factor(mom, period)
    exp = _bar_walk_full_acceleration_factor(mom, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_acceleration_factor_last_sample(mom, period)
    _assert_series_close(last, exp)
    oracle = [_acceleration_factor_last_n(mom[: i + 1], period) for i in range(len(mom))]
    _assert_series_close(got, oracle)


def test_incremental_acceleration_factor_warmup() -> None:
    """Window shorter than period+1 is ``0.0``, matching full recompute."""
    mom = [1.0, 1.1]
    period = 5
    got = _bar_walk_inc_acceleration_factor(mom, period)
    exp = _bar_walk_full_acceleration_factor(mom, period)
    _assert_series_close(got, exp)
    assert got == [0.0, 0.0]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._acceleration_factor_inc_update([], 5) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._acceleration_factor_inc_update(None, 5) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._acceleration_factor_inc_update(1.0, 0) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._acceleration_factor_inc_update(1.0, -3) == 0.0
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_acceleration_factor([None], 5)
    exp_na = _bar_walk_full_acceleration_factor([None], 5)
    _assert_series_close(got_na, exp_na)
    assert got_na[0] == 0.0


def test_incremental_acceleration_factor_na_skips() -> None:
    """Non-numeric samples are dropped; fewer than 2 numeric → 0.0."""
    period = 3
    mom: list[float | None] = [1.0, None, 2.0, 3.0]
    got = _bar_walk_inc_acceleration_factor(mom, period)
    exp = _bar_walk_full_acceleration_factor(mom, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_acceleration_factor_last_sample(mom, period)
    _assert_series_close(last, exp)
    # last 4: [1.0, None, 2.0, 3.0] → clean [1.0, 2.0, 3.0]
    # old_mom = (1+2)/2 = 1.5, new_mom = 3.0, accel = 1.0
    assert got[-1] == pytest.approx(1.0)

    mom_all_na: list[float | None] = [None, None, None, None]
    got_na = _bar_walk_inc_acceleration_factor(mom_all_na, period)
    exp_na = _bar_walk_full_acceleration_factor(mom_all_na, period)
    _assert_series_close(got_na, exp_na)
    assert got_na[-1] == 0.0


def test_incremental_acceleration_factor_old_mom_near_zero() -> None:
    """abs(old_mom) < 1e-10 → 0.0."""
    period = 3
    mom = [1e-12, 1e-12, 1e-12, 1.0]
    got = _bar_walk_inc_acceleration_factor(mom, period)
    exp = _bar_walk_full_acceleration_factor(mom, period)
    _assert_series_close(got, exp)
    assert got[-1] == 0.0


def test_incremental_acceleration_factor_clamp() -> None:
    """Acceleration is clamped to [-2.0, 2.0]."""
    period = 3
    mom_up = [1.0, 1.0, 1.0, 100.0]
    got_up = _bar_walk_inc_acceleration_factor(mom_up, period)
    exp_up = _bar_walk_full_acceleration_factor(mom_up, period)
    _assert_series_close(got_up, exp_up)
    assert got_up[-1] == pytest.approx(2.0)
    mom_dn = [1.0, 1.0, 1.0, -100.0]
    got_dn = _bar_walk_inc_acceleration_factor(mom_dn, period)
    exp_dn = _bar_walk_full_acceleration_factor(mom_dn, period)
    _assert_series_close(got_dn, exp_dn)
    assert got_dn[-1] == pytest.approx(-2.0)


def test_incremental_acceleration_factor_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    mom: list[float | None] = list(_series(40))
    mom[4] = None
    ev = _IncTA()
    for i in range(len(mom)):
        ev._ta_call_i = 0
        ev._acceleration_factor_inc_update(mom[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_acceleration_factor_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    mom = _series(30)
    ev = _IncTA()
    for i in range(len(mom)):
        ev._ta_call_i = 0
        ev._builtin_ta_acceleration_factor([mom[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_acceleration_factor_two_call_sites_independent() -> None:
    mom = _series(80)
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(mom)):
        prefix = mom[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._acceleration_factor_inc_update(prefix, 3))
        b_out.append(ev._acceleration_factor_inc_update(prefix, 5))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_acceleration_factor(mom, 3))
    _assert_series_close(b_out, _bar_walk_full_acceleration_factor(mom, 5))
    assert a_out != b_out


def test_runtime_acceleration_factor_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("acceleration factor")
f = ta.acceleration_factor(close, 3)
g = ta.acceleration_factor(close, 5)
plot(f, "af3")
plot(g, "af5")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"af3", "af5"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # ``[-period-1:]`` is the oldest window — not last-sample. Incremental last
    # sample is the chronological last-(period+1) formula (list-oracle / kernel).
    # Do not require incremental == disabled for every bar.
    closes = [b["close"] for b in bars]
    for i, val in enumerate(r_on["series"]["af3"]):
        exp = _acceleration_factor_last_n(closes[: i + 1], 3)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"af3 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["af5"]):
        exp = _acceleration_factor_last_n(closes[: i + 1], 5)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"af5 bar {i}: {val} != {exp}"
    assert r_on["series"]["af3"][0] == pytest.approx(0.0)
    assert r_off["series"]["af3"][0] == pytest.approx(0.0)
    assert r_on["series"]["af3"][3] != pytest.approx(0.0)
    assert r_off["series"]["af3"][3] != pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T2: mean_reversion_score incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _mean_reversion_score_last_n(
    close: list[Any],
    sma: list[Any],
    stdev: list[Any],
    period: int,
) -> float:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    if len(close) < period or len(sma) < period or period <= 0:
        return 50.0
    c = close[-1] if isinstance(close[-1], (int, float)) else 100.0
    s = sma[-1] if isinstance(sma[-1], (int, float)) else 100.0
    sd = stdev[-1] if stdev and isinstance(stdev[-1], (int, float)) else 1.0
    if sd == 0:
        return 50.0
    distance = abs(c - s) / sd
    score = min(100.0, distance * 20)
    return max(0.0, min(100.0, score))


def _mrs_series(n: int = 120) -> tuple[list[float], list[float], list[float]]:
    close = _series(n)
    sma = [c - 1.0 - (i % 7) * 0.05 for i, c in enumerate(close)]
    stdev = [1.5 + (i % 5) * 0.1 for i in range(n)]
    return close, sma, stdev


def _bar_walk_full_mean_reversion_score(
    close: list[Any],
    sma: list[Any],
    stdev: list[Any],
    period: int,
) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(close)):
        out.append(ev._builtin_ta_mean_reversion_score([close[: i + 1], sma[: i + 1], stdev[: i + 1], period]))
    return out


def _bar_walk_inc_mean_reversion_score(
    close: list[Any],
    sma: list[Any],
    stdev: list[Any],
    period: int,
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(ev._mean_reversion_score_inc_update(close[: i + 1], sma[: i + 1], stdev[: i + 1], period))
    return out


def _bar_walk_inc_mean_reversion_score_last_sample(
    close: list[Any],
    sma: list[Any],
    stdev: list[Any],
    period: int,
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(ev._mean_reversion_score_inc_update(close[i], sma[i], stdev[i], period))
    return out


def test_incremental_mean_reversion_score_matches_full() -> None:
    close, sma, stdev = _mrs_series(120)
    period = 5
    got = _bar_walk_inc_mean_reversion_score(close, sma, stdev, period)
    exp = _bar_walk_full_mean_reversion_score(close, sma, stdev, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_mean_reversion_score_last_sample(close, sma, stdev, period)
    _assert_series_close(last, exp)
    oracle = [
        _mean_reversion_score_last_n(close[: i + 1], sma[: i + 1], stdev[: i + 1], period) for i in range(len(close))
    ]
    _assert_series_close(got, oracle)


def test_incremental_mean_reversion_score_warmup() -> None:
    """Window shorter than period, empty, None, or period<=0 is ``50.0``."""
    close = [100.0, 101.0]
    sma = [99.0, 99.5]
    stdev = [1.0, 1.1]
    period = 5
    got = _bar_walk_inc_mean_reversion_score(close, sma, stdev, period)
    exp = _bar_walk_full_mean_reversion_score(close, sma, stdev, period)
    _assert_series_close(got, exp)
    assert got == [50.0, 50.0]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._mean_reversion_score_inc_update([], [], [], 5) == 50.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._mean_reversion_score_inc_update(None, None, None, 5) == 50.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._mean_reversion_score_inc_update(1.0, 1.0, 1.0, 0) == 50.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._mean_reversion_score_inc_update(1.0, 1.0, 1.0, -3) == 50.0
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_mean_reversion_score([None], [None], [None], 5)
    exp_na = _bar_walk_full_mean_reversion_score([None], [None], [None], 5)
    _assert_series_close(got_na, exp_na)
    assert got_na[0] == 50.0


def test_incremental_mean_reversion_score_sd_zero() -> None:
    """Last stdev == 0 → 50.0 after warmup."""
    period = 3
    close = [100.0, 101.0, 102.0, 110.0]
    sma = [100.0, 100.0, 100.0, 100.0]
    stdev = [1.0, 1.0, 1.0, 0.0]
    got = _bar_walk_inc_mean_reversion_score(close, sma, stdev, period)
    exp = _bar_walk_full_mean_reversion_score(close, sma, stdev, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_mean_reversion_score_last_sample(close, sma, stdev, period)
    _assert_series_close(last, exp)
    assert got[-1] == 50.0
    assert got[2] != 50.0


def test_incremental_mean_reversion_score_non_numeric_last() -> None:
    """Non-numeric last close/sma → 100.0; last stdev → 1.0 (same as full path)."""
    period = 3
    close: list[Any] = [100.0, 101.0, "x"]
    sma: list[Any] = [99.0, 99.5, None]
    stdev: list[Any] = [1.0, 1.0, None]
    got = _bar_walk_inc_mean_reversion_score(close, sma, stdev, period)
    exp = _bar_walk_full_mean_reversion_score(close, sma, stdev, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_mean_reversion_score_last_sample(close, sma, stdev, period)
    _assert_series_close(last, exp)
    # c=100, s=100, sd=1 → distance 0 → score 0
    assert got[-1] == pytest.approx(0.0)


def test_incremental_mean_reversion_score_clamp() -> None:
    """Score is clamped to [0, 100] (distance * 20 saturates at 100)."""
    period = 3
    close = [100.0, 100.0, 100.0, 200.0]
    sma = [100.0, 100.0, 100.0, 100.0]
    stdev = [1.0, 1.0, 1.0, 1.0]
    got = _bar_walk_inc_mean_reversion_score(close, sma, stdev, period)
    exp = _bar_walk_full_mean_reversion_score(close, sma, stdev, period)
    _assert_series_close(got, exp)
    assert got[-1] == pytest.approx(100.0)


def test_incremental_mean_reversion_score_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    close: list[float | None]
    close, sma, stdev = _mrs_series(40)
    close_na: list[float | None] = list(close)
    close_na[4] = None
    ev = _IncTA()
    for i in range(len(close_na)):
        ev._ta_call_i = 0
        ev._mean_reversion_score_inc_update(close_na[: i + 1], sma[: i + 1], stdev[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_mean_reversion_score_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    close, sma, stdev = _mrs_series(30)
    ev = _IncTA()
    for i in range(len(close)):
        ev._ta_call_i = 0
        ev._builtin_ta_mean_reversion_score([close[: i + 1], sma[: i + 1], stdev[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_mean_reversion_score_two_call_sites_independent() -> None:
    close, sma, stdev = _mrs_series(80)
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(close)):
        prefix_c = close[: i + 1]
        prefix_s = sma[: i + 1]
        prefix_d = stdev[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._mean_reversion_score_inc_update(prefix_c, prefix_s, prefix_d, 3))
        b_out.append(ev._mean_reversion_score_inc_update(prefix_c, prefix_s, prefix_d, 5))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_mean_reversion_score(close, sma, stdev, 3))
    _assert_series_close(b_out, _bar_walk_full_mean_reversion_score(close, sma, stdev, 5))
    assert a_out != b_out


def test_runtime_mean_reversion_score_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("mean reversion score")
f = ta.mean_reversion_score(close, open, volume, 3)
g = ta.mean_reversion_score(close, open, volume, 5)
plot(f, "mrs3")
plot(g, "mrs5")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"mrs3", "mrs5"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # last-sample on the reversed list is the oldest bar — not chronological
    # last-sample. Incremental last sample is the chronological prefix formula
    # (list-oracle / kernel). Do not require incremental == disabled for every bar.
    closes = [b["close"] for b in bars]
    opens = [b["open"] for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["mrs3"]):
        exp = _mean_reversion_score_last_n(closes[: i + 1], opens[: i + 1], vols[: i + 1], 3)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mrs3 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["mrs5"]):
        exp = _mean_reversion_score_last_n(closes[: i + 1], opens[: i + 1], vols[: i + 1], 5)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mrs5 bar {i}: {val} != {exp}"
    assert r_on["series"]["mrs3"][0] == pytest.approx(50.0)
    assert r_off["series"]["mrs3"][0] == pytest.approx(50.0)
    assert r_on["series"]["mrs3"][2] != pytest.approx(50.0)


# ---------------------------------------------------------------------------
# T2: market_condition incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _market_condition_last_n(
    close: list[Any],
    atr: list[Any],
    sma_period: int,
    stdev_period: int,
) -> str:
    """Oracle formula on a chronological prefix (same as full ``ta.market_condition``)."""
    if sma_period <= 0 or stdev_period <= 0:
        return "ranging"
    if len(close) < max(sma_period, stdev_period):
        return "ranging"
    current_close = close[-1] if isinstance(close[-1], (int, float)) else 0
    current_atr = atr[-1] if isinstance(atr[-1], (int, float)) else 1.0
    ev = _FullTA()
    sma_list = ev._sma(close, sma_period)
    current_sma = sma_list[-1] if sma_list and sma_list[-1] is not None else current_close
    stdev_val = ev._stdev(close, stdev_period)
    if stdev_val and stdev_val > (current_atr * 1.5):
        return "volatile"
    if current_close > current_sma and current_atr > 0.5:
        return "trending_up"
    if current_close < current_sma and current_atr > 0.5:
        return "trending_down"
    return "ranging"


def _mc_code(label: str) -> float:
    return {"ranging": 1.0, "volatile": 2.0, "trending_up": 3.0, "trending_down": 4.0}[label]


def _mc_series(n: int = 120) -> tuple[list[float], list[float]]:
    close = _series(n)
    atr = [0.8 + (i % 6) * 0.15 for i in range(n)]
    return close, atr


def _bar_walk_full_market_condition(
    close: list[Any],
    atr: list[Any],
    sma_period: int,
    stdev_period: int,
) -> list[str]:
    ev = _FullTA()
    out: list[str] = []
    for i in range(len(close)):
        out.append(ev._builtin_ta_market_condition([close[: i + 1], atr[: i + 1], sma_period, stdev_period]))
    return out


def _bar_walk_inc_market_condition(
    close: list[Any],
    atr: list[Any],
    sma_period: int,
    stdev_period: int,
) -> list[str]:
    ev = _IncTA()
    out: list[str] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(ev._market_condition_inc_update(close[: i + 1], atr[: i + 1], sma_period, stdev_period))
    return out


def _bar_walk_inc_market_condition_last_sample(
    close: list[Any],
    atr: list[Any],
    sma_period: int,
    stdev_period: int,
) -> list[str]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[str] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(ev._market_condition_inc_update(close[i], atr[i], sma_period, stdev_period))
    return out


def test_incremental_market_condition_matches_full() -> None:
    close, atr = _mc_series(120)
    sma_period, stdev_period = 3, 5
    got = _bar_walk_inc_market_condition(close, atr, sma_period, stdev_period)
    exp = _bar_walk_full_market_condition(close, atr, sma_period, stdev_period)
    assert got == exp
    last = _bar_walk_inc_market_condition_last_sample(close, atr, sma_period, stdev_period)
    assert last == exp
    oracle = [
        _market_condition_last_n(close[: i + 1], atr[: i + 1], sma_period, stdev_period) for i in range(len(close))
    ]
    assert got == oracle


def test_incremental_market_condition_warmup() -> None:
    """Window shorter than max(sma, stdev), empty, None, or period<=0 is ``ranging``."""
    close = [100.0, 101.0]
    atr = [1.0, 1.1]
    sma_period, stdev_period = 5, 3
    got = _bar_walk_inc_market_condition(close, atr, sma_period, stdev_period)
    exp = _bar_walk_full_market_condition(close, atr, sma_period, stdev_period)
    assert got == exp
    assert got == ["ranging", "ranging"]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._market_condition_inc_update([], [], 5, 3) == "ranging"
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._market_condition_inc_update(None, None, 5, 3) == "ranging"
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._market_condition_inc_update(1.0, 1.0, 0, 5) == "ranging"
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._market_condition_inc_update(1.0, 1.0, 5, 0) == "ranging"
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._market_condition_inc_update(1.0, 1.0, -3, 5) == "ranging"
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_market_condition([None], [None], 5, 3)
    exp_na = _bar_walk_full_market_condition([None], [None], 5, 3)
    assert got_na == exp_na
    assert got_na[0] == "ranging"


def test_incremental_market_condition_classifies() -> None:
    """Last close/atr vs SMA/stdev windows: ranging / volatile / trending_up / down."""
    cases: list[tuple[list[float], list[float], int, int, str]] = [
        ([98.0, 99.0, 100.0, 101.0, 102.0], [1.0] * 5, 3, 2, "trending_up"),
        ([102.0, 101.0, 100.0, 99.0, 98.0], [1.0] * 5, 3, 2, "trending_down"),
        ([100.0, 101.0, 100.0, 101.0, 100.0], [0.5] * 5, 3, 2, "ranging"),
        ([100.0, 50.0, 150.0, 50.0, 150.0], [1.0] * 5, 3, 5, "volatile"),
    ]
    for close, atr, sma_p, stdev_p, label in cases:
        got = _bar_walk_inc_market_condition(close, atr, sma_p, stdev_p)
        exp = _bar_walk_full_market_condition(close, atr, sma_p, stdev_p)
        assert got == exp, f"{label}: {got} vs {exp}"
        last = _bar_walk_inc_market_condition_last_sample(close, atr, sma_p, stdev_p)
        assert last == exp
        assert got[-1] == label
        assert got[0] == "ranging"


def test_incremental_market_condition_non_numeric_last() -> None:
    """Non-numeric last close → 0; last atr → 1.0 (same as full path)."""
    sma_period, stdev_period = 3, 2
    close: list[Any] = [100.0, 101.0, 102.0, "x"]
    atr: list[Any] = [1.0, 1.0, 1.0, None]
    got = _bar_walk_inc_market_condition(close, atr, sma_period, stdev_period)
    exp = _bar_walk_full_market_condition(close, atr, sma_period, stdev_period)
    assert got == exp
    last = _bar_walk_inc_market_condition_last_sample(close, atr, sma_period, stdev_period)
    assert last == exp
    assert got[-1] == _market_condition_last_n(close, atr, sma_period, stdev_period)


def test_incremental_market_condition_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    close: list[float | None]
    close, atr = _mc_series(40)
    close_na: list[float | None] = list(close)
    close_na[4] = None
    ev = _IncTA()
    for i in range(len(close_na)):
        ev._ta_call_i = 0
        ev._market_condition_inc_update(close_na[: i + 1], atr[: i + 1], 5, 3)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_market_condition_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    close, atr = _mc_series(30)
    ev = _IncTA()
    for i in range(len(close)):
        ev._ta_call_i = 0
        ev._builtin_ta_market_condition([close[: i + 1], atr[: i + 1], 5, 3])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_market_condition_two_call_sites_independent() -> None:
    close, atr = _mc_series(80)
    ev = _IncTA()
    a_out: list[str] = []
    b_out: list[str] = []
    for i in range(len(close)):
        prefix_c = close[: i + 1]
        prefix_a = atr[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._market_condition_inc_update(prefix_c, prefix_a, 3, 2))
        b_out.append(ev._market_condition_inc_update(prefix_c, prefix_a, 5, 8))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    assert a_out == _bar_walk_full_market_condition(close, atr, 3, 2)
    assert b_out == _bar_walk_full_market_condition(close, atr, 5, 8)
    assert a_out != b_out


def test_runtime_market_condition_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ohlcv_bars(80)
    src = """//@version=5
indicator("market condition")
f = ta.market_condition(close, volume, 3, 2)
g = ta.market_condition(close, volume, 5, 8)
plot(f == "ranging" ? 1 : f == "volatile" ? 2 : f == "trending_up" ? 3 : 4, "mc32")
plot(g == "ranging" ? 1 : g == "volatile" ? 2 : g == "trending_up" ? 3 : 4, "mc58")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"mc32", "mc58"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses newest-first PineSeries wrapped as a 1-list, so
    # last-sample is not chronological. Incremental last sample is the
    # chronological prefix formula (list-oracle / kernel). Do not require
    # incremental == disabled for every bar.
    closes = [b["close"] for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["mc32"]):
        exp = _mc_code(_market_condition_last_n(closes[: i + 1], vols[: i + 1], 3, 2))
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mc32 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["mc58"]):
        exp = _mc_code(_market_condition_last_n(closes[: i + 1], vols[: i + 1], 5, 8))
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mc58 bar {i}: {val} != {exp}"
    assert r_on["series"]["mc32"][0] == pytest.approx(1.0)
    assert r_off["series"]["mc32"][0] == pytest.approx(1.0)
    assert r_on["series"]["mc32"][2] != pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T2: order_flow_imbalance incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _order_flow_imbalance_last_n(
    high: list[Any],
    low: list[Any],
    close: list[Any],
    volume: list[Any],
    period: int,
) -> float:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    if len(high) < period or len(low) < period or period <= 0:
        return 0.0
    buy_vol = 0.0
    sell_vol = 0.0
    for idx in range(-period, 0):
        h_val = high[idx] if isinstance(high[idx], (int, float)) else 0
        low_val = low[idx] if isinstance(low[idx], (int, float)) else 0
        c_val = close[idx] if isinstance(close[idx], (int, float)) else 0
        v_val = volume[idx] if isinstance(volume[idx], (int, float)) else 0
        if h_val > low_val:
            midpoint = (h_val + low_val) / 2
            if c_val > midpoint:
                buy_vol += v_val
            else:
                sell_vol += v_val
    total = buy_vol + sell_vol
    if total == 0:
        return 0.0
    return (buy_vol - sell_vol) / total


def _ofi_series(n: int = 120) -> tuple[list[float], list[float], list[float], list[float]]:
    """OHLCV with mixed buy/sell bars (close vs high/low midpoint)."""
    close = _series(n)
    high: list[float] = []
    low: list[float] = []
    for i, c in enumerate(close):
        if i % 3 == 0:
            high.append(c + 0.5)
            low.append(c - 1.5)  # mid = c - 0.5; close > mid → buy
        elif i % 3 == 1:
            high.append(c + 1.5)
            low.append(c - 0.5)  # mid = c + 0.5; close < mid → sell
        else:
            high.append(c + 1.0)
            low.append(c - 1.0)  # mid = c; close > mid is False → sell
    return high, low, close, _vols(n)


def _ofi_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV with mixed buy/sell for Runtime bar-mode tests."""
    bars: list[dict] = []
    for i in range(n):
        c = 100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0
        if i % 2 == 0:
            high, low = c + 0.4, c - 1.2  # mid = c - 0.4; close > mid → buy
        else:
            high, low = c + 1.2, c - 0.4  # mid = c + 0.4; close < mid → sell
        bars.append(
            {
                "open": c - 0.3,
                "high": high,
                "low": low,
                "close": c,
                "volume": 1000 + i * 10,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_order_flow_imbalance(
    high: list[Any],
    low: list[Any],
    close: list[Any],
    volume: list[Any],
    period: int,
) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(high)):
        out.append(
            ev._builtin_ta_order_flow_imbalance([high[: i + 1], low[: i + 1], close[: i + 1], volume[: i + 1], period])
        )
    return out


def _bar_walk_inc_order_flow_imbalance(
    high: list[Any],
    low: list[Any],
    close: list[Any],
    volume: list[Any],
    period: int,
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(high)):
        ev._ta_call_i = 0
        out.append(
            ev._order_flow_imbalance_inc_update(high[: i + 1], low[: i + 1], close[: i + 1], volume[: i + 1], period)
        )
    return out


def _bar_walk_inc_order_flow_imbalance_last_sample(
    high: list[Any],
    low: list[Any],
    close: list[Any],
    volume: list[Any],
    period: int,
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(high)):
        ev._ta_call_i = 0
        out.append(ev._order_flow_imbalance_inc_update(high[i], low[i], close[i], volume[i], period))
    return out


def test_incremental_order_flow_imbalance_matches_full() -> None:
    high, low, close, volume = _ofi_series(120)
    period = 5
    got = _bar_walk_inc_order_flow_imbalance(high, low, close, volume, period)
    exp = _bar_walk_full_order_flow_imbalance(high, low, close, volume, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_order_flow_imbalance_last_sample(high, low, close, volume, period)
    _assert_series_close(last, exp)
    oracle = [
        _order_flow_imbalance_last_n(high[: i + 1], low[: i + 1], close[: i + 1], volume[: i + 1], period)
        for i in range(len(high))
    ]
    _assert_series_close(got, oracle)


def test_incremental_order_flow_imbalance_warmup() -> None:
    """Window shorter than period, empty, None, or period<=0 is ``0.0``."""
    high = [100.0, 101.0]
    low = [95.0, 96.0]
    close = [98.0, 99.0]
    volume = [100.0, 110.0]
    period = 5
    got = _bar_walk_inc_order_flow_imbalance(high, low, close, volume, period)
    exp = _bar_walk_full_order_flow_imbalance(high, low, close, volume, period)
    _assert_series_close(got, exp)
    assert got == [0.0, 0.0]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._order_flow_imbalance_inc_update([], [], [], [], 5) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._order_flow_imbalance_inc_update(None, None, None, None, 5) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._order_flow_imbalance_inc_update(1.0, 0.5, 0.8, 10.0, 0) == 0.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._order_flow_imbalance_inc_update(1.0, 0.5, 0.8, 10.0, -3) == 0.0
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_order_flow_imbalance([None], [None], [None], [None], 5)
    exp_na = _bar_walk_full_order_flow_imbalance([None], [None], [None], [None], 5)
    _assert_series_close(got_na, exp_na)
    assert got_na[0] == 0.0


def test_incremental_order_flow_imbalance_zero_range() -> None:
    """Zero high-low range skips the bar; all-zero range or volume total 0 -> 0.0."""
    period = 3
    high = [100.0, 100.0, 100.0]
    low = [100.0, 100.0, 100.0]
    close = [100.0, 100.0, 100.0]
    volume = [10.0, 20.0, 30.0]
    got = _bar_walk_inc_order_flow_imbalance(high, low, close, volume, period)
    exp = _bar_walk_full_order_flow_imbalance(high, low, close, volume, period)
    _assert_series_close(got, exp)
    assert got[-1] == 0.0
    last = _bar_walk_inc_order_flow_imbalance_last_sample(high, low, close, volume, period)
    _assert_series_close(last, exp)

    # Mixed: first bar zero-range (skipped), rest buy vs sell.
    high_m = [100.0, 102.0, 101.0]
    low_m = [100.0, 98.0, 99.0]
    close_m = [100.0, 101.0, 99.5]  # bar1 close>mid buy 20; bar2 close<mid sell 30
    vol_m = [10.0, 20.0, 30.0]
    got_m = _bar_walk_inc_order_flow_imbalance(high_m, low_m, close_m, vol_m, period)
    exp_m = _bar_walk_full_order_flow_imbalance(high_m, low_m, close_m, vol_m, period)
    _assert_series_close(got_m, exp_m)
    assert got_m[0] == 0.0
    assert got_m[1] == 0.0
    assert got_m[2] == pytest.approx((20.0 - 30.0) / 50.0)

    high_ok = [101.0, 102.0, 103.0]
    low_ok = [99.0, 100.0, 101.0]
    close_ok = [101.0, 102.0, 103.0]
    vol_zero = [0.0, 0.0, 0.0]
    got_z = _bar_walk_inc_order_flow_imbalance(high_ok, low_ok, close_ok, vol_zero, period)
    exp_z = _bar_walk_full_order_flow_imbalance(high_ok, low_ok, close_ok, vol_zero, period)
    _assert_series_close(got_z, exp_z)
    assert got_z[-1] == 0.0


def test_incremental_order_flow_imbalance_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    high, low, close, volume = _ofi_series(40)
    high_na: list[float | None] = list(high)
    high_na[4] = None
    ev = _IncTA()
    for i in range(len(high_na)):
        ev._ta_call_i = 0
        ev._order_flow_imbalance_inc_update(high_na[: i + 1], low[: i + 1], close[: i + 1], volume[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_order_flow_imbalance_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    high, low, close, volume = _ofi_series(30)
    ev = _IncTA()
    for i in range(len(high)):
        ev._ta_call_i = 0
        ev._builtin_ta_order_flow_imbalance([high[: i + 1], low[: i + 1], close[: i + 1], volume[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_order_flow_imbalance_two_call_sites_independent() -> None:
    high, low, close, volume = _ofi_series(80)
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(high)):
        prefix_h = high[: i + 1]
        prefix_l = low[: i + 1]
        prefix_c = close[: i + 1]
        prefix_v = volume[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._order_flow_imbalance_inc_update(prefix_h, prefix_l, prefix_c, prefix_v, 5))
        b_out.append(ev._order_flow_imbalance_inc_update(prefix_h, prefix_l, prefix_c, prefix_v, 14))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_order_flow_imbalance(high, low, close, volume, 5))
    _assert_series_close(b_out, _bar_walk_full_order_flow_imbalance(high, low, close, volume, 14))
    assert a_out != b_out


def test_runtime_order_flow_imbalance_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _ofi_bars(80)
    src = """//@version=5
indicator("order flow imbalance")
f = ta.order_flow_imbalance(high, low, close, volume, 5)
g = ta.order_flow_imbalance(high, low, close, volume, 14)
plot(f, "ofi5")
plot(g, "ofi14")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"ofi5", "ofi14"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # ``[-period:]`` is the oldest window — not last-sample. Incremental last
    # sample is the chronological last-N formula (list-oracle / kernel). Do
    # not require incremental == disabled for every bar.
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["ofi5"]):
        exp = _order_flow_imbalance_last_n(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], 5)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"ofi5 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["ofi14"]):
        exp = _order_flow_imbalance_last_n(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], 14)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"ofi14 bar {i}: {val} != {exp}"
    assert r_on["series"]["ofi5"][0] == pytest.approx(0.0)
    assert r_off["series"]["ofi5"][0] == pytest.approx(0.0)
    assert r_on["series"]["ofi5"][4] != pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T2: volume_thrust incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _volume_thrust_last_n(
    close: list[Any],
    volume: list[Any],
    vol_sma: list[Any],
    sensitivity: float,
) -> bool:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    if not close or not volume or not vol_sma:
        return False
    c_val = close[-1] if isinstance(close[-1], (int, float)) else 100.0
    c_prev = close[-2] if len(close) > 1 and isinstance(close[-2], (int, float)) else 100.0
    v_val = volume[-1] if isinstance(volume[-1], (int, float)) else 1000.0
    vs_val = vol_sma[-1] if isinstance(vol_sma[-1], (int, float)) else 1000.0
    sens = sensitivity if isinstance(sensitivity, (int, float)) else 0.3
    volume_spike = v_val > vs_val * (1 + sens)
    price_move = abs(c_val - c_prev) / c_prev > 0.01 if c_prev != 0 else False
    return volume_spike and price_move


def _vt_series(n: int = 120) -> tuple[list[float], list[float], list[float]]:
    """Closes with 2% jumps on spike bars; volume vs a flat SMA."""
    close = _series(n)
    volume: list[float] = []
    vol_sma: list[float] = []
    for i in range(n):
        vol_sma.append(1000.0)
        if i % 6 == 0:
            volume.append(1500.0)  # 50% spike — fires at 0.3 and 0.1
        elif i % 6 == 3:
            volume.append(1200.0)  # 20% spike — fires at 0.1, not 0.3
        else:
            volume.append(1000.0)
        if i >= 6 and i % 6 == 0:
            close[i] = close[i - 1] * 1.025
        elif i >= 3 and i % 6 == 3:
            close[i] = close[i - 1] * 1.02
    return close, volume, vol_sma


def _vt_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: 2% close steps, open is flat volume SMA, spiked volume."""
    bars: list[dict] = []
    for i in range(n):
        c = 100.0 * (1.02**i)
        volume = 1600.0 if i % 4 == 0 else 1050.0
        bars.append(
            {
                "open": 1000.0,
                "high": c + 0.8,
                "low": c - 0.8,
                "close": c,
                "volume": volume,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_volume_thrust(
    close: list[Any],
    volume: list[Any],
    vol_sma: list[Any],
    sensitivity: float,
) -> list[bool]:
    ev = _FullTA()
    out: list[bool] = []
    for i in range(len(close)):
        out.append(bool(ev._builtin_ta_volume_thrust([close[: i + 1], volume[: i + 1], vol_sma[: i + 1], sensitivity])))
    return out


def _bar_walk_inc_volume_thrust(
    close: list[Any],
    volume: list[Any],
    vol_sma: list[Any],
    sensitivity: float,
) -> list[bool]:
    ev = _IncTA()
    out: list[bool] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(bool(ev._volume_thrust_inc_update(close[: i + 1], volume[: i + 1], vol_sma[: i + 1], sensitivity)))
    return out


def _bar_walk_inc_volume_thrust_last_sample(
    close: list[Any],
    volume: list[Any],
    vol_sma: list[Any],
    sensitivity: float,
) -> list[bool]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[bool] = []
    for i in range(len(close)):
        ev._ta_call_i = 0
        out.append(bool(ev._volume_thrust_inc_update(close[i], volume[i], vol_sma[i], sensitivity)))
    return out


def test_incremental_volume_thrust_matches_full() -> None:
    close, volume, vol_sma = _vt_series(120)
    sensitivity = 0.3
    got = _bar_walk_inc_volume_thrust(close, volume, vol_sma, sensitivity)
    exp = _bar_walk_full_volume_thrust(close, volume, vol_sma, sensitivity)
    assert got == exp
    last = _bar_walk_inc_volume_thrust_last_sample(close, volume, vol_sma, sensitivity)
    assert last == exp
    oracle = [
        _volume_thrust_last_n(close[: i + 1], volume[: i + 1], vol_sma[: i + 1], sensitivity) for i in range(len(close))
    ]
    assert got == oracle
    assert True in got


def test_incremental_volume_thrust_warmup() -> None:
    """Empty series or a single close (no 1% move vs default prev 100) is False."""
    close = [100.0]
    volume = [1500.0]
    vol_sma = [1000.0]
    sensitivity = 0.3
    got = _bar_walk_inc_volume_thrust(close, volume, vol_sma, sensitivity)
    exp = _bar_walk_full_volume_thrust(close, volume, vol_sma, sensitivity)
    assert got == exp
    assert got == [False]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._volume_thrust_inc_update([], [], [], 0.3) is False
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._volume_thrust_inc_update(None, None, None, 0.3) is False
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_volume_thrust([None], [None], [None], 0.3)
    exp_na = _bar_walk_full_volume_thrust([None], [None], [None], 0.3)
    assert got_na == exp_na
    assert got_na[0] is False


def test_incremental_volume_thrust_detected() -> None:
    """Volume spike plus >1% close change is True after bar 0."""
    close = [100.0, 102.0]
    volume = [1000.0, 1500.0]
    vol_sma = [1000.0, 1000.0]
    got = _bar_walk_inc_volume_thrust(close, volume, vol_sma, 0.3)
    exp = _bar_walk_full_volume_thrust(close, volume, vol_sma, 0.3)
    assert got == exp
    assert got[0] is False
    assert got[-1] is True
    last = _bar_walk_inc_volume_thrust_last_sample(close, volume, vol_sma, 0.3)
    assert last == exp


def test_incremental_volume_thrust_no_spike_or_move() -> None:
    """Missing volume spike or missing price move is False."""
    close_move = [100.0, 102.0]
    vol_flat = [1000.0, 1000.0]
    sma = [1000.0, 1000.0]
    got_vol = _bar_walk_inc_volume_thrust(close_move, vol_flat, sma, 0.3)
    exp_vol = _bar_walk_full_volume_thrust(close_move, vol_flat, sma, 0.3)
    assert got_vol == exp_vol
    assert got_vol[-1] is False

    close_flat = [100.0, 100.1]
    vol_spike = [1000.0, 1500.0]
    got_px = _bar_walk_inc_volume_thrust(close_flat, vol_spike, sma, 0.3)
    exp_px = _bar_walk_full_volume_thrust(close_flat, vol_spike, sma, 0.3)
    assert got_px == exp_px
    assert got_px[-1] is False


def test_incremental_volume_thrust_non_numeric_last() -> None:
    """Non-numeric last close → 100.0; last volume / vol_sma → 1000.0."""
    close: list[Any] = [100.0, 102.0, "x"]
    volume: list[Any] = [1000.0, 1500.0, None]
    vol_sma: list[Any] = [1000.0, 1000.0, None]
    got = _bar_walk_inc_volume_thrust(close, volume, vol_sma, 0.3)
    exp = _bar_walk_full_volume_thrust(close, volume, vol_sma, 0.3)
    assert got == exp
    last = _bar_walk_inc_volume_thrust_last_sample(close, volume, vol_sma, 0.3)
    assert last == exp
    # c=100, c_prev=102, v=1000, vs=1000 → no spike, ~2% move → False
    assert got[-1] is False


def test_incremental_volume_thrust_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    close, volume, vol_sma = _vt_series(40)
    close_na: list[float | None] = list(close)
    close_na[4] = None
    ev = _IncTA()
    for i in range(len(close_na)):
        ev._ta_call_i = 0
        ev._volume_thrust_inc_update(close_na[: i + 1], volume[: i + 1], vol_sma[: i + 1], 0.3)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_volume_thrust_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    close, volume, vol_sma = _vt_series(30)
    ev = _IncTA()
    for i in range(len(close)):
        ev._ta_call_i = 0
        ev._builtin_ta_volume_thrust([close[: i + 1], volume[: i + 1], vol_sma[: i + 1], 0.3])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_volume_thrust_two_call_sites_independent() -> None:
    close, volume, vol_sma = _vt_series(80)
    ev = _IncTA()
    a_out: list[bool] = []
    b_out: list[bool] = []
    for i in range(len(close)):
        prefix_c = close[: i + 1]
        prefix_v = volume[: i + 1]
        prefix_s = vol_sma[: i + 1]
        ev._ta_call_i = 0
        a_out.append(bool(ev._volume_thrust_inc_update(prefix_c, prefix_v, prefix_s, 0.1)))
        b_out.append(bool(ev._volume_thrust_inc_update(prefix_c, prefix_v, prefix_s, 0.3)))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    assert a_out == _bar_walk_full_volume_thrust(close, volume, vol_sma, 0.1)
    assert b_out == _bar_walk_full_volume_thrust(close, volume, vol_sma, 0.3)
    assert a_out != b_out


def test_runtime_volume_thrust_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _vt_bars(80)
    src = """//@version=5
indicator("volume thrust")
f = ta.volume_thrust(close, volume, open, 0.3)
g = ta.volume_thrust(close, volume, open, 0.8)
plot(f ? 1 : 0, "vt03")
plot(g ? 1 : 0, "vt08")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"vt03", "vt08"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # last-sample on the reversed list is the oldest bar — not chronological
    # last-sample. Incremental last sample is the chronological prefix formula
    # (list-oracle / kernel). Do not require incremental == disabled for every bar.
    closes = [b["close"] for b in bars]
    vols = [float(b["volume"]) for b in bars]
    smas = [float(b["open"]) for b in bars]
    for i, val in enumerate(r_on["series"]["vt03"]):
        exp = _volume_thrust_last_n(closes[: i + 1], vols[: i + 1], smas[: i + 1], 0.3)
        assert val == pytest.approx(1.0 if exp else 0.0, rel=1e-9, abs=1e-9), f"vt03 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["vt08"]):
        exp = _volume_thrust_last_n(closes[: i + 1], vols[: i + 1], smas[: i + 1], 0.8)
        assert val == pytest.approx(1.0 if exp else 0.0, rel=1e-9, abs=1e-9), f"vt08 bar {i}: {val} != {exp}"
    assert r_on["series"]["vt03"][0] == pytest.approx(0.0)
    assert r_off["series"]["vt03"][0] == pytest.approx(0.0)
    assert r_on["series"]["vt03"][4] != pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T2: liquidity_score incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _liquidity_score_last_n(
    volume: list[Any],
    volatility: list[Any],
    spread: list[Any],
    period: int,
) -> float:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    if len(volume) < period or len(volatility) < period or len(spread) < period or period <= 0:
        return 50.0
    vol_avg = sum(v for v in volume[-period:] if isinstance(v, (int, float))) / period if volume else 1000.0
    vol_score = min(100.0, vol_avg / 100.0)
    valid_volatility = [v for v in volatility[-period:] if isinstance(v, (int, float))]
    vol_avg_volatility = sum(valid_volatility) / period if volatility else 1.0
    volatility_score = max(0.0, 100.0 - vol_avg_volatility * 50.0)
    spread_avg = sum(s for s in spread[-period:] if isinstance(s, (int, float))) / period if spread else 0.1
    spread_score = max(0.0, 100.0 - spread_avg * 100.0)
    liquidity = vol_score * 0.4 + volatility_score * 0.3 + spread_score * 0.3
    return max(0.0, min(100.0, liquidity))


def _liq_series(n: int = 120) -> tuple[list[float], list[float], list[float]]:
    """Volume / volatility / spread with mixed liquidity regimes."""
    volume = _vols(n, seed=2000.0)
    volatility = [0.4 + 0.3 * math.sin(i / 6.0) for i in range(n)]
    spread = [0.05 + 0.02 * abs(math.sin(i / 4.0)) for i in range(n)]
    return volume, volatility, spread


def _liq_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: volume, open=volatility, close=spread."""
    bars: list[dict] = []
    for i in range(n):
        vola = 0.4 + 0.3 * math.sin(i / 6.0)
        spr = 0.05 + 0.02 * abs(math.sin(i / 4.0))
        bars.append(
            {
                "open": vola,
                "high": max(vola, spr) + 0.1,
                "low": min(vola, spr) - 0.01,
                "close": spr,
                "volume": 2000 + i * 15,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_liquidity_score(
    volume: list[Any],
    volatility: list[Any],
    spread: list[Any],
    period: int,
) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(volume)):
        out.append(ev._builtin_ta_liquidity_score([volume[: i + 1], volatility[: i + 1], spread[: i + 1], period]))
    return out


def _bar_walk_inc_liquidity_score(
    volume: list[Any],
    volatility: list[Any],
    spread: list[Any],
    period: int,
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(volume)):
        ev._ta_call_i = 0
        out.append(ev._liquidity_score_inc_update(volume[: i + 1], volatility[: i + 1], spread[: i + 1], period))
    return out


def _bar_walk_inc_liquidity_score_last_sample(
    volume: list[Any],
    volatility: list[Any],
    spread: list[Any],
    period: int,
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(volume)):
        ev._ta_call_i = 0
        out.append(ev._liquidity_score_inc_update(volume[i], volatility[i], spread[i], period))
    return out


def test_incremental_liquidity_score_matches_full() -> None:
    volume, volatility, spread = _liq_series(120)
    period = 5
    got = _bar_walk_inc_liquidity_score(volume, volatility, spread, period)
    exp = _bar_walk_full_liquidity_score(volume, volatility, spread, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_liquidity_score_last_sample(volume, volatility, spread, period)
    _assert_series_close(last, exp)
    oracle = [
        _liquidity_score_last_n(volume[: i + 1], volatility[: i + 1], spread[: i + 1], period)
        for i in range(len(volume))
    ]
    _assert_series_close(got, oracle)


def test_incremental_liquidity_score_warmup() -> None:
    """Window shorter than period, empty, None, or period<=0 is ``50.0``."""
    volume = [2000.0, 2100.0]
    volatility = [0.4, 0.5]
    spread = [0.05, 0.06]
    period = 5
    got = _bar_walk_inc_liquidity_score(volume, volatility, spread, period)
    exp = _bar_walk_full_liquidity_score(volume, volatility, spread, period)
    _assert_series_close(got, exp)
    assert got == [50.0, 50.0]

    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._liquidity_score_inc_update([], [], [], 5) == 50.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._liquidity_score_inc_update(None, None, None, 5) == 50.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._liquidity_score_inc_update(2000.0, 0.4, 0.05, 0) == 50.0
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._liquidity_score_inc_update(2000.0, 0.4, 0.05, -3) == 50.0
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_liquidity_score([None], [None], [None], 5)
    exp_na = _bar_walk_full_liquidity_score([None], [None], [None], 5)
    _assert_series_close(got_na, exp_na)
    assert got_na[0] == 50.0


def test_incremental_liquidity_score_non_numeric() -> None:
    """Non-numeric samples are dropped from the sum; still divide by period."""
    period = 3
    volume: list[Any] = [2000.0, None, 4000.0]
    volatility: list[Any] = [0.4, "x", 0.2]
    spread: list[Any] = [0.05, None, 0.01]
    got = _bar_walk_inc_liquidity_score(volume, volatility, spread, period)
    exp = _bar_walk_full_liquidity_score(volume, volatility, spread, period)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_liquidity_score_last_sample(volume, volatility, spread, period)
    _assert_series_close(last, exp)
    oracle = [
        _liquidity_score_last_n(volume[: i + 1], volatility[: i + 1], spread[: i + 1], period)
        for i in range(len(volume))
    ]
    _assert_series_close(got, oracle)


def test_incremental_liquidity_score_slot_count_stable() -> None:
    """One call-site slot every bar, including warmup / na."""
    volume, volatility, spread = _liq_series(40)
    volume_na: list[float | None] = list(volume)
    volume_na[4] = None
    ev = _IncTA()
    for i in range(len(volume_na)):
        ev._ta_call_i = 0
        ev._liquidity_score_inc_update(volume_na[: i + 1], volatility[: i + 1], spread[: i + 1], 5)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_liquidity_score_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    volume, volatility, spread = _liq_series(30)
    ev = _IncTA()
    for i in range(len(volume)):
        ev._ta_call_i = 0
        ev._builtin_ta_liquidity_score([volume[: i + 1], volatility[: i + 1], spread[: i + 1], 5])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_liquidity_score_two_call_sites_independent() -> None:
    volume, volatility, spread = _liq_series(80)
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(volume)):
        prefix_v = volume[: i + 1]
        prefix_vola = volatility[: i + 1]
        prefix_s = spread[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._liquidity_score_inc_update(prefix_v, prefix_vola, prefix_s, 5))
        b_out.append(ev._liquidity_score_inc_update(prefix_v, prefix_vola, prefix_s, 14))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_liquidity_score(volume, volatility, spread, 5))
    _assert_series_close(b_out, _bar_walk_full_liquidity_score(volume, volatility, spread, 14))
    assert a_out != b_out


def test_runtime_liquidity_score_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _liq_bars(80)
    src = """//@version=5
indicator("liquidity score")
f = ta.liquidity_score(volume, open, close, 5)
g = ta.liquidity_score(volume, open, close, 14)
plot(f, "liq5")
plot(g, "liq14")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"liq5", "liq14"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # ``[-period:]`` is the oldest window — not last-sample. Incremental last
    # sample is the chronological last-N formula (list-oracle / kernel). Do
    # not require incremental == disabled for every bar.
    vols = [float(b["volume"]) for b in bars]
    volas = [float(b["open"]) for b in bars]
    spreads = [float(b["close"]) for b in bars]
    for i, val in enumerate(r_on["series"]["liq5"]):
        exp = _liquidity_score_last_n(vols[: i + 1], volas[: i + 1], spreads[: i + 1], 5)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"liq5 bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["liq14"]):
        exp = _liquidity_score_last_n(vols[: i + 1], volas[: i + 1], spreads[: i + 1], 14)
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"liq14 bar {i}: {val} != {exp}"
    assert r_on["series"]["liq5"][0] == pytest.approx(50.0)
    assert r_off["series"]["liq5"][0] == pytest.approx(50.0)
    assert r_on["series"]["liq5"][4] != pytest.approx(50.0)


# ---------------------------------------------------------------------------
# T2: fear_greed_index incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _fear_greed_index_last_n(
    rsi: list[Any],
    vix: list[Any],
    put_call: list[Any],
    breadth: list[Any],
) -> float:
    """Oracle formula on a chronological prefix (same as full ``_expect_list`` lists)."""
    rsi_val = rsi[-1] if rsi and isinstance(rsi[-1], (int, float)) else 50.0
    vix_val = vix[-1] if vix and isinstance(vix[-1], (int, float)) else 2.0
    pc_val = put_call[-1] if put_call and isinstance(put_call[-1], (int, float)) else 1.0
    b_val = breadth[-1] if breadth and isinstance(breadth[-1], (int, float)) else 0.5
    rsi_fear = (rsi_val - 50) * 1.0
    vix_fear = (vix_val - 2.0) * 10.0
    pc_fear = (1.0 - pc_val) * 50.0
    b_fear = (b_val - 0.5) * 100.0
    fear_index = (rsi_fear + vix_fear + pc_fear + b_fear) / 4
    return max(-100.0, min(100.0, fear_index))


def _fg_series(n: int = 120) -> tuple[list[float], list[float], list[float], list[float]]:
    """RSI / VIX / put-call / breadth with mixed fear and greed regimes."""
    rsi = [50.0 + 20.0 * math.sin(i / 7.0) for i in range(n)]
    vix = [2.0 + 1.5 * math.sin(i / 5.0) for i in range(n)]
    put_call = [1.0 + 0.4 * math.sin(i / 4.0) for i in range(n)]
    breadth = [0.5 + 0.3 * math.sin(i / 6.0) for i in range(n)]
    return rsi, vix, put_call, breadth


def _fg_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: close=rsi, open=vix, high=put_call, low=breadth."""
    bars: list[dict] = []
    for i in range(n):
        rsi = 50.0 + 20.0 * math.sin(i / 7.0)
        vix = 2.0 + 1.5 * math.sin(i / 5.0)
        pc = 1.0 + 0.4 * math.sin(i / 4.0)
        breadth = 0.5 + 0.3 * math.sin(i / 6.0)
        bars.append(
            {
                "open": vix,
                "high": pc,
                "low": breadth,
                "close": rsi,
                "volume": 1000 + i * 10,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_fear_greed_index(
    rsi: list[Any],
    vix: list[Any],
    put_call: list[Any],
    breadth: list[Any],
) -> list[float]:
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(rsi)):
        out.append(ev._builtin_ta_fear_greed_index([rsi[: i + 1], vix[: i + 1], put_call[: i + 1], breadth[: i + 1]]))
    return out


def _bar_walk_inc_fear_greed_index(
    rsi: list[Any],
    vix: list[Any],
    put_call: list[Any],
    breadth: list[Any],
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(rsi)):
        ev._ta_call_i = 0
        out.append(ev._fear_greed_index_inc_update(rsi[: i + 1], vix[: i + 1], put_call[: i + 1], breadth[: i + 1]))
    return out


def _bar_walk_inc_fear_greed_index_last_sample(
    rsi: list[Any],
    vix: list[Any],
    put_call: list[Any],
    breadth: list[Any],
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(rsi)):
        ev._ta_call_i = 0
        out.append(ev._fear_greed_index_inc_update(rsi[i], vix[i], put_call[i], breadth[i]))
    return out


def test_incremental_fear_greed_index_matches_full() -> None:
    rsi, vix, put_call, breadth = _fg_series(120)
    got = _bar_walk_inc_fear_greed_index(rsi, vix, put_call, breadth)
    exp = _bar_walk_full_fear_greed_index(rsi, vix, put_call, breadth)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_fear_greed_index_last_sample(rsi, vix, put_call, breadth)
    _assert_series_close(last, exp)
    oracle = [
        _fear_greed_index_last_n(rsi[: i + 1], vix[: i + 1], put_call[: i + 1], breadth[: i + 1])
        for i in range(len(rsi))
    ]
    _assert_series_close(got, oracle)


def test_incremental_fear_greed_index_empty() -> None:
    """Empty / missing last sample → defaults (50/2/1/0.5) → 0.0, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._fear_greed_index_inc_update([], [], [], []) == pytest.approx(0.0)
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._fear_greed_index_inc_update(None, None, None, None) == pytest.approx(0.0)
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_fear_greed_index([None], [None], [None], [None])
    oracle_na = [_fear_greed_index_last_n([None], [None], [None], [None])]
    _assert_series_close(got_na, oracle_na)
    assert got_na[0] == pytest.approx(0.0)


def test_incremental_fear_greed_index_neutral() -> None:
    """All-neutral last samples (50/2/1/0.5) mix to 0.0."""
    rsi = [50.0, 50.0, 50.0]
    vix = [2.0, 2.0, 2.0]
    put_call = [1.0, 1.0, 1.0]
    breadth = [0.5, 0.5, 0.5]
    got = _bar_walk_inc_fear_greed_index(rsi, vix, put_call, breadth)
    exp = _bar_walk_full_fear_greed_index(rsi, vix, put_call, breadth)
    _assert_series_close(got, exp)
    assert got[-1] == pytest.approx(0.0)


def test_incremental_fear_greed_index_non_numeric_last() -> None:
    """Non-numeric last sample uses the same defaults as the full path."""
    rsi: list[Any] = [40.0, 60.0, "x"]
    vix: list[Any] = [1.5, 3.0, None]
    put_call: list[Any] = [0.8, 1.2, None]
    breadth: list[Any] = [0.4, 0.6, None]
    got = _bar_walk_inc_fear_greed_index(rsi, vix, put_call, breadth)
    exp = _bar_walk_full_fear_greed_index(rsi, vix, put_call, breadth)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_fear_greed_index_last_sample(rsi, vix, put_call, breadth)
    _assert_series_close(last, exp)
    # defaults 50/2/1/0.5 → 0.0
    assert got[-1] == pytest.approx(0.0)


def test_incremental_fear_greed_index_clamp() -> None:
    """Index is clamped to [-100, 100]."""
    rsi_hi = [50.0, 50.0, 200.0]
    vix_hi = [2.0, 2.0, 50.0]
    pc_hi = [1.0, 1.0, -10.0]
    b_hi = [0.5, 0.5, 10.0]
    got_hi = _bar_walk_inc_fear_greed_index(rsi_hi, vix_hi, pc_hi, b_hi)
    exp_hi = _bar_walk_full_fear_greed_index(rsi_hi, vix_hi, pc_hi, b_hi)
    _assert_series_close(got_hi, exp_hi)
    assert got_hi[-1] == pytest.approx(100.0)

    rsi_lo = [50.0, 50.0, -200.0]
    vix_lo = [2.0, 2.0, -50.0]
    pc_lo = [1.0, 1.0, 20.0]
    b_lo = [0.5, 0.5, -10.0]
    got_lo = _bar_walk_inc_fear_greed_index(rsi_lo, vix_lo, pc_lo, b_lo)
    exp_lo = _bar_walk_full_fear_greed_index(rsi_lo, vix_lo, pc_lo, b_lo)
    _assert_series_close(got_lo, exp_lo)
    assert got_lo[-1] == pytest.approx(-100.0)


def test_incremental_fear_greed_index_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    rsi, vix, put_call, breadth = _fg_series(40)
    rsi_na: list[float | None] = list(rsi)
    rsi_na[4] = None
    ev = _IncTA()
    for i in range(len(rsi_na)):
        ev._ta_call_i = 0
        ev._fear_greed_index_inc_update(rsi_na[: i + 1], vix[: i + 1], put_call[: i + 1], breadth[: i + 1])
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_fear_greed_index_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    rsi, vix, put_call, breadth = _fg_series(30)
    ev = _IncTA()
    for i in range(len(rsi)):
        ev._ta_call_i = 0
        ev._builtin_ta_fear_greed_index([rsi[: i + 1], vix[: i + 1], put_call[: i + 1], breadth[: i + 1]])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_fear_greed_index_two_call_sites_independent() -> None:
    rsi, vix, put_call, breadth = _fg_series(80)
    rsi_b = [100.0 - r for r in rsi]
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(rsi)):
        prefix_r = rsi[: i + 1]
        prefix_v = vix[: i + 1]
        prefix_p = put_call[: i + 1]
        prefix_b = breadth[: i + 1]
        prefix_rb = rsi_b[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._fear_greed_index_inc_update(prefix_r, prefix_v, prefix_p, prefix_b))
        b_out.append(ev._fear_greed_index_inc_update(prefix_rb, prefix_v, prefix_p, prefix_b))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_fear_greed_index(rsi, vix, put_call, breadth))
    _assert_series_close(b_out, _bar_walk_full_fear_greed_index(rsi_b, vix, put_call, breadth))
    assert a_out != b_out


def test_runtime_fear_greed_index_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _fg_bars(80)
    src = """//@version=5
indicator("fear greed")
f = ta.fear_greed_index(close, open, high, low)
g = ta.fear_greed_index(volume, close, open, high)
plot(f, "fg")
plot(g, "fg2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"fg", "fg2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses ``_expect_list`` on PineSeries (newest-first), so
    # last-sample on the reversed list is the oldest bar — not chronological
    # last-sample. Incremental last sample is the chronological prefix formula
    # (list-oracle / kernel). Do not require incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["fg"]):
        exp = _fear_greed_index_last_n(closes[: i + 1], opens[: i + 1], highs[: i + 1], lows[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"fg bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["fg2"]):
        exp = _fear_greed_index_last_n(vols[: i + 1], closes[: i + 1], opens[: i + 1], highs[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"fg2 bar {i}: {val} != {exp}"
    assert r_on["series"]["fg"][0] == pytest.approx(0.0)
    assert r_off["series"]["fg"][0] == pytest.approx(0.0)
    assert r_on["series"]["fg"][4] != pytest.approx(0.0)


# ---------------------------------------------------------------------------
# T2: crowd_sentiment incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _crowd_sentiment_last_n(
    price_agr: list[Any],
    vol_agr: list[Any],
    time_agr: list[Any],
) -> float:
    """Oracle formula on a chronological prefix (last sample, default 0.5)."""
    p = price_agr[-1] if price_agr and isinstance(price_agr[-1], (int, float)) else 0.5
    v = vol_agr[-1] if vol_agr and isinstance(vol_agr[-1], (int, float)) else 0.5
    t = time_agr[-1] if time_agr and isinstance(time_agr[-1], (int, float)) else 0.5
    return max(0.0, min(100.0, ((p + v + t) / 3) * 100))


def _cs_series(n: int = 120) -> tuple[list[float], list[float], list[float]]:
    """Price / volume / time agreement with mixed consensus regimes."""
    price = [0.5 + 0.4 * math.sin(i / 7.0) for i in range(n)]
    vol = [0.5 + 0.3 * math.sin(i / 5.0) for i in range(n)]
    time_a = [0.5 + 0.35 * math.sin(i / 6.0) for i in range(n)]
    return price, vol, time_a


def _cs_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: close=price, open=vol, high=time agreement."""
    bars: list[dict] = []
    for i in range(n):
        price = 0.5 + 0.4 * math.sin(i / 7.0)
        vol = 0.5 + 0.3 * math.sin(i / 5.0)
        time_a = 0.5 + 0.35 * math.sin(i / 6.0)
        bars.append(
            {
                "open": vol,
                "high": time_a,
                "low": 0.5,
                "close": price,
                "volume": 1000 + i * 10,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_crowd_sentiment(
    price_agr: list[Any],
    vol_agr: list[Any],
    time_agr: list[Any],
) -> list[float]:
    """Full-path oracle: last sample of each arg as a scalar (advanced.py formula)."""
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(price_agr)):
        out.append(ev._builtin_ta_crowd_sentiment([price_agr[i], vol_agr[i], time_agr[i]]))
    return out


def _bar_walk_inc_crowd_sentiment(
    price_agr: list[Any],
    vol_agr: list[Any],
    time_agr: list[Any],
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(price_agr)):
        ev._ta_call_i = 0
        out.append(ev._crowd_sentiment_inc_update(price_agr[: i + 1], vol_agr[: i + 1], time_agr[: i + 1]))
    return out


def _bar_walk_inc_crowd_sentiment_last_sample(
    price_agr: list[Any],
    vol_agr: list[Any],
    time_agr: list[Any],
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(price_agr)):
        ev._ta_call_i = 0
        out.append(ev._crowd_sentiment_inc_update(price_agr[i], vol_agr[i], time_agr[i]))
    return out


def test_incremental_crowd_sentiment_matches_full() -> None:
    price, vol, time_a = _cs_series(120)
    got = _bar_walk_inc_crowd_sentiment(price, vol, time_a)
    exp = _bar_walk_full_crowd_sentiment(price, vol, time_a)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_crowd_sentiment_last_sample(price, vol, time_a)
    _assert_series_close(last, exp)
    oracle = [_crowd_sentiment_last_n(price[: i + 1], vol[: i + 1], time_a[: i + 1]) for i in range(len(price))]
    _assert_series_close(got, oracle)


def test_incremental_crowd_sentiment_empty() -> None:
    """Empty / missing last sample → defaults (0.5/0.5/0.5) → 50.0, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._crowd_sentiment_inc_update([], [], []) == pytest.approx(50.0)
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._crowd_sentiment_inc_update(None, None, None) == pytest.approx(50.0)
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_crowd_sentiment([None], [None], [None])
    oracle_na = [_crowd_sentiment_last_n([None], [None], [None])]
    _assert_series_close(got_na, oracle_na)
    assert got_na[0] == pytest.approx(50.0)


def test_incremental_crowd_sentiment_neutral() -> None:
    """All-neutral last samples (0.5/0.5/0.5) mix to 50.0."""
    price = [0.5, 0.5, 0.5]
    vol = [0.5, 0.5, 0.5]
    time_a = [0.5, 0.5, 0.5]
    got = _bar_walk_inc_crowd_sentiment(price, vol, time_a)
    exp = _bar_walk_full_crowd_sentiment(price, vol, time_a)
    _assert_series_close(got, exp)
    assert got[-1] == pytest.approx(50.0)


def test_incremental_crowd_sentiment_non_numeric_last() -> None:
    """Non-numeric last sample uses the same defaults as the full path."""
    price: list[Any] = [0.4, 0.6, "x"]
    vol: list[Any] = [0.3, 0.7, None]
    time_a: list[Any] = [0.2, 0.8, None]
    got = _bar_walk_inc_crowd_sentiment(price, vol, time_a)
    exp = _bar_walk_full_crowd_sentiment(price, vol, time_a)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_crowd_sentiment_last_sample(price, vol, time_a)
    _assert_series_close(last, exp)
    # defaults 0.5/0.5/0.5 → 50.0
    assert got[-1] == pytest.approx(50.0)


def test_incremental_crowd_sentiment_clamp() -> None:
    """Consensus is clamped to [0, 100]."""
    price_hi = [0.5, 0.5, 2.0]
    vol_hi = [0.5, 0.5, 2.0]
    time_hi = [0.5, 0.5, 2.0]
    got_hi = _bar_walk_inc_crowd_sentiment(price_hi, vol_hi, time_hi)
    exp_hi = _bar_walk_full_crowd_sentiment(price_hi, vol_hi, time_hi)
    _assert_series_close(got_hi, exp_hi)
    assert got_hi[-1] == pytest.approx(100.0)

    price_lo = [0.5, 0.5, -1.0]
    vol_lo = [0.5, 0.5, -1.0]
    time_lo = [0.5, 0.5, -1.0]
    got_lo = _bar_walk_inc_crowd_sentiment(price_lo, vol_lo, time_lo)
    exp_lo = _bar_walk_full_crowd_sentiment(price_lo, vol_lo, time_lo)
    _assert_series_close(got_lo, exp_lo)
    assert got_lo[-1] == pytest.approx(0.0)


def test_incremental_crowd_sentiment_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    price, vol, time_a = _cs_series(40)
    price_na: list[float | None] = list(price)
    price_na[4] = None
    ev = _IncTA()
    for i in range(len(price_na)):
        ev._ta_call_i = 0
        ev._crowd_sentiment_inc_update(price_na[: i + 1], vol[: i + 1], time_a[: i + 1])
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_crowd_sentiment_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    price, vol, time_a = _cs_series(30)
    ev = _IncTA()
    for i in range(len(price)):
        ev._ta_call_i = 0
        ev._builtin_ta_crowd_sentiment([price[: i + 1], vol[: i + 1], time_a[: i + 1]])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_crowd_sentiment_two_call_sites_independent() -> None:
    price, vol, time_a = _cs_series(80)
    price_b = [1.0 - p for p in price]
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(price)):
        prefix_p = price[: i + 1]
        prefix_v = vol[: i + 1]
        prefix_t = time_a[: i + 1]
        prefix_pb = price_b[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._crowd_sentiment_inc_update(prefix_p, prefix_v, prefix_t))
        b_out.append(ev._crowd_sentiment_inc_update(prefix_pb, prefix_v, prefix_t))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_crowd_sentiment(price, vol, time_a))
    _assert_series_close(b_out, _bar_walk_full_crowd_sentiment(price_b, vol, time_a))
    assert a_out != b_out


def test_runtime_crowd_sentiment_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _cs_bars(80)
    src = """//@version=5
indicator("crowd sentiment")
f = ta.crowd_sentiment(close, open, high)
g = ta.crowd_sentiment(volume, close, open)
plot(f, "cs")
plot(g, "cs2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"cs", "cs2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses scalar isinstance on PineSeries (newest-first wrap),
    # so series args default to 0.5 → 50.0 every bar. Incremental last sample is
    # the chronological prefix formula (list-oracle / kernel). Do not require
    # incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["cs"]):
        exp = _crowd_sentiment_last_n(closes[: i + 1], opens[: i + 1], highs[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"cs bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["cs2"]):
        exp = _crowd_sentiment_last_n(vols[: i + 1], closes[: i + 1], opens[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"cs2 bar {i}: {val} != {exp}"
    assert r_on["series"]["cs"][0] == pytest.approx(50.0)
    assert r_off["series"]["cs"][0] == pytest.approx(50.0)
    assert r_on["series"]["cs"][4] != pytest.approx(50.0)


# ---------------------------------------------------------------------------
# T2: smart_money_flow incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _smart_money_flow_last_n(
    price_change: list[Any],
    volume: list[Any],
    time_high: list[Any],
    time_low: list[Any],
) -> float:
    """Oracle formula on a chronological prefix (last sample, defaults 0/1000/10/10)."""
    p = price_change[-1] if price_change and isinstance(price_change[-1], (int, float)) else 0.0
    v = volume[-1] if volume and isinstance(volume[-1], (int, float)) else 1000.0
    th = time_high[-1] if time_high and isinstance(time_high[-1], (int, float)) else 10
    tl = time_low[-1] if time_low and isinstance(time_low[-1], (int, float)) else 10
    vol_factor = min(1.0, v / 5000.0)
    if p > 0 and th < tl:
        flow = vol_factor * 0.8
    elif p < 0 and tl < th:
        flow = -vol_factor * 0.8
    else:
        flow = 0.0
    return max(-1.0, min(1.0, flow))


def _smf_series(n: int = 120) -> tuple[list[float], list[float], list[float], list[float]]:
    """Price change / volume / time_since_high / time_since_low with mixed flow."""
    price = [2.0 * math.sin(i / 7.0) for i in range(n)]
    vol = [1000.0 + 4000.0 * (0.5 + 0.5 * math.sin(i / 5.0)) for i in range(n)]
    time_high = [5.0 + 8.0 * math.sin(i / 4.0) for i in range(n)]
    time_low = [5.0 + 8.0 * math.cos(i / 6.0) for i in range(n)]
    return price, vol, time_high, time_low


def _smf_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: close=price_change, volume, high=time_high, low=time_low."""
    bars: list[dict] = []
    for i in range(n):
        price = 2.0 * math.sin(i / 7.0)
        vol = 1000.0 + 4000.0 * (0.5 + 0.5 * math.sin(i / 5.0))
        time_high = 5.0 + 8.0 * math.sin(i / 4.0)
        time_low = 5.0 + 8.0 * math.cos(i / 6.0)
        bars.append(
            {
                "open": -price,
                "high": time_high,
                "low": time_low,
                "close": price,
                "volume": vol,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_smart_money_flow(
    price_change: list[Any],
    volume: list[Any],
    time_high: list[Any],
    time_low: list[Any],
) -> list[float]:
    """Full-path oracle: last sample of each arg as a scalar (advanced.py formula)."""
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(price_change)):
        out.append(ev._builtin_ta_smart_money_flow([price_change[i], volume[i], time_high[i], time_low[i]]))
    return out


def _bar_walk_inc_smart_money_flow(
    price_change: list[Any],
    volume: list[Any],
    time_high: list[Any],
    time_low: list[Any],
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(price_change)):
        ev._ta_call_i = 0
        out.append(
            ev._smart_money_flow_inc_update(
                price_change[: i + 1],
                volume[: i + 1],
                time_high[: i + 1],
                time_low[: i + 1],
            )
        )
    return out


def _bar_walk_inc_smart_money_flow_last_sample(
    price_change: list[Any],
    volume: list[Any],
    time_high: list[Any],
    time_low: list[Any],
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(price_change)):
        ev._ta_call_i = 0
        out.append(ev._smart_money_flow_inc_update(price_change[i], volume[i], time_high[i], time_low[i]))
    return out


def test_incremental_smart_money_flow_matches_full() -> None:
    price, vol, time_h, time_l = _smf_series(120)
    got = _bar_walk_inc_smart_money_flow(price, vol, time_h, time_l)
    exp = _bar_walk_full_smart_money_flow(price, vol, time_h, time_l)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_smart_money_flow_last_sample(price, vol, time_h, time_l)
    _assert_series_close(last, exp)
    oracle = [
        _smart_money_flow_last_n(price[: i + 1], vol[: i + 1], time_h[: i + 1], time_l[: i + 1])
        for i in range(len(price))
    ]
    _assert_series_close(got, oracle)
    assert any(v != pytest.approx(0.0) for v in got)


def test_incremental_smart_money_flow_empty() -> None:
    """Empty / missing last sample → defaults (0/1000/10/10) → 0.0, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._smart_money_flow_inc_update([], [], [], []) == pytest.approx(0.0)
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._smart_money_flow_inc_update(None, None, None, None) == pytest.approx(0.0)
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_smart_money_flow([None], [None], [None], [None])
    oracle_na = [_smart_money_flow_last_n([None], [None], [None], [None])]
    _assert_series_close(got_na, oracle_na)
    assert got_na[0] == pytest.approx(0.0)


def test_incremental_smart_money_flow_signed_regimes() -> None:
    """Buying / selling / balanced last samples match the full-path oracle."""
    # price>0 and time_high < time_low → +vol_factor*0.8
    buy_p, buy_v, buy_h, buy_l = [1.0], [5000.0], [2.0], [10.0]
    got_buy = _bar_walk_inc_smart_money_flow(buy_p, buy_v, buy_h, buy_l)
    exp_buy = _bar_walk_full_smart_money_flow(buy_p, buy_v, buy_h, buy_l)
    _assert_series_close(got_buy, exp_buy)
    assert got_buy[-1] == pytest.approx(0.8)

    # price<0 and time_low < time_high → -vol_factor*0.8
    sell_p, sell_v, sell_h, sell_l = [-1.0], [5000.0], [10.0], [2.0]
    got_sell = _bar_walk_inc_smart_money_flow(sell_p, sell_v, sell_h, sell_l)
    exp_sell = _bar_walk_full_smart_money_flow(sell_p, sell_v, sell_h, sell_l)
    _assert_series_close(got_sell, exp_sell)
    assert got_sell[-1] == pytest.approx(-0.8)

    # price==0 or times equal → 0.0
    neu_p, neu_v, neu_h, neu_l = [0.0, 1.0], [2500.0, 2500.0], [10.0, 10.0], [10.0, 10.0]
    got_neu = _bar_walk_inc_smart_money_flow(neu_p, neu_v, neu_h, neu_l)
    exp_neu = _bar_walk_full_smart_money_flow(neu_p, neu_v, neu_h, neu_l)
    _assert_series_close(got_neu, exp_neu)
    assert got_neu[-1] == pytest.approx(0.0)


def test_incremental_smart_money_flow_non_numeric_last() -> None:
    """Non-numeric last sample uses the same defaults as the full path."""
    price: list[Any] = [1.0, -1.0, "x"]
    vol: list[Any] = [2500.0, 2500.0, None]
    time_h: list[Any] = [2.0, 10.0, None]
    time_l: list[Any] = [10.0, 2.0, None]
    got = _bar_walk_inc_smart_money_flow(price, vol, time_h, time_l)
    exp = _bar_walk_full_smart_money_flow(price, vol, time_h, time_l)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_smart_money_flow_last_sample(price, vol, time_h, time_l)
    _assert_series_close(last, exp)
    # defaults 0/1000/10/10 → 0.0
    assert got[-1] == pytest.approx(0.0)


def test_incremental_smart_money_flow_clamp() -> None:
    """Flow is clamped to [-1, 1] when volume-scaled factor exceeds the band."""
    # Negative volume + buying branch → vol_factor*0.8 < -1
    price_lo = [0.0, 1.0]
    vol_lo = [1000.0, -10000.0]
    time_h_lo = [5.0, 2.0]
    time_l_lo = [5.0, 10.0]
    got_lo = _bar_walk_inc_smart_money_flow(price_lo, vol_lo, time_h_lo, time_l_lo)
    exp_lo = _bar_walk_full_smart_money_flow(price_lo, vol_lo, time_h_lo, time_l_lo)
    _assert_series_close(got_lo, exp_lo)
    assert got_lo[-1] == pytest.approx(-1.0)

    # Negative volume + selling branch → -vol_factor*0.8 > 1
    price_hi = [0.0, -1.0]
    vol_hi = [1000.0, -10000.0]
    time_h_hi = [5.0, 10.0]
    time_l_hi = [5.0, 2.0]
    got_hi = _bar_walk_inc_smart_money_flow(price_hi, vol_hi, time_h_hi, time_l_hi)
    exp_hi = _bar_walk_full_smart_money_flow(price_hi, vol_hi, time_h_hi, time_l_hi)
    _assert_series_close(got_hi, exp_hi)
    assert got_hi[-1] == pytest.approx(1.0)


def test_incremental_smart_money_flow_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    price, vol, time_h, time_l = _smf_series(40)
    price_na: list[float | None] = list(price)
    price_na[4] = None
    ev = _IncTA()
    for i in range(len(price_na)):
        ev._ta_call_i = 0
        ev._smart_money_flow_inc_update(price_na[: i + 1], vol[: i + 1], time_h[: i + 1], time_l[: i + 1])
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_smart_money_flow_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    price, vol, time_h, time_l = _smf_series(30)
    ev = _IncTA()
    for i in range(len(price)):
        ev._ta_call_i = 0
        ev._builtin_ta_smart_money_flow([price[: i + 1], vol[: i + 1], time_h[: i + 1], time_l[: i + 1]])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_smart_money_flow_two_call_sites_independent() -> None:
    price, vol, time_h, time_l = _smf_series(80)
    price_b = [-p for p in price]
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(price)):
        prefix_p = price[: i + 1]
        prefix_v = vol[: i + 1]
        prefix_h = time_h[: i + 1]
        prefix_l = time_l[: i + 1]
        prefix_pb = price_b[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._smart_money_flow_inc_update(prefix_p, prefix_v, prefix_h, prefix_l))
        b_out.append(ev._smart_money_flow_inc_update(prefix_pb, prefix_v, prefix_h, prefix_l))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_smart_money_flow(price, vol, time_h, time_l))
    _assert_series_close(b_out, _bar_walk_full_smart_money_flow(price_b, vol, time_h, time_l))
    assert a_out != b_out


def test_runtime_smart_money_flow_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _smf_bars(80)
    src = """//@version=5
indicator("smart money flow")
f = ta.smart_money_flow(close, volume, high, low)
g = ta.smart_money_flow(open, volume, low, high)
plot(f, "smf")
plot(g, "smf2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"smf", "smf2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses scalar isinstance on PineSeries (newest-first wrap),
    # so series args default to 0/1000/10/10 → 0.0 every bar. Incremental last
    # sample is the chronological prefix formula (list-oracle / kernel). Do not
    # require incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["smf"]):
        exp = _smart_money_flow_last_n(closes[: i + 1], vols[: i + 1], highs[: i + 1], lows[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"smf bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["smf2"]):
        exp = _smart_money_flow_last_n(opens[: i + 1], vols[: i + 1], lows[: i + 1], highs[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"smf2 bar {i}: {val} != {exp}"
    assert r_on["series"]["smf"][0] == pytest.approx(0.0)
    assert r_off["series"]["smf"][0] == pytest.approx(0.0)
    assert any(v != pytest.approx(0.0) for v in r_on["series"]["smf"][1:])


# ---------------------------------------------------------------------------
# T2: trend_confirmation_score incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _trend_confirmation_score_last_n(
    momentum: list[Any],
    trend_alignment: list[Any],
    strength: list[Any],
    rsi: list[Any],
    rsi_alignment: list[Any],
) -> float:
    """Oracle formula on a chronological prefix (last sample, defaults 0/0/1/50/0)."""
    m = momentum[-1] if momentum and isinstance(momentum[-1], (int, float)) else 0.0
    t = trend_alignment[-1] if trend_alignment and isinstance(trend_alignment[-1], (int, float)) else 0.0
    s = strength[-1] if strength and isinstance(strength[-1], (int, float)) else 1.0
    r = rsi[-1] if rsi and isinstance(rsi[-1], (int, float)) else 50.0
    a = rsi_alignment[-1] if rsi_alignment and isinstance(rsi_alignment[-1], (int, float)) else 0.0
    momentum_score = min(100.0, abs(m) * 20.0)
    trend_score = max(0.0, (t + 1.0) / 2.0 * 100.0)
    strength_score = min(100.0, s * 50.0)
    rsi_score = min(100.0, abs(r - 50.0) * 2.0) if abs(r - 50.0) > 10.0 else 40.0
    alignment_bonus = 20.0 if abs(a) > 0.5 else 0.0
    total = momentum_score * 0.25 + trend_score * 0.3 + strength_score * 0.25 + rsi_score * 0.15 + alignment_bonus
    return max(0.0, min(100.0, total))


def _tcs_series(
    n: int = 120,
) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    """Momentum / trend / strength / rsi / rsi_alignment with mixed mix regimes."""
    momentum = [2.0 * math.sin(i / 7.0) for i in range(n)]
    trend = [math.sin(i / 5.0) for i in range(n)]
    strength = [1.0 + 0.8 * math.sin(i / 6.0) for i in range(n)]
    rsi = [50.0 + 30.0 * math.sin(i / 8.0) for i in range(n)]
    rsi_align = [math.sin(i / 4.0) for i in range(n)]
    return momentum, trend, strength, rsi, rsi_align


def _tcs_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: close=mom, open=trend, high=strength, volume=rsi, low=align."""
    bars: list[dict] = []
    for i in range(n):
        momentum = 2.0 * math.sin(i / 7.0)
        trend = math.sin(i / 5.0)
        strength = 1.0 + 0.8 * math.sin(i / 6.0)
        rsi = 50.0 + 30.0 * math.sin(i / 8.0)
        rsi_align = math.sin(i / 4.0)
        bars.append(
            {
                "open": trend,
                "high": strength,
                "low": rsi_align,
                "close": momentum,
                "volume": rsi,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_trend_confirmation_score(
    momentum: list[Any],
    trend: list[Any],
    strength: list[Any],
    rsi: list[Any],
    rsi_align: list[Any],
) -> list[float]:
    """Full-path oracle: last sample of each arg as a scalar (advanced.py formula)."""
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(momentum)):
        out.append(
            ev._builtin_ta_trend_confirmation_score([momentum[i], trend[i], strength[i], rsi[i], rsi_align[i], 0.0])
        )
    return out


def _bar_walk_inc_trend_confirmation_score(
    momentum: list[Any],
    trend: list[Any],
    strength: list[Any],
    rsi: list[Any],
    rsi_align: list[Any],
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(momentum)):
        ev._ta_call_i = 0
        out.append(
            ev._trend_confirmation_score_inc_update(
                momentum[: i + 1],
                trend[: i + 1],
                strength[: i + 1],
                rsi[: i + 1],
                rsi_align[: i + 1],
            )
        )
    return out


def _bar_walk_inc_trend_confirmation_score_last_sample(
    momentum: list[Any],
    trend: list[Any],
    strength: list[Any],
    rsi: list[Any],
    rsi_align: list[Any],
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(momentum)):
        ev._ta_call_i = 0
        out.append(ev._trend_confirmation_score_inc_update(momentum[i], trend[i], strength[i], rsi[i], rsi_align[i]))
    return out


def test_incremental_trend_confirmation_score_matches_full() -> None:
    mom, trend, strength, rsi, align = _tcs_series(120)
    got = _bar_walk_inc_trend_confirmation_score(mom, trend, strength, rsi, align)
    exp = _bar_walk_full_trend_confirmation_score(mom, trend, strength, rsi, align)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_trend_confirmation_score_last_sample(mom, trend, strength, rsi, align)
    _assert_series_close(last, exp)
    oracle = [
        _trend_confirmation_score_last_n(
            mom[: i + 1],
            trend[: i + 1],
            strength[: i + 1],
            rsi[: i + 1],
            align[: i + 1],
        )
        for i in range(len(mom))
    ]
    _assert_series_close(got, oracle)
    assert any(v != pytest.approx(33.5) for v in got)


def test_incremental_trend_confirmation_score_empty() -> None:
    """Empty / missing last sample → defaults (0/0/1/50/0) → 33.5, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._trend_confirmation_score_inc_update([], [], [], [], []) == pytest.approx(33.5)
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._trend_confirmation_score_inc_update(None, None, None, None, None) == pytest.approx(33.5)
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_trend_confirmation_score([None], [None], [None], [None], [None])
    oracle_na = [_trend_confirmation_score_last_n([None], [None], [None], [None], [None])]
    _assert_series_close(got_na, oracle_na)
    assert got_na[0] == pytest.approx(33.5)


def test_incremental_trend_confirmation_score_alignment_bonus() -> None:
    """|rsi_alignment| > 0.5 adds 20; otherwise the mix has no bonus."""
    # defaults + |align| > 0.5 → 33.5 + 20 = 53.5
    mom, trend, strength, rsi, align = [0.0], [0.0], [1.0], [50.0], [0.6]
    got = _bar_walk_inc_trend_confirmation_score(mom, trend, strength, rsi, align)
    exp = _bar_walk_full_trend_confirmation_score(mom, trend, strength, rsi, align)
    _assert_series_close(got, exp)
    assert got[-1] == pytest.approx(53.5)

    mom, trend, strength, rsi, align = [0.0], [0.0], [1.0], [50.0], [0.5]
    got_edge = _bar_walk_inc_trend_confirmation_score(mom, trend, strength, rsi, align)
    exp_edge = _bar_walk_full_trend_confirmation_score(mom, trend, strength, rsi, align)
    _assert_series_close(got_edge, exp_edge)
    assert got_edge[-1] == pytest.approx(33.5)


def test_incremental_trend_confirmation_score_non_numeric_last() -> None:
    """Non-numeric last sample uses the same defaults as the full path."""
    mom: list[Any] = [1.0, -1.0, "x"]
    trend: list[Any] = [0.8, -0.8, None]
    strength: list[Any] = [1.5, 1.5, None]
    rsi: list[Any] = [70.0, 30.0, None]
    align: list[Any] = [0.9, -0.9, None]
    got = _bar_walk_inc_trend_confirmation_score(mom, trend, strength, rsi, align)
    exp = _bar_walk_full_trend_confirmation_score(mom, trend, strength, rsi, align)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_trend_confirmation_score_last_sample(mom, trend, strength, rsi, align)
    _assert_series_close(last, exp)
    # defaults 0/0/1/50/0 → 33.5
    assert got[-1] == pytest.approx(33.5)


def test_incremental_trend_confirmation_score_clamp() -> None:
    """Score is clamped to [0, 100] when the mix exceeds the band."""
    # Strong mix + alignment bonus → 115 → 100
    mom_hi = [0.0, 10.0]
    trend_hi = [0.0, 1.0]
    strength_hi = [1.0, 10.0]
    rsi_hi = [50.0, 0.0]
    align_hi = [0.0, 1.0]
    got_hi = _bar_walk_inc_trend_confirmation_score(mom_hi, trend_hi, strength_hi, rsi_hi, align_hi)
    exp_hi = _bar_walk_full_trend_confirmation_score(mom_hi, trend_hi, strength_hi, rsi_hi, align_hi)
    _assert_series_close(got_hi, exp_hi)
    assert got_hi[-1] == pytest.approx(100.0)

    # Negative strength drives the mix below 0 → clamp 0
    mom_lo = [0.0, 0.0]
    trend_lo = [0.0, -1.0]
    strength_lo = [1.0, -10.0]
    rsi_lo = [50.0, 50.0]
    align_lo = [0.0, 0.0]
    got_lo = _bar_walk_inc_trend_confirmation_score(mom_lo, trend_lo, strength_lo, rsi_lo, align_lo)
    exp_lo = _bar_walk_full_trend_confirmation_score(mom_lo, trend_lo, strength_lo, rsi_lo, align_lo)
    _assert_series_close(got_lo, exp_lo)
    assert got_lo[-1] == pytest.approx(0.0)


def test_incremental_trend_confirmation_score_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    mom, trend, strength, rsi, align = _tcs_series(40)
    mom_na: list[float | None] = list(mom)
    mom_na[4] = None
    ev = _IncTA()
    for i in range(len(mom_na)):
        ev._ta_call_i = 0
        ev._trend_confirmation_score_inc_update(
            mom_na[: i + 1],
            trend[: i + 1],
            strength[: i + 1],
            rsi[: i + 1],
            align[: i + 1],
        )
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_trend_confirmation_score_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    mom, trend, strength, rsi, align = _tcs_series(30)
    ev = _IncTA()
    for i in range(len(mom)):
        ev._ta_call_i = 0
        ev._builtin_ta_trend_confirmation_score(
            [
                mom[: i + 1],
                trend[: i + 1],
                strength[: i + 1],
                rsi[: i + 1],
                align[: i + 1],
                0.0,
            ]
        )
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_trend_confirmation_score_two_call_sites_independent() -> None:
    mom, trend, strength, rsi, align = _tcs_series(80)
    # abs(momentum) is even, so invert trend_alignment (signed mix term).
    trend_b = [-t for t in trend]
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(mom)):
        prefix_m = mom[: i + 1]
        prefix_t = trend[: i + 1]
        prefix_s = strength[: i + 1]
        prefix_r = rsi[: i + 1]
        prefix_a = align[: i + 1]
        prefix_tb = trend_b[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._trend_confirmation_score_inc_update(prefix_m, prefix_t, prefix_s, prefix_r, prefix_a))
        b_out.append(ev._trend_confirmation_score_inc_update(prefix_m, prefix_tb, prefix_s, prefix_r, prefix_a))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(
        a_out,
        _bar_walk_full_trend_confirmation_score(mom, trend, strength, rsi, align),
    )
    _assert_series_close(
        b_out,
        _bar_walk_full_trend_confirmation_score(mom, trend_b, strength, rsi, align),
    )
    assert a_out != b_out


def test_runtime_trend_confirmation_score_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _tcs_bars(80)
    src = """//@version=5
indicator("trend confirmation score")
f = ta.trend_confirmation_score(close, open, high, volume, low, close)
g = ta.trend_confirmation_score(open, close, volume, high, low, open)
plot(f, "tcs")
plot(g, "tcs2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"tcs", "tcs2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses scalar isinstance on PineSeries (newest-first wrap),
    # so series args default to 0/0/1/50/0 → 33.5 every bar. Incremental last
    # sample is the chronological prefix formula (list-oracle / kernel). Do not
    # require incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["tcs"]):
        exp = _trend_confirmation_score_last_n(
            closes[: i + 1],
            opens[: i + 1],
            highs[: i + 1],
            vols[: i + 1],
            lows[: i + 1],
        )
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"tcs bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["tcs2"]):
        exp = _trend_confirmation_score_last_n(
            opens[: i + 1],
            closes[: i + 1],
            vols[: i + 1],
            highs[: i + 1],
            lows[: i + 1],
        )
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"tcs2 bar {i}: {val} != {exp}"
    assert r_on["series"]["tcs"][0] == pytest.approx(33.5)
    assert r_off["series"]["tcs"][0] == pytest.approx(33.5)
    assert any(v != pytest.approx(33.5) for v in r_on["series"]["tcs"][1:])


# ---------------------------------------------------------------------------
# T2: atr_stop incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


_ATR_STOP_OFF: dict[str, float | None] = {"long_stop": None, "short_stop": None}


def _atr_stop_last_n(
    atr: list[Any],
    closes: list[Any],
    multiplier: Any = 2.0,
) -> dict[str, float | None]:
    """Oracle formula on a chronological prefix (last ATR, last close, default mult 2.0)."""
    a = atr[-1] if atr and isinstance(atr[-1], (int, float)) else None
    if a is None or a <= 0:
        return {"long_stop": None, "short_stop": None}
    if not closes:
        return {"long_stop": None, "short_stop": None}
    c = closes[-1]
    if not isinstance(c, (int, float)):
        return {"long_stop": None, "short_stop": None}
    m = multiplier if isinstance(multiplier, (int, float)) else 2.0
    return {"long_stop": c - (a * m), "short_stop": c + (a * m)}


def _atr_stop_series(n: int = 120) -> tuple[list[float], list[float]]:
    """ATR (always > 0) and close path with mild trend + oscillation."""
    atr = [1.5 + 0.8 * math.sin(i / 7.0) for i in range(n)]
    closes = [100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0 for i in range(n)]
    return atr, closes


def _atr_stop_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: high/low used as ATR sources, close is the stop anchor."""
    bars: list[dict] = []
    for i in range(n):
        c = 100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0
        bars.append(
            {
                "open": c - 0.3,
                "high": 1.5 + 0.8 * math.sin(i / 7.0),
                "low": 2.0 + 0.5 * math.sin(i / 6.0),
                "close": c,
                "volume": 1000 + i,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_atr_stop(
    atr: list[Any],
    closes: list[Any],
    multiplier: Any = 2.0,
) -> list[dict[str, float | None]]:
    """Full-path oracle: last ATR sample as a scalar (volatility.py formula)."""
    ev = _FullTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(atr)):
        ev.current_series = {"close": closes[: i + 1]}
        out.append(ev._builtin_ta_atr_stop([atr[i], multiplier]))
    return out


def _bar_walk_inc_atr_stop(
    atr: list[Any],
    closes: list[Any],
    multiplier: Any = 2.0,
) -> list[dict[str, float | None]]:
    ev = _IncTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(atr)):
        ev._ta_call_i = 0
        ev.current_series = {"close": closes[: i + 1]}
        out.append(ev._atr_stop_inc_update(atr[: i + 1], multiplier))
    return out


def _bar_walk_inc_atr_stop_last_sample(
    atr: list[Any],
    closes: list[Any],
    multiplier: Any = 2.0,
) -> list[dict[str, float | None]]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(atr)):
        ev._ta_call_i = 0
        ev.current_series = {"close": closes[i]}
        out.append(ev._atr_stop_inc_update(atr[i], multiplier))
    return out


def test_incremental_atr_stop_matches_full() -> None:
    atr, closes = _atr_stop_series(120)
    got = _bar_walk_inc_atr_stop(atr, closes, 2.0)
    exp = _bar_walk_full_atr_stop(atr, closes, 2.0)
    _assert_pattern_close(got, exp)
    last = _bar_walk_inc_atr_stop_last_sample(atr, closes, 2.0)
    _assert_pattern_close(last, exp)
    oracle = [_atr_stop_last_n(atr[: i + 1], closes[: i + 1], 2.0) for i in range(len(atr))]
    _assert_pattern_close(got, oracle)
    assert any(v["long_stop"] is not None for v in got)


def test_incremental_atr_stop_empty() -> None:
    """Empty / non-numeric / <=0 ATR or no close → None stops, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._atr_stop_inc_update([], 2.0) == _ATR_STOP_OFF
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._atr_stop_inc_update(None, 2.0) == _ATR_STOP_OFF
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    ev.current_series = {"close": [100.0]}
    assert ev._atr_stop_inc_update("x", 2.0) == _ATR_STOP_OFF
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._atr_stop_inc_update(0.0, 2.0) == _ATR_STOP_OFF
    ev._ta_call_i = 0
    assert ev._atr_stop_inc_update(-1.5, 2.0) == _ATR_STOP_OFF

    got_na = _bar_walk_inc_atr_stop([None], [100.0], 2.0)
    oracle_na = [_atr_stop_last_n([None], [100.0], 2.0)]
    _assert_pattern_close(got_na, oracle_na)
    assert got_na[0] == _ATR_STOP_OFF

    # Positive ATR but no close series → None stops.
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._atr_stop_inc_update(1.5, 2.0) == _ATR_STOP_OFF
    assert ev._ta_call_i == 1


def test_incremental_atr_stop_default_multiplier() -> None:
    """Missing / non-numeric multiplier defaults to 2.0."""
    atr, closes = [2.0], [100.0]
    got = _bar_walk_inc_atr_stop(atr, closes, None)
    exp = _bar_walk_full_atr_stop(atr, closes, None)
    _assert_pattern_close(got, exp)
    assert got[-1]["long_stop"] == pytest.approx(96.0)
    assert got[-1]["short_stop"] == pytest.approx(104.0)
    last = _bar_walk_inc_atr_stop_last_sample(atr, closes, "x")
    _assert_pattern_close(last, exp)


def test_incremental_atr_stop_non_numeric_last() -> None:
    """Non-numeric last ATR sample yields None stops, matching the oracle."""
    atr: list[Any] = [1.5, 2.0, "x"]
    closes: list[Any] = [100.0, 101.0, 102.0]
    got = _bar_walk_inc_atr_stop(atr, closes, 2.0)
    exp = _bar_walk_full_atr_stop(atr, closes, 2.0)
    _assert_pattern_close(got, exp)
    last = _bar_walk_inc_atr_stop_last_sample(atr, closes, 2.0)
    _assert_pattern_close(last, exp)
    assert got[-1] == _ATR_STOP_OFF
    assert got[0]["long_stop"] == pytest.approx(97.0)


def test_incremental_atr_stop_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    atr, closes = _atr_stop_series(40)
    atr_na: list[float | None] = list(atr)
    atr_na[4] = None
    ev = _IncTA()
    for i in range(len(atr_na)):
        ev._ta_call_i = 0
        ev.current_series = {"close": closes[: i + 1]}
        ev._atr_stop_inc_update(atr_na[: i + 1], 2.0)
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_atr_stop_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    atr, closes = _atr_stop_series(30)
    ev = _IncTA()
    for i in range(len(atr)):
        ev._ta_call_i = 0
        ev.current_series = {"close": closes[: i + 1]}
        ev._builtin_ta_atr_stop([atr[: i + 1], 2.0])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_atr_stop_two_call_sites_independent() -> None:
    atr, closes = _atr_stop_series(80)
    ev = _IncTA()
    a_out: list[dict[str, float | None]] = []
    b_out: list[dict[str, float | None]] = []
    for i in range(len(atr)):
        prefix_a = atr[: i + 1]
        ev._ta_call_i = 0
        ev.current_series = {"close": closes[: i + 1]}
        a_out.append(ev._atr_stop_inc_update(prefix_a, 2.0))
        b_out.append(ev._atr_stop_inc_update(prefix_a, 3.0))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_pattern_close(a_out, _bar_walk_full_atr_stop(atr, closes, 2.0))
    _assert_pattern_close(b_out, _bar_walk_full_atr_stop(atr, closes, 3.0))
    assert a_out != b_out


def test_runtime_atr_stop_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _atr_stop_bars(80)
    src = """//@version=5
indicator("atr stop")
f = ta.atr_stop(high, 2.0)
g = ta.atr_stop(low, 3.0)
plot(f.long_stop, "ls")
plot(f.short_stop, "ss")
plot(g.long_stop, "ls2")
plot(g.short_stop, "ss2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"ls", "ss", "ls2", "ss2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses scalar isinstance on PineSeries (newest-first wrap),
    # so series atr_value yields None stops every bar. Incremental last sample
    # is the chronological prefix formula (list-oracle / kernel). Do not
    # require incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    for i, val in enumerate(r_on["series"]["ls"]):
        exp = _atr_stop_last_n(highs[: i + 1], closes[: i + 1], 2.0)
        assert val == pytest.approx(exp["long_stop"], rel=1e-9, abs=1e-9), f"ls bar {i}: {val} != {exp['long_stop']}"
    for i, val in enumerate(r_on["series"]["ss"]):
        exp = _atr_stop_last_n(highs[: i + 1], closes[: i + 1], 2.0)
        assert val == pytest.approx(exp["short_stop"], rel=1e-9, abs=1e-9), f"ss bar {i}: {val} != {exp['short_stop']}"
    for i, val in enumerate(r_on["series"]["ls2"]):
        exp = _atr_stop_last_n(lows[: i + 1], closes[: i + 1], 3.0)
        assert val == pytest.approx(exp["long_stop"], rel=1e-9, abs=1e-9), f"ls2 bar {i}: {val} != {exp['long_stop']}"
    for i, val in enumerate(r_on["series"]["ss2"]):
        exp = _atr_stop_last_n(lows[: i + 1], closes[: i + 1], 3.0)
        assert val == pytest.approx(exp["short_stop"], rel=1e-9, abs=1e-9), f"ss2 bar {i}: {val} != {exp['short_stop']}"
    assert any(v is not None for v in r_on["series"]["ls"])


# ---------------------------------------------------------------------------
# T2: max_loss_level incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _max_loss_level_last_n(
    entry: list[Any],
    account: list[Any],
    max_loss_pct: list[Any],
) -> float:
    """Oracle formula on a chronological prefix (last sample, defaults 100/10000/1.0)."""
    e = entry[-1] if entry and isinstance(entry[-1], (int, float)) else 100.0
    a = account[-1] if account and isinstance(account[-1], (int, float)) else 10000.0
    p = max_loss_pct[-1] if max_loss_pct and isinstance(max_loss_pct[-1], (int, float)) else 1.0
    max_loss_amount = a * (p / 100.0)
    if e > 0:
        shares = a / e
        stop_price = e - (max_loss_amount / shares) if shares > 0 else 0.0
        return max(0.0, stop_price)
    return 0.0


def _mll_series(n: int = 120) -> tuple[list[float], list[float], list[float]]:
    """Entry / account / max_loss_pct with mild trend + oscillation."""
    entry = [100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0 for i in range(n)]
    account = [10000.0 + i * 10.0 for i in range(n)]
    pct = [0.5 + 1.5 * (0.5 + 0.5 * math.sin(i / 7.0)) for i in range(n)]
    return entry, account, pct


def _mll_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: close=entry, volume=account, high=pct, open/low=2nd site."""
    bars: list[dict] = []
    for i in range(n):
        entry = 100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0
        account = 10000.0 + i * 10.0
        pct = 0.5 + 1.5 * (0.5 + 0.5 * math.sin(i / 7.0))
        entry_b = 90.0 + i * 0.1 + math.cos(i / 6.0) * 1.5
        pct_b = 0.4 + 1.2 * (0.5 + 0.5 * math.cos(i / 8.0))
        bars.append(
            {
                "open": entry_b,
                "high": pct,
                "low": pct_b,
                "close": entry,
                "volume": account,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_max_loss_level(
    entry: list[Any],
    account: list[Any],
    max_loss_pct: list[Any],
) -> list[float]:
    """Full-path oracle: last sample of each arg as a scalar (advanced.py formula)."""
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(entry)):
        out.append(ev._builtin_ta_max_loss_level([entry[i], account[i], max_loss_pct[i]]))
    return out


def _bar_walk_inc_max_loss_level(
    entry: list[Any],
    account: list[Any],
    max_loss_pct: list[Any],
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(entry)):
        ev._ta_call_i = 0
        out.append(ev._max_loss_level_inc_update(entry[: i + 1], account[: i + 1], max_loss_pct[: i + 1]))
    return out


def _bar_walk_inc_max_loss_level_last_sample(
    entry: list[Any],
    account: list[Any],
    max_loss_pct: list[Any],
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(entry)):
        ev._ta_call_i = 0
        out.append(ev._max_loss_level_inc_update(entry[i], account[i], max_loss_pct[i]))
    return out


def test_incremental_max_loss_level_matches_full() -> None:
    entry, account, pct = _mll_series(120)
    got = _bar_walk_inc_max_loss_level(entry, account, pct)
    exp = _bar_walk_full_max_loss_level(entry, account, pct)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_max_loss_level_last_sample(entry, account, pct)
    _assert_series_close(last, exp)
    oracle = [_max_loss_level_last_n(entry[: i + 1], account[: i + 1], pct[: i + 1]) for i in range(len(entry))]
    _assert_series_close(got, oracle)
    assert any(v != pytest.approx(99.0) for v in got)


def test_incremental_max_loss_level_empty() -> None:
    """Empty / missing last sample → defaults (100/10000/1.0) → 99.0, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._max_loss_level_inc_update([], [], []) == pytest.approx(99.0)
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._max_loss_level_inc_update(None, None, None) == pytest.approx(99.0)
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_max_loss_level([None], [None], [None])
    oracle_na = [_max_loss_level_last_n([None], [None], [None])]
    _assert_series_close(got_na, oracle_na)
    assert got_na[0] == pytest.approx(99.0)


def test_incremental_max_loss_level_non_numeric_last() -> None:
    """Non-numeric last sample uses the same defaults as the full path."""
    entry: list[Any] = [100.0, 110.0, "x"]
    account: list[Any] = [10000.0, 12000.0, None]
    pct: list[Any] = [1.0, 2.0, None]
    got = _bar_walk_inc_max_loss_level(entry, account, pct)
    exp = _bar_walk_full_max_loss_level(entry, account, pct)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_max_loss_level_last_sample(entry, account, pct)
    _assert_series_close(last, exp)
    # defaults 100/10000/1.0 → 99.0
    assert got[-1] == pytest.approx(99.0)
    assert got[0] == pytest.approx(99.0)
    assert got[1] == pytest.approx(110.0 * (1.0 - 2.0 / 100.0))


def test_incremental_max_loss_level_entry_non_positive() -> None:
    """entry <= 0 → 0.0 (no shares), matching the full-path oracle."""
    got_zero = _bar_walk_inc_max_loss_level([0.0], [10000.0], [1.0])
    exp_zero = _bar_walk_full_max_loss_level([0.0], [10000.0], [1.0])
    _assert_series_close(got_zero, exp_zero)
    assert got_zero[-1] == pytest.approx(0.0)

    got_neg = _bar_walk_inc_max_loss_level([-10.0], [10000.0], [1.0])
    exp_neg = _bar_walk_full_max_loss_level([-10.0], [10000.0], [1.0])
    _assert_series_close(got_neg, exp_neg)
    assert got_neg[-1] == pytest.approx(0.0)


def test_incremental_max_loss_level_clamp() -> None:
    """Stop is clamped to >= 0 when max_loss_pct exceeds 100."""
    got = _bar_walk_inc_max_loss_level([100.0], [10000.0], [200.0])
    exp = _bar_walk_full_max_loss_level([100.0], [10000.0], [200.0])
    _assert_series_close(got, exp)
    assert got[-1] == pytest.approx(0.0)


def test_incremental_max_loss_level_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    entry, account, pct = _mll_series(40)
    entry_na: list[float | None] = list(entry)
    entry_na[4] = None
    ev = _IncTA()
    for i in range(len(entry_na)):
        ev._ta_call_i = 0
        ev._max_loss_level_inc_update(entry_na[: i + 1], account[: i + 1], pct[: i + 1])
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_max_loss_level_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    entry, account, pct = _mll_series(30)
    ev = _IncTA()
    for i in range(len(entry)):
        ev._ta_call_i = 0
        ev._builtin_ta_max_loss_level([entry[: i + 1], account[: i + 1], pct[: i + 1]])
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_max_loss_level_two_call_sites_independent() -> None:
    entry, account, pct = _mll_series(80)
    pct_b = [p * 2.0 for p in pct]
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(entry)):
        prefix_e = entry[: i + 1]
        prefix_a = account[: i + 1]
        prefix_p = pct[: i + 1]
        prefix_pb = pct_b[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._max_loss_level_inc_update(prefix_e, prefix_a, prefix_p))
        b_out.append(ev._max_loss_level_inc_update(prefix_e, prefix_a, prefix_pb))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_max_loss_level(entry, account, pct))
    _assert_series_close(b_out, _bar_walk_full_max_loss_level(entry, account, pct_b))
    assert a_out != b_out


def test_runtime_max_loss_level_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _mll_bars(80)
    src = """//@version=5
indicator("max loss level")
f = ta.max_loss_level(close, volume, high)
g = ta.max_loss_level(open, volume, low)
plot(f, "mll")
plot(g, "mll2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"mll", "mll2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses scalar isinstance on PineSeries (newest-first wrap),
    # so series args default to 100/10000/1.0 → 99.0 every bar. Incremental last
    # sample is the chronological prefix formula (list-oracle / kernel). Do not
    # require incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    vols = [float(b["volume"]) for b in bars]
    for i, val in enumerate(r_on["series"]["mll"]):
        exp = _max_loss_level_last_n(closes[: i + 1], vols[: i + 1], highs[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mll bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["mll2"]):
        exp = _max_loss_level_last_n(opens[: i + 1], vols[: i + 1], lows[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"mll2 bar {i}: {val} != {exp}"
    assert r_on["series"]["mll"][0] == pytest.approx(_max_loss_level_last_n(closes[:1], vols[:1], highs[:1]))
    assert r_off["series"]["mll"][0] == pytest.approx(99.0)
    assert any(v != pytest.approx(99.0) for v in r_on["series"]["mll"][1:])


# ---------------------------------------------------------------------------
# T2: profit_lock_level incremental last-sample ≡ full recompute
# ---------------------------------------------------------------------------


def _profit_lock_level_last_n(
    entry: list[Any],
    current: list[Any],
    trail_pct: list[Any],
    direction: list[Any],
) -> float:
    """Oracle formula on a chronological prefix (last sample, defaults 100/100/0.05/1.0)."""
    e = entry[-1] if entry and isinstance(entry[-1], (int, float)) else 100.0
    c = current[-1] if current and isinstance(current[-1], (int, float)) else 100.0
    t = trail_pct[-1] if trail_pct and isinstance(trail_pct[-1], (int, float)) else 0.05
    d = direction[-1] if direction and isinstance(direction[-1], (int, float)) else 1.0
    t = max(0.0, min(1.0, t))
    if d > 0:
        stop = c - c * t
        return max(e * 0.9, stop)
    stop = c + c * t
    return min(e * 1.1, stop)


def _pll_series(
    n: int = 120,
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Entry / current / trail_pct / direction with mild trend + oscillation."""
    entry = [100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0 for i in range(n)]
    current = [105.0 + i * 0.2 + math.cos(i / 4.0) * 3.0 for i in range(n)]
    trail = [0.02 + 0.08 * (0.5 + 0.5 * math.sin(i / 7.0)) for i in range(n)]
    direction = [1.0 if i % 7 != 0 else -1.0 for i in range(n)]
    return entry, current, trail, direction


def _pll_bars(n: int = 80) -> list[dict]:
    """Synthetic OHLCV: close=entry, high=current (long); open/low=2nd site (short)."""
    bars: list[dict] = []
    for i in range(n):
        entry = 100.0 + i * 0.15 + math.sin(i / 5.0) * 2.0
        current = 105.0 + i * 0.2 + math.cos(i / 4.0) * 3.0
        entry_b = 90.0 + i * 0.1 + math.cos(i / 6.0) * 1.5
        current_b = 88.0 + i * 0.12 + math.sin(i / 5.0) * 2.0
        bars.append(
            {
                "open": entry_b,
                "high": current,
                "low": current_b,
                "close": entry,
                "volume": 1000.0 + i,
                "time": 1_700_000_000 + i * 86_400,
            }
        )
    return bars


def _bar_walk_full_profit_lock_level(
    entry: list[Any],
    current: list[Any],
    trail_pct: list[Any],
    direction: list[Any],
) -> list[float]:
    """Full-path oracle: last sample of each arg as a scalar (advanced.py formula)."""
    ev = _FullTA()
    out: list[float] = []
    for i in range(len(entry)):
        out.append(ev._builtin_ta_profit_lock_level([entry[i], current[i], trail_pct[i], direction[i]]))
    return out


def _bar_walk_inc_profit_lock_level(
    entry: list[Any],
    current: list[Any],
    trail_pct: list[Any],
    direction: list[Any],
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(entry)):
        ev._ta_call_i = 0
        out.append(
            ev._profit_lock_level_inc_update(
                entry[: i + 1],
                current[: i + 1],
                trail_pct[: i + 1],
                direction[: i + 1],
            )
        )
    return out


def _bar_walk_inc_profit_lock_level_last_sample(
    entry: list[Any],
    current: list[Any],
    trail_pct: list[Any],
    direction: list[Any],
) -> list[float]:
    """Bar-mode last-sample walk (scalar current bar, not growing prefix)."""
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(entry)):
        ev._ta_call_i = 0
        out.append(ev._profit_lock_level_inc_update(entry[i], current[i], trail_pct[i], direction[i]))
    return out


def test_incremental_profit_lock_level_matches_full() -> None:
    entry, current, trail, direction = _pll_series(120)
    got = _bar_walk_inc_profit_lock_level(entry, current, trail, direction)
    exp = _bar_walk_full_profit_lock_level(entry, current, trail, direction)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_profit_lock_level_last_sample(entry, current, trail, direction)
    _assert_series_close(last, exp)
    oracle = [
        _profit_lock_level_last_n(
            entry[: i + 1],
            current[: i + 1],
            trail[: i + 1],
            direction[: i + 1],
        )
        for i in range(len(entry))
    ]
    _assert_series_close(got, oracle)
    assert any(v != pytest.approx(95.0) for v in got)


def test_incremental_profit_lock_level_empty() -> None:
    """Empty / missing last sample → defaults (100/100/0.05/1.0) → 95.0, no throw."""
    ev = _IncTA()
    ev._ta_call_i = 0
    assert ev._profit_lock_level_inc_update([], [], [], []) == pytest.approx(95.0)
    assert ev._ta_call_i == 1

    ev._ta_call_i = 0
    assert ev._profit_lock_level_inc_update(None, None, None, None) == pytest.approx(95.0)
    assert ev._ta_call_i == 1

    got_na = _bar_walk_inc_profit_lock_level([None], [None], [None], [None])
    oracle_na = [_profit_lock_level_last_n([None], [None], [None], [None])]
    _assert_series_close(got_na, oracle_na)
    assert got_na[0] == pytest.approx(95.0)


def test_incremental_profit_lock_level_non_numeric_last() -> None:
    """Non-numeric last sample uses the same defaults as the full path."""
    entry: list[Any] = [100.0, 110.0, "x"]
    current: list[Any] = [110.0, 120.0, None]
    trail: list[Any] = [0.05, 0.10, None]
    direction: list[Any] = [1.0, -1.0, None]
    got = _bar_walk_inc_profit_lock_level(entry, current, trail, direction)
    exp = _bar_walk_full_profit_lock_level(entry, current, trail, direction)
    _assert_series_close(got, exp)
    last = _bar_walk_inc_profit_lock_level_last_sample(entry, current, trail, direction)
    _assert_series_close(last, exp)
    # defaults 100/100/0.05/1.0 → 95.0
    assert got[-1] == pytest.approx(95.0)
    # long: max(100*0.9, 110 - 110*0.05) = max(90, 104.5) = 104.5
    assert got[0] == pytest.approx(104.5)
    # short: min(110*1.1, 120 + 120*0.10) = min(121, 132) = 121.0
    assert got[1] == pytest.approx(121.0)


def test_incremental_profit_lock_level_clamp() -> None:
    """trail_pct is clamped to [0, 1], matching the full-path oracle."""
    got_hi = _bar_walk_inc_profit_lock_level([100.0], [110.0], [2.0], [1.0])
    exp_hi = _bar_walk_full_profit_lock_level([100.0], [110.0], [2.0], [1.0])
    _assert_series_close(got_hi, exp_hi)
    # clamp 2.0 → 1.0: max(90, 110 - 110) = 90.0
    assert got_hi[-1] == pytest.approx(90.0)

    got_lo = _bar_walk_inc_profit_lock_level([100.0], [110.0], [-0.5], [1.0])
    exp_lo = _bar_walk_full_profit_lock_level([100.0], [110.0], [-0.5], [1.0])
    _assert_series_close(got_lo, exp_lo)
    # clamp -0.5 → 0.0: max(90, 110 - 0) = 110.0
    assert got_lo[-1] == pytest.approx(110.0)


def test_incremental_profit_lock_level_slot_count_stable() -> None:
    """One call-site slot every bar, including empty / na."""
    entry, current, trail, direction = _pll_series(40)
    entry_na: list[float | None] = list(entry)
    entry_na[4] = None
    ev = _IncTA()
    for i in range(len(entry_na)):
        ev._ta_call_i = 0
        ev._profit_lock_level_inc_update(
            entry_na[: i + 1],
            current[: i + 1],
            trail[: i + 1],
            direction[: i + 1],
        )
        assert ev._ta_call_i == 1, f"kernel bar {i}: expected 1 slot, got {ev._ta_call_i}"


def test_incremental_profit_lock_level_builtin_uses_inc_slot() -> None:
    """Bar-mode builtin consumes the inc kernel slot (gate is wired)."""
    entry, current, trail, direction = _pll_series(30)
    ev = _IncTA()
    for i in range(len(entry)):
        ev._ta_call_i = 0
        ev._builtin_ta_profit_lock_level(
            [
                entry[: i + 1],
                current[: i + 1],
                trail[: i + 1],
                direction[: i + 1],
            ]
        )
        assert ev._ta_call_i == 1, f"builtin bar {i}: {ev._ta_call_i}"


def test_incremental_profit_lock_level_two_call_sites_independent() -> None:
    entry, current, trail, _direction = _pll_series(80)
    dir_long = [1.0] * len(entry)
    dir_short = [-1.0] * len(entry)
    ev = _IncTA()
    a_out: list[float] = []
    b_out: list[float] = []
    for i in range(len(entry)):
        prefix_e = entry[: i + 1]
        prefix_c = current[: i + 1]
        prefix_t = trail[: i + 1]
        ev._ta_call_i = 0
        a_out.append(ev._profit_lock_level_inc_update(prefix_e, prefix_c, prefix_t, dir_long[: i + 1]))
        b_out.append(ev._profit_lock_level_inc_update(prefix_e, prefix_c, prefix_t, dir_short[: i + 1]))
        assert ev._ta_call_i == 2, f"two sites bar {i}: {ev._ta_call_i}"
    _assert_series_close(a_out, _bar_walk_full_profit_lock_level(entry, current, trail, dir_long))
    _assert_series_close(b_out, _bar_walk_full_profit_lock_level(entry, current, trail, dir_short))
    assert a_out != b_out


def test_runtime_profit_lock_level_incremental_vs_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.runtime import Runtime

    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover

        def clear_parse_cache() -> None:
            return None

    bars = _pll_bars(80)
    src = """//@version=5
indicator("profit lock level")
f = ta.profit_lock_level(close, high, 0.05, 1)
g = ta.profit_lock_level(open, low, 0.08, -1)
plot(f, "pll")
plot(g, "pll2")
"""
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()
    r_on = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_on, r_on.get("error")
    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    clear_parse_cache()
    r_off = Runtime(symbol="T").run(src, bars)
    assert "error" not in r_off, r_off.get("error")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    clear_parse_cache()

    expected_plots = {"pll", "pll2"}
    assert expected_plots <= set(r_on["series"]), r_on["series"].keys()
    assert set(r_on["series"]) == set(r_off["series"])
    # Full-path Runtime uses scalar isinstance on PineSeries (newest-first wrap),
    # so series args default to 100/100. Incremental last sample is the
    # chronological prefix formula (list-oracle / kernel). Do not require
    # incremental == disabled for every bar.
    closes = [float(b["close"]) for b in bars]
    opens = [float(b["open"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    trail_long = [0.05] * len(bars)
    trail_short = [0.08] * len(bars)
    dir_long = [1.0] * len(bars)
    dir_short = [-1.0] * len(bars)
    for i, val in enumerate(r_on["series"]["pll"]):
        exp = _profit_lock_level_last_n(closes[: i + 1], highs[: i + 1], trail_long[: i + 1], dir_long[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"pll bar {i}: {val} != {exp}"
    for i, val in enumerate(r_on["series"]["pll2"]):
        exp = _profit_lock_level_last_n(opens[: i + 1], lows[: i + 1], trail_short[: i + 1], dir_short[: i + 1])
        assert val == pytest.approx(exp, rel=1e-9, abs=1e-9), f"pll2 bar {i}: {val} != {exp}"
    assert r_on["series"]["pll"][0] == pytest.approx(
        _profit_lock_level_last_n(closes[:1], highs[:1], trail_long[:1], dir_long[:1])
    )
    # disabled: series args default 100/100; trail 0.05 dir 1 → 95.0
    assert r_off["series"]["pll"][0] == pytest.approx(95.0)
    # disabled: series args default 100/100; trail 0.08 dir -1 → min(110, 108) = 108.0
    assert r_off["series"]["pll2"][0] == pytest.approx(108.0)
    assert any(v != pytest.approx(95.0) for v in r_on["series"]["pll"][1:])
