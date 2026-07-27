# Copyright (C) 2025 jango-blockchained
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
