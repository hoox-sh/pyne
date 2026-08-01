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

"""v3/v4 bare aliases: ``security``, ``tickerid``, ``heikinashi``, etc."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.ticker import TickerInfo
from pynescript.ast.helper import parse
from pynescript.ast.helper import unparse


def test_security_bare_alias_dispatches_to_request_security():
    ev = NodeLiteralEvaluator()
    m = ev._build_builtin_map()
    assert "security" in m
    assert "request.security" in m
    # Bound methods are not necessarily identical objects; same handler name.
    assert m["security"].__func__ is m["request.security"].__func__
    # Call path (mock fallback returns a series list)
    out = m["security"](["AAPL", "D", "close"])
    assert out is not None


def test_tickerid_constructs_exchange_symbol():
    ev = NodeLiteralEvaluator()
    m = ev._build_builtin_map()
    assert "tickerid" in m
    assert m["tickerid"](["BINANCE", "BTCUSDT"]) == "BINANCE:BTCUSDT"
    assert m["tickerid"](["BTCUSDT"]) == "BTCUSDT"
    assert m["tickerid"]([]) == ""


def test_heikinashi_bare_alias():
    ev = NodeLiteralEvaluator()
    m = ev._build_builtin_map()
    assert "heikinashi" in m
    t = m["heikinashi"](["AAPL"])
    assert isinstance(t, TickerInfo)
    assert t.heikinashi_applied is True


def test_v4_script_security_tickerid_roundtrip_and_run():
    """Realistic v4 fragment: tickerid + security like CMF [Yield]."""
    source = """//@version=4
study("v4 bare aliases")
t = tickerid("BINANCE", "BTCUSDT")
c = security(t, "D", close)
plot(c)
"""
    tree = parse(source)
    again = parse(unparse(tree))
    assert repr(tree) == repr(again)

    from backend.runtime import Runtime

    ohlcv = [
        {"open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "time": 1_000_000 + i * 86_400_000}
        for i in range(20)
    ]
    result = Runtime().run(source, ohlcv)
    assert "error" not in result, result.get("error")
    assert result.get("count", 0) > 0


def test_v4_security_with_syminfo_tickerid():
    source = """//@version=4
study("security syminfo")
y = security(syminfo.tickerid, "D", close)
plot(y)
"""
    from backend.runtime import Runtime

    ohlcv = [
        {"open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "time": 1_000_000 + i * 86_400_000}
        for i in range(10)
    ]
    result = Runtime().run(source, ohlcv)
    assert "error" not in result, result.get("error")


def test_random_and_round_to_mintick_bare_aliases():
    """v4 bare ``random`` / ``round_to_mintick`` map to math.* handlers."""
    ev = NodeLiteralEvaluator()
    m = ev._build_builtin_map()
    assert "random" in m
    assert "math.random" in m
    assert m["random"].__func__ is m["math.random"].__func__
    assert "round_to_mintick" in m
    assert m["round_to_mintick"].__func__ is m["math.round_to_mintick"].__func__

    r = m["random"]([0, 10])
    assert isinstance(r, float)
    assert 0.0 <= r <= 10.0
    assert m["round_to_mintick"]([1.23456789123]) == 1.23456789


def test_offset_series_lookback():
    """Community ``offset(source, n)`` ≡ source[n] (Ichimoku lead lines)."""
    ev = NodeLiteralEvaluator()
    m = ev._build_builtin_map()
    assert "offset" in m
    # chronological list: last is current
    assert m["offset"]([[10.0, 20.0, 30.0, 40.0], 0]) == 40.0
    assert m["offset"]([[10.0, 20.0, 30.0, 40.0], 2]) == 20.0
    assert m["offset"]([[10.0, 20.0], 5]) is None


def test_random_round_offset_runtime_script():
    """Interpret path: bare random / round_to_mintick / offset do not raise."""
    from backend.runtime import Runtime

    source = """//@version=5
indicator("bare math/offset")
r = random(0, 100)
v = round_to_mintick(close)
o = offset(close, 1)
plot(r)
plot(v)
plot(o)
"""
    ohlcv = [
        {
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 102.0 + i * 0.1,
            "time": 1_000_000 + i * 86_400_000,
            "volume": 1000.0,
        }
        for i in range(15)
    ]
    result = Runtime().run(source, ohlcv, mode="interpret")
    assert not result.get("error"), result.get("error")
    assert result.get("count", 0) > 0
