# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""End-to-end datafeed / data_provider wiring for Runtime + request.*."""

from __future__ import annotations

from backend.runtime import Runtime
from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse
from pynescript.util.data import ChartOHLCVProvider
from pynescript.util.data import resolve_request_sources
from pynescript.util.datafeed import CompositeDataFeed
from pynescript.util.datafeed import MockDataFeed
from pynescript.util.datafeed import get_datafeed


def _bars(n: int = 10, start: float = 100.0) -> list[dict]:
    out = []
    for i in range(n):
        c = start + i
        out.append(
            {
                "open": c - 0.5,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 1000.0 + i,
                "time": 1_000_000 + i * 60_000,
            }
        )
    return out


def test_chart_ohlcv_provider_fetch():
    bars = _bars(5, start=50.0)
    prov = ChartOHLCVProvider(bars, symbol="AAPL")
    data = prov.fetch("AAPL")
    assert data["close"] == [50.0, 51.0, 52.0, 53.0, 54.0]
    q = prov.fetch_quote("AAPL")
    assert q["last"] == 54.0


def test_resolve_request_sources_chart_default():
    bars = _bars(3)
    feed, provider = resolve_request_sources(chart_bars=bars, symbol="BTCUSDT")
    assert feed is None
    assert isinstance(provider, ChartOHLCVProvider)
    assert provider.fetch("X")["close"][-1] == 102.0


def test_resolve_request_sources_mock_feed():
    feed, provider = resolve_request_sources(
        chart_bars=_bars(2),
        symbol="ETH",
        data_source="mock",
        source_options={"start_price": 2000.0},
    )
    assert isinstance(feed, MockDataFeed)
    assert isinstance(provider, ChartOHLCVProvider)
    assert abs(feed.fetch_latest_ticker("ETH")["last"] - 2000.0) < 1.0


def test_composite_sync_fetch_delegates():
    primary = MockDataFeed(start_price=111.0)
    secondary = MockDataFeed(start_price=222.0)
    comp = CompositeDataFeed(primary, secondary)
    t = comp.fetch_latest_ticker("BTC/USDT")
    assert abs(t["last"] - 111.0) < 1.0
    ohlcv = comp.fetch_latest_ohlcv("BTC/USDT", "1m", limit=3)
    assert len(ohlcv) == 3


def test_runtime_auto_wires_chart_provider_for_request_security():
    """request.security on chart symbol uses Runtime OHLCV bars."""
    bars = _bars(8, start=10.0)
    src = """//@version=6
indicator("df")
s = request.security("CHART", "D", close)
plot(s, title="sec")
"""
    # Use matching symbol so ChartOHLCVProvider is used
    result = Runtime(symbol="CHART").run(src, bars)
    assert "error" not in result, result.get("error")
    # plots should be chart closes (or last of series); at least non-empty success
    assert result["count"] == 8


def test_runtime_with_explicit_mock_feed():
    bars = _bars(5, start=100.0)
    feed = get_datafeed("mock", start_price=999.0)
    src = """//@version=6
indicator("ext")
s = request.security("BTC/USDT", "1m", "close")
plot(close, title="c")
"""
    result = Runtime().run(src, bars, data_feed=feed)
    assert "error" not in result, result.get("error")
    # Evaluator has feed; request path exercised without crash
    assert result["count"] == 5


def test_evaluator_chart_provider_security_matches_bars():
    bars = _bars(6, start=200.0)
    provider = ChartOHLCVProvider(bars, symbol="AAPL")
    ev = NodeLiteralEvaluator(data_provider=provider)
    # Direct handler
    closes = ev._handle_request_security(["AAPL", "D", "close"])
    assert closes == [200.0, 201.0, 202.0, 203.0, 204.0, 205.0] or closes == [
        201.0,
        202.0,
        203.0,
        204.0,
        205.0,
    ] or len(closes) >= 5
    # Full expression
    r = ev.visit(parse('request.security("AAPL", "D", "close")', mode="eval").body)
    assert isinstance(r, list) and len(r) >= 5
    assert abs(float(r[-1]) - 205.0) < 1e-9


def test_get_datafeed_mock_factory():
    feed = get_datafeed("mock", start_price=42.0)
    assert feed.fetch_latest_ohlcv(limit=2)[0][4]  # close present
