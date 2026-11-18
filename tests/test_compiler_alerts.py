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

"""Compile-mode alert() / alertcondition() export vs interpret goldens."""

from __future__ import annotations

from typing import Any

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import clear_disk_compile_cache
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import has_numba
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime
from pynescript.runtime import host as runtime_host


clear_disk_compile_cache()


def _bars(n: int = 8) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for i in range(n):
        c = 100.0 + i
        up = i % 2 == 0
        o = c - 0.5 if up else c + 1.0
        out.append(
            {
                "time": 1_700_000_000_000 + i * 60_000,
                "open": o,
                "high": max(o, c) + 1.0,
                "low": min(o, c) - 1.0,
                "close": c,
                "volume": 1000.0 + i,
            }
        )
    return out


def _run_dual(src: str, bars: list[dict[str, float | int]]) -> tuple[dict[str, Any], dict[str, Any]]:
    clear_parse_cache()
    clear_compile_cache()
    clear_disk_compile_cache()
    runtime_host._HOST_COMPILE_CACHE.clear()
    interp = Runtime(symbol="ALRT").run(src, bars, mode="interpret")
    assert "error" not in interp, interp.get("error")
    compiled = Runtime(symbol="ALRT").run(src, bars, mode="compile")
    assert "error" not in compiled, compiled.get("error")
    return interp, compiled


def _alert_core(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": a.get("message"),
        "freq": a.get("freq"),
        "bar_index": a.get("bar_index"),
        "time": a.get("time"),
        "source": a.get("source"),
        "title": a.get("title"),
    }


class TestCompileAlertTranspile:
    def test_alert_forces_object_mode(self) -> None:
        src = """//@version=6
indicator("a")
alert("hello")
plot(close)
"""
        clear_compile_cache()
        clear_disk_compile_cache()
        code = transpile(src)
        assert "@numba.njit" not in code
        assert "__alerts" in code
        compiled = compile_script(src)
        assert compiled.object_mode is True


class TestCompileAlertsDualHost:
    def test_simple_alert_last_bar_message_present(self) -> None:
        src = """//@version=6
indicator("a")
alert("hello")
plot(close)
"""
        bars = _bars(5)
        interp, compiled = _run_dual(src, bars)
        assert compiled.get("mode") == "compile"
        assert compiled.get("object_mode") is True
        calerts = list(compiled.get("alerts") or [])
        ialerts = list(interp.get("alerts") or [])
        assert calerts, "compile must export alert() firings"
        assert any(a.get("message") == "hello" for a in calerts)
        last_i = len(bars) - 1
        assert any(a.get("bar_index") == last_i and a.get("message") == "hello" for a in calerts)
        assert [_alert_core(a) for a in calerts] == [_alert_core(a) for a in ialerts]

    def test_freq_all_vs_once_per_bar_count(self) -> None:
        src_once = """//@version=6
indicator("o")
alert("once")
alert("once")
plot(close)
"""
        src_all = """//@version=6
indicator("a")
alert("all", alert.freq_all)
alert("all", alert.freq_all)
plot(close)
"""
        bars = _bars(4)
        i_once, c_once = _run_dual(src_once, bars)
        i_all, c_all = _run_dual(src_all, bars)
        assert len(c_once.get("alerts") or []) == len(bars)
        assert len(i_once.get("alerts") or []) == len(bars)
        assert len(c_all.get("alerts") or []) == len(bars) * 2
        assert len(i_all.get("alerts") or []) == len(bars) * 2
        assert all(a.get("freq") == "once_per_bar" for a in c_once["alerts"])
        assert all(a.get("freq") == "all" for a in c_all["alerts"])

    def test_alertcondition_true_fires(self) -> None:
        src = """//@version=6
indicator("c")
alertcondition(true, "Title", "Fired")
plot(close)
"""
        bars = _bars(3)
        interp, compiled = _run_dual(src, bars)
        calerts = list(compiled.get("alerts") or [])
        ialerts = list(interp.get("alerts") or [])
        assert calerts
        assert all(a.get("source") == "alertcondition" for a in calerts)
        assert all(a.get("message") == "Fired" for a in calerts)
        assert all(a.get("title") == "Title" for a in calerts)
        assert [_alert_core(a) for a in calerts] == [_alert_core(a) for a in ialerts]

    def test_alertcondition_false_does_not_fire(self) -> None:
        src = """//@version=6
indicator("c")
alertcondition(false, "Title", "Silent")
plot(close)
"""
        interp, compiled = _run_dual(src, _bars(3))
        assert list(compiled.get("alerts") or []) == []
        assert list(interp.get("alerts") or []) == []

    def test_bar_index_and_time_populated(self) -> None:
        src = """//@version=6
indicator("t")
alert("tick")
plot(close)
"""
        bars = _bars(6)
        interp, compiled = _run_dual(src, bars)
        calerts = list(compiled.get("alerts") or [])
        assert calerts
        times = {int(b["time"]) for b in bars}
        for a in calerts:
            assert a.get("bar_index") is not None
            assert 0 <= int(a["bar_index"]) < len(bars)
            assert a.get("time") is not None
            assert int(a["time"]) in times
            assert a.get("source") == "alert"
        assert [_alert_core(a) for a in calerts] == [_alert_core(a) for a in interp.get("alerts") or []]


class TestCompileAlertsInUDF:
    """``alert()`` / ``alertcondition()`` inside a user-defined function.

    Regression: ``__emit_alert`` used to be nested inside
    ``execute_script_compiled``, so a UDF calling ``alert()`` raised
    ``NameError: name '__emit_alert' is not defined``. The helper is now
    module-scoped and shared by the bar loop and every UDF.
    """

    def test_alert_inside_udf_fires(self) -> None:
        src = """//@version=6
indicator("u")
method bullish() =>
    close > open
if bullish()
    alert("bullish", alert.freq_all)
plot(close)
"""
        interp, compiled = _run_dual(src, _bars(6))
        calerts = list(compiled.get("alerts") or [])
        ialerts = list(interp.get("alerts") or [])
        assert calerts
        assert all(a.get("message") == "bullish" for a in calerts)
        assert [_alert_core(a) for a in calerts] == [_alert_core(a) for a in ialerts]

    def test_alertcondition_inside_udf_fires(self) -> None:
        src = """//@version=6
indicator("u")
method up() =>
    close > open
if up()
    alertcondition(true, "Up", "Fired")
plot(close)
"""
        interp, compiled = _run_dual(src, _bars(6))
        calerts = list(compiled.get("alerts") or [])
        assert calerts
        assert all(a.get("source") == "alertcondition" for a in calerts)
        assert [_alert_core(a) for a in calerts] == [_alert_core(a) for a in interp.get("alerts") or []]

    def test_transpile_emits_module_level_emit_alert(self) -> None:
        src = """//@version=6
indicator("u")
method f() =>
    alert("x")
f()
plot(close)
"""
        clear_compile_cache()
        clear_disk_compile_cache()
        code = transpile(src)
        assert "__alerts = []" in code
        assert "__alert_fire_bars = {}" in code
        assert "def __emit_alert(" in code
        compiled = compile_script(src)
        assert compiled.object_mode is True


class TestCompileAlertsNumericEligible:
    def test_scripts_without_alert_return_empty_and_stay_numeric(self) -> None:
        src = """//@version=6
indicator("n")
plot(close, title="c")
"""
        clear_compile_cache()
        clear_disk_compile_cache()
        compiled_script = compile_script(src)
        if has_numba():
            assert compiled_script.object_mode is False
            assert "@numba.njit" in compiled_script.generated_code
        bars = _bars(5)
        result = Runtime(symbol="ALRT").run(src, bars, mode="compile")
        assert "error" not in result, result.get("error")
        assert list(result.get("alerts") or []) == []
        interp = Runtime(symbol="ALRT").run(src, bars, mode="interpret")
        assert list(interp.get("alerts") or []) == []


class TestAlertStateAcrossRuns:
    """Regression: object-mode module-level ``__alerts`` / ``__alert_fire_bars``
    are shared by every run of a cached ``CompiledScript``. The emitted prologue
    must rebind them per run, or alerts accumulate and the once-per-bar gate
    carries stale state across runs (cross-run leak)."""

    @staticmethod
    def _run_twice(src: str, bars: list[dict[str, float | int]], times: list[int] | None = None):
        clear_compile_cache()
        clear_disk_compile_cache()
        compiled = compile_script(src)
        assert compiled.object_mode is True
        o = [b["open"] for b in bars]
        h = [b["high"] for b in bars]
        lo = [b["low"] for b in bars]
        c = [b["close"] for b in bars]
        v = [b["volume"] for b in bars]
        t = times if times is not None else [int(b["time"]) for b in bars]
        r1 = compiled.run(o, h, lo, c, v, time=t)
        r2 = compiled.run(o, h, lo, c, v, time=t)
        return r1, r2

    def test_repeated_runs_do_not_accumulate_alerts(self) -> None:
        src = """//@version=6
indicator("rep leak")
alert("leak", alert.freq_all)
plot(close)
"""
        bars = _bars(5)
        r1, r2 = self._run_twice(src, bars)
        a1 = list(r1["__alerts"])
        a2 = list(r2["__alerts"])
        assert len(a1) == len(bars)
        assert len(a2) == len(bars), f"run 2 accumulated stale alerts: {len(a2)} != {len(bars)}"
        assert [a["bar_index"] for a in a2] == list(range(len(bars)))

    def test_once_per_bar_gate_does_not_leak_across_runs(self) -> None:
        src = """//@version=6
indicator("rep gate")
alert("once", alert.freq_once_per_bar)
plot(close)
"""
        bars = _bars(1)
        t1 = [1_700_000_000_000]
        t2 = [1_800_000_000_000]
        clear_compile_cache()
        clear_disk_compile_cache()
        compiled = compile_script(src)
        o = [bars[0]["open"]]
        h = [bars[0]["high"]]
        lo = [bars[0]["low"]]
        c = [bars[0]["close"]]
        v = [bars[0]["volume"]]
        r1 = compiled.run(o, h, lo, c, v, time=t1)
        r2 = compiled.run(o, h, lo, c, v, time=t2)
        assert [a["time"] for a in r1["__alerts"]] == t1
        assert [a["time"] for a in r2["__alerts"]] == t2, (
            "stale once-per-bar gate suppressed run 2's alert or returned run 1's event"
        )

    def test_mixed_freqs_repeat_identically(self) -> None:
        src = """//@version=6
indicator("rep mix")
alert("every", alert.freq_all)
alert("once", alert.freq_once_per_bar)
plot(close)
"""
        bars = _bars(4)
        r1, r2 = self._run_twice(src, bars)
        a1 = list(r1["__alerts"])
        a2 = list(r2["__alerts"])
        assert len(a2) == len(a1) == 2 * len(bars)
        assert [a["message"] for a in a2] == [a["message"] for a in a1]
