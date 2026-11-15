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

"""Compile-mode realtime multi-pass (D-04) vs interpret goldens.

Object-mode compile must honor the same ``Runtime.run`` realtime window
kwargs as interpret for ``var`` / ``varip`` / ``barstate.isrealtime`` /
``isconfirmed`` / ``once``. Numeric nopython stays historical unless the
script already forced object mode (or the host re-emits object mode for
an active realtime window).
"""

from __future__ import annotations

from typing import Any

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime


_VAR_VARIP_SRC = """
//@version=5
indicator("var varip rt")
var int v = 0
varip int vip = 0
v := v + 1
vip := vip + 1
plot(v, "v")
plot(vip, "vip")
"""

_ISREALTIME_SRC = """
//@version=5
indicator("isrealtime")
plot(barstate.isrealtime ? 1 : 0, "rt")
plot(barstate.isconfirmed ? 1 : 0, "cf")
plot(barstate.ishistory ? 1 : 0, "hist")
"""

_ONCE_RT_SRC = """
//@version=6
indicator("once rt")
var int n = 0
if barstate.isrealtime
    once
        n := n + 1
plot(n, "n")
"""


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


def _num(value: object) -> float:
    if value is None:
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def _series(out: dict[str, Any], name: str) -> list[float]:
    assert "error" not in out, out.get("error")
    assert "series" in out
    col = out["series"][name]
    return [_num(v) for v in col]


def _run(
    src: str,
    bars: list[dict[str, float | int]],
    mode: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return Runtime(symbol="TEST").run(src, bars, mode=mode, **kwargs)


def _dual(src: str, bars: list[dict[str, float | int]], **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    interp = _run(src, bars, "interpret", **kwargs)
    compiled = _run(src, bars, "compile", **kwargs)
    assert "error" not in interp, interp.get("error")
    assert "error" not in compiled, compiled.get("error")
    return interp, compiled


def test_historical_default_compile_isrealtime_false() -> None:
    """Default historical host: compile isrealtime stays false; var==varip."""
    n = 10
    bars = _bars(n)
    interp, compiled = _dual(_VAR_VARIP_SRC, bars)
    assert _series(interp, "v")[-1] == n
    assert _series(interp, "vip")[-1] == n
    assert _series(compiled, "v")[-1] == n
    assert _series(compiled, "vip")[-1] == n
    assert _series(compiled, "v") == _series(interp, "v")
    assert _series(compiled, "vip") == _series(interp, "vip")

    flags_i, flags_c = _dual(_ISREALTIME_SRC, bars)
    assert _series(flags_c, "rt") == [0.0] * n
    assert _series(flags_c, "rt") == _series(flags_i, "rt")
    assert _series(flags_c, "cf") == [1.0] * n
    assert _series(flags_c, "hist") == [1.0] * n


def test_numeric_nopython_stays_historical_without_object_features() -> None:
    """Pure numeric scripts still emit njit; no object-mode tick loop."""
    src = """
//@version=5
indicator("num")
plot(close, "c")
"""
    code = transpile(src)
    assert "@numba.njit" in code
    assert "rt_first" not in code
    assert "for __tick_i" not in code


def test_realtime_last_bar_sets_isrealtime_on_compile() -> None:
    """realtime_last_bar=True: last bar isrealtime on both hosts."""
    n = 12
    bars = _bars(n)
    interp, compiled = _dual(_ISREALTIME_SRC, bars, realtime_last_bar=True)
    rt_i = _series(interp, "rt")
    rt_c = _series(compiled, "rt")
    assert rt_i[:-1] == [0.0] * (n - 1)
    assert rt_i[-1] == 1.0
    assert rt_c == rt_i
    assert _series(compiled, "cf")[-1] == 1.0
    assert _series(compiled, "hist")[-1] == 0.0
    assert _series(compiled, "hist")[:-1] == [1.0] * (n - 1)


def test_varip_reinit_under_realtime_last_bar_multi_tick() -> None:
    """Multi-tick last bar: var commits once; varip re-inits; series length = n."""
    n = 8
    ticks = 5
    bars = _bars(n)
    interp, compiled = _dual(
        _VAR_VARIP_SRC,
        bars,
        realtime_last_bar=True,
        realtime_ticks=ticks,
    )
    for out in (interp, compiled):
        v = _series(out, "v")
        vip = _series(out, "vip")
        assert len(v) == n
        assert len(vip) == n
        assert v[-1] == n
        assert vip[-1] == 1.0
    assert _series(compiled, "v") == _series(interp, "v")
    assert _series(compiled, "vip") == _series(interp, "vip")


def test_realtime_ticks_implies_last_bar_realtime() -> None:
    """realtime_ticks>1 enables last-bar isrealtime without the bool flag."""
    n = 6
    ticks = 3
    bars = _bars(n)
    interp, compiled = _dual(_VAR_VARIP_SRC, bars, realtime_ticks=ticks)
    assert _series(compiled, "v")[-1] == n
    assert _series(compiled, "vip")[-1] == 1.0
    assert _series(compiled, "v") == _series(interp, "v")
    assert _series(compiled, "vip") == _series(interp, "vip")

    flags_i, flags_c = _dual(_ISREALTIME_SRC, bars, realtime_ticks=ticks)
    assert _series(flags_c, "rt")[-1] == 1.0
    assert _series(flags_c, "rt")[:-1] == [0.0] * (n - 1)
    assert _series(flags_c, "rt") == _series(flags_i, "rt")


def test_realtime_last_bar_single_tick_sets_isrealtime() -> None:
    """One confirmed realtime tick: var accumulates; varip re-inits then +1."""
    n = 12
    bars = _bars(n)
    hist_i, hist_c = _dual(_VAR_VARIP_SRC, bars)
    rt_i, rt_c = _dual(_VAR_VARIP_SRC, bars, realtime_last_bar=True)
    assert _series(hist_c, "v")[-1] == n
    assert _series(hist_c, "vip")[-1] == n
    assert _series(rt_c, "v")[-1] == n
    assert _series(rt_c, "vip")[-1] == 1.0
    assert _series(rt_c, "v") == _series(rt_i, "v")
    assert _series(rt_c, "vip") == _series(rt_i, "vip")
    assert _series(hist_c, "vip") == _series(hist_i, "vip")


def test_varip_vs_var_across_last_two_realtime_bars() -> None:
    """realtime_bars=2: history before window; each RT bar commits var once."""
    n = 8
    ticks = 3
    k = 2
    bars = _bars(n)
    interp, compiled = _dual(
        _VAR_VARIP_SRC,
        bars,
        realtime_bars=k,
        realtime_ticks=ticks,
    )
    hist_visits = n - k
    for out in (interp, compiled):
        v = _series(out, "v")
        vip = _series(out, "vip")
        assert len(v) == n
        assert v[hist_visits - 1] == hist_visits
        assert vip[hist_visits - 1] == hist_visits
        assert v[-2] == hist_visits + 1
        assert vip[-2] == 1.0
        assert v[-1] == hist_visits + 2
        assert vip[-1] == 1.0
    assert _series(compiled, "v") == _series(interp, "v")
    assert _series(compiled, "vip") == _series(interp, "vip")


def test_realtime_from_bar_window() -> None:
    """realtime_from_bar sets absolute window start."""
    n = 6
    ticks = 2
    from_bar = n - 2
    bars = _bars(n)
    interp, compiled = _dual(
        _VAR_VARIP_SRC,
        bars,
        realtime_from_bar=from_bar,
        realtime_ticks=ticks,
    )
    hist_visits = from_bar
    assert _series(compiled, "v")[-1] == hist_visits + 2
    assert _series(compiled, "vip")[-1] == 1.0
    assert _series(compiled, "vip")[-2] == 1.0
    assert _series(compiled, "vip")[from_bar - 1] == hist_visits
    assert _series(compiled, "v") == _series(interp, "v")
    assert _series(compiled, "vip") == _series(interp, "vip")


def test_realtime_bars_default_zero_keeps_historical() -> None:
    """realtime_bars=0 without other flags: pure historical path on compile."""
    n = 5
    bars = _bars(n)
    interp, compiled = _dual(_VAR_VARIP_SRC, bars, realtime_bars=0, realtime_ticks=1)
    assert _series(compiled, "v")[-1] == n
    assert _series(compiled, "vip")[-1] == n
    assert _series(compiled, "v") == _series(interp, "v")
    assert _series(compiled, "vip") == _series(interp, "vip")


def test_once_unconfirmed_ticks_can_refire() -> None:
    """Unconfirmed realtime ticks do not latch once; confirmed tick fires once."""
    bars_n = 6
    ticks = 4
    bars = _bars(bars_n)
    interp, compiled = _dual(
        _ONCE_RT_SRC,
        bars,
        realtime_last_bar=True,
        realtime_ticks=ticks,
    )
    n_i = _series(interp, "n")
    n_c = _series(compiled, "n")
    assert n_i[:-1] == [0.0] * (bars_n - 1)
    assert n_i[-1] == 1.0
    assert n_c == n_i


_VAR_ARRAY_PUSH_SRC = """
//@version=6
indicator("rt arr")
var a = array.new_float()
if barstate.isrealtime
    array.push(a, close)
plot(array.size(a), "sz")
"""


def test_var_array_push_rolls_back_unconfirmed_ticks_dual_host() -> None:
    """``array.push`` on a ``var`` array commits once on both hosts."""
    n = 5
    ticks = 3
    bars = _bars(n)
    interp, compiled = _dual(_VAR_ARRAY_PUSH_SRC, bars, realtime_ticks=ticks)
    expected = [0.0] * (n - 1) + [1.0]
    assert _series(interp, "sz") == expected
    assert _series(compiled, "sz") == expected
    assert _series(compiled, "sz") == _series(interp, "sz")


_VAR_NESTED_ARRAY_SRC = """
//@version=6
indicator("rt nested")
var a = array.new<array<float>>()
if array.size(a) == 0
    array.push(a, array.new_float())
if barstate.isrealtime
    array.push(array.get(a, 0), close)
plot(array.size(array.get(a, 0)), "sz")
"""


def test_var_nested_array_push_rolls_back_unconfirmed_ticks_dual_host() -> None:
    """Inner ``array.push`` on a ``var`` list-of-lists commits once on both hosts."""
    n = 5
    ticks = 3
    bars = _bars(n)
    interp, compiled = _dual(_VAR_NESTED_ARRAY_SRC, bars, realtime_ticks=ticks)
    expected = [0.0] * (n - 1) + [1.0]
    assert _series(interp, "sz") == expected
    assert _series(compiled, "sz") == expected
    assert _series(compiled, "sz") == _series(interp, "sz")


def test_object_mode_tick_snapshot_copies_inner_lists() -> None:
    """Object-mode emit copies one extra list/dict level on unconfirmed ticks."""
    code = transpile(_VAR_NESTED_ARRAY_SRC)
    assert "[__r.copy() if isinstance(__r, (list, dict)) else __r for __r in a]" in code
    assert "{__k: (__v.copy() if isinstance(__v, (list, dict)) else __v)" in code


def test_object_mode_execute_keeps_six_arg_positional() -> None:
    """Existing 6-arg execute_script_compiled calls stay valid (kwargs default)."""
    src = """
//@version=5
indicator("obj")
var label l = label.new(bar_index, close, "x")
plot(close, "c")
"""
    compiled = compile_script(src, use_cache=False)
    assert compiled.object_mode is True
    n = 4
    opens = [100.0 + i for i in range(n)]
    highs = [101.0 + i for i in range(n)]
    lows = [99.0 + i for i in range(n)]
    closes = [100.5 + i for i in range(n)]
    vols = [1000.0] * n
    times = [1_700_000_000_000 + i * 60_000 for i in range(n)]
    out = compiled.execute(opens, highs, lows, closes, vols, times)
    assert "c" in out
    assert len(out["c"]) == n


def _compiled_arrays(bars: list[dict[str, float | int]]) -> tuple[list[float], ...]:
    return (
        [float(b["open"]) for b in bars],
        [float(b["high"]) for b in bars],
        [float(b["low"]) for b in bars],
        [float(b["close"]) for b in bars],
        [float(b["volume"]) for b in bars],
        [float(b["time"]) for b in bars],
    )


def test_numeric_compiled_run_routes_realtime_to_object_mode() -> None:
    """Direct numeric CompiledScript.run must not ignore realtime kwargs."""
    compiled = compile_script(_ISREALTIME_SRC, use_cache=False)
    assert compiled.object_mode is False

    n = 8
    bars = _bars(n)
    opens, highs, lows, closes, vols, times = _compiled_arrays(bars)
    out = compiled.run(
        opens,
        highs,
        lows,
        closes,
        vols,
        time=times,
        rt_first=n - 1,
        rt_ticks=2,
    )

    assert out["rt"][-1] == 1.0
    assert list(out["rt"][:-1]) == [0.0] * (n - 1)
    assert out["cf"][-1] == 1.0
    assert out["hist"][-1] == 0.0
    # The numeric cache entry must stay numeric for later historical runs.
    assert compiled.object_mode is False
    hist = compiled.run(opens, highs, lows, closes, vols, time=times)
    assert list(hist["rt"]) == [0.0] * n
    assert list(hist["hist"]) == [1.0] * n


def test_numeric_compiled_run_varip_matches_interpret_realtime() -> None:
    """Numeric varip must re-init per realtime tick, not behave like var."""
    n = 8
    ticks = 3
    bars = _bars(n)
    interp = Runtime(symbol="TEST").run(
        _VAR_VARIP_SRC,
        bars,
        mode="interpret",
        realtime_ticks=ticks,
    )
    assert "error" not in interp, interp.get("error")
    interp_v = _series(interp, "v")
    interp_vip = _series(interp, "vip")

    compiled = compile_script(_VAR_VARIP_SRC, use_cache=False)
    assert compiled.object_mode is False
    opens, highs, lows, closes, vols, times = _compiled_arrays(bars)
    out = compiled.run(
        opens,
        highs,
        lows,
        closes,
        vols,
        time=times,
        rt_first=n - 1,
        rt_ticks=ticks,
    )

    assert out["v"][-1] == n
    assert out["vip"][-1] == 1.0
    assert list(out["v"]) == interp_v
    assert list(out["vip"]) == interp_vip
    assert compiled.object_mode is False
    hist = compiled.run(opens, highs, lows, closes, vols, time=times)
    assert hist["v"][-1] == n
    assert hist["vip"][-1] == n
