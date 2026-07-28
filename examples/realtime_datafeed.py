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

"""Example: Using the CCXT Pro realtime datafeed.

Requires:
    pip install ccxt

Run:
    python examples/realtime_datafeed.py
"""

from __future__ import annotations

import asyncio

from pynescript.util.datafeed import get_datafeed


async def stream_ohlcv():
    """Stream live 1-minute candles for BTC/USDT on Binance."""
    feed = get_datafeed("ccxtpro", exchange="binance")

    print("Streaming OHLCV (BTC/USDT 1m) - press Ctrl+C to stop")
    count = 0
    try:
        async with feed:
            async for candle in feed.watch_ohlcv("BTC/USDT", "1m"):
                print(f"Candle: {candle}")
                count += 1
                if count >= 3:  # demo: stop after a few updates
                    break
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:  # noqa: BLE001 - top level demo
        print(f"Error: {e}")


async def stream_trades():
    """Stream live trades."""
    feed = get_datafeed("ccxtpro", exchange="binance")

    print("Streaming trades (ETH/USDT) - 5 updates")
    count = 0
    async with feed:
        async for trade in feed.watch_trades("ETH/USDT"):
            print(f"Trade: {trade}")
            count += 1
            if count >= 5:
                break


if __name__ == "__main__":
    # Run one of the examples
    asyncio.run(stream_ohlcv())
    # asyncio.run(stream_trades())
