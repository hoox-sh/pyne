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

"""Regression tests for the transient realtime object-mode re-emit cache.

``CompiledScript._object_mode_for_realtime`` re-emits a numeric script as
object mode for an active realtime window. It used to re-transpile on every
call (once per realtime tick). The re-emit is now backed by a small
process-wide LRU (``_OBJECT_MODE_RT_CACHE``, bounded by ``_IR_CACHE_MAX``)
keyed on the source identity plus the ``_DISK_META_VERSION`` marker.
"""

from __future__ import annotations

from pynescript.compiler import engine


_SRC = """//@version=5
indicator("rt cache slice")
plot(close, "c")
"""

# Same script with a semantically different plot input.
_SRC_ALT = _SRC.replace("close", "open")


def _bars(n: int = 6) -> list[dict[str, float]]:
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


def _spy_transpile(monkeypatch):
    calls: list[tuple] = []
    real = engine._transpile_once

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "_transpile_once", spy)
    return calls


def setup_function() -> None:
    engine.clear_compile_cache()


def teardown_function() -> None:
    engine.clear_compile_cache()


def test_realtime_reeemit_transpiles_once_then_cache_hit(monkeypatch) -> None:
    compiled = engine.compile_script(_SRC)
    assert not compiled.object_mode, "fixture script should stay numeric in compile mode"
    calls = _spy_transpile(monkeypatch)
    first = compiled._object_mode_for_realtime()
    second = compiled._object_mode_for_realtime()
    assert len(calls) == 1, "second identical call must not re-transpile"
    assert second is first
    assert first.object_mode is True


def test_changed_source_retranspiles(monkeypatch) -> None:
    base = engine.compile_script(_SRC)
    changed = engine.compile_script(_SRC_ALT)
    calls = _spy_transpile(monkeypatch)
    first = base._object_mode_for_realtime()
    second = changed._object_mode_for_realtime()
    assert len(calls) == 2
    assert first is not second
    assert first.generated_code != second.generated_code
    assert engine._object_mode_rt_key(_SRC) != engine._object_mode_rt_key(_SRC_ALT)


def test_cached_decision_matches_uncached_transpile() -> None:
    code, titles, kinds, object_mode, attrs = engine._transpile_once(_SRC, force_object_mode=True)
    compiled = engine.compile_script(_SRC)
    cached = compiled._object_mode_for_realtime()
    assert cached.generated_code == code
    assert cached.plot_titles == titles
    assert cached.plot_kinds == kinds
    assert cached.plot_attrs == attrs
    assert cached.object_mode is True
    assert object_mode is True
    # Second (cached) call returns the identical decision.
    again = compiled._object_mode_for_realtime()
    assert again.generated_code == code
    assert again.plot_titles == titles
    assert again.object_mode is True


def test_clear_compile_cache_evicts_realtime_cache(monkeypatch) -> None:
    compiled = engine.compile_script(_SRC)
    calls = _spy_transpile(monkeypatch)
    compiled._object_mode_for_realtime()
    engine.clear_compile_cache()
    compiled._object_mode_for_realtime()
    assert len(calls) == 2


def test_realtime_cache_is_bounded() -> None:
    engine.clear_compile_cache()
    for i in range(engine._IR_CACHE_MAX + 8):
        engine._cache_put(engine._OBJECT_MODE_RT_CACHE, f"synthetic-{i}", object(), engine._IR_CACHE_MAX)
    assert len(engine._OBJECT_MODE_RT_CACHE) == engine._IR_CACHE_MAX
    engine._OBJECT_MODE_RT_CACHE.clear()


def test_run_with_rt_first_reuses_transient_object_mode(monkeypatch) -> None:
    bars = _bars(6)
    compiled = engine.compile_script(_SRC)
    assert not compiled.object_mode
    calls = _spy_transpile(monkeypatch)
    out1 = compiled.run(
        [b["open"] for b in bars],
        [b["high"] for b in bars],
        [b["low"] for b in bars],
        [b["close"] for b in bars],
        [b["volume"] for b in bars],
        time=[b["time"] for b in bars],
        rt_first=len(bars) - 1,
        rt_ticks=2,
    )
    out2 = compiled.run(
        [b["open"] for b in bars],
        [b["high"] for b in bars],
        [b["low"] for b in bars],
        [b["close"] for b in bars],
        [b["volume"] for b in bars],
        time=[b["time"] for b in bars],
        rt_first=len(bars) - 1,
        rt_ticks=2,
    )
    assert calls and len(calls) == 1, "second rt_first run must hit the transient cache"
    assert "c" in out1 and "c" in out2
    assert list(out1["c"]) == list(out2["c"])
