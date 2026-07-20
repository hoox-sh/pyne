# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
