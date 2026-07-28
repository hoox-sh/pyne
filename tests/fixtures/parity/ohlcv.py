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

"""Shared synthetic OHLCV dataset for parity tests.

Generated once, imported by both the test suite and the fixture generator.
50 bars of realistic-ish price action (sinusoidal with noise).

Every consumer of this module should import ``OHLCV`` and use it as the
data argument to ``Runtime.run()``.
"""

from __future__ import annotations

import math
import random

from typing import Any


# Deterministic seed for reproducible prices
_SEED = 42
_rng = random.Random(_SEED)

N_BARS = 50


def _generate_ohlcv(n: int = N_BARS) -> list[dict[str, Any]]:
    """Return a synthetic OHLCV list with ``n`` bars.

    Starts at ~100, follows a gentle sine wave with ±2% daily noise.
    """
    bars: list[dict[str, Any]] = []
    price = 100.0
    for i in range(n):
        # Trend component: slow sine wave over the full range
        trend = 15.0 * math.sin(2.0 * math.pi * i / (n * 0.7))
        noise = _rng.gauss(0, 2.0)  # ±2% daily noise
        open_ = round(price + noise, 2)
        close_ = round(open_ + trend * 0.3 + _rng.gauss(0, 1.0), 2)
        high_ = round(max(open_, close_) + abs(_rng.gauss(0, 1.0)), 2)
        low_ = round(min(open_, close_) - abs(_rng.gauss(0, 1.0)), 2)
        # Ensure high >= low >= 0
        high_ = max(high_, low_ + 0.01)
        low_ = max(low_, 0.01)

        bars.append(
            {
                "open": open_,
                "high": high_,
                "low": low_,
                "close": close_,
                "time": 1_000_000 + i * 86_400_000,  # daily ms timestamps
            }
        )

        price = close_
    return bars


OHLCV: list[dict[str, Any]] = _generate_ohlcv()


def ohlcv_head(n: int = 5) -> None:
    """Pretty-print the first ``n`` rows (for debugging)."""
    for bar in OHLCV[:n]:
        print(
            f"t={bar['time']}  "
            f"O={bar['open']:>8.2f}  "
            f"H={bar['high']:>8.2f}  "
            f"L={bar['low']:>8.2f}  "
            f"C={bar['close']:>8.2f}"
        )


if __name__ == "__main__":
    print(f"OHLCV dataset: {len(OHLCV)} bars")
    ohlcv_head(5)
    print("...")
    ohlcv_head(3)  # last 3
