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

"""Dual-host goldens: same-symbol request.security passthrough vs foreign-na.

Policy (no live multi-symbol feed):
- same-symbol simple OHLCV on the chart TF → chart passthrough
- foreign ticker (``NOT_THE_CHART``, ``UPVOL.NY``) → ``na`` on interpret *and* compile
- foreign + complex UDF → ``na`` (no chart-close-as-foreign)
- foreign tuple / single unpack must not invent chart OHLCV on compile
"""

from __future__ import annotations

import math

from backend.runtime import Runtime


def _bars(n: int = 24, *, step_ms: int = 86_400_000) -> list[dict]:
    """Synthetic OHLCV. Default daily spacing matches Runtime period ``D``."""
    bars: list[dict] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        lo = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "time": 1_700_000_000_000 + i * int(step_ms),
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


def _is_na(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        return bool(math.isnan(float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _series(out: dict, title: str, index: int) -> list:
    """Prefer titled key; fall back to ``plot_N`` (IR-cache may share titles)."""
    series = out.get("series") or {}
    if title in series:
        return series[title]
    key = f"plot_{index}"
    assert key in series, sorted(series)
    return series[key]


def _run_both(src: str, bars: list[dict], *, symbol: str = "AAPL") -> tuple[dict, dict]:
    rt = Runtime(symbol=symbol)
    si = rt.run(src, bars, mode="interpret")
    sc = rt.run(src, bars, mode="compile")
    assert not si.get("error"), si.get("error")
    assert not sc.get("error"), sc.get("error")
    return si, sc


class TestSameSymbolPassthrough:
    def test_tickerid_close_passthrough_both_modes(self) -> None:
        src = """//@version=6
indicator("a07_same_tickerid")
plot(request.security(syminfo.tickerid, "D", close), title="sec")
plot(close, title="c")
plot(701.0, title="id")
"""
        bars = _bars(20)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            sec = _series(out, "sec", 0)
            close = _series(out, "c", 1)
            assert any(not _is_na(x) for x in sec)
            assert abs(float(sec[-1]) - float(close[-1])) < 1e-9
            assert abs(float(sec[-1]) - float(bars[-1]["close"])) < 1e-9

    def test_empty_symbol_tuple_passthrough_both_modes(self) -> None:
        src = """//@version=6
indicator("a07_same_tuple")
[o, h, l, c] = request.security("", "D", [open, high, low, close])
plot(o, title="o")
plot(c, title="c")
plot(close, title="chart")
plot(702.0, title="id")
"""
        bars = _bars(16)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            assert abs(float(_series(out, "o", 0)[-1]) - float(bars[-1]["open"])) < 1e-9
            assert abs(float(_series(out, "c", 1)[-1]) - float(bars[-1]["close"])) < 1e-9


class TestForeignSecurityNa:
    def test_not_the_chart_close_is_na_both_modes(self) -> None:
        src = """//@version=6
indicator("a07_not_the_chart")
plot(request.security("NOT_THE_CHART", "D", close), title="bare")
plot(request.security("NOT_THE_CHART", "D", "close"), title="str")
plot(close, title="c")
plot(703.0, title="id")
"""
        bars = _bars(20)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            assert all(_is_na(x) for x in _series(out, "bare", 0))
            assert all(_is_na(x) for x in _series(out, "str", 1))
            assert any(not _is_na(x) for x in _series(out, "c", 2))

    def test_upvol_ny_close_is_na_both_modes(self) -> None:
        src = """//@version=6
indicator("a07_upvol")
plot(request.security("UPVOL.NY", "D", close), title="up")
plot(request.security("UPVOL.NY", "D", "close"), title="up2")
plot(close, title="c")
plot(704.0, title="id")
"""
        bars = _bars(20)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            assert all(_is_na(x) for x in _series(out, "up", 0))
            assert all(_is_na(x) for x in _series(out, "up2", 1))
            assert any(not _is_na(x) for x in _series(out, "c", 2))

    def test_foreign_udf_year_sum_is_na_both_modes(self) -> None:
        src = """//@version=6
indicator("a07_foreign_udf")
year_sum(src) =>
    ta.cum(src)
plot(request.security("NOT_THE_CHART", "D", year_sum(close)), title="sec")
plot(close, title="c")
plot(705.0, title="id")
"""
        bars = _bars(20)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            assert all(_is_na(x) for x in _series(out, "sec", 0))
            assert any(not _is_na(x) for x in _series(out, "c", 1))

    def test_foreign_tuple_unpack_is_na_both_modes(self) -> None:
        """Compile must not lower foreign ``[o,h,l,c]`` as chart OHLCV."""
        src = """//@version=6
indicator("a07_foreign_tuple")
[o, h, l, c] = request.security("UPVOL.NY", "D", [open, high, low, close])
plot(o, title="o")
plot(h, title="h")
plot(l, title="l")
plot(c, title="c")
plot(close, title="chart")
plot(706.0, title="id")
"""
        bars = _bars(16)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            for title, idx in (("o", 0), ("h", 1), ("l", 2), ("c", 3)):
                assert all(_is_na(x) for x in _series(out, title, idx)), title
            assert any(not _is_na(x) for x in _series(out, "chart", 4))

    def test_foreign_single_unpack_is_na_both_modes(self) -> None:
        src = """//@version=6
indicator("a07_foreign_single")
[x] = request.security("NOT_THE_CHART", "D", close)
plot(x, title="sec")
plot(close, title="c")
plot(707.0, title="id")
"""
        bars = _bars(12)
        si, sc = _run_both(src, bars)
        for out in (si, sc):
            assert all(_is_na(x) for x in _series(out, "sec", 0))
            assert any(not _is_na(x) for x in _series(out, "c", 1))

    def test_compile_foreign_unpack_emits_nan_not_chart_close(self) -> None:
        from pynescript.compiler.engine import transpile

        src = """//@version=6
indicator("a07_emit_unpack")
[o, h, l, c] = request.security("UPVOL.NY", "D", [open, high, low, close])
plot(c)
plot(708.0)
"""
        code = transpile(src)
        assert "o_arr[__bar_idx] = open_arr[__bar_idx]" not in code
        assert "c_arr[__bar_idx] = close_arr[__bar_idx]" not in code
        assert "o_arr[__bar_idx] = np.nan" in code
        assert "c_arr[__bar_idx] = np.nan" in code
