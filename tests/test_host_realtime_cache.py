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

"""Host-path regression: ``Runtime.run`` reuses the cached object-mode re-emit.

``Runtime.run(mode="compile")`` with an active realtime window re-emits a
numeric-compiled script as object mode for that window. Until e157fd14 the host
called ``compile_script(source, use_cache=False, force_object_mode=True)`` on
every run, which bypassed ``_OBJECT_MODE_RT_CACHE`` and re-transpiled once per
realtime tick.

``tests/test_engine_realtime_cache.py`` only exercises ``CompiledScript.run``,
and that path already reached the cache at a85c6cb6 — so it cannot observe the
host bypass. These tests drive ``Runtime.run`` instead, so reverting the host
wiring in ``runtime/host.py`` fails here.
"""

from __future__ import annotations

from typing import Any

from pynescript.compiler import engine
from pynescript.runtime import Runtime
from pynescript.runtime import host as host_module


# Distinctive source so the module-level host compile cache can never collide
# with another test's script hash.
_SRC = """//@version=5
indicator("host rt cache")
plot(close, "c")
"""


def _bars(n: int = 6) -> list[dict[str, Any]]:
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


def _forced_object_transpiles(monkeypatch) -> list[dict[str, Any]]:
    """Record ``_transpile_once(..., force_object_mode=True)`` calls.

    This is the observable seam, and it needs no production instrumentation:
    both the cached re-emit (``CompiledScript._object_mode_for_realtime``) and
    the pre-e157fd14 host bypass (``compile_script(..., force_object_mode=True)``,
    which forces ``use_cache=False``) funnel through ``engine._transpile_once``.
    A call count therefore distinguishes cache reuse from a fresh transpile.
    """
    calls: list[dict[str, Any]] = []
    real = engine._transpile_once

    def spy(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("force_object_mode"):
            calls.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "_transpile_once", spy)
    return calls


def setup_function() -> None:
    engine.clear_compile_cache()
    host_module._HOST_COMPILE_CACHE.clear()


def teardown_function() -> None:
    engine.clear_compile_cache()
    host_module._HOST_COMPILE_CACHE.clear()


def test_host_realtime_second_run_reuses_cached_object_mode(monkeypatch) -> None:
    """Two realtime runs of one script must emit object mode exactly once.

    Fails when ``runtime/host.py`` is reverted to
    ``compile_script(..., use_cache=False, force_object_mode=True)``: the second
    run then transpiles again (2 forced emits for 2 runs).
    """
    forced = _forced_object_transpiles(monkeypatch)
    rt = Runtime(symbol="HOSTRTCACHE")

    first = rt.run(_SRC, _bars(), mode="compile", realtime_ticks=2)
    assert "error" not in first, first.get("error")
    after_first = len(forced)
    assert after_first == 1, (
        f"first realtime run must emit object mode exactly once, got {after_first} forced transpile(s)"
    )

    second = rt.run(_SRC, _bars(), mode="compile", realtime_ticks=2)
    assert "error" not in second, second.get("error")
    assert len(forced) == after_first, (
        "second run of the same realtime script re-transpiled instead of reusing the cached "
        f"object-mode re-emit: {len(forced)} forced transpile(s) after two runs"
    )

    # Same script, same realtime window: results must stay identical whether the
    # re-emit came from the cache or from a fresh transpile.
    assert list(first["series"]["c"]) == list(second["series"]["c"])


def test_host_realtime_reemit_populates_object_mode_cache() -> None:
    """The host re-emit lands in ``_OBJECT_MODE_RT_CACHE``, not the numeric cache."""
    rt = Runtime(symbol="HOSTRTCACHE2")
    out = rt.run(_SRC, _bars(), mode="compile", realtime_ticks=2)
    assert "error" not in out, out.get("error")

    key = engine._object_mode_rt_key(engine.compile_script(_SRC).source)
    assert key in engine._OBJECT_MODE_RT_CACHE, "host path did not populate the realtime object-mode cache"
    assert engine._OBJECT_MODE_RT_CACHE[key].object_mode is True

    # The re-emit is transient: the historical compile must stay numeric.
    numeric = engine.compile_script(_SRC)
    assert numeric.object_mode is False
