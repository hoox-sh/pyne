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

"""Smoke tests for the public :mod:`pynescript.runtime` package surface.

Guards H1 package façade: import path, interpret bar-loop, and backend shim
identity so existing ``from backend.runtime import Runtime`` callers keep
working against the same implementation.
"""

from __future__ import annotations

import pytest

from pynescript.runtime import Runtime
from pynescript.runtime import host as runtime_host


def _bars(n: int = 20) -> list[dict[str, float | int]]:
    return [
        {
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0 + i,
            "time": 1_700_000_000_000 + i * 60_000,
        }
        for i in range(n)
    ]


def _is_na(value: object) -> bool:
    if value is None:
        return True
    try:
        return value != value
    except Exception:
        return False


def test_import_runtime_from_package() -> None:
    assert Runtime is runtime_host.Runtime


def test_interpret_tiny_script() -> None:
    src = """
//@version=5
indicator("pkg facade")
plot(close, "c")
"""
    out = Runtime(symbol="TEST").run(src, _bars(15), mode="interpret")
    assert "error" not in out, out.get("error")
    assert "series" in out
    series = out["series"]
    assert "c" in series
    assert len(series["c"]) == 15
    # Last bar close matches synthetic OHLCV
    assert series["c"][-1] == 100.5 + 14


def test_backend_runtime_shim_is_host_module() -> None:
    import backend.runtime as backend_rt

    assert backend_rt is runtime_host
    assert backend_rt.Runtime is Runtime


def test_historical_default_isrealtime_false_var_varip_same() -> None:
    """Default historical host: var and varip both init-once (no multi-tick)."""
    src = """
//@version=5
indicator("var varip hist")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 10
    out = Runtime(symbol="TEST").run(src, _bars(n), mode="interpret")
    assert "error" not in out, out.get("error")
    series = out["series"]
    # One visit per bar → both accumulate to n
    assert series["v"][-1] == n
    assert series["vip"][-1] == n
    assert len(series["v"]) == n
    assert len(series["vip"]) == n


def test_varip_reinit_under_realtime_last_bar_multi_tick() -> None:
    """Multi-tick last bar: varip re-inits each tick; var keeps accumulating.

    Evaluator contract when barstate.isrealtime: varip RHS re-runs each visit;
    var stays init-once. With ``v := v + 1`` / ``vip := vip + 1`` after
    ``var/varip int x = 0``, after N realtime ticks on the last bar:
    - ``v`` ends at historical_bars + N (accumulates across ticks)
    - ``vip`` ends at 1 (reset to 0 then +1 on the final tick)
    """
    src = """
//@version=5
indicator("varip rt")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 8
    ticks = 5
    out = Runtime(symbol="TEST").run(
        src,
        _bars(n),
        mode="interpret",
        realtime_last_bar=True,
        realtime_ticks=ticks,
    )
    assert "error" not in out, out.get("error")
    series = out["series"]
    # Series length still one cell per OHLCV bar (intermediate ticks discarded)
    assert len(series["v"]) == n
    assert len(series["vip"]) == n
    # Historical bars 0..n-2: one visit each → n-1 increments, then last bar N ticks
    assert series["v"][-1] == (n - 1) + ticks
    # varip re-inits to 0 on each realtime tick, then +1 → final cell is 1
    assert series["vip"][-1] == 1


def test_realtime_ticks_implies_last_bar_realtime() -> None:
    """realtime_ticks>1 enables last-bar isrealtime even without the bool flag."""
    src = """
//@version=5
indicator("rt ticks only")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 6
    ticks = 3
    out = Runtime(symbol="TEST").run(
        src,
        _bars(n),
        mode="interpret",
        realtime_ticks=ticks,
    )
    assert "error" not in out, out.get("error")
    series = out["series"]
    assert series["v"][-1] == (n - 1) + ticks
    assert series["vip"][-1] == 1


def test_realtime_last_bar_single_tick_sets_isrealtime() -> None:
    """realtime_last_bar=True with default ticks=1 still sets isrealtime on last bar.

    On the last bar alone, varip re-runs ``= 0`` then ``:= +1`` → ends at 1,
    while var keeps its historical accumulation → ends at n.
    """
    src = """
//@version=5
indicator("rt single")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 12
    bars = _bars(n)
    hist = Runtime(symbol="TEST").run(src, bars, mode="interpret")
    rt = Runtime(symbol="TEST").run(
        src, bars, mode="interpret", realtime_last_bar=True
    )
    assert "error" not in hist, hist.get("error")
    assert "error" not in rt, rt.get("error")
    # Historical: both accumulate one increment per bar
    assert hist["series"]["v"][-1] == n
    assert hist["series"]["vip"][-1] == n
    # Realtime last bar (1 tick): var still accumulates; varip re-inits then +1
    assert rt["series"]["v"][-1] == n
    assert rt["series"]["vip"][-1] == 1


def test_varip_vs_var_across_last_two_realtime_bars() -> None:
    """realtime_bars=2: multi-tick on last two bars; history before window.

    Bars ``[0, n-2)`` stay historical (one visit, isrealtime=False).
    Bars ``n-2`` and ``n-1`` each re-visit ``ticks`` times with isrealtime.
    - ``var`` accumulates across every visit
    - ``varip`` re-inits on each realtime tick → final cell per RT bar is 1
    Series length remains one sample per OHLCV bar.
    """
    src = """
//@version=5
indicator("varip two rt bars")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 8
    ticks = 3
    k = 2
    out = Runtime(symbol="TEST").run(
        src,
        _bars(n),
        mode="interpret",
        realtime_bars=k,
        realtime_ticks=ticks,
    )
    assert "error" not in out, out.get("error")
    series = out["series"]
    assert len(series["v"]) == n
    assert len(series["vip"]) == n

    # Historical bars 0..n-3: one visit each → n-k increments for both
    hist_visits = n - k
    assert series["v"][hist_visits - 1] == hist_visits
    assert series["vip"][hist_visits - 1] == hist_visits

    # First realtime bar (index n-2): var += ticks; varip final = 1
    assert series["v"][-2] == hist_visits + ticks
    assert series["vip"][-2] == 1

    # Last realtime bar: var += another ticks; varip final = 1
    assert series["v"][-1] == hist_visits + k * ticks
    assert series["vip"][-1] == 1


def test_realtime_from_bar_window() -> None:
    """realtime_from_bar sets absolute window start (same as last-2 when I=n-2)."""
    src = """
//@version=5
indicator("from bar")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 6
    ticks = 2
    from_bar = n - 2
    out = Runtime(symbol="TEST").run(
        src,
        _bars(n),
        mode="interpret",
        realtime_from_bar=from_bar,
        realtime_ticks=ticks,
    )
    assert "error" not in out, out.get("error")
    series = out["series"]
    hist_visits = from_bar
    assert series["v"][-1] == hist_visits + 2 * ticks
    assert series["vip"][-1] == 1
    assert series["vip"][-2] == 1
    # Bar before window is still historical accumulation for varip
    assert series["vip"][from_bar - 1] == hist_visits


def test_realtime_bars_default_zero_keeps_historical() -> None:
    """realtime_bars=0 (default) without other flags: pure historical path."""
    src = """
//@version=5
indicator("rt bars zero")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""
    n = 5
    out = Runtime(symbol="TEST").run(
        src, _bars(n), mode="interpret", realtime_bars=0, realtime_ticks=1
    )
    assert "error" not in out, out.get("error")
    assert out["series"]["v"][-1] == n
    assert out["series"]["vip"][-1] == n


def test_user_var_lookback_matches_host_close_cap() -> None:
    """Evaluator-created var series must honour the host 1000-sample floor.

    ``x[600]`` used to go na at 512 while ``close[600]`` stayed valid.
    """
    src = """
//@version=5
indicator("cap600")
var float x = close
plot(close[600], "c600")
plot(x[600], "x600")
"""
    n = 650
    out = Runtime(symbol="TEST").run(src, _bars(n), mode="interpret")
    assert "error" not in out, out.get("error")
    c600 = out["series"]["c600"]
    x600 = out["series"]["x600"]
    assert len(c600) == n
    for i in range(600):
        assert _is_na(c600[i]), f"close[600] warmup bar {i}"
        assert _is_na(x600[i]), f"x[600] warmup bar {i}"
    # var x = close persists bar-0 close; x[600] after 600 bars is that seed.
    seed = 100.5
    assert x600[600] == seed
    assert x600[-1] == seed
    assert c600[600] == seed
    assert c600[-1] == 100.5 + (n - 1 - 600)


def test_derived_hl2_hlc3_ohlc4_time_close_still_correct() -> None:
    """Skipping unused derived updates must not break named identifiers."""
    src = """
//@version=5
indicator("derived")
plot(hl2, "hl2")
plot(hlc3, "hlc3")
plot(ohlc4, "ohlc4")
plot(tr, "tr")
plot(time_close, "tc")
"""
    n = 8
    bars = _bars(n)
    out = Runtime(symbol="TEST").run(src, bars, mode="interpret")
    assert "error" not in out, out.get("error")
    series = out["series"]
    last = bars[-1]
    assert series["hl2"][-1] == pytest.approx((last["high"] + last["low"]) * 0.5)
    assert series["hlc3"][-1] == pytest.approx(
        (last["high"] + last["low"] + last["close"]) / 3.0
    )
    assert series["ohlc4"][-1] == pytest.approx(
        (last["open"] + last["high"] + last["low"] + last["close"]) * 0.25
    )
    prev = bars[-2]
    expect_tr = max(
        last["high"] - last["low"],
        abs(last["high"] - prev["close"]),
        abs(last["low"] - prev["close"]),
    )
    assert series["tr"][-1] == pytest.approx(expect_tr)
    assert series["tc"][-1] is not None


def test_ta_vwap_default_source_uses_live_hlc3() -> None:
    """``ta.vwap()`` defaults to hlc3 even when that identifier is absent."""
    src = """
//@version=5
indicator("vwap default")
plot(ta.vwap, "v")
"""
    bars = _bars(8)
    out = Runtime(symbol="TEST").run(src, bars, mode="interpret")
    assert "error" not in out, out.get("error")
    values = [x for x in out["series"]["v"] if x is not None]
    assert values
    # Session VWAP of typical price (hlc3), not close-only.
    cum_pv = 0.0
    cum_v = 0.0
    expect = None
    for b in bars:
        px = (b["high"] + b["low"] + b["close"]) / 3.0
        vol = float(b["volume"])
        cum_pv += px * vol
        cum_v += vol
        expect = cum_pv / cum_v if cum_v else px
    assert values[-1] == pytest.approx(expect)


def test_input_source_hl2_override_updates_derived() -> None:
    """input.source override to hl2 must see a live derived series."""
    src = """
//@version=5
indicator("src in")
src = input.source(close, "Source")
plot(src, "s")
"""
    n = 6
    bars = _bars(n)
    out = Runtime(symbol="TEST").run(
        src, bars, mode="interpret", inputs={"Source": "hl2"}
    )
    assert "error" not in out, out.get("error")
    last = bars[-1]
    expect = (last["high"] + last["low"]) * 0.5
    assert out["series"]["s"][-1] == pytest.approx(expect)


def test_indicator_skips_strategy_snapshot_but_strategy_still_events() -> None:
    """Indicators must not grow strategy series; strategies still emit events."""
    from pynescript.runtime.evaluator import CustomEvaluator

    captured: dict = {}
    real_init = CustomEvaluator.__init__

    def spy_init(self, *a, **k):  # type: ignore[no-untyped-def]
        real_init(self, *a, **k)
        captured["ev"] = self

    CustomEvaluator.__init__ = spy_init  # type: ignore[method-assign]
    try:
        ind = Runtime(symbol="TEST").run(
            '//@version=5\nindicator("i")\nplot(close, "c")\n',
            _bars(10),
            mode="interpret",
        )
        assert "error" not in ind, ind.get("error")
        st = getattr(captured["ev"], "_strategy_state", None)
        assert st is not None
        assert len(getattr(st, "_size_hist", [])) == 0
        captured.clear()
        strat_src = """
//@version=5
strategy("s")
if bar_index == 2
    strategy.entry("L", strategy.long)
plot(close, "c")
"""
        st_out = Runtime(symbol="TEST").run(strat_src, _bars(8), mode="interpret")
        assert "error" not in st_out, st_out.get("error")
        assert len(st_out.get("events") or []) >= 1
        st2 = getattr(captured["ev"], "_strategy_state", None)
        assert st2 is not None
        assert len(getattr(st2, "_size_hist", [])) == 8
    finally:
        CustomEvaluator.__init__ = real_init  # type: ignore[method-assign]
