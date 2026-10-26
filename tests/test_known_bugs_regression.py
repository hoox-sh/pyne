# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Regression locks for bugs found during the coverage campaign.

Formerly xfail locks; both defects are fixed — keep the assertions as
permanent guards against regressions.
"""

from __future__ import annotations

from pynescript.ast.evaluator.builtins.ticker import ticker_new
from pynescript.runtime import Runtime


def _bars(n: int = 5) -> list[dict]:
    return [
        {
            "time": i * 60_000,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 1.0,
        }
        for i in range(n)
    ]


def test_bug_ticker_new_prefix_ticker_positional() -> None:
    """TradingView ``ticker.new(syminfo.prefix, syminfo.ticker)`` two-arg form.

    ``ticker.new(prefix, ticker)`` joins to ``PREFIX:TICKER`` (same as
    ``tickerid``), so ``request.security`` on a matching chart returns values.
    """
    info = ticker_new("NASDAQ", "AAPL")
    symbol = getattr(info, "symbol", None) or (info.get("symbol") if isinstance(info, dict) else None)
    assert symbol == "NASDAQ:AAPL"

    src = """//@version=6
indicator("t")
t = ticker.new(syminfo.prefix, syminfo.ticker)
plot(request.security(t, timeframe.period, close), "c")
"""
    out = Runtime(symbol="NASDAQ:AAPL").run(src, _bars(), mode="interpret")
    assert "error" not in out or not out.get("error")
    series = (out.get("series") or {}).get("c") or []
    assert series and series[-1] is not None


def test_bug_compile_mode_swallows_parse_errors() -> None:
    """Garbage source must fail in compile mode the same way as interpret."""
    bars = _bars(3)
    bad = "@@@not pine"
    inter = Runtime().run(bad, bars, mode="interpret")
    comp = Runtime().run(bad, bars, mode="compile")
    assert inter.get("error_kind") == "parse"
    assert comp.get("error_kind") == "parse"
    assert comp.get("error")
    # must not look like a successful plot run
    series = comp.get("series") or {}
    plot_keys = [k for k in series if not str(k).startswith("__")]
    assert not plot_keys
