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

"""time()/time_close() must not ignore a foreign timeframe.

Chart timeframe (or no args) stays the chart bar open/close. A coarser
timeframe returns the fixed-width bucket from ``timeframe_bucket_ms``.
A finer or unknown timeframe, and session / timezone / bars-back, raise
the same runtime error on both hosts.
"""

from __future__ import annotations

import pytest

from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime


# 2024-01-01 00:00 UTC, aligned to the hour and to 15 minutes.
_T0 = 1_704_067_200_000
_STEP_15 = 15 * 60 * 1000
_HOUR = 3_600_000
_DAY = 86_400_000


def _bars_15m(n: int = 8) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for i in range(n):
        c = 100.0 + i
        out.append(
            {
                "time": _T0 + i * _STEP_15,
                "open": c,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1.0,
            }
        )
    return out


def _run(src: str, bars: list[dict[str, float]], timeframe: str | None, mode: str) -> dict:
    return Runtime(symbol="TFEE", timeframe=timeframe).run(src, bars, mode=mode)


def _detail(message: str) -> str:
    marker = "RuntimeError: "
    assert marker in message, message
    return message.split(marker, 1)[1]


def _assert_same_error(src: str, bars: list[dict[str, float]], timeframe: str | None, detail: str) -> None:
    details: list[str] = []
    for mode in ("interpret", "compile"):
        out = _run(src, bars, timeframe, mode)
        assert out.get("error"), (mode, out)
        assert out.get("error_kind") == "runtime", (mode, out)
        assert detail in out["error"], (mode, out.get("error"))
        details.append(_detail(str(out["error"])))
    assert details[0] == details[1]


def _series(src: str, bars: list[dict[str, float]], timeframe: str | None) -> dict[str, list[float]]:
    outs = [_run(src, bars, timeframe, mode) for mode in ("interpret", "compile")]
    for mode, out in zip(("interpret", "compile"), outs, strict=True):
        assert not out.get("error"), (mode, out.get("error"))
    left = {key: [float(v) for v in values] for key, values in outs[0]["series"].items()}
    right = {key: [float(v) for v in values] for key, values in outs[1]["series"].items()}
    assert left.keys() == right.keys()
    for key, values in left.items():
        assert values == right[key], (key, values, right[key])
    return left


_CHART = """//@version=6
indicator("chart time")
plot(time, "bare")
plot(time(), "call")
plot(time(""), "empty")
plot(time(timeframe.period), "period")
plot(time("15"), "same")
plot(time_close, "tc_bare")
plot(time_close(), "tc_call")
plot(time_close(""), "tc_empty")
plot(time_close(timeframe.period), "tc_period")
plot(time_close("15"), "tc_same")
"""

_HTF = """//@version=6
indicator("htf time")
plot(time, "bare")
plot(time("60"), "h")
plot(time("1H"), "h_alias")
plot(time(timeframe="60"), "h_kw")
plot(time_close("60"), "hc")
plot(time_close(timeframe="1H"), "hc_kw")
"""


def test_chart_timeframe_stays_bar_open_and_close() -> None:
    bars = _bars_15m()
    got = _series(_CHART, bars, "15")
    opens = [float(b["time"]) for b in bars]
    closes = [*opens[1:], opens[-1] + _DAY]
    for key in ("bare", "call", "empty", "period", "same"):
        assert got[key] == opens, key
    for key in ("tc_bare", "tc_call", "tc_empty", "tc_period", "tc_same"):
        assert got[key] == closes, key


def test_coarser_timeframe_returns_bucket_not_chart_open() -> None:
    bars = _bars_15m()
    got = _series(_HTF, bars, "15")
    opens = [float(b["time"]) for b in bars]
    hour = [float((_T0 + i * _STEP_15) // _HOUR * _HOUR) for i in range(len(bars))]
    assert hour[1] != opens[1]
    assert got["bare"] == opens
    assert got["h"] == hour
    assert got["h_alias"] == hour
    assert got["h_kw"] == hour
    assert got["hc"] == [v + _HOUR for v in hour]
    assert got["hc_kw"] == [v + _HOUR for v in hour]


def test_chart_equivalent_alias_is_not_rebucketed() -> None:
    """``60`` and ``1H`` on a 60-minute chart are the bar open, even if misaligned."""
    bars = []
    for i in range(4):
        t = _T0 + 15 * 60 * 1000 + i * _HOUR
        bars.append({"time": t, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0})
    src = """//@version=6
indicator("alias")
plot(time, "bare")
plot(time("60"), "same")
plot(time("1H"), "alias")
plot(time_close("60"), "tc")
plot(time("120"), "two")
"""
    got = _series(src, bars, "60")
    opens = [float(b["time"]) for b in bars]
    assert got["bare"] == opens
    assert got["same"] == opens
    assert got["alias"] == opens
    assert got["tc"] == [*opens[1:], opens[-1] + _DAY]
    two = 2 * _HOUR
    assert got["two"] == [float(int(t) // two * two) for t in opens]
    assert got["two"][0] != opens[0]


def test_default_daily_chart_rejects_intraday_timeframe() -> None:
    src = """//@version=6
indicator("daily")
plot(time("60"), "t")
"""
    _assert_same_error(src, _bars_15m(3), None, "time() cannot use timeframe '60' on this bar feed")


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ('plot(time("5"), "t")', "time() cannot use timeframe '5' on this bar feed"),
        ('plot(time_close("nope"), "t")', "time_close() cannot use timeframe 'nope' on this bar feed"),
        ('plot(time("15", "0930-1600"), "t")', "time() cannot use session on this bar feed"),
        (
            'plot(time_close(timeframe.period, "0930-1600", "America/New_York"), "t")',
            "time_close() cannot use session on this bar feed",
        ),
        (
            'plot(time("15", timezone="America/New_York"), "t")',
            "time() cannot use timezone on this bar feed",
        ),
        (
            'plot(time(timeframe.period, timeframe_bars_back=1), "t")',
            "time() cannot use timeframe_bars_back on this bar feed",
        ),
        ('plot(time(na), "t")', "time() cannot use timeframe 'na' on this bar feed"),
        ('plot(time_close(na), "t")', "time_close() cannot use timeframe 'na' on this bar feed"),
    ],
)
def test_unsupported_time_args_agree(body: str, detail: str) -> None:
    src = f'//@version=6\nindicator("t")\n{body}\n'
    _assert_same_error(src, _bars_15m(3), "15", detail)


def test_bare_time_does_not_call_the_bucket_helper() -> None:
    code = transpile('//@version=6\nindicator("t")\nplot(time)\nplot(time())\nplot(time_close)\nplot(time_close())\n')
    assert "pine_time_call" not in code
    assert "time_arr[__bar_idx]" in code
    assert "time_close_arr" in code


def test_foreign_time_lowers_to_shared_helper() -> None:
    code = transpile('//@version=6\nindicator("t")\nplot(time("60"))\nplot(time_close("60"))\n')
    assert code.count("pine_time_call") == 2
