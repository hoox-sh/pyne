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

"""Round 8 Agent 11 — Runtime host packing parity (interpret ↔ compile).

Guards:
- Shared OHLCV/time packing defaults (volume 1.0, synthetic time, OHLC 0.0)
- Compile series envelope keys match interpret surface
- Auto mode never falls back on successful compile to paper over value drift
"""

from __future__ import annotations

import math

import pytest

from backend.runtime import (
    Runtime,
    _coerce_time_cell,
    _coerce_volume_cell,
    _ohlcv_dicts_to_arrays,
    _ohlcv_pack_cached,
    _ohlcv_times_to_array,
    _pack_ohlcv_columns,
    _parse_script_header_fields,
)


def _bars_full(n: int = 30) -> list[dict]:
    return [
        {
            "open": float(100 + i),
            "high": float(101 + i),
            "low": float(99 + i),
            "close": float(100.5 + i),
            "volume": float(10 + i),
            "time": int(1_700_000_000_000 + i * 86_400_000),
        }
        for i in range(n)
    ]


def _bars_missing_vol_time(n: int = 12) -> list[dict]:
    """OHLC only — host packing must apply shared volume/time defaults."""
    return [
        {
            "open": float(1 + i),
            "high": float(2 + i),
            "low": float(0.5 + i),
            "close": float(1.5 + i),
        }
        for i in range(n)
    ]


class TestSharedOhlcvPacking:
    def test_volume_default_is_one_not_zero(self) -> None:
        cols = _pack_ohlcv_columns(_bars_missing_vol_time(3))
        _o, _h, _l, _c, v, _t = cols
        assert v == [1.0, 1.0, 1.0]
        assert _coerce_volume_cell(None) == 1.0
        assert _coerce_volume_cell(0) == 0.0  # explicit zero kept

    def test_time_synthetic_matches_engine_contract(self) -> None:
        cols = _pack_ohlcv_columns(_bars_missing_vol_time(4))
        times = cols[5]
        assert times == [0.0, 60_000.0, 120_000.0, 180_000.0]
        assert _coerce_time_cell(None, 2) == 120_000.0
        assert _coerce_time_cell("bad", 1) == 60_000.0
        assert _coerce_time_cell(1_700_000_000_000, 99) == 1_700_000_000_000.0

    def test_none_volume_and_time_cells(self) -> None:
        rows = [
            {
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": None,
                "time": None,
            }
            for _ in range(3)
        ]
        _o, _h, _l, _c, v, t = _pack_ohlcv_columns(rows)
        assert v == [1.0, 1.0, 1.0]
        assert t == [0.0, 60_000.0, 120_000.0]

    def test_numpy_pack_matches_python_columns(self) -> None:
        rows = _bars_full(8)
        o, h, l, c, v, t = _pack_ohlcv_columns(rows)
        ao, ah, al, ac, av = _ohlcv_dicts_to_arrays(rows)
        at = _ohlcv_times_to_array(rows)
        packed = _ohlcv_pack_cached(rows)
        assert packed[0].tolist() == pytest.approx(o)
        assert ao.tolist() == pytest.approx(o)
        assert ah.tolist() == pytest.approx(h)
        assert al.tolist() == pytest.approx(l)
        assert ac.tolist() == pytest.approx(c)
        assert av.tolist() == pytest.approx(v)
        assert at.tolist() == pytest.approx(t)
        assert packed[5].tolist() == pytest.approx(t)

    def test_pack_cache_hit_same_list(self) -> None:
        rows = _bars_full(5)
        a = _ohlcv_pack_cached(rows)
        b = _ohlcv_pack_cached(rows)
        assert a is b or all(x is y for x, y in zip(a, b, strict=True))


class TestInterpretCompileHostPackingParity:
    """Same script + same bars → same volume/time series under both modes."""

    def test_missing_volume_and_time_plot_parity(self) -> None:
        src = """//@version=5
indicator("pack")
plot(volume, title="v")
plot(time, title="t")
plot(close, title="c")
"""
        bars = _bars_missing_vol_time(15)
        rt = Runtime(symbol="T")
        ri = rt.run(src, bars, mode="interpret")
        rc = rt.run(src, bars, mode="compile")
        assert "error" not in ri, ri.get("error")
        assert "error" not in rc, rc.get("error")
        si, sc = ri["series"], rc["series"]
        assert list(si.keys()) == list(sc.keys()) or set(si) == set(sc)
        for key in ("v", "t", "c"):
            iv = si[key]
            cv = sc[key]
            assert len(iv) == len(cv) == len(bars)
            for i, (a, b) in enumerate(zip(iv, cv, strict=True)):
                # None ↔ nan both mean na
                if a is None or (isinstance(a, float) and math.isnan(a)):
                    assert b is None or (isinstance(b, float) and math.isnan(b)), (key, i, a, b)
                    continue
                if b is None or (isinstance(b, float) and math.isnan(b)):
                    assert a is None or (isinstance(a, float) and math.isnan(a)), (key, i, a, b)
                    continue
                assert a == pytest.approx(float(b), rel=1e-5, abs=1e-6), (key, i, a, b)

    def test_explicit_ohlcv_still_matches(self) -> None:
        src = """//@version=5
indicator("x")
plot(volume, title="v")
plot(time, title="t")
"""
        bars = _bars_full(20)
        rt = Runtime(symbol="T")
        ri = rt.run(src, bars, mode="interpret")
        rc = rt.run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for key in ("v", "t"):
            for a, b in zip(ri["series"][key], rc["series"][key], strict=True):
                assert float(a) == pytest.approx(float(b), rel=1e-9, abs=1e-9)


class TestCompileSeriesEnvelope:
    def test_header_parse(self) -> None:
        h = _parse_script_header_fields(
            '//@version=5\nindicator("My SMA", overlay=true)\nplot(close)\n'
        )
        assert h["script_name"] == "My SMA"
        assert h["script_type"] == "indicator"
        assert h["overlay"] is True
        h2 = _parse_script_header_fields('strategy("S")\nplot(close)\n')
        assert h2["script_type"] == "strategy"
        assert h2["overlay"] is True  # strategy default
        h3 = _parse_script_header_fields('indicator("Pane")\nplot(close)\n')
        assert h3["overlay"] is False

    def test_compile_envelope_keys(self) -> None:
        src = """//@version=5
indicator("Env Test", overlay=true)
plot(close, title="c")
"""
        rt = Runtime(symbol="T")
        rc = rt.run(src, _bars_full(10), mode="compile")
        assert "error" not in rc, rc.get("error")
        assert rc.get("mode") == "compile"
        assert isinstance(rc.get("plot_meta"), dict)
        assert "c" in rc["plot_meta"]
        assert rc["plot_meta"]["c"].get("kind") == "plot"
        assert rc.get("script_name") == "Env Test"
        assert rc.get("overlay") is True
        assert rc.get("script_type") == "indicator"
        assert isinstance(rc.get("inputs"), list)
        meta = rc.get("meta") or {}
        assert meta.get("script_name") == "Env Test"
        assert meta.get("overlay") is True

    def test_envelope_keys_present_both_modes(self) -> None:
        src = """//@version=5
indicator("Both", overlay=false)
plot(ta.sma(close, 5), title="sma")
"""
        bars = _bars_full(25)
        rt = Runtime(symbol="T")
        ri = rt.run(src, bars, mode="interpret")
        rc = rt.run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for key in (
            "plots",
            "series",
            "plot_meta",
            "events",
            "drawings",
            "alerts",
            "inputs",
            "count",
            "mode",
            "overlay",
            "script_name",
            "script_type",
            "meta",
        ):
            assert key in ri, f"interpret missing {key}"
            assert key in rc, f"compile missing {key}"
        assert ri["script_name"] == rc["script_name"] == "Both"
        assert ri["overlay"] is False and rc["overlay"] is False


class TestAutoDoesNotPaperOverValues:
    def test_auto_stays_on_compile_when_eligible(self) -> None:
        """Successful compile must not be swapped to interpret for 'safety'."""
        src = """//@version=5
indicator("auto")
plot(close, title="c")
"""
        r = Runtime(symbol="T").run(src, _bars_full(40), mode="auto")
        assert "error" not in r, r.get("error")
        assert r.get("auto_backend") == "compile"
        assert r.get("mode") == "compile"
        assert "compile_fallback_reason" not in r

    def test_auto_fallback_reasons_are_structural(self) -> None:
        src = """//@version=5
indicator("imp")
import user/Lib/1 as L
plot(close)
"""
        r = Runtime(symbol="T").run(src, _bars_full(5), mode="auto")
        assert r.get("auto_backend") == "interpret"
        reason = (r.get("compile_fallback_reason") or "").lower()
        assert "import" in reason
        # Must not look like a value-mismatch message
        assert "mismatch" not in reason
        assert "allclose" not in reason
