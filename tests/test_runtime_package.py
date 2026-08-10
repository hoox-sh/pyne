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
