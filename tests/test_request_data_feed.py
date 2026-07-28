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

"""request.* uses injected data_feed (MockDataFeed sync helpers)."""

from __future__ import annotations

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.helper import parse
from pynescript.util.datafeed import MockDataFeed


def _eval(ev: NodeLiteralEvaluator, src: str):
    return ev.visit(parse(src, mode="eval").body)


class TestRequestDataFeed:
    def test_security_uses_mock_feed_ohlcv(self) -> None:
        feed = MockDataFeed(symbol="BTC/USDT", start_price=30_000.0)
        ev = NodeLiteralEvaluator(data_feed=feed)
        result = _eval(ev, 'request.security("BTC/USDT", "1m", "close")')
        # Returns a price-like series or value derived from feed closes (~30000)
        if isinstance(result, list):
            assert all(abs(float(x) - 30_000.0) < 500 for x in result)
        else:
            assert abs(float(result) - 30_000.0) < 500

    def test_currency_rate_prefers_feed_pair(self) -> None:
        feed = MockDataFeed(symbol="EUR/USD", start_price=1.12)
        ev = NodeLiteralEvaluator(data_feed=feed)
        rate = _eval(ev, 'request.currency_rate("EUR", "USD")')
        assert abs(float(rate) - 1.12) < 0.01

    def test_dividends_scales_with_feed_price(self) -> None:
        feed = MockDataFeed(symbol="AAPL", start_price=200.0)
        ev = NodeLiteralEvaluator(data_feed=feed)
        # base AAPL div 0.24 scaled by last/100
        div = _eval(ev, 'request.dividends("AAPL")')
        assert float(div) > 0.24  # scaled up vs base at 100

    def test_request_seed_stored_in_context(self) -> None:
        ev = NodeLiteralEvaluator()
        _eval(ev, "request.seed(42)")
        assert ev.context.get("request.seed") == 42
