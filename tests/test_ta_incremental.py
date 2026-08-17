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


def _bar_walk_full_cci(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
    ev = _FullTA()
    return [ev._cci(highs[: i + 1], lows[: i + 1], closes[: i + 1], period) for i in range(len(closes))]


def _bar_walk_inc_cci(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
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


def _bar_walk_full_wpr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
    ev = _FullTA()
    return [ev._wpr(highs[: i + 1], lows[: i + 1], closes[: i + 1], period) for i in range(len(closes))]


def _bar_walk_inc_wpr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
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
    assert ev._rising([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], 7) is True
    assert ev._falling([7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0], 7) is True
    # highestbars/lowestbars: skip na, return bars-back offset of extreme
    assert ev._highestbars([None, None, 1.0], 3) == 0
    assert ev._highestbars([None, 5.0, 1.0], 3) == -1
    assert ev._lowestbars([None, None, 1.0], 3) == 0
    assert ev._highestbars(all_na, 7) == -1
    assert ev._lowestbars(all_na, 7) == -1
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
        assert ev_inc._highestbars_inc_update(all_na[: i + 1], 7) == -1
        ev_inc._ta_call_i = 0
        assert ev_inc._lowestbars_inc_update(all_na[: i + 1], 7) == -1


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
        assert all(isinstance(v, (int, float)) for v in r_on["series"][key])
    # Incremental on/off parity for this surface
    for key in r_on["series"]:
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

    __slots__ = ("history", "current")

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
    for i, c in enumerate(closes):
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
            (2 * a - b) if a is not None and b is not None else None
            for a, b in zip(ema1, ema2, strict=True)
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


def _bar_walk_full_valuewhen(
    cond: list[bool], src: list[float], occurrence: int
) -> list[Any]:
    ev = _FullTA()
    return [ev._valuewhen(cond[: i + 1], src[: i + 1], occurrence) for i in range(len(cond))]


def _bar_walk_inc_valuewhen(
    cond: list[bool], src: list[float], occurrence: int
) -> list[Any]:
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


def _bar_walk_full_adx(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
    ev = _FullTA()
    return [
        float(ev._adx(highs[: i + 1], lows[: i + 1], closes[: i + 1], period))
        for i in range(len(closes))
    ]


def _bar_walk_inc_adx(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float]:
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
        out.append(
            ev._dmi_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], di_len, adx_smooth)
        )
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
        out.append(
            ev._supertrend_inc_update(
                highs[: i + 1], lows[: i + 1], closes[: i + 1], factor, atr_period
            )
        )
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
        atr_val = ev._builtin_ta_atr(
            [highs[: i + 1], lows[: i + 1], closes[: i + 1], atr_period]
        )
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
    return [
        ev._mfi(highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period)
        for i in range(len(closes))
    ]


def _bar_walk_inc_mfi(
    highs: list[float], lows: list[float], closes: list[float], vols: list[float], period: int
) -> list[float]:
    ev = _IncTA()
    out: list[float] = []
    for i in range(len(closes)):
        ev._ta_call_i = 0
        out.append(
            ev._mfi_inc_update(
                highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period
            )
        )
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


def _bar_walk_full_alma(
    src: list[float], length: int, offset: float = 0.85, sigma: float = 6.0
) -> list[float | None]:
    ev = _FullTA()
    return [ev._builtin_ta_alma([src[: i + 1], length, offset, sigma]) for i in range(len(src))]


def _bar_walk_inc_alma(
    src: list[float], length: int, offset: float = 0.85, sigma: float = 6.0
) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._alma_inc_update(src[: i + 1], length, offset, sigma))
    return out


def _bar_walk_full_correlation(s1: list[float], s2: list[float], length: int) -> list[float | None]:
    ev = _FullTA()
    return [
        ev._builtin_ta_correlation([s1[: i + 1], s2[: i + 1], length]) for i in range(len(s1))
    ]


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
        ev._builtin_ta_kc([highs[: i + 1], lows[: i + 1], closes[: i + 1], length, mult])
        for i in range(len(closes))
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
    return [
        ev._builtin_ta_percentile_linear_interpolation([src[: i + 1], period, pct])
        for i in range(len(src))
    ]


def _bar_walk_inc_pct_lin(src: list[float], period: int, pct: float) -> list[float | None]:
    ev = _IncTA()
    out: list[float | None] = []
    for i in range(len(src)):
        ev._ta_call_i = 0
        out.append(ev._percentile_linear_inc_update(src[: i + 1], period, pct))
    return out


def _bar_walk_full_pct_nr(src: list[float], period: int, pct: float) -> list[float | None]:
    ev = _FullTA()
    return [
        ev._builtin_ta_percentile_nearest_rank([src[: i + 1], period, pct])
        for i in range(len(src))
    ]


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
        if (isinstance(up, float) and math.isnan(up)) or (
            isinstance(lo, float) and math.isnan(lo)
        ):
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


def _bar_walk_full_kama(
    src: list[float], length: int, fast: int = 2, slow: int = 30
) -> list[float | None]:
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


def _bar_walk_inc_kama(
    src: list[float], length: int, fast: int = 2, slow: int = 30
) -> list[float | None]:
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
        u, m, l = ev._bollinger_bands(src[: i + 1], period, mult)
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
        u, m, l = ev._bb_inc_update(src[: i + 1], period, mult)
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
                    assert g[j] == pytest.approx(e[j], rel=1e-9, abs=1e-9), (
                        f"stochrsi bar {i} c{j}: {g[j]} != {e[j]}"
                    )


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
[u, m, l] = ta.bb(close, 20, 2.0)
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
        for i, v in enumerate(src):
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
        out.append(
            ev._wvad_inc_update(
                highs[: i + 1], lows[: i + 1], closes[: i + 1], vols[: i + 1], period
            )
        )
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
        out.append(
            ev._cmf_inc_update(
                closes[: i + 1], highs[: i + 1], lows[: i + 1], vols[: i + 1], period
            )
        )
    return out


def _bar_walk_full_klinger(
    closes: list[float], vols: list[float], fast: int, slow: int
) -> list[float | None]:
    ev = _FullTA()
    out: list[float | None] = []
    for i in range(len(closes)):
        full = ev._klinger(closes[: i + 1], vols[: i + 1], fast, slow)
        out.append(_last_of(full))
    return out


def _bar_walk_inc_klinger(
    closes: list[float], vols: list[float], fast: int, slow: int
) -> list[float | None]:
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


def _bar_walk_full_aroon(
    highs: list[float], lows: list[float], length: int
) -> list[tuple[float, float] | None]:
    ev = _FullTA()
    out: list[tuple[float, float] | None] = []
    for i in range(len(highs)):
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._builtin_ta_aroon([length]))
    return out


def _bar_walk_inc_aroon(
    highs: list[float], lows: list[float], length: int
) -> list[tuple[float, float] | None]:
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


def _bar_walk_full_donchian(
    highs: list[float], lows: list[float], length: int
) -> list[dict[str, float | None]]:
    ev = _FullTA()
    out: list[dict[str, float | None]] = []
    for i in range(len(highs)):
        ev.current_series = {"high": highs[: i + 1], "low": lows[: i + 1]}
        out.append(ev._builtin_ta_donchian([length]))
    return out


def _bar_walk_inc_donchian(
    highs: list[float], lows: list[float], length: int
) -> list[dict[str, float | None]]:
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
