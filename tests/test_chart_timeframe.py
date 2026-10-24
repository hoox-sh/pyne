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

"""``Runtime(timeframe=...)`` drives ``timeframe.*`` on both hosts."""

from __future__ import annotations

import pytest

from pynescript.ast.helper import clear_parse_cache
from pynescript.compiler.engine import clear_compile_cache
from pynescript.runtime import Runtime


_T0_MS = 1_704_067_200_000

_SRC = """
//@version=6
indicator("chart tf")
plot(timeframe.in_seconds(), "sec")
plot(timeframe.in_seconds(timeframe.period), "sec_period")
plot(timeframe.in_seconds("240"), "sec_240")
plot(timeframe.multiplier, "mult")
plot(timeframe.isintraday ? 1 : 0, "intraday")
plot(timeframe.isseconds ? 1 : 0, "seconds")
plot(timeframe.isminutes ? 1 : 0, "minutes")
plot(timeframe.isdaily ? 1 : 0, "daily")
plot(timeframe.isweekly ? 1 : 0, "weekly")
plot(timeframe.isdwm ? 1 : 0, "dwm")
plot(str.length(timeframe.period), "period_len")
plot(timeframe.period == "15" ? 1 : 0, "period_15")
plot(timeframe.in_seconds(timeframe.from_seconds(900)), "from_900")
"""

#: period ? expected last value of every plot above
_EXPECTED = {
    "30S": {
        "sec": 30, "sec_period": 30, "sec_240": 14400, "mult": 30, "intraday": 1, "seconds": 1,
        "minutes": 0, "daily": 0, "weekly": 0, "dwm": 0, "period_len": 3, "period_15": 0, "from_900": 900,
    },
    "15": {
        "sec": 900, "sec_period": 900, "sec_240": 14400, "mult": 15, "intraday": 1, "seconds": 0,
        "minutes": 1, "daily": 0, "weekly": 0, "dwm": 0, "period_len": 2, "period_15": 1, "from_900": 900,
    },
    "D": {
        "sec": 86400, "sec_period": 86400, "sec_240": 14400, "mult": 1, "intraday": 0, "seconds": 0,
        "minutes": 0, "daily": 1, "weekly": 0, "dwm": 1, "period_len": 1, "period_15": 0, "from_900": 900,
    },
    "W": {
        "sec": 604800, "sec_period": 604800, "sec_240": 14400, "mult": 1, "intraday": 0, "seconds": 0,
        "minutes": 0, "daily": 0, "weekly": 1, "dwm": 1, "period_len": 1, "period_15": 0, "from_900": 900,
    },
}


def _bars(n: int = 5) -> list[dict[str, float | int]]:
    return [
        {"time": _T0_MS + i * 60_000, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
        for i in range(n)
    ]


def _last_values(period: str | None, mode: str) -> dict[str, float]:
    clear_parse_cache()
    out = Runtime(symbol="TF", timeframe=period).run(_SRC, _bars(), mode=mode)
    assert "error" not in out, out.get("error")
    return {key: float(series[-1]) for key, series in out["series"].items()}


@pytest.mark.parametrize("period", sorted(_EXPECTED))
@pytest.mark.parametrize("mode", ["interpret", "compile"])
def test_chart_timeframe_drives_timeframe_namespace(period: str, mode: str) -> None:
    clear_compile_cache()
    assert _last_values(period, mode) == pytest.approx(_EXPECTED[period])


def test_compiled_script_follows_timeframe_of_each_run() -> None:
    """One cached compile serves every timeframe: nothing chart-specific is baked in."""
    clear_compile_cache()
    assert _last_values("15", "compile")["sec"] == 900
    assert _last_values("D", "compile")["sec"] == 86400
    assert _last_values("30S", "compile")["sec"] == 30


def test_default_timeframe_is_daily_on_both_hosts() -> None:
    clear_compile_cache()
    for mode in ("interpret", "compile"):
        values = _last_values(None, mode)
        assert values["sec"] == 86400
        assert values["daily"] == 1
        assert values["intraday"] == 0
        assert values["mult"] == 1


def test_literal_in_seconds_stays_constant() -> None:
    """A literal frame folds to a number; no run-time chart lookup is emitted."""
    from pynescript.compiler.engine import transpile

    code = transpile('//@version=6\nindicator("x")\nplot(timeframe.in_seconds("60"), "s")\n')
    assert "3600.0" in code
    assert "chart_timeframe" not in code
