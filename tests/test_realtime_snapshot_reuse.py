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

"""Realtime tick snapshots: one bar-open TA/var copy, not one per tick."""

from __future__ import annotations

import pytest

from pynescript.ast.helper import parse
from pynescript.runtime import host as host_mod
from pynescript.runtime.host import Runtime


SRC = '//@version=6\nindicator("t")\nplot(ta.ema(close, 20))\n'


def _bars(n: int) -> list[dict[str, float | int]]:
    return [
        {
            "time": i * 60_000,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1.0,
        }
        for i in range(n)
    ]


def test_intermediate_ticks_reuse_bar_open_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    parse(SRC)
    calls: list[int] = []
    real = host_mod._snapshot_ta_state

    def spy(ev):
        calls.append(1)
        return real(ev)

    monkeypatch.setattr(host_mod, "_snapshot_ta_state", spy)
    result = Runtime(symbol="T").run(
        SRC,
        _bars(100),
        mode="interpret",
        realtime_last_bar=True,
        realtime_ticks=20,
    )
    assert "error" not in result, result.get("error")
    assert len(calls) == 1
